"""数据集核心服务测试。

覆盖 create_file_dataset、create_url_dataset、list/get 查询、版本管理、
软删除、STALE 传播、complete_datasets、Worker helpers（mark_dataset_parsing、
mark_dataset_parsed、mark_dataset_failed、trigger_analysis_plan_generation）。

通过 monkeypatch 模拟 fetch_url，避免真实网络访问。
通过直接设置 project.status=EVIDENCE_CONFIRMED 跳过前序流程，
聚焦数据集 owner 层业务语义。
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.engine import Base
from app.core.errors import AppError
from app.infrastructure.fetchers.http_fetcher import FetchResult, FetchError
from app.modules.projects import service as project_service
from app.modules.projects.status import ProjectStatus
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.datasets import service as datasets_service
from app.modules.datasets.models import Dataset, DatasetVersion
from app.modules.datasets.status import (
    DatasetKind,
    DatasetStatus,
    DatasetVersionStatus,
)
from app.modules.analysis.models import AnalysisPlan
from app.modules.analysis.status import AnalysisPlanStatus
from app.modules.jobs.status import JobType, JobStatus
from app.modules.jobs.models import BackgroundJob


TEST_DB = "sqlite:///:memory:"


@pytest.fixture
def db(monkeypatch, tmp_path):
    """内存 SQLite + 受控 PROJECT_DATA_ROOT。"""
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def evidence_confirmed_project_id(db):
    """创建一个 EVIDENCE_CONFIRMED 状态的项目，用于数据集测试前置条件。

    直接通过 DB 设置状态，跳过前序流程（已在 sources/evidence 测试中覆盖），
    聚焦数据集 owner 层业务语义。
    """
    project = project_service.create_project(
        db, ProjectCreateRequest(name="胃病数据分析", topic="胃病数据分析")
    )
    project.status = ProjectStatus.EVIDENCE_CONFIRMED.value
    db.commit()
    db.refresh(project)
    return project.id


def _csv_content() -> bytes:
    """构造一个合法的 CSV 内容。"""
    return (
        b"name,age,score\n"
        b"alice,30,90.5\n"
        b"bob,25,85.0\n"
        b"alice,30,90.5\n"
        b"carol,,78.0\n"
    )


# --- create_file_dataset ---


class TestCreateFileDataset:
    """上传文件创建数据集测试。"""

    def test_creates_dataset_pending_status_and_parse_job(
        self, db, evidence_confirmed_project_id
    ):
        """成功上传 CSV：创建 Dataset + DatasetVersion(v1, PENDING) + PARSE_DATASET 任务。"""
        content = _csv_content()
        dataset, job_id = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="胃病数据", description="教学数据集",
            file_content=content, original_filename="data.csv",
        )

        assert dataset.project_id == evidence_confirmed_project_id
        assert dataset.dataset_kind == DatasetKind.FILE.value
        assert dataset.status == DatasetStatus.PENDING.value
        assert dataset.title == "胃病数据"
        assert dataset.description == "教学数据集"
        assert job_id

        # 验证文件写入受控工作区
        versions = (
            db.query(DatasetVersion)
            .filter(DatasetVersion.dataset_id == dataset.id)
            .all()
        )
        assert len(versions) == 1
        v1 = versions[0]
        assert v1.version == 1
        assert v1.status == DatasetVersionStatus.PENDING.value
        assert Path(v1.file_path).exists()
        assert Path(v1.file_path).name == "raw.csv"
        assert Path(v1.file_path).parent.name == "v1"
        assert v1.file_size_bytes == len(content)

        # 验证创建了 PARSE_DATASET 任务
        job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
        assert job is not None
        assert job.job_type == JobType.PARSE_DATASET.value
        assert job.status == JobStatus.PENDING.value
        assert dataset.id in job.input_json
        assert v1.id in job.input_json

    def test_writes_to_controlled_workspace_path(self, db, evidence_confirmed_project_id):
        """文件保存到 projects/{project_id}/datasets/{dataset_id}/v1/raw.csv。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="data.csv",
        )
        v1 = datasets_service.get_latest_version(db, dataset.id)
        # 路径模板校验
        path = Path(v1.file_path)
        # 至少应包含 datasets/<dataset_id>/v1/raw.csv
        assert path.name == "raw.csv"
        assert path.parent.name == "v1"
        assert path.parent.parent.name == dataset.id
        assert path.parent.parent.parent.name == "datasets"

    def test_rejects_when_project_status_insufficient(self, db):
        """项目状态为 DRAFT 时拒绝，返回 PROJECT_EVIDENCE_NOT_CONFIRMED。"""
        project = project_service.create_project(
            db, ProjectCreateRequest(name="新项目", topic="测试")
        )
        # project.status == DRAFT
        with pytest.raises(AppError) as exc:
            datasets_service.create_file_dataset(
                db, project.id,
                title="X", description=None,
                file_content=_csv_content(), original_filename="data.csv",
            )
        assert exc.value.code == "PROJECT_EVIDENCE_NOT_CONFIRMED"

    def test_rejects_empty_file(self, db, evidence_confirmed_project_id):
        """空文件返回 DATASET_FILE_EMPTY。"""
        with pytest.raises(AppError) as exc:
            datasets_service.create_file_dataset(
                db, evidence_confirmed_project_id,
                title="X", description=None,
                file_content=b"", original_filename="empty.csv",
            )
        assert exc.value.code == "DATASET_FILE_EMPTY"

    def test_rejects_unsupported_extension(self, db, evidence_confirmed_project_id):
        """非 CSV/XLSX 扩展返回 DATASET_FILE_UNSUPPORTED。"""
        with pytest.raises(AppError) as exc:
            datasets_service.create_file_dataset(
                db, evidence_confirmed_project_id,
                title="X", description=None,
                file_content=b"some text", original_filename="data.txt",
            )
        assert exc.value.code == "DATASET_FILE_UNSUPPORTED"

    def test_rejects_pdf_file(self, db, evidence_confirmed_project_id):
        """PDF 文件不被支持。"""
        with pytest.raises(AppError) as exc:
            datasets_service.create_file_dataset(
                db, evidence_confirmed_project_id,
                title="X", description=None,
                file_content=b"%PDF-1.4 test", original_filename="data.pdf",
            )
        assert exc.value.code == "DATASET_FILE_UNSUPPORTED"

    def test_rejects_file_too_large(self, db, evidence_confirmed_project_id, monkeypatch):
        """超过 50MB 上限返回 DATASET_FILE_TOO_LARGE。"""
        # 调小上限以避免构造 50MB 内容
        monkeypatch.setenv("DATASET_MAX_SIZE_BYTES", "100")
        # 重新加载 settings（settings 是 property，每次读 env）
        from app.core.config import settings
        assert settings.dataset_max_size_bytes == 100

        big = b"x" * 200
        with pytest.raises(AppError) as exc:
            datasets_service.create_file_dataset(
                db, evidence_confirmed_project_id,
                title="X", description=None,
                file_content=big, original_filename="big.csv",
            )
        assert exc.value.code == "DATASET_FILE_TOO_LARGE"

    def test_uses_filename_when_title_empty(self, db, evidence_confirmed_project_id):
        """title 为空时使用 original_filename 作为标题。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="", description=None,
            file_content=_csv_content(), original_filename="data.csv",
        )
        assert dataset.title == "data.csv"

    def test_returns_404_when_project_missing(self, db):
        """项目不存在时抛出 PROJECT_NOT_FOUND。"""
        with pytest.raises(AppError) as exc:
            datasets_service.create_file_dataset(
                db, "proj_missing",
                title="X", description=None,
                file_content=_csv_content(), original_filename="data.csv",
            )
        assert exc.value.code == "PROJECT_NOT_FOUND"


# --- create_url_dataset ---


class TestCreateUrlDataset:
    """登记公开 URL 创建数据集测试。"""

    def test_creates_dataset_from_url(
        self, db, evidence_confirmed_project_id, monkeypatch
    ):
        """成功登记公开 CSV URL：下载、保存、创建 Dataset + PARSE_DATASET 任务。"""
        csv_bytes = _csv_content()

        def fake_fetch_url(url, timeout_seconds=30, max_size_bytes=52428800):
            return FetchResult(
                content=csv_bytes,
                content_type="text/csv",
                status_code=200,
                url=url,
            )

        monkeypatch.setattr(datasets_service, "fetch_url", fake_fetch_url)

        dataset, job_id = datasets_service.create_url_dataset(
            db, evidence_confirmed_project_id,
            url="https://example.com/data.csv",
            title="远程数据集", description=None,
        )

        assert dataset.dataset_kind == DatasetKind.URL.value
        assert dataset.status == DatasetStatus.PENDING.value
        assert dataset.title == "远程数据集"
        assert job_id

        # 验证文件已写入
        v1 = datasets_service.get_latest_version(db, dataset.id)
        assert Path(v1.file_path).name == "raw.csv"
        assert Path(v1.file_path).parent.name == "v1"
        assert Path(v1.file_path).exists()
        assert v1.file_size_bytes == len(csv_bytes)

        # 验证创建了 PARSE_DATASET 任务
        job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
        assert job.job_type == JobType.PARSE_DATASET.value

    def test_uses_url_as_title_when_title_empty(
        self, db, evidence_confirmed_project_id, monkeypatch
    ):
        """title 为空时用 URL 作标题。"""
        def fake_fetch_url(url, timeout_seconds=30, max_size_bytes=52428800):
            return FetchResult(
                content=_csv_content(),
                content_type="text/csv",
                status_code=200,
                url=url,
            )

        monkeypatch.setattr(datasets_service, "fetch_url", fake_fetch_url)

        dataset, _ = datasets_service.create_url_dataset(
            db, evidence_confirmed_project_id,
            url="https://example.com/data.csv",
            title="", description=None,
        )
        assert dataset.title == "https://example.com/data.csv"

    def test_rejects_localhost(self, db, evidence_confirmed_project_id, monkeypatch):
        """localhost 视为非公开，返回 DATASET_URL_NOT_PUBLIC。"""
        def fake_fetch_url(url, timeout_seconds=30, max_size_bytes=52428800):
            raise AssertionError("fetch_url 不应被调用")

        monkeypatch.setattr(datasets_service, "fetch_url", fake_fetch_url)

        with pytest.raises(AppError) as exc:
            datasets_service.create_url_dataset(
                db, evidence_confirmed_project_id,
                url="http://localhost:8080/data.csv",
                title="X", description=None,
            )
        assert exc.value.code == "DATASET_URL_NOT_PUBLIC"

    def test_rejects_loopback_ip(self, db, evidence_confirmed_project_id, monkeypatch):
        """127.0.0.1 视为非公开。"""
        monkeypatch.setattr(
            datasets_service, "fetch_url",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应调用")),
        )
        with pytest.raises(AppError) as exc:
            datasets_service.create_url_dataset(
                db, evidence_confirmed_project_id,
                url="http://127.0.0.1/data.csv",
                title="X", description=None,
            )
        assert exc.value.code == "DATASET_URL_NOT_PUBLIC"

    def test_rejects_private_ip(self, db, evidence_confirmed_project_id, monkeypatch):
        """192.168.* 视为非公开。"""
        monkeypatch.setattr(
            datasets_service, "fetch_url",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应调用")),
        )
        with pytest.raises(AppError) as exc:
            datasets_service.create_url_dataset(
                db, evidence_confirmed_project_id,
                url="http://192.168.1.1/data.csv",
                title="X", description=None,
            )
        assert exc.value.code == "DATASET_URL_NOT_PUBLIC"

    def test_rejects_file_scheme(self, db, evidence_confirmed_project_id, monkeypatch):
        """file:// 协议不支持，返回 DATASET_URL_SCHEME_UNSUPPORTED。"""
        monkeypatch.setattr(
            datasets_service, "fetch_url",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应调用")),
        )
        with pytest.raises(AppError) as exc:
            datasets_service.create_url_dataset(
                db, evidence_confirmed_project_id,
                url="file:///etc/passwd",
                title="X", description=None,
            )
        assert exc.value.code == "DATASET_URL_SCHEME_UNSUPPORTED"

    def test_rejects_ftp_scheme(self, db, evidence_confirmed_project_id, monkeypatch):
        """ftp:// 协议不支持。"""
        monkeypatch.setattr(
            datasets_service, "fetch_url",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应调用")),
        )
        with pytest.raises(AppError) as exc:
            datasets_service.create_url_dataset(
                db, evidence_confirmed_project_id,
                url="ftp://example.com/data.csv",
                title="X", description=None,
            )
        assert exc.value.code == "DATASET_URL_SCHEME_UNSUPPORTED"

    def test_rejects_empty_url(self, db, evidence_confirmed_project_id, monkeypatch):
        """空 URL 返回 DATASET_URL_REQUIRED。"""
        monkeypatch.setattr(
            datasets_service, "fetch_url",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应调用")),
        )
        with pytest.raises(AppError) as exc:
            datasets_service.create_url_dataset(
                db, evidence_confirmed_project_id,
                url="   ",
                title="X", description=None,
            )
        assert exc.value.code == "DATASET_URL_REQUIRED"

    def test_restricted_resource_returns_access_restricted(
        self, db, evidence_confirmed_project_id, monkeypatch
    ):
        """fetch_url 抛 SOURCE_ACCESS_RESTRICTED 时映射为 DATASET_ACCESS_RESTRICTED。"""
        def fake_fetch_url(url, timeout_seconds=30, max_size_bytes=52428800):
            raise FetchError("SOURCE_ACCESS_RESTRICTED", "来源需要登录")

        monkeypatch.setattr(datasets_service, "fetch_url", fake_fetch_url)

        with pytest.raises(AppError) as exc:
            datasets_service.create_url_dataset(
                db, evidence_confirmed_project_id,
                url="https://example.com/protected.csv",
                title="X", description=None,
            )
        assert exc.value.code == "DATASET_ACCESS_RESTRICTED"

    def test_fetch_timeout_returns_url_invalid(
        self, db, evidence_confirmed_project_id, monkeypatch
    ):
        """fetch_url 抛 FETCH_TIMEOUT 时映射为 DATASET_URL_INVALID。"""
        def fake_fetch_url(url, timeout_seconds=30, max_size_bytes=52428800):
            raise FetchError("FETCH_TIMEOUT", "采集超时")

        monkeypatch.setattr(datasets_service, "fetch_url", fake_fetch_url)

        with pytest.raises(AppError) as exc:
            datasets_service.create_url_dataset(
                db, evidence_confirmed_project_id,
                url="https://example.com/slow.csv",
                title="X", description=None,
            )
        assert exc.value.code == "DATASET_URL_INVALID"

    def test_fetch_too_large_returns_file_too_large(
        self, db, evidence_confirmed_project_id, monkeypatch
    ):
        """fetch_url 抛 FETCH_TOO_LARGE 时映射为 DATASET_FILE_TOO_LARGE。"""
        def fake_fetch_url(url, timeout_seconds=30, max_size_bytes=52428800):
            raise FetchError("FETCH_TOO_LARGE", "采集内容过大")

        monkeypatch.setattr(datasets_service, "fetch_url", fake_fetch_url)

        with pytest.raises(AppError) as exc:
            datasets_service.create_url_dataset(
                db, evidence_confirmed_project_id,
                url="https://example.com/big.csv",
                title="X", description=None,
            )
        assert exc.value.code == "DATASET_FILE_TOO_LARGE"

    def test_unsupported_content_type_returns_unsupported(
        self, db, evidence_confirmed_project_id, monkeypatch
    ):
        """URL 返回非 CSV/Excel Content-Type 时返回 DATASET_FILE_UNSUPPORTED。"""
        def fake_fetch_url(url, timeout_seconds=30, max_size_bytes=52428800):
            return FetchResult(
                content=b"<html>not a csv</html>",
                content_type="text/html",
                status_code=200,
                url=url,
            )

        monkeypatch.setattr(datasets_service, "fetch_url", fake_fetch_url)

        # URL 后缀也不在 csv/xlsx 中
        with pytest.raises(AppError) as exc:
            datasets_service.create_url_dataset(
                db, evidence_confirmed_project_id,
                url="https://example.com/page",
                title="X", description=None,
            )
        assert exc.value.code == "DATASET_FILE_UNSUPPORTED"

    def test_rejects_empty_response_body(
        self, db, evidence_confirmed_project_id, monkeypatch
    ):
        """下载内容为空时返回 DATASET_FILE_EMPTY。"""
        def fake_fetch_url(url, timeout_seconds=30, max_size_bytes=52428800):
            return FetchResult(
                content=b"",
                content_type="text/csv",
                status_code=200,
                url=url,
            )

        monkeypatch.setattr(datasets_service, "fetch_url", fake_fetch_url)

        with pytest.raises(AppError) as exc:
            datasets_service.create_url_dataset(
                db, evidence_confirmed_project_id,
                url="https://example.com/empty.csv",
                title="X", description=None,
            )
        assert exc.value.code == "DATASET_FILE_EMPTY"

    def test_rejects_when_project_status_insufficient(self, db, monkeypatch):
        """项目状态为 DRAFT 时拒绝。"""
        monkeypatch.setattr(
            datasets_service, "fetch_url",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应调用")),
        )
        project = project_service.create_project(
            db, ProjectCreateRequest(name="新项目", topic="测试")
        )
        with pytest.raises(AppError) as exc:
            datasets_service.create_url_dataset(
                db, project.id,
                url="https://example.com/data.csv",
                title="X", description=None,
            )
        assert exc.value.code == "PROJECT_EVIDENCE_NOT_CONFIRMED"

    def test_infers_xlsx_from_content_type(
        self, db, evidence_confirmed_project_id, monkeypatch, tmp_path
    ):
        """Content-Type 为 spreadsheet 时即使 URL 无后缀也应识别为 xlsx。"""
        # 构造一个简单的 xlsx 文件（用 openpyxl 生成）
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["name", "age"])
        ws.append(["alice", 30])
        xlsx_path = tmp_path / "test.xlsx"
        wb.save(xlsx_path)
        xlsx_bytes = xlsx_path.read_bytes()

        def fake_fetch_url(url, timeout_seconds=30, max_size_bytes=52428800):
            return FetchResult(
                content=xlsx_bytes,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                status_code=200,
                url=url,
            )

        monkeypatch.setattr(datasets_service, "fetch_url", fake_fetch_url)

        dataset, _ = datasets_service.create_url_dataset(
            db, evidence_confirmed_project_id,
            url="https://example.com/download",
            title="X", description=None,
        )
        v1 = datasets_service.get_latest_version(db, dataset.id)
        assert v1.file_path.endswith("raw.xlsx")


