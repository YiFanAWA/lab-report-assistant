# SPEC 0025｜PPT 三角色彩系统与深浅对比三明治结构

> 状态：已完成实现与验收（2026-07-31）
> 所属版本：V2.6.0（独立新切片，依赖 SPEC 0024 已收口）
> 上游 SPEC：[SPEC 0024 PPT 渲染器布局与视觉层次改进](0024-ppt-renderer-layout-and-visual-hierarchy.md)（已确认收口，建立单色主题 + 空白版式 + 双栏布局基础）
> 上游 SPEC：[SPEC 0011 PPT 配置选项](0011-ppt-config-options.md)（已确认收口，定义 PptConfig 配置合同）
> 关联 SPEC：[SPEC 0006 大纲与交付物](0006-outline-and-deliverables.md)（已确认收口，定义 PptRenderer 基础渲染）
> 关联决策：[决策 0034](../decisions/0034-start-spec-0025-ppt-color-system.md)

---

## 实现收口说明（2026-07-31）

SPEC 0025 已完成实现与验收，关键结果：

- **核心实现**：在 `ppt_renderer.py` 中新增 `_derive_color_palette` 方法（使用 `colorsys` 标准库从单一 `theme_color` 派生主色/辅助色/强调色/标题文字色），重构 `_add_page_title`（主色背景标题栏）、`_add_footer`（主色背景页脚栏）、`_add_content_left_column`（辅助色背景 + 强调色要点）、`_render_title_slide`（底部主色窄条三明治收口）、`_add_chart_slide` 和 `_render_summary_slide`（适配三明治结构）
- **三角色彩派生**：主色 = 原值；辅助色 = 高亮度（L=0.92）低饱和度（S≤0.30）浅色；强调色 = 互补色相（H+0.5）中亮度（L=0.45）高饱和度（S=0.50-0.70）；低饱和度（S<0.20）特殊处理为蓝色 #2563EB
- **对比度保障**：主色亮度 > 0.60 时标题文字用深灰，否则用白色；阈值 0.60 覆盖紫色 #7c3aed（L≈0.578），使 5 种预设深色统一用白字（紫色白字对比度 5.83:1 通过 WCAG AA）
- **三明治结构**：所有页面统一为"深色标题栏（1.0"）→ 浅色内容区（5.6"）→ 深色页脚栏（0.5"）"三层结构
- **测试新增**：新增 16 个 SPEC 0025 专用测试（8 个色彩派生 + 7 个三明治结构 + 1 个紫色阈值），覆盖 6 种预设色派生、灰色特殊处理、无效色降级、标题栏/页脚栏/左栏背景存在性、强调色要点验证
- **回归验证**：PPT config + renderer 测试 57 passed（含 16 个新增）；PPT/outline/renderer 全量 222 passed（1 预存 DEEPSEEK 失败）；outline worker/API/service 83 passed；前端 lint/build 通过；Alembic 迁移通过
- **真实文件验证**：生成 6 种预设色 PPT 文件，程序化验证三角色彩派生正确性和三明治结构完整性（封面/内容页/总结页都有主色背景，内容页有辅助色背景和强调色文字）
- **约束遵守**：不引入新依赖（`colorsys` 是 Python 标准库）、不改变 PptConfig 合同、不改变 API/service/Worker 接线、不修改数据库 schema、不改变 SPEC 0024 布局参数

---

## 一、背景与目标

### 1.1 痛点

SPEC 0024 已建立 16:9 画布 + 空白版式 + 双栏布局 + 五级字号 + 单色主题的基础视觉体系，但端到端视觉测评发现仍有**两个结构性短板**：

| 问题 | 现状（SPEC 0024 ppt_renderer.py） | 影响 |
| --- | --- | --- |
| **单色平涂，缺乏色彩层次** | 全片只用一个 `theme_color` 涂色块、分隔线、圆点、标题文字 | 无辅助色做背景衬托、无强调色突出关键信息，视觉扁平 |
| **全浅色页面，缺乏深浅对比节奏** | 标题区无背景色块（只有彩色文字 + 细分隔线）、页脚只有浅灰细线 | 页面"轻飘飘"，标题区和页脚区与内容区无视觉分离，缺乏专业 PPT 的"三明治"层次感 |
| **要点标记与正文同色** | 圆点标记和标题都用 `theme_color`，说明文本用 `#333333` | 无法区分"结构标记"和"强调重点"，信息优先级扁平 |
| **图表区域无背景衬托** | 右栏图表直接放在白色画布上 | 图表与左栏文本缺乏视觉分离，双栏边界模糊 |

### 1.2 目标

