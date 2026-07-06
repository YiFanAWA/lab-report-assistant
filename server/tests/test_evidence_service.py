"""证据卡片核心服务测试。

覆盖 generate_evidence_cards、list_evidence_cards、update_evidence_card、
confirm_evidence_card、reject_evidence_card、complete_evidence 的状态机。
"""

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
from app.modules.sources.models import Source, ParsedDocument, EvidenceCard
from app.modules.sources.contracts import UpdateEvidenceCardRequest
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


def _make_parsed_source(db, project_id: str,
                         parsed_text: str = "背景：本节介绍胃病数据分析的研究背景。"
                                            "方法：采用描述性统计和可视化方法分析数据。"
                                            "结果：分析显示关键变量之间存在显著相关。") -> tuple[Source, ParsedDocument]:
    """构造一个 PARSED 状态的来源和 ParsedDocument。"""
    source = Source(
        id="src_parsed_evidence",
        project_id=project_id,
        source_kind=SourceKind.URL.value,
        title="已解析来源",
        url="https://example.com/article.html",
        status=SourceStatus.PARSED.value,
        content_type="text/html",
        content_hash="hash_evidence_001",
        file_path="/tmp/raw.html",
    )
    db.add(source)
    pd = ParsedDocument(
        id="pd_evidence_001",
        source_id=source.id,
        project_id=project_id,
        title="测试文档",
        parsed_text=parsed_text,
        metadata_json='{"description": "测试"}',
    )
    db.add(pd)
    db.commit()
    return source, pd


def _make_candidate_card(db, project_id: str, source_id: str,
                          pd_id: str, summary: str = "测试证据卡片。",
                          evidence_type: str = "BACKGROUND") -> EvidenceCard:
    """直接构造一张 CANDIDATE 证据卡片。"""
    card = EvidenceCard(
        id="card_cand_" + str(hash(summary) & 0xFFFF),
        project_id=project_id,
        source_id=source_id,
        parsed_document_id=pd_id,
        summary=summary,
        evidence_type=evidence_type,
        locator="第1段",
        source_quote=summary[:100],
        status=EvidenceCardStatus.CANDIDATE.value,
        candidate_source=CandidateSource.LOCAL_RULE.value,
    )
    db.add(card)
    db.commit()
    return card


# --- generate_evidence_cards ---


class TestGenerateEvidenceCards:
    """触发生成证据卡片测试。"""

    def test_creates_generate_evidence_job(self, db, confirmed_project_id):
        """成功创建 GENERATE_EVIDENCE 任务。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)

        job_id = sources_service.generate_evidence_cards(
            db, confirmed_project_id, source.id
        )

        from app.modules.jobs.models import BackgroundJob
        job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
        assert job is not None
        assert job.job_type == JobType.GENERATE_EVIDENCE.value
        assert job.status == JobStatus.PENDING.value
        assert source.id in job.input_json
        assert pd.id in job.input_json

    def test_rejects_when_source_not_parsed(self, db, confirmed_project_id):
        """来源未解析时返回 EVIDENCE_SOURCE_NOT_PARSED。"""
        # 创建一个 PENDING 来源（不经过 fetch/parse 流程）
        source = Source(
            id="src_not_parsed",
            project_id=confirmed_project_id,
            source_kind=SourceKind.URL.value,
            title="未解析来源",
            url="https://example.com/a.html",
            status=SourceStatus.PENDING.value,
        )
        db.add(source)
        db.commit()

        with pytest.raises(AppError) as exc:
            sources_service.generate_evidence_cards(
                db, confirmed_project_id, source.id
            )
        assert exc.value.code == "EVIDENCE_SOURCE_NOT_PARSED"

    def test_rejects_when_no_parsed_document(self, db, confirmed_project_id):
        """来源已 PARSED 但无关联 ParsedDocument 时也返回 EVIDENCE_SOURCE_NOT_PARSED。"""
        source = Source(
            id="src_parsed_no_pd",
            project_id=confirmed_project_id,
            source_kind=SourceKind.URL.value,
            title="PARSED 但无 PD",
            url="https://example.com/a.html",
            status=SourceStatus.PARSED.value,
        )
        db.add(source)
        db.commit()

        with pytest.raises(AppError) as exc:
            sources_service.generate_evidence_cards(
                db, confirmed_project_id, source.id
            )
        assert exc.value.code == "EVIDENCE_SOURCE_NOT_PARSED"


# --- list_evidence_cards ---


class TestListEvidenceCards:
    """证据卡片列表测试。"""

    def test_lists_cards_filtered_by_status(self, db, confirmed_project_id):
        """按 status 筛选证据卡片。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)
        card_cand = _make_candidate_card(
            db, confirmed_project_id, source.id, pd.id,
            summary="候选卡片", evidence_type="BACKGROUND",
        )
        card_confirmed = _make_candidate_card(
            db, confirmed_project_id, source.id, pd.id,
            summary="已确认卡片", evidence_type="METHOD",
        )
        card_confirmed.status = EvidenceCardStatus.CONFIRMED.value
        db.commit()

        cand_only = sources_service.list_evidence_cards(
            db, confirmed_project_id, status=EvidenceCardStatus.CANDIDATE.value
        )
        assert len(cand_only) == 1
        assert cand_only[0].id == card_cand.id

        confirmed_only = sources_service.list_evidence_cards(
            db, confirmed_project_id, status=EvidenceCardStatus.CONFIRMED.value
        )
        assert len(confirmed_only) == 1
        assert confirmed_only[0].id == card_confirmed.id

    def test_lists_cards_filtered_by_source_id(self, db, confirmed_project_id):
        """按 source_id 筛选证据卡片。"""
        source1, pd1 = _make_parsed_source(db, confirmed_project_id)
        # 第二个来源
        source2 = Source(
            id="src_second",
            project_id=confirmed_project_id,
            source_kind=SourceKind.URL.value,
            title="第二个来源",
            url="https://example.com/b.html",
            status=SourceStatus.PARSED.value,
        )
        db.add(source2)
        pd2 = ParsedDocument(
            id="pd_second",
            source_id=source2.id,
            project_id=confirmed_project_id,
            title="第二文档",
            parsed_text="另一个文档的解析文本内容。",
        )
        db.add(pd2)
        db.commit()

        _make_candidate_card(db, confirmed_project_id, source1.id, pd1.id,
                              summary="来源1卡片")
        _make_candidate_card(db, confirmed_project_id, source2.id, pd2.id,
                              summary="来源2卡片")

        s1_cards = sources_service.list_evidence_cards(
            db, confirmed_project_id, source_id=source1.id
        )
        assert len(s1_cards) == 1
        assert s1_cards[0].source_id == source1.id


