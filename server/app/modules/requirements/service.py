"""需求核心服务。"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Generator
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.projects import service as project_service
from app.modules.projects.status import ProjectStatus
from app.modules.requirements.models import RequirementSource, RequirementPlan, ChangeRecord
from app.modules.requirements.contracts import (
    TextSourceRequest,
    GeneratePlanRequest,
    UpdatePlanRequest,
    RequirementPlanPayload,
    RequirementSourceResponse,
    RequirementPlanResponse,
)
from app.modules.requirements.status import (
    SourceType,
    PlanStatus,
    CandidateSource,
    ChangeType,
)


# --- SPEC 0018 流式事件类型 ---


@dataclass
class StreamChunkEvent:
    """流式 chunk 事件，承载一个 LLM 生成的内容片段。"""

    text: str


@dataclass
class StreamDoneEvent:
    """流式完成事件，承载任务单保存后的元信息。"""

    plan_id: str
    candidate_source: str
    fallback_used: bool


@dataclass
class StreamErrorEvent:
    """流式错误事件，承载失败时的错误信息和已生成的部分文本。"""

    error_code: str
    message: str
    partial_text: str


StreamEvent = StreamChunkEvent | StreamDoneEvent | StreamErrorEvent


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _source_to_response(s: RequirementSource) -> RequirementSourceResponse:
    return RequirementSourceResponse(
        id=s.id,
        project_id=s.project_id,
        source_type=s.source_type,
        title=s.title,
        original_text=s.original_text,
        original_file_path=s.original_file_path,
        content_hash=s.content_hash,
        created_at=s.created_at.isoformat(),
    )


def _plan_to_response(p: RequirementPlan) -> RequirementPlanResponse:
    return RequirementPlanResponse(
        id=p.id,
        project_id=p.project_id,
        source_id=p.source_id,
        status=p.status,
        payload=RequirementPlanPayload.model_validate(json.loads(p.payload_json)),
        candidate_source=p.candidate_source,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat(),
        confirmed_at=p.confirmed_at.isoformat() if p.confirmed_at else None,
    )


def _add_change(db: Session, project_id: str, change_type: str, summary: str) -> None:
    rec = ChangeRecord(project_id=project_id, change_type=change_type, summary=summary)
    db.add(rec)


def _ensure_project(db: Session, project_id: str):
    return project_service.get_project(db, project_id)


# --- 要求来源 ---

def add_text_source(db: Session, project_id: str, req: TextSourceRequest) -> RequirementSource:
    if not req.text.strip():
        raise AppError(code="REQUIREMENT_TEXT_REQUIRED", message="实验要求不能为空", field="text")

    _ensure_project(db, project_id)

    source = RequirementSource(
        project_id=project_id,
        source_type=SourceType.PASTED_TEXT.value,
        title=req.title.strip(),
        original_text=req.text.strip(),
        content_hash=_hash_text(req.text.strip()),
    )
    db.add(source)
    _add_change(db, project_id, ChangeType.REQUIREMENT_SOURCE_CREATED.value,
                f"添加文本要求来源：{source.title}")
    db.commit()
    db.refresh(source)
    return source


def add_docx_source(db: Session, project_id: str, title: str, text: str,
                    file_path: str) -> RequirementSource:
    if not text.strip():
        raise AppError(code="REQUIREMENT_DOCX_TEXT_EMPTY", message="Word 文件解析后无文本内容",
                       field="file")

    _ensure_project(db, project_id)

    source = RequirementSource(
        project_id=project_id,
        source_type=SourceType.DOCX_FILE.value,
        title=title.strip() or "实验要求文档",
        original_text=text.strip(),
        original_file_path=file_path,
        content_hash=_hash_text(text.strip()),
    )
    db.add(source)
    _add_change(db, project_id, ChangeType.REQUIREMENT_SOURCE_CREATED.value,
                f"上传 Word 要求来源：{source.title}")
    db.commit()
    db.refresh(source)
    return source


def list_sources(db: Session, project_id: str) -> list[RequirementSource]:
    _ensure_project(db, project_id)
    return (
        db.query(RequirementSource)
        .filter(RequirementSource.project_id == project_id)
        .order_by(RequirementSource.created_at.desc())
        .all()
    )


def get_source(db: Session, source_id: str) -> RequirementSource:
    s = db.query(RequirementSource).filter(RequirementSource.id == source_id).first()
    if not s:
        raise AppError(code="REQUIREMENT_SOURCE_NOT_FOUND",
                       message=f"未找到要求来源 {source_id}")
    return s


# --- 任务单 ---

def generate_plan(db: Session, project_id: str, req: GeneratePlanRequest,
                  provider) -> RequirementPlan:
    project = _ensure_project(db, project_id)
    source = get_source(db, req.source_id)
    if source.project_id != project_id:
        raise AppError(code="REQUIREMENT_SOURCE_NOT_FOUND",
                       message=f"要求来源不属于该项目")

    from app.modules.requirements.contracts import RequirementPlanPayload
    payload: RequirementPlanPayload = provider.draft(source.original_text)
    candidate_source_val = provider.source_label()

    # 标记已有 CANDIDATE 为 STALE
    old = (
        db.query(RequirementPlan)
        .filter(
            RequirementPlan.project_id == project_id,
            RequirementPlan.status == PlanStatus.CANDIDATE.value,
        )
        .all()
    )
    for p in old:
        p.status = PlanStatus.STALE.value

    plan = RequirementPlan(
        project_id=project_id,
        source_id=source.id,
        status=PlanStatus.CANDIDATE.value,
        payload_json=payload.model_dump_json(),
        candidate_source=candidate_source_val,
    )
    db.add(plan)
    project.status = ProjectStatus.REQUIREMENT_PARSED.value
    _add_change(db, project_id, ChangeType.REQUIREMENT_PLAN_GENERATED.value,
                f"生成任务单候选（{candidate_source_val}）")
    db.commit()
    db.refresh(plan)
    return plan


def stream_generate_plan(
    db: Session, project_id: str, req: GeneratePlanRequest, provider
) -> Generator[StreamEvent, None, None]:
    """流式生成任务单。

    SPEC 0018 流式 LLM 输出。

    流程（分段持有 db session，避免 SQLite 写锁阻塞）：
    1. Phase 1 校验（持有 db）：校验 project + source 归属
    2. Phase 2 流式生成（关闭 db，不持有连接）：调用 provider.stream_draft()
    3. Phase 3 JSON 校验：用 Pydantic 校验完整 JSON
    4. Phase 4 保存（重新打开 db）：保存 RequirementPlan + 推进 project.status

    中途失败：yield StreamErrorEvent（保留 partial_text），不保存 RequirementPlan。

    兼容不支持 stream_draft 的 provider（LocalRule）：调用 draft() 一次性 yield。

    yield StreamEvent：StreamChunkEvent / StreamDoneEvent / StreamErrorEvent。
    """
    from app.infrastructure.database.engine import SessionLocal

    # Phase 1: 校验（持有 db）
    project = _ensure_project(db, project_id)
    source = get_source(db, req.source_id)
    if source.project_id != project_id:
        raise AppError(
            code="REQUIREMENT_SOURCE_NOT_FOUND",
            message="要求来源不属于该项目",
        )
    requirement_text = source.original_text
    db.close()  # 显式关闭，避免流式期间持有连接

    # Phase 2: 流式生成（不持有 db）
    chunks: list[str] = []
    fallback_used = False
    try:
        if hasattr(provider, "stream_draft"):
            for chunk in provider.stream_draft(requirement_text):
                chunks.append(chunk)
                yield StreamChunkEvent(text=chunk)
        else:
            # 兼容 LocalRule provider（不支持流式）
            payload = provider.draft(requirement_text)
            full_json = payload.model_dump_json()
            # 拆分为多个 chunk 模拟流式（按 50 字符拆分）
            for i in range(0, len(full_json), 50):
                piece = full_json[i:i + 50]
                chunks.append(piece)
                yield StreamChunkEvent(text=piece)
    except Exception as e:
        # 流式中途失败
        partial_text = "".join(chunks)
        yield StreamErrorEvent(
            error_code=getattr(e, "code", "STREAM_FAILED"),
            message=str(e) or e.__class__.__name__,
            partial_text=partial_text,
        )
        return

    # Phase 3: 校验完整 JSON
    raw = "".join(chunks)
    try:
        from app.modules.llm.deepseek_requirement_provider import (
            DeepSeekRequirementResponse,
            deepseek_response_to_payload,
        )
        parsed = DeepSeekRequirementResponse.model_validate_json(raw)
        payload = deepseek_response_to_payload(parsed)
    except Exception as e:
        yield StreamErrorEvent(
            error_code="DEEPSEEK_JSON_PARSE_ERROR",
            message=f"流式生成的 JSON 校验失败: {e}",
            partial_text=raw,
        )
        return

    # Phase 4: 保存（重新打开 db）
    db2 = SessionLocal()
    try:
        old = (
            db2.query(RequirementPlan)
            .filter(
                RequirementPlan.project_id == project_id,
                RequirementPlan.status == PlanStatus.CANDIDATE.value,
            )
            .all()
        )
        for p in old:
            p.status = PlanStatus.STALE.value

        candidate_source_val = provider.source_label()
        plan = RequirementPlan(
            project_id=project_id,
            source_id=source.id,
            status=PlanStatus.CANDIDATE.value,
            payload_json=payload.model_dump_json(),
            candidate_source=candidate_source_val,
        )
        db2.add(plan)
        project2 = _ensure_project(db2, project_id)
        project2.status = ProjectStatus.REQUIREMENT_PARSED.value
        _add_change(
            db2, project_id,
            ChangeType.REQUIREMENT_PLAN_GENERATED.value,
            f"流式生成任务单候选（{candidate_source_val}）",
        )
        db2.commit()
        db2.refresh(plan)

        yield StreamDoneEvent(
            plan_id=plan.id,
            candidate_source=candidate_source_val,
            fallback_used=fallback_used,
        )
    except Exception as e:
        yield StreamErrorEvent(
            error_code="PLAN_SAVE_FAILED",
            message=f"任务单保存失败: {e}",
            partial_text=raw,
        )
    finally:
        db2.close()


def get_current_plan(db: Session, project_id: str) -> RequirementPlan | None:
    _ensure_project(db, project_id)
    return (
        db.query(RequirementPlan)
        .filter(
            RequirementPlan.project_id == project_id,
            RequirementPlan.status.in_([PlanStatus.CANDIDATE.value, PlanStatus.CONFIRMED.value]),
        )
        .order_by(RequirementPlan.updated_at.desc())
        .first()
    )


def get_plan(db: Session, plan_id: str) -> RequirementPlan:
    p = db.query(RequirementPlan).filter(RequirementPlan.id == plan_id).first()
    if not p:
        raise AppError(code="REQUIREMENT_PLAN_NOT_FOUND",
                       message=f"未找到任务单 {plan_id}")
    return p


def update_plan(db: Session, project_id: str, plan_id: str,
                req: UpdatePlanRequest) -> RequirementPlan:
    _ensure_project(db, project_id)
    plan = get_plan(db, plan_id)
    if plan.project_id != project_id:
        raise AppError(code="REQUIREMENT_PLAN_NOT_FOUND", message="任务单不属于该项目")
    if plan.status not in (PlanStatus.CANDIDATE.value, PlanStatus.STALE.value):
        raise AppError(code="REQUIREMENT_PLAN_NOT_EDITABLE", message="只能修改候选或过期任务单")

    plan.payload_json = req.payload.model_dump_json()
    plan.updated_at = datetime.now(timezone.utc)
    _add_change(db, project_id, ChangeType.REQUIREMENT_PLAN_UPDATED.value,
                "修改任务单候选")
    db.commit()
    db.refresh(plan)
    return plan


def confirm_plan(db: Session, project_id: str, plan_id: str) -> RequirementPlan:
    from datetime import datetime, timezone

    project = _ensure_project(db, project_id)
    plan = get_plan(db, plan_id)
    if plan.project_id != project_id:
        raise AppError(code="REQUIREMENT_PLAN_NOT_FOUND", message="任务单不属于该项目")
    if plan.status != PlanStatus.CANDIDATE.value:
        raise AppError(code="REQUIREMENT_PLAN_NOT_EDITABLE", message="只能确认候选任务单")

    plan.status = PlanStatus.CONFIRMED.value
    plan.confirmed_at = datetime.now(timezone.utc)
    plan.updated_at = datetime.now(timezone.utc)

    project.status = ProjectStatus.REQUIREMENT_CONFIRMED.value

    _add_change(db, project_id, ChangeType.REQUIREMENT_PLAN_CONFIRMED.value,
                "确认任务单")
    db.commit()
    db.refresh(plan)
    return plan
