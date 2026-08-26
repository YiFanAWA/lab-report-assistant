"""SPEC 0043 发布链验收脚本。

只读检查 manifest、DOCX、PDF 与 PPTX 的可交付性，并输出结构化 PASS/FAIL。
示例：
    python verify_spec0043_publication_chain.py --manifest path/to/manifest.json
    python verify_spec0043_publication_chain.py --docx a.docx --pdf a.pdf --pptx a.pptx
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


EMU_PER_INCH = 914400
PPT_WIDE_EMU = (12192000, 6858000)
PPT_STANDARD_EMU = (9144000, 6858000)
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


@dataclass
class Check:
    name: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PptxMetrics:
    slides: int
    width: int
    height: int
    image_count: int
    title_min_font_pt: float | None
    body_min_font_pt: float | None
    caption_min_font_pt: float | None
    max_image_ratio: float


def check(name: str, ok: bool, message: str, **details: Any) -> Check:
    return Check(name, "PASS" if ok else "FAIL", message, details)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def first_path(value: Any, keys: Iterable[str]) -> Path | None:
    if not isinstance(value, dict):
        return None
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate:
            return Path(candidate)
    return None


def find_artifact(root: Path, suffixes: tuple[str, ...], preferred: str | None = None) -> Path | None:
    if preferred:
        path = Path(preferred)
        if path.exists():
            return path
        candidate = root / preferred
        if candidate.exists():
            return candidate
    files = sorted(p for suffix in suffixes for p in root.rglob(f"*{suffix}") if p.is_file())
    return files[0] if files else None


def resolve_manifest_paths(manifest_path: Path, payload: Any) -> dict[str, Path]:
    root = manifest_path.parent
    result: dict[str, Path] = {}
    names = {
        "docx": ("docx", "word", "word_path", "document", "document_path", "file_path", "path"),
        "pdf": ("pdf", "pdf_path", "file_path", "path"),
        "pptx": ("pptx", "ppt", "pptx_path", "presentation", "presentation_path", "file_path", "path"),
    }
    containers: list[Any] = []
    if isinstance(payload, dict):
        for key in ("deliverables", "artifacts"):
            value = payload.get(key)
            if isinstance(value, dict):
                containers.append(value)
            elif isinstance(value, list):
                containers.extend(item for item in value if isinstance(item, dict))

    kind_tokens = {
        "docx": ("docx", "word", "document"),
        "pdf": ("pdf",),
        "pptx": ("pptx", "ppt", "presentation", "powerpoint"),
    }
    artifacts_are_list = isinstance(payload.get("artifacts") if isinstance(payload, dict) else None, list)
    for kind, keys in names.items():
        for container in containers:
            path = first_path(container, keys)
            if path is None:
                continue
            if artifacts_are_list and container in containers:
                labels = " ".join(
                    str(container.get(key, ""))
                    for key in ("artifact_type", "kind", "type", "name")
                ).lower()
                suffix = path.suffix.lower()
                if labels and not any(token in labels for token in kind_tokens[kind]):
                    if suffix != f".{kind}":
                        continue
            result[kind] = path if path.is_absolute() else root / path
            break
    return result


def verify_manifest(path: Path | None) -> Check:
    if path is None:
        return check("manifest", False, "未提供 manifest")
    if not path.is_file():
        return check("manifest", False, "manifest 不存在", path=str(path))
    try:
        payload = read_json(path)
    except (OSError, ValueError) as exc:
        return check("manifest", False, "manifest 不是有效 JSON", path=str(path), error=str(exc))
    if not isinstance(payload, dict):
        return check("manifest", False, "manifest 顶层必须是对象", path=str(path))

    missing = ["spec"] if "spec" not in payload else []
    container_name = next(
        (
            key
            for key in ("deliverables", "artifacts")
            if isinstance(payload.get(key), (dict, list))
        ),
        None,
    )
    container = payload.get(container_name) if container_name else None
    if container_name is None:
        missing.append("deliverables or artifacts(object/list)")
    elif container_name == "deliverables":
        required_deliverables = ("docx", "pdf", "pptx")
        missing.extend(
            f"deliverables.{key}"
            for key in required_deliverables
            if not isinstance(container, dict) or not isinstance(container.get(key), str) or not container[key]
        )
    if missing:
        return check("manifest", False, "manifest 缺少必需字段", path=str(path), missing=missing)
    return check(
        "manifest",
        True,
        "manifest 可解析且包含发布链字段",
        path=str(path),
        spec=payload.get("spec"),
        container=container_name,
        artifact_keys=list(container) if isinstance(container, dict) else len(container),
    )


def xml_from_zip(archive: zipfile.ZipFile, name: str) -> ET.Element | None:
    try:
        return ET.fromstring(archive.read(name))
    except (KeyError, ET.ParseError, OSError):
        return None


def verify_docx(path: Path | None) -> list[Check]:
    if path is None or not path.is_file():
        return [check("docx", False, "DOCX 不存在", path=str(path) if path else None)]
    try:
        with zipfile.ZipFile(path) as archive:
            document = xml_from_zip(archive, "word/document.xml")
            settings = xml_from_zip(archive, "word/settings.xml")
            header_names = [n for n in archive.namelist() if n.startswith("word/header") and n.endswith(".xml")]
            footer_names = [n for n in archive.namelist() if n.startswith("word/footer") and n.endswith(".xml")]
            media = [n for n in archive.namelist() if n.startswith("word/media/") and not n.endswith("/")]
    except (zipfile.BadZipFile, OSError) as exc:
        return [check("docx", False, "DOCX 不是有效压缩包", path=str(path), error=str(exc))]
    if document is None:
        return [check("docx", False, "缺少 word/document.xml", path=str(path))]

    sections = document.findall(".//w:sectPr", NS)
    paragraphs = document.findall(".//w:p", NS)
    field_codes = [node.text or "" for node in document.iter() if local_name(node.tag) == "instrText"]
    field_text = " ".join(field_codes).upper()
    required_fields = ("TOC", "SEQ FIGURE", "SEQ TABLE", "REF", "PAGEREF", "PAGE")
    missing_fields = [field for field in required_fields if field not in field_text]
    has_page_number = "PAGE" in field_text or any("PAGE" in (ET.tostring(ET.fromstring(b"<x/>"), encoding="unicode") if False else "") for _ in ())
    checks = [
        check("docx.open", True, "DOCX 可读取", path=str(path), bytes=path.stat().st_size),
        check("docx.sections", len(sections) >= 2, "DOCX 至少包含前置页与正文节", count=len(sections)),
        check("docx.media", len(media) >= 1, "DOCX 包含论文图形媒体", count=len(media), files=media),
        check(
            "docx.fields",
            not missing_fields and has_page_number,
            "DOCX 包含目录、图表编号、交叉引用与页码字段" if not missing_fields and has_page_number else "DOCX 字段不完整",
            found=sorted(set(field for field in required_fields if field in field_text)),
            missing=missing_fields,
        ),
        check(
            "docx.structure",
            len(paragraphs) >= 10 and (settings is not None or bool(header_names) or bool(footer_names)),
            "DOCX 具备正文结构与页面配置",
            paragraphs=len(paragraphs),
            headers=len(header_names),
            footers=len(footer_names),
        ),
    ]
    return checks


def pdf_page_count(path: Path) -> int:
    data = path.read_bytes()
    return len(re.findall(rb"/Type\s*/Page(?:\s|/|>)", data))


def verify_pdf(path: Path | None, minimum_pages: int = 2) -> Check:
    if path is None or not path.is_file():
        return check("pdf", False, "PDF 不存在", path=str(path) if path else None)
    try:
        data = path.read_bytes()
        signature = data[:5] == b"%PDF-"
        pages = pdf_page_count(path)
    except OSError as exc:
        return check("pdf", False, "PDF 无法读取", path=str(path), error=str(exc))
    return check(
        "pdf",
        signature and pages >= minimum_pages,
        "PDF 签名与页数通过" if signature and pages >= minimum_pages else "PDF 签名或页数不通过",
        path=str(path),
        signature=signature,
        pages=pages,
        minimum_pages=minimum_pages,
    )


def _pptx_text_role(shape: ET.Element, text: str) -> str:
    offset = shape.find("p:spPr/a:xfrm/a:off", NS)
    if offset is None:
        offset = shape.find(".//a:xfrm/a:off", NS)
    top = int(offset.attrib.get("y", "0")) if offset is not None else None
    if top is not None and top < int(1.2 * EMU_PER_INCH):
        return "title"
    if "图" in text or "来源" in text:
        return "caption"
    return "body"


def pptx_metrics(path: Path) -> PptxMetrics:
    with zipfile.ZipFile(path) as archive:
        presentation = xml_from_zip(archive, "ppt/presentation.xml")
        if presentation is None:
            raise ValueError("缺少 ppt/presentation.xml")
        size = presentation.find("p:sldSz", NS)
        width = int(size.attrib.get("cx", "0")) if size is not None else 0
        height = int(size.attrib.get("cy", "0")) if size is not None else 0
        slide_names = sorted(n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n))
        image_count = 0
        role_min_font_pt: dict[str, float | None] = {"title": None, "body": None, "caption": None}
        slide_area = max(width * height, 1)
        max_image_ratio = 0.0
        for name in slide_names:
            root = xml_from_zip(archive, name)
            if root is None:
                continue
            image_count += len(root.findall(".//p:pic", NS))
            for pic in root.findall(".//p:pic", NS):
                extent = pic.find(".//a:xfrm/a:ext", NS)
                if extent is not None:
                    area = int(extent.attrib.get("cx", "0")) * int(extent.attrib.get("cy", "0"))
                    max_image_ratio = max(max_image_ratio, area / slide_area)
            slide_number = int(re.search(r"slide(\d+)\.xml$", name).group(1))
            if slide_number == 1:
                continue
            for shape in root.findall(".//p:sp", NS):
                text = "".join(node.text or "" for node in shape.findall(".//a:t", NS)).strip()
                if not text:
                    continue
                role = _pptx_text_role(shape, text)
                for size_node in shape.findall(".//a:defRPr", NS) + shape.findall(".//a:rPr", NS):
                    raw = size_node.attrib.get("sz")
                    if not raw or not raw.isdigit():
                        continue
                    value = int(raw) / 100
                    current = role_min_font_pt[role]
                    role_min_font_pt[role] = value if current is None else min(current, value)
        return PptxMetrics(
            slides=len(slide_names),
            width=width,
            height=height,
            image_count=image_count,
            title_min_font_pt=role_min_font_pt["title"],
            body_min_font_pt=role_min_font_pt["body"],
            caption_min_font_pt=role_min_font_pt["caption"],
            max_image_ratio=max_image_ratio,
        )


def verify_pptx(
    path: Path | None,
    minimum_slides: int = 8,
    minimum_font_pt: float = 18.0,
    minimum_image_ratio: float = 0.35,
    minimum_title_font_pt: float = 35.0,
    minimum_caption_font_pt: float = 12.0,
) -> list[Check]:
    if path is None or not path.is_file():
        return [check("pptx", False, "PPTX 不存在", path=str(path) if path else None)]
    try:
        metrics = pptx_metrics(path)
    except (OSError, zipfile.BadZipFile, ValueError, AttributeError) as exc:
        return [check("pptx", False, "PPTX 无法解析", path=str(path), error=str(exc))]
    wide_or_standard = (metrics.width, metrics.height) in (PPT_WIDE_EMU, PPT_STANDARD_EMU)
    title_ok = metrics.title_min_font_pt is None or metrics.title_min_font_pt >= minimum_title_font_pt
    body_ok = metrics.body_min_font_pt is None or metrics.body_min_font_pt >= minimum_font_pt
    caption_ok = metrics.caption_min_font_pt is None or metrics.caption_min_font_pt >= minimum_caption_font_pt
    font_details = {
        "minimum_title_pt": minimum_title_font_pt,
        "observed_title_pt": metrics.title_min_font_pt,
        "minimum_body_pt": minimum_font_pt,
        "observed_body_pt": metrics.body_min_font_pt,
        "minimum_caption_pt": minimum_caption_font_pt,
        "observed_caption_pt": metrics.caption_min_font_pt,
    }
    return [
        check("pptx.slides", metrics.slides >= minimum_slides, "PPT 页数通过" if metrics.slides >= minimum_slides else "PPT 页数不足", slides=metrics.slides, minimum=minimum_slides),
        check("pptx.size", wide_or_standard, "PPT 尺寸为标准 16:9 或 4:3", width=metrics.width, height=metrics.height),
        check("pptx.font.title", title_ok, "PPT 标题字号通过" if title_ok else "PPT 标题字号过小", **font_details),
        check("pptx.font.body", body_ok, "PPT 正文字号通过" if body_ok else "PPT 正文字号过小", **font_details),
        check("pptx.font.caption", caption_ok, "PPT 图注字号通过" if caption_ok else "PPT 图注字号过小", **font_details),
        check("pptx.font", title_ok and body_ok and caption_ok, "PPT 分级字号通过" if title_ok and body_ok and caption_ok else "PPT 存在不符合分级合同的字号", **font_details),
        check("pptx.main_visual", metrics.image_count >= 1 and metrics.max_image_ratio >= minimum_image_ratio, "PPT 主图占比通过" if metrics.image_count >= 1 and metrics.max_image_ratio >= minimum_image_ratio else "PPT 缺少足够大的主图", image_count=metrics.image_count, maximum_image_ratio=round(metrics.max_image_ratio, 4), minimum_ratio=minimum_image_ratio),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="验证 SPEC 0043 论文与答辩发布链")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--docx", type=Path)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--pptx", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="未显式提供产物时搜索的目录")
    parser.add_argument("--minimum-pdf-pages", type=int, default=2)
    parser.add_argument("--minimum-slides", type=int, default=8)
    parser.add_argument("--minimum-font-pt", type=float, default=18.0)
    parser.add_argument("--minimum-title-font-pt", type=float, default=35.0)
    parser.add_argument("--minimum-caption-font-pt", type=float, default=12.0)
    parser.add_argument("--minimum-image-ratio", type=float, default=0.35)
    args = parser.parse_args(argv)

    manifest_payload: Any = None
    if args.manifest and args.manifest.is_file():
        try:
            manifest_payload = read_json(args.manifest)
        except (OSError, ValueError):
            manifest_payload = None
    manifest_check = verify_manifest(args.manifest)
    from_manifest = (
        resolve_manifest_paths(args.manifest, manifest_payload)
        if args.manifest and manifest_payload and manifest_check.status == "PASS"
        else {}
    )
    if args.manifest:
        docx = args.docx or from_manifest.get("docx")
        pdf = args.pdf or from_manifest.get("pdf")
        pptx = args.pptx or from_manifest.get("pptx")
    else:
        docx = args.docx or find_artifact(args.root, (".docx",))
        pdf = args.pdf or find_artifact(args.root, (".pdf",))
        pptx = args.pptx or find_artifact(args.root, (".pptx", ".ppt"))
    checks = [manifest_check]
    checks.extend(verify_docx(docx))
    checks.append(verify_pdf(pdf, args.minimum_pdf_pages))
    checks.extend(
        verify_pptx(
            pptx,
            args.minimum_slides,
            args.minimum_font_pt,
            args.minimum_image_ratio,
            args.minimum_title_font_pt,
            args.minimum_caption_font_pt,
        )
    )
    failed = [item for item in checks if item.status == "FAIL"]
    result = {
        "spec": "0043",
        "status": "FAIL" if failed else "PASS",
        "checks": [asdict(item) for item in checks],
        "artifacts": {"manifest": str(args.manifest) if args.manifest else None, "docx": str(docx) if docx else None, "pdf": str(pdf) if pdf else None, "pptx": str(pptx) if pptx else None},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
