"""项目核心服务。

项目工作区的创建、查询与持久化。拥有项目业务语义。
"""

import shutil

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.projects.models import Project, generate_project_id
from app.modules.projects.status import ProjectStatus


def create_project(db: Session, req: ProjectCreateRequest) -> Project:
    """创建实验项目，保存到数据库。"""
    if not req.name.strip():
        raise AppError(code="PROJECT_NAME_REQUIRED", message="项目名称不能为空", field="name")
    if not req.topic.strip():
        raise AppError(code="PROJECT_TOPIC_REQUIRED", message="课题不能为空", field="topic")

    project_id = generate_project_id()
    workspace_root = settings.project_data_root / project_id
    workspace_root.mkdir(parents=True, exist_ok=False)

    project = Project(
        id=project_id,
        name=req.name.strip(),
        topic=req.topic.strip(),
        status=ProjectStatus.DRAFT.value,
        workspace_root=str(workspace_root),
    )
    try:
        db.add(project)
        db.commit()
        db.refresh(project)
    except Exception:
        db.rollback()
        shutil.rmtree(workspace_root, ignore_errors=True)
        raise
    return project


def list_projects(db: Session) -> list[Project]:
    """按更新时间降序列出所有项目。"""
    return (
        db.query(Project)
        .order_by(Project.updated_at.desc())
        .all()
    )


def get_project(db: Session, project_id: str) -> Project:
    """查询单个项目，不存在时抛出 AppError。"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise AppError(
            code="PROJECT_NOT_FOUND",
            message=f"未找到项目 {project_id}",
        )
    return project
