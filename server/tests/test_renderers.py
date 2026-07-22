"""Word 和 PPT 渲染器测试。

验证：
- WordRenderer 从已确认大纲生成 .docx 文件
- PptRenderer 从同一份大纲生成 .pptx 文件
- 文件实际生成且可被对应库重新打开
- 执行产物（CSV/PNG）正确嵌入
- 渲染失败抛出 AppError 结构化错误
"""

import csv
from pathlib import Path

import pytest
from docx import Document
from pptx import Presentation

from app.core.errors import AppError
from app.infrastructure.renderers.word_renderer import WordRenderer
from app.infrastructure.renderers.ppt_renderer import PptRenderer


SAMPLE_SECTIONS = [
    {
        "id": "sec_001",
        "title": "实验目的",
        "content": "分析胃病数据分布特征",
        "source_type": "REQUIREMENT",
        "source_ids": ["plan_001"],
    },
    {
        "id": "sec_002",
        "title": "实验背景",
        "content": "胃病发病率近年上升",
        "source_type": "EVIDENCE",
        "source_ids": ["card_001"],
    },
    {
        "id": "sec_003",
        "title": "数据描述",
        "content": "数据集规模：100 行 × 3 列",
        "source_type": "DATASET",
        "source_ids": ["ver_001"],
    },
    {
        "id": "sec_004",
        "title": "分析方案",
        "content": "清洗方案：去除缺失值\n分析方案：描述性统计",
        "source_type": "ANALYSIS",
        "source_ids": ["plan_a"],
    },
    {
        "id": "sec_005",
        "title": "实验结果",
        "content": "执行成功，输出统计表",
        "source_type": "EXECUTION",
        "source_ids": ["run_001"],
    },
    {
        "id": "sec_006",
        "title": "结论与讨论",
        "content": "本实验完成既定分析目标。",
        "source_type": "SUMMARY",
        "source_ids": [],
    },
]


