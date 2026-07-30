# SPEC 0024｜PPT 渲染器布局与视觉层次改进

> 状态：已完成实现与验收（2026-07-30）
> 所属版本：V2.5.0（独立新切片，不依赖 SPEC 0023 是否先行）
> 上游 SPEC：[SPEC 0011 PPT 配置选项](0011-ppt-config-options.md)（已确认收口，定义 PptConfig 配置合同）
> 关联 SPEC：[SPEC 0006 大纲与交付物](0006-outline-and-deliverables.md)（已确认收口，定义 PptRenderer 基础渲染）
> 关联决策：[决策 0032](../decisions/0032-start-spec-0024-ppt-renderer-layout.md)

---

## 实现收口说明（2026-07-30）

SPEC 0024 已完成实现与验收，关键结果：

- **核心实现**：重构 `ppt_renderer.py` 为空白版式（`slide_layouts[6]`）+ 精确定位驱动，新增 16:9 画布、双栏内容页（40% 文本 + 60% 图表）、图表自适应布局（单图居中/双图并排/2×2 网格）、五级字号体系（36/28/20/16/12 pt）、主题色扩展应用（色块/分隔线/圆点/标题）
- **测试修复**：修复 `test_ppt_config.py` 中 4 个因空白版式导致的测试（3 个失败 + 1 个空跳），新增 `_slide_has_color()` 辅助函数适配主题色验证
- **回归验证**：142 个 PPT/outline/word/renderer 相关测试全部通过（15.86s），107 个其他非流式测试通过（93.85s），无 SPEC 0024 引入的回归
- **真实文件验证**：生成 PPT 文件确认 16:9 画布（13.333×7.5 英寸）、五级字号完整（[12,16,20,28,36]pt）、主题色应用到全部 4/4 页面、双栏布局图文混排正确
- **约束遵守**：不引入新依赖、不改变 PptConfig 合同、不改变 API/service/Worker 接线、不修改数据库 schema、不改变文件存储路径和版本管理
- **预存非阻断债务**：`test_code_task_stream_api.py` 和 `test_requirement_api.py` 各有 1 个预存失败（`candidate_source` 期望 LOCAL_RULE 实际 DEEPSEEK），根因为 `server/.env` 中 `DEEPSEEK_API_KEY` 已设置导致 LLM 网关使用 DeepSeek provider，与 SPEC 0024 无关

---

## 一、背景与目标

### 1.1 痛点

SPEC 0011 已为 PPT 生成增加了配置能力（目标页数、主题色、图表开关），但端到端链路验证后发现 **PPT 视觉效果不尽人意**，具体问题：

| 问题 | 现状（ppt_renderer.py） | 影响 |
| --- | --- | --- |
| **布局粗糙** | 直接使用内置 `slide_layouts[0/1/5]`，依赖 PowerPoint 默认母版 | 视觉效果像未设计的默认模板，缺乏专业感 |
| **图表布置僵硬** | `Inches(1 + i*4)` 横向排列，固定 3.5 英寸宽，最多 2 张 | 单图不居中放大、多图溢出、无自适应布局 |
| **图文分离** | 图表页（layout 5）只有图、内容页（layout 1）只有文字 | 无法做"左文右图"双栏，信息割裂，演示节奏断裂 |
| **无视觉层次** | 内容 14pt、总结 16pt，无色块/分隔线/装饰元素 | 纯文字堆砌，缺乏层次感和呼吸感 |
| **主题色应用浅** | `_apply_theme_color` 只涂标题文字颜色 | 无色块背景、无分隔线、无要点标记色，主题色存在感弱 |
| **字体单一** | 全程默认 Calibri，无字号体系 | 无标题/副标题/正文/注释的层级区分 |
| **4:3 默认比例** | `Presentation()` 默认 10×7.5 英寸（4:3） | 不符合现代 16:9 投影/显示器标准 |

### 1.2 目标

在不引入新依赖、不改变 PptConfig 配置合同、不改变文件存储与版本管理机制的前提下，重构 `PptRenderer` 的布局与视觉层次：

