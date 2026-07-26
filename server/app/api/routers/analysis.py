"""分析方案 API 路由。

只做协议映射，不拥有业务语义。
前缀 /api/projects/{project_id}。

路由：
  POST /datasets/{dataset_id}/analysis/generate
  POST /datasets/{dataset_id}/analysis/stream-generate
  GET  /analysis
  GET  /analysis/{plan_id}
  PUT  /analysis/{plan_id}
  POST /analysis/{plan_id}/confirm
  POST /analysis/{plan_id}/reject
  POST /analysis/complete
"""

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.infrastructure.database.engine import SessionLocal
from app.core.errors import AppError
from app.modules.llm.gateway import get_analysis_plan_provider
from app.modules.analysis import service as analysis_service
from app.modules.analysis.contracts import (
    UpdateAnalysisPlanRequest,
    AnalysisPlanResponse,
    AnalysisPlanListResponse,
    CompleteAnalysisResponse,
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


# --- 触发生成分析方案 ---


@router.post("/datasets/{dataset_id}/analysis/generate", status_code=201)
def generate_analysis_plan(project_id: str, dataset_id: str,
                            db: Session = Depends(_db)):
    job_id = analysis_service.generate_analysis_plan(
        db, project_id, dataset_id)
    return {"job_id": job_id}


# --- 流式生成分析方案（SPEC 0021） ---


def _serialize_analysis_sse_event(event) -> str:
    """序列化 StreamAnalysisEvent 为 SSE 文本块。

    SSE 格式：
        event: <event_name>
        data: <json_data>

    事件块以 \\n\\n 结尾分隔。
    """
    if isinstance(event, analysis_service.StreamAnalysisChunkEvent):
        data = json.dumps({"text": event.text}, ensure_ascii=False)
        return f"event: chunk\ndata: {data}\n\n"
    elif isinstance(event, analysis_service.StreamAnalysisDoneEvent):
        data = json.dumps({
            "plan_id": event.plan_id,
            "candidate_source": event.candidate_source,
            "fallback_used": event.fallback_used,
        }, ensure_ascii=False)
        return f"event: done\ndata: {data}\n\n"
    elif isinstance(event, analysis_service.StreamAnalysisErrorEvent):
        data = json.dumps({
            "error_code": event.error_code,
            "message": event.message,
            "partial_text": event.partial_text,
        }, ensure_ascii=False)
        return f"event: error\ndata: {data}\n\n"
    return ""


@router.post("/datasets/{dataset_id}/analysis/stream-generate")
def stream_generate_analysis_plan_endpoint(project_id: str, dataset_id: str):
    """SSE 流式生成分析方案。

    SPEC 0021 分析方案生成流式化。

    返回 text/event-stream，事件格式：
    - event: chunk / data: {"text": "..."}
    - event: done / data: {"plan_id": "...", "candidate_source": "...", "fallback_used": false}
    - event: error / data: {"error_code": "...", "message": "...", "partial_text": "..."}

    预校验：在 StreamingResponse 开始前校验 project 和 dataset 存在，
    确保 PROJECT_NOT_FOUND / DATASET_NOT_FOUND 能返回结构化 404 而非 SSE 错误流。
    流式期间错误（状态/版本校验、LLM 中断等）走 StreamAnalysisErrorEvent。
    """
    provider = get_analysis_plan_provider()

    # 预校验：项目和数据集存在（确保 404 而非 SSE 错误流）
    db = SessionLocal()
    try:
        from app.modules.projects import service as project_service
        from app.modules.datasets import service as dataset_service
        project_service.get_project(db, project_id)
        dataset_service.get_dataset_by_id_and_project(db, project_id, dataset_id)
    finally:
        db.close()

    def event_stream():
        # 端点层创建独立 db session，传入 service 由其管理生命周期
        # service 内部会重新校验（Phase 1）并管理 db.close() / 重新打开
        db = SessionLocal()
        try:
            for event in analysis_service.stream_generate_analysis_plan(
                db, project_id, dataset_id, provider
            ):
                yield _serialize_analysis_sse_event(event)
        except AppError as e:
            # Phase 1 校验失败（状态/版本未解析等），转为 error 事件
            yield _serialize_analysis_sse_event(
                analysis_service.StreamAnalysisErrorEvent(
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


# --- 分析方案列表 ---


@router.get("/analysis", response_model=AnalysisPlanListResponse)
def list_analysis_plans(project_id: str,
                        dataset_id: str | None = None,
                        status: str | None = None,
                        db: Session = Depends(_db)):
    plans = analysis_service.list_analysis_plans(
        db, project_id, dataset_id=dataset_id, status=status)
    return analysis_service.plan_list_to_response(plans)


# --- 分析方案详情 ---


@router.get("/analysis/{plan_id}", response_model=AnalysisPlanResponse)
def get_analysis_plan(project_id: str, plan_id: str,
                      db: Session = Depends(_db)):
    plan = analysis_service.get_analysis_plan_by_project(
        db, project_id, plan_id)
    return analysis_service.plan_to_response(plan)


# --- 编辑分析方案 ---


@router.put("/analysis/{plan_id}", response_model=AnalysisPlanResponse)
def update_analysis_plan(project_id: str, plan_id: str, body: dict,
                          db: Session = Depends(_db)):
    try:
        req = UpdateAnalysisPlanRequest(**body)
    except ValidationError as exc:
        raise AppError(
            code="REQUEST_VALIDATION_ERROR",
            message="请求参数不符合要求",
            field=_field_from_validation(exc),
        )
    plan = analysis_service.update_analysis_plan(
        db, project_id, plan_id, req)
    return analysis_service.plan_to_response(plan)


# --- 确认分析方案 ---


@router.post("/analysis/{plan_id}/confirm",
              response_model=AnalysisPlanResponse)
def confirm_analysis_plan(project_id: str, plan_id: str,
                           db: Session = Depends(_db)):
    plan = analysis_service.confirm_analysis_plan(db, project_id, plan_id)
    return analysis_service.plan_to_response(plan)


# --- 拒绝分析方案 ---


@router.post("/analysis/{plan_id}/reject",
              response_model=AnalysisPlanResponse)
def reject_analysis_plan(project_id: str, plan_id: str,
                          db: Session = Depends(_db)):
    plan = analysis_service.reject_analysis_plan(db, project_id, plan_id)
    return analysis_service.plan_to_response(plan)


# --- 完成分析方案确认 ---


@router.post("/analysis/complete", response_model=CompleteAnalysisResponse)
def complete_analysis(project_id: str, db: Session = Depends(_db)):
    project = analysis_service.complete_analysis(db, project_id)
    return analysis_service.complete_analysis_to_response(project)
