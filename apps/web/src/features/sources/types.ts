export type SourceKind = "PUBLIC_URL" | "LOCAL_FILE";
export type SourceType = "WEB_PAGE" | "PDF" | "DOCX" | "TXT" | "CSV" | "EXCEL" | "UNKNOWN";
export type CollectionStatus = "REGISTERED" | "FETCHED" | "PARSED" | "BLOCKED" | "FAILED" | "UNSUPPORTED";
export type EvidenceStatus = "CANDIDATE" | "CONFIRMED" | "REJECTED" | "STALE";
export type EvidenceType = "BACKGROUND" | "METHOD" | "DATA_SOURCE" | "METRIC" | "RESULT" | "LIMITATION" | "DEFINITION" | "REFERENCE";

export interface SourceRecord {
  id: string;
  project_id: string;
  source_kind: SourceKind;
  source_type: SourceType;
  title: string;
  url: string | null;
  original_file_path: string | null;
  content_hash: string | null;
  collection_status: CollectionStatus;
  access_reason: string | null;
  content_type: string | null;
  size_bytes: number | null;
  created_at: string;
  updated_at: string;
}

export interface ParsedDocument {
  id: string;
  project_id: string;
  source_id: string;
  parser_type: "HTML_TEXT" | "PDF_TEXT" | "DOCX_TEXT" | "TXT_TEXT";
  title: string;
  parsed_text: string;
  text_hash: string;
  location_map_json: string | null;
  parse_status: "SUCCEEDED" | "FAILED" | "UNSUPPORTED";
  parse_error_code: string | null;
  created_at: string;
}

export interface EvidenceCard {
  id: string;
  project_id: string;
  source_id: string;
  parsed_document_id: string;
  status: EvidenceStatus;
  evidence_type: EvidenceType;
  summary: string;
  source_quote: string;
  location_label: string;
  relevance_to_requirement: string;
  candidate_source: "LOCAL_RULE" | "MODEL" | "MANUAL";
  created_at: string;
  confirmed_at: string | null;
}

export interface EvidencePatch {
  summary?: string;
  evidence_type?: EvidenceType;
  relevance_to_requirement?: string;
}

export interface SourceListResponse {
  items: SourceRecord[];
}

export interface EvidenceListResponse {
  items: EvidenceCard[];
}
