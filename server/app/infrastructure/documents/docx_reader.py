""".docx  文件简单正文提取。

只提取段落文本，不解析表格、图片、宏。
"""

from docx import Document


def extract_text(file_data: bytes) -> str:
    """从 .docx 文件字节流中提取段落文本。"""
    from io import BytesIO
    doc = Document(BytesIO(file_data))
    paragraphs = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)
