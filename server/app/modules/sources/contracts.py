"""来源与证据侧合同 (Pydantic schema)。"""

from pydantic import BaseModel, Field
from app.modules.sources.status import EvidenceType, ParserType


# --- SourceRecord ---

class SourceCreateRequest(BaseModel):
    url: str = Field(..., description="公开 URL", max_length=2000)
    title: str = Field(default="", description="来源标题", max_length=500)


class SourceRecordResponse(BaseModel):
    id: str
    project_id: str
    source_kind: str
    source_type: str
    title: str
    url: str | None
    original_file_path: str | None
    content_hash: str | None
    collection_status: str
    access_reason: str | None
    content_type: str | None
    size_bytes: int | None
    created_at: str
    updated_at: str


class SourceListResponse(BaseModel):
    items: list[SourceRecordResponse]


# --- ParsedDocument ---

class ParsedDocumentResponse(BaseModel):
    id: str
    project_id: str
    source_id: str
    parser_type: str
    title: str
    parsed_text: str
    text_hash: str
    location_map_json: str | None
    parse_status: str
    parse_error_code: str | None
    created_at: str


# --- EvidenceCard ---

class EvidenceCardResponse(BaseModel):
    id: str
    project_id: str
    source_id: str
    parsed_document_id: str
    status: str
    evidence_type: str
    summary: str
    source_quote: str
    location_label: str
    relevance_to_requirement: str
    candidate_source: str
    created_at: str
    confirmed_at: str | None


class EvidenceUpdateRequest(BaseModel):
    summary: str | None = Field(default=None, min_length=1, max_length=2000, description="证据摘要")
    evidence_type: EvidenceType | None = Field(default=None, description="证据类型")
    relevance_to_requirement: str | None = Field(default=None, min_length=1, max_length=1000, description="相关性")


class EvidenceListResponse(BaseModel):
    items: list[EvidenceCardResponse]


# --- Evidence Draft 合同 ---

class EvidenceDraftCandidate(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    source_quote: str = Field(min_length=1, max_length=2000)
    evidence_type: EvidenceType
    location_label: str = Field(min_length=1, max_length=500)
    relevance_to_requirement: str = Field(min_length=1, max_length=1000)


class EvidenceDraftDocument(BaseModel):
    parsed_text: str
    title: str
    parser_type: ParserType
    location_map: dict[str, object]
