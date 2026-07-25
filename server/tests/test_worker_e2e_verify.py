"""SPEC 0016 TD-008 worker_e2e_verify.py 参数解析测试。

覆盖 --version 和 --output 参数解析、环境变量覆盖、默认值兼容性。
不实际执行完整端到端流程（避免数据库依赖），只测 parse_args() 逻辑。
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# 确保 server/ 根目录在 sys.path 中以导入 worker_e2e_verify
SERVER_DIR = Path(__file__).parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from worker_e2e_verify import parse_args, LOG_FILE  # noqa: E402


class TestParseArgsVersion:
    """--version 参数解析测试。"""

    def test_default_version_is_v1_0(self, monkeypatch):
        """AC-12：不指定参数且无环境变量时，version 默认为 "V1.0"。"""
        # 清除环境变量，确保测试隔离
        monkeypatch.delenv("WORKER_E2E_VERSION", raising=False)
        with patch("sys.argv", ["worker_e2e_verify.py"]):
            args = parse_args()
        assert args.version == "V1.0"

    def test_version_from_arg(self, monkeypatch):
        """AC-11：--version V1.3.0 时，version 为 "V1.3.0"。"""
        monkeypatch.delenv("WORKER_E2E_VERSION", raising=False)
        with patch("sys.argv", ["worker_e2e_verify.py", "--version", "V1.3.0"]):
            args = parse_args()
        assert args.version == "V1.3.0"

    def test_version_from_env(self, monkeypatch):
        """AC-14：设置 WORKER_E2E_VERSION=V1.2.0 且不指定 --version 时，version 为 "V1.2.0"。"""
        monkeypatch.setenv("WORKER_E2E_VERSION", "V1.2.0")
        with patch("sys.argv", ["worker_e2e_verify.py"]):
            args = parse_args()
        assert args.version == "V1.2.0"

    def test_arg_overrides_env(self, monkeypatch):
        """AC-14：同时设置参数和环境变量时，命令行参数优先。"""
        monkeypatch.setenv("WORKER_E2E_VERSION", "V1.2.0")
        with patch("sys.argv", ["worker_e2e_verify.py", "--version", "V1.3.0"]):
            args = parse_args()
        assert args.version == "V1.3.0"


class TestParseArgsOutput:
    """--output 参数解析测试。"""

    def test_default_output_path(self, monkeypatch):
        """AC-13：不指定 --output 时，output 为 LOG_FILE 默认值。"""
        monkeypatch.delenv("WORKER_E2E_VERSION", raising=False)
        with patch("sys.argv", ["worker_e2e_verify.py"]):
            args = parse_args()
        assert args.output == LOG_FILE

    def test_custom_output_path(self, monkeypatch, tmp_path):
        """AC-13：--output 指定路径时，output 为指定路径。"""
        monkeypatch.delenv("WORKER_E2E_VERSION", raising=False)
        custom_path = str(tmp_path / "custom-e2e-log.md")
        with patch("sys.argv", ["worker_e2e_verify.py", "--output", custom_path]):
            args = parse_args()
        assert args.output == custom_path
        # 验证路径与默认 LOG_FILE 不同
        assert args.output != LOG_FILE


class TestParseArgsHelp:
    """--help 输出测试（验证参数文档）。"""

    def test_help_exits_zero(self, capsys):
        """--help 输出用法说明，退出码 0。"""
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["worker_e2e_verify.py", "--help"]):
                parse_args()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # 验证 help 输出包含关键参数说明
        assert "--version" in captured.out
        assert "--output" in captured.out
        assert "WORKER_E2E_VERSION" in captured.out
