/** 执行核心侧 API 调用 — 复用 handle 错误处理模式。

覆盖 11 个端点：
- code_tasks（7 个）：generate/list/get/update/confirm/reject/execute
- execution_runs（4 个）：list/get/download/complete
 */

import type {
  CodeTask,
  CodeTaskListResponse,
  UpdateCodeTaskRequest,
  ExecutionRun,
  ExecutionRunListResponse,
  GenerateCodeTaskResponse,
  ExecuteCodeTaskResponse,
  CompleteExecutionResponse,
} from "./types";

const BASE = "/api";

async function handle<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let detail: any = null;
    try {
      detail = await r.json();
    } catch {
      detail = { message: `请求失败 (${r.status})` };
    }
    throw detail?.error ?? detail ?? { message: r.statusText };
  }
  return r.json() as Promise<T>;
}

// --- 代码任务（7 个端点） ---

/** 触发生成代码候选。返回 job_id 用于轮询。 */
export async function generateCodeTask(
  projectId: string,
  planId: string
): Promise<GenerateCodeTaskResponse> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/analysis/${encodeURIComponent(planId)}/code/generate`,
    { method: "POST" }
  );
  return handle<GenerateCodeTaskResponse>(r);
}

/** 获取代码任务列表（支持 status 过滤）。 */
export async function listCodeTasks(
  projectId: string,
  status?: string
): Promise<CodeTask[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/code-tasks${qs}`
  );
  const data = await handle<CodeTaskListResponse>(r);
  return data.items;
}

/** 获取代码任务详情。 */
export async function getCodeTask(
  projectId: string,
  taskId: string
): Promise<CodeTask> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/code-tasks/${encodeURIComponent(taskId)}`
  );
  return handle<CodeTask>(r);
}

/** 编辑代码任务（code 字段）。只能修改 CANDIDATE 或 STALE 状态。 */
export async function updateCodeTask(
  projectId: string,
  taskId: string,
  payload: UpdateCodeTaskRequest
): Promise<CodeTask> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/code-tasks/${encodeURIComponent(taskId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  return handle<CodeTask>(r);
}

/** 确认代码任务。只能确认 CANDIDATE 状态。 */
export async function confirmCodeTask(
  projectId: string,
  taskId: string
): Promise<CodeTask> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/code-tasks/${encodeURIComponent(taskId)}/confirm`,
    { method: "POST" }
  );
  return handle<CodeTask>(r);
}

/** 拒绝代码任务。只能拒绝 CANDIDATE 状态。 */
export async function rejectCodeTask(
  projectId: string,
  taskId: string
): Promise<CodeTask> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/code-tasks/${encodeURIComponent(taskId)}/reject`,
    { method: "POST" }
  );
  return handle<CodeTask>(r);
}

/** 触发代码执行（前置：CodeTask CONFIRMED）。返回 job_id 和 code_task_id。 */
export async function executeCodeTask(
  projectId: string,
  taskId: string
): Promise<ExecuteCodeTaskResponse> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/code-tasks/${encodeURIComponent(taskId)}/execute`,
    { method: "POST" }
  );
  return handle<ExecuteCodeTaskResponse>(r);
}

// --- 执行记录（4 个端点） ---

/** 获取执行记录列表（含 artifacts，支持 status 过滤）。 */
export async function listExecutionRuns(
  projectId: string,
  status?: string
): Promise<ExecutionRun[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/execution-runs${qs}`
  );
  const data = await handle<ExecutionRunListResponse>(r);
  return data.items;
}

/** 获取执行记录详情（含 stdout/stderr/artifacts）。 */
export async function getExecutionRun(
  projectId: string,
  runId: string
): Promise<ExecutionRun> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/execution-runs/${encodeURIComponent(runId)}`
  );
  return handle<ExecutionRun>(r);
}

/** 构造执行产物下载 URL（由浏览器直接访问触发下载）。 */
export function buildArtifactDownloadUrl(
  projectId: string,
  runId: string,
  artifactId: string
): string {
  return `${BASE}/projects/${encodeURIComponent(projectId)}/execution-runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}`;
}

/** 完成结果确认，推进项目状态到 RESULT_CONFIRMED。 */
export async function completeExecution(
  projectId: string
): Promise<CompleteExecutionResponse> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/execution-runs/complete`,
    { method: "POST" }
  );
  return handle<CompleteExecutionResponse>(r);
}
