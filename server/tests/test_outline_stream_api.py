"""大纲流式生成 API 合同测试 (POST /outline/stream-generate)。

SPEC 0019 大纲生成流式化。

测试 SSE 端点：
- 返回 text/event-stream
- SSE 事件格式：chunk / done / error
- 完整流程：多 chunk + done
- 项目不存在：返回 404
- 无成功执行记录：返回 error 事件
- 原同步端点零回归（POST /outline/generate 仍可用）

使用默认 LocalRule provider（不支持 stream_generate，service 层降级为一次性 yield）。
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
from app.modules.execution.models import CodeTask, ExecutionRun
from app.modules.execution.status import (
    CodeTaskStatus,
    ExecutionRunStatus,
)
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

    from app.api.routers import outlines as outline_router
    from app.api.routers import projects as project_router
    from app.infrastructure.database import engine as db_engine

    monkeypatch.setattr(project_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(outline_router, "SessionLocal", TestingSessionLocal)
    # service 层的 stream_generate_outline 内部从 engine 模块导入 SessionLocal，
    # 必须同时 patch engine.SessionLocal，否则 Phase 4 会用真实数据库
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


def _setup_project_ready_for_outline(client, project_id: str) -> str:
    """设置项目状态为 RESULT_CONFIRMED + 插入成功的执行记录。"""
    TestingSessionLocal = client.testing_session_local
    db = TestingSessionLocal()
    try:
        from app.modules.projects.models import Project
        project = db.query(Project).filter(Project.id == project_id).first()
        project.status = ProjectStatus.RESULT_CONFIRMED.value

        task = CodeTask(
            id="task_api_001",
            project_id=project_id,
            analysis_plan_id="plan_api_dummy",
            dataset_id="ds_api_dummy",
            dataset_version_id="ver_api_dummy",
            code="print('hello')",
            code_version=1,
            status=CodeTaskStatus.CONFIRMED.value,
            candidate_source="local_rule",
        )
        db.add(task)

        run = ExecutionRun(
            id="run_api_001",
            project_id=project_id,
            code_task_id=task.id,
            dataset_version_id="ver_api_dummy",
            code_version=1,
            status=ExecutionRunStatus.SUCCEEDED.value,
            stdout="执行成功，输出统计结果",
            stderr="",
            exit_code=0,
            started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            finished_at=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
            duration_seconds=1.0,
        )
        db.add(run)
        db.commit()
        return run.id
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


class TestStreamGenerateOutlineEndpoint:
    """SSE 流式生成大纲端点测试。"""

    def test_返回text_event_stream_content_type(self, client):
        """端点应返回 text/event-stream。"""
        project_id = _create_project(client)
        _setup_project_ready_for_outline(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/outline/stream-generate",
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_完整流程多chunk加done事件(self, client):
        """完整流程应有多个 chunk 事件 + 1 个 done 事件。"""
        project_id = _create_project(client)
        _setup_project_ready_for_outline(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/outline/stream-generate",
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)

        # 应有多个 chunk 事件
        chunk_events = [e for e in events if e["event"] == "chunk"]
        assert len(chunk_events) >= 1

        # 应有 1 个 done 事件
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1

        # done 事件 data 应包含 outline_id 和 candidate_source
        done_data = json.loads(done_events[0]["data"])
        assert "outline_id" in done_data
        assert "candidate_source" in done_data
        assert done_data["candidate_source"] == "local_rule"

    def test_chunk拼接为有效JSON(self, client):
        """所有 chunk 拼接后应为有效的 JSON。"""
        project_id = _create_project(client)
        _setup_project_ready_for_outline(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/outline/stream-generate",
        )

        events = _parse_sse_events(response.text)
        chunk_events = [e for e in events if e["event"] == "chunk"]

        full_text = "".join(
            json.loads(e["data"])["text"] for e in chunk_events
        )
        parsed = json.loads(full_text)
        assert "sections" in parsed
        assert len(parsed["sections"]) == 6

    def test_done事件包含fallback_used字段(self, client):
        """done 事件应包含 fallback_used 字段。"""
        project_id = _create_project(client)
        _setup_project_ready_for_outline(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/outline/stream-generate",
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
            "/api/projects/nonexistent_project/outline/stream-generate",
        )

        assert response.status_code == 404

    def test_无成功执行记录返回error事件(self, client):
        """无成功执行记录时应返回 error 事件（而非 500）。"""
        project_id = _create_project(client)
        # 设置状态为 RESULT_CONFIRMED 但不插入执行记录
        TestingSessionLocal = client.testing_session_local
        db = TestingSessionLocal()
        try:
            from app.modules.projects.models import Project
            project = db.query(Project).filter(Project.id == project_id).first()
            project.status = ProjectStatus.RESULT_CONFIRMED.value
            db.commit()
        finally:
            db.close()

        response = client.post(
            f"/api/projects/{project_id}/outline/stream-generate",
        )

        # 应返回 200 + error 事件（预校验只检查项目存在，执行记录检查在 service Phase 1）
        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1

        error_data = json.loads(error_events[0]["data"])
        assert error_data["error_code"] == "OUTLINE_NOT_GENERATABLE"

    def test_项目状态未满足返回error事件(self, client):
        """项目状态未达 RESULT_CONFIRMED 时应返回 error 事件。"""
        project_id = _create_project(client)
        # 不设置状态（默认 CREATED），但插入执行记录
        _setup_project_ready_for_outline(client, project_id)
        # 覆盖状态回 CREATED
        TestingSessionLocal = client.testing_session_local
        db = TestingSessionLocal()
        try:
            from app.modules.projects.models import Project
            project = db.query(Project).filter(Project.id == project_id).first()
            project.status = ProjectStatus.DRAFT.value
            db.commit()
        finally:
            db.close()

        response = client.post(
            f"/api/projects/{project_id}/outline/stream-generate",
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert json.loads(error_events[0]["data"])["error_code"] == "OUTLINE_NOT_GENERATABLE"


class TestOriginalEndpointZeroRegression:
    """原同步端点零回归测试。"""

    def test_原generate端点仍可用(self, client):
        """POST /outline/generate（Worker 异步）端点应不受影响。"""
        project_id = _create_project(client)
        _setup_project_ready_for_outline(client, project_id)

        response = client.post(
            f"/api/projects/{project_id}/outline/generate",
        )

        assert response.status_code == 201
        data = response.json()
        assert "job_id" in data
        assert data["job_id"]
