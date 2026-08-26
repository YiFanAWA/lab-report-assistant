"""SPEC 0043 结果章节的论文图文节奏规划。

本模块只拥有“结果段落如何承接图形”的确定性投影，不拥有图形统计真相。
输入由已确认的 FigurePlan 或等价映射提供；工程追溯信息只进入独立 manifest，
不进入正文投影。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class RhythmValidationError(ValueError):
    """论文图文节奏合同不完整。"""


class ResultSemantic(StrEnum):
    """结果图在论证链中的语义位置。"""

    PRIMARY = "primary"
    STRATIFIED = "stratified"
    SENSITIVITY = "sensitivity"
    MECHANISM = "mechanism"
    EXPLORATORY = "exploratory"


class RhythmBeatKind(StrEnum):
    """一个结果段落的固定阅读节拍。"""

    LEAD = "lead"
    VISUAL = "visual"
    CAPTION = "caption"
    INTERPRETATION = "interpretation"
    BOUNDARY = "boundary"


_SEMANTIC_ORDER = {
    ResultSemantic.PRIMARY: 0,
    ResultSemantic.STRATIFIED: 1,
    ResultSemantic.SENSITIVITY: 2,
    ResultSemantic.MECHANISM: 3,
    ResultSemantic.EXPLORATORY: 4,
}

_SEMANTIC_ALIASES = {
    "primary": ResultSemantic.PRIMARY,
    "main": ResultSemantic.PRIMARY,
    "主要结果": ResultSemantic.PRIMARY,
    "主结果": ResultSemantic.PRIMARY,
    "stratified": ResultSemantic.STRATIFIED,
    "subgroup": ResultSemantic.STRATIFIED,
    "分层": ResultSemantic.STRATIFIED,
    "分层结果": ResultSemantic.STRATIFIED,
    "sensitivity": ResultSemantic.SENSITIVITY,
    "sensitivity_analysis": ResultSemantic.SENSITIVITY,
    "敏感性": ResultSemantic.SENSITIVITY,
    "敏感性分析": ResultSemantic.SENSITIVITY,
    "mechanism": ResultSemantic.MECHANISM,
    "机制": ResultSemantic.MECHANISM,
    "机制路径": ResultSemantic.MECHANISM,
    "exploratory": ResultSemantic.EXPLORATORY,
    "探索": ResultSemantic.EXPLORATORY,
    "探索性": ResultSemantic.EXPLORATORY,
}


@dataclass(frozen=True)
class RhythmBeat:
    """结果段落中的一个可渲染节拍。"""

    kind: RhythmBeatKind
    text: str
    figure_ref: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise RhythmValidationError(f"{self.kind.value} 节拍不能为空")
        if not self.figure_ref.strip():
            raise RhythmValidationError("节拍必须引用 figure_ref")


@dataclass(frozen=True)
class RhythmSequence:
    """一张结果图对应的一段 lead→visual→caption→interpretation→boundary。"""

    figure_ref: str
    title: str
    semantic: ResultSemantic
    beats: tuple[RhythmBeat, ...]
    artifact_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    execution_run_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.figure_ref.strip() or not self.title.strip():
            raise RhythmValidationError("结果节奏必须包含 figure_ref 和 title")
        expected = tuple(RhythmBeatKind)
        actual = tuple(beat.kind for beat in self.beats)
        if actual != expected:
            raise RhythmValidationError(
                "结果节奏必须严格遵循 lead→visual→caption→interpretation→boundary"
            )
        if any(beat.figure_ref != self.figure_ref for beat in self.beats):
            raise RhythmValidationError("同一结果节奏的所有 beat 必须引用同一 figure_ref")


@dataclass(frozen=True)
class ManuscriptRhythmPlan:
    """结果章节的确定性图文节奏计划。"""

    sequences: tuple[RhythmSequence, ...]
    chapter_role: str = "results"

    def __post_init__(self) -> None:
        if self.chapter_role != "results":
            raise RhythmValidationError("ManuscriptRhythmPlan 只负责 results 章节")
        if not self.sequences:
            raise RhythmValidationError("结果章节至少一项图文节奏")
        refs = [item.figure_ref for item in self.sequences]
        if len(refs) != len(set(refs)):
            raise RhythmValidationError("结果章节中的 figure_ref 不能重复")
        if tuple(sorted(self.sequences, key=lambda item: _SEMANTIC_ORDER[item.semantic])) != self.sequences:
            raise RhythmValidationError("结果图必须按 primary→stratified→sensitivity→mechanism 顺序")

    def body_projection(self) -> dict[str, object]:
        """输出正文所需的阅读内容，排除工程追溯信息。"""

        return {
            "chapter_role": self.chapter_role,
            "sequences": [
                {
                    "figure_ref": item.figure_ref,
                    "title": item.title,
                    "semantic": item.semantic.value,
                    "beats": [
                        {"kind": beat.kind.value, "figure_ref": beat.figure_ref, "text": beat.text}
                        for beat in item.beats
                    ],
                }
                for item in self.sequences
            ],
        }

    def traceability_manifest(self) -> dict[str, object]:
        """输出供 artifact/source 审计使用的独立追溯投影。"""

        return {
            "chapter_role": self.chapter_role,
            "sequences": [
                {
                    "figure_ref": item.figure_ref,
                    "semantic": item.semantic.value,
                    "artifact_ids": list(item.artifact_ids),
                    "source_ids": list(item.source_ids),
                    "execution_run_ids": list(item.execution_run_ids),
                }
                for item in self.sequences
            ],
        }


def classify_result_semantic(figure: object) -> ResultSemantic:
    """按显式 metadata、语义角色、标题的固定优先级识别结果语义。"""

    metadata = _field(figure, "metadata", {})
    if isinstance(metadata, Mapping):
        explicit = _normalize_semantic(metadata.get("result_semantic"))
        if explicit is not None:
            return explicit

    for value in (_field(figure, "semantic_role", ""), _field(figure, "title", "")):
        explicit = _normalize_semantic(value)
        if explicit is not None:
            return explicit
    return ResultSemantic.EXPLORATORY


def build_manuscript_rhythm_plan(figures: Sequence[object]) -> ManuscriptRhythmPlan:
    """把已确认图形规划转换为结果章节的确定性图文节奏。"""

    if not figures:
        raise RhythmValidationError("结果章节至少需要一张已确认图形")

    candidates = []
    for index, figure in enumerate(figures, start=1):
        candidates.append(_build_sequence(figure, index))
    candidates.sort(key=lambda item: (_SEMANTIC_ORDER[item.semantic], item.figure_ref))
    return ManuscriptRhythmPlan(sequences=tuple(candidates))


def _build_sequence(figure: object, index: int) -> RhythmSequence:
    title = _required_text(figure, "title", f"图 {index}")
    figure_ref = f"fig-{index}"
    semantic = classify_result_semantic(figure)
    caption = _required_text(figure, "caption", "")
    argument = _field(figure, "argument", {})
    result = _field(argument, "result", "") if argument else ""
    boundary = _field(argument, "boundary", "") if argument else ""
    result = str(result).strip()
    boundary = str(boundary).strip()
    if not result:
        raise RhythmValidationError(f"{title} 缺少 interpretation 结果文本")
    if not boundary:
        raise RhythmValidationError(f"{title} 缺少 boundary 解释边界")

    lead = _lead_text(title, semantic)
    beats = (
        RhythmBeat(RhythmBeatKind.LEAD, lead, figure_ref),
        RhythmBeat(RhythmBeatKind.VISUAL, f"见图 {index}：{title}", figure_ref),
        RhythmBeat(RhythmBeatKind.CAPTION, caption, figure_ref),
        RhythmBeat(RhythmBeatKind.INTERPRETATION, result, figure_ref),
        RhythmBeat(RhythmBeatKind.BOUNDARY, boundary, figure_ref),
    )
    return RhythmSequence(
        figure_ref=figure_ref,
        title=title,
        semantic=semantic,
        beats=beats,
        artifact_ids=_string_tuple(_field(figure, "data_artifact_ids", ())),
        source_ids=_string_tuple(_field(figure, "source_ids", ())),
        execution_run_ids=_string_tuple(_field(figure, "execution_run_ids", ())),
    )


def _lead_text(title: str, semantic: ResultSemantic) -> str:
    labels = {
        ResultSemantic.PRIMARY: "首先检验主要研究问题",
        ResultSemantic.STRATIFIED: "随后检验主要结果在分层人群中的一致性",
        ResultSemantic.SENSITIVITY: "进一步检验主要结果对分析设定的敏感性",
        ResultSemantic.MECHANISM: "最后讨论与结果相符的可能机制或关系路径",
        ResultSemantic.EXPLORATORY: "补充考察结果中的探索性模式",
    }
    return f"{labels[semantic]}：{title}。"


def _normalize_semantic(value: object) -> ResultSemantic | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in _SEMANTIC_ALIASES:
        return _SEMANTIC_ALIASES[normalized]
    for alias, semantic in _SEMANTIC_ALIASES.items():
        if alias and alias in normalized:
            return semantic
    return None


def _field(value: object, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _required_text(value: object, name: str, default: str) -> str:
    result = str(_field(value, name, default) or "").strip()
    if not result:
        raise RhythmValidationError(f"结果图缺少 {name}")
    return result


def _string_tuple(values: object) -> tuple[str, ...]:
    if isinstance(values, str):
        values = (values,)
    if values is None:
        return ()
    return tuple(str(value).strip() for value in values if str(value).strip())

