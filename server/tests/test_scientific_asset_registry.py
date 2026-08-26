"""SPEC 0042 开放许可科研图形资产库合同测试。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.modules.scientific_assets import (
    LicenseDisposition,
    ScientificAssetError,
    ScientificAssetRegistry,
    build_attribution_markdown,
    evaluate_license,
    inspect_svg,
)


SAFE_SVG = b'''<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80" viewBox="0 0 100 80"><rect x="5" y="5" width="90" height="70" fill="#eef"/></svg>'''


def _write_registry(tmp_path: Path, **overrides) -> Path:
    svg_dir = tmp_path / "svg" / "apparatus"
    svg_dir.mkdir(parents=True)
    svg_path = svg_dir / "tube.svg"
    svg_path.write_bytes(SAFE_SVG)
    entry = {
        "asset_id": "tube-cc0",
        "title": "离心管",
        "semantic_roles": ["sample_container"],
        "category": "apparatus",
        "source_name": "Example Open Library",
        "source_url": "https://example.test/library",
        "upstream_file_url": "https://example.test/tube.svg",
        "upstream_revision": "abc123",
        "author": "",
        "license_id": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "attribution_text": "",
        "modification_note": "未修改",
        "source_format": "svg",
        "source_path": "svg/apparatus/tube.svg",
        "source_sha256": hashlib.sha256(SAFE_SVG).hexdigest(),
        "preview_path": None,
        "preview_sha256": None,
        "width": 100,
        "height": 80,
        "view_box": "0 0 100 80",
        "publication_allowed": True,
        "redistribution_allowed": True,
        "verified_at": "2026-08-13",
    }
    entry.update(overrides)
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "assets": [entry]}, ensure_ascii=False),
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.parametrize(
    "license_id",
    ["PUBLIC-DOMAIN", "CC0-1.0", "MIT", "APACHE-2.0", "BSD-3-CLAUSE", "CC-BY-4.0"],
)
def test_license_allowlist(license_id: str):
    assert evaluate_license(license_id).disposition == LicenseDisposition.ALLOW


@pytest.mark.parametrize(
    ("license_id", "disposition"),
    [
        ("CC-BY-SA-4.0", LicenseDisposition.REVIEW),
        ("CC-BY-NC-4.0", LicenseDisposition.DENY),
        ("CC-BY-ND-4.0", LicenseDisposition.DENY),
        ("UNKNOWN", LicenseDisposition.DENY),
    ],
)
def test_license_review_and_deny(license_id: str, disposition: LicenseDisposition):
    assert evaluate_license(license_id).disposition == disposition


def test_registry_loads_safe_cc0_asset(tmp_path: Path):
    registry = ScientificAssetRegistry.load(_write_registry(tmp_path))
    assert registry.get("tube-cc0").title == "离心管"
    assert registry.find(semantic_role="sample_container")[0].asset_id == "tube-cc0"


def test_registry_rejects_hash_drift(tmp_path: Path):
    root = _write_registry(tmp_path, source_sha256="0" * 64)
    with pytest.raises(ScientificAssetError, match="哈希"):
        ScientificAssetRegistry.load(root)


def test_registry_rejects_path_escape(tmp_path: Path):
    root = _write_registry(tmp_path, source_path="../tube.svg")
    with pytest.raises(ScientificAssetError, match="受控根目录"):
        ScientificAssetRegistry.load(root)


def test_registry_requires_cc_by_attribution(tmp_path: Path):
    root = _write_registry(
        tmp_path,
        license_id="CC-BY-4.0",
        author="",
        attribution_text="",
        modification_note="",
    )
    with pytest.raises(ScientificAssetError, match="署名字段"):
        ScientificAssetRegistry.load(root)


@pytest.mark.parametrize(
    "payload",
    [
        b'<svg viewBox="0 0 10 10"><script>alert(1)</script></svg>',
        b'<svg viewBox="0 0 10 10"><image href="https://example.test/x.png"/></svg>',
        b'<svg viewBox="0 0 10 10"><foreignObject/></svg>',
        b'<svg viewBox="0 0 10 10"><rect onclick="alert(1)"/></svg>',
        b'<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><svg viewBox="0 0 10 10"/>',
    ],
)
def test_svg_security_rejects_dynamic_or_external_content(payload: bytes):
    with pytest.raises(ScientificAssetError):
        inspect_svg(payload)


def test_svg_security_rejects_external_url_in_style_element():
    payload = b'''<svg viewBox="0 0 10 10"><style>.x{fill:url(https://example.test/a.svg)}</style><rect class="x"/></svg>'''
    with pytest.raises(ScientificAssetError, match="style"):
        inspect_svg(payload)


def test_svg_security_rejects_external_url_in_any_attribute():
    payload = b'''<svg viewBox="0 0 10 10"><path marker-start="url(https://example.test/marker.svg#x)"/></svg>'''
    with pytest.raises(ScientificAssetError, match="外部 URL"):
        inspect_svg(payload)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_svg_security_rejects_non_finite_viewbox(value: str):
    payload = f'<svg viewBox="0 0 {value} 10"/>'.encode()
    with pytest.raises(ScientificAssetError, match="非有限"):
        inspect_svg(payload)


def test_registry_rejects_non_array_semantic_roles(tmp_path: Path):
    root = _write_registry(tmp_path, semantic_roles="sample_container")
    with pytest.raises(ScientificAssetError, match="semantic_roles"):
        ScientificAssetRegistry.load(root)


@pytest.mark.parametrize("field", ["publication_allowed", "redistribution_allowed"])
def test_registry_rejects_string_boolean_flags(tmp_path: Path, field: str):
    root = _write_registry(tmp_path, **{field: "false"})
    with pytest.raises(ScientificAssetError, match="必须是布尔值"):
        ScientificAssetRegistry.load(root)


def test_attribution_is_stable(tmp_path: Path):
    asset = ScientificAssetRegistry.load(_write_registry(tmp_path)).assets[0]
    markdown = build_attribution_markdown([asset])
    assert "tube-cc0" in markdown
    assert "CC0-1.0" in markdown
    assert "abc123" in markdown
