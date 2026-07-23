"""独立 Worker 进程。

启动方式：python -m worker.main
轮询 background_jobs 表，领取 PENDING 任务并执行。
"""

import time
import sys
import traceback

from sqlalchemy.orm import Session
from app.infrastructure.database.engine import SessionLocal
from app.modules.jobs import service as job_service
from worker.handlers import HANDLERS


def get_poll_interval() -> float:
    import os
    raw = os.getenv("WORKER_POLL_INTERVAL_SECONDS", "1")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 1.0


def run_once(db: Session) -> bool:
    """领取并执行一个任务，返回是否执行了任务。"""
    job = job_service.claim_pending_job(db)
    if not job:
        return False

    print(f"[Worker] 领取任务 {job.id} ({job.job_type})", flush=True)
    handler = HANDLERS.get(job.job_type)
    if not handler:
        job_service.mark_failed(db, job.id, "JOB_TYPE_UNKNOWN",
                                f"未知任务类型：{job.job_type}")
        return True

    try:
        output = handler(db, job)
        job_service.mark_succeeded(db, job.id, output)
        print(f"[Worker] 任务 {job.id} 成功", flush=True)
    except Exception as e:
        error_code = getattr(e, "code", "JOB_EXECUTION_ERROR")
        error_message = str(e)
        job_service.mark_failed(db, job.id, error_code, error_message)
        print(f"[Worker] 任务 {job.id} 失败：{error_code} - {error_message}",
              file=sys.stderr, flush=True)

    return True


def main():
    print("[Worker] 启动后台任务 Worker...", flush=True)
    interval = get_poll_interval()
    while True:
        db = SessionLocal()
        try:
            executed = run_once(db)
            if not executed:
                time.sleep(interval)
        except Exception as e:
            print(f"[Worker] 主循环异常：{e}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
        finally:
            db.close()


if __name__ == "__main__":
    main()
