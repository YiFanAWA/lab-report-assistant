"""分析方案核心服务。

拥有分析方案候选生成、用户确认状态、STALE 传播的业务语义。
API、Worker、提示词只能调用本服务，不能直接修改方案状态。
"""

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.analysis.contracts import (
    AnalysisPlanResponse,
    AnalysisPlanListResponse,
    CompleteAnalysisResponse,
    UpdateAnalysisPlanRequest,
)
from app.modules.analysis.models import AnalysisPlan, _uid, _now
from app.modules.analysis.status import AnalysisPlanStatus, AnalysisChangeType
from app.modules.datasets import service as dataset_service
from app.modules.datasets.status import DatasetStatus
from app.modules.jobs import service as job_service
from app.modules.jobs.status import JobType
from app.modules.projects import service as project_service
from app.modules.projects.status import ProjectStatus
from app.modules.requirements.models import ChangeRecord


# --- 内部辅助 ---


def _ensure_project(db: Session, project_id: str):
    return project_service.get_project(db, project_id)


def _add_change(db: Session, project_id: str, change_type: str,
                summary: str) -> None:
    """写入变更记录。"""
    rec = ChangeRecord(
        project_id=project_id,
        change_type=change_type,
        summary=summary,
    )
    db.add(rec)


def _ensure_project_ready_for_analysis(project) -> None:
    """校验项目状态是 DATASET_READY 或之后。"""
    allowed = [
        ProjectStatus.DATASET_READY.value,
        ProjectStatus.ANALYSIS_PLANNED.value,
        ProjectStatus.ANALYSIS_CONFIRMED.value,
        ProjectStatus.EXECUTING.value,
        ProjectStatus.RESULT_CONFIRMED.value,
        ProjectStatus.OUTLINE_CONFIRMED.value,
        ProjectStatus.GENERATING.value,
        ProjectStatus.COMPLETED.value,
    ]
    if project.status not in allowed:
        raise AppError(
            code="PROJECT_EVIDENCE_NOT_CONFIRMED",
            message="项目数据集未就绪，无法生成分析方案",
        )


# --- 响应转换 ---


def _plan_to_response(p: AnalysisPlan) -> AnalysisPlanResponse:
    """将 AnalysisPlan ORM 模型转换为 AnalysisPlanResponse。"""
    return AnalysisPlanResponse(
        id=p.id,
        project_id=p.project_id,
        dataset_id=p.dataset_id,
        dataset_version_id=p.dataset_version_id,
        cleaning_plan=p.cleaning_plan,
        analysis_plan=p.analysis_plan,
        chart_plan=p.chart_plan,
        status=p.status,
        candidate_source=p.candidate_source,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
        confirmed_at=p.confirmed_at.isoformat() if p.confirmed_at else None,
    )


def _plan_list_to_response(plans: list[AnalysisPlan]) -> AnalysisPlanListResponse:
    return AnalysisPlanListResponse(items=[_plan_to_response(p) for p in plans])


# --- 对外暴露 ---


def plan_to_response(p: AnalysisPlan) -> AnalysisPlanResponse:
    return _plan_to_response(p)


def plan_list_to_response(plans: list[AnalysisPlan]) -> AnalysisPlanListResponse:
    return _plan_list_to_response(plans)


def complete_analysis_to_response(project) -> CompleteAnalysisResponse:
    return CompleteAnalysisResponse(status=project.status)


# --- 分析方案生成 ---


def generate_analysis_plan(
    db: Session,
    project_id: str,
    dataset_id: str,
) -> str:
    """触发生成分析方案候选，返回 job_id。

    前置条件：dataset.status=READY。
    """
    project = _ensure_project(db, project_id)
    _ensure_project_ready_for_analysis(project)

    dataset = dataset_service.get_dataset_by_id_and_project(
        db, project_id, dataset_id)
    if dataset.status != DatasetStatus.READY.value:
        raise AppError(
            code="DATASET_NOT_PARSED",
            message="数据集未解析，无法生成分析方案",
            field="dataset_id",
        )

    latest_version = dataset_service.get_latest_version(db, dataset_id)
    if latest_version.status != "PARSED":
        raise AppError(
            code="DATASET_NOT_PARSED",
            message="数据集版本未解析完成",
            field="dataset_id",
        )

    job = job_service.create_job(
        db,
        project_id=project_id,
        job_type=JobType.GENERATE_ANALYSIS_PLAN.value,
        input_data={
            "dataset_id": dataset_id,
            "dataset_version_id": latest_version.id,
        },
    )

    _add_change(db, project_id,
                AnalysisChangeType.ANALYSIS_PLAN_GENERATED.value,
                f"触发分析方案生成：{dataset.title}")
    db.commit()
    return job.id


