"""统一大模型网关入口。"""

from app.core.config import settings
from app.core.errors import AppError


def get_provider():
    """返回当前激活的任务单草案提供者。"""
    provider_name = getattr(settings, "requirement_draft_provider", "local_rule")
    if provider_name == "local_rule" or provider_name is None:
        from app.modules.llm.local_rule_provider import LocalRuleRequirementDraftProvider
        return LocalRuleRequirementDraftProvider()
    if provider_name == "fake":
        from app.modules.llm.local_rule_provider import FakeRequirementDraftProvider
        return FakeRequirementDraftProvider()
    raise AppError(
        code="REQUIREMENT_DRAFT_PROVIDER_UNAVAILABLE",
        message=f"未知的任务单草案提供者：{provider_name}",
    )
