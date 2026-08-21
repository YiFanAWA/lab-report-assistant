from __future__ import annotations

import importlib.util
import socket
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER_PATH = REPO_ROOT / "packaging" / "windows" / "launcher_entry.py"


def _load_launcher():
    spec = importlib.util.spec_from_file_location("spec0046_launcher", LAUNCHER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载启动器模块：{LAUNCHER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def launcher():
    return _load_launcher()


def test_sqlite_url_uses_windows_safe_absolute_uri(launcher):
    database_path = Path("C:/Users/demo/AppData/Local/LabReportAssistant/db/app.db")

    assert launcher.sqlite_url(database_path) == (
        "sqlite:///C:/Users/demo/AppData/Local/LabReportAssistant/db/app.db"
    )


def test_build_environment_uses_packaged_local_rule_defaults(launcher, tmp_path):
    bundle_root = tmp_path / "bundle"
    data_root = tmp_path / "user-data"

    environment = launcher.build_environment(bundle_root, data_root, 9001)

    assert environment["APP_ENV"] == "packaged"
    assert environment["LAB_REPORT_PACKAGED"] == "1"
    assert environment["LAB_REPORT_PORT"] == "9001"
    assert environment["LAB_REPORT_BIND_HOST"] == "127.0.0.1"
    assert environment["LLM_PROVIDER"] == "local_rule"
    assert environment["REQUIREMENT_DRAFT_PROVIDER"] == "local_rule"
    assert environment["OUTLINE_PROVIDER"] == "local_rule"
    assert environment["DATABASE_URL"] == launcher.sqlite_url(
        data_root / "db" / "app.db"
    )
    assert Path(environment["PROJECT_DATA_ROOT"]) == (data_root / "projects").resolve()
    assert Path(environment["PACKAGED_FRONTEND_ROOT"]) == (
        bundle_root / "web"
    ).resolve()


def test_user_data_root_uses_local_app_data(monkeypatch, launcher, tmp_path):
    local_app_data = tmp_path / "Local AppData"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    assert launcher.user_data_root() == local_app_data / "LabReportAssistant"


def test_choose_port_skips_occupied_preferred_port(launcher):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        try:
            occupied.bind(("127.0.0.1", 8897))
        except OSError:
            pytest.skip("测试端口已被其他进程占用")

        selected = launcher.choose_port(8897)
