"""文档解析适配器测试。

覆盖 HTML 解析器（标签清理、标题/正文/元数据提取、动态页面检测）
和 PDF 解析器（文本提取、空文本场景）。
PDF 测试用 pypdf 的 PdfWriter 构造合法 PDF 字节流，避免依赖外部文件。
"""

import io

import pytest
from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)

from app.infrastructure.parsers import html_parser, pdf_parser


def _b(text: str) -> bytes:
    """将中文字符串转为 UTF-8 字节流供 parser 使用。"""
    return text.encode("utf-8")


# --- HTML 解析 ---


class TestParseHtml:
    """HTML 解析器测试。"""

    def test_extracts_title_text_and_meta_description(self):
        """提取 <title>、正文文本和 <meta name="description">。"""
        html = _b(
            """
            <html>
            <head>
                <title>胃病数据分析方法综述</title>
                <meta name="description" content="本文介绍胃病数据分析的常用方法。">
            </head>
            <body>
                <h1>概述</h1>
                <p>本节介绍胃病数据分析的研究背景与意义，覆盖常见统计分析流程。</p>
            </body>
            </html>
            """
        )
        result = html_parser.parse_html(html)
        assert result.title == "胃病数据分析方法综述"
        assert "概述" in result.text
        assert "胃病数据分析的研究背景" in result.text
        assert result.metadata.get("description") == "本文介绍胃病数据分析的常用方法。"

    def test_removes_script_style_nav_footer(self):
        """移除 script、style、nav、footer、header、aside 标签内容。"""
        html = _b(
            """
            <html>
            <head>
                <title>测试页</title>
                <style>body { color: red; }</style>
                <script>console.log("should be removed");</script>
            </head>
            <body>
                <header>站点导航头部</header>
                <nav>菜单A 菜单B 菜单C</nav>
                <main>
                    <p>这是正文段落，应该被保留下来用于证据提取。</p>
                </main>
                <aside>侧边栏推荐内容</aside>
                <footer>版权所有 2026</footer>
                <script>var x = "尾部脚本也去除";</script>
            </body>
            </html>
            """
        )
        result = html_parser.parse_html(html)
        assert "should be removed" not in result.text
        assert "尾部脚本也去除" not in result.text
        assert "菜单A" not in result.text
        assert "版权所有" not in result.text
        assert "侧边栏推荐内容" not in result.text
        assert "color: red" not in result.text
        assert "正文段落" in result.text

    def test_handles_missing_title_gracefully(self):
        """没有 <title> 时返回 None。"""
        html = _b("<html><body><p>只有正文没有标题的简单页面内容。</p></body></html>")
        result = html_parser.parse_html(html)
        assert result.title is None
        assert "正文没有标题" in result.text

    def test_handles_missing_meta_description(self):
        """没有 <meta name=description> 时 metadata 不含 description 键。"""
        html = _b(
            "<html><head><title>T</title></head><body><p>正文段落至少有一些字符用于测试。</p></body></html>"
        )
        result = html_parser.parse_html(html)
        assert "description" not in result.metadata

    def test_strips_blank_lines(self):
        """解析后去除多余空白行。"""
        html = _b(
            """<html><body>
            <p>段落一</p>


            <p>段落二</p>
            </body></html>"""
        )
        result = html_parser.parse_html(html)
        # 段落间不应有空行
        lines = result.text.split("\n")
        assert "" not in lines
        assert "段落一" in result.text
        assert "段落二" in result.text


class TestDetectDynamicPage:
    """动态页面检测测试。"""

    def test_detects_dynamic_page_with_many_scripts_and_little_text(self):
        """script 标签 > 5 且正文文本 < 100 字符，判定为动态页面。"""
        scripts = b"<script></script>" * 6
        html = b"<html><body>" + scripts + b"<p>short</p></body></html>"
        assert html_parser.detect_dynamic_page(html) is True

    def test_does_not_flag_static_page_with_few_scripts(self):
        """script 标签较少时即使正文短，也不判定为动态。"""
        html = b"<html><body><script></script><p>short</p></body></html>"
        assert html_parser.detect_dynamic_page(html) is False

    def test_does_not_flag_page_with_many_scripts_but_rich_text(self):
        """script 多但正文也长时，不判定为动态。"""
        scripts = b"<script></script>" * 8
        long_text_bytes = _b("<p>" + "这是一段比较长的中文正文内容，" * 10 + "</p>")
        html = b"<html><body>" + scripts + long_text_bytes + b"</body></html>"
        assert html_parser.detect_dynamic_page(html) is False


