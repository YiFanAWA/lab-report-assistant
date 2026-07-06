"""证据卡片 API 路由。

只做协议映射，不拥有业务语义。
前缀 /api/projects/{project_id}。
"""

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.infrastructure.database.engine import SessionLocal
from app.core.errors import AppError
from app.modules.sources import service as sources_service
from app.modules.sources.contracts import (
    UpdateEvidenceCardRequest,
    EvidenceCardResponse,
    EvidenceCardListResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}")


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _field_from_validation(exc: ValidationError) -> str | None:
    if not exc.errors():
        return None
    loc = exc.errors()[0].get("loc", ())
    return str(loc[0]) if loc else None


# --- 生成证据卡片候选 ---

@router.post("/sources/{source_id}/evidence/generate", status_code=201)
def generate_evidence_cards(project_id: str, source_id: str,
                              db: Session = Depends(_db)):
    job_id = sources_service.generate_evidence_cards(
        db, project_id, source_id)
    return {"job_id": job_id}


# --- 证据卡片列表 ---

@router.get("/evidence", response_model=EvidenceCardListResponse)
def list_evidence(project_id: str,
                  source_id: str | None = None,
                  status: str | None = None,
                  db: Session = Depends(_db)):
    cards = sources_service.list_evidence_cards(
        db, project_id, source_id=source_id, status=status)
    return sources_service._evidence_list_to_response(cards)


# --- 更新证据卡片 ---

@router.put("/evidence/{card_id}", response_model=EvidenceCardResponse)
def update_evidence_card(project_id: str, card_id: str,
                          body: dict,
                          db: Session = Depends(_db)):
    try:
        req = UpdateEvidenceCardRequest(**body)
    except ValidationError as exc:
        raise AppError(
            code="REQUEST_VALIDATION_ERROR",
            message="请求参数不符合要求",
            field=_field_from_validation(exc),
        )
    card = sources_service.update_evidence_card(
        db, project_id, card_id, req)
    return sources_service._evidence_card_to_response(card)


# --- 确认证据卡片 ---

@router.post("/evidence/{card_id}/confirm",
              response_model=EvidenceCardResponse)
def confirm_evidence_card(project_id: str, card_id: str,
                           db: Session = Depends(_db)):
    card = sources_service.confirm_evidence_card(db, project_id, card_id)
    return sources_service._evidence_card_to_response(card)


# --- 拒绝证据卡片 ---

@router.post("/evidence/{card_id}/reject",
              response_model=EvidenceCardResponse)
def reject_evidence_card(project_id: str, card_id: str,
                         db: Session = Depends(_db)):
    card = sources_service.reject_evidence_card(db, project_id, card_id)
    return sources_service._evidence_card_to_response(card)


# --- 完成证据确认 ---

@router.post("/evidence/complete")
def complete_evidence(project_id: str, db: Session = Depends(_db)):
    project = sources_service.complete_evidence(db, project_id)
    return {"project_id": project.id, "status": project.status}
