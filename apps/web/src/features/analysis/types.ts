/** 分析方案类型 — 与后端 AnalysisPlanResponse 等合同一致（snake_case）。 */

export type AnalysisPlanStatus =
  | "CANDIDATE"
  | "CONFIRMED"
  | "REJECTED"
  | "STALE";

export type CandidateSource = "MODEL" | "LOCAL_RULE" | "MANUAL";

/** 分析方案响应体。 */
export interface AnalysisPlan {
  id: string;
  project_id: string;
  dataset_id: string;
  dataset_version_id: string;
  /** JSON 字符串，包含清洗方案条目数组。 */
  cleaning_plan: string;
  /** JSON 字符串，包含分析方案条目数组。 */
  analysis_plan: string;
  /** JSON 字符串，包含图表方案条目数组。 */
  chart_plan: string;
  status: AnalysisPlanStatus;
  candidate_source: CandidateSource;
  created_at: string;
  updated_at: string | null;
  confirmed_at: string | null;
}

/** 分析方案列表响应。 */
export interface AnalysisPlanListResponse {
  items: AnalysisPlan[];
}

/** 更新分析方案请求体。所有字段可选，未传字段保持原值。 */
export interface UpdateAnalysisPlanRequest {
  cleaning_plan?: string | null;
  analysis_plan?: string | null;
  chart_plan?: string | null;
}

/** 完成分析方案确认响应。 */
export interface CompleteAnalysisResponse {
  status: string;
}

/** 清洗方案条目。 */
export interface CleaningPlanItem {
  field: string;
  issue_type: string;
  action: string;
  reason: string;
}

/** 分析方案条目。 */
export interface AnalysisPlanItem {
  analysis_type: string;
  target_fields: string[];
  method: string;
  expected_output: string;
}

/** 图表方案条目。 */
export interface ChartPlanItem {
  chart_type: string;
  title: string;
  data_fields: string[];
  description: string;
}
