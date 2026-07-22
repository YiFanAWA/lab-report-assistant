"""执行核心 API 端点测试。

覆盖 11 个端点的成功路径、失败路径与状态机推进：
- POST /analysis/{plan_id}/code/generate
- GET  /code-tasks
- GET  /code-tasks/{task_id}
- PUT  /code-tasks/{task_id}
- POST /code-tasks/{task_id}/confirm
- POST /code-tasks/{task_id}/reject
- POST /code-tasks/{task_id}/execute
- GET  /execution-runs
- GET  /execution-runs/{run_id}
- GET  /execution-runs/{run_id}/artifacts/{artifact_id}
- POST /execution-runs/complete
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.engine import Base
from app.main import app
from app.modules.projects.models import Project  # noqa: F401
from app.modules.requirements.models import (  # noqa: F401
    RequirementSource,
    RequirementPlan,
    ChangeRecord,
)
from app.modules.sources.models import (  # noqa: F401
    Source,
    ParsedDocument,
    EvidenceCard,
)
from app.modules.jobs.models import BackgroundJob  # noqa: F401
from app.modules.datasets.models import Dataset, DatasetVersion  # noqa: F401
from app.modules.analysis.models import AnalysisPlan  # noqa: F401
from app.modules.execution.models import (  # noqa: F401
    CodeTask,
    ExecutionRun,
    ExecutionArtifact,
)
from app.modules.datasets.status import (
    DatasetKind,
    DatasetStatus,
    DatasetVersionStatus,
)
from app.modules.analysis.status import AnalysisPlanStatus
from app.modules.execution.status import (
    CodeTaskStatus,
    ExecutionRunStatus,
    ExecutionArtifactType,
)
from app.modules.projects.status import ProjectStatus


TEST_DB = "sqlite:///:memory:"


@pytest.fixture
def client(monkeypatch, tmp_path):
    """TestClient + 内存 SQLite + 受控工作区。"""
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    engine = create_engine(
        TEST_DB,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    from app.api.routers import projects as project_router
    from app.api.routers import requirements as requirement_router
    from app.api.routers import sources as sources_router
    from app.api.routers import evidence as evidence_router
    from app.api.routers import jobs as jobs_router
    from app.api.routers import datasets as datasets_router
    from app.api.routers import analysis as analysis_router
    from app.api.routers import code_tasks as code_tasks_router
    from app.api.routers import execution_runs as execution_runs_router

    monkeypatch.setattr(project_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(requirement_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(sources_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(evidence_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(jobs_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(datasets_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(analysis_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(code_tasks_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(execution_runs_router, "SessionLocal", TestingSessionLocal)

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)


def _create_project(client: TestClient) -> str:
    """创建项目，返回项目 ID。"""
    response = client.post(
        "/api/projects",
        json={"name": "胃病数据分析", "topic": "胃病数据分析"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _seed_dataset_ready_project(SessionLocal) -> tuple[str, str, str, str]:
    """创建 ANALYSIS_CONFIRMED 状态项目 + READY 数据集 + PARSED 版本 + CONFIRMED 方案。

    返回 (project_id, dataset_id, version_id, plan_id)。
    """
    project_id = _create_project_with_status(SessionLocal, ProjectStatus.ANALYSIS_CONFIRMED.value)
    dataset_id = "ds_exec_test"
    version_id = "ver_exec_001"
    plan_id = "plan_confirmed"

    db = SessionLocal()
    try:
        dataset = Dataset(
            id=dataset_id,
            project_id=project_id,
            dataset_kind=DatasetKind.FILE.value,
            title="执行测试数据集",
            status=DatasetStatus.READY.value,
        )
        db.add(dataset)
        version = DatasetVersion(
            id=version_id,
            dataset_id=dataset.id,
            project_id=project_id,
            version=1,
            status=DatasetVersionStatus.PARSED.value,
            file_path="/tmp/raw.csv",
            file_size_bytes=100,
            row_count=10,
            column_count=3,
            profile_json='{"row_count": 10, "column_count": 3, "field_profiles": []}',
        )
        db.add(version)
        plan = AnalysisPlan(
            id=plan_id,
            project_id=project_id,
            dataset_id=dataset.id,
            dataset_version_id=version.id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CONFIRMED.value,
            candidate_source="LOCAL_RULE",
            confirmed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        db.add(plan)
        db.commit()
        return project_id, dataset_id, version_id, plan_id
    finally:
        db.close()


def _create_project_with_status(SessionLocal, status: str) -> str:
    """通过 service 创建项目（自动设置 workspace_root），然后修改状态。"""
    from app.modules.projects.contracts import ProjectCreateRequest
    from app.modules.projects import service as project_service
    db = SessionLocal()
    try:
        req = ProjectCreateRequest(name="执行测试项目", topic="胃病数据分析")
        project = project_service.create_project(db, req)
        project.status = status
        db.commit()
        return project.id
    finally:
        db.close()


def _seed_candidate_code_task(SessionLocal, project_id: str, dataset_id: str,
                               version_id: str, plan_id: str,
                               task_id: str = "task_api_001",
                               status: str = CodeTaskStatus.CANDIDATE.value,
                               code: str = "print('hello')") -> str:
    """直接插入 CodeTask。"""
    db = SessionLocal()
    try:
        task = CodeTask(
            id=task_id,
            project_id=project_id,
            analysis_plan_id=plan_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            code=code,
            code_version=1,
            status=status,
            candidate_source="LOCAL_RULE",
        )
        db.add(task)
        db.commit()
        return task.id
    finally:
        db.close()


def _seed_execution_run(SessionLocal, project_id: str, task_id: str,
                        version_id: str, run_id: str = "run_api_001",
                        status: str = ExecutionRunStatus.SUCCEEDED.value,
                        stdout: str = "ok") -> str:
    """直接插入 ExecutionRun。"""
    db = SessionLocal()
    try:
        run = ExecutionRun(
            id=run_id,
            project_id=project_id,
            code_task_id=task_id,
            dataset_version_id=version_id,
            code_version=1,
            status=status,
            stdout=stdout,
            stderr="",
            exit_code=0 if status == ExecutionRunStatus.SUCCEEDED.value else 1,
            started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            finished_at=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
            duration_seconds=1.0,
        )
        db.add(run)
        db.commit()
        return run.id
    finally:
        db.close()


def _seed_artifact(SessionLocal, project_id: str, run_id: str,
                   artifact_id: str = "art_api_001",
                   name: str = "chart.png",
                   file_path: str = "chart.png") -> str:
    """直接插入 ExecutionArtifact。"""
    db = SessionLocal()
    try:
        art = ExecutionArtifact(
            id=artifact_id,
            execution_run_id=run_id,
            project_id=project_id,
            artifact_type=ExecutionArtifactType.CHART_PNG.value
            if name.endswith(".png") else ExecutionArtifactType.TABLE_CSV.value,
            file_path=file_path,
            file_size_bytes=100,
            name=name,
        )
        db.add(art)
        db.commit()
        return art.id
    finally:
        db.close()


# --- POST /analysis/{plan_id}/code/generate ---


class TestGenerateCodeTaskApi:
    """触发生成代码候选 API 测试。"""

    def test_generate_returns_201_with_job_id(self, client):
        """成功触发，返回 job_id。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)

        response = client.post(
            f"/api/projects/{project_id}/analysis/{plan_id}/code/generate"
        )
        assert response.status_code == 201
        assert response.json()["job_id"]

    def test_rejects_when_plan_not_confirmed(self, client):
        """方案未 CONFIRMED 返回 ANALYSIS_PLAN_NOT_CONFIRMED。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)

        # 将方案状态改为 CANDIDATE
        db = SessionLocal()
        try:
            plan = db.query(AnalysisPlan).filter(AnalysisPlan.id == plan_id).first()
            plan.status = AnalysisPlanStatus.CANDIDATE.value
            db.commit()
        finally:
            db.close()

        response = client.post(
            f"/api/projects/{project_id}/analysis/{plan_id}/code/generate"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "ANALYSIS_PLAN_NOT_CONFIRMED"

    def test_returns_404_when_project_missing(self, client):
        """项目不存在时返回 PROJECT_NOT_FOUND。"""
        response = client.post(
            "/api/projects/proj_missing/analysis/plan_x/code/generate"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    def test_rejects_when_project_not_analysis_confirmed(self, client):
        """项目状态未达 ANALYSIS_CONFIRMED 时返回 PROJECT_ANALYSIS_NOT_CONFIRMED。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)

        # 将项目状态降级
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            project.status = ProjectStatus.DATASET_READY.value
            db.commit()
        finally:
            db.close()

        response = client.post(
            f"/api/projects/{project_id}/analysis/{plan_id}/code/generate"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PROJECT_ANALYSIS_NOT_CONFIRMED"


# --- GET /code-tasks (列表) ---


class TestListCodeTasksApi:
    """代码任务列表 API 测试。"""

    def test_lists_tasks(self, client):
        """GET /code-tasks 返回 CodeTaskListResponse。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_list_1",
        )
        _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_list_2",
        )

        response = client.get(f"/api/projects/{project_id}/code-tasks")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 2

    def test_filters_by_status(self, client):
        """按 status 过滤。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_filter_cand",
            status=CodeTaskStatus.CANDIDATE.value,
        )
        _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_filter_conf",
            status=CodeTaskStatus.CONFIRMED.value,
        )

        response = client.get(
            f"/api/projects/{project_id}/code-tasks?status=CONFIRMED"
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["status"] == "CONFIRMED"

    def test_returns_empty_when_no_tasks(self, client):
        """无代码任务时返回空列表。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, _, _, _ = _seed_dataset_ready_project(SessionLocal)

        response = client.get(f"/api/projects/{project_id}/code-tasks")
        assert response.status_code == 200
        assert response.json()["items"] == []


# --- GET /code-tasks/{task_id} (详情) ---


class TestGetCodeTaskApi:
    """代码任务详情 API 测试。"""

    def test_returns_task_by_id(self, client):
        """GET /code-tasks/{task_id} 返回 CodeTaskResponse。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_get_1",
        )

        response = client.get(
            f"/api/projects/{project_id}/code-tasks/{task_id}"
        )
        assert response.status_code == 200
        assert response.json()["id"] == task_id
        assert response.json()["code"] == "print('hello')"

    def test_returns_404_when_task_missing(self, client):
        """代码任务不存在时返回 CODE_TASK_NOT_FOUND。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, _, _, _ = _seed_dataset_ready_project(SessionLocal)

        response = client.get(
            f"/api/projects/{project_id}/code-tasks/task_missing"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "CODE_TASK_NOT_FOUND"


# --- PUT /code-tasks/{task_id} (编辑) ---


class TestUpdateCodeTaskApi:
    """编辑代码任务 API 测试。"""

    def test_updates_candidate_task(self, client):
        """编辑 CANDIDATE 代码，code_version 递增。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_upd_cand",
        )

        response = client.put(
            f"/api/projects/{project_id}/code-tasks/{task_id}",
            json={"code": "print('updated')"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "print('updated')"
        assert body["code_version"] == 2
        assert body["status"] == "CANDIDATE"

    def test_confirmed_task_edits_back_to_candidate(self, client):
        """编辑 CONFIRMED 代码 → 状态回到 CANDIDATE，confirmed_at 清空。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_upd_conf",
            status=CodeTaskStatus.CONFIRMED.value,
        )

        response = client.put(
            f"/api/projects/{project_id}/code-tasks/{task_id}",
            json={"code": "print('revised')"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "CANDIDATE"
        assert body["confirmed_at"] is None

    def test_rejects_updating_stale_task(self, client):
        """编辑 STALE 代码返回 CODE_TASK_NOT_EDITABLE。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_upd_stale",
            status=CodeTaskStatus.STALE.value,
        )

        response = client.put(
            f"/api/projects/{project_id}/code-tasks/{task_id}",
            json={"code": "print('x')"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CODE_TASK_NOT_EDITABLE"

    def test_rejects_updating_rejected_task(self, client):
        """编辑 REJECTED 代码返回 CODE_TASK_NOT_EDITABLE。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_upd_rej",
            status=CodeTaskStatus.REJECTED.value,
        )

        response = client.put(
            f"/api/projects/{project_id}/code-tasks/{task_id}",
            json={"code": "print('x')"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CODE_TASK_NOT_EDITABLE"

    def test_propagates_stale_to_execution_runs(self, client):
        """编辑 CONFIRMED 代码 → 关联 ExecutionRun 全部变 STALE。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_stale_prop",
            status=CodeTaskStatus.CONFIRMED.value,
        )
        _seed_execution_run(
            SessionLocal, project_id, task_id, version_id,
            run_id="run_stale_1",
            status=ExecutionRunStatus.SUCCEEDED.value,
        )

        response = client.put(
            f"/api/projects/{project_id}/code-tasks/{task_id}",
            json={"code": "print('revised')"},
        )
        assert response.status_code == 200

        # 验证 ExecutionRun 变 STALE
        db = SessionLocal()
        try:
            run = db.query(ExecutionRun).filter(
                ExecutionRun.id == "run_stale_1").first()
            assert run.status == ExecutionRunStatus.STALE.value
        finally:
            db.close()


# --- POST /code-tasks/{task_id}/confirm ---


class TestConfirmCodeTaskApi:
    """确认代码任务 API 测试。"""

    def test_confirms_candidate_returns_200(self, client):
        """确认 CANDIDATE 代码 → CONFIRMED。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_conf_1",
        )

        response = client.post(
            f"/api/projects/{project_id}/code-tasks/{task_id}/confirm"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "CONFIRMED"
        assert body["confirmed_at"] is not None

    def test_returns_400_when_not_candidate(self, client):
        """非 CANDIDATE 状态确认返回 400。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_conf_fail",
            status=CodeTaskStatus.CONFIRMED.value,
        )

        response = client.post(
            f"/api/projects/{project_id}/code-tasks/{task_id}/confirm"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CODE_TASK_NOT_CONFIRMABLE"

    def test_returns_404_when_task_missing(self, client):
        """代码任务不存在时返回 404。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, _, _, _ = _seed_dataset_ready_project(SessionLocal)

        response = client.post(
            f"/api/projects/{project_id}/code-tasks/task_missing/confirm"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "CODE_TASK_NOT_FOUND"


# --- POST /code-tasks/{task_id}/reject ---


class TestRejectCodeTaskApi:
    """拒绝代码任务 API 测试。"""

    def test_rejects_candidate_returns_200(self, client):
        """拒绝 CANDIDATE 代码 → REJECTED。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_rej_1",
        )

        response = client.post(
            f"/api/projects/{project_id}/code-tasks/{task_id}/reject"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "REJECTED"

    def test_returns_400_when_not_candidate(self, client):
        """非 CANDIDATE 状态拒绝返回 400。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_rej_fail",
            status=CodeTaskStatus.REJECTED.value,
        )

        response = client.post(
            f"/api/projects/{project_id}/code-tasks/{task_id}/reject"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CODE_TASK_NOT_CONFIRMABLE"


# --- POST /code-tasks/{task_id}/execute ---


class TestExecuteCodeTaskApi:
    """触发执行 API 测试。"""

    def test_execute_returns_201_with_job_id(self, client):
        """CONFIRMED 代码触发执行返回 201。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_exec_1",
            status=CodeTaskStatus.CONFIRMED.value,
        )

        response = client.post(
            f"/api/projects/{project_id}/code-tasks/{task_id}/execute"
        )
        assert response.status_code == 201
        body = response.json()
        assert body["job_id"]
        assert body["code_task_id"] == task_id

    def test_returns_400_when_not_confirmed(self, client):
        """非 CONFIRMED 状态执行返回 CODE_TASK_NOT_EXECUTABLE。"""
        from app.api.routers import code_tasks as code_tasks_router
        SessionLocal = code_tasks_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_exec_fail",
            status=CodeTaskStatus.CANDIDATE.value,
        )

        response = client.post(
            f"/api/projects/{project_id}/code-tasks/{task_id}/execute"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CODE_TASK_NOT_EXECUTABLE"


# --- GET /execution-runs (列表) ---


class TestListExecutionRunsApi:
    """执行记录列表 API 测试。"""

    def test_lists_runs(self, client):
        """GET /execution-runs 返回 ExecutionRunListResponse。"""
        from app.api.routers import execution_runs as execution_runs_router
        SessionLocal = execution_runs_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_list_runs",
        )
        _seed_execution_run(
            SessionLocal, project_id, task_id, version_id,
            run_id="run_list_1",
        )
        _seed_execution_run(
            SessionLocal, project_id, task_id, version_id,
            run_id="run_list_2",
        )

        response = client.get(f"/api/projects/{project_id}/execution-runs")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 2
        assert items[0]["artifacts"] == []

    def test_filters_by_status(self, client):
        """按 status 过滤。"""
        from app.api.routers import execution_runs as execution_runs_router
        SessionLocal = execution_runs_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_filter_runs",
        )
        _seed_execution_run(
            SessionLocal, project_id, task_id, version_id,
            run_id="run_filter_succ",
            status=ExecutionRunStatus.SUCCEEDED.value,
        )
        _seed_execution_run(
            SessionLocal, project_id, task_id, version_id,
            run_id="run_filter_fail",
            status=ExecutionRunStatus.FAILED.value,
        )

        response = client.get(
            f"/api/projects/{project_id}/execution-runs?status=FAILED"
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["status"] == "FAILED"

    def test_includes_artifacts_in_response(self, client):
        """列表中包含 artifacts 字段。"""
        from app.api.routers import execution_runs as execution_runs_router
        SessionLocal = execution_runs_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_art_list",
        )
        run_id = _seed_execution_run(
            SessionLocal, project_id, task_id, version_id,
            run_id="run_art_list",
        )
        _seed_artifact(
            SessionLocal, project_id, run_id,
            artifact_id="art_list_1",
            name="chart.png",
        )

        response = client.get(f"/api/projects/{project_id}/execution-runs")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items[0]["artifacts"]) == 1


