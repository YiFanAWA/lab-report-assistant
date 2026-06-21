"""来源与证据 API 合同、项目隔离和状态推进测试。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.engine import Base
from app.main import app
from app.modules.projects.models import Project  # noqa: F401
from app.modules.requirements.models import ChangeRecord, RequirementPlan, RequirementSource  # noqa: F401
from app.modules.sources.models import EvidenceCard, ParsedDocument, SourceRecord  # noqa: F401


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine)

    from app.api.routers import projects, requirements, sources

    monkeypatch.setattr(projects, "SessionLocal", testing_session)
    monkeypatch.setattr(requirements, "SessionLocal", testing_session)
    monkeypatch.setattr(sources, "SessionLocal", testing_session)

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)


def create_project(client: TestClient, name: str = "胃病数据分析") -> str:
    response = client.post("/api/projects", json={"name": name, "topic": name})
    assert response.status_code == 200
    return response.json()["id"]


def create_confirmed_project(client: TestClient, name: str = "胃病数据分析") -> str:
    project_id = create_project(client, name)
    source = client.post(
        f"/api/projects/{project_id}/requirements/sources/text",
        json={"title": "老师要求", "text": "完成公开资料分析"},
    ).json()
    plan = client.post(
        f"/api/projects/{project_id}/requirements/plans/generate",
        json={"source_id": source["id"]},
    ).json()
    response = client.post(
        f"/api/projects/{project_id}/requirements/plans/{plan['id']}/confirm"
    )
    assert response.status_code == 200
    return project_id


@pytest.fixture
def confirmed_project(client):
    return create_confirmed_project(client)


@pytest.fixture
def prepared_source(client, confirmed_project):
    upload = client.post(
        f"/api/projects/{confirmed_project}/sources/files",
        files={
            "file": (
                "source.txt",
                "背景资料。\n\n方法采用公开数据分析。".encode("utf-8"),
                "text/plain",
            )
        },
    )
    assert upload.status_code == 200
    source = upload.json()
    parsed = client.post(
        f"/api/projects/{confirmed_project}/sources/{source['id']}/parse"
    )
    assert parsed.status_code == 200
    return confirmed_project, source


@pytest.fixture
def candidate_card(client, prepared_source):
    project_id, source = prepared_source
    response = client.post(
        f"/api/projects/{project_id}/sources/{source['id']}/evidence/generate"
    )
    assert response.status_code == 200
    return project_id, response.json()["items"][0]


def test_url_requires_confirmed_plan(client):
    project_id = create_project(client)
    response = client.post(
        f"/api/projects/{project_id}/sources/urls",
        json={"url": "https://example.com/public", "title": "公开资料"},
    )
    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "REQUIREMENT_PLAN_NOT_CONFIRMED",
            "message": "请先确认实验任务单",
            "field": None,
        }
    }


def test_parsed_document_cannot_cross_project_boundary(client, prepared_source):
    _, source = prepared_source
    other_project = create_confirmed_project(client, name="另一个项目")
    response = client.get(
        f"/api/projects/{other_project}/sources/{source['id']}/parsed-document"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SOURCE_RECORD_NOT_FOUND"


def test_invalid_evidence_type_is_structured(client, candidate_card):
    project_id, card = candidate_card
    response = client.put(
        f"/api/projects/{project_id}/evidence/{card['id']}",
        json={"evidence_type": "NOT_REAL"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_upload_rejects_content_over_limit_without_persisting(
    client, confirmed_project
):
    response = client.post(
        f"/api/projects/{confirmed_project}/sources/files",
        files={
            "file": (
                "large.txt",
                b"x" * (20 * 1024 * 1024 + 1),
                "text/plain",
            )
        },
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "SOURCE_FILE_TOO_LARGE"
    listed = client.get(f"/api/projects/{confirmed_project}/sources")
    assert listed.json()["items"] == []


def test_source_evidence_happy_path_persists_and_advances(client, candidate_card):
    project_id, card = candidate_card
    response = client.post(
        f"/api/projects/{project_id}/evidence/{card['id']}/confirm"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "CONFIRMED"
    assert client.get(f"/api/projects/{project_id}").json()["status"] == "EVIDENCE_CONFIRMED"
    assert client.get(f"/api/projects/{project_id}/sources").json()["items"]
    evidence = client.get(f"/api/projects/{project_id}/evidence").json()["items"]
    assert evidence[0]["status"] == "CONFIRMED"