1. **16:9 宽屏画布**：幻灯片尺寸改为 13.333×7.5 英寸
2. **双栏内容页**：左栏文本要点 + 右栏图表，40%/60% 分割
3. **图表自适应布局**：单图居中放大、双图并排、三图及以上网格排列
4. **视觉层次体系**：封面色块、章节分隔、字号体系、主题色扩展应用
5. **空白版式驱动**：放弃内置 layout，改用 `slide_layouts[6]`（空白版式）+ 精确定位

### 1.3 与 SPEC 0011 的关系

SPEC 0024 是 SPEC 0011 的**渲染层增强**，不改变配置合同：

| 维度 | SPEC 0011（已完成） | SPEC 0024（本切片） |
| --- | --- | --- |
| 改动层 | 配置合同 + 渲染器参数 | **仅渲染器布局与视觉** |
| PptConfig | 新增 | **不动**（保持 target_slide_count/theme_color/include_charts） |
| API/service/Worker | 新增 config 传递 | **不动** |
| 前端 UI | 新增配置表单 | **不动**（除非新增布局选项，见决策 5） |
| 渲染器内部 | 增加 config 解析 | **重构布局方法** |

**关键约束**：SPEC 0024 不修改 `PptRenderer.render()` 的方法签名和 `PptConfig` 合同，只重构渲染器内部的布局方法。现有调用方（Worker handler、service 层）零改动。

---

## 二、范围与边界

### 2.1 本切片实现

| # | 功能点 | 说明 |
| --- | --- | --- |
| F1 | 16:9 画布 | 幻灯片尺寸改为 13.333×7.5 英寸（`prs.slide_width = Inches(13.333)`） |
| F2 | 空白版式驱动 | 所有页面改用 `slide_layouts[6]`（空白版式），不再依赖内置 layout 0/1/5 |
| F3 | 封面页重构 | 主题色顶部色块 + 白色大标题 + 副标题 + 底部装饰线 |
| F4 | 双栏内容页 | 左栏 40% 文本要点（带主题色圆点）+ 右栏 60% 图表或补充文本 |
| F5 | 图表自适应布局 | 单图居中放大、双图并排、三图及以上 2×N 网格 |
| F6 | 图文混排页 | 内容页支持"左文右图"布局，当章节有关联图表时自动启用双栏 |
| F7 | 总结页重构 | 居中排版 + 主题色分隔线 + 要点提炼 |
| F8 | 字号体系 | 主标题 36pt / 页面标题 28pt / 副标题 20pt / 正文 16pt / 注释 12pt |
| F9 | 主题色扩展应用 | 色块背景、分隔线、要点圆点标记、章节左侧色条 |
| F10 | 页脚信息 | 每页底部显示项目名 + 页码（封面页除外） |

### 2.2 本切片不做

- **不引入新依赖**（继续使用 `python-pptx>=1.0.2`，不做 html2pptx、不做 MckEngine）
- **不改变 PptConfig 合同**（`target_slide_count`/`theme_color`/`include_charts` 三字段不变）
- **不改变 API/service/Worker 接线**（`render()` 签名不变，调用方零改动）
- **不改变文件存储路径和版本管理**（仍是 `ppt_v{version}.pptx`，版本递增，旧版本保留）
- **不做 PPT 动画、过渡效果**（推迟到 V3.0）
- **不做 PPT 母版上传**（推迟到 V2.0 或后续）
- **不做在线 PPT 预览**（推迟到 V2.0）
- **不做 Word 生成流程改动**（Word 渲染器不动）
- **不做配置持久化**（每次生成时传参，不落库）
- **不做自定义字体嵌入**（使用系统通用字体，见决策 4）

---

## 三、设计决策

### 决策 1：采用 16:9 宽屏画布

**选择**：幻灯片尺寸改为 13.333×7.5 英寸（16:9）。

**理由**：
- 现代投影仪、显示器、笔记本屏幕均为 16:9 或 16:10
- 4:3 画布在 16:9 屏幕上左右出现黑边，视觉效果差
- 16:9 横向空间更充裕，适合双栏布局
- python-pptx 支持 `prs.slide_width = Inches(13.333)` 直接设置

**约束**：
- 所有布局参数基于 13.333×7.5 英寸画布设计
- 不支持混合比例（全片统一 16:9）

