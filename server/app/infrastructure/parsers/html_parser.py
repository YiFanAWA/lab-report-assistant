"""HTML 文档解析适配器。

使用 BeautifulSoup + lxml 解析 HTML，提取标题、正文和基础元数据。
不执行 HTML 中的脚本，不渲染动态内容。
"""

from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass
class HtmlParseResult:
    """HTML 解析结果。"""

    title: str | None
    text: str
    metadata: dict


_NON_CONTENT_TAGS = ("script", "style", "nav", "footer", "header", "aside")


def parse_html(content: bytes) -> HtmlParseResult:
    """解析 HTML 字节流，提取正文和元数据。"""
    soup = BeautifulSoup(content, "lxml")

    # 提取标题
    title_tag = soup.find("title")
    title: str | None = None
    if title_tag and title_tag.get_text(strip=True):
        title = title_tag.get_text(strip=True)

    # 提取 meta description
    metadata: dict = {}
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        metadata["description"] = meta_desc["content"].strip()

    # 移除非正文标签
    for tag_name in _NON_CONTENT_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # 提取 body 文本
    body = soup.find("body")
    if body is not None:
        raw_text = body.get_text(separator="\n")
    else:
        raw_text = soup.get_text(separator="\n")

    # 去除多余空白
    lines = [line.strip() for line in raw_text.splitlines()]
    text = "\n".join(line for line in lines if line)

    return HtmlParseResult(
        title=title,
        text=text,
        metadata=metadata,
    )


def detect_dynamic_page(content: bytes) -> bool:
    """检测是否为动态网页。

    判定标准：`<script>` 标签数量 > 5 且正文文本去空白后长度 < 100。
    """
    soup = BeautifulSoup(content, "lxml")
    script_count = len(soup.find_all("script"))

    body = soup.find("body")
    if body is not None:
        raw_text = body.get_text(separator=" ")
    else:
        raw_text = soup.get_text(separator=" ")
    body_text = "".join(raw_text.split())

    return script_count > 5 and len(body_text) < 100
