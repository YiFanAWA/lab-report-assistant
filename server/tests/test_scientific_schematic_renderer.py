"""SPEC 0042 科研示意图 renderer 测试。"""

from pathlib import Path

from PIL import Image

from app.infrastructure.renderers.scientific_schematic_renderer import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    ScientificSchematicRenderer,
)
from app.modules.outlines.figure_planner import (
    FigureEdge,
    FigureKind,
    FigureNode,
    ScientificSchematicSpec,
    SchematicConnector,
    SchematicPanel,
    SchematicPlacement,
    recommend_figure_plan,
)
from app.modules.scientific_assets import ScientificAssetRegistry


def test_renderer_uses_registered_assets_and_writes_metadata(tmp_path: Path):
    registry = ScientificAssetRegistry.load(Path("app/assets/scientific"))
    plan = recommend_figure_plan(
        figure_kind=FigureKind.DATA_PIPELINE,
        semantic_role="开放数据分析管线",
        title="公开数据到统计结果",
        nodes=(
            FigureNode("data", "开放数据", role="data"),
            FigureNode("analysis", "受控统计分析", role="analysis"),
            FigureNode("result", "结果图表", role="output"),
        ),
        edges=(
            FigureEdge("data", "analysis", relation="transforms", label="校验与建模"),
            FigureEdge("analysis", "result", relation="produces", label="生成结果"),
        ),
        caption="公开数据分析流程",
        note="流程不表达医学因果。",
        schematic=ScientificSchematicSpec(
            panels=(SchematicPanel("A", "A", "数据分析流程"),),
            placements=(
                SchematicPlacement("p1", "data", "bioicons-cc0-well-plate", "开放数据", "data", "A", 1),
                SchematicPlacement("p2", "analysis", "bioicons-cc0-algorithm", "受控统计分析", "analysis", "A", 2),
                SchematicPlacement("p3", "result", "bioicons-cc0-qpcr-plot", "结果图表", "output", "A", 3),
            ),
            connectors=(
                SchematicConnector("p1", "p2", "transforms", "校验与建模"),
                SchematicConnector("p2", "p3", "produces", "生成结果"),
            ),
            legend_items=("开放数据", "受控分析", "可追溯结果"),
        ),
    )
    output = tmp_path / "schematic.png"
    rendered = ScientificSchematicRenderer(registry).render(plan, output)
    assert output.is_file()
    assert Path(rendered.metadata_path).is_file()
    assert rendered.asset_ids == (
        "bioicons-cc0-algorithm",
        "bioicons-cc0-qpcr-plot",
        "bioicons-cc0-well-plate",
    )
    with Image.open(output) as image:
        assert image.size == (CANVAS_WIDTH, CANVAS_HEIGHT)
        assert image.info["dpi"][0] >= 299
    artifact = rendered.to_artifact(
        plan,
        name="开放数据分析流程",
        execution_run_id="run-spec0042",
        artifact_group="scientific_schematic",
    )
    assert artifact["file_path"] == str(output)
    assert artifact["scientific_asset_ids"] == list(rendered.asset_ids)
    assert artifact["scientific_asset_attributions"]
    assert all(
        "CC0-1.0" in value
        for value in artifact["scientific_asset_attributions"]
    )
    assert artifact["scientific_asset_render_metadata"] == rendered.metadata_path
    assert artifact["scientific_asset_image_sha256"] == rendered.image_sha256