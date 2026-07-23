"""SPEC 0012 清理脚本命令行接口测试。

覆盖 dry-run/execute 模式、参数解析、help 输出。
"""

import sys
from io import StringIO
from unittest.mock import patch

import pytest


class TestScriptArguments:
    """命令行参数解析测试。"""

    def test_help_exits_zero(self, capsys):
        """S-10：--help 输出用法说明，退出码 0。"""
        from scripts.cleanup_expired_data import main
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["cleanup", "--help"]):
                main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "数据保留周期清理" in captured.out or "usage" in captured.out.lower()

    def test_no_args_defaults_dry_run(self, capsys):
        """S-01：无参数默认 dry-run。"""
        from scripts.cleanup_expired_data import main
        with patch("sys.argv", ["cleanup"]):
            with patch("scripts.cleanup_expired_data.run_cleanup") as mock_run:
                mock_run.return_value = 0
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0
                # 验证 run_cleanup 被调用时 execute=False
                mock_run.assert_called_once()
                args, kwargs = mock_run.call_args
                assert kwargs.get("execute") is False or args[1] is False

    def test_dry_run_flag(self, capsys):
        """S-02：显式 --dry-run。"""
        from scripts.cleanup_expired_data import main
        with patch("sys.argv", ["cleanup", "--dry-run"]):
            with patch("scripts.cleanup_expired_data.run_cleanup") as mock_run:
                mock_run.return_value = 0
                with pytest.raises(SystemExit):
                    main()
                mock_run.assert_called_once()

    def test_execute_flag(self, capsys):
        """S-05：--execute 实际执行。"""
        from scripts.cleanup_expired_data import main
        with patch("sys.argv", ["cleanup", "--execute"]):
            with patch("scripts.cleanup_expired_data.run_cleanup") as mock_run:
                mock_run.return_value = 0
                with pytest.raises(SystemExit):
                    main()
                mock_run.assert_called_once()
                args, kwargs = mock_run.call_args
                # execute 应该是 True
                assert kwargs.get("execute") is True or args[1] is True

    def test_dry_run_and_execute_both_defaults_to_dry_run(self, capsys):
        """S-09：同时指定 --dry-run 和 --execute，dry-run 优先。"""
        from scripts.cleanup_expired_data import main
        with patch("sys.argv", ["cleanup", "--dry-run", "--execute"]):
            with patch("scripts.cleanup_expired_data.run_cleanup") as mock_run:
                mock_run.return_value = 0
                with pytest.raises(SystemExit):
                    main()
                captured = capsys.readouterr()
                # 应该输出提示
                assert "dry-run" in captured.out.lower() or "安全" in captured.out
                # execute 应该是 False
                args, kwargs = mock_run.call_args
                assert kwargs.get("execute") is False or args[1] is False


