"""开放许可科研图形资产核心。

本模块拥有资产清单、许可证策略、SVG 安全与完整性校验、检索和署名合同。
图形研究语义仍由 outlines.figure_planner 拥有，renderer 只能消费本模块已验证资产。
"""

from .attribution import build_attribution_markdown
from .license_policy import LicenseDecision, LicenseDisposition, evaluate_license
from .models import ScientificAsset, ScientificAssetError
from .registry import ScientificAssetRegistry
from .svg_security import SvgInspection, inspect_svg

__all__ = [
    "LicenseDecision",
    "LicenseDisposition",
    "ScientificAsset",
    "ScientificAssetError",
    "ScientificAssetRegistry",
    "SvgInspection",
    "build_attribution_markdown",
    "evaluate_license",
    "inspect_svg",
]
