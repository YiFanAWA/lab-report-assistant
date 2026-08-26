"""SPEC 0043 DOCX→PDF 单一出版链测试。"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.errors import AppError
from app.infrastructure.documents.docx_pdf_exporter import DocxPdfExporter


def test_exporter_rejects_non_docx_source(tmp_path: Path):
    source = tmp_path / "paper.txt"
    source.write_text("not a docx", encoding="utf-8")

    with pytest.raises(AppError) as error:
        DocxPdfExporter().export(source, tmp_path / "paper.pdf")

    assert error.value.code == "DOCX_PDF_SOURCE_INVALID"


def test_exporter_requires_existing_docx(tmp_path: Path):
    with pytest.raises(AppError) as error:
        DocxPdfExporter().export(tmp_path / "missing.docx", tmp_path / "paper.pdf")

    assert error.value.code == "DOCX_PDF_SOURCE_NOT_FOUND"


def test_exporter_uses_only_the_supplied_docx(monkeypatch, tmp_path: Path):
    source = tmp_path / "paper.docx"
    target = tmp_path / "paper.pdf"
    source.write_bytes(b"PK\x03\x04fixture")
    calls = []

    def fake_export(source_path: Path, target_path: Path) -> None:
        calls.append((source_path, target_path))
        target_path.write_bytes(b"%PDF-1.7\n%%EOF")

    exporter = DocxPdfExporter(word_export=fake_export)
    result = exporter.export(source, target)

    assert calls == [(source.resolve(), target.resolve())]
    assert result == target.resolve()


def test_configured_converter_uses_libreoffice_adapter(monkeypatch, tmp_path: Path):
    source = tmp_path / "paper.docx"
    target = tmp_path / "paper.pdf"
    source.write_bytes(b"PK\\x03\\x04fixture")
    converter = tmp_path / "soffice.exe"
    converter.write_bytes(b"runtime")
    calls = []

    exporter = DocxPdfExporter(converter_path=converter)

    def fake_export(source_path: Path, target_path: Path) -> None:
        calls.append((source_path, target_path))
        target_path.write_bytes(b"%PDF-1.7\\n%%EOF")

    monkeypatch.setattr(exporter, "_export_with_libreoffice", fake_export)
    result = exporter.export(source, target)

    assert calls == [(source.resolve(), target.resolve())]
    assert result == target.resolve()
    assert result.read_bytes().startswith(b"%PDF-")


def test_default_word_fallback_is_static_method(monkeypatch, tmp_path: Path):
    source = tmp_path / "paper.docx"
    target = tmp_path / "paper.pdf"
    source.write_bytes(b"PK\\x03\\x04fixture")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        env = kwargs["env"]
        Path(env["LAB_REPORT_ASSISTANT_PDF_PATH"]).write_bytes(b"%PDF-1.7\\n%%EOF")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "app.infrastructure.documents.docx_pdf_exporter.subprocess.run",
        fake_run,
    )
    exporter = DocxPdfExporter()
    exporter._converter_configured = False
    exporter._converter_path = None

    result = exporter.export(source, target)