在 SPEC 0024 已建立的空白版式 + 精确定位基础上，引入**三角色彩系统**和**深浅对比三明治结构**：

1. **三角色彩系统**：从用户选择的单一 `theme_color` 算法派生主色、辅助色、强调色三个角色，各自承担明确的视觉职责
2. **深浅对比三明治结构**：每页统一为"深色标题栏 → 浅色内容区 → 深色页脚栏"三层结构，通过明暗对比建立视觉节奏
3. **不改 PptConfig 合同**：继续使用单一 `theme_color` 入口，三色由渲染器内部算法派生，用户无需配置三个颜色

### 1.3 与 SPEC 0024 的关系

SPEC 0025 是 SPEC 0024 的**色彩与结构增强**，不改变布局基础：

| 维度 | SPEC 0024（已完成） | SPEC 0025（本切片） |
| --- | --- | --- |
| 画布与版式 | 16:9 + 空白版式 + 双栏 40%/60% | **不动**（保持布局参数） |
| 色彩系统 | 单一 `theme_color` | **升级为三角色彩**（主/辅/强调） |
| 标题区 | 彩色文字 + 细分隔线 | **深色背景栏 + 白色文字** |
| 页脚区 | 浅灰细线 + 灰色文字 | **深色背景栏 + 白色文字** |
| 内容区背景 | 纯白画布 | **辅助色浅色背景衬托** |
| PptConfig | 三字段不变 | **不动**（算法派生，不加字段） |
| API/service/Worker | 不动 | **不动** |

**关键约束**：SPEC 0025 不修改 `PptRenderer.render()` 的方法签名和 `PptConfig` 合同，只重构渲染器内部的色彩派生与标题/页脚渲染方法。现有调用方（Worker handler、service 层）零改动。

---

## 二、范围与边界

### 2.1 本切片实现

| # | 功能点 | 说明 |
| --- | --- | --- |
| F1 | 三角色彩派生 | 从 `theme_color` 算法派生主色（Primary）、辅助色（Auxiliary）、强调色（Accent） |
| F2 | 深色标题栏 | 内容页/图表页/总结页标题区改为深色背景栏（主色填充）+ 白色标题文字 |
| F3 | 深色页脚栏 | 所有页面页脚区改为深色背景栏（主色填充）+ 白色项目名和页码 |
| F4 | 辅助色背景衬托 | 左栏文本区添加辅助色浅色背景矩形，与右栏图表区视觉分离 |
| F5 | 强调色要点标记 | 左栏圆点标记和章节标题改用强调色，与主色标题栏形成区分 |
| F6 | 封面页三明治收口 | 封面页底部增加深色页脚栏，与顶部色块形成完整三明治结构 |
| F7 | 色彩对比度保障 | 深色栏上用白色文字，浅色区上用深色文字，确保 WCAG AA 对比度 |

### 2.2 本切片不做

- **不引入新依赖**（继续使用 `python-pptx>=1.0.2` + Python 标准库 `colorsys`）
- **不改变 PptConfig 合同**（`target_slide_count`/`theme_color`/`include_charts` 三字段不变）
- **不改变 PPT_THEME_COLORS 预设色板**（6 色不变，用户仍从中选一个）
- **不改变 API/service/Worker 接线**（`render()` 签名不变，调用方零改动）
- **不改变 SPEC 0024 布局参数**（画布尺寸、双栏比例、字号体系、图表自适应布局不变）
- **不改变文件存储路径和版本管理**（仍是 `ppt_v{version}.pptx`）
- **不做用户自定义三色配置**（三色由算法派生，不加 `auxiliary_color`/`accent_color` 字段）
- **不做 PPT 动画、过渡效果**（推迟到 V3.0）
- **不做 Word 渲染器色彩改进**（独立切片，不混入本切片）
- **不做色盲友好配色**（推迟到后续 SPEC，本切片先用互补色派生）

---

## 三、设计决策

### 决策 1：采用算法派生三角色，不扩展 PptConfig

**选择**：从用户选择的单一 `theme_color` 算法派生主色、辅助色、强调色，不新增 PptConfig 字段。

**理由**：
- 保持 PptConfig 三字段不变，向后兼容 SPEC 0011/0024
- 用户只需选一个主题色，降低配置负担
- 算法派生可保证三色色彩协调（同色系辅助色 + 互补强调色）
- 避免 UI 表单新增两个颜色选择器
- 若后续需要用户自定义三色，可另立 SPEC 扩展 PptConfig

**约束**：
- `theme_color=None` 时使用默认主色 `#333333`（深灰），派生辅助色和强调色
- 派生算法必须对 6 种预设色都产生视觉合理的输出
- 派生失败时降级到默认三色组合（不报错）