class TestRunCleanupOutput:
    """run_cleanup 输出测试。"""

    def test_zero_retention_exits_early(self, capsys, monkeypatch):
        """S-04：0 天保留期，输出"无过期项目"并退出。"""
        from scripts.cleanup_expired_data import run_cleanup
        monkeypatch.setenv("DATA_RETENTION_DAYS", "0")
        exit_code = run_cleanup(retention_days=0, execute=True)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "永久" in captured.out or "无过期" in captured.out

    def test_no_expired_projects(self, capsys, monkeypatch, tmp_path):
        """无过期项目时输出"无过期项目"。"""
        from scripts.cleanup_expired_data import run_cleanup
        with patch("scripts.cleanup_expired_data.settings") as mock_settings:
            mock_settings.data_retention_days = 30
            mock_settings.database_url = "sqlite:///:memory:"
            mock_settings.project_data_root = tmp_path
            with patch("scripts.cleanup_expired_data.find_expired_projects", return_value=[]):
                exit_code = run_cleanup(retention_days=30, execute=False)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "无过期项目" in captured.out

    def test_dry_run_reports_expired(self, capsys, monkeypatch, tmp_path):
        """S-03：dry-run 输出过期项目报告。"""
        from datetime import datetime, timedelta, timezone
        from scripts.cleanup_expired_data import run_cleanup
        from app.modules.projects.models import Project
        from app.modules.projects.status import ProjectStatus

        now = datetime.now(timezone.utc)
        mock_project = Project(
            id="p_dryrun",
            name="dry-run 测试项目",
            topic="测试",
            status=ProjectStatus.COMPLETED.value,
            workspace_root=str(tmp_path / "p_dryrun"),
            created_at=now - timedelta(days=35),
            updated_at=now - timedelta(days=35),
        )

        with patch("scripts.cleanup_expired_data.settings") as mock_settings:
            mock_settings.data_retention_days = 30
            mock_settings.database_url = "sqlite:///:memory:"
            mock_settings.project_data_root = tmp_path
            with patch("scripts.cleanup_expired_data.find_expired_projects", return_value=[mock_project]):
                with patch("scripts.cleanup_expired_data.has_active_jobs", return_value=False):
                    with patch("scripts.cleanup_expired_data.create_engine"):
                        with patch("scripts.cleanup_expired_data.sessionmaker") as mock_sm:
                            mock_db = mock_sm.return_value.return_value
                            exit_code = run_cleanup(retention_days=30, execute=False)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "p_dryrun" in captured.out
        assert "dry-run" in captured.out.lower() or "预览" in captured.out

    def test_execute_mode(self, capsys, monkeypatch, tmp_path):
        """S-06：execute 模式实际删除。"""
        from datetime import datetime, timedelta, timezone
        from scripts.cleanup_expired_data import run_cleanup
        from app.modules.projects.models import Project
        from app.modules.projects.status import ProjectStatus

        now = datetime.now(timezone.utc)
        mock_project = Project(
            id="p_exec",
            name="execute 测试项目",
            topic="测试",
            status=ProjectStatus.COMPLETED.value,
            workspace_root=str(tmp_path / "p_exec"),
            created_at=now - timedelta(days=35),
            updated_at=now - timedelta(days=35),
        )

        with patch("scripts.cleanup_expired_data.settings") as mock_settings:
            mock_settings.data_retention_days = 30
            mock_settings.database_url = "sqlite:///:memory:"
            mock_settings.project_data_root = tmp_path
            with patch("scripts.cleanup_expired_data.find_expired_projects", return_value=[mock_project]):
                with patch("scripts.cleanup_expired_data.has_active_jobs", return_value=False):
                    with patch("scripts.cleanup_expired_data.create_engine"):
                        with patch("scripts.cleanup_expired_data.sessionmaker"):
                            with patch("scripts.cleanup_expired_data.delete_project_filesystem", return_value=(True, "已删除")):
                                with patch("scripts.cleanup_expired_data.delete_project_database_records", return_value=(5, [])):
                                    exit_code = run_cleanup(retention_days=30, execute=True)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "成功" in captured.out

    def test_execute_with_failures_returns_nonzero(self, capsys, monkeypatch, tmp_path):
        """F-07：有项目清理失败时退出码非 0。"""
        from datetime import datetime, timedelta, timezone
        from scripts.cleanup_expired_data import run_cleanup
        from app.modules.projects.models import Project
        from app.modules.projects.status import ProjectStatus

        now = datetime.now(timezone.utc)
        mock_project = Project(
            id="p_fail",
            name="失败项目",
            topic="测试",
            status=ProjectStatus.COMPLETED.value,
            workspace_root=str(tmp_path / "p_fail"),
            created_at=now - timedelta(days=35),
            updated_at=now - timedelta(days=35),
        )

        with patch("scripts.cleanup_expired_data.settings") as mock_settings:
            mock_settings.data_retention_days = 30
            mock_settings.database_url = "sqlite:///:memory:"
            mock_settings.project_data_root = tmp_path
            with patch("scripts.cleanup_expired_data.find_expired_projects", return_value=[mock_project]):
                with patch("scripts.cleanup_expired_data.has_active_jobs", return_value=False):
                    with patch("scripts.cleanup_expired_data.create_engine"):
                        with patch("scripts.cleanup_expired_data.sessionmaker"):
                            with patch("scripts.cleanup_expired_data.delete_project_filesystem", return_value=(False, "权限不足")):
                                with patch("scripts.cleanup_expired_data.delete_project_database_records", return_value=(0, ["projects 删除失败"])):
                                    exit_code = run_cleanup(retention_days=30, execute=True)
        # partial 状态返回 1
        assert exit_code == 1
