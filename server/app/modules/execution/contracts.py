"""执行核心侧 Pydantic 合同。

请求与响应 schema 定义。API 层只做协议映射，业务语义在 service 层。
"""

from pydantic import BaseModel


# --- 请求 ---


class UpdateCodeTaskRequest(BaseModel):
    """编辑代码任务请求。"""

    code: str


# --- 响应 ---


class CodeTaskResponse(BaseModel):
    """代码任务响应。"""

    id: str
    project_id: str
    analysis_plan_id: str
    dataset_id: str
    dataset_version_id: str
    code: str
    code_version: int
    status: str
    candidate_source: str
    created_at: str
    updated_at: str | None = None
    confirmed_at: str | None = None


class CodeTaskListResponse(BaseModel):
    """代码任务列表响应。"""

    items: list[CodeTaskResponse]


class ExecutionArtifactResponse(BaseModel):
    """执行产物响应。"""

    id: str
    execution_run_id: str
    artifact_type: str
    file_path: str
    file_size_bytes: int
    name: str
    created_at: str


class ExecutionRunResponse(BaseModel):
    """执行记录响应（含产物列表）。"""

    id: str
    project_id: str
    code_task_id: str
    dataset_version_id: str
    code_version: int
    status: str
    stdout: str
    stderr: str
    exit_code: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: str
    artifacts: list[ExecutionArtifactResponse] = []


class ExecutionRunListResponse(BaseModel):
    """执行记录列表响应。"""

    items: list[ExecutionRunResponse]


class CompleteExecutionResponse(BaseModel):
    """完成结果确认响应。"""

    status: str


class ExecuteCodeTaskResponse(BaseModel):
    """触发执行响应。"""

    job_id: str
    code_task_id: str


class GenerateCodeTaskResponse(BaseModel):
    """触发生成代码候选响应。"""

    job_id: str