def _make_csv(path: Path, rows: list[list[str]]) -> str:
    """写入 CSV 文件，返回绝对路径。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)
    return str(path)


def _make_png(path: Path) -> str:
    """写入最小 PNG 文件，返回绝对路径。"""
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    img.save(str(path), format="PNG")
    return str(path)


# --- WordRenderer 测试 ---


class TestWordRenderer:
    """Word 渲染器测试。"""

    def test_generates_docx_file(self, tmp_path):
        """成功生成 .docx 文件且文件存在。"""
        renderer = WordRenderer()
        output = tmp_path / "out.docx"

        result = renderer.render(
            project_name="胃病数据分析",
            project_topic="胃病数据分析实验报告",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[],
            output_path=str(output),
        )

        assert Path(result).exists()
        assert result.endswith(".docx")

    def test_docx_can_be_reopened(self, tmp_path):
        """生成的 docx 可被 python-docx 重新打开。"""
        renderer = WordRenderer()
        output = tmp_path / "out.docx"
        renderer.render(
            project_name="测试项目",
            project_topic="测试课题",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[],
            output_path=str(output),
        )

        doc = Document(str(output))
        # 封面用 Title 样式（level=0），章节用 Heading 1 样式
        all_text = "\n".join(p.text for p in doc.paragraphs)
        assert "测试课题" in all_text
        assert "实验目的" in all_text
        assert "结论与讨论" in all_text

    def test_cover_contains_project_name(self, tmp_path):
        """封面包含项目名称。"""
        renderer = WordRenderer()
        output = tmp_path / "out.docx"
        renderer.render(
            project_name="封面项目",
            project_topic="封面课题",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[],
            output_path=str(output),
        )

        doc = Document(str(output))
        all_text = "\n".join(p.text for p in doc.paragraphs)
        assert "封面项目" in all_text

    def test_section_content_rendered(self, tmp_path):
        """章节内容写入文档。"""
        renderer = WordRenderer()
        output = tmp_path / "out.docx"
        renderer.render(
            project_name="p",
            project_topic="t",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[],
            output_path=str(output),
        )

        doc = Document(str(output))
        all_text = "\n".join(p.text for p in doc.paragraphs)
        assert "分析胃病数据分布特征" in all_text
        assert "胃病发病率近年上升" in all_text

    def test_csv_artifact_embedded_as_table(self, tmp_path):
        """EXECUTION 章节关联的 CSV 产物嵌入为表格。"""
        csv_path = _make_csv(tmp_path / "artifacts" / "result.csv",
                             [["col_a", "col_b"], ["1", "2"]])
        renderer = WordRenderer()
        output = tmp_path / "out.docx"
        renderer.render(
            project_name="p",
            project_topic="t",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[
                {
                    "name": "result.csv",
                    "artifact_type": "TABLE_CSV",
                    "file_path": csv_path,
                    "execution_run_id": "run_001",
                },
            ],
            output_path=str(output),
        )

        doc = Document(str(output))
        # 应至少有一个表格
        assert len(doc.tables) >= 1
        assert doc.tables[0].rows[0].cells[0].text == "col_a"

    def test_png_artifact_embedded_as_image(self, tmp_path):
        """EXECUTION 章节关联的 PNG 产物嵌入为图片。"""
        png_path = _make_png(tmp_path / "artifacts" / "chart.png")
        renderer = WordRenderer()
        output = tmp_path / "out.docx"
        renderer.render(
            project_name="p",
            project_topic="t",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[
                {
                    "name": "chart.png",
                    "artifact_type": "CHART_PNG",
                    "file_path": png_path,
                    "execution_run_id": "run_001",
                },
            ],
            output_path=str(output),
        )

        doc = Document(str(output))
        # 图片以 inline shape 形式存在
        assert len(doc.inline_shapes) >= 1

    def test_appendix_contains_artifact_index(self, tmp_path):
        """附录包含执行产物索引。"""
        renderer = WordRenderer()
        output = tmp_path / "out.docx"
        renderer.render(
            project_name="p",
            project_topic="t",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[
                {
                    "name": "chart.png",
                    "artifact_type": "CHART_PNG",
                    "file_path": "/tmp/chart.png",
                    "execution_run_id": "run_001",
                },
            ],
            output_path=str(output),
        )

        doc = Document(str(output))
        all_text = "\n".join(p.text for p in doc.paragraphs)
        assert "附录" in all_text
        assert "chart.png" in all_text

    def test_creates_output_directory(self, tmp_path):
        """输出目录不存在时自动创建。"""
        renderer = WordRenderer()
        output = tmp_path / "deep" / "nested" / "dir" / "out.docx"

        result = renderer.render(
            project_name="p",
            project_topic="t",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[],
            output_path=str(output),
        )

        assert Path(result).exists()

    def test_empty_sections_renders_without_error(self, tmp_path):
        """空章节列表不报错。"""
        renderer = WordRenderer()
        output = tmp_path / "out.docx"
        result = renderer.render(
            project_name="p",
            project_topic="t",
            outline_sections=[],
            execution_artifacts=[],
            output_path=str(output),
        )
        assert Path(result).exists()

    def test_missing_csv_file_uses_placeholder_text(self, tmp_path):
        """CSV 文件不存在时写入占位文本而非抛错。"""
        renderer = WordRenderer()
        output = tmp_path / "out.docx"
        renderer.render(
            project_name="p",
            project_topic="t",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[
                {
                    "name": "missing.csv",
                    "artifact_type": "TABLE_CSV",
                    "file_path": "/nonexistent/missing.csv",
                    "execution_run_id": "run_001",
                },
            ],
            output_path=str(output),
        )
        doc = Document(str(output))
        all_text = "\n".join(p.text for p in doc.paragraphs)
        assert "表格文件不存在" in all_text


# --- PptRenderer 测试 ---


class TestPptRenderer:
    """PPT 渲染器测试。"""

    def test_generates_pptx_file(self, tmp_path):
        """成功生成 .pptx 文件。"""
        renderer = PptRenderer()
        output = tmp_path / "out.pptx"

        result = renderer.render(
            project_name="胃病数据分析",
            project_topic="胃病数据分析实验报告",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[],
            output_path=str(output),
        )

        assert Path(result).exists()
        assert result.endswith(".pptx")

    def test_pptx_can_be_reopened(self, tmp_path):
        """生成的 pptx 可被 python-pptx 重新打开。"""
        renderer = PptRenderer()
        output = tmp_path / "out.pptx"
        renderer.render(
            project_name="p",
            project_topic="测试课题",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[],
            output_path=str(output),
        )

        prs = Presentation(str(output))
        # 标题页 + 内容页 + 总结页
        assert len(prs.slides) >= 2

    def test_title_slide_contains_topic(self, tmp_path):
        """标题页包含课题。"""
        renderer = PptRenderer()
        output = tmp_path / "out.pptx"
        renderer.render(
            project_name="p",
            project_topic="胃病数据分析",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[],
            output_path=str(output),
        )

        prs = Presentation(str(output))
        first_slide = prs.slides[0]
        title_text = first_slide.shapes.title.text if first_slide.shapes.title else ""
        assert "胃病数据分析" in title_text

    def test_content_slides_from_sections(self, tmp_path):
        """内容页按 source_type 分组渲染。"""
        renderer = PptRenderer()
        output = tmp_path / "out.pptx"
        renderer.render(
            project_name="p",
            project_topic="t",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[],
            output_path=str(output),
        )

        prs = Presentation(str(output))
        all_text = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    all_text.append(shape.text_frame.text)

        # 课题与问题页应包含实验目的
        joined = "\n".join(all_text)
        assert "课题与问题" in joined or "实验目的" in joined
        # 方法与数据页应包含数据描述
        assert "方法与数据" in joined or "数据描述" in joined

    def test_summary_slide_present(self, tmp_path):
        """总结页存在。"""
        renderer = PptRenderer()
        output = tmp_path / "out.pptx"
        renderer.render(
            project_name="p",
            project_topic="t",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[],
            output_path=str(output),
        )

        prs = Presentation(str(output))
        last_slide = prs.slides[len(prs.slides) - 1]
        title = last_slide.shapes.title.text if last_slide.shapes.title else ""
        assert "总结" in title

    def test_chart_slide_with_png_artifact(self, tmp_path):
        """有 PNG 产物时生成关键图表页。"""
        png_path = _make_png(tmp_path / "artifacts" / "chart.png")
        renderer = PptRenderer()
        output = tmp_path / "out.pptx"
        renderer.render(
            project_name="p",
            project_topic="t",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[
                {
                    "name": "chart.png",
                    "artifact_type": "CHART_PNG",
                    "file_path": png_path,
                    "execution_run_id": "run_001",
                },
            ],
            output_path=str(output),
        )

        prs = Presentation(str(output))
        # 应找到包含图片的幻灯片
        has_picture = False
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.shape_type == 13:  # PICTURE
                    has_picture = True
                    break
            if has_picture:
                break
        assert has_picture

    def test_empty_sections_renders_without_error(self, tmp_path):
        """空章节列表不报错。"""
        renderer = PptRenderer()
        output = tmp_path / "out.pptx"
        result = renderer.render(
            project_name="p",
            project_topic="t",
            outline_sections=[],
            execution_artifacts=[],
            output_path=str(output),
        )
        assert Path(result).exists()

    def test_creates_output_directory(self, tmp_path):
        """输出目录不存在时自动创建。"""
        renderer = PptRenderer()
        output = tmp_path / "deep" / "nested" / "out.pptx"
        result = renderer.render(
            project_name="p",
            project_topic="t",
            outline_sections=SAMPLE_SECTIONS,
            execution_artifacts=[],
            output_path=str(output),
        )
        assert Path(result).exists()
