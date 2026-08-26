"""SPEC 0037 图表语义规划测试。"""

from app.modules.outlines.chart_planner import ChartKind, recommend_chart_plan


def test_chart_planner_uses_flow_for_sample_accounting():
    plan = recommend_chart_plan(analysis_intent="sample_flow", value_kind="count")
    assert plan.kind == ChartKind.FLOW
    assert "流程图" in plan.rationale


def test_chart_planner_uses_composition_for_outcome_mix():
    plan = recommend_chart_plan(
        analysis_intent="composition", value_kind="proportion", category_count=3
    )
    assert plan.kind == ChartKind.STACKED_COMPOSITION
    assert "100%" in plan.encoding or "构成" in plan.rationale


def test_chart_planner_uses_point_interval_for_group_risk():
    plan = recommend_chart_plan(
        analysis_intent="group_difference",
        value_kind="proportion",
        confidence_interval=True,
        comparison_count=2,
    )
    assert plan.kind == ChartKind.POINT_CI
    assert "置信区间" in plan.rationale


def test_chart_planner_uses_ordered_line_for_ordered_strata():
    plan = recommend_chart_plan(
        analysis_intent="ordered_trend", value_kind="proportion", ordered=True
    )
    assert plan.kind == ChartKind.ORDERED_LINE


def test_chart_planner_uses_dumbbell_for_paper_local_pair():
    plan = recommend_chart_plan(
        analysis_intent="paired_comparison", value_kind="proportion", comparison_count=2
    )
    assert plan.kind == ChartKind.DUMBBELL


def test_chart_planner_uses_forest_for_adjusted_effects():
    plan = recommend_chart_plan(analysis_intent="model_effect", value_kind="effect")
    assert plan.kind == ChartKind.FOREST
