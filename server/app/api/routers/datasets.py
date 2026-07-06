"""数据集 API 路由。

只做协议映射，不拥有业务语义。
前缀 /api/projects/{project_id}/datasets。
"""

import re

from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.infrastructure.database.engine import SessionLocal
from app.core.errors import AppError
from app.modules.datasets import service as datasets_service
from app.modules.datasets.contracts import (
    DatasetUrlRequest,
    DatasetResponse,
    DatasetListResponse,
    DatasetVersionListResponse,
    CompleteDatasetsResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}/datasets")


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


def _safe_upload_filename(filename: str, ext: str) -> str:
    """清洗上传文件名，限制为安全字符并强制扩展名。"""
    raw_name = filename.replace("\\", "/").split("/")[-1]
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._-")
    if not safe_name:
        return f"upload.{ext}"
    if not safe_name.lower().endswith(f".{ext}"):
        return f"{safe_name}.{ext}"
    return safe_name


# --- 上传 CSV/Excel 文件 ---


@router.post("/upload", response_model=DatasetResponse, status_code=201)
async def upload_dataset(
    project_id: str,
    file: UploadFile = File(...),
    title: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(_db),
):
    """上传 CSV/Excel 文件，创建 Dataset 与首个版本。"""
    from app.core.config import settings

    content = await file.read()
    if len(content) == 0:
        raise AppError(code="DATASET_FILE_EMPTY", message="文件不能为空",
                       field="file")
    if len(content) > settings.dataset_max_size_bytes:
        raise AppError(code="DATASET_FILE_TOO_LARGE",
                       message="文件大小超过上限", field="file")

    original_filename = file.filename or "upload.csv"
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    if ext not in ("csv", "xlsx"):
        raise AppError(code="DATASET_FILE_UNSUPPORTED",
                       message="仅支持 CSV 和 XLSX 文件", field="file")

    safe_filename = _safe_upload_filename(original_filename, ext)
    dataset, job_id = datasets_service.create_file_dataset(
        db, project_id, title, description, content, safe_filename)
    return datasets_service.dataset_to_response(dataset, job_id=job_id)


# --- 登记 CSV/Excel 公开 URL ---


@router.post("/url", response_model=DatasetResponse, status_code=201)
def create_url_dataset(project_id: str, body: dict,
                       db: Session = Depends(_db)):
    try:
        req = DatasetUrlRequest(**body)
    except ValidationError as exc:
        field = _field_from_validation(exc)
        if field == "url":
            raise AppError(code="DATASET_URL_REQUIRED", message="URL 不能为空",
                           field="url")
        raise AppError(code="REQUEST_VALIDATION_ERROR",
                       message="请求参数不符合要求", field=field)
    dataset, job_id = datasets_service.create_url_dataset(
        db, project_id, req.url, req.title, req.description)
    return datasets_service.dataset_to_response(dataset, job_id=job_id)


# --- 数据集列表 ---


@router.get("", response_model=DatasetListResponse)
def list_datasets(project_id: str, db: Session = Depends(_db)):
    datasets = datasets_service.list_datasets(db, project_id)
    return datasets_service.dataset_list_to_response(datasets)


# --- 数据集详情 ---


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(project_id: str, dataset_id: str,
                db: Session = Depends(_db)):
    dataset = datasets_service.get_dataset_by_id_and_project(
        db, project_id, dataset_id)
    return datasets_service.dataset_to_response(dataset)


# --- 数据集版本列表 ---


@router.get("/{dataset_id}/versions",
            response_model=DatasetVersionListResponse)
def list_dataset_versions(project_id: str, dataset_id: str,
                          db: Session = Depends(_db)):
    # 先校验归属
    datasets_service.get_dataset_by_id_and_project(db, project_id, dataset_id)
    versions = datasets_service.list_dataset_versions(db, dataset_id)
    return datasets_service.version_list_to_response(versions)


# --- 软删除数据集 ---


@router.delete("/{dataset_id}", response_model=DatasetResponse)
def delete_dataset(project_id: str, dataset_id: str,
                   db: Session = Depends(_db)):
    dataset = datasets_service.delete_dataset(db, project_id, dataset_id)
    return datasets_service.dataset_to_response(dataset)


# --- 重新上传（创建新版本） ---


@router.post("/{dataset_id}/reupload",
             response_model=DatasetResponse)
async def reupload_dataset(
    project_id: str,
    dataset_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(_db),
):
    """重新上传文件，创建新版本，旧版本变 SUPERSEDED。"""
    from app.core.config import settings

    content = await file.read()
    if len(content) == 0:
        raise AppError(code="DATASET_FILE_EMPTY", message="文件不能为空",
                       field="file")
    if len(content) > settings.dataset_max_size_bytes:
        raise AppError(code="DATASET_FILE_TOO_LARGE",
                       message="文件大小超过上限", field="file")

    original_filename = file.filename or "upload.csv"
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    if ext not in ("csv", "xlsx"):
        raise AppError(code="DATASET_FILE_UNSUPPORTED",
                       message="仅支持 CSV 和 XLSX 文件", field="file")

    safe_filename = _safe_upload_filename(original_filename, ext)
    dataset, job_id = datasets_service.create_file_dataset(
        db, project_id, None, None, content, safe_filename,
        existing_dataset_id=dataset_id)
    return datasets_service.dataset_to_response(dataset, job_id=job_id)


# --- 完成数据集收集 ---


@router.post("/complete", response_model=CompleteDatasetsResponse)
def complete_datasets(project_id: str, db: Session = Depends(_db)):
    project = datasets_service.complete_datasets(db, project_id)
    return datasets_service.complete_datasets_to_response(project)
