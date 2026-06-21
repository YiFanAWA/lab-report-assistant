"""PDF 文本提取。

只提取可复制文本和页码，不做 OCR。
输出带 start/end 偏移的位置块。
"""


def extract_text(pdf_bytes: bytes) -> tuple[str, dict]:
    """从 PDF 字节流提取文本，返回 (文本, 位置信息)。"""
    try:
        from pypdf import PdfReader
    except ImportError:
        return ("", {"error": "pypdf not installed", "blocks": []})

    from io import BytesIO
    reader = PdfReader(BytesIO(pdf_bytes))
    text_parts: list[str] = []
    blocks: list[dict] = []
    char_count = 0

    for i, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        page_text = page_text.strip()
        if page_text:
            label = f"第 {i + 1} 页"
            start = char_count
            text_parts.append(page_text)
            end = char_count + len(page_text)
            blocks.append({"label": label, "start": start, "end": end})
            char_count += len(page_text) + 2

    return ("\n\n".join(text_parts), {"source": "pdf", "pages": len(reader.pages), "blocks": blocks})
