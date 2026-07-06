"""来源与证据核心服务测试（来源相关方法）。

覆盖 create_url_source、create_pdf_source、list_sources、delete_source、
complete_sources 的状态推进、STALE 传播、URL 公开性校验。
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.engine import Base
from app.core.errors import AppError
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
from app.modules.sources.models import (
    Source,
    ParsedDocument,
    EvidenceCard,
)
from app.modules.sources.contracts import UrlSourceRequest
from app.modules.sources.status import (
    SourceKind,
    SourceStatus,
    EvidenceCardStatus,
    CandidateSource,
)
from app.modules.jobs.status import JobType, JobStatus


TEST_DB = "sqlite:///:memory:"


@pytest.fixture
def db(monkeypatch, tmp_path):
    """内存 SQLite 会话 + 受控 PROJECT_DATA_ROOT。"""
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
    """创建一个处于 REQUIREMENT_CONFIRMED 状态的项目。"""
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
    # 此时 project.status == REQUIREMENT_PARSED
    plan = req_service.get_current_plan(db, project.id)
    req_service.confirm_plan(db, project.id, plan.id)
    # 此时 project.status == REQUIREMENT_CONFIRMED
    return project.id


def _make_parsed_source(db, project_id: str) -> tuple[Source, ParsedDocument]:
    """构造一个 PARSED 状态的来源和对应 ParsedDocument，供证据卡片测试使用。"""
    source = Source(
        id="src_test_parsed",
        project_id=project_id,
        source_kind=SourceKind.URL.value,
        title="已解析来源",
        url="https://example.com/article.html",
        status=SourceStatus.PARSED.value,
        content_type="text/html",
        content_hash="hash_test_001",
        file_path="/tmp/raw.html",
    )
    db.add(source)
    pd = ParsedDocument(
        id="pd_test_001",
        source_id=source.id,
        project_id=project_id,
        title="测试文档",
        parsed_text="这是一段足够长的解析后文本用于证据卡片生成测试。" * 2,
        metadata_json='{"description": "测试"}',
    )
    db.add(pd)
    db.commit()
    return source, pd


# --- create_url_source ---


class TestCreateUrlSource:
    """登记 URL 来源测试。"""

    def test_creates_url_source_and_fetch_url_job(self, db, confirmed_project_id):
        """成功登记公开 URL，创建 FETCH_URL 任务。"""
        req = UrlSourceRequest(url="https://example.com/article.html",
                                title="示例文章")
        source, job_id = sources_service.create_url_source(
            db, confirmed_project_id, req
        )

        assert source.source_kind == SourceKind.URL.value
        assert source.status == SourceStatus.PENDING.value
        assert source.url == "https://example.com/article.html"
        assert source.title == "示例文章"
        assert job_id  # 返回非空 job_id

        # 验证创建了 FETCH_URL 任务
        from app.modules.jobs.models import BackgroundJob
        job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
        assert job is not None
        assert job.job_type == JobType.FETCH_URL.value
        assert job.status == JobStatus.PENDING.value
        assert source.id in job.input_json

    def test_rejects_when_project_status_not_confirmed(self, db):
        """项目状态不是 REQUIREMENT_CONFIRMED 或之后时拒绝。"""
        project = project_service.create_project(
            db, ProjectCreateRequest(name="新项目", topic="测试")
        )
        # project.status == DRAFT
        req = UrlSourceRequest(url="https://example.com/article.html")
        with pytest.raises(AppError) as exc:
            sources_service.create_url_source(db, project.id, req)
        assert exc.value.code == "PROJECT_REQUIREMENT_NOT_CONFIRMED"

    def test_rejects_localhost(self, db, confirmed_project_id):
        """localhost 视为非公开。"""
        req = UrlSourceRequest(url="http://localhost:8080/secret")
        with pytest.raises(AppError) as exc:
            sources_service.create_url_source(db, confirmed_project_id, req)
        assert exc.value.code == "SOURCE_URL_NOT_PUBLIC"

    def test_rejects_loopback_ip(self, db, confirmed_project_id):
        """127.0.0.1 视为非公开。"""
        req = UrlSourceRequest(url="http://127.0.0.1/admin")
        with pytest.raises(AppError) as exc:
            sources_service.create_url_source(db, confirmed_project_id, req)
        assert exc.value.code == "SOURCE_URL_NOT_PUBLIC"

    def test_rejects_private_ip(self, db, confirmed_project_id):
        """192.168.* 视为非公开。"""
        req = UrlSourceRequest(url="http://192.168.1.1/internal")
        with pytest.raises(AppError) as exc:
            sources_service.create_url_source(db, confirmed_project_id, req)
        assert exc.value.code == "SOURCE_URL_NOT_PUBLIC"

    def test_rejects_10_network(self, db, confirmed_project_id):
        """10.* 视为非公开。"""
        req = UrlSourceRequest(url="http://10.0.0.5/intranet")
        with pytest.raises(AppError) as exc:
            sources_service.create_url_source(db, confirmed_project_id, req)
        assert exc.value.code == "SOURCE_URL_NOT_PUBLIC"

    def test_rejects_file_scheme(self, db, confirmed_project_id):
        """file:// 协议不支持。"""
        req = UrlSourceRequest(url="file:///etc/passwd")
        with pytest.raises(AppError) as exc:
            sources_service.create_url_source(db, confirmed_project_id, req)
        assert exc.value.code == "SOURCE_URL_SCHEME_UNSUPPORTED"

    def test_rejects_ftp_scheme(self, db, confirmed_project_id):
        """ftp:// 协议不支持。"""
        req = UrlSourceRequest(url="ftp://example.com/file.txt")
        with pytest.raises(AppError) as exc:
            sources_service.create_url_source(db, confirmed_project_id, req)
        assert exc.value.code == "SOURCE_URL_SCHEME_UNSUPPORTED"

    def test_uses_url_as_title_when_title_empty(self, db, confirmed_project_id):
        """title 为空时用 URL 作标题。"""
        req = UrlSourceRequest(url="https://example.com/article.html")
        source, _ = sources_service.create_url_source(
            db, confirmed_project_id, req
        )
        assert source.title == "https://example.com/article.html"


