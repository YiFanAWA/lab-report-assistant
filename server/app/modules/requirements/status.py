"""需求侧枚举。"""

from enum import Enum


class SourceType(str, Enum):
    PASTED_TEXT = "PASTED_TEXT"
    DOCX_FILE = "DOCX_FILE"
    USER_NOTE = "USER_NOTE"


class PlanStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    STALE = "STALE"


class CandidateSource(str, Enum):
    MODEL = "MODEL"
    LOCAL_RULE = "LOCAL_RULE"
    MANUAL = "MANUAL"


class TaskType(str, Enum):
    REQUIRED = "REQUIRED"
    RECOMMENDED = "RECOMMENDED"
    OPTIONAL = "OPTIONAL"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    UNKNOWN = "UNKNOWN"


class ReplicationLevelEnum(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class ChangeType(str, Enum):
    REQUIREMENT_SOURCE_CREATED = "REQUIREMENT_SOURCE_CREATED"
    REQUIREMENT_PLAN_GENERATED = "REQUIREMENT_PLAN_GENERATED"
    REQUIREMENT_PLAN_UPDATED = "REQUIREMENT_PLAN_UPDATED"
    REQUIREMENT_PLAN_CONFIRMED = "REQUIREMENT_PLAN_CONFIRMED"
