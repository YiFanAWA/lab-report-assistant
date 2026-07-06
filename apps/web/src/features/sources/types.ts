/** 资料来源类型 — 与后端 SourceResponse 等合同一致（snake_case）。 */

export type SourceKind = "URL" | "FILE";

export type SourceStatus =
  | "PENDING"
  | "FETCHED"
  | "PARSED"
  | "FAILED"
  | "DELETED";

/** 来源响应体。 */
export interface Source {
  id: string;
  project_id: string;
  source_kind: SourceKind;
  title: string;
  url: string | null;
  file_path: string | null;
  content_type: string | null;
  content_hash: string | null;
  status: SourceStatus;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  fetched_at: string | null;
  parsed_at: string | null;
  /** 创建来源时返回的关联任务 ID（仅创建响应非空）。 */
  job_id: string | null;
}

/** 来源列表响应。 */
export interface SourceListResponse {
  items: Source[];
}

/** 解析文档响应体。 */
export interface ParsedDocument {
  id: string;
  source_id: string;
  project_id: string;
  title: string | null;
  parsed_text: string;
  metadata_json: string | null;
  parsed_at: string;
}

/** 完成来源收集响应。 */
export interface CompleteSourcesResponse {
  project_id: string;
  status: string;
}
