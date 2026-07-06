"""后台任务核心合同 (Pydantic schema)。"""

from pydantic import BaseModel, Field


class JobResponse(BaseModel):
    """后台任务响应体。"""

    id: str
    project_id: str
    job_type: str
    status: str
    input_json: str
    output_json: str | None
    error_code: str | None
    error_message: str | None
    retry_count: int
    max_retries: int
    created_at: str
    started_at: str | None
    finished_at: str | None
    next_retry_at: str | None


class JobListResponse(BaseModel):
    """后台任务列表响应体。"""

    items: list[JobResponse] = Field(default_factory=list)
