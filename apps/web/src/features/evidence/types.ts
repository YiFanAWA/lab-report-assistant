/** 证据卡片类型 — 与后端 EvidenceCardResponse 一致（snake_case）。 */

export type EvidenceType =
  | "BACKGROUND"
  | "METHOD"
  | "RESULT"
  | "CONCLUSION"
  | "LIMITATION"
  | "REFERENCE";

export type EvidenceCardStatus =
  | "CANDIDATE"
  | "CONFIRMED"
  | "REJECTED"
  | "STALE";

export type CandidateSource = "MODEL" | "LOCAL_RULE" | "MANUAL";

/** 证据卡片响应体。 */
export interface EvidenceCard {
  id: string;
  project_id: string;
  source_id: string;
  parsed_document_id: string;
  summary: string;
  evidence_type: EvidenceType;
  locator: string;
  source_quote: string | null;
  status: EvidenceCardStatus;
  candidate_source: CandidateSource;
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
}

/** 证据卡片列表响应。 */
export interface EvidenceCardListResponse {
  items: EvidenceCard[];
}

/** 更新证据卡片请求体。 */
export interface UpdateEvidenceCardRequest {
  summary: string;
  evidence_type: EvidenceType;
  locator: string;
  source_quote: string | null;
}

/** 完成证据确认响应。 */
export interface CompleteEvidenceResponse {
  project_id: string;
  status: string;
}
