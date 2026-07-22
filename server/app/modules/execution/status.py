"""执行核心侧枚举。"""

from enum import Enum


class CodeTaskStatus(str, Enum):
    """代码任务状态。"""

    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    STALE = "STALE"


class ExecutionRunStatus(str, Enum):
    """执行记录状态。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    STALE = "STALE"


class ExecutionArtifactType(str, Enum):
    """执行产物类型。"""

    TABLE_CSV = "TABLE_CSV"
    CHART_PNG = "CHART_PNG"


class CodeChangeType(str, Enum):
    """代码任务变更类型（用于 ChangeRecord）。"""

    CODE_TASK_GENERATED = "CODE_TASK_GENERATED"
    CODE_TASK_UPDATED = "CODE_TASK_UPDATED"
    CODE_TASK_CONFIRMED = "CODE_TASK_CONFIRMED"
    CODE_TASK_REJECTED = "CODE_TASK_REJECTED"
    CODE_TASK_EXECUTED = "CODE_TASK_EXECUTED"


class ExecutionChangeType(str, Enum):
    """执行记录变更类型（用于 ChangeRecord）。"""

    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_SUCCEEDED = "EXECUTION_SUCCEEDED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXECUTIONS_COMPLETED = "EXECUTIONS_COMPLETED"
