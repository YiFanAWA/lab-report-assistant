"""证据卡片核心服务流式生成测试 (stream_generate_evidence_cards)。

SPEC 0020：证据卡片生成流式化。

测试：
- 流式成功：yield StreamEvidenceChunkEvent 多个 + StreamEvidenceDoneEvent，EvidenceCard 保存
- 中途失败：yield StreamEvidenceErrorEvent，不保存 EvidenceCard
- 兼容不支持流式的 provider（LocalRule/Fake）：调用 draft() 一次性 yield
- 项目状态不满足：抛 AppError
- 来源未解析：抛 AppError
- 项目不存在：抛 AppError
- 来源不存在：抛 AppError
- ParsedDocument 不存在：抛 AppError
- JSON 校验失败：yield StreamEvidenceErrorEvent，不保存 EvidenceCard

mock provider.stream_draft 生成器方法。
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.errors import AppError
from app.infrastructure.database.engine import Base
from app.modules.sources import service as sources_service
from app.modules.sources.models import Source, ParsedDocument, EvidenceCard
from app.modules.sources.status import (
    SourceKind,
    SourceStatus,
    EvidenceCardStatus,
    CandidateSource,
)
from app.modules.projects import service as project_service
from app.modules.projects.contracts import ProjectCreateRequest
from app.modules.projects.status import ProjectStatus


TEST_DB = "sqlite:///:memory:"


def _make_valid_evidence_json() -> str:
    """构造有效的证据卡片 JSON（符合 DeepSeekEvidenceResponse 校验，3 张卡片）。"""
    return json.dumps({
        "cards": [
            {
                "summary": "研究采用回顾性分析方法。",
                "evidence_type": "METHOD",
                "locator": "第 2 段",
                "source_quote": "采用回顾性分析方法",
            },
            {
                "summary": "结果显示胃病发病率上升。",
                "evidence_type": "RESULT",
                "locator": "第 3 段",
                "source_quote": "发病率上升",
            },
            {
                "summary": "研究存在样本量不足的局限。",
                "evidence_type": "LIMITATION",
                "locator": "第 5 段",
                "source_quote": None,
            },
        ]
    }, ensure_ascii=False)


# --- fixtures ---


@pytest.fixture
def engine_factory(monkeypatch, tmp_path):
    """创建内存 SQLite engine + SessionLocal factory，供 Phase 3 复用。"""
    monkeypatch.setenv("PROJECT_DATA_ROOT", str(tmp_path / "projects"))
    engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    # patch engine.SessionLocal，让 service Phase 3 用同一 engine
    from app.infrastructure.database import engine as db_engine
    monkeypatch.setattr(db_engine, "SessionLocal", TestingSessionLocal)

    yield engine, TestingSessionLocal
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db(engine_factory):
    _, TestingSessionLocal = engine_factory
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def testing_session_local(engine_factory):
    _, TestingSessionLocal = engine_factory
    return TestingSessionLocal


# --- 辅助函数 ---


def _create_project(db, status: str = ProjectStatus.REQUIREMENT_CONFIRMED.value) -> str:
    """创建项目并设置状态。默认 REQUIREMENT_CONFIRMED（满足证据卡片生成前置条件）。"""
    project = project_service.create_project(
        db, ProjectCreateRequest(name="流式证据卡片测试项目", topic="胃病数据分析")
    )
    project.status = status
    db.commit()
    return project.id


def _seed_parsed_source(
    db, project_id: str,
    source_id: str = "src_stream_001",
    pd_id: str = "pd_stream_001",
    parsed_text: str = "背景：本节介绍胃病数据研究背景。方法：采用描述性统计方法。结果：分析显示相关。",
    source_status: str = SourceStatus.PARSED.value,
) -> tuple[str, str]:
    """插入 PARSED 状态的来源和 ParsedDocument，返回 (source_id, pd_id)。"""
    source = Source(
        id=source_id,
        project_id=project_id,
        source_kind=SourceKind.URL.value,
        title="已解析来源",
        url="https://example.com/article.html",
        status=source_status,
        content_type="text/html",
        content_hash="hash_stream_" + source_id,
        file_path="/tmp/raw.html",
    )
    db.add(source)
    pd = ParsedDocument(
        id=pd_id,
        source_id=source.id,
        project_id=project_id,
        title="测试文档",
        parsed_text=parsed_text,
        metadata_json='{"description": "测试"}',
    )
    db.add(pd)
    db.commit()
    return source.id, pd.id


# --- Mock Provider ---


class _MockStreamProvider:
    """支持流式的证据卡片 provider 测试替身。"""

    def __init__(self, chunks: list[str], source_label: str = "DEEPSEEK"):
        self._chunks = chunks
        self._label = source_label

    def source_label(self) -> str:
        return self._label

    def stream_draft(self, text):
        for c in self._chunks:
            yield c


class _MockSyncProvider:
    """不支持流式的证据卡片 provider 测试替身（LocalRule/Fake 风格）。"""

    def __init__(self, evidence_json: str, source_label: str = "LOCAL_RULE"):
        self._evidence_json = evidence_json
        self._label = source_label

    def source_label(self) -> str:
        return self._label

    def draft(self, text):
        """同步返回 list[EvidenceCardDraft]。"""
        from app.modules.llm.evidence_card_provider import EvidenceCardDraft
        data = json.loads(self._evidence_json)
        return [
            EvidenceCardDraft(
                summary=c["summary"],
                evidence_type=c["evidence_type"],
                locator=c["locator"],
                source_quote=c.get("source_quote"),
            )
            for c in data["cards"]
        ]


class _MockFailingStreamProvider:
    """中途失败的流式 provider。"""

    def __init__(self, chunks_before_failure: list[str], exc: Exception):
        self._chunks = chunks_before_failure
        self._exc = exc

    def source_label(self) -> str:
        return "DEEPSEEK"

    def stream_draft(self, text):
        for c in self._chunks:
            yield c
        raise self._exc


# --- 共享 fixture ---


@pytest.fixture
def project_with_parsed_source(db):
    """创建项目（REQUIREMENT_CONFIRMED）+ PARSED 来源，返回 (project_id, source_id, pd_id)。"""
    project_id = _create_project(db)
    source_id, pd_id = _seed_parsed_source(db, project_id)
    return project_id, source_id, pd_id


# --- 流式成功场景 ---


class TestStreamGenerateEvidenceSuccess:
    """流式成功场景。"""

    def test_流式成功yield_chunks_和_done(self, db, testing_session_local, project_with_parsed_source):
        """完整流程：yield StreamEvidenceChunkEvent 多个 + StreamEvidenceDoneEvent。"""
        project_id, source_id, _ = project_with_parsed_source
        full_json = _make_valid_evidence_json()
        chunks = [full_json[i:i + 30] for i in range(0, len(full_json), 30)]
        provider = _MockStreamProvider(chunks=chunks)

        events = list(sources_service.stream_generate_evidence_cards(
            db, project_id, source_id, provider
        ))

        chunk_events = [e for e in events
                        if isinstance(e, sources_service.StreamEvidenceChunkEvent)]
        done_events = [e for e in events
                       if isinstance(e, sources_service.StreamEvidenceDoneEvent)]

        assert len(chunk_events) == len(chunks)
        assert len(done_events) == 1

        # chunk 内容拼接应等于 full_json
        assert "".join(e.text for e in chunk_events) == full_json

        # done 事件应包含 card_count 和 candidate_source
        done = done_events[0]
        assert done.candidate_source == "DEEPSEEK"
        assert done.card_count == 3  # 3 张卡片
        assert done.fallback_used is False

    def test_流式成功后保存EvidenceCard(self, db, testing_session_local, project_with_parsed_source):
        """流式完成后应保存 EvidenceCard 到数据库（CANDIDATE 状态）。"""
        project_id, source_id, _ = project_with_parsed_source
        full_json = _make_valid_evidence_json()
        provider = _MockStreamProvider(chunks=[full_json])

        events = list(sources_service.stream_generate_evidence_cards(
            db, project_id, source_id, provider
        ))

        done_events = [e for e in events
                       if isinstance(e, sources_service.StreamEvidenceDoneEvent)]
        assert len(done_events) == 1
        assert done_events[0].card_count == 3

        # 用新 session 查询数据库，验证 cards 已保存
        verify_db = testing_session_local()
        try:
            cards = verify_db.query(EvidenceCard).filter(
                EvidenceCard.source_id == source_id,
                EvidenceCard.status == EvidenceCardStatus.CANDIDATE.value,
            ).all()
            assert len(cards) == 3
            for card in cards:
                assert card.candidate_source == "DEEPSEEK"
                assert card.evidence_type in ("METHOD", "RESULT", "LIMITATION")
        finally:
            verify_db.close()

    def test_流式成功后写变更记录(self, db, testing_session_local, project_with_parsed_source):
        """流式完成后应写变更记录（EVIDENCE_CARD_GENERATED）。"""
        project_id, source_id, _ = project_with_parsed_source
        full_json = _make_valid_evidence_json()
        provider = _MockStreamProvider(chunks=[full_json])

        list(sources_service.stream_generate_evidence_cards(
            db, project_id, source_id, provider
        ))

        # 用新 session 查询变更记录
        verify_db = testing_session_local()
        try:
            from app.modules.requirements.models import ChangeRecord
            changes = verify_db.query(ChangeRecord).filter(
                ChangeRecord.project_id == project_id,
                ChangeRecord.change_type == "EVIDENCE_CARD_GENERATED",
            ).all()
            # 应至少有 1 条 EVIDENCE_CARD_GENERATED 变更记录
            assert len(changes) >= 1
        finally:
            verify_db.close()


# --- 中途失败场景 ---


class TestStreamGenerateEvidenceMidStreamFailure:
    """中途失败场景。"""

    def test_中途失败yield_StreamErrorEvent(self, db, testing_session_local, project_with_parsed_source):
        """provider 中途失败应 yield StreamEvidenceErrorEvent，不保存 EvidenceCard。"""
        project_id, source_id, _ = project_with_parsed_source
        provider = _MockFailingStreamProvider(
            chunks_before_failure=["部分内容"],
            exc=Exception("LLM 中断"),
        )

        events = list(sources_service.stream_generate_evidence_cards(
            db, project_id, source_id, provider
        ))

        chunk_events = [e for e in events
                        if isinstance(e, sources_service.StreamEvidenceChunkEvent)]
        error_events = [e for e in events
                       if isinstance(e, sources_service.StreamEvidenceErrorEvent)]
        done_events = [e for e in events
                       if isinstance(e, sources_service.StreamEvidenceDoneEvent)]

        assert len(chunk_events) == 1
        assert len(error_events) == 1
        assert len(done_events) == 0

        err = error_events[0]
        assert err.partial_text == "部分内容"
        assert err.error_code  # 非空

    def test_中途失败不保存EvidenceCard(self, db, testing_session_local, project_with_parsed_source):
        """中途失败时不应保存 EvidenceCard。"""
        project_id, source_id, _ = project_with_parsed_source
        provider = _MockFailingStreamProvider(
            chunks_before_failure=["部分"],
            exc=Exception("中断"),
        )

        list(sources_service.stream_generate_evidence_cards(
            db, project_id, source_id, provider
        ))

        verify_db = testing_session_local()
        try:
            count = verify_db.query(EvidenceCard).filter(
                EvidenceCard.source_id == source_id,
                EvidenceCard.status == EvidenceCardStatus.CANDIDATE.value,
            ).count()
            assert count == 0
        finally:
            verify_db.close()


# --- JSON 校验失败场景 ---


class TestStreamGenerateEvidenceJsonParseFailure:
    """JSON 校验失败场景。"""

    def test_JSON校验失败yield_ErrorEvent(self, db, testing_session_local, project_with_parsed_source):
        """流式完成后 JSON 校验失败应 yield StreamEvidenceErrorEvent。"""
        project_id, source_id, _ = project_with_parsed_source
        # 提供无效 JSON
        provider = _MockStreamProvider(chunks=["{invalid json}"])

        events = list(sources_service.stream_generate_evidence_cards(
            db, project_id, source_id, provider
        ))

        error_events = [e for e in events
                       if isinstance(e, sources_service.StreamEvidenceErrorEvent)]
        done_events = [e for e in events
                       if isinstance(e, sources_service.StreamEvidenceDoneEvent)]

        assert len(error_events) == 1
        assert len(done_events) == 0
        assert error_events[0].error_code == "EVIDENCE_JSON_PARSE_ERROR"

    def test_JSON校验失败不保存EvidenceCard(self, db, testing_session_local, project_with_parsed_source):
        """JSON 校验失败时不应保存 EvidenceCard。"""
        project_id, source_id, _ = project_with_parsed_source
        provider = _MockStreamProvider(chunks=["{invalid}"])

        list(sources_service.stream_generate_evidence_cards(
            db, project_id, source_id, provider
        ))

        verify_db = testing_session_local()
        try:
            count = verify_db.query(EvidenceCard).filter(
                EvidenceCard.source_id == source_id,
                EvidenceCard.status == EvidenceCardStatus.CANDIDATE.value,
            ).count()
            assert count == 0
        finally:
            verify_db.close()


# --- 兼容同步 provider 场景 ---


class TestStreamGenerateEvidenceSyncProvider:
    """兼容不支持 stream_draft 的 provider。"""

    def test_同步provider一次性yield(self, db, testing_session_local, project_with_parsed_source):
        """LocalRule/Fake provider 不支持 stream_draft，应调用 draft() 一次性 yield。"""
        project_id, source_id, _ = project_with_parsed_source
        provider = _MockSyncProvider(_make_valid_evidence_json())

        events = list(sources_service.stream_generate_evidence_cards(
            db, project_id, source_id, provider
        ))

        chunk_events = [e for e in events
                        if isinstance(e, sources_service.StreamEvidenceChunkEvent)]
        done_events = [e for e in events
                       if isinstance(e, sources_service.StreamEvidenceDoneEvent)]

        # 应有多个 chunk（按 50 字符拆分）+ 1 个 done
        assert len(chunk_events) >= 1
        assert len(done_events) == 1
        assert done_events[0].candidate_source == "LOCAL_RULE"

    def test_同步provider保存EvidenceCard(self, db, testing_session_local, project_with_parsed_source):
        """同步 provider 流式后应保存 EvidenceCard。"""
        project_id, source_id, _ = project_with_parsed_source
        provider = _MockSyncProvider(_make_valid_evidence_json())

        events = list(sources_service.stream_generate_evidence_cards(
            db, project_id, source_id, provider
        ))

        done_events = [e for e in events
                       if isinstance(e, sources_service.StreamEvidenceDoneEvent)]
        assert len(done_events) == 1

        verify_db = testing_session_local()
        try:
            cards = verify_db.query(EvidenceCard).filter(
                EvidenceCard.source_id == source_id,
            ).all()
            assert len(cards) == 3
            for card in cards:
                assert card.candidate_source == "LOCAL_RULE"
                assert card.status == EvidenceCardStatus.CANDIDATE.value
        finally:
            verify_db.close()


# --- 校验失败场景 ---


class TestStreamGenerateEvidenceValidation:
    """前置校验失败场景。"""

    def test_项目不存在抛AppError(self, db):
        """项目不存在应抛 AppError。"""
        provider = _MockStreamProvider(chunks=[_make_valid_evidence_json()])

        with pytest.raises(AppError) as exc_info:
            list(sources_service.stream_generate_evidence_cards(
                db, "nonexistent_project", "src_001", provider
            ))
        assert exc_info.value.code == "PROJECT_NOT_FOUND"

    def test_项目状态不满足抛AppError(self, db, testing_session_local):
        """项目状态未达 REQUIREMENT_CONFIRMED 应抛 AppError。"""
        project_id = _create_project(
            db, status=ProjectStatus.DRAFT.value
        )
        source_id, _ = _seed_parsed_source(db, project_id)

        provider = _MockStreamProvider(chunks=[_make_valid_evidence_json()])

        with pytest.raises(AppError) as exc_info:
            list(sources_service.stream_generate_evidence_cards(
                db, project_id, source_id, provider
            ))
        assert exc_info.value.code == "PROJECT_REQUIREMENT_NOT_CONFIRMED"

    def test_来源不存在抛AppError(self, db, testing_session_local):
        """来源不存在应抛 AppError。"""
        project_id = _create_project(db)

        provider = _MockStreamProvider(chunks=[_make_valid_evidence_json()])

        with pytest.raises(AppError) as exc_info:
            list(sources_service.stream_generate_evidence_cards(
                db, project_id, "nonexistent_source", provider
            ))
        assert exc_info.value.code == "SOURCE_NOT_FOUND"

    def test_来源未解析抛AppError(self, db, testing_session_local):
        """来源未解析（status != PARSED）应抛 AppError（EVIDENCE_SOURCE_NOT_PARSED）。"""
        project_id = _create_project(db)
        # 插入一个 FETCHED 状态（未解析）的来源
        source_id, _ = _seed_parsed_source(
            db, project_id,
            source_id="src_unparsed",
            source_status=SourceStatus.FETCHED.value,
        )

        provider = _MockStreamProvider(chunks=[_make_valid_evidence_json()])

        with pytest.raises(AppError) as exc_info:
            list(sources_service.stream_generate_evidence_cards(
                db, project_id, source_id, provider
            ))
        assert exc_info.value.code == "EVIDENCE_SOURCE_NOT_PARSED"

    def test_ParsedDocument不存在抛AppError(self, db, testing_session_local):
        """来源是 PARSED 状态但 ParsedDocument 不存在应抛 AppError。"""
        project_id = _create_project(db)
        # 插入一个 PARSED 状态的来源但不创建 ParsedDocument
        source = Source(
            id="src_no_pd",
            project_id=project_id,
            source_kind=SourceKind.URL.value,
            title="无 ParsedDocument 的来源",
            url="https://example.com/no_pd.html",
            status=SourceStatus.PARSED.value,
            content_type="text/html",
            content_hash="hash_no_pd",
            file_path="/tmp/raw.html",
        )
        db.add(source)
        db.commit()

        provider = _MockStreamProvider(chunks=[_make_valid_evidence_json()])

        with pytest.raises(AppError) as exc_info:
            list(sources_service.stream_generate_evidence_cards(
                db, project_id, source.id, provider
            ))
        assert exc_info.value.code == "EVIDENCE_SOURCE_NOT_PARSED"
