"""项目工作台进度投影的唯一 owner。

本模块只查询各领域当前事实并生成统一只读 projection。
它不修改项目状态，也不把数据集、执行或交付物的语义复制成第二套状态机。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.analysis.models import AnalysisPlan
from app.modules.analysis.status import AnalysisPlanStatus
from app.modules.datasets.models import Dataset, DatasetVersion
from app.modules.datasets.status import DatasetStatus, DatasetVersionStatus
from app.modules.execution.models import ExecutionRun
from app.modules.execution.status import ExecutionRunStatus
from app.modules.outlines.models import Deliverable, DeliverableVersion, Outline
from app.modules.outlines.status import (
    DeliverableStatus,
    DeliverableType,
    DeliverableVersionStatus,
    OutlineStatus,
)
from app.modules.projects.contracts import (
    ProjectProgressProjection,
    WorkspaceBlockingReason,
    WorkspaceNextAction,
    WorkspaceProgressAction,
    WorkspaceProgressCurrent,
    WorkspaceProgressDisplay,
    WorkspaceProgressPhase,
    WorkspaceProgressStep,
    WorkspaceProjectSummary,
    WorkspaceStageProjection,
)
from app.modules.projects.models import Project
from app.modules.projects.status import ProjectStatus
from app.modules.requirements.models import RequirementPlan, RequirementSource
from app.modules.requirements.status import PlanStatus
from app.modules.sources.models import EvidenceCard, ParsedDocument, Source
from app.modules.sources.status import EvidenceCardStatus, SourceStatus


_STATUS_RANK: dict[str, int] = {
    ProjectStatus.DRAFT.value: 0,
    ProjectStatus.REQUIREMENT_PARSED.value: 1,
    ProjectStatus.REQUIREMENT_CONFIRMED.value: 2,
    ProjectStatus.SOURCES_COLLECTED.value: 3,
    ProjectStatus.EVIDENCE_CONFIRMED.value: 4,
    ProjectStatus.DATASET_READY.value: 5,
    ProjectStatus.ANALYSIS_PLANNED.value: 6,
    ProjectStatus.ANALYSIS_CONFIRMED.value: 7,
    ProjectStatus.EXECUTING.value: 8,
    ProjectStatus.EXECUTION_FAILED.value: 8,
    ProjectStatus.RESULT_CONFIRMED.value: 9,
    ProjectStatus.OUTLINE_CONFIRMED.value: 10,
    ProjectStatus.GENERATING.value: 11,
    ProjectStatus.COMPLETED.value: 12,
}

_PROJECT_STATUS_LABELS: dict[str, str] = {
    ProjectStatus.DRAFT.value: "草稿",
    ProjectStatus.REQUIREMENT_PARSED.value: "要求已解析",
    ProjectStatus.REQUIREMENT_CONFIRMED.value: "实验要求已确认",
    ProjectStatus.SOURCES_COLLECTED.value: "资料来源已收集",
    ProjectStatus.EVIDENCE_CONFIRMED.value: "证据卡片已确认",
    ProjectStatus.DATASET_READY.value: "数据集已就绪",
    ProjectStatus.ANALYSIS_PLANNED.value: "分析方案已生成",
    ProjectStatus.ANALYSIS_CONFIRMED.value: "分析方案已确认",
    ProjectStatus.EXECUTING.value: "正在执行",
    ProjectStatus.EXECUTION_FAILED.value: "执行需要处理",
    ProjectStatus.RESULT_CONFIRMED.value: "分析结果已确认",
    ProjectStatus.OUTLINE_CONFIRMED.value: "报告大纲已确认",
    ProjectStatus.GENERATING.value: "交付物正在生成",
    ProjectStatus.COMPLETED.value: "项目已完成",
}

_PROGRESS_STATUS_LABELS: dict[str, str] = {
    "LOCKED": "未开放",
    "READY": "待开始",
    "IN_PROGRESS": "进行中",
    "BLOCKED": "需处理",
    "FAILED": "需要恢复",
    "COMPLETED": "已完成",
}

_PHASE_DESCRIPTIONS: dict[str, str] = {
    "requirements": "明确实验目的、研究问题、数据需求与交付要求。",
    "sources_evidence": "整理资料来源并确认可追溯证据卡片。",
    "datasets": "上传原始数据并完成数据预览与基本检查。",
    "analysis": "确定分析方法、建立分析计划与评估指标。",
    "execution": "运行受控代码并确认表格、图表等执行产物。",
    "outline": "确认报告结构以及 Word/PPT 共用的大纲。",
    "deliverables": "检查并下载正式 Word、PDF 和 PPT 交付物。",
}

_STAGE_DEFINITIONS = (
    {
        "id": "requirements",
        "label": "实验要求",
        "description": "明确实验目的、研究问题、数据需求与交付要求。",
        "phase_id": "requirements",
        "phase_label": "实验要求",
        "is_substep": False,
        "workspace": "requirements",
        "unlock_rank": 0,
        "complete_rank": 2,
    },
    {
        "id": "sources",
        "label": "资料来源",
        "description": "登记公开 URL 或本地辅助资料，等待采集和解析。",
        "phase_id": "sources_evidence",
        "phase_label": "资料与证据",
        "is_substep": True,
        "workspace": "sources",
        "unlock_rank": 2,
        "complete_rank": 3,
    },
    {
        "id": "evidence",
        "label": "证据卡片",
        "description": "从已解析资料中确认可追溯的证据卡片。",
        "phase_id": "sources_evidence",
        "phase_label": "资料与证据",
        "is_substep": True,
        "workspace": "evidence",
        "unlock_rank": 3,
        "complete_rank": 4,
    },
    {
        "id": "datasets",
        "label": "数据上传",
        "description": "上传数据并完成字段概览与质量检查。",
        "phase_id": "datasets",
        "phase_label": "数据上传",
        "is_substep": False,
        "workspace": "datasets",
        "unlock_rank": 4,
        "complete_rank": 5,
    },
    {
        "id": "analysis",
        "label": "分析方案",
        "description": "生成、编辑并确认分析和图表方案。",
        "phase_id": "analysis",
        "phase_label": "分析方案",
        "is_substep": False,
        "workspace": "analysis",
        "unlock_rank": 5,
        "complete_rank": 7,
    },
    {
        "id": "execution",
        "label": "结果执行",
        "description": "生成受控代码、查看执行记录并确认结果。",
        "phase_id": "execution",
        "phase_label": "结果执行",
        "is_substep": False,
        "workspace": "execution",
        "unlock_rank": 7,
        "complete_rank": 9,
    },
    {
        "id": "outline",
        "label": "报告大纲",
        "description": "确认 Word/PPT 共用的正式报告结构。",
        "phase_id": "outline",
        "phase_label": "报告大纲",
        "is_substep": False,
        "workspace": "outline",
        "unlock_rank": 9,
        "complete_rank": 10,
    },
    {
        "id": "deliverables",
        "label": "正式交付物",
        "description": "审阅并下载正式 Word、PDF 和 PPT 文件。",
        "phase_id": "deliverables",
        "phase_label": "正式交付物",
        "is_substep": False,
        "workspace": "deliverables",
        "unlock_rank": 10,
        "complete_rank": 12,
    },
)


def _route(project_id: str, workspace: str) -> str:
    return f"/projects/{project_id}/{workspace}"


def _reason(
    code: str,
    message: str,
    source: str,
    kind: str = "BLOCKED",
) -> WorkspaceBlockingReason:
    return WorkspaceBlockingReason(
        code=code,
        message=message,
        display_message=message,
        source=source,
        kind=kind,
    )


def _lock_reason(label: str) -> WorkspaceBlockingReason:
    return _reason(
        "WORKSPACE_LOCKED",
        f"请先完成前置阶段后再进入{label}。",
        "projects",
        "LOCKED",
    )


def _has_reason_kind(
    reasons: list[WorkspaceBlockingReason],
    kind: str,
) -> bool:
    return any(item.kind == kind for item in reasons)


def _latest_requirement_plan(db: Session, project_id: str) -> RequirementPlan | None:
    return (
        db.query(RequirementPlan)
        .filter(RequirementPlan.project_id == project_id)
        .order_by(RequirementPlan.updated_at.desc())
        .first()
    )


def _latest_dataset_version(db: Session, project_id: str) -> DatasetVersion | None:
    dataset = (
        db.query(Dataset)
        .filter(
            Dataset.project_id == project_id,
            Dataset.status != DatasetStatus.DELETED.value,
        )
        .order_by(Dataset.updated_at.desc())
        .first()
    )
    if not dataset:
        return None
    return (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset.id)
        .order_by(DatasetVersion.version.desc())
        .first()
    )


def _has_successful_deliverable(
    db: Session, project_id: str, deliverable_type: str
) -> bool:
    deliverables = (
        db.query(Deliverable)
        .filter(
            Deliverable.project_id == project_id,
            Deliverable.deliverable_type == deliverable_type,
            Deliverable.status != DeliverableStatus.STALE.value,
        )
        .all()
    )
    return any(
        db.query(DeliverableVersion)
        .filter(
            DeliverableVersion.deliverable_id == deliverable.id,
            DeliverableVersion.status == DeliverableVersionStatus.SUCCEEDED.value,
        )
        .count()
        > 0
        for deliverable in deliverables
    )


def _blocking_reasons(
    db: Session, project_id: str, stage_id: str
) -> list[WorkspaceBlockingReason]:
    if stage_id == "requirements":
        source_count = (
            db.query(RequirementSource)
            .filter(RequirementSource.project_id == project_id)
            .count()
        )
        if source_count == 0:
            return [
                _reason(
                    "REQUIREMENT_SOURCE_MISSING",
                    "还没有录入实验要求。",
                    "requirements",
                )
            ]
        plan = _latest_requirement_plan(db, project_id)
        if plan is None:
            return [
                _reason(
                    "REQUIREMENT_PLAN_NOT_GENERATED",
                    "实验要求已录入，但还没有生成结构化任务单。",
                    "requirements",
                )
            ]
        if plan.status != PlanStatus.CONFIRMED.value:
            return [
                _reason(
                    "REQUIREMENT_CONFIRM_REQUIRED",
                    "结构化任务单尚未确认。",
                    "requirements",
                )
            ]
        return []

    if stage_id == "sources":
        sources = (
            db.query(Source)
            .filter(
                Source.project_id == project_id,
                Source.status != SourceStatus.DELETED.value,
            )
            .all()
        )
        if not sources:
            return [
                _reason("SOURCE_MATERIAL_MISSING", "还没有登记资料来源。", "sources")
            ]
        failed = [item for item in sources if item.status == SourceStatus.FAILED.value]
        if failed:
            return [
                _reason(
                    "SOURCE_FETCH_FAILED",
                    f"有 {len(failed)} 个资料来源处理失败。",
                    "sources",
                    "FAILED",
                )
            ]
        return []

    if stage_id == "evidence":
        parsed_count = (
            db.query(ParsedDocument)
            .filter(ParsedDocument.project_id == project_id)
            .count()
        )
        if parsed_count == 0:
            return [
                _reason(
                    "SOURCE_NOT_PARSED",
                    "资料还没有完成解析，暂时不能确认证据。",
                    "sources",
                )
            ]
        confirmed_count = (
            db.query(EvidenceCard)
            .filter(
                EvidenceCard.project_id == project_id,
                EvidenceCard.status == EvidenceCardStatus.CONFIRMED.value,
            )
            .count()
        )
        if confirmed_count == 0:
            return [
                _reason(
                    "EVIDENCE_CONFIRM_REQUIRED",
                    "还没有确认的证据卡片。",
                    "evidence",
                )
            ]
        return []

    if stage_id == "datasets":
        version = _latest_dataset_version(db, project_id)
        if version is None:
            return [
                _reason("DATASET_MISSING", "还没有上传数据集。", "datasets")
            ]
        if version.status != DatasetVersionStatus.PARSED.value:
            return [
                _reason(
                    "DATASET_NOT_READY",
                    "最新数据版本还没有完成解析。",
                    "datasets",
                )
            ]
        return []

    if stage_id == "analysis":
        plans = (
            db.query(AnalysisPlan)
            .filter(AnalysisPlan.project_id == project_id)
            .order_by(AnalysisPlan.updated_at.desc())
            .all()
        )
        if any(plan.status == AnalysisPlanStatus.CONFIRMED.value for plan in plans):
            return []
        if plans:
            return [
                _reason(
                    "ANALYSIS_CONFIRM_REQUIRED",
                    "分析方案已生成，但还没有确认。",
                    "analysis",
                )
            ]
        return [
            _reason(
                "ANALYSIS_PLAN_MISSING",
                "还没有生成分析方案。",
                "analysis",
            )
        ]

    if stage_id == "execution":
        failed_count = (
            db.query(ExecutionRun)
            .filter(
                ExecutionRun.project_id == project_id,
                ExecutionRun.status == ExecutionRunStatus.FAILED.value,
            )
            .count()
        )
        if failed_count:
            return [
                _reason(
                    "EXECUTION_FAILED",
                    f"有 {failed_count} 次执行失败，需要查看错误并重试。",
                    "execution",
                    "FAILED",
                )
            ]
        succeeded_count = (
            db.query(ExecutionRun)
            .filter(
                ExecutionRun.project_id == project_id,
                ExecutionRun.status == ExecutionRunStatus.SUCCEEDED.value,
            )
            .count()
        )
        if succeeded_count == 0:
            return [
                _reason(
                    "EXECUTION_NOT_CONFIRMED",
                    "还没有成功的执行记录。",
                    "execution",
                )
            ]
        return []

    if stage_id == "outline":
        outlines = (
            db.query(Outline)
            .filter(Outline.project_id == project_id)
            .order_by(Outline.updated_at.desc())
            .all()
        )
        if any(item.status == OutlineStatus.CONFIRMED.value for item in outlines):
            return []
        if outlines:
            return [
                _reason(
                    "OUTLINE_CONFIRM_REQUIRED",
                    "报告大纲已生成，但还没有确认。",
                    "outline",
                )
            ]
        return [
            _reason("OUTLINE_MISSING", "还没有生成报告大纲。", "outline")
        ]

    if stage_id == "deliverables":
        reasons: list[WorkspaceBlockingReason] = []
        for deliverable_type, label in (
            (DeliverableType.WORD.value, "Word"),
            (DeliverableType.PDF.value, "PDF"),
            (DeliverableType.PPT.value, "PPT"),
        ):
            if not _has_successful_deliverable(db, project_id, deliverable_type):
                reasons.append(
                    _reason(
                        f"DELIVERABLE_{deliverable_type}_MISSING",
                        f"{label} 还没有成功版本。",
                        "outlines",
                    )
                )
        return reasons

    return []


def _stage_state(
    status_rank: int,
    status: str,
    definition: dict,
    reasons: list[WorkspaceBlockingReason],
) -> str:
    """将真实事实映射为规范工作区状态。

    锁定优先于所有内容；失败和已开放工作区的阻断事实优先于完成等级，
    从而避免“达到完成 rank 但仍有失败事实”被错误标为 COMPLETED。
    """

    if status_rank < definition["unlock_rank"]:
        return "LOCKED"
    if (
        definition["id"] == "execution"
        and status == ProjectStatus.EXECUTION_FAILED.value
    ):
        return "FAILED"
    if _has_reason_kind(reasons, "FAILED"):
        return "FAILED"
    if status_rank >= definition["complete_rank"]:
        if _has_reason_kind(reasons, "BLOCKED"):
            return "BLOCKED"
        return "COMPLETED"
    if status_rank == definition["unlock_rank"]:
        return "READY"
    if _has_reason_kind(reasons, "BLOCKED"):
        return "BLOCKED"
    return "IN_PROGRESS"


def _step_display(
    state: str,
    label: str,
    reasons: list[WorkspaceBlockingReason],
) -> WorkspaceProgressDisplay:
    if state == "LOCKED":
        next_step_text = "完成前置阶段后开放。"
    elif state == "FAILED":
        next_step_text = "查看失败原因并重试或修正后继续。"
    elif state == "BLOCKED" and reasons:
        next_step_text = reasons[0].display_message or reasons[0].message
    elif state == "COMPLETED":
        next_step_text = "该步骤已完成。"
    elif state == "READY":
        next_step_text = f"进入{label}工作区开始处理。"
    else:
        next_step_text = f"继续完成{label}工作区中的任务。"
    return WorkspaceProgressDisplay(
        status_label=_PROGRESS_STATUS_LABELS[state],
        next_step_text=next_step_text,
    )


def _step_actions(
    project_id: str,
    definition: dict,
    state: str,
    open_reason: WorkspaceBlockingReason | None,
) -> tuple[list[WorkspaceProgressAction], WorkspaceProgressAction | None]:
    route = _route(project_id, definition["workspace"])
    navigate = WorkspaceProgressAction(
        id=f"open_{definition['id']}",
        kind="NAVIGATE",
        label=f"进入{definition['label']}工作区",
        description=definition["description"],
        enabled=state != "LOCKED",
        disabled_reason=open_reason,
        route=route,
        command_id=f"workspace.open.{definition['id']}",
    )
    recovery = None
    actions = [navigate]
    if state == "FAILED":
        recovery = WorkspaceProgressAction(
            id=f"recover_{definition['id']}",
            kind="NAVIGATE",
            label=f"查看{definition['label']}失败原因",
            description="进入工作区查看错误详情，并使用现有页面操作进行重试或修正。",
            enabled=True,
            route=route,
            command_id=f"workspace.recover.{definition['id']}",
        )
        actions.append(recovery)
    return actions, recovery


def _phase_state(steps: list[WorkspaceProgressStep]) -> str:
    statuses = [step.status for step in steps]
    if any(status == "FAILED" for status in statuses):
        return "FAILED"
    if any(status == "BLOCKED" for status in statuses):
        return "BLOCKED"
    if statuses and all(status == "COMPLETED" for status in statuses):
        return "COMPLETED"
    if any(status == "IN_PROGRESS" for status in statuses):
        return "IN_PROGRESS"
    if any(status == "READY" for status in statuses):
        return "READY"
    return "LOCKED"


def _unique_reasons(
    reasons: list[WorkspaceBlockingReason],
) -> list[WorkspaceBlockingReason]:
    result: list[WorkspaceBlockingReason] = []
    seen: set[str] = set()
    for reason in reasons:
        if reason.code in seen:
            continue
        seen.add(reason.code)
        result.append(reason)
    return result


def _phase_display(
    state: str,
    label: str,
    steps: list[WorkspaceProgressStep],
) -> WorkspaceProgressDisplay:
    reasons = [
        reason
        for step in steps
        for reason in step.blocking_reasons
    ]
    return _step_display(state, label, reasons)


def build_workspace_projection(
    db: Session, project_id: str
) -> ProjectProgressProjection:
    """从当前项目和各领域事实生成统一工作台进度投影。"""
    project: Project | None = (
        db.query(Project).filter(Project.id == project_id).first()
    )
    if not project:
        raise AppError(code="PROJECT_NOT_FOUND", message=f"未找到项目 {project_id}")
    if project.status not in _STATUS_RANK:
        raise AppError(
            code="PROJECT_STATUS_UNKNOWN",
            message=f"项目状态无法生成工作台投影：{project.status}",
        )

    rank = _STATUS_RANK[project.status]
    step_records: list[dict] = []
    compatibility_stages: list[WorkspaceStageProjection] = []
    for definition in _STAGE_DEFINITIONS:
        raw_reasons = _blocking_reasons(db, project_id, definition["id"])
        state = _stage_state(rank, project.status, definition, raw_reasons)
        open_reason = _lock_reason(definition["label"]) if state == "LOCKED" else None
        reasons = [] if state == "LOCKED" else raw_reasons
        actions, recovery_action = _step_actions(
            project_id,
            definition,
            state,
            open_reason,
        )
        route = _route(project_id, definition["workspace"])
        step = WorkspaceProgressStep(
            id=definition["id"],
            label=definition["label"],
            description=definition["description"],
            is_substep=definition["is_substep"],
            status=state,
            is_open=state != "LOCKED",
            open_reason=open_reason,
            blocking_reasons=reasons,
            display=_step_display(state, definition["label"], reasons),
            route=route,
            command_id=f"workspace.open.{definition['id']}",
            actions=actions,
            recovery_action=recovery_action,
        )
        step_records.append(
            {
                "definition": definition,
                "step": step,
                "state": state,
                "reasons": reasons,
            }
        )
        compatibility_stages.append(
            WorkspaceStageProjection(
                id=definition["id"],
                label=definition["label"],
                route=route,
                state=state,
                phase_id=definition["phase_id"],
                phase_label=definition["phase_label"],
                is_substep=definition["is_substep"],
                blocking_reasons=reasons,
            )
        )

    phase_records: list[dict] = []
    phase_order: list[str] = []
    for record in step_records:
        phase_id = record["definition"]["phase_id"]
        if phase_id not in phase_order:
            phase_order.append(phase_id)
            phase_records.append(
                {
                    "id": phase_id,
                    "label": record["definition"]["phase_label"],
                    "description": _PHASE_DESCRIPTIONS[phase_id],
                    "steps": [],
                }
            )
        phase_records[phase_order.index(phase_id)]["steps"].append(record["step"])

    phases: list[WorkspaceProgressPhase] = []
    phase_by_step_id: dict[str, WorkspaceProgressPhase] = {}
    for phase_record in phase_records:
        steps = phase_record["steps"]
        state = _phase_state(steps)
        open_reason = _lock_reason(phase_record["label"]) if state == "LOCKED" else None
        reasons = _unique_reasons(
            [
                reason
                for step in steps
                if step.is_open
                for reason in step.blocking_reasons
            ]
        )
        open_steps = [step for step in steps if step.is_open]
        phase_actions: list[WorkspaceProgressAction] = []
        if open_steps:
            phase_actions.append(open_steps[0].actions[0])
        else:
            phase_actions.append(
                WorkspaceProgressAction(
                    id=f"open_{phase_record['id']}",
                    kind="NAVIGATE",
                    label=f"进入{phase_record['label']}",
                    description=phase_record["description"],
                    enabled=False,
                    disabled_reason=open_reason,
                    command_id=f"workspace.open.phase.{phase_record['id']}",
                )
            )
        phase = WorkspaceProgressPhase(
            id=phase_record["id"],
            label=phase_record["label"],
            description=phase_record["description"],
            status=state,
            is_open=state != "LOCKED",
            open_reason=open_reason,
            blocking_reasons=reasons,
            display=_phase_display(state, phase_record["label"], steps),
            steps=steps,
            actions=phase_actions,
        )
        phases.append(phase)
        for step in steps:
            phase_by_step_id[step.id] = phase

    if project.status == ProjectStatus.EXECUTION_FAILED.value:
        current_record = next(
            record
            for record in step_records
            if record["step"].id == "execution"
        )
    elif project.status == ProjectStatus.COMPLETED.value:
        current_record = step_records[-1]
    else:
        current_record = next(
            (record for record in step_records if record["state"] != "COMPLETED"),
            step_records[-1],
        )
    current_step: WorkspaceProgressStep = current_record["step"]
    current_phase = phase_by_step_id[current_step.id]
    current = WorkspaceProgressCurrent(
        phase_id=current_phase.id,
        phase_label=current_phase.label,
        step_id=current_step.id,
        label=current_step.label,
        status=current_step.status,
    )

    recommended_next_action = None
    if project.status != ProjectStatus.COMPLETED.value:
        recommended_next_action = (
            current_step.recovery_action
            if current_step.status == "FAILED" and current_step.recovery_action
            else current_step.actions[0]
        )

    legacy_next_action = None
    if recommended_next_action and recommended_next_action.route:
        legacy_next_action = WorkspaceNextAction(
            stage_id=current_step.id,
            label=recommended_next_action.label,
            route=recommended_next_action.route,
            reason=current_step.display.next_step_text,
        )

    return ProjectProgressProjection(
        project_id=project_id,
        project=WorkspaceProjectSummary(
            id=project.id,
            name=project.name,
            topic=project.topic,
            status=project.status,
            status_label=_PROJECT_STATUS_LABELS[project.status],
            updated_at=project.updated_at.isoformat(),
        ),
        current=current,
        phases=phases,
        recommended_next_action=recommended_next_action,
        current_stage=compatibility_stages[
            [record["step"].id for record in step_records].index(current_step.id)
        ],
        next_action=legacy_next_action,
        stages=compatibility_stages,
        projection_generated_at=datetime.now(timezone.utc).isoformat(),
    )