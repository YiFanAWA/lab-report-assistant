"""受控 Python 执行环境。

通过 subprocess + 临时脚本文件执行用户代码，施加以下限制：
- 限时 30 秒（subprocess timeout 硬限制）
- 输出大小 10 MB（捕获后截断，标记 EXECUTION_OUTPUT_TOO_LARGE）
- 内存 1024 MB（psutil 软监控，0.5s 轮询，超限 kill + 标记 EXECUTION_MEMORY_LIMIT）
- import 白名单（AST 解析校验，禁止 os/subprocess/socket/ssl/http.client/urllib/requests 等）
- __import__() 动态调用拦截（AST Call 节点校验）
- 工作目录限制（cwd 设为受控工作目录）
- 网络完全禁用（通过 import 白名单禁止 socket 等网络模块实现）
- 禁止 shell=True（subprocess.run([python, script], ...) 直接执行）

不使用 exec()/eval()/Notebook 内核，因为它们难以施加资源限制和 import 白名单。
"""

import ast
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import psutil


# 默认 import 白名单（SPEC 0005 决策 0016 确认）
DEFAULT_ALLOWED_IMPORTS: list[str] = [
    "pandas",
    "numpy",
    "matplotlib",
    "scipy",
    "sklearn",
    "openpyxl",
]

# 严格禁止的模块（网络与系统操作）。
# 用户确认扩展拉黑列表：socket, ssl, http.client, urllib, requests 全部纳入。
FORBIDDEN_MODULES: set[str] = {
    # 系统操作
    "os", "sys", "subprocess", "shutil", "ctypes", "signal",
    "select", "resource", "fcntl", "pathlib", "io",
    # 网络访问（用户确认全部拉黑）
    "socket", "ssl", "http", "http.client", "http.server",
    "urllib", "urllib.request", "urllib.parse", "urllib.error",
    "requests", "telnetlib", "smtplib", "poplib", "ftplib",
    "imaplib", "nntplib", "socketserver", "xmlrpc", "webbrowser",
    "asyncore", "asynchat",
    # 并发与序列化（防止绕过限制）
    "multiprocessing", "threading", "asyncio", "concurrent",
    "concurrent.futures", "pickle", "email",
}

# 禁止调用的动态导入函数名
_FORBIDDEN_DYNAMIC_IMPORTS: set[str] = {
    "__import__",
}


@dataclass
class ArtifactInfo:
    """执行产物信息。"""

    file_path: str  # 相对 work_dir 的路径
    file_size_bytes: int
    name: str
    artifact_type: str  # TABLE_CSV 或 CHART_PNG


@dataclass
class ExecutionResult:
    """执行结果。"""

    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    artifacts: list[ArtifactInfo] = field(default_factory=list)
    # 执行环境标记的错误码（非 None 表示被环境限制终止，非脚本本身错误）
    sandbox_error_code: str | None = None


