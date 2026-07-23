"""Word 文档渲染器。

从已确认大纲生成 .docx 文件。
使用 python-docx 库，模板驱动。

设计要点：
- 从同一份已确认大纲生成，不直接从模型临时上下文生成
- 章节按顺序渲染：封面、实验目的、实验背景、数据描述、分析方案、实验结果、结论与讨论
- 执行产物（CSV/PNG）按 source_ids 关联到对应章节
- 输出文件路径由调用方指定，渲染器只负责生成文件
- SPEC 0010：支持项目级 Word 模板（Jinja2 风格占位符）
  - 封面变量：{{project_name}} {{project_topic}} {{generated_date}}
  - 章节循环：{{#sections}}...{{/sections}}
  - 循环内变量：{{section_title}} {{section_content}} {{section_source_type}} {{section_source_ids}}
  - 模板解析失败时降级到默认渲染
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docx import Document
from docx.shared import Inches, Pt

from app.core.errors import AppError

logger = logging.getLogger(__name__)

# Jinja2 风格占位符正则
_VAR_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_SECTION_START = "{{#sections}}"
_SECTION_END = "{{/sections}}"


class WordRenderer:
    """Word 文档渲染器。

    从已确认大纲的 sections 列表生成 .docx 文件。
    支持项目级模板（SPEC 0010）。
    """

    def render(
        self,
        project_name: str,
        project_topic: str,
        outline_sections: list[dict],
        execution_artifacts: list[dict],
        output_path: str,
    ) -> str:
        """渲染 Word 文档（默认渲染，无模板）。

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

    def render_with_template(
        self,
        template_path: str,
        project_name: str,
        project_topic: str,
        outline_sections: list[dict],
        execution_artifacts: list[dict],
        output_path: str,
    ) -> str:
        """使用项目级模板渲染 Word 文档（SPEC 0010）。

        流程：
        1. 打开模板 .docx
        2. 识别 {{#sections}}...{{/sections}} 循环块
        3. 循环块外：替换封面变量
        4. 循环块内：按每个 section 重复段落，替换章节变量
        5. 执行产物按 source_ids 嵌入到对应章节
        6. 保存到输出路径

        降级策略：
        - 模板文件不存在 → WORD_TEMPLATE_FILE_MISSING
        - 模板无法打开 → WORD_TEMPLATE_PARSE_FAILED
        - 循环标记不匹配 → WORD_TEMPLATE_SECTION_BLOCK_INVALID
        """
        template = Path(template_path)
        if not template.exists():
            raise AppError(
                code="WORD_TEMPLATE_FILE_MISSING",
                message=f"模板文件不存在：{template_path}",
            )

        try:
            doc = Document(str(template))
        except Exception as exc:
            raise AppError(
                code="WORD_TEMPLATE_PARSE_FAILED",
                message=f"模板文件无法打开：{exc}",
            ) from exc

        try:
            # 准备封面变量
            cover_vars = {
                "project_name": project_name or "",
                "project_topic": project_topic or "",
                "generated_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "student_name": "",
                "course_name": "",
            }

            # 识别章节循环块（在段落级别）
            start_idx, end_idx = self._find_section_block(doc.paragraphs)

            if start_idx is not None and end_idx is None:
                # 有开始标记但无结束标记
                raise AppError(
                    code="WORD_TEMPLATE_SECTION_BLOCK_INVALID",
                    message="模板含 {{#sections}} 但缺少 {{/sections}}",
                )

            if start_idx is not None and end_idx is not None:
                # 替换循环块
                self._render_template_sections(
                    doc, start_idx, end_idx, outline_sections,
                    execution_artifacts, cover_vars,
                )
                # 循环块外（封面等）的变量也需要替换
                self._replace_cover_vars(doc, cover_vars)
            else:
                # 无循环块：只替换封面变量
                self._replace_cover_vars(doc, cover_vars)
                # 追加默认章节渲染（保持兼容）
                for section in outline_sections:
                    self._render_section(doc, section, execution_artifacts)

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
                message=f"模板渲染失败：{exc}",
            ) from exc

    # --- 模板辅助方法 ---

    def _find_section_block(self, paragraphs) -> tuple[int | None, int | None]:
        """在段落中查找 {{#sections}} 和 {{/sections}} 标记的位置。

        返回 (start_idx, end_idx)，未找到返回 (None, None)。
        """
        start_idx = None
        end_idx = None
        for i, p in enumerate(paragraphs):
            text = p.text
            if _SECTION_START in text and start_idx is None:
                start_idx = i
            if _SECTION_END in text and start_idx is not None:
                end_idx = i
                break
        return start_idx, end_idx

    def _replace_cover_vars(self, doc: Document, cover_vars: dict) -> None:
        """替换文档中所有段落的封面变量。"""
        for paragraph in doc.paragraphs:
            self._replace_vars_in_paragraph(paragraph, cover_vars)
        # 表格中的段落也替换
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        self._replace_vars_in_paragraph(paragraph, cover_vars)

    def _replace_vars_in_paragraph(self, paragraph, vars_dict: dict) -> None:
        """替换单个段落中的变量。"""
        if not paragraph.runs:
            # 无 runs 的段落直接替换文本
            if paragraph.text:
                new_text = self._replace_vars(paragraph.text, vars_dict)
                paragraph.text = new_text
            return
        # 有 runs 的段落：保留第一个 run 的格式，替换文本
        full_text = paragraph.text
        if not full_text:
            return
        new_text = self._replace_vars(full_text, vars_dict)
        if new_text != full_text:
            # 清空所有 runs，只在第一个 run 写入新文本
            first_run = paragraph.runs[0]
            first_run.text = new_text
            for run in paragraph.runs[1:]:
                run.text = ""

    def _replace_vars(self, text: str, vars_dict: dict) -> str:
        """替换文本中的 {{var}} 占位符。"""
        def replacer(match):
            var_name = match.group(1)
            return str(vars_dict.get(var_name, match.group(0)))
        return _VAR_PATTERN.sub(replacer, text)

    def _render_template_sections(
        self,
        doc: Document,
        start_idx: int,
        end_idx: int,
        outline_sections: list[dict],
        execution_artifacts: list[dict],
        cover_vars: dict,
    ) -> None:
        """渲染章节循环块。

        策略：使用文本重建方式。
        1. 收集循环块外的段落文本（保留封面等）
        2. 收集循环块内的段落文本作为模板
        3. 删除所有段落
        4. 按"循环块前 + 每个section的循环块内容 + 循环块后"重建段落
        5. 执行产物追加到末尾
        """
        paragraphs = list(doc.paragraphs)

        # 收集循环块前的段落文本（不含 start 标记）
        before_lines = [paragraphs[i].text for i in range(0, start_idx)]

        # 收集循环块内的段落文本（不含 start/end 标记）
        template_lines = [paragraphs[i].text for i in range(start_idx + 1, end_idx)]

        # 收集循环块后的段落文本（不含 end 标记）
        after_lines = [paragraphs[i].text for i in range(end_idx + 1, len(paragraphs))]

        # 删除所有现有段落
        body = doc.element.body
        for p in list(doc.paragraphs):
            p._element.getparent().remove(p._element)

        # 重建：循环块前的段落
        for line in before_lines:
            doc.add_paragraph(line)

        # 为每个 section 生成循环块内的段落
        for section in outline_sections:
            section_vars = {
                "section_title": section.get("title", ""),
                "section_content": section.get("content", ""),
                "section_source_type": section.get("source_type", ""),
                "section_source_ids": ", ".join(
                    str(sid) for sid in section.get("source_ids", []) or []
                ),
            }
            merged_vars = {**cover_vars, **section_vars}

            for line in template_lines:
                new_text = self._replace_vars(line, merged_vars)
                doc.add_paragraph(new_text)

        # 重建：循环块后的段落
        for line in after_lines:
            doc.add_paragraph(line)

        # 执行产物嵌入（按 source_ids 关联到章节）
        for section in outline_sections:
            source_type = section.get("source_type", "")
            source_ids = section.get("source_ids", []) or []
            if source_type == "EXECUTION":
                relevant = [
                    art for art in execution_artifacts
                    if not source_ids or art.get("execution_run_id") in source_ids
                ]
                if relevant:
                    doc.add_heading("执行产物", level=2)
                    for art in relevant:
                        self._render_single_artifact(doc, art)

    def _render_single_artifact(self, doc: Document, art: dict) -> None:
        """渲染单个执行产物。"""
        name = art.get("name", "")
        file_path = art.get("file_path", "")
        art_type = art.get("artifact_type", "")
        doc.add_paragraph(f"产物：{name}")

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
            self._render_single_artifact(doc, art)

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
