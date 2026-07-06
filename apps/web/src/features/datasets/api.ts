/** 数据集 API 调用 — 复用 handle 错误处理模式。 */

import type {
  Dataset,
  DatasetListResponse,
  DatasetVersion,
  DatasetVersionListResponse,
  CompleteDatasetsResponse,
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

/** 上传 CSV/Excel 文件数据集。返回 Dataset（含 job_id）。 */
export async function uploadDataset(
  projectId: string,
  file: File,
  title: string,
  description?: string
): Promise<Dataset> {
  const body = new FormData();
  body.append("file", file);
  body.append("title", title);
  if (description) body.append("description", description);
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/datasets/upload`,
    {
      method: "POST",
      body,
    }
  );
  return handle<Dataset>(r);
}

/** 登记公开 CSV/Excel URL 数据集。返回 Dataset（含 job_id）。 */
export async function createUrlDataset(
  projectId: string,
  url: string,
  title: string,
  description?: string
): Promise<Dataset> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/datasets/url`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, title, description }),
    }
  );
  return handle<Dataset>(r);
}

/** 获取数据集列表。 */
export async function listDatasets(projectId: string): Promise<Dataset[]> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/datasets`
  );
  const data = await handle<DatasetListResponse>(r);
  return data.items;
}

/** 获取数据集详情。 */
export async function getDataset(
  projectId: string,
  datasetId: string
): Promise<Dataset> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/datasets/${encodeURIComponent(datasetId)}`
  );
  return handle<Dataset>(r);
}

/** 获取数据集版本列表。 */
export async function listDatasetVersions(
  projectId: string,
  datasetId: string
): Promise<DatasetVersion[]> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/datasets/${encodeURIComponent(datasetId)}/versions`
  );
  const data = await handle<DatasetVersionListResponse>(r);
  return data.items;
}

/** 软删除数据集。关联分析方案变 STALE。 */
export async function deleteDataset(
  projectId: string,
  datasetId: string
): Promise<Dataset> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/datasets/${encodeURIComponent(datasetId)}`,
    { method: "DELETE" }
  );
  return handle<Dataset>(r);
}

/** 重新上传数据集（创建新版本）。返回 Dataset（含 job_id）。 */
export async function reuploadDataset(
  projectId: string,
  datasetId: string,
  file: File
): Promise<Dataset> {
  const body = new FormData();
  body.append("file", file);
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/datasets/${encodeURIComponent(datasetId)}/reupload`,
    {
      method: "POST",
      body,
    }
  );
  return handle<Dataset>(r);
}

/** 完成数据集收集，推进项目状态到 DATASET_READY。 */
export async function completeDatasets(
  projectId: string
): Promise<CompleteDatasetsResponse> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/datasets/complete`,
    { method: "POST" }
  );
  return handle<CompleteDatasetsResponse>(r);
}
