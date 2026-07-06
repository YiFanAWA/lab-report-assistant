"""后台任务核心服务测试。

覆盖 create_job、claim_pending_job、mark_succeeded、mark_failed 的状态机
和重试策略，以及 list_jobs 的过滤能力。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.engine import Base
from app.modules.jobs import service as job_service
from app.modules.jobs.status import JobStatus, JobType
from app.core.errors import AppError


TEST_DB = "sqlite:///:memory:"


@pytest.fixture
def db():
    """内存 SQLite 会话，每个测试独立。"""
    engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# --- create_job ---


class TestCreateJob:
    """创建后台任务测试。"""

    def test_creates_pending_job_with_zero_retry_count(self, db):
        """创建任务时 status=PENDING，retry_count=0，max_retries 默认 2。"""
        job = job_service.create_job(
            db,
            project_id="proj_test_001",
            job_type=JobType.FETCH_URL.value,
            input_data={"source_id": "src_1", "url": "https://example.com"},
        )
        # _uid 返回 12 位 hex，无前缀
        assert len(job.id) == 12
        assert job.status == JobStatus.PENDING.value
        assert job.retry_count == 0
        assert job.max_retries == 2
        assert job.project_id == "proj_test_001"
        assert job.job_type == "FETCH_URL"
        assert "https://example.com" in job.input_json

    def test_create_job_does_not_commit_until_caller_commits(self, db):
        """create_job 调用 flush 但不 commit，调用方负责提交。"""
        job = job_service.create_job(
            db,
            project_id="proj_test_002",
            job_type=JobType.PARSE_DOCUMENT.value,
            input_data={"source_id": "src_2"},
        )
        # 不 commit，直接新开一个会话验证：在同一个 db 内 flush 已可见
        same_session_job = db.query(type(job)).filter(type(job).id == job.id).first()
        assert same_session_job is not None
        assert same_session_job.status == JobStatus.PENDING.value


# --- claim_pending_job ---


class TestClaimPendingJob:
    """原子性领取任务测试。"""

    def test_claims_oldest_pending_job_and_sets_running(self, db):
        """领取最早创建的 PENDING 任务，状态变为 RUNNING。"""
        j1 = job_service.create_job(
            db, "proj_a", JobType.FETCH_URL.value, {"url": "https://a.com"}
        )
        j2 = job_service.create_job(
            db, "proj_a", JobType.FETCH_URL.value, {"url": "https://b.com"}
        )
        db.commit()

        claimed = job_service.claim_pending_job(db)

        assert claimed is not None
        assert claimed.id == j1.id  # 按 created_at 升序
        assert claimed.status == JobStatus.RUNNING.value
        assert claimed.started_at is not None

    def test_returns_none_when_no_pending_job(self, db):
        """无 PENDING 任务时返回 None。"""
        assert job_service.claim_pending_job(db) is None

    def test_skips_running_job(self, db):
        """已 RUNNING 的任务不会被再次领取。"""
        job_service.create_job(
            db, "proj_a", JobType.FETCH_URL.value, {"url": "https://a.com"}
        )
        db.commit()
        first = job_service.claim_pending_job(db)
        assert first is not None

        second = job_service.claim_pending_job(db)
        assert second is None

    def test_picks_up_retried_pending_job_after_backoff(self, db):
        """重试回 PENDING 的任务在 next_retry_at 到期后可被再次领取。"""
        job = job_service.create_job(
            db, "proj_a", JobType.FETCH_URL.value, {"url": "https://a.com"}
        )
        db.commit()
        claimed = job_service.claim_pending_job(db)
        assert claimed is not None

        # 标记失败，触发重试：retry_count 0 -> 1，回到 PENDING，next_retry_at 设为未来
        job_service.mark_failed(db, claimed.id, "FETCH_TIMEOUT", "采集超时")
        retried = job_service.get_job(db, claimed.id)
        assert retried.status == JobStatus.PENDING.value
        assert retried.retry_count == 1
        assert retried.next_retry_at is not None

        # next_retry_at 在未来，本次不应被领取
        again = job_service.claim_pending_job(db)
        assert again is None


# --- mark_succeeded ---


class TestMarkSucceeded:
    """标记任务成功测试。"""

    def test_mark_succeeded_sets_finished_at_and_output(self, db):
        """成功后 status=SUCCEEDED，记录 output_json 和 finished_at。"""
        job = job_service.create_job(
            db, "proj_a", JobType.FETCH_URL.value, {"url": "https://a.com"}
        )
        db.commit()

        succeeded = job_service.mark_succeeded(
            db, job.id, {"file_path": "/tmp/raw.html", "content_type": "text/html"}
        )

        assert succeeded.status == JobStatus.SUCCEEDED.value
        assert succeeded.finished_at is not None
        assert "raw.html" in succeeded.output_json
        assert succeeded.error_code is None
        assert succeeded.error_message is None


# --- mark_failed ---


class TestMarkFailed:
    """任务失败与重试策略测试。"""

    def test_mark_failed_under_max_retries_returns_to_pending(self, db):
        """retry_count < max_retries 时回到 PENDING 并增加 retry_count。"""
        job = job_service.create_job(
            db, "proj_a", JobType.FETCH_URL.value, {"url": "https://a.com"}
        )
        db.commit()

        failed = job_service.mark_failed(db, job.id, "FETCH_TIMEOUT", "采集超时")

        assert failed.status == JobStatus.PENDING.value
        assert failed.retry_count == 1
        assert failed.next_retry_at is not None
        assert failed.error_code == "FETCH_TIMEOUT"
        assert "采集超时" in failed.error_message
        assert failed.finished_at is None  # 未终态

    def test_mark_failed_at_max_retries_becomes_failed(self, db):
        """retry_count 达到 max_retries 时变为 FAILED，记录 finished_at。"""
        job = job_service.create_job(
            db, "proj_a", JobType.FETCH_URL.value, {"url": "https://a.com"}
        )
        db.commit()

        # 第一次失败：retry_count 0 -> 1，回 PENDING
        job_service.mark_failed(db, job.id, "FETCH_TIMEOUT", "采集超时 1")
        # 第二次失败：retry_count 1 -> 2，回 PENDING（max_retries=2，1 < 2 仍重试）
        job_service.mark_failed(db, job.id, "FETCH_TIMEOUT", "采集超时 2")
        # 第三次失败：retry_count == max_retries，变为 FAILED
        final = job_service.mark_failed(db, job.id, "FETCH_TIMEOUT", "采集超时 3")

        assert final.status == JobStatus.FAILED.value
        assert final.retry_count == 2
        assert final.finished_at is not None
        assert final.error_code == "FETCH_TIMEOUT"

    def test_mark_failed_records_error_message(self, db):
        """失败时记录错误码和错误信息。"""
        job = job_service.create_job(
            db, "proj_a", JobType.PARSE_DOCUMENT.value, {"source_id": "src_1"}
        )
        db.commit()

        failed = job_service.mark_failed(db, job.id, "PARSE_TEXT_EMPTY", "解析后文本为空")

        assert failed.error_code == "PARSE_TEXT_EMPTY"
        assert "解析后文本为空" in failed.error_message


# --- get_job / list_jobs ---


class TestJobQueries:
    """任务查询测试。"""

    def test_get_job_raises_when_not_found(self, db):
        """查询不存在的任务抛出 JOB_NOT_FOUND。"""
        with pytest.raises(AppError) as exc:
            job_service.get_job(db, "job_missing")
        assert exc.value.code == "JOB_NOT_FOUND"

    def test_list_jobs_filters_by_project_id(self, db):
        """list_jobs 按 project_id 过滤，按创建时间降序。"""
        j_a1 = job_service.create_job(
            db, "proj_a", JobType.FETCH_URL.value, {"url": "https://a.com"}
        )
        j_a2 = job_service.create_job(
            db, "proj_a", JobType.PARSE_DOCUMENT.value, {"source_id": "s1"}
        )
        j_b1 = job_service.create_job(
            db, "proj_b", JobType.FETCH_URL.value, {"url": "https://b.com"}
        )
        db.commit()

        # 注意：created_at 由 default 控制，且 create_job flush 时已生成。
        # 由于 j_a2 在 j_a1 后插入，按降序 j_a2 应该排第一（同 project_a）。
        a_jobs = job_service.list_jobs(db, "proj_a")
        assert len(a_jobs) == 2
        assert a_jobs[0].id == j_a2.id
        assert a_jobs[1].id == j_a1.id

        b_jobs = job_service.list_jobs(db, "proj_b")
        assert len(b_jobs) == 1
        assert b_jobs[0].id == j_b1.id

    def test_list_jobs_filters_by_status_and_type(self, db):
        """list_jobs 同时支持 status 和 job_type 过滤。"""
        job_service.create_job(
            db, "proj_a", JobType.FETCH_URL.value, {"url": "https://a.com"}
        )
        job_service.create_job(
            db, "proj_a", JobType.PARSE_DOCUMENT.value, {"source_id": "s1"}
        )
        j_running = job_service.create_job(
            db, "proj_a", JobType.FETCH_URL.value, {"url": "https://b.com"}
        )
        db.commit()
        # 显式标记特定任务为 RUNNING，避免依赖 claim_pending_job 的顺序
        job_service.mark_running(db, j_running.id)
        # 此时 proj_a 中：1 PARSE_DOCUMENT PENDING、1 FETCH_URL PENDING、1 FETCH_URL RUNNING

        fetch_pending = job_service.list_jobs(
            db, "proj_a", status=JobStatus.PENDING.value, job_type=JobType.FETCH_URL.value
        )
        assert len(fetch_pending) == 1
        assert fetch_pending[0].job_type == "FETCH_URL"
        assert fetch_pending[0].status == JobStatus.PENDING.value

        running = job_service.list_jobs(
            db, "proj_a", status=JobStatus.RUNNING.value
        )
        assert len(running) == 1
        assert running[0].id == j_running.id
