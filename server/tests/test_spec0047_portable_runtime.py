from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_PATH = REPO_ROOT / "packaging" / "windows" / "build_windows_bundle.py"


def _load_build_module():
    spec = importlib.util.spec_from_file_location("spec0047_windows_build", BUILD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 Windows 打包脚本：{BUILD_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_runtime(root: Path, *, include_hash: bool = True) -> Path:
    (root / "program").mkdir(parents=True)
    (root / "program" / "soffice.exe").write_bytes(b"portable-soffice")
    (root / "LICENSE.html").write_text("license", encoding="utf-8")
    metadata = {
        "version": "26.2.5",
        "source": "https://example.invalid/libreoffice.msi",
        "license_files": ["LICENSE.html"],
    }
    if include_hash:
        metadata["source_sha256"] = "a" * 64
    (root / "runtime-metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    return root


def test_portable_manifest_records_runtime_source_hash_and_licenses(tmp_path):
    build = _load_build_module()
    runtime = _write_runtime(tmp_path / "runtime")
    build.LIBREOFFICE_ROOT = runtime
    release = tmp_path / "release"
    release.mkdir()

    build.copy_libreoffice_runtime(release)
    build.write_manifest(release)

    manifest = json.loads((release / "release-manifest.json").read_text())
    assert manifest["pdf_converter"] == {
        "provider": "LibreOffice",
        "executable": "libreoffice/program/soffice.exe",
        "version": "26.2.5",
        "source": "https://example.invalid/libreoffice.msi",
        "source_sha256": "a" * 64,
        "license_files": ["LICENSE.html"],
    }
    assert (release / "libreoffice" / "LICENSE.html").is_file()


def test_portable_runtime_rejects_metadata_without_source_hash(tmp_path):
    build = _load_build_module()
    runtime = _write_runtime(tmp_path / "runtime", include_hash=False)
    build.LIBREOFFICE_ROOT = runtime

    with pytest.raises(SystemExit, match="source_sha256"):
        build.copy_libreoffice_runtime(tmp_path / "release")
