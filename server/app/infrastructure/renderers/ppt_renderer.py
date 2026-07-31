"""PPT 文档渲染器（SPEC 0026 视觉效果增强）。

从同一份已确认大纲提炼生成 .pptx 文件。
使用 python-pptx 库，空白版式 + 精确定位驱动。

设计要点（SPEC 0024）：
- 16:9 宽屏画布（13.333×7.5 英寸）
- 空白版式（slide_layouts[6]）+ add_textbox/add_picture/add_shape 精确定位
- 双栏内容页：左栏 40% 文本要点 + 右栏 60% 图表
- 图表自适应：单图居中放大、双图并排、3-4 图 2×2 网格
- 五级字号体系：36/28/20/16/12 pt

设计要点（SPEC 0025）：
- 三角色彩系统：从单一 theme_color 用 colorsys 派生主色/辅助色/强调色
- 深浅对比三明治结构：深色标题栏 → 浅色内容区 → 深色页脚栏
- 辅助色浅色背景衬托左栏，强调色用于圆点标记和章节标题
- 主色亮度 > 0.60 时自动切换深色标题文字（对比度保障，阈值覆盖紫色 #7c3aed）

设计要点（SPEC 0026）：
- 渐变填充：封面顶部色块、标题栏、页脚栏改为线性渐变（主色 → 主色暗化）
- 圆角矩形：左栏背景衬托改为圆角矩形（半径 0.05），柔化硬边缘
- 外阴影效果：右栏图表添加柔和外阴影（oxml 操作 a:effectLst）
- 形状细边框：右栏图表添加辅助色 1pt 边框
- SPEC 0011 配置兼容：target_slide_count/theme_color/include_charts 三字段不变
"""

import colorsys
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


# === SPEC 0025 三明治结构常量 ===

# 标题栏（深色背景栏）
TITLE_BAR_HEIGHT = 1.0           # 内容页/图表页/总结页标题栏高度

# 页脚栏（深色背景栏）
FOOTER_BAR_HEIGHT = 0.5          # 页脚栏高度
FOOTER_BAR_TOP = SLIDE_HEIGHT - FOOTER_BAR_HEIGHT  # 7.0

# 内容区（三明治夹心：标题栏和页脚栏之间）
CONTENT_TOP = TITLE_BAR_HEIGHT + 0.2    # 1.2（内容起始纵向位置）
CONTENT_BOTTOM = FOOTER_BAR_TOP - 0.2   # 6.8
CONTENT_HEIGHT = CONTENT_BOTTOM - CONTENT_TOP  # 5.6

# 图表可用区域上边界（图表页标题栏下方）
CHART_AREA_TOP = TITLE_BAR_HEIGHT + 0.3  # 1.3

# 文字颜色
TEXT_COLOR_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
TEXT_COLOR_DARK = RGBColor(0x33, 0x33, 0x33)
TEXT_COLOR_MUTED = RGBColor(0x55, 0x55, 0x55)


