"""SPEC 0039 论文级多语义图形规划契约测试。"""

import pytest

from app.modules.outlines.figure_planner import (
    ArgumentPlan,
    FigureEdge,
    FigureFamily,
    FigureKind,
    FigureNode,
    FigurePortfolioPlan,
    FigurePlan,
    FigureValidationError,
    RejectedFigureCandidate,
    recommend_figure_plan,
    validate_figure_plan,
)


def _nodes() -> tuple[FigureNode, ...]:
    return (
        FigureNode("paper", "原论文证据", role="source", source_ids=("paper-1",)),
        FigureNode("dataset", "公开数据集", role="dataset", source_ids=("data-1",)),
        FigureNode("review", "本地复核", role="analysis", execution_run_ids=("run-1",)),
        FigureNode("boundary", "解释边界", role="boundary", evidence_status="confirmed"),
    )


def test_evidence_chain_is_not_inferred_as_hierarchy():
    evidence_nodes = (
        FigureNode("question", "研究问题", role="source"),
        FigureNode("paper", "原论文", role="source", source_ids=("paper-1",)),
        FigureNode("method", "原文方法", role="analysis"),
        FigureNode("claim", "原文主张", role="outcome"),
        FigureNode("dataset", "公开数据", role="data", source_ids=("data-1",)),
        FigureNode("fields", "字段核查", role="analysis"),
        FigureNode("review", "本地复核", role="analysis", execution_run_ids=("run-1",)),
        FigureNode("boundary", "解释边界", role="boundary", evidence_status="confirmed"),
    )
    plan = recommend_figure_plan(
        figure_kind=FigureKind.EVIDENCE_CHAIN,
        semantic_role="证据来源与本地复核之间的证据链",
        title="论文证据与本地复核链",
        nodes=evidence_nodes,
        edges=(
            FigureEdge("question", "paper", relation="defines", label="研究对象"),
            FigureEdge("paper", "method", relation="documents", label="原文方法"),
            FigureEdge("method", "claim", relation="supports", label="原文结论"),
            FigureEdge("dataset", "fields", relation="contains", label="字段入口"),
            FigureEdge("fields", "review", relation="produces", label="复核入口"),
            FigureEdge("claim", "review", relation="compared_with", label="结果对照"),
            FigureEdge("review", "boundary", relation="bounded_by", label="解释边界"),
        ),
        source_ids=("paper-1", "data-1"),
        execution_run_ids=("run-1",),
        caption="论文证据与本地复核的关系",
        note="本地复核不等同于原论文模型复现。",
        panel_labels=("A 原论文", "B 数据口径", "C 本地复核", "D 证据对照"),
    )

    assert plan.figure_kind == FigureKind.EVIDENCE_CHAIN
    assert plan.figure_kind != FigureKind.HIERARCHY
    assert plan.to_metadata()["figure_kind"] == "evidence_chain"
    assert plan.to_metadata()["edges"][0]["relation"] == "defines"


def test_data_pipeline_keeps_stage_semantics():
    plan = recommend_figure_plan(
        figure_kind="data_pipeline",
        semantic_role="原始数据到结果产物的处理路径",
        title="数据处理管线",
        nodes=(
            FigureNode("raw", "原始 CSV", role="input"),
            FigureNode("clean", "缺失结构检查", role="transform"),
            FigureNode("result", "统计结果", role="output"),
        ),
        edges=(
            FigureEdge("raw", "clean", relation="transforms"),
            FigureEdge("clean", "result", relation="produces"),
        ),
        caption="数据从原始记录到统计结果的处理路径",
        note="各阶段均对应真实执行产物或已确认分析步骤。",
    )

    assert plan.figure_kind == FigureKind.DATA_PIPELINE
    assert [edge.relation for edge in plan.edges] == ["transforms", "produces"]
    assert plan.target_surfaces == ("word", "ppt")


def test_invalid_edge_reference_is_rejected():
    with pytest.raises(FigureValidationError, match="不存在"):
        FigurePlan(
            figure_kind=FigureKind.RELATIONSHIP_GRAPH,
            semantic_role="变量关系",
            title="变量关系图",
            nodes=(FigureNode("exposure", "HbA1c 检测"), FigureNode("outcome", "再入院")),
            edges=(FigureEdge("exposure", "missing", relation="associational"),),
            caption="变量关系",
            note="观察性关联，不代表因果关系。",
        )


