"""大纲与交付物核心合同 (Pydantic schema)。

请求与响应 schema 定义。API 层只做协议映射，业务语义在 service 层。
"""

from pydantic import BaseModel, Field, field_validator

from app.modules.outlines.ppt_workflows import PPT_WORKFLOW_IDS


# --- SPEC 0011 PPT 配置常量 ---

#: PPT 预设主题色板（hex 值集合），用户只能从中选择。
PPT_THEME_COLORS: set[str] = {
    "#2563eb",  # 蓝色（默认推荐）
    "#7c3aed",  # 紫色
    "#16a34a",  # 绿色
    "#dc2626",  # 红色
    "#ea580c",  # 橙色
    "#475569",  # 灰色
}


# --- SPEC 0030 pptxforge 主题预设常量 ---

#: pptxforge 合法主题名枚举（SPEC 0030 方案 B）。
#: 优先级：theme_preset > theme_color 映射 > 默认 SLATE_MINIMALIST。
PPT_THEME_PRESETS: set[str] = {
    "MIDNIGHT_EXECUTIVE",   # 严肃/执行/商务（蓝色系）
    "PACIFIC_DEEP",         # 科学/医学/解剖（青色系）
    "FOREST_MOSS",          # 可持续/生物/农业（绿色系）
    "ROYAL_PLUM",           # 奢华/品牌（紫色系）
    "BERRY_BOLD",           # 奢华/品牌（紫色系，明亮）
    "MONOCHROME_INK",       # 编辑/工程（灰色系）
    "SLATE_MINIMALIST",     # 编辑/工程（灰色系，默认中性）
    "AMBER_EDITORIAL",      # 编辑/消费（暖色系）
    "CORAL_ENERGY",         # 编辑/消费（暖色系，珊瑚）
    "SUNRISE_CITRUS",       # 明亮/营销（黄色系）
}


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
    outline_version: int | None = None
    dataset_version_id: str | None = None
    dataset_version_ids: list[str] = Field(default_factory=list)
    analysis_plan_id: str | None = None
    analysis_plan_ids: list[str] = Field(default_factory=list)
    execution_run_id: str | None = None
    execution_run_ids: list[str] = Field(default_factory=list)
    source_word_version_id: str | None = None
    file_sha256: str | None = None


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


class PptConfig(BaseModel):
    """PPT 生成配置（SPEC 0011 + SPEC 0030 扩展）。

    所有字段可选，未提供时使用默认值。
    配置不持久化，每次生成时传入。

    SPEC 0030 方案 B：新增 theme_preset 字段（pptxforge 主题名）。
    主题优先级：theme_preset > theme_color 映射 > 默认 SLATE_MINIMALIST。
    """

    target_slide_count: int | None = Field(
        default=None,
        description="目标页数（5-20），None 表示使用默认行为",
        ge=5,
        le=20,
    )
    theme_color: str | None = Field(
        default=None,
        description="主题色 hex 值，None 表示使用默认黑色",
    )
    include_charts: bool = Field(
        default=True,
        description="是否包含图表页",
    )
    theme_preset: str | None = Field(
        default=None,
        description="pptxforge 主题名（SPEC 0030），None 时由 theme_color 映射",
    )
    ppt_workflow: str | None = Field(
        default=None,
        description="PPT 工作流模式（SPEC 0032），None 等同于 native_editable",
    )

    @field_validator("theme_preset")
    @classmethod
    def validate_theme_preset(cls, v: str | None) -> str | None:
        """校验 theme_preset 必须为 pptxforge 合法主题名（SPEC 0030 方案 B）。"""
        if v is None:
            return v
        if v not in PPT_THEME_PRESETS:
            raise ValueError(
                f"theme_preset 必须为 pptxforge 合法主题名之一：{sorted(PPT_THEME_PRESETS)}"
            )
        return v

    @field_validator("ppt_workflow")
    @classmethod
    def validate_ppt_workflow(cls, v: str | None) -> str | None:
        """校验 SPEC 0032 PPT 工作流模式。"""
        if v is None:
            return v
        if v not in PPT_WORKFLOW_IDS:
            raise ValueError(
                f"ppt_workflow 必须为合法模式之一：{sorted(PPT_WORKFLOW_IDS)}"
            )
        return v


class GeneratePptRequest(BaseModel):
    """触发 PPT 生成请求（SPEC 0011）。

    所有字段可选，不传时使用默认配置。
    """

    config: PptConfig = Field(default_factory=PptConfig)


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
