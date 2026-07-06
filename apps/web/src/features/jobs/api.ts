/** 后台任务 API 调用。 */

import type { BackgroundJob, JobListResponse } from "./types";

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

/** 获取任务详情。 */
export async function fetchJob(
  projectId: string,
  jobId: string
): Promise<BackgroundJob> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/jobs/${encodeURIComponent(jobId)}`
  );
  return handle<BackgroundJob>(r);
}

/** 获取任务列表。 */
export async function listJobs(
  projectId: string,
  filters?: { status?: string; job_type?: string }
): Promise<BackgroundJob[]> {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.job_type) params.set("job_type", filters.job_type);
  const qs = params.toString();
  const url = qs
    ? `${BASE}/projects/${encodeURIComponent(projectId)}/jobs?${qs}`
    : `${BASE}/projects/${encodeURIComponent(projectId)}/jobs`;
  const r = await fetch(url);
  const data = await handle<JobListResponse>(r);
  return data.items;
}