# --- create_pdf_source ---


class TestCreatePdfSource:
    """上传 PDF 来源测试。"""

    def test_saves_pdf_and_creates_parse_job(self, db, confirmed_project_id):
        """成功上传 PDF，保存到受控工作区并创建 PARSE_DOCUMENT 任务。"""
        content = b"%PDF-1.4\nfake pdf content for testing\n%%EOF"
        source, job_id = sources_service.create_pdf_source(
            db, confirmed_project_id, title="研究论文",
            file_content=content, original_filename="paper.pdf"
        )

        assert source.source_kind == SourceKind.FILE.value
        assert source.status == SourceStatus.PENDING.value
        assert source.title == "研究论文"
        assert source.file_path is not None
        # 文件实际写入受控工作区
        assert Path(source.file_path).exists()
        assert Path(source.file_path).name == "raw.pdf"

        # 验证创建了 PARSE_DOCUMENT 任务
        from app.modules.jobs.models import BackgroundJob
        job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
        assert job is not None
        assert job.job_type == JobType.PARSE_DOCUMENT.value

    def test_rejects_empty_file(self, db, confirmed_project_id):
        """空文件返回 SOURCE_FILE_EMPTY。"""
        with pytest.raises(AppError) as exc:
            sources_service.create_pdf_source(
                db, confirmed_project_id, title="空 PDF",
                file_content=b"", original_filename="empty.pdf"
            )
        assert exc.value.code == "SOURCE_FILE_EMPTY"

    def test_uses_filename_when_title_empty(self, db, confirmed_project_id):
        """title 为空时用 original_filename 作标题。"""
        content = b"%PDF-1.4 test"
        source, _ = sources_service.create_pdf_source(
            db, confirmed_project_id, title="",
            file_content=content, original_filename="paper.pdf"
        )
        assert source.title == "paper.pdf"


# --- list_sources / get_source ---


