"""论文级多语义图形规划器（SPEC 0039）。

该模块拥有逻辑图与数据图的交付物语义合同。它只规划表达方式和追溯
关系，不生成统计事实、不推断医学机制，也不负责 Word/PPT 的坐标布局。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Iterable


class FigureKind(StrEnum):
    """论文图形的语义类别。"""

    DATA_CHART = "data_chart"
    RESEARCH_FRAMEWORK = "research_framework"
    PROCESS_FLOW = "process_flow"
    RELATIONSHIP_GRAPH = "relationship_graph"
    CAUSAL_DAG = "causal_dag"
    EVIDENCE_CHAIN = "evidence_chain"
    DATA_PIPELINE = "data_pipeline"
    MECHANISM_PATH = "mechanism_path"
    TIMELINE = "timeline"
    HIERARCHY = "hierarchy"
    COMPARISON_MATRIX = "comparison_matrix"


class FigureFamily(StrEnum):
    """论文图形的视觉语法家族。"""

    STATISTICAL = "statistical"
    PROCESS = "process"
    RELATIONSHIP = "relationship"
    MATRIX = "matrix"
    EVIDENCE_ARGUMENT = "evidence_argument"
    TEMPORAL = "temporal"
    STRUCTURAL = "structural"
    MECHANISM = "mechanism"


class EvidenceStatus(StrEnum):
    """节点/边的证据状态。"""

    CONFIRMED = "confirmed"
    UNCERTAIN = "uncertain"
    OUT_OF_SCOPE = "out_of_scope"


class FigureValidationError(ValueError):
    """图形计划不满足追溯或关系安全约束。"""


@dataclass(frozen=True)
class RejectedFigureCandidate:
    """被编排器拒绝的候选图形及其结构化原因。"""

    name: str
    visual_family: FigureFamily | str
    reason: str
    missing_requirements: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise FigureValidationError("被拒绝的图形候选必须包含 name")
        if isinstance(self.visual_family, str):
            object.__setattr__(self, "visual_family", FigureFamily(self.visual_family))
        if not self.reason.strip():
            raise FigureValidationError(f"图形候选 {self.name} 必须包含拒绝原因")
        object.__setattr__(
            self,
            "missing_requirements",
            _as_tuple(self.missing_requirements),
        )


@dataclass(frozen=True)
class FigurePortfolioPlan:
    """一篇论文的异构图形组合计划。"""

    figures: tuple[FigurePlan, ...]
    coverage: tuple[str, ...] = ()
    selection_rationale: tuple[str, ...] = ()
    rejected_candidates: tuple[RejectedFigureCandidate, ...] = ()

    def __post_init__(self) -> None:
        if not self.figures:
            raise FigureValidationError("图形组合计划至少需要一张图形")
        titles = [figure.title for figure in self.figures]
        if len(set(titles)) != len(titles):
            raise FigureValidationError("图形组合计划中的 title 不能重复")
        if any(not isinstance(figure, FigurePlan) for figure in self.figures):
            raise FigureValidationError("图形组合计划只能包含 FigurePlan")
        object.__setattr__(self, "coverage", _as_tuple(self.coverage))
        object.__setattr__(self, "selection_rationale", _as_tuple(self.selection_rationale))
        normalized_rejected = tuple(self.rejected_candidates)
        if any(not isinstance(item, RejectedFigureCandidate) for item in normalized_rejected):
            raise FigureValidationError("rejected_candidates 必须是 RejectedFigureCandidate")
        object.__setattr__(self, "rejected_candidates", normalized_rejected)

    def to_metadata(self) -> dict[str, object]:
        """输出组合元数据，供 analysis_summary 和 artifact 审计使用。"""

        return {
            "figures": [figure.to_metadata() for figure in self.figures],
            "coverage": list(self.coverage),
            "selection_rationale": list(self.selection_rationale),
            "rejected_candidates": [
                {
                    "name": item.name,
                    "visual_family": item.visual_family.value,
                    "reason": item.reason,
                    "missing_requirements": list(item.missing_requirements),
                }
                for item in self.rejected_candidates
            ],
        }


@dataclass(frozen=True)
class ArgumentPlan:
    """期刊级图形论证合同。"""

    claim: str
    evidence_refs: tuple[str, ...] = ()
    method: str = ""
    result: str = ""
    boundary: str = ""
    body_reference: str = ""
    evidence_status: str = EvidenceStatus.CONFIRMED.value

    def __post_init__(self) -> None:
        if not self.claim.strip():
            raise FigureValidationError("论证计划必须包含主张 claim")
        if not self.evidence_refs:
            raise FigureValidationError("论证计划必须包含至少一个 evidence_refs")
        if not self.result.strip():
            raise FigureValidationError("论证计划必须包含结果 result")
        if not self.boundary.strip():
            raise FigureValidationError("论证计划必须包含解释边界 boundary")
        if self.evidence_status == EvidenceStatus.OUT_OF_SCOPE.value:
            raise FigureValidationError("超范围论证不能进入可渲染图形")


@dataclass(frozen=True)
class FigureNode:
    """逻辑图节点。"""

    node_id: str
    label: str
    role: str = ""
    source_ids: tuple[str, ...] = ()
    execution_run_ids: tuple[str, ...] = ()
    evidence_status: str = EvidenceStatus.CONFIRMED.value

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise FigureValidationError("节点 id 不能为空")
        if not self.label.strip():
            raise FigureValidationError(f"节点 {self.node_id} 的标签不能为空")


@dataclass(frozen=True)
class FigureEdge:
    """逻辑图边；relation 明确区分因果和观察性关联。"""

    source_node_id: str
    target_node_id: str
    relation: str
    label: str = ""
    evidence_status: str = EvidenceStatus.CONFIRMED.value
    source_ids: tuple[str, ...] = ()
    execution_run_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SchematicPanel:
    """科研示意图中的受控面板。"""

    panel_id: str
    label: str
    title: str

    def __post_init__(self) -> None:
        if not self.panel_id.strip() or not self.title.strip():
            raise FigureValidationError("科研示意图面板必须包含 panel_id 和 title")


@dataclass(frozen=True)
class SchematicPlacement:
    """把 FigureNode 映射到已注册的开放科研组件。"""

    placement_id: str
    node_id: str
    asset_id: str
    label: str
    role: str
    panel_id: str
    step_number: int | None = None

    def __post_init__(self) -> None:
        required = (
            self.placement_id,
            self.node_id,
            self.asset_id,
            self.label,
            self.role,
            self.panel_id,
        )
        if any(not value.strip() for value in required):
            raise FigureValidationError("科研组件 placement 字段不能为空")
        if self.step_number is not None and self.step_number < 1:
            raise FigureValidationError("科研组件 step_number 必须从 1 开始")


@dataclass(frozen=True)
class SchematicConnector:
    """科研组件之间的确定性连接；语义仍引用 FigureEdge。"""

    source_placement_id: str
    target_placement_id: str
    edge_relation: str
    label: str = ""
    style: str = "solid"

    def __post_init__(self) -> None:
        if not self.source_placement_id.strip() or not self.target_placement_id.strip():
            raise FigureValidationError("科研示意图连接必须包含起点和终点")
        if not self.edge_relation.strip():
            raise FigureValidationError("科研示意图连接必须引用 edge_relation")
        if self.style not in {"solid", "dashed", "inhibitory"}:
            raise FigureValidationError("科研示意图连接 style 无效")


@dataclass(frozen=True)
class ScientificSchematicSpec:
    """开放组件驱动的科研示意图呈现合同。"""

    panels: tuple[SchematicPanel, ...]
    placements: tuple[SchematicPlacement, ...]
    connectors: tuple[SchematicConnector, ...]
    legend_items: tuple[str, ...] = ()
    style_profile: str = "journal_clean"

    def __post_init__(self) -> None:
        if not self.panels or not self.placements:
            raise FigureValidationError("科研示意图至少需要一个面板和一个组件")
        if not self.style_profile.strip():
            raise FigureValidationError("科研示意图必须声明 style_profile")


@dataclass(frozen=True)
class FigurePlan:
    """跨 Word/PDF/PPT 消费的论文图形计划。"""

    figure_kind: FigureKind
    semantic_role: str
    title: str
    visual_family: FigureFamily | None = None
    layout_profile: str = "single_focus"
    data_requirements: tuple[str, ...] = ()
    selection_rationale: str = ""
    nodes: tuple[FigureNode, ...] = ()
    edges: tuple[FigureEdge, ...] = ()
    data_artifact_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    execution_run_ids: tuple[str, ...] = ()
    caption: str = ""
    note: str = ""
    rationale: str = ""
    editable_preference: str = "vector"
    target_surfaces: tuple[str, ...] = ("word", "ppt")
    chart_kind: str = ""
    chart_encoding: str = ""
    argument: ArgumentPlan | None = None
    legend_items: tuple[str, ...] = ()
    panel_labels: tuple[str, ...] = ()
    body_reference: str = ""
    schematic: ScientificSchematicSpec | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.figure_kind, str):
            object.__setattr__(self, "figure_kind", FigureKind(self.figure_kind))
        if self.visual_family is None:
            object.__setattr__(self, "visual_family", _default_figure_family(self.figure_kind))
        elif isinstance(self.visual_family, str):
            object.__setattr__(self, "visual_family", FigureFamily(self.visual_family))
        validate_figure_plan(self)

    def to_metadata(self) -> dict[str, object]:
        """输出 JSON 可序列化元数据，供 artifact 索引和审计使用。"""

        payload = asdict(self)
        payload["figure_kind"] = self.figure_kind.value
        payload["visual_family"] = self.visual_family.value
        payload["nodes"] = [asdict(node) for node in self.nodes]
        payload["edges"] = [asdict(edge) for edge in self.edges]
        payload["schematic"] = asdict(self.schematic) if self.schematic else None
        return payload


def _as_tuple(values: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(str(value).strip() for value in (values or ()) if str(value).strip())


def _default_figure_family(kind: FigureKind) -> FigureFamily:
    return {
        FigureKind.DATA_CHART: FigureFamily.STATISTICAL,
        FigureKind.PROCESS_FLOW: FigureFamily.PROCESS,
        FigureKind.DATA_PIPELINE: FigureFamily.PROCESS,
        FigureKind.RELATIONSHIP_GRAPH: FigureFamily.RELATIONSHIP,
        FigureKind.CAUSAL_DAG: FigureFamily.RELATIONSHIP,
        FigureKind.EVIDENCE_CHAIN: FigureFamily.EVIDENCE_ARGUMENT,
        FigureKind.TIMELINE: FigureFamily.TEMPORAL,
        FigureKind.RESEARCH_FRAMEWORK: FigureFamily.STRUCTURAL,
        FigureKind.HIERARCHY: FigureFamily.STRUCTURAL,
        FigureKind.MECHANISM_PATH: FigureFamily.MECHANISM,
        FigureKind.COMPARISON_MATRIX: FigureFamily.MATRIX,
    }[kind]


def validate_figure_plan(plan: FigurePlan) -> None:
    """验证节点/边引用、证据和因果表达的安全边界。"""

    if not plan.semantic_role.strip() or not plan.title.strip():
        raise FigureValidationError("图形计划必须包含 semantic_role 和 title")
    if not plan.caption.strip() or not plan.note.strip():
        raise FigureValidationError("图形计划必须包含 caption 和 note")
    if not plan.layout_profile.strip():
        raise FigureValidationError("图形计划必须包含 layout_profile")
    if not isinstance(plan.visual_family, FigureFamily):
        raise FigureValidationError("visual_family 必须是有效的 FigureFamily")
    if not isinstance(plan.data_requirements, tuple):
        raise FigureValidationError("data_requirements 必须是 tuple")

    node_ids = [node.node_id for node in plan.nodes]
    if len(set(node_ids)) != len(node_ids):
        raise FigureValidationError("图形节点 id 不能重复")

    valid_nodes = set(node_ids)
    for edge in plan.edges:
        if edge.source_node_id not in valid_nodes or edge.target_node_id not in valid_nodes:
            raise FigureValidationError(
                f"图形边引用不存在的节点：{edge.source_node_id}->{edge.target_node_id}"
            )
        if not edge.relation.strip():
            raise FigureValidationError("图形边 relation 不能为空")
        if edge.relation == "causal" and not (edge.source_ids or edge.execution_run_ids):
            raise FigureValidationError("因果边必须关联已确认来源或执行记录")
        if edge.relation == "associational" and not any(
            phrase in plan.note
            for phrase in ("非因果", "不代表因果", "不构成因果")
        ):
            raise FigureValidationError("观察性关联图必须在图注中明确非因果边界")
        if edge.evidence_status == EvidenceStatus.OUT_OF_SCOPE.value:
            raise FigureValidationError("超范围关系不能进入可渲染图形")

    if plan.figure_kind == FigureKind.CAUSAL_DAG and not any(
        edge.relation == "causal" for edge in plan.edges
    ):
        raise FigureValidationError("CAUSAL_DAG 至少需要一条已验证因果边")
    if plan.editable_preference not in {"native", "vector", "raster"}:
        raise FigureValidationError("editable_preference 必须为 native/vector/raster")
    if not plan.target_surfaces or not set(plan.target_surfaces).issubset({"word", "ppt"}):
        raise FigureValidationError("target_surfaces 只能包含 word 或 ppt")
    if plan.argument is not None and not isinstance(plan.argument, ArgumentPlan):
        raise FigureValidationError("argument 必须是 ArgumentPlan")
    if plan.figure_kind == FigureKind.EVIDENCE_CHAIN:
        if len(plan.nodes) < 8:
            raise FigureValidationError("证据链图至少需要 8 个论证节点")
        if len(plan.panel_labels) < 4:
            raise FigureValidationError("证据链图必须声明至少 4 个面板")
        required_relations = {"supports", "contains", "produces", "compared_with", "bounded_by"}
        relations = {edge.relation for edge in plan.edges}
        missing_relations = required_relations - relations
        if missing_relations:
            raise FigureValidationError(
                f"多面板证据链缺少论证关系：{','.join(sorted(missing_relations))}"
            )
    if plan.figure_kind == FigureKind.COMPARISON_MATRIX:
        if plan.visual_family != FigureFamily.MATRIX:
            raise FigureValidationError("比较矩阵必须使用 matrix 图形家族")
        if not plan.data_requirements:
            raise FigureValidationError("比较矩阵必须声明二维数据前提")
    if plan.figure_kind == FigureKind.TIMELINE:
        if plan.visual_family != FigureFamily.TEMPORAL:
            raise FigureValidationError("时间线必须使用 temporal 图形家族")
        if not plan.data_requirements:
            raise FigureValidationError("时间线必须声明可排序时间或阶段前提")
    if plan.figure_kind == FigureKind.DATA_PIPELINE and plan.visual_family != FigureFamily.PROCESS:
        raise FigureValidationError("数据管线必须使用 process 图形家族")
    if plan.figure_kind == FigureKind.RELATIONSHIP_GRAPH and plan.visual_family != FigureFamily.RELATIONSHIP:
        raise FigureValidationError("变量关系图必须使用 relationship 图形家族")
    if plan.figure_kind == FigureKind.EVIDENCE_CHAIN and plan.visual_family != FigureFamily.EVIDENCE_ARGUMENT:
        raise FigureValidationError("证据链必须使用 evidence_argument 图形家族")
    if plan.body_reference and not plan.body_reference.strip():
        raise FigureValidationError("body_reference 不能只有空白")
    if plan.schematic is not None:
        _validate_scientific_schematic(plan)


def _validate_scientific_schematic(plan: FigurePlan) -> None:
    schematic = plan.schematic
    if not isinstance(schematic, ScientificSchematicSpec):
        raise FigureValidationError("schematic 必须是 ScientificSchematicSpec")
    if plan.figure_kind not in {
        FigureKind.PROCESS_FLOW,
        FigureKind.DATA_PIPELINE,
        FigureKind.RESEARCH_FRAMEWORK,
        FigureKind.MECHANISM_PATH,
    }:
        raise FigureValidationError("当前图形语义不允许科研组件示意图")
    panel_ids = [panel.panel_id for panel in schematic.panels]
    if len(set(panel_ids)) != len(panel_ids):
        raise FigureValidationError("科研示意图 panel_id 不能重复")
    placement_ids = [placement.placement_id for placement in schematic.placements]
    if len(set(placement_ids)) != len(placement_ids):
        raise FigureValidationError("科研示意图 placement_id 不能重复")
    valid_panels = set(panel_ids)
    valid_nodes = {node.node_id for node in plan.nodes}
    valid_placements = set(placement_ids)
    placements = {placement.placement_id: placement for placement in schematic.placements}
    node_by_id = {node.node_id: node for node in plan.nodes}
    for placement in schematic.placements:
        if placement.panel_id not in valid_panels:
            raise FigureValidationError(
                f"科研组件 {placement.placement_id} 引用不存在的面板"
            )
        if placement.node_id not in valid_nodes:
            raise FigureValidationError(
                f"科研组件 {placement.placement_id} 引用不存在的 FigureNode"
            )
        if placement.label != node_by_id[placement.node_id].label:
            raise FigureValidationError("科研组件标签必须与 FigureNode 真源一致")
    figure_relations = {
        (edge.source_node_id, edge.target_node_id, edge.relation) for edge in plan.edges
    }
    incoming = {placement_id: 0 for placement_id in valid_placements}
    outgoing = {placement_id: [] for placement_id in valid_placements}
    for connector in schematic.connectors:
        if (
            connector.source_placement_id not in valid_placements
            or connector.target_placement_id not in valid_placements
        ):
            raise FigureValidationError("科研示意图连接引用不存在的 placement")
        incoming[connector.target_placement_id] += 1
        outgoing[connector.source_placement_id].append(
            connector.target_placement_id
        )
        source_node = placements[connector.source_placement_id].node_id
        target_node = placements[connector.target_placement_id].node_id
        if (source_node, target_node, connector.edge_relation) not in figure_relations:
            raise FigureValidationError("科研示意图连接没有对应 FigureEdge 真源")
        matching_edge = next(
            edge
            for edge in plan.edges
            if (
                edge.source_node_id,
                edge.target_node_id,
                edge.relation,
            ) == (source_node, target_node, connector.edge_relation)
        )
        if connector.label and connector.label != matching_edge.label:
            raise FigureValidationError("科研示意图连接标签必须与 FigureEdge 真源一致")

    queue = [placement_id for placement_id, count in incoming.items() if count == 0]
    visited = 0
    while queue:
        source = queue.pop(0)
        visited += 1
        for target in outgoing[source]:
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
    if visited != len(valid_placements):
        raise FigureValidationError("科研示意图连接必须构成无环图")

def recommend_figure_plan(
    *,
    figure_kind: FigureKind | str,
    semantic_role: str,
    title: str,
    visual_family: FigureFamily | str | None = None,
    layout_profile: str = "single_focus",
    data_requirements: Iterable[str] = (),
    selection_rationale: str = "",
    nodes: Iterable[FigureNode] = (),
    edges: Iterable[FigureEdge] = (),
    data_artifact_ids: Iterable[str] = (),
    source_ids: Iterable[str] = (),
    execution_run_ids: Iterable[str] = (),
    caption: str,
    note: str,
    rationale: str = "",
    editable_preference: str = "vector",
    target_surfaces: Iterable[str] = ("word", "ppt"),
    chart_kind: str = "",
    chart_encoding: str = "",
    argument: ArgumentPlan | None = None,
    legend_items: Iterable[str] = (),
    panel_labels: Iterable[str] = (),
    body_reference: str = "",
    schematic: ScientificSchematicSpec | None = None,
    metadata: dict[str, object] | None = None,
) -> FigurePlan:
    """构造并校验一个图形计划；所有语义输入必须由上游真源提供。"""

    kind = FigureKind(figure_kind)
    default_family = _default_figure_family(kind)
    plan = FigurePlan(
        figure_kind=kind,
        semantic_role=semantic_role.strip(),
        title=title.strip(),
        visual_family=FigureFamily(visual_family) if visual_family is not None else default_family,
        layout_profile=layout_profile.strip(),
        data_requirements=_as_tuple(data_requirements),
        selection_rationale=selection_rationale.strip() or rationale.strip(),
        nodes=tuple(nodes),
        edges=tuple(edges),
        data_artifact_ids=_as_tuple(data_artifact_ids),
        source_ids=_as_tuple(source_ids),
        execution_run_ids=_as_tuple(execution_run_ids),
        caption=caption.strip(),
        note=note.strip(),
        rationale=rationale.strip(),
        editable_preference=editable_preference,
        target_surfaces=_as_tuple(target_surfaces),
        chart_kind=chart_kind.strip(),
        chart_encoding=chart_encoding.strip(),
        argument=argument,
        legend_items=_as_tuple(legend_items),
        panel_labels=_as_tuple(panel_labels),
        body_reference=body_reference.strip(),
        schematic=schematic,
        metadata=metadata or {},
    )
    return plan


def figure_plan_to_artifact(
    plan: FigurePlan,
    *,
    name: str,
    file_path: str,
    artifact_type: str = "CHART_PNG",
    execution_run_id: str = "",
    artifact_group: str = "",
) -> dict[str, object]:
    """把图形计划映射为现有执行产物合同，不改变原始 artifact 字段。"""

    payload: dict[str, object] = {
        "name": name,
        "artifact_type": artifact_type,
        "file_path": file_path,
        "execution_run_id": execution_run_id,
        "artifact_group": artifact_group,
        "figure_kind": plan.figure_kind.value,
        "figure_semantic_role": plan.semantic_role,
        "figure_visual_family": plan.visual_family.value,
        "figure_layout_profile": plan.layout_profile,
        "figure_data_requirements": list(plan.data_requirements),
        "figure_selection_rationale": plan.selection_rationale,
        "figure_caption": plan.caption,
        "figure_note": plan.note,
        "figure_rationale": plan.rationale,
        "figure_editable_preference": plan.editable_preference,
        "figure_plan": plan.to_metadata(),
        "figure_argument": (
            asdict(plan.argument) if plan.argument is not None else {}
        ),
        "figure_legend_items": list(plan.legend_items),
        "figure_panel_labels": list(plan.panel_labels),
        "figure_body_reference": plan.body_reference,
        "figure_schematic": asdict(plan.schematic) if plan.schematic is not None else {},
    }
    if plan.chart_kind:
        payload["chart_kind"] = plan.chart_kind
    if plan.chart_encoding:
        payload["chart_encoding"] = plan.chart_encoding
    return payload
