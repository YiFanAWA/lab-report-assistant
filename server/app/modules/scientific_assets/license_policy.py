"""开放科研资产许可证白名单和拒绝策略。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LicenseDisposition(StrEnum):
    ALLOW = "allow"
    REVIEW = "review"
    DENY = "deny"


@dataclass(frozen=True)
class LicenseDecision:
    license_id: str
    disposition: LicenseDisposition
    attribution_required: bool
    notice_required: bool
    reason: str


_ALIASES = {
    "PUBLIC DOMAIN": "PUBLIC-DOMAIN",
    "PUBLIC-DOMAIN": "PUBLIC-DOMAIN",
    "CC0": "CC0-1.0",
    "CC-0": "CC0-1.0",
    "CC0-1.0": "CC0-1.0",
    "CC BY 3.0": "CC-BY-3.0",
    "CC-BY-3.0": "CC-BY-3.0",
    "CC BY 4.0": "CC-BY-4.0",
    "CC-BY-4.0": "CC-BY-4.0",
    "CC BY-SA 3.0": "CC-BY-SA-3.0",
    "CC-BY-SA-3.0": "CC-BY-SA-3.0",
    "CC BY-SA 4.0": "CC-BY-SA-4.0",
    "CC-BY-SA-4.0": "CC-BY-SA-4.0",
    "APACHE 2.0": "APACHE-2.0",
    "APACHE-2.0": "APACHE-2.0",
    "BSD 2-CLAUSE": "BSD-2-CLAUSE",
    "BSD-2-CLAUSE": "BSD-2-CLAUSE",
    "BSD 3-CLAUSE": "BSD-3-CLAUSE",
    "BSD-3-CLAUSE": "BSD-3-CLAUSE",
    "MIT": "MIT",
}

_ALLOW_NO_ATTRIBUTION = {"PUBLIC-DOMAIN", "CC0-1.0"}
_ALLOW_ATTRIBUTION = {"CC-BY-3.0", "CC-BY-4.0"}
_ALLOW_NOTICE = {"MIT", "APACHE-2.0", "BSD-2-CLAUSE", "BSD-3-CLAUSE"}
_REVIEW = {"CC-BY-SA-3.0", "CC-BY-SA-4.0"}
_DENY_TOKENS = (
    "-NC",
    "-ND",
    "NONCOMMERCIAL",
    "NO DERIVATIVES",
    "PERSONAL USE",
    "EDITORIAL USE",
    "NO REDISTRIBUTION",
    "PROPRIETARY",
)


def normalize_license_id(license_id: str) -> str:
    normalized = " ".join(license_id.strip().upper().replace("_", "-").split())
    return _ALIASES.get(normalized, normalized)


def evaluate_license(license_id: str) -> LicenseDecision:
    normalized = normalize_license_id(license_id)
    if normalized in _ALLOW_NO_ATTRIBUTION:
        return LicenseDecision(
            normalized,
            LicenseDisposition.ALLOW,
            attribution_required=False,
            notice_required=False,
            reason="公共领域或 CC0，可在保留来源记录后复用。",
        )
    if normalized in _ALLOW_ATTRIBUTION:
        return LicenseDecision(
            normalized,
            LicenseDisposition.ALLOW,
            attribution_required=True,
            notice_required=False,
            reason="允许修改与再分发，但成品必须署名并标注修改。",
        )
    if normalized in _ALLOW_NOTICE:
        return LicenseDecision(
            normalized,
            LicenseDisposition.ALLOW,
            attribution_required=False,
            notice_required=True,
            reason="允许复用，但必须保留版权和许可证通知。",
        )
    if normalized in _REVIEW:
        return LicenseDecision(
            normalized,
            LicenseDisposition.REVIEW,
            attribution_required=True,
            notice_required=True,
            reason="ShareAlike 可能影响组合图与交付物许可，首期必须人工审核。",
        )
    if any(token in normalized for token in _DENY_TOKENS):
        reason = "许可证包含非商业、禁止衍生、禁止再分发或其他不兼容限制。"
    else:
        reason = "许可证未知或没有进入项目白名单。"
    return LicenseDecision(
        normalized or "UNKNOWN",
        LicenseDisposition.DENY,
        attribution_required=False,
        notice_required=False,
        reason=reason,
    )
