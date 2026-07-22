"""代码任务 API 路由。

只做协议映射，不拥有业务语义。
前缀 /api/projects/{project_id}。

路由：
  POST /analysis/{plan_id}/code/generate   触发生成代码候选
  GET  /code-tasks                         代码任务列表（支持 status 过滤）
  GET  /code-tasks/{task_id}               代码任务详情
  PUT  /code-tasks/{task_id}               编辑代码
  POST /code-tasks/{task_id}/confirm       确认代码
  POST /code-tasks/{task_id}/reject        拒绝代码
  POST /code-tasks/{task_id}/execute       触发执行（前置：CONFIRMED）
"""

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.infrastructure.database.engine import SessionLocal
from app.core.errors import AppError
from app.modules.execution import service as execution_service
from app.modules.execution.contracts import (
    UpdateCodeTaskRequest,
    CodeTaskResponse,
    CodeTaskListResponse,
    ExecuteCodeTaskResponse,
    GenerateCodeTaskResponse,
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


# --- 触发生成代码候选 ---


@router.post("/analysis/{plan_id}/code/generate",
             response_model=GenerateCodeTaskResponse,
             status_code=201)
def generate_code_task(project_id: str, plan_id: str,
                        db: Session = Depends(_db)):
    job_id = execution_service.generate_code_task(
        db, project_id, plan_id)
    return GenerateCodeTaskResponse(job_id=job_id)


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
