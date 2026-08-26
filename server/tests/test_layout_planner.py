"""SPEC 0033 论文级语义布局规划器测试。"""

from app.modules.outlines.layout_planner import LayoutKind, plan_section_layouts


def _section(title: str, source_type: str, content: str, source_ids=None) -> dict:
    return {
        "id": title,
        "title": title,
        "content": content,
        "source_type": source_type,
        "source_ids": source_ids or [],
    }


def test_standard_sections_select_semantic_layouts():
    sections = [
        _section("实验目的", "REQUIREMENT", "说明本实验目标。"),
        _section("数据描述", "DATASET", "样本量：200 行；字段数：15 列；缺失率：1.2%。"),
        _section("分析方案", "ANALYSIS", "1. 清洗缺失值；2. 描述性统计；3. 相关性分析。"),
        _section("实验结果", "EXECUTION", "结果显示年龄与指标存在趋势。", ["run-1"]),
        _section("结论与讨论", "SUMMARY", "本实验完成数据分析并得到可追溯结果。"),
    ]
    artifacts = [
        {"artifact_type": "CHART_PNG", "execution_run_id": "run-1", "name": "result.png"},
    ]

    plans = plan_section_layouts(sections, artifacts)

    assert [plan.layout_kind for plan in plans] == [
        LayoutKind.NARRATIVE,
        LayoutKind.DATA_OVERVIEW,
        LayoutKind.METHOD_FLOW,
        LayoutKind.RESULT_FOCUS,
        LayoutKind.SUMMARY,
    ]
    assert plans[1].metrics == (("样本量", "200 行"), ("字段数", "15 列"), ("缺失率", "1.2%"))
    assert plans[2].steps == ("清洗缺失值", "描述性统计", "相关性分析")


def test_execution_with_multiple_charts_selects_compare_layout():
    section = _section("实验结果", "EXECUTION", "比较不同指标。", ["run-2"])
    artifacts = [
        {"artifact_type": "CHART_PNG", "execution_run_id": "run-2", "name": "a.png"},
        {"artifact_type": "CHART_PNG", "execution_run_id": "run-2", "name": "b.png"},
    ]

    plan = plan_section_layouts([section], artifacts)[0]

    assert plan.layout_kind == LayoutKind.RESULT_COMPARE
    assert len(plan.chart_artifacts) == 2


def test_non_execution_artifacts_do_not_leak_into_layout_plan():
    section = _section("数据描述", "DATASET", "样本量：10；字段数：2。", ["run-3"])
    artifacts = [
        {"artifact_type": "CHART_PNG", "execution_run_id": "run-3", "name": "chart.png"},
    ]

    plan = plan_section_layouts([section], artifacts)[0]

    assert plan.layout_kind == LayoutKind.DATA_OVERVIEW
    assert plan.chart_artifacts == ()
