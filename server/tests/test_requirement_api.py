"""实验要求 API 合同测试。"""

from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.engine import Base
from app.main import app
from app.modules.projects.models import Project  # noqa: F401
from app.modules.requirements.models import RequirementSource, RequirementPlan, ChangeRecord  # noqa: F401


TEST_DB = "sqlite:///:memory:"


def _docx_bytes(text: str) -> bytes:
    doc = Document()
    if text:
        doc.add_paragraph(text)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


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

    monkeypatch.setattr(project_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(requirement_router, "SessionLocal", TestingSessionLocal)

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)


def _create_project(client: TestClient) -> str:
    response = client.post("/api/projects", json={"name": "胃病数据分析", "topic": "胃病数据分析"})
    assert response.status_code == 200
    return response.json()["id"]


def test_text_source_returns_structured_error_for_empty_text(client):
    project_id = _create_project(client)
    response = client.post(
        f"/api/projects/{project_id}/requirements/sources/text",
        json={"title": "老师要求", "text": ""},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REQUIREMENT_TEXT_REQUIRED"


def test_text_source_rejects_missing_project(client):
    response = client.post(
        "/api/projects/proj_missing/requirements/sources/text",
        json={"title": "老师要求", "text": "请完成数据分析"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


def test_requirement_api_happy_path_updates_and_confirms_plan(client):
    project_id = _create_project(client)
    source_response = client.post(
        f"/api/projects/{project_id}/requirements/sources/text",
        json={"title": "老师要求", "text": "完整复刻论文全部实验，生成 Word 报告和 PPT"},
    )
    assert source_response.status_code == 200
    source_id = source_response.json()["id"]

    plan_response = client.post(
        f"/api/projects/{project_id}/requirements/plans/generate",
        json={"source_id": source_id},
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["status"] == "CANDIDATE"
    assert plan["candidate_source"] == "LOCAL_RULE"
    assert plan["payload"]["replication_level"]["level"] == "L3"
    assert plan["payload"]["replication_level"]["supported_in_v1"] is False

    project_after_generate = client.get(f"/api/projects/{project_id}")
    assert project_after_generate.json()["status"] == "REQUIREMENT_PARSED"

    edited_payload = plan["payload"]
    edited_payload["topic"] = "胃病数据分析任务单"
    update_response = client.put(
        f"/api/projects/{project_id}/requirements/plans/{plan['id']}",
        json={"payload": edited_payload},
    )
    assert update_response.status_code == 200
    assert update_response.json()["payload"]["topic"] == "胃病数据分析任务单"

    confirm_response = client.post(
        f"/api/projects/{project_id}/requirements/plans/{plan['id']}/confirm",
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "CONFIRMED"

    project_after_confirm = client.get(f"/api/projects/{project_id}")
    assert project_after_confirm.json()["status"] == "REQUIREMENT_CONFIRMED"


def test_docx_upload_saves_source_and_sanitizes_filename(client):
    project_id = _create_project(client)
    response = client.post(
        f"/api/projects/{project_id}/requirements/sources/docx",
        data={"title": "Word 要求"},
        files={
            "file": (
                "../..\\evil:name?.docx",
                _docx_bytes("请完成胃病数据清洗、统计分析和可视化。"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "DOCX_FILE"
    assert "胃病数据清洗" in data["original_text"]
    saved_name = Path(data["original_file_path"]).name
    assert ".." not in saved_name
    assert ":" not in saved_name
    assert "?" not in saved_name


def test_docx_upload_rejects_empty_docx_text(client):
    project_id = _create_project(client)
    response = client.post(
        f"/api/projects/{project_id}/requirements/sources/docx",
        data={"title": "空 Word"},
        files={
            "file": (
                "empty.docx",
                _docx_bytes(""),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REQUIREMENT_DOCX_TEXT_EMPTY"


def test_docx_upload_rejects_unsupported_file_with_structured_error(client):
    project_id = _create_project(client)
    response = client.post(
        f"/api/projects/{project_id}/requirements/sources/docx",
        files={"file": ("requirement.txt", b"text", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REQUIREMENT_FILE_UNSUPPORTED"
