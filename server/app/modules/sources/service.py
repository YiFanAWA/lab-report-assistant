"""来源与证据核心服务。

拥有来源登记、采集状态、解析状态、证据卡片候选、确认和 STALE 传播的业务语义。
API、Worker、提示词只能调用本服务，不能直接修改来源或证据状态。
"""

import ipaddress
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.modules.projects import service as project_service
from app.modules.projects.status import ProjectStatus
from app.modules.requirements.models import ChangeRecord
from app.modules.sources.models import Source, ParsedDocument, EvidenceCard, _uid
from app.modules.sources.contracts import (
    UrlSourceRequest,
    UpdateEvidenceCardRequest,
    SourceResponse,
    SourceListResponse,
    ParsedDocumentResponse,
    EvidenceCardResponse,
    EvidenceCardListResponse,
)
from app.modules.sources.status import (
    SourceKind,
    SourceStatus,
    EvidenceType,
    EvidenceCardStatus,
    CandidateSource,
    SourceChangeType,
)
from app.modules.jobs import service as job_service
from app.modules.jobs.status import JobType


# --- 内部辅助 ---

_POST_REQUIREMENT_CONFIRMED_STATUSES = [
    ProjectStatus.REQUIREMENT_CONFIRMED.value,
    ProjectStatus.SOURCES_COLLECTED.value,
    ProjectStatus.EVIDENCE_CONFIRMED.value,
    ProjectStatus.DATASET_READY.value,
    ProjectStatus.ANALYSIS_PLANNED.value,
    ProjectStatus.ANALYSIS_CONFIRMED.value,
    ProjectStatus.EXECUTING.value,
    ProjectStatus.RESULT_CONFIRMED.value,
    ProjectStatus.OUTLINE_CONFIRMED.value,
    ProjectStatus.GENERATING.value,
    ProjectStatus.COMPLETED.value,
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_project(db: Session, project_id: str):
    return project_service.get_project(db, project_id)


def _ensure_project_ready_for_sources(project) -> None:
    """校验项目状态是 REQUIREMENT_CONFIRMED 或之后。"""
    if project.status not in _POST_REQUIREMENT_CONFIRMED_STATUSES:
        raise AppError(
            code="PROJECT_REQUIREMENT_NOT_CONFIRMED",
            message="项目需求未确认，无法登记来源",
        )


def _validate_public_url(url: str) -> tuple[bool, str | None]:
    """校验 URL 是否公开可访问。

    拒绝 localhost、私有 IP 段、file://、ftp:// 等。
    返回 (is_valid, error_code)。
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if not scheme:
        return (False, "SOURCE_URL_INVALID")
    if scheme not in ("http", "https"):
        return (False, "SOURCE_URL_SCHEME_UNSUPPORTED")

    hostname = parsed.hostname
    if not hostname:
        return (False, "SOURCE_URL_INVALID")

    if hostname == "localhost":
        return (False, "SOURCE_URL_NOT_PUBLIC")

    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return (False, "SOURCE_URL_NOT_PUBLIC")
    except ValueError:
        # 非 IP 字面量，视为域名，允许通过
        pass

    return (True, None)


def _add_change(db: Session, project_id: str, change_type: str,
                summary: str) -> None:
    """写入变更记录，复用 requirements.models.ChangeRecord。"""
    rec = ChangeRecord(
        project_id=project_id,
        change_type=change_type,
        summary=summary,
    )
    db.add(rec)


def _mark_evidence_stale(db: Session, source_id: str) -> int:
    """将关联证据卡片标记为 STALE，返回受影响行数。"""
    cards = (
        db.query(EvidenceCard)
        .filter(
            EvidenceCard.source_id == source_id,
            EvidenceCard.status.in_([
                EvidenceCardStatus.CANDIDATE.value,
                EvidenceCardStatus.CONFIRMED.value,
                EvidenceCardStatus.REJECTED.value,
            ]),
        )
        .all()
    )
    for card in cards:
        card.status = EvidenceCardStatus.STALE.value
    return len(cards)


def _source_to_response(s: Source, job_id: str | None = None) -> SourceResponse:
    """将 Source ORM 模型转换为 SourceResponse。"""
    return SourceResponse(
        id=s.id,
        project_id=s.project_id,
        source_kind=s.source_kind,
        title=s.title,
        url=s.url,
        file_path=s.file_path,
        content_type=s.content_type,
        content_hash=s.content_hash,
        status=s.status,
        error_code=s.error_code,
        error_message=s.error_message,
        created_at=s.created_at.isoformat(),
        fetched_at=s.fetched_at.isoformat() if s.fetched_at else None,
        parsed_at=s.parsed_at.isoformat() if s.parsed_at else None,
        job_id=job_id,
    )


# --- 来源登记 ---

def create_url_source(db: Session, project_id: str,
                      req: UrlSourceRequest) -> tuple[Source, str]:
    """登记公开 URL 来源，创建 FETCH_URL 后台任务。

    校验：项目存在、项目状态 REQUIREMENT_CONFIRMED 或之后、URL 公开性、URL 协议。
    返回 (source, job_id)。
    """
    project = _ensure_project(db, project_id)
    _ensure_project_ready_for_sources(project)

    url = req.url.strip()
    if not url:
        raise AppError(code="SOURCE_URL_REQUIRED", message="URL 不能为空",
                       field="url")

    is_valid, error_code = _validate_public_url(url)
    if not is_valid:
        if error_code == "SOURCE_URL_SCHEME_UNSUPPORTED":
            raise AppError(code="SOURCE_URL_SCHEME_UNSUPPORTED",
                           message="仅支持 http 和 https 协议", field="url")
        if error_code == "SOURCE_URL_NOT_PUBLIC":
            raise AppError(code="SOURCE_URL_NOT_PUBLIC",
                           message="URL 指向非公开地址", field="url")
        raise AppError(code="SOURCE_URL_INVALID", message="URL 格式不正确",
                       field="url")

    source_id = _uid()
    title = (req.title.strip() if req.title and req.title.strip() else url)
    source = Source(
        id=source_id,
        project_id=project_id,
        source_kind=SourceKind.URL.value,
        title=title,
        url=url,
        status=SourceStatus.PENDING.value,
    )
    db.add(source)

    job = job_service.create_job(
        db,
        project_id=project_id,
        job_type=JobType.FETCH_URL.value,
        input_data={"source_id": source_id, "url": url},
    )

    _add_change(db, project_id, SourceChangeType.SOURCE_CREATED.value,
                f"登记 URL 来源：{title}")
    db.commit()
    db.refresh(source)
    return (source, job.id)


def create_pdf_source(db: Session, project_id: str, title: str | None,
                      file_content: bytes,
                      original_filename: str) -> tuple[Source, str]:
    """上传 PDF 文件来源，保存到受控工作区，创建 PARSE_DOCUMENT 后台任务。

    返回 (source, job_id)。
    """
    project = _ensure_project(db, project_id)
    _ensure_project_ready_for_sources(project)

    if not file_content:
        raise AppError(code="SOURCE_FILE_EMPTY", message="文件不能为空",
                       field="file")

    source_id = _uid()
    dest_dir = settings.project_data_root / project_id / "sources" / source_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / "raw.pdf"
    with open(dest_path, "wb") as f:
        f.write(file_content)

    display_title = (title.strip() if title and title.strip()
                     else original_filename or "PDF 文件")
    source = Source(
        id=source_id,
        project_id=project_id,
        source_kind=SourceKind.FILE.value,
        title=display_title,
        file_path=str(dest_path),
        status=SourceStatus.PENDING.value,
    )
    db.add(source)

    job = job_service.create_job(
        db,
        project_id=project_id,
        job_type=JobType.PARSE_DOCUMENT.value,
        input_data={"source_id": source_id},
    )

    _add_change(db, project_id, SourceChangeType.SOURCE_CREATED.value,
                f"上传 PDF 来源：{display_title}")
    db.commit()
    db.refresh(source)
    return (source, job.id)


# --- 来源查询 ---

def list_sources(db: Session, project_id: str) -> list[Source]:
    """按创建时间降序列出来源。"""
    _ensure_project(db, project_id)
    return (
        db.query(Source)
        .filter(Source.project_id == project_id)
        .order_by(Source.created_at.desc())
        .all()
    )


def get_source(db: Session, source_id: str) -> Source:
    """查询单个来源，不存在时抛出 SOURCE_NOT_FOUND。"""
    s = db.query(Source).filter(Source.id == source_id).first()
    if not s:
        raise AppError(code="SOURCE_NOT_FOUND",
                       message=f"未找到来源 {source_id}")
    return s


def get_source_by_id_and_project(db: Session, project_id: str,
                                  source_id: str) -> Source:
    """查询来源并校验归属，不匹配时抛出 SOURCE_NOT_FOUND。"""
    s = (
        db.query(Source)
        .filter(Source.id == source_id, Source.project_id == project_id)
        .first()
    )
    if not s:
        raise AppError(code="SOURCE_NOT_FOUND",
                       message=f"未找到来源 {source_id}")
    return s


# --- 来源删除 ---

def delete_source(db: Session, project_id: str, source_id: str) -> Source:
    """软删除来源：status=DELETED，关联证据卡片变 STALE。"""
    source = get_source_by_id_and_project(db, project_id, source_id)
    source.status = SourceStatus.DELETED.value
    _mark_evidence_stale(db, source_id)
    _add_change(db, project_id, SourceChangeType.SOURCE_DELETED.value,
                f"删除来源：{source.title}")
    db.commit()
    db.refresh(source)
    return source


# --- 完成来源收集 ---

def complete_sources(db: Session, project_id: str):
    """推进项目状态到 SOURCES_COLLECTED。

    前置条件：至少一个来源 status=PARSED。
    """
    project = _ensure_project(db, project_id)

    parsed_count = (
        db.query(Source)
        .filter(
            Source.project_id == project_id,
            Source.status == SourceStatus.PARSED.value,
        )
        .count()
    )
    if parsed_count == 0:
        raise AppError(code="PROJECT_NO_PARSED_SOURCE",
                       message="没有已解析的来源，无法完成来源收集")

    project.status = ProjectStatus.SOURCES_COLLECTED.value
    _add_change(db, project_id, SourceChangeType.SOURCES_COMPLETED.value,
                f"完成来源收集（已解析来源 {parsed_count} 个）")
    db.commit()
    db.refresh(project)
    return project


# --- 响应转换 ---

def _source_list_to_response(sources: list[Source]) -> SourceListResponse:
    return SourceListResponse(items=[_source_to_response(s) for s in sources])


def _parsed_document_to_response(pd: ParsedDocument) -> ParsedDocumentResponse:
    """将 ParsedDocument ORM 模型转换为 ParsedDocumentResponse。"""
    return ParsedDocumentResponse(
        id=pd.id,
        source_id=pd.source_id,
        project_id=pd.project_id,
        title=pd.title,
        parsed_text=pd.parsed_text,
        metadata_json=pd.metadata_json,
        parsed_at=pd.parsed_at.isoformat(),
    )


def _evidence_card_to_response(c: EvidenceCard) -> EvidenceCardResponse:
    """将 EvidenceCard ORM 模型转换为 EvidenceCardResponse。"""
    return EvidenceCardResponse(
        id=c.id,
        project_id=c.project_id,
        source_id=c.source_id,
        parsed_document_id=c.parsed_document_id,
        summary=c.summary,
        evidence_type=c.evidence_type,
        locator=c.locator,
        source_quote=c.source_quote,
        status=c.status,
        candidate_source=c.candidate_source,
        created_at=c.created_at.isoformat(),
        updated_at=c.updated_at.isoformat() if c.updated_at else None,
        confirmed_at=c.confirmed_at.isoformat() if c.confirmed_at else None,
    )


def _evidence_list_to_response(cards: list[EvidenceCard]) -> EvidenceCardListResponse:
    return EvidenceCardListResponse(
        items=[_evidence_card_to_response(c) for c in cards],
    )


# --- 证据卡片方法 ---

def generate_evidence_cards(db: Session, project_id: str,
                            source_id: str) -> str:
    """对已解析来源触发生成证据卡片候选，返回 job_id。

    前置条件：来源 status=PARSED。
    """
    project = _ensure_project(db, project_id)
    _ensure_project_ready_for_sources(project)

    source = get_source_by_id_and_project(db, project_id, source_id)
    if source.status != SourceStatus.PARSED.value:
        raise AppError(
            code="EVIDENCE_SOURCE_NOT_PARSED",
            message="来源未解析，无法生成证据卡片",
            field="source_id",
        )

    pd = (
        db.query(ParsedDocument)
        .filter(ParsedDocument.source_id == source_id)
        .first()
    )
    if not pd:
        raise AppError(
            code="EVIDENCE_SOURCE_NOT_PARSED",
            message="来源未解析，无法生成证据卡片",
            field="source_id",
        )

    job = job_service.create_job(
        db,
        project_id=project_id,
        job_type=JobType.GENERATE_EVIDENCE.value,
        input_data={
            "source_id": source_id,
            "parsed_document_id": pd.id,
        },
    )
    _add_change(db, project_id, SourceChangeType.EVIDENCE_CARD_GENERATED.value,
                f"触发证据卡片生成：{source.title}")
    db.commit()
    return job.id


def list_evidence_cards(db: Session, project_id: str,
                        source_id: str | None = None,
                        status: str | None = None) -> list[EvidenceCard]:
    """按条件筛选证据卡片列表，按创建时间降序。"""
    _ensure_project(db, project_id)
    query = db.query(EvidenceCard).filter(EvidenceCard.project_id == project_id)
    if source_id:
        query = query.filter(EvidenceCard.source_id == source_id)
    if status:
        query = query.filter(EvidenceCard.status == status)
    return query.order_by(EvidenceCard.created_at.desc()).all()


def get_evidence_card(db: Session, card_id: str) -> EvidenceCard:
    """查询单个证据卡片，不存在时抛出 EVIDENCE_CARD_NOT_FOUND。"""
    c = db.query(EvidenceCard).filter(EvidenceCard.id == card_id).first()
    if not c:
        raise AppError(code="EVIDENCE_CARD_NOT_FOUND",
                       message=f"未找到证据卡片 {card_id}")
    return c


def get_evidence_card_by_project(db: Session, project_id: str,
                                  card_id: str) -> EvidenceCard:
    """查询证据卡片并校验归属，不匹配时抛出 EVIDENCE_CARD_NOT_FOUND。"""
    c = (
        db.query(EvidenceCard)
        .filter(
            EvidenceCard.id == card_id,
            EvidenceCard.project_id == project_id,
        )
        .first()
    )
    if not c:
        raise AppError(code="EVIDENCE_CARD_NOT_FOUND",
                       message=f"未找到证据卡片 {card_id}")
    return c


def update_evidence_card(db: Session, project_id: str, card_id: str,
                          req: UpdateEvidenceCardRequest) -> EvidenceCard:
    """更新候选或过期证据卡片的可编辑字段。"""
    card = get_evidence_card_by_project(db, project_id, card_id)
    if card.status not in (
        EvidenceCardStatus.CANDIDATE.value,
        EvidenceCardStatus.STALE.value,
    ):
        raise AppError(
            code="EVIDENCE_CARD_NOT_EDITABLE",
            message="只能修改候选或过期卡片",
        )

    card.summary = req.summary
    card.evidence_type = req.evidence_type
    card.locator = req.locator
    if req.source_quote is not None:
        card.source_quote = req.source_quote
    card.updated_at = _now()

    _add_change(db, project_id, SourceChangeType.EVIDENCE_CARD_UPDATED.value,
                f"更新证据卡片：{card.summary[:40]}")
    db.commit()
    db.refresh(card)
    return card


def confirm_evidence_card(db: Session, project_id: str,
                           card_id: str) -> EvidenceCard:
    """确认候选证据卡片，状态变为 CONFIRMED。"""
    card = get_evidence_card_by_project(db, project_id, card_id)
    if card.status != EvidenceCardStatus.CANDIDATE.value:
        raise AppError(
            code="EVIDENCE_CARD_NOT_CONFIRMABLE",
            message="只能确认候选卡片",
        )
    card.status = EvidenceCardStatus.CONFIRMED.value
    card.confirmed_at = _now()
    card.updated_at = _now()
    _add_change(db, project_id,
                SourceChangeType.EVIDENCE_CARD_CONFIRMED.value,
                f"确认证据卡片：{card.summary[:40]}")
    db.commit()
    db.refresh(card)
    return card


def reject_evidence_card(db: Session, project_id: str,
                          card_id: str) -> EvidenceCard:
    """拒绝候选证据卡片，状态变为 REJECTED。"""
    card = get_evidence_card_by_project(db, project_id, card_id)
    if card.status != EvidenceCardStatus.CANDIDATE.value:
        raise AppError(
            code="EVIDENCE_CARD_NOT_CONFIRMABLE",
            message="只能拒绝候选卡片",
        )
    card.status = EvidenceCardStatus.REJECTED.value
    card.updated_at = _now()
    _add_change(db, project_id,
                SourceChangeType.EVIDENCE_CARD_REJECTED.value,
                f"拒绝证据卡片：{card.summary[:40]}")
    db.commit()
    db.refresh(card)
    return card


def complete_evidence(db: Session, project_id: str):
    """推进项目状态到 EVIDENCE_CONFIRMED。

    前置条件：至少一张证据卡片 status=CONFIRMED。
    """
    project = _ensure_project(db, project_id)

    confirmed_count = (
        db.query(EvidenceCard)
        .filter(
            EvidenceCard.project_id == project_id,
            EvidenceCard.status == EvidenceCardStatus.CONFIRMED.value,
        )
        .count()
    )
    if confirmed_count == 0:
        raise AppError(
            code="PROJECT_NO_CONFIRMED_EVIDENCE",
            message="没有已确认的证据卡片，无法完成证据确认",
        )

    project.status = ProjectStatus.EVIDENCE_CONFIRMED.value
    _add_change(db, project_id, SourceChangeType.EVIDENCE_COMPLETED.value,
                f"完成证据确认（已确认卡片 {confirmed_count} 张）")
    db.commit()
    db.refresh(project)
    return project


# --- Worker 调用的内部方法（供 Worker handlers 使用） ---

def mark_source_fetched(db: Session, source_id: str, content_type: str,
                         content_hash: str, file_path: str) -> Source:
    """更新 Source status=FETCHED 及相关字段。

    若旧 content_hash 与新不同，触发 STALE 传播。
    不提交事务（由调用方提交）。
    """
    source = get_source(db, source_id)
    old_hash = source.content_hash
    source.status = SourceStatus.FETCHED.value
    source.content_type = content_type
    source.content_hash = content_hash
    source.file_path = file_path
    source.fetched_at = _now()
    source.error_code = None
    source.error_message = None

    if old_hash and old_hash != content_hash:
        _mark_evidence_stale(db, source_id)

    _add_change(db, source.project_id,
                SourceChangeType.SOURCE_FETCHED.value,
                f"采集来源：{source.title}")
    db.flush()
    return source


def mark_source_failed(db: Session, source_id: str, error_code: str,
                        error_message: str) -> Source:
    """更新 Source status=FAILED 及错误信息。不提交事务。"""
    source = get_source(db, source_id)
    source.status = SourceStatus.FAILED.value
    source.error_code = error_code
    source.error_message = error_message
    db.flush()
    return source


def mark_source_parsed(db: Session, source_id: str,
                        parsed_document_id: str) -> Source:
    """更新 Source status=PARSED，记录 parsed_at。不提交事务。"""
    source = get_source(db, source_id)
    source.status = SourceStatus.PARSED.value
    source.parsed_at = _now()
    source.error_code = None
    source.error_message = None
    _add_change(db, source.project_id,
                SourceChangeType.SOURCE_PARSED.value,
                f"解析来源：{source.title}")
    db.flush()
    return source


def create_parsed_document(db: Session, source_id: str, project_id: str,
                            title: str | None, parsed_text: str,
                            metadata: dict) -> ParsedDocument:
    """创建 ParsedDocument 记录。不提交事务。

    若来源已存在 ParsedDocument，先删除旧记录（按 SPEC 约束：一个来源只能有一个）。
    """
    existing = (
        db.query(ParsedDocument)
        .filter(ParsedDocument.source_id == source_id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    import json
    pd = ParsedDocument(
        id=_uid(),
        source_id=source_id,
        project_id=project_id,
        title=title,
        parsed_text=parsed_text,
        metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
        parsed_at=_now(),
    )
    db.add(pd)
    db.flush()
    return pd


def save_evidence_card_drafts(db: Session, project_id: str, source_id: str,
                                parsed_document_id: str, drafts: list,
                                candidate_source: str) -> list[EvidenceCard]:
    """批量创建 EvidenceCard 记录，status=CANDIDATE。不提交事务。

    drafts 是 EvidenceCardDraft 列表（来自 evidence_card_provider）。
    """
    cards: list[EvidenceCard] = []
    now = _now()
    for draft in drafts:
        card = EvidenceCard(
            id=_uid(),
            project_id=project_id,
            source_id=source_id,
            parsed_document_id=parsed_document_id,
            summary=draft.summary,
            evidence_type=draft.evidence_type,
            locator=draft.locator,
            source_quote=draft.source_quote,
            status=EvidenceCardStatus.CANDIDATE.value,
            candidate_source=candidate_source,
            created_at=now,
            updated_at=now,
        )
        db.add(card)
        cards.append(card)
    if cards:
        _add_change(db, project_id,
                    SourceChangeType.EVIDENCE_CARD_GENERATED.value,
                    f"生成证据卡片候选 {len(cards)} 张")
    db.flush()
    return cards
