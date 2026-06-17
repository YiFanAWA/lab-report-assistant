"""项目数据模型。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.engine import Base
from app.modules.projects.status import ProjectStatus


def generate_project_id() -> str:
    """生成项目唯一标识。"""
    return f"proj_{uuid.uuid4().hex[:12]}"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_project_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ProjectStatus.DRAFT.value)
    workspace_root: Mapped[str] = mapped_column(String(1000), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