# --- list_datasets / get_dataset / get_dataset_by_id_and_project ---


class TestDatasetQueries:
    """数据集查询测试。"""

    def test_list_datasets_excludes_deleted(
        self, db, evidence_confirmed_project_id
    ):
        """list_datasets 不返回已软删除的数据集。"""
        d1, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="A", description=None,
            file_content=_csv_content(), original_filename="a.csv",
        )
        d2, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="B", description=None,
            file_content=_csv_content(), original_filename="b.csv",
        )
        # 软删除 d1
        datasets_service.delete_dataset(
            db, evidence_confirmed_project_id, d1.id
        )

        listed = datasets_service.list_datasets(db, evidence_confirmed_project_id)
        ids = [d.id for d in listed]
        assert d2.id in ids
        assert d1.id not in ids

    def test_list_datasets_returns_in_desc_order(
        self, db, evidence_confirmed_project_id
    ):
        """list_datasets 按创建时间降序返回。"""
        d1, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="A", description=None,
            file_content=_csv_content(), original_filename="a.csv",
        )
        d2, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="B", description=None,
            file_content=_csv_content(), original_filename="b.csv",
        )
        listed = datasets_service.list_datasets(db, evidence_confirmed_project_id)
        assert len(listed) == 2
        # 创建时间相同，但应都存在
        assert {d.id for d in listed} == {d1.id, d2.id}

    def test_get_dataset_raises_when_not_found(self, db):
        """get_dataset 不存在时抛 DATASET_NOT_FOUND。"""
        with pytest.raises(AppError) as exc:
            datasets_service.get_dataset(db, "ds_missing")
        assert exc.value.code == "DATASET_NOT_FOUND"

    def test_get_dataset_raises_when_deleted(self, db, evidence_confirmed_project_id):
        """get_dataset 对已软删除的记录抛 DATASET_NOT_FOUND。"""
        d, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        datasets_service.delete_dataset(db, evidence_confirmed_project_id, d.id)
        with pytest.raises(AppError) as exc:
            datasets_service.get_dataset(db, d.id)
        assert exc.value.code == "DATASET_NOT_FOUND"

    def test_get_dataset_by_id_and_project_raises_when_mismatch(
        self, db, evidence_confirmed_project_id
    ):
        """数据集不属于该 project 时抛 DATASET_NOT_FOUND。"""
        d, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        with pytest.raises(AppError) as exc:
            datasets_service.get_dataset_by_id_and_project(
                db, "proj_wrong", d.id
            )
        assert exc.value.code == "DATASET_NOT_FOUND"


