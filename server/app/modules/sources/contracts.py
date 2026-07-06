"""来源与证据核心合同 (Pydantic schema)。"""

from pydantic import BaseModel, Field


# --- API 请求 ---

class UrlSourceRequest(BaseModel):
    """登记公开 URL 请求体。"""

    url: str = Field(..., description="公开 URL 地址")
    title: str | None = Field(default=None, description="可选标题", max_length=500)


class UpdateEvidenceCardRequest(BaseModel):
    """更新证据卡片请求体。"""

    summary: str = Field(..., description="证据摘要")
    evidence_type: str = Field(..., description="证据类型")
    locator: str = Field(..., description="来源位置", max_length=200)
    source_quote: str | None = Field(default=None, description="原文短摘录")


# --- API 响应 ---

class SourceResponse(BaseModel):
    """来源响应体。"""

    id: str
    project_id: str
    source_kind: str
    title: str
    url: str | None
    file_path: str | None
    content_type: str | None
    content_hash: str | None
    status: str
    error_code: str | None
    error_message: str | None
    created_at: str
    fetched_at: str | None
    parsed_at: str | None
    job_id: str | None = None


class SourceListResponse(BaseModel):
    """来源列表响应体。"""

    items: list[SourceResponse]


class ParsedDocumentResponse(BaseModel):
    """解析文档响应体。"""

    id: str
    source_id: str
    project_id: str
    title: str | None
    parsed_text: str
    metadata_json: str | None
    parsed_at: str


class EvidenceCardResponse(BaseModel):
    """证据卡片响应体。"""

    id: str
    project_id: str
    source_id: str
    parsed_document_id: str
    summary: str
    evidence_type: str
    locator: str
    source_quote: str | None
    status: str
    candidate_source: str
    created_at: str
    updated_at: str
    confirmed_at: str | None


class EvidenceCardListResponse(BaseModel):
    """证据卡片列表响应体。"""

    items: list[EvidenceCardResponse]
