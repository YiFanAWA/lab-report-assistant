"""Word 文档渲染器。

从已确认大纲生成 .docx 文件。
使用 python-docx 库，模板驱动。

设计要点：
- 从同一份已确认大纲生成，不直接从模型临时上下文生成
- 章节按顺序渲染：封面、实验目的、实验背景、数据描述、分析方案、实验结果、结论与讨论
- 执行产物（CSV/PNG）按 source_ids 关联到对应章节
- 输出文件路径由调用方指定，渲染器只负责生成文件
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docx import Document
from docx.shared import Inches, Pt

from app.core.errors import AppError


class WordRenderer:
    """Word 文档渲染器。

    从已确认大纲的 sections 列表生成 .docx 文件。
    """

    def render(
        self,
        project_name: str,
        project_topic: str,
        outline_sections: list[dict],
        execution_artifacts: list[dict],
        output_path: str,
    ) -> str:
        """渲染 Word 文档。

        参数：
        - project_name: 项目名称（用于封面）
        - project_topic: 项目课题（用于封面）
        - outline_sections: 已确认大纲的 sections 列表（dict 形式）
        - execution_artifacts: 执行产物列表（含 file_path/name/artifact_type）
        - output_path: 输出文件绝对路径

        返回：生成的文件路径

        异常：渲染失败抛出 AppError(code="WORD_RENDER_FAILED")。
        """
        try:
            doc = Document()

            # 封面
            self._render_cover(doc, project_name, project_topic)

            # 章节内容
            for section in outline_sections:
                self._render_section(doc, section, execution_artifacts)

            # 附录：执行产物索引
            self._render_appendix(doc, execution_artifacts)

            # 确保输出目录存在
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(output))
            return str(output)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                code="WORD_RENDER_FAILED",
                message=f"Word 文档生成失败：{exc}",
            ) from exc

    def _render_cover(self, doc: Document, project_name: str,
                       project_topic: str) -> None:
        """渲染封面。"""
        # 标题
        heading = doc.add_heading("", level=0)
        run = heading.add_run(project_topic or "实验报告")
        run.font.size = Pt(28)
        run.bold = True

        # 副标题
        p = doc.add_paragraph()
        p.alignment = 1  # WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"项目：{project_name}")
        run.font.size = Pt(14)

        # 日期
        p = doc.add_paragraph()
        p.alignment = 1
        now = datetime.now(timezone.utc)
        run = p.add_run(f"生成日期：{now.strftime('%Y-%m-%d')}")
        run.font.size = Pt(12)

        doc.add_page_break()

    def _render_section(self, doc: Document, section: dict,
                         artifacts: list[dict]) -> None:
        """渲染单个章节。"""
        title = section.get("title", "")
        content = section.get("content", "")
        source_type = section.get("source_type", "")
        source_ids = section.get("source_ids", []) or []

        # 章节标题
        doc.add_heading(title, level=1)

        # 章节内容
        if content:
            for line in str(content).split("\n"):
                if line.strip():
                    doc.add_paragraph(line)

        # 执行产物引用（仅 EXECUTION 类型章节）
        if source_type == "EXECUTION":
            self._render_artifacts(doc, artifacts, source_ids)

    def _render_artifacts(self, doc: Document, artifacts: list[dict],
                          source_ids: list[str]) -> None:
        """渲染执行产物（图表和表格）。"""
        relevant = []
        for art in artifacts:
            # 按 source_ids 过滤，若 source_ids 为空则包含全部
            if not source_ids or art.get("execution_run_id") in source_ids:
                relevant.append(art)

        if not relevant:
            return

        doc.add_heading("执行产物", level=2)
        for art in relevant:
            name = art.get("name", "")
            file_path = art.get("file_path", "")
            art_type = art.get("artifact_type", "")
            doc.add_paragraph(f"产物：{name}")

            # 尝试嵌入 PNG 图片
            if art_type == "CHART_PNG" and file_path:
                path = Path(file_path)
                if path.exists():
                    try:
                        doc.add_picture(str(path), width=Inches(5.5))
                    except Exception:
                        doc.add_paragraph(f"[图片无法嵌入：{name}]")
                else:
                    doc.add_paragraph(f"[图片文件不存在：{name}]")
            elif art_type == "TABLE_CSV" and file_path:
                path = Path(file_path)
                if path.exists():
                    try:
                        self._render_csv_table(doc, path)
                    except Exception:
                        doc.add_paragraph(f"[表格无法嵌入：{name}]")
                else:
                    doc.add_paragraph(f"[表格文件不存在：{name}]")

    def _render_csv_table(self, doc: Document, csv_path: Path) -> None:
        """将 CSV 文件渲染为 Word 表格（前 10 行，前 6 列）。"""
        import csv

        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            return

        # 限制行数和列数
        max_rows = 10
        max_cols = 6
        rows = rows[:max_rows]
        rows = [row[:max_cols] for row in rows]

        table = doc.add_table(rows=len(rows), cols=len(rows[0]))
        table.style = "Table Grid"
        for i, row in enumerate(rows):
            for j, cell_text in enumerate(row):
                if j < len(table.rows[i].cells):
                    table.rows[i].cells[j].text = str(cell_text)

    def _render_appendix(self, doc: Document,
                          artifacts: list[dict]) -> None:
        """渲染附录：执行产物索引。"""
        if not artifacts:
            return

        doc.add_page_break()
        doc.add_heading("附录：执行产物索引", level=1)
        for art in artifacts:
            name = art.get("name", "")
            art_type = art.get("artifact_type", "")
            file_path = art.get("file_path", "")
            doc.add_paragraph(f"- {name}（{art_type}）：{file_path}")
