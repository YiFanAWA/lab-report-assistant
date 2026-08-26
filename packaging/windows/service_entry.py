"""Windows 便携包的统一后端/Worker/沙箱入口。"""

from __future__ import annotations

import argparse
import os
import runpy
import sys
from pathlib import Path


def _resource_root() -> Path:
    """返回 PyInstaller 内部资源根目录或源码运行目录。"""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parents[2] / "server"


def _service_dir() -> Path:
    return Path(sys.executable).resolve().parent


def _set_packaged_defaults() -> None:
    os.environ.setdefault("APP_ENV", "packaged")
    os.environ.setdefault("LLM_PROVIDER", "local_rule")
    os.environ.setdefault("REQUIREMENT_DRAFT_PROVIDER", "local_rule")
    os.environ.setdefault("EVIDENCE_CARD_PROVIDER", "local_rule")
    os.environ.setdefault("ANALYSIS_PLAN_PROVIDER", "local_rule")
    os.environ.setdefault("CODE_TASK_PROVIDER", "local_rule")
    os.environ.setdefault("OUTLINE_PROVIDER", "local_rule")
    os.environ.setdefault("LLM_CACHE_ENABLED", "false")
    converter = _service_dir().parent / "libreoffice" / "program" / "soffice.exe"
    os.environ.setdefault("PDF_CONVERTER_PATH", str(converter))


def _set_packaged_sandbox_executable() -> None:
    """让受控代码执行复用同一发布包中的 Python 运行时。"""
    sandbox_runner = _service_dir() / "sandbox_runner.exe"
    if sandbox_runner.is_file():
        # python_executor 使用 sys.executable 启动受控代码；这里把它映射
        # 到同一 PyInstaller 目录下的副本，避免把冻结的 service.exe 当作
        # 普通 python.exe 直接执行临时脚本。
        sys.executable = str(sandbox_runner)


def _mount_packaged_frontend():
    raw_root = os.getenv("PACKAGED_FRONTEND_ROOT", "").strip()
    if not raw_root:
        return
    frontend_root = Path(raw_root).resolve()
    if not (frontend_root / "index.html").is_file():
        raise RuntimeError(f"发布包缺少前端构建产物：{frontend_root}")

    from app.infrastructure.packaging.static_files import SPAStaticFiles

    from app.main import app

    app.mount(
        "/",
        SPAStaticFiles(directory=str(frontend_root), html=True),
        name="packaged-frontend",
    )


def _run_sandbox(script_path: str) -> None:
    script = Path(script_path).resolve()
    if not script.is_file():
        raise FileNotFoundError(f"受控执行脚本不存在：{script}")
    sys.argv = [str(script)]
    runpy.run_path(str(script), run_name="__main__")


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    root = _resource_root()
    ini_path = root / "alembic.ini"
    script_path = root / "alembic"
    if not ini_path.is_file() or not script_path.is_dir():
        raise RuntimeError("发布包缺少 Alembic 迁移资源")

    config = Config(str(ini_path))
    config.set_main_option("script_location", str(script_path))
    command.upgrade(config, "head")


def _run_backend(host: str, port: int) -> None:
    _set_packaged_defaults()
    _set_packaged_sandbox_executable()
    _run_migrations()
    _mount_packaged_frontend()

    import uvicorn
    from app.main import app

    uvicorn.run(app, host=host, port=port, log_level="info")


def _run_worker() -> None:
    _set_packaged_defaults()
    _set_packaged_sandbox_executable()

    from worker.main import main as worker_main

    worker_main()


def main() -> None:
    argv = sys.argv[1:]
    executable_name = Path(sys.argv[0]).stem.lower()

    if "--lab-sandbox-run" in argv or executable_name == "sandbox_runner":
        flag_index = argv.index("--lab-sandbox-run") if "--lab-sandbox-run" in argv else -1
        script_arg = argv[flag_index + 1] if flag_index >= 0 else (argv[0] if argv else "")
        _run_sandbox(script_arg)
        return

    parser = argparse.ArgumentParser(prog="实验报告助手服务")
    parser.add_argument("mode", choices=("backend", "worker"))
    parser.add_argument("--host", default=os.getenv("LAB_REPORT_BIND_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("LAB_REPORT_PORT", "8001")))
    args = parser.parse_args(argv)

    if args.mode == "backend":
        _run_backend(args.host, args.port)
    else:
        _run_worker()


if __name__ == "__main__":
    main()
