"""证据卡片 API 路由。

只做协议映射，不拥有业务语义。
前缀 /api/projects/{project_id}。
"""

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.infrastructure.database.engine import SessionLocal
from app.core.errors import AppError
from app.modules.llm.gateway import get_evidence_card_provider
from app.modules.sources import service as sources_service
from app.modules.sources.contracts import (
    UpdateEvidenceCardRequest,
    EvidenceCardResponse,
    EvidenceCardListResponse,
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


# --- 生成证据卡片候选 ---

@router.post("/sources/{source_id}/evidence/generate", status_code=201)
def generate_evidence_cards(project_id: str, source_id: str,
                              db: Session = Depends(_db)):
    job_id = sources_service.generate_evidence_cards(
        db, project_id, source_id)
    return {"job_id": job_id}


# --- 流式生成证据卡片（SPEC 0020） ---


def _serialize_evidence_sse_event(event) -> str:
    """序列化 StreamEvidenceEvent 为 SSE 文本块。

    SSE 格式：
        event: <event_name>
        data: <json_data>

    事件块以 \\n\\n 结尾分隔。
    """
    if isinstance(event, sources_service.StreamEvidenceChunkEvent):
        data = json.dumps({"text": event.text}, ensure_ascii=False)
        return f"event: chunk\ndata: {data}\n\n"
    elif isinstance(event, sources_service.StreamEvidenceDoneEvent):
        data = json.dumps({
            "card_count": event.card_count,
            "candidate_source": event.candidate_source,
            "fallback_used": event.fallback_used,
        }, ensure_ascii=False)
        return f"event: done\ndata: {data}\n\n"
    elif isinstance(event, sources_service.StreamEvidenceErrorEvent):
        data = json.dumps({
            "error_code": event.error_code,
            "message": event.message,
            "partial_text": event.partial_text,
        }, ensure_ascii=False)
        return f"event: error\ndata: {data}\n\n"
    return ""


@router.post("/sources/{source_id}/evidence/stream-generate")
def stream_generate_evidence_cards_endpoint(project_id: str, source_id: str):
    """SSE 流式生成证据卡片。

    SPEC 0020 证据卡片生成流式化。

    返回 text/event-stream，事件格式：
    - event: chunk / data: {"text": "..."}
    - event: done / data: {"card_count": 3, "candidate_source": "...", "fallback_used": false}
    - event: error / data: {"error_code": "...", "message": "...", "partial_text": "..."}

    预校验：在 StreamingResponse 开始前校验 project 和 source 存在，
    确保 PROJECT_NOT_FOUND / SOURCE_NOT_FOUND 能返回结构化 404 而非 SSE 错误流。
    流式期间错误（状态/解析记录校验、LLM 中断等）走 StreamEvidenceErrorEvent。
    """
    provider = get_evidence_card_provider()

    # 预校验：项目和来源存在（确保 404 而非 SSE 错误流）
    db = SessionLocal()
    try:
        from app.modules.projects import service as project_service
        project_service.get_project(db, project_id)
        sources_service.get_source_by_id_and_project(db, project_id, source_id)
    finally:
        db.close()

    def event_stream():
        # 端点层创建独立 db session，传入 service 由其管理生命周期
        # service 内部会重新校验（Phase 1）并管理 db.close() / 重新打开
        db = SessionLocal()
        try:
            for event in sources_service.stream_generate_evidence_cards(
                db, project_id, source_id, provider
            ):
                yield _serialize_evidence_sse_event(event)
        except AppError as e:
            # Phase 1 校验失败（状态/来源未解析等），转为 error 事件
            yield _serialize_evidence_sse_event(
                sources_service.StreamEvidenceErrorEvent(
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


# --- 证据卡片列表 ---

@router.get("/evidence", response_model=EvidenceCardListResponse)
def list_evidence(project_id: str,
                  source_id: str | None = None,
                  status: str | None = None,
                  db: Session = Depends(_db)):
    cards = sources_service.list_evidence_cards(
        db, project_id, source_id=source_id, status=status)
    return sources_service._evidence_list_to_response(cards)


# --- 更新证据卡片 ---

@router.put("/evidence/{card_id}", response_model=EvidenceCardResponse)
def update_evidence_card(project_id: str, card_id: str,
                          body: dict,
                          db: Session = Depends(_db)):
    try:
        req = UpdateEvidenceCardRequest(**body)
    except ValidationError as exc:
        raise AppError(
            code="REQUEST_VALIDATION_ERROR",
            message="请求参数不符合要求",
            field=_field_from_validation(exc),
        )
    card = sources_service.update_evidence_card(
        db, project_id, card_id, req)
    return sources_service._evidence_card_to_response(card)


# --- 确认证据卡片 ---

@router.post("/evidence/{card_id}/confirm",
              response_model=EvidenceCardResponse)
def confirm_evidence_card(project_id: str, card_id: str,
                           db: Session = Depends(_db)):
    card = sources_service.confirm_evidence_card(db, project_id, card_id)
    return sources_service._evidence_card_to_response(card)


# --- 拒绝证据卡片 ---

@router.post("/evidence/{card_id}/reject",
              response_model=EvidenceCardResponse)
def reject_evidence_card(project_id: str, card_id: str,
                         db: Session = Depends(_db)):
    card = sources_service.reject_evidence_card(db, project_id, card_id)
    return sources_service._evidence_card_to_response(card)


# --- 完成证据确认 ---

@router.post("/evidence/complete")
def complete_evidence(project_id: str, db: Session = Depends(_db)):
    project = sources_service.complete_evidence(db, project_id)
    return {"project_id": project.id, "status": project.status}
