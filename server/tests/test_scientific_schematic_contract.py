"""SPEC 0042 科研示意图组件合同测试。"""

import pytest

from app.modules.outlines.figure_planner import (
    FigureEdge,
    FigureKind,
    FigureNode,
    FigureValidationError,
    ScientificSchematicSpec,
    SchematicConnector,
    SchematicPanel,
    SchematicPlacement,
    recommend_figure_plan,
)


def _plan(*, placement_label: str = "公开数据", relation: str = "transforms"):
    nodes = (
        FigureNode("raw", "公开数据", role="data"),
        FigureNode("analysis", "统计分析", role="analysis"),
    )
    return recommend_figure_plan(
        figure_kind=FigureKind.DATA_PIPELINE,
        semantic_role="数据分析流程",
        title="公开数据到统计结果",
        nodes=nodes,
        edges=(FigureEdge("raw", "analysis", relation=relation, label="进入分析"),),
        caption="数据分析流程",
        note="各步骤来自已确认分析方案，不表达医学因果。",
        schematic=ScientificSchematicSpec(
            panels=(SchematicPanel("A", "A", "数据与分析"),),
            placements=(
                SchematicPlacement(
                    "p-raw", "raw", "bioicons-cc0-well-plate",
                    placement_label, "data", "A", 1,
                ),
                SchematicPlacement(
                    "p-analysis", "analysis", "bioicons-cc0-algorithm",
                    "统计分析", "analysis", "A", 2,
                ),
            ),
            connectors=(
                SchematicConnector("p-raw", "p-analysis", "transforms", "进入分析"),
            ),
            legend_items=("开放数据", "受控分析"),
        ),
    )


def test_schematic_serializes_with_figure_plan():
    metadata = _plan().to_metadata()
    assert metadata["schematic"]["placements"][0]["asset_id"] == "bioicons-cc0-well-plate"
    assert metadata["schematic"]["connectors"][0]["edge_relation"] == "transforms"


def test_schematic_label_must_match_figure_node():
    with pytest.raises(FigureValidationError, match="标签"):
        _plan(placement_label="模型自行改写")


def test_schematic_connector_requires_matching_figure_edge():
    with pytest.raises(FigureValidationError, match="FigureEdge"):
        _plan(relation="produces")

def test_schematic_rejects_connector_cycle():
    nodes = (
        FigureNode("a", "步骤 A", role="transform"),
        FigureNode("b", "步骤 B", role="transform"),
    )
    with pytest.raises(FigureValidationError, match="无环"):
        recommend_figure_plan(
            figure_kind=FigureKind.PROCESS_FLOW,
            semantic_role="循环流程",
            title="错误的循环示意图",
            nodes=nodes,
            edges=(
                FigureEdge("a", "b", relation="transforms"),
                FigureEdge("b", "a", relation="transforms"),
            ),
            caption="循环流程",
            note="用于验证环路拒绝。",
            schematic=ScientificSchematicSpec(
                panels=(SchematicPanel("A", "A", "错误循环"),),
                placements=(
                    SchematicPlacement("p-a", "a", "asset-a", "步骤 A", "transform", "A"),
                    SchematicPlacement("p-b", "b", "asset-b", "步骤 B", "transform", "A"),
                ),
                connectors=(
                    SchematicConnector("p-a", "p-b", "transforms"),
                    SchematicConnector("p-b", "p-a", "transforms"),
                ),
            ),
        )
def test_schematic_connector_label_must_match_figure_edge():
    nodes = (
        FigureNode("raw", "公开数据", role="data"),
        FigureNode("analysis", "统计分析", role="analysis"),
    )
    with pytest.raises(FigureValidationError, match="连接标签"):
        recommend_figure_plan(
            figure_kind=FigureKind.DATA_PIPELINE,
            semantic_role="数据分析流程",
            title="公开数据到统计结果",
            nodes=nodes,
            edges=(FigureEdge("raw", "analysis", relation="transforms", label="读取"),),
            caption="数据分析流程",
            note="不表达医学因果。",
            schematic=ScientificSchematicSpec(
                panels=(SchematicPanel("A", "A", "流程"),),
                placements=(
                    SchematicPlacement("p-raw", "raw", "asset-a", "公开数据", "data", "A"),
                    SchematicPlacement("p-analysis", "analysis", "asset-b", "统计分析", "analysis", "A"),
                ),
                connectors=(
                    SchematicConnector("p-raw", "p-analysis", "transforms", "模型改写"),
                ),
            ),
        )


def test_associational_relation_requires_explicit_non_causal_note():
    with pytest.raises(FigureValidationError, match="非因果"):
        recommend_figure_plan(
            figure_kind=FigureKind.RELATIONSHIP_GRAPH,
            semantic_role="变量关系",
            title="观察性关系",
            nodes=(FigureNode("a", "A"), FigureNode("b", "B")),
            edges=(FigureEdge("a", "b", relation="associational"),),
            caption="变量关系",
            note="可能存在因果关系。",
        )