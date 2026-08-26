"""SPEC 0034 正式论文与答辩 PPT 共享结构规划测试。"""

from app.modules.outlines.document_planner import (
    ManuscriptPlan,
    ManuscriptRole,
    plan_defense_deck,
    plan_thesis_document,
)


def _section(title: str, source_type: str, content: str, source_ids=None) -> dict:
    return {
        "id": title,
        "title": title,
        "content": content,
        "source_type": source_type,
        "source_ids": source_ids or [],
    }


def _fixture() -> tuple[list[dict], list[dict]]:
    sections = [
        _section("实验目的", "REQUIREMENT", "明确实验目标与分析边界。"),
        _section("研究背景", "EVIDENCE", "公开资料与研究背景。", ["source-1"]),
        _section("数据概览", "DATASET", "样本量：120；字段数：8；缺失率：0%。"),
        _section("分析方法", "ANALYSIS", "1. 清洗数据；2. 描述性统计；3. 绘制图表。"),
        _section("实验结果", "EXECUTION", "结果支持研究问题的初步判断。", ["run-1"]),
        _section("结论与讨论", "SUMMARY", "研究结论与局限。"),
    ]
    artifacts = [
        {
            "name": f"chart-{index}.png",
            "artifact_type": "CHART_PNG",
            "execution_run_id": "run-1",
        }
        for index in range(1, 5)
    ]
    return sections, artifacts


def test_thesis_plan_groups_chapters_and_references():
    sections, artifacts = _fixture()

    plan = plan_thesis_document("胃病数据分析实验", sections, artifacts)

    assert [chapter.number for chapter in plan.chapters] == [1, 2, 3, 4, 5, 6]
    assert plan.chapters[0].title == "绪论与实验要求"
    assert plan.chapters[2].title == "数据与资料"
    assert plan.chapters[4].title == "实验结果"
    assert "研究结论与局限" in plan.abstract
    assert "胃病数据分析实验" in plan.keywords
    assert plan.references == ("证据来源：source-1",)


def test_formal_thesis_plan_uses_academic_chapters_and_citations():
    sections, artifacts = _fixture()

    plan = plan_thesis_document(
        "胃病数据分析实验",
        sections,
        artifacts,
        formal=True,
        reference_catalog={
            "source-1": "作者甲等. 研究论文. 2024;1:1.",
            "run-1": "项目执行记录. 2026.",
        },
        abstract_override="这是摘要。",
        formal_title="正式论文标题",
        formal_subtitle="正式论文副标题",
        formal_metadata={"研究类型": "教学性分析"},
    )

    assert [chapter.title for chapter in plan.chapters] == [
        "绪论",
        "研究设计与统计方法",
        "结果",
        "讨论",
    ]
    assert plan.abstract == "这是摘要。"
    assert plan.references == (
        "[1] 作者甲等. 研究论文. 2024;1:1.",
        "[2] 项目执行记录. 2026.",
    )
    assert plan.citation_map == (("source-1", 1), ("run-1", 2))
    assert plan.formal_title == "正式论文标题"
    assert plan.formal_metadata == (("研究类型", "教学性分析"),)
    assert isinstance(plan, ManuscriptPlan)
    assert plan.publication_profile.profile_id == "zh_academic_thesis"
    assert plan.sufficiency.publishable is True


def test_formal_plan_uses_manuscript_role_instead_of_source_type_and_normalizes_titles():
    sections, artifacts = _fixture()
    sections[1]["manuscript_role"] = ManuscriptRole.INTRODUCTION.value
    sections[1]["title"] = "1.2 研究背景"
    sections[2]["source_type"] = "EVIDENCE"
    sections[2]["manuscript_role"] = ManuscriptRole.METHODS.value
    sections[2]["title"] = "2 数据来源"

    plan = plan_thesis_document(
        "胃病数据分析实验",
        sections,
        artifacts,
        formal=True,
        reference_catalog={"source-1": "作者甲等. 研究论文. 2024;1:1."},
    )

    introduction = next(chapter for chapter in plan.chapters if chapter.title == "绪论")
    methods = next(chapter for chapter in plan.chapters if chapter.title == "研究设计与统计方法")
    assert [section["title"] for section in introduction.sections] == ["实验目的", "研究背景"]
    assert "数据来源" in [section["title"] for section in methods.sections]


def test_formal_plan_reports_structured_content_gaps():
    plan = plan_thesis_document(
        "空白论文",
        [_section("背景", "EVIDENCE", "只有背景，没有数据与结果。")],
        [],
        formal=True,
    )

    assert plan.sufficiency.publishable is False
    assert {issue.code for issue in plan.sufficiency.issues} >= {
        "MANUSCRIPT_RESEARCH_QUESTION_MISSING",
        "MANUSCRIPT_DATA_MISSING",
        "MANUSCRIPT_METHODS_MISSING",
        "MANUSCRIPT_RESULTS_MISSING",
        "MANUSCRIPT_DISCUSSION_MISSING",
        "MANUSCRIPT_REFERENCES_MISSING",
    }


def test_defense_plan_has_narrative_sequence_and_two_charts_per_slide():
    sections, artifacts = _fixture()

    plan = plan_defense_deck(sections, artifacts)

    assert [slide.role for slide in plan.slides] == [
        "question", "data", "method", "result", "result", "conclusion",
    ]
    result_slides = [slide for slide in plan.slides if slide.role == "result"]
    assert [len(slide.chart_artifacts) for slide in result_slides] == [2, 2]
    assert all(slide.title for slide in result_slides)
