"""SPEC 0042：开放科研组件驱动的确定性示意图 renderer。"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import hashlib
import json
import math
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont
import resvg_py

from app.modules.outlines.figure_planner import (
    FigurePlan,
    ScientificSchematicSpec,
    SchematicConnector,
    SchematicPlacement,
    figure_plan_to_artifact,
)
from app.modules.scientific_assets import ScientificAssetError, ScientificAssetRegistry

if TYPE_CHECKING:
    from PIL.ImageFont import FreeTypeFont


CANVAS_WIDTH = 2400
CANVAS_HEIGHT = 1350
BACKGROUND = "#F7F8FA"
PANEL_FILL = "#FFFFFF"
PANEL_BORDER = "#D7DEE6"
TEXT = "#17212B"
MUTED = "#647281"
ARROW = "#4D6173"
TEAL = "#0B7189"
BLUE = "#3F6EA5"
ORANGE = "#C77700"
RED = "#B94B58"
GREEN = "#4E7B5B"
ROLE_COLORS = {
    "sample": TEAL,
    "data": TEAL,
    "quality": ORANGE,
    "transform": ORANGE,
    "group": BLUE,
    "analysis": ORANGE,
    "instrument": BLUE,
    "output": RED,
    "result": RED,
    "boundary": MUTED,
}


@dataclass(frozen=True)
class RenderedScientificSchematic:
    image_path: str
    metadata_path: str
    image_sha256: str
    asset_ids: tuple[str, ...]
    attributions: tuple[str, ...]

    def to_artifact(
        self,
        plan: FigurePlan,
        *,
        name: str,
        execution_run_id: str = "",
        artifact_group: str = "",
    ) -> dict[str, object]:
        """映射为 Word/PPT 共用的执行产物，并保留资产级追溯。"""

        artifact = figure_plan_to_artifact(
            plan,
            name=name,
            file_path=self.image_path,
            execution_run_id=execution_run_id,
            artifact_group=artifact_group,
        )
        artifact.update(
            {
                "scientific_asset_ids": list(self.asset_ids),
                "scientific_asset_attributions": list(self.attributions),
                "scientific_asset_render_metadata": self.metadata_path,
                "scientific_asset_image_sha256": self.image_sha256,
            }
        )
        return artifact


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _font(size: int, *, bold: bool = False) -> FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default(size=size)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: FreeTypeFont) -> float:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def _wrap_text(
    draw: ImageDraw.ImageDraw, text: str, font: FreeTypeFont, max_width: float
) -> list[str]:
    lines: list[str] = []
    current = ""
    for character in text:
        candidate = current + character
        if current and _text_width(draw, candidate, font) > max_width:
            lines.append(current)
            current = character
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:3]


def _render_asset_icon(
    registry: ScientificAssetRegistry,
    asset_id: str,
    *,
    width: int,
    height: int,
) -> Image.Image:
    source = registry.source_path(asset_id)
    # 原始 SVG 已由注册表执行安全、许可证和哈希门禁；转换器不接收任意路径。
    # 让 resvg 按 SVG 自身 viewBox/物理单位解析；部分开放 SVG 使用 mm，
    # 强制覆盖 width/height 会触发绑定库的尺寸冲突。Pillow 统一最终包围框。
    png_bytes = resvg_py.svg_to_bytes(
        svg_path=str(source), dpi=96.0, skip_system_fonts=True
    )
    icon = Image.open(BytesIO(png_bytes)).convert("RGBA")
    icon.thumbnail((width, height), Image.Resampling.LANCZOS)
    return icon


def _panel_boxes(count: int) -> list[tuple[int, int, int, int]]:
    left, top, right, bottom = 70, 175, CANVAS_WIDTH - 70, CANVAS_HEIGHT - 115
    if count == 1:
        return [(left, top, right, bottom)]
    if count == 2:
        gap = 36
        width = (right - left - gap) // 2
        return [
            (left, top, left + width, bottom),
            (left + width + gap, top, right, bottom),
        ]
    columns = 2
    rows = math.ceil(count / columns)
    gap = 30
    width = (right - left - gap) // columns
    height = (bottom - top - gap * (rows - 1)) // rows
    return [
        (
            left + (index % columns) * (width + gap),
            top + (index // columns) * (height + gap),
            left + (index % columns) * (width + gap) + width,
            top + (index // columns) * (height + gap) + height,
        )
        for index in range(count)
    ]


def _topological_levels(
    placements: list[SchematicPlacement], connectors: tuple[SchematicConnector, ...]
) -> dict[str, int]:
    ids = [placement.placement_id for placement in placements]
    incoming = {placement_id: 0 for placement_id in ids}
    outgoing = {placement_id: [] for placement_id in ids}
    for connector in connectors:
        if connector.source_placement_id in outgoing and connector.target_placement_id in incoming:
            outgoing[connector.source_placement_id].append(connector.target_placement_id)
            incoming[connector.target_placement_id] += 1
    queue = [placement_id for placement_id in ids if incoming[placement_id] == 0]
    levels = {placement_id: 0 for placement_id in queue}
    while queue:
        source = queue.pop(0)
        for target in outgoing[source]:
            levels[target] = max(levels.get(target, 0), levels[source] + 1)
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
    # 环或孤立异常不让 renderer 猜关系：按清单顺序保守排布。
    if len(levels) != len(ids):
        return {placement_id: index for index, placement_id in enumerate(ids)}
    return levels


def _layout_panel(
    box: tuple[int, int, int, int],
    placements: list[SchematicPlacement],
    connectors: tuple[SchematicConnector, ...],
) -> dict[str, tuple[int, int]]:
    left, top, right, bottom = box
    inner_left, inner_right = left + 105, right - 105
    inner_top, inner_bottom = top + 190, bottom - 120
    levels = _topological_levels(placements, connectors)
    max_level = max(levels.values(), default=0)
    grouped: dict[int, list[SchematicPlacement]] = {}
    for placement in placements:
        grouped.setdefault(levels[placement.placement_id], []).append(placement)
    positions: dict[str, tuple[int, int]] = {}
    for level, group in grouped.items():
        x = int(
            inner_left
            if max_level == 0
            else inner_left + (inner_right - inner_left) * level / max_level
        )
        if len(group) == 1:
            ys = [(inner_top + inner_bottom) // 2]
        else:
            span = min(inner_bottom - inner_top, 300 * (len(group) - 1))
            start = (inner_top + inner_bottom - span) / 2
            ys = [int(start + span * index / (len(group) - 1)) for index in range(len(group))]
        for placement, y in zip(group, ys):
            positions[placement.placement_id] = (x, y)
    return positions


def _draw_bezier_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    color: str,
    dashed: bool,
) -> None:
    x1, y1 = start
    x2, y2 = end
    control_offset = max(70, abs(x2 - x1) * 0.38)
    points: list[tuple[float, float]] = []
    for index in range(41):
        t = index / 40
        one = 1 - t
        x = one**3 * x1 + 3 * one**2 * t * (x1 + control_offset) + 3 * one * t**2 * (x2 - control_offset) + t**3 * x2
        y = one**3 * y1 + 3 * one**2 * t * y1 + 3 * one * t**2 * y2 + t**3 * y2
        points.append((x, y))
    if dashed:
        for index in range(0, len(points) - 1, 4):
            draw.line(points[index:min(index + 3, len(points))], fill=color, width=7)
    else:
        draw.line(points, fill=color, width=7, joint="curve")
    angle = math.atan2(points[-1][1] - points[-3][1], points[-1][0] - points[-3][0])
    size = 24
    tip = points[-1]
    arrow = [
        tip,
        (
            tip[0] - size * math.cos(angle - math.pi / 6),
            tip[1] - size * math.sin(angle - math.pi / 6),
        ),
        (
            tip[0] - size * math.cos(angle + math.pi / 6),
            tip[1] - size * math.sin(angle + math.pi / 6),
        ),
    ]
    draw.polygon(arrow, fill=color)


class ScientificSchematicRenderer:
    """将 FigurePlan + 已验证资产注册表生成高分辨率论文示意图。"""

    def __init__(self, registry: ScientificAssetRegistry) -> None:
        self.registry = registry

    def render(self, plan: FigurePlan, output_path: str | Path) -> RenderedScientificSchematic:
        if not isinstance(plan.schematic, ScientificSchematicSpec):
            raise ScientificAssetError("FigurePlan 不包含科研示意图合同")
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), BACKGROUND)
        draw = ImageDraw.Draw(canvas)
        title_font = _font(54, bold=True)
        panel_title_font = _font(30, bold=True)
        label_font = _font(28, bold=True)
        role_font = _font(20)
        small_font = _font(18)
        draw.text((74, 54), plan.title, fill=TEXT, font=title_font)
        draw.line((74, 132, CANVAS_WIDTH - 74, 132), fill="#CED7E0", width=3)

        schematic = plan.schematic
        panel_boxes = _panel_boxes(len(schematic.panels))
        positions: dict[str, tuple[int, int]] = {}
        for panel, box in zip(schematic.panels, panel_boxes):
            left, top, right, bottom = box
            draw.rounded_rectangle(box, radius=28, fill=PANEL_FILL, outline=PANEL_BORDER, width=3)
            badge = (left + 34, top + 30, left + 92, top + 88)
            draw.rounded_rectangle(badge, radius=14, fill="#E5F1F4")
            draw.text((left + 51, top + 38), panel.label, fill=TEAL, font=panel_title_font)
            draw.text((left + 112, top + 36), panel.title, fill=TEXT, font=panel_title_font)
            panel_placements = [
                placement for placement in schematic.placements if placement.panel_id == panel.panel_id
            ]
            panel_connectors = tuple(
                connector
                for connector in schematic.connectors
                if any(p.placement_id == connector.source_placement_id for p in panel_placements)
                and any(p.placement_id == connector.target_placement_id for p in panel_placements)
            )
            positions.update(_layout_panel(box, panel_placements, panel_connectors))

        # 先画连接，再画组件，箭头端点由图标留白覆盖，避免穿过图标主体。
        for connector in schematic.connectors:
            source = positions[connector.source_placement_id]
            target = positions[connector.target_placement_id]
            source_anchor = (source[0] + 92, source[1])
            target_anchor = (target[0] - 92, target[1])
            _draw_bezier_arrow(
                draw,
                source_anchor,
                target_anchor,
                color=RED if connector.style == "inhibitory" else ARROW,
                dashed=connector.style == "dashed",
            )
            if connector.label:
                mid = ((source_anchor[0] + target_anchor[0]) // 2, (source_anchor[1] + target_anchor[1]) // 2 - 38)
                bbox = draw.textbbox(mid, connector.label, font=small_font, anchor="mm")
                draw.rounded_rectangle(
                    (bbox[0] - 14, bbox[1] - 8, bbox[2] + 14, bbox[3] + 8),
                    radius=10,
                    fill="#FFFFFF",
                    outline="#D5DDE5",
                    width=2,
                )
                draw.text(mid, connector.label, fill=MUTED, font=small_font, anchor="mm")

        attributions: list[str] = []
        asset_ids: list[str] = []
        for placement in schematic.placements:
            x, y = positions[placement.placement_id]
            asset = self.registry.get(placement.asset_id)
            asset_ids.append(asset.asset_id)
            attribution = asset.attribution_text or (
                f"{asset.title} — {asset.source_name}; {asset.author or '公共领域'}; "
                f"{asset.license_id}; {asset.upstream_file_url}"
            )
            attributions.append(attribution)
            role_color = ROLE_COLORS.get(placement.role, BLUE)
            draw.ellipse((x - 98, y - 98, x + 98, y + 98), fill="#F1F5F8")
            icon = _render_asset_icon(self.registry, placement.asset_id, width=166, height=146)
            canvas.paste(
                icon,
                (x - icon.width // 2, y - icon.height // 2 - 7),
                icon,
            )
            if placement.step_number is not None:
                badge = (x - 112, y - 112, x - 66, y - 66)
                draw.ellipse(badge, fill=role_color)
                draw.text((x - 89, y - 89), str(placement.step_number), fill="white", font=small_font, anchor="mm")
            lines = _wrap_text(draw, placement.label, label_font, 230)
            label_y = y + 118
            for line_index, line in enumerate(lines):
                draw.text((x, label_y + line_index * 34), line, fill=TEXT, font=label_font, anchor="ma")
            draw.text((x, label_y + len(lines) * 34 + 8), placement.role, fill=role_color, font=role_font, anchor="ma")

        legend_y = CANVAS_HEIGHT - 70
        legend = "  ·  ".join(schematic.legend_items)
        if legend:
            draw.text((74, legend_y), f"图例：{legend}", fill=MUTED, font=small_font)
        draw.text(
            (CANVAS_WIDTH - 74, legend_y),
            "组件：开放许可科研资产库 · 关系：FigurePlan 已确认节点/边",
            fill=MUTED,
            font=small_font,
            anchor="ra",
        )
        canvas.save(output, format="PNG", optimize=True, dpi=(300, 300))

        metadata_path = output.with_suffix(".json")
        metadata = {
            "figure_plan": plan.to_metadata(),
            "image_path": str(output),
            "image_sha256": _sha256(output),
            "asset_ids": sorted(set(asset_ids)),
            "asset_source_sha256": {
                asset_id: self.registry.get(asset_id).source_sha256
                for asset_id in sorted(set(asset_ids))
            },
            "attributions": sorted(set(attributions)),
            "renderer": "ScientificSchematicRenderer/spec0042",
            "canvas": {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "dpi": 300},
        }
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return RenderedScientificSchematic(
            image_path=str(output),
            metadata_path=str(metadata_path),
            image_sha256=metadata["image_sha256"],
            asset_ids=tuple(metadata["asset_ids"]),
            attributions=tuple(metadata["attributions"]),
        )
