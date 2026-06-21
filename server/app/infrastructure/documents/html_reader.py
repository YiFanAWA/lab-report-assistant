"""HTML 可见文本提取器，输出可回指原文的正文偏移块。"""

from html.parser import HTMLParser


class _VisibleTextParser(HTMLParser):
    _SKIP_TAGS = {"script", "style", "noscript", "iframe", "svg"}
    _BLOCK_TAGS = {
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "li",
        "td",
        "th",
        "blockquote",
        "pre",
    }

    def __init__(self):
        super().__init__()
        self.title_parts: list[str] = []
        self.raw_blocks: list[tuple[str, str]] = []
        self._active_tag: str | None = None
        self._active_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = True
            return
        if tag in self._BLOCK_TAGS:
            self._flush_block()
            self._active_tag = tag

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = False
            return
        if self._active_tag == tag:
            self._flush_block()

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        elif self._active_tag:
            self._active_parts.append(text)

    def _flush_block(self):
        text = " ".join(self._active_parts).strip()
        if self._active_tag and text:
            self.raw_blocks.append((self._active_tag, text))
        self._active_tag = None
        self._active_parts = []

    def close(self):
        self._flush_block()
        super().close()


def extract_text(html_bytes: bytes, max_length: int = 500_000) -> tuple[str, dict]:
    parser = _VisibleTextParser()
    parser.feed(html_bytes.decode("utf-8", errors="replace"))
    parser.close()

    text_parts: list[str] = []
    blocks: list[dict[str, int | str]] = []
    paragraph_number = 0
    offset = 0
    for tag, content in parser.raw_blocks:
        if tag.startswith("h"):
            label = f"标题 {content[:80]}"
        else:
            paragraph_number += 1
            label = f"段落 {paragraph_number}"
        start = offset
        end = start + len(content)
        text_parts.append(content)
        blocks.append({"label": label, "start": start, "end": end})
        offset = end + 2

    text = "\n\n".join(text_parts)[:max_length]
    clipped_blocks = []
    for block in blocks:
        if int(block["start"]) >= len(text):
            continue
        clipped_blocks.append(
            {
                **block,
                "end": min(int(block["end"]), len(text)),
            }
        )

    return text, {
        "source": "html",
        "title": " ".join(parser.title_parts).strip(),
        "blocks": clipped_blocks,
    }
