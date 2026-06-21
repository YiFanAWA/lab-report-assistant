"""证据提供者网关。"""

from app.core.config import settings


def get_evidence_provider():
    provider_name = getattr(settings, "evidence_draft_provider", "local_rule") or "local_rule"
    if provider_name == "local_rule":
        from app.modules.llm.local_rule_evidence_provider import LocalRuleEvidenceDraftProvider
        return LocalRuleEvidenceDraftProvider()
    if provider_name == "fake":
        from app.modules.llm.local_rule_evidence_provider import FakeEvidenceDraftProvider
        return FakeEvidenceDraftProvider()
    raise ValueError(f"未知的证据提供者: {provider_name}")
