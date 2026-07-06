/** 证据卡片 API 调用。 */

import type {
  EvidenceCard,
  EvidenceCardListResponse,
  UpdateEvidenceCardRequest,
  CompleteEvidenceResponse,
} from "./types";
import type { GenerateEvidenceResponse } from "../jobs/types";

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

/** 生成证据卡片候选。返回 job_id 用于轮询。 */
export async function generateEvidence(
  projectId: string,
  sourceId: string
): Promise<GenerateEvidenceResponse> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/sources/${encodeURIComponent(sourceId)}/evidence/generate`,
    { method: "POST" }
  );
  return handle<GenerateEvidenceResponse>(r);
}

/** 获取证据卡片列表。可选 source_id 和 status 筛选。 */
export async function listEvidence(
  projectId: string,
  filters?: { source_id?: string; status?: string }
): Promise<EvidenceCard[]> {
  const params = new URLSearchParams();
  if (filters?.source_id) params.set("source_id", filters.source_id);
  if (filters?.status) params.set("status", filters.status);
  const qs = params.toString();
  const url = qs
    ? `${BASE}/projects/${encodeURIComponent(projectId)}/evidence?${qs}`
    : `${BASE}/projects/${encodeURIComponent(projectId)}/evidence`;
  const r = await fetch(url);
  const data = await handle<EvidenceCardListResponse>(r);
  return data.items;
}

/** 更新证据卡片。只能修改 CANDIDATE 或 STALE 状态的卡片。 */
export async function updateEvidence(
  projectId: string,
  cardId: string,
  payload: UpdateEvidenceCardRequest
): Promise<EvidenceCard> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/evidence/${encodeURIComponent(cardId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  return handle<EvidenceCard>(r);
}

/** 确认证据卡片。只能确认 CANDIDATE 状态的卡片。 */
export async function confirmEvidence(
  projectId: string,
  cardId: string
): Promise<EvidenceCard> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/evidence/${encodeURIComponent(cardId)}/confirm`,
    { method: "POST" }
  );
  return handle<EvidenceCard>(r);
}

/** 拒绝证据卡片。只能拒绝 CANDIDATE 状态的卡片。 */
export async function rejectEvidence(
  projectId: string,
  cardId: string
): Promise<EvidenceCard> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/evidence/${encodeURIComponent(cardId)}/reject`,
    { method: "POST" }
  );
  return handle<EvidenceCard>(r);
}

/** 完成证据确认，推进项目状态到 EVIDENCE_CONFIRMED。 */
export async function completeEvidence(
  projectId: string
): Promise<CompleteEvidenceResponse> {
  const r = await fetch(
    `${BASE}/projects/${encodeURIComponent(projectId)}/evidence/complete`,
    { method: "POST" }
  );
  return handle<CompleteEvidenceResponse>(r);
}
