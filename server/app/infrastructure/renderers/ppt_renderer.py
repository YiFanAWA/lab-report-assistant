"""PPT 文档渲染器。

从同一份已确认大纲提炼生成 .pptx 文件。
使用 python-pptx 库，母版驱动。

设计要点：
- PPT 从大纲提炼关键内容，不包含全部细节
- 5-8 页：标题页、课题与问题、方法与数据、关键图表、主要发现、总结
- 关键图表引用执行产物中的 PNG
- 输出文件路径由调用方指定，渲染器只负责生成文件
- SPEC 0011：支持可选 config 配置（目标页数、主题色、图表开关）
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

from app.core.errors import AppError

logger = logging.getLogger(__name__)


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
        config: dict | None = None,
    ) -> str:
        """渲染 PPT 文档。

        参数：
        - project_name: 项目名称（用于标题页）
        - project_topic: 项目课题（用于标题页）
        - outline_sections: 已确认大纲的 sections 列表（dict 形式）
        - execution_artifacts: 执行产物列表（含 file_path/name/artifact_type）
        - output_path: 输出文件绝对路径
        - config: PPT 配置（SPEC 0011），可选。支持字段：
          - target_slide_count: 目标页数（5-20），None 表示默认
          - theme_color: 主题色 hex 值，None 表示默认黑色
          - include_charts: 是否包含图表页，默认 True

        返回：生成的文件路径

        异常：渲染失败抛出 AppError(code="PPT_RENDER_FAILED")。
        """
        # 解析 config（SPEC 0011）
        cfg = config or {}
        target_slide_count = cfg.get("target_slide_count")
        theme_color = cfg.get("theme_color")
        include_charts = cfg.get("include_charts", True)

        try:
            prs = Presentation()

            # 解析主题色（异常时降级到 None）
            theme_rgb = self._parse_theme_color(theme_color)

            # 1. 标题页
            self._render_title_slide(prs, project_name, project_topic, theme_rgb)

            # 2-5. 内容页（从大纲提炼）
            self._render_content_slides(
                prs, outline_sections, execution_artifacts,
                theme_rgb, include_charts, target_slide_count,
            )

            # 6. 总结页
            self._render_summary_slide(prs, outline_sections, theme_rgb)

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

    def _parse_theme_color(self, theme_color: str | None) -> RGBColor | None:
        """解析 hex 色值为 RGBColor（SPEC 0011）。

        theme_color 为 None 或空时返回 None（使用默认）。
        解析失败时记录 warning 并返回 None（降级到默认）。
        """
        if not theme_color:
            return None
        try:
            # python-pptx 的 RGBColor.from_string 接受不带 # 的 6 位 hex
            hex_str = theme_color.lstrip("#")
            return RGBColor.from_string(hex_str)
        except Exception as exc:
            logger.warning(
                "PPT 主题色解析失败，降级到默认颜色：%s (value=%s)",
                exc, theme_color,
            )
            return None

    def _apply_theme_color(self, shape, theme_rgb: RGBColor | None) -> None:
        """将主题色应用到标题文字（SPEC 0011）。

        theme_rgb 为 None 时不修改（保持默认）。
        """
        if theme_rgb is None:
            return
        try:
            if shape and shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    for run in para.runs:
                        run.font.color.rgb = theme_rgb
        except Exception:
            # 主题色应用失败不影响整体渲染
            pass

    def _render_title_slide(self, prs: Presentation, project_name: str,
                             project_topic: str,
                             theme_rgb: RGBColor | None = None) -> None:
        """渲染标题页（SPEC 0011：应用主题色）。"""
        slide_layout = prs.slide_layouts[0]  # 标题幻灯片
        slide = prs.slides.add_slide(slide_layout)

        title = slide.shapes.title
        title.text = project_topic or "实验报告"
        self._apply_theme_color(title, theme_rgb)

        if len(slide.placeholders) > 1:
            subtitle = slide.placeholders[1]
            now = datetime.now(timezone.utc)
            subtitle.text = f"项目：{project_name}\n生成日期：{now.strftime('%Y-%m-%d')}"

    def _render_content_slides(
        self,
        prs: Presentation,
        outline_sections: list[dict],
        artifacts: list[dict],
        theme_rgb: RGBColor | None = None,
        include_charts: bool = True,
        target_slide_count: int | None = None,
    ) -> None:
        """渲染内容页（课题与问题、方法与数据、关键图表、主要发现）。

        SPEC 0011：
        - include_charts=False 时跳过图表页
        - target_slide_count 指定时，内容页数不超过 target-2（减去标题页和总结页）
        """
        # 按 source_type 分组提炼
        by_type = {}
        for section in outline_sections:
            st = section.get("source_type", "")
            by_type.setdefault(st, []).append(section)

        # 收集内容页候选（顺序：课题与问题、方法与数据、主要发现）
        content_groups: list[tuple[str, list[dict]]] = []

        req_sections = by_type.get("REQUIREMENT", [])
        if req_sections:
            content_groups.append(("课题与问题", req_sections))

        method_sections = (
            by_type.get("EVIDENCE", [])
            + by_type.get("DATASET", [])
            + by_type.get("ANALYSIS", [])
        )
        if method_sections:
            content_groups.append(("方法与数据", method_sections))

        exec_sections = by_type.get("EXECUTION", [])
        if exec_sections:
            content_groups.append(("主要发现", exec_sections))

        # 页数控制（SPEC 0011）
        if target_slide_count is not None:
            available_slots = max(0, target_slide_count - 2)
            if available_slots == 0:
                content_groups = []
            elif len(content_groups) > available_slots:
                # 合并所有内容到 available_slots 个页面，每页最多 5 个要点
                all_sections: list[dict] = []
                all_titles: list[str] = []
                for title, sections in content_groups:
                    all_titles.append(title)
                    all_sections.extend(sections)
                merged_title = "、".join(all_titles)
                # 截断到 available_slots * 5 个要点
                max_items = available_slots * 5
                all_sections = all_sections[:max_items]
                content_groups = []
                for i in range(available_slots):
                    start = i * 5
                    end = start + 5
                    chunk = all_sections[start:end]
                    if chunk:
                        content_groups.append((merged_title, chunk))

        # 渲染内容页
        for title, sections in content_groups:
            self._add_content_slide(prs, title, sections, theme_rgb)

        # 关键图表（SPEC 0011：include_charts 开关）
        if include_charts:
            chart_artifacts = [
                a for a in artifacts
                if a.get("artifact_type") == "CHART_PNG"
            ]
            if chart_artifacts:
                self._add_chart_slide(prs, chart_artifacts, theme_rgb)

    def _add_content_slide(
        self,
        prs: Presentation,
        title: str,
        sections: list[dict],
        theme_rgb: RGBColor | None = None,
    ) -> None:
        """添加内容页（SPEC 0011：应用主题色）。"""
        slide_layout = prs.slide_layouts[1]  # 标题和内容
        slide = prs.slides.add_slide(slide_layout)

        title_shape = slide.shapes.title
        title_shape.text = title
        self._apply_theme_color(title_shape, theme_rgb)

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
                          chart_artifacts: list[dict],
                          theme_rgb: RGBColor | None = None) -> None:
        """添加关键图表页（SPEC 0011：应用主题色）。"""
        slide_layout = prs.slide_layouts[5]  # 仅标题
        slide = prs.slides.add_slide(slide_layout)

        title_shape = slide.shapes.title
        title_shape.text = "关键图表"
        self._apply_theme_color(title_shape, theme_rgb)

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
                                outline_sections: list[dict],
                                theme_rgb: RGBColor | None = None) -> None:
        """渲染总结页（SPEC 0011：应用主题色）。"""
        slide_layout = prs.slide_layouts[1]  # 标题和内容
        slide = prs.slides.add_slide(slide_layout)

        title_shape = slide.shapes.title
        title_shape.text = "总结"
        self._apply_theme_color(title_shape, theme_rgb)

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