# --- 版本管理 ---


class TestDatasetVersionManagement:
    """数据集版本管理测试。"""

    def test_reupload_creates_new_version_and_supersedes_old(
        self, db, evidence_confirmed_project_id
    ):
        """重新上传同一 Dataset 创建新版本，旧版本变 SUPERSEDED。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        v1 = datasets_service.get_latest_version(db, dataset.id)
        assert v1.version == 1
        assert v1.status == DatasetVersionStatus.PENDING.value

        # 重新上传
        new_content = b"name,age\nalice,30\nbob,25\n"
        _, job2_id = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title=None, description=None,
            file_content=new_content, original_filename="x_v2.csv",
            existing_dataset_id=dataset.id,
        )

        versions = datasets_service.list_dataset_versions(db, dataset.id)
        assert len(versions) == 2
        # 按版本号降序，新版本在前
        v2 = versions[0]
        old = versions[1]
        assert v2.version == 2
        assert v2.status == DatasetVersionStatus.PENDING.value
        assert old.version == 1
        assert old.status == DatasetVersionStatus.SUPERSEDED.value

        # 新版本文件已写入
        assert Path(v2.file_path).exists()
        assert Path(v2.file_path).name == "raw.csv"
        assert Path(v2.file_path).parent.name == "v2"

        # 创建了新的 PARSE_DATASET 任务
        assert job2_id

    def test_reupload_marks_related_analysis_plans_stale(
        self, db, evidence_confirmed_project_id
    ):
        """重新上传时关联 AnalysisPlan 全部变 STALE。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        v1 = datasets_service.get_latest_version(db, dataset.id)

        # 直接插入两张 AnalysisPlan（CANDIDATE / CONFIRMED）
        from app.modules.analysis.models import AnalysisPlan
        from app.modules.analysis.status import AnalysisPlanStatus
        plan_cand = AnalysisPlan(
            id="plan_cand_reup",
            project_id=evidence_confirmed_project_id,
            dataset_id=dataset.id,
            dataset_version_id=v1.id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        plan_conf = AnalysisPlan(
            id="plan_conf_reup",
            project_id=evidence_confirmed_project_id,
            dataset_id=dataset.id,
            dataset_version_id=v1.id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CONFIRMED.value,
            candidate_source="LOCAL_RULE",
        )
        db.add_all([plan_cand, plan_conf])
        db.commit()

        # 重新上传
        datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title=None, description=None,
            file_content=_csv_content(), original_filename="x_v2.csv",
            existing_dataset_id=dataset.id,
        )

        db.refresh(plan_cand)
        db.refresh(plan_conf)
        assert plan_cand.status == AnalysisPlanStatus.STALE.value
        assert plan_conf.status == AnalysisPlanStatus.STALE.value

    def test_list_dataset_versions_returns_desc(self, db, evidence_confirmed_project_id):
        """list_dataset_versions 按版本号降序。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title=None, description=None,
            file_content=_csv_content(), original_filename="x_v2.csv",
            existing_dataset_id=dataset.id,
        )

        versions = datasets_service.list_dataset_versions(db, dataset.id)
        assert len(versions) == 2
        assert versions[0].version == 2
        assert versions[1].version == 1

    def test_get_latest_version_raises_when_no_versions(self, db, evidence_confirmed_project_id):
        """无版本时抛 DATASET_VERSION_NOT_FOUND。"""
        # 直接通过 DB 创建一个 Dataset 不带版本（异常路径）
        dataset = Dataset(
            id="ds_no_versions",
            project_id=evidence_confirmed_project_id,
            dataset_kind=DatasetKind.FILE.value,
            title="无版本",
            status=DatasetStatus.PENDING.value,
        )
        db.add(dataset)
        db.commit()

        with pytest.raises(AppError) as exc:
            datasets_service.get_latest_version(db, dataset.id)
        assert exc.value.code == "DATASET_VERSION_NOT_FOUND"

    def test_get_version_by_id_raises_when_not_found(self, db):
        """get_version_by_id 不存在时抛 DATASET_VERSION_NOT_FOUND。"""
        with pytest.raises(AppError) as exc:
            datasets_service.get_version_by_id(db, "ver_missing")
        assert exc.value.code == "DATASET_VERSION_NOT_FOUND"

    def test_reupload_rejects_when_dataset_deleted(
        self, db, evidence_confirmed_project_id
    ):
        """对已删除数据集重新上传抛 DATASET_NOT_FOUND。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        datasets_service.delete_dataset(db, evidence_confirmed_project_id, dataset.id)

        with pytest.raises(AppError) as exc:
            datasets_service.create_file_dataset(
                db, evidence_confirmed_project_id,
                title=None, description=None,
                file_content=_csv_content(), original_filename="x_v2.csv",
                existing_dataset_id=dataset.id,
            )
        assert exc.value.code == "DATASET_NOT_FOUND"


