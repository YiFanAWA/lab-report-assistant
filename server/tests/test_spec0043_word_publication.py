import zipfile
from pathlib import Path

import pytest
from docx import Document

from app.core.errors import AppError
from app.infrastructure.renderers.word_renderer import WordRenderer


def _valid_sections() -> list[dict]:
    return [
        {
            "title": "研究问题",
            "content": "本研究比较不同分组的主要结果。",
            "source_type": "REQUIREMENT",
            "source_ids": ["req-1"],
        },
        {
            "title": "数据来源",
            "content": "研究对象来自公开数据集。",
            "source_type": "DATASET",
            "source_ids": ["data-1"],
        },
        {
            "title": "统计方法",
            "content": "采用描述性统计和分层比较。",
            "source_type": "ANALYSIS",
            "source_ids": ["method-1"],
        },
        {
            "title": "主要结果",
            "content": "主要结果见图示。",
            "source_type": "EXECUTION",
            "source_ids": ["run-1"],
        },
        {
            "title": "讨论与局限",
            "content": "结果仅支持描述性解释，不能替代因果推断。",
            "source_type": "SUMMARY",
            "source_ids": ["discussion-1"],
        },
    ]


def _formal_config() -> dict:
    return {
        "document_profile": "formal_academic",
        "reference_catalog": {
            "req-1": "研究要求说明。",
            "data-1": "公开数据集说明。",
            "method-1": "统计方法说明。",
            "run-1": "本地执行记录。",
            "discussion-1": "讨论依据。",
        },
    }


def _xml_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def test_formal_rejects_unpublishable_plan_with_issue_codes(tmp_path):
    output = tmp_path / "blocked.docx"

    with pytest.raises(AppError) as captured:
        WordRenderer().render(
            project_name="项目",
            project_topic="不完整论文",
            outline_sections=[],
            execution_artifacts=[],
            output_path=str(output),
            config={"document_profile": "formal_academic"},
        )

    error = captured.value
    assert error.code == "WORD_CONTENT_NOT_PUBLISHABLE"
    assert set(error.codes) >= {
        "MANUSCRIPT_RESEARCH_QUESTION_MISSING",
        "MANUSCRIPT_DATA_MISSING",
        "MANUSCRIPT_METHODS_MISSING",
        "MANUSCRIPT_RESULTS_MISSING",
        "MANUSCRIPT_DISCUSSION_MISSING",
        "MANUSCRIPT_REFERENCES_MISSING",
    }
    assert error.field == "sufficiency"
    assert not output.exists()


def test_formal_document_contains_real_publication_fields_and_sections(tmp_path):
    image = tmp_path / "result.png"
    from PIL import Image

    Image.new("RGB", (320, 180), "white").save(image)
    output = tmp_path / "formal.docx"

    WordRenderer().render(
        project_name="正式论文项目",
        project_topic="公开数据分析",
        outline_sections=_valid_sections(),
        execution_artifacts=[
            {
                "name": "主要结果.png",
                "artifact_type": "CHART_PNG",
                "file_path": str(image),
                "execution_run_id": "run-1",
                "figure_caption": "分组结果与不确定性区间",
                "figure_body_reference": "主要结果段落",
            },
            {
                "name": "summary.csv",
                "artifact_type": "TABLE_CSV",
                "file_path": str(tmp_path / "summary.csv"),
                "execution_run_id": "run-1",
                "table_caption": "主要变量汇总",
            },
        ],
        output_path=str(output),
        config=_formal_config(),
    )

    xml = _xml_text(output)
    assert "PAGEREF chapter_1" in xml
    assert "PAGEREF section_1_1" in xml
    assert "SEQ Figure" in xml
    assert "SEQ Table" in xml
    assert "REF fig_1" in xml
    assert "PAGEREF fig_1" in xml

    doc = Document(output)
    assert len(doc.sections) >= 3
    section_xml = "".join(section._sectPr.xml for section in doc.sections)
    assert 'w:fmt="lowerRoman"' in section_xml
    assert 'w:fmt="decimal"' in section_xml

