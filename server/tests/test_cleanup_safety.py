"""SPEC 0012 RUNNING job 保护逻辑详细单元测试。

覆盖 has_active_jobs 查询方法的所有场景：
- 无任务、有终态任务、有活跃任务（PENDING/RUNNING）
- 多任务混合状态
- 不存在的项目
- cleanup_project 中 RUNNING job 保护接线
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.engine import Base
from app.modules.jobs.models import BackgroundJob, _uid
from app.modules.jobs.service import has_active_jobs, create_job
from app.modules.jobs.status import JobStatus
from app.modules.projects.models import Project
from app.modules.projects.status import ProjectStatus


TEST_DB = "sqlite:///:memory:"


@pytest.fixture
def db():
    """内存 SQLite + 所有表。"""
    engine = create_engine(
        TEST_DB,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _create_project(db, project_id: str = "proj_test_1") -> Project:
    """创建测试项目。"""
    project = Project(
        id=project_id,
        name=f"测试项目_{project_id}",
        topic=f"测试课题_{project_id}",
        status=ProjectStatus.COMPLETED.value,
        workspace_root=f"/tmp/{project_id}",
    )
    db.add(project)
    db.commit()
    return project


def _create_job(db, project_id: str, status: str, job_type: str = "FETCH_URL"):
    """创建指定状态的 Job。"""
    job = BackgroundJob(
        id=_uid(),
        project_id=project_id,
        job_type=job_type,
        status=status,
        input_json="{}",
        retry_count=0,
        max_retries=2,
    )
    db.add(job)
    db.commit()
    return job


# --- has_active_jobs 基础查询 ---


class TestHasActiveJobsBasic:
    """has_active_jobs 基础查询测试。"""

    def test_no_jobs_returns_false(self, db):
        """F-06-a：项目无任何任务，返回 False。"""
        _create_project(db, "proj_empty")
        assert has_active_jobs(db, "proj_empty") is False

    def test_only_succeeded_jobs_returns_false(self, db):
        """F-05-a：项目只有 SUCCEEDED 任务，返回 False。"""
        _create_project(db, "proj_done")
        _create_job(db, "proj_done", JobStatus.SUCCEEDED.value)
        assert has_active_jobs(db, "proj_done") is False

    def test_only_failed_jobs_returns_false(self, db):
        """F-05-b：项目只有 FAILED 任务，返回 False。"""
        _create_project(db, "proj_failed")
        _create_job(db, "proj_failed", JobStatus.FAILED.value)
        assert has_active_jobs(db, "proj_failed") is False

    def test_only_cancelled_jobs_returns_false(self, db):
        """F-05-c：项目只有 CANCELLED 任务，返回 False。"""
        _create_project(db, "proj_cancelled")
        _create_job(db, "proj_cancelled", JobStatus.CANCELLED.value)
        assert has_active_jobs(db, "proj_cancelled") is False

    def test_running_job_returns_true(self, db):
        """F-03：项目有 RUNNING 任务，返回 True。"""
        _create_project(db, "proj_running")
        _create_job(db, "proj_running", JobStatus.RUNNING.value)
        assert has_active_jobs(db, "proj_running") is True

    def test_pending_job_returns_true(self, db):
        """F-04：项目有 PENDING 任务，返回 True。"""
        _create_project(db, "proj_pending")
        _create_job(db, "proj_pending", JobStatus.PENDING.value)
        assert has_active_jobs(db, "proj_pending") is True


# --- has_active_jobs 混合状态 ---


class TestHasActiveJobsMixed:
    """has_active_jobs 混合状态测试。"""

    def test_mixed_active_and_terminal_returns_true(self, db):
        """混合：1 个 SUCCEEDED + 1 个 RUNNING，返回 True。"""
        _create_project(db, "proj_mixed_1")
        _create_job(db, "proj_mixed_1", JobStatus.SUCCEEDED.value)
        _create_job(db, "proj_mixed_1", JobStatus.RUNNING.value)
        assert has_active_jobs(db, "proj_mixed_1") is True

    def test_mixed_pending_and_failed_returns_true(self, db):
        """混合：1 个 FAILED + 1 个 PENDING，返回 True。"""
        _create_project(db, "proj_mixed_2")
        _create_job(db, "proj_mixed_2", JobStatus.FAILED.value)
        _create_job(db, "proj_mixed_2", JobStatus.PENDING.value)
        assert has_active_jobs(db, "proj_mixed_2") is True

    def test_all_terminal_returns_false(self, db):
        """混合：全部终态（SUCCEEDED + FAILED + CANCELLED），返回 False。"""
        _create_project(db, "proj_mixed_3")
        _create_job(db, "proj_mixed_3", JobStatus.SUCCEEDED.value)
        _create_job(db, "proj_mixed_3", JobStatus.FAILED.value)
        _create_job(db, "proj_mixed_3", JobStatus.CANCELLED.value)
        assert has_active_jobs(db, "proj_mixed_3") is False

    def test_multiple_running_returns_true(self, db):
        """多个 RUNNING 任务，返回 True。"""
        _create_project(db, "proj_multi_run")
        _create_job(db, "proj_multi_run", JobStatus.RUNNING.value, "FETCH_URL")
        _create_job(db, "proj_multi_run", JobStatus.RUNNING.value, "PARSE_DOCUMENT")
        _create_job(db, "proj_multi_run", JobStatus.RUNNING.value, "GENERATE_EVIDENCE")
        assert has_active_jobs(db, "proj_multi_run") is True


# --- has_active_jobs 边界情况 ---


class TestHasActiveJobsEdgeCases:
    """has_active_jobs 边界情况测试。"""

    def test_nonexistent_project_returns_false(self, db):
        """不存在的项目 ID，返回 False（无记录即无活跃任务）。"""
        assert has_active_jobs(db, "proj_nonexistent") is False

    def test_other_project_jobs_not_counted(self, db):
        """项目 B 的活跃任务不影响项目 A 的判断。"""
        _create_project(db, "proj_a")
        _create_project(db, "proj_b")
        _create_job(db, "proj_b", JobStatus.RUNNING.value)
        # 项目 A 无任务
        assert has_active_jobs(db, "proj_a") is False
        # 项目 B 有活跃任务
        assert has_active_jobs(db, "proj_b") is True

    def test_all_job_types_with_running_status(self, db):
        """所有 JobType 都能正确识别 RUNNING 状态。"""
        _create_project(db, "proj_all_types")
        from app.modules.jobs.status import JobType
        for jt in JobType:
            _create_job(db, "proj_all_types", JobStatus.RUNNING.value, jt.value)
        assert has_active_jobs(db, "proj_all_types") is True


# --- create_job 默认状态验证 ---


class TestCreateJobDefault:
    """create_job 创建的 Job 默认状态验证（确保 PENDING 被正确识别为活跃）。"""

    def test_create_job_defaults_to_pending(self, db):
        """create_job 创建的任务默认是 PENDING（活跃）。"""
        _create_project(db, "proj_create")
        job = create_job(db, "proj_create", "FETCH_URL", {"url": "https://example.com"})
        assert job.status == JobStatus.PENDING.value
        assert has_active_jobs(db, "proj_create") is True


# --- cleanup_project RUNNING job 保护接线 ---


class TestCleanupProjectProtection:
    """cleanup_project 中 RUNNING job 保护接线测试。"""

    def test_cleanup_skips_project_with_running_job(self, db, monkeypatch, tmp_path):
        """F-03：过期项目有 RUNNING job，被跳过。"""
        from scripts.cleanup_expired_data import cleanup_project

        monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path))

        # 创建过期项目（updated_at 35天前）
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        project = Project(
            id="proj_cleanup_run",
            name="有活跃任务的项目",
            topic="测试课题",
            status=ProjectStatus.COMPLETED.value,
            workspace_root=str(tmp_path / "proj_cleanup_run"),
            created_at=now - timedelta(days=35),
            updated_at=now - timedelta(days=35),
        )
        db.add(project)
        db.commit()

        # 创建 RUNNING job
        _create_job(db, "proj_cleanup_run", JobStatus.RUNNING.value)

        # 执行清理（execute 模式）
        result = cleanup_project(db, project, execute=True)

        assert result["status"] == "skipped"
        assert "活跃任务" in result["message"]
        # 项目仍在数据库中
        assert db.query(Project).filter(Project.id == "proj_cleanup_run").first() is not None

    def test_cleanup_skips_project_with_pending_job(self, db, monkeypatch, tmp_path):
        """F-04：过期项目有 PENDING job，被跳过。"""
        from scripts.cleanup_expired_data import cleanup_project

        monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path))

        from datetime import timedelta
        now = datetime.now(timezone.utc)
        project = Project(
            id="proj_cleanup_pending",
            name="有等待任务的项目",
            topic="测试课题",
            status=ProjectStatus.COMPLETED.value,
            workspace_root=str(tmp_path / "proj_cleanup_pending"),
            created_at=now - timedelta(days=35),
            updated_at=now - timedelta(days=35),
        )
        db.add(project)
        db.commit()

        _create_job(db, "proj_cleanup_pending", JobStatus.PENDING.value)

        result = cleanup_project(db, project, execute=True)

        assert result["status"] == "skipped"
        assert "活跃任务" in result["message"]

    def test_cleanup_proceeds_when_jobs_all_terminal(self, db, monkeypatch, tmp_path):
        """F-05：过期项目 job 全部终态，正常清理。"""
        from scripts.cleanup_expired_data import cleanup_project

        monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path))

        from datetime import timedelta
        now = datetime.now(timezone.utc)
        project = Project(
            id="proj_cleanup_done",
            name="任务已完成的项目",
            topic="测试课题",
            status=ProjectStatus.COMPLETED.value,
            workspace_root=str(tmp_path / "proj_cleanup_done"),
            created_at=now - timedelta(days=35),
            updated_at=now - timedelta(days=35),
        )
        db.add(project)
        db.commit()

        # 创建终态 job
        _create_job(db, "proj_cleanup_done", JobStatus.SUCCEEDED.value)
        _create_job(db, "proj_cleanup_done", JobStatus.FAILED.value)

        result = cleanup_project(db, project, execute=True)

        assert result["status"] == "success"
        # 项目已从数据库删除
        assert db.query(Project).filter(Project.id == "proj_cleanup_done").first() is None

    def test_cleanup_dry_run_with_running_job_still_skips(self, db, monkeypatch, tmp_path):
        """dry-run 模式下有活跃任务也跳过（保护逻辑优先于 dry-run）。"""
        from scripts.cleanup_expired_data import cleanup_project

        monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path))

        from datetime import timedelta
        now = datetime.now(timezone.utc)
        project = Project(
            id="proj_dryrun_run",
            name="dry-run 有活跃任务",
            topic="测试课题",
            status=ProjectStatus.COMPLETED.value,
            workspace_root=str(tmp_path / "proj_dryrun_run"),
            created_at=now - timedelta(days=35),
            updated_at=now - timedelta(days=35),
        )
        db.add(project)
        db.commit()

        _create_job(db, "proj_dryrun_run", JobStatus.RUNNING.value)

        # dry-run 模式
        result = cleanup_project(db, project, execute=False)

        # 即使 dry-run，有活跃任务也标记为 skipped（而非 dry_run）
        assert result["status"] == "skipped"
        assert "活跃任务" in result["message"]