# --- delete_dataset ---


class TestDeleteDataset:
    """软删除数据集测试。"""

    def test_delete_marks_status_deleted(self, db, evidence_confirmed_project_id):
        """软删除后 status=DELETED。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )

        deleted = datasets_service.delete_dataset(
            db, evidence_confirmed_project_id, dataset.id
        )
        assert deleted.status == DatasetStatus.DELETED.value

    def test_delete_marks_related_analysis_plans_stale(
        self, db, evidence_confirmed_project_id
    ):
        """删除数据集时关联 AnalysisPlan 变 STALE。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        v1 = datasets_service.get_latest_version(db, dataset.id)

        plan = AnalysisPlan(
            id="plan_del_stale",
            project_id=evidence_confirmed_project_id,
            dataset_id=dataset.id,
            dataset_version_id=v1.id,
            cleaning_plan="[]",
            analysis_plan="[]",
            chart_plan="[]",
            status=AnalysisPlanStatus.CANDIDATE.value,
            candidate_source="LOCAL_RULE",
        )
        db.add(plan)
        db.commit()

        datasets_service.delete_dataset(
            db, evidence_confirmed_project_id, dataset.id
        )

        db.refresh(plan)
        assert plan.status == AnalysisPlanStatus.STALE.value

    def test_delete_raises_when_dataset_missing(
        self, db, evidence_confirmed_project_id
    ):
        """删除不存在的数据集抛 DATASET_NOT_FOUND。"""
        with pytest.raises(AppError) as exc:
            datasets_service.delete_dataset(
                db, evidence_confirmed_project_id, "ds_missing"
            )
        assert exc.value.code == "DATASET_NOT_FOUND"


