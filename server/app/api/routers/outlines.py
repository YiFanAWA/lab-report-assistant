"""大纲 API 路由。

只做协议映射，不拥有业务语义。
前缀 /api/projects/{project_id}。

路由：
  POST /outline/generate                         触发生成大纲候选
  POST /outline/stream-generate                  SSE 流式生成大纲候选（SPEC 0019）
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

import json

from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.infrastructure.database.engine import SessionLocal
from app.core.errors import AppError
from app.modules.llm.gateway import get_outline_provider
from app.modules.outlines import service as outline_service
from app.modules.outlines.contracts import (
    UpdateOutlineRequest,
    OutlineResponse,
    OutlineListResponse,
    GenerateOutlineResponse,
    GenerateDeliverableResponse,
    GeneratePptRequest,
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


# --- SPEC 0019 流式生成大纲候选 ---


def _serialize_outline_sse_event(event) -> str:
    """序列化 StreamOutlineEvent 为 SSE 文本块。

    SSE 格式：
        event: <event_name>
        data: <json_data>

    事件块以 \\n\\n 结尾分隔。
    """
    if isinstance(event, outline_service.StreamOutlineChunkEvent):
        data = json.dumps({"text": event.text}, ensure_ascii=False)
        return f"event: chunk\ndata: {data}\n\n"
    elif isinstance(event, outline_service.StreamOutlineDoneEvent):
        data = json.dumps({
            "outline_id": event.outline_id,
            "candidate_source": event.candidate_source,
            "fallback_used": event.fallback_used,
        }, ensure_ascii=False)
        return f"event: done\ndata: {data}\n\n"
    elif isinstance(event, outline_service.StreamOutlineErrorEvent):
        data = json.dumps({
            "error_code": event.error_code,
            "message": event.message,
            "partial_text": event.partial_text,
        }, ensure_ascii=False)
        return f"event: error\ndata: {data}\n\n"
    return ""


@router.post("/outline/stream-generate")
def stream_generate_outline_endpoint(project_id: str):
    """SSE 流式生成大纲。

    SPEC 0019 大纲生成流式化。

    返回 text/event-stream，事件格式：
    - event: chunk / data: {"text": "..."}
    - event: done / data: {"outline_id": "...", "candidate_source": "...", "fallback_used": false}
    - event: error / data: {"error_code": "...", "message": "...", "partial_text": "..."}

    预校验：在 StreamingResponse 开始前校验 project 存在，
    确保 PROJECT_NOT_FOUND 能返回结构化 404 而非 SSE 错误流。
    流式期间错误（状态/执行记录校验、LLM 中断等）走 StreamOutlineErrorEvent。
    """
    provider = get_outline_provider()

    # 预校验：项目存在（确保 PROJECT_NOT_FOUND 返回 404 而非 SSE 错误）
    db = SessionLocal()
    try:
        from app.modules.projects import service as project_service
        project_service.get_project(db, project_id)
    finally:
        db.close()

    def event_stream():
        # 端点层创建独立 db session，传入 service 由其管理生命周期
        # service 内部会重新校验（Phase 1）并管理 db.close() / 重新打开
        db = SessionLocal()
        try:
            for event in outline_service.stream_generate_outline(
                db, project_id, provider
            ):
                yield _serialize_outline_sse_event(event)
        except AppError as e:
            # Phase 1 校验失败（状态/执行记录等），转为 error 事件
            yield _serialize_outline_sse_event(
                outline_service.StreamOutlineErrorEvent(
                    error_code=e.code,
                    message=e.message,
                    partial_text="",
                )
            )
        finally:
            try:
                db.close()
            except Exception:
                # session 可能已被 service 关闭（Phase 1 后 db.close()）
                pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx 禁用缓冲
        },
    )


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
                  body: GeneratePptRequest | None = None,
                  db: Session = Depends(_db)):
    """触发 PPT 生成（SPEC 0011：支持可选 config 配置）。"""
    config = body.config.model_dump() if body else None
    job_id, deliverable_id = outline_service.generate_ppt(
        db, project_id, outline_id, config=config)
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
