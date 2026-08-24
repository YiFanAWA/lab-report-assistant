"""交付审阅投影合同。

这些类型是只读审阅投影，不是交付物写入合同。所有质量结论必须由
delivery_review 查询 owner 从真实项目事实计算；缺少事实时保留
NOT_RUN/N/A 语义，不能由前端补齐。
"""

from pydantic import BaseModel, Field


class DeliverableFailure(BaseModel):
    code: str | None = None
    message: str | None = None
    recovery_action: str | None = None


class DeliveryPreview(BaseModel):
    """真实预览状态；没有真实缩略图时不能伪造预览。"""

    status: str
    label: str
    reason: str | None = None
    asset_path: str | None = None


class DeliveryVisualInspection(BaseModel):
    status: str
    label: str
    reason: str | None = None
    checked_at: str | None = None


class DeliveryVersionProvenance(BaseModel):
    outline_id: str | None = None
    outline_version: int | None = None
    dataset_version_id: str | None = None
    dataset_version_ids: list[str] = Field(default_factory=list)
    analysis_plan_id: str | None = None
    analysis_plan_ids: list[str] = Field(default_factory=list)
    execution_run_id: str | None = None
    execution_run_ids: list[str] = Field(default_factory=list)
    source_word_version_id: str | None = None
    file_sha256: str | None = None
    unavailable_reason: str | None = None


class DeliveryVersionReview(BaseModel):
    id: str
    version: int
    status: str
    file_size_bytes: int | None = None
    created_at: str
    finished_at: str | None = None
    is_recommended: bool = False
    is_stale: bool = False
    invalidation_reason: str | None = None
    diff_summary: str | None = None
    provenance: DeliveryVersionProvenance = Field(
        default_factory=DeliveryVersionProvenance
    )
    preview: DeliveryPreview
    visual_inspection: DeliveryVisualInspection
    failure: DeliverableFailure | None = None
    recovery_action: str | None = None


class DeliveryReviewDeliverable(BaseModel):
    id: str
    type: str
    status: str
    current_version_id: str | None = None
    version_number: int | None = None
    outline_id: str
    source_execution_id: str | None = None
    is_stale: bool
    failure: DeliverableFailure | None = None
    recommended_version_id: str | None = None
    versions: list[DeliveryVersionReview] = Field(default_factory=list)
    provenance: DeliveryVersionProvenance = Field(
        default_factory=DeliveryVersionProvenance
    )


class DeliveryTraceability(BaseModel):
    outline_id: str | None = None
    outline_version: int | None = None
    dataset_version_id: str | None = None
    dataset_version_ids: list[str] = Field(default_factory=list)
    analysis_version_id: str | None = None
    analysis_plan_id: str | None = None
    analysis_plan_ids: list[str] = Field(default_factory=list)
    execution_run_id: str | None = None
    execution_run_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    unavailable_reason: str | None = None


class QualityGate(BaseModel):
    code: str
    label: str
    status: str
    severity: str
    reason: str | None = None
    recovery_action: str | None = None
    source: str
    checked_at: str


class ReviewCheck(BaseModel):
    """内容质量或统计边界检查。"""

    code: str
    label: str
    status: str
    reason: str | None = None
    recovery_action: str | None = None
    source: str
    checked_at: str


class RecommendedDownload(BaseModel):
    deliverable_id: str
    deliverable_type: str
    version_id: str
    version_number: int
    reason: str


class AvailableActions(BaseModel):
    can_download: bool
    can_regenerate: bool
    can_complete: bool
    blocked_reasons: list[str] = Field(default_factory=list)
    can_preview: bool = False
    can_view_traceability: bool = True
    can_retry_failed: bool = False


class DeliveryReviewResponse(BaseModel):
    project_id: str
    review_status: str
    deliverables: list[DeliveryReviewDeliverable]
    traceability: DeliveryTraceability
    quality_gates: list[QualityGate]
    content_quality: list[ReviewCheck] = Field(default_factory=list)
    boundary_checks: list[ReviewCheck] = Field(default_factory=list)
    recommended_downloads: list[RecommendedDownload] = Field(default_factory=list)
    available_actions: AvailableActions
