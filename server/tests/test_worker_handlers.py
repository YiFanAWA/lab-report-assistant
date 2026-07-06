"""Worker 处理器测试。

mock fetch_url 和 get_evidence_card_provider，避免真实网络和真实模型调用。
覆盖 handle_fetch_url、handle_parse_document、handle_generate_evidence 的
成功与失败路径，以及异常时调用 mark_failed 的错误处理。
"""

import hashlib
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
from app.modules.requirements import service as req_service
from app.modules.requirements.contracts import (
    TextSourceRequest,
    GeneratePlanRequest,
)
from app.modules.llm.local_rule_provider import LocalRuleRequirementDraftProvider
from app.modules.sources import service as sources_service
from app.modules.sources.models import Source, ParsedDocument, EvidenceCard
from app.modules.sources.status import (
    SourceKind,
    SourceStatus,
    EvidenceCardStatus,
)
from app.modules.jobs import service as job_service
from app.modules.jobs.status import JobType, JobStatus
from worker import handlers as worker_handlers


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
def provider():
    return LocalRuleRequirementDraftProvider()


@pytest.fixture
def confirmed_project_id(db, provider):
    """创建 REQUIREMENT_CONFIRMED 状态的项目。"""
    project = project_service.create_project(
        db, ProjectCreateRequest(name="胃病数据分析", topic="胃病数据分析")
    )
    src = req_service.add_text_source(
        db, project.id,
        TextSourceRequest(title="需求", text="完成数据清洗、统计分析和可视化"),
    )
    req_service.generate_plan(
        db, project.id, GeneratePlanRequest(source_id=src.id), provider
    )
    plan = req_service.get_current_plan(db, project.id)
    req_service.confirm_plan(db, project.id, plan.id)
    return project.id


def _make_pending_source(db, project_id: str, url: str = "https://example.com/a.html") -> Source:
    """构造一个 PENDING 状态的 URL 来源。"""
    source = Source(
        id="src_worker_test",
        project_id=project_id,
        source_kind=SourceKind.URL.value,
        title="Worker 测试来源",
        url=url,
        status=SourceStatus.PENDING.value,
    )
    db.add(source)
    db.commit()
    return source


def _make_fetched_html_source(
    db, project_id: str,
    content: bytes,
    content_type: str = "text/html",
) -> tuple[Source, str]:
    """构造一个 FETCHED 状态的 HTML 来源，写入真实文件供 parse_document 使用。"""
    from app.core.config import settings
    source_id = "src_worker_fetched"
    source = Source(
        id=source_id,
        project_id=project_id,
        source_kind=SourceKind.URL.value,
        title="已采集 HTML 来源",
        url="https://example.com/a.html",
        status=SourceStatus.FETCHED.value,
        content_type=content_type,
        content_hash=hashlib.sha256(content).hexdigest(),
    )
    db.add(source)
    db.commit()

    # 写入文件到受控工作区
    dest_dir = settings.project_data_root / project_id / "sources" / source_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = "raw.pdf" if "pdf" in content_type.lower() else "raw.html"
    dest_path = dest_dir / filename
    dest_path.write_bytes(content)
    source.file_path = str(dest_path)
    db.commit()
    return source, str(dest_path)


# --- handle_fetch_url ---


class TestHandleFetchUrl:
    """采集 URL 处理器测试。"""

    def test_html_success_path(
        self, db, confirmed_project_id, monkeypatch
    ):
        """HTML 成功路径：fetch_url 返回 200 text/html，Source 变 FETCHED，
        自动创建 PARSE_DOCUMENT 任务。"""
        source = _make_pending_source(db, confirmed_project_id)
        job = job_service.create_job(
            db, confirmed_project_id, JobType.FETCH_URL.value,
            {"source_id": source.id, "url": source.url},
        )
        db.commit()

        # mock fetch_url 返回 HTML
        html = "<html><head><title>测试页</title></head><body><p>这是公开网页的正文内容。</p></body></html>".encode("utf-8")
        captured_calls = []

        def fake_fetch_url(url, timeout_seconds=30, max_size_bytes=10485760):
            captured_calls.append({
                "url": url, "timeout": timeout_seconds, "max_size": max_size_bytes,
            })
            return FetchResult(
                content=html,
                content_type="text/html; charset=utf-8",
                status_code=200,
                url=url,
            )

        monkeypatch.setattr(worker_handlers, "fetch_url", fake_fetch_url)

        result = worker_handlers.handle_fetch_url(db, job)

        # 验证 Source 状态
        db.refresh(source)
        assert source.status == SourceStatus.FETCHED.value
        assert source.content_type == "text/html; charset=utf-8"
        assert source.content_hash == hashlib.sha256(html).hexdigest()
        assert source.fetched_at is not None
        assert source.file_path is not None
        assert Path(source.file_path).exists()

        # 验证 fetch_url 被正确参数调用
        assert captured_calls[0]["url"] == source.url

        # 验证自动创建了 PARSE_DOCUMENT 任务
        from app.modules.jobs.models import BackgroundJob
        parse_jobs = (
            db.query(BackgroundJob)
            .filter(
                BackgroundJob.project_id == confirmed_project_id,
                BackgroundJob.job_type == JobType.PARSE_DOCUMENT.value,
            )
            .all()
        )
        assert len(parse_jobs) == 1
        assert source.id in parse_jobs[0].input_json

        # 验证返回值
        assert "file_path" in result
        assert result["content_type"] == "text/html; charset=utf-8"

    def test_restricted_resource_marks_source_failed(
        self, db, confirmed_project_id, monkeypatch
    ):
        """受限资源返回 SOURCE_ACCESS_RESTRICTED，Source 变 FAILED。"""
        source = _make_pending_source(db, confirmed_project_id)
        job = job_service.create_job(
            db, confirmed_project_id, JobType.FETCH_URL.value,
            {"source_id": source.id, "url": source.url},
        )
        db.commit()

        def fake_fetch_url(url, timeout_seconds=30, max_size_bytes=10485760):
            raise FetchError("SOURCE_ACCESS_RESTRICTED", "来源需要登录")

        monkeypatch.setattr(worker_handlers, "fetch_url", fake_fetch_url)

        with pytest.raises(FetchError) as exc_info:
            worker_handlers.handle_fetch_url(db, job)
        assert exc_info.value.code == "SOURCE_ACCESS_RESTRICTED"

        # Source 应被标记为 FAILED
        db.refresh(source)
        assert source.status == SourceStatus.FAILED.value
        assert source.error_code == "SOURCE_ACCESS_RESTRICTED"

    def test_timeout_marks_source_failed(
        self, db, confirmed_project_id, monkeypatch
    ):
        """超时返回 FETCH_TIMEOUT，Source 变 FAILED。"""
        source = _make_pending_source(db, confirmed_project_id)
        job = job_service.create_job(
            db, confirmed_project_id, JobType.FETCH_URL.value,
            {"source_id": source.id, "url": source.url},
        )
        db.commit()

        def fake_fetch_url(url, timeout_seconds=30, max_size_bytes=10485760):
            raise FetchError("FETCH_TIMEOUT", "采集超时")

        monkeypatch.setattr(worker_handlers, "fetch_url", fake_fetch_url)

        with pytest.raises(FetchError):
            worker_handlers.handle_fetch_url(db, job)

        db.refresh(source)
        assert source.status == SourceStatus.FAILED.value
        assert source.error_code == "FETCH_TIMEOUT"


