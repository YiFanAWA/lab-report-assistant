"""项目 API 路由。

只做协议映射，不拥有业务语义。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.infrastructure.database.engine import SessionLocal
from app.core.errors import AppError, ErrorResponse
from app.modules.projects import service as project_service
from app.modules.projects.contracts import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectListResponse,
)

router = APIRouter(prefix="/api/projects")


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _project_to_response(p) -> ProjectResponse:
    return ProjectResponse(
        id=p.id,
        name=p.name,
        topic=p.topic,
        status=p.status,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat(),
    )


@router.post("", response_model=ProjectResponse, responses={400: {"model": ErrorResponse}})
def create_project(req: ProjectCreateRequest, db: Session = Depends(_db)):
    project = project_service.create_project(db, req)
    return _project_to_response(project)


@router.get("", response_model=ProjectListResponse)
def list_projects(db: Session = Depends(_db)):
    projects = project_service.list_projects(db)
    return ProjectListResponse(items=[_project_to_response(p) for p in projects])


@router.get("/{project_id}", response_model=ProjectResponse, responses={404: {"model": ErrorResponse}})
def get_project(project_id: str, db: Session = Depends(_db)):
    project = project_service.get_project(db, project_id)
    return _project_to_response(project)
