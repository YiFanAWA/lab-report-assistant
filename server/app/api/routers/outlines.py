"""大纲 API 路由。

只做协议映射，不拥有业务语义。
前缀 /api/projects/{project_id}。

路由：
  POST /outline/generate                         触发生成大纲候选
  GET  /outline                                  大纲列表（支持 status 过滤）
  GET  /outline/{outline_id}                     大纲详情
  PUT  /outline/{outline_id}                     编辑大纲（sections 字段）
  POST /outline/{outline_id}/confirm             确认大纲
  POST /outline/{outline_id}/reject             拒绝大纲
  POST /outline/{outline_id}/word/generate       触发 Word 生成
  POST /outline/{outline_id}/ppt/generate        触发 PPT 生成

  SPEC 0010 Word 模板支持：
  POST /word-template                            上传 Word 模板
  GET  /word-template                            获取 Word 模板信息
  DELETE /word-template                          删除 Word 模板
  GET  /word-template/download                   下载 Word 模板
"""

from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.infrastructure.database.engine import SessionLocal
from app.core.errors import AppError
from app.modules.outlines import service as outline_service
from app.modules.outlines.contracts import (
    UpdateOutlineRequest,
    OutlineResponse,
    OutlineListResponse,
    GenerateOutlineResponse,
    GenerateDeliverableResponse,
    WordTemplateResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}")


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


# --- 触发生成大纲候选 ---


@router.post("/outline/generate",
             response_model=GenerateOutlineResponse,
             status_code=201)
def generate_outline(project_id: str, db: Session = Depends(_db)):
    job_id = outline_service.generate_outline(db, project_id)
    return GenerateOutlineResponse(job_id=job_id)


# --- 大纲列表 ---


@router.get("/outline", response_model=OutlineListResponse)
def list_outlines(project_id: str,
                  status: str | None = None,
                  db: Session = Depends(_db)):
    outlines = outline_service.list_outlines(
        db, project_id, status=status)
    return outline_service.outline_list_to_response(outlines)


# --- 大纲详情 ---


@router.get("/outline/{outline_id}", response_model=OutlineResponse)
def get_outline(project_id: str, outline_id: str,
                 db: Session = Depends(_db)):
    outline = outline_service.get_outline_by_project(
        db, project_id, outline_id)
    return outline_service.outline_to_response(outline)


# --- 编辑大纲 ---


@router.put("/outline/{outline_id}", response_model=OutlineResponse)
def update_outline(project_id: str, outline_id: str, body: dict,
                    db: Session = Depends(_db)):
    try:
        req = UpdateOutlineRequest(**body)
    except ValidationError as exc:
        raise AppError(
            code="REQUEST_VALIDATION_ERROR",
            message="请求参数不符合要求",
            field=_field_from_validation(exc),
        )
    outline = outline_service.update_outline(
        db, project_id, outline_id, req)
    return outline_service.outline_to_response(outline)


# --- 确认大纲 ---


@router.post("/outline/{outline_id}/confirm",
              response_model=OutlineResponse)
def confirm_outline(project_id: str, outline_id: str,
                     db: Session = Depends(_db)):
    outline = outline_service.confirm_outline(db, project_id, outline_id)
    return outline_service.outline_to_response(outline)


# --- 拒绝大纲 ---


@router.post("/outline/{outline_id}/reject",
              response_model=OutlineResponse)
def reject_outline(project_id: str, outline_id: str,
                    db: Session = Depends(_db)):
    outline = outline_service.reject_outline(db, project_id, outline_id)
    return outline_service.outline_to_response(outline)


# --- 触发 Word 生成 ---


@router.post("/outline/{outline_id}/word/generate",
             response_model=GenerateDeliverableResponse,
             status_code=201)
def generate_word(project_id: str, outline_id: str,
                   db: Session = Depends(_db)):
    job_id, deliverable_id = outline_service.generate_word(
        db, project_id, outline_id)
    # 检查是否有项目级 Word 模板
    template = outline_service.get_word_template(db, project_id)
    template_used = template is not None
    return GenerateDeliverableResponse(
        job_id=job_id,
        deliverable_id=deliverable_id,
        template_used=template_used,
    )


# --- 触发 PPT 生成 ---


@router.post("/outline/{outline_id}/ppt/generate",
             response_model=GenerateDeliverableResponse,
             status_code=201)
def generate_ppt(project_id: str, outline_id: str,
                  db: Session = Depends(_db)):
    job_id, deliverable_id = outline_service.generate_ppt(
        db, project_id, outline_id)
    return GenerateDeliverableResponse(
        job_id=job_id, deliverable_id=deliverable_id, template_used=False)


# --- SPEC 0010 Word 模板管理 ---


@router.post("/word-template",
             response_model=WordTemplateResponse,
             status_code=200)
def upload_word_template(project_id: str,
                          file: UploadFile = File(...),
                          db: Session = Depends(_db)):
    """上传或替换项目的 Word 模板。"""
    template = outline_service.upload_word_template(
        db, project_id, file)
    return outline_service.word_template_to_response(template)


@router.get("/word-template",
            response_model=WordTemplateResponse | None)
def get_word_template(project_id: str,
                       db: Session = Depends(_db)):
    """获取项目的 Word 模板信息。无模板返回 null。"""
    template = outline_service.get_word_template(db, project_id)
    if not template:
        return None
    return outline_service.word_template_to_response(template)


@router.delete("/word-template", status_code=204)
def delete_word_template(project_id: str,
                         db: Session = Depends(_db)):
    """删除项目的 Word 模板。"""
    outline_service.delete_word_template(db, project_id)
    return None


@router.get("/word-template/download")
def download_word_template(project_id: str,
                             db: Session = Depends(_db)):
    """下载项目的 Word 模板文件。"""
    info = outline_service.get_word_template_file_path(db, project_id)
    if not info:
        raise AppError(
            code="WORD_TEMPLATE_NOT_FOUND",
            message="项目未上传 Word 模板",
        )
    abs_path, original_filename = info
    media_type = ("application/vnd.openxmlformats-officedocument"
                  ".wordprocessingml.document")
    return FileResponse(
        path=str(abs_path),
        media_type=media_type,
        filename=original_filename,
    )
