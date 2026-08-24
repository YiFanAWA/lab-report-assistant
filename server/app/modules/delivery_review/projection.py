"""交付物审阅投影查询 owner。"""

from __future__ import annotations

from datetime import datetime, timezone
import json

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.analysis.models import AnalysisPlan
from app.modules.analysis.status import AnalysisPlanStatus
from app.modules.datasets.models import DatasetVersion
from app.modules.datasets.status import DatasetVersionStatus
from app.modules.delivery_review.contracts import (
    AvailableActions,
    DeliveryPreview,
    DeliveryReviewDeliverable,
    DeliveryReviewResponse,
    DeliveryTraceability,
    DeliveryVersionProvenance,
    DeliveryVersionReview,
    DeliveryVisualInspection,
    DeliverableFailure,
    QualityGate,
    RecommendedDownload,
    ReviewCheck,
)
from app.modules.execution.models import ExecutionArtifact, ExecutionRun
from app.modules.execution.status import ExecutionArtifactType, ExecutionRunStatus
from app.modules.outlines.document_planner import content_sufficiency_report
from app.modules.outlines.models import Deliverable, DeliverableVersion, Outline
from app.modules.outlines.status import (
    DeliverableStatus,
    DeliverableType,
    DeliverableVersionStatus,
    OutlineStatus,
)
from app.modules.projects.models import Project
from app.modules.requirements.models import RequirementPlan
from app.modules.requirements.status import PlanStatus
from app.modules.sources.models import EvidenceCard, Source
from app.modules.sources.status import EvidenceCardStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _ids(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        result = json.loads(value)
    except (TypeError, ValueError):
        return []
    return [str(item) for item in result] if isinstance(result, list) else []


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item))


def _check(code: str, label: str, status: str, source: str,
           reason: str | None = None, recovery: str | None = None) -> ReviewCheck:
    return ReviewCheck(
        code=code, label=label, status=status, reason=reason,
        recovery_action=recovery, source=source, checked_at=_now(),
    )


def _gate(code: str, label: str, status: str, severity: str, source: str,
          reason: str | None = None, recovery: str | None = None) -> QualityGate:
    return QualityGate(
        code=code, label=label, status=status, severity=severity,
        reason=reason, recovery_action=recovery, source=source, checked_at=_now(),
    )


def _gate_status(condition: bool, label: str, code: str, source: str,
                 reason: str, *, blocking: bool = True,
                 recovery: str | None = None) -> QualityGate:
    if condition:
        return _gate(code, label, "PASS", "INFO", source)
    return _gate(
        code, label, "BLOCKED" if blocking else "NOT_RUN",
        "BLOCKING" if blocking else "WARNING", source, reason, recovery,
    )


def _outline(db: Session, project_id: str) -> Outline | None:
    return (
        db.query(Outline)
        .filter(Outline.project_id == project_id,
                Outline.status == OutlineStatus.CONFIRMED.value)
        .order_by(Outline.updated_at.desc())
        .first()
    )


def _analysis(db: Session, project_id: str) -> AnalysisPlan | None:
    return (
        db.query(AnalysisPlan)
        .filter(AnalysisPlan.project_id == project_id,
                AnalysisPlan.status == AnalysisPlanStatus.CONFIRMED.value)
        .order_by(AnalysisPlan.updated_at.desc())
        .first()
    )


def _dataset(db: Session, project_id: str) -> DatasetVersion | None:
    return (
        db.query(DatasetVersion)
        .filter(DatasetVersion.project_id == project_id,
                DatasetVersion.status == DatasetVersionStatus.PARSED.value)
        .order_by(DatasetVersion.version.desc())
        .first()
    )


def _runs(db: Session, project_id: str) -> list[ExecutionRun]:
    return (
        db.query(ExecutionRun)
        .filter(ExecutionRun.project_id == project_id,
                ExecutionRun.status == ExecutionRunStatus.SUCCEEDED.value)
        .order_by(ExecutionRun.created_at.desc())
        .all()
    )


