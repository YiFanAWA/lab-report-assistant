"""PPT 文档渲染器。

从同一份已确认大纲提炼生成 .pptx 文件。
使用 python-pptx 库，母版驱动。

设计要点：
- PPT 从大纲提炼关键内容，不包含全部细节
- 5-8 页：标题页、课题与问题、方法与数据、关键图表、主要发现、总结
- 关键图表引用执行产物中的 PNG
- 输出文件路径由调用方指定，渲染器只负责生成文件
"""

from datetime import datetime, timezone
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

from app.core.errors import AppError


class PptRenderer:
    """PPT 文档渲染器。

    从同一份已确认大纲提炼生成 .pptx 文件。
    """

    def render(
        self,
        project_name: str,
        project_topic: str,
        outline_sections: list[dict],
        execution_artifacts: list[dict],
        output_path: str,
    ) -> str:
        """渲染 PPT 文档。

        参数：
        - project_name: 项目名称（用于标题页）
        - project_topic: 项目课题（用于标题页）
        - outline_sections: 已确认大纲的 sections 列表（dict 形式）
        - execution_artifacts: 执行产物列表（含 file_path/name/artifact_type）
        - output_path: 输出文件绝对路径

        返回：生成的文件路径

        异常：渲染失败抛出 AppError(code="PPT_RENDER_FAILED")。
        """
        try:
            prs = Presentation()

            # 1. 标题页
            self._render_title_slide(prs, project_name, project_topic)

            # 2-5. 内容页（从大纲提炼）
            self._render_content_slides(prs, outline_sections, execution_artifacts)

            # 6. 总结页
            self._render_summary_slide(prs, outline_sections)

            # 确保输出目录存在
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            prs.save(str(output))
            return str(output)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                code="PPT_RENDER_FAILED",
                message=f"PPT 文档生成失败：{exc}",
            ) from exc

    def _render_title_slide(self, prs: Presentation, project_name: str,
                             project_topic: str) -> None:
        """渲染标题页。"""
        slide_layout = prs.slide_layouts[0]  # 标题幻灯片
        slide = prs.slides.add_slide(slide_layout)

        title = slide.shapes.title
        title.text = project_topic or "实验报告"

        if len(slide.placeholders) > 1:
            subtitle = slide.placeholders[1]
            now = datetime.now(timezone.utc)
            subtitle.text = f"项目：{project_name}\n生成日期：{now.strftime('%Y-%m-%d')}"

    def _render_content_slides(
        self,
        prs: Presentation,
        outline_sections: list[dict],
        artifacts: list[dict],
    ) -> None:
        """渲染内容页（课题与问题、方法与数据、关键图表、主要发现）。"""
        # 按 source_type 分组提炼
        by_type = {}
        for section in outline_sections:
            st = section.get("source_type", "")
            by_type.setdefault(st, []).append(section)

        # 2. 课题与问题（REQUIREMENT）
        req_sections = by_type.get("REQUIREMENT", [])
        if req_sections:
            self._add_content_slide(
                prs,
                "课题与问题",
                req_sections,
            )

        # 3. 方法与数据（EVIDENCE + DATASET + ANALYSIS）
        method_sections = (
            by_type.get("EVIDENCE", [])
            + by_type.get("DATASET", [])
            + by_type.get("ANALYSIS", [])
        )
        if method_sections:
            self._add_content_slide(
                prs,
                "方法与数据",
                method_sections,
            )

        # 4. 关键图表（引用执行产物中的 PNG）
        chart_artifacts = [
            a for a in artifacts
            if a.get("artifact_type") == "CHART_PNG"
        ]
        if chart_artifacts:
            self._add_chart_slide(prs, chart_artifacts)

        # 5. 主要发现（EXECUTION）
        exec_sections = by_type.get("EXECUTION", [])
        if exec_sections:
            self._add_content_slide(
                prs,
                "主要发现",
                exec_sections,
            )

    def _add_content_slide(
        self,
        prs: Presentation,
        title: str,
        sections: list[dict],
    ) -> None:
        """添加内容页。"""
        slide_layout = prs.slide_layouts[1]  # 标题和内容
        slide = prs.slides.add_slide(slide_layout)

        title_shape = slide.shapes.title
        title_shape.text = title

        if len(slide.placeholders) > 1:
            body = slide.placeholders[1]
            tf = body.text_frame
            tf.clear()

            for i, section in enumerate(sections[:5]):  # 最多 5 个要点
                content = section.get("content", "")
                # 取内容前 200 字符
                short_content = content[:200] + ("…" if len(content) > 200 else "")
                if i == 0:
                    p = tf.paragraphs[0]
                else:
                    p = tf.add_paragraph()
                p.text = f"• {section.get('title', '')}：{short_content}"
                p.font.size = Pt(14)

    def _add_chart_slide(self, prs: Presentation,
                          chart_artifacts: list[dict]) -> None:
        """添加关键图表页。"""
        slide_layout = prs.slide_layouts[5]  # 仅标题
        slide = prs.slides.add_slide(slide_layout)

        title_shape = slide.shapes.title
        title_shape.text = "关键图表"

        # 嵌入最多 2 张图表
        for i, art in enumerate(chart_artifacts[:2]):
            file_path = art.get("file_path", "")
            name = art.get("name", "")
            if file_path:
                path = Path(file_path)
                if path.exists():
                    try:
                        left = Inches(1 + i * 4)
                        top = Inches(1.5)
                        slide.shapes.add_picture(
                            str(path), left, top, width=Inches(3.5)
                        )
                    except Exception:
                        # 图片嵌入失败，添加文本占位
                        tb = slide.shapes.add_textbox(
                            Inches(1 + i * 4), Inches(1.5), Inches(3.5), Inches(2)
                        )
                        tb.text_frame.text = f"[图片无法嵌入：{name}]"
                else:
                    tb = slide.shapes.add_textbox(
                        Inches(1 + i * 4), Inches(1.5), Inches(3.5), Inches(2)
                    )
                    tb.text_frame.text = f"[图片文件不存在：{name}]"

    def _render_summary_slide(self, prs: Presentation,
                                outline_sections: list[dict]) -> None:
        """渲染总结页。"""
        slide_layout = prs.slide_layouts[1]  # 标题和内容
        slide = prs.slides.add_slide(slide_layout)

        title_shape = slide.shapes.title
        title_shape.text = "总结"

        if len(slide.placeholders) > 1:
            body = slide.placeholders[1]
            tf = body.text_frame
            tf.clear()

            # 提取 SUMMARY 类型章节作为总结
            summary_sections = [
                s for s in outline_sections
                if s.get("source_type") == "SUMMARY"
            ]
            if summary_sections:
                for i, section in enumerate(summary_sections):
                    content = section.get("content", "")
                    if i == 0:
                        p = tf.paragraphs[0]
                    else:
                        p = tf.add_paragraph()
                    p.text = content
                    p.font.size = Pt(16)
            else:
                p = tf.paragraphs[0]
                p.text = "本实验已按既定方案完成数据分析与可视化。"
                p.font.size = Pt(16)
