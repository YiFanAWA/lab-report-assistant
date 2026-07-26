"""证据卡片流式生成 API 合同测试 (POST /sources/{source_id}/evidence/stream-generate)。

SPEC 0020：证据卡片生成流式化。

测试 SSE 端点：
- 返回 text/event-stream
- SSE 事件格式：chunk / done / error
- 完整流程：多 chunk + done
- 项目不存在：返回 404
- 来源不存在：返回 404
- 来源未解析：返回 error 事件
- 项目状态未满足：返回 error 事件
- 原同步端点零回归（POST /evidence/generate 仍可用）

使用默认 LocalRule provider（不支持 stream_draft，service 层降级为一次性 yield）。
"""

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.engine import Base
from app.main import app
from app.modules.projects.status import ProjectStatus


TEST_DB = "sqlite:///:memory:"


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

    from app.api.routers import evidence as evidence_router
    from app.api.routers import projects as project_router
    from app.infrastructure.database import engine as db_engine

    monkeypatch.setattr(project_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(evidence_router, "SessionLocal", TestingSessionLocal)
    # service 层的 stream_generate_evidence_cards 内部从 engine 模块导入 SessionLocal，
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


def _setup_project_ready_for_evidence(client, project_id: str) -> tuple[str, str]:
    """设置项目状态为 REQUIREMENT_CONFIRMED + 插入 PARSED 来源和 ParsedDocument。

    返回 (source_id, pd_id)。
    """
    TestingSessionLocal = client.testing_session_local
    db = TestingSessionLocal()
    try:
        from app.modules.projects.models import Project
        from app.modules.sources.models import Source, ParsedDocument
        from app.modules.sources.status import SourceKind, SourceStatus

        project = db.query(Project).filter(Project.id == project_id).first()
        project.status = ProjectStatus.REQUIREMENT_CONFIRMED.value

        source = Source(
            id="src_api_001",
            project_id=project_id,
            source_kind=SourceKind.URL.value,
            title="已解析来源",
            url="https://example.com/article.html",
            status=SourceStatus.PARSED.value,
            content_type="text/html",
            content_hash="hash_api_001",
            file_path="/tmp/raw.html",
        )
        db.add(source)
        pd = ParsedDocument(
            id="pd_api_001",
            source_id=source.id,
            project_id=project_id,
            title="测试文档",
            parsed_text=(
                "背景：本节介绍胃病数据的研究背景与意义，包含流行病学统计和疾病分类说明。\n"
                "方法：采用描述性统计方法和可视化技术分析数据，包括均值、标准差和分布检验。\n"
                "结果：分析显示关键变量之间存在显著相关，胃病发病率呈现上升趋势。"
            ),
            metadata_json='{"description": "测试"}',
        )
        db.add(pd)
        db.commit()
        return source.id, pd.id
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


class TestStreamGenerateEvidenceEndpoint:
    """SSE 流式生成证据卡片端点测试。"""

    def test_返回text_event_stream_content_type(self, client):
        """端点应返回 text/event-stream。"""
        project_id = _create_project(client)
        _setup_project_ready_for_evidence(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/sources/src_api_001/evidence/stream-generate",
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_完整流程多chunk加done事件(self, client):
        """完整流程应有多个 chunk 事件 + 1 个 done 事件。"""
        project_id = _create_project(client)
        _setup_project_ready_for_evidence(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/sources/src_api_001/evidence/stream-generate",
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)

        # 应有多个 chunk 事件
        chunk_events = [e for e in events if e["event"] == "chunk"]
        assert len(chunk_events) >= 1

        # 应有 1 个 done 事件
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1

        # done 事件 data 应包含 card_count 和 candidate_source
        done_data = json.loads(done_events[0]["data"])
        assert "card_count" in done_data
        assert "candidate_source" in done_data
        assert done_data["candidate_source"] == "LOCAL_RULE"

    def test_chunk拼接为有效JSON(self, client):
        """所有 chunk 拼接后应为有效的 JSON（含 cards 字段）。"""
        project_id = _create_project(client)
        _setup_project_ready_for_evidence(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/sources/src_api_001/evidence/stream-generate",
        )

        events = _parse_sse_events(response.text)
        chunk_events = [e for e in events if e["event"] == "chunk"]

        full_text = "".join(
            json.loads(e["data"])["text"] for e in chunk_events
        )
        parsed = json.loads(full_text)
        assert "cards" in parsed
        # LocalRule 应至少生成 1 张卡片
        assert len(parsed["cards"]) >= 1

    def test_done事件包含card_count字段(self, client):
        """done 事件应包含 card_count 字段（替代 outline_id）。"""
        project_id = _create_project(client)
        _setup_project_ready_for_evidence(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/sources/src_api_001/evidence/stream-generate",
        )

        events = _parse_sse_events(response.text)
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1

        done_data = json.loads(done_events[0]["data"])
        assert "card_count" in done_data
        assert isinstance(done_data["card_count"], int)
        assert done_data["card_count"] >= 1

    def test_done事件包含fallback_used字段(self, client):
        """done 事件应包含 fallback_used 字段。"""
        project_id = _create_project(client)
        _setup_project_ready_for_evidence(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/sources/src_api_001/evidence/stream-generate",
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
            "/api/projects/nonexistent_project/sources/src_xxx/evidence/stream-generate",
        )

        assert response.status_code == 404

    def test_来源不存在返回404(self, client):
        """来源不存在时应返回 404。"""
        project_id = _create_project(client)
        # 设置项目状态为 REQUIREMENT_CONFIRMED，但不创建来源
        TestingSessionLocal = client.testing_session_local
        db = TestingSessionLocal()
        try:
            from app.modules.projects.models import Project
            project = db.query(Project).filter(Project.id == project_id).first()
            project.status = ProjectStatus.REQUIREMENT_CONFIRMED.value
            db.commit()
        finally:
            db.close()

        response = client.post(
            f"/api/projects/{project_id}/sources/nonexistent_source/evidence/stream-generate",
        )

        assert response.status_code == 404

    def test_来源未解析返回error事件(self, client):
        """来源未解析（status != PARSED）应返回 error 事件。"""
        project_id = _create_project(client)
        # 插入一个 FETCHED 状态的来源（未解析）
        TestingSessionLocal = client.testing_session_local
        db = TestingSessionLocal()
        try:
            from app.modules.projects.models import Project
            from app.modules.sources.models import Source
            from app.modules.sources.status import SourceKind, SourceStatus

            project = db.query(Project).filter(Project.id == project_id).first()
            project.status = ProjectStatus.REQUIREMENT_CONFIRMED.value

            source = Source(
                id="src_unparsed_api",
                project_id=project_id,
                source_kind=SourceKind.URL.value,
                title="未解析来源",
                url="https://example.com/unparsed.html",
                status=SourceStatus.FETCHED.value,
                content_type="text/html",
                content_hash="hash_unparsed",
                file_path="/tmp/raw.html",
            )
            db.add(source)
            db.commit()
        finally:
            db.close()

        response = client.post(
            f"/api/projects/{project_id}/sources/src_unparsed_api/evidence/stream-generate",
        )

        # 应返回 200 + error 事件（预校验只检查项目/来源存在，状态检查在 service Phase 1）
        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1

        error_data = json.loads(error_events[0]["data"])
        assert error_data["error_code"] == "EVIDENCE_SOURCE_NOT_PARSED"

    def test_项目状态未满足返回error事件(self, client):
        """项目状态未达 REQUIREMENT_CONFIRMED 时应返回 error 事件。"""
        project_id = _create_project(client)
        # 不设置状态（默认 CREATED）+ 插入 PARSED 来源
        TestingSessionLocal = client.testing_session_local
        db = TestingSessionLocal()
        try:
            from app.modules.sources.models import Source, ParsedDocument
            from app.modules.sources.status import SourceKind, SourceStatus

            source = Source(
                id="src_status_test",
                project_id=project_id,
                source_kind=SourceKind.URL.value,
                title="已解析来源",
                url="https://example.com/article.html",
                status=SourceStatus.PARSED.value,
                content_type="text/html",
                content_hash="hash_status_test",
                file_path="/tmp/raw.html",
            )
            db.add(source)
            pd = ParsedDocument(
                id="pd_status_test",
                source_id=source.id,
                project_id=project_id,
                title="测试文档",
                parsed_text=(
                    "背景：本节介绍胃病数据的研究背景与意义。\n"
                    "方法：采用描述性统计方法分析数据。\n"
                    "结果：分析显示关键变量之间存在显著相关。"
                ),
                metadata_json='{"description": "测试"}',
            )
            db.add(pd)
            db.commit()
        finally:
            db.close()

        response = client.post(
            f"/api/projects/{project_id}/sources/src_status_test/evidence/stream-generate",
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert json.loads(error_events[0]["data"])["error_code"] == "PROJECT_REQUIREMENT_NOT_CONFIRMED"


class TestOriginalEndpointZeroRegression:
    """原同步端点零回归测试。"""

    def test_原generate端点仍可用(self, client):
        """POST /evidence/generate（Worker 异步）端点应不受影响。"""
        project_id = _create_project(client)
        _setup_project_ready_for_evidence(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/sources/src_api_001/evidence/generate",
        )

        assert response.status_code == 201
        data = response.json()
        assert "job_id" in data
        assert data["job_id"]
