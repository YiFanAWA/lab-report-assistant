"""需求核心服务。"""

import hashlib
import json
from datetime import datetime, timezone
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