### 决策 2：三角色彩派生算法

**选择**：使用 Python 标准库 `colorsys`（RGB ↔ HLS 转换）派生三色。

**角色定义**：

| 角色 | 用途 | 派生方式 |
| --- | --- | --- |
| **主色（Primary）** | 标题栏背景、页脚栏背景、封面色块 | = `theme_color`（原值） |
| **辅助色（Auxiliary）** | 左栏背景衬托、图表区背景、分隔线 | 主色提高亮度到 92%（`L=0.92`），降低饱和度到 30%（`S=0.30`） |
| **强调色（Accent）** | 要点圆点标记、章节标题、关键结论 | 主色色相旋转 180°（互补色），亮度 45%，饱和度 70% |

**算法实现**（伪代码）：

```python
import colorsys

def _derive_color_palette(self, theme_rgb: RGBColor) -> tuple[RGBColor, RGBColor, RGBColor]:
    """从主题色派生三角色彩（主色/辅助色/强调色）。

    返回 (primary, auxiliary, accent)。
    """
    # 提取 RGB 分量（0-1 范围）
    r = theme_rgb[0] / 255
    g = theme_rgb[1] / 255
    b = theme_rgb[2] / 255

    # 转 HLS
    h, l, s = colorsys.rgb_to_hls(r, g, b)

    # 主色 = 原色
    primary = theme_rgb

    # 辅助色 = 高亮度低饱和度（浅色背景）
    aux_h, aux_l, aux_s = h, 0.92, min(s, 0.30)
    aux_r, aux_g, aux_b = colorsys.hls_to_rgb(aux_h, aux_l, aux_s)
    auxiliary = RGBColor(
        int(aux_r * 255), int(aux_g * 255), int(aux_b * 255),
    )

    # 强调色 = 互补色相（H+0.5），中亮度高饱和度
    acc_h = (h + 0.5) % 1.0
    acc_l, acc_s = 0.45, min(max(s, 0.50), 0.70)
    acc_r, acc_g, acc_b = colorsys.hls_to_rgb(acc_h, acc_l, acc_s)
    accent = RGBColor(
        int(acc_r * 255), int(acc_g * 255), int(acc_b * 255),
    )

    return primary, auxiliary, accent
```

**6 种预设色的派生结果**（预期）：

| theme_color | 主色 | 辅助色（浅） | 强调色（互补） |
| --- | --- | --- | --- |
| `#2563eb` 蓝 | `#2563eb` | `#DBE6F7`（浅蓝灰） | `#ebb225`（金黄） |
| `#7c3aed` 紫 | `#7c3aed` | `#E5DCF5`（浅紫灰） | `#aed225`（黄绿） |
| `#16a34a` 绿 | `#16a34a` | `#D5EBDC`（浅绿灰） | `#d22563`（玫红） |
| `#dc2626` 红 | `#dc2626` | `#F5DCDC`（浅红灰） | `#26dcdc`（青） |
| `#ea580c` 橙 | `#ea580c` | `#F8E3D5`（浅橙灰） | `#0cea9e`（青绿） |
| `#475569` 灰 | `#475569` | `#E2E5EA`（浅灰） | `#694775 → 调整`（紫灰） |

> 注：灰色（`#475569`）的互补色仍为灰色系，强调色视觉区分度低。对灰色特殊处理：强调色固定使用 `#2563eb`（蓝色）作为对比。

**灰色特殊处理**：

```python
# 低饱和度色的互补色区分度不足，强调色无区分度
if s < 0.20:
    # 固定使用蓝色作为强调色
    # 阈值 0.20 覆盖 #475569（饱和度约 0.193）等灰蓝色
    accent = RGBColor(0x25, 0x63, 0xeb)
```

### 决策 3：三明治结构布局

**选择**：所有页面统一采用"深色标题栏 → 浅色内容区 → 深色页脚栏"三层结构。

**内容页三明治结构**：

```
┌─────────────────────────────────────────┐
│ ████████████████████████████████████████ │  ← 主色标题栏（高 1.0"）
│ ██ 页面标题（28pt 白色 Bold）          ██ │
│ ████████████████████████████████████ ────│  ← 标题栏底边（主色）
├──────────────────┬──────────────────────┤
│░░░░░░░░░░░░░░░░░│                      │  ← 辅助色浅色背景
│░ ● 要点 1（强调色）░│     [图表]            │
│░   说明文本...   ░│                      │  ← 白色/浅色内容区
│░ ● 要点 2（强调色）░│                      │
│░   说明文本...   ░│                      │
│░░░░░░░░░░░░░░░░░│                      │
├──────────────────┴──────────────────────┤
│ ████████████████████████████████████████ │  ← 主色页脚栏（高 0.5"）
│ ██ 项目名（12pt 白色）      第 N 页（白色）██ │
│ ████████████████████████████████████████ │
└─────────────────────────────────────────┘
```

