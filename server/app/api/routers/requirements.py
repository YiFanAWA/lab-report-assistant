"""实验要求 API 路由。

只做协议映射，不拥有业务语义。
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import ValidationError
from sqlalchemy.orm import Session
import re

from app.infrastructure.database.engine import SessionLocal
from app.core.errors import AppError
from app.modules.requirements import service as req_service
from app.modules.requirements.contracts import (
    TextSourceRequest,
    GeneratePlanRequest,
    UpdatePlanRequest,
    SourceListResponse,
)
from app.modules.llm.gateway import get_provider

router = APIRouter(prefix="/api/projects/{project_id}/requirements")


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


def _safe_upload_filename(filename: str) -> str:
    raw_name = filename.replace("\\", "/").split("/")[-1]
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._-")
    if not safe_name:
        return "requirement.docx"
    if not safe_name.lower().endswith(".docx"):
        return f"{safe_name}.docx"
    return safe_name


# --- 粘贴文本要求 ---

@router.post("/sources/text")
def add_text_source(project_id: str,
                    body: dict,
                    db: Session = Depends(_db)):
    try:
        req = TextSourceRequest(**body)
    except ValidationError as exc:
        field = _field_from_validation(exc)
        if field == "text":
            raise AppError(code="REQUIREMENT_TEXT_REQUIRED", message="实验要求不能为空", field="text")
        raise AppError(code="REQUEST_VALIDATION_ERROR", message="请求参数不符合要求", field=field)
    src = req_service.add_text_source(db, project_id, req)
    return req_service._source_to_response(src)


# --- 上传 Word 要求 ---

@router.post("/sources/docx")
async def add_docx_source(project_id: str,
                          file: UploadFile = File(...),
                          title: str = Form(""),
                          db: Session = Depends(_db)):
    # 文件大小限制 10 MB
    MAX_SIZE = 10 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise AppError(code="REQUIREMENT_FILE_TOO_LARGE", message="文件大小超过 10 MB 上限", field="file")

    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise AppError(code="REQUIREMENT_FILE_UNSUPPORTED", message="仅支持 .docx 格式", field="file")
    if len(content) == 0:
        raise AppError(code="REQUIREMENT_FILE_EMPTY", message="文件不能为空", field="file")

    # 保存文件到项目工作区
    from app.modules.projects.service import get_project
    from app.core.config import settings
    from datetime import datetime, timezone

    get_project(db, project_id)
    dest_dir = settings.project_data_root / project_id / "requirements"
    dest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_filename = _safe_upload_filename(file.filename)
    dest_path = dest_dir / f"{ts}_{safe_filename}"
    with open(dest_path, "wb") as f:
        f.write(content)

    # 提取正文
    from app.infrastructure.documents.docx_reader import extract_text
    try:
        text = extract_text(content)
    except Exception:
        raise AppError(code="REQUIREMENT_FILE_UNSUPPORTED", message="无法解析该 .docx 文件", field="file")

    src = req_service.add_docx_source(db, project_id, title, text, str(dest_path))
    return req_service._source_to_response(src)


# --- 来源列表 ---

@router.get("/sources")
def list_sources(project_id: str, db: Session = Depends(_db)):
    sources = req_service.list_sources(db, project_id)
    return SourceListResponse(items=[req_service._source_to_response(s) for s in sources])


# --- 生成任务单候选 ---

@router.post("/plans/generate")
def generate_plan(project_id: str,
                  body: dict,
                  db: Session = Depends(_db)):
    try:
        req = GeneratePlanRequest(**body)
    except ValidationError as exc:
        raise AppError(
            code="REQUEST_VALIDATION_ERROR",
            message="请求参数不符合要求",
            field=_field_from_validation(exc),
        )

    provider = get_provider()
    plan = req_service.generate_plan(db, project_id, req, provider)
    return req_service._plan_to_response(plan)


# --- 获取当前任务单 ---

@router.get("/plan")
def get_current_plan(project_id: str, db: Session = Depends(_db)):
    plan = req_service.get_current_plan(db, project_id)
    if not plan:
        raise AppError(code="REQUIREMENT_PLAN_NOT_FOUND", message="当前没有任务单")
    return req_service._plan_to_response(plan)


# --- 更新任务单 ---

@router.put("/plans/{plan_id}")
def update_plan(project_id: str, plan_id: str,
                body: dict,
                db: Session = Depends(_db)):
    try:
        req = UpdatePlanRequest(**body)
    except ValidationError:
        raise AppError(code="REQUIREMENT_PLAN_INVALID", message="任务单结构不符合要求")

    plan = req_service.update_plan(db, project_id, plan_id, req)
    return req_service._plan_to_response(plan)


# --- 确认任务单 ---

@router.post("/plans/{plan_id}/confirm")
def confirm_plan(project_id: str, plan_id: str,
                 db: Session = Depends(_db)):
    plan = req_service.confirm_plan(db, project_id, plan_id)
    return req_service._plan_to_response(plan)
