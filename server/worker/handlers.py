"""Worker 任务处理器。

每个 handler 接收 (db: Session, job: BackgroundJob)，使用传入的 db 执行业务。
handler 内部不创建新 Session。Worker 主循环负责创建和关闭 Session。
"""

import json
import hashlib
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.infrastructure.fetchers.http_fetcher import fetch_url, FetchError
from app.infrastructure.parsers import html_parser, pdf_parser
from app.infrastructure.parsers.dataset_parser import (
    parse_dataset,
    DatasetParseError,
    profile_to_dict,
    profile_from_dict,
)
from app.modules.jobs import service as job_service
from app.modules.jobs.status import JobType
from app.modules.llm.gateway import get_evidence_card_provider, get_analysis_plan_provider
from app.modules.sources import service as sources_service


def _parse_input(job) -> dict:
    """解析任务的 input_json。"""
    return json.loads(job.input_json)


def _source_dir(project_id: str, source_id: str) -> Path:
    """返回来源受控工作区目录。"""
    return settings.project_data_root / project_id / "sources" / source_id


def _content_type_kind(content_type: str) -> str:
    """根据 Content-Type 判断是 HTML 还是 PDF。"""
    ct = (content_type or "").lower()
    if "pdf" in ct:
        return "pdf"
    return "html"