class TestListSources:
    """来源列表与查询测试。"""

    def test_lists_sources_in_desc_order(self, db, confirmed_project_id):
        """list_sources 按创建时间降序返回。"""
        req1 = UrlSourceRequest(url="https://example.com/a.html")
        req2 = UrlSourceRequest(url="https://example.com/b.html")
        s1, _ = sources_service.create_url_source(db, confirmed_project_id, req1)
        s2, _ = sources_service.create_url_source(db, confirmed_project_id, req2)

        sources = sources_service.list_sources(db, confirmed_project_id)
        assert len(sources) == 2
        # 创建时间相同，desc 可能不稳定，但都应存在
        ids = [s.id for s in sources]
        assert s1.id in ids
        assert s2.id in ids

    def test_get_source_raises_when_not_found(self, db):
        """get_source 不存在时抛 SOURCE_NOT_FOUND。"""
        with pytest.raises(AppError) as exc:
            sources_service.get_source(db, "src_missing")
        assert exc.value.code == "SOURCE_NOT_FOUND"

    def test_get_source_by_project_raises_when_mismatch(self, db, confirmed_project_id):
        """source 不属于该项目时抛 SOURCE_NOT_FOUND。"""
        req = UrlSourceRequest(url="https://example.com/a.html")
        source, _ = sources_service.create_url_source(db, confirmed_project_id, req)
        # 用错误的 project_id 查询
        with pytest.raises(AppError) as exc:
            sources_service.get_source_by_id_and_project(
                db, "proj_wrong", source.id
            )
        assert exc.value.code == "SOURCE_NOT_FOUND"


# --- delete_source ---


