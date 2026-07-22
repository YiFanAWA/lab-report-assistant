"""大纲与交付物核心数据模型。

Outline、Deliverable、DeliverableVersion ORM 实体。

设计要点：
- Outline.sections_json 存储章节列表，每章节含 title/content/source_type/source_ids
- Deliverable 关联 Outline，类型 WORD 或 PPT
- DeliverableVersion 每次生成创建新版本，旧版本保留不删除
- 失败状态不被覆盖为成功
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.engine import Base


def _uid() -> str:
    """生成 12 位十六进制唯一标识。"""
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


class Outline(Base):
    """统一实验大纲实体。

    基于已确认的实验要求、证据卡片、数据概览、分析方案和执行结果生成。
    用户确认后才能进入 Word/PPT 生成阶段。
    一个项目可有多个 Outline（重新生成时旧的变 STALE）。
    """

    __tablename__ = "outlines"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # 大纲内容 JSON：章节列表，每章节含 id/title/content/source_type/source_ids
    sections_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_source: Mapped[str] = mapped_column(String(32), nullable=False)
    code_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Deliverable(Base):
    """交付物实体（Word 或 PPT）。

    从同一份已确认大纲生成，不直接从模型临时上下文生成。
    一个 Outline 可对应多个 Deliverable（Word 和 PPT 各一，重新生成时旧的变 STALE）。
    """

    __tablename__ = "deliverables"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    outline_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    deliverable_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # WORD 或 PPT
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class DeliverableVersion(Base):
    """交付物版本实体。

    每次生成创建一个新版本，旧版本保留不删除。
    记录文件路径、生成状态和追溯索引。
    失败状态不被覆盖为成功；用户必须重新生成才能获得新版本。
    """

    __tablename__ = "deliverable_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    deliverable_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