### 决策 2：采用空白版式 + 精确定位

**选择**：放弃内置 `slide_layouts[0/1/5]`，全部改用 `slide_layouts[6]`（空白版式），用 `add_textbox`/`add_picture`/`add_shape` 精确控制每个元素。

**理由**：
- 内置 layout 依赖 PowerPoint 默认母版，视觉效果不可控
- 空白版式 + 精确定位可以完全控制位置、大小、配色、字体
- python-pptx 的 `add_textbox`/`add_picture`/`add_shape` API 足够灵活
- 不引入新依赖，纯 python-pptx 实现

**约束**：
- 每个元素的位置（left/top）和大小（width/height）必须显式指定
- 使用 `Inches()` 和 `Pt()` 确保跨平台一致性

### 决策 3：双栏内容页采用 40%/60% 分割

**选择**：内容页左栏文本占 40%（约 5.3 英寸），右栏图表占 60%（约 7.2 英寸）。

**理由**：
- 实验报告的图表通常比文字更需要展示空间（数据可视化是核心）
- 40% 左栏足够展示 3-5 个要点（每行约 30 个汉字）
- 60% 右栏可以完整展示一张标准 matplotlib 图表（默认 6.4×4.8 英寸）
- 符合 Anthropic pptx skill 推荐的双栏比例

**约束**：
- 当章节无关联图表时，右栏展示补充文本或留白（不强行填充）
- 当章节图表超过 1 张时，右栏只放第一张，其余图表进入独立图表页
- 左栏要点超过 5 个时截断并加省略号

### 决策 4：字号体系与字体选择

**选择**：建立五级字号体系，使用系统通用字体。

**字号体系**：

| 层级 | 字号 | 用途 | 字重 |
| --- | --- | --- | --- |
| L1 主标题 | 36pt | 封面页项目课题 | Bold |
| L2 页面标题 | 28pt | 内容页/图表页/总结页标题 | Bold |
| L3 副标题 | 20pt | 封面副标题、总结正文 | Regular |
| L4 正文 | 16pt | 内容页要点 | Regular |
| L5 注释 | 12pt | 页脚、图表说明 | Regular |

**字体选择**：
- 中文：微软雅黑（Windows 系统通用，渲染稳定）
- 英文/数字：Calibri（python-pptx 默认，兼容性好）
- 不嵌入字体文件（避免文件体积膨胀）

**理由**：
- 五级字号体系覆盖所有 PPT 场景，层次清晰
- 微软雅黑是 Windows 系统字体，无需额外安装
- 不嵌入字体避免文件体积从 60KB 膨胀到数 MB

### 决策 5：主题色扩展应用（不新增配置字段）

**选择**：扩展现有 `theme_color` 的应用范围，不新增 PptConfig 字段。

**应用范围扩展**（SPEC 0011 基础上）：

| 元素 | SPEC 0011 | SPEC 0024 新增 |
| --- | --- | --- |
| 标题文字颜色 | ✅ | ✅（保持） |
| 封面色块背景 | ❌ | ✅ 顶部全幅色块 |
| 标题下分隔线 | ❌ | ✅ 主题色细线 |
| 要点圆点标记 | ❌ | ✅ 主题色实心圆点 |
| 章节左侧色条 | ❌ | ✅ 主题色竖条 |
| 页脚分隔线 | ❌ | ✅ 主题色浅色细线 |

**理由**：
- 主题色应用范围扩展是渲染器内部改进，不需要用户额外配置
- 保持 PptConfig 三字段不变，向后兼容
- `theme_color=None` 时使用默认深灰色（`#333333`）替代黑色，视觉更柔和

### 决策 6：图表自适应布局策略

**选择**：根据图表数量自动选择布局模式。

| 图表数量 | 布局模式 | 参数 |
| --- | --- | --- |
| 1 张 | 居中放大 | left=2.67", top=1.5", width=8"（居中） |
| 2 张 | 左右并排 | 各 width=5.8"，left=0.5" 和 7.0" |
| 3-4 张 | 2×2 网格 | 各 width=3.8"，2 行 2 列 |
| 5+ 张 | 截断到 4 张 | 仅展示前 4 张，加注释"共 N 张，已展示前 4 张" |

