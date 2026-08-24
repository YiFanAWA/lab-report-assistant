"""交付物审阅 API 合同测试。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.engine import Base
from app.main import app


@pytest.fixture
def client(monkeypatch, tmp_path):
    """使用独立内存数据库验证 HTTP 映射。"""
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    from app.api.routers import deliverables as deliverables_router
    from app.api.routers import outlines as outlines_router
    from app.api.routers import projects as projects_router

    monkeypatch.setattr(deliverables_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(outlines_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(projects_router, "SessionLocal", TestingSessionLocal)

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)


def test_delivery_review_api_returns_structured_projection(client):
    created = client.post(
        "/api/projects",
        json={"name": "交付审阅 API", "topic": "胃病数据分析"},
    )
    assert created.status_code == 200
    project_id = created.json()["id"]

    response = client.get(f"/api/projects/{project_id}/delivery-review")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == project_id
    assert payload["review_status"] == "BLOCKED"
    assert isinstance(payload["deliverables"], list)
    assert isinstance(payload["content_quality"], list)
    assert isinstance(payload["boundary_checks"], list)
    assert isinstance(payload["recommended_downloads"], list)
    assert set(("traceability", "quality_gates", "available_actions")).issubset(payload)
    assert any(
        gate["code"] == "VISUAL_INSPECTION" and gate["status"] == "NOT_RUN"
        for gate in payload["quality_gates"]
    )
    assert payload["available_actions"]["can_complete"] is False