class SandboxError(Exception):
    """受控执行环境错误。

    code 取值：
    - EXECUTION_IMPORT_FORBIDDEN：import 白名单校验失败
    - EXECUTION_TIMEOUT：执行超时
    - EXECUTION_MEMORY_LIMIT：内存超限
    - EXECUTION_FAILED：其他未预期错误
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


# --- AST 校验 ---


def _top_level_module(name: str) -> str:
    """从 import 名提取顶级模块。'scipy.stats' -> 'scipy'。"""
    return name.split(".", 1)[0] if name else name


def _check_import_name(name: str, allowed: list[str]) -> None:
    """检查单个 import 名是否在白名单内且不在黑名单内。

    校验规则：
    1. 完整名或顶级名在 FORBIDDEN_MODULES -> 拒绝
    2. 顶级名不在 allowed 白名单 -> 拒绝
    """
    if not name:
        return

    top = _top_level_module(name)

    # 1. 黑名单优先（完整名或顶级名任一匹配即拒绝）
    if name in FORBIDDEN_MODULES or top in FORBIDDEN_MODULES:
        raise SandboxError(
            code="EXECUTION_IMPORT_FORBIDDEN",
            message=f"禁止 import 模块: {name}",
        )

    # 2. 白名单校验（按顶级模块匹配）
    allowed_tops = {_top_level_module(a) for a in allowed}
    if top not in allowed_tops:
        raise SandboxError(
            code="EXECUTION_IMPORT_FORBIDDEN",
            message=f"模块 {name} 不在 import 白名单内",
        )


def _check_call_for_dynamic_import(node: ast.Call) -> None:
    """检查 Call 节点是否调用了 __import__ 或 importlib.import_module 等动态导入。"""
    func = node.func

    # 直接调用 __import__()
    if isinstance(func, ast.Name) and func.id in _FORBIDDEN_DYNAMIC_IMPORTS:
        raise SandboxError(
            code="EXECUTION_IMPORT_FORBIDDEN",
            message=f"禁止调用动态导入函数: {func.id}()",
        )

    # 调用 importlib.import_module() / importlib.__import__()
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name) and func.value.id == "importlib":
            raise SandboxError(
                code="EXECUTION_IMPORT_FORBIDDEN",
                message="禁止调用 importlib.import_module() 等动态导入",
            )


def validate_code(code: str, allowed_imports: list[str] | None = None) -> None:
    """AST 解析校验 import 白名单和动态调用。

    校验流程：
    1. ast.parse 解析代码（语法错误归为 EXECUTION_IMPORT_FORBIDDEN）
    2. 遍历所有节点
    3. Import 节点：每个 alias.name 走 _check_import_name
    4. ImportFrom 节点：node.module 走 _check_import_name
    5. Call 节点：检查动态导入函数调用

    违规抛出 SandboxError(code=EXECUTION_IMPORT_FORBIDDEN)。
    """
    allowed = allowed_imports if allowed_imports is not None else DEFAULT_ALLOWED_IMPORTS

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise SandboxError(
            code="EXECUTION_IMPORT_FORBIDDEN",
            message=f"代码语法错误: {e.msg}",
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_import_name(alias.name, allowed)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                _check_import_name(node.module, allowed)
        elif isinstance(node, ast.Call):
            _check_call_for_dynamic_import(node)


# --- 脚本构建 ---


_SCRIPT_TEMPLATE = '''"""受控执行环境自动生成的脚本。