# --- update_evidence_card ---


class TestUpdateEvidenceCard:
    """更新证据卡片测试。"""

    def test_updates_candidate_card_fields(self, db, confirmed_project_id):
        """更新 CANDIDATE 卡片的 summary、evidence_type、locator、source_quote。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)
        card = _make_candidate_card(db, confirmed_project_id, source.id, pd.id)

        req = UpdateEvidenceCardRequest(
            summary="修改后的摘要",
            evidence_type="METHOD",
            locator="第5段",
            source_quote="用户编辑后的原文摘录",
        )
        updated = sources_service.update_evidence_card(
            db, confirmed_project_id, card.id, req
        )

        assert updated.summary == "修改后的摘要"
        assert updated.evidence_type == "METHOD"
        assert updated.locator == "第5段"
        assert updated.source_quote == "用户编辑后的原文摘录"
        assert updated.updated_at is not None

    def test_updates_stale_card(self, db, confirmed_project_id):
        """STALE 卡片也可编辑。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)
        card = _make_candidate_card(db, confirmed_project_id, source.id, pd.id)
        card.status = EvidenceCardStatus.STALE.value
        db.commit()

        req = UpdateEvidenceCardRequest(
            summary="编辑 STALE 卡片",
            evidence_type="RESULT",
            locator="第3段",
            source_quote="摘录",
        )
        updated = sources_service.update_evidence_card(
            db, confirmed_project_id, card.id, req
        )
        assert updated.summary == "编辑 STALE 卡片"
        assert updated.evidence_type == "RESULT"

    def test_rejects_updating_confirmed_card(self, db, confirmed_project_id):
        """CONFIRMED 卡片不可编辑，返回 EVIDENCE_CARD_NOT_EDITABLE。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)
        card = _make_candidate_card(db, confirmed_project_id, source.id, pd.id)
        card.status = EvidenceCardStatus.CONFIRMED.value
        db.commit()

        req = UpdateEvidenceCardRequest(
            summary="尝试修改 CONFIRMED",
            evidence_type="METHOD",
            locator="第1段",
            source_quote=None,
        )
        with pytest.raises(AppError) as exc:
            sources_service.update_evidence_card(
                db, confirmed_project_id, card.id, req
            )
        assert exc.value.code == "EVIDENCE_CARD_NOT_EDITABLE"


# --- confirm / reject ---


class TestConfirmRejectEvidenceCard:
    """确认与拒绝证据卡片测试。"""

    def test_confirm_candidate_sets_confirmed_and_confirmed_at(
        self, db, confirmed_project_id
    ):
        """确认 CANDIDATE 卡片后 status=CONFIRMED，记录 confirmed_at。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)
        card = _make_candidate_card(db, confirmed_project_id, source.id, pd.id)

        confirmed = sources_service.confirm_evidence_card(
            db, confirmed_project_id, card.id
        )

        assert confirmed.status == EvidenceCardStatus.CONFIRMED.value
        assert confirmed.confirmed_at is not None

    def test_confirm_rejects_non_candidate(self, db, confirmed_project_id):
        """非 CANDIDATE 卡片无法确认，返回 EVIDENCE_CARD_NOT_CONFIRMABLE。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)
        card = _make_candidate_card(db, confirmed_project_id, source.id, pd.id)
        card.status = EvidenceCardStatus.CONFIRMED.value
        db.commit()

        with pytest.raises(AppError) as exc:
            sources_service.confirm_evidence_card(
                db, confirmed_project_id, card.id
            )
        assert exc.value.code == "EVIDENCE_CARD_NOT_CONFIRMABLE"

    def test_reject_candidate_sets_rejected(self, db, confirmed_project_id):
        """拒绝 CANDIDATE 卡片后 status=REJECTED。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)
        card = _make_candidate_card(db, confirmed_project_id, source.id, pd.id)

        rejected = sources_service.reject_evidence_card(
            db, confirmed_project_id, card.id
        )

        assert rejected.status == EvidenceCardStatus.REJECTED.value
        assert rejected.updated_at is not None

    def test_reject_rejects_non_candidate(self, db, confirmed_project_id):
        """非 CANDIDATE 卡片无法拒绝。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)
        card = _make_candidate_card(db, confirmed_project_id, source.id, pd.id)
        card.status = EvidenceCardStatus.CONFIRMED.value
        db.commit()

        with pytest.raises(AppError) as exc:
            sources_service.reject_evidence_card(
                db, confirmed_project_id, card.id
            )
        assert exc.value.code == "EVIDENCE_CARD_NOT_CONFIRMABLE"


# --- complete_evidence ---


class TestCompleteEvidence:
    """完成证据确认测试。"""

    def test_advances_project_to_evidence_confirmed(self, db, confirmed_project_id):
        """有 CONFIRMED 卡片时推进到 EVIDENCE_CONFIRMED。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)
        card = _make_candidate_card(db, confirmed_project_id, source.id, pd.id)
        sources_service.confirm_evidence_card(db, confirmed_project_id, card.id)

        project = sources_service.complete_evidence(db, confirmed_project_id)

        assert project.status == ProjectStatus.EVIDENCE_CONFIRMED.value

    def test_rejects_when_no_confirmed_card(self, db, confirmed_project_id):
        """无 CONFIRMED 卡片时返回 PROJECT_NO_CONFIRMED_EVIDENCE。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)
        # 只有 CANDIDATE 卡片
        _make_candidate_card(db, confirmed_project_id, source.id, pd.id)

        with pytest.raises(AppError) as exc:
            sources_service.complete_evidence(db, confirmed_project_id)
        assert exc.value.code == "PROJECT_NO_CONFIRMED_EVIDENCE"


# --- get_evidence_card / save_evidence_card_drafts ---


class TestEvidenceCardQueries:
    """证据卡片查询与批量保存测试。"""

    def test_get_evidence_card_raises_when_not_found(self, db):
        """get_evidence_card 不存在时抛 EVIDENCE_CARD_NOT_FOUND。"""
        with pytest.raises(AppError) as exc:
            sources_service.get_evidence_card(db, "card_missing")
        assert exc.value.code == "EVIDENCE_CARD_NOT_FOUND"

    def test_get_evidence_card_by_project_raises_when_mismatch(
        self, db, confirmed_project_id
    ):
        """卡片不属于该项目时抛 EVIDENCE_CARD_NOT_FOUND。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)
        card = _make_candidate_card(db, confirmed_project_id, source.id, pd.id)

        with pytest.raises(AppError) as exc:
            sources_service.get_evidence_card_by_project(
                db, "proj_wrong", card.id
            )
        assert exc.value.code == "EVIDENCE_CARD_NOT_FOUND"

    def test_save_evidence_card_drafts_creates_candidate_cards(
        self, db, confirmed_project_id
    ):
        """save_evidence_card_drafts 批量创建 CANDIDATE 卡片。"""
        source, pd = _make_parsed_source(db, confirmed_project_id)

        from app.modules.llm.evidence_card_provider import (
            FakeEvidenceCardProvider,
        )
        provider = FakeEvidenceCardProvider()
        drafts = provider.draft(pd.parsed_text)

        cards = sources_service.save_evidence_card_drafts(
            db,
            project_id=confirmed_project_id,
            source_id=source.id,
            parsed_document_id=pd.id,
            drafts=drafts,
            candidate_source=provider.source_label(),
        )
        db.commit()

        assert len(cards) == 3
        for card in cards:
            assert card.status == EvidenceCardStatus.CANDIDATE.value
            assert card.candidate_source == "LOCAL_RULE"
            assert card.project_id == confirmed_project_id
            assert card.source_id == source.id
            assert card.parsed_document_id == pd.id
