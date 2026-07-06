"""数据集 API 端点测试。

使用 TestClient + monkeypatch SessionLocal，覆盖 8 个 API 端点的成功与失败路径：
- POST /upload (multipart/form-data)
- POST /url
- GET / (列表)
- GET /{dataset_id}
- GET /{dataset_id}/versions
- DELETE /{dataset_id}
- POST /{dataset_id}/reupload
- POST /complete

错误码验证：DATASET_FILE_UNSUPPORTED、DATASET_FILE_TOO_LARGE、DATASET_NOT_FOUND 等。
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
from app.modules.sources.models import (  # noqa: F401
    Source,
    ParsedDocument,
    EvidenceCard,
)
from app.modules.jobs.models import BackgroundJob  # noqa: F401
from app.modules.datasets.models import Dataset, DatasetVersion  # noqa: F401
from app.modules.analysis.models import AnalysisPlan  # noqa: F401
from app.infrastructure.fetchers.http_fetcher import FetchResult


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


def _evidence_confirmed_project(client: TestClient, monkeypatch) -> str:
    """创建一个 EVIDENCE_CONFIRMED 状态的项目（绕过前序流程）。

    通过 API 创建项目后，直接通过 DB 设置状态。
    """
    project_id = _create_project(client)
    from app.api.routers import projects as project_router
    SessionLocal = project_router.SessionLocal
    from app.modules.projects.models import Project
    from app.modules.projects.status import ProjectStatus

    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        project.status = ProjectStatus.EVIDENCE_CONFIRMED.value
        db.commit()
    finally:
        db.close()
    return project_id


def _csv_bytes() -> bytes:
    """构造合法的 CSV 内容。"""
    return (
        b"name,age,score\n"
        b"alice,30,90.5\n"
        b"bob,25,85.0\n"
        b"carol,28,78.0\n"
    )


# --- POST /upload ---


class TestUploadDatasetApi:
    """上传 CSV/Excel 数据集 API 测试。"""

    def test_uploads_csv_returns_201(self, client, monkeypatch):
        """成功上传 CSV 文件，返回 201。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        response = client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "胃病数据", "description": "教学数据集"},
            files={
                "file": ("data.csv", _csv_bytes(), "text/csv"),
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["dataset_kind"] == "FILE"
        assert data["status"] == "PENDING"
        assert data["title"] == "胃病数据"
        assert data["description"] == "教学数据集"
        assert data["job_id"]

    def test_uploads_xlsx_returns_201(self, client, monkeypatch, tmp_path):
        """成功上传 XLSX 文件。"""
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["name", "age"])
        ws.append(["alice", 30])
        xlsx_path = tmp_path / "test.xlsx"
        wb.save(xlsx_path)

        project_id = _evidence_confirmed_project(client, monkeypatch)
        with open(xlsx_path, "rb") as f:
            response = client.post(
                f"/api/projects/{project_id}/datasets/upload",
                data={"title": "Excel 数据"},
                files={"file": ("data.xlsx", f.read(),
                                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        assert response.status_code == 201
        assert response.json()["dataset_kind"] == "FILE"

    def test_rejects_empty_file(self, client, monkeypatch):
        """空文件返回 DATASET_FILE_EMPTY（400）。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        response = client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "X"},
            files={"file": ("empty.csv", b"", "text/csv")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DATASET_FILE_EMPTY"

    def test_rejects_unsupported_extension(self, client, monkeypatch):
        """非 CSV/XLSX 扩展返回 DATASET_FILE_UNSUPPORTED（400）。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        response = client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "X"},
            files={"file": ("data.txt", b"some text", "text/plain")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DATASET_FILE_UNSUPPORTED"

    def test_rejects_pdf_file(self, client, monkeypatch):
        """PDF 文件不被支持。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        response = client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "X"},
            files={"file": ("data.pdf", b"%PDF-1.4 test", "application/pdf")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DATASET_FILE_UNSUPPORTED"

    def test_rejects_file_too_large(self, client, monkeypatch):
        """超过 50MB 上限返回 413。"""
        monkeypatch.setenv("DATASET_MAX_SIZE_BYTES", "100")
        project_id = _evidence_confirmed_project(client, monkeypatch)
        big = b"x" * 200
        response = client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "X"},
            files={"file": ("big.csv", big, "text/csv")},
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "DATASET_FILE_TOO_LARGE"

    def test_rejects_when_project_status_insufficient(self, client):
        """项目状态为 DRAFT 时返回 PROJECT_EVIDENCE_NOT_CONFIRMED。"""
        project_id = _create_project(client)
        response = client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "X"},
            files={"file": ("data.csv", _csv_bytes(), "text/csv")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PROJECT_EVIDENCE_NOT_CONFIRMED"

    def test_returns_404_when_project_missing(self, client):
        """项目不存在时返回 PROJECT_NOT_FOUND。"""
        response = client.post(
            "/api/projects/proj_missing/datasets/upload",
            data={"title": "X"},
            files={"file": ("data.csv", _csv_bytes(), "text/csv")},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    def test_uses_filename_when_title_empty(self, client, monkeypatch):
        """title 为空时用文件名作为标题。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        response = client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": ""},
            files={"file": ("data.csv", _csv_bytes(), "text/csv")},
        )
        assert response.status_code == 201
        assert response.json()["title"] == "data.csv"


# --- POST /url ---


class TestCreateUrlDatasetApi:
    """登记公开 URL 数据集 API 测试。"""

    def test_creates_url_dataset_returns_201(self, client, monkeypatch):
        """成功登记公开 CSV URL，返回 201。"""
        # mock fetch_url
        from app.modules.datasets import service as datasets_service
        from app.infrastructure.fetchers.http_fetcher import FetchResult

        def fake_fetch_url(url, timeout_seconds=30, max_size_bytes=52428800):
            return FetchResult(
                content=_csv_bytes(),
                content_type="text/csv",
                status_code=200,
                url=url,
            )

        monkeypatch.setattr(datasets_service, "fetch_url", fake_fetch_url)

        project_id = _evidence_confirmed_project(client, monkeypatch)
        response = client.post(
            f"/api/projects/{project_id}/datasets/url",
            json={
                "url": "https://example.com/data.csv",
                "title": "远程数据集",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["dataset_kind"] == "URL"
        assert data["status"] == "PENDING"
        assert data["title"] == "远程数据集"

    def test_rejects_non_public_url(self, client, monkeypatch):
        """非公开 URL 返回 DATASET_URL_NOT_PUBLIC（400）。"""
        from app.modules.datasets import service as datasets_service
        monkeypatch.setattr(
            datasets_service, "fetch_url",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应调用")),
        )

        project_id = _evidence_confirmed_project(client, monkeypatch)
        response = client.post(
            f"/api/projects/{project_id}/datasets/url",
            json={"url": "http://localhost:8080/secret.csv"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DATASET_URL_NOT_PUBLIC"

    def test_rejects_unsupported_scheme(self, client, monkeypatch):
        """非 http/https 协议返回 DATASET_URL_SCHEME_UNSUPPORTED（400）。"""
        from app.modules.datasets import service as datasets_service
        monkeypatch.setattr(
            datasets_service, "fetch_url",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应调用")),
        )

        project_id = _evidence_confirmed_project(client, monkeypatch)
        response = client.post(
            f"/api/projects/{project_id}/datasets/url",
            json={"url": "file:///etc/passwd"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DATASET_URL_SCHEME_UNSUPPORTED"

    def test_rejects_when_project_status_insufficient(self, client, monkeypatch):
        """项目状态不足时返回 PROJECT_EVIDENCE_NOT_CONFIRMED。"""
        from app.modules.datasets import service as datasets_service
        monkeypatch.setattr(
            datasets_service, "fetch_url",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应调用")),
        )

        project_id = _create_project(client)
        response = client.post(
            f"/api/projects/{project_id}/datasets/url",
            json={"url": "https://example.com/data.csv"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PROJECT_EVIDENCE_NOT_CONFIRMED"

    def test_returns_404_when_project_missing(self, client, monkeypatch):
        """项目不存在时返回 PROJECT_NOT_FOUND。"""
        from app.modules.datasets import service as datasets_service
        monkeypatch.setattr(
            datasets_service, "fetch_url",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应调用")),
        )

        response = client.post(
            "/api/projects/proj_missing/datasets/url",
            json={"url": "https://example.com/data.csv"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    def test_rejects_restricted_resource(self, client, monkeypatch):
        """受限资源返回 DATASET_ACCESS_RESTRICTED（403）。"""
        from app.modules.datasets import service as datasets_service
        from app.infrastructure.fetchers.http_fetcher import FetchError

        def fake_fetch_url(url, timeout_seconds=30, max_size_bytes=52428800):
            raise FetchError("SOURCE_ACCESS_RESTRICTED", "需要登录")

        monkeypatch.setattr(datasets_service, "fetch_url", fake_fetch_url)

        project_id = _evidence_confirmed_project(client, monkeypatch)
        response = client.post(
            f"/api/projects/{project_id}/datasets/url",
            json={"url": "https://example.com/protected.csv"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DATASET_ACCESS_RESTRICTED"


# --- GET / (列表) ---


class TestListDatasetsApi:
    """数据集列表 API 测试。"""

    def test_lists_datasets(self, client, monkeypatch):
        """GET /datasets 返回 DatasetListResponse。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "A"},
            files={"file": ("a.csv", _csv_bytes(), "text/csv")},
        )
        client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "B"},
            files={"file": ("b.csv", _csv_bytes(), "text/csv")},
        )

        response = client.get(f"/api/projects/{project_id}/datasets")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 2

    def test_returns_empty_list_when_no_datasets(self, client, monkeypatch):
        """无数据集时返回空列表。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        response = client.get(f"/api/projects/{project_id}/datasets")
        assert response.status_code == 200
        assert response.json()["items"] == []

    def test_returns_404_when_project_missing(self, client):
        """项目不存在时返回 PROJECT_NOT_FOUND。"""
        response = client.get("/api/projects/proj_missing/datasets")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


# --- GET /{dataset_id} ---


class TestGetDatasetApi:
    """数据集详情 API 测试。"""

    def test_returns_dataset_by_id(self, client, monkeypatch):
        """GET /{id} 返回 DatasetResponse。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        create_resp = client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "X"},
            files={"file": ("data.csv", _csv_bytes(), "text/csv")},
        )
        dataset_id = create_resp.json()["id"]

        response = client.get(
            f"/api/projects/{project_id}/datasets/{dataset_id}"
        )
        assert response.status_code == 200
        assert response.json()["id"] == dataset_id

    def test_returns_404_when_dataset_missing(self, client, monkeypatch):
        """数据集不存在时返回 DATASET_NOT_FOUND。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        response = client.get(
            f"/api/projects/{project_id}/datasets/ds_missing"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "DATASET_NOT_FOUND"


# --- GET /{dataset_id}/versions ---


class TestListDatasetVersionsApi:
    """数据集版本列表 API 测试。"""

    def test_lists_versions(self, client, monkeypatch):
        """GET /{id}/versions 返回 DatasetVersionListResponse。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        create_resp = client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "X"},
            files={"file": ("data.csv", _csv_bytes(), "text/csv")},
        )
        dataset_id = create_resp.json()["id"]

        response = client.get(
            f"/api/projects/{project_id}/datasets/{dataset_id}/versions"
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["version"] == 1

    def test_returns_404_when_dataset_missing(self, client, monkeypatch):
        """数据集不存在时返回 DATASET_NOT_FOUND。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        response = client.get(
            f"/api/projects/{project_id}/datasets/ds_missing/versions"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "DATASET_NOT_FOUND"


# --- DELETE /{dataset_id} ---


class TestDeleteDatasetApi:
    """软删除数据集 API 测试。"""

    def test_deletes_dataset_returns_200(self, client, monkeypatch):
        """DELETE /{id} 软删除数据集。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        create_resp = client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "X"},
            files={"file": ("data.csv", _csv_bytes(), "text/csv")},
        )
        dataset_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/projects/{project_id}/datasets/{dataset_id}"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "DELETED"

    def test_second_query_returns_404_after_delete(self, client, monkeypatch):
        """删除后再次 GET 返回 404。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        create_resp = client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "X"},
            files={"file": ("data.csv", _csv_bytes(), "text/csv")},
        )
        dataset_id = create_resp.json()["id"]

        client.delete(f"/api/projects/{project_id}/datasets/{dataset_id}")

        response = client.get(
            f"/api/projects/{project_id}/datasets/{dataset_id}"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "DATASET_NOT_FOUND"

    def test_returns_404_when_dataset_missing(self, client, monkeypatch):
        """数据集不存在时返回 DATASET_NOT_FOUND。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        response = client.delete(
            f"/api/projects/{project_id}/datasets/ds_missing"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "DATASET_NOT_FOUND"


# --- POST /{dataset_id}/reupload ---


class TestReuploadDatasetApi:
    """重新上传数据集 API 测试。"""

    def test_reupload_creates_new_version(self, client, monkeypatch):
        """重新上传创建新版本。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        create_resp = client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "X"},
            files={"file": ("data.csv", _csv_bytes(), "text/csv")},
        )
        dataset_id = create_resp.json()["id"]

        # 重新上传
        response = client.post(
            f"/api/projects/{project_id}/datasets/{dataset_id}/reupload",
            files={"file": ("v2.csv", _csv_bytes(), "text/csv")},
        )
        assert response.status_code == 200
        # 验证有 2 个版本
        versions_resp = client.get(
            f"/api/projects/{project_id}/datasets/{dataset_id}/versions"
        )
        assert len(versions_resp.json()["items"]) == 2

    def test_reupload_rejects_unsupported_extension(self, client, monkeypatch):
        """reupload 不支持的扩展名返回 DATASET_FILE_UNSUPPORTED。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        create_resp = client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "X"},
            files={"file": ("data.csv", _csv_bytes(), "text/csv")},
        )
        dataset_id = create_resp.json()["id"]

        response = client.post(
            f"/api/projects/{project_id}/datasets/{dataset_id}/reupload",
            files={"file": ("data.txt", b"text", "text/plain")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DATASET_FILE_UNSUPPORTED"

    def test_reupload_returns_404_when_dataset_missing(self, client, monkeypatch):
        """数据集不存在时返回 DATASET_NOT_FOUND。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        response = client.post(
            f"/api/projects/{project_id}/datasets/ds_missing/reupload",
            files={"file": ("data.csv", _csv_bytes(), "text/csv")},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "DATASET_NOT_FOUND"

    def test_reupload_rejects_empty_file(self, client, monkeypatch):
        """reupload 空文件返回 DATASET_FILE_EMPTY。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        create_resp = client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "X"},
            files={"file": ("data.csv", _csv_bytes(), "text/csv")},
        )
        dataset_id = create_resp.json()["id"]

        response = client.post(
            f"/api/projects/{project_id}/datasets/{dataset_id}/reupload",
            files={"file": ("empty.csv", b"", "text/csv")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DATASET_FILE_EMPTY"


# --- POST /complete ---


class TestCompleteDatasetsApi:
    """完成数据集收集 API 测试。"""

    def test_completes_returns_200_with_status(self, client, monkeypatch):
        """有 READY 数据集时完成收集，返回 project status=DATASET_READY。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        create_resp = client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "X"},
            files={"file": ("data.csv", _csv_bytes(), "text/csv")},
        )
        dataset_id = create_resp.json()["id"]

        # 直接在 DB 把 dataset 设为 READY（绕过 Worker）
        from app.api.routers import datasets as datasets_router
        from app.modules.datasets.models import Dataset
        from app.modules.datasets.status import DatasetStatus

        SessionLocal = datasets_router.SessionLocal
        db = SessionLocal()
        try:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            ds.status = DatasetStatus.READY.value
            db.commit()
        finally:
            db.close()

        response = client.post(f"/api/projects/{project_id}/datasets/complete")
        assert response.status_code == 200
        assert response.json()["status"] == "DATASET_READY"

    def test_rejects_when_no_ready_dataset(self, client, monkeypatch):
        """无 READY 数据集时返回 PROJECT_NO_READY_DATASET。"""
        project_id = _evidence_confirmed_project(client, monkeypatch)
        client.post(
            f"/api/projects/{project_id}/datasets/upload",
            data={"title": "X"},
            files={"file": ("data.csv", _csv_bytes(), "text/csv")},
        )
        # dataset.status 仍为 PENDING
        response = client.post(f"/api/projects/{project_id}/datasets/complete")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PROJECT_NO_READY_DATASET"

    def test_returns_404_when_project_missing(self, client):
        """项目不存在时返回 PROJECT_NOT_FOUND。"""
        response = client.post("/api/projects/proj_missing/datasets/complete")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


# --- 路由路径冲突验证 ---


class TestDatasetRouteConflict:
    """验证 /complete 路由不会被 /{dataset_id} 捕获。"""

    def test_complete_route_takes_precedence_over_dataset_id(
        self, client, monkeypatch
    ):
        """POST /complete 应匹配 complete 路由，不应被解释为 dataset_id='complete'。

        如果路由顺序错误，FastAPI 会尝试以 'complete' 作为 dataset_id 查询数据集，
        返回 DATASET_NOT_FOUND 而非 PROJECT_NO_READY_DATASET。
        """
        project_id = _evidence_confirmed_project(client, monkeypatch)
        response = client.post(f"/api/projects/{project_id}/datasets/complete")
        # 应返回 PROJECT_NO_READY_DATASET（项目状态正确但无 READY 数据集），
        # 而不是 DATASET_NOT_FOUND
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PROJECT_NO_READY_DATASET"
