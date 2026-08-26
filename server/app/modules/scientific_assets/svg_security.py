"""静态科研 SVG 的安全检查与资源上界。"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from xml.etree import ElementTree as ET

from .models import ScientificAssetError


MAX_SVG_BYTES = 2 * 1024 * 1024
MAX_SVG_ELEMENTS = 5_000
MAX_SVG_DEPTH = 64

_FORBIDDEN_ELEMENTS = {
    "script",
    "foreignobject",
    "iframe",
    "object",
    "embed",
    "audio",
    "video",
    "animate",
    "animatemotion",
    "animatetransform",
    "set",
}
_EXTERNAL_SCHEME = re.compile(r"^(?:https?|ftp|file|javascript):", re.IGNORECASE)


@dataclass(frozen=True)
class SvgInspection:
    width: float
    height: float
    view_box: str
    element_count: int
    max_depth: int


def _local_name(value: str) -> str:
    return value.rsplit("}", 1)[-1].lower()


def _parse_length(value: str | None) -> float | None:
    if not value:
        return None
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*(?:px|pt|mm|cm|in)?\s*", value)
    return float(match.group(1)) if match else None


def inspect_svg(svg_bytes: bytes) -> SvgInspection:
    """拒绝动态/外部内容，并返回可用于 manifest 对账的静态尺寸。"""

    if len(svg_bytes) > MAX_SVG_BYTES:
        raise ScientificAssetError("SVG 超过 2 MiB 上限")
    lowered = svg_bytes.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ScientificAssetError("SVG 不允许 DTD 或实体声明")
    try:
        root = ET.fromstring(svg_bytes)
    except ET.ParseError as exc:
        raise ScientificAssetError(f"SVG XML 无效：{exc}") from exc
    if _local_name(root.tag) != "svg":
        raise ScientificAssetError("资产根元素必须是 svg")

    element_count = 0
    max_depth = 0
    stack: list[tuple[ET.Element, int]] = [(root, 1)]
    while stack:
        element, depth = stack.pop()
        element_count += 1
        max_depth = max(max_depth, depth)
        if element_count > MAX_SVG_ELEMENTS:
            raise ScientificAssetError("SVG 元素数量超过 5,000 上限")
        if depth > MAX_SVG_DEPTH:
            raise ScientificAssetError("SVG 嵌套深度超过 64 上限")
        if _local_name(element.tag) in _FORBIDDEN_ELEMENTS:
            raise ScientificAssetError(f"SVG 包含禁止元素：{_local_name(element.tag)}")
        if _local_name(element.tag) == "style":
            style_text = (element.text or "").strip().lower()
            if "@import" in style_text or "javascript:" in style_text:
                raise ScientificAssetError("SVG style 元素包含动态或外部内容")
            for match in re.finditer(r"url\(([^)]+)\)", style_text):
                target = match.group(1).strip(" \t\"'")
                if not target.startswith("#"):
                    raise ScientificAssetError("SVG style 元素包含外部 URL")
        for raw_name, raw_value in element.attrib.items():
            name = _local_name(raw_name)
            value = raw_value.strip()
            lowered_value = value.lower()
            if name.startswith("on"):
                raise ScientificAssetError(f"SVG 包含事件属性：{name}")
            if name in {"href", "src"}:
                if value and not value.startswith("#"):
                    raise ScientificAssetError(f"SVG 包含外部或内嵌资源引用：{name}")
            if name in {"style", "fill", "stroke", "filter", "clip-path", "mask"}:
                if "@import" in lowered_value or "javascript:" in lowered_value:
                    raise ScientificAssetError("SVG 样式包含动态或外部内容")
                for match in re.finditer(r"url\(([^)]+)\)", lowered_value):
                    target = match.group(1).strip(" \t\"'")
                    if not target.startswith("#"):
                        raise ScientificAssetError("SVG 样式包含外部 URL")
            if _EXTERNAL_SCHEME.match(lowered_value):
                raise ScientificAssetError("SVG 属性包含外部协议")
            for match in re.finditer(r"url\(([^)]+)\)", lowered_value):
                target = match.group(1).strip(" \t\"'")
                if not target.startswith("#"):
                    raise ScientificAssetError("SVG 属性包含外部 URL")
        stack.extend((child, depth + 1) for child in list(element))

    raw_view_box = root.attrib.get("viewBox") or root.attrib.get("viewbox")
    if not raw_view_box:
        raise ScientificAssetError("SVG 必须包含有效 viewBox")
    view_box_parts = raw_view_box.replace(",", " ").split()
    if len(view_box_parts) != 4:
        raise ScientificAssetError("SVG viewBox 必须包含四个数值")
    try:
        view_values = tuple(float(value) for value in view_box_parts)
    except ValueError as exc:
        raise ScientificAssetError("SVG viewBox 包含非数值") from exc
    if not all(math.isfinite(value) for value in view_values):
        raise ScientificAssetError("SVG viewBox 包含非有限数值")
    _, _, view_width, view_height = view_values
    if view_width <= 0 or view_height <= 0:
        raise ScientificAssetError("SVG viewBox 尺寸必须大于 0")
    width = _parse_length(root.attrib.get("width")) or view_width
    height = _parse_length(root.attrib.get("height")) or view_height
    return SvgInspection(width, height, " ".join(view_box_parts), element_count, max_depth)
