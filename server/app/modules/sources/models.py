"""来源与证据侧数据模型。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.engine import Base


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SourceRecord(Base):
    __tablename__ = "source_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    original_file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    collection_status: Mapped[str] = mapped_column(String(32), nullable=False)
    access_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class ParsedDocument(Base):
    __tablename__ = "parsed_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(32), nullable=False)
    parser_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    parsed_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    location_map_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False)
    parse_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class EvidenceCard(Base):
    __tablename__ = "evidence_cards"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(32), nullable=False)
    parsed_document_id: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_quote: Mapped[str] = mapped_column(String(2000), nullable=False)
    location_label: Mapped[str] = mapped_column(String(500), nullable=False)
    relevance_to_requirement: Mapped[str] = mapped_column(String(1000), nullable=False)
    candidate_source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
