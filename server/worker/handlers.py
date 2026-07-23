"""Worker 任务处理器。

每个 handler 接收 (db: Session, job: BackgroundJob)，使用传入的 db 执行业务。
handler 内部不创建新 Session。Worker 主循环负责创建和关闭 Session。
"""

import json
import hashlib
from datetime import datetime, timezone
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
from app.modules.llm.gateway import (
    get_evidence_card_provider,
    get_analysis_plan_provider,
    get_code_task_provider,
    get_outline_provider,
)
from app.modules.sources import service as sources_service


def _parse_input(job) -> dict:
    """解析任务的 input_json。"""
    return json.loads(job.input_json)


def _now() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


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


def handle_generate_code_task(db: Session, job) -> dict:
    """基于已确认分析方案生成代码任务候选。

    调用 CodeTaskDraftProvider 基于 AnalysisPlan 的 cleaning/analysis/chart plan
    拼装可执行 Python 代码，保存为 CodeTask（status=CANDIDATE）。

    设计决策（用户确认）：AnalysisPlan 阶段为字段截断唯一截断点，
    CodeTask 生成时直接透传已截断字段内容，提供者不做二次截断。
    """
    data = _parse_input(job)
    analysis_plan_id = data.get("analysis_plan_id")
    dataset_id = data.get("dataset_id")
    dataset_version_id = data.get("dataset_version_id")
    if not analysis_plan_id or not dataset_id or not dataset_version_id:
        raise AppError(code="JOB_INPUT_INVALID",
                       message="任务缺少 analysis_plan_id、dataset_id 或 dataset_version_id")

    from app.modules.analysis import service as analysis_service
    from app.modules.execution import service as execution_service

    plan = analysis_service.get_analysis_plan_by_project(
        db, job.project_id, analysis_plan_id)
    if plan.status != "CONFIRMED":
        raise AppError(code="ANALYSIS_PLAN_NOT_CONFIRMED",
                       message="分析方案未确认，无法生成代码任务")

    # 构建 analysis_plan dict 传给提供者
    try:
        cleaning_plan = json.loads(plan.cleaning_plan) if plan.cleaning_plan else []
        analysis_plan_items = json.loads(plan.analysis_plan) if plan.analysis_plan else []
        chart_plan = json.loads(plan.chart_plan) if plan.chart_plan else []
    except json.JSONDecodeError as exc:
        raise AppError(code="ANALYSIS_PLAN_INVALID",
                       message=f"分析方案 JSON 解析失败：{exc}") from exc

    plan_dict = {
        "cleaning_plan": cleaning_plan,
        "analysis_plan": analysis_plan_items,
        "chart_plan": chart_plan,
    }

    provider = get_code_task_provider()
    draft = provider.generate(plan_dict)

    task = execution_service.save_code_task_draft(
        db,
        project_id=job.project_id,
        analysis_plan_id=analysis_plan_id,
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
        code=draft.code,
        candidate_source=provider.source_label(),
    )

    db.commit()
    return {
        "code_task_id": task.id,
        "code_length": len(draft.code),
        "code_version": task.code_version,
    }


