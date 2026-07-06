"""后台任务 API 路由。

只做协议映射，不拥有业务语义。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.infrastructure.database.engine import SessionLocal
from app.modules.jobs import service as job_service
from app.modules.jobs.contracts import JobResponse, JobListResponse

router = APIRouter(prefix="/api/projects/{project_id}/jobs")


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- 任务详情 ---

@router.get("/{job_id}", response_model=JobResponse)
def get_job(project_id: str, job_id: str, db: Session = Depends(_db)):
    job = job_service.get_job(db, job_id)
    if job.project_id != project_id:
        from app.core.errors import AppError
        raise AppError(code="JOB_NOT_FOUND", message=f"未找到任务 {job_id}")
    return job_service._job_to_response(job)


# --- 任务列表 ---

@router.get("", response_model=JobListResponse)
def list_jobs(project_id: str,
              status: str | None = None,
              job_type: str | None = None,
              db: Session = Depends(_db)):
    jobs = job_service.list_jobs(
        db, project_id, status=status, job_type=job_type)
    return job_service._job_list_to_response(jobs)
