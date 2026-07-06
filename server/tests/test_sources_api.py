"""来源 API 端点测试。

使用 TestClient + monkeypatch SessionLocal，覆盖 POST /sources/url、
POST /sources/pdf、GET /sources、GET /sources/{id}、DELETE /sources/{id}、
POST /sources/complete 的成功与失败路径。
"""

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
from app.modules.sources.models import Source, ParsedDocument, EvidenceCard  # noqa: F401
from app.modules.jobs.models import BackgroundJob  # noqa: F401


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

    monkeypatch.setattr(project_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(requirement_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(sources_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(evidence_router, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(jobs_router, "SessionLocal", TestingSessionLocal)

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


def _confirm_requirements(client: TestClient, project_id: str) -> None:
    """走完整需求流程，使项目进入 REQUIREMENT_CONFIRMED 状态。"""
    source_response = client.post(
        f"/api/projects/{project_id}/requirements/sources/text",
        json={"title": "需求", "text": "完成数据清洗、统计分析和可视化"},
    )
    assert source_response.status_code == 200
    source_id = source_response.json()["id"]

    plan_response = client.post(
        f"/api/projects/{project_id}/requirements/plans/generate",
        json={"source_id": source_id},
    )
    assert plan_response.status_code == 200
    plan_id = plan_response.json()["id"]

    confirm_response = client.post(
        f"/api/projects/{project_id}/requirements/plans/{plan_id}/confirm"
    )
    assert confirm_response.status_code == 200


def _create_confirmed_project(client: TestClient) -> str:
    """创建并返回 REQUIREMENT_CONFIRMED 状态的项目 ID。"""
    project_id = _create_project(client)
    _confirm_requirements(client, project_id)
    return project_id


# --- POST /sources/url ---


class TestCreateUrlSourceApi:
    """登记 URL 来源 API 测试。"""

    def test_creates_url_source_returns_201(self, client):
        """成功登记公开 URL，返回 201 和 SourceResponse。"""
        project_id = _create_confirmed_project(client)
        response = client.post(
            f"/api/projects/{project_id}/sources/url",
            json={"url": "https://example.com/article.html", "title": "示例文章"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_kind"] == "URL"
        assert data["status"] == "PENDING"
        assert data["url"] == "https://example.com/article.html"
        assert data["title"] == "示例文章"
        assert data["job_id"]  # 返回 job_id

    def test_rejects_non_public_url(self, client):
        """非公开 URL 返回 SOURCE_URL_NOT_PUBLIC（400）。"""
        project_id = _create_confirmed_project(client)
        response = client.post(
            f"/api/projects/{project_id}/sources/url",
            json={"url": "http://localhost:8080/secret"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "SOURCE_URL_NOT_PUBLIC"

    def test_rejects_unsupported_scheme(self, client):
        """非 http/https 协议返回 SOURCE_URL_SCHEME_UNSUPPORTED（400）。"""
        project_id = _create_confirmed_project(client)
        response = client.post(
            f"/api/projects/{project_id}/sources/url",
            json={"url": "file:///etc/passwd"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "SOURCE_URL_SCHEME_UNSUPPORTED"

    def test_rejects_when_project_not_confirmed(self, client):
        """项目状态不足时返回 PROJECT_REQUIREMENT_NOT_CONFIRMED（400）。"""
        project_id = _create_project(client)
        response = client.post(
            f"/api/projects/{project_id}/sources/url",
            json={"url": "https://example.com/article.html"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PROJECT_REQUIREMENT_NOT_CONFIRMED"

    def test_returns_404_when_project_missing(self, client):
        """项目不存在时返回 PROJECT_NOT_FOUND（404）。"""
        response = client.post(
            "/api/projects/proj_missing/sources/url",
            json={"url": "https://example.com/article.html"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


# --- POST /sources/pdf ---


class TestCreatePdfSourceApi:
    """上传 PDF 来源 API 测试。"""

    def test_uploads_pdf_returns_201(self, client):
        """成功上传 PDF，返回 201，文件保存到受控工作区。"""
        project_id = _create_confirmed_project(client)
        pdf_bytes = b"%PDF-1.4\nfake pdf content for testing\n%%EOF"
        response = client.post(
            f"/api/projects/{project_id}/sources/pdf",
            data={"title": "研究论文"},
            files={
                "file": (
                    "paper.pdf",
                    pdf_bytes,
                    "application/pdf",
                )
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_kind"] == "FILE"
        assert data["status"] == "PENDING"
        assert data["title"] == "研究论文"
        assert data["file_path"] is not None
        assert data["job_id"]

    def test_rejects_empty_pdf(self, client):
        """空 PDF 返回 SOURCE_FILE_EMPTY（400）。"""
        project_id = _create_confirmed_project(client)
        response = client.post(
            f"/api/projects/{project_id}/sources/pdf",
            data={"title": "空"},
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "SOURCE_FILE_EMPTY"

    def test_rejects_non_pdf_extension(self, client):
        """非 PDF 扩展名返回 SOURCE_FILE_UNSUPPORTED（400）。"""
        project_id = _create_confirmed_project(client)
        response = client.post(
            f"/api/projects/{project_id}/sources/pdf",
            data={"title": "非 PDF"},
            files={"file": ("file.txt", b"text", "text/plain")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "SOURCE_FILE_UNSUPPORTED"

    def test_rejects_when_project_not_confirmed(self, client):
        """项目状态不足时返回 PROJECT_REQUIREMENT_NOT_CONFIRMED。"""
        project_id = _create_project(client)
        response = client.post(
            f"/api/projects/{project_id}/sources/pdf",
            data={"title": "X"},
            files={"file": ("a.pdf", b"%PDF-1.4 test", "application/pdf")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PROJECT_REQUIREMENT_NOT_CONFIRMED"


# --- GET /sources ---


class TestListSourcesApi:
    """来源列表 API 测试。"""

    def test_lists_sources(self, client):
        """GET /sources 返回 SourceListResponse。"""
        project_id = _create_confirmed_project(client)
        client.post(
            f"/api/projects/{project_id}/sources/url",
            json={"url": "https://example.com/a.html"},
        )
        client.post(
            f"/api/projects/{project_id}/sources/url",
            json={"url": "https://example.com/b.html"},
        )

        response = client.get(f"/api/projects/{project_id}/sources")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        for item in data["items"]:
            assert item["source_kind"] == "URL"
            assert item["status"] == "PENDING"

    def test_returns_empty_list_when_no_sources(self, client):
        """无来源时返回空列表。"""
        project_id = _create_confirmed_project(client)
        response = client.get(f"/api/projects/{project_id}/sources")
        assert response.status_code == 200
        assert response.json()["items"] == []

    def test_returns_404_when_project_missing(self, client):
        """项目不存在时返回 PROJECT_NOT_FOUND。"""
        response = client.get("/api/projects/proj_missing/sources")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


# --- GET /sources/{id} ---


class TestGetSourceApi:
    """来源详情 API 测试。"""

    def test_returns_source_by_id(self, client):
        """GET /sources/{id} 返回单条来源。"""
        project_id = _create_confirmed_project(client)
        create_resp = client.post(
            f"/api/projects/{project_id}/sources/url",
            json={"url": "https://example.com/a.html"},
        )
        source_id = create_resp.json()["id"]

        response = client.get(
            f"/api/projects/{project_id}/sources/{source_id}"
        )
        assert response.status_code == 200
        assert response.json()["id"] == source_id

    def test_returns_404_when_source_missing(self, client):
        """来源不存在时返回 SOURCE_NOT_FOUND。"""
        project_id = _create_confirmed_project(client)
        response = client.get(
            f"/api/projects/{project_id}/sources/src_missing"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SOURCE_NOT_FOUND"


# --- DELETE /sources/{id} ---


class TestDeleteSourceApi:
    """删除来源 API 测试。"""

    def test_deletes_source_returns_200(self, client):
        """DELETE /sources/{id} 软删除来源，返回 200。"""
        project_id = _create_confirmed_project(client)
        create_resp = client.post(
            f"/api/projects/{project_id}/sources/url",
            json={"url": "https://example.com/a.html"},
        )
        source_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/projects/{project_id}/sources/{source_id}"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "DELETED"

    def test_returns_404_when_source_missing(self, client):
        """来源不存在时返回 SOURCE_NOT_FOUND。"""
        project_id = _create_confirmed_project(client)
        response = client.delete(
            f"/api/projects/{project_id}/sources/src_missing"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SOURCE_NOT_FOUND"


# --- POST /sources/complete ---


class TestCompleteSourcesApi:
    """完成来源收集 API 测试。"""

    def test_completes_returns_200_with_status(self, client, monkeypatch):
        """有 PARSED 来源时完成收集，返回 project status=SOURCES_COLLECTED。"""
        project_id = _create_confirmed_project(client)
        # 先登记一个来源
        create_resp = client.post(
            f"/api/projects/{project_id}/sources/url",
            json={"url": "https://example.com/a.html"},
        )
        source_id = create_resp.json()["id"]

        # 直接在数据库里把 source 改为 PARSED（绕过 Worker）
        from app.api.routers import sources as sources_router
        SessionLocal = sources_router.SessionLocal
        from app.modules.sources.models import Source
        from app.modules.sources.status import SourceStatus
        db = SessionLocal()
        try:
            src = db.query(Source).filter(Source.id == source_id).first()
            src.status = SourceStatus.PARSED.value
            db.commit()
        finally:
            db.close()

        response = client.post(f"/api/projects/{project_id}/sources/complete")
        assert response.status_code == 200
        assert response.json()["status"] == "SOURCES_COLLECTED"

    def test_rejects_when_no_parsed_source(self, client):
        """无 PARSED 来源时返回 PROJECT_NO_PARSED_SOURCE。"""
        project_id = _create_confirmed_project(client)
        # 仅登记一个 PENDING 来源
        client.post(
            f"/api/projects/{project_id}/sources/url",
            json={"url": "https://example.com/a.html"},
        )
        response = client.post(f"/api/projects/{project_id}/sources/complete")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PROJECT_NO_PARSED_SOURCE"