**各页面的三明治实现**：

| 页面类型 | 标题栏 | 内容区 | 页脚栏 |
| --- | --- | --- | --- |
| 封面页 | 顶部主色色块（高 2.5"，SPEC 0024 已有） | 白色副标题区 | **新增**底部主色窄条（高 0.5"） |
| 内容页 | **新增**主色背景栏（高 1.0"）+ 白色标题 | 左栏辅助色背景 + 右栏白色 | **新增**主色背景栏（高 0.5"）+ 白色文字 |
| 图表页 | **新增**主色背景栏（高 1.0"）+ 白色标题 | 白色图表区 | **新增**主色背景栏（高 0.5"）+ 白色文字 |
| 总结页 | **新增**主色背景栏（高 1.0"）+ 白色标题 | 白色总结正文 | **新增**主色背景栏（高 0.5"）+ 白色文字 |

**尺寸参数**：

```python
# 三明治结构尺寸（英寸）
TITLE_BAR_HEIGHT = 1.0      # 内容页/图表页/总结页标题栏高度
FOOTER_BAR_HEIGHT = 0.5     # 所有页面页脚栏高度
FOOTER_BAR_TOP = SLIDE_HEIGHT - FOOTER_BAR_HEIGHT  # 7.0

# 内容区（标题栏和页脚栏之间）
CONTENT_AREA_TOP = TITLE_BAR_HEIGHT + 0.2   # 1.2
CONTENT_AREA_HEIGHT = FOOTER_BAR_TOP - CONTENT_AREA_TOP - 0.2  # 5.6
```

**理由**：
- 深色标题栏和页脚栏形成"面包片"，浅色内容区形成"夹心"
- 主色统一用于上下色块，视觉节奏一致
- 辅助色浅色背景只用于左栏，不铺满内容区（避免过度着色）
- 三明治结构是 McKinsey/BCG 咨询 PPT 的标准布局模式

### 决策 4：强调色应用范围

**选择**：强调色用于"需要视觉突出"的元素，不用于大面积背景。

| 元素 | SPEC 0024（主色） | SPEC 0025（强调色） |
| --- | --- | --- |
| 左栏圆点标记 | `theme_rgb` | **`accent_rgb`** |
| 左栏章节标题 | `theme_rgb` | **`accent_rgb`** |
| 封面副标题 | `theme_rgb` | 保持主色（封面无强调色） |
| 标题栏背景 | 无背景 | **主色**（不是强调色） |
| 页脚栏背景 | 无背景 | **主色**（不是强调色） |
| 分隔线 | `theme_rgb` | **辅助色**（更柔和） |

**理由**：
- 强调色用于小面积元素（圆点、标题文字），视觉突出但不喧宾夺主
- 主色用于大面积色块（标题栏、页脚栏），建立结构框架
- 辅助色用于背景衬托，不抢视觉焦点
- 三色各司其职，层次分明

### 决策 5：色彩对比度保障

**选择**：深色栏上用白色文字，浅色区上用深色文字，确保可读性。

| 背景 | 文字色 | 对比度保障 |
| --- | --- | --- |
| 主色标题栏（深） | 白色 `#FFFFFF` | 主色亮度 ≤ 60% 时白字可读 |
| 主色页脚栏（深） | 白色 `#FFFFFF` | 同上 |
| 辅助色背景（浅） | 深灰 `#333333` | 辅助色亮度 92%，深灰文字对比度 > 7:1 |
| 白色内容区 | 深灰 `#333333` | 对比度 > 12:1 |
| 强调色文字 | — | 强调色亮度 45%，在白色/浅色背景上可读 |

**主色亮度边界处理**：

```python
# 如果主色本身偏亮（亮度 > 0.60），标题栏文字改用深色
# 阈值 0.60 覆盖紫色 #7c3aed（L≈0.578），使 5 种预设深色统一用白字
if l > 0.60:
    title_text_color = RGBColor(0x33, 0x33, 0x33)  # 深灰
else:
    title_text_color = RGBColor(0xFF, 0xFF, 0xFF)  # 白色
```

