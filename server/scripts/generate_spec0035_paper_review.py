"""生成 SPEC 0037 论文级论文解读案例。

案例仍使用 Diabetes 130-US Hospitals 与 Strack 等 2014 年开放论文，
但把原来的统一柱状图改为按数据语义选择图表：样本流程、构成图、缺失率
排序图、点估计置信区间、自然顺序趋势图、森林图和论文/本地 Dumbbell 对照。
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import sys
import textwrap
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "server"))

from app.infrastructure.renderers.ppt_renderer import PptRenderer
from app.infrastructure.documents.docx_pdf_exporter import DocxPdfExporter
from app.infrastructure.renderers.word_renderer import WordRenderer
from app.modules.outlines.chart_planner import ChartPlan, recommend_chart_plan
from app.modules.outlines.figure_planner import (
    ArgumentPlan,
    FigureEdge,
    FigureFamily,
    FigureKind,
    FigureNode,
    FigurePortfolioPlan,
    RejectedFigureCandidate,
    figure_plan_to_artifact,
    recommend_figure_plan,
)


OUTPUT_DIR = PROJECT_ROOT / "server" / "dev-docs" / "e2e-screenshots" / "spec0035_paper_review"
DATA_PATH = OUTPUT_DIR / "data" / "diabetic_data.csv"
SOURCE_DIR = OUTPUT_DIR / "sources"
CHART_DIR = OUTPUT_DIR / "charts"
RUN_ID = "spec0040_argumentation"
PUBLICATION_PREFIX = "spec0043_publication"
MISSING_TOKENS = {"?", "", "NaN", "nan", "NULL", "Unknown", "Unknown/Invalid"}
A1C_MEASURED_VALUES = {">8", ">7", "Norm"}
A1C_NOT_MEASURED_VALUE = "None"
DEATH_HOSPICE_DISPOSITION_IDS = {11, 13, 14, 19, 20, 21}
PRIMARY_DIAGNOSIS_GROUPS = (
    "Circulatory",
    "Respiratory",
    "Digestive",
    "Diabetes",
    "Injury",
    "Musculoskeletal",
    "Genitourinary",
    "Neoplasms",
    "Other",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _publication_artifacts(artifacts: list[dict]) -> list[dict]:
    """构造论文正文投影，保留渲染所需路径，移除工程追溯字段。"""
    projection = []
    for artifact in artifacts:
        item = dict(artifact)
        for key in (
            "scientific_asset_image_sha256",
            "scientific_asset_render_metadata",
            "scientific_asset_ids",
            "scientific_asset_attributions",
        ):
            item.pop(key, None)
        item["execution_run_id"] = ""
        item["figure_note"] = item.get("figure_note") or "数据来源与分析边界见正文及参考文献。"
        projection.append(item)
    return projection

def _rate(frame: pd.DataFrame, mask: pd.Series) -> float:
    if int(mask.sum()) == 0:
        return 0.0
    return float(frame.loc[mask, "early_readmission"].mean())


def _wilson(count: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    p = count / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _risk_summary(frame: pd.DataFrame, mask: pd.Series) -> dict:
    subset = frame.loc[mask]
    total = len(subset)
    count = int(subset["early_readmission"].sum())
    lower, upper = _wilson(count, total)
    return {
        "n": total,
        "events": count,
        "rate": count / total if total else 0.0,
        "ci_low": lower,
        "ci_high": upper,
    }


def _write_csv(path: Path, rows: list[list[object]], artifact_group: str) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    return {
        "name": path.name,
        "artifact_type": "TABLE_CSV",
        "file_path": str(path),
        "execution_run_id": RUN_ID,
        "artifact_group": artifact_group,
    }


def _chart_artifact(
    path: Path,
    name: str,
    artifact_group: str,
    chart_plan: ChartPlan,
) -> dict:
    return {
        "name": name,
        "artifact_type": "CHART_PNG",
        "file_path": str(path),
        "execution_run_id": RUN_ID,
        "artifact_group": artifact_group,
        "chart_kind": chart_plan.kind.value,
        "chart_encoding": chart_plan.encoding,
        "chart_rationale": chart_plan.rationale,
    }


def _academic_artifact(artifact: dict, *, caption: str, note: str) -> dict:
    """为论文渲染补充题注元数据，不改变执行产物的核心合同。"""
    artifact = dict(artifact)
    argument = ArgumentPlan(
        claim=caption,
        evidence_refs=(str(artifact["name"]),),
        method=str(artifact.get("chart_encoding", "统计图编码")),
        result="图中呈现与题名对应的分布、比较、趋势或效应区间。",
        boundary=note,
        body_reference="见对应结果章节",
    )
    plan = recommend_figure_plan(
        figure_kind=FigureKind.DATA_CHART,
        semantic_role="data_chart",
        title=caption,
        data_artifact_ids=(str(artifact["name"]),),
        execution_run_ids=(str(artifact.get("execution_run_id", "")),),
        caption=caption,
        note=note,
        rationale=str(artifact.get("chart_rationale", "基于数值比较、分布或不确定性选择统计图。")),
        layout_profile="single_focus",
        data_requirements=(
            f"真实数值产物：{artifact['name']}",
            "图表编码与分析意图一致",
        ),
        selection_rationale=str(artifact.get("chart_rationale", "按数据语义选择统计图。")),
        chart_kind=str(artifact.get("chart_kind", "")),
        chart_encoding=str(artifact.get("chart_encoding", "")),
        argument=argument,
        body_reference="见对应结果章节",
    )
    artifact.update(figure_plan_to_artifact(
        plan,
        name=str(artifact["name"]),
        file_path=str(artifact["file_path"]),
        artifact_type=str(artifact.get("artifact_type", "CHART_PNG")),
        execution_run_id=str(artifact.get("execution_run_id", "")),
        artifact_group=str(artifact.get("artifact_group", "")),
    ))
    artifact["figure_caption"] = caption
    artifact["figure_note"] = note
    return artifact


def _save_bar_chart(
    path: Path,
    title: str,
    labels: list[str],
    values: list[float],
    ylabel: str,
    *,
    errors: list[tuple[float, float]] | None = None,
    percent: bool = True,
    colors: list[str] | None = None,
) -> None:
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(8, 4.8), layout="constrained")
    palette = colors or ["#1F4E79", "#4F81BD", "#A9C6E8", "#F28E2B", "#6B8E9E"]
    positions = list(range(len(values)))
    bars = ax.bar(positions, values, color=palette[: len(values)], width=0.62)
    if errors:
        lower = [max(0, value - low) for value, (low, _high) in zip(values, errors)]
        upper = [max(0, high - value) for value, (_low, high) in zip(values, errors)]
        ax.errorbar(positions, values, yerr=[lower, upper], fmt="none", ecolor="#222222", capsize=4, linewidth=1.2)
    ax.set_title(title, fontsize=15, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_xticks(positions, labels, fontsize=9)
    ax.grid(axis="y", alpha=0.18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for bar, value in zip(bars, values):
        label = f"{value:.1%}" if percent else f"{value:,.0f}"
        ax.text(bar.get_x() + bar.get_width() / 2, value, label, ha="center", va="bottom", fontsize=9)
    if percent:
        ax.set_ylim(0, max(values) * 1.28 if values else 1)
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def _save_horizontal_bar_chart(
    path: Path,
    title: str,
    labels: list[str],
    values: list[float],
    xlabel: str,
) -> None:
    import matplotlib.pyplot as plt

    _set_chart_style()
    positions = list(range(len(labels)))[::-1]
    plotted_labels = labels[::-1]
    plotted_values = values[::-1]
    fig, ax = plt.subplots(figsize=(8.4, 4.5), layout="constrained")
    bars = ax.barh(positions, plotted_values, color=CHART_COLORS[0], height=0.55)
    ax.set_yticks(positions, plotted_labels, fontsize=9)
    ax.set_xlabel(xlabel)
    ax.set_title(title, fontsize=15, fontweight="bold", loc="left")
    ax.grid(axis="x", alpha=0.18)
    ax.spines[["top", "right", "left"]].set_visible(False)
    for bar, value in zip(bars, plotted_values):
        ax.text(value, bar.get_y() + bar.get_height() / 2, f" {value:.1%}", va="center", fontsize=9)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


FIGURE_TEXT = "#1F2933"
FIGURE_MUTED = "#68737D"
FIGURE_GRID = "#D9E0E6"
FIGURE_NAVY = "#1F4E79"
FIGURE_BLUE = "#4F81BD"
FIGURE_TEAL = "#0B6173"
FIGURE_ORANGE = "#D97706"
FIGURE_RED = "#B74752"
FIGURE_GREEN = "#5B7F5E"
CHART_COLORS = [FIGURE_NAVY, FIGURE_BLUE, "#A9C6E8", FIGURE_ORANGE, FIGURE_GREEN]


def _set_chart_style() -> None:
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans", "Arial"],
        "axes.unicode_minus": False,
        "axes.titleweight": "bold",
        "axes.titlesize": 15,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "axes.linewidth": 1.0,
        "grid.color": FIGURE_GRID,
        "grid.linewidth": 0.8,
        "grid.alpha": 0.7,
        "savefig.dpi": 300,
    })


def _save_semantic_figure(
    path: Path,
    title: str,
    nodes: tuple[FigureNode, ...],
    edges: tuple[FigureEdge, ...],
    positions: dict[str, tuple[float, float]],
    *,
    footer: str,
) -> None:
    """将已校验的 FigurePlan 节点/边绘制为高 DPI 逻辑图。"""
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    _set_chart_style()
    fig, ax = plt.subplots(figsize=(10.4, 4.6), layout="constrained")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    node_lookup = {node.node_id: node for node in nodes}
    for edge in edges:
        start = positions[edge.source_node_id]
        end = positions[edge.target_node_id]
        style = "--" if edge.evidence_status == "uncertain" else "-"
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops={
                "arrowstyle": "-|>",
                "color": "#7A8793",
                "lw": 1.7,
                "linestyle": style,
                "shrinkA": 38,
                "shrinkB": 38,
                "connectionstyle": "arc3,rad=0.02",
            },
            zorder=1,
        )
        if edge.label:
            midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + 0.045)
            ax.text(
                midpoint[0], midpoint[1], edge.label,
                ha="center", va="center", fontsize=8.5, color="#45515C",
                bbox={"boxstyle": "round,pad=0.22", "facecolor": "white", "edgecolor": "#D9E0E6"},
                zorder=3,
            )

    colors = {
        "source": ("#E7F1F3", "#0B6173"),
        "data": ("#EDF3FA", "#4A6FA5"),
        "analysis": ("#FFF4E5", "#B56B00"),
        "boundary": ("#F1F3F5", "#68737D"),
        "outcome": ("#FBEAEC", "#B74752"),
        "covariate": ("#EEF5ED", "#5B7F5E"),
    }
    for node in nodes:
        x, y = positions[node.node_id]
        face, edge_color = colors.get(node.role, ("#F5F7F9", "#65717C"))
        box = FancyBboxPatch(
            (x - 0.085, y - 0.095), 0.17, 0.19,
            boxstyle="round,pad=0.012,rounding_size=0.025",
            facecolor=face, edgecolor=edge_color, linewidth=1.5,
            zorder=2,
        )
        ax.add_patch(box)
        label = "\n".join(textwrap.wrap(node.label, width=11))
        ax.text(x, y + 0.008, label, ha="center", va="center", fontsize=9.5,
                color="#1F2933", fontweight="bold", zorder=4)
        if node.role:
            ax.text(x, y - 0.072, node.role, ha="center", va="center", fontsize=7.5,
                    color=edge_color, zorder=4)

    ax.text(0.01, 0.965, title, ha="left", va="top", fontsize=15,
            color="#1F2933", fontweight="bold")
    ax.text(0.01, 0.015, footer, ha="left", va="bottom", fontsize=8.5,
            color="#68737D")
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def _save_evidence_argument_figure(
    path: Path,
    plan,
    *,
    meta: dict,
    footer: str,
    figure_title: str | None = None,
) -> None:
    """绘制期刊级多面板证据论证图，而不是线性来源流程图。"""
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

    _set_chart_style()
    # 证据论证图在 Word 中需要保留论文式面板密度，在 PPT 中又不能
    # 因为内容页的纵向标题区被压成缩略图，因此采用接近内容页的
    # 2.4:1 画布。面板仍保持 2×2 结构，信息复杂度不靠缩小字体换取。
    fig, axes = plt.subplots(2, 2, figsize=(16.0, 6.6), layout="constrained")
    fig.patch.set_facecolor("white")
    panel_colors = {
        "source": ("#E9F2F4", "#0B6173"),
        "data": ("#EDF3FA", "#4A6FA5"),
        "analysis": ("#FFF4E5", "#B56B00"),
        "result": ("#F3EDF8", "#7653A6"),
        "boundary": ("#F1F3F5", "#68737D"),
        "compare": ("#FBEAEC", "#B74752"),
    }

    def panel(ax, letter: str, title: str) -> None:
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.add_patch(Rectangle((0, 0), 1, 1, facecolor="white", edgecolor="#D9E0E6", linewidth=1.0))
        ax.text(0.035, 0.955, letter, ha="left", va="top", fontsize=13, fontweight="bold", color="#0B6173")
        ax.text(0.095, 0.955, title, ha="left", va="top", fontsize=11.5, fontweight="bold", color="#1F2933")

    def box(ax, x: float, y: float, w: float, h: float, text: str, role: str, *, fontsize: float = 8.5) -> None:
        face, edge = panel_colors[role]
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.012,rounding_size=0.018",
            facecolor=face, edgecolor=edge, linewidth=1.2,
        ))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize,
                color="#1F2933", fontweight="bold", wrap=True)

    def arrow(ax, start: tuple[float, float], end: tuple[float, float], *, color: str = "#7A8793", dashed: bool = False) -> None:
        ax.add_patch(FancyArrowPatch(
            start, end, arrowstyle="-|>", mutation_scale=10,
            linewidth=1.3, color=color, linestyle="--" if dashed else "-",
            shrinkA=5, shrinkB=5,
        ))

    total_records = int(meta.get("total_records", 101766))
    measured_records = int(meta.get("a1c_measured_records", 17018))
    local_rate = float(meta.get("a1c_measurement_rate", measured_records / max(total_records, 1)))
    measured_rate = float(meta.get("early_rate_measured", 0.0984839582))
    unmeasured_rate = float(meta.get("early_rate_unmeasured", 0.1142327843))
    risk_difference = float(meta.get("risk_difference", measured_rate - unmeasured_rate))
    risk_ci = meta.get("risk_difference_ci", [-0.0207, -0.0108])
    a1c_missing = float(meta.get("top_missingness", {}).get("A1Cresult", 0.8328))
    paper_sample = int(meta.get("paper_final_sample", 69984))
    paper_rate = float(meta.get("paper_reported_a1c_measurement_rate", 0.184))
    panel(axes[0, 0], "A", "Original paper: research question and claim")
    box(axes[0, 0], 0.08, 0.65, 0.84, 0.18, "Research question\nHbA1c testing and 30-day readmission", "source")
    box(axes[0, 0], 0.08, 0.36, 0.38, 0.16, f"Open paper\nFinal sample {paper_sample:,}", "source", fontsize=8.0)
    box(axes[0, 0], 0.54, 0.36, 0.38, 0.16, "Original method\nVariable definitions and study design", "analysis", fontsize=8.0)
    arrow(axes[0, 0], (0.50, 0.65), (0.50, 0.54))
    arrow(axes[0, 0], (0.28, 0.36), (0.40, 0.26))
    arrow(axes[0, 0], (0.73, 0.36), (0.60, 0.26))
    box(axes[0, 0], 0.18, 0.08, 0.64, 0.14, f"Reported claim\nHbA1c testing rate {paper_rate:.1%}", "result", fontsize=8.2)

    panel(axes[0, 1], "B", "Open data: source and analytic scope")
    box(axes[0, 1], 0.07, 0.66, 0.86, 0.16, f"UCI dataset · {total_records:,} records · 47 features", "data", fontsize=8.3)
    box(axes[0, 1], 0.07, 0.39, 0.27, 0.14, "Field definition\nHbA1c / readmitted", "data", fontsize=7.7)
    box(axes[0, 1], 0.365, 0.39, 0.27, 0.14, f"Missingness\nA1Cresult {a1c_missing:.1%}", "analysis", fontsize=7.7)
    box(axes[0, 1], 0.66, 0.39, 0.27, 0.14, f"Local cohort\n{measured_records:,} measured", "analysis", fontsize=7.7)
    arrow(axes[0, 1], (0.50, 0.66), (0.205, 0.54))
    arrow(axes[0, 1], (0.50, 0.66), (0.50, 0.54))
    arrow(axes[0, 1], (0.50, 0.66), (0.795, 0.54))
    box(axes[0, 1], 0.16, 0.10, 0.68, 0.14, "Scope check\nPublic CSV and paper final sample are different cohorts", "boundary", fontsize=8.0)
    arrow(axes[0, 1], (0.50, 0.39), (0.50, 0.25), dashed=True)

    panel(axes[1, 0], "C", "Local review: method and results")
    box(axes[1, 0], 0.08, 0.66, 0.25, 0.16, f"Group comparison\n{measured_rate:.1%} vs {unmeasured_rate:.1%}", "analysis", fontsize=8.0)
    box(axes[1, 0], 0.375, 0.66, 0.25, 0.16, f"Risk difference\n{risk_difference * 100:.1f} percentage points", "result", fontsize=8.0)
    box(axes[1, 0], 0.67, 0.66, 0.25, 0.16, f"95% CI\n[{float(risk_ci[0]) * 100:.1f}%, {float(risk_ci[1]) * 100:.1f}%]", "result", fontsize=8.0)
    arrow(axes[1, 0], (0.33, 0.74), (0.37, 0.74))
    arrow(axes[1, 0], (0.625, 0.74), (0.665, 0.74))
    box(axes[1, 0], 0.08, 0.37, 0.40, 0.15, "Simplified logistic review\n9 variables · OR and 95% CI", "analysis", fontsize=8.0)
    box(axes[1, 0], 0.52, 0.37, 0.40, 0.15, "Result outputs\nFigures and summary tables", "result", fontsize=8.0)
    arrow(axes[1, 0], (0.50, 0.66), (0.28, 0.53), dashed=True)
    arrow(axes[1, 0], (0.50, 0.66), (0.72, 0.53), dashed=True)
    box(axes[1, 0], 0.16, 0.10, 0.68, 0.14, "Interpretation\nResults can be traced to the public CSV and analysis tables", "data", fontsize=8.0)
    arrow(axes[1, 0], (0.50, 0.37), (0.50, 0.25), dashed=True)

    panel(axes[1, 1], "D", "Comparability: evidence and interpretation boundary")
    box(axes[1, 1], 0.07, 0.69, 0.39, 0.14, f"Original paper\n{paper_rate:.1%} testing rate\nFinal sample {paper_sample:,}", "source", fontsize=7.8)
    box(axes[1, 1], 0.54, 0.69, 0.39, 0.14, f"Local review\n{local_rate:.1%} testing rate\nPublic CSV {total_records:,}", "data", fontsize=7.8)
    arrow(axes[1, 1], (0.46, 0.76), (0.54, 0.76), color=FIGURE_RED, dashed=True)
    axes[1, 1].text(0.50, 0.83, "Not directly equivalent", ha="center", va="center", fontsize=8.0, color=FIGURE_RED, fontweight="bold")
    box(axes[1, 1], 0.07, 0.39, 0.86, 0.16, "Comparable elements: research question, key variables, and directional evidence", "compare", fontsize=8.1)
    box(axes[1, 1], 0.07, 0.10, 0.86, 0.16, "Boundary: local review is not a full replication; observational association is not causation", "boundary", fontsize=8.0)
    arrow(axes[1, 1], (0.50, 0.69), (0.50, 0.55), dashed=True)
    arrow(axes[1, 1], (0.50, 0.39), (0.50, 0.27), dashed=True)

    fig.suptitle(figure_title or plan.title, x=0.02, y=1.01, ha="left", va="bottom", fontsize=17,
                 color=FIGURE_TEXT, fontweight="bold")
    fig.text(0.02, -0.005, footer, ha="left", va="bottom", fontsize=8.5, color=FIGURE_MUTED)
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def _semantic_artifact(
    path: Path,
    name: str,
    artifact_group: str,
    plan,
) -> dict:
    return figure_plan_to_artifact(
        plan,
        name=name,
        file_path=str(path),
        artifact_type="CHART_PNG",
        execution_run_id=RUN_ID,
        artifact_group=artifact_group,
    )


def _save_relationship_figure(
    path: Path,
    plan,
    *,
    footer: str,
    figure_title: str | None = None,
) -> None:
    """以无交叉的研究设计结构绘制观察性变量关系图。"""
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    _set_chart_style()
    fig, ax = plt.subplots(figsize=(10.4, 4.6), layout="constrained")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    colors = {
        "exposure": ("#EDF3FA", "#4A6FA5"),
        "outcome": ("#FBEAEC", "#B74752"),
        "covariate": ("#EEF5ED", "#5B7F5E"),
    }
    node_by_id = {node.node_id: node for node in plan.nodes}

    def draw_box(x: float, y: float, width: float, height: float, label: str, role: str) -> None:
        face, edge_color = colors.get(role, ("#F5F7F9", "#65717C"))
        ax.add_patch(FancyBboxPatch(
            (x - width / 2, y - height / 2), width, height,
            boxstyle="round,pad=0.012,rounding_size=0.025",
            facecolor=face, edgecolor=edge_color, linewidth=1.6, zorder=2,
        ))
        ax.text(x, y + 0.008, "\n".join(textwrap.wrap(label, width=15)),
                ha="center", va="center", fontsize=10.5, fontweight="bold",
                color="#1F2933", zorder=3)
        ax.text(x, y - height / 2 + 0.045, role, ha="center", va="center",
                fontsize=8, color=edge_color, zorder=3)

    exposure = node_by_id["exposure"]
    outcome = node_by_id["outcome"]
    covariates = [node_by_id["age"], node_by_id["complexity"]]
    draw_box(0.24, 0.62, 0.24, 0.20, exposure.label.replace("\n", " "), "exposure")
    draw_box(0.76, 0.62, 0.24, 0.20, outcome.label.replace("\n", " "), "outcome")
    ax.annotate("", xy=(0.64, 0.62), xytext=(0.36, 0.62),
                arrowprops={"arrowstyle": "-|>", "color": "#6B7785", "lw": 1.8})
    ax.text(0.50, 0.69, "Observational association", ha="center", va="center", fontsize=9,
            color="#45515C", bbox={"boxstyle": "round,pad=0.22", "facecolor": "white", "edgecolor": FIGURE_GRID})
    ax.add_patch(FancyBboxPatch(
        (0.20, 0.08), 0.60, 0.20,
        boxstyle="round,pad=0.012,rounding_size=0.025",
        facecolor="#EEF5ED", edgecolor="#5B7F5E", linewidth=1.5, zorder=2,
    ))
    cov_label = "; ".join(node.label.replace("\n", " ") for node in covariates)
    ax.text(0.50, 0.18, cov_label, ha="center", va="center", fontsize=10,
            color="#1F2933", fontweight="bold", zorder=3)
    ax.text(0.50, 0.115, "Stratification / covariate review", ha="center", va="center", fontsize=8,
            color=FIGURE_GREEN, zorder=3)
    for x in (0.31, 0.69):
        ax.plot([0.50, x], [0.28, 0.50], color="#7A8793", lw=1.4,
                linestyle="--", zorder=1)
    ax.text(0.01, 0.965, figure_title or plan.title, ha="left", va="top", fontsize=15,
            color=FIGURE_TEXT, fontweight="bold")
    ax.text(0.01, 0.015, footer, ha="left", va="bottom", fontsize=8.5,
            color=FIGURE_MUTED)
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def _save_stacked_composition_chart(
    path: Path, title: str, labels: list[str], values: list[int]
) -> None:
    import matplotlib.pyplot as plt

    _set_chart_style()
    total = sum(values) or 1
    fig, ax = plt.subplots(figsize=(8.6, 3.8), layout="constrained")
    left = 0.0
    for index, (label, value) in enumerate(zip(labels, values)):
        share = value / total
        ax.barh(
            ["All records"], [share], left=left,
            color=CHART_COLORS[index % len(CHART_COLORS)], height=0.52, label=label,
        )
        if share >= 0.06:
            ax.text(
                left + share / 2, 0, f"{share:.1%}",
                ha="center", va="center", color="white", fontsize=10, fontweight="bold",
            )
        left += share
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(lambda value, _position: f"{value:.0%}")
    ax.set_title(title, fontsize=15, fontweight="bold", loc="left")
    ax.legend(
        ncol=len(labels), bbox_to_anchor=(0, -0.22), loc="upper left",
        frameon=False, fontsize=9,
    )
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _save_point_ci_chart(
    path: Path,
    title: str,
    labels: list[str],
    values: list[float],
    intervals: list[tuple[float, float]],
) -> None:
    import matplotlib.pyplot as plt

    _set_chart_style()
    positions = list(range(len(labels)))[::-1]
    plotted_values = values[::-1]
    plotted_intervals = intervals[::-1]
    lower = [[value - interval[0] for value, interval in zip(plotted_values, plotted_intervals)]]
    upper = [[interval[1] - value for value, interval in zip(plotted_values, plotted_intervals)]]
    fig, ax = plt.subplots(figsize=(8.4, 4.5), layout="constrained")
    ax.errorbar(
        plotted_values, positions, xerr=lower + upper,
        fmt="o", color=CHART_COLORS[0], ecolor=CHART_COLORS[0],
        capsize=4, markersize=7, linewidth=2,
    )
    ax.set_yticks(positions, labels[::-1], fontsize=10)
    ax.xaxis.set_major_formatter(lambda value, _position: f"{value:.1%}")
    ax.set_xlabel("30-day readmission rate; points = estimates, lines = 95% CI")
    ax.set_title(title, fontsize=15, fontweight="bold", loc="left")
    ax.grid(axis="x", alpha=0.18)
    ax.spines[["top", "right", "left"]].set_visible(False)
    for value, position in zip(plotted_values, positions):
        ax.text(value, position + 0.16, f"{value:.1%}", ha="center", fontsize=9)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)



def _save_diagnosis_interaction_chart(
    path: Path, rows: list[dict]
) -> None:
    """绘制主要诊断分层下的 HbA1c 组间率和 Wilson 区间。"""

    import matplotlib.pyplot as plt

    _set_chart_style()
    labels = [row["group"] for row in rows][::-1]
    positions = list(range(len(labels)))
    measured_values = [row["measured_rate"] for row in rows][::-1]
    unmeasured_values = [row["not_measured_rate"] for row in rows][::-1]
    measured_intervals = [row["measured_ci"] for row in rows][::-1]
    unmeasured_intervals = [row["not_measured_ci"] for row in rows][::-1]
    colors = (CHART_COLORS[0], CHART_COLORS[3])
    fig, ax = plt.subplots(figsize=(9.2, 6.4), layout="constrained")
    for offset, values, intervals, color, label in (
        (0.11, measured_values, measured_intervals, colors[0], "已检测"),
        (-0.11, unmeasured_values, unmeasured_intervals, colors[1], "未检测"),
    ):
        lower = [[value - interval[0] for value, interval in zip(values, intervals)]]
        upper = [[interval[1] - value for value, interval in zip(values, intervals)]]
        ax.errorbar(
            values,
            [position + offset for position in positions],
            xerr=lower + upper,
            fmt="o",
            color=color,
            ecolor=color,
            capsize=3,
            markersize=6,
            linewidth=1.6,
            label=label,
        )
    ax.set_yticks(positions, labels, fontsize=9.5)
    ax.xaxis.set_major_formatter(lambda value, _position: f"{value:.0%}")
    ax.set_xlabel("30 天内再入院率；点为估计值，线为 Wilson 95% CI")
    ax.set_title("主要诊断分层与 HbA1c 检测状态", fontsize=15, fontweight="bold", loc="left")
    ax.grid(axis="x", alpha=0.18)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(frameon=False, loc="lower right")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _save_ordered_line_chart(
    path: Path, title: str, labels: list[str], values: list[float]
) -> None:
    import matplotlib.pyplot as plt

    _set_chart_style()
    positions = list(range(len(labels)))
    fig, ax = plt.subplots(figsize=(8.4, 4.5), layout="constrained")
    ax.plot(
        positions, values, color=CHART_COLORS[0], marker="o",
        linewidth=2.4, markersize=7,
    )
    ax.fill_between(positions, values, [0] * len(values), color=CHART_COLORS[0], alpha=0.08)
    ax.set_xticks(positions, labels, fontsize=9)
    ax.yaxis.set_major_formatter(lambda value, _position: f"{value:.0%}")
    ax.set_ylabel("30-day readmission rate")
    ax.set_title(title, fontsize=15, fontweight="bold", loc="left")
    ax.grid(axis="y", alpha=0.18)
    ax.spines[["top", "right"]].set_visible(False)
    for position, value in zip(positions, values):
        ax.text(position, value + max(values) * 0.035, f"{value:.1%}", ha="center", fontsize=9)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _save_dumbbell_chart(
    path: Path, title: str, labels: list[str], values: list[float]
) -> None:
    import matplotlib.pyplot as plt

    _set_chart_style()
    fig, ax = plt.subplots(figsize=(8.4, 3.6), layout="constrained")
    left, right = min(values), max(values)
    ax.plot([left, right], [0, 0], color="#AAB4BE", linewidth=3, zorder=1)
    ax.scatter(
        [left, right], [0, 0], s=90,
        color=[CHART_COLORS[0], CHART_COLORS[1]], zorder=2,
    )
    for value, label, color in zip(values, labels, [CHART_COLORS[0], CHART_COLORS[1]]):
        ax.text(
            value, 0.13, f"{label}\n{value:.1%}", ha="center", va="bottom",
            color=color, fontsize=10, fontweight="bold",
        )
    ax.set_xlim(max(0, left - 0.03), right + 0.03)
    ax.xaxis.set_major_formatter(lambda value, _position: f"{value:.0%}")
    ax.set_yticks([])
    ax.set_xlabel("HbA1c testing rate")
    ax.set_title(title, fontsize=15, fontweight="bold", loc="left")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", alpha=0.18)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _save_comparison_matrix_figure(
    path: Path,
    title: str,
    rows: list[tuple[str, str, str, str]],
    *,
    footer: str,
) -> None:
    """绘制论文—本地复核比较矩阵，保留口径、方法和可比性边界。"""
    import matplotlib.pyplot as plt

    _set_chart_style()
    fig, ax = plt.subplots(figsize=(12.0, 4.7), layout="constrained")
    ax.axis("off")
    table = ax.table(
        cellText=[list(row) for row in rows],
        colLabels=["Dimension", "Original paper", "Local open-data review", "Comparability"],
        colWidths=[0.16, 0.27, 0.30, 0.27],
        cellLoc="left",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10.5)
    table.scale(1.0, 2.65)
    for (row_index, column_index), cell in table.get_celld().items():
        cell.set_edgecolor("#D9E0E6")
        cell.set_linewidth(0.8)
        cell.PAD = 0.025
        if row_index == 0:
            cell.set_facecolor("#0B6173")
            cell.get_text().set_color("white")
            cell.get_text().set_fontweight("bold")
            cell.get_text().set_ha("center")
        else:
            cell.set_facecolor("#F7FAFC" if row_index % 2 else "#EEF5F7")
            cell.get_text().set_color("#1F2933")
            cell.get_text().set_va("center")
            if column_index == 0:
                cell.get_text().set_fontweight("bold")
    ax.set_title(title, loc="left", fontsize=16, fontweight="bold", color="#1F2933", pad=8)
    fig.text(0.01, 0.012, footer, ha="left", va="bottom", fontsize=8.8, color="#68737D")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _save_flow_chart(path: Path, stages: list[tuple[str, int]], artifact_group: str) -> dict:
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    _set_chart_style()
    fig, ax = plt.subplots(figsize=(10, 3.8), layout="constrained")
    ax.set_xlim(0, len(stages))
    ax.set_ylim(0, 1)
    ax.axis("off")
    for index, (label, value) in enumerate(stages):
        x = index + 0.08
        box = FancyBboxPatch(
            (x, 0.28), 0.82, 0.42,
            boxstyle="round,pad=0.02,rounding_size=0.04",
            facecolor=CHART_COLORS[index % len(CHART_COLORS)],
            edgecolor="none",
        )
        ax.add_patch(box)
        ax.text(x + 0.41, 0.51, label, ha="center", va="center", color="white", fontsize=9)
        ax.text(x + 0.41, 0.17, f"{value:,} records", ha="center", va="center", fontsize=10, fontweight="bold")
        if index < len(stages) - 1:
            ax.annotate(
                "", xy=(x + 0.96, 0.49), xytext=(x + 0.84, 0.49),
                arrowprops={"arrowstyle": "-|>", "color": "#9AA6B2", "lw": 1.5},
            )
    ax.set_title("Sample inclusion and analytic scope", fontsize=15, fontweight="bold", loc="left")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _save_missingness_chart(path: Path, missing_rates: pd.Series) -> None:
    import matplotlib.pyplot as plt

    _set_chart_style()

    values = missing_rates.sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(8, 4.8), layout="constrained")
    ax.barh([str(value) for value in values.index], values.values, color=CHART_COLORS[2])
    ax.set_title("Top fields by missingness", fontsize=15, fontweight="bold", loc="left")
    ax.set_xlabel("Missing rate")
    ax.xaxis.set_major_formatter(lambda value, _position: f"{value:.0%}")
    ax.grid(axis="x", alpha=0.18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for index, value in enumerate(values.values):
        ax.text(value, index, f" {value:.1%}", va="center", fontsize=9)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _save_forest_chart(path: Path, rows: list[dict]) -> None:
    import matplotlib.pyplot as plt

    _set_chart_style()

    display = [row["variable"] for row in rows][::-1]
    odds = [row["odds_ratio"] for row in rows][::-1]
    low = [row["ci_low"] for row in rows][::-1]
    high = [row["ci_high"] for row in rows][::-1]
    positions = list(range(len(display)))
    fig, ax = plt.subplots(figsize=(8.2, 5.4), layout="constrained")
    ax.errorbar(
        odds,
        positions,
        xerr=[[odds[i] - low[i] for i in range(len(odds))], [high[i] - odds[i] for i in range(len(odds))]],
        fmt="o",
        color=CHART_COLORS[0],
        ecolor=CHART_COLORS[0],
        capsize=3,
    )
    ax.axvline(1.0, color=CHART_COLORS[1], linestyle="--", linewidth=1)
    ax.set_yticks(positions, display, fontsize=9)
    ax.set_xscale("log")
    ax.set_xlabel("Odds ratio (log scale); 95% CI")
    ax.set_title("HbA1c × primary diagnosis interaction model", fontsize=15, fontweight="bold", loc="left")
    ax.grid(axis="x", alpha=0.18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _age_midpoint(value: str) -> float:
    match = re.match(r"\[(\d+)-(\d+)\)", str(value))
    return (int(match.group(1)) + int(match.group(2))) / 2 if match else 50.0


def _zscore(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return (numeric - numeric.mean()) / numeric.std(ddof=0)


def _a1c_status(value: object) -> str:
    """区分已检测、明确未检测和真正缺失/未知。"""

    value = str(value).strip()
    if value in A1C_MEASURED_VALUES:
        return "measured"
    if value == A1C_NOT_MEASURED_VALUE:
        return "not_measured"
    return "missing_or_unknown"


def _primary_diagnosis_group(value: object) -> str:
    """按原论文 Table 2 的 ICD-9 三位码规则映射主要诊断。"""

    value = str(value).strip()
    try:
        code = float(value)
    except (TypeError, ValueError):
        return "Other"
    if 390 <= code <= 459 or code == 785:
        return "Circulatory"
    if 460 <= code <= 519 or code == 786:
        return "Respiratory"
    if 520 <= code <= 579 or code == 787:
        return "Digestive"
    if 250 <= code < 251:
        return "Diabetes"
    if 800 <= code <= 999:
        return "Injury"
    if 710 <= code <= 739:
        return "Musculoskeletal"
    if 580 <= code <= 629 or code == 788:
        return "Genitourinary"
    if 140 <= code <= 239:
        return "Neoplasms"
    return "Other"


def _primary_diagnosis_missing(value: object) -> bool:
    value = str(value).strip()
    return value in MISSING_TOKENS or value in {"None", "nan"}


def _annotate_analysis_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """给原始记录添加分析合同字段；不在这里做队列筛选。"""

    frame = raw.copy()
    frame["discharge_disposition_numeric"] = pd.to_numeric(
        frame["discharge_disposition_id"], errors="coerce"
    )
    frame["death_hospice"] = frame["discharge_disposition_numeric"].isin(
        DEATH_HOSPICE_DISPOSITION_IDS
    )
    frame["outcome_known"] = frame["readmitted"].isin({"NO", ">30", "<30"})
    frame["early_readmission"] = frame["readmitted"].eq("<30")
    frame["a1c_status"] = frame["A1Cresult"].map(_a1c_status)
    frame["primary_diagnosis_group"] = frame["diag_1"].map(_primary_diagnosis_group)
    frame["primary_diagnosis_missing"] = frame["diag_1"].map(_primary_diagnosis_missing)
    frame["age_mid"] = frame["age"].map(_age_midpoint)
    return frame


def _safe_exp(value: float) -> float:
    return float(math.exp(min(700.0, max(-700.0, value))))


def _p_value_from_z(z_value: float, norm) -> float:
    """用 log survival function 避免极小 P 值下溢为 0。"""

    if not math.isfinite(z_value):
        return 1.0
    log_p = math.log(2.0) + float(norm.logsf(abs(z_value)))
    import numpy as np

    min_positive = float(np.nextafter(0.0, 1.0))
    return min_positive if log_p < math.log(min_positive) else float(math.exp(log_p))


def _format_p_value(value: float) -> str:
    if not math.isfinite(value):
        return "NA"
    if value < 0.001:
        return "<0.001"
    if value < 0.01:
        return f"{value:.3f}"
    return f"{value:.2f}"


def _zscore(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return (numeric - numeric.mean()) / numeric.std(ddof=0)


def _fit_logistic(df: pd.DataFrame, *, model_name: str) -> dict:
    """拟合教学性 Logistic，并以 patient_nbr 聚类的 sandwich SE 报告不确定性。"""

    import numpy as np
    from scipy.stats import chi2, norm
    from sklearn.linear_model import LogisticRegression

    model_frame = df.loc[
        df["outcome_known"]
        & df["a1c_status"].isin({"measured", "not_measured"})
        & ~df["primary_diagnosis_missing"]
        & ~df["gender"].eq("Unknown/Invalid")
    ].copy()
    features = pd.DataFrame(index=model_frame.index)
    features["a1c_measured"] = model_frame["a1c_status"].eq("measured").astype(float)
    for diagnosis in PRIMARY_DIAGNOSIS_GROUPS[1:]:
        indicator = model_frame["primary_diagnosis_group"].eq(diagnosis).astype(float)
        features[f"dx_{diagnosis}"] = indicator
        features[f"a1c_x_{diagnosis}"] = features["a1c_measured"] * indicator
    for column in (
        "age_mid",
        "time_in_hospital",
        "num_lab_procedures",
        "num_medications",
        "number_diagnoses",
        "number_inpatient",
    ):
        features[f"{column}_per_1SD"] = _zscore(model_frame[column])
    features["male"] = model_frame["gender"].eq("Male").astype(float)
    features["diabetes_med"] = model_frame["diabetesMed"].eq("Yes").astype(float)
    features = features.replace([np.inf, -np.inf], np.nan)
    valid = features.notna().all(axis=1)
    features = features.loc[valid]
    y = model_frame.loc[valid, "early_readmission"].astype(int).to_numpy()
    groups = model_frame.loc[valid, "patient_nbr"].to_numpy()

    model = LogisticRegression(C=1e9, solver="lbfgs", max_iter=2000)
    model.fit(features, y)
    design = np.column_stack([np.ones(len(features)), features.to_numpy(dtype=float)])
    probabilities = model.predict_proba(features)[:, 1]
    residuals = y - probabilities
    weights = probabilities * (1 - probabilities)
    bread = np.linalg.pinv(design.T @ (design * weights[:, None]))
    cluster_ids, cluster_index = np.unique(groups, return_inverse=True)
    cluster_scores = np.zeros((len(cluster_ids), design.shape[1]), dtype=float)
    np.add.at(cluster_scores, cluster_index, design * residuals[:, None])
    meat = cluster_scores.T @ cluster_scores
    covariance = bread @ meat @ bread
    if len(cluster_ids) > 1 and len(y) > design.shape[1]:
        covariance *= (len(cluster_ids) / (len(cluster_ids) - 1)) * (
            (len(y) - 1) / (len(y) - design.shape[1])
        )
    standard_errors = np.sqrt(np.maximum(np.diag(covariance), 0))
    coefficients = np.concatenate([model.intercept_, model.coef_[0]])
    internal_columns = list(features.columns)
    display_labels = {
        "a1c_measured": "HbA1c 已检测（相对未检测）",
        "male": "男性（相对女性）",
        "diabetes_med": "使用糖尿病药物（相对否）",
        "age_mid_per_1SD": "年龄（每 1 SD）",
        "time_in_hospital_per_1SD": "住院天数（每 1 SD）",
        "num_lab_procedures_per_1SD": "实验室检查数（每 1 SD）",
        "num_medications_per_1SD": "用药数（每 1 SD）",
        "number_diagnoses_per_1SD": "诊断数（每 1 SD）",
        "number_inpatient_per_1SD": "既往住院次数（每 1 SD）",
    }
    for diagnosis in PRIMARY_DIAGNOSIS_GROUPS[1:]:
        display_labels[f"dx_{diagnosis}"] = f"主要诊断：{diagnosis}（相对循环系统）"
        display_labels[f"a1c_x_{diagnosis}"] = f"HbA1c × 主要诊断：{diagnosis}"

    rows: list[dict] = []
    column_index = {name: index + 1 for index, name in enumerate(internal_columns)}
    for internal_name in internal_columns:
        index = column_index[internal_name]
        coefficient = float(coefficients[index])
        standard_error = float(standard_errors[index])
        z_value = coefficient / standard_error if standard_error > 0 else math.inf
        p_value = _p_value_from_z(z_value, norm)
        rows.append({
            "term": internal_name,
            "variable": display_labels[internal_name],
            "odds_ratio": _safe_exp(coefficient),
            "ci_low": _safe_exp(coefficient - 1.96 * standard_error),
            "ci_high": _safe_exp(coefficient + 1.96 * standard_error),
            "standard_error": standard_error,
            "p_value": p_value,
            "p_value_display": _format_p_value(p_value),
        })

    interaction_terms = [
        f"a1c_x_{diagnosis}" for diagnosis in PRIMARY_DIAGNOSIS_GROUPS[1:]
    ]
    interaction_positions = [column_index[name] for name in interaction_terms]
    restriction = np.zeros((len(interaction_positions), len(coefficients)))
    for row_index, position in enumerate(interaction_positions):
        restriction[row_index, position] = 1.0
    restricted_covariance = restriction @ covariance @ restriction.T
    restricted_beta = restriction @ coefficients
    joint_statistic = float(
        restricted_beta
        @ np.linalg.pinv(restricted_covariance)
        @ restricted_beta
    )
    joint_p_value = float(chi2.sf(joint_statistic, len(interaction_terms)))
    return {
        "model_name": model_name,
        "rows": rows,
        "n_model": int(len(y)),
        "events": int(y.sum()),
        "clusters": int(len(cluster_ids)),
        "records": int(len(df)),
        "excluded_from_model": int(len(df) - len(y)),
        "interaction_terms": interaction_terms,
        "interaction_joint_statistic": joint_statistic,
        "interaction_joint_p_value": joint_p_value,
        "interaction_joint_p_value_display": _format_p_value(joint_p_value),
        "reference_primary_diagnosis": "Circulatory",
        "cluster_variable": "patient_nbr",
    }

def _analyze() -> tuple[list[dict], dict]:
    import matplotlib

    matplotlib.use("Agg")
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(DATA_PATH, low_memory=False, keep_default_na=False)
    annotated = _annotate_analysis_frame(raw)
    indexed = annotated.sort_values("encounter_id", kind="mergesort").drop_duplicates(
        "patient_nbr", keep="first"
    )
    primary = indexed.loc[
        indexed["outcome_known"] & ~indexed["death_hospice"]
    ].copy()
    all_eligible = annotated.loc[
        annotated["outcome_known"] & ~annotated["death_hospice"]
    ].copy()
    index_with_death_hospice = indexed.loc[indexed["outcome_known"]].copy()
    exposure_frame = primary.loc[
        primary["a1c_status"].isin({"measured", "not_measured"})
    ].copy()
    total = len(raw)
    unique_patients = int(raw["patient_nbr"].nunique())
    repeated_patient_records = int(len(raw) - unique_patients)
    index_records = len(indexed)
    death_hospice_index = int(indexed["death_hospice"].sum())
    measured = int(exposure_frame["a1c_status"].eq("measured").sum())
    measured_risk = _risk_summary(
        exposure_frame, exposure_frame["a1c_status"].eq("measured")
    )
    unmeasured_risk = _risk_summary(
        exposure_frame, exposure_frame["a1c_status"].eq("not_measured")
    )
    overall_risk = _risk_summary(primary, pd.Series(True, index=primary.index))
    risk_difference = measured_risk["rate"] - unmeasured_risk["rate"]
    risk_difference_se = math.sqrt(
        measured_risk["rate"] * (1 - measured_risk["rate"]) / measured_risk["n"]
        + unmeasured_risk["rate"] * (1 - unmeasured_risk["rate"]) / unmeasured_risk["n"]
    )
    risk_difference_ci = (
        risk_difference - 1.96 * risk_difference_se,
        risk_difference + 1.96 * risk_difference_se,
    )

    normalized = raw.replace(list(MISSING_TOKENS), pd.NA)
    missing_rates = normalized.isna().mean().drop(
        labels=["readmitted"], errors="ignore"
    ).sort_values(ascending=False)
    top_missing = missing_rates.head(8)
    outcome_counts = primary["readmitted"].value_counts().reindex(
        ["NO", ">30", "<30"]
    ).fillna(0).astype(int)
    by_age = primary.groupby("age", sort=False)["early_readmission"].agg(
        ["count", "mean"]
    ).reset_index()
    by_stay = primary.groupby("time_in_hospital")["early_readmission"].agg(
        ["count", "mean"]
    ).reset_index()
    by_a1c = (
        exposure_frame.groupby("a1c_status", sort=False)["early_readmission"]
        .agg(["count", "mean"])
        .reset_index()
    )
    diagnosis_summary = []
    for diagnosis in PRIMARY_DIAGNOSIS_GROUPS:
        group = primary.loc[primary["primary_diagnosis_group"].eq(diagnosis)]
        measured_group = group.loc[group["a1c_status"].eq("measured")]
        unmeasured_group = group.loc[group["a1c_status"].eq("not_measured")]
        diagnosis_summary.append({
            "group": diagnosis,
            "n": int(len(group)),
            "events": int(group["early_readmission"].sum()),
            "rate": float(group["early_readmission"].mean()) if len(group) else 0.0,
            "measured_n": int(len(measured_group)),
            "measured_events": int(measured_group["early_readmission"].sum()),
            "measured_rate": float(measured_group["early_readmission"].mean()) if len(measured_group) else 0.0,
            "measured_ci": _wilson(int(measured_group["early_readmission"].sum()), len(measured_group)),
            "not_measured_n": int(len(unmeasured_group)),
            "not_measured_events": int(unmeasured_group["early_readmission"].sum()),
            "not_measured_rate": float(unmeasured_group["early_readmission"].mean()) if len(unmeasured_group) else 0.0,
            "not_measured_ci": _wilson(int(unmeasured_group["early_readmission"].sum()), len(unmeasured_group)),
        })
    model_fit = _fit_logistic(
        primary, model_name="primary_index_encounter_cluster_robust"
    )
    sensitivity_cluster_fit = _fit_logistic(
        all_eligible, model_name="all_eligible_encounters_clustered_by_patient"
    )
    sensitivity_death_fit = _fit_logistic(
        index_with_death_hospice,
        model_name="index_encounter_including_death_hospice_as_non_event",
    )
    model_rows = model_fit["rows"]
    model_plot_rows = [
        row for row in model_rows
        if row["term"] == "a1c_measured" or row["term"].startswith("a1c_x_")
    ]
    import platform
    from importlib.metadata import PackageNotFoundError, version

    def _package_version(name: str) -> str:
        try:
            return version(name)
        except PackageNotFoundError:
            return "unknown"

    software_versions = {
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": _package_version("numpy"),
        "scipy": _package_version("scipy"),
        "scikit_learn": _package_version("scikit-learn"),
        "matplotlib": _package_version("matplotlib"),
    }
    model_contract = {
        "analysis_position": "教学性论文复核报告，不是独立研究论文",
        "unit_of_analysis": "每位患者按 encounter_id 升序保留首个住院记录",
        "primary_cohort": "已知 readmitted 且排除 discharge disposition 11/13/14/19/20/21",
        "outcome": "readmitted=<30 编码为 1；NO 或 >30 编码为 0",
        "exposure": "A1Cresult 为 >8、>7 或 Norm 编码为已检测；字面 None 编码为明确未检测",
        "missing_handling": "A1Cresult 空值、问号、Unknown 或未识别编码单列为真正缺失/未知，不进入主暴露比较和模型",
        "primary_diagnosis": "diag_1 按原论文 Table 2 的 ICD-9 三位码规则分为 9 类，Circulatory 为参考组",
        "interaction": "HbA1c measurement × primary diagnosis group，报告联合 Wald χ² 检验",
        "covariates": "年龄、住院天数、实验室检查数、用药数、诊断数、既往住院次数按每 1 SD；性别和糖尿病药物使用为二元指示变量",
        "standard_errors": "按 patient_nbr 聚类的 sandwich/cluster-robust 标准误；主队列去重后每个患者一个观测，敏感性分析保留重复记录",
        "software_versions": software_versions,
    }

    flow_path = CHART_DIR / "sample_cohort_flow.png"
    _save_flow_chart(
        flow_path,
        [
            ("Raw CSV encounters", total),
            ("Unique patients", unique_patients),
            ("Index encounters", index_records),
            ("Exclude death/hospice", index_records - death_hospice_index),
            ("Primary analysis cohort", len(primary)),
        ], "sample_structure")
    missing_path = CHART_DIR / "missingness_top8.png"
    _save_missingness_chart(missing_path, top_missing)
    outcome_path = CHART_DIR / "outcome_distribution.png"
    _save_stacked_composition_chart(
        outcome_path,
        "30-day readmission outcome composition",
        ["No readmission", ">30 days", "<30 days"],
        outcome_counts.tolist(),
    )
    paper_compare_path = CHART_DIR / "paper_local_comparison.png"
    _save_dumbbell_chart(
        paper_compare_path,
        "Paper vs local review: HbA1c testing rate",
        ["Original paper", "Local CSV"],
        [0.184, measured / len(exposure_frame)],
    )
    matrix_path = CHART_DIR / "paper_local_comparison_matrix.png"
    _save_comparison_matrix_figure(
        matrix_path,
        "Paper vs local review: scope comparison matrix",
        [
            ("Research question", "HbA1c testing and 30-day readmission", "Same question and outcome definition", "Study logic is comparable"),
            ("Analysis cohort", "Final sample 69,984", f"Index cohort {len(primary):,}", "Different cohorts"),
            ("HbA1c testing rate", "18.4%", f"{measured / len(exposure_frame):.1%}", "Affected by sample and field handling"),
            ("Method level", "Original multivariable logistic model", "Descriptive comparison + simplified logistic model", "Not a full replication"),
            ("Interpretation boundary", "Observational database study", "Teaching-oriented local review", "No causal or clinical claim"),
        ],
        footer="Source: Strack et al. 2014, the UCI-296 public CSV, and local analytical results; the matrix compares scopes without merging the analyses.",
    )
    primary_path = CHART_DIR / "a1c_measurement_effect.png"
    _save_point_ci_chart(
        primary_path,
        "HbA1c testing and 30-day readmission",
        ["Measured", "Not measured"],
        [measured_risk["rate"], unmeasured_risk["rate"]],
        [(measured_risk["ci_low"], measured_risk["ci_high"]), (unmeasured_risk["ci_low"], unmeasured_risk["ci_high"])],
    )
    category_path = CHART_DIR / "a1c_category_readmission.png"
    _save_horizontal_bar_chart(
        category_path,
        "HbA1c status and 30-day readmission rate",
        ["已检测" if value == "measured" else "未检测" for value in by_a1c["a1c_status"]],
        by_a1c["mean"].tolist(),
        "30-day readmission rate",
    )
    age_path = CHART_DIR / "age_readmission.png"
    _save_ordered_line_chart(
        age_path,
        "Age group and 30-day readmission rate",
        [str(value) for value in by_age["age"]],
        by_age["mean"].tolist(),
    )
    stay_path = CHART_DIR / "stay_readmission.png"
    _save_ordered_line_chart(
        stay_path,
        "Length of stay and 30-day readmission rate",
        [str(value) for value in by_stay["time_in_hospital"]],
        by_stay["mean"].tolist(),
    )
    forest_path = CHART_DIR / "logistic_forest.png"
    _save_forest_chart(forest_path, model_plot_rows)
    diagnosis_path = CHART_DIR / "primary_diagnosis_a1c_interaction.png"
    _save_diagnosis_interaction_chart(diagnosis_path, diagnosis_summary)

    evidence_nodes = (
        FigureNode("research_question", "研究问题\nHbA1c 检测与再入院", role="source", source_ids=("paper:PMC3996476",)),
        FigureNode("paper", "开放论文\n原文样本 69,984 条", role="source", source_ids=("paper:PMC3996476",)),
        FigureNode("paper_method", "原文方法\n变量定义与研究设计", role="analysis", source_ids=("paper:PMC3996476",)),
        FigureNode("paper_claim", "原文主张\n检测率 18.4%", role="outcome", source_ids=("paper:PMC3996476",)),
        FigureNode("dataset", "UCI 数据集\n原始记录 101,766 条", role="data", source_ids=("dataset:UCI-296",)),
        FigureNode("field_check", "字段核查\nHbA1c / readmitted", role="analysis", execution_run_ids=(RUN_ID,)),
        FigureNode("missingness", f"真实缺失/未知\nA1Cresult {float(missing_rates.get('A1Cresult', 0.0)):.1%}", role="analysis", execution_run_ids=(RUN_ID,)),
        FigureNode("local_review", f"本地主队列\n已检测 {measured:,} 条", role="analysis", execution_run_ids=(RUN_ID,)),
        FigureNode("local_result", f"本地结果\n{measured_risk['rate']:.1%} vs {unmeasured_risk['rate']:.1%}", role="outcome", execution_run_ids=(RUN_ID,)),
        FigureNode("comparison", "可比性核对\n样本、变量、模型", role="compare", source_ids=("paper:PMC3996476", "dataset:UCI-296")),
        FigureNode("boundary", "解释边界\n不等于完整复现\n不代表因果", role="boundary", source_ids=("paper:PMC3996476", "dataset:UCI-296")),
    )
    evidence_edges = (
        FigureEdge("research_question", "paper", "defines", "研究对象"),
        FigureEdge("paper", "paper_method", "documents", "原文方法"),
        FigureEdge("paper_method", "paper_claim", "supports", "原文结论"),
        FigureEdge("dataset", "field_check", "contains", "字段入口"),
        FigureEdge("field_check", "missingness", "reveals", "缺失结构"),
        FigureEdge("missingness", "local_review", "qualifies", "口径核对"),
        FigureEdge("local_review", "local_result", "produces", "本地结果"),
        FigureEdge("paper_claim", "comparison", "compared_with", "原文对照"),
        FigureEdge("local_result", "comparison", "compared_with", "复核对照"),
        FigureEdge("comparison", "boundary", "bounded_by", "解释边界"),
    )
    evidence_plan = recommend_figure_plan(
        figure_kind=FigureKind.EVIDENCE_CHAIN,
        semantic_role="evidence_chain",
        title="研究证据链：来源、数据、复核与解释边界",
        nodes=evidence_nodes,
        edges=evidence_edges,
        source_ids=("paper:PMC3996476", "dataset:UCI-296"),
        execution_run_ids=(RUN_ID,),
        caption="研究证据链与解释边界",
        note="注：论文最终样本与公开 CSV 不是同一分析口径，本地复核不宣称完整复现原论文。",
        rationale="内容同时包含原论文主张、公开数据血缘、本地复核结果和可比性限制，因此选择多面板证据论证图，而不是线性流程图或树状图。",
        visual_family=FigureFamily.EVIDENCE_ARGUMENT,
        layout_profile="evidence_panels",
        data_requirements=("原论文主张与样本口径", "公开 CSV 字段与计数", "本地执行结果", "可比性边界"),
        selection_rationale="主张、来源、数据口径、本地结果和解释边界属于不同证据层，因此使用多面板论证图。",
        argument=ArgumentPlan(
            claim="本地复核用于核对研究逻辑，而非宣称完整复现原论文。",
            evidence_refs=("paper:PMC3996476", "dataset:UCI-296", RUN_ID),
            method="来源、公开数据与本地复核的证据链对照",
            result="论文结论与本地结果可以沿来源和执行批次回溯。",
            boundary="论文最终样本与公开 CSV 口径不同，不进行精确复现宣称。",
            body_reference="见第 2.1 节",
        ),
        legend_items=("论文主张", "公开数据", "本地复核", "结果对照", "解释边界"),
        panel_labels=("A 原论文", "B 数据口径", "C 本地复核", "D 证据对照"),
        body_reference="见第 2.1 节",
    )
    evidence_path = CHART_DIR / "evidence_chain.png"
    _save_evidence_argument_figure(
        evidence_path,
        evidence_plan,
        figure_title="Evidence chain: source, data, review, and interpretation boundary",
        meta={
            "execution_run_id": RUN_ID,
            "total_records": total,
            "a1c_measured_records": measured,
            "a1c_measurement_rate": measured / len(exposure_frame),
            "early_rate_measured": measured_risk["rate"],
            "early_rate_unmeasured": unmeasured_risk["rate"],
            "risk_difference": risk_difference,
            "risk_difference_ci": list(risk_difference_ci),
            "paper_final_sample": 69984,
            "paper_reported_a1c_measurement_rate": 0.184,
            "top_missingness": {str(key): float(value) for key, value in top_missing.items()},
        },
        footer="Source: open paper, UCI dataset, and local analytical results; panels A-D show the original claim, data scope, local review, and comparability boundary.",
    )

    pipeline_nodes = (
        FigureNode("raw", f"Raw CSV\n{total:,} encounters", role="source", source_ids=("dataset:UCI-296",)),
        FigureNode("quality", f"True missing/unknown\nA1Cresult {float(missing_rates.get('A1Cresult', 0.0)):.1%}", role="analysis", execution_run_ids=(RUN_ID,)),
        FigureNode("group", f"HbA1c groups\n{measured:,} measured", role="analysis", execution_run_ids=(RUN_ID,)),
        FigureNode("outcome", f"30-day readmission\noverall {overall_risk['rate']:.1%}", role="outcome", execution_run_ids=(RUN_ID,)),
        FigureNode("model", "Cluster-robust model\nprimary diagnosis interaction", role="analysis", execution_run_ids=(RUN_ID,)),
    )
    pipeline_edges = (
        FigureEdge("raw", "quality", "process", "retain missingness"),
        FigureEdge("quality", "group", "process", "define testing status"),
        FigureEdge("group", "outcome", "analysis", "group comparison"),
        FigureEdge("outcome", "model", "analysis", "covariate review"),
    )
    pipeline_plan = recommend_figure_plan(
        figure_kind=FigureKind.DATA_PIPELINE,
        semantic_role="data_pipeline",
        title="数据处理管线：从原始记录到可复核结果",
        nodes=pipeline_nodes,
        edges=pipeline_edges,
        data_artifact_ids=("primary_effect_summary.csv", "logistic_reanalysis.csv"),
        source_ids=("dataset:UCI-296", "paper:PMC3996476"),
        execution_run_ids=(RUN_ID,),
        caption="公开数据处理与分析产物管线",
        note="注：管线展示实际执行步骤；交互模型用于教学性复核，并不宣称完整复现原论文模型。",
        rationale="内容表达数据处理阶段和产物流转，适合数据管线图，不适合用统计图或层级树表达。",
        visual_family=FigureFamily.PROCESS,
        layout_profile="flow_stages",
        data_requirements=("有序处理阶段", "阶段之间存在真实转移关系", "每个阶段可追溯到来源或执行批次"),
        selection_rationale="内容是实际处理阶段和产物流转，流程语法比节点层级更准确。",
        argument=ArgumentPlan(
            claim="分析结果来自可复核的数据处理路径。",
            evidence_refs=("dataset:UCI-296", "primary_effect_summary.csv", "logistic_reanalysis.csv"),
            method="缺失结构检查、分组比较、置信区间与含主要诊断交互的 Logistic 复核",
            result="生成分组结果、风险差、森林图和结果索引。",
            boundary="交互模型仅为教学性复核，不等同原论文完整模型。",
            body_reference="见第 4.2 节",
        ),
        legend_items=("原始数据", "质量检查", "分析步骤", "结果产物"),
        body_reference="见第 4.2 节",
    )
    pipeline_path = CHART_DIR / "data_pipeline.png"
    _save_semantic_figure(
        pipeline_path,
        "Data processing pipeline: from raw records to auditable results",
        pipeline_nodes,
        pipeline_edges,
        {"raw": (0.10, 0.55), "quality": (0.30, 0.55), "group": (0.50, 0.55), "outcome": (0.70, 0.55), "model": (0.90, 0.55)},
        footer="Outputs: primary effect summary and model reanalysis.",
    )

    relationship_nodes = (
        FigureNode("exposure", "HbA1c\ntesting status", role="data", source_ids=("paper:PMC3996476",), execution_run_ids=(RUN_ID,)),
        FigureNode("outcome", "30-day\nreadmission", role="outcome", source_ids=("paper:PMC3996476",), execution_run_ids=(RUN_ID,)),
        FigureNode("age", "Age", role="covariate", execution_run_ids=(RUN_ID,)),
        FigureNode("complexity", "Length of stay and\ncare complexity", role="covariate", execution_run_ids=(RUN_ID,)),
    )
    relationship_edges = (
        FigureEdge("exposure", "outcome", "associational", "observational association", execution_run_ids=(RUN_ID,)),
        FigureEdge("age", "outcome", "adjusted", "stratification / covariates", execution_run_ids=(RUN_ID,)),
        FigureEdge("complexity", "outcome", "adjusted", "stratification / covariates", execution_run_ids=(RUN_ID,)),
        FigureEdge("complexity", "exposure", "potential_mixing", "potential shared signal", execution_run_ids=(RUN_ID,)),
    )
    relationship_plan = recommend_figure_plan(
        figure_kind=FigureKind.RELATIONSHIP_GRAPH,
        semantic_role="relationship_graph",
        title="变量关系图：关联、协变量与解释边界",
        nodes=relationship_nodes,
        edges=relationship_edges,
        source_ids=("paper:PMC3996476", "dataset:UCI-296"),
        execution_run_ids=(RUN_ID,),
        caption="HbA1c 检测、再入院结局与分析协变量的关系",
        note="注：图中为观察性关联，不代表因果关系；年龄与医疗复杂度用于分层或协变量复核。",
        rationale="关系图用于说明变量在分析设计中的位置；由于证据不支持确定因果，不绘制因果 DAG。",
        visual_family=FigureFamily.RELATIONSHIP,
        layout_profile="relationship_layers",
        data_requirements=("暴露、结局和协变量角色", "有语义的观察性边", "非因果解释边界"),
        selection_rationale="内容表达变量角色和观察性关联，而不是数值大小或样本阶段，因此使用分层关系图。",
        argument=ArgumentPlan(
            claim="HbA1c 检测状态与 30 天再入院之间存在观察性关联。",
            evidence_refs=("paper:PMC3996476", "primary_effect_summary.csv", RUN_ID),
            method="组间比例、分层描述与含主要诊断交互的协变量复核",
            result="已检测组与未检测组的再入院率存在描述性差异。",
            boundary="关联不代表因果；年龄、住院时长与医疗复杂度可能影响解释。",
            body_reference="见第 5.1 节",
        ),
        legend_items=("主要变量", "结局", "分层/协变量", "观察性关联"),
        body_reference="见第 5.1 节",
    )
    relationship_path = CHART_DIR / "variable_relationship.png"
    _save_relationship_figure(
        relationship_path,
        relationship_plan,
        figure_title="Variable relationships: association, covariates, and interpretation boundary",
        footer="Study design: the exposure and outcome are observationally associated; covariates are shown in a separate review layer.",
    )

    evidence_artifact = _semantic_artifact(evidence_path, "研究证据链图", "evidence_logic", evidence_plan)
    pipeline_artifact = _semantic_artifact(pipeline_path, "数据处理管线图", "method_logic", pipeline_plan)
    relationship_artifact = _semantic_artifact(relationship_path, "变量关系图", "relationship_logic", relationship_plan)

    matrix_plan = recommend_figure_plan(
        figure_kind=FigureKind.COMPARISON_MATRIX,
        semantic_role="comparison_matrix",
        title="论文与本地复核的口径比较矩阵",
        source_ids=("paper:PMC3996476", "dataset:UCI-296"),
        execution_run_ids=(RUN_ID,),
        data_artifact_ids=("paper_local_comparison_matrix.png",),
        caption="论文原文与本地公开数据复核的多维口径比较",
        note="注：矩阵用于比较研究问题、队列、检测率、方法层级和解释边界，不将两套分析合并为一次复现。",
        rationale="比较对象具有多个稳定维度，二维矩阵比流程图或单一差异图更适合呈现可比与不可比部分。",
        visual_family=FigureFamily.MATRIX,
        layout_profile="matrix_grid",
        data_requirements=("行维度：比较维度", "列维度：原论文/本地复核/可比性", "每个单元格均有来源或执行依据"),
        selection_rationale="多个对象在研究问题、队列、方法和边界上需要并列对应，使用比较矩阵而不是线性图。",
        argument=ArgumentPlan(
            claim="论文原文与本地复核在研究问题上可对照，但在队列和方法层级上不能等同。",
            evidence_refs=("paper:PMC3996476", "dataset:UCI-296", RUN_ID),
            method="研究问题、队列、检测率、方法和解释边界的多维对照",
            result="矩阵同时标出可比部分与不可直接交换的分析口径。",
            boundary="本地复核不等于原论文完整模型复现。",
            body_reference="见第 2.2 节",
        ),
        body_reference="见第 2.2 节",
    )
    matrix_artifact = _semantic_artifact(matrix_path, "论文与本地复核比较矩阵", "comparison_matrix", matrix_plan)

    portfolio_statistical_plan = recommend_figure_plan(
        figure_kind=FigureKind.DATA_CHART,
        semantic_role="statistical_result",
        title="统计结果：HbA1c 检测与 30 天再入院",
        data_artifact_ids=("a1c_measurement_effect.png", "primary_effect_summary.csv"),
        source_ids=("dataset:UCI-296",),
        execution_run_ids=(RUN_ID,),
        caption="HbA1c 检测状态与 30 天再入院率",
        note="注：点为组内比例，误差线为 Wilson 95% 置信区间；观察性关联不代表因果。",
        rationale="组间比例带有不确定性，使用点估计与置信区间而不是只显示柱高。",
        visual_family=FigureFamily.STATISTICAL,
        layout_profile="single_focus",
        data_requirements=("分组估计值", "Wilson 95% 置信区间", "真实执行产物"),
        selection_rationale="主张是组间差异及其不确定性，因此使用点区间图。",
        chart_kind="point_ci",
        chart_encoding="group -> point estimate + interval",
        argument=ArgumentPlan(
            claim="已检测组与未检测组的 30 天再入院率存在描述性差异。",
            evidence_refs=("primary_effect_summary.csv", RUN_ID),
            method="组间比例与 Wilson 95% 置信区间",
            result="点区间图同时呈现两组估计值及其不确定性。",
            boundary="观察性关联不代表检测行为造成风险变化。",
            body_reference="见第 5.1 节",
        ),
        body_reference="见第 5.1 节",
    )

    portfolio = FigurePortfolioPlan(
        figures=(evidence_plan, pipeline_plan, relationship_plan, matrix_plan, portfolio_statistical_plan),
        coverage=("evidence_argument", "process", "relationship", "matrix", "statistical"),
        selection_rationale=(
            "证据论证图回答主张与边界。",
            "流程图回答数据如何进入结果。",
            "关系图回答变量如何组织且不暗示因果。",
            "比较矩阵回答论文口径与本地复核如何对应。",
            "统计图回答大小、差异、不确定性和趋势。",
        ),
        rejected_candidates=(
            RejectedFigureCandidate(
                name="质量热力图",
                visual_family=FigureFamily.MATRIX,
                reason="当前案例只有字段级缺失率，没有可追溯的行×字段缺失矩阵。",
                missing_requirements=("行×字段缺失单元格", "质量矩阵执行产物"),
            ),
            RejectedFigureCandidate(
                name="时间线",
                visual_family=FigureFamily.TEMPORAL,
                reason="论文与公开 CSV 没有用于本地复核的事件时间序列，不能伪造时间轴。",
                missing_requirements=("可排序事件时间字段",),
            ),
        ),
    )

    flow_artifact = _academic_artifact(_chart_artifact(
        flow_path, "样本与分析口径流程图", "sample_structure",
        recommend_chart_plan(analysis_intent="sample_flow", value_kind="count"),
    ), caption="样本纳入与分析口径流程", note="注：流程展示患者去重、死亡/临终关怀排除和主分析队列；论文最终样本为原文报告口径。")
    missing_artifact = _academic_artifact(_chart_artifact(
        missing_path, "关键字段缺失率", "quality",
        recommend_chart_plan(analysis_intent="ranking", value_kind="proportion", category_count=8),
    ), caption="关键字段真正缺失/未知率排序", note="注：缺失率按字段的真正缺失/未知标记计算；A1Cresult 的字面 None 是明确未检测，不计为真正缺失。")
    outcome_artifact = _academic_artifact(_chart_artifact(
        outcome_path, "再入院结局分布", "sample_structure",
        recommend_chart_plan(analysis_intent="composition", value_kind="proportion", category_count=3),
    ), caption="30 天内再入院结局构成", note="注：<30、>30 与 NO 为原始数据中的结局标签。")
    paper_compare_artifact = _academic_artifact(_chart_artifact(
        paper_compare_path, "论文与本地检测率对照", "comparison",
        recommend_chart_plan(analysis_intent="paired_comparison", value_kind="proportion", comparison_count=2),
    ), caption="论文报告与本地复核的 HbA1c 检测率", note="注：两者分析口径不同，不应直接解释为复现误差。")
    primary_artifact = _academic_artifact(_chart_artifact(
        primary_path, "HbA1c 检测与 30 天再入院", "primary",
        recommend_chart_plan(analysis_intent="group_difference", value_kind="proportion", confidence_interval=True, comparison_count=2),
    ), caption="HbA1c 检测状态与 30 天再入院率", note="注：点为组内比例，误差线为 Wilson 95% 置信区间。")
    category_artifact = _academic_artifact(_chart_artifact(
        category_path, "HbA1c 分组再入院率", "primary",
        recommend_chart_plan(analysis_intent="ranking", value_kind="proportion", category_count=len(by_a1c)),
    ), caption="HbA1c 状态的 30 天再入院率", note="注：明确未检测作为独立状态保留；真正缺失/未知记录不进入主暴露比较，未进行无依据的插补。")
    age_artifact = _academic_artifact(_chart_artifact(
        age_path, "年龄分层再入院率", "stratified",
        recommend_chart_plan(analysis_intent="ordered_trend", value_kind="proportion", ordered=True, category_count=len(by_age)),
    ), caption="年龄组与 30 天再入院率", note="注：横轴按年龄组自然顺序排列，仅用于描述性分层。")
    stay_artifact = _academic_artifact(_chart_artifact(
        stay_path, "住院天数分层再入院率", "stratified",
        recommend_chart_plan(analysis_intent="ordered_trend", value_kind="proportion", ordered=True, category_count=len(by_stay)),
    ), caption="住院天数与 30 天再入院率", note="注：横轴为住院天数，结果不作为临床风险分层工具。")
    forest_artifact = _academic_artifact(_chart_artifact(
        forest_path, "HbA1c × 主要诊断交互森林图", "model",
        recommend_chart_plan(analysis_intent="model_effect", value_kind="effect"),
    ), caption="HbA1c × 主要诊断交互模型的优势比", note="注：误差线为按 patient_nbr 聚类的稳健 95% CI；循环系统为主要诊断参考组。")
    diagnosis_artifact = _academic_artifact(_chart_artifact(
        diagnosis_path, "主要诊断分层与 HbA1c 检测状态", "diagnosis_stratified",
        recommend_chart_plan(analysis_intent="group_difference", value_kind="proportion", confidence_interval=True, comparison_count=2),
    ), caption="主要诊断分层下 HbA1c 检测状态与 30 天再入院率", note="注：主要诊断按原论文 Table 2 的 ICD-9 规则映射；点为组内比例，误差线为 Wilson 95% CI；该图用于描述性分层，不替代交互模型。")
    interaction_rows = [
        row for row in model_rows
        if row["term"] == "a1c_measured" or row["term"].startswith("a1c_x_")
    ]
    model_table = _write_csv(CHART_DIR / "logistic_reanalysis.csv", [
        ["变量", "优势比 OR", "95% CI", "聚类稳健 SE", "P 值"],
        *[[row["variable"], f"{row['odds_ratio']:.3f}", f"[{row['ci_low']:.3f}, {row['ci_high']:.3f}]", f"{row['standard_error']:.4f}", row["p_value_display"]] for row in interaction_rows],
    ], "model")
    full_model_table = _write_csv(CHART_DIR / "logistic_reanalysis_full.csv", [
        ["变量", "优势比 OR", "95% CI 下限", "95% CI 上限", "聚类稳健 SE", "P 值"],
        *[[row["variable"], f"{row['odds_ratio']:.6g}", f"{row['ci_low']:.6g}", f"{row['ci_high']:.6g}", f"{row['standard_error']:.6g}", row["p_value_display"]] for row in model_rows],
    ], "model_full")
    a1c_status_counts = primary["a1c_status"].value_counts().reindex(
        ["measured", "not_measured", "missing_or_unknown"]
    ).fillna(0).astype(int)
    status_table = _write_csv(CHART_DIR / "a1c_status_summary.csv", [
        ["HbA1c 状态", "定义", "主队列 n", "占比"],
        ["已检测", "A1Cresult 为 >8、>7 或 Norm", int(a1c_status_counts["measured"]), f"{a1c_status_counts['measured'] / len(primary):.2%}"],
        ["明确未检测", "A1Cresult 字面值为 None", int(a1c_status_counts["not_measured"]), f"{a1c_status_counts['not_measured'] / len(primary):.2%}"],
        ["真正缺失/未知", "空值、问号、Unknown 或未识别编码", int(a1c_status_counts["missing_or_unknown"]), f"{a1c_status_counts['missing_or_unknown'] / len(primary):.2%}"],
    ], "quality")
    diagnosis_table = _write_csv(CHART_DIR / "primary_diagnosis_summary.csv", [
        ["主要诊断", "样本数", "早期再入院 n", "总体率", "已检测率", "未检测率"],
        *[[row["group"], row["n"], row["events"], f"{row['rate']:.2%}", f"{row['measured_rate']:.2%}", f"{row['not_measured_rate']:.2%}"] for row in diagnosis_summary],
    ], "diagnosis_stratified")
    variable_coding_table = _write_csv(CHART_DIR / "variable_coding.csv", [
        ["变量", "角色", "编码/参考组", "进入模型的处理", "缺失规则"],
        ["早期再入院", "主要结局", "<30=1；NO 或 >30=0", "二元 Logistic", "未知结局排除"],
        ["HbA1c 状态", "主要暴露", "已检测=1；明确未检测=0", "主效应 + 与主要诊断交互", "真正缺失/未知排除"],
        ["主要诊断", "效应修饰变量", "9 类；循环系统为参考", "分类主效应 + 交互", "缺失/未知诊断排除"],
        ["年龄/住院天数", "协变量", "年龄组中点/原始天数", "每 1 SD", "数值无法解析排除"],
        ["实验室检查数/用药数", "协变量", "原始计数", "每 1 SD", "数值无法解析排除"],
        ["诊断数/既往住院次数", "协变量", "原始计数", "每 1 SD", "数值无法解析排除"],
        ["性别", "协变量", "男性 vs 女性", "二元指示变量", "Unknown/Invalid 排除"],
        ["糖尿病药物", "协变量", "Yes vs No", "二元指示变量", "其他编码按 No 处理"],
    ], "model")
    sensitivity_rows = []
    for label, fit_result in (
        ("主分析：患者首个记录，排除死亡/临终关怀", model_fit),
        ("敏感性：保留重复记录，按患者聚类", sensitivity_cluster_fit),
        ("敏感性：纳入死亡/临终关怀并视为非早期再入院", sensitivity_death_fit),
    ):
        exposure_row = next(row for row in fit_result["rows"] if row["term"] == "a1c_measured")
        sensitivity_rows.append([
            label,
            fit_result["n_model"],
            fit_result["clusters"],
            f"{exposure_row['odds_ratio']:.3f}",
            f"[{exposure_row['ci_low']:.3f}, {exposure_row['ci_high']:.3f}]",
            exposure_row["p_value_display"],
        ])
    sensitivity_table = _write_csv(CHART_DIR / "sensitivity_analysis.csv", [
        ["分析口径", "模型 n", "患者聚类数", "HbA1c OR", "95% CI", "P 值"],
        *sensitivity_rows,
    ], "model")
    primary_table = _write_csv(CHART_DIR / "primary_effect_summary.csv", [
        ["分组", "样本数", "早期再入院事件数", "再入院率", "95% CI"],
        ["HbA1c 已检测", measured_risk["n"], measured_risk["events"], f"{measured_risk['rate']:.4%}", f"[{measured_risk['ci_low']:.4%}, {measured_risk['ci_high']:.4%}]"],
        ["HbA1c 未检测", unmeasured_risk["n"], unmeasured_risk["events"], f"{unmeasured_risk['rate']:.4%}", f"[{unmeasured_risk['ci_low']:.4%}, {unmeasured_risk['ci_high']:.4%}]"],
        ["风险差（已检测-未检测）", "", "", f"{risk_difference:.4%}", f"[{risk_difference_ci[0]:.4%}, {risk_difference_ci[1]:.4%}]"],
    ], "primary")
    model_table.update({
        "table_caption": "HbA1c × 主要诊断交互模型结果（循环系统为参考组）",
    })
    full_model_table.update({
        "table_caption": "完整调整变量模型结果（全文结果索引）",
    })
    status_table.update({
        "table_caption": "HbA1c 状态定义与主队列分布",
    })
    diagnosis_table.update({
        "table_caption": "主要诊断分层的结局与 HbA1c 分组率",
    })
    variable_coding_table.update({
        "table_caption": "分析变量编码与缺失处理合同",
    })
    sensitivity_table.update({
        "table_caption": "患者去重、死亡/临终关怀与聚类标准误敏感性分析",
    })
    primary_table.update({
        "table_caption": "HbA1c 检测状态与主要结局汇总",
    })
    artifacts = [
        flow_artifact, outcome_artifact, missing_artifact, paper_compare_artifact, matrix_artifact,
        primary_artifact, category_artifact, age_artifact, stay_artifact, diagnosis_artifact,
        forest_artifact, evidence_artifact, pipeline_artifact, relationship_artifact,
        model_table, status_table, diagnosis_table, variable_coding_table,
        sensitivity_table, primary_table,
    ]

    meta = {
        "execution_run_id": RUN_ID,
        "total_records": total,
        "unique_patients": unique_patients,
        "repeated_patient_records": repeated_patient_records,
        "index_records": index_records,
        "death_hospice_index_records": death_hospice_index,
        "primary_analysis_records": int(len(primary)),
        "primary_model_records": model_fit["n_model"],
        "primary_model_clusters": model_fit["clusters"],
        "columns": 50,
        "uci_features": 47,
        "a1c_measured_records": measured,
        "a1c_measurement_rate": measured / len(exposure_frame),
        "overall_early_readmission_rate": overall_risk["rate"],
        "early_rate_measured": measured_risk["rate"],
        "early_rate_unmeasured": unmeasured_risk["rate"],
        "risk_difference": risk_difference,
        "risk_difference_ci": list(risk_difference_ci),
        "paper_final_sample": 69984,
        "paper_reported_a1c_measurement_rate": 0.184,
        "top_missingness": {str(key): float(value) for key, value in top_missing.items()},
        "outcome_counts": {str(key): int(value) for key, value in outcome_counts.items()},
        "logistic_reanalysis": model_rows,
        "model_contract": model_contract,
        "interaction_joint_p_value": model_fit["interaction_joint_p_value"],
        "interaction_joint_p_value_display": model_fit["interaction_joint_p_value_display"],
        "sensitivity_analysis": {
            "clustered_repeated_records": sensitivity_cluster_fit,
            "including_death_hospice": sensitivity_death_fit,
        },
        "a1c_status_counts": {str(key): int(value) for key, value in a1c_status_counts.items()},
        "primary_diagnosis_summary": diagnosis_summary,
        "software_versions": software_versions,
        "artifact_count": len(artifacts),
        "chart_plans": {
            artifact["name"]: {
                "file_name": Path(str(artifact["file_path"])).name,
                "chart_kind": artifact["chart_kind"],
                "encoding": artifact["chart_encoding"],
                "rationale": artifact["chart_rationale"],
            }
            for artifact in artifacts
            if artifact.get("artifact_type") == "CHART_PNG" and artifact.get("chart_kind")
        },
        "figure_plans": {
            artifact["name"]: artifact["figure_plan"]
            for artifact in artifacts
            if artifact.get("figure_plan")
        },
        "figure_portfolio_plan": portfolio.to_metadata(),
    }
    (OUTPUT_DIR / "analysis_summary.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (SOURCE_DIR / "source_manifest.json").write_text(json.dumps({
        "paper": {
            "title": "Impact of HbA1c Measurement on Hospital Readmission Rates: Analysis of 70,000 Clinical Database Patient Records",
            "authors": "Strack et al.",
            "year": 2014,
            "doi": "10.1155/2014/781670",
            "open_access_source": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3996476/",
            "full_text_xml": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC3996476/fullTextXML",
            "local_file": "sources/strack_2014_hba1c_readmission.pdf",
        },
        "dataset": {
            "title": "Diabetes 130-US hospitals for years 1999-2008",
            "doi": "10.24432/C5230J",
            "original_source": "https://archive.ics.uci.edu/dataset/296/diabetes+130-us-hospitals+for+years+1999-2008",
            "download_mirror": "https://github.com/jonneff/Diabetes2/blob/master/diabetic_data.csv",
            "license": "CC BY 4.0",
            "local_file": "data/diabetic_data.csv",
        },
        "analysis": {
            "execution_run_id": RUN_ID,
            "scope": "教学性论文复核报告：患者去重、死亡/临终关怀排除、诊断分层、HbA1c × 主要诊断交互和聚类稳健标准误；不等同原论文完整模型复现",
            "position": "教学性复核报告，不是独立研究论文",
            "model_contract": model_contract,
        },
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return artifacts, meta


def _sections(meta: dict) -> list[dict]:
    measured_rate = f"{meta['a1c_measurement_rate']:.1%}"
    early_measured = f"{meta['early_rate_measured']:.1%}"
    early_unmeasured = f"{meta['early_rate_unmeasured']:.1%}"
    rd = f"{meta['risk_difference']:.1%}"
    primary_n = f"{meta['primary_analysis_records']:,}"
    model_n = f"{meta['primary_model_records']:,}"
    interaction_p = meta.get("interaction_joint_p_value_display", "N/A")
    software_text = "; ".join(f"{key} {value}" for key, value in meta["software_versions"].items())
    return [
        {
            "id": "question", "manuscript_role": "introduction", "title": "研究问题与论文假设", "presentation_role": "question",
            "content": "论文研究 HbA1c 检测是否反映住院期间更充分的糖尿病管理，以及检测行为是否与 30 天内再入院相关。本文正式定位为教学性论文复核报告，而非独立研究论文；原论文结论与本地分析结果分开陈述。",
            "paragraphs": [
                "原论文关注一个具有明确临床语境的观察性问题：住院期间是否完成 HbA1c 检测，能否作为医疗管理过程的可观测标志，并与出院后 30 天内再入院风险呈现稳定关联。",
                "本文是教学性论文复核报告，不是独立研究论文，也不宣称已经完整复现原论文的核心交互或最终模型。HbA1c 检测不被直接解释为干预效果，全文沿着“研究问题—变量定义—样本口径—复核证据—解释边界”的顺序展开。",
            ],
            "presentation_content": "本文是教学性论文复核报告，不是独立研究论文；原论文与本地分析分开陈述。",
            "source_type": "REQUIREMENT", "source_ids": ["paper:PMC3996476"],
        },
        {
            "id": "objective", "manuscript_role": "introduction", "title": "研究目标与解读路径",
            "paragraphs": [
                "本报告的第一项任务是还原原论文的研究对象、核心变量和主要结论；第二项任务是使用可公开取得的 UCI 数据，核对这些变量之间是否存在方向一致的描述性证据。",
                "两项任务分别对应论文解读与教学性复核。前者回答“原论文做了什么”，后者回答“公开数据能支持到什么程度”，二者不共享一个未经验证的精确复现结论。",
            ],
            "content": "本报告先还原原论文的研究对象、变量定义和主要结论，再使用公开 UCI 数据开展教学性描述性复核；论文解读与本地复核分别回答不同问题，不合并为一个精确复现结论。",
            "source_type": "REQUIREMENT", "source_ids": ["paper:PMC3996476"],
        },
        {
            "id": "source", "manuscript_role": "methods", "title": "论文、数据与研究对象", "presentation_role": "source",
            "content": f"论文基于 Cerner Health Facts 临床数据库；本地使用 UCI 公开 CSV。原始 CSV 有 {meta['total_records']:,} 条记录、{meta['unique_patients']:,} 名患者，其中 {meta['repeated_patient_records']:,} 条为重复患者记录。按预先声明的患者首个记录规则并排除死亡/临终关怀出院后，主分析队列为 {primary_n} 条；这与原论文报告的 {meta['paper_final_sample']:,} 条接近但不等同。",
            "paragraphs": [
                "原论文使用 Cerner Health Facts 临床数据库，覆盖 1999—2008 年、130 家医院及其整合医疗网络；研究对象是住院患者记录，分析重点是 HbA1c 检测行为与再入院结局之间的关系。",
                f"本地复核使用 UCI Machine Learning Repository 发布的 Diabetes 130-US Hospitals 数据。原始 CSV 包含 {meta['total_records']:,} 条住院记录和 {meta['unique_patients']:,} 名患者；按 encounter_id 升序为每位患者保留首个记录，排除 {meta['death_hospice_index_records']:,} 条死亡/临终关怀首记录后形成 {primary_n} 条主分析队列。",
            ],
            "source_type": "EVIDENCE", "source_ids": ["paper:PMC3996476", "dataset:UCI-296"],
        },
        {
            "id": "evidence_chain", "manuscript_role": "introduction", "title": "研究证据链与解释边界", "presentation_role": "evidence_chain",
            "content": "开放论文提供研究问题和原始结论，UCI 数据集提供可核验的公开记录，本地 CSV 复核只验证研究逻辑与方向性证据，最终解释必须回到样本口径、缺失结构和观察性研究边界。",
            "paragraphs": [
                "证据链由三类材料组成：开放论文提供研究问题、变量定义和原始结论；UCI 数据集提供可取得的公开记录；本地执行产物保存复核过程、数值结果和图表来源。",
                "这三类材料承担的证明责任不同。公开数据可以帮助核对研究逻辑和方向性证据，但不能在缺少原始筛选队列和完整模型设定时，替代原论文的精确复现。",
            ],
            "figure_lead": "证据链图将来源、数据、复核和边界放在同一条证据链中，先说明材料之间如何衔接，再进入数值结果。",
            "figure_takeaway": "由图可见，本地复核的证据位置是“核对研究逻辑”，而不是把公开 CSV 重新命名为论文最终样本。",
            "presentation_content": "开放论文 → UCI 数据集 → 本地 CSV 复核 → 解释边界；不把不同样本口径合并成精确复现。",
            "source_type": "EVIDENCE", "source_ids": ["paper:PMC3996476", "dataset:UCI-296"], "artifact_group": "evidence_logic",
        },
        {
            "id": "sample", "manuscript_role": "methods", "title": "样本规模与口径对照", "presentation_role": "sample",
            "content": f"原始记录 {meta['total_records']:,} 条，唯一患者 {meta['unique_patients']:,} 名，重复患者记录 {meta['repeated_patient_records']:,} 条；患者首记录 {meta['index_records']:,} 条，排除死亡/临终关怀首记录 {meta['death_hospice_index_records']:,} 条后，主分析队列 {primary_n} 条。论文最终样本为 {meta['paper_final_sample']:,} 条，二者接近但不宣称相同。",
            "paragraphs": [
                f"公开数据共包含 {meta['total_records']:,} 条住院记录和 {meta['columns']} 个字段，其中 {meta['unique_patients']:,} 名患者对应 {meta['repeated_patient_records']:,} 条重复患者记录。",
                f"本地主分析按 encounter_id 升序保留每位患者首个记录，并排除 {meta['death_hospice_index_records']:,} 条死亡/临终关怀首记录，得到 {primary_n} 条已知结局记录；该队列是本报告自行执行的分析口径，不被写成原论文队列。",
            ],
            "source_type": "DATASET", "source_ids": ["dataset:UCI-296"],
        },
        {
            "id": "data_definition", "manuscript_role": "methods", "title": "研究对象与变量口径",
            "content": "主分析单位是每位患者按 encounter_id 升序保留的首个住院记录；主要解释变量为 HbA1c 状态，主要结局为出院后 30 天内再入院。主分析排除死亡/临终关怀首记录，并将真正缺失/未知与字面 None 的明确未检测分开。",
            "paragraphs": [
                "患者首记录规则避免同一患者的重复住院记录把样本量和精度人为放大；死亡/临终关怀出院记录从主分析排除，以保持与原论文的研究逻辑一致。",
                "HbA1c 的 >8、>7 和 Norm 记为已检测，字面 None 记为明确未检测；空值、问号、Unknown 或未识别编码另列为真正缺失/未知，不进入主暴露比较和模型。",
                f"主要诊断按原论文 Table 2 的 ICD-9 规则分为 9 类，循环系统为参考组；模型样本为 {model_n} 条、{meta['primary_model_clusters']:,} 名患者。",
            ],
            "source_type": "DATASET", "source_ids": ["dataset:UCI-296", "paper:PMC3996476"],
        },
        {
            "id": "sample_structure", "manuscript_role": "methods", "title": "样本与结局分布", "presentation_role": "sample_structure",
            "content": f"样本流程图展示原始住院记录、唯一患者、患者首记录、排除死亡/临终关怀后的主分析队列；结局分布用于说明 <30、>30 和 NO 三类标签的基线构成。",
            "presentation_content": f"原始记录 {meta['total_records']:,} 条；唯一患者 {meta['unique_patients']:,} 名；主分析队列 {primary_n} 条；论文最终样本 {meta['paper_final_sample']:,} 条。",
            "source_type": "EXECUTION", "source_ids": [RUN_ID], "artifact_group": "sample_structure",
        },
        {
            "id": "quality", "manuscript_role": "methods", "title": "数据质量与缺失结构", "presentation_role": "quality",
            "content": f"主队列 HbA1c 已检测率为 {measured_rate}；明确未检测与真正缺失/未知分别计数，不能将字面 None 当作普通缺失。字段缺失结构仍然具有系统性，因此本地复核不做无依据的完整案例推断。",
            "paragraphs": [
                f"在 {primary_n} 条主分析记录中，HbA1c 已检测 {meta['a1c_status_counts']['measured']:,} 条，明确未检测 {meta['a1c_status_counts']['not_measured']:,} 条，真正缺失/未知 {meta['a1c_status_counts']['missing_or_unknown']:,} 条。字面 None 是数据集中的明确未检测状态，不应被错误计入缺失。",
                "缺失结构并非均匀分布：重量、支付方、专科和部分实验字段的缺失比例较高。因此，本地复核不进行无依据的完整案例推断，结果解释需要同时考虑数据可得性和医疗行为差异。[4]",
            ],
            "figure_lead": "缺失结构图只展示真正缺失/未知字段，HbA1c 状态表另行区分已检测、明确未检测和真正缺失/未知。",
            "figure_takeaway": "缺失集中在少数字段，说明数据质量问题具有结构性；因此结果应被理解为公开记录上的条件性复核，而不是完整临床队列的无偏估计。",
            "presentation_content": "缺失率最高的字段集中于 weight、max_glu_serum 和 A1Cresult；本地分析保留缺失结构，不假设完整案例。",
            "source_type": "EXECUTION", "source_ids": [RUN_ID, "ref:missing"], "artifact_group": "quality",
        },
        {
            "id": "method", "manuscript_role": "methods", "title": "变量定义与分析路径", "presentation_role": "method",
            "content": "主线：患者去重、死亡/临终关怀排除、HbA1c 状态编码、主要诊断交互、聚类稳健模型与敏感性分析。",
            "presentation_content": "去重与排除 → HbA1c 状态 → 诊断交互 → 敏感性分析。",
            "source_type": "ANALYSIS", "source_ids": ["paper:PMC3996476", RUN_ID],
        },
        {
            "id": "pipeline", "manuscript_role": "methods", "title": "数据处理管线", "presentation_role": "data_pipeline",
            "content": "数据先保留原始缺失结构，再按患者首记录和死亡/临终关怀排除规则形成主队列，随后定义 HbA1c 状态、30 天再入院结局、主要诊断分层和交互模型。管线图对应真实执行产物，不把文件列表当作论文逻辑。",
            "paragraphs": [
                "分析先形成患者级主队列，再定义 HbA1c 状态和 30 天再入院结局；随后计算总体与诊断分层风险、Wilson 区间，并拟合含 HbA1c × 主要诊断交互的模型。",
                "这一顺序把数据处理和论证责任分开：前半段回答“如何从原始记录得到比较量”，后半段回答“这些比较量能支持什么解释”，敏感性分析则检验关键口径是否改变方向。",
            ],
            "figure_lead": "数据处理管线展示从原始记录、患者去重和死亡/临终关怀排除，到状态编码、交互模型和结果索引的实际路径。",
            "figure_takeaway": "管线的关键不是步骤数量，而是每个结果都能回到原始 CSV、执行批次、变量编码和结果表，避免把图表生成误当成分析本身。",
            "presentation_content": "原始 CSV → 患者级队列 → 死亡/临终关怀排除 → HbA1c/诊断编码 → 交互模型与敏感性分析。",
            "source_type": "ANALYSIS", "source_ids": ["dataset:UCI-296", RUN_ID], "artifact_group": "method_logic",
        },
        {
            "id": "model", "manuscript_role": "methods", "title": "教学性多变量模型与交互分析", "presentation_role": "model",
            "content": f"主模型在患者首个住院记录且排除死亡/临终关怀的主队列上拟合，以 HbA1c 已检测为暴露、循环系统主要诊断为参考组，并加入 HbA1c × 主要诊断交互。模型样本为 {model_n} 条、{meta['primary_model_clusters']:,} 名患者；标准误按 patient_nbr 聚类稳健估计。",
            "paragraphs": [
                "模型合同预先规定：<30 记为早期再入院事件，NO 或 >30 记为非事件；HbA1c 的 >8、>7 和 Norm 记为已检测，字面 None 记为明确未检测，真正缺失/未知排除。",
                "主要诊断依据原论文 Table 2 的 ICD-9 规则分为循环系统、呼吸系统、消化系统、糖尿病、损伤、肌肉骨骼、泌尿生殖系统、肿瘤和其他 9 类，循环系统为参考组；连续协变量按每 1 个标准差进入模型。",
                f"HbA1c × 主要诊断交互的联合 Wald 检验 P {interaction_p}。主模型使用按 patient_nbr 聚类的 sandwich 标准误；保留重复记录和纳入死亡/临终关怀的口径作为敏感性分析。软件版本为 {software_text}。",
            ],
            "figure_lead": "交互森林图同时呈现 HbA1c 主效应和主要诊断交互项的 OR 与 95% CI；联合 Wald P 值用于判断是否存在整体交互信号。",
            "figure_takeaway": "模型结果只能说明在本地教学性复核合同下的条件性关联，不能消除残余混杂，也不能被称为原论文完整模型复现。",
            "presentation_content": f"患者首记录主模型：HbA1c × 主要诊断交互；聚类稳健 SE；模型 n={model_n}，联合交互 P {interaction_p}。",
            "source_type": "EXECUTION", "source_ids": [RUN_ID, "ref:STROBE", "ref:cluster"], "artifact_group": "model",
        },
        {
            "id": "primary", "manuscript_role": "results", "title": "主要结果：HbA1c 检测与再入院", "presentation_role": "primary",
            "content": f"在 {primary_n} 条主分析记录中，HbA1c 已检测组 30 天内再入院率为 {early_measured}，明确未检测组为 {early_unmeasured}，风险差为 {rd}。图表同时呈现 95% 置信区间；这支持组间存在描述性差异，但不能单独推出检测行为造成风险下降。",
            "paragraphs": [
                f"在患者级主分析队列中，HbA1c 已检测组 30 天内再入院率为 {early_measured}，明确未检测组为 {early_unmeasured}，两组风险差为 {rd}。真正缺失/未知记录不进入这项主暴露比较。",
                "该差异是描述性比较，图表同时呈现 95% 置信区间。它可以支持“两个观察组的结局分布不同”这一判断，但不能单独推出检测行为造成风险下降。",
            ],
            "figure_lead": "主要结果点区间图直接比较两组再入院率及其区间，读者应先确认患者级队列、估计值和分组定义，再进入因果解释。",
            "figure_takeaway": "已检测组的观察风险低于未检测组，但这个差异仍可能受到患者复杂度、医疗关注度和字段缺失等因素影响。",
            "presentation_content": f"已检测组 {early_measured}，明确未检测组 {early_unmeasured}；风险差 {rd}，图中附 95% 置信区间。",
            "source_type": "EXECUTION", "source_ids": [RUN_ID], "artifact_group": "primary",
        },
        {
            "id": "stratified", "manuscript_role": "results", "title": "分层结果：年龄与住院时长", "presentation_role": "stratified",
            "content": "年龄和住院天数分层显示，再入院率不是单一 HbA1c 指标可以完整解释的结果。分层图用于暴露结构差异和潜在混杂，不替代论文的多变量模型，也不作临床风险分层工具。",
            "paragraphs": [
                "年龄和住院天数分层后，再入院率呈现出不同的结构，说明结局并非由单一 HbA1c 指标即可完整解释。",
                "分层图的用途是暴露潜在混杂和患者复杂度差异，而不是替代论文的多变量模型，也不是面向个体的临床风险分层工具。",
            ],
            "figure_lead": "年龄与住院时长分层图从两个方向拆开总体差异，观察分层后结果是否保持同一形态。",
            "figure_takeaway": "分层结果提醒我们：总体关联可能混合了患者复杂度和住院过程差异，必须避免把单一指标解释成独立因果因素。",
            "presentation_content": "年龄与住院时长存在分层差异，提示 HbA1c 关联不能脱离患者复杂度解释。",
            "source_type": "EXECUTION", "source_ids": [RUN_ID], "artifact_group": "stratified",
        },
        {
            "id": "diagnosis_stratified", "manuscript_role": "results", "title": "主要诊断分层与 HbA1c 交互", "presentation_role": "diagnosis_stratified",
            "content": f"主要诊断分层显示，HbA1c 已检测与明确未检测的再入院率差异并非在所有诊断组中相同；交互模型的联合 Wald 检验 P {interaction_p}。分层率用于展示异质性，交互模型用于检验整体差异。",
            "paragraphs": [
                "主要诊断分层沿用原论文 Table 2 的 ICD-9 分组规则，并将循环系统设为参考组。每组同时展示 HbA1c 已检测与明确未检测的样本数、事件数、比例和 Wilson 95% 置信区间。",
                f"HbA1c × 主要诊断交互的联合 Wald 检验 P {interaction_p}；该结果只能说明本地教学性复核合同下的统计异质性信号，不能替代原论文的完整模型或临床机制解释。",
            ],
            "figure_lead": "主要诊断分层图并列呈现两种 HbA1c 状态的再入院率与 Wilson 95% CI，交互森林图另行呈现模型估计。",
            "figure_takeaway": "分层差异和交互项需要同时阅读样本量、区间宽度与模型合同，不能把某一诊断组的较高或较低比例解释为因果效应。",
            "presentation_content": f"9 类主要诊断分层；已检测/明确未检测率及 Wilson CI；交互联合 P {interaction_p}。",
            "source_type": "EXECUTION", "source_ids": [RUN_ID], "artifact_group": "diagnosis_stratified",
        },
        {
            "id": "relationship", "manuscript_role": "discussion", "title": "变量关系与观察性边界", "presentation_role": "relationship_graph",
            "content": "HbA1c 检测状态与 30 天再入院之间呈现观察性关联；年龄、住院时长和医疗复杂度用于分层或协变量复核。图形不表达确定性因果路径，避免把检测行为误读为干预。",
            "paragraphs": [
                "从变量关系看，HbA1c 检测状态与 30 天再入院之间存在需要进一步复核的观察性关联；年龄、住院时长和医疗复杂度是解释这一关联时必须保留的背景变量。",
                "关系图只表达变量在分析中的角色和连接方式，不表达确定性因果路径。尤其不能把“完成检测”直接理解为已经实施的一项随机化干预。",
            ],
            "figure_lead": "变量关系图将暴露、结局和协变量的分析角色分层展示，避免用单一箭头替代观察性研究中的因果讨论。",
            "figure_takeaway": "该图支持的是变量角色和观察性关联的可读化，不支持“检测导致风险下降”的因果结论。",
            "presentation_content": "HbA1c 检测 ↔ 30 天再入院：观察性关联；年龄与医疗复杂度作为分层/协变量。",
            "source_type": "ANALYSIS", "source_ids": ["paper:PMC3996476", RUN_ID], "artifact_group": "relationship_logic",
        },
        {
            "id": "comparison", "manuscript_role": "results", "title": "论文结论与本地复核对照", "presentation_role": "comparison",
            "content": f"论文报告 HbA1c 检测率为 18.4%；按患者首记录、排除死亡/临终关怀并分开明确未检测与真正缺失/未知后，本地主分析检测率为 {meta['a1c_measurement_rate']:.1%}。两者仍来自不同数据来源和分析合同，因此本地结果用于复核研究逻辑，不宣称精确复现论文。",
            "paragraphs": [
                f"论文报告 HbA1c 检测率为 18.4%；本地主分析队列的检测率为 {meta['a1c_measurement_rate']:.1%}。这两个数字可以用于发现口径差异，但不能直接当作同一队列上的复现误差。",
                "本地分析已经处理患者重复记录、死亡/临终关怀首记录、HbA1c 状态语义和主要诊断交互，但仍缺少原论文完整数据库筛选过程与全部模型实现。因此，本地结果的任务是复核研究逻辑和方向性证据，而不是宣称精确复现原论文。",
            ],
            "figure_lead": "论文与本地检测率对照图先把两个报告值放在同一坐标系中，再用口径说明限制数值比较的含义。",
            "figure_takeaway": "两项检测率可以并列展示，但不能被解释为完全同口径的复现误差；先确认分析队列，再讨论数值是否可比。",
            "presentation_content": f"论文检测率 18.4%；本地主分析队列为 {meta['a1c_measurement_rate']:.1%}。两者口径不同，不能直接当作复现误差。",
            "source_type": "EXECUTION", "source_ids": [RUN_ID], "artifact_group": "comparison",
        },
        {
            "id": "comparison_matrix", "manuscript_role": "results", "title": "论文与本地复核的多维口径矩阵", "presentation_role": "comparison_matrix",
            "content": "比较矩阵将研究问题、分析队列、HbA1c 检测率、方法层级和解释边界并列展开，区分哪些内容可以对照，哪些内容不能直接交换。它补充 Dumbbell 的数值差异，不把多维口径压缩成一个百分比。",
            "paragraphs": [
                "单一检测率只能呈现数值差异，不能说明两个分析是否回答了同一个研究问题。比较矩阵因此同时列出研究问题、分析队列、检测率、方法层级和解释边界。",
                "矩阵的阅读顺序是先看可比性，再看数值，最后看解释边界。它补充 Dumbbell 图的配对比较，不把多维口径压缩成一个百分比。",
            ],
            "figure_lead": "论文与本地复核比较矩阵将“可对照”和“不可直接交换”放在同一张表中，作为论文结论与本地复核之间的解释闸门。",
            "figure_takeaway": "矩阵显示：研究问题和方向性结论可以对照，但分析队列、方法层级和解释边界不能被视为完全相同。",
            "presentation_content": "矩阵同时呈现可比部分与不可直接交换的分析口径。",
            "source_type": "EXECUTION", "source_ids": [RUN_ID], "artifact_group": "comparison_matrix",
        },
        {
            "id": "limitation", "manuscript_role": "discussion", "title": "局限性与解释边界", "presentation_role": "limitation",
            "content": "本地分析存在观察性研究的混杂风险、字段缺失、医院与医生行为差异、公开 CSV 与论文最终队列不完全一致等限制。HbA1c 检测可能是整体医疗关注度的代理变量；结果不构成因果结论、治疗建议或临床决策依据。",
            "paragraphs": [
                "本地分析至少存在四类限制：观察性研究中的混杂风险，字段缺失带来的信息不完整，医院与医生行为差异，以及公开 CSV 与论文最终分析队列不完全一致。",
                "HbA1c 检测可能是整体医疗关注度、病情复杂度或住院流程差异的代理变量。因此，本文结果不构成因果结论、治疗建议或临床决策依据。",
            ],
            "source_type": "SUMMARY", "source_ids": ["paper:PMC3996476", "dataset:UCI-296"],
        },
        {
            "id": "conclusion", "manuscript_role": "conclusion", "title": "结论与可复核证据链", "presentation_role": "conclusion",
            "content": "原论文的研究问题、公开数据的方向性复核与观察性边界共同构成结论基础；本地结果支持可复核的关联判断，但不支持精确复现或临床因果推断。",
            "paragraphs": [
                "这篇论文的价值不只在于报告一个检测率差异，而在于把临床行为指标、再入院结局和观察性研究局限放在同一分析框架中。",
                "综合原文与本地结果，公开数据支持 HbA1c 检测状态与再入院之间存在需要进一步解释的观察性关联；样本口径、缺失结构和医疗行为差异决定了这一结论的适用边界。",
            ],
            "source_type": "SUMMARY", "source_ids": ["paper:PMC3996476", "dataset:UCI-296"],
        },
    ]


def _formal_paper_config(meta: dict) -> dict:
    """返回统计完整性修订后的正式论文渲染合同。"""
    primary_n = meta["primary_analysis_records"]
    model_n = meta["primary_model_records"]
    software_text = "; ".join(f"{key} {value}" for key, value in meta["software_versions"].items())
    interaction_p = meta.get("interaction_joint_p_value_display", "N/A")
    return {
        "document_profile": "formal_academic",
        "formal_title": "HbA1c 检测与住院再入院：公开论文教学性复核报告",
        "formal_subtitle": "基于 Diabetes 130-US Hospitals 数据集与 Strack 等研究（非独立研究论文）",
        "formal_metadata": {
            "作者": "实验报告助手项目组",
            "单位": "本地单用户数据分析实验工作台",
            "研究类型": "教学性论文复核报告（非独立研究论文；不宣称完整复现）",
            "研究对象": "Diabetes 130-US Hospitals 公开住院记录",
            "原始数据": f"{meta['total_records']:,} 条记录；{meta['unique_patients']:,} 名患者；50 个字段",
            "主分析队列": f"患者首记录 {meta['index_records']:,} 条，排除死亡/临终关怀后 {primary_n:,} 条",
            "模型合同": f"HbA1c × 主要诊断交互；patient_nbr 聚类稳健 SE；模型 n={model_n:,}",
            "软件与版本": software_text,
            "执行批次": meta["execution_run_id"],
            "分析边界": "不宣称完整复现原论文模型，不提供临床诊疗建议",
        },
        "abstract": (
            f"本报告围绕 HbA1c 检测与住院后 30 天内再入院之间的关系，对 Strack 等人的开放论文进行结构化解读，并使用公开 UCI 数据集开展教学性复核。"
            f"原始 CSV 共 {meta['total_records']:,} 条记录、{meta['unique_patients']:,} 名患者；按 encounter_id 升序为每位患者保留首个记录，排除 {meta['death_hospice_index_records']:,} 条死亡/临终关怀首记录后形成 {primary_n:,} 条主分析队列。"
            f"HbA1c 已检测 {meta['a1c_status_counts']['measured']:,} 条、明确未检测 {meta['a1c_status_counts']['not_measured']:,} 条，真正缺失/未知单列；两组 30 天再入院率分别为 {meta['early_rate_measured']:.1%} 与 {meta['early_rate_unmeasured']:.1%}。"
            f"模型加入主要诊断分层及 HbA1c × 主要诊断交互，并按 patient_nbr 使用聚类稳健标准误；联合交互检验 P {interaction_p}。本文定位为教学性论文复核报告，不是独立研究论文，也不宣称完整复现原论文。"
            "[1–5]"
        ),
        "abstract_sections": {
            "目的": "解读公开论文的研究问题、变量定义和主要证据，评估公开数据能否在明确分析合同下支持方向性复核；本文定位为教学性论文复核报告而非独立研究论文。",
            "方法": (
                f"基于 Diabetes 130-US Hospitals 公开 CSV，按 encounter_id 为每位患者保留首个记录，排除死亡/临终关怀首记录，形成 {primary_n:,} 条主分析队列。"
                "将 HbA1c 已检测、明确未检测和真正缺失/未知分开，按原论文 Table 2 的 ICD-9 规则建立 9 类主要诊断，并拟合 HbA1c × 主要诊断交互模型；标准误按 patient_nbr 聚类稳健估计。"
            ),
            "结果": (
                f"主队列中 HbA1c 已检测 {meta['a1c_status_counts']['measured']:,} 条，明确未检测 {meta['a1c_status_counts']['not_measured']:,} 条，真正缺失/未知 {meta['a1c_status_counts']['missing_or_unknown']:,} 条。"
                f"已检测组与明确未检测组的 30 天再入院率分别为 {meta['early_rate_measured']:.1%} 与 {meta['early_rate_unmeasured']:.1%}；交互联合 Wald 检验 P {interaction_p}。"
            ),
            "结论": "本地分析在患者级队列、死亡/临终关怀排除、缺失语义、主要诊断交互和聚类稳健标准误均明确后，可作为教学性方向核对；它不能替代原论文的完整复现，也不支持因果或临床判断。",
        },
        "abstract_en": (
            "Purpose: To interpret the original study and assess what can be checked using the public dataset in a transparent teaching-oriented review. "
            f"Methods: We retained the first encounter per patient by encounter_id, excluded {meta['death_hospice_index_records']:,} index records with death or hospice dispositions, separated measured HbA1c, explicitly unmeasured HbA1c, and true missing/unknown values, and fitted a model with primary-diagnosis strata and an HbA1c-by-diagnosis interaction using patient-level cluster-robust standard errors. "
            f"Results: The primary cohort contained {primary_n:,} records; readmission rates were {meta['early_rate_measured']:.1%} and {meta['early_rate_unmeasured']:.1%} in the measured and explicitly unmeasured groups, respectively. The joint interaction test had P {interaction_p}. "
            "Conclusion: This is a teaching-oriented review report, not an independent research paper or a claim of complete replication of the original model; results are associational and not clinical advice."
        ),
        "abstract_sections_en": {
            "Purpose": "To interpret the original paper and assess the scope of a transparent public-data review.",
            "Methods": (
                f"We retained one index encounter per patient, excluded death/hospice index records, and analyzed {primary_n:,} records. HbA1c measurement, explicit non-measurement, and true missing/unknown values were separated. The model included primary-diagnosis strata, an HbA1c-by-diagnosis interaction, prespecified covariates, and patient-level cluster-robust standard errors."
            ),
            "Results": (
                f"Readmission rates were {meta['early_rate_measured']:.1%} and {meta['early_rate_unmeasured']:.1%} in the measured and explicitly unmeasured groups, respectively; the joint interaction test had P {interaction_p}."
            ),
            "Conclusion": "The findings support a bounded teaching-oriented review of associational patterns, not an independent study, clinical inference, or complete replication of the original paper.",
        },
        "reference_catalog": {
            "paper:PMC3996476": "Strack B, et al. Impact of HbA1c Measurement on Hospital Readmission Rates: Analysis of 70,000 Clinical Database Patient Records. BioMed Research International. 2014;2014:781670. doi:10.1155/2014/781670.",
            "dataset:UCI-296": "UCI Machine Learning Repository. Diabetes 130-US Hospitals for Years 1999–2008 [dataset]. doi:10.24432/C5230J.",
            "ref:STROBE": "von Elm E, Altman DG, Egger M, et al. The Strengthening the Reporting of Observational Studies in Epidemiology (STROBE) Statement: Guidelines for Reporting Observational Studies. PLoS Med. 2007;4(10):e296. doi:10.1371/journal.pmed.0040296.",
            "ref:missing": "Ibrahim JG, Chu H, Chen MH. Missing data in clinical studies: issues and methods. J Clin Oncol. 2012;30(26):3297-3303. doi:10.1200/JCO.2011.38.7589.",
            "ref:cluster": "Cameron AC, Miller DL. A Practitioner’s Guide to Cluster-Robust Inference. J Human Resources. 2015;50(2):317-372. doi:10.3368/jhr.50.2.317.",
        },
    }


def main() -> None:
    if not DATA_PATH.exists():
        raise SystemExit(f"缺少公开数据文件：{DATA_PATH}")
    if OUTPUT_DIR.exists():
        for child in OUTPUT_DIR.iterdir():
            if child.name not in {"data", "sources"}:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    try:
                        child.unlink()
                    except PermissionError:
                        # Word 仍打开历史成品时保留该文件；0040 使用独立命名重新生成。
                        continue
    artifacts, meta = _analyze()
    sections = _sections(meta)
    topic = "论文解读：HbA1c 检测与再入院"
    formal_config = _formal_paper_config(meta)
    publication_artifacts = _publication_artifacts(artifacts)
    publication_docx = OUTPUT_DIR / f"{PUBLICATION_PREFIX}.docx"
    publication_pdf = OUTPUT_DIR / f"{PUBLICATION_PREFIX}.pdf"
    publication_pptx = OUTPUT_DIR / f"{PUBLICATION_PREFIX}.pptx"

    WordRenderer().render(
        project_name="大样本临床论文解读",
        project_topic=topic,
        outline_sections=sections,
        execution_artifacts=publication_artifacts,
        output_path=str(publication_docx),
        config=formal_config,
    )
    # PDF 只允许从本轮刚生成的最终 DOCX 导出，不存在第二套正文排版。
    DocxPdfExporter().export(publication_docx, publication_pdf)

    WordRenderer().render(
        project_name="大样本临床论文解读",
        project_topic=topic,
        outline_sections=sections,
        execution_artifacts=publication_artifacts,
        output_path=str(OUTPUT_DIR / "spec0040_argumentation.docx"),
        config=formal_config,
    )
    PptRenderer().render(
        project_name="大样本临床论文解读",
        project_topic=topic,
        outline_sections=sections,
        execution_artifacts=publication_artifacts,
        output_path=str(publication_pptx),
        config={"ppt_workflow": "academic"},
    )
    PptRenderer().render(
        project_name="大样本临床论文解读",
        project_topic=topic,
        outline_sections=sections,
        execution_artifacts=publication_artifacts,
        output_path=str(OUTPUT_DIR / "spec0035_sjtu_paper_review.pptx"),
        config={"ppt_workflow": "sjtu_academic"},
    )

    # 历史 SPEC 别名继续指向同一批真实产物，避免旧验收路径失效。
    for source_name, target_name in (
        (publication_docx.name, "spec0035_paper_review.docx"),
        (publication_docx.name, "spec0041_heterogeneous.docx"),
        (publication_docx.name, "spec0042_paper_language.docx"),
        (publication_pptx.name, "spec0035_paper_review.pptx"),
        (publication_pptx.name, "spec0040_argumentation.pptx"),
        (publication_pptx.name, "spec0041_heterogeneous.pptx"),
        (publication_pptx.name, "spec0042_paper_language.pptx"),
        ("spec0035_sjtu_paper_review.pptx", "spec0040_argumentation_sjtu.pptx"),
        ("spec0035_sjtu_paper_review.pptx", "spec0041_heterogeneous_sjtu.pptx"),
        ("spec0035_sjtu_paper_review.pptx", "spec0042_paper_language_sjtu.pptx"),
    ):
        try:
            shutil.copy2(OUTPUT_DIR / source_name, OUTPUT_DIR / target_name)
        except PermissionError:
            continue

    (OUTPUT_DIR / "publication_manifest.json").write_text(
        json.dumps(
            {
                "spec": "0043",
                "deliverables": {
                    "docx": publication_docx.name,
                    "pdf": publication_pdf.name,
                    "pptx": publication_pptx.name,
                    "sjtu_pptx": "spec0035_sjtu_paper_review.pptx",
                },
                "pdf_binding": {
                    "exporter": "DocxPdfExporter",
                    "source_docx": publication_docx.name,
                    "source_docx_sha256": _sha256(publication_docx),
                    "pdf_sha256": _sha256(publication_pdf),
                },
                "source_manifest": "sources/source_manifest.json",
                "analysis_summary": "analysis_summary.json",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