**理由**：
- 单图居中放大突出重点
- 双图并排便于对比
- 网格布局容纳多图且不溢出
- 截断到 4 张避免页面拥挤

**约束**：
- 图表保持原始宽高比（`width` 指定，`height` 自适应）
- 图表嵌入失败时显示占位文本框（保持现有降级行为）

---

## 四、架构设计

### 4.1 Owner 边界（不变）

SPEC 0024 不改变现有 owner 边界，只重构 `PptRenderer` 内部方法：

| 层 | 文件 | 职责变化 |
| --- | --- | --- |
| 渲染器 | `server/app/infrastructure/renderers/ppt_renderer.py` | **重构布局方法**（本切片核心） |
| 合同层 | `server/app/modules/outlines/contracts.py` | 不变 |
| Service 层 | `server/app/modules/outlines/service.py` | 不变 |
| API 适配层 | `server/app/api/routers/outlines.py` | 不变 |
| Worker | `server/worker/handlers.py` | 不变 |
| 前端 | `apps/web/src/` | 不变 |

### 4.2 画布与布局常量

在 `ppt_renderer.py` 顶部新增布局常量（不作为配置，只作为渲染器内部参数）：

```python
# 16:9 画布尺寸（英寸）
SLIDE_WIDTH = 13.333
SLIDE_HEIGHT = 7.5

# 页面边距
MARGIN_LEFT = 0.5
MARGIN_RIGHT = 0.5
MARGIN_TOP = 0.5
MARGIN_BOTTOM = 0.5

# 双栏布局参数
CONTENT_LEFT_WIDTH = 5.3    # 左栏文本宽度（40%）
CONTENT_RIGHT_LEFT = 6.1    # 右栏起始位置
CONTENT_RIGHT_WIDTH = 6.7   # 右栏图表宽度（60%）

# 字号体系（Pt）
FONT_SIZE_MAIN_TITLE = 36
FONT_SIZE_PAGE_TITLE = 28
FONT_SIZE_SUBTITLE = 20
FONT_SIZE_BODY = 16
FONT_SIZE_CAPTION = 12

# 字体
FONT_NAME_CN = "微软雅黑"
FONT_NAME_EN = "Calibri"

# 默认主题色（theme_color=None 时使用）
DEFAULT_THEME_COLOR = "333333"  # 深灰色

# 色块高度
TITLE_BANNER_HEIGHT = 2.5      # 封面顶部色块高度
SECTION_BAR_WIDTH = 0.3        # 章节左侧色条宽度
DIVIDER_HEIGHT = 0.04          # 分隔线粗细
```

### 4.3 封面页布局

```
┌─────────────────────────────────────────┐
│                                         │  ← 主题色全幅色块（高 2.5"）
│           项目课题（36pt 白色 Bold）       │
│                                         │
├─────────────────────────────────────────┤
│                                         │
│  项目：XXX（20pt 深灰）                    │
│  生成日期：2026-07-30（20pt 深灰）          │
│                                         │
│                                         │
│                                         │
├─────────────────────────────────────────┤
│  ─────── 主题色装饰线 ───────────────────  │  ← 底部装饰线
└─────────────────────────────────────────┘
```

**实现**：
```python
def _render_title_slide(self, prs, project_name, project_topic, theme_rgb):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # 空白版式

    # 1. 顶部主题色块
    banner = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0),
        Inches(SLIDE_WIDTH), Inches(TITLE_BANNER_HEIGHT),
    )
    banner.fill.solid()
    banner.fill.fore_color.rgb = theme_rgb
    banner.line.fill.background()  # 无边框

    # 2. 主标题（色块内白色文字）
    title_tb = slide.shapes.add_textbox(
        Inches(0.5), Inches(0.6),
        Inches(SLIDE_WIDTH - 1), Inches(1.4),
    )
    title_tb.text_frame.text = project_topic or "实验报告"
    # 设置字号 36pt、白色、Bold、居中、微软雅黑

    # 3. 副标题（色块下方）
    subtitle_tb = slide.shapes.add_textbox(
        Inches(0.5), Inches(3.0),
        Inches(SLIDE_WIDTH - 1), Inches(1.5),
    )
    # 设置项目名 + 日期，20pt 深灰

    # 4. 底部装饰线
    divider = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0.5), Inches(SLIDE_HEIGHT - 0.6),
        Inches(SLIDE_WIDTH - 1), Inches(DIVIDER_HEIGHT),
    )
    divider.fill.solid()
    divider.fill.fore_color.rgb = theme_rgb
```