def test_causal_edge_requires_explicit_source():
    with pytest.raises(FigureValidationError, match="因果"):
        FigurePlan(
            figure_kind=FigureKind.CAUSAL_DAG,
            semantic_role="因果结构",
            title="因果关系图",
            nodes=(FigureNode("x", "暴露"), FigureNode("y", "结局")),
            edges=(FigureEdge("x", "y", relation="causal"),),
            caption="因果结构",
            note="需要明确来源支持。",
        )


def test_associational_edge_requires_non_causal_note():
    plan = FigurePlan(
        figure_kind=FigureKind.RELATIONSHIP_GRAPH,
        semantic_role="观察性变量关系",
        title="变量关系图",
        nodes=(FigureNode("x", "HbA1c 检测"), FigureNode("y", "再入院")),
        edges=(FigureEdge("x", "y", relation="associational"),),
        caption="HbA1c 检测与再入院的观察性关联",
        note="观察性关联，不代表因果关系。",
    )

    validate_figure_plan(plan)


def test_argument_plan_requires_claim_evidence_result_and_boundary():
    argument = ArgumentPlan(
        claim="检测状态与再入院率存在描述性差异",
        evidence_refs=("primary_effect_summary.csv",),
        method="Wilson 95% 置信区间",
        result="风险差为 -1.6 个百分点",
        boundary="观察性关联，不代表检测行为造成风险下降",
        body_reference="见第 5.1 节",
    )
    plan = recommend_figure_plan(
        figure_kind=FigureKind.DATA_CHART,
        semantic_role="主要结果论证",
        title="主要结果",
        data_artifact_ids=("primary_effect_summary.csv",),
        execution_run_ids=("run-1",),
        caption="HbA1c 检测状态与再入院率",
        note="图中给出组间差异及解释边界。",
        argument=argument,
        legend_items=("已检测", "未检测", "95% CI"),
        body_reference="见第 5.1 节",
    )
    artifact = plan.to_metadata()
    assert artifact["argument"]["claim"] == "检测状态与再入院率存在描述性差异"
    assert artifact["body_reference"] == "见第 5.1 节"


def test_argument_plan_rejects_missing_evidence():
    with pytest.raises(FigureValidationError, match="evidence_refs"):
        ArgumentPlan(
            claim="缺少证据的主张",
            result="结果",
            boundary="边界",
        )


def test_comparison_matrix_requires_two_dimensional_data_requirement():
    with pytest.raises(FigureValidationError, match="二维"):
        FigurePlan(
            figure_kind=FigureKind.COMPARISON_MATRIX,
            semantic_role="论文与本地复核对照",
            title="比较矩阵",
            caption="多维口径对照",
            note="比较矩阵不等同于复现。",
        )


def test_heterogeneous_portfolio_serializes_rejected_candidates():
    matrix = recommend_figure_plan(
        figure_kind=FigureKind.COMPARISON_MATRIX,
        semantic_role="论文与本地复核对照",
        title="比较矩阵",
        caption="多维口径对照",
        note="比较矩阵不等同于复现。",
        visual_family=FigureFamily.MATRIX,
        layout_profile="matrix_grid",
        data_requirements=("行维度", "列维度", "单元格证据"),
        selection_rationale="多维对象对照使用矩阵。",
    )
    portfolio = FigurePortfolioPlan(
        figures=(matrix,),
        coverage=("matrix",),
        selection_rationale=("矩阵回答多维对照。",),
        rejected_candidates=(
            RejectedFigureCandidate(
                name="热力图",
                visual_family=FigureFamily.MATRIX,
                reason="缺少行×字段质量矩阵。",
                missing_requirements=("二维单元格",),
            ),
        ),
    )
    metadata = portfolio.to_metadata()
    assert metadata["figures"][0]["visual_family"] == "matrix"
    assert metadata["rejected_candidates"][0]["missing_requirements"] == ["二维单元格"]
