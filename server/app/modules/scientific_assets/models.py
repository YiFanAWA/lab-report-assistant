"""科研图形资产的不可变合同。"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path


class ScientificAssetError(ValueError):
    """资产清单、许可证、完整性或 SVG 安全校验失败。"""


@dataclass(frozen=True)
class ScientificAsset:
    """一项经过逐项审计的开放许可科研 SVG。"""

    asset_id: str
    title: str
    semantic_roles: tuple[str, ...]
    category: str
    source_name: str
    source_url: str
    upstream_file_url: str
    upstream_revision: str
    author: str
    license_id: str
    license_url: str
    attribution_text: str
    modification_note: str
    source_format: str
    source_path: str
    source_sha256: str
    preview_path: str | None
    preview_sha256: str | None
    width: float
    height: float
    view_box: str
    publication_allowed: bool
    redistribution_allowed: bool
    verified_at: str

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ScientificAsset:
        """从 manifest 条目创建合同；未知字段由调用方在 schema 版本中治理。"""

        try:
            publication_allowed = payload["publication_allowed"]
            redistribution_allowed = payload["redistribution_allowed"]
            if not isinstance(publication_allowed, bool):
                raise TypeError("publication_allowed 必须是布尔值")
            if not isinstance(redistribution_allowed, bool):
                raise TypeError("redistribution_allowed 必须是布尔值")
            raw_roles = payload.get("semantic_roles", [])
            if not isinstance(raw_roles, (list, tuple)):
                raise TypeError("semantic_roles 必须是数组")
            semantic_roles = tuple(
                str(value).strip()
                for value in raw_roles
                if str(value).strip()
            )
            asset = cls(
                asset_id=str(payload["asset_id"]).strip(),
                title=str(payload["title"]).strip(),
                semantic_roles=semantic_roles,
                category=str(payload["category"]).strip(),
                source_name=str(payload["source_name"]).strip(),
                source_url=str(payload["source_url"]).strip(),
                upstream_file_url=str(payload["upstream_file_url"]).strip(),
                upstream_revision=str(payload["upstream_revision"]).strip(),
                author=str(payload.get("author", "")).strip(),
                license_id=str(payload["license_id"]).strip(),
                license_url=str(payload["license_url"]).strip(),
                attribution_text=str(payload.get("attribution_text", "")).strip(),
                modification_note=str(payload.get("modification_note", "")).strip(),
                source_format=str(payload.get("source_format", "svg")).strip().lower(),
                source_path=str(payload["source_path"]).strip(),
                source_sha256=str(payload["source_sha256"]).strip().lower(),
                preview_path=(
                    str(payload["preview_path"]).strip()
                    if payload.get("preview_path")
                    else None
                ),
                preview_sha256=(
                    str(payload["preview_sha256"]).strip().lower()
                    if payload.get("preview_sha256")
                    else None
                ),
                width=float(payload["width"]),
                height=float(payload["height"]),
                view_box=str(payload["view_box"]).strip(),
                publication_allowed=publication_allowed,
                redistribution_allowed=redistribution_allowed,
                verified_at=str(payload["verified_at"]).strip(),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ScientificAssetError(f"资产 manifest 字段无效：{exc}") from exc
        asset.validate_contract()
        return asset

    def validate_contract(self) -> None:
        required_text = {
            "asset_id": self.asset_id,
            "title": self.title,
            "category": self.category,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "upstream_file_url": self.upstream_file_url,
            "upstream_revision": self.upstream_revision,
            "license_id": self.license_id,
            "license_url": self.license_url,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "view_box": self.view_box,
            "verified_at": self.verified_at,
        }
        missing = [name for name, value in required_text.items() if not value]
        if missing:
            raise ScientificAssetError(
                f"资产 {self.asset_id or '<unknown>'} 缺少字段：{', '.join(missing)}"
            )
        if not self.semantic_roles:
            raise ScientificAssetError(f"资产 {self.asset_id} 必须声明 semantic_roles")
        if self.source_format != "svg" or Path(self.source_path).suffix.lower() != ".svg":
            raise ScientificAssetError(f"资产 {self.asset_id} 的真源必须是 SVG")
        if len(self.source_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.source_sha256
        ):
            raise ScientificAssetError(f"资产 {self.asset_id} 的 source_sha256 无效")
        if self.preview_path and not self.preview_sha256:
            raise ScientificAssetError(f"资产 {self.asset_id} 的预览缺少 preview_sha256")
        if self.preview_sha256 and (
            len(self.preview_sha256) != 64
            or any(char not in "0123456789abcdef" for char in self.preview_sha256)
        ):
            raise ScientificAssetError(f"资产 {self.asset_id} 的 preview_sha256 无效")
        if (
            not math.isfinite(self.width)
            or not math.isfinite(self.height)
            or self.width <= 0
            or self.height <= 0
        ):
            raise ScientificAssetError(f"资产 {self.asset_id} 的尺寸必须大于 0")
        if not self.publication_allowed or not self.redistribution_allowed:
            raise ScientificAssetError(
                f"资产 {self.asset_id} 未获论文发表或本地再分发许可"
            )
