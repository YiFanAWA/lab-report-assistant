"""需求侧合同 (Pydantic schema)。"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# --- RequirementTask ---

class RequirementTask(BaseModel):
    title: str
    description: str
    task_type: str  # REQUIRED | RECOMMENDED | OPTIONAL | OUT_OF_SCOPE | UNKNOWN
    reason: str
    source_quote: str | None = None


# --- ReplicationLevel ---

class ReplicationLevel(BaseModel):
    level: str  # L0 | L1 | L2 | L3
    label: str
    supported_in_v1: bool
    reason: str
    suggested_scope: str


# --- RequirementPlan payload ---

class RequirementPlanPayload(BaseModel):
    topic: str
    experiment_type: str
    research_subject: str
    required_tasks: list[RequirementTask] = Field(default_factory=list)
    recommended_tasks: list[RequirementTask] = Field(default_factory=list)
    optional_tasks: list[RequirementTask] = Field(default_factory=list)
    out_of_scope_tasks: list[RequirementTask] = Field(default_factory=list)
    unknown_items: list[RequirementTask] = Field(default_factory=list)
    data_requirements: list[str] = Field(default_factory=list)
    method_requirements: list[str] = Field(default_factory=list)
    chart_requirements: list[str] = Field(default_factory=list)
    report_requirements: list[str] = Field(default_factory=list)
    presentation_requirements: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    replication_level: ReplicationLevel | None = None


# --- API 请求 ---

class TextSourceRequest(BaseModel):
    title: str = Field(..., description="来源标题", max_length=500)
    text: str = Field(..., description="实验要求文本", min_length=1)


class GeneratePlanRequest(BaseModel):
    source_id: str = Field(..., description="要求来源标识")


class UpdatePlanRequest(BaseModel):
    payload: RequirementPlanPayload = Field(..., description="修改后的任务单")


# --- API 响应 ---

class RequirementSourceResponse(BaseModel):
    id: str
    project_id: str
    source_type: str
    title: str
    original_text: str
    original_file_path: str | None
    content_hash: str
    created_at: str


class SourceListResponse(BaseModel):
    items: list[RequirementSourceResponse]


class RequirementPlanResponse(BaseModel):
    id: str
    project_id: str
    source_id: str
    status: str
    payload: RequirementPlanPayload
    candidate_source: str
    created_at: str
    updated_at: str
    confirmed_at: str | None
