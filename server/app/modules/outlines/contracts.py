"""大纲与交付物核心合同 (Pydantic schema)。

请求与响应 schema 定义。API 层只做协议映射，业务语义在 service 层。
"""

from pydantic import BaseModel, Field


# --- 大纲章节合同 ---


class OutlineSection(BaseModel):
    """大纲章节。

    source_type 取值：
    - REQUIREMENT：来自实验要求和任务单
    - EVIDENCE：来自证据卡片
    - DATASET：来自数据集字段概览
    - ANALYSIS：来自分析方案
    - EXECUTION：来自执行结果（stdout、表格、图表）
    - SUMMARY：综合总结（由大纲生成器归纳）
    """

    id: str
    title: str
    content: str
    source_type: str
    source_ids: list[str] = Field(default_factory=list)


# --- 请求 ---


class UpdateOutlineRequest(BaseModel):
    """编辑大纲请求。"""

    sections: list[OutlineSection]


# --- 响应 ---


class OutlineResponse(BaseModel):
    """大纲响应。"""

    id: str
    project_id: str
    sections: list[OutlineSection]
    status: str
    candidate_source: str
    version: int
    created_at: str
    updated_at: str | None = None
    confirmed_at: str | None = None


class OutlineListResponse(BaseModel):
    """大纲列表响应。"""

    items: list[OutlineResponse]


class DeliverableResponse(BaseModel):
    """交付物响应。"""

    id: str
    project_id: str
    outline_id: str
    deliverable_type: str
    status: str
    created_at: str
    updated_at: str | None = None


class DeliverableListResponse(BaseModel):
    """交付物列表响应。"""

    items: list[DeliverableResponse]


class DeliverableVersionResponse(BaseModel):
    """交付物版本响应。"""

    id: str
    deliverable_id: str
    version: int
    status: str
    file_path: str | None = None
    file_size_bytes: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    created_at: str


class DeliverableVersionListResponse(BaseModel):
    """交付物版本列表响应。"""

    items: list[DeliverableVersionResponse]


class GenerateOutlineResponse(BaseModel):
    """触发生成大纲候选响应。"""

    job_id: str


class GenerateDeliverableResponse(BaseModel):
    """触发生成交付物响应。

    template_used 表示是否使用了项目级 Word 模板（SPEC 0010）。
    PPT 生成的响应 template_used 固定为 False。
    """

    job_id: str
    deliverable_id: str
    template_used: bool = False


class WordTemplateResponse(BaseModel):
    """Word 模板响应（SPEC 0010）。"""

    id: str
    project_id: str
    original_filename: str
    file_size_bytes: int
    content_hash: str
    created_at: str
    updated_at: str | None = None


class CompleteProjectResponse(BaseModel):
    """完成项目响应。"""

    status: str