**理由**：
- 6 种预设色中 5 种为深色（蓝/紫/绿/红/橙），亮度均 < 0.60，白字可读
- 紫色 `#7c3aed` 亮度约 57.8%，阈值 0.60 确保其使用白字（更符合 PPT 设计惯例）
- 灰色 `#475569` 亮度约 34.5%，白字可读
- 算法需处理用户可能传入的浅色（虽然预设色板限制，但渲染器需防御）

---

## 四、架构设计

### 4.1 Owner 边界（不变）

SPEC 0025 不改变现有 owner 边界，只重构 `PptRenderer` 内部方法：

| 层 | 文件 | 职责变化 |
| --- | --- | --- |
| 渲染器 | `server/app/infrastructure/renderers/ppt_renderer.py` | **重构色彩派生与标题/页脚渲染**（本切片核心） |
| 合同层 | `server/app/modules/outlines/contracts.py` | 不变 |
| Service 层 | `server/app/modules/outlines/service.py` | 不变 |
| API 适配层 | `server/app/api/routers/outlines.py` | 不变 |
| Worker | `server/worker/handlers.py` | 不变 |
| 前端 | `apps/web/src/` | 不变 |

### 4.2 新增布局常量

在 `ppt_renderer.py` 顶部新增三明治结构常量（与 SPEC 0024 常量并存）：

```python
# === SPEC 0025 三明治结构常量 ===

# 标题栏（深色背景栏）
TITLE_BAR_HEIGHT = 1.0           # 内容页/图表页/总结页标题栏高度
TITLE_BAR_TEXT_COLOR_LIGHT = RGBColor(0xFF, 0xFF, 0xFF)   # 深色背景上的白字
TITLE_BAR_TEXT_COLOR_DARK = RGBColor(0x33, 0x33, 0x33)    # 浅色背景上的深字

# 页脚栏（深色背景栏）
FOOTER_BAR_HEIGHT = 0.5          # 页脚栏高度
FOOTER_BAR_TOP = SLIDE_HEIGHT - FOOTER_BAR_HEIGHT  # 7.0

# 内容区（三明治夹心）
CONTENT_AREA_TOP = TITLE_BAR_HEIGHT + 0.2    # 1.2
CONTENT_AREA_BOTTOM = FOOTER_BAR_TOP - 0.2   # 6.8
CONTENT_AREA_HEIGHT = CONTENT_AREA_BOTTOM - CONTENT_AREA_TOP  # 5.6

# 辅助色背景
LEFT_COL_BG_TOP = CONTENT_AREA_TOP
LEFT_COL_BG_HEIGHT = CONTENT_AREA_HEIGHT

# 文字颜色
TEXT_COLOR_DARK = RGBColor(0x33, 0x33, 0x33)    # 深灰正文
TEXT_COLOR_MUTED = RGBColor(0x55, 0x55, 0x55)   # 中灰补充文本
```

### 4.3 三角色彩派生方法

新增 `PptRenderer` 私有方法：

```python
def _derive_color_palette(
    self, theme_rgb: RGBColor,
) -> tuple[RGBColor, RGBColor, RGBColor, RGBColor]:
    """从主题色派生三角色彩（SPEC 0025）。

    返回 (primary, auxiliary, accent, title_text_color)。
    - primary: 主色（= theme_rgb），用于标题栏/页脚栏背景
    - auxiliary: 辅助色（浅色），用于左栏背景衬托
    - accent: 强调色（互补色），用于圆点标记/章节标题
    - title_text_color: 标题栏文字色（白或深灰，取决于主色亮度）
    """
```

### 4.4 标题栏渲染重构

**SPEC 0024**（`_add_page_title`）：彩色文字 + 细分隔线
**SPEC 0025**（`_add_page_title`）：主色背景栏 + 白色文字

```python
def _add_page_title(
    self, slide, title: str, primary: RGBColor,
    title_text_color: RGBColor,
) -> None:
    """添加深色标题栏（主色背景 + 白色标题文字）。"""
    # 1. 主色背景栏（全幅）
    self._add_color_block(
        slide,
        Inches(0), Inches(0),
        Inches(SLIDE_WIDTH), Inches(TITLE_BAR_HEIGHT),
        primary,
    )
    # 2. 标题文字（白色或深灰，取决于主色亮度）
    title_tb = slide.shapes.add_textbox(
        Inches(MARGIN_LEFT), Inches(0.15),
        Inches(SLIDE_WIDTH - 2 * MARGIN_LEFT), Inches(0.7),
    )
    tf = title_tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    run = tf.paragraphs[0].add_run()
    run.text = title
    self._set_run_font(
        run, FONT_SIZE_PAGE_TITLE, title_text_color, bold=True,
    )
```

### 4.5 页脚栏渲染重构

