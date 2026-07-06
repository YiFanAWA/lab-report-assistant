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
from app.modules.jobs import service as job_service
from app.modules.jobs.status import JobType
from app.modules.llm.gateway import get_evidence_card_provider
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


HANDLERS: dict[str, Callable] = {
    JobType.FETCH_URL.value: handle_fetch_url,
    JobType.PARSE_DOCUMENT.value: handle_parse_document,
    JobType.GENERATE_EVIDENCE.value: handle_generate_evidence,
}