def handle_execute_code_task(db: Session, job) -> dict:
    """在受控环境中执行已确认代码任务。

    流程：
    1. 获取已确认 CodeTask
    2. 创建 ExecutionRun（PENDING）
    3. 标记为 RUNNING，推进 project.status 到 EXECUTING
    4. 调用 python_executor.execute_code_safe 执行
    5. 根据结果标记 SUCCEEDED 或 FAILED
    """
    data = _parse_input(job)
    code_task_id = data.get("code_task_id")
    dataset_version_id = data.get("dataset_version_id")
    code_version = data.get("code_version")
    if not code_task_id or not dataset_version_id:
        raise AppError(code="JOB_INPUT_INVALID",
                       message="任务缺少 code_task_id 或 dataset_version_id")

    from app.modules.datasets import service as dataset_service
    from app.modules.execution import service as execution_service
    from app.infrastructure.sandbox.python_executor import execute_code_safe

    task = execution_service.get_code_task_by_project(db, job.project_id, code_task_id)
    if task.status != "CONFIRMED":
        raise AppError(code="CODE_TASK_NOT_EXECUTABLE",
                       message="代码任务未确认，无法执行")

    # 获取数据集文件路径
    version = dataset_service.get_version_by_id(db, dataset_version_id)
    data_path = version.file_path
    if not data_path:
        raise AppError(code="DATASET_PARSE_FAILED",
                       message="数据集版本未关联文件")

    # 创建执行记录
    run = execution_service.create_execution_run(
        db,
        project_id=job.project_id,
        code_task_id=code_task_id,
        dataset_version_id=dataset_version_id,
        code_version=code_version or task.code_version,
    )

    # 标记为 RUNNING（推进 project.status 到 EXECUTING）
    execution_service.mark_execution_running(db, run.id)
    db.flush()

    # 准备执行工作目录
    work_dir = settings.project_data_root / job.project_id / "executions" / run.id
    work_dir.mkdir(parents=True, exist_ok=True)

    started_at = _now()
    result = execute_code_safe(
        code=task.code,
        work_dir=str(work_dir),
        data_path=data_path,
        timeout_seconds=settings.execution_timeout_seconds,
        memory_limit_mb=settings.execution_memory_limit_mb,
        output_max_bytes=settings.execution_output_max_bytes,
    )
    finished_at = _now()
    duration = (finished_at - started_at).total_seconds()

    # 转换产物为 dict 列表
    artifacts_data = [
        {
            "artifact_type": a.artifact_type,
            "file_path": a.file_path,
            "file_size_bytes": a.file_size_bytes,
            "name": a.name,
        }
        for a in result.artifacts
    ]

    if result.sandbox_error_code is None and result.exit_code == 0:
        # 执行成功
        execution_service.mark_execution_succeeded(
            db,
            run_id=run.id,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
            artifacts=artifacts_data,
        )
        db.commit()
        return {
            "run_id": run.id,
            "exit_code": result.exit_code,
            "artifact_count": len(artifacts_data),
            "duration_seconds": duration,
        }
    else:
        # 执行失败（脚本错误或沙箱限制）
        error_code = result.sandbox_error_code or "EXECUTION_SCRIPT_ERROR"
        error_message = result.stderr[:500] if result.stderr else f"脚本退出码 {result.exit_code}"
        execution_service.mark_execution_failed(
            db,
            run_id=run.id,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            error_code=error_code,
            error_message=error_message,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
            artifacts=artifacts_data,
        )
        db.commit()
        return {
            "run_id": run.id,
            "exit_code": result.exit_code,
            "error_code": error_code,
            "artifact_count": len(artifacts_data),
            "duration_seconds": duration,
        }