def handle_fetch_url(db: Session, job) -> dict:
    """采集公开 URL 内容并保存到受控工作区。"""
    data = _parse_input(job)
    source_id = data.get("source_id")
    url = data.get("url")
    if not source_id or not url:
        raise AppError(code="JOB_INPUT_INVALID",
                       message="任务缺少 source_id 或 url")

    try:
        result = fetch_url(
            url=url,
            timeout_seconds=settings.source_fetch_timeout_seconds,
            max_size_bytes=settings.source_fetch_max_size_bytes,
        )
    except FetchError as err:
        sources_service.mark_source_failed(
            db, source_id, err.code, err.message)
        db.commit()
        raise
    except Exception as exc:
        sources_service.mark_source_failed(
            db, source_id, "FETCH_FAILED", str(exc))
        db.commit()
        raise FetchError("FETCH_FAILED", str(exc)) from exc

    kind = _content_type_kind(result.content_type)
    dest_dir = _source_dir(job.project_id, source_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = "raw.pdf" if kind == "pdf" else "raw.html"
    dest_path = dest_dir / filename
    with open(dest_path, "wb") as f:
        f.write(result.content)

    content_hash = hashlib.sha256(result.content).hexdigest()

    sources_service.mark_source_fetched(
        db, source_id,
        content_type=result.content_type,
        content_hash=content_hash,
        file_path=str(dest_path),
    )

    job_service.create_job(
        db,
        project_id=job.project_id,
        job_type=JobType.PARSE_DOCUMENT.value,
        input_data={"source_id": source_id},
    )

    db.commit()
    return {"file_path": str(dest_path), "content_type": result.content_type}


def handle_parse_document(db: Session, job) -> dict:
    """解析已采集来源，提取正文和元数据。"""
    data = _parse_input(job)
    source_id = data.get("source_id")
    if not source_id:
        raise AppError(code="JOB_INPUT_INVALID",
                       message="任务缺少 source_id")

    source = sources_service.get_source(db, source_id)
    file_path = source.file_path
    content_type = source.content_type or ""
    if not file_path:
        sources_service.mark_source_failed(
            db, source_id, "PARSE_FAILED", "来源未关联文件")
        db.commit()
        raise AppError(code="PARSE_FAILED", message="来源未关联文件")

    path = Path(file_path)
    if not path.exists():
        sources_service.mark_source_failed(
            db, source_id, "PARSE_FAILED", f"文件不存在：{file_path}")
        db.commit()
        raise AppError(code="PARSE_FAILED", message=f"文件不存在：{file_path}")

    try:
        content = path.read_bytes()
        kind = _content_type_kind(content_type)
        if kind == "pdf":
            parsed = pdf_parser.parse_pdf(content)
            text = parsed.text
            title = None
            metadata = {"page_count": parsed.page_count}
        else:
            if html_parser.detect_dynamic_page(content):
                raise FetchError("SOURCE_UNSUPPORTED_DYNAMIC",
                                 "检测到动态网页，建议手动上传 PDF")
            parsed = html_parser.parse_html(content)
            text = parsed.text
            title = parsed.title
            metadata = parsed.metadata

        if len(text.strip()) < 50:
            raise AppError(code="PARSE_TEXT_EMPTY",
                           message="解析后文本为空或过短")

        pd = sources_service.create_parsed_document(
            db,
            source_id=source_id,
            project_id=job.project_id,
            title=title,
            parsed_text=text,
            metadata=metadata,
        )
        sources_service.mark_source_parsed(db, source_id, pd.id)
        db.commit()
        return {"parsed_document_id": pd.id, "text_length": len(text)}
    except FetchError as err:
        sources_service.mark_source_failed(
            db, source_id, err.code, err.message)
        db.commit()
        raise
    except AppError as err:
        sources_service.mark_source_failed(
            db, source_id, err.code, err.message)
        db.commit()
        raise
    except Exception as exc:
        sources_service.mark_source_failed(
            db, source_id, "PARSE_FAILED", str(exc))
        db.commit()
        raise


def handle_generate_evidence(db: Session, job) -> dict:
    """从已解析文档生成证据卡片候选。"""
    data = _parse_input(job)
    source_id = data.get("source_id")
    parsed_document_id = data.get("parsed_document_id")
    if not source_id or not parsed_document_id:
        raise AppError(code="JOB_INPUT_INVALID",
                       message="任务缺少 source_id 或 parsed_document_id")

    from app.modules.sources.models import ParsedDocument
    pd = (
        db.query(ParsedDocument)
        .filter(ParsedDocument.id == parsed_document_id)
        .first()
    )
    if not pd:
        raise AppError(code="PARSE_TEXT_EMPTY",
                       message="未找到解析文档")

    provider = get_evidence_card_provider()
    drafts = provider.draft(pd.parsed_text)

    sources_service.save_evidence_card_drafts(
        db,
        project_id=job.project_id,
        source_id=source_id,
        parsed_document_id=parsed_document_id,
        drafts=drafts,
        candidate_source=provider.source_label(),
    )
    db.commit()
    return {"card_count": len(drafts)}


def handle_parse_dataset(db: Session, job) -> dict:
    """解析数据集文件，生成字段概览和质量检查结果。

    解析成功后自动触发 GENERATE_ANALYSIS_PLAN 任务。
    """
    data = _parse_input(job)
    dataset_id = data.get("dataset_id")
    version_id = data.get("version_id")
    file_extension = data.get("file_extension", "")
    if not dataset_id or not version_id:
        raise AppError(code="JOB_INPUT_INVALID",
                       message="任务缺少 dataset_id 或 version_id")

    from app.modules.datasets import service as dataset_service

    version = dataset_service.get_version_by_id(db, version_id)
    file_path = version.file_path
    if not file_path:
        dataset_service.mark_dataset_failed(
            db, version_id, "DATASET_PARSE_FAILED", "版本未关联文件")
        db.commit()
        raise AppError(code="DATASET_PARSE_FAILED", message="版本未关联文件")

    path = Path(file_path)
    if not path.exists():
        dataset_service.mark_dataset_failed(
            db, version_id, "DATASET_PARSE_FAILED",
            f"文件不存在：{file_path}")
        db.commit()
        raise AppError(code="DATASET_PARSE_FAILED",
                       message=f"文件不存在：{file_path}")

    # 标记为 PARSING
    dataset_service.mark_dataset_parsing(db, version_id)
    db.flush()

    try:
        result = parse_dataset(file_path, file_extension)
    except DatasetParseError as err:
        dataset_service.mark_dataset_failed(
            db, version_id, err.code, err.message)
        db.commit()
        raise
    except Exception as exc:
        dataset_service.mark_dataset_failed(
            db, version_id, "DATASET_PARSE_FAILED", str(exc))
        db.commit()
        raise AppError(code="DATASET_PARSE_FAILED",
                       message=f"解析失败：{exc}") from exc

    # 序列化 profile 并写入 DatasetVersion
    profile_dict = profile_to_dict(result.profile)
    _, dataset = dataset_service.mark_dataset_parsed(
        db,
        version_id=version_id,
        profile_data=profile_dict,
        row_count=result.profile.row_count,
        column_count=result.profile.column_count,
    )

    # 自动触发分析方案生成
    job_id = dataset_service.trigger_analysis_plan_generation(
        db,
        project_id=job.project_id,
        dataset_id=dataset_id,
        version_id=version_id,
    )

    db.commit()
    return {
        "row_count": result.profile.row_count,
        "column_count": result.profile.column_count,
        "quality_score": result.profile.quality_score,
        "analysis_plan_job_id": job_id,
    }


def handle_generate_analysis_plan(db: Session, job) -> dict:
    """基于已解析数据集生成分析方案候选。

    调用 AnalysisPlanDraftProvider 生成 cleaning/analysis/chart plan 候选，
    保存为 AnalysisPlan，并推进 project.status 到 ANALYSIS_PLANNED。
    """
    data = _parse_input(job)
    dataset_id = data.get("dataset_id")
    dataset_version_id = data.get("dataset_version_id")
    if not dataset_id or not dataset_version_id:
        raise AppError(code="JOB_INPUT_INVALID",
                       message="任务缺少 dataset_id 或 dataset_version_id")

    from app.modules.datasets import service as dataset_service
    from app.modules.analysis import service as analysis_service

    version = dataset_service.get_version_by_id(db, dataset_version_id)
    if not version.profile_json:
        raise AppError(code="DATASET_NOT_PARSED",
                       message="数据集版本未解析，无 profile 数据")

    try:
        profile_data = json.loads(version.profile_json)
    except json.JSONDecodeError as exc:
        raise AppError(code="DATASET_PARSE_FAILED",
                       message=f"profile_json 解析失败：{exc}") from exc

    profile = profile_from_dict(profile_data)

    provider = get_analysis_plan_provider()
    draft = provider.generate(profile)

    plan = analysis_service.save_analysis_plan_draft(
        db,
        project_id=job.project_id,
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
        draft=draft,
        candidate_source=provider.source_label(),
    )

    # 推进项目状态到 ANALYSIS_PLANNED
    analysis_service.advance_project_to_planned(db, job.project_id)

    db.commit()
    return {
        "plan_id": plan.id,
        "cleaning_plan_count": len(draft.cleaning_plan),
        "analysis_plan_count": len(draft.analysis_plan),
        "chart_plan_count": len(draft.chart_plan),
    }


HANDLERS: dict[str, Callable] = {
    JobType.FETCH_URL.value: handle_fetch_url,
    JobType.PARSE_DOCUMENT.value: handle_parse_document,
    JobType.GENERATE_EVIDENCE.value: handle_generate_evidence,
    JobType.PARSE_DATASET.value: handle_parse_dataset,
    JobType.GENERATE_ANALYSIS_PLAN.value: handle_generate_analysis_plan,
}
