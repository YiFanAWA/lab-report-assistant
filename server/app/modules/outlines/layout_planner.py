"""论文级交付物语义布局规划器（SPEC 0033）。

规划器只消费已确认大纲和真实执行产物，输出稳定、可解释的章节版式计划。
PPT/Word 渲染器不得各自复制 source_type、图表数量和内容密度的判断。
"""

from dataclasses import dataclass
from enum import StrEnum
import re


class LayoutKind(StrEnum):
    """跨 Word/PPT 的稳定版式语义。"""

    NARRATIVE = "narrative"
    DATA_OVERVIEW = "data_overview"
    METHOD_FLOW = "method_flow"
    RESULT_FOCUS = "result_focus"
    RESULT_COMPARE = "result_compare"
    SUMMARY = "summary"


@dataclass(frozen=True)
class SectionLayoutPlan:
    """单个大纲章节的版式计划。"""

    section: dict
    layout_kind: LayoutKind
    chart_artifacts: tuple[dict, ...]
    text_density: str
    steps: tuple[str, ...] = ()
    metrics: tuple[tuple[str, str], ...] = ()
    presentation_role: str = ""
    figure_family: str = ""

    @property
    def title(self) -> str:
        return str(self.section.get("title", "内容")) or "内容"

    @property
    def content(self) -> str:
        return str(self.section.get("content", ""))


_METRIC_PATTERN = re.compile(
    r"([^：:\n]{1,18})[：:]\s*([^，,。；;\n]{1,24})"
)
_STEP_SPLIT_PATTERN = re.compile(r"(?:\n+|[；;。]|\s*(?:\d+[.)、]|[①②③④⑤])\s*)")


def _text_density(content: str) -> str:
    """把正文长度归一为低/中/高密度，供渲染器做安全降级。"""

    length = len(" ".join(content.split()))
    if length <= 90:
        return "low"
    if length <= 260:
        return "medium"
    return "high"


def _extract_metrics(content: str) -> tuple[tuple[str, str], ...]:
    """提取已有文本中的标签-值对；不创建新数据。"""

    metrics: list[tuple[str, str]] = []
    for label, value in _METRIC_PATTERN.findall(content):
        cleaned_label = " ".join(label.lstrip("；;，,").split())
        cleaned_value = " ".join(value.split())
        if cleaned_label and cleaned_value:
            metrics.append((cleaned_label, cleaned_value))
    return tuple(metrics[:4])


def _extract_steps(content: str) -> tuple[str, ...]:
    """从已有分析文本提取步骤，无法识别时返回空。"""

    pieces = [" ".join(piece.split()) for piece in _STEP_SPLIT_PATTERN.split(content)]
    pieces = [piece for piece in pieces if len(piece) >= 3]
    return tuple(pieces[:5])


def _artifact_matches_section(artifact: dict, section: dict) -> bool:
    artifact_group = section.get("artifact_group")
    if artifact_group and artifact.get("artifact_group") != artifact_group:
        return False
    # 逻辑图可以由论文来源或已确认大纲创建，不一定挂在执行 run 上。
    # 唯一 artifact_group 已经是该章节的归属合同，不再用 execution_run_id
    # 把它错误过滤掉。
    if artifact_group:
        return True
    source_ids = section.get("source_ids", []) or []
    run_id = artifact.get("execution_run_id")
    return not source_ids or run_id in source_ids


def _charts_for_section(section: dict, execution_artifacts: list[dict]) -> tuple[dict, ...]:
    if section.get("source_type") != "EXECUTION" and not section.get("artifact_group"):
        return ()
    figure_family = str(section.get("figure_family", "")).strip()
    return tuple(
        artifact
        for artifact in execution_artifacts
        if artifact.get("artifact_type") == "CHART_PNG"
        and _artifact_matches_section(artifact, section)
        and (
            not figure_family
            or artifact.get("figure_visual_family") == figure_family
            or (artifact.get("figure_plan") or {}).get("visual_family") == figure_family
        )
    )


def plan_section_layouts(
    outline_sections: list[dict],
    execution_artifacts: list[dict],
) -> tuple[SectionLayoutPlan, ...]:
    """为大纲生成章节版式计划。

    语义优先级：source_type -> 图表数量 -> 文本密度。
    """

    plans: list[SectionLayoutPlan] = []
    for section in outline_sections:
        source_type = str(section.get("source_type", ""))
        content = str(section.get("content", ""))
        charts = _charts_for_section(section, execution_artifacts)

        if source_type == "SUMMARY":
            kind = LayoutKind.SUMMARY
        elif charts and len(charts) == 1:
            kind = LayoutKind.RESULT_FOCUS
        elif charts and len(charts) >= 2:
            kind = LayoutKind.RESULT_COMPARE
        elif source_type == "DATASET" and len(_extract_metrics(content)) >= 2:
            kind = LayoutKind.DATA_OVERVIEW
        elif source_type == "ANALYSIS" and len(_extract_steps(content)) >= 2:
            kind = LayoutKind.METHOD_FLOW
        elif source_type == "EXECUTION" and len(charts) == 1:
            kind = LayoutKind.RESULT_FOCUS
        elif source_type == "EXECUTION" and len(charts) >= 2:
            kind = LayoutKind.RESULT_COMPARE
        else:
            kind = LayoutKind.NARRATIVE

        plans.append(
            SectionLayoutPlan(
                section=section,
                layout_kind=kind,
                chart_artifacts=charts,
                text_density=_text_density(content),
                steps=_extract_steps(content) if kind == LayoutKind.METHOD_FLOW else (),
                metrics=_extract_metrics(content) if kind == LayoutKind.DATA_OVERVIEW else (),
                presentation_role=str(section.get("presentation_role", "")).strip(),
                figure_family=(
                    str(charts[0].get("figure_visual_family", "")).strip()
                    if charts else str(section.get("figure_family", "")).strip()
                ),
            )
        )
    return tuple(plans)
