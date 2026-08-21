"""正式论文与答辩交付物的共享结构规划。

这里拥有交付物层的章节/页序语义；Word、PDF 和 PPT 渲染器只负责把计划
呈现为对应格式。规划器只重排已确认大纲与真实执行产物，不生成实验事实。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.modules.outlines.layout_planner import (
    LayoutKind,
    SectionLayoutPlan,
    plan_section_layouts,
)


@dataclass(frozen=True)
class ThesisChapterPlan:
    """论文一级章节及其原始大纲章节。"""

    number: int
    title: str
    sections: tuple[dict, ...]


@dataclass(frozen=True)
class ManuscriptPlan:
    """正式论文文档的结构计划。"""

    abstract: str
    keywords: tuple[str, ...]
    chapters: tuple[ThesisChapterPlan, ...]
    references: tuple[str, ...]
    citation_map: tuple[tuple[str, int], ...] = ()
    formal_title: str = ""
    formal_subtitle: str = ""
    formal_metadata: tuple[tuple[str, str], ...] = ()
    publication_profile: "PublicationProfile" | None = None
    sufficiency: "ContentSufficiencyReport" | None = None
    abstract_en: str = ""
    abstract_sections: tuple[tuple[str, str], ...] = ()
    abstract_sections_en: tuple[tuple[str, str], ...] = ()


ThesisDocumentPlan = ManuscriptPlan


class ManuscriptRole(str, Enum):
    """论文修辞角色；与证据来源类型相互独立。"""

    INTRODUCTION = "introduction"
    METHODS = "methods"
    RESULTS = "results"
    DISCUSSION = "discussion"
    CONCLUSION = "conclusion"


@dataclass(frozen=True)
class PublicationProfile:
    """由渲染器消费的明确出版版式合同。"""

    profile_id: str = "zh_academic_thesis"
    page_size: str = "A4"
    body_font_cjk: str = "宋体"
    body_font_latin: str = "Times New Roman"
    body_size_pt: float = 10.5
    line_spacing: float = 1.5
    first_line_indent_chars: float = 2.0
    page_margin_left_cm: float = 2.4
    page_margin_right_cm: float = 2.4
    page_margin_top_cm: float = 2.2
    page_margin_bottom_cm: float = 2.2
    title_size_pt: float = 22.0
    subtitle_size_pt: float = 13.0
    heading1_size_pt: float = 16.0
    heading2_size_pt: float = 12.0
    heading3_size_pt: float = 10.5
    caption_size_pt: float = 9.0
    text_color_hex: str = "222222"
    muted_color_hex: str = "6B7280"
    formal_monochrome: bool = True
    reader_first: bool = True
    include_audit_appendix: bool = False
    front_page_number_format: str = "lowerRoman"
    body_page_number_format: str = "decimal"


@dataclass(frozen=True)
class ContentIssue:
    """论文内容充分性问题。"""

    code: str
    severity: str
    manuscript_role: str
    message: str
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContentSufficiencyReport:
    """正式论文生成前的内容门禁报告。"""

    publishable: bool
    issues: tuple[ContentIssue, ...]


@dataclass(frozen=True)
class DefenseSlidePlan:
    """答辩 PPT 的一页语义计划。"""

    role: str
    title: str
    content: str
    layout_kind: LayoutKind
    chart_artifacts: tuple[dict, ...] = ()
    steps: tuple[str, ...] = ()
    metrics: tuple[tuple[str, str], ...] = ()
    figure_family: str = ""
    figure_lead: str = ""
    figure_takeaway: str = ""


@dataclass(frozen=True)
class DefenseDeckPlan:
    """答辩 PPT 的页序计划。"""

    slides: tuple[DefenseSlidePlan, ...]


_CHAPTER_TITLES = (
    ("REQUIREMENT", "绪论与实验要求"),
    ("EVIDENCE", "研究背景与资料"),
    ("DATASET", "数据与资料"),
    ("ANALYSIS", "方法与分析流程"),
    ("EXECUTION", "实验结果"),
    ("SUMMARY", "讨论、局限与结论"),
)

_FORMAL_ROLE_TITLES = (
    (ManuscriptRole.INTRODUCTION, "绪论"),
    (ManuscriptRole.METHODS, "研究设计与统计方法"),
    (ManuscriptRole.RESULTS, "结果"),
    (ManuscriptRole.DISCUSSION, "讨论"),
    (ManuscriptRole.CONCLUSION, "结论"),
)

_SOURCE_ROLE_FALLBACK = {
    "REQUIREMENT": ManuscriptRole.INTRODUCTION,
    "EVIDENCE": ManuscriptRole.INTRODUCTION,
    "DATASET": ManuscriptRole.METHODS,
    "ANALYSIS": ManuscriptRole.METHODS,
    "EXECUTION": ManuscriptRole.RESULTS,
    "SUMMARY": ManuscriptRole.DISCUSSION,
}

_NUMBERED_TITLE_RE = re.compile(
    r"^\s*(?:第\s*[一二三四五六七八九十百零〇\d]+\s*[章节篇]\s*|\d+(?:\.\d+)*\s*[、.．:]?\s*)"
)


def _normalize_section(section: dict) -> dict:
    normalized = dict(section)
    title = str(normalized.get("title", "")).strip()
    previous = None
    while title and title != previous:
        previous = title
        title = _NUMBERED_TITLE_RE.sub("", title).strip()
    normalized["title"] = title or "内容"
    return normalized


_READER_TEXT_REPLACEMENTS = (
    ("本地执行产物", "本地分析结果"),
    ("执行批次", "分析过程"),
    ("执行产物", "分析结果"),
    ("结果索引", "结果表"),
    ("文件列表", "结果罗列"),
)


def _reader_text(value: object) -> object:
    """Project engineering trace wording into reader-facing prose."""
    if not isinstance(value, str):
        return value
    projected = value
    for source, target in _READER_TEXT_REPLACEMENTS:
        projected = projected.replace(source, target)
    return projected


def _project_reader_section(section: dict) -> dict:
    """Construct the formal reader-first section projection."""
    projected = dict(section)
    for key in ("content", "figure_takeaway"):
        if key in projected:
            projected[key] = _reader_text(projected[key])
    if projected.get("paragraphs"):
        projected["paragraphs"] = [
            _reader_text(paragraph) for paragraph in projected["paragraphs"]
        ]
    if not projected.get("reader_figure_lead"):
        projected.pop("figure_lead", None)
    return projected


def _resolve_manuscript_role(section: dict) -> ManuscriptRole:
    declared = str(section.get("manuscript_role", "")).strip().lower()
    if declared:
        try:
            return ManuscriptRole(declared)
        except ValueError:
            pass
    return _SOURCE_ROLE_FALLBACK.get(
        str(section.get("source_type", "")).upper(),
        ManuscriptRole.DISCUSSION,
    )


def _build_formal_chapters(outline_sections: list[dict]) -> list[ThesisChapterPlan]:
    groups = {role: [] for role, _ in _FORMAL_ROLE_TITLES}
    for raw_section in outline_sections:
        section = _project_reader_section(_normalize_section(raw_section))
        groups[_resolve_manuscript_role(section)].append(section)

    chapters: list[ThesisChapterPlan] = []
    for role, title in _FORMAL_ROLE_TITLES:
        sections = groups[role]
        if not sections:
            continue
        chapters.append(
            ThesisChapterPlan(
                number=len(chapters) + 1,
                title=title,
                sections=tuple(sections),
            )
        )
    return chapters


def _content_sufficiency_report(
    outline_sections: list[dict],
    execution_artifacts: list[dict],
    reference_catalog: dict[str, str] | None,
) -> ContentSufficiencyReport:
    roles = {_resolve_manuscript_role(section) for section in outline_sections}
    source_ids = {
        str(source_id).strip()
        for section in outline_sections
        for source_id in (section.get("source_ids", []) or [])
        if str(source_id).strip()
    }
    has_result_artifact = any(
        artifact.get("artifact_type") in {
            "CHART_PNG", "TABLE_CSV", "CSV_TABLE", "SCIENTIFIC_SCHEMATIC",
        }
        for artifact in execution_artifacts
    )
    checks = (
        (not any(str(section.get("source_type", "")).upper() == "REQUIREMENT" or section.get("research_question") for section in outline_sections), "MANUSCRIPT_RESEARCH_QUESTION_MISSING", ManuscriptRole.INTRODUCTION, "缺少明确的研究问题或目标。"),
        (not any(str(section.get("source_type", "")).upper() == "DATASET" for section in outline_sections), "MANUSCRIPT_DATA_MISSING", ManuscriptRole.METHODS, "缺少真实数据来源、研究对象或样本说明。"),
        (ManuscriptRole.METHODS not in roles, "MANUSCRIPT_METHODS_MISSING", ManuscriptRole.METHODS, "缺少可复核的研究设计或统计方法。"),
        (ManuscriptRole.RESULTS not in roles or not has_result_artifact, "MANUSCRIPT_RESULTS_MISSING", ManuscriptRole.RESULTS, "缺少由真实执行产物支撑的结果。"),
        (ManuscriptRole.DISCUSSION not in roles, "MANUSCRIPT_DISCUSSION_MISSING", ManuscriptRole.DISCUSSION, "缺少回应结果的讨论与局限。"),
        (not reference_catalog or not any(source_id in reference_catalog for source_id in source_ids), "MANUSCRIPT_REFERENCES_MISSING", ManuscriptRole.INTRODUCTION, "缺少可列入参考文献表的外部来源。"),
    )
    issues = tuple(
        ContentIssue(code=code, severity="blocking", manuscript_role=role.value, message=message)
        for missing, code, role, message in checks
        if missing
    )
    return ContentSufficiencyReport(publishable=not issues, issues=issues)

def plan_thesis_document(
    project_topic: str,
    outline_sections: list[dict],
    execution_artifacts: list[dict],
    *,
    formal: bool = False,
    reference_catalog: dict[str, str] | None = None,
    abstract_override: str | None = None,
    abstract_en_override: str | None = None,
    abstract_sections_override: dict[str, str] | None = None,
    abstract_sections_en_override: dict[str, str] | None = None,
    formal_title: str = "",
    formal_subtitle: str = "",
    formal_metadata: dict[str, str] | None = None,
) -> ManuscriptPlan:
    """从已确认大纲生成正式论文的前置内容、章节和参考资料计划。"""

    if formal:
        chapters = _build_formal_chapters(outline_sections)
    else:
        groups: dict[str, list[dict]] = {source_type: [] for source_type, _ in _CHAPTER_TITLES}
        groups["OTHER"] = []
        for section in outline_sections:
            source_type = str(section.get("source_type", "OTHER")).upper()
            groups.setdefault(source_type, []).append(section)

        chapters = []
        for source_type, title in _CHAPTER_TITLES:
            sections = groups.get(source_type, [])
            if not sections:
                continue
            chapters.append(
                ThesisChapterPlan(
                    number=len(chapters) + 1,
                    title=title,
                    sections=tuple(sections),
                )
            )
        if groups["OTHER"]:
            chapters.append(
                ThesisChapterPlan(
                    number=len(chapters) + 1,
                    title="补充内容",
                    sections=tuple(groups["OTHER"]),
                )
            )

    summary_parts = [
        str(section.get("content", "")).strip()
        for section in outline_sections
        if section.get("source_type") == "SUMMARY" and section.get("content")
    ]
    if abstract_override:
        abstract = abstract_override.strip()
    elif summary_parts:
        abstract = " ".join(summary_parts)
    else:
        abstract_parts = [
            str(section.get("content", "")).strip()
            for section in outline_sections
            if section.get("source_type") in {"REQUIREMENT", "DATASET", "ANALYSIS"}
            and section.get("content")
        ]
        abstract = " ".join(abstract_parts[:3])
    abstract = abstract or "摘要内容未在已确认大纲中提供。"

    abstract_order = ("目的", "方法", "结果", "结论")
    abstract_sections = tuple(
        (label, str((abstract_sections_override or {}).get(label, "")).strip())
        for label in abstract_order
        if str((abstract_sections_override or {}).get(label, "")).strip()
    )
    abstract_order_en = ("Purpose", "Methods", "Results", "Conclusion")
    abstract_sections_en = tuple(
        (label, str((abstract_sections_en_override or {}).get(label, "")).strip())
        for label in abstract_order_en
        if str((abstract_sections_en_override or {}).get(label, "")).strip()
    )
    abstract_en = str(abstract_en_override or "").strip()
    if not abstract_en and abstract_sections_en:
        abstract_en = chr(32).join(f"{label}: {content}" for label, content in abstract_sections_en)

    keywords = _derive_keywords(project_topic, outline_sections)

    references: list[str] = []
    citation_map: list[tuple[str, int]] = []
    seen_source_ids: set[str] = set()
    for section in outline_sections:
        for source_id in section.get("source_ids", []) or []:
            label = str(source_id).strip()
            if not label or label in seen_source_ids:
                continue
            seen_source_ids.add(label)
            if reference_catalog and label in reference_catalog:
                citation_map.append((label, len(citation_map) + 1))
                references.append(f"[{len(citation_map)}] {reference_catalog[label]}")
            elif not formal and section.get("source_type") == "EVIDENCE":
                references.append(f"证据来源：{label}")
    if not references:
        if formal:
            references.append("本报告未提供可列入参考文献表的外部来源。")
        else:
            references.append("已确认大纲未提供可列入参考资料的外部来源。")

    # 让参数参与规划契约校验，避免未来将论文图表关系完全另起一套。
    plan_section_layouts(outline_sections, execution_artifacts)
    return ManuscriptPlan(
        abstract=abstract,
        keywords=keywords,
        chapters=tuple(chapters),
        references=tuple(references),
        citation_map=tuple(citation_map),
        formal_title=formal_title or project_topic,
        formal_subtitle=formal_subtitle,
        formal_metadata=tuple(
            (str(key), str(value))
            for key, value in (formal_metadata or {}).items()
            if not (
                formal
                and str(key).strip().lower()
                in {
                    "执行批次", "execution_run_id", "run_id", "sha256",
                    "artifact_id", "file_path", "json path", "json 路径",
                }
            )
        ),
        publication_profile=(PublicationProfile() if formal else None),
        sufficiency=(
            _content_sufficiency_report(
                outline_sections,
                execution_artifacts,
                reference_catalog,
            )
            if formal
            else None
        ),
        abstract_en=abstract_en,
        abstract_sections=abstract_sections,
        abstract_sections_en=abstract_sections_en,
    )


def plan_defense_deck(
    outline_sections: list[dict],
    execution_artifacts: list[dict],
) -> DefenseDeckPlan:
    """将论文章节压缩为问题—方法—结果—局限—结论答辩页序。"""

    section_plans = plan_section_layouts(outline_sections, execution_artifacts)
    results: list[DefenseSlidePlan] = []

    # SPEC 0036：论文解读案例可声明显式答辩角色。显式角色让案例把
    # “来源、样本、质量、模型、结果、局限”分别占据叙事页，避免所有
    # DATASET/EXECUTION 内容被旧的六类章节压扁成一页。
    explicit_plans = [
        plan for plan in section_plans if plan.presentation_role
    ]
    if explicit_plans:
        for plan in explicit_plans:
            role = plan.presentation_role
            steps = plan.steps
            if role in {"sample", "model"} and not steps:
                from app.modules.outlines.layout_planner import _extract_steps
                steps = _extract_steps(plan.content)
            metrics = plan.metrics
            results.append(
                DefenseSlidePlan(
                    role=role,
                    title=plan.title,
                    content=str(
                        plan.section.get("presentation_content", plan.content)
                    ),
                    layout_kind=plan.layout_kind,
                    chart_artifacts=plan.chart_artifacts,
                    steps=steps,
                    metrics=metrics,
                    figure_family=plan.figure_family,
                    figure_lead=str(plan.section.get("figure_lead", "")).strip(),
                    figure_takeaway=str(plan.section.get("figure_takeaway", "")).strip(),
                )
            )
        return DefenseDeckPlan(slides=tuple(results))

    narrative = [
        plan for plan in section_plans
        if plan.layout_kind == LayoutKind.NARRATIVE
    ]
    if narrative:
        results.append(
            DefenseSlidePlan(
                role="question",
                title="研究问题与目标",
                content="\n\n".join(plan.content for plan in narrative[:2]),
                layout_kind=LayoutKind.NARRATIVE,
            )
        )

    data_plans = [
        plan for plan in section_plans
        if plan.layout_kind == LayoutKind.DATA_OVERVIEW
    ]
    method_plans = [
        plan for plan in section_plans
        if plan.layout_kind == LayoutKind.METHOD_FLOW
    ]
    if data_plans:
        plan = data_plans[0]
        results.append(
            DefenseSlidePlan(
                role="data",
                title="数据概览",
                content=plan.content,
                layout_kind=LayoutKind.DATA_OVERVIEW,
                metrics=plan.metrics,
            )
        )
    if method_plans:
        plan = method_plans[0]
        results.append(
            DefenseSlidePlan(
                role="method",
                title="分析方法与流程",
                content=plan.content,
                layout_kind=LayoutKind.METHOD_FLOW,
                steps=plan.steps,
            )
        )

    for plan in section_plans:
        if plan.layout_kind not in {LayoutKind.RESULT_FOCUS, LayoutKind.RESULT_COMPARE}:
            continue
        # 答辩页每页最多承载两张结果图，避免 2×2 网格把图表压成缩略图。
        chart_chunks = (
            tuple(
                plan.chart_artifacts[index:index + 2]
                for index in range(0, len(plan.chart_artifacts), 2)
            )
            if plan.chart_artifacts
            else ((),)
        )
        for chunk_index, chart_chunk in enumerate(chart_chunks):
            results.append(
                DefenseSlidePlan(
                    role="result",
                    title=(
                        plan.title
                        if chunk_index == 0
                        else f"{plan.title}（补充证据）"
                    ),
                    content=(
                        plan.content
                        if chunk_index == 0
                        else "补充图表用于从不同角度核对同一结果。"
                    ),
                    layout_kind=(
                        LayoutKind.RESULT_FOCUS
                        if len(chart_chunk) == 1
                        else LayoutKind.RESULT_COMPARE
                    ),
                    chart_artifacts=chart_chunk,
                )
            )

    # 论文解读案例中的执行产物可能使用了不同 run_id，但仍属于同一份
    # 已确认结果集。将未被 EXECUTION 章节 source_ids 消费的真实图表补入
    # 结果页，避免它们全部落到末尾的“补充图表”页而脱离叙事主线。
    consumed_chart_ids = {
        id(artifact)
        for slide in results
        if slide.role == "result"
        for artifact in slide.chart_artifacts
    }
    remaining_charts = tuple(
        artifact
        for artifact in execution_artifacts
        if artifact.get("artifact_type") == "CHART_PNG"
        and id(artifact) not in consumed_chart_ids
    )
    if remaining_charts:
        for chunk_index in range(0, len(remaining_charts), 2):
            chart_chunk = tuple(remaining_charts[chunk_index:chunk_index + 2])
            results.append(
                DefenseSlidePlan(
                    role="result",
                    title=("关键复核结果" if chunk_index == 0 else "关键复核结果（补充）"),
                    content="公开数据复核结果：图表用于解释样本结构与结局差异，不替代论文原始回归模型。",
                    layout_kind=(
                        LayoutKind.RESULT_FOCUS
                        if len(chart_chunk) == 1
                        else LayoutKind.RESULT_COMPARE
                    ),
                    chart_artifacts=chart_chunk,
                )
            )

    summary_plans = [
        plan for plan in section_plans
        if plan.layout_kind == LayoutKind.SUMMARY
    ]
    if summary_plans:
        summary = "\n\n".join(plan.content for plan in summary_plans)
        results.append(
            DefenseSlidePlan(
                role="conclusion",
                title="结论、局限与可复核证据",
                content=summary,
                layout_kind=LayoutKind.SUMMARY,
            )
        )

    if not results:
        results.append(
            DefenseSlidePlan(
                role="conclusion",
                title="研究结论",
                content="已确认大纲未提供可用于答辩页的正文内容。",
                layout_kind=LayoutKind.SUMMARY,
            )
        )
    return DefenseDeckPlan(slides=tuple(results))


def _derive_keywords(project_topic: str, outline_sections: list[dict]) -> tuple[str, ...]:
    """只从题目和显式关键词字段生成关键词，不把章节标题当作论文关键词。"""

    candidates = re.split(r"[，、；：:（）()\-\s]+", str(project_topic or ""))
    for section in outline_sections:
        explicit = section.get("keywords", []) or []
        if isinstance(explicit, str):
            explicit = [explicit]
        candidates.extend(str(value) for value in explicit)

    keywords: list[str] = []
    for candidate in candidates:
        value = candidate.strip()
        if len(value) < 2 or value in keywords:
            continue
        keywords.append(value)
        if len(keywords) >= 5:
            break
    return tuple(keywords) or ("数据分析", "实验报告")