# --- handle_parse_document ---


class TestHandleParseDocument:
    """解析文档处理器测试。"""

    def test_html_success_path(self, db, confirmed_project_id):
        """HTML 成功路径：创建 ParsedDocument，Source 变 PARSED。"""
        html = """
        <html>
        <head><title>解析测试页</title>
        <meta name="description" content="测试页面元数据">
        </head>
        <body>
            <h1>研究背景</h1>
            <p>本节介绍胃病数据分析的研究背景与研究意义，覆盖常见统计分析流程。</p>
            <p>方法部分：采用描述性统计和可视化方法分析数据并生成图表。</p>
        </body>
        </html>
        """.encode("utf-8")
        source, file_path = _make_fetched_html_source(
            db, confirmed_project_id, html, content_type="text/html"
        )

        job = job_service.create_job(
            db, confirmed_project_id, JobType.PARSE_DOCUMENT.value,
            {"source_id": source.id},
        )
        db.commit()

        result = worker_handlers.handle_parse_document(db, job)

        # 验证返回值
        assert "parsed_document_id" in result
        assert result["text_length"] > 0

        # 验证 Source 状态
        db.refresh(source)
        assert source.status == SourceStatus.PARSED.value
        assert source.parsed_at is not None

        # 验证 ParsedDocument 已创建
        pd = (
            db.query(ParsedDocument)
            .filter(ParsedDocument.source_id == source.id)
            .first()
        )
        assert pd is not None
        assert pd.title == "解析测试页"
        assert "研究背景" in pd.parsed_text
        assert "采用描述性统计" in pd.parsed_text
        # 元数据中应包含 description
        assert "测试页面元数据" in (pd.metadata_json or "")

    def test_pdf_success_path(self, db, confirmed_project_id):
        """PDF 成功路径：提取文本，Source 变 PARSED。"""
        # 用 pypdf 构造一个带文本的 PDF
        from pypdf import PdfWriter
        from pypdf.generic import (
            DecodedStreamObject,
            DictionaryObject,
            NameObject,
        )
        import io as _io

        w = PdfWriter()
        page = w.add_blank_page(width=612, height=792)
        content_stream = DecodedStreamObject()
        # 文本需超过 50 字符以通过 PARSE_TEXT_EMPTY 阈值
        content_stream.set_data(
            b"BT /F1 12 Tf 72 720 Td (Hello PDF parser test with long enough content for threshold) Tj ET"
        )
        content_obj = w._add_object(content_stream)
        font = DictionaryObject()
        font[NameObject("/Type")] = NameObject("/Font")
        font[NameObject("/Subtype")] = NameObject("/Type1")
        font[NameObject("/BaseFont")] = NameObject("/Helvetica")
        font_obj = w._add_object(font)
        resources = DictionaryObject()
        font_dict = DictionaryObject()
        font_dict[NameObject("/F1")] = font_obj
        resources[NameObject("/Font")] = font_dict
        page[NameObject("/Contents")] = content_obj
        page[NameObject("/Resources")] = resources
        buf = _io.BytesIO()
        w.write(buf)
        pdf_bytes = buf.getvalue()

        source, _ = _make_fetched_html_source(
            db, confirmed_project_id, pdf_bytes, content_type="application/pdf"
        )

        job = job_service.create_job(
            db, confirmed_project_id, JobType.PARSE_DOCUMENT.value,
            {"source_id": source.id},
        )
        db.commit()

        result = worker_handlers.handle_parse_document(db, job)

        db.refresh(source)
        assert source.status == SourceStatus.PARSED.value

        pd = (
            db.query(ParsedDocument)
            .filter(ParsedDocument.source_id == source.id)
            .first()
        )
        assert pd is not None
        # PDF 文本应被提取
        assert "Hello" in pd.parsed_text or "hello" in pd.parsed_text.lower()

    def test_empty_text_returns_parse_text_empty(self, db, confirmed_project_id):
        """解析后文本为空（<50 字符）返回 PARSE_TEXT_EMPTY。"""
        # 构造一个正文非常短的 HTML
        html = "<html><head><title>T</title></head><body><p>短</p></body></html>".encode("utf-8")
        source, _ = _make_fetched_html_source(
            db, confirmed_project_id, html, content_type="text/html"
        )

        job = job_service.create_job(
            db, confirmed_project_id, JobType.PARSE_DOCUMENT.value,
            {"source_id": source.id},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_parse_document(db, job)
        assert exc_info.value.code == "PARSE_TEXT_EMPTY"

        # Source 应被标记为 FAILED
        db.refresh(source)
        assert source.status == SourceStatus.FAILED.value
        assert source.error_code == "PARSE_TEXT_EMPTY"

    def test_dynamic_page_returns_unsupported_dynamic(
        self, db, confirmed_project_id
    ):
        """检测到动态网页返回 SOURCE_UNSUPPORTED_DYNAMIC。"""
        # script 标签 > 5 且正文 < 100 字符
        scripts = b"<script></script>" * 6
        html = b"<html><body>" + scripts + b"<p>short</p></body></html>"
        source, _ = _make_fetched_html_source(
            db, confirmed_project_id, html, content_type="text/html"
        )

        job = job_service.create_job(
            db, confirmed_project_id, JobType.PARSE_DOCUMENT.value,
            {"source_id": source.id},
        )
        db.commit()

        with pytest.raises(FetchError) as exc_info:
            worker_handlers.handle_parse_document(db, job)
        assert exc_info.value.code == "SOURCE_UNSUPPORTED_DYNAMIC"

        db.refresh(source)
        assert source.status == SourceStatus.FAILED.value
        assert source.error_code == "SOURCE_UNSUPPORTED_DYNAMIC"


# --- handle_generate_evidence ---


class TestHandleGenerateEvidence:
    """生成证据卡片处理器测试。"""

    def test_generates_evidence_card_drafts(self, db, confirmed_project_id, monkeypatch):
        """使用 FakeEvidenceCardProvider 成功生成 3 张候选卡片。"""
        # 构造一个 PARSED 来源和 ParsedDocument
        source = Source(
            id="src_worker_evidence",
            project_id=confirmed_project_id,
            source_kind=SourceKind.URL.value,
            title="已解析来源",
            url="https://example.com/a.html",
            status=SourceStatus.PARSED.value,
            content_type="text/html",
            content_hash="hash_worker_ev_001",
        )
        db.add(source)
        pd = ParsedDocument(
            id="pd_worker_ev_001",
            source_id=source.id,
            project_id=confirmed_project_id,
            title="测试文档",
            parsed_text="背景：本节介绍研究背景。方法：采用统计方法。结果：分析显示相关。",
        )
        db.add(pd)
        db.commit()

        job = job_service.create_job(
            db, confirmed_project_id, JobType.GENERATE_EVIDENCE.value,
            {"source_id": source.id, "parsed_document_id": pd.id},
        )
        db.commit()

        # mock get_evidence_card_provider 返回 FakeEvidenceCardProvider
        from app.modules.llm.evidence_card_provider import FakeEvidenceCardProvider

        fake_provider = FakeEvidenceCardProvider()
        monkeypatch.setattr(
            worker_handlers, "get_evidence_card_provider",
            lambda: fake_provider,
        )

        result = worker_handlers.handle_generate_evidence(db, job)

        # 验证返回值
        assert result["card_count"] == 3

        # 验证 3 张 CANDIDATE 卡片已创建
        cards = (
            db.query(EvidenceCard)
            .filter(EvidenceCard.source_id == source.id)
            .all()
        )
        assert len(cards) == 3
        for card in cards:
            assert card.status == EvidenceCardStatus.CANDIDATE.value
            assert card.candidate_source == "LOCAL_RULE"
            assert card.parsed_document_id == pd.id

    def test_missing_parsed_document_raises(self, db, confirmed_project_id, monkeypatch):
        """找不到 ParsedDocument 时抛 PARSE_TEXT_EMPTY 并标记任务失败。"""
        source = Source(
            id="src_worker_no_pd",
            project_id=confirmed_project_id,
            source_kind=SourceKind.URL.value,
            title="无 PD 来源",
            url="https://example.com/a.html",
            status=SourceStatus.PARSED.value,
        )
        db.add(source)
        db.commit()

        job = job_service.create_job(
            db, confirmed_project_id, JobType.GENERATE_EVIDENCE.value,
            {"source_id": source.id, "parsed_document_id": "pd_missing"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_evidence(db, job)
        assert exc_info.value.code == "PARSE_TEXT_EMPTY"

    def test_uses_local_rule_provider_label(self, db, confirmed_project_id, monkeypatch):
        """生成的卡片 candidate_source 标记为 LOCAL_RULE，不伪装为 MODEL。"""
        source = Source(
            id="src_worker_label",
            project_id=confirmed_project_id,
            source_kind=SourceKind.URL.value,
            title="标签测试",
            url="https://example.com/a.html",
            status=SourceStatus.PARSED.value,
        )
        db.add(source)
        pd = ParsedDocument(
            id="pd_worker_label",
            source_id=source.id,
            project_id=confirmed_project_id,
            title="x",
            parsed_text="测试文本内容。",
        )
        db.add(pd)
        db.commit()

        job = job_service.create_job(
            db, confirmed_project_id, JobType.GENERATE_EVIDENCE.value,
            {"source_id": source.id, "parsed_document_id": pd.id},
        )
        db.commit()

        from app.modules.llm.evidence_card_provider import FakeEvidenceCardProvider
        monkeypatch.setattr(
            worker_handlers, "get_evidence_card_provider",
            lambda: FakeEvidenceCardProvider(),
        )

        worker_handlers.handle_generate_evidence(db, job)

        cards = (
            db.query(EvidenceCard)
            .filter(EvidenceCard.source_id == source.id)
            .all()
        )
        for card in cards:
            assert card.candidate_source == "LOCAL_RULE"
            assert card.candidate_source != "MODEL"


# --- HANDLERS 注册表 ---


class TestHandlersRegistry:
    """HANDLERS 注册表测试。"""

    def test_handlers_registry_maps_all_job_types(self):
        """HANDLERS 包含三种 job_type 的映射。"""
        assert worker_handlers.HANDLERS[JobType.FETCH_URL.value] is worker_handlers.handle_fetch_url
        assert worker_handlers.HANDLERS[JobType.PARSE_DOCUMENT.value] is worker_handlers.handle_parse_document
        assert worker_handlers.HANDLERS[JobType.GENERATE_EVIDENCE.value] is worker_handlers.handle_generate_evidence


# --- 错误处理 ---


class TestWorkerErrorHandling:
    """Worker 错误处理测试。"""

    def test_fetch_url_generic_exception_marks_source_failed(
        self, db, confirmed_project_id, monkeypatch
    ):
        """fetch_url 抛通用异常时 Source 标记为 FAILED（FETCH_FAILED）。"""
        source = _make_pending_source(db, confirmed_project_id)
        job = job_service.create_job(
            db, confirmed_project_id, JobType.FETCH_URL.value,
            {"source_id": source.id, "url": source.url},
        )
        db.commit()

        def fake_fetch_url(url, timeout_seconds=30, max_size_bytes=10485760):
            raise RuntimeError("unexpected error")

        monkeypatch.setattr(worker_handlers, "fetch_url", fake_fetch_url)

        with pytest.raises(FetchError) as exc_info:
            worker_handlers.handle_fetch_url(db, job)
        assert exc_info.value.code == "FETCH_FAILED"

        db.refresh(source)
        assert source.status == SourceStatus.FAILED.value
        assert source.error_code == "FETCH_FAILED"

    def test_parse_document_missing_file_marks_source_failed(
        self, db, confirmed_project_id
    ):
        """来源关联文件不存在时 Source 标记为 FAILED（PARSE_FAILED）。"""
        source = Source(
            id="src_worker_missing_file",
            project_id=confirmed_project_id,
            source_kind=SourceKind.URL.value,
            title="无文件来源",
            url="https://example.com/a.html",
            status=SourceStatus.FETCHED.value,
            content_type="text/html",
            file_path="/tmp/nonexistent_file.html",
        )
        db.add(source)
        db.commit()

        job = job_service.create_job(
            db, confirmed_project_id, JobType.PARSE_DOCUMENT.value,
            {"source_id": source.id},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_parse_document(db, job)
        assert exc_info.value.code == "PARSE_FAILED"

        db.refresh(source)
        assert source.status == SourceStatus.FAILED.value
        assert source.error_code == "PARSE_FAILED"

    def test_parse_document_no_file_path_marks_source_failed(
        self, db, confirmed_project_id
    ):
        """来源未关联 file_path 时 Source 标记为 FAILED。"""
        source = Source(
            id="src_worker_no_path",
            project_id=confirmed_project_id,
            source_kind=SourceKind.URL.value,
            title="无路径来源",
            url="https://example.com/a.html",
            status=SourceStatus.FETCHED.value,
            content_type="text/html",
            file_path=None,
        )
        db.add(source)
        db.commit()

        job = job_service.create_job(
            db, confirmed_project_id, JobType.PARSE_DOCUMENT.value,
            {"source_id": source.id},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_parse_document(db, job)
        assert exc_info.value.code == "PARSE_FAILED"

    def test_invalid_job_input_raises(self, db, confirmed_project_id):
        """任务缺少 source_id 时抛 JOB_INPUT_INVALID。"""
        job = job_service.create_job(
            db, confirmed_project_id, JobType.FETCH_URL.value,
            {"url": "https://example.com"},  # 缺 source_id
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_fetch_url(db, job)
        assert exc_info.value.code == "JOB_INPUT_INVALID"


# --- 数据集测试辅助 ---

# 触发 datasets/analysis models 注册到 Base.metadata，
# 确保 db fixture 的 create_all 包含这些表
from app.modules.datasets.models import Dataset, DatasetVersion  # noqa: F401,E402
from app.modules.analysis.models import AnalysisPlan  # noqa: F401,E402


def _make_evidence_confirmed_project(db) -> str:
    """创建 EVIDENCE_CONFIRMED 状态项目，用于数据集测试前置条件。

    直接通过 DB 设置状态，跳过前序流程（已在 sources/evidence 测试中覆盖）。
    """
    project = project_service.create_project(
        db, ProjectCreateRequest(name="胃病数据分析", topic="胃病数据分析")
    )
    project.status = ProjectStatus.EVIDENCE_CONFIRMED.value
    db.commit()
    db.refresh(project)
    return project.id


def _csv_content() -> bytes:
    """构造合法 CSV 内容：4 行 3 列，含 1 个重复行和 1 个缺失值。"""
    return (
        b"name,age,score\n"
        b"alice,30,90.5\n"
        b"bob,25,85.0\n"
        b"alice,30,90.5\n"
        b"carol,,78.0\n"
    )


def _make_xlsx_bytes() -> bytes:
    """构造合法 XLSX 内容：3 行 3 列，含 1 个缺失值。"""
    import io
    import pandas as pd
    df = pd.DataFrame({
        "name": ["alice", "bob", "carol"],
        "age": [30, 25, None],
        "score": [90.5, 85.0, 78.0],
    })
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _make_pending_dataset_version(
    db, project_id: str, content: bytes, ext: str = "csv"
):
    """构造 PENDING 状态的 Dataset + DatasetVersion，文件已写入受控工作区。"""
    from app.core.config import settings
    from app.modules.datasets.models import (
        Dataset, DatasetVersion, _uid, _now,
    )
    from app.modules.datasets.status import (
        DatasetKind, DatasetStatus, DatasetVersionStatus,
    )

    dataset_id = _uid()
    dataset = Dataset(
        id=dataset_id,
        project_id=project_id,
        dataset_kind=DatasetKind.FILE.value,
        title="测试数据集",
        status=DatasetStatus.PENDING.value,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(dataset)
    db.flush()

    version = DatasetVersion(
        id=_uid(),
        dataset_id=dataset_id,
        project_id=project_id,
        version=1,
        status=DatasetVersionStatus.PENDING.value,
        file_path="placeholder",  # 占位，下面设置真实路径
        file_size_bytes=len(content),
        created_at=_now(),
    )
    db.add(version)
    db.flush()

    dest_dir = (settings.project_data_root / project_id
                / "datasets" / dataset_id / "v1")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"raw.{ext}"
    dest_path.write_bytes(content)
    version.file_path = str(dest_path)
    db.commit()
    db.refresh(version)
    return dataset, version


def _seed_parsed_dataset(db) -> tuple[str, str, str]:
    """构造已解析数据集：项目 DATASET_READY，Dataset READY，Version PARSED。

    使用真实 parse_dataset 解析 CSV 并写入 profile_json，确保
    handle_generate_analysis_plan 能反序列化 profile。
    """
    from app.modules.datasets import service as dataset_service
    from app.modules.datasets.models import DatasetVersion
    from app.modules.projects.models import Project
    from app.infrastructure.parsers.dataset_parser import (
        parse_dataset, profile_to_dict,
    )

    project_id = _make_evidence_confirmed_project(db)
    content = _csv_content()
    dataset, version = _make_pending_dataset_version(db, project_id, content, "csv")

    result = parse_dataset(version.file_path, "csv")
    profile_dict = profile_to_dict(result.profile)
    dataset_service.mark_dataset_parsed(
        db,
        version_id=version.id,
        profile_data=profile_dict,
        row_count=result.profile.row_count,
        column_count=result.profile.column_count,
    )

    # 推进项目状态到 DATASET_READY（advance_project_to_planned 的前置条件）
    project = db.query(Project).filter(Project.id == project_id).first()
    project.status = ProjectStatus.DATASET_READY.value
    db.commit()

    db.refresh(version)
    db.refresh(dataset)
    return project_id, dataset.id, version.id


# --- handle_parse_dataset ---


class TestHandleParseDataset:
    """数据集解析处理器测试。

    覆盖 CSV/XLSX 成功路径、解析失败、文件不存在、扩展名不支持、
    PARSING 中间状态、自动触发 GENERATE_ANALYSIS_PLAN。
    """

    def test_csv_success_path(self, db):
        """CSV 成功路径：version 变 PARSED，Dataset 变 READY，自动触发 GENERATE_ANALYSIS_PLAN。"""
        from app.modules.datasets.models import Dataset, DatasetVersion
        from app.modules.datasets.status import (
            DatasetStatus, DatasetVersionStatus,
        )
        from app.modules.jobs.models import BackgroundJob

        project_id = _make_evidence_confirmed_project(db)
        content = _csv_content()
        dataset, version = _make_pending_dataset_version(
            db, project_id, content, "csv"
        )
        job = job_service.create_job(
            db, project_id, JobType.PARSE_DATASET.value,
            {"dataset_id": dataset.id, "version_id": version.id,
             "file_extension": "csv"},
        )
        db.commit()

        result = worker_handlers.handle_parse_dataset(db, job)

        # 验证返回值
        assert result["row_count"] == 4
        assert result["column_count"] == 3
        assert result["quality_score"] >= 0
        assert result["analysis_plan_job_id"]

        # 验证 version 和 dataset 状态
        db.refresh(version)
        db.refresh(dataset)
        assert version.status == DatasetVersionStatus.PARSED.value
        assert version.profile_json is not None
        assert version.row_count == 4
        assert version.column_count == 3
        assert version.parsed_at is not None
        assert dataset.status == DatasetStatus.READY.value

        # 验证自动创建了 GENERATE_ANALYSIS_PLAN 任务
        plan_jobs = (
            db.query(BackgroundJob)
            .filter(
                BackgroundJob.project_id == project_id,
                BackgroundJob.job_type == JobType.GENERATE_ANALYSIS_PLAN.value,
            )
            .all()
        )
        assert len(plan_jobs) == 1
        assert version.id in plan_jobs[0].input_json
        assert dataset.id in plan_jobs[0].input_json

    def test_xlsx_success_path(self, db):
        """XLSX 成功路径：解析为 PARSED，Dataset 变 READY。"""
        from app.modules.datasets.models import Dataset, DatasetVersion
        from app.modules.datasets.status import (
            DatasetStatus, DatasetVersionStatus,
        )

        project_id = _make_evidence_confirmed_project(db)
        content = _make_xlsx_bytes()
        dataset, version = _make_pending_dataset_version(
            db, project_id, content, "xlsx"
        )
        job = job_service.create_job(
            db, project_id, JobType.PARSE_DATASET.value,
            {"dataset_id": dataset.id, "version_id": version.id,
             "file_extension": "xlsx"},
        )
        db.commit()

        result = worker_handlers.handle_parse_dataset(db, job)

        db.refresh(version)
        db.refresh(dataset)
        assert version.status == DatasetVersionStatus.PARSED.value
        assert dataset.status == DatasetStatus.READY.value
        assert result["column_count"] == 3
        assert result["row_count"] == 3
        assert version.profile_json is not None

    def test_missing_dataset_id_raises(self, db):
        """任务缺少 dataset_id 时抛 JOB_INPUT_INVALID。"""
        project_id = _make_evidence_confirmed_project(db)
        job = job_service.create_job(
            db, project_id, JobType.PARSE_DATASET.value,
            {"version_id": "v_xxx", "file_extension": "csv"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_parse_dataset(db, job)
        assert exc_info.value.code == "JOB_INPUT_INVALID"

    def test_missing_version_id_raises(self, db):
        """任务缺少 version_id 时抛 JOB_INPUT_INVALID。"""
        project_id = _make_evidence_confirmed_project(db)
        job = job_service.create_job(
            db, project_id, JobType.PARSE_DATASET.value,
            {"dataset_id": "ds_xxx", "file_extension": "csv"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_parse_dataset(db, job)
        assert exc_info.value.code == "JOB_INPUT_INVALID"

    def test_version_not_found_raises(self, db):
        """version_id 不存在时抛 DATASET_VERSION_NOT_FOUND。"""
        project_id = _make_evidence_confirmed_project(db)
        job = job_service.create_job(
            db, project_id, JobType.PARSE_DATASET.value,
            {"dataset_id": "ds_xxx", "version_id": "v_missing",
             "file_extension": "csv"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_parse_dataset(db, job)
        assert exc_info.value.code == "DATASET_VERSION_NOT_FOUND"

    def test_file_not_exist_marks_version_failed(self, db):
        """文件不存在时 version 变 FAILED，抛 DATASET_PARSE_FAILED。"""
        from app.modules.datasets.status import DatasetVersionStatus

        project_id = _make_evidence_confirmed_project(db)
        content = _csv_content()
        dataset, version = _make_pending_dataset_version(
            db, project_id, content, "csv"
        )
        # 删除文件模拟丢失
        Path(version.file_path).unlink()
        job = job_service.create_job(
            db, project_id, JobType.PARSE_DATASET.value,
            {"dataset_id": dataset.id, "version_id": version.id,
             "file_extension": "csv"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_parse_dataset(db, job)
        assert exc_info.value.code == "DATASET_PARSE_FAILED"

        db.refresh(version)
        assert version.status == DatasetVersionStatus.FAILED.value
        assert version.error_code == "DATASET_PARSE_FAILED"

    def test_unsupported_extension_raises_parse_error(self, db):
        """不支持的扩展名触发 DatasetParseError，version 变 FAILED。"""
        from app.modules.datasets.status import DatasetVersionStatus
        from app.infrastructure.parsers.dataset_parser import DatasetParseError

        project_id = _make_evidence_confirmed_project(db)
        content = b"some text content"
        dataset, version = _make_pending_dataset_version(
            db, project_id, content, "csv"
        )
        job = job_service.create_job(
            db, project_id, JobType.PARSE_DATASET.value,
            {"dataset_id": dataset.id, "version_id": version.id,
             "file_extension": "txt"},
        )
        db.commit()

        with pytest.raises(DatasetParseError) as exc_info:
            worker_handlers.handle_parse_dataset(db, job)
        assert exc_info.value.code == "DATASET_FILE_UNSUPPORTED"

        db.refresh(version)
        assert version.status == DatasetVersionStatus.FAILED.value
        assert version.error_code == "DATASET_FILE_UNSUPPORTED"

    def test_empty_file_raises_parse_error(self, db):
        """空文件触发 DatasetParseError，version 变 FAILED。"""
        from app.modules.datasets.status import DatasetVersionStatus
        from app.infrastructure.parsers.dataset_parser import DatasetParseError

        project_id = _make_evidence_confirmed_project(db)
        dataset, version = _make_pending_dataset_version(
            db, project_id, b"", "csv"
        )
        job = job_service.create_job(
            db, project_id, JobType.PARSE_DATASET.value,
            {"dataset_id": dataset.id, "version_id": version.id,
             "file_extension": "csv"},
        )
        db.commit()

        with pytest.raises(DatasetParseError):
            worker_handlers.handle_parse_dataset(db, job)

        db.refresh(version)
        assert version.status == DatasetVersionStatus.FAILED.value

    def test_marks_version_parsing_intermediate_state(self, db, monkeypatch):
        """解析过程中版本状态先变为 PARSING（通过 mock 捕获中间状态）。"""
        from app.modules.datasets.models import DatasetVersion
        from app.modules.datasets.status import DatasetVersionStatus

        project_id = _make_evidence_confirmed_project(db)
        content = _csv_content()
        dataset, version = _make_pending_dataset_version(
            db, project_id, content, "csv"
        )
        version_id = version.id
        job = job_service.create_job(
            db, project_id, JobType.PARSE_DATASET.value,
            {"dataset_id": dataset.id, "version_id": version_id,
             "file_extension": "csv"},
        )
        db.commit()

        captured_status = []
        original_parse = worker_handlers.parse_dataset

        def spy_parse(file_path, file_extension):
            v = (
                db.query(DatasetVersion)
                .filter(DatasetVersion.id == version_id)
                .first()
            )
            captured_status.append(v.status)
            return original_parse(file_path, file_extension)

        monkeypatch.setattr(worker_handlers, "parse_dataset", spy_parse)

        worker_handlers.handle_parse_dataset(db, job)

        # 在 parse_dataset 被调用时，version 应已标记为 PARSING
        assert captured_status[0] == DatasetVersionStatus.PARSING.value

    def test_return_value_includes_quality_score(self, db):
        """返回值包含 quality_score 字段且在 0-100 范围内。"""
        project_id = _make_evidence_confirmed_project(db)
        content = _csv_content()
        dataset, version = _make_pending_dataset_version(
            db, project_id, content, "csv"
        )
        job = job_service.create_job(
            db, project_id, JobType.PARSE_DATASET.value,
            {"dataset_id": dataset.id, "version_id": version.id,
             "file_extension": "csv"},
        )
        db.commit()

        result = worker_handlers.handle_parse_dataset(db, job)

        assert "quality_score" in result
        assert isinstance(result["quality_score"], (int, float))
        assert 0 <= result["quality_score"] <= 100


# --- handle_generate_analysis_plan ---


class TestHandleGenerateAnalysisPlan:
    """生成分析方案候选处理器测试。

    覆盖成功生成、provider 异常、save_analysis_plan_draft 调用、
    advance_project_to_planned 调用、profile_json 损坏等场景。
    """

    def test_success_path(self, db, monkeypatch):
        """成功路径：生成 AnalysisPlan(CANDIDATE)，项目状态推进到 ANALYSIS_PLANNED。"""
        from app.modules.analysis.models import AnalysisPlan
        from app.modules.analysis.status import AnalysisPlanStatus
        from app.modules.projects.models import Project
        from app.modules.llm.analysis_plan_provider import FakeAnalysisPlanProvider

        project_id, dataset_id, version_id = _seed_parsed_dataset(db)
        job = job_service.create_job(
            db, project_id, JobType.GENERATE_ANALYSIS_PLAN.value,
            {"dataset_id": dataset_id, "dataset_version_id": version_id},
        )
        db.commit()

        monkeypatch.setattr(
            worker_handlers, "get_analysis_plan_provider",
            lambda: FakeAnalysisPlanProvider(),
        )

        result = worker_handlers.handle_generate_analysis_plan(db, job)

        # 验证返回值
        assert result["plan_id"]
        assert result["cleaning_plan_count"] >= 1
        assert result["analysis_plan_count"] >= 1
        assert result["chart_plan_count"] >= 1

        # 验证 AnalysisPlan 创建
        plans = (
            db.query(AnalysisPlan)
            .filter(AnalysisPlan.dataset_version_id == version_id)
            .all()
        )
        assert len(plans) == 1
        assert plans[0].status == AnalysisPlanStatus.CANDIDATE.value
        assert plans[0].candidate_source == "LOCAL_RULE"
        assert plans[0].cleaning_plan  # 非空 JSON 字符串
        assert plans[0].analysis_plan
        assert plans[0].chart_plan

        # 验证项目状态推进到 ANALYSIS_PLANNED
        project = db.query(Project).filter(Project.id == project_id).first()
        assert project.status == ProjectStatus.ANALYSIS_PLANNED.value

    def test_missing_dataset_id_raises(self, db):
        """任务缺少 dataset_id 时抛 JOB_INPUT_INVALID。"""
        project_id = _make_evidence_confirmed_project(db)
        job = job_service.create_job(
            db, project_id, JobType.GENERATE_ANALYSIS_PLAN.value,
            {"dataset_version_id": "v_xxx"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_analysis_plan(db, job)
        assert exc_info.value.code == "JOB_INPUT_INVALID"

    def test_missing_dataset_version_id_raises(self, db):
        """任务缺少 dataset_version_id 时抛 JOB_INPUT_INVALID。"""
        project_id = _make_evidence_confirmed_project(db)
        job = job_service.create_job(
            db, project_id, JobType.GENERATE_ANALYSIS_PLAN.value,
            {"dataset_id": "ds_xxx"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_analysis_plan(db, job)
        assert exc_info.value.code == "JOB_INPUT_INVALID"

    def test_version_not_found_raises(self, db):
        """version_id 不存在时抛 DATASET_VERSION_NOT_FOUND。"""
        project_id = _make_evidence_confirmed_project(db)
        job = job_service.create_job(
            db, project_id, JobType.GENERATE_ANALYSIS_PLAN.value,
            {"dataset_id": "ds_xxx", "dataset_version_id": "v_missing"},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_analysis_plan(db, job)
        assert exc_info.value.code == "DATASET_VERSION_NOT_FOUND"

    def test_version_not_parsed_raises(self, db):
        """version 无 profile_json 时抛 DATASET_NOT_PARSED。"""
        project_id = _make_evidence_confirmed_project(db)
        content = _csv_content()
        dataset, version = _make_pending_dataset_version(
            db, project_id, content, "csv"
        )
        # version 是 PENDING 状态，没有 profile_json
        job = job_service.create_job(
            db, project_id, JobType.GENERATE_ANALYSIS_PLAN.value,
            {"dataset_id": dataset.id, "dataset_version_id": version.id},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_analysis_plan(db, job)
        assert exc_info.value.code == "DATASET_NOT_PARSED"

    def test_corrupted_profile_json_raises(self, db, monkeypatch):
        """profile_json 损坏时抛 DATASET_PARSE_FAILED。"""
        from app.modules.datasets.models import DatasetVersion
        from app.modules.llm.analysis_plan_provider import FakeAnalysisPlanProvider

        project_id, dataset_id, version_id = _seed_parsed_dataset(db)
        # 篡改 profile_json 为非法 JSON
        version = (
            db.query(DatasetVersion)
            .filter(DatasetVersion.id == version_id)
            .first()
        )
        version.profile_json = "{invalid json"
        db.commit()

        monkeypatch.setattr(
            worker_handlers, "get_analysis_plan_provider",
            lambda: FakeAnalysisPlanProvider(),
        )

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_ANALYSIS_PLAN.value,
            {"dataset_id": dataset_id, "dataset_version_id": version_id},
        )
        db.commit()

        with pytest.raises(AppError) as exc_info:
            worker_handlers.handle_generate_analysis_plan(db, job)
        assert exc_info.value.code == "DATASET_PARSE_FAILED"

    def test_provider_exception_propagates(self, db, monkeypatch):
        """LLM provider 抛异常时异常向上传播，不静默吞错。"""
        project_id, dataset_id, version_id = _seed_parsed_dataset(db)
        job = job_service.create_job(
            db, project_id, JobType.GENERATE_ANALYSIS_PLAN.value,
            {"dataset_id": dataset_id, "dataset_version_id": version_id},
        )
        db.commit()

        class _BadProvider:
            def source_label(self):
                return "LOCAL_RULE"

            def generate(self, profile):
                raise RuntimeError("provider crashed")

        monkeypatch.setattr(
            worker_handlers, "get_analysis_plan_provider",
            lambda: _BadProvider(),
        )

        with pytest.raises(RuntimeError):
            worker_handlers.handle_generate_analysis_plan(db, job)

    def test_advances_project_to_planned(self, db, monkeypatch):
        """advance_project_to_planned 被调用：项目从 DATASET_READY 推进到 ANALYSIS_PLANNED。"""
        from app.modules.projects.models import Project
        from app.modules.llm.analysis_plan_provider import FakeAnalysisPlanProvider

        project_id, dataset_id, version_id = _seed_parsed_dataset(db)
        # _seed_parsed_dataset 已将项目设为 DATASET_READY
        project = db.query(Project).filter(Project.id == project_id).first()
        assert project.status == ProjectStatus.DATASET_READY.value

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_ANALYSIS_PLAN.value,
            {"dataset_id": dataset_id, "dataset_version_id": version_id},
        )
        db.commit()

        monkeypatch.setattr(
            worker_handlers, "get_analysis_plan_provider",
            lambda: FakeAnalysisPlanProvider(),
        )

        worker_handlers.handle_generate_analysis_plan(db, job)

        db.refresh(project)
        assert project.status == ProjectStatus.ANALYSIS_PLANNED.value

    def test_does_not_advance_if_already_past_planned(self, db, monkeypatch):
        """项目已超过 ANALYSIS_PLANNED 状态时不回退。"""
        from app.modules.projects.models import Project
        from app.modules.llm.analysis_plan_provider import FakeAnalysisPlanProvider

        project_id, dataset_id, version_id = _seed_parsed_dataset(db)
        # 推进项目状态到 ANALYSIS_CONFIRMED（已超过 ANALYSIS_PLANNED）
        project = db.query(Project).filter(Project.id == project_id).first()
        project.status = ProjectStatus.ANALYSIS_CONFIRMED.value
        db.commit()

        job = job_service.create_job(
            db, project_id, JobType.GENERATE_ANALYSIS_PLAN.value,
            {"dataset_id": dataset_id, "dataset_version_id": version_id},
        )
        db.commit()

        monkeypatch.setattr(
            worker_handlers, "get_analysis_plan_provider",
            lambda: FakeAnalysisPlanProvider(),
        )

        worker_handlers.handle_generate_analysis_plan(db, job)

        db.refresh(project)
        # 不应回退到 ANALYSIS_PLANNED
        assert project.status == ProjectStatus.ANALYSIS_CONFIRMED.value

    def test_uses_local_rule_label_not_model(self, db, monkeypatch):
        """生成方案的 candidate_source 标记为 LOCAL_RULE，不伪装为 MODEL。"""
        from app.modules.analysis.models import AnalysisPlan
        from app.modules.llm.analysis_plan_provider import FakeAnalysisPlanProvider

        project_id, dataset_id, version_id = _seed_parsed_dataset(db)
        job = job_service.create_job(
            db, project_id, JobType.GENERATE_ANALYSIS_PLAN.value,
            {"dataset_id": dataset_id, "dataset_version_id": version_id},
        )
        db.commit()

        monkeypatch.setattr(
            worker_handlers, "get_analysis_plan_provider",
            lambda: FakeAnalysisPlanProvider(),
        )

        worker_handlers.handle_generate_analysis_plan(db, job)

        plan = (
            db.query(AnalysisPlan)
            .filter(AnalysisPlan.dataset_version_id == version_id)
            .first()
        )
        assert plan.candidate_source == "LOCAL_RULE"
        assert plan.candidate_source != "MODEL"


# --- HANDLERS 注册表扩展 ---


class TestHandlersRegistryExtended:
    """HANDLERS 注册表扩展测试：覆盖新增的 PARSE_DATASET 和 GENERATE_ANALYSIS_PLAN。"""

    def test_handlers_registry_includes_dataset_handlers(self):
        """HANDLERS 包含 PARSE_DATASET 和 GENERATE_ANALYSIS_PLAN 的映射。"""
        assert (
            worker_handlers.HANDLERS[JobType.PARSE_DATASET.value]
            is worker_handlers.handle_parse_dataset
        )
        assert (
            worker_handlers.HANDLERS[JobType.GENERATE_ANALYSIS_PLAN.value]
            is worker_handlers.handle_generate_analysis_plan
        )
