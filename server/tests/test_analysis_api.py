"""分析方案 API 端点测试。

使用 TestClient + monkeypatch SessionLocal，覆盖 7 个 API 端点的成功与失败路径：
- POST /datasets/{dataset_id}/analysis/generate
- GET /analysis
- GET /analysis/{plan_id}
- PUT /analysis/{plan_id}
- POST /analysis/{plan_id}/confirm
- POST /analysis/{plan_id}/reject
- POST /analysis/complete
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
from app.modules.datasets.status import (
    DatasetKind,
    DatasetStatus,
    DatasetVersionStatus,
)
from app.modules.analysis.status import AnalysisPlanStatus
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

    monkeypatch.setattr(project_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(requirement_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(sources_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(evidence_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(jobs_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(datasets_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(analysis_router, "SessionLocal", TestingSessionLocal)

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


def _seed_dataset_ready_project(client: TestClient) -> tuple[str, str, str]:
    """创建一个 DATASET_READY 状态项目 + READY 数据集 + PARSED 版本。

    返回 (project_id, dataset_id, version_id)。
    """
    project_id = _create_project(client)

    from app.api.routers import projects as project_router
    SessionLocal = project_router.SessionLocal
    from app.modules.projects.models import Project

    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        project.status = ProjectStatus.DATASET_READY.value

        # 创建 READY 数据集 + PARSED 版本
        dataset = Dataset(
            id="ds_api_test",
            project_id=project_id,
            dataset_kind=DatasetKind.FILE.value,
            title="API 测试数据集",
            status=DatasetStatus.READY.value,
        )
        db.add(dataset)
        version = DatasetVersion(
            id="ver_api_001",
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
        db.commit()
        return project_id, dataset.id, version.id
    finally:
        db.close()


def _seed_candidate_plan(SessionLocal, project_id: str, dataset_id: str,
                          version_id: str, plan_id: str = "plan_api_001") -> str:
    """直接插入 CANDIDATE 分析方案。"""
    db = SessionLocal()
    try:
        plan = AnalysisPlan(
            id=plan_id,
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        db.add(plan)
        db.commit()
        return plan.id
    finally:
        db.close()


def _seed_confirmed_plan(SessionLocal, project_id: str, dataset_id: str,
                          version_id: str, plan_id: str = "plan_confirmed") -> str:
    """直接插入 CONFIRMED 分析方案。"""
    db = SessionLocal()
    try:
        plan = AnalysisPlan(
            id=plan_id,
            project_id=project_id,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CONFIRMED.value,
            candidate_source="LOCAL_RULE",
            confirmed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        db.add(plan)
        db.commit()
        return plan.id
    finally:
        db.close()


# --- POST /datasets/{dataset_id}/analysis/generate ---


class TestGenerateAnalysisPlanApi:
    """触发生成分析方案 API 测试。"""

    def test_generate_returns_201_with_job_id(self, client):
        """成功触发生成方案，返回 job_id。"""
        project_id, dataset_id, _ = _seed_dataset_ready_project(client)

        response = client.post(
            f"/api/projects/{project_id}/datasets/{dataset_id}/analysis/generate"
        )
        assert response.status_code == 201
        assert response.json()["job_id"]

    def test_rejects_when_dataset_not_ready(self, client):
        """数据集未 READY 时返回 DATASET_NOT_PARSED。"""
        project_id = _create_project(client)
        from app.api.routers import projects as project_router
        SessionLocal = project_router.SessionLocal
        from app.modules.projects.models import Project

        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            project.status = ProjectStatus.DATASET_READY.value
            dataset = Dataset(
                id="ds_pending_api",
                project_id=project_id,
                dataset_kind=DatasetKind.FILE.value,
                title="X",
                status=DatasetStatus.PENDING.value,
            )
            db.add(dataset)
            db.commit()
            dataset_id = dataset.id
        finally:
            db.close()

        response = client.post(
            f"/api/projects/{project_id}/datasets/{dataset_id}/analysis/generate"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DATASET_NOT_PARSED"

    def test_returns_404_when_dataset_missing(self, client):
        """数据集不存在时返回 DATASET_NOT_FOUND。"""
        project_id, _, _ = _seed_dataset_ready_project(client)
        response = client.post(
            f"/api/projects/{project_id}/datasets/ds_missing/analysis/generate"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "DATASET_NOT_FOUND"

    def test_returns_404_when_project_missing(self, client):
        """项目不存在时返回 PROJECT_NOT_FOUND。"""
        response = client.post(
            "/api/projects/proj_missing/datasets/ds_x/analysis/generate"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


# --- GET /analysis (列表) ---


class TestListAnalysisPlansApi:
    """分析方案列表 API 测试。"""

    def test_lists_plans(self, client):
        """GET /analysis 返回 AnalysisPlanListResponse。"""
        project_id, dataset_id, version_id = _seed_dataset_ready_project(client)
        from app.api.routers import analysis as analysis_router
        _seed_candidate_plan(
            analysis_router.SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_list_1",
        )
        _seed_candidate_plan(
            analysis_router.SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_list_2",
        )

        response = client.get(f"/api/projects/{project_id}/analysis")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 2

    def test_filters_by_dataset_id(self, client):
        """按 dataset_id 过滤。"""
        project_id, dataset_id, version_id = _seed_dataset_ready_project(client)
        from app.api.routers import analysis as analysis_router
        SessionLocal = analysis_router.SessionLocal
        _seed_candidate_plan(
            SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_filter_1",
        )

        # 创建第二个数据集
        db = SessionLocal()
        try:
            ds2 = Dataset(
                id="ds_filter_2",
                project_id=project_id,
                dataset_kind=DatasetKind.FILE.value,
                title="X",
                status=DatasetStatus.READY.value,
            )
            db.add(ds2)
            v2 = DatasetVersion(
                id="ver_filter_2",
                dataset_id=ds2.id,
                project_id=project_id,
                version=1,
                status=DatasetVersionStatus.PARSED.value,
                file_path="/tmp/x.csv",
                file_size_bytes=100,
            )
            db.add(v2)
            db.commit()
            ds2_id = ds2.id
            v2_id = v2.id
        finally:
            db.close()
        _seed_candidate_plan(
            SessionLocal, project_id, ds2_id, v2_id,
            plan_id="plan_filter_2",
        )

        response = client.get(
            f"/api/projects/{project_id}/analysis",
            params={"dataset_id": dataset_id},
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["dataset_id"] == dataset_id

    def test_filters_by_status(self, client):
        """按 status 过滤。"""
        project_id, dataset_id, version_id = _seed_dataset_ready_project(client)
        from app.api.routers import analysis as analysis_router
        SessionLocal = analysis_router.SessionLocal
        _seed_candidate_plan(
            SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_status_cand",
        )
        _seed_confirmed_plan(
            SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_status_conf",
        )

        cand_resp = client.get(
            f"/api/projects/{project_id}/analysis",
            params={"status": "CANDIDATE"},
        )
        assert cand_resp.status_code == 200
        cand_items = cand_resp.json()["items"]
        assert len(cand_items) == 1
        assert cand_items[0]["status"] == "CANDIDATE"

        conf_resp = client.get(
            f"/api/projects/{project_id}/analysis",
            params={"status": "CONFIRMED"},
        )
        assert conf_resp.status_code == 200
        conf_items = conf_resp.json()["items"]
        assert len(conf_items) == 1
        assert conf_items[0]["status"] == "CONFIRMED"

    def test_returns_empty_when_no_plans(self, client):
        """无方案时返回空列表。"""
        project_id, _, _ = _seed_dataset_ready_project(client)
        response = client.get(f"/api/projects/{project_id}/analysis")
        assert response.status_code == 200
        assert response.json()["items"] == []

    def test_returns_404_when_project_missing(self, client):
        """项目不存在时返回 PROJECT_NOT_FOUND。"""
        response = client.get("/api/projects/proj_missing/analysis")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


# --- GET /analysis/{plan_id} ---


class TestGetAnalysisPlanApi:
    """分析方案详情 API 测试。"""

    def test_returns_plan_by_id(self, client):
        """GET /analysis/{plan_id} 返回 AnalysisPlanResponse。"""
        project_id, dataset_id, version_id = _seed_dataset_ready_project(client)
        from app.api.routers import analysis as analysis_router
        plan_id = _seed_candidate_plan(
            analysis_router.SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_get_001",
        )

        response = client.get(
            f"/api/projects/{project_id}/analysis/{plan_id}"
        )
        assert response.status_code == 200
        assert response.json()["id"] == plan_id

    def test_returns_404_when_plan_missing(self, client):
        """方案不存在时返回 ANALYSIS_PLAN_NOT_FOUND。"""
        project_id, _, _ = _seed_dataset_ready_project(client)
        response = client.get(
            f"/api/projects/{project_id}/analysis/plan_missing"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ANALYSIS_PLAN_NOT_FOUND"


# --- PUT /analysis/{plan_id} ---


class TestUpdateAnalysisPlanApi:
    """更新分析方案 API 测试。"""

    def test_updates_candidate_plan(self, client):
        """PUT /analysis/{plan_id} 更新 CANDIDATE 方案。"""
        project_id, dataset_id, version_id = _seed_dataset_ready_project(client)
        from app.api.routers import analysis as analysis_router
        plan_id = _seed_candidate_plan(
            analysis_router.SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_upd_api",
        )

        response = client.put(
            f"/api/projects/{project_id}/analysis/{plan_id}",
            json={
                "cleaning_plan": '[{"field": "x"}]',
                "analysis_plan": '[{"analysis_type": "X"}]',
                "chart_plan": '[{"chart_type": "BAR"}]',
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["cleaning_plan"] == '[{"field": "x"}]'
        assert data["status"] == "CANDIDATE"

    def test_confirmed_plan_edits_back_to_candidate(self, client):
        """编辑 CONFIRMED 方案后状态回到 CANDIDATE。"""
        project_id, dataset_id, version_id = _seed_dataset_ready_project(client)
        from app.api.routers import analysis as analysis_router
        plan_id = _seed_confirmed_plan(
            analysis_router.SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_back_cand",
        )

        response = client.put(
            f"/api/projects/{project_id}/analysis/{plan_id}",
            json={"cleaning_plan": '[{"new": true}]'},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "CANDIDATE"
        assert response.json()["confirmed_at"] is None

    def test_returns_404_when_plan_missing(self, client):
        """方案不存在时返回 ANALYSIS_PLAN_NOT_FOUND。"""
        project_id, _, _ = _seed_dataset_ready_project(client)
        response = client.put(
            f"/api/projects/{project_id}/analysis/plan_missing",
            json={"cleaning_plan": "[]"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ANALYSIS_PLAN_NOT_FOUND"

    def test_rejects_updating_rejected_plan(self, client):
        """REJECTED 方案不可编辑。"""
        project_id, dataset_id, version_id = _seed_dataset_ready_project(client)
        from app.api.routers import analysis as analysis_router
        SessionLocal = analysis_router.SessionLocal
        db = SessionLocal()
        try:
            plan = AnalysisPlan(
                id="plan_rejected_api",
                project_id=project_id,
                dataset_id=dataset_id,
                dataset_version_id=version_id,
                cleaning_plan="[]",
                analysis_plan="[]",
                chart_plan="[]",
                status=AnalysisPlanStatus.REJECTED.value,
                candidate_source="LOCAL_RULE",
            )
            db.add(plan)
            db.commit()
        finally:
            db.close()

        response = client.put(
            f"/api/projects/{project_id}/analysis/plan_rejected_api",
            json={"cleaning_plan": '[{"new": true}]'},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "ANALYSIS_PLAN_NOT_EDITABLE"


# --- POST /analysis/{plan_id}/confirm ---


class TestConfirmAnalysisPlanApi:
    """确认分析方案 API 测试。"""

    def test_confirms_candidate_returns_200(self, client):
        """POST /confirm 确认 CANDIDATE 方案。"""
        project_id, dataset_id, version_id = _seed_dataset_ready_project(client)
        from app.api.routers import analysis as analysis_router
        plan_id = _seed_candidate_plan(
            analysis_router.SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_confirm_api",
        )

        response = client.post(
            f"/api/projects/{project_id}/analysis/{plan_id}/confirm"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "CONFIRMED"
        assert response.json()["confirmed_at"] is not None

    def test_returns_400_when_not_candidate(self, client):
        """非 CANDIDATE 方案确认时返回 ANALYSIS_PLAN_NOT_CONFIRMABLE。"""
        project_id, dataset_id, version_id = _seed_dataset_ready_project(client)
        from app.api.routers import analysis as analysis_router
        plan_id = _seed_confirmed_plan(
            analysis_router.SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_already_confirmed_api",
        )

        response = client.post(
            f"/api/projects/{project_id}/analysis/{plan_id}/confirm"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "ANALYSIS_PLAN_NOT_CONFIRMABLE"

    def test_returns_404_when_plan_missing(self, client):
        """方案不存在时返回 ANALYSIS_PLAN_NOT_FOUND。"""
        project_id, _, _ = _seed_dataset_ready_project(client)
        response = client.post(
            f"/api/projects/{project_id}/analysis/plan_missing/confirm"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ANALYSIS_PLAN_NOT_FOUND"


# --- POST /analysis/{plan_id}/reject ---


class TestRejectAnalysisPlanApi:
    """拒绝分析方案 API 测试。"""

    def test_rejects_candidate_returns_200(self, client):
        """POST /reject 拒绝 CANDIDATE 方案。"""
        project_id, dataset_id, version_id = _seed_dataset_ready_project(client)
        from app.api.routers import analysis as analysis_router
        plan_id = _seed_candidate_plan(
            analysis_router.SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_reject_api",
        )

        response = client.post(
            f"/api/projects/{project_id}/analysis/{plan_id}/reject"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "REJECTED"

    def test_returns_404_when_plan_missing(self, client):
        """方案不存在时返回 ANALYSIS_PLAN_NOT_FOUND。"""
        project_id, _, _ = _seed_dataset_ready_project(client)
        response = client.post(
            f"/api/projects/{project_id}/analysis/plan_missing/reject"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ANALYSIS_PLAN_NOT_FOUND"

    def test_returns_400_when_not_candidate(self, client):
        """非 CANDIDATE 方案拒绝时返回 ANALYSIS_PLAN_NOT_CONFIRMABLE。"""
        project_id, dataset_id, version_id = _seed_dataset_ready_project(client)
        from app.api.routers import analysis as analysis_router
        plan_id = _seed_confirmed_plan(
            analysis_router.SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_reject_conf_api",
        )

        response = client.post(
            f"/api/projects/{project_id}/analysis/{plan_id}/reject"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "ANALYSIS_PLAN_NOT_CONFIRMABLE"


# --- POST /analysis/complete ---


class TestCompleteAnalysisApi:
    """完成分析方案确认 API 测试。"""

    def test_completes_when_confirmed_plan_exists(self, client):
        """有 CONFIRMED 方案时完成分析确认。"""
        project_id, dataset_id, version_id = _seed_dataset_ready_project(client)
        from app.api.routers import analysis as analysis_router
        _seed_confirmed_plan(
            analysis_router.SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_complete_api",
        )

        response = client.post(
            f"/api/projects/{project_id}/analysis/complete"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ANALYSIS_CONFIRMED"

    def test_rejects_when_no_confirmed_plan(self, client):
        """无 CONFIRMED 方案时返回 PROJECT_NO_CONFIRMED_ANALYSIS_PLAN。"""
        project_id, dataset_id, version_id = _seed_dataset_ready_project(client)
        from app.api.routers import analysis as analysis_router
        _seed_candidate_plan(
            analysis_router.SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_only_cand_api",
        )

        response = client.post(
            f"/api/projects/{project_id}/analysis/complete"
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PROJECT_NO_CONFIRMED_ANALYSIS_PLAN"

    def test_returns_404_when_project_missing(self, client):
        """项目不存在时返回 PROJECT_NOT_FOUND。"""
        response = client.post(
            "/api/projects/proj_missing/analysis/complete"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


# --- STALE 传播端到端 ---


class TestStalePropagationFlow:
    """STALE 传播端到端测试。"""

    def test_reupload_dataset_propagates_stale_to_plans(self, client, monkeypatch):
        """重新上传数据集 → 关联方案变 STALE（端到端 API）。"""
        project_id, dataset_id, version_id = _seed_dataset_ready_project(client)
        from app.api.routers import analysis as analysis_router
        SessionLocal = analysis_router.SessionLocal
        # 先创建一个 CANDIDATE 方案
        plan_id = _seed_candidate_plan(
            SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_stale_flow",
        )

        # 重新上传（应触发 STALE）
        csv_bytes = b"name,age\nalice,30\nbob,25\n"
        client.post(
            f"/api/projects/{project_id}/datasets/{dataset_id}/reupload",
            files={"file": ("v2.csv", csv_bytes, "text/csv")},
        )

        # 验证方案状态
        db = SessionLocal()
        try:
            plan = db.query(AnalysisPlan).filter(AnalysisPlan.id == plan_id).first()
            assert plan.status == AnalysisPlanStatus.STALE.value
        finally:
            db.close()

    def test_delete_dataset_propagates_stale_to_plans(self, client, monkeypatch):
        """删除数据集 → 关联方案变 STALE（端到端 API）。"""
        project_id, dataset_id, version_id = _seed_dataset_ready_project(client)
        from app.api.routers import analysis as analysis_router
        SessionLocal = analysis_router.SessionLocal
        plan_id = _seed_candidate_plan(
            SessionLocal, project_id, dataset_id, version_id,
            plan_id="plan_del_stale_flow",
        )

        client.delete(
            f"/api/projects/{project_id}/datasets/{dataset_id}"
        )

        db = SessionLocal()
        try:
            plan = db.query(AnalysisPlan).filter(AnalysisPlan.id == plan_id).first()
            assert plan.status == AnalysisPlanStatus.STALE.value
        finally:
            db.close()
