"""HTML、PDF、TXT 解析文本和位置映射测试。"""

from io import BytesIO
import json

import pytest
from docx import Document

from app.core.errors import AppError
from app.infrastructure.documents.html_reader import extract_text as extract_html
from app.infrastructure.documents.pdf_reader import extract_text as extract_pdf
from app.infrastructure.documents.text_reader import extract_text as extract_txt
from app.modules.sources import service as source_service
from app.modules.sources.models import ParsedDocument


def test_html_reader_excludes_script_and_tracks_paragraphs():
    raw = b"""
    <html><head><title>Public Page</title><script>secret()</script></head>
    <body><h1>Heading</h1><p>First evidence.</p><p>Second evidence.</p></body>
    </html>
    """
    text, location = extract_html(raw)
    assert "secret()" not in text
    assert location["title"] == "Public Page"
    assert [block["label"] for block in location["blocks"]] == [
        "标题 Heading",
        "段落 1",
        "段落 2",
    ]
    first_paragraph = location["blocks"][1]
    assert text[first_paragraph["start"] : first_paragraph["end"]] == "First evidence."


def test_txt_reader_tracks_encoding_and_single_block():
    text, location = extract_txt("胃病资料".encode("gb18030"))
    assert text == "胃病资料"
    assert location["encoding"] == "gb18030"
    assert location["blocks"][0]["label"] == "全文"


def test_pdf_reader_tracks_each_page(pdf_with_text_bytes):
    text, location = extract_pdf(pdf_with_text_bytes)
    assert [block["label"] for block in location["blocks"]] == ["第 1 页", "第 2 页"]
    for block in location["blocks"]:
        assert text[block["start"] : block["end"]].strip()


def test_pdf_without_text_persists_structured_failure(db, project_with_plan):
    source = source_service.add_file_source(
        db,
        project_with_plan,
        "空白 PDF",
        "blank.pdf",
        b"%PDF-invalid",
        "application/pdf",
    )
    with pytest.raises(AppError) as exc:
        source_service.parse_source(db, project_with_plan, source.id)
    assert exc.value.code in {"SOURCE_PARSE_UNEXPECTED_ERROR", "SOURCE_PDF_TEXT_EMPTY"}

    db.expire_all()
    failed = (
        db.query(ParsedDocument).filter(ParsedDocument.source_id == source.id).first()
    )
    assert failed is not None
    assert failed.parse_status == "FAILED"
    assert json.loads(failed.location_map_json or "{}") == {}


def test_docx_source_tracks_full_text_block(db, project_with_plan):
    document = Document()
    document.add_paragraph("可定位的 Word 资料")
    buffer = BytesIO()
    document.save(buffer)
    source = source_service.add_file_source(
        db,
        project_with_plan,
        "Word 资料",
        "source.docx",
        buffer.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    parsed = source_service.parse_source(db, project_with_plan, source.id)
    location = json.loads(parsed.location_map_json or "{}")
    assert location["blocks"] == [
        {"label": "全文", "start": 0, "end": len(parsed.parsed_text)}
    ]
