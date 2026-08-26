"""Windows 便携发布包启动器。

启动器只负责路径、进程和用户可见运行状态；不拥有业务语义。
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


APP_NAME = "实验报告助手"
SERVICE_RELATIVE_PATH = Path("service") / "service.exe"
WEB_RELATIVE_PATH = Path("web")
DEFAULT_PORT = 8787
STARTUP_TIMEOUT_SECONDS = 60


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def user_data_root() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    base = Path(local_app_data) if local_app_data else Path.home()
    return base / "LabReportAssistant"


def choose_port(preferred: int = DEFAULT_PORT) -> int:
    for candidate in range(preferred, preferred + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", candidate))
            except OSError:
                continue
            return candidate
    raise RuntimeError("没有可用的本机服务端口（已检查 8787-8886）")


def sqlite_url(database_path: Path) -> str:
    return f"sqlite:///{database_path.resolve().as_posix()}"


def build_environment(root: Path, data_root: Path, port: int) -> dict[str, str]:
    env = os.environ.copy()
    database_path = data_root / "db" / "app.db"
    env.update(
        {
            "APP_ENV": "packaged",
            "DATABASE_URL": sqlite_url(database_path),
            "PROJECT_DATA_ROOT": str((data_root / "projects").resolve()),
            "PACKAGED_FRONTEND_ROOT": str((root / WEB_RELATIVE_PATH).resolve()),
            "PDF_CONVERTER_PATH": str((root / "libreoffice" / "program" / "soffice.exe").resolve()),
            "LAB_REPORT_PACKAGED": "1",
            "LAB_REPORT_PORT": str(port),
            "LAB_REPORT_BIND_HOST": "127.0.0.1",
            "LLM_PROVIDER": "local_rule",
            "REQUIREMENT_DRAFT_PROVIDER": "local_rule",
            "EVIDENCE_CARD_PROVIDER": "local_rule",
            "ANALYSIS_PLAN_PROVIDER": "local_rule",
            "CODE_TASK_PROVIDER": "local_rule",
            "OUTLINE_PROVIDER": "local_rule",
            "LLM_CACHE_ENABLED": "false",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    return env


def wait_for_health(
    port: int,
    process: subprocess.Popen,
    timeout: float = STARTUP_TIMEOUT_SECONDS,
) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"后端进程提前退出，退出码：{process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.25)
    raise TimeoutError(f"后端在 {timeout:.0f} 秒内未通过健康检查：{url}")


def _message_box(title: str, message: str, error: bool = True) -> None:
    flags = 0x10 if error else 0x40
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, flags)
    except Exception:
        print(f"{title}: {message}", file=sys.stderr, flush=True)

class Win32LifecycleWindow:
    """提供可见的退出入口，并把服务进程生命周期绑定到启动器。"""

    WM_CLOSE = 0x0010
    WM_COMMAND = 0x0111
    WM_TIMER = 0x0113
    WS_CAPTION = 0x00C00000
    WS_SYSMENU = 0x00080000
    WS_MINIMIZEBOX = 0x00020000
    WS_CHILD = 0x40000000
    WS_VISIBLE = 0x10000000
    WS_TABSTOP = 0x00010000
    SW_SHOWNORMAL = 1
    TIMER_ID = 1

    def __init__(self, port: int, processes: list[subprocess.Popen]) -> None:
        if os.name != "nt":
            raise OSError("Windows 生命周期窗口只能在 Windows 上运行")
        self._processes = processes
        self.failure_message: str | None = None
        self._window = wintypes.HWND()
        self._configure_win32_api()
        self._create_window(port)

    def _configure_win32_api(self) -> None:
        user32 = ctypes.windll.user32
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.INT,
            wintypes.INT,
            wintypes.INT,
            wintypes.INT,
            wintypes.HWND,
            wintypes.HMENU,
            wintypes.HINSTANCE,
            wintypes.LPVOID,
        ]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.SetTimer.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
            ctypes.c_void_p,
        ]
        user32.SetTimer.restype = ctypes.c_size_t
        user32.KillTimer.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.KillTimer.restype = wintypes.BOOL
        user32.ShowWindow.argtypes = [wintypes.HWND, wintypes.INT]
        user32.UpdateWindow.argtypes = [wintypes.HWND]
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        user32.DestroyWindow.restype = wintypes.BOOL
        user32.IsWindow.argtypes = [wintypes.HWND]
        user32.IsWindow.restype = wintypes.BOOL
        user32.PostQuitMessage.argtypes = [wintypes.INT]
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.GetMessageW.restype = ctypes.c_int
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]

    def _create_window(self, port: int) -> None:
        user32 = ctypes.windll.user32
        style = self.WS_CAPTION | self.WS_SYSMENU | self.WS_MINIMIZEBOX
        self._window = user32.CreateWindowExW(
            0,
            "STATIC",
            f"{APP_NAME} - 运行中",
            style,
            100,
            100,
            420,
            180,
            None,
            None,
            None,
            None,
        )
        if not self._window:
            raise ctypes.WinError()

        child_style = self.WS_CHILD | self.WS_VISIBLE
        user32.CreateWindowExW(
            0,
            "STATIC",
            f"服务已启动，浏览器地址：http://127.0.0.1:{port}/",
            child_style,
            20,
            20,
            370,
            50,
            self._window,
            None,
            None,
            None,
        )
        user32.CreateWindowExW(
            0,
            "BUTTON",
            "退出应用",
            child_style | self.WS_TABSTOP,
            145,
            88,
            120,
            32,
            self._window,
            ctypes.c_void_p(1),
            None,
            None,
        )
        user32.SetTimer(self._window, self.TIMER_ID, 1000, None)

    def _close_window(self) -> None:
        user32 = ctypes.windll.user32
        user32.KillTimer(self._window, self.TIMER_ID)
        user32.DestroyWindow(self._window)
        user32.PostQuitMessage(0)

    def _check_processes(self) -> None:
        for process in self._processes:
            if process.poll() is not None:
                self.failure_message = f"服务进程已退出，退出码：{process.returncode}"
                self._close_window()
                return

    def run(self) -> None:
        user32 = ctypes.windll.user32
        user32.ShowWindow(self._window, self.SW_SHOWNORMAL)
        user32.UpdateWindow(self._window)
        message = wintypes.MSG()
        while True:
            result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
            if result <= 0:
                break

            if message.message == self.WM_COMMAND:
                if (int(message.wParam) & 0xFFFF) == 1:
                    self._close_window()
                    continue
            elif message.message == self.WM_TIMER and int(message.wParam) == self.TIMER_ID:
                self._check_processes()
                continue
            elif message.message == self.WM_CLOSE:
                self._close_window()
                continue

            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
            if not user32.IsWindow(self._window):
                user32.PostQuitMessage(0)


def start_service(
    root: Path,
    data_root: Path,
    port: int,
) -> tuple[subprocess.Popen, subprocess.Popen, list[object]]:
    service_exe = root / SERVICE_RELATIVE_PATH
    if not service_exe.is_file():
        raise FileNotFoundError(f"发布包缺少服务入口：{service_exe}")

    # SQLite 不会自动创建父目录；用户数据目录由启动器统一初始化。
    (data_root / "db").mkdir(parents=True, exist_ok=True)
    (data_root / "projects").mkdir(parents=True, exist_ok=True)
    log_root = data_root / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    env = build_environment(root, data_root, port)
    handles: list[object] = []
    creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    def spawn(mode: str, log_name: str) -> subprocess.Popen:
        log_file = (log_root / log_name).open("a", encoding="utf-8")
        handles.append(log_file)
        args = [str(service_exe), mode]
        if mode == "backend":
            args.extend(["--host", "127.0.0.1", "--port", str(port)])
        return subprocess.Popen(
            args,
            cwd=str(root),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
        )

    backend = spawn("backend", "backend.log")
    try:
        wait_for_health(port, backend)
        worker = spawn("worker", "worker.log")
    except Exception:
        terminate_processes([backend])
        for handle in handles:
            handle.close()
        raise
    return backend, worker, handles


def terminate_processes(processes: list[subprocess.Popen]) -> None:
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 5
    for process in reversed(processes):
        if process.poll() is None:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                process.kill()


def run() -> int:
    root = bundle_root()
    data_root = user_data_root()
    data_root.mkdir(parents=True, exist_ok=True)
    port = choose_port()
    processes: list[subprocess.Popen] = []
    log_handles: list[object] = []

    try:
        backend, worker, log_handles = start_service(root, data_root, port)
        processes.extend([backend, worker])
        try:
            webbrowser.open(f"http://127.0.0.1:{port}/")
        except Exception:
            # 浏览器属于可选外部集成；打不开时仍保留本地服务和退出窗口。
            pass

        # 原生小窗口提供退出入口；退出窗口时 finally 会回收子进程。
        lifecycle_window = Win32LifecycleWindow(port, processes)
        lifecycle_window.run()
        if lifecycle_window.failure_message:
            raise RuntimeError(lifecycle_window.failure_message)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        _message_box(APP_NAME, f"启动失败：{exc}\n\n日志目录：{data_root / 'logs'}")
        return 1
    finally:
        terminate_processes(processes)
        for handle in log_handles:
            try:
                handle.close()
            except Exception:
                pass


    return 0

if __name__ == "__main__":
    raise SystemExit(run())
