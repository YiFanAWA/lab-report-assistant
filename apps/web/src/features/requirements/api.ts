import type {
  RequirementSource,
  SourceListResponse,
  RequirementPlanResponse,
  RequirementPlanPayload,
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
