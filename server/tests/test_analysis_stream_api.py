"""分析方案流式生成 API 合同测试 (POST /datasets/{dataset_id}/analysis/stream-generate)。

SPEC 0021：分析方案生成流式化。

测试 SSE 端点：
- 返回 text/event-stream
- SSE 事件格式：chunk / done / error
- 完整流程：多 chunk + done
- 项目不存在：返回 404
- 数据集不存在：返回 404
- 数据集未解析：返回 error 事件
- 项目状态未满足：返回 error 事件
- 原同步端点零回归（POST /analysis/generate 仍可用）

使用默认 LocalRule provider（不支持 stream_generate，service 层降级为一次性 yield）。
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.engine import Base
from app.main import app
from app.modules.projects.status import ProjectStatus


TEST_DB = "sqlite:///:memory:"


def _make_profile_json() -> str:
    """构造有效的 DatasetProfile JSON（存入 DatasetVersion.profile_json）。"""
    return json.dumps({
        "row_count": 100,
        "column_count": 3,
        "complete_row_count": 85,
        "incomplete_row_count": 15,
        "duplicate_row_count": 2,
        "quality_score": 85.0,
        "field_profiles": [
            {
                "name": "age",
                "inferred_type": "int",
                "non_null_count": 95,
                "null_count": 5,
                "null_rate": 0.05,
                "unique_count": 63,
                "sample_values": ["25", "30", "45"],
                "min_value": 18.0,
                "max_value": 80.0,
                "mean_value": 45.0,
            },
            {
                "name": "gender",
                "inferred_type": "string",
                "non_null_count": 98,
                "null_count": 2,
                "null_rate": 0.02,
                "unique_count": 2,
                "sample_values": ["男", "女"],
            },
        ],
    }, ensure_ascii=False)


@pytest.fixture
def client(monkeypatch, tmp_path):
    """TestClient + 内存 SQLite，patch 所有 SessionLocal 引用。"""
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    engine = create_engine(
        TEST_DB,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    from app.api.routers import analysis as analysis_router
    from app.api.routers import projects as project_router
    from app.infrastructure.database import engine as db_engine

    monkeypatch.setattr(project_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(analysis_router, "SessionLocal", TestingSessionLocal)
    # service 层的 stream_generate_analysis_plan 内部从 engine 模块导入 SessionLocal，
    # 必须同时 patch engine.SessionLocal，否则 Phase 3 会用真实数据库
    monkeypatch.setattr(db_engine, "SessionLocal", TestingSessionLocal)

    with TestClient(app) as test_client:
        test_client.testing_session_local = TestingSessionLocal
        yield test_client

    Base.metadata.drop_all(bind=engine)


def _create_project(client) -> str:
    """通过 API 创建项目，返回 project_id。"""
    response = client.post(
        "/api/projects",
        json={"name": "胃病数据分析", "topic": "胃病数据分析"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _setup_project_ready_for_analysis(client, project_id: str) -> str:
    """设置项目状态为 DATASET_READY + 插入 READY 数据集和 PARSED 版本。

    返回 dataset_id。
    """
    TestingSessionLocal = client.testing_session_local
    db = TestingSessionLocal()
    try:
        from app.modules.projects.models import Project
        from app.modules.datasets.models import Dataset, DatasetVersion
        from app.modules.datasets.status import DatasetStatus, DatasetVersionStatus

        project = db.query(Project).filter(Project.id == project_id).first()
        project.status = ProjectStatus.DATASET_READY.value

        dataset = Dataset(
            id="ds_api_001",
            project_id=project_id,
            dataset_kind="FILE",
            title="测试数据集",
            status=DatasetStatus.READY.value,
        )
        db.add(dataset)

        version = DatasetVersion(
            id="dv_api_001",
            dataset_id=dataset.id,
            project_id=project_id,
            version=1,
            status=DatasetVersionStatus.PARSED.value,
            file_path="/tmp/test.csv",
            file_size_bytes=1024,
            row_count=100,
            column_count=3,
            profile_json=_make_profile_json(),
        )
        db.add(version)
        db.commit()
        return dataset.id
    finally:
        db.close()


def _parse_sse_events(text: str) -> list[dict]:
    """解析 SSE 文本为事件列表。

    返回 [{"event": "chunk", "data": "..."}, ...]
    """
    events = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event_name = "message"
        data = ""
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
        if data:
            events.append({"event": event_name, "data": data})
    return events


class TestStreamGenerateAnalysisPlanEndpoint:
    """SSE 流式生成分析方案端点测试。"""

    def test_返回text_event_stream_content_type(self, client):
        """端点应返回 text/event-stream。"""
        project_id = _create_project(client)
        dataset_id = _setup_project_ready_for_analysis(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/datasets/{dataset_id}/analysis/stream-generate",
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_完整流程多chunk加done事件(self, client):
        """完整流程应有多个 chunk 事件 + 1 个 done 事件。"""
        project_id = _create_project(client)
        dataset_id = _setup_project_ready_for_analysis(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/datasets/{dataset_id}/analysis/stream-generate",
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)

        # 应有多个 chunk 事件
        chunk_events = [e for e in events if e["event"] == "chunk"]
        assert len(chunk_events) >= 1

        # 应有 1 个 done 事件
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1

        # done 事件 data 应包含 plan_id 和 candidate_source
        done_data = json.loads(done_events[0]["data"])
        assert "plan_id" in done_data
        assert "candidate_source" in done_data
        assert done_data["candidate_source"] == "LOCAL_RULE"

    def test_chunk拼接为有效JSON(self, client):
        """所有 chunk 拼接后应为有效的 JSON（含 cleaning/analysis/chart plan）。"""
        project_id = _create_project(client)
        dataset_id = _setup_project_ready_for_analysis(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/datasets/{dataset_id}/analysis/stream-generate",
        )

        events = _parse_sse_events(response.text)
        chunk_events = [e for e in events if e["event"] == "chunk"]

        full_text = "".join(
            json.loads(e["data"])["text"] for e in chunk_events
        )
        parsed = json.loads(full_text)
        assert "cleaning_plan" in parsed
        assert "analysis_plan" in parsed
        assert "chart_plan" in parsed

    def test_done事件包含plan_id字段(self, client):
        """done 事件应包含 plan_id 字段。"""
        project_id = _create_project(client)
        dataset_id = _setup_project_ready_for_analysis(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/datasets/{dataset_id}/analysis/stream-generate",
        )

        events = _parse_sse_events(response.text)
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1

        done_data = json.loads(done_events[0]["data"])
        assert "plan_id" in done_data
        assert isinstance(done_data["plan_id"], str)
        assert done_data["plan_id"]

    def test_done事件包含fallback_used字段(self, client):
        """done 事件应包含 fallback_used 字段。"""
        project_id = _create_project(client)
        dataset_id = _setup_project_ready_for_analysis(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/datasets/{dataset_id}/analysis/stream-generate",
        )

        events = _parse_sse_events(response.text)
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1

        done_data = json.loads(done_events[0]["data"])
        assert "fallback_used" in done_data
        assert done_data["fallback_used"] is False

    def test_项目不存在返回404(self, client):
        """项目不存在时应返回 404。"""
        response = client.post(
            "/api/projects/nonexistent_project/datasets/ds_xxx/analysis/stream-generate",
        )

        assert response.status_code == 404

    def test_数据集不存在返回404(self, client):
        """数据集不存在时应返回 404。"""
        project_id = _create_project(client)
        # 设置项目状态为 DATASET_READY，但不创建数据集
        TestingSessionLocal = client.testing_session_local
        db = TestingSessionLocal()
        try:
            from app.modules.projects.models import Project
            project = db.query(Project).filter(Project.id == project_id).first()
            project.status = ProjectStatus.DATASET_READY.value
            db.commit()
        finally:
            db.close()

        response = client.post(
            f"/api/projects/{project_id}/datasets/nonexistent_dataset/analysis/stream-generate",
        )

        assert response.status_code == 404

    def test_数据集未解析返回error事件(self, client):
        """数据集状态不是 READY 应返回 error 事件。"""
        project_id = _create_project(client)
        # 插入一个 PENDING 状态的数据集
        TestingSessionLocal = client.testing_session_local
        db = TestingSessionLocal()
        try:
            from app.modules.projects.models import Project
            from app.modules.datasets.models import Dataset
            from app.modules.datasets.status import DatasetStatus

            project = db.query(Project).filter(Project.id == project_id).first()
            project.status = ProjectStatus.DATASET_READY.value

            dataset = Dataset(
                id="ds_unparsed_api",
                project_id=project_id,
                dataset_kind="FILE",
                title="未解析数据集",
                status=DatasetStatus.PENDING.value,
            )
            db.add(dataset)
            db.commit()
        finally:
            db.close()

        response = client.post(
            f"/api/projects/{project_id}/datasets/ds_unparsed_api/analysis/stream-generate",
        )

        # 应返回 200 + error 事件（预校验只检查项目/数据集存在，状态检查在 service Phase 1）
        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1

        error_data = json.loads(error_events[0]["data"])
        assert error_data["error_code"] == "DATASET_NOT_PARSED"

    def test_项目状态未满足返回error事件(self, client):
        """项目状态未达 DATASET_READY 时应返回 error 事件。"""
        project_id = _create_project(client)
        # 不设置状态（默认 CREATED）+ 插入 READY 数据集
        TestingSessionLocal = client.testing_session_local
        db = TestingSessionLocal()
        try:
            from app.modules.datasets.models import Dataset, DatasetVersion
            from app.modules.datasets.status import DatasetStatus, DatasetVersionStatus

            dataset = Dataset(
                id="ds_status_test",
                project_id=project_id,
                dataset_kind="FILE",
                title="测试数据集",
                status=DatasetStatus.READY.value,
            )
            db.add(dataset)
            version = DatasetVersion(
                id="dv_status_test",
                dataset_id=dataset.id,
                project_id=project_id,
                version=1,
                status=DatasetVersionStatus.PARSED.value,
                file_path="/tmp/test.csv",
                file_size_bytes=1024,
                row_count=100,
                column_count=3,
                profile_json=_make_profile_json(),
            )
            db.add(version)
            db.commit()
        finally:
            db.close()

        response = client.post(
            f"/api/projects/{project_id}/datasets/ds_status_test/analysis/stream-generate",
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert json.loads(error_events[0]["data"])["error_code"] == "PROJECT_EVIDENCE_NOT_CONFIRMED"


class TestOriginalEndpointZeroRegression:
    """原同步端点零回归测试。"""

    def test_原generate端点仍可用(self, client):
        """POST /analysis/generate（Worker 异步）端点应不受影响。"""
        project_id = _create_project(client)
        dataset_id = _setup_project_ready_for_analysis(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/datasets/{dataset_id}/analysis/generate",
        )

        assert response.status_code == 201
        data = response.json()
        assert "job_id" in data
        assert data["job_id"]
