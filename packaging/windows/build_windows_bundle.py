"""构建 Windows x64 便携发布包。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "apps" / "web"
SERVER_DIR = ROOT / "server"
PACKAGING_DIR = ROOT / "packaging" / "windows"
OUTPUT_ROOT = SERVER_DIR / ".tmp" / "windows-package"
PYI_DIST = OUTPUT_ROOT / "pyinstaller-dist"
PYI_WORK = OUTPUT_ROOT / "pyinstaller-work"
PYI_SPEC = OUTPUT_ROOT / "pyinstaller-spec"
RELEASE_ROOT = OUTPUT_ROOT / "release"
PYTHON = SERVER_DIR / ".venv" / "Scripts" / "python.exe"
LIBREOFFICE_ROOT = Path(os.getenv("LIBREOFFICE_ROOT", str(PACKAGING_DIR / "runtime" / "libreoffice")))


def run(command: list[str], cwd: Path) -> None:
    print("[packaging]", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def ensure_tools() -> None:
    if not PYTHON.is_file():
        raise SystemExit(f"找不到项目 Python：{PYTHON}")
    if not (WEB_DIR / "package.json").is_file():
        raise SystemExit(f"找不到前端 package.json：{WEB_DIR}")
    run(
        [
            str(PYTHON),
            "-c",
            "import PyInstaller; print(PyInstaller.__version__)",
        ],
        ROOT,
    )


def build_frontend() -> None:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise SystemExit(
            "找不到 npm；打包机需要 Node.js 仅用于构建前端，用户运行包不需要 Node.js"
        )
    run([npm, "run", "build"], WEB_DIR)


def _base_runtime_binaries() -> list[Path]:
    """返回当前 Python 基座必须随 EXE 携带的 Conda DLL。"""
    conda_root = Path(sys.base_prefix)
    dll_root = conda_root / "Library" / "bin"
    names = [
        "ffi.dll",
        "libbz2.dll",
        "libcrypto-3-x64.dll",
        "libexpat.dll",
        "liblzma.dll",
        "libmpdec-4.dll",
        "libssl-3-x64.dll",
        "sqlite3.dll",
    ]
    missing = [dll_root / name for name in names if not (dll_root / name).is_file()]
    if missing:
        raise SystemExit(
            "Python 基座缺少必要 DLL：" + ", ".join(str(path) for path in missing)
        )
    return [dll_root / name for name in names]


def pyinstaller_args() -> list[str]:
    collect_data = [
        "pandas",
        "numpy",
        "scipy",
        "sklearn",
        "matplotlib",
        "seaborn",
        "openpyxl",
        "docx",
        "pptx",
        "pypdf",
        "lxml",
    ]
    # 这三个包没有足够完整的 PyInstaller hook，收集其运行时模块和数据。
    # pandas/scipy/matplotlib 等大包只收集 data，避免把 tests 打进发布包。
    collect_all = ["pptxforge", "easypptx", "resvg_py"]
    hidden_imports = [
        "pandas",
        "numpy",
        "scipy",
        "scipy.stats",
        "sklearn",
        "matplotlib",
        "matplotlib.pyplot",
        "seaborn",
        "openpyxl",
        "docx",
        "pptx",
        "pypdf",
        "resvg_py",
    ]
    args = [
        str(PYTHON),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        "service",
        "--distpath",
        str(PYI_DIST),
        "--workpath",
        str(PYI_WORK / "service"),
        "--specpath",
        str(PYI_SPEC),
        "--paths",
        str(SERVER_DIR),
        "--add-data",
        f"{SERVER_DIR / 'alembic'}{os.pathsep}alembic",
        "--add-data",
        f"{SERVER_DIR / 'alembic.ini'}{os.pathsep}.",
        "--add-data",
        f"{SERVER_DIR / 'app' / 'assets'}{os.pathsep}app/assets",
        "--collect-submodules",
        "app",
        "--collect-submodules",
        "worker",
        "--exclude-module",
        "tkinter",
        "--exclude-module",
        "_tkinter",
    ]
    for package in collect_data:
        args.extend(["--collect-data", package])
    for package in collect_all:
        args.extend(["--collect-all", package])
    for module in hidden_imports:
        args.extend(["--hidden-import", module])
    for dll in _base_runtime_binaries():
        args.extend(["--add-binary", f"{dll}{os.pathsep}."])
    args.append(str(PACKAGING_DIR / "service_entry.py"))
    return args


def build_service() -> Path:
    run(pyinstaller_args(), ROOT)
    service_dir = PYI_DIST / "service"
    service_exe = service_dir / "service.exe"
    if not service_exe.is_file():
        raise SystemExit(f"PyInstaller 未生成服务入口：{service_exe}")
    # 入口代码按程序名识别 sandbox_runner；复制 exe，不复制第二套运行时。
    shutil.copy2(service_exe, service_dir / "sandbox_runner.exe")
    return service_dir


def build_launcher() -> Path:
    launcher_dist = PYI_DIST / "launcher"
    launcher_work = PYI_WORK / "launcher"
    launcher_args = [
        str(PYTHON),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "实验报告助手",
        "--distpath",
        str(launcher_dist),
        "--workpath",
        str(launcher_work),
        "--specpath",
        str(PYI_SPEC),
    ]
    # 一文件启动器也会导入 ctypes，需要携带 Conda 基座 DLL。
    for dll in _base_runtime_binaries():
        launcher_args.extend(["--add-binary", f"{dll}{os.pathsep}."])
    launcher_args.append(str(PACKAGING_DIR / "launcher_entry.py"))
    run(launcher_args, ROOT)
    launcher = launcher_dist / "实验报告助手.exe"
    if not launcher.is_file():
        raise SystemExit(f"PyInstaller 未生成启动器：{launcher}")
    return launcher


def copy_libreoffice_runtime(release_dir: Path) -> Path:
    """复制随包提供的 LibreOffice runtime，并校验发布元数据。"""
    source = LIBREOFFICE_ROOT.resolve()
    executable = source / "program" / "soffice.exe"
    metadata_path = source / "runtime-metadata.json"
    if not executable.is_file():
        raise SystemExit(
            "缺少 LibreOffice runtime："
            f"{executable}；请设置 LIBREOFFICE_ROOT 指向已解压目录"
        )
    if not metadata_path.is_file():
        raise SystemExit(
            f"缺少 LibreOffice runtime 元数据：{metadata_path}"
        )
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"LibreOffice runtime 元数据无效：{exc}") from exc
    required = ("version", "source", "source_sha256", "license_files")
    missing = [key for key in required if not metadata.get(key)]
    if missing:
        raise SystemExit(
            "LibreOffice runtime 元数据缺少字段：" + ", ".join(missing)
        )
    source_sha256 = metadata["source_sha256"]
    if not isinstance(source_sha256, str) or not re.fullmatch(
        r"[0-9a-fA-F]{64}", source_sha256
    ):
        raise SystemExit(
            "LibreOffice runtime 元数据中的 source_sha256 无效：需要 64 位十六进制 SHA-256"
        )
    license_files = metadata["license_files"]
    if not isinstance(license_files, list) or not license_files:
        raise SystemExit(
            "LibreOffice runtime 元数据中的 license_files 无效：需要非空文件路径列表"
        )
    for relative_path in license_files:
        if not isinstance(relative_path, str) or not relative_path:
            raise SystemExit(
                "LibreOffice runtime 元数据中的 license_files 包含无效路径"
            )
        license_path = (source / relative_path).resolve()
        try:
            license_path.relative_to(source)
        except ValueError as exc:
            raise SystemExit(
                f"LibreOffice runtime 许可证路径越界：{relative_path}"
            ) from exc
        if not license_path.is_file():
            raise SystemExit(
                f"LibreOffice runtime 缺少许可证/归属文件：{license_path}"
            )
    target = release_dir / "libreoffice"
    shutil.copytree(source, target)
    return target


def copy_release(service_dir: Path, launcher: Path) -> Path:
    release_dir = RELEASE_ROOT / "实验报告助手-win-x64"
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True)
    shutil.copytree(service_dir, release_dir / "service")
    shutil.copytree(WEB_DIR / "dist", release_dir / "web")
    shutil.copy2(launcher, release_dir / "实验报告助手.exe")
    copy_libreoffice_runtime(release_dir)
    (release_dir / "README-使用说明.txt").write_text(
        "双击“实验报告助手.exe”启动。\n"
        "用户数据默认保存在 %LOCALAPPDATA%\\LabReportAssistant。\n"
        "如启动失败，请查看该目录下的 logs\\backend.log 和 worker.log。\n",
        encoding="utf-8",
    )
    return release_dir


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(release_dir: Path) -> None:
    files = []
    for path in sorted(release_dir.rglob("*")):
        if path.is_file() and path.name != "release-manifest.json":
            files.append(
                {
                    "path": str(path.relative_to(release_dir)).replace("\\", "/"),
                    "size": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    runtime_metadata = json.loads(
        (release_dir / "libreoffice" / "runtime-metadata.json").read_text(encoding="utf-8")
    )
    manifest = {
        "product": "实验报告助手",
        "platform": "windows-x64",
        "format": "portable-bundle",
        "entrypoint": "实验报告助手.exe",
        "runtime": "PyInstaller one-file launcher + one-directory service runtime",
        "pdf_converter": {
            "provider": "LibreOffice",
            "executable": "libreoffice/program/soffice.exe",
            "version": runtime_metadata["version"],
            "source": runtime_metadata["source"],
            "source_sha256": runtime_metadata["source_sha256"],
            "license_files": runtime_metadata["license_files"],
        },
        "files": files,
    }
    (release_dir / "release-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    os.environ["MPLBACKEND"] = "Agg"
    ensure_tools()
    build_frontend()
    service_dir = build_service()
    launcher = build_launcher()
    release_dir = copy_release(service_dir, launcher)
    write_manifest(release_dir)
    print(f"[packaging] 发布包已生成：{release_dir}", flush=True)


if __name__ == "__main__":
    main()
