/** 资料来源 API 调用 — 复用 handle 错误处理模式。 */

import type {
  Source,
  SourceListResponse,
  CompleteSourcesResponse,
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

/** 登记公开 URL 来源。返回 Source（含 job_id）。 */
export async function createUrlSource(
  projectId: string,
  url: string,
  title: string
): Promise<Source> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/sources/url`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, title }),
    }
  );
  return handle<Source>(r);
}

/** 上传 PDF 文件来源。返回 Source（含 job_id）。 */
export async function createPdfSource(
  projectId: string,
  file: File,
  title: string
): Promise<Source> {
  const body = new FormData();
  body.append("file", file);
  body.append("title", title);
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/sources/pdf`,
    {
      method: "POST",
      body,
    }
  );
  return handle<Source>(r);
}

/** 获取来源列表。 */
export async function listSources(projectId: string): Promise<Source[]> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/sources`
  );
  const data = await handle<SourceListResponse>(r);
  return data.items;
}

/** 获取来源详情。 */
export async function getSource(
  projectId: string,
  sourceId: string
): Promise<Source> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/sources/${encodeURIComponent(sourceId)}`
  );
  return handle<Source>(r);
}

/** 删除来源（软删除，关联证据卡片变为 STALE）。 */
export async function deleteSource(
  projectId: string,
  sourceId: string
): Promise<Source> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/sources/${encodeURIComponent(sourceId)}`,
    { method: "DELETE" }
  );
  return handle<Source>(r);
}

/** 完成来源收集，推进项目状态到 SOURCES_COLLECTED。 */
export async function completeSources(
  projectId: string
): Promise<CompleteSourcesResponse> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/sources/complete`,
    { method: "POST" }
  );
  return handle<CompleteSourcesResponse>(r);
}