# --- GET /execution-runs/{run_id} (详情) ---


class TestGetExecutionRunApi:
    """执行记录详情 API 测试。"""

    def test_returns_run_by_id(self, client):
        """GET /execution-runs/{run_id} 返回 ExecutionRunResponse。"""
        from app.api.routers import execution_runs as execution_runs_router
        SessionLocal = execution_runs_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_get_run",
        )
        run_id = _seed_execution_run(
            SessionLocal, project_id, task_id, version_id,
            run_id="run_get_1",
            stdout="execution output",
        )
        _seed_artifact(
            SessionLocal, project_id, run_id,
            artifact_id="art_get_1",
            name="chart.png",
        )

        response = client.get(
            f"/api/projects/{project_id}/execution-runs/{run_id}"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == run_id
        assert body["stdout"] == "execution output"
        assert body["exit_code"] == 0
        assert len(body["artifacts"]) == 1
        assert body["artifacts"][0]["name"] == "chart.png"

    def test_returns_404_when_run_missing(self, client):
        """执行记录不存在时返回 EXECUTION_RUN_NOT_FOUND。"""
        from app.api.routers import execution_runs as execution_runs_router
        SessionLocal = execution_runs_router.SessionLocal
        project_id, _, _, _ = _seed_dataset_ready_project(SessionLocal)

        response = client.get(
            f"/api/projects/{project_id}/execution-runs/run_missing"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "EXECUTION_RUN_NOT_FOUND"


# --- GET /execution-runs/{run_id}/artifacts/{artifact_id} (下载) ---


class TestDownloadArtifactApi:
    """下载产物 API 测试。"""

    def test_downloads_png(self, client, tmp_path):
        """下载 PNG 产物返回 image/png。"""
        from app.api.routers import execution_runs as execution_runs_router
        SessionLocal = execution_runs_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_dl_png",
        )
        run_id = _seed_execution_run(
            SessionLocal, project_id, task_id, version_id,
            run_id="run_dl_png",
        )
        art_id = _seed_artifact(
            SessionLocal, project_id, run_id,
            artifact_id="art_dl_png",
            name="chart.png",
            file_path="chart.png",
        )

        # 创建实际产物文件
        run_dir = tmp_path / "projects" / project_id / "executions" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "chart.png").write_bytes(b"\x89PNG\r\n\x1a\nfake-png-data")

        response = client.get(
            f"/api/projects/{project_id}/execution-runs/{run_id}/artifacts/{art_id}"
        )
        assert response.status_code == 200
        assert "image/png" in response.headers.get("content-type", "")
        assert response.content == b"\x89PNG\r\n\x1a\nfake-png-data"

    def test_downloads_csv(self, client, tmp_path):
        """下载 CSV 产物返回 text/csv。"""
        from app.api.routers import execution_runs as execution_runs_router
        SessionLocal = execution_runs_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_dl_csv",
        )
        run_id = _seed_execution_run(
            SessionLocal, project_id, task_id, version_id,
            run_id="run_dl_csv",
        )
        art_id = _seed_artifact(
            SessionLocal, project_id, run_id,
            artifact_id="art_dl_csv",
            name="table.csv",
            file_path="table.csv",
        )

        run_dir = tmp_path / "projects" / project_id / "executions" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "table.csv").write_bytes(b"a,b\n1,2\n")

        response = client.get(
            f"/api/projects/{project_id}/execution-runs/{run_id}/artifacts/{art_id}"
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        assert b"a,b\n1,2\n" in response.content

    def test_returns_404_when_artifact_missing(self, client):
        """产物不存在时返回 EXECUTION_ARTIFACT_NOT_FOUND。"""
        from app.api.routers import execution_runs as execution_runs_router
        SessionLocal = execution_runs_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_dl_404",
        )
        run_id = _seed_execution_run(
            SessionLocal, project_id, task_id, version_id,
            run_id="run_dl_404",
        )

        response = client.get(
            f"/api/projects/{project_id}/execution-runs/{run_id}/artifacts/art_missing"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "EXECUTION_ARTIFACT_NOT_FOUND"


# --- POST /execution-runs/complete ---


class TestCompleteExecutionApi:
    """完成结果确认 API 测试。"""

    def test_completes_when_succeeded_run_exists(self, client):
        """存在 SUCCEEDED 执行时推进到 RESULT_CONFIRMED。"""
        from app.api.routers import execution_runs as execution_runs_router
        SessionLocal = execution_runs_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_complete",
        )
        _seed_execution_run(
            SessionLocal, project_id, task_id, version_id,
            run_id="run_complete_succ",
            status=ExecutionRunStatus.SUCCEEDED.value,
        )

        response = client.post(
            f"/api/projects/{project_id}/execution-runs/complete"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "RESULT_CONFIRMED"

    def test_rejects_when_no_succeeded_run(self, client):
        """无 SUCCEEDED 执行时返回 PROJECT_NO_SUCCESSFUL_EXECUTION_RUN。"""
        from app.api.routers import execution_runs as execution_runs_router
        SessionLocal = execution_runs_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)
        task_id = _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_no_succ",
        )
        _seed_execution_run(
            SessionLocal, project_id, task_id, version_id,
            run_id="run_failed_only",
            status=ExecutionRunStatus.FAILED.value,
        )

        response = client.post(
            f"/api/projects/{project_id}/execution-runs/complete"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PROJECT_NO_SUCCESSFUL_EXECUTION_RUN"

    def test_returns_404_when_project_missing(self, client):
        """项目不存在时返回 PROJECT_NOT_FOUND。"""
        response = client.post(
            "/api/projects/proj_missing/execution-runs/complete"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


# --- STALE 传播端到端 ---


class TestStalePropagationFlow:
    """STALE 传播端到端测试。"""

    def test_reconfirm_analysis_plan_propagates_stale_to_code_tasks(self, client):
        """重新确认 AnalysisPlan → 关联 CodeTask 全部变 STALE。"""
        from app.api.routers import analysis as analysis_router
        SessionLocal = analysis_router.SessionLocal
        project_id, dataset_id, version_id, plan_id = _seed_dataset_ready_project(SessionLocal)

        # 先创建一个 CANDIDATE CodeTask
        _seed_candidate_code_task(
            SessionLocal, project_id, dataset_id, version_id, plan_id,
            task_id="task_stale_prop_e2e",
            status=CodeTaskStatus.CANDIDATE.value,
        )

        # 将方案降回 CANDIDATE
        db = SessionLocal()
        try:
            plan = db.query(AnalysisPlan).filter(AnalysisPlan.id == plan_id).first()
            plan.status = AnalysisPlanStatus.CANDIDATE.value
            db.commit()
        finally:
            db.close()

        # 重新确认方案
        response = client.post(
            f"/api/projects/{project_id}/analysis/{plan_id}/confirm"
        )
        assert response.status_code == 200

        # 验证 CodeTask 变 STALE
        db = SessionLocal()
        try:
            task = db.query(CodeTask).filter(
                CodeTask.id == "task_stale_prop_e2e").first()
            assert task.status == CodeTaskStatus.STALE.value
        finally:
            db.close()
