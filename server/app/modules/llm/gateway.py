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


def get_evidence_card_provider():
    """返回当前激活的证据卡片候选提供者。"""
    provider_name = getattr(settings, "evidence_card_provider", "local_rule")
    if provider_name == "local_rule" or provider_name is None:
        from app.modules.llm.evidence_card_provider import LocalRuleEvidenceCardProvider
        return LocalRuleEvidenceCardProvider()
    if provider_name == "fake":
        from app.modules.llm.evidence_card_provider import FakeEvidenceCardProvider
        return FakeEvidenceCardProvider()
    raise AppError(
        code="EVIDENCE_PROVIDER_UNAVAILABLE",
        message=f"未知的证据卡片提供者：{provider_name}",
    )


def get_analysis_plan_provider():
    """返回当前激活的分析方案候选提供者。"""
    provider_name = getattr(settings, "analysis_plan_provider", "local_rule")
    if provider_name == "local_rule" or provider_name is None:
        from app.modules.llm.analysis_plan_provider import LocalRuleAnalysisPlanProvider
        return LocalRuleAnalysisPlanProvider()
    if provider_name == "fake":
        from app.modules.llm.analysis_plan_provider import FakeAnalysisPlanProvider
        return FakeAnalysisPlanProvider()
    raise AppError(
        code="ANALYSIS_PLAN_PROVIDER_UNAVAILABLE",
        message=f"未知的分析方案提供者：{provider_name}",
    )


def get_code_task_provider():
    """返回当前激活的代码任务候选提供者。

    设计决策（用户确认）：AnalysisPlan 阶段为字段截断唯一截断点，
    CodeTask 生成时直接透传已截断字段内容，提供者不做二次截断。
    """
    provider_name = getattr(settings, "code_task_provider", "local_rule")
    if provider_name == "local_rule" or provider_name is None:
        from app.modules.llm.code_task_provider import LocalRuleCodeTaskProvider
        return LocalRuleCodeTaskProvider()
    if provider_name == "fake":
        from app.modules.llm.code_task_provider import FakeCodeTaskProvider
        return FakeCodeTaskProvider()
    raise AppError(
        code="CODE_TASK_PROVIDER_UNAVAILABLE",
        message=f"未知的代码任务提供者：{provider_name}",
    )


def get_outline_provider():
    """返回当前激活的大纲候选提供者。

    设计决策（用户确认）：AnalysisPlan 阶段为字段截断唯一截断点，
    Outline 生成时直接透传已截断字段内容，提供者不做二次截断。
    """
    provider_name = getattr(settings, "outline_provider", "local_rule")
    if provider_name == "local_rule" or provider_name is None:
        from app.modules.llm.outline_provider import LocalRuleOutlineProvider
        return LocalRuleOutlineProvider()
    if provider_name == "fake":
        from app.modules.llm.outline_provider import FakeOutlineProvider
        return FakeOutlineProvider()
    raise AppError(
        code="OUTLINE_PROVIDER_UNAVAILABLE",
        message=f"未知的大纲提供者：{provider_name}",
    )
