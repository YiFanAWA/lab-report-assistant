"""代码任务执行与生成 Worker 处理器测试。

覆盖 2 个核心 handler：
- handle_generate_code_task：基于已确认分析方案生成代码任务候选
- handle_execute_code_task：在受控环境中执行已确认代码任务

mock get_code_task_provider 和 execute_code_safe，避免真实 LLM 和真实 subprocess。
覆盖成功路径、失败路径、前置条件校验、产物收集等场景。

测试原则：
- 不调用真实 DeepSeek API
- 不执行真实 subprocess（mock execute_code_safe）
- 内存 SQLite + 受控 PROJECT_DATA_ROOT
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.engine import Base
from app.infrastructure.sandbox.python_executor import (
    ExecutionResult,
    ArtifactInfo,
)
from app.modules.execution.models import CodeTask, ExecutionRun, ExecutionArtifact
from app.modules.execution.status import (
    CodeTaskStatus,
    ExecutionRunStatus,
    ExecutionArtifactType,
)
from app.modules.jobs import service as job_service
from app.modules.jobs.status import JobType
from app.modules.projects import service as project_service
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.projects.models import Project
from app.modules.projects.status import ProjectStatus
from worker import handlers as worker_handlers


# 触发模型注册到 Base.metadata
from app.modules.datasets.models import Dataset, DatasetVersion  # noqa: F401
from app.modules.analysis.models import AnalysisPlan  # noqa: F401


TEST_DB = "sqlite:///:memory:"


@pytest.fixture
def db(monkeypatch, tmp_path):
    """内存 SQLite + 受控 PROJECT_DATA_ROOT。"""
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# --- 辅助函数 ---


def _create_project(
    db, status: str = ProjectStatus.ANALYSIS_CONFIRMED.value
) -> str:
    """创建项目并设置状态。"""
    project = project_service.create_project(
        db, ProjectCreateRequest(name="执行测试项目", topic="胃病数据分析")
    )
    project.status = status
    db.commit()
    return project.id


def _seed_confirmed_analysis_plan(
    db, project_id: str, plan_id: str = "plan_exec_001"
) -> tuple[str, str, str]:
    """插入一条 CONFIRMED 状态的 AnalysisPlan，返回 (plan_id, dataset_id, version_id)。

    包含 cleaning/analysis/chart plan 的有效 JSON。
    """
    from app.modules.analysis.status import AnalysisPlanStatus
    from app.modules.datasets.models import Dataset, DatasetVersion
    from app.modules.datasets.status import (
        DatasetKind,
        DatasetStatus,
        DatasetVersionStatus,
    )

    dataset_id = "ds_exec_001"
    version_id = "ver_exec_001"

    dataset = Dataset(
        id=dataset_id,
        project_id=project_id,
        dataset_kind=DatasetKind.FILE.value,
        title="测试数据集",
        status=DatasetStatus.READY.value,
    )
    db.add(dataset)

    version = DatasetVersion(
        id=version_id,
        dataset_id=dataset_id,
        project_id=project_id,
        version=1,
        status=DatasetVersionStatus.PARSED.value,
        file_path="data/test.csv",  # 占位，后续测试按需覆盖
        file_size_bytes=100,
    )
    db.add(version)

    plan = AnalysisPlan(
        id=plan_id,
        project_id=project_id,
        dataset_id=dataset_id,
        dataset_version_id=version_id,
        status=AnalysisPlanStatus.CONFIRMED.value,
        candidate_source="LOCAL_RULE",
        cleaning_plan=json.dumps([
            {"field": "age", "issue_type": "MISSING_VALUE",
             "action": "中位数填充", "reason": "数值字段"},
        ]),
        analysis_plan=json.dumps([
            {"analysis_type": "DESCRIPTIVE_STATISTICS",
             "target_fields": ["age"],
             "method": "计算均值", "expected_output": "统计表"},
        ]),
        chart_plan=json.dumps([
            {"chart_type": "HISTOGRAM", "title": "age 分布",
             "data_fields": ["age"], "description": "直方图"},
        ]),
    )
    db.add(plan)
    db.commit()
    return plan_id, dataset_id, version_id


def _seed_confirmed_code_task(
    db, project_id: str, plan_id: str = "plan_exec_001",
    task_id: str = "task_exec_001",
    dataset_id: str = "ds_exec_001",
    version_id: str = "ver_exec_001",
) -> str:
    """插入一条 CONFIRMED 状态的 CodeTask，返回 task_id。"""
    task = CodeTask(
        id=task_id,
        project_id=project_id,
        analysis_plan_id=plan_id,
        dataset_id=dataset_id,
        dataset_version_id=version_id,
        code="import pandas as pd\nprint('hello')",
        code_version=1,
        status=CodeTaskStatus.CONFIRMED.value,
        candidate_source="LOCAL_RULE",
    )
    db.add(task)
    db.commit()
    return task_id


def _seed_dataset_version_with_file(
    db, project_id: str, version_id: str = "ver_exec_001"
) -> str:
    """为 DatasetVersion 写入真实文件，返回绝对路径。"""
    from app.core.config import settings
    from app.modules.datasets.models import DatasetVersion

    version = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.id == version_id)
        .first()
    )
    # 写入测试 CSV 文件
    dest_dir = settings.project_data_root / project_id / "datasets" / "ds_exec_001" / "v1"
    dest_dir.mkdir(parents=True, exist_ok=True)
    csv_path = dest_dir / "raw.csv"
    csv_path.write_text("name,age\nalice,30\nbob,25\n", encoding="utf-8")
    version.file_path = str(csv_path)
    db.commit()
    return str(csv_path)


def _make_execution_result(
    exit_code: int = 0,
    stdout: str = "执行成功",
    stderr: str = "",
    artifacts: list[ArtifactInfo] | None = None,
    sandbox_error_code: str | None = None,
) -> ExecutionResult:
    """构造 mock execute_code_safe 的返回值。"""
    return ExecutionResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=1.0,
        artifacts=artifacts or [],
        sandbox_error_code=sandbox_error_code,
    )


# --- handle_generate_code_task ---


class TestHandleGenerateCodeTask:
    """代码任务生成处理器测试。"""

    def test_success_path(self, db, monkeypatch):
        """成功路径：生成 CodeTask(CANDIDATE)，包含 code 和 code_version。"""
        from app.modules.llm.code_task_provider import (
            CodeTaskDraft,
            LocalRuleCodeTaskProvider,
        )

        project_id = _create_project(db)
        plan_id, dataset_id, version_id = _seed_confirmed_analysis_plan(db, project_id)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_CODE_TASK.value,
            {"analysis_plan_id": plan_id,
             "dataset_id": dataset_id,
             "dataset_version_id": version_id},
        )
        db.commit()

        # mock provider
        fake_provider = LocalRuleCodeTaskProvider()
        monkeypatch.setattr(
            worker_handlers, "get_code_task_provider",
            lambda: fake_provider,
        )

        result = worker_handlers.handle_generate_code_task(db, job)

        # 验证返回值
        assert result["code_task_id"]
        assert result["code_length"] > 0
        assert result["code_version"] == 1

        # 验证 CodeTask 创建
        task = (
            db.query(CodeTask)
            .filter(CodeTask.id == result["code_task_id"])
            .first()
        )
        assert task is not None
        assert task.status == CodeTaskStatus.CANDIDATE.value
        assert task.candidate_source == "LOCAL_RULE"
        assert task.code
        assert task.analysis_plan_id == plan_id

    def test_plan_not_confirmed_raises(self, db, monkeypatch):
        """分析方案未确认时抛 ANALYSIS_PLAN_NOT_CONFIRMED。"""
        from app.modules.analysis.status import AnalysisPlanStatus

        project_id = _create_project(db)
        plan_id, dataset_id, version_id = _seed_confirmed_analysis_plan(db, project_id)

        # 将 plan 改为 CANDIDATE
        from app.modules.analysis.models import AnalysisPlan
        plan = db.query(AnalysisPlan).filter(AnalysisPlan.id == plan_id).first()
        plan.status = AnalysisPlanStatus.CANDIDATE.value
        db.commit()

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_CODE_TASK.value,
            {"analysis_plan_id": plan_id,
             "dataset_id": dataset_id,
             "dataset_version_id": version_id},
        )
        db.commit()

        from app.modules.llm.code_task_provider import LocalRuleCodeTaskProvider
        monkeypatch.setattr(
            worker_handlers, "get_code_task_provider",
            lambda: LocalRuleCodeTaskProvider(),
        )

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_code_task(db, job)
        assert exc_info.value.code == "ANALYSIS_PLAN_NOT_CONFIRMED"

    def test_missing_analysis_plan_id_raises(self, db):
        """缺少 analysis_plan_id 时抛 JOB_INPUT_INVALID。"""
        project_id = _create_project(db)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_CODE_TASK.value,
            {"dataset_id": "ds_xxx", "dataset_version_id": "v_xxx"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_code_task(db, job)
        assert exc_info.value.code == "JOB_INPUT_INVALID"

    def test_missing_dataset_id_raises(self, db):
        """缺少 dataset_id 时抛 JOB_INPUT_INVALID。"""
        project_id = _create_project(db)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_CODE_TASK.value,
            {"analysis_plan_id": "plan_xxx", "dataset_version_id": "v_xxx"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_code_task(db, job)
        assert exc_info.value.code == "JOB_INPUT_INVALID"

    def test_missing_dataset_version_id_raises(self, db):
        """缺少 dataset_version_id 时抛 JOB_INPUT_INVALID。"""
        project_id = _create_project(db)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_CODE_TASK.value,
            {"analysis_plan_id": "plan_xxx", "dataset_id": "ds_xxx"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_code_task(db, job)
        assert exc_info.value.code == "JOB_INPUT_INVALID"

    def test_plan_not_found_raises(self, db):
        """analysis_plan_id 在数据库找不到时抛 ANALYSIS_PLAN_NOT_FOUND。"""
        project_id = _create_project(db)

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_CODE_TASK.value,
            {"analysis_plan_id": "plan_nonexist",
             "dataset_id": "ds_xxx", "dataset_version_id": "v_xxx"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_code_task(db, job)
        assert exc_info.value.code == "ANALYSIS_PLAN_NOT_FOUND"

    def test_invalid_plan_json_raises(self, db, monkeypatch):
        """分析方案 JSON 解析失败时抛 ANALYSIS_PLAN_INVALID。"""
        from app.modules.analysis.models import AnalysisPlan
        from app.modules.llm.code_task_provider import LocalRuleCodeTaskProvider

        project_id = _create_project(db)
        plan_id, dataset_id, version_id = _seed_confirmed_analysis_plan(db, project_id)

        # 破坏 cleaning_plan JSON
        plan = db.query(AnalysisPlan).filter(AnalysisPlan.id == plan_id).first()
        plan.cleaning_plan = "{invalid json"
        db.commit()

        monkeypatch.setattr(
            worker_handlers, "get_code_task_provider",
            lambda: LocalRuleCodeTaskProvider(),
        )

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_CODE_TASK.value,
            {"analysis_plan_id": plan_id,
             "dataset_id": dataset_id, "dataset_version_id": version_id},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_code_task(db, job)
        assert exc_info.value.code == "ANALYSIS_PLAN_INVALID"


# --- handle_execute_code_task ---


class TestHandleExecuteCodeTask:
    """代码任务执行处理器测试。

    mock execute_code_safe 避免真实 subprocess。
    覆盖成功、脚本错误、沙箱限制、前置条件校验等场景。
    """

    def test_success_path(self, db, monkeypatch):
        """成功路径：执行 exit_code=0，ExecutionRun SUCCEEDED，产物收集。"""
        project_id = _create_project(db, ProjectStatus.ANALYSIS_CONFIRMED.value)
        plan_id, dataset_id, version_id = _seed_confirmed_analysis_plan(db, project_id)
        _seed_dataset_version_with_file(db, project_id, version_id)
        task_id = _seed_confirmed_code_task(db, project_id, plan_id)

        job = job_service.create_job(
            db, project_id, JobType.EXECUTE_CODE_TASK.value,
            {"code_task_id": task_id, "dataset_version_id": version_id},
        )
        db.commit()

        # mock execute_code_safe 返回成功
        artifacts = [
            ArtifactInfo(file_path="stats.csv", file_size_bytes=100,
                         name="stats.csv", artifact_type="TABLE_CSV"),
            ArtifactInfo(file_path="chart.png", file_size_bytes=200,
                         name="chart.png", artifact_type="CHART_PNG"),
        ]
        mock_result = _make_execution_result(
            exit_code=0, stdout="执行成功", artifacts=artifacts,
        )
        monkeypatch.setattr(
            "app.infrastructure.sandbox.python_executor.execute_code_safe",
            lambda **kwargs: mock_result,
        )

        result = worker_handlers.handle_execute_code_task(db, job)

        # 验证返回值
        assert result["run_id"]
        assert result["exit_code"] == 0
        assert result["artifact_count"] == 2
        assert result["duration_seconds"] >= 0

        # 验证 ExecutionRun 状态
        run = (
            db.query(ExecutionRun)
            .filter(ExecutionRun.id == result["run_id"])
            .first()
        )
        assert run.status == ExecutionRunStatus.SUCCEEDED.value
        assert run.exit_code == 0
        assert run.stdout == "执行成功"

        # 验证产物已保存
        arts = (
            db.query(ExecutionArtifact)
            .filter(ExecutionArtifact.execution_run_id == run.id)
            .all()
        )
        assert len(arts) == 2

        # 验证项目状态推进到 EXECUTING
        project = db.query(Project).filter(Project.id == project_id).first()
        assert project.status == ProjectStatus.EXECUTING.value

    def test_script_error_marks_failed(self, db, monkeypatch):
        """脚本错误（exit_code=1）标记 FAILED + EXECUTION_SCRIPT_ERROR。"""
        project_id = _create_project(db, ProjectStatus.ANALYSIS_CONFIRMED.value)
        plan_id, dataset_id, version_id = _seed_confirmed_analysis_plan(db, project_id)
        _seed_dataset_version_with_file(db, project_id, version_id)
        task_id = _seed_confirmed_code_task(db, project_id, plan_id)

        job = job_service.create_job(
            db, project_id, JobType.EXECUTE_CODE_TASK.value,
            {"code_task_id": task_id, "dataset_version_id": version_id},
        )
        db.commit()

        # mock execute_code_safe 返回脚本错误
        mock_result = _make_execution_result(
            exit_code=1,
            stdout="",
            stderr="KeyError: 'diagnosis'",
            sandbox_error_code=None,
        )
        monkeypatch.setattr(
            "app.infrastructure.sandbox.python_executor.execute_code_safe",
            lambda **kwargs: mock_result,
        )

        result = worker_handlers.handle_execute_code_task(db, job)

        # 验证返回值
        assert result["exit_code"] == 1
        assert result["error_code"] == "EXECUTION_SCRIPT_ERROR"
        assert result["artifact_count"] == 0

        # 验证 ExecutionRun FAILED
        run = (
            db.query(ExecutionRun)
            .filter(ExecutionRun.id == result["run_id"])
            .first()
        )
        assert run.status == ExecutionRunStatus.FAILED.value
        assert run.error_code == "EXECUTION_SCRIPT_ERROR"

    def test_sandbox_limit_marks_failed(self, db, monkeypatch):
        """沙箱限制（sandbox_error_code 非 None）标记 FAILED + 对应错误码。"""
        project_id = _create_project(db, ProjectStatus.ANALYSIS_CONFIRMED.value)
        plan_id, dataset_id, version_id = _seed_confirmed_analysis_plan(db, project_id)
        _seed_dataset_version_with_file(db, project_id, version_id)
        task_id = _seed_confirmed_code_task(db, project_id, plan_id)

        job = job_service.create_job(
            db, project_id, JobType.EXECUTE_CODE_TASK.value,
            {"code_task_id": task_id, "dataset_version_id": version_id},
        )
        db.commit()

        # mock execute_code_safe 返回沙箱限制
        mock_result = _make_execution_result(
            exit_code=1,
            stderr="import os 被禁止",
            sandbox_error_code="EXECUTION_IMPORT_FORBIDDEN",
        )
        monkeypatch.setattr(
            "app.infrastructure.sandbox.python_executor.execute_code_safe",
            lambda **kwargs: mock_result,
        )

        result = worker_handlers.handle_execute_code_task(db, job)

        # 验证错误码使用 sandbox_error_code
        assert result["error_code"] == "EXECUTION_IMPORT_FORBIDDEN"

        run = (
            db.query(ExecutionRun)
            .filter(ExecutionRun.id == result["run_id"])
            .first()
        )
        assert run.status == ExecutionRunStatus.FAILED.value
        assert run.error_code == "EXECUTION_IMPORT_FORBIDDEN"

    def test_memory_limit_marks_failed(self, db, monkeypatch):
        """内存超限标记 FAILED + EXECUTION_MEMORY_LIMIT。"""
        project_id = _create_project(db, ProjectStatus.ANALYSIS_CONFIRMED.value)
        plan_id, dataset_id, version_id = _seed_confirmed_analysis_plan(db, project_id)
        _seed_dataset_version_with_file(db, project_id, version_id)
        task_id = _seed_confirmed_code_task(db, project_id, plan_id)

        job = job_service.create_job(
            db, project_id, JobType.EXECUTE_CODE_TASK.value,
            {"code_task_id": task_id, "dataset_version_id": version_id},
        )
        db.commit()

        mock_result = _make_execution_result(
            exit_code=1,
            stderr="内存超限",
            sandbox_error_code="EXECUTION_MEMORY_LIMIT",
        )
        monkeypatch.setattr(
            "app.infrastructure.sandbox.python_executor.execute_code_safe",
            lambda **kwargs: mock_result,
        )

        result = worker_handlers.handle_execute_code_task(db, job)
        assert result["error_code"] == "EXECUTION_MEMORY_LIMIT"

    def test_code_task_not_confirmed_raises(self, db, monkeypatch):
        """代码任务未确认时抛 CODE_TASK_NOT_EXECUTABLE。"""
        project_id = _create_project(db, ProjectStatus.ANALYSIS_CONFIRMED.value)
        plan_id, dataset_id, version_id = _seed_confirmed_analysis_plan(db, project_id)
        _seed_dataset_version_with_file(db, project_id, version_id)
        task_id = _seed_confirmed_code_task(db, project_id, plan_id)

        # 将 task 改为 CANDIDATE
        task = db.query(CodeTask).filter(CodeTask.id == task_id).first()
        task.status = CodeTaskStatus.CANDIDATE.value
        db.commit()

        job = job_service.create_job(
            db, project_id, JobType.EXECUTE_CODE_TASK.value,
            {"code_task_id": task_id, "dataset_version_id": version_id},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_execute_code_task(db, job)
        assert exc_info.value.code == "CODE_TASK_NOT_EXECUTABLE"

    def test_missing_code_task_id_raises(self, db):
        """缺少 code_task_id 时抛 JOB_INPUT_INVALID。"""
        project_id = _create_project(db)

        job = job_service.create_job(
            db, project_id, JobType.EXECUTE_CODE_TASK.value,
            {"dataset_version_id": "v_xxx"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_execute_code_task(db, job)
        assert exc_info.value.code == "JOB_INPUT_INVALID"

    def test_missing_dataset_version_id_raises(self, db):
        """缺少 dataset_version_id 时抛 JOB_INPUT_INVALID。"""
        project_id = _create_project(db)

        job = job_service.create_job(
            db, project_id, JobType.EXECUTE_CODE_TASK.value,
            {"code_task_id": "task_xxx"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_execute_code_task(db, job)
        assert exc_info.value.code == "JOB_INPUT_INVALID"

    def test_dataset_no_file_raises(self, db, monkeypatch):
        """数据集版本未关联文件时抛 DATASET_PARSE_FAILED。"""
        project_id = _create_project(db, ProjectStatus.ANALYSIS_CONFIRMED.value)
        plan_id, dataset_id, version_id = _seed_confirmed_analysis_plan(db, project_id)
        # 不调用 _seed_dataset_version_with_file，file_path 保持占位
        # 将 file_path 设为 None
        from app.modules.datasets.models import DatasetVersion
        version = (
            db.query(DatasetVersion)
            .filter(DatasetVersion.id == version_id)
            .first()
        )
        version.file_path = ""  # 空字符串模拟未关联文件
        db.commit()

        task_id = _seed_confirmed_code_task(db, project_id, plan_id)

        job = job_service.create_job(
            db, project_id, JobType.EXECUTE_CODE_TASK.value,
            {"code_task_id": task_id, "dataset_version_id": version_id},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_execute_code_task(db, job)
        assert exc_info.value.code == "DATASET_PARSE_FAILED"

    def test_artifacts_collected_correctly(self, db, monkeypatch):
        """产物正确收集：TABLE_CSV 和 CHART_PNG 类型都保存。"""
        project_id = _create_project(db, ProjectStatus.ANALYSIS_CONFIRMED.value)
        plan_id, dataset_id, version_id = _seed_confirmed_analysis_plan(db, project_id)
        _seed_dataset_version_with_file(db, project_id, version_id)
        task_id = _seed_confirmed_code_task(db, project_id, plan_id)

        job = job_service.create_job(
            db, project_id, JobType.EXECUTE_CODE_TASK.value,
            {"code_task_id": task_id, "dataset_version_id": version_id},
        )
        db.commit()

        # mock 返回多种类型的产物
        artifacts = [
            ArtifactInfo(file_path="stats.csv", file_size_bytes=150,
                         name="stats.csv", artifact_type="TABLE_CSV"),
            ArtifactInfo(file_path="age_hist.png", file_size_bytes=300,
                         name="age_hist.png", artifact_type="CHART_PNG"),
            ArtifactInfo(file_path="gender_bar.png", file_size_bytes=250,
                         name="gender_bar.png", artifact_type="CHART_PNG"),
        ]
        mock_result = _make_execution_result(exit_code=0, artifacts=artifacts)
        monkeypatch.setattr(
            "app.infrastructure.sandbox.python_executor.execute_code_safe",
            lambda **kwargs: mock_result,
        )

        result = worker_handlers.handle_execute_code_task(db, job)

        assert result["artifact_count"] == 3

        run = (
            db.query(ExecutionRun)
            .filter(ExecutionRun.id == result["run_id"])
            .first()
        )
        arts = (
            db.query(ExecutionArtifact)
            .filter(ExecutionArtifact.execution_run_id == run.id)
            .all()
        )
        assert len(arts) == 3

        # 验证产物类型
        types = {a.artifact_type for a in arts}
        assert "TABLE_CSV" in types
        assert "CHART_PNG" in types

    def test_work_dir_created(self, db, monkeypatch, tmp_path):
        """执行时创建受控工作目录 executions/{run_id}。"""
        from app.core.config import settings

        project_id = _create_project(db, ProjectStatus.ANALYSIS_CONFIRMED.value)
        plan_id, dataset_id, version_id = _seed_confirmed_analysis_plan(db, project_id)
        _seed_dataset_version_with_file(db, project_id, version_id)
        task_id = _seed_confirmed_code_task(db, project_id, plan_id)

        job = job_service.create_job(
            db, project_id, JobType.EXECUTE_CODE_TASK.value,
            {"code_task_id": task_id, "dataset_version_id": version_id},
        )
        db.commit()

        captured_kwargs = {}

        def mock_execute(**kwargs):
            captured_kwargs.update(kwargs)
            return _make_execution_result(exit_code=0)

        monkeypatch.setattr(
            "app.infrastructure.sandbox.python_executor.execute_code_safe",
            mock_execute,
        )

        result = worker_handlers.handle_execute_code_task(db, job)

        # 验证 work_dir 被创建
        work_dir = captured_kwargs.get("work_dir", "")
        assert work_dir, "work_dir 应传给 execute_code_safe"
        assert Path(work_dir).exists(), "work_dir 目录应已创建"
        assert "executions" in work_dir
        assert result["run_id"] in work_dir

    def test_execute_code_safe_called_with_correct_params(
        self, db, monkeypatch
    ):
        """execute_code_safe 被正确参数调用（code, work_dir, data_path）。"""
        project_id = _create_project(db, ProjectStatus.ANALYSIS_CONFIRMED.value)
        plan_id, dataset_id, version_id = _seed_confirmed_analysis_plan(db, project_id)
        csv_path = _seed_dataset_version_with_file(db, project_id, version_id)
        task_id = _seed_confirmed_code_task(db, project_id, plan_id)

        job = job_service.create_job(
            db, project_id, JobType.EXECUTE_CODE_TASK.value,
            {"code_task_id": task_id, "dataset_version_id": version_id},
        )
        db.commit()

        captured = {}

        def mock_execute(**kwargs):
            captured.update(kwargs)
            return _make_execution_result(exit_code=0)

        monkeypatch.setattr(
            "app.infrastructure.sandbox.python_executor.execute_code_safe",
            mock_execute,
        )

        worker_handlers.handle_execute_code_task(db, job)

        # 验证调用参数
        task = db.query(CodeTask).filter(CodeTask.id == task_id).first()
        assert captured["code"] == task.code
        assert captured["data_path"] == csv_path
        assert "work_dir" in captured
        assert "timeout_seconds" in captured
        assert "memory_limit_mb" in captured

    def test_code_task_not_found_raises(self, db):
        """code_task_id 在数据库找不到时抛 CODE_TASK_NOT_FOUND。"""
        project_id = _create_project(db)

        job = job_service.create_job(
            db, project_id, JobType.EXECUTE_CODE_TASK.value,
            {"code_task_id": "task_nonexist", "dataset_version_id": "ver_xxx"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_execute_code_task(db, job)
        assert exc_info.value.code == "CODE_TASK_NOT_FOUND"

    def test_dataset_version_not_found_raises(self, db):
        """dataset_version_id 在数据库找不到时抛 DATASET_VERSION_NOT_FOUND。"""
        project_id = _create_project(db, ProjectStatus.ANALYSIS_CONFIRMED.value)
        plan_id, dataset_id, version_id = _seed_confirmed_analysis_plan(db, project_id)
        task_id = _seed_confirmed_code_task(db, project_id, plan_id)

        # job 引用不存在的 version_id
        job = job_service.create_job(
            db, project_id, JobType.EXECUTE_CODE_TASK.value,
            {"code_task_id": task_id, "dataset_version_id": "ver_nonexist"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_execute_code_task(db, job)
        assert exc_info.value.code == "DATASET_VERSION_NOT_FOUND"

    def test_script_error_empty_stderr(self, db, monkeypatch):
        """脚本错误且 stderr 为空时，错误消息回退为"脚本退出码 N"。"""
        project_id = _create_project(db, ProjectStatus.ANALYSIS_CONFIRMED.value)
        plan_id, dataset_id, version_id = _seed_confirmed_analysis_plan(db, project_id)
        _seed_dataset_version_with_file(db, project_id, version_id)
        task_id = _seed_confirmed_code_task(db, project_id, plan_id)

        job = job_service.create_job(
            db, project_id, JobType.EXECUTE_CODE_TASK.value,
            {"code_task_id": task_id, "dataset_version_id": version_id},
        )
        db.commit()

        mock_result = _make_execution_result(
            exit_code=1, stdout="", stderr="", sandbox_error_code=None,
        )
        monkeypatch.setattr(
            "app.infrastructure.sandbox.python_executor.execute_code_safe",
            lambda **kwargs: mock_result,
        )

        result = worker_handlers.handle_execute_code_task(db, job)
        assert result["error_code"] == "EXECUTION_SCRIPT_ERROR"

        run = (
            db.query(ExecutionRun)
            .filter(ExecutionRun.id == result["run_id"])
            .first()
        )
        assert run.error_message == "脚本退出码 1"


# --- HANDLERS 注册表 ---


class TestHandlersRegistryExecution:
    """HANDLERS 注册表测试：覆盖 EXECUTE_CODE_TASK 和 GENERATE_CODE_TASK。"""

    def test_handlers_registry_includes_code_task_handlers(self):
        """HANDLERS 包含 GENERATE_CODE_TASK 和 EXECUTE_CODE_TASK 的映射。"""
        assert (
            worker_handlers.HANDLERS[JobType.GENERATE_CODE_TASK.value]
            is worker_handlers.handle_generate_code_task
        )
        assert (
            worker_handlers.HANDLERS[JobType.EXECUTE_CODE_TASK.value]
            is worker_handlers.handle_execute_code_task
        )
