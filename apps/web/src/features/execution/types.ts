/** 执行核心侧类型 — 与后端 CodeTaskResponse/ExecutionRunResponse 等合同一致（snake_case）。

对应后端 owner：server/app/modules/execution/（contracts.py + status.py）。
 */

/** 代码任务状态。与后端 CodeTaskStatus 枚举一致。 */
export type CodeTaskStatus =
  | "CANDIDATE"
  | "CONFIRMED"
  | "REJECTED"
  | "STALE";

/** 执行记录状态。与后端 ExecutionRunStatus 枚举一致。 */
export type ExecutionRunStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "STALE";

/** 执行产物类型。与后端 ExecutionArtifactType 枚举一致。 */
export type ExecutionArtifactType = "TABLE_CSV" | "CHART_PNG";

/** 候选来源。与分析方案保持一致。 */
export type CandidateSource = "MODEL" | "LOCAL_RULE" | "MANUAL";

/** 代码任务响应体。对应后端 CodeTaskResponse。 */
export interface CodeTask {
  id: string;
  project_id: string;
  analysis_plan_id: string;
  dataset_id: string;
  dataset_version_id: string;
  code: string;
  code_version: number;
  status: CodeTaskStatus;
  candidate_source: CandidateSource;
  created_at: string;
  updated_at: string | null;
  confirmed_at: string | null;
}

/** 代码任务列表响应。 */
export interface CodeTaskListResponse {
  items: CodeTask[];
}

/** 编辑代码任务请求体。对应后端 UpdateCodeTaskRequest。 */
export interface UpdateCodeTaskRequest {
  code: string;
}

/** 执行产物响应体。对应后端 ExecutionArtifactResponse。 */
export interface ExecutionArtifact {
  id: string;
  execution_run_id: string;
  artifact_type: ExecutionArtifactType;
  file_path: string;
  file_size_bytes: number;
  name: string;
  created_at: string;
}

/** 执行记录响应体（含产物列表）。对应后端 ExecutionRunResponse。 */
export interface ExecutionRun {
  id: string;
  project_id: string;
  code_task_id: string;
  dataset_version_id: string;
  code_version: number;
  status: ExecutionRunStatus;
  stdout: string;
  stderr: string;
  exit_code: number | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  artifacts: ExecutionArtifact[];
}

/** 执行记录列表响应。 */
export interface ExecutionRunListResponse {
  items: ExecutionRun[];
}

/** 触发生成代码候选响应。对应后端 GenerateCodeTaskResponse。 */
export interface GenerateCodeTaskResponse {
  job_id: string;
}

/** 触发执行响应。对应后端 ExecuteCodeTaskResponse。 */
export interface ExecuteCodeTaskResponse {
  job_id: string;
  code_task_id: string;
}

/** 完成结果确认响应。对应后端 CompleteExecutionResponse。 */
export interface CompleteExecutionResponse {
  status: string;
}
