"""PPT 工作流注册表。

这里是 PPT 工作流模式、默认主题和外部来源说明的唯一 owner。
API、前端和渲染器只消费这个注册表提供的稳定 ID，不各自维护模式语义。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PptWorkflowSpec:
    """一个 PPT 工作流模式的静态渲染约束。"""

    workflow_id: str
    label: str
    description: str
    default_theme_preset: str | None
    fallback_theme_color: str | None
    source: str


PPT_WORKFLOWS: dict[str, PptWorkflowSpec] = {
    "native_editable": PptWorkflowSpec(
        workflow_id="native_editable",
        label="原生可编辑",
        description="保持当前项目的原生 PPTX 输出和默认主题行为。",
        default_theme_preset=None,
        fallback_theme_color=None,
        source="当前项目 PptRenderer；参考 ppt-master 原生可编辑工作流",
    ),
    "academic": PptWorkflowSpec(
        workflow_id="academic",
        label="学术实验汇报",
        description="使用清晰的科学汇报层级、图表优先布局和低装饰主题。",
        default_theme_preset="PACIFIC_DEEP",
        fallback_theme_color="#0B6173",
        source="当前项目 Nature 风格图表规则；参考 ppt-master academic routing",
    ),
    "sjtu_academic": PptWorkflowSpec(
        workflow_id="sjtu_academic",
        label="上海交大风格学术汇报",
        description="使用交大模板风格参考的深红强调色和学术汇报层级。",
        default_theme_preset="CORAL_ENERGY",
        fallback_theme_color="#8C1D40",
        source="xhh678876/openclaw-sjtu 模板/交大 PPT 入口；仅复用风格适配，不接入校园服务",
    ),
}

PPT_WORKFLOW_IDS = frozenset(PPT_WORKFLOWS)


def resolve_ppt_workflow(workflow_id: str | None) -> PptWorkflowSpec:
    """解析工作流 ID；未指定时保持默认原生可编辑模式。"""

    if workflow_id is None:
        return PPT_WORKFLOWS["native_editable"]
    try:
        return PPT_WORKFLOWS[workflow_id]
    except KeyError as exc:
        raise ValueError(
            f"ppt_workflow 必须为合法模式之一：{sorted(PPT_WORKFLOW_IDS)}"
        ) from exc