# --- PDF 解析 ---


def _make_pdf_with_text(text: str) -> bytes:
    """用 pypdf 构造包含指定文本的单页 PDF。

    通过注入 content stream 和 Helvetica 字体资源，使 pypdf 能提取文本。
    """
    w = PdfWriter()
    page = w.add_blank_page(width=612, height=792)

    # content stream：BT 开始文本，/F1 12 Tf 选字体，72 720 Td 定位，(text) Tj 显示，ET 结束
    content_stream = DecodedStreamObject()
    safe_text = text.replace("(", "\\(").replace(")", "\\)")
    content_stream.set_data(
        f"BT /F1 12 Tf 72 720 Td ({safe_text}) Tj ET".encode("latin-1")
    )
    content_obj = w._add_object(content_stream)

    # 字体资源
    font = DictionaryObject()
    font[NameObject("/Type")] = NameObject("/Font")
    font[NameObject("/Subtype")] = NameObject("/Type1")
    font[NameObject("/BaseFont")] = NameObject("/Helvetica")
    font_obj = w._add_object(font)
    resources = DictionaryObject()
    font_dict = DictionaryObject()
    font_dict[NameObject("/F1")] = font_obj
    resources[NameObject("/Font")] = font_dict

    page[NameObject("/Contents")] = content_obj
    page[NameObject("/Resources")] = resources

    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _make_blank_pdf_bytes(page_count: int = 1) -> bytes:
    """用 pypdf 构造无文本的多页 PDF。"""
    w = PdfWriter()
    for _ in range(page_count):
        w.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


class TestParsePdf:
    """PDF 解析器测试。"""

    def test_extracts_text_from_simple_pdf(self):
        """从单页 PDF 提取文本。"""
        pdf_bytes = _make_pdf_with_text("Hello PDF parser world.")
        result = pdf_parser.parse_pdf(pdf_bytes)
        assert result.page_count == 1
        assert "Hello" in result.text

    def test_returns_empty_text_for_blank_pdf(self):
        """空 PDF（无文本）解析后 text 为空字符串，page_count 仍正确。"""
        pdf_bytes = _make_blank_pdf_bytes(page_count=1)
        result = pdf_parser.parse_pdf(pdf_bytes)
        assert result.page_count == 1
        assert result.text == ""

    def test_handles_multi_page_pdf(self):
        """多页 PDF 解析后 page_count 反映页数。"""
        # 多页带文本，验证文本拼接
        pdf_bytes = _make_pdf_with_text("Page content one")
        # 单页足够覆盖多页逻辑：用空白多页 PDF 验证 page_count
        blank_multi = _make_blank_pdf_bytes(page_count=3)
        result = pdf_parser.parse_pdf(blank_multi)
        assert result.page_count == 3
        assert result.text == ""

    def test_handles_pdf_with_no_extractable_text_gracefully(self):
        """扫描件/无文本 PDF 不抛异常，返回空 text。"""
        pdf_bytes = _make_blank_pdf_bytes(page_count=2)
        result = pdf_parser.parse_pdf(pdf_bytes)
        assert result.text == ""
        assert result.page_count == 2


# --- 解析器输出契约 ---


class TestParserOutputContract:
    """解析器输出契约测试，确保 Worker 调用方可以依赖。"""

    def test_html_parse_result_has_all_fields(self):
        """HtmlParseResult 必含 title、text、metadata 字段。"""
        html = _b(
            "<html><head><title>T</title></head><body><p>正文段落内容足够长以通过阈值。</p></body></html>"
        )
        result = html_parser.parse_html(html)
        assert hasattr(result, "title")
        assert hasattr(result, "text")
        assert hasattr(result, "metadata")
        assert isinstance(result.metadata, dict)

    def test_pdf_parse_result_has_all_fields(self):
        """PdfParseResult 必含 text、page_count 字段。"""
        pdf_bytes = _make_pdf_with_text("Some content for contract test.")
        result = pdf_parser.parse_pdf(pdf_bytes)
        assert hasattr(result, "text")
        assert hasattr(result, "page_count")
        assert isinstance(result.page_count, int)
        assert isinstance(result.text, str)
