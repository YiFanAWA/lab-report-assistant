"""TXT 文本读取。

按 UTF-8 优先解析，失败时尝试常见中文编码。
输出带 start/end 偏移的位置块。
"""


def extract_text(txt_bytes: bytes) -> tuple[str, dict]:
    """从 TXT 字节流提取文本，返回 (文本, 位置信息)。"""
    encodings = ["utf-8", "gb18030", "big5", "latin-1"]
    text = ""
    encoding = "unknown"

    for enc in encodings:
        try:
            text = txt_bytes.decode(enc)
            encoding = enc
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if not text:
        text = txt_bytes.decode("utf-8", errors="replace")
        encoding = "utf-8-replace"

    blocks: list[dict] = []
    if text.strip():
        blocks.append({"label": "全文", "start": 0, "end": len(text)})

    return (text, {"source": "txt", "encoding": encoding, "blocks": blocks})