def _gather_outline_context(db: Session, project_id: str) -> dict:
    """聚合大纲生成所需的上下文。

    从各 owner 服务查询已确认内容：
    - requirements: 已确认任务单
    - sources: 已确认证据卡片
    - datasets: 数据集字段概览
    - analysis: 已确认分析方案
    - execution: 成功的执行记录和产物
    """
    from app.modules.requirements import service as req_service
    from app.modules.requirements.models import RequirementPlan
    from app.modules.requirements.status import PlanStatus
    from app.modules.sources.models import EvidenceCard
    from app.modules.sources.status import EvidenceCardStatus
    from app.modules.datasets import service as dataset_service
    from app.modules.datasets.models import Dataset, DatasetVersion
    from app.modules.datasets.status import DatasetStatus
    from app.modules.analysis import service as analysis_service
    from app.modules.analysis.models import AnalysisPlan
    from app.modules.analysis.status import AnalysisPlanStatus
    from app.modules.execution.models import ExecutionRun, ExecutionArtifact
    from app.modules.execution.status import ExecutionRunStatus
    from app.modules.projects.models import Project

    context: dict = {}

    # 项目信息
    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        context["project"] = {
            "id": project.id,
            "name": project.name,
            "topic": project.topic,
        }

    # 已确认任务单
    plan = (
        db.query(RequirementPlan)
        .filter(
            RequirementPlan.project_id == project_id,
            RequirementPlan.status == PlanStatus.CONFIRMED.value,
        )
        .order_by(RequirementPlan.confirmed_at.desc())
        .first()
    )
    if plan:
        import json as _json
        try:
            payload = _json.loads(plan.payload_json)
        except Exception:
            payload = {}
        context["requirements"] = {
            "plan_id": plan.id,
            "payload": payload,
        }

    # 已确认证据卡片
    cards = (
        db.query(EvidenceCard)
        .filter(
            EvidenceCard.project_id == project_id,
            EvidenceCard.status == EvidenceCardStatus.CONFIRMED.value,
        )
        .all()
    )
    context["evidence_cards"] = [
        {
            "id": c.id,
            "claim": c.claim if hasattr(c, "claim") else "",
            "summary": getattr(c, "summary", "") or getattr(c, "claim", ""),
        }
        for c in cards
    ]

    # 数据集字段概览（取最新已解析版本）
    dataset = (
        db.query(Dataset)
        .filter(Dataset.project_id == project_id)
        .order_by(Dataset.created_at.desc())
        .first()
    )
    if dataset:
        version = (
            db.query(DatasetVersion)
            .filter(DatasetVersion.dataset_id == dataset.id)
            .order_by(DatasetVersion.version.desc())
            .first()
        )
        if version and version.profile_json:
            import json as _json
            try:
                profile = _json.loads(version.profile_json)
            except Exception:
                profile = {}
            context["dataset"] = {
                "dataset_id": dataset.id,
                "version_id": version.id,
                "row_count": version.row_count,
                "column_count": version.column_count,
                "profile": profile,
            }

    # 已确认分析方案
    analysis_plan = (
        db.query(AnalysisPlan)
        .filter(
            AnalysisPlan.project_id == project_id,
            AnalysisPlan.status == AnalysisPlanStatus.CONFIRMED.value,
        )
        .order_by(AnalysisPlan.confirmed_at.desc())
        .first()
    )
    if analysis_plan:
        import json as _json
        try:
            cleaning_plan = _json.loads(analysis_plan.cleaning_plan) if analysis_plan.cleaning_plan else []
            analysis_plan_items = _json.loads(analysis_plan.analysis_plan) if analysis_plan.analysis_plan else []
            chart_plan = _json.loads(analysis_plan.chart_plan) if analysis_plan.chart_plan else []
        except Exception:
            cleaning_plan, analysis_plan_items, chart_plan = [], [], []
        context["analysis_plan"] = {
            "plan_id": analysis_plan.id,
            "cleaning_plan": cleaning_plan,
            "analysis_plan": analysis_plan_items,
            "chart_plan": chart_plan,
        }

    # 成功的执行记录和产物
    runs = (
        db.query(ExecutionRun)
        .filter(
            ExecutionRun.project_id == project_id,
            ExecutionRun.status == ExecutionRunStatus.SUCCEEDED.value,
        )
        .order_by(ExecutionRun.created_at.desc())
        .all()
    )
    executions = []
    for run in runs:
        artifacts = (
            db.query(ExecutionArtifact)
            .filter(ExecutionArtifact.execution_run_id == run.id)
            .all()
        )
        executions.append({
            "run_id": run.id,
            "stdout": run.stdout or "",
            "stderr": run.stderr or "",
            "artifacts": [
                {
                    "name": a.name,
                    "artifact_type": a.artifact_type,
                    "file_path": a.file_path,
                    "execution_run_id": run.id,
                }
                for a in artifacts
            ],
        })
    context["executions"] = executions

    return context


def handle_generate_outline(db: Session, job) -> dict:
    """基于已确认的实验要求、证据、数据集、分析方案和执行结果生成大纲候选。

    调用 OutlineDraftProvider 拼装大纲章节，保存为 Outline（status=CANDIDATE）。
    """
    data = _parse_input(job)
    project_id = data.get("project_id") or job.project_id
    if not project_id:
        raise AppError(code="JOB_INPUT_INVALID",
                       message="任务缺少 project_id")

    from app.modules.outlines import service as outline_service
    from app.modules.execution.models import ExecutionRun
    from app.modules.execution.status import ExecutionRunStatus

    # 前置条件：至少一个成功的执行记录
    succeeded_count = (
        db.query(ExecutionRun)
        .filter(
            ExecutionRun.project_id == project_id,
            ExecutionRun.status == ExecutionRunStatus.SUCCEEDED.value,
        )
        .count()
    )
    if succeeded_count == 0:
        raise AppError(code="OUTLINE_NOT_GENERATABLE",
                       message="没有成功的执行记录，无法生成大纲")

    # 聚合上下文
    context = _gather_outline_context(db, project_id)

    provider = get_outline_provider()
    draft = provider.generate(context)

    # 转换为 dict 列表保存
    sections_data = [
        {
            "id": s.id,
            "title": s.title,
            "content": s.content,
            "source_type": s.source_type,
            "source_ids": s.source_ids,
        }
        for s in draft.sections
    ]

    outline = outline_service.save_outline_draft(
        db,
        project_id=project_id,
        sections=sections_data,
        candidate_source=provider.source_label(),
    )

    db.commit()
    return {
        "outline_id": outline.id,
        "section_count": len(draft.sections),
    }


