import type {
  RequirementSource,
  SourceListResponse,
  RequirementPlanResponse,
  RequirementPlanPayload,
} from "./types";
import { streamSSE, type SSEEvent } from "../../shared/stream-sse";
import { STREAMING_BASE } from "../../shared/api-base";

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

// --- Sources ---

export async function addTextSource(
  projectId: string,
  title: string,
  text: string
): Promise<RequirementSource> {
  const r = await fetch(`${BASE}/projects/${encodeURIComponent(projectId)}/requirements/sources/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, text }),
  });
  return handle<RequirementSource>(r);
}

export async function addDocxSource(
  projectId: string,
  title: string,
  file: File
): Promise<RequirementSource> {
  const body = new FormData();
  body.append("file", file);
  body.append("title", title);
  const r = await fetch(`${BASE}/projects/${encodeURIComponent(projectId)}/requirements/sources/docx`, {
    method: "POST",
    body,
  });
  return handle<RequirementSource>(r);
}

export async function fetchSources(projectId: string): Promise<RequirementSource[]> {
  const r = await fetch(`${BASE}/projects/${encodeURIComponent(projectId)}/requirements/sources`);
  const data = await handle<SourceListResponse>(r);
  return data.items;
}

// --- Plan ---

export async function generatePlan(
  projectId: string,
  sourceId: string
): Promise<RequirementPlanResponse> {
  const r = await fetch(`${BASE}/projects/${encodeURIComponent(projectId)}/requirements/plans/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_id: sourceId }),
  });
  return handle<RequirementPlanResponse>(r);
}

/**
 * 流式生成任务单（SPEC 0018）。
 *
 * 返回异步迭代器，逐个 yield SSE 事件。
 * 调用方负责处理 chunk / done / error 事件。
 *
 * @param projectId 项目 ID
 * @param sourceId 要求来源 ID
 * @param signal 可选的 AbortSignal，用于取消流式
 */
export async function* streamGeneratePlan(
  projectId: string,
  sourceId: string,
  signal?: AbortSignal
): AsyncGenerator<SSEEvent, void, unknown> {
  // 流式端点使用 STREAMING_BASE：dev 直连后端绕过 Vite 代理对 chunked SSE 的缓冲
  const url = `${STREAMING_BASE}/projects/${encodeURIComponent(projectId)}/requirements/plans/stream-generate`;
  yield* streamSSE(url, { source_id: sourceId }, signal);
}

export async function fetchCurrentPlan(projectId: string): Promise<RequirementPlanResponse> {
  const r = await fetch(`${BASE}/projects/${encodeURIComponent(projectId)}/requirements/plan`);
  return handle<RequirementPlanResponse>(r);
}

export async function confirmPlan(projectId: string, planId: string): Promise<RequirementPlanResponse> {
  const r = await fetch(`${BASE}/projects/${encodeURIComponent(projectId)}/requirements/plans/${encodeURIComponent(planId)}/confirm`, {
    method: "POST",
  });
  return handle<RequirementPlanResponse>(r);
}

export async function updatePlan(
  projectId: string,
  planId: string,
  payload: RequirementPlanPayload
): Promise<RequirementPlanResponse> {
  const r = await fetch(`${BASE}/projects/${encodeURIComponent(projectId)}/requirements/plans/${encodeURIComponent(planId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payload }),
  });
  return handle<RequirementPlanResponse>(r);
}
