"""证据摘录、位置、原子保存和状态转换测试。"""

import pytest

from app.core.errors import AppError
from app.modules.llm.local_rule_evidence_provider import LocalRuleEvidenceDraftProvider
from app.modules.projects import service as project_service
from app.modules.sources import service as source_service


@pytest.fixture
def parsed_source(db, project_with_plan):
    source = source_service.add_file_source(
        db,
        project_with_plan,
        "文本资料",
        "source.txt",
        "背景资料。\n\n方法采用公开数据分析。".encode("utf-8"),
        "text/plain",
    )
    parsed = source_service.parse_source(db, project_with_plan, source.id)
    return source, parsed


@pytest.fixture
def pdf_parsed_source(db, project_with_plan, pdf_with_text_bytes):
    source = source_service.add_file_source(
        db,
        project_with_plan,
        "PDF 资料",
        "source.pdf",
        pdf_with_text_bytes,
        "application/pdf",
    )
    parsed = source_service.parse_source(db, project_with_plan, source.id)
    return source, parsed


class InventedQuoteProvider:
    def source_label(self) -> str:
        return "LOCAL_RULE"

    def draft(self, *args):
        return [
            {
                "summary": "伪造候选",
                "source_quote": "原文中不存在",
                "evidence_type": "BACKGROUND",
                "location_label": "段落 1",
                "relevance_to_requirement": "背景",
            }
        ]


class WrongLocationProvider:
    def source_label(self) -> str:
        return "LOCAL_RULE"

    def draft(self, document):
        return [
            {
                "summary": "真实摘录，错误位置",
                "source_quote": "背景资料。",
                "evidence_type": "BACKGROUND",
                "location_label": "不存在的位置",
                "relevance_to_requirement": "背景",
            }
        ]


class RecordingProvider:
    def __init__(self):
        self.args = ()

    def source_label(self) -> str:
        return "LOCAL_RULE"

    def draft(self, *args):
        self.args = args
        text = args[0].parsed_text if len(args) == 1 else args[0]
        return [
            {
                "summary": "背景资料",
                "source_quote": "背景资料。",
                "evidence_type": "BACKGROUND",
                "location_label": "全文",
                "relevance_to_requirement": "背景",
            }
        ]


def test_rejects_candidate_quote_missing_from_parsed_text(parsed_source, db):
    source, _ = parsed_source
    with pytest.raises(AppError) as exc:
        source_service.generate_evidence(
            db, source.project_id, source.id, InventedQuoteProvider()
        )
    assert exc.value.code == "EVIDENCE_CARD_INVALID_QUOTE"
    assert source_service.list_evidence(db, source.project_id) == []


def test_provider_receives_validated_document(parsed_source, db):
    source, _ = parsed_source
    provider = RecordingProvider()
    source_service.generate_evidence(db, source.project_id, source.id, provider)
    assert len(provider.args) == 1
    assert provider.args[0].parsed_text.startswith("背景资料")


def test_rejects_candidate_with_false_location(parsed_source, db):
    source, _ = parsed_source
    with pytest.raises(AppError) as exc:
        source_service.generate_evidence(
            db, source.project_id, source.id, WrongLocationProvider()
        )
    assert exc.value.code == "EVIDENCE_CARD_INVALID_LOCATION"
    assert source_service.list_evidence(db, source.project_id) == []


def test_local_rule_candidate_uses_real_page_label(pdf_parsed_source, db):
    source, parsed = pdf_parsed_source
    cards = source_service.generate_evidence(
        db, source.project_id, source.id, LocalRuleEvidenceDraftProvider()
    )
    assert cards[0].location_label in {"第 1 页", "第 2 页"}
    assert cards[0].source_quote in parsed.parsed_text


def test_failed_regeneration_leaves_existing_candidate_unchanged(parsed_source, db):
    source, _ = parsed_source
    original = source_service.generate_evidence(
        db, source.project_id, source.id, LocalRuleEvidenceDraftProvider()
    )[0]

    with pytest.raises(AppError):
        source_service.generate_evidence(
            db, source.project_id, source.id, InventedQuoteProvider()
        )
    db.rollback()
    refreshed = source_service.get_evidence(db, source.project_id, original.id)
    assert refreshed.status == "CANDIDATE"
    assert len(source_service.list_evidence(db, source.project_id)) == 1


def test_confirming_first_candidate_advances_project(db, parsed_source):
    source, _ = parsed_source
    card = source_service.generate_evidence(
        db, source.project_id, source.id, LocalRuleEvidenceDraftProvider()
    )[0]
    source_service.confirm_evidence(db, source.project_id, card.id)
    project = project_service.get_project(db, source.project_id)
    assert project.status == "EVIDENCE_CONFIRMED"


def test_cannot_reject_confirmed_evidence(db, parsed_source):
    source, _ = parsed_source
    card = source_service.generate_evidence(
        db, source.project_id, source.id, LocalRuleEvidenceDraftProvider()
    )[0]
    confirmed = source_service.confirm_evidence(db, source.project_id, card.id)
    with pytest.raises(AppError) as exc:
        source_service.reject_evidence(db, source.project_id, confirmed.id)
    assert exc.value.code == "EVIDENCE_CARD_NOT_EDITABLE"
