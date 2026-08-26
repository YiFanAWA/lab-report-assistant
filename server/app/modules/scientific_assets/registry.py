"""资产 manifest 的加载、许可证、路径、安全和哈希门禁。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .license_policy import LicenseDisposition, evaluate_license, normalize_license_id
from .models import ScientificAsset, ScientificAssetError
from .svg_security import inspect_svg


SUPPORTED_SCHEMA_VERSION = 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ScientificAssetRegistry:
    """只暴露已通过全部门禁的资产。"""

    def __init__(self, root: Path, assets: tuple[ScientificAsset, ...]) -> None:
        self.root = root.resolve()
        self._assets = {asset.asset_id: asset for asset in assets}

    @classmethod
    def load(cls, root: str | Path) -> ScientificAssetRegistry:
        root_path = Path(root).resolve()
        manifest_path = root_path / "manifest.json"
        if not manifest_path.is_file():
            raise ScientificAssetError(f"缺少资产 manifest：{manifest_path}")
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ScientificAssetError(f"资产 manifest 无法读取：{exc}") from exc
        if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
            raise ScientificAssetError("资产 manifest schema_version 不受支持")
        entries = payload.get("assets")
        if not isinstance(entries, list):
            raise ScientificAssetError("资产 manifest 的 assets 必须是数组")

        assets: list[ScientificAsset] = []
        seen_ids: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ScientificAssetError("资产 manifest 条目必须是对象")
            asset = ScientificAsset.from_dict(entry)
            if asset.asset_id in seen_ids:
                raise ScientificAssetError(f"资产 id 重复：{asset.asset_id}")
            seen_ids.add(asset.asset_id)
            decision = evaluate_license(asset.license_id)
            if decision.disposition != LicenseDisposition.ALLOW:
                raise ScientificAssetError(
                    f"资产 {asset.asset_id} 的许可证 {decision.license_id} 不允许自动入库："
                    f"{decision.reason}"
                )
            if decision.attribution_required and (
                not asset.author or not asset.attribution_text or not asset.modification_note
            ):
                raise ScientificAssetError(
                    f"资产 {asset.asset_id} 的 {decision.license_id} 署名字段不完整"
                )
            source = cls._controlled_path(root_path, asset.source_path)
            if not source.is_file():
                raise ScientificAssetError(f"资产文件不存在：{asset.source_path}")
            if _sha256(source) != asset.source_sha256:
                raise ScientificAssetError(f"资产 {asset.asset_id} 的 SVG 哈希不一致")
            inspection = inspect_svg(source.read_bytes())
            if inspection.view_box != asset.view_box:
                raise ScientificAssetError(f"资产 {asset.asset_id} 的 viewBox 与 manifest 不一致")
            if abs(inspection.width - asset.width) > 0.01 or abs(inspection.height - asset.height) > 0.01:
                raise ScientificAssetError(f"资产 {asset.asset_id} 的尺寸与 manifest 不一致")
            if normalize_license_id(asset.license_id) != asset.license_id:
                raise ScientificAssetError(
                    f"资产 {asset.asset_id} 必须使用规范化许可证 id：{decision.license_id}"
                )
            if asset.preview_path:
                preview = cls._controlled_path(root_path, asset.preview_path)
                if not preview.is_file() or _sha256(preview) != asset.preview_sha256:
                    raise ScientificAssetError(f"资产 {asset.asset_id} 的预览哈希不一致")
            assets.append(asset)
        return cls(root_path, tuple(assets))

    @staticmethod
    def _controlled_path(root: Path, relative_path: str) -> Path:
        path = (root / relative_path).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ScientificAssetError(f"资产路径越过受控根目录：{relative_path}") from exc
        return path

    @property
    def assets(self) -> tuple[ScientificAsset, ...]:
        return tuple(self._assets.values())

    def get(self, asset_id: str) -> ScientificAsset:
        try:
            return self._assets[asset_id]
        except KeyError as exc:
            raise ScientificAssetError(f"未知科研图形资产：{asset_id}") from exc

    def source_path(self, asset_id: str) -> Path:
        return self._controlled_path(self.root, self.get(asset_id).source_path)

    def find(
        self, *, semantic_role: str | None = None, category: str | None = None
    ) -> tuple[ScientificAsset, ...]:
        matches = self.assets
        if semantic_role:
            matches = tuple(
                asset for asset in matches if semantic_role in asset.semantic_roles
            )
        if category:
            matches = tuple(asset for asset in matches if asset.category == category)
        return tuple(sorted(matches, key=lambda asset: asset.asset_id))
