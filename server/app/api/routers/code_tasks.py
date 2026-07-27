"""代码任务 API 路由。

只做协议映射，不拥有业务语义。
前缀 /api/projects/{project_id}。

路由：
  POST /analysis/{plan_id}/code/generate        触发生成代码候选（Worker 异步）
  POST /analysis/{plan_id}/code/stream-generate SSE 流式生成代码候选（SPEC 0022）
  GET  /code-tasks                              代码任务列表（支持 status 过滤）
  GET  /code-tasks/{task_id}                    代码任务详情
  PUT  /code-tasks/{task_id}                    编辑代码
  POST /code-tasks/{task_id}/confirm            确认代码
  POST /code-tasks/{task_id}/reject             拒绝代码
  POST /code-tasks/{task_id}/execute            触发执行（前置：CONFIRMED）
"""

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.infrastructure.database.engine import SessionLocal
from app.core.errors import AppError, ErrorResponse
from app.modules.execution import service as execution_service
from app.modules.execution.contracts import (
    UpdateCodeTaskRequest,
    CodeTaskResponse,
    CodeTaskListResponse,
    ExecuteCodeTaskResponse,
    GenerateCodeTaskResponse,
)
from app.modules.llm.gateway import get_code_task_provider

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


def _make_conflict_response(code: str, message: str, field: str | None = None):
    """构造 409 Conflict JSONResponse（SPEC 0022 流式预校验失败）。

    不依赖 AppError handler 的状态码映射，因为原有 generate_code_task 端点
    期望 ANALYSIS_PLAN_NOT_CONFIRMED 返回 400，而流式端点期望返回 409。
    """
    return JSONResponse(
        status_code=409,
        content=ErrorResponse.from_app_error(
            AppError(code=code, message=message, field=field)
        ).model_dump(),
    )


# --- 触发生成代码候选（Worker 异步，零回归保留） ---


@router.post("/analysis/{plan_id}/code/generate",
             response_model=GenerateCodeTaskResponse,
             status_code=201)
def generate_code_task(project_id: str, plan_id: str,
                        db: Session = Depends(_db)):
    job_id = execution_service.generate_code_task(
        db, project_id, plan_id)
    return GenerateCodeTaskResponse(job_id=job_id)


# --- 流式生成代码候选（SPEC 0022） ---


def _serialize_code_task_sse_event(event) -> str:
    """序列化 StreamCodeTaskEvent 为 SSE 文本块。

    SSE 格式：
        event: <event_name>
        data: <json_data>

    事件块以 \\n\\n 结尾分隔。
    """
    if isinstance(event, execution_service.StreamCodeTaskChunkEvent):
        data = json.dumps({"text": event.text}, ensure_ascii=False)
        return f"event: chunk\ndata: {data}\n\n"
    elif isinstance(event, execution_service.StreamCodeTaskDoneEvent):
        data = json.dumps({
            "code_task_id": event.code_task_id,
            "candidate_source": event.candidate_source,
            "fallback_used": event.fallback_used,
        }, ensure_ascii=False)
        return f"event: done\ndata: {data}\n\n"
    elif isinstance(event, execution_service.StreamCodeTaskErrorEvent):
        data = json.dumps({
            "error_code": event.error_code,
            "message": event.message,
            "partial_text": event.partial_text,
        }, ensure_ascii=False)
        return f"event: error\ndata: {data}\n\n"
    return ""


