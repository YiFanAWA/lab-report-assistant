"""论文级图表语义规划器（SPEC 0037）。

图表类型不是装饰选择，而是由数据类型、分析目的、是否有不确定性和
变量是否有自然顺序共同决定。该模块只输出可解释的规划结果；真实统计
和绘图仍由分析/执行产物生成器负责。
"""

from dataclasses import dataclass
from enum import StrEnum


class ChartKind(StrEnum):
    """交付物层可消费的图表类别。"""

    FLOW = "flow"
    HORIZONTAL_BAR = "horizontal_bar"
    STACKED_COMPOSITION = "stacked_composition"
    DUMBBELL = "dumbbell"
    POINT_CI = "point_ci"
    ORDERED_LINE = "ordered_line"
    FOREST = "forest"


@dataclass(frozen=True)
class ChartPlan:
    """一个图表的表达计划和可追溯理由。"""

    kind: ChartKind
    encoding: str
    rationale: str


def recommend_chart_plan(
    *,
    analysis_intent: str,
    value_kind: str,
    ordered: bool = False,
    confidence_interval: bool = False,
    category_count: int | None = None,
    comparison_count: int | None = None,
) -> ChartPlan:
    """根据分析目的和数据语义选择图表。

    ``category_count`` 和 ``comparison_count`` 只用于表达约束与记录理由，
    不把“图形种类越多越好”当成目标。无法安全表达时回退到横向条形图，
    因为它对标签和小样本类别最稳健。
    """

    intent = str(analysis_intent).strip().lower()
    value = str(value_kind).strip().lower()

    if intent == "sample_flow":
        return ChartPlan(
            kind=ChartKind.FLOW,
            encoding="stages -> nodes -> transitions",
            rationale="样本筛选是阶段转移关系，使用流程图比用柱形长度表达更准确。",
        )

    if intent == "composition":
        return ChartPlan(
            kind=ChartKind.STACKED_COMPOSITION,
            encoding="category -> share of whole",
            rationale=f"类别构成需要强调总体比例，使用 100% 堆叠构成图（{category_count or '多'} 类）。",
        )

    if intent == "ranking":
        return ChartPlan(
            kind=ChartKind.HORIZONTAL_BAR,
            encoding="category -> magnitude",
            rationale=f"无自然顺序的多类别排序适合横向条形图，便于读取长字段名（{category_count or '多'} 类）。",
        )

    if intent == "paired_comparison":
        return ChartPlan(
            kind=ChartKind.DUMBBELL,
            encoding="paired entities -> two estimates -> gap",
            rationale="论文结果与本地复核是成对估计，使用 Dumbbell 直接呈现差距而非制造柱高错觉。",
        )

    if intent == "group_difference":
        if confidence_interval:
            return ChartPlan(
                kind=ChartKind.POINT_CI,
                encoding="group -> point estimate + interval",
                rationale=f"组间比例比较带有不确定性，使用点估计与置信区间（{comparison_count or category_count or '多'} 组）。",
            )
        return ChartPlan(
            kind=ChartKind.HORIZONTAL_BAR,
            encoding="group -> magnitude",
            rationale="组间比较没有可用区间时使用横向条形图，并保留清晰的基线与标签。",
        )

    if intent == "ordered_trend" and ordered:
        return ChartPlan(
            kind=ChartKind.ORDERED_LINE,
            encoding="ordered level -> rate trajectory",
            rationale="年龄组或住院天数具有自然顺序，使用点线图显示趋势而非把各组当作无序类别。",
        )

    if intent == "model_effect" or value == "effect":
        return ChartPlan(
            kind=ChartKind.FOREST,
            encoding="term -> adjusted effect + interval",
            rationale="多变量模型需要同时比较效应方向、大小和区间，使用对数轴森林图。",
        )

    return ChartPlan(
        kind=ChartKind.HORIZONTAL_BAR,
        encoding="category -> magnitude",
        rationale="当前语义不足以支持更强的编码，回退到标签可读性最稳健的横向条形图。",
    )
