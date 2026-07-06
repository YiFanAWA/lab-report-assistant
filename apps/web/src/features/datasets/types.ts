/** 数据集类型 — 与后端 DatasetResponse 等合同一致（snake_case）。 */

export type DatasetKind = "FILE" | "URL";

export type DatasetStatus =
  | "PENDING"
  | "READY"
  | "FAILED"
  | "DELETED";

export type DatasetVersionStatus =
  | "PENDING"
  | "PARSING"
  | "PARSED"
  | "FAILED"
  | "SUPERSEDED";

/** 数据集响应体。 */
export interface Dataset {
  id: string;
  project_id: string;
  dataset_kind: DatasetKind;
  title: string;
  description: string | null;
  status: DatasetStatus;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string | null;
  /** 创建或重新上传时返回的关联任务 ID。 */
  job_id: string | null;
}

/** 数据集列表响应。 */
export interface DatasetListResponse {
  items: Dataset[];
}

/** 数据集版本响应体。 */
export interface DatasetVersion {
  id: string;
  dataset_id: string;
  project_id: string;
  version: number;
  status: DatasetVersionStatus;
  file_path: string;
  file_size_bytes: number;
  row_count: number | null;
  column_count: number | null;
  /** JSON 字符串，包含字段概览和质量概览。 */
  profile_json: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  parsed_at: string | null;
}

/** 数据集版本列表响应。 */
export interface DatasetVersionListResponse {
  items: DatasetVersion[];
}

/** 完成数据集收集响应。 */
export interface CompleteDatasetsResponse {
  status: string;
}

/** 高频值（与后端 list[tuple[str, int]] 序列化为 [value, count] 数组）。 */
export type TopValue = [string, number];

/** 字段概览。对应后端 FieldProfile dataclass。 */
export interface FieldProfile {
  name: string;
  inferred_type: string;
  non_null_count: number;
  null_count: number;
  null_rate: number;
  unique_count: number;
  sample_values: string[];
  /** 数值字段额外统计。 */
  min_value: number | null;
  max_value: number | null;
  mean_value: number | null;
  median_value: number | null;
  std_value: number | null;
  q1: number | null;
  q3: number | null;
  /** 字符串字段高频值（前 10）。 */
  top_values: TopValue[];
}

/** 数据集概览。对应后端 DatasetProfile dataclass。 */
export interface DatasetProfile {
  row_count: number;
  column_count: number;
  complete_row_count: number;
  incomplete_row_count: number;
  duplicate_row_count: number;
  field_profiles: FieldProfile[];
  quality_score: number;
}
