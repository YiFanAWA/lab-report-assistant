/** 大纲与交付物类型 — 与后端 OutlineResponse/DeliverableResponse 等合同一致（snake_case）。 */

/** 大纲章节来源类型。 */
export type OutlineSourceType =
  | "REQUIREMENT"
  | "EVIDENCE"
  | "DATASET"
  | "ANALYSIS"
  | "EXECUTION"
  | "SUMMARY";

/** 大纲章节。 */
export interface OutlineSection {
  id: string;
  title: string;
  content: string;
  source_type: string;
  source_ids: string[];
}

/** 大纲状态。 */
export type OutlineStatus =
  | "CANDIDATE"
  | "CONFIRMED"
  | "REJECTED"
  | "STALE";

/** 交付物类型。 */
export type DeliverableType = "WORD" | "PDF" | "PPT";

/** 交付物状态。 */
export type DeliverableStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "STALE";

/** 交付物版本状态。 */
export type DeliverableVersionStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED";

/** 大纲响应体。 */
export interface Outline {
  id: string;
  project_id: string;
  sections: OutlineSection[];
  status: OutlineStatus;
  candidate_source: string;
  version: number;
  created_at: string;
  updated_at: string | null;
  confirmed_at: string | null;
}

/** 大纲列表响应。 */
export interface OutlineListResponse {
  items: Outline[];
}

/** 编辑大纲请求体。 */
export interface UpdateOutlineRequest {
  sections: OutlineSection[];
}

/** 交付物响应体。 */
export interface Deliverable {
  id: string;
  project_id: string;
  outline_id: string;
  deliverable_type: DeliverableType;
  status: DeliverableStatus;
  created_at: string;
  updated_at: string | null;
}

/** 交付物列表响应。 */
export interface DeliverableListResponse {
  items: Deliverable[];
}

/** 交付物版本响应体。 */
export interface DeliverableVersion {
  id: string;
  deliverable_id: string;
  version: number;
  status: DeliverableVersionStatus;
  file_path: string | null;
  file_size_bytes: number | null;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  created_at: string;
}

/** 交付物版本列表响应。 */
export interface DeliverableVersionListResponse {
  items: DeliverableVersion[];
}

/** 触发生成大纲候选响应。 */
export interface GenerateOutlineResponse {
  job_id: string;
}

/** 触发生成交付物响应。

 * template_used 表示是否使用了项目级 Word 模板（SPEC 0010）。
 */
export interface GenerateDeliverableResponse {
  job_id: string;
  deliverable_id: string;
  template_used?: boolean;
}

/** PPT 生成配置（SPEC 0011）。所有字段可选，未提供时使用默认值。 */
export interface PptConfig {
  /** 目标页数（5-20），null 表示使用默认行为 */
  target_slide_count?: number | null;
  /** 主题色 hex 值，null 表示使用默认黑色 */
  theme_color?: string | null;
  /** 是否包含图表页，默认 true */
  include_charts?: boolean;
}

/** 触发 PPT 生成请求（SPEC 0011）。 */
export interface GeneratePptRequest {
  config?: PptConfig;
}

/** PPT 预设主题色板（SPEC 0011）。 */
export const PPT_THEME_COLORS: string[] = [
  "#2563eb", // 蓝色（默认推荐）
  "#7c3aed", // 紫色
  "#16a34a", // 绿色
  "#dc2626", // 红色
  "#ea580c", // 橙色
  "#475569", // 灰色
];

/** Word 模板响应体（SPEC 0010）。 */
export interface WordTemplate {
  id: string;
  project_id: string;
  original_filename: string;
  file_size_bytes: number;
  content_hash: string;
  created_at: string;
  updated_at: string | null;
}

/** 完成项目响应。 */
export interface CompleteProjectResponse {
  status: string;
}

export interface DeliveryReviewDeliverable {
  id: string;
  type: DeliverableType;
  status: DeliverableStatus;
  current_version_id: string | null;
  version_number: number | null;
  outline_id: string;
  source_execution_id: string | null;
  is_stale: boolean;
  failure: { code: string | null; message: string | null; recovery_action?: string | null } | null;
  recommended_version_id: string | null;
  versions: DeliveryVersionReview[];
  provenance: DeliveryVersionProvenance;
}

export interface DeliveryReviewProjection {
  project_id: string;
  review_status: "READY" | "NEEDS_REVIEW" | "BLOCKED" | "STALE";
  deliverables: DeliveryReviewDeliverable[];
  traceability: {
    outline_id: string | null;
    outline_version?: number | null;
    dataset_version_id: string | null;
    dataset_version_ids?: string[];
    analysis_version_id: string | null;
    analysis_plan_id?: string | null;
    analysis_plan_ids?: string[];
    execution_run_id: string | null;
    execution_run_ids?: string[];
    evidence_ids: string[];
    artifact_ids?: string[];
    unavailable_reason?: string | null;
  };
  quality_gates: Array<{
    code: string;
    label: string;
    status: "PASS" | "WARN" | "BLOCKED" | "NOT_RUN";
    severity: "INFO" | "WARNING" | "BLOCKING";
    reason: string | null;
    recovery_action?: string | null;
    source: string;
    checked_at: string;
  }>;
  available_actions: {
    can_download: boolean;
    can_regenerate: boolean;
    can_complete: boolean;
    blocked_reasons: string[];
    can_preview?: boolean;
    can_view_traceability?: boolean;
    can_retry_failed?: boolean;
  };
  content_quality?: ReviewCheck[];
  boundary_checks?: ReviewCheck[];
  recommended_downloads?: RecommendedDownload[];
}

export interface DeliveryVersionProvenance {
  outline_id: string | null;
  outline_version: number | null;
  dataset_version_id: string | null;
  dataset_version_ids: string[];
  analysis_plan_id: string | null;
  analysis_plan_ids: string[];
  execution_run_id: string | null;
  execution_run_ids: string[];
  source_word_version_id: string | null;
  file_sha256: string | null;
  unavailable_reason: string | null;
}

export interface DeliveryVersionReview {
  id: string;
  version: number;
  status: DeliverableVersionStatus;
  file_size_bytes: number | null;
  created_at: string;
  finished_at: string | null;
  is_recommended: boolean;
  is_stale: boolean;
  invalidation_reason: string | null;
  diff_summary: string | null;
  provenance: DeliveryVersionProvenance;
  preview: { status: string; label: string; reason: string | null; asset_path: string | null };
  visual_inspection: { status: string; label: string; reason: string | null; checked_at: string | null };
  failure: { code: string | null; message: string | null; recovery_action?: string | null } | null;
  recovery_action: string | null;
}

export interface ReviewCheck {
  code: string;
  label: string;
  status: "PASS" | "WARN" | "BLOCKED" | "NOT_RUN";
  reason: string | null;
  recovery_action: string | null;
  source: string;
  checked_at: string;
}

export interface RecommendedDownload {
  deliverable_id: string;
  deliverable_type: DeliverableType;
  version_id: string;
  version_number: number;
  reason: string;
}
