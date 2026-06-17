import type { Project, ProjectCreateRequest, ProjectListResponse, ApiError } from "../../shared/types";

const BASE = "/api";

async function handleResponse<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let body: ApiError | null = null;
    try {
      body = await resp.json();
    } catch {
      // response not JSON — use status text
    }
    throw body?.error ?? { code: "UNKNOWN", message: `请求失败 (${resp.status})` };
  }
  return resp.json() as Promise<T>;
}

export async function fetchProjects(): Promise<Project[]> {
  const resp = await fetch(`${BASE}/projects`);
  const data = await handleResponse<ProjectListResponse>(resp);
  return data.items;
}

export async function fetchProject(id: string): Promise<Project> {
  const resp = await fetch(`${BASE}/projects/${encodeURIComponent(id)}`);
  return handleResponse<Project>(resp);
}

export async function createProject(req: ProjectCreateRequest): Promise<Project> {
  const resp = await fetch(`${BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<Project>(resp);
}