def _gather_execution_artifacts_for_render(
    db: Session, project_id: str
) -> list[dict]:
    """收集项目下所有成功执行记录的产物（绝对路径）。"""
    from app.modules.execution.models import ExecutionRun, ExecutionArtifact
    from app.modules.execution.status import ExecutionRunStatus

    runs = (
        db.query(ExecutionRun)
        .filter(
            ExecutionRun.project_id == project_id,
            ExecutionRun.status == ExecutionRunStatus.SUCCEEDED.value,
        )
        .order_by(ExecutionRun.created_at.desc())
        .all()
    )
    artifacts = []
    for run in runs:
        arts = (
            db.query(ExecutionArtifact)
            .filter(ExecutionArtifact.execution_run_id == run.id)
            .all()
        )
        for a in arts:
            # 构造产物绝对路径
            base_dir = (settings.project_data_root / project_id
                        / "executions" / run.id)
            abs_path = str((base_dir / a.file_path).resolve())
            artifacts.append({
                "name": a.name,
                "artifact_type": a.artifact_type,
                "file_path": abs_path,
                "execution_run_id": run.id,
            })
    return artifacts


def handle_generate_word(db: Session, job) -> dict:
    """从已确认大纲生成 Word 文档。

    调用 WordRenderer 渲染 .docx 文件，保存为 DeliverableVersion（status=SUCCEEDED）。

    SPEC 0010：若项目有 Word 模板，使用 render_with_template；
    模板解析失败时降级到默认渲染并记录日志。
    """
    data = _parse_input(job)
    outline_id = data.get("outline_id")
    deliverable_id = data.get("deliverable_id")
    if not outline_id or not deliverable_id:
        raise AppError(code="JOB_INPUT_INVALID",
                       message="任务缺少 outline_id 或 deliverable_id")

    from app.modules.outlines import service as outline_service
    from app.modules.outlines.status import DeliverableType
    from app.modules.projects import service as project_service
    from app.infrastructure.renderers.word_renderer import WordRenderer

    outline = outline_service.get_outline_by_project(
        db, job.project_id, outline_id)
    if outline.status != "CONFIRMED":
        raise AppError(code="DELIVERABLE_NOT_GENERATABLE",
                       message="大纲未确认，无法生成 Word")

    # 创建版本并标记为 RUNNING
    _, version = outline_service.create_deliverable_version(
        db, job.project_id, deliverable_id)
    outline_service.mark_deliverable_version_running(db, version.id)
    db.flush()

    started_at = _now()
    try:
        import json as _json
        sections = _json.loads(outline.sections_json)
        project = project_service.get_project(db, job.project_id)
        artifacts = _gather_execution_artifacts_for_render(db, job.project_id)

        # 输出路径：project_data_root / project_id / deliverables / deliverable_id / word_v{version}.docx
        output_dir = (settings.project_data_root / job.project_id
                      / "deliverables" / deliverable_id)
        output_path = output_dir / f"word_v{version.version}.docx"

        # SPEC 0010：检查项目级 Word 模板
        template = outline_service.get_word_template(db, job.project_id)
        renderer = WordRenderer()

        if template:
            # 拼接模板绝对路径
            template_abs_path = (
                settings.project_data_root / template.file_path
            ).resolve()
            try:
                renderer.render_with_template(
                    template_path=str(template_abs_path),
                    project_name=project.name,
                    project_topic=project.topic,
                    outline_sections=sections,
                    execution_artifacts=artifacts,
                    output_path=str(output_path),
                )
            except AppError as template_err:
                # 降级到默认渲染
                import logging
                logging.getLogger(__name__).warning(
                    "Word 模板渲染失败，降级到默认渲染：%s (code=%s)",
                    template_err.message, template_err.code,
                )
                renderer.render(
                    project_name=project.name,
                    project_topic=project.topic,
                    outline_sections=sections,
                    execution_artifacts=artifacts,
                    output_path=str(output_path),
                )
        else:
            renderer.render(
                project_name=project.name,
                project_topic=project.topic,
                outline_sections=sections,
                execution_artifacts=artifacts,
                output_path=str(output_path),
            )

        finished_at = _now()
        duration = (finished_at - started_at).total_seconds()
        file_size = output_path.stat().st_size if output_path.exists() else 0

        outline_service.mark_deliverable_version_succeeded(
            db,
            version_id=version.id,
            file_path=f"word_v{version.version}.docx",
            file_size_bytes=file_size,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
        )
        db.commit()
        return {
            "deliverable_id": deliverable_id,
            "version_id": version.id,
            "version": version.version,
            "file_size_bytes": file_size,
            "duration_seconds": duration,
            "template_used": template is not None,
        }
    except AppError as err:
        finished_at = _now()
        duration = (finished_at - started_at).total_seconds()
        outline_service.mark_deliverable_version_failed(
            db,
            version_id=version.id,
            error_code=err.code,
            error_message=err.message,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
        )
        db.commit()
        raise
    except Exception as exc:
        finished_at = _now()
        duration = (finished_at - started_at).total_seconds()
        outline_service.mark_deliverable_version_failed(
            db,
            version_id=version.id,
            error_code="WORD_RENDER_FAILED",
            error_message=str(exc),
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
        )
        db.commit()
        raise AppError(code="WORD_RENDER_FAILED",
                       message=f"Word 生成失败：{exc}") from exc


