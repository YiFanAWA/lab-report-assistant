"""PDF 文档解析适配器。

使用 pypdf 提取 PDF 文本内容，不解析表单、宏或扫描件。
"""

import io
from dataclasses import dataclass

from pypdf import PdfReader


@dataclass
class PdfParseResult:
    """PDF 解析结果。"""

    text: str
    page_count: int


def parse_pdf(content: bytes) -> PdfParseResult:
    """解析 PDF 字节流，提取所有页面文本。"""
    reader = PdfReader(io.BytesIO(content))
    page_texts: list[str] = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        page_texts.append(page_text)

    text = "\n\n".join(part for part in page_texts if part)

    return PdfParseResult(
        text=text,
        page_count=len(reader.pages),
    )
