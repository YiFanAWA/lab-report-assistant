"""PPT 文档渲染器（SPEC 0024 布局与视觉层次改进）。

从同一份已确认大纲提炼生成 .pptx 文件。
使用 python-pptx 库，空白版式 + 精确定位驱动。

设计要点（SPEC 0024）：
- 16:9 宽屏画布（13.333×7.5 英寸）
- 空白版式（slide_layouts[6]）+ add_textbox/add_picture/add_shape 精确定位
- 双栏内容页：左栏 40% 文本要点 + 右栏 60% 图表
- 图表自适应：单图居中放大、双图并排、3-4 图 2×2 网格
- 五级字号体系：36/28/20/16/12 pt
- 主题色扩展应用：色块背景、分隔线、要点圆点标记
- SPEC 0011 配置兼容：target_slide_count/theme_color/include_charts 三字段不变
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn

from app.core.errors import AppError

logger = logging.getLogger(__name__)


# === SPEC 0024 布局常量 ===

# 16:9 画布尺寸（英寸）
SLIDE_WIDTH = 13.333
SLIDE_HEIGHT = 7.5

# 页面边距
MARGIN_LEFT = 0.5
MARGIN_TOP = 0.5
MARGIN_BOTTOM = 0.5

# 双栏布局参数
CONTENT_LEFT_WIDTH = 5.3      # 左栏文本宽度（40%）
CONTENT_RIGHT_LEFT = 6.1      # 右栏起始位置
CONTENT_RIGHT_WIDTH = 6.7     # 右栏图表宽度（60%）
CONTENT_TOP = 1.6             # 双栏内容起始纵向位置
CONTENT_HEIGHT = 5.2          # 双栏内容高度

# 字号体系（Pt）
FONT_SIZE_MAIN_TITLE = 36
FONT_SIZE_PAGE_TITLE = 28
FONT_SIZE_SUBTITLE = 20
FONT_SIZE_BODY = 16
FONT_SIZE_CAPTION = 12

# 字体
FONT_NAME_CN = "微软雅黑"
FONT_NAME_EN = "Calibri"

# 默认主题色（theme_color=None 时使用，深灰色）
DEFAULT_THEME_COLOR = "333333"

# 色块与分隔线
TITLE_BANNER_HEIGHT = 2.5     # 封面顶部色块高度
DIVIDER_HEIGHT = 0.04         # 分隔线粗细
FOOTER_TOP = 7.0              # 页脚纵向位置


class PptRenderer:
    """PPT 文档渲染器（SPEC 0024 布局与视觉层次改进）。

    从同一份已确认大纲提炼生成 .pptx 文件。
    采用 16:9 画布 + 空白版式精确定位 + 双栏内容页 + 图表自适应布局。
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
        - project_name: 项目名称（用于标题页和页脚）
        - project_topic: 项目课题（用于标题页）
        - outline_sections: 已确认大纲的 sections 列表（dict 形式）
        - execution_artifacts: 执行产物列表（含 file_path/name/artifact_type）
        - output_path: 输出文件绝对路径
        - config: PPT 配置（SPEC 0011），可选。支持字段：
          - target_slide_count: 目标页数（5-20），None 表示默认
          - theme_color: 主题色 hex 值，None 表示使用默认深灰色
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
            # SPEC 0024: 16:9 宽屏画布
            prs.slide_width = Inches(SLIDE_WIDTH)
            prs.slide_height = Inches(SLIDE_HEIGHT)

            # 解析主题色（None 时降级到默认深灰色）
            theme_rgb = self._resolve_theme_color(theme_color)

            # 收集图表产物
            chart_artifacts = (
                [a for a in execution_artifacts
                 if a.get("artifact_type") == "CHART_PNG"]
                if include_charts else []
            )

            # 构建内容页候选（按 source_type 分组，关联图表）
            content_groups = self._build_content_groups(
                outline_sections, chart_artifacts,
            )

            # 页数控制（SPEC 0011 逻辑，不改变）
            if target_slide_count is not None:
                content_groups = self._control_slide_count(
                    content_groups, target_slide_count,
                )

            # 计算剩余图表（未被内容页消耗的）
            # dict 不可哈希，用 id() 去重
            used_chart_ids = {
                id(g["chart"])
                for g in content_groups
                if g["chart"] is not None
            }
            remaining_charts = [
                a for a in chart_artifacts if id(a) not in used_chart_ids
            ]

            # 计算总页数
            total_pages = (
                1  # 封面页
                + len(content_groups)  # 内容页
                + (1 if remaining_charts else 0)  # 图表页
                + 1  # 总结页
            )

            # 1. 封面页
            self._render_title_slide(
                prs, project_name, project_topic, theme_rgb,
            )

            # 2-N. 内容页（双栏布局）
            for i, group in enumerate(content_groups):
                self._add_content_slide(
                    prs,
                    title=group["title"],
                    sections=group["sections"],
                    theme_rgb=theme_rgb,
                    chart_artifact=group["chart"],
                    page_num=i + 2,
                    total_pages=total_pages,
                    project_name=project_name,
                )

            # 图表页（剩余图表）
            page_offset = 2 + len(content_groups)
            if remaining_charts:
                self._add_chart_slide(
                    prs, remaining_charts, theme_rgb,
                    page_num=page_offset,
                    total_pages=total_pages,
                    project_name=project_name,
                )
                page_offset += 1

            # 总结页
            self._render_summary_slide(
                prs, outline_sections, theme_rgb,
                page_num=page_offset,
                total_pages=total_pages,
                project_name=project_name,
            )

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

    # === 主题色处理 ===

    def _resolve_theme_color(self, theme_color: str | None) -> RGBColor:
        """解析主题色，None 时降级到默认深灰色（SPEC 0024）。

        SPEC 0011 中 None 表示默认黑色；
        SPEC 0024 改为默认深灰色 #333333，视觉更柔和。
        解析失败时记录 warning 并返回默认深灰色。
        """
        if not theme_color:
            return RGBColor.from_string(DEFAULT_THEME_COLOR)
        try:
            hex_str = theme_color.lstrip("#")
            return RGBColor.from_string(hex_str)
        except Exception as exc:
            logger.warning(
                "PPT 主题色解析失败，降级到默认深灰色：%s (value=%s)",
                exc, theme_color,
            )
            return RGBColor.from_string(DEFAULT_THEME_COLOR)

    # === 内容页候选构建 ===

    def _build_content_groups(
        self,
        outline_sections: list[dict],
        chart_artifacts: list[dict],
    ) -> list[dict]:
        """每个章节单独构建一个内容页候选，关联图表。

        返回列表，每项为：
        {"title": str, "sections": list[dict], "chart": dict | None}

        布局规则（SPEC 0024 改进）：
        - 每个章节单独一页，使用章节自身 title 作为页面标题
        - 不再按 source_type 合并分组成 3 页，解除 6 页限制
        - SUMMARY 类型章节由总结页处理，不进入内容页
        - EXECUTION 类型章节优先关联 CHART_PNG 产物
        - 每个内容页取第一张关联图表放入右栏
        - 剩余图表进入独立图表页
        """
        content_groups: list[dict] = []
        chart_idx = 0

        for section in outline_sections:
            st = section.get("source_type", "")
            # SUMMARY 类型章节由总结页处理，不进入内容页
            if st == "SUMMARY":
                continue

            title = section.get("title", "") or "内容"
            group = {
                "title": title,
                "sections": [section],
                "chart": None,
            }

            # EXECUTION 类型章节优先关联图表
            if st == "EXECUTION" and chart_idx < len(chart_artifacts):
                group["chart"] = chart_artifacts[chart_idx]
                chart_idx += 1

            content_groups.append(group)

        # 剩余图表分配给未关联图表的内容页（从后往前）
        for group in reversed(content_groups):
            if chart_idx >= len(chart_artifacts):
                break
            if group["chart"] is None:
                group["chart"] = chart_artifacts[chart_idx]
                chart_idx += 1

        return content_groups

    def _control_slide_count(
        self,
        content_groups: list[dict],
        target_slide_count: int,
    ) -> list[dict]:
        """页数控制（SPEC 0011 逻辑，不改变）。

        target_slide_count 指定时，内容页数不超过 target-2（减去标题页和总结页）。
        """
        available_slots = max(0, target_slide_count - 2)
        if available_slots == 0:
            return []
        if len(content_groups) <= available_slots:
            return content_groups

        # 合并所有内容到 available_slots 个页面
        all_sections: list[dict] = []
        all_titles: list[str] = []
        all_charts: list[dict | None] = []
        for group in content_groups:
            all_titles.append(group["title"])
            all_sections.extend(group["sections"])
            if group["chart"] is not None:
                all_charts.append(group["chart"])

        merged_title = "、".join(all_titles)
        max_items = available_slots * 5
        all_sections = all_sections[:max_items]

        result: list[dict] = []
        chart_idx = 0
        for i in range(available_slots):
            start = i * 5
            end = start + 5
            chunk = all_sections[start:end]
            if chunk:
                chart = (
                    all_charts[chart_idx]
                    if chart_idx < len(all_charts) else None
                )
                if chart is not None:
                    chart_idx += 1
                result.append({
                    "title": merged_title,
                    "sections": chunk,
                    "chart": chart,
                })
        return result

    # === 封面页 ===

    def _render_title_slide(
        self,
        prs: Presentation,
        project_name: str,
        project_topic: str,
        theme_rgb: RGBColor,
    ) -> None:
        """渲染封面页：顶部主题色块 + 白色大标题 + 副标题 + 底部装饰线。"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # 空白版式

        # 1. 顶部主题色全幅色块
        self._add_color_block(
            slide, Inches(0), Inches(0),
            Inches(SLIDE_WIDTH), Inches(TITLE_BANNER_HEIGHT),
            theme_rgb,
        )

        # 2. 主标题（色块内白色文字，36pt Bold，居中）
        title_tb = slide.shapes.add_textbox(
            Inches(MARGIN_LEFT), Inches(0.7),
            Inches(SLIDE_WIDTH - 2 * MARGIN_LEFT), Inches(1.2),
        )
        tf = title_tb.text_frame
        tf.word_wrap = True
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        run = tf.paragraphs[0].add_run()
        run.text = project_topic or "实验报告"
        self._set_run_font(
            run, FONT_SIZE_MAIN_TITLE,
            RGBColor(0xFF, 0xFF, 0xFF), bold=True,
        )

        # 3. 副标题（色块下方，20pt 深灰）
        subtitle_tb = slide.shapes.add_textbox(
            Inches(MARGIN_LEFT), Inches(3.2),
            Inches(SLIDE_WIDTH - 2 * MARGIN_LEFT), Inches(1.5),
        )
        stf = subtitle_tb.text_frame
        stf.word_wrap = True
        now = datetime.now(timezone.utc)
        p1 = stf.paragraphs[0]
        p1.alignment = PP_ALIGN.CENTER
        r1 = p1.add_run()
        r1.text = f"项目：{project_name}"
        self._set_run_font(r1, FONT_SIZE_SUBTITLE, theme_rgb)

        p2 = stf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run()
        r2.text = f"生成日期：{now.strftime('%Y-%m-%d')}"
        self._set_run_font(r2, FONT_SIZE_SUBTITLE, theme_rgb)

        # 4. 底部装饰线
        self._add_divider(
            slide,
            Inches(MARGIN_LEFT), Inches(SLIDE_HEIGHT - 0.8),
            Inches(SLIDE_WIDTH - 2 * MARGIN_LEFT),
            theme_rgb,
        )

    # === 双栏内容页 ===

    def _add_content_slide(
        self,
        prs: Presentation,
        title: str,
        sections: list[dict],
        theme_rgb: RGBColor,
        chart_artifact: dict | None = None,
        page_num: int = 0,
        total_pages: int = 0,
        project_name: str = "",
    ) -> None:
        """添加双栏内容页：左栏文本要点 + 右栏图表/补充文本。"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # 空白版式

        # 1. 页面标题 + 分隔线
        self._add_page_title(slide, title, theme_rgb)

        # 2. 左栏文本（40%）
        self._add_content_left_column(slide, sections, theme_rgb)

        # 3. 右栏图表或补充文本（60%）
        if chart_artifact:
            self._add_content_right_chart(slide, chart_artifact)
        else:
            self._add_content_right_text(slide, sections, theme_rgb)

        # 4. 页脚
        self._add_footer(
            slide, project_name, page_num, total_pages, theme_rgb,
        )

    def _add_page_title(
        self,
        slide,
        title: str,
        theme_rgb: RGBColor,
    ) -> None:
        """添加页面标题（28pt 主题色 Bold）+ 主题色分隔线。"""
        # 标题文本框
        title_tb = slide.shapes.add_textbox(
            Inches(MARGIN_LEFT), Inches(MARGIN_TOP),
            Inches(SLIDE_WIDTH - 2 * MARGIN_LEFT), Inches(0.8),
        )
        tf = title_tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = title
        self._set_run_font(run, FONT_SIZE_PAGE_TITLE, theme_rgb, bold=True)

        # 标题下分隔线
        self._add_divider(
            slide,
            Inches(MARGIN_LEFT), Inches(1.3),
            Inches(SLIDE_WIDTH - 2 * MARGIN_LEFT),
            theme_rgb,
        )

    def _add_content_left_column(
        self,
        slide,
        sections: list[dict],
        theme_rgb: RGBColor,
    ) -> None:
        """添加左栏文本要点（主题色圆点 + 标题 + 说明，16pt）。"""
        tb = slide.shapes.add_textbox(
            Inches(MARGIN_LEFT), Inches(CONTENT_TOP),
            Inches(CONTENT_LEFT_WIDTH), Inches(CONTENT_HEIGHT),
        )
        tf = tb.text_frame
        tf.word_wrap = True

        for i, section in enumerate(sections[:5]):  # 最多 5 个要点
            content = section.get("content", "")
            short_content = content[:500] + ("…" if len(content) > 500 else "")
            section_title = section.get("title", "")

            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()

            # 圆点标记（主题色）
            bullet_run = p.add_run()
            bullet_run.text = "● "
            self._set_run_font(
                bullet_run, FONT_SIZE_BODY, theme_rgb, bold=True,
            )

            # 标题（Bold）
            title_run = p.add_run()
            title_run.text = section_title
            self._set_run_font(
                title_run, FONT_SIZE_BODY, theme_rgb, bold=True,
            )

            # 说明文本（换行）
            if short_content:
                desc_p = tf.add_paragraph()
                desc_run = desc_p.add_run()
                desc_run.text = f"  {short_content}"
                self._set_run_font(
                    desc_run, FONT_SIZE_BODY,
                    RGBColor(0x33, 0x33, 0x33),
                )

        # 超过 5 个要点加省略号
        if len(sections) > 5:
            more_p = tf.add_paragraph()
            more_run = more_p.add_run()
            more_run.text = "…"
            self._set_run_font(
                more_run, FONT_SIZE_BODY, theme_rgb,
            )

    def _add_content_right_chart(self, slide, artifact: dict) -> None:
        """添加右栏图表（自适应缩放到右栏可用区域）。"""
        file_path = artifact.get("file_path", "")
        name = artifact.get("name", "")

        # 可用区域：top=CONTENT_TOP 到 FOOTER_TOP
        max_width = CONTENT_RIGHT_WIDTH  # 6.7"
        max_height = FOOTER_TOP - CONTENT_TOP  # 5.4"

        if file_path and Path(file_path).exists():
            w, h = self._fit_image_size(file_path, max_width, max_height)
            try:
                slide.shapes.add_picture(
                    str(file_path),
                    Inches(CONTENT_RIGHT_LEFT), Inches(CONTENT_TOP),
                    width=Inches(w), height=Inches(h),
                )
            except Exception:
                self._add_placeholder_textbox(
                    slide, CONTENT_RIGHT_LEFT, CONTENT_TOP,
                    max_width, CONTENT_HEIGHT,
                    f"[图片无法嵌入：{name}]",
                )
        else:
            self._add_placeholder_textbox(
                slide, CONTENT_RIGHT_LEFT, CONTENT_TOP,
                max_width, CONTENT_HEIGHT,
                f"[图片文件不存在：{name}]",
            )

    def _add_content_right_text(
        self,
        slide,
        sections: list[dict],
        theme_rgb: RGBColor,
    ) -> None:
        """无图表时右栏展示补充文本。"""
        tb = slide.shapes.add_textbox(
            Inches(CONTENT_RIGHT_LEFT), Inches(CONTENT_TOP),
            Inches(CONTENT_RIGHT_WIDTH), Inches(CONTENT_HEIGHT),
        )
        tf = tb.text_frame
        tf.word_wrap = True

        # 取所有章节的完整内容作为补充文本
        for i, section in enumerate(sections[:5]):
            content = section.get("content", "")
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            run = p.add_run()
            run.text = content[:500] + ("…" if len(content) > 500 else "")
            self._set_run_font(
                run, FONT_SIZE_BODY, RGBColor(0x55, 0x55, 0x55),
            )

    # === 图表自适应布局 ===

    def _add_chart_slide(
        self,
        prs: Presentation,
        chart_artifacts: list[dict],
        theme_rgb: RGBColor,
        page_num: int = 0,
        total_pages: int = 0,
        project_name: str = "",
    ) -> None:
        """添加关键图表页（图表自适应布局）。"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # 空白版式
        self._add_page_title(slide, "关键图表", theme_rgb)

        count = min(len(chart_artifacts), 4)  # 最多 4 张
        if count == 1:
            self._place_chart_centered(slide, chart_artifacts[0])
        elif count == 2:
            self._place_chart_side_by_side(slide, chart_artifacts[:2])
        elif count == 3:
            self._place_chart_three(slide, chart_artifacts[:3])
        else:
            self._place_chart_grid(slide, chart_artifacts[:4])

        if len(chart_artifacts) > 4:
            self._add_truncation_note(slide, len(chart_artifacts))

        self._add_footer(
            slide, project_name, page_num, total_pages, theme_rgb,
        )

    def _fit_image_size(
        self, file_path: str, max_width: float, max_height: float,
    ) -> tuple[float, float]:
        """按宽高比缩放图片，确保不超过最大宽度和高度。

        返回 (width, height) 英寸。同时设置 width 和 height 不会拉伸图片，
        因为两者按原始宽高比等比计算。
        """
        try:
            from PIL import Image

            with Image.open(file_path) as img:
                orig_w, orig_h = img.size
        except Exception:
            # 无法读取尺寸时，用默认 5:3 比例
            return max_width, min(max_width * 0.6, max_height)

        ratio = orig_w / orig_h
        # 先按最大宽度缩放
        w = max_width
        h = w / ratio
        # 如果高度超出，改为按最大高度缩放
        if h > max_height:
            h = max_height
            w = h * ratio
        return round(w, 2), round(h, 2)

    def _place_chart_centered(self, slide, artifact: dict) -> None:
        """单图居中放大布局（自适应缩放到可用区域）。"""
        file_path = artifact.get("file_path", "")
        name = artifact.get("name", "")

        # 可用区域：top=1.8 到 FOOTER_TOP=7.0
        max_width = 8.0
        max_height = FOOTER_TOP - 1.8  # 5.2"

        if file_path and Path(file_path).exists():
            w, h = self._fit_image_size(file_path, max_width, max_height)
            left = (SLIDE_WIDTH - w) / 2  # 水平居中
            try:
                slide.shapes.add_picture(
                    str(file_path),
                    Inches(left), Inches(1.8),
                    width=Inches(w), height=Inches(h),
                )
            except Exception:
                self._add_placeholder_textbox(
                    slide, left, 1.8, max_width, 4,
                    f"[图片无法嵌入：{name}]",
                )
        else:
            left = (SLIDE_WIDTH - max_width) / 2
            self._add_placeholder_textbox(
                slide, left, 1.8, max_width, 4,
                f"[图片文件不存在：{name}]",
            )

    def _place_chart_side_by_side(
        self, slide, artifacts: list[dict],
    ) -> None:
        """双图左右并排布局（各自适应缩放到可用区域）。"""
        max_width = 5.8
        max_height = FOOTER_TOP - 1.8  # 5.2"
        positions = [(0.5, 1.8), (7.0, 1.8)]
        for i, art in enumerate(artifacts[:2]):
            file_path = art.get("file_path", "")
            name = art.get("name", "")
            left, top = positions[i]

            if file_path and Path(file_path).exists():
                w, h = self._fit_image_size(file_path, max_width, max_height)
                try:
                    slide.shapes.add_picture(
                        str(file_path),
                        Inches(left), Inches(top),
                        width=Inches(w), height=Inches(h),
                    )
                except Exception:
                    self._add_placeholder_textbox(
                        slide, left, top, max_width, 3.5,
                        f"[图片无法嵌入：{name}]",
                    )
            else:
                self._add_placeholder_textbox(
                    slide, left, top, max_width, 3.5,
                    f"[图片文件不存在：{name}]",
                )

    def _place_chart_three(self, slide, artifacts: list[dict]) -> None:
        """3 张图布局：上排 2 张并排 + 下排 1 张居中。

        布局约束（SPEC 0024）：
        - 上排 top=1.5, 下排 top=4.0, 行高 max 2.3"
        - 下排底部最大 6.3"，为页脚（top=7.0）预留空间
        """
        max_width_top = 5.8
        max_width_bottom = 8.0
        max_height = 2.3
        top_positions = [(0.5, 1.5), (7.0, 1.5)]

        # 上排 2 张
        for i, art in enumerate(artifacts[:2]):
            file_path = art.get("file_path", "")
            name = art.get("name", "")
            left, top = top_positions[i]
            if file_path and Path(file_path).exists():
                w, h = self._fit_image_size(file_path, max_width_top, max_height)
                try:
                    slide.shapes.add_picture(
                        str(file_path),
                        Inches(left), Inches(top),
                        width=Inches(w), height=Inches(h),
                    )
                except Exception:
                    self._add_placeholder_textbox(
                        slide, left, top, max_width_top, max_height,
                        f"[图片无法嵌入：{name}]",
                    )
            else:
                self._add_placeholder_textbox(
                    slide, left, top, max_width_top, max_height,
                    f"[图片文件不存在：{name}]",
                )

        # 下排 1 张居中
        if len(artifacts) >= 3:
            art = artifacts[2]
            file_path = art.get("file_path", "")
            name = art.get("name", "")
            top = 4.0
            if file_path and Path(file_path).exists():
                w, h = self._fit_image_size(file_path, max_width_bottom, max_height)
                left = (SLIDE_WIDTH - w) / 2  # 水平居中
                try:
                    slide.shapes.add_picture(
                        str(file_path),
                        Inches(left), Inches(top),
                        width=Inches(w), height=Inches(h),
                    )
                except Exception:
                    self._add_placeholder_textbox(
                        slide, left, top, max_width_bottom, max_height,
                        f"[图片无法嵌入：{name}]",
                    )
            else:
                left = (SLIDE_WIDTH - max_width_bottom) / 2
                self._add_placeholder_textbox(
                    slide, left, top, max_width_bottom, max_height,
                    f"[图片文件不存在：{name}]",
                )

    def _place_chart_grid(self, slide, artifacts: list[dict]) -> None:
        """多图 2×2 网格布局（各自适应缩放到网格单元）。

        布局约束（SPEC 0024）：
        - 上排 top=1.5, 下排 top=4.0, 行高 max 2.3"
        - 下排底部最大 6.3"，为截断注释（top=6.5）和页脚（top=7.0）预留空间
        - 避免图片与截断注释/页脚重叠
        """
        max_width = 3.8
        max_height = 2.3  # 每行可用高度（原 2.5 收缩以避免与截断注释重叠）
        positions = [
            (0.7, 1.5), (6.8, 1.5),
            (0.7, 4.0), (6.8, 4.0),
        ]
        for i, art in enumerate(artifacts[:4]):
            file_path = art.get("file_path", "")
            name = art.get("name", "")
            left, top = positions[i]

            if file_path and Path(file_path).exists():
                w, h = self._fit_image_size(file_path, max_width, max_height)
                try:
                    slide.shapes.add_picture(
                        str(file_path),
                        Inches(left), Inches(top),
                        width=Inches(w), height=Inches(h),
                    )
                except Exception:
                    self._add_placeholder_textbox(
                        slide, left, top, max_width, max_height,
                        f"[图片无法嵌入：{name}]",
                    )
            else:
                self._add_placeholder_textbox(
                    slide, left, top, max_width, max_height,
                    f"[图片文件不存在：{name}]",
                )

    def _add_truncation_note(self, slide, total_count: int) -> None:
        """添加截断注释（超过 4 张图表时）。"""
        tb = slide.shapes.add_textbox(
            Inches(MARGIN_LEFT), Inches(6.5),
            Inches(SLIDE_WIDTH - 2 * MARGIN_LEFT), Inches(0.4),
        )
        tf = tb.text_frame
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = f"共 {total_count} 张图表，已展示前 4 张"
        self._set_run_font(
            run, FONT_SIZE_CAPTION, RGBColor(0x88, 0x88, 0x88),
        )

    # === 总结页 ===

    def _render_summary_slide(
        self,
        prs: Presentation,
        outline_sections: list[dict],
        theme_rgb: RGBColor,
        page_num: int = 0,
        total_pages: int = 0,
        project_name: str = "",
    ) -> None:
        """渲染总结页：居中排版 + 主题色分隔线 + 要点提炼。"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # 空白版式

        # 页面标题 + 分隔线
        self._add_page_title(slide, "总结", theme_rgb)

        # 提取 SUMMARY 类型章节作为总结
        summary_sections = [
            s for s in outline_sections
            if s.get("source_type") == "SUMMARY"
        ]

        # 总结正文（居中，20pt 深灰）
        tb = slide.shapes.add_textbox(
            Inches(MARGIN_LEFT), Inches(2.5),
            Inches(SLIDE_WIDTH - 2 * MARGIN_LEFT), Inches(3.5),
        )
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE

        if summary_sections:
            for i, section in enumerate(summary_sections):
                content = section.get("content", "")
                if i == 0:
                    p = tf.paragraphs[0]
                else:
                    p = tf.add_paragraph()
                p.alignment = PP_ALIGN.CENTER
                run = p.add_run()
                run.text = content
                self._set_run_font(
                    run, FONT_SIZE_SUBTITLE, RGBColor(0x33, 0x33, 0x33),
                )
        else:
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            run = p.add_run()
            run.text = "本实验已按既定方案完成数据分析与可视化。"
            self._set_run_font(
                run, FONT_SIZE_SUBTITLE, RGBColor(0x33, 0x33, 0x33),
            )

        # 底部装饰线
        self._add_divider(
            slide,
            Inches(MARGIN_LEFT), Inches(SLIDE_HEIGHT - 1.0),
            Inches(SLIDE_WIDTH - 2 * MARGIN_LEFT),
            theme_rgb,
        )

        # 页脚
        self._add_footer(
            slide, project_name, page_num, total_pages, theme_rgb,
        )

    # === 辅助方法：样式 ===

    def _set_run_font(
        self,
        run,
        size: int,
        color_rgb: RGBColor | None = None,
        bold: bool = False,
        font_name: str = FONT_NAME_CN,
    ) -> None:
        """统一设置 run 的字体样式（含东亚字体）。"""
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.name = font_name
        if color_rgb is not None:
            run.font.color.rgb = color_rgb
        # 设置东亚字体（确保中文正确渲染）
        rPr = run._r.get_or_add_rPr()
        ea = rPr.find(qn("a:ea"))
        if ea is None:
            ea = rPr.makeelement(qn("a:ea"), {})
            rPr.append(ea)
        ea.set("typeface", font_name)

    def _add_color_block(
        self,
        slide,
        left,
        top,
        width,
        height,
        color_rgb: RGBColor,
    ) -> None:
        """添加纯色色块（无边框矩形）。"""
        shape = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, left, top, width, height,
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = color_rgb
        shape.line.fill.background()  # 无边框

    def _add_divider(
        self,
        slide,
        left,
        top,
        width,
        color_rgb: RGBColor,
        height: float = DIVIDER_HEIGHT,
    ) -> None:
        """添加分隔线（细矩形）。"""
        shape = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            left, top, width, Inches(height),
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = color_rgb
        shape.line.fill.background()

    def _add_footer(
        self,
        slide,
        project_name: str,
        page_num: int,
        total_pages: int,
        theme_rgb: RGBColor,
    ) -> None:
        """添加页脚（项目名 + 页码 + 分隔线）。"""
        # 页脚分隔线
        self._add_divider(
            slide,
            Inches(MARGIN_LEFT), Inches(FOOTER_TOP),
            Inches(SLIDE_WIDTH - 2 * MARGIN_LEFT),
            RGBColor(0xCC, 0xCC, 0xCC),  # 浅灰色
        )

        # 项目名（左）
        left_tb = slide.shapes.add_textbox(
            Inches(MARGIN_LEFT), Inches(FOOTER_TOP + 0.1),
            Inches(6), Inches(0.3),
        )
        lt = left_tb.text_frame
        lr = lt.paragraphs[0].add_run()
        lr.text = project_name
        self._set_run_font(
            lr, FONT_SIZE_CAPTION, RGBColor(0x88, 0x88, 0x88),
        )

        # 页码（右）
        right_tb = slide.shapes.add_textbox(
            Inches(SLIDE_WIDTH - 3), Inches(FOOTER_TOP + 0.1),
            Inches(2.5), Inches(0.3),
        )
        rt = right_tb.text_frame
        rt.paragraphs[0].alignment = PP_ALIGN.RIGHT
        rr = rt.paragraphs[0].add_run()
        rr.text = f"第 {page_num} / {total_pages} 页"
        self._set_run_font(
            rr, FONT_SIZE_CAPTION, RGBColor(0x88, 0x88, 0x88),
        )

    def _add_placeholder_textbox(
        self,
        slide,
        left: float,
        top: float,
        width: float,
        height: float,
        text: str,
    ) -> None:
        """添加占位文本框（图片嵌入失败时使用）。"""
        tb = slide.shapes.add_textbox(
            Inches(left), Inches(top), Inches(width), Inches(height),
        )
        tf = tb.text_frame
        tf.word_wrap = True
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        run = tf.paragraphs[0].add_run()
        run.text = text
        self._set_run_font(
            run, FONT_SIZE_BODY, RGBColor(0x88, 0x88, 0x88),
        )