def handle_generate_ppt(db: Session, job) -> dict:
    """从同一份已确认大纲生成 PPT 文档。

    调用 PptRenderer 渲染 .pptx 文件，保存为 DeliverableVersion（status=SUCCEEDED）。
    """
    data = _parse_input(job)
    outline_id = data.get("outline_id")
    deliverable_id = data.get("deliverable_id")
    if not outline_id or not deliverable_id:
        raise AppError(code="JOB_INPUT_INVALID",
                       message="任务缺少 outline_id 或 deliverable_id")

    from app.modules.outlines import service as outline_service
    from app.modules.projects import service as project_service
    from app.infrastructure.renderers.ppt_renderer import PptRenderer

    outline = outline_service.get_outline_by_project(
        db, job.project_id, outline_id)
    if outline.status != "CONFIRMED":
        raise AppError(code="DELIVERABLE_NOT_GENERATABLE",
                       message="大纲未确认，无法生成 PPT")

    # 创建版本并标记为 RUNNING
    _, version = outline_service.create_deliverable_version(
        db, job.project_id, deliverable_id)
    outline_service.mark_deliverable_version_running(db, version.id)
    db.flush()

    started_at = _now()
    try:
        import json as _json
        sections = _json.loads(outline.sections_json)
        project = project_service.get_project(db, job.project_id)
        artifacts = _gather_execution_artifacts_for_render(db, job.project_id)

        output_dir = (settings.project_data_root / job.project_id
                      / "deliverables" / deliverable_id)
        output_path = output_dir / f"ppt_v{version.version}.pptx"

        renderer = PptRenderer()
        renderer.render(
            project_name=project.name,
            project_topic=project.topic,
            outline_sections=sections,
            execution_artifacts=artifacts,
            output_path=str(output_path),
        )

        finished_at = _now()
        duration = (finished_at - started_at).total_seconds()
        file_size = output_path.stat().st_size if output_path.exists() else 0

        outline_service.mark_deliverable_version_succeeded(
            db,
            version_id=version.id,
            file_path=f"ppt_v{version.version}.pptx",
            file_size_bytes=file_size,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
        )
        db.commit()
        return {
            "deliverable_id": deliverable_id,
            "version_id": version.id,
            "version": version.version,
            "file_size_bytes": file_size,
            "duration_seconds": duration,
        }
    except AppError as err:
        finished_at = _now()
        duration = (finished_at - started_at).total_seconds()
        outline_service.mark_deliverable_version_failed(
            db,
            version_id=version.id,
            error_code=err.code,
            error_message=err.message,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
        )
        db.commit()
        raise
    except Exception as exc:
        finished_at = _now()
        duration = (finished_at - started_at).total_seconds()
        outline_service.mark_deliverable_version_failed(
            db,
            version_id=version.id,
            error_code="PPT_RENDER_FAILED",
            error_message=str(exc),
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
        )
        db.commit()
        raise AppError(code="PPT_RENDER_FAILED",
                       message=f"PPT 生成失败：{exc}") from exc


HANDLERS: dict[str, Callable] = {
    JobType.FETCH_URL.value: handle_fetch_url,
    JobType.PARSE_DOCUMENT.value: handle_parse_document,
    JobType.GENERATE_EVIDENCE.value: handle_generate_evidence,
    JobType.PARSE_DATASET.value: handle_parse_dataset,
    JobType.GENERATE_ANALYSIS_PLAN.value: handle_generate_analysis_plan,
    JobType.GENERATE_CODE_TASK.value: handle_generate_code_task,
    JobType.EXECUTE_CODE_TASK.value: handle_execute_code_task,
    JobType.GENERATE_OUTLINE.value: handle_generate_outline,
    JobType.GENERATE_WORD.value: handle_generate_word,
    JobType.GENERATE_PPT.value: handle_generate_ppt,
}
