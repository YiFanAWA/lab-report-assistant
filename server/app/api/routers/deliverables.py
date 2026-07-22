"""交付物 API 路由。

只做协议映射，不拥有业务语义。
前缀 /api/projects/{project_id}。

路由：
  GET  /deliverables                                          交付物列表
  GET  /deliverables/{deliverable_id}/versions                交付物版本列表
  GET  /deliverables/{deliverable_id}/versions/{version_id}/download  下载交付物文件
  POST /complete                                              完成项目
"""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.infrastructure.database.engine import SessionLocal
from app.modules.outlines import service as outline_service
from app.modules.outlines.contracts import (
    DeliverableListResponse,
    DeliverableVersionListResponse,
    CompleteProjectResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}")


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- 交付物列表 ---


@router.get("/deliverables", response_model=DeliverableListResponse)
def list_deliverables(project_id: str,
                      status: str | None = None,
                      db: Session = Depends(_db)):
    deliverables = outline_service.list_deliverables(
        db, project_id, status=status)
    return outline_service.deliverable_list_to_response(deliverables)


# --- 交付物版本列表 ---


@router.get("/deliverables/{deliverable_id}/versions",
             response_model=DeliverableVersionListResponse)
def list_deliverable_versions(project_id: str, deliverable_id: str,
                                db: Session = Depends(_db)):
    versions = outline_service.list_deliverable_versions(
        db, project_id, deliverable_id)
    return outline_service.version_list_to_response(versions)


# --- 下载交付物文件 ---


@router.get("/deliverables/{deliverable_id}/versions/{version_id}/download")
def download_deliverable(project_id: str, deliverable_id: str,
                          version_id: str,
                          db: Session = Depends(_db)):
    abs_path, filename, media_type = outline_service.get_deliverable_file_path(
        db, project_id, deliverable_id, version_id)
    return FileResponse(
        path=str(abs_path),
        media_type=media_type,
        filename=filename,
    )


# --- 完成项目 ---


@router.post("/complete", response_model=CompleteProjectResponse)
def complete_project(project_id: str, db: Session = Depends(_db)):
    project = outline_service.complete_project(db, project_id)
    return outline_service.complete_project_to_response(project)
