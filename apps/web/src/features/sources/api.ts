import type { ApiError } from "../../shared/types";
import type {
  EvidenceCard,
  EvidenceListResponse,
  EvidencePatch,
  EvidenceStatus,
  ParsedDocument,
  SourceListResponse,
  SourceRecord,
} from "./types";

const BASE = "/api";

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let body: ApiError | null = null;
    try {
      body = (await response.json()) as ApiError;
    } catch {
      // 非 JSON 错误由统一回退文案承接。
    }
    throw body?.error ?? {
      code: "UNKNOWN",
      message: `请求失败 (${response.status})`,
      field: null,
    };
  }
  return response.json() as Promise<T>;
}

function projectBase(projectId: string) {
  return `${BASE}/projects/${encodeURIComponent(projectId)}`;
}

export async function fetchSourceRecords(projectId: string): Promise<SourceRecord[]> {
  const response = await fetch(`${projectBase(projectId)}/sources`);
  return (await handle<SourceListResponse>(response)).items;
}

export async function addUrlSource(projectId: string, url: string, title: string): Promise<SourceRecord> {
  const response = await fetch(`${projectBase(projectId)}/sources/urls`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, title }),
  });
  return handle<SourceRecord>(response);
}

export async function uploadSourceFile(projectId: string, file: File, title: string): Promise<SourceRecord> {
  const body = new FormData();
  body.append("file", file);
  body.append("title", title);
  const response = await fetch(`${projectBase(projectId)}/sources/files`, {
    method: "POST",
    body,
  });
  return handle<SourceRecord>(response);
}

export async function parseSource(projectId: string, sourceId: string): Promise<ParsedDocument> {
  const response = await fetch(`${projectBase(projectId)}/sources/${encodeURIComponent(sourceId)}/parse`, {
    method: "POST",
  });
  return handle<ParsedDocument>(response);
}

export async function fetchParsedDocument(projectId: string, sourceId: string): Promise<ParsedDocument> {
  const response = await fetch(`${projectBase(projectId)}/sources/${encodeURIComponent(sourceId)}/parsed-document`);
  return handle<ParsedDocument>(response);
}

export async function generateEvidence(projectId: string, sourceId: string): Promise<EvidenceCard[]> {
  const response = await fetch(`${projectBase(projectId)}/sources/${encodeURIComponent(sourceId)}/evidence/generate`, {
    method: "POST",
  });
  return (await handle<EvidenceListResponse>(response)).items;
}

export async function fetchEvidence(
  projectId: string,
  filters: { sourceId?: string; status?: EvidenceStatus } = {}
): Promise<EvidenceCard[]> {
  const params = new URLSearchParams();
  if (filters.sourceId) params.set("source_id", filters.sourceId);
  if (filters.status) params.set("status", filters.status);
  const query = params.size ? `?${params.toString()}` : "";
  const response = await fetch(`${projectBase(projectId)}/evidence${query}`);
  return (await handle<EvidenceListResponse>(response)).items;
}

export async function updateEvidence(
  projectId: string,
  evidenceId: string,
  patch: EvidencePatch
): Promise<EvidenceCard> {
  const response = await fetch(`${projectBase(projectId)}/evidence/${encodeURIComponent(evidenceId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return handle<EvidenceCard>(response);
}

export async function confirmEvidence(projectId: string, evidenceId: string): Promise<EvidenceCard> {
  const response = await fetch(`${projectBase(projectId)}/evidence/${encodeURIComponent(evidenceId)}/confirm`, {
    method: "POST",
  });
  return handle<EvidenceCard>(response);
}

export async function rejectEvidence(projectId: string, evidenceId: string): Promise<EvidenceCard> {
  const response = await fetch(`${projectBase(projectId)}/evidence/${encodeURIComponent(evidenceId)}/reject`, {
    method: "POST",
  });
  return handle<EvidenceCard>(response);
}
