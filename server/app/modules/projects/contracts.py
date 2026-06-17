"""项目合同 (Pydantic schema)。

输入和输出的合同定义，与数据库模型解耦。
"""

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    """创建项目请求体。"""

    name: str = Field(..., description="项目名称", min_length=1, max_length=200)
    topic: str = Field(..., description="课题", min_length=1, max_length=500)


class ProjectResponse(BaseModel):
    """项目响应体。"""

    id: str
    name: str
    topic: str
    status: str
    created_at: str
    updated_at: str


class ProjectListResponse(BaseModel):
    """项目列表响应体。"""

    items: list[ProjectResponse]


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str
    service: str
