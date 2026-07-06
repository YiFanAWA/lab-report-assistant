"""后台任务核心服务。

拥有后台任务的状态机、领取边界和重试策略。Worker 只通过本服务读写任务状态。
"""

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import update, or_
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.jobs.models import BackgroundJob, _uid
from app.modules.jobs.contracts import JobResponse, JobListResponse
from app.modules.jobs.status import JobStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _retry_backoff_seconds() -> int:
    raw = os.getenv("JOB_RETRY_BACKOFF_SECONDS", "5")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 5


def _default_max_retries() -> int:
    raw = os.getenv("JOB_MAX_RETRIES", "2")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 2


def create_job(db: Session, project_id: str, job_type: str,
              input_data: dict[str, Any]) -> BackgroundJob:
    """创建后台任务记录，状态为 PENDING，retry_count 为 0。

    不提交事务，由调用方负责提交。
    """
    job = BackgroundJob(
        id=_uid(),
        project_id=project_id,
        job_type=job_type,
        status=JobStatus.PENDING.value,
        input_json=json.dumps(input_data, ensure_ascii=False),
        retry_count=0,
        max_retries=_default_max_retries(),
    )
    db.add(job)
    db.flush()  # 确保 job.id 可用
    return job


def claim_pending_job(db: Session) -> BackgroundJob | None:
    """原子性领取一个待执行任务。

    查询 status=PENDING 且 (next_retry_at IS NULL OR next_retry_at <= now) 的任务，
    按创建时间升序取第一个，通过条件 UPDATE 原子性地将状态改为 RUNNING。
    若领取成功（rowcount=1）返回 job，否则返回 None。
    """
    now = _now()
    candidate = (
        db.query(BackgroundJob)
        .filter(
            BackgroundJob.status == JobStatus.PENDING.value,
            or_(
                BackgroundJob.next_retry_at.is_(None),
                BackgroundJob.next_retry_at <= now,
            ),
        )
        .order_by(BackgroundJob.created_at.asc())
        .first()
    )
    if not candidate:
        return None

    result = db.execute(
        update(BackgroundJob)
        .where(
            BackgroundJob.id == candidate.id,
            BackgroundJob.status == JobStatus.PENDING.value,
        )
        .values(
            status=JobStatus.RUNNING.value,
            started_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    db.commit()
    if result.rowcount == 1:
        db.refresh(candidate)
        return candidate
    # 被其他 Worker 抢占
    return None


def mark_running(db: Session, job_id: str) -> BackgroundJob:
    """显式标记任务为 RUNNING，记录 started_at。"""
    job = get_job(db, job_id)
    job.status = JobStatus.RUNNING.value
    job.started_at = _now()
    db.commit()
    db.refresh(job)
    return job


def mark_succeeded(db: Session, job_id: str,
                   output_data: dict[str, Any]) -> BackgroundJob:
    """标记任务成功，记录 finished_at 和 output_json。"""
    job = get_job(db, job_id)
    job.status = JobStatus.SUCCEEDED.value
    job.finished_at = _now()
    job.output_json = json.dumps(output_data, ensure_ascii=False)
    job.error_code = None
    job.error_message = None
    db.commit()
    db.refresh(job)
    return job


def mark_failed(db: Session, job_id: str, error_code: str,
                error_message: str) -> BackgroundJob:
    """标记任务失败，根据 retry_count 和 max_retries 决定重试或终态。

    - retry_count < max_retries：状态回到 PENDING，retry_count+1，next_retry_at=now+backoff
    - retry_count >= max_retries：状态变为 FAILED，记录 finished_at
    """
    job = get_job(db, job_id)
    now = _now()
    job.error_code = error_code
    job.error_message = error_message

    if job.retry_count < job.max_retries:
        job.status = JobStatus.PENDING.value
        job.retry_count += 1
        job.next_retry_at = now + timedelta(seconds=_retry_backoff_seconds())
    else:
        job.status = JobStatus.FAILED.value
        job.finished_at = now

    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: str) -> BackgroundJob:
    """查询单个任务，不存在时抛出 AppError。"""
    job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
    if not job:
        raise AppError(code="JOB_NOT_FOUND", message=f"未找到任务 {job_id}")
    return job


def list_jobs(db: Session, project_id: str, status: str | None = None,
              job_type: str | None = None) -> list[BackgroundJob]:
    """按条件筛选任务列表，按创建时间降序。"""
    query = db.query(BackgroundJob).filter(BackgroundJob.project_id == project_id)
    if status:
        query = query.filter(BackgroundJob.status == status)
    if job_type:
        query = query.filter(BackgroundJob.job_type == job_type)
    return query.order_by(BackgroundJob.created_at.desc()).all()


def _job_to_response(job: BackgroundJob) -> JobResponse:
    """将 BackgroundJob ORM 模型转换为 JobResponse。"""
    return JobResponse(
        id=job.id,
        project_id=job.project_id,
        job_type=job.job_type,
        status=job.status,
        input_json=job.input_json,
        output_json=job.output_json,
        error_code=job.error_code,
        error_message=job.error_message,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        next_retry_at=job.next_retry_at.isoformat() if job.next_retry_at else None,
    )


def _job_list_to_response(jobs: list[BackgroundJob]) -> JobListResponse:
    return JobListResponse(items=[_job_to_response(j) for j in jobs])
