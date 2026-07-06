"""数据集核心合同 (Pydantic schema)。"""

from pydantic import BaseModel, Field


# --- API 请求 ---


class DatasetUploadRequest(BaseModel):
    """上传 CSV/Excel 数据集请求体（用于 reupload，初次上传用 multipart）。"""

    title: str | None = Field(default=None, description="可选标题", max_length=500)
    description: str | None = Field(default=None, description="可选描述")


class DatasetUrlRequest(BaseModel):
    """登记公开 CSV/Excel URL 请求体。"""

    url: str = Field(..., description="公开 URL 地址")
    title: str | None = Field(default=None, description="可选标题", max_length=500)
    description: str | None = Field(default=None, description="可选描述")


# --- API 响应 ---


class DatasetResponse(BaseModel):
    """数据集响应体。"""

    id: str
    project_id: str
    dataset_kind: str
    title: str
    description: str | None
    status: str
    error_code: str | None
    error_message: str | None
    created_at: str
    updated_at: str | None
    job_id: str | None = None  # 关联的最新任务


class DatasetListResponse(BaseModel):
    """数据集列表响应体。"""

    items: list[DatasetResponse]


class DatasetVersionResponse(BaseModel):
    """数据集版本响应体。"""

    id: str
    dataset_id: str
    project_id: str
    version: int
    status: str
    file_path: str
    file_size_bytes: int
    row_count: int | None
    column_count: int | None
    profile_json: str | None  # JSON 字符串
    error_code: str | None
    error_message: str | None
    created_at: str
    parsed_at: str | None


class DatasetVersionListResponse(BaseModel):
    """数据集版本列表响应体。"""

    items: list[DatasetVersionResponse]


class CompleteDatasetsResponse(BaseModel):
    """完成数据集收集响应体。"""

    status: str