**SPEC 0024**（`_add_footer`）：浅灰细线 + 灰色文字
**SPEC 0025**（`_add_footer`）：主色背景栏 + 白色文字

```python
def _add_footer(
    self, slide, project_name: str, page_num: int,
    total_pages: int, primary: RGBColor,
    title_text_color: RGBColor,
) -> None:
    """添加深色页脚栏（主色背景 + 白色项目名和页码）。"""
    # 1. 主色背景栏（全幅）
    self._add_color_block(
        slide,
        Inches(0), Inches(FOOTER_BAR_TOP),
        Inches(SLIDE_WIDTH), Inches(FOOTER_BAR_HEIGHT),
        primary,
    )
    # 2. 项目名（左，白色）
    left_tb = slide.shapes.add_textbox(
        Inches(MARGIN_LEFT), Inches(FOOTER_BAR_TOP + 0.1),
        Inches(6), Inches(0.3),
    )
    lr = left_tb.text_frame.paragraphs[0].add_run()
    lr.text = project_name
    self._set_run_font(lr, FONT_SIZE_CAPTION, title_text_color)

    # 3. 页码（右，白色）
    right_tb = slide.shapes.add_textbox(
        Inches(SLIDE_WIDTH - 3), Inches(FOOTER_BAR_TOP + 0.1),
        Inches(2.5), Inches(0.3),
    )
    rt = right_tb.text_frame
    rt.paragraphs[0].alignment = PP_ALIGN.RIGHT
    rr = rt.paragraphs[0].add_run()
    rr.text = f"第 {page_num} / {total_pages} 页"
    self._set_run_font(rr, FONT_SIZE_CAPTION, title_text_color)
```

### 4.6 左栏辅助色背景

内容页左栏添加辅助色浅色背景矩形：

```python
def _add_content_left_column(
    self, slide, sections: list[dict],
    accent: RGBColor, auxiliary: RGBColor,
) -> None:
    """添加左栏文本要点（辅助色背景 + 强调色圆点 + 章节标题）。"""
    # 1. 辅助色背景矩形
    self._add_color_block(
        slide,
        Inches(MARGIN_LEFT), Inches(CONTENT_AREA_TOP),
        Inches(CONTENT_LEFT_WIDTH), Inches(CONTENT_AREA_HEIGHT),
        auxiliary,
    )
    # 2. 文本要点（叠在背景上）
    tb = slide.shapes.add_textbox(
        Inches(MARGIN_LEFT + 0.1), Inches(CONTENT_AREA_TOP + 0.1),
        Inches(CONTENT_LEFT_WIDTH - 0.2), Inches(CONTENT_AREA_HEIGHT - 0.2),
    )
    tf = tb.text_frame
    tf.word_wrap = True

    for i, section in enumerate(sections[:5]):
        # 圆点标记 → 强调色
        # 章节标题 → 强调色
        # 说明文本 → 深灰
        ...
```

### 4.7 封面页三明治收口

封面页已有顶部主色色块（SPEC 0024），新增底部主色窄条：

```python
def _render_title_slide(
    self, prs, project_name, project_topic,
    primary: RGBColor, auxiliary: RGBColor,
    title_text_color: RGBColor,
) -> None:
    """渲染封面页：顶部主色块 + 白色标题 + 副标题 + 底部主色窄条。"""
    # 1. 顶部主色全幅色块（SPEC 0024 已有，保持）
    # 2. 主标题（色块内白色文字，36pt Bold）—— 保持
    # 3. 副标题（色块下方）—— 保持
    # 4. 底部主色窄条（SPEC 0025 新增，形成三明治下层面包）
    self._add_color_block(
        slide,
        Inches(0), Inches(FOOTER_BAR_TOP),
        Inches(SLIDE_WIDTH), Inches(FOOTER_BAR_HEIGHT),
        primary,
    )
```

### 4.8 render() 方法签名不变

`render()` 方法签名和 `PptConfig` 合同完全不变。内部变化：

```python
def render(self, ... config: dict | None = None) -> str:
    # SPEC 0024: 解析单一 theme_rgb
    # SPEC 0025: 派生三角色彩
    primary, auxiliary, accent, title_text_color = self._derive_color_palette(
        self._resolve_theme_color(theme_color)
    )
    # 后续渲染方法传入四色而非单一 theme_rgb
    ...
```

---

## 五、实现计划

### 步骤 1：三角色彩派生

- 新增 `_derive_color_palette` 方法（使用 `colorsys` 标准库）
- 新增灰色特殊处理（饱和度 < 0.15 时强调色固定蓝色）
- 新增主色亮度判断（决定标题栏文字色白/深灰）
- 单元测试：6 种预设色 + 默认色 + 灰色边界 + 无效色降级

