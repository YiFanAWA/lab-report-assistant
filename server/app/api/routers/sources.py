"""来源 API 路由。

只做协议映射，不拥有业务语义。
"""

import re

from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.infrastructure.database.engine import SessionLocal
from app.core.errors import AppError
from app.modules.sources import service as sources_service
from app.modules.sources.contracts import (
    UrlSourceRequest,
    SourceResponse,
    SourceListResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}/sources")


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _field_from_validation(exc: ValidationError) -> str | None:
    if not exc.errors():
        return None
    loc = exc.errors()[0].get("loc", ())
    return str(loc[0]) if loc else None


def _safe_pdf_filename(filename: str) -> str:
    raw_name = filename.replace("\\", "/").split("/")[-1]
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._-")
    if not safe_name:
        return "upload.pdf"
    if not safe_name.lower().endswith(".pdf"):
        return f"{safe_name}.pdf"
    return safe_name


# --- 登记 URL 来源 ---

@router.post("/url", response_model=SourceResponse, status_code=201)
def create_url_source(project_id: str, body: dict,
                       db: Session = Depends(_db)):
    try:
        req = UrlSourceRequest(**body)
    except ValidationError as exc:
        field = _field_from_validation(exc)
        if field == "url":
            raise AppError(code="SOURCE_URL_REQUIRED", message="URL 不能为空",
                           field="url")
        raise AppError(code="REQUEST_VALIDATION_ERROR",
                       message="请求参数不符合要求", field=field)
    source, job_id = sources_service.create_url_source(db, project_id, req)
    return sources_service._source_to_response(source, job_id=job_id)


# --- 上传 PDF 文件 ---

@router.post("/pdf", response_model=SourceResponse, status_code=201)
async def create_pdf_source(project_id: str,
                             file: UploadFile = File(...),
                             title: str = Form(""),
                             db: Session = Depends(_db)):
    MAX_SIZE = 10 * 1024 * 1024
    content = await file.read()
    if len(content) == 0:
        raise AppError(code="SOURCE_FILE_EMPTY", message="文件不能为空",
                       field="file")
    if len(content) > MAX_SIZE:
        raise AppError(code="SOURCE_FILE_TOO_LARGE",
                       message="文件大小超过 10 MB 上限", field="file")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise AppError(code="SOURCE_FILE_UNSUPPORTED",
                       message="仅支持 PDF 文件", field="file")

    original_filename = _safe_pdf_filename(file.filename)
    source, job_id = sources_service.create_pdf_source(
        db, project_id, title, content, original_filename)
    return sources_service._source_to_response(source, job_id=job_id)


# --- 来源列表 ---

@router.get("", response_model=SourceListResponse)
def list_sources(project_id: str, db: Session = Depends(_db)):
    sources = sources_service.list_sources(db, project_id)
    return sources_service._source_list_to_response(sources)


# --- 来源详情 ---

@router.get("/{source_id}", response_model=SourceResponse)
def get_source(project_id: str, source_id: str,
               db: Session = Depends(_db)):
    source = sources_service.get_source_by_id_and_project(
        db, project_id, source_id)
    return sources_service._source_to_response(source)


# --- 删除来源 ---

@router.delete("/{source_id}", response_model=SourceResponse)
def delete_source(project_id: str, source_id: str,
                  db: Session = Depends(_db)):
    source = sources_service.delete_source(db, project_id, source_id)
    return sources_service._source_to_response(source)


# --- 完成来源收集 ---

@router.post("/complete")
def complete_sources(project_id: str, db: Session = Depends(_db)):
    project = sources_service.complete_sources(db, project_id)
    return {"project_id": project.id, "status": project.status}
