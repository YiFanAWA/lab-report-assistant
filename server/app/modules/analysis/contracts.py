"""分析方案核心合同 (Pydantic schema)。"""

from pydantic import BaseModel, Field


# --- API 请求 ---


class UpdateAnalysisPlanRequest(BaseModel):
    """更新分析方案请求体。

    三个 plan 字段均为 JSON 字符串，可选更新。
    """

    cleaning_plan: str | None = Field(default=None, description="清洗方案 JSON 字符串")
    analysis_plan: str | None = Field(default=None, description="分析方案 JSON 字符串")
    chart_plan: str | None = Field(default=None, description="图表方案 JSON 字符串")


# --- API 响应 ---


class AnalysisPlanResponse(BaseModel):
    """分析方案响应体。"""

    id: str
    project_id: str
    dataset_id: str
    dataset_version_id: str
    cleaning_plan: str  # JSON 字符串
    analysis_plan: str  # JSON 字符串
    chart_plan: str  # JSON 字符串
    status: str
    candidate_source: str
    created_at: str
    updated_at: str | None
    confirmed_at: str | None


class AnalysisPlanListResponse(BaseModel):
    """分析方案列表响应体。"""

    items: list[AnalysisPlanResponse]


class CompleteAnalysisResponse(BaseModel):
    """完成分析方案确认响应体。"""

    status: str