### 4.4 双栏内容页布局

```
┌─────────────────────────────────────────┐
│ 页面标题（28pt 主题色 Bold）               │
│ ─────── 主题色分隔线 ───────────────────  │
├──────────────────┬──────────────────────┤
│                  │                      │
│  • 要点 1（16pt）  │                      │
│    说明文本...     │     [图表/图片]        │
│  • 要点 2（16pt）  │                      │
│    说明文本...     │                      │
│  • 要点 3（16pt）  │                      │
│    说明文本...     │                      │
│                  │                      │
├──────────────────┴──────────────────────┤
│ 项目名                          第 N 页   │  ← 页脚（12pt 浅灰）
└─────────────────────────────────────────┘
```

**左栏（文本，40%）**：
- 位置：`left=0.5", top=1.5", width=5.3", height=5.0"`
- 要点格式：主题色实心圆点 + 标题（Bold）+ 换行 + 说明文本
- 最多 5 个要点，超出截断加省略号
- 字号 16pt，行距 1.2 倍

**右栏（图表/补充文本，60%）**：
- 位置：`left=6.1", top=1.5", width=6.7", height=5.0"`
- 有关联图表：嵌入第一张图表（自适应缩放到右栏宽度）
- 无关联图表：展示补充文本或留白

**实现**：
```python
def _add_content_slide(self, prs, title, sections, theme_rgb,
                       chart_artifact=None, page_num=0, total_pages=0,
                       project_name=""):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # 1. 页面标题 + 分隔线
    self._add_page_title(slide, title, theme_rgb)

    # 2. 左栏文本
    self._add_content_left_column(slide, sections, theme_rgb)

    # 3. 右栏图表或补充文本
    if chart_artifact:
        self._add_content_right_chart(slide, chart_artifact)
    else:
        self._add_content_right_text(slide, sections, theme_rgb)

    # 4. 页脚
    self._add_footer(slide, project_name, page_num, total_pages, theme_rgb)
```

### 4.5 图表自适应布局

独立图表页（当内容页无法容纳所有图表时使用）：

```python
def _add_chart_slide(self, prs, chart_artifacts, theme_rgb,
                     page_num=0, total_pages=0, project_name=""):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    self._add_page_title(slide, "关键图表", theme_rgb)

    count = len(chart_artifacts[:4])  # 最多 4 张
    if count == 1:
        # 单图居中放大
        self._place_chart_centered(slide, chart_artifacts[0])
    elif count == 2:
        # 双图左右并排
        self._place_chart_side_by_side(slide, chart_artifacts[:2])
    else:
        # 3-4 图 2×2 网格
        self._place_chart_grid(slide, chart_artifacts[:4])

    if len(chart_artifacts) > 4:
        # 添加截断注释
        self._add_truncation_note(slide, len(chart_artifacts))

    self._add_footer(slide, project_name, page_num, total_pages, theme_rgb)
```

**布局参数**：

| 模式 | 参数 |
| --- | --- |
| 单图居中 | `left=2.67", top=1.5", width=8"` |
| 双图并排 | 各 `width=5.8"`，`left=0.5"` 和 `7.0"`，`top=1.8"` |
| 2×2 网格 | 各 `width=3.8"`，`left=0.7"/6.8"`，`top=1.5"/4.2"` |

### 4.6 总结页布局

```
┌─────────────────────────────────────────┐
│ 总结（28pt 主题色 Bold）                  │
│ ─────── 主题色分隔线 ───────────────────  │
├─────────────────────────────────────────┤
│                                         │
│                                         │
│        总结正文（20pt 深灰，居中）          │
│        第一段...                          │
│        第二段...                          │
│                                         │
│                                         │
│                                         │
├─────────────────────────────────────────┤
│ ─────── 主题色装饰线 ───────────────────  │
│ 项目名                          第 N 页   │
└─────────────────────────────────────────┘
```