@router.post("/analysis/{plan_id}/code/stream-generate")
def stream_generate_code_task_endpoint(project_id: str, plan_id: str,
                                         request: Request):
    """SSE 流式生成代码任务。

    SPEC 0022 代码任务生成流式化。

    返回 text/event-stream，事件格式：
    - event: chunk / data: {"text": "..."}
    - event: done / data: {"code_task_id": "...", "candidate_source": "...", "fallback_used": false}
    - event: error / data: {"error_code": "...", "message": "...", "partial_text": "..."}

    预校验：在 StreamingResponse 开始前校验 project、AnalysisPlan 存在及状态，
    确保 PROJECT_NOT_FOUND / ANALYSIS_PLAN_NOT_FOUND 返回结构化 404，
    ANALYSIS_PLAN_NOT_CONFIRMED / PROJECT_ANALYSIS_NOT_CONFIRMED 返回 409。
    流式期间错误（状态/版本校验、LLM 中断等）走 StreamCodeTaskErrorEvent。
    """
    # 并发保护：同一 AnalysisPlan 同一时刻只允许一个活动流式请求
    if plan_id in execution_service.active_streams:
        raise AppError(
            code="STREAM_ALREADY_ACTIVE",
            message="该分析方案已有正在进行的流式生成请求，请等待完成或取消后重试",
        )

    provider = get_code_task_provider()

    # 预校验：项目和 AnalysisPlan 存在 + 状态满足（确保 404/409 而非 SSE 错误流）
    db = SessionLocal()
    try:
        from app.modules.projects import service as project_service
        from app.modules.analysis import service as analysis_service
        from app.modules.analysis.status import AnalysisPlanStatus

        # 项目不存在 → 404（走 AppError handler）
        project = project_service.get_project(db, project_id)

        # 项目状态不满足 → 409（直接返回，不依赖 AppError handler）
        from app.modules.projects.status import ProjectStatus
        allowed = [
            ProjectStatus.ANALYSIS_CONFIRMED.value,
            ProjectStatus.EXECUTING.value,
            ProjectStatus.EXECUTION_FAILED.value,
            ProjectStatus.RESULT_CONFIRMED.value,
            ProjectStatus.OUTLINE_CONFIRMED.value,
            ProjectStatus.GENERATING.value,
            ProjectStatus.COMPLETED.value,
        ]
        if project.status not in allowed:
            return _make_conflict_response(
                code="PROJECT_ANALYSIS_NOT_CONFIRMED",
                message="项目分析方案未确认，无法生成代码任务",
            )

        # AnalysisPlan 不存在 → 404（走 AppError handler）
        plan = analysis_service.get_analysis_plan_by_project(db, project_id, plan_id)

        # AnalysisPlan 未确认 → 409（直接返回，不依赖 AppError handler）
        if plan.status != AnalysisPlanStatus.CONFIRMED.value:
            return _make_conflict_response(
                code="ANALYSIS_PLAN_NOT_CONFIRMED",
                message="分析方案未确认，无法生成代码任务",
                field="analysis_plan_id",
            )
    finally:
        db.close()

    # 标记活动流式请求
    execution_service.active_streams[plan_id] = "active"

    def event_stream():
        try:
            # 端点层创建独立 db session，传入 service 由其管理生命周期
            # service 内部会重新校验（Phase 1）并管理 db.close() / 重新打开
            db = SessionLocal()
            try:
                for event in execution_service.stream_generate_code_task(
                    db, request, project_id, plan_id, provider
                ):
                    yield _serialize_code_task_sse_event(event)
            except AppError as e:
                # Phase 1 校验失败（状态/版本变化等），转为 error 事件
                yield _serialize_code_task_sse_event(
                    execution_service.StreamCodeTaskErrorEvent(
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
        finally:
            # 清理活动流式请求标记
            execution_service.active_streams.pop(plan_id, None)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx 禁用缓冲
        },
    )


# --- 代码任务列表 ---


@router.get("/code-tasks", response_model=CodeTaskListResponse)
def list_code_tasks(project_id: str,
                    status: str | None = None,
                    db: Session = Depends(_db)):
    tasks = execution_service.list_code_tasks(
        db, project_id, status=status)
    return execution_service.task_list_to_response(tasks)


# --- 代码任务详情 ---


@router.get("/code-tasks/{task_id}", response_model=CodeTaskResponse)
def get_code_task(project_id: str, task_id: str,
                  db: Session = Depends(_db)):
    task = execution_service.get_code_task_by_project(
        db, project_id, task_id)
    return execution_service.task_to_response(task)


# --- 编辑代码 ---


@router.put("/code-tasks/{task_id}", response_model=CodeTaskResponse)
def update_code_task(project_id: str, task_id: str, body: dict,
                      db: Session = Depends(_db)):
    try:
        req = UpdateCodeTaskRequest(**body)
    except ValidationError as exc:
        raise AppError(
            code="REQUEST_VALIDATION_ERROR",
            message="请求参数不符合要求",
            field=_field_from_validation(exc),
        )
    task = execution_service.update_code_task(
        db, project_id, task_id, req)
    return execution_service.task_to_response(task)


# --- 确认代码 ---


@router.post("/code-tasks/{task_id}/confirm",
              response_model=CodeTaskResponse)
def confirm_code_task(project_id: str, task_id: str,
                       db: Session = Depends(_db)):
    task = execution_service.confirm_code_task(db, project_id, task_id)
    return execution_service.task_to_response(task)


# --- 拒绝代码 ---


@router.post("/code-tasks/{task_id}/reject",
              response_model=CodeTaskResponse)
def reject_code_task(project_id: str, task_id: str,
                      db: Session = Depends(_db)):
    task = execution_service.reject_code_task(db, project_id, task_id)
    return execution_service.task_to_response(task)


# --- 触发执行 ---


@router.post("/code-tasks/{task_id}/execute",
              response_model=ExecuteCodeTaskResponse,
              status_code=201)
def execute_code_task(project_id: str, task_id: str,
                       db: Session = Depends(_db)):
    job_id = execution_service.execute_code_task(
        db, project_id, task_id)
    return ExecuteCodeTaskResponse(job_id=job_id, code_task_id=task_id)
