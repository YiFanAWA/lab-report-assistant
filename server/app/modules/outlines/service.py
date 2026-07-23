"""大纲与交付物核心服务。

拥有大纲生成、用户确认、编辑、失效传播和 Word/PPT 生成请求的业务语义。

API、Worker 只能调用本服务，不能直接修改大纲状态或绕过 STALE 传播。

状态机：
- Outline: CANDIDATE → CONFIRMED / REJECTED；CONFIRMED 编辑回到 CANDIDATE（version 递增）；
  ExecutionRun 重新执行时关联 Outline 变 STALE
- Deliverable: PENDING → RUNNING → SUCCEEDED / FAILED；
  Outline 编辑或重新确认时关联 Deliverable 变 STALE
- DeliverableVersion: PENDING → RUNNING → SUCCEEDED / FAILED；
  失败状态不被覆盖为成功

STALE 传播链：
- ExecutionRun 重新执行 → Outline STALE
- Outline 编辑 → Deliverable STALE
- Outline 重新确认 → 旧 Deliverable STALE

项目状态推进：
- RESULT_CONFIRMED → 生成大纲候选（保持 RESULT_CONFIRMED）
- 确认大纲 → OUTLINE_CONFIRMED
- 触发 Word/PPT 生成 → GENERATING
- 生成完成 → COMPLETED（需至少一个 Word 和一个 PPT 成功）
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.modules.outlines.contracts import (
    CompleteProjectResponse,
    DeliverableListResponse,
    DeliverableResponse,
    DeliverableVersionListResponse,
    DeliverableVersionResponse,
    GenerateDeliverableResponse,
    GenerateOutlineResponse,
    OutlineListResponse,
    OutlineResponse,
    OutlineSection,
    PPT_THEME_COLORS,
    UpdateOutlineRequest,
)
from app.modules.outlines.models import (
    Deliverable,
    DeliverableVersion,
    Outline,
    WordTemplate,
    _now,
    _uid,
)
from app.modules.outlines.status import (
    DeliverableChangeType,
    DeliverableStatus,
    DeliverableType,
    DeliverableVersionStatus,
    OutlineChangeType,
    OutlineStatus,
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


def _ensure_project_ready_for_outline(project) -> None:
    """校验项目状态达到 RESULT_CONFIRMED 或之后（允许重新生成）。"""
    allowed = [
        ProjectStatus.RESULT_CONFIRMED.value,
        ProjectStatus.OUTLINE_CONFIRMED.value,
        ProjectStatus.GENERATING.value,
        ProjectStatus.COMPLETED.value,
    ]
    if project.status not in allowed:
        raise AppError(
            code="OUTLINE_NOT_GENERATABLE",
            message="项目执行结果未确认，无法生成大纲",
        )


def _ensure_project_ready_for_deliverable(project) -> None:
    """校验项目状态达到 OUTLINE_CONFIRMED 或之后。"""
    allowed = [
        ProjectStatus.OUTLINE_CONFIRMED.value,
        ProjectStatus.GENERATING.value,
        ProjectStatus.COMPLETED.value,
    ]
    if project.status not in allowed:
        raise AppError(
            code="DELIVERABLE_NOT_GENERATABLE",
            message="项目大纲未确认，无法生成交付物",
        )


# --- 响应转换 ---


def _section_from_dict(d: dict) -> OutlineSection:
    return OutlineSection(
        id=d.get("id", ""),
        title=d.get("title", ""),
        content=d.get("content", ""),
        source_type=d.get("source_type", ""),
        source_ids=d.get("source_ids", []),
    )


def _sections_to_json(sections) -> str:
    """将 OutlineSection 列表或 dict 列表序列化为 JSON。"""
    if sections and hasattr(sections[0], "model_dump"):
        data = [s.model_dump() for s in sections]
    else:
        data = list(sections)
    return json.dumps(data, ensure_ascii=False)


def _sections_from_json(sections_json: str) -> list[OutlineSection]:
    """从 JSON 反序列化为 OutlineSection 列表。"""
    data = json.loads(sections_json)
    return [_section_from_dict(d) for d in data]


def _outline_to_response(o: Outline) -> OutlineResponse:
    sections = _sections_from_json(o.sections_json)
    return OutlineResponse(
        id=o.id,
        project_id=o.project_id,
        sections=sections,
        status=o.status,
        candidate_source=o.candidate_source,
        version=o.code_version,
        created_at=o.created_at.isoformat(),
        updated_at=o.updated_at.isoformat() if o.updated_at else None,
        confirmed_at=o.confirmed_at.isoformat() if o.confirmed_at else None,
    )


def _outline_list_to_response(outlines: list[Outline]) -> OutlineListResponse:
    return OutlineListResponse(items=[_outline_to_response(o) for o in outlines])


def _deliverable_to_response(d: Deliverable) -> DeliverableResponse:
    return DeliverableResponse(
        id=d.id,
        project_id=d.project_id,
        outline_id=d.outline_id,
        deliverable_type=d.deliverable_type,
        status=d.status,
        created_at=d.created_at.isoformat(),
        updated_at=d.updated_at.isoformat() if d.updated_at else None,
    )


def _deliverable_list_to_response(
    deliverables: list[Deliverable]) -> DeliverableListResponse:
    return DeliverableListResponse(
        items=[_deliverable_to_response(d) for d in deliverables])


def _version_to_response(v: DeliverableVersion) -> DeliverableVersionResponse:
    return DeliverableVersionResponse(
        id=v.id,
        deliverable_id=v.deliverable_id,
        version=v.version,
        status=v.status,
        file_path=v.file_path,
        file_size_bytes=v.file_size_bytes,
        error_code=v.error_code,
        error_message=v.error_message,
        started_at=v.started_at.isoformat() if v.started_at else None,
        finished_at=v.finished_at.isoformat() if v.finished_at else None,
        duration_seconds=v.duration_seconds,
        created_at=v.created_at.isoformat(),
    )


def _version_list_to_response(
    versions: list[DeliverableVersion]) -> DeliverableVersionListResponse:
    return DeliverableVersionListResponse(
        items=[_version_to_response(v) for v in versions])


# --- 对外暴露的响应转换 ---


def outline_to_response(o: Outline) -> OutlineResponse:
    return _outline_to_response(o)


def outline_list_to_response(outlines: list[Outline]) -> OutlineListResponse:
    return _outline_list_to_response(outlines)


def deliverable_to_response(d: Deliverable) -> DeliverableResponse:
    return _deliverable_to_response(d)


def deliverable_list_to_response(
    deliverables: list[Deliverable]) -> DeliverableListResponse:
    return _deliverable_list_to_response(deliverables)


def version_list_to_response(
    versions: list[DeliverableVersion]) -> DeliverableVersionListResponse:
    return _version_list_to_response(versions)


def complete_project_to_response(project) -> CompleteProjectResponse:
    return CompleteProjectResponse(status=project.status)


# --- 大纲生成触发 ---


def generate_outline(db: Session, project_id: str) -> str:
    """触发生成大纲候选，返回 job_id。

    前置条件：
    - project.status == RESULT_CONFIRMED 或之后（允许重新生成）
    - 至少一个 ExecutionRun.status == SUCCEEDED（由 Worker handler 再次校验）
    """
    project = _ensure_project(db, project_id)
    _ensure_project_ready_for_outline(project)

    job = job_service.create_job(
        db,
        project_id=project_id,
        job_type=JobType.GENERATE_OUTLINE.value,
        input_data={"project_id": project_id},
    )

    _add_change(db, project_id,
                OutlineChangeType.OUTLINE_GENERATED.value,
                f"触发大纲生成")
    db.commit()
    return job.id


# --- 查询：Outline ---


def list_outlines(
    db: Session,
    project_id: str,
    status: str | None = None,
) -> list[Outline]:
    """按条件筛选大纲列表，按创建时间降序。"""
    _ensure_project(db, project_id)
    query = db.query(Outline).filter(Outline.project_id == project_id)
    if status:
        query = query.filter(Outline.status == status)
    return query.order_by(Outline.created_at.desc()).all()


def get_outline(db: Session, outline_id: str) -> Outline:
    """查询单个大纲，不存在时抛出 OUTLINE_NOT_FOUND。"""
    o = db.query(Outline).filter(Outline.id == outline_id).first()
    if not o:
        raise AppError(code="OUTLINE_NOT_FOUND",
                       message=f"未找到大纲 {outline_id}")
    return o


def get_outline_by_project(db: Session, project_id: str,
                            outline_id: str) -> Outline:
    """查询大纲并校验归属，不匹配时抛出 OUTLINE_NOT_FOUND。"""
    o = (
        db.query(Outline)
        .filter(
            Outline.id == outline_id,
            Outline.project_id == project_id,
        )
        .first()
    )
    if not o:
        raise AppError(code="OUTLINE_NOT_FOUND",
                       message=f"未找到大纲 {outline_id}")
    return o


# --- 编辑、确认、拒绝 ---


def update_outline(
    db: Session,
    project_id: str,
    outline_id: str,
    req: UpdateOutlineRequest,
) -> Outline:
    """编辑大纲。

    - CANDIDATE 或 CONFIRMED 可编辑
    - CONFIRMED 编辑后回到 CANDIDATE，code_version 递增
    - STALE / REJECTED 不可编辑（需重新生成）
    - 编辑后关联 Deliverable 全部变 STALE
    """
    outline = get_outline_by_project(db, project_id, outline_id)

    if outline.status not in (
        OutlineStatus.CANDIDATE.value,
        OutlineStatus.CONFIRMED.value,
    ):
        raise AppError(
            code="OUTLINE_NOT_EDITABLE",
            message="只能修改候选或已确认大纲（STALE/REJECTED 不可编辑，需重新生成）",
        )

    was_confirmed = outline.status == OutlineStatus.CONFIRMED.value
    outline.sections_json = _sections_to_json(req.sections)
    outline.status = OutlineStatus.CANDIDATE.value
    outline.updated_at = _now()
    if was_confirmed:
        outline.confirmed_at = None
        outline.code_version += 1

    # STALE 传播：关联 Deliverable 全部变 STALE
    stale_count = _mark_deliverables_stale(db, outline_id)

    _add_change(db, project_id,
                OutlineChangeType.OUTLINE_UPDATED.value,
                f"更新大纲：{outline_id}（版本 {outline.code_version}，"
                f"{stale_count} 个交付物变 STALE）")
    db.commit()
    db.refresh(outline)
    return outline


def confirm_outline(db: Session, project_id: str,
                     outline_id: str) -> Outline:
    """确认候选大纲，状态变为 CONFIRMED。

    推进 project.status 到 OUTLINE_CONFIRMED。
    重新确认时，旧 Deliverable 全部变 STALE（首次确认时无 Deliverable，传播为空操作）。
    """
    outline = get_outline_by_project(db, project_id, outline_id)
    if outline.status != OutlineStatus.CANDIDATE.value:
        raise AppError(
            code="OUTLINE_NOT_CONFIRMABLE",
            message="只能确认候选大纲",
        )
    outline.status = OutlineStatus.CONFIRMED.value
    outline.confirmed_at = _now()
    outline.updated_at = _now()

    # STALE 传播：重新确认时旧 Deliverable 全部变 STALE
    stale_count = _mark_deliverables_stale(db, outline_id)

    # 推进项目状态到 OUTLINE_CONFIRMED
    project = _ensure_project(db, project_id)
    project.status = ProjectStatus.OUTLINE_CONFIRMED.value

    _add_change(db, project_id,
                OutlineChangeType.OUTLINE_CONFIRMED.value,
                f"确认大纲：{outline_id}"
                + (f"（{stale_count} 个旧交付物变 STALE）" if stale_count else ""))
    db.commit()
    db.refresh(outline)
    return outline


def reject_outline(db: Session, project_id: str,
                    outline_id: str) -> Outline:
    """拒绝候选大纲，状态变为 REJECTED。必须重新生成。"""
    outline = get_outline_by_project(db, project_id, outline_id)
    if outline.status != OutlineStatus.CANDIDATE.value:
        raise AppError(
            code="OUTLINE_NOT_CONFIRMABLE",
            message="只能拒绝候选大纲",
        )
    outline.status = OutlineStatus.REJECTED.value
    outline.updated_at = _now()
    _add_change(db, project_id,
                OutlineChangeType.OUTLINE_REJECTED.value,
                f"拒绝大纲：{outline_id}")
    db.commit()
    db.refresh(outline)
    return outline


# --- Word/PPT 生成触发 ---


def _create_or_get_deliverable(
    db: Session, project_id: str, outline_id: str,
    deliverable_type: str,
) -> Deliverable:
    """获取或创建交付物（一个 Outline + 一个 type 对应一个 Deliverable）。

    若已有非 STALE 的同类型 Deliverable，标记为 STALE（重新生成时旧版本保留）。
    """
    existing = (
        db.query(Deliverable)
        .filter(
            Deliverable.outline_id == outline_id,
            Deliverable.deliverable_type == deliverable_type,
            Deliverable.status != DeliverableStatus.STALE.value,
        )
        .first()
    )
    if existing:
        # 标记旧 Deliverable 为 STALE，保留历史版本
        existing.status = DeliverableStatus.STALE.value
        existing.updated_at = _now()

    now = _now()
    deliverable = Deliverable(
        id=_uid(),
        project_id=project_id,
        outline_id=outline_id,
        deliverable_type=deliverable_type,
        status=DeliverableStatus.PENDING.value,
        created_at=now,
        updated_at=now,
    )
    db.add(deliverable)
    db.flush()
    return deliverable


def generate_word(db: Session, project_id: str, outline_id: str) -> tuple[str, str]:
    """触发 Word 生成，返回 (job_id, deliverable_id)。

    前置条件：outline.status == CONFIRMED。
    """
    project = _ensure_project(db, project_id)
    _ensure_project_ready_for_deliverable(project)
    outline = get_outline_by_project(db, project_id, outline_id)
    if outline.status != OutlineStatus.CONFIRMED.value:
        raise AppError(
            code="DELIVERABLE_NOT_GENERATABLE",
            message="大纲未确认，无法生成 Word",
        )

    deliverable = _create_or_get_deliverable(
        db, project_id, outline_id, DeliverableType.WORD.value)

    job = job_service.create_job(
        db,
        project_id=project_id,
        job_type=JobType.GENERATE_WORD.value,
        input_data={
            "outline_id": outline_id,
            "deliverable_id": deliverable.id,
        },
    )

    _add_change(db, project_id,
                DeliverableChangeType.WORD_GENERATED.value,
                f"触发 Word 生成：大纲 {outline_id}")
    db.commit()
    return job.id, deliverable.id


def generate_ppt(
    db: Session, project_id: str, outline_id: str,
    config: dict | None = None,
) -> tuple[str, str]:
    """触发 PPT 生成，返回 (job_id, deliverable_id)。

    前置条件：outline.status == CONFIRMED。

    SPEC 0011：config 可选，含 target_slide_count/theme_color/include_charts。
    theme_color 非空时必须在预设色板内。
    """
    project = _ensure_project(db, project_id)
    _ensure_project_ready_for_deliverable(project)
    outline = get_outline_by_project(db, project_id, outline_id)
    if outline.status != OutlineStatus.CONFIRMED.value:
        raise AppError(
            code="DELIVERABLE_NOT_GENERATABLE",
            message="大纲未确认，无法生成 PPT",
        )

    # SPEC 0011：校验 PPT 配置
    if config:
        theme_color = config.get("theme_color")
        if theme_color and theme_color not in PPT_THEME_COLORS:
            raise AppError(
                code="PPT_CONFIG_INVALID_THEME_COLOR",
                message=f"主题色 {theme_color} 不在预设色板内",
            )

    deliverable = _create_or_get_deliverable(
        db, project_id, outline_id, DeliverableType.PPT.value)

    job = job_service.create_job(
        db,
        project_id=project_id,
        job_type=JobType.GENERATE_PPT.value,
        input_data={
            "outline_id": outline_id,
            "deliverable_id": deliverable.id,
            "config": config or {},
        },
    )

    _add_change(db, project_id,
                DeliverableChangeType.PPT_GENERATED.value,
                f"触发 PPT 生成：大纲 {outline_id}")
    db.commit()
    return job.id, deliverable.id


# --- 查询：Deliverable ---


def list_deliverables(
    db: Session,
    project_id: str,
    status: str | None = None,
) -> list[Deliverable]:
    """按条件筛选交付物列表，按创建时间降序。"""
    _ensure_project(db, project_id)
    query = db.query(Deliverable).filter(Deliverable.project_id == project_id)
    if status:
        query = query.filter(Deliverable.status == status)
    return query.order_by(Deliverable.created_at.desc()).all()


def get_deliverable_by_project(db: Session, project_id: str,
                                deliverable_id: str) -> Deliverable:
    """查询交付物并校验归属。"""
    d = (
        db.query(Deliverable)
        .filter(
            Deliverable.id == deliverable_id,
            Deliverable.project_id == project_id,
        )
        .first()
    )
    if not d:
        raise AppError(code="DELIVERABLE_NOT_FOUND",
                       message=f"未找到交付物 {deliverable_id}")
    return d


def list_deliverable_versions(
    db: Session, project_id: str, deliverable_id: str,
) -> list[DeliverableVersion]:
    """查询交付物版本列表，按版本号降序。"""
    get_deliverable_by_project(db, project_id, deliverable_id)
    return (
        db.query(DeliverableVersion)
        .filter(DeliverableVersion.deliverable_id == deliverable_id)
        .order_by(DeliverableVersion.version.desc())
        .all()
    )


def get_version_by_project(
    db: Session, project_id: str, deliverable_id: str, version_id: str,
) -> DeliverableVersion:
    """查询交付物版本并校验归属。"""
    get_deliverable_by_project(db, project_id, deliverable_id)
    v = (
        db.query(DeliverableVersion)
        .filter(
            DeliverableVersion.id == version_id,
            DeliverableVersion.deliverable_id == deliverable_id,
        )
        .first()
    )
    if not v:
        raise AppError(code="DELIVERABLE_VERSION_NOT_FOUND",
                       message=f"未找到交付物版本 {version_id}")
    return v


def get_deliverable_file_path(
    db: Session, project_id: str, deliverable_id: str, version_id: str,
) -> tuple[Path, str, str]:
    """返回交付物下载信息：(绝对路径, 文件名, media_type)。

    校验：
    - Deliverable 存在且归属 project_id
    - DeliverableVersion 存在且归属 deliverable_id
    - 版本状态为 SUCCEEDED
    - 拼接后路径不越界（防穿越）
    """
    deliverable = get_deliverable_by_project(db, project_id, deliverable_id)
    version = get_version_by_project(db, project_id, deliverable_id, version_id)

    if version.status != DeliverableVersionStatus.SUCCEEDED.value:
        raise AppError(
            code="DELIVERABLE_NOT_DOWNLOADABLE",
            message=f"交付物版本状态非 SUCCEEDED，无法下载",
        )

    if not version.file_path:
        raise AppError(
            code="DELIVERABLE_NOT_DOWNLOADABLE",
            message="交付物版本未关联文件",
        )

    base_dir = (settings.project_data_root / project_id
                / "deliverables" / deliverable_id)
    abs_path = (base_dir / version.file_path).resolve()
    base_resolved = base_dir.resolve()
    if not str(abs_path).startswith(str(base_resolved)):
        raise AppError(code="DELIVERABLE_NOT_DOWNLOADABLE",
                       message="交付物路径无效")

    if deliverable.deliverable_type == DeliverableType.WORD.value:
        media_type = ("application/vnd.openxmlformats-officedocument"
                      ".wordprocessingml.document")
        filename = f"word_v{version.version}.docx"
    else:
        media_type = ("application/vnd.openxmlformats-officedocument"
                      ".presentationml.presentation")
        filename = f"ppt_v{version.version}.pptx"
    return abs_path, filename, media_type


# --- 完成项目 ---


def complete_project(db: Session, project_id: str):
    """推进 project.status 到 COMPLETED。

    前置条件：至少一个 Word DeliverableVersion 和一个 PPT DeliverableVersion 为 SUCCEEDED。
    """
    project = _ensure_project(db, project_id)

    # 查询所有非 STALE 的交付物
    deliverables = (
        db.query(Deliverable)
        .filter(
            Deliverable.project_id == project_id,
            Deliverable.status != DeliverableStatus.STALE.value,
        )
        .all()
    )

    word_succeeded = False
    ppt_succeeded = False
    for d in deliverables:
        if d.deliverable_type == DeliverableType.WORD.value:
            versions = (
                db.query(DeliverableVersion)
                .filter(
                    DeliverableVersion.deliverable_id == d.id,
                    DeliverableVersion.status
                    == DeliverableVersionStatus.SUCCEEDED.value,
                )
                .count()
            )
            if versions > 0:
                word_succeeded = True
        elif d.deliverable_type == DeliverableType.PPT.value:
            versions = (
                db.query(DeliverableVersion)
                .filter(
                    DeliverableVersion.deliverable_id == d.id,
                    DeliverableVersion.status
                    == DeliverableVersionStatus.SUCCEEDED.value,
                )
                .count()
            )
            if versions > 0:
                ppt_succeeded = True

    if not (word_succeeded and ppt_succeeded):
        raise AppError(
            code="PROJECT_NO_SUCCESSFUL_DELIVERABLE",
            message="没有成功的 Word 和 PPT 交付物，无法完成项目",
        )

    project.status = ProjectStatus.COMPLETED.value
    _add_change(db, project_id,
                DeliverableChangeType.PROJECT_COMPLETED.value,
                "完成项目（Word 和 PPT 均已生成）")
    db.commit()
    db.refresh(project)
    return project


# --- STALE 传播 ---


def _mark_deliverables_stale(db: Session, outline_id: str) -> int:
    """将关联 Outline 的非 STALE Deliverable 全部标记为 STALE。

    幂等：已是 STALE 的保持 STALE，不重复标记。
    返回被标记的记录数。
    """
    deliverables = (
        db.query(Deliverable)
        .filter(
            Deliverable.outline_id == outline_id,
            Deliverable.status != DeliverableStatus.STALE.value,
        )
        .all()
    )
    count = 0
    for d in deliverables:
        d.status = DeliverableStatus.STALE.value
        d.updated_at = _now()
        count += 1
    return count


def mark_outlines_stale(db: Session, project_id: str) -> int:
    """对外暴露的 STALE 传播方法（供 execution 模块调用）。

    将项目下所有非 STALE 的 Outline 标记为 STALE。
    幂等：已是 STALE 的保持 STALE。
    """
    outlines = (
        db.query(Outline)
        .filter(
            Outline.project_id == project_id,
            Outline.status != OutlineStatus.STALE.value,
        )
        .all()
    )
    count = 0
    for o in outlines:
        o.status = OutlineStatus.STALE.value
        o.updated_at = _now()
        count += 1
    return count


# --- Worker 调用的内部方法 ---


def save_outline_draft(
    db: Session,
    project_id: str,
    sections: list,
    candidate_source: str,
) -> Outline:
    """保存大纲候选，status=CANDIDATE。不提交事务。

    若该项目已有候选大纲，先标记为 STALE 再创建新候选。
    """
    # 旧候选变 STALE
    existing = (
        db.query(Outline)
        .filter(
            Outline.project_id == project_id,
            Outline.status == OutlineStatus.CANDIDATE.value,
        )
        .all()
    )
    for old in existing:
        old.status = OutlineStatus.STALE.value
        old.updated_at = _now()

    now = _now()
    outline = Outline(
        id=_uid(),
        project_id=project_id,
        sections_json=_sections_to_json(sections),
        status=OutlineStatus.CANDIDATE.value,
        candidate_source=candidate_source,
        code_version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(outline)

    _add_change(db, project_id,
                OutlineChangeType.OUTLINE_GENERATED.value,
                f"生成大纲候选：{len(sections)} 个章节")
    db.flush()
    return outline


def create_deliverable_version(
    db: Session,
    project_id: str,
    deliverable_id: str,
) -> tuple[Deliverable, DeliverableVersion]:
    """创建交付物版本，status=PENDING。不提交事务。

    同时推进 Deliverable.status 到 RUNNING 和 project.status 到 GENERATING。
    """
    deliverable = (
        db.query(Deliverable)
        .filter(Deliverable.id == deliverable_id)
        .first()
    )
    if not deliverable:
        raise AppError(code="DELIVERABLE_NOT_FOUND",
                       message=f"未找到交付物 {deliverable_id}")

    # 计算新版本号
    max_version = (
        db.query(DeliverableVersion)
        .filter(DeliverableVersion.deliverable_id == deliverable_id)
        .count()
    )
    new_version = max_version + 1

    now = _now()
    version = DeliverableVersion(
        id=_uid(),
        deliverable_id=deliverable_id,
        project_id=project_id,
        version=new_version,
        status=DeliverableVersionStatus.PENDING.value,
        created_at=now,
    )
    db.add(version)

    # 推进 Deliverable 和 project 状态
    deliverable.status = DeliverableStatus.RUNNING.value
    deliverable.updated_at = now

    project = _ensure_project(db, project_id)
    if project.status == ProjectStatus.OUTLINE_CONFIRMED.value:
        project.status = ProjectStatus.GENERATING.value

    change_type = (DeliverableChangeType.WORD_GENERATED.value
                   if deliverable.deliverable_type == DeliverableType.WORD.value
                   else DeliverableChangeType.PPT_GENERATED.value)
    _add_change(db, project_id,
                change_type,
                f"开始生成交付物：{deliverable_id} 版本 {new_version}")
    db.flush()
    return deliverable, version


def mark_deliverable_version_running(
    db: Session, version_id: str,
) -> DeliverableVersion:
    """标记交付物版本为 RUNNING，记录 started_at。不提交事务。"""
    v = db.query(DeliverableVersion).filter(
        DeliverableVersion.id == version_id).first()
    if not v:
        raise AppError(code="DELIVERABLE_VERSION_NOT_FOUND",
                       message=f"未找到交付物版本 {version_id}")
    v.status = DeliverableVersionStatus.RUNNING.value
    v.started_at = _now()
    db.flush()
    return v


def mark_deliverable_version_succeeded(
    db: Session,
    version_id: str,
    file_path: str,
    file_size_bytes: int,
    started_at: datetime,
    finished_at: datetime,
    duration_seconds: float,
) -> DeliverableVersion:
    """标记交付物版本为 SUCCEEDED，保存文件路径。不提交事务。

    同时推进 Deliverable.status 到 SUCCEEDED。
    """
    v = db.query(DeliverableVersion).filter(
        DeliverableVersion.id == version_id).first()
    if not v:
        raise AppError(code="DELIVERABLE_VERSION_NOT_FOUND",
                       message=f"未找到交付物版本 {version_id}")

    v.status = DeliverableVersionStatus.SUCCEEDED.value
    v.file_path = file_path
    v.file_size_bytes = file_size_bytes
    v.started_at = started_at
    v.finished_at = finished_at
    v.duration_seconds = duration_seconds
    v.error_code = None
    v.error_message = None

    # 推进 Deliverable 到 SUCCEEDED
    deliverable = (
        db.query(Deliverable)
        .filter(Deliverable.id == v.deliverable_id)
        .first()
    )
    if deliverable:
        deliverable.status = DeliverableStatus.SUCCEEDED.value
        deliverable.updated_at = _now()

    _add_change(db, v.project_id,
                DeliverableChangeType.DELIVERABLE_SUCCEEDED.value,
                f"交付物生成成功：版本 {version_id}（{file_size_bytes} 字节）")
    db.flush()
    return v


def mark_deliverable_version_failed(
    db: Session,
    version_id: str,
    error_code: str,
    error_message: str,
    started_at: datetime | None,
    finished_at: datetime,
    duration_seconds: float,
) -> DeliverableVersion:
    """标记交付物版本为 FAILED，保存错误信息。不提交事务。

    失败状态不被覆盖为成功。
    Deliverable.status 保持 RUNNING（允许用户重新生成，会创建新版本）。
    """
    v = db.query(DeliverableVersion).filter(
        DeliverableVersion.id == version_id).first()
    if not v:
        raise AppError(code="DELIVERABLE_VERSION_NOT_FOUND",
                       message=f"未找到交付物版本 {version_id}")

    v.status = DeliverableVersionStatus.FAILED.value
    v.error_code = error_code
    v.error_message = error_message
    v.started_at = started_at
    v.finished_at = finished_at
    v.duration_seconds = duration_seconds

    # 推进 Deliverable 到 FAILED（允许重新生成）
    deliverable = (
        db.query(Deliverable)
        .filter(Deliverable.id == v.deliverable_id)
        .first()
    )
    if deliverable:
        deliverable.status = DeliverableStatus.FAILED.value
        deliverable.updated_at = _now()

    _add_change(db, v.project_id,
                DeliverableChangeType.DELIVERABLE_FAILED.value,
                f"交付物生成失败：版本 {version_id}（error={error_code}）")
    db.flush()
    return v


# --- Word 模板管理（SPEC 0010）---


import hashlib
from fastapi import UploadFile


def _word_template_to_response(t: "WordTemplate") -> "WordTemplateResponse":
    from app.modules.outlines.contracts import WordTemplateResponse
    return WordTemplateResponse(
        id=t.id,
        project_id=t.project_id,
        original_filename=t.original_filename,
        file_size_bytes=t.file_size_bytes,
        content_hash=t.content_hash,
        created_at=t.created_at.isoformat(),
        updated_at=t.updated_at.isoformat() if t.updated_at else None,
    )


def word_template_to_response(t: "WordTemplate") -> "WordTemplateResponse":
    """对外暴露的响应转换。"""
    return _word_template_to_response(t)


def get_word_template(db: Session, project_id: str) -> "WordTemplate | None":
    """查询项目的 Word 模板，不存在返回 None。"""
    _ensure_project(db, project_id)
    return (
        db.query(WordTemplate)
        .filter(WordTemplate.project_id == project_id)
        .first()
    )


def _save_word_template_file(
    project_id: str, content: bytes
) -> tuple[str, str, int]:
    """保存模板文件到受控工作区，返回 (relative_path, content_hash, file_size)。

    存储路径：{PROJECT_DATA_ROOT}/{project_id}/word_template/template.docx
    使用固定文件名，覆盖式存储。
    """
    base_dir = settings.project_data_root / project_id / "word_template"
    base_dir.mkdir(parents=True, exist_ok=True)
    file_path = base_dir / "template.docx"
    file_path.write_bytes(content)

    content_hash = hashlib.sha256(content).hexdigest()
    # 相对路径（相对 project_data_root）
    relative_path = f"{project_id}/word_template/template.docx"
    return relative_path, content_hash, len(content)


def _delete_word_template_file(project_id: str) -> None:
    """删除模板文件，幂等。"""
    base_dir = settings.project_data_root / project_id / "word_template"
    if base_dir.exists():
        import shutil
        shutil.rmtree(base_dir, ignore_errors=True)


def upload_word_template(
    db: Session,
    project_id: str,
    upload_file: UploadFile,
) -> "WordTemplate":
    """上传或替换项目的 Word 模板。

    校验：
    - 项目存在
    - 文件名后缀为 .docx
    - 文件大小不超过 word_template_max_size_bytes
    - 文件内容可被 python-docx 打开（推迟到渲染器层校验，此处仅校验大小和后缀）

    若已有模板，先删旧记录和旧文件，再写新记录和新文件。
    """
    project = _ensure_project(db, project_id)

    # 校验文件名后缀
    original_filename = upload_file.filename or "template.docx"
    if not original_filename.lower().endswith(".docx"):
        raise AppError(
            code="WORD_TEMPLATE_FILE_UNSUPPORTED",
            message="仅支持 .docx 文件",
        )

    # 读取内容
    content = upload_file.file.read()
    file_size = len(content)

    # 校验大小
    if file_size > settings.word_template_max_size_bytes:
        raise AppError(
            code="WORD_TEMPLATE_TOO_LARGE",
            message=(
                f"模板文件大小 {file_size} 字节超过上限 "
                f"{settings.word_template_max_size_bytes} 字节"
            ),
        )
    if file_size == 0:
        raise AppError(
            code="WORD_TEMPLATE_FILE_UNSUPPORTED",
            message="模板文件为空",
        )

    # 删除旧模板（如果存在）
    existing = (
        db.query(WordTemplate)
        .filter(WordTemplate.project_id == project_id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    # 保存文件
    relative_path, content_hash, saved_size = _save_word_template_file(
        project_id, content
    )

    # 创建新记录
    now = _now()
    template = WordTemplate(
        id=_uid(),
        project_id=project_id,
        file_path=relative_path,
        original_filename=original_filename,
        content_hash=content_hash,
        file_size_bytes=saved_size,
        created_at=now,
        updated_at=now,
    )
    db.add(template)

    _add_change(db, project_id,
                "WORD_TEMPLATE_UPLOADED",
                f"上传 Word 模板：{original_filename}（{saved_size} 字节）")
    db.commit()
    db.refresh(template)
    return template


def delete_word_template(db: Session, project_id: str) -> None:
    """删除项目的 Word 模板。

    删除数据库记录和文件。
    不存在时抛出 WORD_TEMPLATE_NOT_FOUND。
    """
    _ensure_project(db, project_id)
    template = (
        db.query(WordTemplate)
        .filter(WordTemplate.project_id == project_id)
        .first()
    )
    if not template:
        raise AppError(
            code="WORD_TEMPLATE_NOT_FOUND",
            message="项目未上传 Word 模板",
        )
    db.delete(template)
    _delete_word_template_file(project_id)
    _add_change(db, project_id,
                "WORD_TEMPLATE_DELETED",
                "删除 Word 模板")
    db.commit()


def get_word_template_file_path(
    db: Session, project_id: str
) -> tuple[Path, str] | None:
    """返回模板文件下载信息：(绝对路径, 原始文件名)。

    无模板时返回 None。
    """
    template = get_word_template(db, project_id)
    if not template:
        return None
    abs_path = (settings.project_data_root / template.file_path).resolve()
    # 防路径穿越
    base = settings.project_data_root.resolve()
    if not str(abs_path).startswith(str(base)):
        raise AppError(
            code="WORD_TEMPLATE_NOT_DOWNLOADABLE",
            message="模板路径无效",
        )
    return abs_path, template.original_filename