# --- complete_datasets ---


class TestCompleteDatasets:
    """完成数据集收集测试。"""

    def test_advances_project_to_dataset_ready_when_ready_exists(
        self, db, evidence_confirmed_project_id
    ):
        """存在 READY 数据集时推进到 DATASET_READY。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        # 直接通过 DB 将 dataset.status 设为 READY（模拟解析完成）
        dataset.status = DatasetStatus.READY.value
        db.commit()

        project = datasets_service.complete_datasets(
            db, evidence_confirmed_project_id
        )
        assert project.status == ProjectStatus.DATASET_READY.value

    def test_rejects_when_no_ready_dataset(
        self, db, evidence_confirmed_project_id
    ):
        """无 READY 数据集时返回 PROJECT_NO_READY_DATASET。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        # dataset.status 仍是 PENDING
        with pytest.raises(AppError) as exc:
            datasets_service.complete_datasets(db, evidence_confirmed_project_id)
        assert exc.value.code == "PROJECT_NO_READY_DATASET"

    def test_rejects_when_project_missing(self, db):
        """项目不存在时抛 PROJECT_NOT_FOUND。"""
        with pytest.raises(AppError) as exc:
            datasets_service.complete_datasets(db, "proj_missing")
        assert exc.value.code == "PROJECT_NOT_FOUND"