由 SPEC 0005 python_executor 注入。
路径变量：
- DATA_PATH: 数据集文件绝对路径（字符串字面量）
- OUTPUT_DIR: 产物输出目录绝对路径（字符串字面量）
"""
# 由受控执行环境注入的路径变量（字符串字面量，不依赖 import os）
DATA_PATH = {data_path_repr}
OUTPUT_DIR = {output_dir_repr}

# 设置 matplotlib agg backend（避免 GUI 依赖）
try:
    import matplotlib
    matplotlib.use("Agg")
except ImportError:
    pass

# 用户代码开始
# ===== 用户代码开始 =====
{user_code}
# ===== 用户代码结束 =====
'''


def _build_script(user_code: str, data_path: str, output_dir: str) -> str:
    """构建完整脚本：路径注入头部 + matplotlib agg backend + 用户代码。

    路径用 repr() 安全转义，避免注入风险。
    matplotlib agg backend 设置在 try-except 中，避免未安装时失败。
    """
    return _SCRIPT_TEMPLATE.format(
        data_path_repr=repr(str(data_path)),
        output_dir_repr=repr(str(output_dir)),
        user_code=user_code,
    )


# --- 产物收集 ---


def _collect_artifacts(work_dir: Path) -> list[ArtifactInfo]:
    """扫描工作目录收集产物（.csv 和 .png 文件，不递归子目录）。

    按名称排序确保结果稳定。
    """
    artifacts: list[ArtifactInfo] = []
    if not work_dir.exists():
        return artifacts

    for entry in work_dir.iterdir():
        if not entry.is_file():
            continue
        suffix = entry.suffix.lower()
        if suffix == ".csv":
            artifact_type = "TABLE_CSV"
        elif suffix == ".png":
            artifact_type = "CHART_PNG"
        else:
            continue

        stat = entry.stat()
        rel_path = str(entry.relative_to(work_dir))
        artifacts.append(
            ArtifactInfo(
                file_path=rel_path,
                file_size_bytes=stat.st_size,
                name=entry.name,
                artifact_type=artifact_type,
            )
        )

    artifacts.sort(key=lambda a: a.name)
    return artifacts


def _get_process_tree_memory(parent: psutil.Process) -> int:
    """获取进程树总内存（RSS 字节数）。

    Windows venv 的 python.exe 是 launcher，实际代码运行在子进程中。
    必须监控整个进程树，否则会漏掉实际执行代码的子进程内存。
    """
    total = 0
    try:
        total += parent.memory_info().rss
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    try:
        for desc in parent.children(recursive=True):
            try:
                total += desc.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return total


def _kill_process_tree(parent: psutil.Process) -> None:
    """杀掉整个进程树（先杀子进程，再杀父进程）。"""
    try:
        for desc in parent.children(recursive=True):
            try:
                desc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    try:
        parent.kill()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass


def _truncate_output(text: str, max_bytes: int) -> tuple[str, bool]:
    """按字节安全截断输出文本，返回 (截断后文本, 是否被截断)。"""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text, False
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return truncated + "\n...[输出被截断]...", True


# --- 执行 ---


def execute_code(
    code: str,
    work_dir: str,
    data_path: str,
    timeout_seconds: int = 30,
    memory_limit_mb: int = 1024,
    output_max_bytes: int = 10 * 1024 * 1024,
    allowed_imports: list[str] | None = None,
    python_executable: str | None = None,
) -> ExecutionResult:
    """在受控环境中执行 Python 代码。

    流程：
    1. validate_code 校验 import 和动态调用
    2. 创建受控工作目录（如不存在）
    3. 写入 _run.py（头部注入 DATA_PATH、OUTPUT_DIR 字符串字面量）
    4. subprocess.Popen([python, _run.py], cwd=work_dir, capture_output=True)
       禁止 shell=True
    5. psutil 软监控：0.5s 轮询 communicate，检查 child.memory_info().rss
       超限 kill 进程树并标记 EXECUTION_MEMORY_LIMIT
    6. 超过 timeout_seconds 则 kill 并抛 EXECUTION_TIMEOUT
    7. 截断 stdout/stderr 超过 output_max_bytes，标记 sandbox_error_code
    8. 扫描 work_dir 收集 .csv 和 .png 产物（无论成功失败）
    9. 返回 ExecutionResult

    异常：
    - SandboxError(code=EXECUTION_IMPORT_FORBIDDEN)
    - SandboxError(code=EXECUTION_TIMEOUT)
    - SandboxError(code=EXECUTION_MEMORY_LIMIT)
    - SandboxError(code=EXECUTION_FAILED)（其他未预期错误）

    注意：输出过大不抛异常，而是返回带 sandbox_error_code=EXECUTION_OUTPUT_TOO_LARGE
    的 ExecutionResult，让调用方决定如何处理。
    """
    # 1. AST 校验（只校验用户代码，不校验脚本头部注入的 import matplotlib）
    validate_code(code, allowed_imports)

    # 2. 准备工作目录
    work_path = Path(work_dir)
    work_path.mkdir(parents=True, exist_ok=True)

    # 3. 写入临时脚本
    script_content = _build_script(code, data_path, str(work_path))
    script_path = work_path / "_run.py"
    script_path.write_text(script_content, encoding="utf-8")

    python = python_executable or sys.executable

    # 4. 启动子进程
    start_time = time.time()
    proc = subprocess.Popen(
        [python, str(script_path)],
        cwd=str(work_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={
            "SANDBOX_DATA_PATH": str(data_path),
            "SANDBOX_OUTPUT_DIR": str(work_path),
            "PYTHONPATH": "",
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "PYTHONIOENCODING": "utf-8",
            "MPLBACKEND": "Agg",
        },
    )

    # 5. psutil 软监控
    try:
        child = psutil.Process(proc.pid)
    except psutil.NoSuchProcess:
        child = None

    stdout_bytes = b""
    stderr_bytes = b""
    poll_interval = 0.5  # 0.5s 轮询，平衡精度与开销

    # 轮询循环
    deadline = start_time + timeout_seconds
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            # 超时
            if child is not None:
                _kill_process_tree(child)
            else:
                proc.kill()
            try:
                stdout_bytes, stderr_bytes = proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                stdout_bytes, stderr_bytes = b"", b""
            duration = time.time() - start_time
            _cleanup_script(script_path)
            raise SandboxError(
                code="EXECUTION_TIMEOUT",
                message=f"执行超过 {timeout_seconds} 秒限制",
            )

        # 检查内存（在 communicate 之前，避免错过内存峰值）
        # 使用进程树总内存，因为 Windows venv launcher 会创建子进程执行实际代码
        if child is not None and child.is_running():
            try:
                tree_memory = _get_process_tree_memory(child)
                if tree_memory > memory_limit_mb * 1024 * 1024:
                    _kill_process_tree(child)
                    try:
                        stdout_bytes, stderr_bytes = proc.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        stdout_bytes, stderr_bytes = b"", b""
                    _cleanup_script(script_path)
                    raise SandboxError(
                        code="EXECUTION_MEMORY_LIMIT",
                        message=f"执行内存超过 {memory_limit_mb} MB 限制（进程树占用 {tree_memory / 1024 / 1024:.1f} MB）",
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # 等待 poll_interval 或进程结束
        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=poll_interval)
            break  # 进程已结束
        except subprocess.TimeoutExpired:
            # 进程仍在运行，继续轮询
            continue

    duration = time.time() - start_time
    exit_code = proc.returncode if proc.returncode is not None else -1

    # 6. 解码和截断输出
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    total_output_bytes = len(stdout_bytes) + len(stderr_bytes)
    output_too_large = total_output_bytes > output_max_bytes

    if output_too_large:
        max_each = output_max_bytes // 2
        stdout, _ = _truncate_output(stdout, max_each)
        stderr, _ = _truncate_output(stderr, max_each)

    # 7. 收集产物（无论成功失败）
    artifacts = _collect_artifacts(work_path)

    # 8. 清理脚本文件
    _cleanup_script(script_path)

    # 9. 确定错误码
    sandbox_error_code: str | None = None
    if exit_code != 0 and "MemoryError" in stderr:
        # 后备检测：进程因 MemoryError 崩溃（监控未及时捕获）
        _cleanup_script(script_path)
        raise SandboxError(
            code="EXECUTION_MEMORY_LIMIT",
            message=f"执行内存超限导致 MemoryError（exit_code={exit_code}）",
        )
    elif output_too_large:
        sandbox_error_code = "EXECUTION_OUTPUT_TOO_LARGE"

    return ExecutionResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=duration,
        artifacts=artifacts,
        sandbox_error_code=sandbox_error_code,
    )


def _cleanup_script(script_path: Path) -> None:
    """清理临时脚本文件。失败不抛异常。"""
    try:
        if script_path.exists():
            script_path.unlink()
    except OSError:
        pass


def execute_code_safe(
    code: str,
    work_dir: str,
    data_path: str,
    timeout_seconds: int = 30,
    memory_limit_mb: int = 1024,
    output_max_bytes: int = 10 * 1024 * 1024,
    allowed_imports: list[str] | None = None,
    python_executable: str | None = None,
) -> ExecutionResult:
    """执行代码并将 SandboxError 转换为带错误信息的 ExecutionResult。

    与 execute_code 的区别：
    - execute_code 抛出 SandboxError
    - execute_code_safe 捕获 SandboxError，返回 exit_code=-1、stderr 含错误信息的 ExecutionResult

    适用于 Worker 调用场景：Worker 不需要处理异常，直接把结果写入数据库。
    """
    try:
        return execute_code(
            code=code,
            work_dir=work_dir,
            data_path=data_path,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
            output_max_bytes=output_max_bytes,
            allowed_imports=allowed_imports,
            python_executable=python_executable,
        )
    except SandboxError as e:
        return ExecutionResult(
            exit_code=-1,
            stdout="",
            stderr=f"[{e.code}] {e.message}",
            duration_seconds=0.0,
            artifacts=[],
            sandbox_error_code=e.code,
        )
