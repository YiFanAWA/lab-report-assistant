"""交付物审阅投影的兼容入口。

交付物审阅的业务判断唯一由 :mod:`projection` 负责。本模块保留原有
``service.build_delivery_review`` 导入路径，避免 API 和既有测试发生无谓
变更，但不再维护第二套状态、质量门禁或 provenance 逻辑。
"""

from app.modules.delivery_review.projection import build_delivery_review

__all__ = ["build_delivery_review"]
