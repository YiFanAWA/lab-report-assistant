"""项目合同 (Pydantic schema)。

输入和输出的合同定义，与数据库模型解耦。
"""

from typing import Literal

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


class WorkspaceBlockingReason(BaseModel):
    """阶段被阻断、失败或锁定的结构化原因。"""

    code: str
    message: str
    source: str
    kind: Literal["LOCKED", "BLOCKED", "FAILED"] = "BLOCKED"
    display_message: str | None = None


class WorkspaceProjectSummary(BaseModel):
    """工作台投影中的项目摘要。"""

    id: str
    name: str
    topic: str
    status: str
    status_label: str
    updated_at: str


class WorkspaceStageProjection(BaseModel):
    """兼容客户端使用的单个工作区阶段投影。"""

    id: str
    label: str
    route: str
    state: str
    phase_id: str
    phase_label: str
    is_substep: bool = False
    blocking_reasons: list[WorkspaceBlockingReason] = Field(
        default_factory=list
    )


class WorkspaceProgressAction(BaseModel):
    """工作区可展示动作；command_id 只是稳定标识，不代表通用命令总线。"""

    id: str
    kind: Literal["NAVIGATE", "COMMAND"]
    label: str
    description: str
    enabled: bool
    disabled_reason: WorkspaceBlockingReason | None = None
    route: str | None = None
    command_id: str | None = None


class WorkspaceProgressDisplay(BaseModel):
    """给学生展示的状态与下一步文案。"""

    status_label: str
    next_step_text: str


class WorkspaceProgressStep(BaseModel):
    """规范合同中的工作区步骤。"""

    id: str
    label: str
    description: str
    is_substep: bool = False
    status: Literal["LOCKED", "READY", "IN_PROGRESS", "BLOCKED", "FAILED", "COMPLETED"]
    is_open: bool
    open_reason: WorkspaceBlockingReason | None = None
    blocking_reasons: list[WorkspaceBlockingReason] = Field(default_factory=list)
    display: WorkspaceProgressDisplay
    route: str
    command_id: str
    actions: list[WorkspaceProgressAction] = Field(default_factory=list)
    recovery_action: WorkspaceProgressAction | None = None


class WorkspaceProgressPhase(BaseModel):
    """规范合同中的顶层阶段，资料与证据以同一阶段承载子步骤。"""

    id: str
    label: str
    description: str
    status: Literal["LOCKED", "READY", "IN_PROGRESS", "BLOCKED", "FAILED", "COMPLETED"]
    is_open: bool
    open_reason: WorkspaceBlockingReason | None = None
    blocking_reasons: list[WorkspaceBlockingReason] = Field(default_factory=list)
    display: WorkspaceProgressDisplay
    steps: list[WorkspaceProgressStep] = Field(default_factory=list)
    actions: list[WorkspaceProgressAction] = Field(default_factory=list)


class WorkspaceProgressCurrent(BaseModel):
    """当前项目所在的规范阶段和步骤。"""

    phase_id: str
    phase_label: str
    step_id: str
    label: str
    status: Literal["LOCKED", "READY", "IN_PROGRESS", "BLOCKED", "FAILED", "COMPLETED"]


class WorkspaceNextAction(BaseModel):
    """兼容客户端使用的下一步动作。"""

    stage_id: str
    label: str
    route: str
    reason: str


class ProjectProgressProjection(BaseModel):
    """统一工作台壳层消费的项目进度规范投影。

    current_stage、next_action、stages 是旧客户端兼容投影，
    不作为新的业务语义 owner。
    """

    project_id: str
    project: WorkspaceProjectSummary
    current: WorkspaceProgressCurrent
    phases: list[WorkspaceProgressPhase] = Field(default_factory=list)
    recommended_next_action: WorkspaceProgressAction | None = None

    # 兼容字段继续保留在同一响应中。
    current_stage: WorkspaceStageProjection
    next_action: WorkspaceNextAction | None = None
    stages: list[WorkspaceStageProjection]
    projection_generated_at: str


# 旧 Python 导入名继续有效；HTTP 路由仍只有一个 workspace-projection 接口。
WorkspaceProjectionResponse = ProjectProgressProjection


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str
    service: str