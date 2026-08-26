"""SPEC 0043 结果章节图文节奏合同测试。"""

from __future__ import annotations

import pytest

from app.modules.outlines.manuscript_rhythm import (
    ManuscriptRhythmPlan,
    RhythmBeatKind,
    RhythmValidationError,
    ResultSemantic,
    build_manuscript_rhythm_plan,
    classify_result_semantic,
)


def _figure(
    title: str,
    *,
    semantic: str | None = None,
    caption: str = "图中给出主要估计值及其不确定性。",
    result: str = "估计结果显示组间存在描述性差异。",
    boundary: str = "该结果来自观察性数据，不代表因果关系。",
    artifact_ids: tuple[str, ...] = ("artifact-result-1",),
    source_ids: tuple[str, ...] = ("source-paper-1",),
    execution_run_ids: tuple[str, ...] = ("run-1",),
) -> dict[str, object]:
    return {
        "title": title,
        "semantic_role": semantic or "结果分析",
        "caption": caption,
        "argument": {"result": result, "boundary": boundary},
        "data_artifact_ids": artifact_ids,
        "source_ids": source_ids,
        "execution_run_ids": execution_run_ids,
        "metadata": {
            "result_semantic": semantic,
            "file_path": r"D:\private\run\result.csv",
            "sha256": "deadbeef" * 8,
        },
    }


def test_result_semantic_is_deterministic_and_explicit_metadata_wins():
    assert classify_result_semantic(_figure("主结果", semantic="primary")) is ResultSemantic.PRIMARY
    assert classify_result_semantic(_figure("自定义标题", semantic="sensitivity")) is ResultSemantic.SENSITIVITY
    assert classify_result_semantic(_figure("分层结果", semantic=None)) is ResultSemantic.STRATIFIED


def test_plan_orders_result_semantics_and_emits_five_beats_per_figure():
    plan = build_manuscript_rhythm_plan(
        [
            _figure("敏感性分析", semantic="sensitivity"),
            _figure("机制路径", semantic="mechanism"),
            _figure("主要结果", semantic="primary"),
            _figure("分层结果", semantic="stratified"),
        ]
    )

    assert plan.chapter_role == "results"
    assert [item.semantic for item in plan.sequences] == [
        ResultSemantic.PRIMARY,
        ResultSemantic.STRATIFIED,
        ResultSemantic.SENSITIVITY,
        ResultSemantic.MECHANISM,
    ]
    assert all(
        [beat.kind for beat in item.beats]
        == [
            RhythmBeatKind.LEAD,
            RhythmBeatKind.VISUAL,
            RhythmBeatKind.CAPTION,
            RhythmBeatKind.INTERPRETATION,
            RhythmBeatKind.BOUNDARY,
        ]
        for item in plan.sequences
    )


def test_body_projection_keeps_reader_content_but_excludes_engineering_trace():
    plan = build_manuscript_rhythm_plan([_figure("主要结果")])

    projection = plan.body_projection()
    serialized = repr(projection)
    assert "artifact-result-1" not in serialized
    assert "source-paper-1" not in serialized
    assert "run-1" not in serialized
    assert "deadbeef" not in serialized
    assert "D:\\private" not in serialized
    assert projection["sequences"][0]["beats"][0]["kind"] == "lead"
    assert projection["sequences"][0]["beats"][2]["kind"] == "caption"
    assert "主要结果" in projection["sequences"][0]["beats"][0]["text"]


def test_traceability_projection_preserves_artifact_and_source_links_separately():
    plan = build_manuscript_rhythm_plan([_figure("主要结果")])

    traceability = plan.traceability_manifest()
    assert traceability["sequences"][0]["artifact_ids"] == ["artifact-result-1"]
    assert traceability["sequences"][0]["source_ids"] == ["source-paper-1"]
    assert traceability["sequences"][0]["execution_run_ids"] == ["run-1"]
    assert "file_path" not in traceability["sequences"][0]
    assert "sha256" not in traceability["sequences"][0]


def test_missing_result_or_boundary_is_rejected():
    with pytest.raises(RhythmValidationError, match="interpretation"):
        build_manuscript_rhythm_plan(
            [_figure("主要结果", result="", boundary="边界说明")]
        )


def test_empty_result_chapter_is_rejected():
    with pytest.raises(RhythmValidationError, match="至少一项"):
        ManuscriptRhythmPlan(sequences=())