### 4.7 辅助方法设计

新增以下辅助方法（均为 `PptRenderer` 的私有方法）：

```python
class PptRenderer:
    # --- 布局辅助 ---

    def _add_page_title(self, slide, title, theme_rgb):
        """添加页面标题 + 主题色分隔线。"""

    def _add_content_left_column(self, slide, sections, theme_rgb):
        """添加左栏文本要点（主题色圆点 + 标题 + 说明）。"""

    def _add_content_right_chart(self, slide, artifact):
        """添加右栏图表（自适应缩放到右栏宽度）。"""

    def _add_content_right_text(self, slide, sections, theme_rgb):
        """无图表时右栏展示补充文本。"""

    def _add_footer(self, slide, project_name, page_num, total_pages, theme_rgb):
        """添加页脚（项目名 + 页码 + 分隔线）。"""

    def _place_chart_centered(self, slide, artifact):
        """单图居中放大布局。"""

    def _place_chart_side_by_side(self, slide, artifacts):
        """双图左右并排布局。"""

    def _place_chart_grid(self, slide, artifacts):
        """多图 2×N 网格布局。"""

    def _add_truncation_note(self, slide, total_count):
        """添加截断注释（超过 4 张图表时）。"""

    # --- 样式辅助 ---

    def _set_font(self, text_frame, size, color_rgb=None,
                  bold=False, font_name=FONT_NAME_CN):
        """统一设置文本框字体样式。"""

    def _add_color_block(self, slide, left, top, width, height, color_rgb):
        """添加纯色色块（无边框矩形）。"""

    def _add_divider(self, slide, left, top, width, color_rgb,
                     height=DIVIDER_HEIGHT):
        """添加分隔线（细矩形）。"""

    def _add_bullet_point(self, text_frame, text, color_rgb,
                          is_first=False):
        """添加要点（主题色圆点 + 文本）。"""
```

### 4.8 主题色默认值处理

SPEC 0011 中 `theme_color=None` 时使用默认黑色。SPEC 0024 改为默认深灰色（`#333333`），视觉更柔和：

```python
def _resolve_theme_color(self, theme_color: str | None) -> RGBColor:
    """解析主题色，None 时降级到默认深灰色。"""
    if not theme_color:
        return RGBColor.from_string(DEFAULT_THEME_COLOR)  # #333333
    # ... 现有解析逻辑 ...
```

**注意**：这不改变 PptConfig 合同，`theme_color=None` 仍表示"使用默认"，只是默认值从黑色改为深灰色。

### 4.9 图文关联策略

内容页是否启用双栏（左文右图）取决于章节是否有关联图表：

**关联规则**：
1. 按章节 `source_type` 分组（与现有逻辑一致）
2. `EXECUTION` 类型章节关联 `CHART_PNG` 产物
3. 每个内容页取第一张关联图表放入右栏
4. 剩余图表进入独立图表页

**实现**：
```python
def _render_content_slides(self, prs, outline_sections, artifacts,
                           theme_rgb, include_charts, target_slide_count):
    # 按 source_type 分组
    by_type = {}
    for section in outline_sections:
        st = section.get("source_type", "")
        by_type.setdefault(st, []).append(section)

    # 收集图表产物
    chart_artifacts = (
        [a for a in artifacts if a.get("artifact_type") == "CHART_PNG"]
        if include_charts else []
    )

    # 构建内容页候选（每页关联一张图表）
    content_groups = self._build_content_groups(by_type, chart_artifacts)

    # 页数控制（复用 SPEC 0011 逻辑）
    if target_slide_count is not None:
        content_groups = self._control_slide_count(
            content_groups, target_slide_count)

    # 渲染内容页
    total_pages = len(content_groups) + 2  # +标题页+总结页
    for i, (title, sections, chart) in enumerate(content_groups):
        self._add_content_slide(
            prs, title, sections, theme_rgb,
            chart_artifact=chart,
            page_num=i + 2, total_pages=total_pages,
            project_name=...,  # 由 render() 传入
        )

    # 剩余图表进入独立图表页
    used_charts = {g[2] for g in content_groups if g[2]}
    remaining_charts = [c for c in chart_artifacts if c not in used_charts]
    if remaining_charts:
        self._add_chart_slide(prs, remaining_charts, theme_rgb, ...)
```

