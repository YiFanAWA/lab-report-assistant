/** 后台任务类型 — 与后端 JobResponse 一致（snake_case）。 */

export type JobType = "FETCH_URL" | "PARSE_DOCUMENT" | "GENERATE_EVIDENCE";

export type JobStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELLED";

/** 后台任务响应体。 */
export interface BackgroundJob {
  id: string;
  project_id: string;
  job_type: JobType;
  status: JobStatus;
  input_json: string;
  output_json: string | null;
  error_code: string | null;
  error_message: string | null;
  retry_count: number;
  max_retries: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  next_retry_at: string | null;
}

/** 任务列表响应。 */
export interface JobListResponse {
  items: BackgroundJob[];
}

/** 生成证据卡片响应。 */
export interface GenerateEvidenceResponse {
  job_id: string;
}