# --- 查询 ---


def list_analysis_plans(
    db: Session,
    project_id: str,
    dataset_id: str | None = None,
    status: str | None = None,
) -> list[AnalysisPlan]:
    """按条件筛选分析方案列表，按创建时间降序。"""
    _ensure_project(db, project_id)
    query = db.query(AnalysisPlan).filter(AnalysisPlan.project_id == project_id)
    if dataset_id:
        query = query.filter(AnalysisPlan.dataset_id == dataset_id)
    if status:
        query = query.filter(AnalysisPlan.status == status)
    return query.order_by(AnalysisPlan.created_at.desc()).all()


def get_analysis_plan(db: Session, plan_id: str) -> AnalysisPlan:
    """查询单个方案，不存在时抛出 ANALYSIS_PLAN_NOT_FOUND。"""
    p = db.query(AnalysisPlan).filter(AnalysisPlan.id == plan_id).first()
    if not p:
        raise AppError(code="ANALYSIS_PLAN_NOT_FOUND",
                       message=f"未找到分析方案 {plan_id}")
    return p


def get_analysis_plan_by_project(db: Session, project_id: str,
                                  plan_id: str) -> AnalysisPlan:
    """查询方案并校验归属，不匹配时抛出 ANALYSIS_PLAN_NOT_FOUND。"""
    p = (
        db.query(AnalysisPlan)
        .filter(
            AnalysisPlan.id == plan_id,
            AnalysisPlan.project_id == project_id,
        )
        .first()
    )
    if not p:
        raise AppError(code="ANALYSIS_PLAN_NOT_FOUND",
                       message=f"未找到分析方案 {plan_id}")
    return p


# --- 编辑、确认、拒绝 ---


def update_analysis_plan(
    db: Session,
    project_id: str,
    plan_id: str,
    req: UpdateAnalysisPlanRequest,
) -> AnalysisPlan:
    """更新分析方案。

    - CANDIDATE 或 STALE 可编辑
    - CONFIRMED 编辑后回到 CANDIDATE
    - REJECTED 不可编辑（需重新生成）
    """
    plan = get_analysis_plan_by_project(db, project_id, plan_id)

    if plan.status not in (
        AnalysisPlanStatus.CANDIDATE.value,
        AnalysisPlanStatus.STALE.value,
        AnalysisPlanStatus.CONFIRMED.value,
    ):
        raise AppError(
            code="ANALYSIS_PLAN_NOT_EDITABLE",
            message="只能修改候选或过期方案",
        )

    if req.cleaning_plan is not None:
        plan.cleaning_plan = req.cleaning_plan
    if req.analysis_plan is not None:
        plan.analysis_plan = req.analysis_plan
    if req.chart_plan is not None:
        plan.chart_plan = req.chart_plan

    # CONFIRMED 编辑后回到 CANDIDATE
    was_confirmed = plan.status == AnalysisPlanStatus.CONFIRMED.value
    plan.status = AnalysisPlanStatus.CANDIDATE.value
    plan.updated_at = _now()
    if was_confirmed:
        # 已确认方案编辑后清除确认时间
        plan.confirmed_at = None

    _add_change(db, project_id,
                AnalysisChangeType.ANALYSIS_PLAN_UPDATED.value,
                f"更新分析方案：{plan.id}")
    db.commit()
    db.refresh(plan)
    return plan


def confirm_analysis_plan(db: Session, project_id: str,
                            plan_id: str) -> AnalysisPlan:
    """确认候选方案，状态变为 CONFIRMED。

    STALE 传播：重新确认时，关联的 CodeTask 全部变 STALE。
    首次确认时无 CodeTask，传播为空操作。
    """
    plan = get_analysis_plan_by_project(db, project_id, plan_id)
    if plan.status != AnalysisPlanStatus.CANDIDATE.value:
        raise AppError(
            code="ANALYSIS_PLAN_NOT_CONFIRMABLE",
            message="只能确认候选方案",
        )
    plan.status = AnalysisPlanStatus.CONFIRMED.value
    plan.confirmed_at = _now()
    plan.updated_at = _now()

    # STALE 传播：重新确认时，关联的 CodeTask 全部变 STALE
    # 延迟导入避免循环依赖（execution.service 依赖 analysis.service）
    from app.modules.execution import service as execution_service
    stale_count = execution_service.mark_code_tasks_stale(db, plan_id)

    _add_change(db, project_id,
                AnalysisChangeType.ANALYSIS_PLAN_CONFIRMED.value,
                f"确认分析方案：{plan.id}"
                + (f"（{stale_count} 个代码任务变 STALE）" if stale_count else ""))
    db.commit()
    db.refresh(plan)
    return plan


