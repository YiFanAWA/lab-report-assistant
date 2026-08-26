"""根据 manifest 稳定生成论文/仓库可用的署名清单。"""

from __future__ import annotations

from collections.abc import Iterable

from .license_policy import evaluate_license
from .models import ScientificAsset


def build_attribution_markdown(assets: Iterable[ScientificAsset]) -> str:
    ordered = sorted(assets, key=lambda asset: asset.asset_id)
    lines = [
        "# 科研图形资产署名与来源",
        "",
        "本文件由资产 manifest 生成。资产仍受各自许可证约束。",
        "",
    ]
    for asset in ordered:
        decision = evaluate_license(asset.license_id)
        lines.extend(
            [
                f"## {asset.title}（`{asset.asset_id}`）",
                "",
                f"- 来源：[{asset.source_name}]({asset.source_url})",
                f"- 上游文件：{asset.upstream_file_url}",
                f"- 上游版本：`{asset.upstream_revision}`",
                f"- 许可证：[{decision.license_id}]({asset.license_url})",
                f"- 作者：{asset.author or '公共领域/未要求署名'}",
                f"- 修改说明：{asset.modification_note or '未修改'}",
            ]
        )
        if asset.attribution_text:
            lines.append(f"- 建议署名：{asset.attribution_text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
