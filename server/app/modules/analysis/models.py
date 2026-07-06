"""分析方案侧数据模型。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.engine import Base


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisPlan(Base):
    """分析方案实体。

    一个 DatasetVersion 可生成一个或多个 AnalysisPlan 候选。
    用户确认后状态变为 CONFIRMED。
    """

    __tablename__ = "analysis_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    dataset_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    dataset_version_id: Mapped[str] = mapped_column(String(32), nullable=False)
    cleaning_plan: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_plan: Mapped[str] = mapped_column(Text, nullable=False)
    chart_plan: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