def _artifacts(db: Session, project_id: str,
               runs: list[ExecutionRun]) -> list[ExecutionArtifact]:
    ids = [run.id for run in runs]
    if not ids:
        return []
    return (
        db.query(ExecutionArtifact)
        .filter(ExecutionArtifact.project_id == project_id,
                ExecutionArtifact.execution_run_id.in_(ids))
        .order_by(ExecutionArtifact.created_at.asc())
        .all()
    )


def _sections(outline: Outline | None) -> list[dict]:
    if not outline:
        return []
    try:
        value = json.loads(outline.sections_json)
    except (TypeError, ValueError):
        return []
    if isinstance(value, dict):
        value = value.get("sections", [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _evidence(db: Session, project_id: str) -> list[EvidenceCard]:
    return (
        db.query(EvidenceCard)
        .filter(EvidenceCard.project_id == project_id,
                EvidenceCard.status == EvidenceCardStatus.CONFIRMED.value)
        .order_by(EvidenceCard.created_at.asc())
        .all()
    )


def _references(db: Session, project_id: str,
                evidence: list[EvidenceCard]) -> dict[str, str]:
    ids = _unique([card.source_id for card in evidence])
    if not ids:
        return {}
    rows = db.query(Source).filter(Source.project_id == project_id,
                                   Source.id.in_(ids)).all()
    return {row.id: row.title for row in rows}


def _recovery(kind: str, code: str | None) -> str:
    if kind == DeliverableType.PDF.value:
        return "检查成功的 Word 版本和 PDF 转换运行时后，重新触发 PDF 生成。"
    if kind == DeliverableType.WORD.value:
        return "返回大纲工作区确认大纲和结果来源后，重新生成 Word。"
    return "查看技术详情中的错误码，修复输入后重新生成该交付物。"


def _provenance(version: DeliverableVersion,
                deliverable: Deliverable) -> DeliveryVersionProvenance:
    datasets = _ids(version.dataset_version_ids_json)
    analyses = _ids(version.analysis_plan_ids_json)
    executions = _ids(version.execution_run_ids_json)
    missing = None
    if not datasets and not analyses and not executions:
        missing = "该版本未保存数据集、分析方案和执行记录绑定，无法从版本本身回推。"
    return DeliveryVersionProvenance(
        outline_id=deliverable.outline_id,
        outline_version=version.outline_version,
        dataset_version_id=version.dataset_version_id,
        dataset_version_ids=datasets,
        analysis_plan_id=version.analysis_plan_id,
        analysis_plan_ids=analyses,
        execution_run_id=version.execution_run_id,
        execution_run_ids=executions,
        source_word_version_id=version.source_word_version_id,
        file_sha256=version.file_sha256,
        unavailable_reason=missing,
    )


def _stale(version: DeliverableVersion, deliverable: Deliverable,
           current: Outline | None) -> tuple[bool, str | None]:
    if deliverable.status == DeliverableStatus.STALE.value:
        return True, "关联交付物已因大纲变更而失效。"
    if current and deliverable.outline_id != current.id:
        return True, "该版本来自旧的大纲版本。"
    if (current and deliverable.outline_id == current.id
            and version.outline_version is not None
            and version.outline_version != current.code_version):
        return True, "该版本的大纲版本与当前确认版本不一致。"
    return False, None


def _version_review(version: DeliverableVersion, deliverable: Deliverable,
                    current: Outline | None, previous: DeliverableVersion | None,
                    recommended: str | None) -> DeliveryVersionReview:
    stale, invalidation = _stale(version, deliverable, current)
    provenance = _provenance(version, deliverable)
    if previous is None:
        diff = "首个版本，没有可比较的历史版本。"
    elif (provenance.dataset_version_ids != _ids(previous.dataset_version_ids_json)
          or provenance.analysis_plan_ids != _ids(previous.analysis_plan_ids_json)
          or provenance.execution_run_ids != _ids(previous.execution_run_ids_json)):
        diff = "数据集、分析方案或执行记录绑定发生变化；正文差异未持久化。"
    else:
        diff = "结构化来源绑定相同；正文差异未持久化，无法判断章节级变化。"
    failure = None
    recovery = None
    if version.status == DeliverableVersionStatus.FAILED.value:
        recovery = _recovery(deliverable.deliverable_type, version.error_code)
        failure = DeliverableFailure(
            code=version.error_code, message=version.error_message,
            recovery_action=recovery,
        )
    return DeliveryVersionReview(
        id=version.id, version=version.version, status=version.status,
        file_size_bytes=version.file_size_bytes, created_at=version.created_at.isoformat(),
        finished_at=_iso(version.finished_at), is_recommended=version.id == recommended,
        is_stale=stale, invalidation_reason=invalidation, diff_summary=diff,
        provenance=provenance,
        preview=DeliveryPreview(
            status="NOT_AVAILABLE", label="预览不可用",
            reason="当前生成链未提供真实渲染缩略图；请下载原文件查看。",
        ),
        visual_inspection=DeliveryVisualInspection(
            status="NOT_CHECKED", label="尚未检查",
            reason="尚未在真实 Word/PDF/PPT 渲染环境逐页检查。",
        ),
        failure=failure, recovery_action=recovery,
    )


def _deliverable(db: Session, item: Deliverable,
                 current: Outline | None) -> DeliveryReviewDeliverable:
    versions = (
        db.query(DeliverableVersion)
        .filter(DeliverableVersion.deliverable_id == item.id)
        .order_by(DeliverableVersion.version.desc())
        .all()
    )
    valid_success = [
        version for version in versions
        if version.status == DeliverableVersionStatus.SUCCEEDED.value
        and bool(version.file_path)
        and not _stale(version, item, current)[0]
    ]
    recommended = valid_success[0] if valid_success else None
    reviewed = [
        _version_review(
            version, item, current,
            versions[index + 1] if index + 1 < len(versions) else None,
            recommended.id if recommended else None,
        )
        for index, version in enumerate(versions)
    ]
    latest = versions[0] if versions else None
    selected = recommended or latest
    provenance = (
        _provenance(selected, item)
        if selected else DeliveryVersionProvenance(
            outline_id=item.outline_id, unavailable_reason="当前没有可审阅的版本。",
        )
    )
    failure = None
    if latest and latest.status == DeliverableVersionStatus.FAILED.value:
        failure = DeliverableFailure(
            code=latest.error_code, message=latest.error_message,
            recovery_action=_recovery(item.deliverable_type, latest.error_code),
        )
    return DeliveryReviewDeliverable(
        id=item.id, type=item.deliverable_type, status=item.status,
        current_version_id=selected.id if selected else None,
        version_number=selected.version if selected else None,
        outline_id=item.outline_id, source_execution_id=provenance.execution_run_id,
        is_stale=item.status == DeliverableStatus.STALE.value, failure=failure,
        recommended_version_id=recommended.id if recommended else None,
        versions=reviewed, provenance=provenance,
    )


def _content(outline: Outline | None, plan: RequirementPlan | None,
             evidence: list[EvidenceCard], artifacts: list[ExecutionArtifact],
             references: dict[str, str]) -> list[ReviewCheck]:
    source = "outlines.document_planner"
    labels = (
        ("REQUIREMENTS_COVERED", "实验要求覆盖"),
        ("EVIDENCE_COVERED", "证据来源覆盖"),
        ("DATA_SAMPLE_DEFINED", "数据与样本口径"),
        ("METHODS_COMPLETE", "方法完整性"),
        ("RESULTS_REAL_OUTPUT", "真实图表或表格"),
        ("DISCUSSION_LIMITATIONS", "讨论与限制"),
        ("REFERENCES_COMPLETE", "引用完整性"),
    )
    if not outline:
        return [
            _check(code, label, "NOT_RUN", source,
                   "没有已确认大纲，无法检查交付物内容。",
                   "先在大纲工作区生成并确认大纲。")
            for code, label in labels
        ]
    sections = _sections(outline)
    report = content_sufficiency_report(
        sections, [{"artifact_type": a.artifact_type} for a in artifacts], references,
    )
    issues = {issue.code for issue in report.issues}
    cited = {
        str(source_id).strip()
        for section in sections
        for source_id in (section.get("source_ids") or [])
        if str(source_id).strip()
    }
    evidence_ids = {card.id for card in evidence}
    evidence_source_ids = {card.source_id for card in evidence}
    checks = [
        ("REQUIREMENTS_COVERED", "实验要求覆盖",
         plan is not None and any(
             str(s.get("source_type", "")).upper() == "REQUIREMENT"
             or bool(s.get("research_question")) for s in sections),
         "大纲没有可回指的实验要求或结构化要求未确认。",
         "确认任务单并重新确认大纲。"),
        ("EVIDENCE_COVERED", "证据来源覆盖",
         bool(evidence_source_ids) and bool(cited.intersection(evidence_source_ids)),
         "没有确认的证据卡片，或大纲没有引用已确认证据。",
         "确认证据卡片并在大纲中关联来源。"),
        ("DATA_SAMPLE_DEFINED", "数据与样本口径",
         "MANUSCRIPT_DATA_MISSING" not in issues and plan is not None,
         "缺少真实数据、研究对象或样本说明。",
         "补充数据来源、样本量和纳入口径。"),
        ("METHODS_COMPLETE", "方法完整性",
         "MANUSCRIPT_METHODS_MISSING" not in issues,
         "缺少可复核的研究设计或统计方法。",
         "补充研究设计、变量编码和统计方法。"),
        ("RESULTS_REAL_OUTPUT", "真实图表或表格",
         "MANUSCRIPT_RESULTS_MISSING" not in issues and any(
             a.artifact_type in {
                 ExecutionArtifactType.CHART_PNG.value,
                 ExecutionArtifactType.TABLE_CSV.value,
             } for a in artifacts),
         "没有成功执行产生的真实图表或表格。",
         "成功执行分析并生成可追溯图表或表格。"),
        ("DISCUSSION_LIMITATIONS", "讨论与限制",
         "MANUSCRIPT_DISCUSSION_MISSING" not in issues,
         "缺少回应结果的讨论或限制。",
         "补充讨论、局限和适用边界。"),
        ("REFERENCES_COMPLETE", "引用完整性",
         bool(cited) and bool(references) and cited.issubset(set(references)),
         "大纲引用的来源没有全部解析为已确认来源。",
         "确认来源和证据卡片，并关联来源 ID。"),
    ]
    return [
        _check(code, label, "PASS" if ok else "BLOCKED", source,
               None if ok else reason, None if ok else recovery)
        for code, label, ok, reason, recovery in checks
    ]


def _boundaries(plan: RequirementPlan | None) -> list[ReviewCheck]:
    source = "requirements.payload_json"
    labels = (
        ("OBSERVATIONAL_CAUSAL_BOUNDARY", "观察性关联与因果边界"),
        ("REPLICATION_LEVEL", "复现层级声明"),
        ("MEDICAL_TEACHING_BOUNDARY", "医学教学边界"),
    )
    if not plan:
        return [
            _check(code, label, "NOT_RUN", source,
                   "没有确认的结构化实验要求，统计边界尚未声明。",
                   "确认任务单后补充研究设计和复现层级。")
            for code, label in labels
        ]
    try:
        payload = json.loads(plan.payload_json)
    except (TypeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    replication = payload.get("replication_level")
    level = replication.get("level") if isinstance(replication, dict) else None
    supported = replication.get("supported_in_v1") if isinstance(replication, dict) else None
    if level == "L3" and supported is False:
        replication_check = _check(
            "REPLICATION_LEVEL", "复现层级声明", "BLOCKED", source,
            "当前任务声明为 L3，但 V1 不支持完整复现。",
            "降级为 L1/L2 教学性复核，或明确标记为超范围。",
        )
    elif level:
        replication_check = _check(
            "REPLICATION_LEVEL", "复现层级声明", "PASS", source,
            f"已声明复现层级 {level}，不会包装为完整复现。",
        )
    else:
        replication_check = _check(
            "REPLICATION_LEVEL", "复现层级声明", "NOT_RUN", source,
            "任务单没有结构化复现层级，无法判断是否为完整复现。",
            "补充 L0-L3 复现层级。",
        )
    design = payload.get("study_design")
    causal_allowed = payload.get("causal_claim_allowed")
    observational = design in {"OBSERVATIONAL", "RETROSPECTIVE", "CROSS_SECTIONAL"}
    if observational and causal_allowed is not False:
        causal = _check(
            "OBSERVATIONAL_CAUSAL_BOUNDARY", "观察性关联与因果边界",
            "BLOCKED", source,
            "研究设计为观察性，但没有明确禁止因果表述。",
            "声明 causal_claim_allowed=false，并保留关联性措辞。",
        )
    elif causal_allowed is False:
        causal = _check(
            "OBSERVATIONAL_CAUSAL_BOUNDARY", "观察性关联与因果边界",
            "PASS", source,
            "任务单已明确禁止把观察性关联解释为因果关系。",
        )
    else:
        causal = _check(
            "OBSERVATIONAL_CAUSAL_BOUNDARY", "观察性关联与因果边界",
            "NOT_RUN", source,
            "没有结构化研究设计或因果声明，未推断统计边界。",
            "补充 study_design 和 causal_claim_allowed。",
        )
    domain = payload.get("domain")
    teaching = payload.get("teaching_analysis_boundary")
    if domain == "MEDICAL" and teaching is not True:
        medical = _check(
            "MEDICAL_TEACHING_BOUNDARY", "医学教学边界", "BLOCKED", source,
            "医学任务没有声明仅用于教学性数据分析。",
            "声明 teaching_analysis_boundary=true，并保留非诊疗文案。",
        )
    elif domain == "MEDICAL":
        medical = _check(
            "MEDICAL_TEACHING_BOUNDARY", "医学教学边界", "PASS", source,
            "已声明为教学性数据分析，不提供诊断或治疗建议。",
        )
    else:
        medical = _check(
            "MEDICAL_TEACHING_BOUNDARY", "医学教学边界", "NOT_RUN", source,
            "没有结构化领域声明，未猜测医学语义。",
            "如属于医学教学分析，请补充 domain 和教学边界声明。",
        )
    return [causal, replication_check, medical]


def _aggregate(checks: list[ReviewCheck], code: str, label: str) -> QualityGate:
    blocked = next((item for item in checks if item.status == "BLOCKED"), None)
    missing = next((item for item in checks if item.status == "NOT_RUN"), None)
    if blocked:
        return _gate(code, label, "BLOCKED", "BLOCKING", "delivery_review",
                     blocked.reason, blocked.recovery_action)
    if missing:
        return _gate(code, label, "NOT_RUN", "WARNING", "delivery_review",
                     missing.reason, missing.recovery_action)
    return _gate(code, label, "PASS", "INFO", "delivery_review")


def build_delivery_review(db: Session, project_id: str) -> DeliveryReviewResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise AppError(code="PROJECT_NOT_FOUND", message=f"未找到项目 {project_id}")
    outline = _outline(db, project_id)
    analysis = _analysis(db, project_id)
    dataset = _dataset(db, project_id)
    runs = _runs(db, project_id)
    artifacts = _artifacts(db, project_id, runs)
    plan = (
        db.query(RequirementPlan)
        .filter(RequirementPlan.project_id == project_id,
                RequirementPlan.status == PlanStatus.CONFIRMED.value)
        .order_by(RequirementPlan.updated_at.desc())
        .first()
    )
    evidence = _evidence(db, project_id)
    references = _references(db, project_id, evidence)
    rows = (
        db.query(Deliverable)
        .filter(Deliverable.project_id == project_id)
        .order_by(Deliverable.created_at.asc())
        .all()
    )
    projections = [_deliverable(db, row, outline) for row in rows]
    content = _content(outline, plan, evidence, artifacts, references)
    boundaries = _boundaries(plan)
    gates = [
        _gate_status(plan is not None, "实验要求已确认", "REQUIREMENT_CONFIRMED",
                     "requirements", "还没有确认的结构化实验要求。",
                     recovery="返回实验要求工作区确认任务单。"),
        _gate_status(
            dataset is not None and dataset.status == DatasetVersionStatus.PARSED.value,
            "数据集可用", "DATASET_READY", "datasets",
            "没有已解析的数据集版本。",
            recovery="上传并解析至少一个数据集版本。",
        ),
        _gate_status(analysis is not None, "分析方案已确认", "ANALYSIS_CONFIRMED",
                     "analysis", "还没有确认的分析方案。",
                     recovery="在分析工作区确认分析方案。"),
        _gate_status(bool(runs), "至少有一次执行成功", "EXECUTION_SUCCEEDED",
                     "execution", "没有成功的执行记录。",
                     recovery="在执行工作区运行已确认的代码任务。"),
        _gate_status(
            any(a.artifact_type == ExecutionArtifactType.CHART_PNG.value for a in artifacts),
            "图表产物可追溯", "CHARTS_TRACEABLE", "execution_artifacts",
            "成功执行记录中没有图表产物。",
            recovery="成功执行分析并生成至少一张真实图表。",
        ),
        _gate_status(outline is not None, "实验大纲已确认", "OUTLINE_CONFIRMED",
                     "outlines", "还没有确认的实验大纲。",
                     recovery="在大纲工作区确认大纲。"),
        _gate_status(bool(evidence), "证据卡片可追溯", "EVIDENCE_TRACEABLE",
                     "evidence_cards", "还没有确认的证据卡片。", blocking=False,
                     recovery="确认来源和证据卡片后关联引用。"),
        _aggregate(content, "CONTENT_QUALITY", "正文内容质量检查"),
        _aggregate(boundaries, "STATISTICAL_BOUNDARIES", "统计与产品边界检查"),
    ]
    active = {item.type: item for item in projections if not item.is_stale}
    for kind, label in ((DeliverableType.WORD.value, "Word"),
                        (DeliverableType.PDF.value, "PDF"),
                        (DeliverableType.PPT.value, "PPT")):
        item = active.get(kind)
        gates.append(_gate_status(
            item is not None and item.status == DeliverableStatus.SUCCEEDED.value
            and item.recommended_version_id is not None,
            f"{label} 正式交付物已成功", f"{kind}_SUCCEEDED", "outlines",
            f"{label} 尚未有当前大纲下的成功版本。",
            recovery=f"返回大纲工作区重新生成 {label}。",
        ))
    same_outline = len(active) >= 3 and len({item.outline_id for item in active.values()}) == 1
    gates.append(_gate_status(
        same_outline, "Word/PDF/PPT 使用同一份大纲",
        "DELIVERABLES_SAME_OUTLINE", "outlines",
        "三类交付物尚未形成同源集合。",
        recovery="从同一份已确认大纲重新生成缺失交付物。",
    ))
    provenance_ok = bool(projections) and all(
        item.recommended_version_id is not None
        and not item.provenance.unavailable_reason
        for item in projections
    )
    gates.append(_gate_status(
        provenance_ok, "推荐版本 provenance 完整", "VERSION_PROVENANCE",
        "deliverable_versions", "历史版本没有保存完整来源绑定。",
        blocking=False, recovery="重新生成交付物以保存版本级来源绑定。",
    ))
    gates.extend([
        _gate("VISUAL_INSPECTION", "真实视觉检查", "NOT_RUN", "WARNING", "renderers",
              "尚未在真实 Word/PDF/PPT 环境逐页检查，不能显示通过。",
              "下载并在真实办公软件中检查版式。"),
        _gate("PDF_CONVERTER_AVAILABLE", "PDF 转换器可用性", "NOT_RUN",
              "WARNING", "packaging/windows",
              "运行时可用性需在 portable Windows 包中验证。",
              "在目标 Windows 包中执行 DOCX→PDF 验收。"),
        _gate("FILE_MANIFEST_VALID", "交付物文件和 manifest 校验", "NOT_RUN",
              "WARNING", "packaging/windows",
              "当前应用没有将 publication manifest 持久化到项目版本合同。",
              "完成真实发布链检查后再记录 manifest 结果。"),
    ])
    reasons = [gate.reason for gate in gates if gate.status == "BLOCKED" and gate.reason]
    required_pass = all(gate.status == "PASS" for gate in gates if gate.severity == "BLOCKING")
    recommendations = [
        RecommendedDownload(
            deliverable_id=item.id, deliverable_type=item.type,
            version_id=item.recommended_version_id, version_number=item.version_number,
            reason="当前大纲下最新成功且未失效的版本。",
        )
        for item in projections
        if item.recommended_version_id and item.version_number is not None
    ]
    datasets: list[str] = []
    analyses: list[str] = []
    executions: list[str] = []
    for item in projections:
        datasets.extend(item.provenance.dataset_version_ids)
        analyses.extend(item.provenance.analysis_plan_ids)
        executions.extend(item.provenance.execution_run_ids)
    datasets, analyses, executions = _unique(datasets), _unique(analyses), _unique(executions)
    artifact_ids = [
        artifact.id
        for artifact in db.query(ExecutionArtifact)
        .filter(ExecutionArtifact.project_id == project_id,
                ExecutionArtifact.execution_run_id.in_(executions))
        .all()
    ] if executions else []
    trace = DeliveryTraceability(
        outline_id=outline.id if outline else None,
        outline_version=outline.code_version if outline else None,
        dataset_version_id=datasets[0] if len(datasets) == 1 else None,
        dataset_version_ids=datasets,
        analysis_version_id=analyses[0] if len(analyses) == 1 else None,
        analysis_plan_id=analyses[0] if len(analyses) == 1 else None,
        analysis_plan_ids=analyses,
        execution_run_id=executions[0] if len(executions) == 1 else None,
        execution_run_ids=executions,
        evidence_ids=[card.id for card in evidence], artifact_ids=artifact_ids,
        unavailable_reason=None if datasets or analyses or executions
        else "当前没有可从交付物版本读取的 provenance。",
    )
    can_complete = (
        project.status != "COMPLETED" and required_pass
        and len(active) == 3
        and all(item.recommended_version_id for item in active.values())
    )
    return DeliveryReviewResponse(
        project_id=project_id,
        review_status=(
            "READY" if required_pass and project.status == "COMPLETED"
            else "STALE" if any(item.is_stale for item in projections)
            else "BLOCKED" if reasons else "NEEDS_REVIEW"
        ),
        deliverables=projections, traceability=trace,
        quality_gates=gates, content_quality=content,
        boundary_checks=boundaries, recommended_downloads=recommendations,
        available_actions=AvailableActions(
            can_download=bool(recommendations),
            can_regenerate=outline is not None,
            can_complete=can_complete,
            blocked_reasons=reasons,
            can_preview=False,
            can_view_traceability=True,
            can_retry_failed=any(item.failure for item in projections),
        ),
    )
