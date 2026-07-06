"""数据集侧枚举。"""

from enum import Enum


class DatasetKind(str, Enum):
    """数据集来源类型。"""

    FILE = "FILE"  # 本地上传
    URL = "URL"  # 公开 URL 下载


class DatasetStatus(str, Enum):
    """数据集状态。"""

    PENDING = "PENDING"  # 等待解析
    READY = "READY"  # 至少一个版本 PARSED
    FAILED = "FAILED"  # 所有版本都失败
    DELETED = "DELETED"  # 软删除


class DatasetVersionStatus(str, Enum):
    """数据集版本状态。"""

    PENDING = "PENDING"
    PARSING = "PARSING"
    PARSED = "PARSED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"  # 被新版本取代


class DatasetChangeType(str, Enum):
    """数据集相关变更记录类型。"""

    DATASET_CREATED = "DATASET_CREATED"
    DATASET_PARSED = "DATASET_PARSED"
    DATASET_REUPLOADED = "DATASET_REUPLOADED"
    DATASET_DELETED = "DATASET_DELETED"
    DATASETS_COMPLETED = "DATASETS_COMPLETED"