class PptRenderer:
    """PPT 文档渲染器（SPEC 0026 视觉效果增强）。

    从同一份已确认大纲提炼生成 .pptx 文件。
    采用 16:9 画布 + 空白版式精确定位 + 双栏内容页 + 图表自适应布局
    + 三角色彩系统（主色/辅助色/强调色）+ 深浅对比三明治结构
    + 渐变填充 + 圆角矩形 + 外阴影 + 细边框（SPEC 0026）。
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

            # SPEC 0025: 从主题色派生三角色彩（主色/辅助色/强调色/标题文字色）
            theme_rgb = self._resolve_theme_color(theme_color)
            primary, auxiliary, accent, title_text_color = (
                self._derive_color_palette(theme_rgb)
            )

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
                prs, project_name, project_topic,
                primary, title_text_color,
            )

            # 2-N. 内容页（双栏布局）
            for i, group in enumerate(content_groups):
                self._add_content_slide(
                    prs,
                    title=group["title"],
                    sections=group["sections"],
                    primary=primary,
                    auxiliary=auxiliary,
                    accent=accent,
                    title_text_color=title_text_color,
                    chart_artifact=group["chart"],
                    page_num=i + 2,
                    total_pages=total_pages,
                    project_name=project_name,
                )

            # 图表页（剩余图表）
            page_offset = 2 + len(content_groups)
            if remaining_charts:
                self._add_chart_slide(
                    prs, remaining_charts,
                    primary, title_text_color,
                    page_num=page_offset,
                    total_pages=total_pages,
                    project_name=project_name,
                )
                page_offset += 1

            # 总结页
            self._render_summary_slide(
                prs, outline_sections,
                primary, title_text_color,
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

    # === SPEC 0025 三角色彩派生 ===

    def _derive_color_palette(
        self, theme_rgb: RGBColor,
    ) -> tuple[RGBColor, RGBColor, RGBColor, RGBColor]:
        """从主题色派生三角色彩（SPEC 0025）。

        使用 Python 标准库 colorsys 进行 RGB ↔ HLS 色彩空间转换。

        返回 (primary, auxiliary, accent, title_text_color)：
        - primary: 主色（= theme_rgb），用于标题栏/页脚栏背景、封面色块
        - auxiliary: 辅助色（高亮度低饱和度浅色），用于左栏背景衬托
        - accent: 强调色（互补色相），用于圆点标记/章节标题
        - title_text_color: 标题栏文字色（白或深灰，取决于主色亮度）
        """
        # 提取 RGB 分量（0-1 范围）
        hex_str = str(theme_rgb)
        r = int(hex_str[0:2], 16) / 255
        g = int(hex_str[2:4], 16) / 255
        b = int(hex_str[4:6], 16) / 255

        # 转 HLS
        h, l, s = colorsys.rgb_to_hls(r, g, b)

        # 主色 = 原色
        primary = theme_rgb

        # 辅助色 = 高亮度（0.92）低饱和度（≤0.30），浅色背景衬托
        aux_l = 0.92
        aux_s = min(s, 0.30)
        aux_r, aux_g, aux_b = colorsys.hls_to_rgb(h, aux_l, aux_s)
        auxiliary = RGBColor(
            int(aux_r * 255), int(aux_g * 255), int(aux_b * 255),
        )

        # 强调色 = 互补色相（H+0.5），中亮度（0.45）高饱和度（0.50-0.70）
        if s < 0.20:
            # 低饱和度特殊处理：互补色区分度不足，固定使用蓝色作为强调色
            # 阈值 0.20 覆盖 #475569（饱和度约 0.193）等灰蓝色
            accent = RGBColor(0x25, 0x63, 0xEB)
        else:
            acc_h = (h + 0.5) % 1.0
            acc_l = 0.45
            acc_s = min(max(s, 0.50), 0.70)
            acc_r, acc_g, acc_b = colorsys.hls_to_rgb(acc_h, acc_l, acc_s)
            accent = RGBColor(
                int(acc_r * 255), int(acc_g * 255), int(acc_b * 255),
            )

        # 标题栏文字色：主色亮度 > 0.60 时用深灰，否则用白色（对比度保障）
        # 阈值 0.60 覆盖紫色 #7c3aed（L≈0.578），使 5 种预设深色统一用白字
        if l > 0.60:
            title_text_color = TEXT_COLOR_DARK
        else:
            title_text_color = TEXT_COLOR_WHITE

        return primary, auxiliary, accent, title_text_color

    # === SPEC 0026 视觉效果增强 ===

    def _darken_color(
        self, rgb: RGBColor, factor: float = 0.20,
    ) -> RGBColor:
        """降低颜色亮度（SPEC 0026 渐变派生）。

        在 HLS 空间将 L 降低 factor，下限 0.10 保护极暗颜色。
        用于渐变填充的结束色派生。
        """
        hex_str = str(rgb)
        r = int(hex_str[0:2], 16) / 255
        g = int(hex_str[2:4], 16) / 255
        b = int(hex_str[4:6], 16) / 255
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        # 亮度降低 factor，下限 0.10 保护
        l = max(l - factor, 0.10)
        dr, dg, db = colorsys.hls_to_rgb(h, l, s)
        return RGBColor(int(dr * 255), int(dg * 255), int(db * 255))

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
        primary: RGBColor,
        title_text_color: RGBColor,
    ) -> None:
        """渲染封面页：顶部渐变色块 + 白色大标题 + 副标题 + 底部主色窄条（三明治）。"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # 空白版式

        # 1. 顶部渐变色块（SPEC 0026：主色 → 主色暗化 20%）
        primary_dark_20 = self._darken_color(primary, 0.20)
        self._add_gradient_block(
            slide, Inches(0), Inches(0),
            Inches(SLIDE_WIDTH), Inches(TITLE_BANNER_HEIGHT),
            primary, primary_dark_20, angle_deg=90,
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
            run, FONT_SIZE_MAIN_TITLE, title_text_color, bold=True,
        )

        # 3. 副标题（色块下方，20pt 主色）
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
        self._set_run_font(r1, FONT_SIZE_SUBTITLE, primary)

        p2 = stf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run()
        r2.text = f"生成日期：{now.strftime('%Y-%m-%d')}"
        self._set_run_font(r2, FONT_SIZE_SUBTITLE, primary)

        # 4. 底部主色窄条（SPEC 0025 新增：三明治下层面包）
        self._add_color_block(
            slide,
            Inches(0), Inches(FOOTER_BAR_TOP),
            Inches(SLIDE_WIDTH), Inches(FOOTER_BAR_HEIGHT),
            primary,
        )

    # === 双栏内容页 ===

    def _add_content_slide(
        self,
        prs: Presentation,
        title: str,
        sections: list[dict],
        primary: RGBColor,
        auxiliary: RGBColor,
        accent: RGBColor,
        title_text_color: RGBColor,
        chart_artifact: dict | None = None,
        page_num: int = 0,
        total_pages: int = 0,
        project_name: str = "",
    ) -> None:
        """添加双栏内容页：深色标题栏 + 左栏文本（辅助色背景）+ 右栏图表 + 深色页脚栏。"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # 空白版式

        # 1. 深色标题栏（SPEC 0025 三明治上层面包）
        self._add_page_title(slide, title, primary, title_text_color)

        # 2. 左栏文本（40%，辅助色背景 + 强调色圆点）
        self._add_content_left_column(slide, sections, accent, auxiliary)

        # 3. 右栏图表或补充文本（60%）
        if chart_artifact:
            self._add_content_right_chart(slide, chart_artifact, auxiliary)
        else:
            self._add_content_right_text(slide, sections)

        # 4. 深色页脚栏（SPEC 0025 三明治下层面包）
        self._add_footer(
            slide, project_name, page_num, total_pages,
            primary, title_text_color,
        )

    def _add_page_title(
        self,
        slide,
        title: str,
        primary: RGBColor,
        title_text_color: RGBColor,
    ) -> None:
        """添加深色标题栏（渐变背景 + 白色/深灰标题文字，SPEC 0025/0026）。"""
        # 1. 渐变背景栏（SPEC 0026：主色 → 主色暗化 15%，全幅，高 TITLE_BAR_HEIGHT）
        primary_dark_15 = self._darken_color(primary, 0.15)
        self._add_gradient_block(
            slide,
            Inches(0), Inches(0),
            Inches(SLIDE_WIDTH), Inches(TITLE_BAR_HEIGHT),
            primary, primary_dark_15, angle_deg=90,
        )

        # 2. 标题文字（title_text_color，28pt Bold，垂直居中）
        title_tb = slide.shapes.add_textbox(
            Inches(MARGIN_LEFT), Inches(0.1),
            Inches(SLIDE_WIDTH - 2 * MARGIN_LEFT), Inches(TITLE_BAR_HEIGHT - 0.2),
        )
        tf = title_tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = title
        self._set_run_font(
            run, FONT_SIZE_PAGE_TITLE, title_text_color, bold=True,
        )

    def _add_content_left_column(
        self,
        slide,
        sections: list[dict],
        accent: RGBColor,
        auxiliary: RGBColor,
    ) -> None:
        """添加左栏文本要点（辅助色圆角背景 + 强调色圆点/标题 + 深灰说明，16pt）。"""
        # 1. 辅助色浅色圆角背景（SPEC 0026：圆角矩形替代直角矩形）
        self._add_rounded_color_block(
            slide,
            Inches(MARGIN_LEFT), Inches(CONTENT_TOP),
            Inches(CONTENT_LEFT_WIDTH), Inches(CONTENT_HEIGHT),
            auxiliary, corner_radius=0.05,
        )

        # 2. 文本要点（叠在背景上，留 0.1" 内边距）
        tb = slide.shapes.add_textbox(
            Inches(MARGIN_LEFT + 0.15), Inches(CONTENT_TOP + 0.1),
            Inches(CONTENT_LEFT_WIDTH - 0.3), Inches(CONTENT_HEIGHT - 0.2),
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

            # 圆点标记（强调色，SPEC 0025）
            bullet_run = p.add_run()
            bullet_run.text = "● "
            self._set_run_font(
                bullet_run, FONT_SIZE_BODY, accent, bold=True,
            )

            # 章节标题（强调色 Bold，SPEC 0025）
            title_run = p.add_run()
            title_run.text = section_title
            self._set_run_font(
                title_run, FONT_SIZE_BODY, accent, bold=True,
            )

            # 说明文本（深灰，换行）
            if short_content:
                desc_p = tf.add_paragraph()
                desc_run = desc_p.add_run()
                desc_run.text = f"  {short_content}"
                self._set_run_font(
                    desc_run, FONT_SIZE_BODY, TEXT_COLOR_DARK,
                )

        # 超过 5 个要点加省略号
        if len(sections) > 5:
            more_p = tf.add_paragraph()
            more_run = more_p.add_run()
            more_run.text = "…"
            self._set_run_font(
                more_run, FONT_SIZE_BODY, accent,
            )

    def _add_content_right_chart(
        self, slide, artifact: dict, auxiliary: RGBColor,
    ) -> None:
        """添加右栏图表（自适应缩放 + 边框 + 阴影，SPEC 0026）。"""
        file_path = artifact.get("file_path", "")
        name = artifact.get("name", "")

        # 可用区域：top=CONTENT_TOP 到 FOOTER_BAR_TOP
        max_width = CONTENT_RIGHT_WIDTH  # 6.7"
        max_height = FOOTER_BAR_TOP - CONTENT_TOP  # 5.4"

        if file_path and Path(file_path).exists():
            w, h = self._fit_image_size(file_path, max_width, max_height)
            try:
                pic = slide.shapes.add_picture(
                    str(file_path),
                    Inches(CONTENT_RIGHT_LEFT), Inches(CONTENT_TOP),
                    width=Inches(w), height=Inches(h),
                )
                # SPEC 0026：细边框（辅助色 1pt）
                pic.line.color.rgb = auxiliary
                pic.line.width = Pt(1)
                # SPEC 0026：外阴影效果
                self._add_picture_shadow(pic)
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
        primary: RGBColor,
        title_text_color: RGBColor,
        page_num: int = 0,
        total_pages: int = 0,
        project_name: str = "",
    ) -> None:
        """添加关键图表页（图表自适应布局 + SPEC 0025 三明治结构）。"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # 空白版式
        self._add_page_title(slide, "关键图表", primary, title_text_color)

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
            slide, project_name, page_num, total_pages,
            primary, title_text_color,
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

        # 可用区域：top=1.8 到 FOOTER_BAR_TOP=7.0
        max_width = 8.0
        max_height = FOOTER_BAR_TOP - 1.8  # 5.2"

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
        max_height = FOOTER_BAR_TOP - 1.8  # 5.2"
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
        primary: RGBColor,
        title_text_color: RGBColor,
        page_num: int = 0,
        total_pages: int = 0,
        project_name: str = "",
    ) -> None:
        """渲染总结页：深色标题栏 + 居中正文 + 深色页脚栏（SPEC 0025 三明治结构）。"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # 空白版式

        # 1. 深色标题栏（SPEC 0025 三明治上层面包）
        self._add_page_title(slide, "总结", primary, title_text_color)

        # 2. 提取 SUMMARY 类型章节作为总结
        summary_sections = [
            s for s in outline_sections
            if s.get("source_type") == "SUMMARY"
        ]

        # 3. 总结正文（居中，20pt 深灰）
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
                    run, FONT_SIZE_SUBTITLE, TEXT_COLOR_DARK,
                )
        else:
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            run = p.add_run()
            run.text = "本实验已按既定方案完成数据分析与可视化。"
            self._set_run_font(
                run, FONT_SIZE_SUBTITLE, TEXT_COLOR_DARK,
            )

        # 4. 深色页脚栏（SPEC 0025 三明治下层面包，取代旧装饰线）
        self._add_footer(
            slide, project_name, page_num, total_pages,
            primary, title_text_color,
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

    def _add_gradient_block(
        self,
        slide,
        left,
        top,
        width,
        height,
        color_start: RGBColor,
        color_end: RGBColor,
        angle_deg: float = 90,
    ) -> None:
        """添加渐变色块（线性渐变，SPEC 0026）。

        使用 python-pptx 原生 fill.gradient() API。
        参数：
        - color_start: 起始色（position=0.0）
        - color_end: 结束色（position=1.0）
        - angle_deg: 渐变角度（90=上→下）
        """
        shape = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, left, top, width, height,
        )
        fill = shape.fill
        fill.gradient()
        fill.gradient_angle = angle_deg
        # 设置两端颜色（默认 gradient() 生成两停止点）
        stops = fill.gradient_stops
        stops[0].color.rgb = color_start
        stops[0].position = 0.0
        stops[1].color.rgb = color_end
        stops[1].position = 1.0
        shape.line.fill.background()  # 无边框

    def _add_rounded_color_block(
        self,
        slide,
        left,
        top,
        width,
        height,
        color_rgb: RGBColor,
        corner_radius: float = 0.05,
    ) -> None:
        """添加圆角色块（圆角矩形 + 纯色填充，SPEC 0026）。

        参数：
        - corner_radius: 圆角半径（0.0-1.0，相对短边比例）
        """
        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height,
        )
        shape.adjustments[0] = corner_radius
        shape.fill.solid()
        shape.fill.fore_color.rgb = color_rgb
        shape.line.fill.background()  # 无边框

    def _add_picture_shadow(
        self,
        picture,
        blur_radius_pt: float = 8,
        distance_pt: float = 4,
        direction_deg: float = 315,
        alpha_pct: int = 30,
    ) -> None:
        """为图片添加外阴影效果（oxml 操作 a:effectLst，SPEC 0026）。

        python-pptx 未暴露 effect_format API，需直接操作 oxml。
        参数：
        - blur_radius_pt: 模糊半径（Pt）
        - distance_pt: 阴影距离（Pt）
        - direction_deg: 阴影方向（度，0=右，90=下，180=左，270=上）
        - alpha_pct: 不透明度百分比（0-100）
        """
        # EMU 转换常量：1 Pt = 12700 EMU；1 度 = 60000（1/60000 度）
        blur_emu = str(int(blur_radius_pt * 12700))
        dist_emu = str(int(distance_pt * 12700))
        dir_emu = str(int(direction_deg * 60000))
        # alpha 百分比 → 千分比（100% = 100000）
        alpha_val = str(int(alpha_pct * 1000))

        spPr = picture._element.spPr
        # 移除已有 effectLst（避免重复）
        existing = spPr.find(qn('a:effectLst'))
        if existing is not None:
            spPr.remove(existing)

        effect_lst = spPr.makeelement(qn('a:effectLst'), {})
        outer_shdw = effect_lst.makeelement(qn('a:outerShdw'), {
            'blurRad': blur_emu,
            'dist': dist_emu,
            'dir': dir_emu,
            'rotWithShape': '0',
        })
        clr = outer_shdw.makeelement(qn('a:srgbClr'), {'val': '000000'})
        alpha = clr.makeelement(qn('a:alpha'), {'val': alpha_val})
        clr.append(alpha)
        outer_shdw.append(clr)
        effect_lst.append(outer_shdw)
        spPr.append(effect_lst)

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
        primary: RGBColor,
        title_text_color: RGBColor,
    ) -> None:
        """添加深色页脚栏（渐变背景 + 白色项目名和页码，SPEC 0025/0026）。"""
        # 1. 渐变背景栏（SPEC 0026：主色暗化 15% → 主色，全幅，高 FOOTER_BAR_HEIGHT）
        primary_dark_15 = self._darken_color(primary, 0.15)
        self._add_gradient_block(
            slide,
            Inches(0), Inches(FOOTER_BAR_TOP),
            Inches(SLIDE_WIDTH), Inches(FOOTER_BAR_HEIGHT),
            primary_dark_15, primary, angle_deg=90,
        )

        # 2. 项目名（左，title_text_color）
        left_tb = slide.shapes.add_textbox(
            Inches(MARGIN_LEFT), Inches(FOOTER_BAR_TOP + 0.1),
            Inches(6), Inches(0.3),
        )
        lt = left_tb.text_frame
        lr = lt.paragraphs[0].add_run()
        lr.text = project_name
        self._set_run_font(
            lr, FONT_SIZE_CAPTION, title_text_color,
        )

        # 3. 页码（右，title_text_color）
        right_tb = slide.shapes.add_textbox(
            Inches(SLIDE_WIDTH - 3), Inches(FOOTER_BAR_TOP + 0.1),
            Inches(2.5), Inches(0.3),
        )
        rt = right_tb.text_frame
        rt.paragraphs[0].alignment = PP_ALIGN.RIGHT
        rr = rt.paragraphs[0].add_run()
        rr.text = f"第 {page_num} / {total_pages} 页"
        self._set_run_font(
            rr, FONT_SIZE_CAPTION, title_text_color,
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