### 步骤 2：三明治结构常量

- 新增 `TITLE_BAR_HEIGHT`、`FOOTER_BAR_HEIGHT`、`CONTENT_AREA_TOP` 等常量
- 调整 `CONTENT_TOP` 和 `CONTENT_HEIGHT`（SPEC 0024 常量）的引用指向新值

### 步骤 3：标题栏重构

- 重写 `_add_page_title`：主色背景栏 + 白色文字
- 适配所有调用方（内容页/图表页/总结页）

### 步骤 4：页脚栏重构

- 重写 `_add_footer`：主色背景栏 + 白色文字
- 适配所有调用方（内容页/图表页/总结页/封面页）

### 步骤 5：左栏辅助色背景 + 强调色要点

- 修改 `_add_content_left_column`：添加辅助色背景矩形 + 圆点/标题改用强调色
- 调整文本框位置（背景矩形上方留 0.1" 内边距）

### 步骤 6：封面页三明治收口

- 修改 `_render_title_slide`：新增底部主色窄条

### 步骤 7：render() 方法接线

- `render()` 入口调用 `_derive_color_palette` 获取四色
- 各渲染方法参数从 `theme_rgb` 改为 `primary/auxiliary/accent/title_text_color`
- 保持 `render()` 签名不变

### 步骤 8：测试更新

- 更新 `test_ppt_config.py`：主题色验证适配三色系统（检查主色出现在标题栏/页脚栏背景）
- 新增三角色彩派生测试：6 种预设色派生结果验证 + 灰色特殊处理 + 无效色降级
- 新增三明治结构测试：标题栏背景色块存在 + 页脚栏背景色块存在 + 左栏辅助色背景存在
- 回归测试：`config=None` + `PptConfig` 各字段仍生效 + SPEC 0024 布局参数不变

### 步骤 9：验收 + 文档回写 + git 收口

- 运行完整验收命令
- 生成真实 PPT 文件视觉验证
- 更新 `acceptance.md`、`implementation-plan.md`、`README.md`
- 新增决策记录
- git commit

---

## 六、验收标准

### 6.1 三角色彩派生验收

| # | 验收点 | 期望结果 |
| --- | --- | --- |
| D1 | `theme_color="#2563eb"` 派生主色 | `#2563eb`（原值） |
| D2 | `theme_color="#2563eb"` 派生辅助色 | 亮度 ≥ 0.85 的浅蓝色 |
| D3 | `theme_color="#2563eb"` 派生强调色 | 互补色相（金黄系） |
| D4 | `theme_color="#475569"`（灰）强调色 | 固定 `#2563eb`（蓝色，特殊处理） |
| D5 | `theme_color=None` 派生 | 使用默认 `#333333` 派生三色 |
| D6 | `theme_color="#invalid"` 降级 | 记录 warning，降级到默认三色 |

### 6.2 三明治结构验收

| # | 验收点 | 期望结果 |
| --- | --- | --- |
| S1 | 内容页标题栏 | 存在主色背景矩形（全幅，高 1.0"） |
| S2 | 内容页标题文字 | 白色（或深灰，取决于主色亮度） |
| S3 | 内容页页脚栏 | 存在主色背景矩形（全幅，高 0.5"） |
| S4 | 内容页页脚文字 | 白色项目名 + 白色页码 |
| S5 | 封面页底部 | 存在主色窄条（全幅，高 0.5"） |
| S6 | 图表页标题栏 | 存在主色背景矩形 |
| S7 | 总结页标题栏 | 存在主色背景矩形 |

### 6.3 辅助色与强调色验收

| # | 验收点 | 期望结果 |
| --- | --- | --- |
| A1 | 左栏背景 | 存在辅助色浅色矩形 |
| A2 | 左栏圆点标记 | 强调色（非主色） |
| A3 | 左栏章节标题 | 强调色（非主色） |
| A4 | 左栏说明文本 | 深灰 `#333333` |
| A5 | 右栏图表区 | 无背景色块（保持白色） |

### 6.4 向后兼容验收

| # | 验收点 | 期望结果 |
| --- | --- | --- |
| B1 | `config=None` 渲染 | 成功生成 PPT，使用默认三色 + 三明治布局 |
| B2 | `config={"theme_color":"#2563eb"}` | 主色为蓝色，辅助色浅蓝，强调色金黄 |
| B3 | `config={"target_slide_count":6}` | 页数控制仍生效（SPEC 0011 逻辑不变） |
| B4 | `config={"include_charts":false}` | 不生成图表页（SPEC 0011 逻辑不变） |
| B5 | `render()` 方法签名 | 与 SPEC 0024 完全一致，调用方零改动 |
| B6 | SPEC 0024 布局参数 | 画布 16:9、双栏 40%/60%、五级字号不变 |

