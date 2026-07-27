"""执行核心服务。

拥有代码任务候选生成、用户确认、受控执行触发、结果保存、STALE 传播、
项目状态推进的业务语义。

API、Worker 只能调用本服务，不能直接修改执行状态或绕过 STALE 传播。

状态机：
- CodeTask: CANDIDATE → CONFIRMED / REJECTED；CONFIRMED 编辑回到 CANDIDATE；
  AnalysisPlan 重新确认时关联 CodeTask 变 STALE
- ExecutionRun: PENDING → RUNNING → SUCCEEDED / FAILED；CodeTask 编辑后变 STALE
- Project: ANALYSIS_CONFIRMED → EXECUTING → RESULT_CONFIRMED（失败 EXECUTION_FAILED，可重试）

STALE 传播链：
- AnalysisPlan 重新确认 → CodeTask STALE
- CodeTask 编辑 → ExecutionRun STALE

失败状态不被覆盖为成功：用户必须重新执行才能获得新的 ExecutionRun。
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.modules.analysis import service as analysis_service
from app.modules.analysis.status import AnalysisPlanStatus
from app.modules.execution.contracts import (
    CodeTaskListResponse,
    CodeTaskResponse,
    CompleteExecutionResponse,
    ExecutionArtifactResponse,
    ExecutionRunListResponse,
    ExecutionRunResponse,
    UpdateCodeTaskRequest,
)
from app.modules.execution.models import (
    CodeTask,
    ExecutionArtifact,
    ExecutionRun,
    _now,
    _uid,
)
from app.modules.execution.status import (
    CodeChangeType,
    CodeTaskStatus,
    ExecutionArtifactType,
    ExecutionChangeType,
    ExecutionRunStatus,
)
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


def _ensure_project_ready_for_execution(project) -> None:
    """校验项目状态达到 ANALYSIS_CONFIRMED 或之后（允许 EXECUTING/EXECUTION_FAILED 重试）。"""
    allowed = [
        ProjectStatus.ANALYSIS_CONFIRMED.value,
        ProjectStatus.EXECUTING.value,
        ProjectStatus.EXECUTION_FAILED.value,
        ProjectStatus.RESULT_CONFIRMED.value,
        ProjectStatus.OUTLINE_CONFIRMED.value,
        ProjectStatus.GENERATING.value,
        ProjectStatus.COMPLETED.value,
    ]
    if project.status not in allowed:
        raise AppError(
            code="PROJECT_ANALYSIS_NOT_CONFIRMED",
            message="项目分析方案未确认，无法生成代码任务",
        )


# --- 响应转换 ---


def _task_to_response(t: CodeTask) -> CodeTaskResponse:
    return CodeTaskResponse(
        id=t.id,
        project_id=t.project_id,
        analysis_plan_id=t.analysis_plan_id,
        dataset_id=t.dataset_id,
        dataset_version_id=t.dataset_version_id,
        code=t.code,
        code_version=t.code_version,
        status=t.status,
        candidate_source=t.candidate_source,
        created_at=t.created_at.isoformat(),
        updated_at=t.updated_at.isoformat() if t.updated_at else None,
        confirmed_at=t.confirmed_at.isoformat() if t.confirmed_at else None,
    )


def _task_list_to_response(tasks: list[CodeTask]) -> CodeTaskListResponse:
    return CodeTaskListResponse(items=[_task_to_response(t) for t in tasks])


def _artifact_to_response(a: ExecutionArtifact) -> ExecutionArtifactResponse:
    return ExecutionArtifactResponse(
        id=a.id,
        execution_run_id=a.execution_run_id,
        artifact_type=a.artifact_type,
        file_path=a.file_path,
        file_size_bytes=a.file_size_bytes,
        name=a.name,
        created_at=a.created_at.isoformat(),
    )


def _run_to_response(r: ExecutionRun,
                     artifacts: list[ExecutionArtifact] | None = None) -> ExecutionRunResponse:
    artifact_list = artifacts if artifacts is not None else []
    return ExecutionRunResponse(
        id=r.id,
        project_id=r.project_id,
        code_task_id=r.code_task_id,
        dataset_version_id=r.dataset_version_id,
        code_version=r.code_version,
        status=r.status,
        stdout=r.stdout,
        stderr=r.stderr,
        exit_code=r.exit_code,
        started_at=r.started_at.isoformat() if r.started_at else None,
        finished_at=r.finished_at.isoformat() if r.finished_at else None,
        duration_seconds=r.duration_seconds,
        error_code=r.error_code,
        error_message=r.error_message,
        created_at=r.created_at.isoformat(),
        artifacts=[_artifact_to_response(a) for a in artifact_list],
    )


def _run_list_to_response(
    runs: list[tuple[ExecutionRun, list[ExecutionArtifact]]]) -> ExecutionRunListResponse:
    return ExecutionRunListResponse(
        items=[_run_to_response(r, arts) for r, arts in runs]
    )


# --- 对外暴露的响应转换 ---


def task_to_response(t: CodeTask) -> CodeTaskResponse:
    return _task_to_response(t)


def task_list_to_response(tasks: list[CodeTask]) -> CodeTaskListResponse:
    return _task_list_to_response(tasks)


def run_to_response(r: ExecutionRun,
                    artifacts: list[ExecutionArtifact] | None = None) -> ExecutionRunResponse:
    return _run_to_response(r, artifacts)


def run_list_to_response(
    runs: list[tuple[ExecutionRun, list[ExecutionArtifact]]]) -> ExecutionRunListResponse:
    return _run_list_to_response(runs)


def complete_execution_to_response(project) -> CompleteExecutionResponse:
    return CompleteExecutionResponse(status=project.status)


# --- 代码任务生成 ---


def generate_code_task(
    db: Session,
    project_id: str,
    analysis_plan_id: str,
) -> str:
    """触发生成代码候选，返回 job_id。

    前置条件：
    - project.status >= ANALYSIS_CONFIRMED
    - analysis_plan.status == CONFIRMED
    """
    project = _ensure_project(db, project_id)
    _ensure_project_ready_for_execution(project)

    plan = analysis_service.get_analysis_plan_by_project(db, project_id, analysis_plan_id)
    if plan.status != AnalysisPlanStatus.CONFIRMED.value:
        raise AppError(
            code="ANALYSIS_PLAN_NOT_CONFIRMED",
            message="分析方案未确认，无法生成代码任务",
            field="analysis_plan_id",
        )

    job = job_service.create_job(
        db,
        project_id=project_id,
        job_type=JobType.GENERATE_CODE_TASK.value,
        input_data={
            "analysis_plan_id": analysis_plan_id,
            "dataset_id": plan.dataset_id,
            "dataset_version_id": plan.dataset_version_id,
        },
    )

    _add_change(db, project_id,
                CodeChangeType.CODE_TASK_GENERATED.value,
                f"触发代码任务生成：分析方案 {analysis_plan_id}")
    db.commit()
    return job.id


# --- 查询：CodeTask ---


def list_code_tasks(
    db: Session,
    project_id: str,
    status: str | None = None,
) -> list[CodeTask]:
    """按条件筛选代码任务列表，按创建时间降序。"""
    _ensure_project(db, project_id)
    query = db.query(CodeTask).filter(CodeTask.project_id == project_id)
    if status:
        query = query.filter(CodeTask.status == status)
    return query.order_by(CodeTask.created_at.desc()).all()


def get_code_task(db: Session, task_id: str) -> CodeTask:
    """查询单个代码任务，不存在时抛出 CODE_TASK_NOT_FOUND。"""
    t = db.query(CodeTask).filter(CodeTask.id == task_id).first()
    if not t:
        raise AppError(code="CODE_TASK_NOT_FOUND",
                       message=f"未找到代码任务 {task_id}")
    return t


def get_code_task_by_project(db: Session, project_id: str,
                              task_id: str) -> CodeTask:
    """查询代码任务并校验归属，不匹配时抛出 CODE_TASK_NOT_FOUND。"""
    t = (
        db.query(CodeTask)
        .filter(
            CodeTask.id == task_id,
            CodeTask.project_id == project_id,
        )
        .first()
    )
    if not t:
        raise AppError(code="CODE_TASK_NOT_FOUND",
                       message=f"未找到代码任务 {task_id}")
    return t


# --- 编辑、确认、拒绝 ---


def update_code_task(
    db: Session,
    project_id: str,
    task_id: str,
    req: UpdateCodeTaskRequest,
) -> CodeTask:
    """编辑代码任务。

    - CANDIDATE 或 CONFIRMED 可编辑
    - CONFIRMED 编辑后回到 CANDIDATE
    - STALE / REJECTED 不可编辑（需重新生成）
    - 编辑后 code_version 递增，关联 ExecutionRun 全部变 STALE
    """
    task = get_code_task_by_project(db, project_id, task_id)

    if task.status not in (
        CodeTaskStatus.CANDIDATE.value,
        CodeTaskStatus.CONFIRMED.value,
    ):
        raise AppError(
            code="CODE_TASK_NOT_EDITABLE",
            message="只能修改候选或已确认代码（STALE/REJECTED 不可编辑，需重新生成）",
        )

    was_confirmed = task.status == CodeTaskStatus.CONFIRMED.value
    task.code = req.code
    task.code_version += 1
    task.status = CodeTaskStatus.CANDIDATE.value
    task.updated_at = _now()
    if was_confirmed:
        task.confirmed_at = None

    # STALE 传播：关联 ExecutionRun 全部变 STALE
    stale_count = _mark_execution_runs_stale(db, task_id)

    _add_change(db, project_id,
                CodeChangeType.CODE_TASK_UPDATED.value,
                f"更新代码任务：{task_id}（版本 {task.code_version}，{stale_count} 个执行记录变 STALE）")
    db.commit()
    db.refresh(task)
    return task


def confirm_code_task(db: Session, project_id: str,
                       task_id: str) -> CodeTask:
    """确认候选代码，状态变为 CONFIRMED。"""
    task = get_code_task_by_project(db, project_id, task_id)
    if task.status != CodeTaskStatus.CANDIDATE.value:
        raise AppError(
            code="CODE_TASK_NOT_CONFIRMABLE",
            message="只能确认候选代码",
        )
    task.status = CodeTaskStatus.CONFIRMED.value
    task.confirmed_at = _now()
    task.updated_at = _now()
    _add_change(db, project_id,
                CodeChangeType.CODE_TASK_CONFIRMED.value,
                f"确认代码任务：{task_id}")
    db.commit()
    db.refresh(task)
    return task


def reject_code_task(db: Session, project_id: str,
                      task_id: str) -> CodeTask:
    """拒绝候选代码，状态变为 REJECTED。必须重新生成。"""
    task = get_code_task_by_project(db, project_id, task_id)
    if task.status != CodeTaskStatus.CANDIDATE.value:
        raise AppError(
            code="CODE_TASK_NOT_CONFIRMABLE",
            message="只能拒绝候选代码",
        )
    task.status = CodeTaskStatus.REJECTED.value
    task.updated_at = _now()
    _add_change(db, project_id,
                CodeChangeType.CODE_TASK_REJECTED.value,
                f"拒绝代码任务：{task_id}")
    db.commit()
    db.refresh(task)
    return task


# --- 执行触发 ---


def execute_code_task(
    db: Session,
    project_id: str,
    task_id: str,
) -> str:
    """触发执行已确认代码，返回 job_id。

    前置条件：task.status == CONFIRMED。
    """
    task = get_code_task_by_project(db, project_id, task_id)
    if task.status != CodeTaskStatus.CONFIRMED.value:
        raise AppError(
            code="CODE_TASK_NOT_EXECUTABLE",
            message="只能执行已确认代码",
        )

    # STALE 传播：重新执行 → 关联 Outline 变 STALE
    from app.modules.outlines import service as outline_service
    outline_service.mark_outlines_stale(db, project_id)

    job = job_service.create_job(
        db,
        project_id=project_id,
        job_type=JobType.EXECUTE_CODE_TASK.value,
        input_data={
            "code_task_id": task_id,
            "dataset_version_id": task.dataset_version_id,
            "code_version": task.code_version,
        },
    )

    _add_change(db, project_id,
                CodeChangeType.CODE_TASK_EXECUTED.value,
                f"触发代码执行：任务 {task_id} 版本 {task.code_version}")
    db.commit()
    return job.id


# --- 查询：ExecutionRun ---


def list_execution_runs(
    db: Session,
    project_id: str,
    status: str | None = None,
) -> list[tuple[ExecutionRun, list[ExecutionArtifact]]]:
    """按条件筛选执行记录列表，按创建时间降序。

    返回 (run, artifacts) 元组列表，artifacts 按 name 排序。
    """
    _ensure_project(db, project_id)
    query = db.query(ExecutionRun).filter(ExecutionRun.project_id == project_id)
    if status:
        query = query.filter(ExecutionRun.status == status)
    runs = query.order_by(ExecutionRun.created_at.desc()).all()

    result: list[tuple[ExecutionRun, list[ExecutionArtifact]]] = []
    for run in runs:
        arts = (
            db.query(ExecutionArtifact)
            .filter(ExecutionArtifact.execution_run_id == run.id)
            .order_by(ExecutionArtifact.name)
            .all()
        )
        result.append((run, arts))
    return result


def get_execution_run(db: Session, run_id: str) -> ExecutionRun:
    """查询单个执行记录，不存在时抛出 EXECUTION_RUN_NOT_FOUND。"""
    r = db.query(ExecutionRun).filter(ExecutionRun.id == run_id).first()
    if not r:
        raise AppError(code="EXECUTION_RUN_NOT_FOUND",
                       message=f"未找到执行记录 {run_id}")
    return r


def get_execution_run_by_project(db: Session, project_id: str,
                                   run_id: str) -> tuple[ExecutionRun, list[ExecutionArtifact]]:
    """查询执行记录并校验归属，返回 (run, artifacts)。"""
    r = (
        db.query(ExecutionRun)
        .filter(
            ExecutionRun.id == run_id,
            ExecutionRun.project_id == project_id,
        )
        .first()
    )
    if not r:
        raise AppError(code="EXECUTION_RUN_NOT_FOUND",
                       message=f"未找到执行记录 {run_id}")
    arts = (
        db.query(ExecutionArtifact)
        .filter(ExecutionArtifact.execution_run_id == run_id)
        .order_by(ExecutionArtifact.name)
        .all()
    )
    return r, arts


def get_artifact_file_path(db: Session, project_id: str, run_id: str,
                            artifact_id: str) -> tuple[Path, str, str]:
    """返回产物下载信息：(绝对路径, 文件名, media_type)。

    校验：
    - ExecutionRun 存在且归属 project_id
    - ExecutionArtifact 存在且归属 run_id
    - 拼接后路径不越界（防穿越）

    绝对路径 = project_data_root / project_id / "executions" / run_id / file_path
    """
    run = (
        db.query(ExecutionRun)
        .filter(
            ExecutionRun.id == run_id,
            ExecutionRun.project_id == project_id,
        )
        .first()
    )
    if not run:
        raise AppError(code="EXECUTION_RUN_NOT_FOUND",
                       message=f"未找到执行记录 {run_id}")

    art = (
        db.query(ExecutionArtifact)
        .filter(
            ExecutionArtifact.id == artifact_id,
            ExecutionArtifact.execution_run_id == run_id,
        )
        .first()
    )
    if not art:
        raise AppError(code="EXECUTION_ARTIFACT_NOT_FOUND",
                       message=f"未找到执行产物 {artifact_id}")

    base_dir = settings.project_data_root / project_id / "executions" / run_id
    abs_path = (base_dir / art.file_path).resolve()
    base_resolved = base_dir.resolve()
    if not str(abs_path).startswith(str(base_resolved)):
        raise AppError(code="EXECUTION_ARTIFACT_NOT_FOUND",
                       message="产物路径无效")

    media_type = "image/png" if art.name.lower().endswith(".png") else "text/csv"
    return abs_path, art.name, media_type


# --- 完成结果确认 ---


def complete_execution(db: Session, project_id: str):
    """推进 project.status 到 RESULT_CONFIRMED。

    前置条件：至少一个 ExecutionRun.status == SUCCEEDED。
    """
    project = _ensure_project(db, project_id)

    succeeded_count = (
        db.query(ExecutionRun)
        .filter(
            ExecutionRun.project_id == project_id,
            ExecutionRun.status == ExecutionRunStatus.SUCCEEDED.value,
        )
        .count()
    )
    if succeeded_count == 0:
        raise AppError(
            code="PROJECT_NO_SUCCESSFUL_EXECUTION_RUN",
            message="没有成功的执行记录，无法完成结果确认",
        )

    project.status = ProjectStatus.RESULT_CONFIRMED.value
    _add_change(db, project_id,
                ExecutionChangeType.EXECUTIONS_COMPLETED.value,
                f"完成执行结果确认（成功执行 {succeeded_count} 个）")
    db.commit()
    db.refresh(project)
    return project


# --- STALE 传播 ---


def _mark_code_tasks_stale(db: Session, analysis_plan_id: str) -> int:
    """将关联 AnalysisPlan 的 CodeTask 全部标记为 STALE。

    幂等：已是 STALE 的保持 STALE，不重复标记。
    返回被标记的记录数。
    """
    tasks = (
        db.query(CodeTask)
        .filter(
            CodeTask.analysis_plan_id == analysis_plan_id,
            CodeTask.status != CodeTaskStatus.STALE.value,
        )
        .all()
    )
    count = 0
    for task in tasks:
        task.status = CodeTaskStatus.STALE.value
        task.updated_at = _now()
        count += 1
    return count


def _mark_execution_runs_stale(db: Session, code_task_id: str) -> int:
    """将关联 CodeTask 的 ExecutionRun 全部标记为 STALE。

    幂等：已是 STALE 的保持 STALE，不重复标记。
    返回被标记的记录数。
    """
    runs = (
        db.query(ExecutionRun)
        .filter(
            ExecutionRun.code_task_id == code_task_id,
            ExecutionRun.status != ExecutionRunStatus.STALE.value,
        )
        .all()
    )
    count = 0
    for run in runs:
        run.status = ExecutionRunStatus.STALE.value
        count += 1
    return count


def mark_code_tasks_stale(db: Session, analysis_plan_id: str) -> int:
    """对外暴露的 STALE 传播方法（供 analysis 模块调用）。"""
    return _mark_code_tasks_stale(db, analysis_plan_id)


# --- Worker 调用的内部方法 ---


def save_code_task_draft(
    db: Session,
    project_id: str,
    analysis_plan_id: str,
    dataset_id: str,
    dataset_version_id: str,
    code: str,
    candidate_source: str,
) -> CodeTask:
    """保存代码任务候选，status=CANDIDATE。不提交事务。

    若该 analysis_plan 已有候选代码任务，先标记为 STALE 再创建新候选。
    """
    # 旧候选变 STALE
    existing = (
        db.query(CodeTask)
        .filter(
            CodeTask.analysis_plan_id == analysis_plan_id,
            CodeTask.status == CodeTaskStatus.CANDIDATE.value,
        )
        .all()
    )
    for old in existing:
        old.status = CodeTaskStatus.STALE.value
        old.updated_at = _now()

    now = _now()
    task = CodeTask(
        id=_uid(),
        project_id=project_id,
        analysis_plan_id=analysis_plan_id,
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
        code=code,
        code_version=1,
        status=CodeTaskStatus.CANDIDATE.value,
        candidate_source=candidate_source,
        created_at=now,
        updated_at=now,
    )
    db.add(task)

    _add_change(db, project_id,
                CodeChangeType.CODE_TASK_GENERATED.value,
                f"生成代码任务候选：分析方案 {analysis_plan_id}")
    db.flush()
    return task


def create_execution_run(
    db: Session,
    project_id: str,
    code_task_id: str,
    dataset_version_id: str,
    code_version: int,
) -> ExecutionRun:
    """创建执行记录，status=PENDING。不提交事务。"""
    now = _now()
    run = ExecutionRun(
        id=_uid(),
        project_id=project_id,
        code_task_id=code_task_id,
        dataset_version_id=dataset_version_id,
        code_version=code_version,
        status=ExecutionRunStatus.PENDING.value,
        stdout="",
        stderr="",
        created_at=now,
    )
    db.add(run)

    _add_change(db, project_id,
                ExecutionChangeType.EXECUTION_STARTED.value,
                f"创建执行记录：代码任务 {code_task_id} 版本 {code_version}")
    db.flush()
    return run


# --- 代码任务流式生成（SPEC 0022） ---


from dataclasses import dataclass
from typing import Generator


@dataclass
class StreamCodeTaskChunkEvent:
    """流式 chunk 事件，携带 LLM 返回的文本片段。"""

    text: str


@dataclass
class StreamCodeTaskDoneEvent:
    """流式完成事件，携带保存结果摘要。"""

    code_task_id: str
    candidate_source: str
    fallback_used: bool


@dataclass
class StreamCodeTaskErrorEvent:
    """流式错误事件，携带已生成的 partial_text 供前端展示。"""

    error_code: str
    message: str
    partial_text: str


StreamCodeTaskEvent = (
    StreamCodeTaskChunkEvent
    | StreamCodeTaskDoneEvent
    | StreamCodeTaskErrorEvent
)


# 并发保护：同一 AnalysisPlan 同一时刻只允许一个活动流式请求（SPEC 0022 §3.7）
active_streams: dict[str, str] = {}


def stream_generate_code_task(
    db: Session,
    request,
    project_id: str,
    plan_id: str,
    provider,
) -> Generator[StreamCodeTaskEvent, None, None]:
    """流式生成代码任务。

    SPEC 0022 代码任务生成流式化。

    流程（分段持有 db session，避免 SQLite 写锁阻塞，复用 SPEC 0019/0020/0021 模式）：
    1. Phase 1 校验（持有 db）：校验 project 状态 + AnalysisPlan CONFIRMED + 取分析方案内容 + 记录版本号
    2. Phase 2 流式生成（关闭 db，不持有连接）：调用 provider.stream_generate()
       检测 request.is_disconnected() 实现服务端取消语义
    3. Phase 3 JSON 校验：用 DeepSeekCodeTaskResponse 校验完整 JSON
    4. Phase 4 保存（重新打开 db2）：Phase 3 状态复核 + save_code_task_draft + 写变更记录

    中途失败：yield StreamCodeTaskErrorEvent（保留 partial_text），不保存 CodeTask。
    客户端断开：不保存 CodeTask，不推送 done/error。
    兼容不支持 stream_generate 的 provider：调用 generate() 一次性 yield。

    yield StreamCodeTaskEvent：StreamCodeTaskChunkEvent / StreamCodeTaskDoneEvent / StreamCodeTaskErrorEvent。
    """
    # Phase 1: 校验（持有 db）
    project = _ensure_project(db, project_id)
    _ensure_project_ready_for_execution(project)

    plan = analysis_service.get_analysis_plan_by_project(db, project_id, plan_id)
    if plan.status != AnalysisPlanStatus.CONFIRMED.value:
        raise AppError(
            code="ANALYSIS_PLAN_NOT_CONFIRMED",
            message="分析方案未确认，无法生成代码任务",
            field="analysis_plan_id",
        )

    # 记录 AnalysisPlan 内容和版本号（用于 Phase 3 状态复核）
    dataset_id = plan.dataset_id
    dataset_version_id = plan.dataset_version_id
    plan_updated_at = plan.updated_at
    analysis_plan_dict = {
        "cleaning_plan": _parse_json_field(plan.cleaning_plan),
        "analysis_plan": _parse_json_field(plan.analysis_plan),
        "chart_plan": _parse_json_field(plan.chart_plan),
    }
    db.close()  # 显式关闭，避免流式期间持有连接

    # Phase 2: 流式生成（不持有 db）
    chunks: list[str] = []
    fallback_used = False
    try:
        if hasattr(provider, "stream_generate"):
            for chunk in provider.stream_generate(analysis_plan_dict):
                # 检测客户端断开（SPEC 0022 §3.3.1 服务端取消语义）
                if _is_disconnected(request):
                    # 客户端断开：终止流式，不保存，不推送 done/error
                    return
                chunks.append(chunk)
                yield StreamCodeTaskChunkEvent(text=chunk)
        else:
            # 兼容只支持同步的 provider
            draft = provider.generate(analysis_plan_dict)
            full_json = json.dumps({"code": draft.code}, ensure_ascii=False)
            # 拆分为多个 chunk 模拟流式
            for i in range(0, len(full_json), 50):
                if _is_disconnected(request):
                    return
                piece = full_json[i:i + 50]
                chunks.append(piece)
                yield StreamCodeTaskChunkEvent(text=piece)
    except Exception as e:
        # 流式中途失败：yield error 事件，不保存
        partial_text = "".join(chunks)
        yield StreamCodeTaskErrorEvent(
            error_code=getattr(e, "code", "CODE_TASK_STREAM_FAILED"),
            message=str(e) or e.__class__.__name__,
            partial_text=partial_text,
        )
        return

    # Phase 3: JSON 校验
    raw = "".join(chunks)
    try:
        from app.modules.llm.deepseek_code_task_provider import (
            DeepSeekCodeTaskResponse,
        )
        parsed = DeepSeekCodeTaskResponse.model_validate_json(raw)
    except Exception as e:
        yield StreamCodeTaskErrorEvent(
            error_code="CODE_TASK_JSON_PARSE_ERROR",
            message=f"代码任务 JSON 校验失败: {e}",
            partial_text=raw,
        )
        return

    # Phase 4: 保存（重新打开 db2）+ 状态复核
    from app.infrastructure.database.engine import SessionLocal
    db2 = SessionLocal()
    try:
        # Phase 3 状态复核（SPEC 0022 §3.4.1）
        # 重新校验 AnalysisPlan 状态和版本
        verify_plan = (
            db2.query(analysis_service.AnalysisPlan)
            .filter(
                analysis_service.AnalysisPlan.id == plan_id,
                analysis_service.AnalysisPlan.project_id == project_id,
            )
            .first()
        )
        if verify_plan is None:
            yield StreamCodeTaskErrorEvent(
                error_code="ANALYSIS_PLAN_NOT_FOUND",
                message="流式生成期间分析方案被删除",
                partial_text=raw,
            )
            return
        if verify_plan.status != AnalysisPlanStatus.CONFIRMED.value:
            yield StreamCodeTaskErrorEvent(
                error_code="ANALYSIS_PLAN_STATUS_CHANGED",
                message=f"流式生成期间分析方案状态变为 {verify_plan.status}",
                partial_text=raw,
            )
            return
        if verify_plan.updated_at != plan_updated_at:
            yield StreamCodeTaskErrorEvent(
                error_code="ANALYSIS_PLAN_MODIFIED",
                message="流式生成期间分析方案被修改",
                partial_text=raw,
            )
            return

        # 保存 CodeTask
        task = save_code_task_draft(
            db2,
            project_id=project_id,
            analysis_plan_id=plan_id,
            dataset_id=dataset_id,
            dataset_version_id=dataset_version_id,
            code=parsed.code,
            candidate_source=provider.source_label(),
        )
        db2.commit()

        yield StreamCodeTaskDoneEvent(
            code_task_id=task.id,
            candidate_source=provider.source_label(),
            fallback_used=fallback_used,
        )
    except Exception as e:
        yield StreamCodeTaskErrorEvent(
            error_code="CODE_TASK_SAVE_FAILED",
            message=f"代码任务保存失败: {e}",
            partial_text=raw,
        )
    finally:
        db2.close()


def _parse_json_field(field) -> list:
    """将 AnalysisPlan 的 JSON 字符串字段解析为 list。

    兼容 JSON 字符串、已解析 list、None。
    """
    if field is None:
        return []
    if isinstance(field, list):
        return field
    if isinstance(field, str):
        try:
            parsed = json.loads(field)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _is_disconnected(request) -> bool:
    """同步检查 request.is_disconnected()，兼容协程返回值。

    FastAPI 的 Request.is_disconnected() 是异步方法，返回协程对象。
    service 层是同步生成器，需要同步获取结果。
    测试中 request 通常是 MagicMock，is_disconnected() 直接返回 bool。
    """
    import inspect
    result = request.is_disconnected()
    if inspect.iscoroutine(result):
        # 协程对象，用 asyncio.run 获取结果
        import asyncio
        try:
            return asyncio.run(result)
        except Exception:
            # 在已有事件循环中或运行失败，视为未断开
            return False
    return bool(result)


def mark_execution_running(db: Session, run_id: str) -> ExecutionRun:
    """标记执行记录为 RUNNING，记录 started_at。不提交事务。

    同时推进 project.status 到 EXECUTING（如果当前是 ANALYSIS_CONFIRMED 或 EXECUTION_FAILED）。
    """
    run = db.query(ExecutionRun).filter(ExecutionRun.id == run_id).first()
    if not run:
        raise AppError(code="EXECUTION_RUN_NOT_FOUND",
                       message=f"未找到执行记录 {run_id}")
    run.status = ExecutionRunStatus.RUNNING.value
    run.started_at = _now()

    # 推进项目状态到 EXECUTING
    project = _ensure_project(db, run.project_id)
    if project.status in (
        ProjectStatus.ANALYSIS_CONFIRMED.value,
        ProjectStatus.EXECUTION_FAILED.value,
    ):
        project.status = ProjectStatus.EXECUTING.value

    db.flush()
    return run


def mark_execution_succeeded(
    db: Session,
    run_id: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    started_at: datetime,
    finished_at: datetime,
    duration_seconds: float,
    artifacts: list[dict] | None = None,
) -> ExecutionRun:
    """标记执行记录为 SUCCEEDED，保存产物。不提交事务。"""
    run = db.query(ExecutionRun).filter(ExecutionRun.id == run_id).first()
    if not run:
        raise AppError(code="EXECUTION_RUN_NOT_FOUND",
                       message=f"未找到执行记录 {run_id}")

    run.status = ExecutionRunStatus.SUCCEEDED.value
    run.stdout = stdout
    run.stderr = stderr
    run.exit_code = exit_code
    run.started_at = started_at
    run.finished_at = finished_at
    run.duration_seconds = duration_seconds
    run.error_code = None
    run.error_message = None

    # 保存产物
    if artifacts:
        _save_artifacts(db, run, artifacts)

    _add_change(db, run.project_id,
                ExecutionChangeType.EXECUTION_SUCCEEDED.value,
                f"执行成功：记录 {run_id}（exit_code={exit_code}）")
    db.flush()
    return run


def mark_execution_failed(
    db: Session,
    run_id: str,
    stdout: str,
    stderr: str,
    exit_code: int,
    error_code: str,
    error_message: str,
    started_at: datetime | None,
    finished_at: datetime,
    duration_seconds: float,
    artifacts: list[dict] | None = None,
) -> ExecutionRun:
    """标记执行记录为 FAILED，保存产物和错误信息。不提交事务。

    同时推进 project.status 到 EXECUTION_FAILED。
    失败状态不被覆盖为成功。
    """
    run = db.query(ExecutionRun).filter(ExecutionRun.id == run_id).first()
    if not run:
        raise AppError(code="EXECUTION_RUN_NOT_FOUND",
                       message=f"未找到执行记录 {run_id}")

    run.status = ExecutionRunStatus.FAILED.value
    run.stdout = stdout
    run.stderr = stderr
    run.exit_code = exit_code
    run.started_at = started_at
    run.finished_at = finished_at
    run.duration_seconds = duration_seconds
    run.error_code = error_code
    run.error_message = error_message

    # 保存产物（失败时仍收集已生成的产物）
    if artifacts:
        _save_artifacts(db, run, artifacts)

    # 推进项目状态到 EXECUTION_FAILED
    project = _ensure_project(db, run.project_id)
    if project.status == ProjectStatus.EXECUTING.value:
        project.status = ProjectStatus.EXECUTION_FAILED.value

    _add_change(db, run.project_id,
                ExecutionChangeType.EXECUTION_FAILED.value,
                f"执行失败：记录 {run_id}（error={error_code}）")
    db.flush()
    return run


def _save_artifacts(db: Session, run: ExecutionRun,
                    artifacts: list[dict]) -> list[ExecutionArtifact]:
    """保存产物列表。不提交事务。"""
    saved: list[ExecutionArtifact] = []
    now = _now()
    for art_info in artifacts:
        art = ExecutionArtifact(
            id=_uid(),
            execution_run_id=run.id,
            project_id=run.project_id,
            artifact_type=art_info.get("artifact_type", "TABLE_CSV"),
            file_path=art_info.get("file_path", ""),
            file_size_bytes=art_info.get("file_size_bytes", 0),
            name=art_info.get("name", "unnamed"),
            created_at=now,
        )
        db.add(art)
        saved.append(art)
    db.flush()
    return saved