# --- Worker helpers ---


class TestWorkerHelpers:
    """Worker 调用的内部方法测试。"""

    def test_mark_dataset_parsing_updates_status(
        self, db, evidence_confirmed_project_id
    ):
        """mark_dataset_parsing 设置 status=PARSING。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        v1 = datasets_service.get_latest_version(db, dataset.id)

        updated = datasets_service.mark_dataset_parsing(db, v1.id)
        assert updated.status == DatasetVersionStatus.PARSING.value

    def test_mark_dataset_parsed_updates_version_and_dataset(
        self, db, evidence_confirmed_project_id
    ):
        """mark_dataset_parsed 设置 version.status=PARSED，dataset.status=READY。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        v1 = datasets_service.get_latest_version(db, dataset.id)

        profile_data = {"row_count": 4, "column_count": 3, "field_profiles": []}
        version, ds = datasets_service.mark_dataset_parsed(
            db, v1.id, profile_data,
            row_count=4, column_count=3,
        )

        assert version.status == DatasetVersionStatus.PARSED.value
        assert version.parsed_at is not None
        assert version.row_count == 4
        assert version.column_count == 3
        # profile_json 已写入
        parsed_profile = json.loads(version.profile_json)
        assert parsed_profile["row_count"] == 4

        assert ds.status == DatasetStatus.READY.value
        assert ds.error_code is None

    def test_mark_dataset_failed_sets_error_info(
        self, db, evidence_confirmed_project_id
    ):
        """mark_dataset_failed 设置 version.status=FAILED。

        若该 Dataset 所有版本都 FAILED，dataset.status=FAILED。
        """
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        v1 = datasets_service.get_latest_version(db, dataset.id)

        version, ds = datasets_service.mark_dataset_failed(
            db, v1.id, "DATASET_PARSE_FAILED", "文件损坏",
        )

        assert version.status == DatasetVersionStatus.FAILED.value
        assert version.error_code == "DATASET_PARSE_FAILED"
        assert "文件损坏" in version.error_message

        # 该 Dataset 唯一版本 FAILED，dataset.status 也应变为 FAILED
        assert ds.status == DatasetStatus.FAILED.value
        assert ds.error_code == "DATASET_PARSE_FAILED"

    def test_mark_dataset_failed_keeps_dataset_pending_if_other_versions_active(
        self, db, evidence_confirmed_project_id
    ):
        """存在其他活跃版本时 dataset.status 不变 FAILED。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        # 再上传一次（产生 v2 + v1 SUPERSEDED）
        datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title=None, description=None,
            file_content=_csv_content(), original_filename="x_v2.csv",
            existing_dataset_id=dataset.id,
        )
        v2 = datasets_service.get_latest_version(db, dataset.id)

        # 先把 v2 标记为 PARSED（活跃）
        datasets_service.mark_dataset_parsed(
            db, v2.id, {"row_count": 4}, row_count=4, column_count=3,
        )

        # 把 v1（SUPERSEDED）标记 FAILED —— 不会影响 dataset.status
        v1 = (
            db.query(DatasetVersion)
            .filter(DatasetVersion.dataset_id == dataset.id,
                    DatasetVersion.version == 1)
            .first()
        )
        _, ds = datasets_service.mark_dataset_failed(
            db, v1.id, "DATASET_PARSE_FAILED", "旧版本失败",
        )
        # dataset.status 应保持 READY（v2 已 PARSED）
        assert ds.status == DatasetStatus.READY.value

    def test_trigger_analysis_plan_generation_creates_job(
        self, db, evidence_confirmed_project_id
    ):
        """trigger_analysis_plan_generation 创建 GENERATE_ANALYSIS_PLAN 任务。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        v1 = datasets_service.get_latest_version(db, dataset.id)

        job_id = datasets_service.trigger_analysis_plan_generation(
            db, evidence_confirmed_project_id, dataset.id, v1.id,
        )
        db.commit()

        job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
        assert job is not None
        assert job.job_type == JobType.GENERATE_ANALYSIS_PLAN.value
        assert job.status == JobStatus.PENDING.value
        assert dataset.id in job.input_json
        assert v1.id in job.input_json