def reject_analysis_plan(db: Session, project_id: str,
                           plan_id: str) -> AnalysisPlan:
    """拒绝候选方案，状态变为 REJECTED。"""
    plan = get_analysis_plan_by_project(db, project_id, plan_id)
    if plan.status != AnalysisPlanStatus.CANDIDATE.value:
        raise AppError(
            code="ANALYSIS_PLAN_NOT_CONFIRMABLE",
            message="只能拒绝候选方案",
        )
    plan.status = AnalysisPlanStatus.REJECTED.value
    plan.updated_at = _now()
    _add_change(db, project_id,
                AnalysisChangeType.ANALYSIS_PLAN_REJECTED.value,
                f"拒绝分析方案：{plan.id}")
    db.commit()
    db.refresh(plan)
    return plan


# --- 完成分析确认 ---


def complete_analysis(db: Session, project_id: str):
    """推进 project.status 到 ANALYSIS_CONFIRMED。

    前置条件：至少一个 AnalysisPlan.status=CONFIRMED。
    """
    project = _ensure_project(db, project_id)

    confirmed_count = (
        db.query(AnalysisPlan)
        .filter(
            AnalysisPlan.project_id == project_id,
            AnalysisPlan.status == AnalysisPlanStatus.CONFIRMED.value,
        )
        .count()
    )
    if confirmed_count == 0:
        raise AppError(
            code="PROJECT_NO_CONFIRMED_ANALYSIS_PLAN",
            message="没有已确认的分析方案，无法完成分析确认",
        )

    project.status = ProjectStatus.ANALYSIS_CONFIRMED.value
    _add_change(db, project_id,
                AnalysisChangeType.ANALYSIS_COMPLETED.value,
                f"完成分析方案确认（已确认方案 {confirmed_count} 个）")
    db.commit()
    db.refresh(project)
    return project


# --- Worker 调用的内部方法 ---


def save_analysis_plan_draft(
    db: Session,
    project_id: str,
    dataset_id: str,
    dataset_version_id: str,
    draft,
    candidate_source: str,
) -> AnalysisPlan:
    """保存分析方案候选，status=CANDIDATE。不提交事务。

    draft 是 AnalysisPlanDraft（来自 analysis_plan_provider）。
    若该 dataset_version 已有候选方案，先标记为 STALE 再创建新候选。
    """
    # 旧候选变 STALE（避免一个版本累积过多候选）
    existing = (
        db.query(AnalysisPlan)
        .filter(
            AnalysisPlan.dataset_version_id == dataset_version_id,
            AnalysisPlan.status == AnalysisPlanStatus.CANDIDATE.value,
        )
        .all()
    )
    for old in existing:
        old.status = AnalysisPlanStatus.STALE.value
        old.updated_at = _now()

    now = _now()
    plan = AnalysisPlan(
        id=_uid(),
        project_id=project_id,
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
        cleaning_plan=json.dumps(draft.cleaning_plan, ensure_ascii=False),
        analysis_plan=json.dumps(draft.analysis_plan, ensure_ascii=False),
        chart_plan=json.dumps(draft.chart_plan, ensure_ascii=False),
        status=AnalysisPlanStatus.CANDIDATE.value,
        candidate_source=candidate_source,
        created_at=now,
        updated_at=now,
    )
    db.add(plan)

    _add_change(db, project_id,
                AnalysisChangeType.ANALYSIS_PLAN_GENERATED.value,
                f"生成分析方案候选：{dataset_id}")
    db.flush()
    return plan


def advance_project_to_planned(db: Session, project_id: str):
    """推进 project.status 到 ANALYSIS_PLANNED（如尚未到达）。不提交事务。

    Worker 生成方案后调用。
    """
    project = _ensure_project(db, project_id)
    if project.status == ProjectStatus.DATASET_READY.value:
        project.status = ProjectStatus.ANALYSIS_PLANNED.value
    db.flush()
    return project
