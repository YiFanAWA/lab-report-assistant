"""来源与证据 API 路由（薄适配层）。

只做协议映射，不拥有业务语义。
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.database.engine import SessionLocal
from app.core.errors import AppError
from app.modules.sources import service as src_service
from app.modules.sources.contracts import (
    SourceCreateRequest, SourceRecordResponse, SourceListResponse,
    ParsedDocumentResponse, EvidenceCardResponse,
    EvidenceUpdateRequest, EvidenceListResponse,
)
from app.modules.llm.evidence_gateway import get_evidence_provider
from app.api.dependencies import require_confirmed_plan

router = APIRouter(prefix="/api/projects/{project_id}")


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- URL 来源 ---

@router.post("/sources/urls", response_model=SourceRecordResponse)
def add_url_source(
    project_id: str,
    req: SourceCreateRequest,
    db: Session = Depends(_db),
):
    require_confirmed_plan(db, project_id)
    source = src_service.add_url_source(db, project_id, req)
    return src_service.source_to_response(source)


# --- 文件来源 ---

@router.post("/sources/files", response_model=SourceRecordResponse)
async def add_file_source(
    project_id: str,
    file: UploadFile = File(...),
    title: str = Form(""),
    db: Session = Depends(_db),
):
    require_confirmed_plan(db, project_id)
    content = await file.read(settings.source_upload_max_bytes + 1)
    if len(content) > settings.source_upload_max_bytes:
        raise AppError(
            code="SOURCE_FILE_TOO_LARGE", message="文件超过 20 MB 上限", field="file",
        )
    source = src_service.add_file_source(
        db, project_id, title, file.filename or "", content, file.content_type or "",
    )
    return src_service.source_to_response(source)


# --- 来源列表 ---

@router.get("/sources", response_model=SourceListResponse)
def list_sources(project_id: str, db: Session = Depends(_db)):
    sources = src_service.list_sources(db, project_id)
    return SourceListResponse(items=[src_service.source_to_response(s) for s in sources])


# --- 解析 ---

@router.post("/sources/{source_id}/parse", response_model=ParsedDocumentResponse)
def parse_source(project_id: str, source_id: str, db: Session = Depends(_db)):
    parsed = src_service.parse_source(db, project_id, source_id)
    return src_service.parsed_to_response(parsed)


@router.get("/sources/{source_id}/parsed-document", response_model=ParsedDocumentResponse)
def get_parsed_document(project_id: str, source_id: str, db: Session = Depends(_db)):
    parsed = src_service.get_parsed_document(db, project_id, source_id)
    if not parsed:
        raise AppError(code="PARSED_DOCUMENT_NOT_FOUND", message="未找到解析文本")
    return src_service.parsed_to_response(parsed)


# --- 证据 ---

@router.post("/sources/{source_id}/evidence/generate", response_model=EvidenceListResponse)
def generate_evidence(project_id: str, source_id: str, db: Session = Depends(_db)):
    provider = get_evidence_provider()
    cards = src_service.generate_evidence(db, project_id, source_id, provider)
    return EvidenceListResponse(items=[src_service.evidence_to_response(c) for c in cards])


@router.get("/evidence", response_model=EvidenceListResponse)
def list_evidence(
    project_id: str,
    source_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(_db),
):
    cards = src_service.list_evidence(db, project_id, source_id=source_id, status=status)
    return EvidenceListResponse(items=[src_service.evidence_to_response(c) for c in cards])


@router.put("/evidence/{evidence_id}", response_model=EvidenceCardResponse)
def update_evidence(
    project_id: str, evidence_id: str, req: EvidenceUpdateRequest,
    db: Session = Depends(_db),
):
    card = src_service.update_evidence(db, project_id, evidence_id, req)
    return src_service.evidence_to_response(card)


@router.post("/evidence/{evidence_id}/confirm", response_model=EvidenceCardResponse)
def confirm_evidence(project_id: str, evidence_id: str, db: Session = Depends(_db)):
    card = src_service.confirm_evidence(db, project_id, evidence_id)
    return src_service.evidence_to_response(card)


@router.post("/evidence/{evidence_id}/reject", response_model=EvidenceCardResponse)
def reject_evidence(project_id: str, evidence_id: str, db: Session = Depends(_db)):
    card = src_service.reject_evidence(db, project_id, evidence_id)
    return src_service.evidence_to_response(card)