---

## 五、实现计划

### 步骤 1：布局常量与辅助方法

- 在 `ppt_renderer.py` 顶部新增布局常量（画布尺寸、边距、字号、字体、颜色）
- 新增辅助方法：`_set_font`、`_add_color_block`、`_add_divider`、`_add_bullet_point`、`_add_page_title`、`_add_footer`

### 步骤 2：封面页重构

- 重写 `_render_title_slide`：空白版式 + 顶部色块 + 白色大标题 + 副标题 + 底部装饰线

### 步骤 3：双栏内容页实现

- 重写 `_add_content_slide`：左栏文本 + 右栏图表/补充文本
- 新增 `_add_content_left_column`、`_add_content_right_chart`、`_add_content_right_text`

### 步骤 4：图表自适应布局

- 重写 `_add_chart_slide`：根据图表数量选择布局模式
- 新增 `_place_chart_centered`、`_place_chart_side_by_side`、`_place_chart_grid`、`_add_truncation_note`

### 步骤 5：总结页重构

- 重写 `_render_summary_slide`：居中排版 + 主题色分隔线 + 要点提炼

### 步骤 6：图文关联与页数控制

- 重写 `_render_content_slides`：构建内容页候选时关联图表
- 复用 SPEC 0011 的 `_control_slide_count` 页数控制逻辑（不改变）

### 步骤 7：画布尺寸与主题色默认值

- `render()` 入口设置 `prs.slide_width = Inches(13.333)` 和 `prs.slide_height = Inches(7.5)`
- `_parse_theme_color` 改为 `_resolve_theme_color`，None 时返回默认深灰色

### 步骤 8：测试

- 渲染器单元测试：覆盖所有布局模式（封面/双栏/图表自适应/总结）、主题色应用、字号体系、页数控制向后兼容
- 回归测试：`config=None` 时行为合理（不报错，使用默认布局）、`PptConfig` 各字段仍生效
- 真实文件生成验证：生成 PPT 后检查页数、元素数量、色块存在性

### 步骤 9：验收 + 文档回写 + git 收口

- 运行完整验收命令
- 更新 `acceptance.md`、`implementation-plan.md`
- 新增决策记录
- git commit + push

---

## 六、验收标准

### 6.1 渲染器布局验收

| # | 验收点 | 期望结果 |
| --- | --- | --- |
| R1 | 生成 PPT 的幻灯片尺寸 | 13.333×7.5 英寸（16:9） |
| R2 | 封面页布局 | 顶部主题色块 + 白色 36pt 标题 + 副标题 + 底部装饰线 |
| R3 | 内容页双栏布局 | 左栏文本（40%）+ 右栏图表或补充文本（60%） |
| R4 | 内容页要点格式 | 主题色圆点 + 16pt 文本，最多 5 个要点 |
| R5 | 图表页单图布局 | 居中放大，width=8" |
| R6 | 图表页双图布局 | 左右并排，各 width=5.8" |
| R7 | 图表页 4 图布局 | 2×2 网格，各 width=3.8" |
| R8 | 图表超过 4 张 | 截断到 4 张，显示截断注释 |
| R9 | 总结页布局 | 居中 20pt 正文 + 主题色分隔线 |
| R10 | 页脚显示 | 项目名 + 页码（封面页除外） |

### 6.2 字号与字体验收

| # | 验收点 | 期望结果 |
| --- | --- | --- |
| F1 | 封面主标题字号 | 36pt Bold |
| F2 | 页面标题字号 | 28pt Bold |
| F3 | 副标题字号 | 20pt Regular |
| F4 | 正文字号 | 16pt Regular |
| F5 | 页脚字号 | 12pt Regular |
| F6 | 中文字体 | 微软雅黑 |

### 6.3 主题色验收

| # | 验收点 | 期望结果 |
| --- | --- | --- |
| C1 | `theme_color="#2563eb"` 封面色块 | 顶部色块为蓝色 |
| C2 | `theme_color="#2563eb"` 分隔线 | 标题下分隔线为蓝色 |
| C3 | `theme_color="#2563eb"` 要点圆点 | 左栏要点圆点为蓝色 |
| C4 | `theme_color=None` 默认色 | 使用深灰色 `#333333` |
| C5 | `theme_color="#invalid"` 降级 | 记录 warning，降级到默认深灰色 |