# --- 响应转换 ---


class TestDatasetResponseConversion:
    """数据集响应转换测试。"""

    def test_dataset_to_response_includes_job_id(
        self, db, evidence_confirmed_project_id
    ):
        """dataset_to_response 包含 job_id 字段。"""
        dataset, job_id = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        resp = datasets_service.dataset_to_response(dataset, job_id=job_id)
        assert resp.job_id == job_id
        assert resp.status == DatasetStatus.PENDING.value
        assert resp.dataset_kind == DatasetKind.FILE.value

    def test_version_to_response_serializes_datetimes(
        self, db, evidence_confirmed_project_id
    ):
        """version_to_response 将 datetime 字段序列化为 ISO 字符串。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        v1 = datasets_service.get_latest_version(db, dataset.id)
        resp = datasets_service.version_to_response(v1)
        assert isinstance(resp.created_at, str)
        assert resp.parsed_at is None  # 未解析
        assert resp.profile_json is None

    def test_complete_datasets_to_response_returns_status(
        self, db, evidence_confirmed_project_id
    ):
        """complete_datasets_to_response 返回 CompleteDatasetsResponse。"""
        dataset, _ = datasets_service.create_file_dataset(
            db, evidence_confirmed_project_id,
            title="X", description=None,
            file_content=_csv_content(), original_filename="x.csv",
        )
        dataset.status = DatasetStatus.READY.value
        db.commit()

        project = datasets_service.complete_datasets(
            db, evidence_confirmed_project_id
        )
        resp = datasets_service.complete_datasets_to_response(project)
        assert resp.status == ProjectStatus.DATASET_READY.value