### 6.5 整体验收命令

```text
server/.venv/Scripts/python.exe -m pytest server/tests/test_ppt_config.py server/tests/test_renderers.py -v
server/.venv/Scripts/python.exe -m pytest server/tests/ -k "ppt or outline or renderer" -v
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
```

### 6.6 真实文件视觉验收

- 生成 6 种预设色的 PPT 文件，逐一打开确认三色协调性和三明治结构
- 截图保存至 `dev-docs/e2e-screenshots/spec0025-*.png`
- 验收点：标题栏深色背景 + 页脚栏深色背景 + 左栏浅色背景 + 强调色圆点 + 文字可读性

---

## 七、风险与降级

### 7.1 互补色派生不协调

**风险**：某些主题色的互补色可能在视觉上不协调（如红色的互补色青色可能过于刺眼）。

**缓解**：
- 强调色饱和度上限 70%，避免过于鲜艳
- 强调色只用于小面积元素（圆点、标题文字），不用于大面积背景
- 6 种预设色的派生结果在真实文件验收中逐一确认
- 若某色派生不理想，可在 `_derive_color_palette` 中为该色增加特殊映射

### 7.2 主色亮度边界

**风险**：如果主色偏亮，标题栏白字不可读。

**缓解**：
- 6 种预设色均为深色（亮度 < 0.55），白字可读
- 渲染器防御性处理：亮度 > 0.55 时自动切换深色文字
- 新增测试覆盖亮度边界

### 7.3 辅助色背景与图表重叠

**风险**：左栏辅助色背景矩形可能被右栏图表覆盖，或文字框超出背景范围。

**缓解**：
- 辅助色背景矩形尺寸严格限定在左栏范围内（`CONTENT_LEFT_WIDTH`）
- 文本框在背景矩形内留 0.1" 内边距
- 右栏图表起始位置（`CONTENT_RIGHT_LEFT=6.1"`）在左栏背景之外
- 新增测试验证背景矩形尺寸和位置

### 7.4 测试回归

**风险**：SPEC 0024 的测试检查 `theme_color` 出现在 PPT 元素中，SPEC 0025 改变了色彩应用位置。

**缓解**：
- 主色仍出现在标题栏/页脚栏背景，`_slide_has_color` 检查仍能找到主题色
- 更新测试断言：从"检查主题色出现在任意元素"扩展为"检查主色出现在标题栏背景"
- 保持 `test_render_theme_color_*_applied` 系列测试通过（主色仍在 slide 上）

### 7.5 性能

**风险**：新增背景矩形和色彩派生增加渲染时间。

**缓解**：
- 色彩派生是纯计算（`colorsys` 转换），耗时 < 1ms
- 每页新增 2-3 个 shape（标题栏 + 页脚栏 + 左栏背景），shape 总量增幅 < 20%
- PPT 生成是低频操作，性能不敏感
- 新增测试验证生成耗时无显著增加

---

## 八、依赖与配置

### 8.1 依赖

- **无新增依赖**
- 使用 Python 标准库 `colorsys`（RGB ↔ HLS 色彩空间转换）
- 继续使用 `python-pptx>=1.0.2`（`MSO_SHAPE.RECTANGLE` 已在 SPEC 0024 使用）

### 8.2 配置

- **无新增环境变量**
- **无新增数据库迁移**（色彩派生是渲染器内部逻辑，不落库）
- **不改变 PptConfig 合同**
- **不改变 PPT_THEME_COLORS 预设色板**

---

## 九、不属于本切片的事项

- 用户自定义三色配置（`auxiliary_color`/`accent_color` 字段，推迟到后续 SPEC）
- 色盲友好配色（Okabe-Ito / ColorBrewer 色板，推迟到后续 SPEC）
- 图表洞察性标题（标题陈述结论而非描述数据，推迟到后续 SPEC）
- 数据可视化专用色板（推迟到后续 SPEC）
- 生产防护规则（文本溢出检测、图表最小尺寸、色彩对比度校验，推迟到后续 SPEC）
- 布局模式扩展（McKinsey 70 种布局模式库，推迟到后续 SPEC）
- PPT 动画与过渡效果（推迟到 V3.0）
- Word 渲染器色彩改进（独立切片）
- PPT 母版上传与自定义模板（推迟到后续）
- 在线 PPT 预览（推迟到后续）
- 自定义字体嵌入（推迟到后续优化）
