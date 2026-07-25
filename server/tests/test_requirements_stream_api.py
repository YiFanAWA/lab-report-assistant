"""实验要求流式生成 API 合同测试 (POST /plans/stream-generate)。

测试 SSE 端点：
- 返回 text/event-stream
- SSE 事件格式：chunk / done / error
- 完整流程：多 chunk + done
- source_id 无效：返回 AppError
- 项目不存在：返回 404
- 原同步端点零回归（POST /plans/generate 仍可用）

使用默认 LocalRule provider（不支持 stream_draft，service 层降级为一次性 yield）。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.engine import Base
from app.main import app


TEST_DB = "sqlite:///:memory:"


@pytest.fixture
def client(monkeypatch, tmp_path):
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
    from app.infrastructure.database import engine as db_engine

    monkeypatch.setattr(project_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(requirement_router, "SessionLocal", TestingSessionLocal)
    # service 层的 stream_generate_plan 内部从 engine 模块导入 SessionLocal，
    # 必须同时 patch engine.SessionLocal，否则 Phase 4 会用真实数据库
    monkeypatch.setattr(db_engine, "SessionLocal", TestingSessionLocal)

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)


def _create_project(client: TestClient) -> str:
    response = client.post("/api/projects", json={"name": "胃病数据分析", "topic": "胃病数据分析"})
    assert response.status_code == 200
    return response.json()["id"]


def _create_source(client: TestClient, project_id: str) -> str:
    response = client.post(
        f"/api/projects/{project_id}/requirements/sources/text",
        json={"title": "老师要求", "text": "完成胃病数据清洗、统计分析和可视化"},
    )
    assert response.status_code == 200
    return response.json()["id"]


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


class TestStreamGenerateEndpoint:
    """SSE 流式生成端点测试。"""

    def test_返回text_event_stream_content_type(self, client):
        project_id = _create_project(client)
        source_id = _create_source(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/requirements/plans/stream-generate",
            json={"source_id": source_id},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_完整流程多chunk加done事件(self, client):
        project_id = _create_project(client)
        source_id = _create_source(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/requirements/plans/stream-generate",
            json={"source_id": source_id},
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
        import json
        done_data = json.loads(done_events[0]["data"])
        assert "plan_id" in done_data
        assert "candidate_source" in done_data
        assert done_data["candidate_source"] == "LOCAL_RULE"

    def test_chunk事件data包含text字段(self, client):
        project_id = _create_project(client)
        source_id = _create_source(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/requirements/plans/stream-generate",
            json={"source_id": source_id},
        )

        events = _parse_sse_events(response.text)
        chunk_events = [e for e in events if e["event"] == "chunk"]

        import json
        for evt in chunk_events:
            data = json.loads(evt["data"])
            assert "text" in data
            assert isinstance(data["text"], str)

    def test_done事件后任务单已保存(self, client):
        project_id = _create_project(client)
        source_id = _create_source(client, project_id)

        # 流式生成
        response = client.post(
            f"/api/projects/{project_id}/requirements/plans/stream-generate",
            json={"source_id": source_id},
        )
        events = _parse_sse_events(response.text)
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1

        import json
        done_data = json.loads(done_events[0]["data"])
        plan_id = done_data["plan_id"]

        # 通过 GET /plan 验证任务单已保存
        plan_resp = client.get(f"/api/projects/{project_id}/requirements/plan")
        assert plan_resp.status_code == 200
        plan = plan_resp.json()
        assert plan["id"] == plan_id
        assert plan["status"] == "CANDIDATE"
        assert plan["candidate_source"] == "LOCAL_RULE"

    def test_流式生成后project状态推进(self, client):
        project_id = _create_project(client)
        source_id = _create_source(client, project_id)

        client.post(
            f"/api/projects/{project_id}/requirements/plans/stream-generate",
            json={"source_id": source_id},
        )

        project_resp = client.get(f"/api/projects/{project_id}")
        assert project_resp.json()["status"] == "REQUIREMENT_PARSED"


class TestStreamGenerateEndpointErrors:
    """SSE 端点错误响应测试。"""

    def test_source_id无效返回AppError(self, client):
        project_id = _create_project(client)

        response = client.post(
            f"/api/projects/{project_id}/requirements/plans/stream-generate",
            json={"source_id": "src_missing"},
        )

        # source 不存在应返回结构化错误（REQUIREMENT_SOURCE_NOT_FOUND 映射为 404）
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "REQUIREMENT_SOURCE_NOT_FOUND"

    def test_项目不存在返回404(self, client):
        response = client.post(
            "/api/projects/proj_missing/requirements/plans/stream-generate",
            json={"source_id": "src_any"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "PROJECT_NOT_FOUND"

    def test_请求体无效返回AppError(self, client):
        project_id = _create_project(client)

        response = client.post(
            f"/api/projects/{project_id}/requirements/plans/stream-generate",
            json={},  # 缺少 source_id
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data


class TestStreamGenerateEndpointSSEFormat:
    """SSE 文本格式规范测试。"""

    def test_每个事件以双换行分隔(self, client):
        project_id = _create_project(client)
        source_id = _create_source(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/requirements/plans/stream-generate",
            json={"source_id": source_id},
        )

        text = response.text
        # SSE 规范：事件块以 \n\n 分隔
        assert "\n\n" in text
        # 每个事件块应包含 event: 和 data: 行
        for block in text.split("\n\n"):
            if not block.strip():
                continue
            assert "event:" in block
            assert "data:" in block

    def test_响应头包含no_cache(self, client):
        project_id = _create_project(client)
        source_id = _create_source(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/requirements/plans/stream-generate",
            json={"source_id": source_id},
        )

        cache_control = response.headers.get("cache-control", "")
        assert "no-cache" in cache_control


class TestSyncEndpointZeroRegression:
    """原同步端点零回归测试。"""

    def test_同步端点仍可用(self, client):
        """POST /plans/generate 同步端点应保持原有行为不变。"""
        project_id = _create_project(client)
        source_id = _create_source(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/requirements/plans/generate",
            json={"source_id": source_id},
        )

        assert response.status_code == 200
        plan = response.json()
        assert plan["status"] == "CANDIDATE"
        assert plan["candidate_source"] == "LOCAL_RULE"
