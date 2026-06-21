"""来源与证据核心服务。

资料的登记、持久化、解析、证据卡片管理。唯一业务 owner。
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from pathlib import Path
from app.core.config import settings
from app.core.errors import AppError
from app.modules.projects import service as proj_service
from app.modules.projects.models import Project
from app.modules.projects.status import ProjectStatus
from app.modules.sources.models import SourceRecord, ParsedDocument, EvidenceCard
from app.modules.sources.contracts import (
    SourceCreateRequest, SourceRecordResponse, SourceListResponse,
    ParsedDocumentResponse, EvidenceDraftCandidate, EvidenceDraftDocument,
    EvidenceCardResponse, EvidenceListResponse, EvidenceUpdateRequest,
)
from app.modules.sources.status import (
    SourceKind, SourceType, CollectionStatus,
    ParserType, ParseStatus,
    EvidenceStatus,
)


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def source_to_response(s: SourceRecord) -> SourceRecordResponse:
    return SourceRecordResponse(
        id=s.id, project_id=s.project_id, source_kind=s.source_kind,
        source_type=s.source_type, title=s.title, url=s.url,
        original_file_path=s.original_file_path, content_hash=s.content_hash,
        collection_status=s.collection_status, access_reason=s.access_reason,
        content_type=s.content_type, size_bytes=s.size_bytes,
        created_at=s.created_at.isoformat(), updated_at=s.updated_at.isoformat(),
    )


def parsed_to_response(p: ParsedDocument) -> ParsedDocumentResponse:
    return ParsedDocumentResponse(
        id=p.id, project_id=p.project_id, source_id=p.source_id,
        parser_type=p.parser_type, title=p.title, parsed_text=p.parsed_text,
        text_hash=p.text_hash, location_map_json=p.location_map_json,
        parse_status=p.parse_status, parse_error_code=p.parse_error_code,
        created_at=p.created_at.isoformat(),
    )


def evidence_to_response(e: EvidenceCard) -> EvidenceCardResponse:
    return EvidenceCardResponse(
        id=e.id, project_id=e.project_id, source_id=e.source_id,
        parsed_document_id=e.parsed_document_id, status=e.status,
        evidence_type=e.evidence_type, summary=e.summary,
        source_quote=e.source_quote, location_label=e.location_label,
        relevance_to_requirement=e.relevance_to_requirement,
        candidate_source=e.candidate_source,
        created_at=e.created_at.isoformat(),
        confirmed_at=e.confirmed_at.isoformat() if e.confirmed_at else None,
    )


def _advance_project_to(db: Session, project_id: str, target: str) -> None:
    """推进项目状态，仅允许前进。"""
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise AppError(code="PROJECT_NOT_FOUND", message=f"项目 {project_id} 不存在")
    if proj.status == ProjectStatus.DRAFT.value:
        raise AppError(code="REQUIREMENT_PLAN_NOT_CONFIRMED", message="请先确认实验任务单")
    allowed_transitions = {
        ProjectStatus.REQUIREMENT_CONFIRMED.value: {
            "SOURCES_COLLECTED": ProjectStatus.SOURCES_COLLECTED.value,
        },
        ProjectStatus.SOURCES_COLLECTED.value: {
            "EVIDENCE_CONFIRMED": ProjectStatus.EVIDENCE_CONFIRMED.value,
        },
    }
    current = proj.status
    allowed = allowed_transitions.get(current, {})
    if target not in allowed:
        return  # 已经处于后续状态或正确目标，不倒退
    proj.status = allowed[target]


# --- URL 来源 ---

def add_url_source(db: Session, project_id: str, req: SourceCreateRequest,
                   fetcher=None) -> SourceRecord:
    """登记公开 URL 来源。支持 fetcher 参数注入测试替身。"""
    from app.infrastructure.sources.url_policy import validate_public_url
    from app.infrastructure.sources.http_fetcher import fetch_url as _real_fetch
    from app.infrastructure.sources.storage import save_source_bytes

    proj = proj_service.get_project(db, project_id)

    url, err_code = validate_public_url(req.url)
    if err_code:
        raise AppError(code=err_code, message="URL 不安全或不支持", field="url")

    fetch = fetcher or _real_fetch
    result = fetch(url)
    content = result.content
    source_type = _guess_type_from_content_type(result.content_type) or SourceType.WEB_PAGE.value

    src = SourceRecord(
        project_id=project_id,
        source_kind=SourceKind.PUBLIC_URL.value,
        source_type=source_type,
        title=req.title.strip() or url[:100],
        url=url,
        content_hash=_hash(content) if content else None,
        collection_status=result.status,
        access_reason=result.error_code or result.error_message,
        content_type=result.content_type,
        size_bytes=len(content) if content else None,
    )
    db.add(src)
    db.flush()

    # 落盘
    if content:
        saved = save_source_bytes(proj.workspace_root, url.split("/")[-1] or "page.html", content)
        src.original_file_path = str(saved)

    if result.status == CollectionStatus.FETCHED.value:
        _advance_project_to(db, project_id, "SOURCES_COLLECTED")
    db.commit()
    db.refresh(src)
    return src


def add_file_source(db: Session, project_id: str, title: str,
                    filename: str, content: bytes, content_type: str) -> SourceRecord:
    """登记本地文件来源。"""
    from app.infrastructure.sources.storage import save_source_bytes

    proj = proj_service.get_project(db, project_id)

    if not content:
        raise AppError(code="SOURCE_FILE_EMPTY", message="文件不能为空", field="file")

    source_type = _guess_type_from_filename(filename)
    if source_type is None:
        raise AppError(code="SOURCE_FILE_UNSUPPORTED", message=f"不支持的文件格式: {filename}", field="file")

    saved = save_source_bytes(proj.workspace_root, filename, content)

    src = SourceRecord(
        project_id=project_id,
        source_kind=SourceKind.LOCAL_FILE.value,
        source_type=source_type,
        title=title.strip() or filename,
        original_file_path=str(saved),
        content_hash=_hash(content),
        collection_status=CollectionStatus.FETCHED.value,
        content_type=content_type,
        size_bytes=len(content),
    )
    db.add(src)
    _advance_project_to(db, project_id, "SOURCES_COLLECTED")
    db.commit()
    db.refresh(src)
    return src


def _guess_type_from_filename(name: str) -> str | None:
    lower = name.lower()
    if lower.endswith(".pdf"): return SourceType.PDF.value
    if lower.endswith(".docx"): return SourceType.DOCX.value
    if lower.endswith(".txt"): return SourceType.TXT.value
    if lower.endswith(".csv"): return SourceType.CSV.value
    if lower.endswith(".xlsx"): return SourceType.EXCEL.value
    return None


def _guess_type_from_content_type(ct: str) -> str | None:
    if not ct: return None
    if "application/pdf" in ct: return SourceType.PDF.value
    if "text/html" in ct: return SourceType.WEB_PAGE.value
    if "text/plain" in ct: return SourceType.TXT.value
    return None


def list_sources(db: Session, project_id: str) -> list[SourceRecord]:
    proj_service.get_project(db, project_id)
    return (
        db.query(SourceRecord)
        .filter(SourceRecord.project_id == project_id)
        .order_by(SourceRecord.created_at.desc())
        .all()
    )


def get_source(db: Session, project_id: str, source_id: str) -> SourceRecord:
    s = db.query(SourceRecord).filter(SourceRecord.id == source_id).first()
    if not s or s.project_id != project_id:
        raise AppError(code="SOURCE_RECORD_NOT_FOUND", message=f"未找到来源 {source_id}")
    return s


# --- 解析 ---

def parse_source(db: Session, project_id: str, source_id: str) -> ParsedDocument:
    """解析来源文本，成功或失败均持久化。"""
    src = get_source(db, project_id, source_id)

    st = src.source_type
    if st in (SourceType.CSV.value, SourceType.EXCEL.value):
        raise AppError(code="SOURCE_PARSE_UNSUPPORTED_FOR_DATASET_FILE",
                       message="CSV/Excel 暂不支持文本解析")

    # 读文件
    raw = b""
    if src.original_file_path and os.path.exists(src.original_file_path):
        with open(src.original_file_path, "rb") as f:
            raw = f.read()
    elif src.collection_status == CollectionStatus.FETCHED.value and not src.original_file_path:
        raise AppError(code="SOURCE_TEXT_EMPTY", message="来源内容不可用（未获取或已丢失）")
    elif not raw:
        raise AppError(code="SOURCE_TEXT_EMPTY", message="来源内容为空")

    # 解析
    try:
        if st == SourceType.WEB_PAGE.value:
            parser_type = ParserType.HTML_TEXT.value
            from app.infrastructure.documents.html_reader import extract_text as extract_html
            text, location = extract_html(raw)
        elif st == SourceType.PDF.value:
            parser_type = ParserType.PDF_TEXT.value
            from app.infrastructure.documents.pdf_reader import extract_text as extract_pdf
            text, location = extract_pdf(raw)
        elif st == SourceType.DOCX.value:
            parser_type = ParserType.DOCX_TEXT.value
            from app.infrastructure.documents.docx_reader import extract_text as extract_docx
            text = extract_docx(raw)
            location = {
                "source": "docx",
                "blocks": (
                    [{"label": "全文", "start": 0, "end": len(text)}]
                    if text.strip()
                    else []
                ),
            }
        elif st == SourceType.TXT.value:
            parser_type = ParserType.TXT_TEXT.value
            from app.infrastructure.documents.text_reader import extract_text as extract_txt
            text, location = extract_txt(raw)
        else:
            raise AppError(code="SOURCE_PARSE_UNSUPPORTED_FOR_DATASET_FILE",
                           message=f"不支持的来源类型: {st}")

        if not text.strip():
            error_code = _parse_error_code_for_st(st)
            parsed = ParsedDocument(
                project_id=project_id, source_id=source_id,
                parser_type=st, title=src.title,
                parsed_text="", text_hash=_hash(b""),
                location_map_json="{}", parse_status=ParseStatus.FAILED.value,
                parse_error_code=error_code,
            )
            db.add(parsed)
            src.collection_status = CollectionStatus.FAILED.value
            db.commit()
            raise AppError(code=error_code, message="解析后文本为空")

    except AppError:
        raise
    except Exception as e:
        parsed = ParsedDocument(
            project_id=project_id, source_id=source_id,
            parser_type=st, title=src.title,
            parsed_text="", text_hash=_hash(b""),
            location_map_json="{}", parse_status=ParseStatus.FAILED.value,
            parse_error_code="SOURCE_PARSE_UNEXPECTED_ERROR",
        )
        db.add(parsed)
        src.collection_status = CollectionStatus.FAILED.value
        db.commit()
        raise AppError(code="SOURCE_PARSE_UNEXPECTED_ERROR", message=str(e)[:300])

    import json
    parsed = ParsedDocument(
        project_id=project_id, source_id=source_id,
        parser_type=parser_type, title=src.title,
        parsed_text=text, text_hash=_hash(text.encode()),
        location_map_json=json.dumps(location) if location else "{}",
        parse_status=ParseStatus.SUCCEEDED.value,
    )
    db.add(parsed)
    src.collection_status = CollectionStatus.PARSED.value
    db.commit()
    db.refresh(parsed)
    return parsed


def _parse_error_code_for_st(st: str) -> str:
    mapping = {
        SourceType.WEB_PAGE.value: "SOURCE_HTML_TEXT_EMPTY",
        SourceType.PDF.value: "SOURCE_PDF_TEXT_EMPTY",
        SourceType.DOCX.value: "SOURCE_DOCX_TEXT_EMPTY",
        SourceType.TXT.value: "SOURCE_TEXT_EMPTY",
    }
    return mapping.get(st, "SOURCE_TEXT_EMPTY")


def get_parsed_document(db: Session, project_id: str, source_id: str) -> ParsedDocument | None:
    """获取解析文档，同时校验来源归属。"""
    src = get_source(db, project_id, source_id)
    return (
        db.query(ParsedDocument)
        .filter(ParsedDocument.source_id == source_id)
        .order_by(ParsedDocument.created_at.desc())
        .first()
    )


# --- 证据卡片 ---

def generate_evidence(db: Session, project_id: str, source_id: str, provider) -> list[EvidenceCard]:
    """生成证据卡片候选。校验摘录真实性。"""
    get_source(db, project_id, source_id)

    parsed = get_parsed_document(db, project_id, source_id)
    if not parsed or parsed.parse_status != ParseStatus.SUCCEEDED.value:
        raise AppError(code="PARSED_DOCUMENT_NOT_FOUND", message="请先解析来源文本")

    doc = EvidenceDraftDocument(
        parsed_text=parsed.parsed_text,
        title=parsed.title,
        parser_type=parsed.parser_type,
        location_map=json.loads(parsed.location_map_json or "{}"),
    )

    items = provider.draft(doc)
    if not items:
        raise AppError(code="EVIDENCE_CARD_INVALID_QUOTE", message="证据提供者未返回任何候选")

    candidates: list[EvidenceDraftCandidate] = []
    for item in items:
        candidate = EvidenceDraftCandidate(**item)
        if candidate.source_quote not in parsed.parsed_text:
            raise AppError(
                code="EVIDENCE_CARD_INVALID_QUOTE",
                message="证据摘录不存在于解析原文",
                field="source_quote",
            )
        if not location_contains_quote(
            doc.location_map,
            candidate.location_label,
            candidate.source_quote,
            parsed.parsed_text,
        ):
            raise AppError(
                code="EVIDENCE_CARD_INVALID_LOCATION",
                message="证据位置无法定位到原文摘录",
                field="location_label",
            )
        candidates.append(candidate)

    for old in db.query(EvidenceCard).filter(
        EvidenceCard.source_id == source_id,
        EvidenceCard.project_id == project_id,
        EvidenceCard.status == EvidenceStatus.CANDIDATE.value,
    ).all():
        old.status = EvidenceStatus.STALE.value

    cards: list[EvidenceCard] = []
    for candidate in candidates:
        card = EvidenceCard(
            project_id=project_id, source_id=source_id,
            parsed_document_id=parsed.id,
            status=EvidenceStatus.CANDIDATE.value,
            evidence_type=candidate.evidence_type.value,
            summary=candidate.summary, source_quote=candidate.source_quote,
            location_label=candidate.location_label,
            relevance_to_requirement=candidate.relevance_to_requirement,
            candidate_source=provider.source_label(),
        )
        db.add(card)
        cards.append(card)

    db.commit()
    for c in cards:
        db.refresh(c)
    return cards


def location_contains_quote(
    location_map: dict,
    location_label: str,
    source_quote: str,
    parsed_text: str,
) -> bool:
    blocks = location_map.get("blocks", [])
    if not isinstance(blocks, list):
        return False
    for block in blocks:
        if not isinstance(block, dict) or block.get("label") != location_label:
            continue
        start = block.get("start")
        end = block.get("end")
        if not isinstance(start, int) or not isinstance(end, int):
            return False
        if start < 0 or end < start or end > len(parsed_text):
            return False
        return source_quote in parsed_text[start:end]
    return False


def list_evidence(db: Session, project_id: str,
                  source_id: str | None = None,
                  status: str | None = None) -> list[EvidenceCard]:
    proj_service.get_project(db, project_id)
    q = db.query(EvidenceCard).filter(EvidenceCard.project_id == project_id)
    if source_id:
        q = q.filter(EvidenceCard.source_id == source_id)
    if status:
        q = q.filter(EvidenceCard.status == status)
    return q.order_by(EvidenceCard.created_at.desc()).all()


def get_evidence(db: Session, project_id: str, evidence_id: str) -> EvidenceCard:
    e = db.query(EvidenceCard).filter(EvidenceCard.id == evidence_id).first()
    if not e or e.project_id != project_id:
        raise AppError(code="EVIDENCE_CARD_NOT_FOUND", message=f"未找到证据卡片 {evidence_id}")
    return e


def update_evidence(db: Session, project_id: str, evidence_id: str,
                    req: EvidenceUpdateRequest) -> EvidenceCard:
    e = get_evidence(db, project_id, evidence_id)
    if e.status != EvidenceStatus.CANDIDATE.value:
        raise AppError(code="EVIDENCE_CARD_NOT_EDITABLE", message="只能修改候选证据")
    if req.summary is not None:
        e.summary = req.summary
    if req.evidence_type is not None:
        e.evidence_type = req.evidence_type.value
    if req.relevance_to_requirement is not None:
        e.relevance_to_requirement = req.relevance_to_requirement
    db.commit()
    db.refresh(e)
    return e


def confirm_evidence(db: Session, project_id: str, evidence_id: str) -> EvidenceCard:
    e = get_evidence(db, project_id, evidence_id)
    if e.status != EvidenceStatus.CANDIDATE.value:
        raise AppError(code="EVIDENCE_CARD_NOT_EDITABLE", message="只能确认候选证据")

    e.status = EvidenceStatus.CONFIRMED.value
    e.confirmed_at = datetime.now(timezone.utc)
    _advance_project_to(db, project_id, "EVIDENCE_CONFIRMED")
    db.commit()
    db.refresh(e)
    return e


def reject_evidence(db: Session, project_id: str, evidence_id: str) -> EvidenceCard:
    e = get_evidence(db, project_id, evidence_id)
    if e.status != EvidenceStatus.CANDIDATE.value:
        raise AppError(code="EVIDENCE_CARD_NOT_EDITABLE", message="只能拒绝候选证据")

    e.status = EvidenceStatus.REJECTED.value
    e.confirmed_at = None
    db.commit()
    db.refresh(e)
    return e
