"""将最终 DOCX 原样导出为 PDF 的单一出版适配器。"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from app.core.errors import AppError


WordExport = Callable[[Path, Path], None]


class DocxPdfExporter:
    """只接受最终 DOCX，不接收第二份正文或布局计划。"""

    def __init__(
        self,
        word_export: WordExport | None = None,
        converter_path: str | Path | None = None,
        timeout_seconds: int | None = None,
    ):
        self._word_export = word_export
        configured = str(converter_path or os.getenv("PDF_CONVERTER_PATH", "")).strip()
        self._converter_configured = bool(configured)
        self._converter_path = self._resolve_converter(configured)
        self._timeout_seconds = timeout_seconds or int(
            os.getenv("PDF_CONVERTER_TIMEOUT_SECONDS", "120")
        )
        self._max_output_size_bytes = int(
            os.getenv("DELIVERABLE_MAX_SIZE_BYTES", str(50 * 1024 * 1024))
        )

    def export(self, source_docx: str | Path, target_pdf: str | Path) -> Path:
        source = Path(source_docx).resolve()
        target = Path(target_pdf).resolve()
        if source.suffix.lower() != ".docx":
            raise AppError(
                code="DOCX_PDF_SOURCE_INVALID",
                message="PDF 出版链只接受最终 DOCX 文件。",
                field="source_docx",
            )
        if not source.is_file():
            raise AppError(
                code="DOCX_PDF_SOURCE_NOT_FOUND",
                message="未找到待导出的最终 DOCX 文件。",
                field="source_docx",
            )
        if target.suffix.lower() != ".pdf":
            raise AppError(
                code="DOCX_PDF_TARGET_INVALID",
                message="PDF 输出路径必须使用 .pdf 扩展名。",
                field="target_pdf",
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self._word_export is not None:
                self._word_export(source, target)
            elif self._converter_configured:
                if self._converter_path is None:
                    raise AppError(
                        code="DOCX_PDF_CONVERTER_NOT_FOUND",
                        message="已配置的 PDF 转换器不可用。",
                        field="converter_path",
                    )
                self._export_with_libreoffice(source, target)
            elif self._converter_path is not None:
                self._export_with_libreoffice(source, target)
            else:
                self._export_with_word(source, target)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                code="DOCX_PDF_EXPORT_FAILED",
                message=f"PDF 导出失败：{exc}",
                field="target_pdf",
            ) from exc
        if not target.is_file():
            raise AppError(
                code="DOCX_PDF_EXPORT_INVALID",
                message="PDF 导出未生成有效文件。",
                field="target_pdf",
            )
        with target.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise AppError(
                    code="DOCX_PDF_EXPORT_INVALID",
                    message="PDF 导出未生成有效 PDF。",
                    field="target_pdf",
                )
        if target.stat().st_size > self._max_output_size_bytes:
            raise AppError(
                code="DOCX_PDF_EXPORT_TOO_LARGE",
                message="PDF 输出超过文件大小上限。",
                field="target_pdf",
            )
        return target

    @staticmethod
    def _resolve_converter(configured: str) -> Path | None:
        candidates = [configured] if configured else []
        for discovered in (shutil.which("soffice"), shutil.which("soffice.exe")):
            if discovered:
                candidates.append(discovered)
        for raw in candidates:
            candidate = Path(raw).expanduser()
            if candidate.is_dir():
                candidate = candidate / "program" / (
                    "soffice.exe" if os.name == "nt" else "soffice"
                )
            if candidate.is_file():
                return candidate.resolve()
        return None

    def _export_with_libreoffice(self, source: Path, target: Path) -> None:
        converter = self._converter_path
        if converter is None:
            raise AppError(
                code="DOCX_PDF_CONVERTER_NOT_FOUND",
                message="PDF 转换器不可用。",
                field="converter_path",
            )
        with tempfile.TemporaryDirectory(prefix="lab-report-pdf-") as raw_tmp:
            temp_root = Path(raw_tmp)
            output_dir = temp_root / "output"
            profile_dir = temp_root / "profile"
            output_dir.mkdir()
            profile_dir.mkdir()
            command = [
                str(converter),
                "--headless",
                f"-env:UserInstallation={profile_dir.as_uri()}",
                "--convert-to",
                "pdf:writer_pdf_Export",
                "--outdir",
                str(output_dir),
                str(source),
            ]
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise AppError(
                    code="DOCX_PDF_CONVERTER_TIMEOUT",
                    message="PDF 转换超过允许时限。",
                    field="source_docx",
                ) from exc
            except OSError as exc:
                raise AppError(
                    code="DOCX_PDF_CONVERTER_FAILED",
                    message="PDF 转换器无法启动。",
                    field="converter_path",
                ) from exc
            if completed.returncode != 0:
                raise AppError(
                    code="DOCX_PDF_CONVERTER_FAILED",
                    message="PDF 转换器执行失败。",
                    field="source_docx",
                )
            generated = output_dir / f"{source.stem}.pdf"
            if not generated.is_file():
                raise AppError(
                    code="DOCX_PDF_CONVERTER_INVALID",
                    message="PDF 转换器未生成输出文件。",
                    field="target_pdf",
                )
            shutil.copyfile(generated, target)
    def _export_with_word(source: Path, target: Path) -> None:
        """通过 PowerShell COM 调用本机 Word；不引入 Python COM 依赖。"""

        source_path = source.resolve()
        target_path = target.resolve()
        script = """
$ErrorActionPreference = 'Stop'
$sourcePath = $env:LAB_REPORT_ASSISTANT_DOCX_PATH
$targetPath = $env:LAB_REPORT_ASSISTANT_PDF_PATH
if ([string]::IsNullOrWhiteSpace($sourcePath) -or [string]::IsNullOrWhiteSpace($targetPath)) {
  throw 'DOCX/PDF path environment variables are missing.'
}
$word = $null
$document = $null
try {
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  $word.DisplayAlerts = 0
  $document = $word.Documents.Open($sourcePath)
  $document.Fields.Update() | Out-Null
  foreach ($toc in $document.TablesOfContents) { $toc.Update() }
  foreach ($tof in $document.TablesOfFigures) { $tof.Update() }
  $document.Repaginate()
  $document.ExportAsFixedFormat($targetPath, 17)
} finally {
  if ($document -ne $null) { $document.Close($false) }
  if ($word -ne $null) { $word.Quit() }
}
"""
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            env={
                **os.environ,
                "LAB_REPORT_ASSISTANT_DOCX_PATH": str(source_path),
                "LAB_REPORT_ASSISTANT_PDF_PATH": str(target_path),
            },
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise AppError(
                code="DOCX_PDF_WORD_UNAVAILABLE",
                message=("Microsoft Word PDF 导出不可用。" + (f" {detail}" if detail else "")),
                field="source_docx",
            )