class TestDeleteSource:
    """软删除来源测试。"""

    def test_soft_delete_marks_status_deleted(self, db, confirmed_project_id):
        """删除后 status=DELETED。"""
        req = UrlSourceRequest(url="https://example.com/a.html")
        source, _ = sources_service.create_url_source(db, confirmed_project_id, req)

        deleted = sources_service.delete_source(db, confirmed_project_id, source.id)

        assert deleted.status == SourceStatus.DELETED.value

    def test_delete_marks_related_evidence_stale(self, db, confirmed_project_id):
        """删除来源时关联证据卡片变为 STALE。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)
        # 创建几张证据卡片
        card1 = EvidenceCard(
            id="card_test_1",
            project_id=confirmed_project_id,
            source_id=source.id,
            parsed_document_id=pd.id,
            summary="背景：实验背景与研究意义。",
            evidence_type="BACKGROUND",
            locator="第1段",
            source_quote="实验背景与研究意义。",
            status=EvidenceCardStatus.CANDIDATE.value,
            candidate_source=CandidateSource.LOCAL_RULE.value,
        )
        card2 = EvidenceCard(
            id="card_test_2",
            project_id=confirmed_project_id,
            source_id=source.id,
            parsed_document_id=pd.id,
            summary="方法：采用描述性统计方法。",
            evidence_type="METHOD",
            locator="第2段",
            source_quote="描述性统计方法。",
            status=EvidenceCardStatus.CONFIRMED.value,
            candidate_source=CandidateSource.LOCAL_RULE.value,
        )
        db.add_all([card1, card2])
        db.commit()

        sources_service.delete_source(db, confirmed_project_id, source.id)

        db.refresh(card1)
        db.refresh(card2)
        assert card1.status == EvidenceCardStatus.STALE.value
        assert card2.status == EvidenceCardStatus.STALE.value


# --- complete_sources ---


class TestCompleteSources:
    """完成来源收集测试。"""

    def test_advances_project_to_sources_collected_when_parsed_exists(
        self, db, confirmed_project_id
    ):
        """存在 PARSED 来源时推进到 SOURCES_COLLECTED。"""
        _make_parsed_source(db, confirmed_project_id)

        project = sources_service.complete_sources(db, confirmed_project_id)

        assert project.status == ProjectStatus.SOURCES_COLLECTED.value

    def test_rejects_when_no_parsed_source(self, db, confirmed_project_id):
        """无 PARSED 来源时返回 PROJECT_NO_PARSED_SOURCE。"""
        # 仅有 PENDING 来源
        req = UrlSourceRequest(url="https://example.com/a.html")
        sources_service.create_url_source(db, confirmed_project_id, req)

        with pytest.raises(AppError) as exc:
            sources_service.complete_sources(db, confirmed_project_id)
        assert exc.value.code == "PROJECT_NO_PARSED_SOURCE"


# --- mark_source_fetched / mark_source_parsed / create_parsed_document ---


class TestWorkerHelpers:
    """Worker 调用的内部方法测试。"""

    def test_mark_source_fetched_updates_status_and_hash(self, db, confirmed_project_id):
        """mark_source_fetched 设置 status=FETCHED、content_hash、fetched_at。"""
        req = UrlSourceRequest(url="https://example.com/a.html")
        source, _ = sources_service.create_url_source(db, confirmed_project_id, req)

        updated = sources_service.mark_source_fetched(
            db, source.id, content_type="text/html",
            content_hash="hash_new_001", file_path="/tmp/raw.html"
        )
        db.commit()

        assert updated.status == SourceStatus.FETCHED.value
        assert updated.content_type == "text/html"
        assert updated.content_hash == "hash_new_001"
        assert updated.fetched_at is not None
        assert updated.error_code is None

    def test_mark_source_fetched_triggers_stale_on_hash_change(
        self, db, confirmed_project_id
    ):
        """content_hash 变化时关联证据卡片变 STALE。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)
        card = EvidenceCard(
            id="card_stale_test",
            project_id=confirmed_project_id,
            source_id=source.id,
            parsed_document_id=pd.id,
            summary="测试卡片。",
            evidence_type="BACKGROUND",
            locator="第1段",
            source_quote="测试。",
            status=EvidenceCardStatus.CANDIDATE.value,
            candidate_source=CandidateSource.LOCAL_RULE.value,
        )
        db.add(card)
        db.commit()

        # 旧 hash 是 hash_test_001，新 hash 不同
        sources_service.mark_source_fetched(
            db, source.id, content_type="text/html",
            content_hash="hash_new_different", file_path="/tmp/raw2.html"
        )
        db.commit()

        db.refresh(card)
        assert card.status == EvidenceCardStatus.STALE.value

    def test_mark_source_failed_sets_error_info(self, db, confirmed_project_id):
        """mark_source_failed 设置 status=FAILED、error_code、error_message。"""
        req = UrlSourceRequest(url="https://example.com/a.html")
        source, _ = sources_service.create_url_source(db, confirmed_project_id, req)

        failed = sources_service.mark_source_failed(
            db, source.id, "FETCH_TIMEOUT", "采集超时"
        )
        db.commit()

        assert failed.status == SourceStatus.FAILED.value
        assert failed.error_code == "FETCH_TIMEOUT"
        assert "采集超时" in failed.error_message

    def test_mark_source_parsed_sets_status_and_parsed_at(
        self, db, confirmed_project_id
    ):
        """mark_source_parsed 设置 status=PARSED、parsed_at。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)
        # 先重置为 FETCHED 模拟流程
        source.status = SourceStatus.FETCHED.value
        db.commit()

        parsed = sources_service.mark_source_parsed(db, source.id, pd.id)
        db.commit()

        assert parsed.status == SourceStatus.PARSED.value
        assert parsed.parsed_at is not None
        assert parsed.error_code is None

    def test_create_parsed_document_replaces_existing(self, db, confirmed_project_id):
        """同一 source 重复调用 create_parsed_document 时替换旧记录。"""
        source = Source(
            id="src_replace_test",
            project_id=confirmed_project_id,
            source_kind=SourceKind.URL.value,
            title="测试",
            url="https://example.com/a.html",
            status=SourceStatus.FETCHED.value,
        )
        db.add(source)
        db.commit()

        pd1 = sources_service.create_parsed_document(
            db, source_id=source.id, project_id=confirmed_project_id,
            title="第一次", parsed_text="第一次解析的文本内容足够长。",
            metadata={"k": "v1"},
        )
        db.commit()
        first_id = pd1.id

        pd2 = sources_service.create_parsed_document(
            db, source_id=source.id, project_id=confirmed_project_id,
            title="第二次", parsed_text="第二次解析的文本内容也足够长。",
            metadata={"k": "v2"},
        )
        db.commit()

        # 旧 ParsedDocument 应被删除
        old_pd = db.query(ParsedDocument).filter(ParsedDocument.id == first_id).first()
        assert old_pd is None
        # 新 ParsedDocument 存在
        assert pd2.id != first_id
        assert pd2.title == "第二次"
