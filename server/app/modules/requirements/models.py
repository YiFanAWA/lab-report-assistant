"""需求侧数据模型。"""

import uuid
import hashlib
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.engine import Base


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RequirementSource(Base):
    __tablename__ = "requirement_sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    original_file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class RequirementPlan(Base):
    __tablename__ = "requirement_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ChangeRecord(Base):
    __tablename__ = "change_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False)
    change_type: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
