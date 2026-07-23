/** 大纲与交付物 API 调用 — 复用 handle 错误处理模式。 */

import type {
  Outline,
  OutlineListResponse,
  UpdateOutlineRequest,
  Deliverable,
  DeliverableListResponse,
  DeliverableVersion,
  DeliverableVersionListResponse,
  GenerateOutlineResponse,
  GenerateDeliverableResponse,
  CompleteProjectResponse,
  WordTemplate,
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

/** 触发生成大纲候选。返回 job_id。 */
export async function generateOutline(
  projectId: string
): Promise<GenerateOutlineResponse> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/outline/generate`,
    { method: "POST" }
  );
  return handle<GenerateOutlineResponse>(r);
}

/** 获取大纲列表（支持 status 过滤）。 */
export async function listOutlines(
  projectId: string,
  status?: string
): Promise<Outline[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/outline${qs}`
  );
  const data = await handle<OutlineListResponse>(r);
  return data.items;
}

/** 获取大纲详情。 */
export async function getOutline(
  projectId: string,
  outlineId: string
): Promise<Outline> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/outline/${encodeURIComponent(outlineId)}`
  );
  return handle<Outline>(r);
}

/** 编辑大纲（sections 字段）。 */
export async function updateOutline(
  projectId: string,
  outlineId: string,
  payload: UpdateOutlineRequest
): Promise<Outline> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/outline/${encodeURIComponent(outlineId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  return handle<Outline>(r);
}

/** 确认大纲。 */
export async function confirmOutline(
  projectId: string,
  outlineId: string
): Promise<Outline> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/outline/${encodeURIComponent(outlineId)}/confirm`,
    { method: "POST" }
  );
  return handle<Outline>(r);
}

/** 拒绝大纲。 */
export async function rejectOutline(
  projectId: string,
  outlineId: string
): Promise<Outline> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/outline/${encodeURIComponent(outlineId)}/reject`,
    { method: "POST" }
  );
  return handle<Outline>(r);
}

/** 触发 Word 生成。返回 job_id 和 deliverable_id。 */
export async function generateWord(
  projectId: string,
  outlineId: string
): Promise<GenerateDeliverableResponse> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/outline/${encodeURIComponent(outlineId)}/word/generate`,
    { method: "POST" }
  );
  return handle<GenerateDeliverableResponse>(r);
}

/** 触发 PPT 生成。返回 job_id 和 deliverable_id。 */
export async function generatePpt(
  projectId: string,
  outlineId: string
): Promise<GenerateDeliverableResponse> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/outline/${encodeURIComponent(outlineId)}/ppt/generate`,
    { method: "POST" }
  );
  return handle<GenerateDeliverableResponse>(r);
}

/** 获取交付物列表（含版本）。 */
export async function listDeliverables(
  projectId: string,
  status?: string
): Promise<Deliverable[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/deliverables${qs}`
  );
  const data = await handle<DeliverableListResponse>(r);
  return data.items;
}

/** 获取交付物版本列表。 */
export async function listDeliverableVersions(
  projectId: string,
  deliverableId: string
): Promise<DeliverableVersion[]> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/deliverables/${encodeURIComponent(deliverableId)}/versions`
  );
  const data = await handle<DeliverableVersionListResponse>(r);
  return data.items;
}

/** 构造交付物下载 URL（由浏览器直接访问触发下载）。 */
export function buildDeliverableDownloadUrl(
  projectId: string,
  deliverableId: string,
  versionId: string
): string {
  return `${BASE}/projects/${encodeURIComponent(projectId)}/deliverables/${encodeURIComponent(deliverableId)}/versions/${encodeURIComponent(versionId)}/download`;
}

/** 完成项目，推进状态到 COMPLETED。 */
export async function completeProject(
  projectId: string
): Promise<CompleteProjectResponse> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/complete`,
    { method: "POST" }
  );
  return handle<CompleteProjectResponse>(r);
}

// --- SPEC 0010 Word 模板管理 ---

/** 上传或替换 Word 模板。 */
export async function uploadWordTemplate(
  projectId: string,
  file: File
): Promise<WordTemplate> {
  const body = new FormData();
  body.append("file", file);
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/word-template`,
    {
      method: "POST",
      body,
    }
  );
  return handle<WordTemplate>(r);
}

/** 获取 Word 模板信息。无模板返回 null。 */
export async function getWordTemplate(
  projectId: string
): Promise<WordTemplate | null> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/word-template`
  );
  if (r.status === 200) {
    return r.json() as Promise<WordTemplate | null>;
  }
  return handle<WordTemplate | null>(r);
}

/** 删除 Word 模板。 */
export async function deleteWordTemplate(
  projectId: string
): Promise<void> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/word-template`,
    { method: "DELETE" }
  );
  if (!r.ok) {
    let detail: any = null;
    try {
      detail = await r.json();
    } catch {
      detail = { message: `请求失败 (${r.status})` };
    }
    throw detail?.error ?? detail ?? { message: r.statusText };
  }
}

/** 构造 Word 模板下载 URL。 */
export function buildWordTemplateDownloadUrl(projectId: string): string {
  return `${BASE}/projects/${encodeURIComponent(projectId)}/word-template/download`;
}
