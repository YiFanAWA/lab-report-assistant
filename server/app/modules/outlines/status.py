"""大纲与交付物核心枚举。

SPEC 0006：限定统一实验大纲、Word/PPT 交付物生成、
Deliverable/DeliverableVersion 核心合同、状态推进到 COMPLETED。
"""

from enum import Enum


class OutlineStatus(str, Enum):
    """大纲状态。"""

    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    STALE = "STALE"


class DeliverableStatus(str, Enum):
    """交付物状态。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    STALE = "STALE"


class DeliverableType(str, Enum):
    """交付物类型。"""

    WORD = "WORD"
    PPT = "PPT"


class DeliverableVersionStatus(str, Enum):
    """交付物版本状态。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class OutlineChangeType(str, Enum):
    """大纲变更类型（用于 ChangeRecord）。"""

    OUTLINE_GENERATED = "OUTLINE_GENERATED"
    OUTLINE_UPDATED = "OUTLINE_UPDATED"
    OUTLINE_CONFIRMED = "OUTLINE_CONFIRMED"
    OUTLINE_REJECTED = "OUTLINE_REJECTED"


class DeliverableChangeType(str, Enum):
    """交付物变更类型（用于 ChangeRecord）。"""

    WORD_GENERATED = "WORD_GENERATED"
    PPT_GENERATED = "PPT_GENERATED"
    DELIVERABLE_SUCCEEDED = "DELIVERABLE_SUCCEEDED"
    DELIVERABLE_FAILED = "DELIVERABLE_FAILED"
    PROJECT_COMPLETED = "PROJECT_COMPLETED"
