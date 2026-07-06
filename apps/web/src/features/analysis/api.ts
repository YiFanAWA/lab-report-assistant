/** 分析方案 API 调用 — 复用 handle 错误处理模式。 */

import type {
  AnalysisPlan,
  AnalysisPlanListResponse,
  UpdateAnalysisPlanRequest,
  CompleteAnalysisResponse,
} from "./types";
import type { GenerateAnalysisResponse } from "../jobs/types";

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

/** 触发生成分析方案候选。返回 job_id 用于轮询。 */
export async function generateAnalysisPlan(
  projectId: string,
  datasetId: string
): Promise<GenerateAnalysisResponse> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/datasets/${encodeURIComponent(datasetId)}/analysis/generate`,
    { method: "POST" }
  );
  return handle<GenerateAnalysisResponse>(r);
}

/** 获取分析方案列表。可选 dataset_id 和 status 筛选。 */
export async function listAnalysisPlans(
  projectId: string,
  filters?: { dataset_id?: string; status?: string }
): Promise<AnalysisPlan[]> {
  const params = new URLSearchParams();
  if (filters?.dataset_id) params.set("dataset_id", filters.dataset_id);
  if (filters?.status) params.set("status", filters.status);
  const qs = params.toString();
  const url = qs
    ? `${BASE}/projects/${encodeURIComponent(projectId)}/analysis?${qs}`
    : `${BASE}/projects/${encodeURIComponent(projectId)}/analysis`;
  const r = await fetch(url);
  const data = await handle<AnalysisPlanListResponse>(r);
  return data.items;
}

/** 获取分析方案详情。 */
export async function getAnalysisPlan(
  projectId: string,
  planId: string
): Promise<AnalysisPlan> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/analysis/${encodeURIComponent(planId)}`
  );
  return handle<AnalysisPlan>(r);
}

/** 编辑分析方案。只能修改 CANDIDATE 或 STALE 状态；CONFIRMED 编辑后回到 CANDIDATE。 */
export async function updateAnalysisPlan(
  projectId: string,
  planId: string,
  payload: UpdateAnalysisPlanRequest
): Promise<AnalysisPlan> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/analysis/${encodeURIComponent(planId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  return handle<AnalysisPlan>(r);
}

/** 确认分析方案。只能确认 CANDIDATE 状态。 */
export async function confirmAnalysisPlan(
  projectId: string,
  planId: string
): Promise<AnalysisPlan> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/analysis/${encodeURIComponent(planId)}/confirm`,
    { method: "POST" }
  );
  return handle<AnalysisPlan>(r);
}

/** 拒绝分析方案。只能拒绝 CANDIDATE 状态。 */
export async function rejectAnalysisPlan(
  projectId: string,
  planId: string
): Promise<AnalysisPlan> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/analysis/${encodeURIComponent(planId)}/reject`,
    { method: "POST" }
  );
  return handle<AnalysisPlan>(r);
}

/** 完成分析方案确认，推进项目状态到 ANALYSIS_CONFIRMED。 */
export async function completeAnalysis(
  projectId: string
): Promise<CompleteAnalysisResponse> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/analysis/complete`,
    { method: "POST" }
  );
  return handle<CompleteAnalysisResponse>(r);
}
