"""执行记录 API 路由。

只做协议映射，不拥有业务语义。
前缀 /api/projects/{project_id}。

路由：
  GET  /execution-runs                                  执行记录列表（含 artifacts）
  GET  /execution-runs/{run_id}                          执行详情（含 stdout/stderr/artifacts）
  GET  /execution-runs/{run_id}/artifacts/{artifact_id}  下载产物（返回文件流）
  POST /execution-runs/complete                          完成结果确认
"""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.infrastructure.database.engine import SessionLocal
from app.modules.execution import service as execution_service
from app.modules.execution.contracts import (
    ExecutionRunListResponse,
    ExecutionRunResponse,
    CompleteExecutionResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}")


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- 执行记录列表 ---


@router.get("/execution-runs", response_model=ExecutionRunListResponse)
def list_execution_runs(project_id: str,
                        status: str | None = None,
                        db: Session = Depends(_db)):
    runs = execution_service.list_execution_runs(
        db, project_id, status=status)
    return execution_service.run_list_to_response(runs)


# --- 执行详情 ---


@router.get("/execution-runs/{run_id}", response_model=ExecutionRunResponse)
def get_execution_run(project_id: str, run_id: str,
                       db: Session = Depends(_db)):
    run, artifacts = execution_service.get_execution_run_by_project(
        db, project_id, run_id)
    return execution_service.run_to_response(run, artifacts)


# --- 下载产物 ---


@router.get("/execution-runs/{run_id}/artifacts/{artifact_id}")
def download_artifact(project_id: str, run_id: str, artifact_id: str,
                       db: Session = Depends(_db)):
    abs_path, filename, media_type = execution_service.get_artifact_file_path(
        db, project_id, run_id, artifact_id)
    return FileResponse(
        path=str(abs_path),
        media_type=media_type,
        filename=filename,
    )


# --- 完成结果确认 ---


@router.post("/execution-runs/complete",
              response_model=CompleteExecutionResponse)
def complete_execution(project_id: str, db: Session = Depends(_db)):
    project = execution_service.complete_execution(db, project_id)
    return execution_service.complete_execution_to_response(project)