### 6.4 向后兼容验收

| # | 验收点 | 期望结果 |
| --- | --- | --- |
| B1 | `config=None` 渲染 | 成功生成 PPT，使用默认布局和默认主题色 |
| B2 | `config={"target_slide_count":6}` | 页数控制仍生效（SPEC 0011 逻辑不变） |
| B3 | `config={"include_charts":false}` | 不生成图表页（SPEC 0011 逻辑不变） |
| B4 | `render()` 方法签名 | 与 SPEC 0011 完全一致，调用方零改动 |

### 6.5 整体验收命令

```text
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
npm.cmd run test -- --run
```

### 6.6 浏览器/真实文件验收

- 生成一份真实 PPT 文件，用 PowerPoint 或 WPS 打开确认视觉效果
- 截图保存至 `dev-docs/e2e-screenshots/spec0024-*.png`
- 验收点：封面色块、双栏布局、图表自适应、字号层次、主题色应用

---

## 七、风险与降级

### 7.1 空白版式兼容性

**风险**：`slide_layouts[6]`（空白版式）在不同 python-pptx 版本中索引可能不同。

**缓解**：
- 使用 `prs.slide_layouts[6]` 时先检查 layout 名称或占位符数量
- 若索引错误，降级到 `prs.slide_layouts[0]` 并删除所有占位符
- 新增单元测试验证空白版式可用性

### 7.2 图表宽高比失真

**风险**：指定 `width` 但不指定 `height` 时，python-pptx 会保持原始宽高比；但同时指定两者可能导致失真。

**缓解**：
- 图表嵌入时只指定 `width`，不指定 `height`（让 python-pptx 自动计算高度）
- 若计算高度超过右栏范围，缩小 `width` 重试
- 新增测试验证图表未失真（检查 width/height 比例）

### 7.3 微软雅黑跨平台

**风险**：Linux 服务器（如 Docker 部署）可能没有微软雅黑字体，PPT 打开时回退到其他字体。

**缓解**：
- 字体回退不影响 PPT 文件结构，只在打开时视觉变化
- Docker 镜像（SPEC 0013）可安装 `fonts-wqy-microhei` 作为中文回退
- 本切片不做字体嵌入（推迟到后续优化）

### 7.4 向后兼容

**风险**：现有调用方依赖内置 layout 的占位符行为。

**缓解**：
- `render()` 方法签名不变，调用方零改动
- `config=None` 时使用新布局（不保留旧布局），但行为合理（不报错）
- 现有测试中 mock 渲染器的不受影响（mock 的是方法，不是 layout）

### 7.5 性能

**风险**：空白版式 + 精确定位可能比内置 layout 稍慢（更多 shape 操作）。

**缓解**：
- PPT 生成是低频操作（用户手动触发），性能不敏感
- 单次生成预计 < 2 秒（与现有持平）
- 新增测试验证生成耗时无显著增加

---

## 八、依赖与配置

### 8.1 依赖

- **无新增依赖**（`python-pptx>=1.0.2` 已安装）
- 需要 `from pptx.enum.shapes import MSO_SHAPE`（用于矩形色块，python-pptx 内置）

### 8.2 配置

- **无新增环境变量**
- **无新增数据库迁移**（布局参数是渲染器内部常量，不落库）
- **不改变 PptConfig 合同**

---

## 九、不属于本切片的事项

- PPT 母版上传与自定义模板（推迟到 V2.0 或后续）
- PPT 动画与过渡效果（推迟到 V3.0）
- 在线 PPT 预览（推迟到 V2.0）
- Word 渲染器布局改进（独立切片，不混入本切片）
- 自定义字体嵌入（推迟到后续优化）
- PPT 配置持久化（每次生成时传参，不落库）
- 新增 PptConfig 字段（如布局模式选择、字号自定义等，推迟到后续）
- html2pptx 工作流（不引入新依赖）
- MckEngine 框架（不引入第三方框架）
