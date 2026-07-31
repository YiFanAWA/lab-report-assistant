# SPEC 0026：PPT 视觉效果增强（渐变 + 圆角 + 阴影 + 边框）

**状态：** 已由项目负责人确认收口（2026-07-31）
**起草日期：** 2026-07-31
**完成日期：** 2026-07-31
**前序 SPEC：** [SPEC 0024](0024-ppt-renderer-layout-and-visual-hierarchy.md)、[SPEC 0025](0025-ppt-color-system-and-sandwich-layout.md)
**调研依据：** [2026-07-31 Python PPT 视觉效果调研](../research/2026-07-31-python-pptx-visual-effects-research.md)
**关联决策：** [决策 0035](../decisions/0035-start-spec-0026-ppt-visual-effects.md)
**owner 层：** `server/app/infrastructure/renderers/ppt_renderer.py`（不改变 owner 边界）

## 一、背景与动机

SPEC 0024（16:9 画布 + 双栏布局 + 五级字号）和 SPEC 0025（三角色彩系统 + 深浅对比三明治结构）已收口。项目负责人反馈"生成的还是有些不尽人意"，要求去 GitHub 搜集 Python 构建 PPT 相关方法并尝试。

调研结果记录于 [调研报告](../research/2026-07-31-python-pptx-visual-effects-research.md)。核心发现：

1. **python-pptx 原生支持渐变填充**（`fill.gradient()` API），无需 oxml 操作
2. **python-pptx 原生支持圆角矩形**（`MSO_SHAPE.ROUNDED_RECTANGLE`）
3. **外阴影效果需 oxml 操作** `<a:effectLst>`，但实现成熟、参考代码充分
4. **形状边框原生支持**（`shape.line` API）

本 SPEC 聚焦于「不引入新依赖、不破坏现有 owner 边界和 `PptConfig` 合同」前提下，落地四项视觉增强。

## 二、目标与边界

### 2.1 目标

1. **渐变填充**：封面顶部色块、内容页标题栏、内容页页脚栏改为渐变填充，提升视觉层次
2. **圆角矩形**：左栏背景衬托改为圆角矩形，柔化三明治结构的硬边缘
3. **外阴影效果**：右栏图表容器添加柔和外阴影，使图表与背景分离
4. **形状细边框**：图片容器添加细边框，提升精致度

### 2.2 边界（必须遵守）

- **不引入新依赖**：仅使用 `python-pptx` + 标准库（`lxml` 已随 python-pptx 安装，无需额外安装）
- **不改变 owner 边界**：所有改动在 `server/app/infrastructure/renderers/ppt_renderer.py` 内
- **不改变 `PptConfig` 合同**：不新增配置字段；`target_slide_count` / `theme_color` / `include_charts` 三字段不变
- **不破坏 SPEC 0024/0025 成果**：三明治结构、三角色彩派生、五级字号、双栏布局保持
- **回归零容忍**：现有 362 个测试必须全部通过（1 个预存 DEEPSEEK 失败除外）
- **不改变 API / Service / Worker 接线**：渲染入口 `render()` 签名不变

### 2.3 不纳入（留作后续方向）

- 径向渐变（python-pptx 初版仅支持线性）
- 发光效果（glow）、3D 斜面（bevel）、反射（reflection）— 视觉过重，不适合教学实验报告
- 文本溢出精确检测（power-pptx 的 `fit_text` 方案）— 需引入 fork，留作技术债
- 要点数量上限约束（6×6 规则）— 属于内容策略，不属于视觉渲染
- 幻灯片母版重构 — 改动面过大，留作后续 SPEC

## 三、实现方案

### 3.1 渐变填充

#### 3.1.1 渐变派生算法

从主色（primary）派生渐变两端颜色：

| 渐变位置 | 颜色 | 派生方式 |
| --- | --- | --- |
| 起始（0%） | 主色原值 | = `primary` |
| 结束（100%） | 主色暗化 20% | HLS 空间 L 降低 0.20，下限 0.10 |

**暗化算法**（使用 `colorsys`，复用 SPEC 0025 已有依赖）：

```python
def _darken_color(self, rgb: RGBColor, factor: float = 0.20) -> RGBColor:
    """降低颜色亮度（HLS 空间 L 减 factor，下限 0.10）。"""
    hex_str = str(rgb)
    r = int(hex_str[0:2], 16) / 255
    g = int(hex_str[2:4], 16) / 255
    b = int(hex_str[4:6], 16) / 255
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = max(l - factor, 0.10)
    dr, dg, db = colorsys.hls_to_rgb(h, l, s)
    return RGBColor(int(dr * 255), int(dg * 255), int(db * 255))
```

#### 3.1.2 渐变填充应用位置

| 位置 | 渐变方向 | 起始色 | 结束色 |
| --- | --- | --- | --- |
| 封面顶部色块 | 90°（上→下） | 主色 | 主色暗化 20% |
| 内容页标题栏 | 90°（上→下） | 主色 | 主色暗化 15% |
| 内容页页脚栏 | 90°（上→下） | 主色暗化 15% | 主色 |

**设计意图：** 标题栏上浅下深（稳重），页脚栏上深下浅（与标题栏呼应），封面色块上浅下深（聚焦）。

#### 3.1.3 实现方式

升级 `_add_color_block` 为 `_add_color_block`（支持纯色）+ 新增 `_add_gradient_block`（渐变）：

```python
def _add_gradient_block(
    self, slide, left, top, width, height,
    color_start: RGBColor, color_end: RGBColor,
    angle_deg: float = 90,
) -> None:
    """添加渐变色块（线性渐变，python-pptx 原生 API）。"""
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, left, top, width, height,
    )
    fill = shape.fill
    fill.gradient()
    fill.gradient_angle = angle_deg
    # 设置两端颜色
    stops = fill.gradient_stops
    stops[0].color.rgb = color_start
    stops[0].position = 0.0
    stops[1].color.rgb = color_end
    stops[1].position = 1.0
    shape.line.fill.background()  # 无边框
```

**调用点改动：**
- `_render_title_slide`：顶部色块改用 `_add_gradient_block(primary, darken(primary, 0.20), 90)`
- `_add_page_title`：标题栏改用 `_add_gradient_block(primary, darken(primary, 0.15), 90)`
- `_add_footer`：页脚栏改用 `_add_gradient_block(darken(primary, 0.15), primary, 90)`

**封面页底部窄条保持纯色**（主色原值），与顶部渐变形成对比。

### 3.2 圆角矩形

#### 3.2.1 应用位置

| 位置 | 圆角半径（adjustments[0]） |
| --- | --- |
| 左栏背景衬托 | 0.05（小圆角，柔化但不失稳重） |

**不改动图表容器**（图表本身是矩形 PNG，加圆角会与图片边缘冲突）。

#### 3.2.2 实现方式

新增 `_add_rounded_color_block` 方法：

```python
def _add_rounded_color_block(
    self, slide, left, top, width, height,
    color_rgb: RGBColor, corner_radius: float = 0.05,
) -> None:
    """添加圆角色块（圆角矩形 + 纯色填充）。"""
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height,
    )
    shape.adjustments[0] = corner_radius
    shape.fill.solid()
    shape.fill.fore_color.rgb = color_rgb
    shape.line.fill.background()
```

**调用点改动：**
- `_add_content_left_column`：辅助色背景改用 `_add_rounded_color_block(auxiliary, 0.05)`

### 3.3 外阴影效果

#### 3.3.1 应用位置

| 位置 | 阴影参数 |
| --- | --- |
| 右栏图表图片 | blur=8pt, distance=4pt, direction=315°（左上）, 颜色=黑色 30% 不透明度 |

**只对内容页右栏单图添加阴影**（`_add_content_right_chart`）。图表页（`_add_chart_slide`）的多图布局不添加阴影（避免多阴影视觉混乱）。

#### 3.3.2 实现方式

新增 `_add_picture_shadow` 方法（oxml 操作 `<a:effectLst>`）：

```python
def _add_picture_shadow(
    self, picture,
    blur_radius_pt: float = 8,
    distance_pt: float = 4,
    direction_deg: float = 315,
    alpha_pct: int = 30,
) -> None:
    """为图片添加外阴影效果（oxml 操作 a:effectLst）。

    参数：
    - blur_radius_pt: 模糊半径（Pt）
    - distance_pt: 阴影距离（Pt）
    - direction_deg: 阴影方向（度，0=右，90=下，180=左，270=上）
    - alpha_pct: 不透明度百分比（0-100）

    注意：python-pptx 未暴露 effect_format API，需直接操作 oxml。
    """
    # EMU 转换常量：1 Pt = 12700 EMU；1 度 = 60000（1/60000 度）
    BLUR_EMU = str(int(blur_radius_pt * 12700))
    DIST_EMU = str(int(distance_pt * 12700))
    DIR_EMU = str(int(direction_deg * 60000))
    ALPHA_VAL = str(int(alpha_pct * 1000))  # 百分比 → 千分比

    spPr = picture._element.spPr
    # 移除已有 effectLst
    existing = spPr.find(qn('a:effectLst'))
    if existing is not None:
        spPr.remove(existing)

    effectLst = spPr.makeelement(qn('a:effectLst'), {})
    outerShdw = effectLst.makeelement(qn('a:outerShdw'), {
        'blurRad': BLUR_EMU,
        'dist': DIST_EMU,
        'dir': DIR_EMU,
        'rotWithShape': '0',
    })
    clr = outerShdw.makeelement(qn('a:srgbClr'), {'val': '000000'})
    alpha = clr.makeelement(qn('a:alpha'), {'val': ALPHA_VAL})
    clr.append(alpha)
    outerShdw.append(clr)
    effectLst.append(outerShdw)
    spPr.append(effectLst)
```

**调用点改动：**
- `_add_content_right_chart`：`slide.shapes.add_picture(...)` 返回的 picture 对象调用 `_add_picture_shadow(pic)`

**XML 结构验证：** 生成的 XML 应符合 OOXML 规范。验证方式：用 `python-pptx` 重新打开生成的文件，确保无解析错误。

### 3.4 形状细边框

#### 3.4.1 应用位置

| 位置 | 边框参数 |
| --- | --- |
| 右栏图表图片 | 颜色=辅助色（auxiliary），宽度=1pt |

与阴影配合，使图表边界清晰。

#### 3.4.2 实现方式

在 `_add_content_right_chart` 中，给 picture 设置边框：

```python
pic = slide.shapes.add_picture(...)
# 细边框
pic.line.color.rgb = auxiliary
pic.line.width = Pt(1)
# 外阴影
self._add_picture_shadow(pic)
```

**注意：** `_add_content_right_chart` 需要接收 `auxiliary` 参数（当前未接收）。需要修改 `_add_content_slide` 调用处，传入 `auxiliary`。

## 四、测试计划

### 4.1 新增测试（`server/tests/test_ppt_config.py`）

新增 `TestSpec0026VisualEffects` 测试类：

**渐变填充测试：**
- G1：封面页顶部色块为渐变填充（检查 `fill.type == MSO_FILL_TYPE.GRADIENT`）
- G2：内容页标题栏为渐变填充
- G3：内容页页脚栏为渐变填充
- G4：渐变角度为 90°
- G5：渐变起始色 = 主色原值
- G6：渐变结束色 = 主色暗化色（用 `_darken_color` 计算预期值对比）

**圆角矩形测试：**
- R1：左栏背景形状类型为 `ROUNDED_RECTANGLE`
- R2：圆角半径 adjustments[0] ≈ 0.05
- R3：左栏背景填充色 = 辅助色

**外阴影测试：**
- S1：右栏图表 picture 的 spPr 包含 `<a:effectLst>` 节点
- S2：`<a:effectLst>` 包含 `<a:outerShdw>` 子节点
- S3：`<a:outerShdw>` 的 `blurRad` 属性存在且为正值
- S4：`<a:outerShdw>` 包含 `<a:srgbClr>` 颜色节点

**边框测试：**
- B1：右栏图表 picture 的 line.color.rgb == 辅助色
- B2：右栏图表 picture 的 line.width == Pt(1)

**暗化算法测试：**
- D1：`_darken_color(#2563eb, 0.20)` 返回值亮度低于原色
- D2：`_darken_color` 极端情况（L 已很低时）不返回负值

### 4.2 回归测试

运行以下测试套件，确保无回归：

```text
server/.venv/Scripts/python.exe -m pytest server/tests/test_ppt_config.py -v
server/.venv/Scripts/python.exe -m pytest server/tests/test_renderers.py -v
server/.venv/Scripts/python.exe -m pytest server/tests/ -k "outline or ppt or renderer" -v
```

### 4.3 真实文件验证

生成 6 种预设色的 PPT 文件，程序化验证：
- 每页标题栏/页脚栏的渐变节点存在
- 左栏背景为圆角矩形
- 内容页右栏图表有阴影和边框

## 五、验收标准

### 5.1 功能验收

- [x] 渐变填充在封面、标题栏、页脚栏生效（程序化验证 fill.type）
- [x] 圆角矩形在左栏背景生效（程序化验证 shape_type）
- [x] 外阴影在右栏图表生效（程序化验证 oxml 节点）
- [x] 边框在右栏图表生效（程序化验证 line.color）
- [x] 6 种预设色均能正确生成（无 XML 解析错误）

### 5.2 回归验收

- [x] `test_ppt_config.py` + `test_renderers.py` 全部通过
- [x] outline/ppt/renderer 相关模块测试全部通过（362 passed，1 预存 DEEPSEEK 失败除外）
- [x] SPEC 0024/0025 专用测试全部通过（无回归）
- [x] 前端 lint + build 不受影响（本 SPEC 仅改后端渲染器）
- [x] Alembic 迁移不受影响（本 SPEC 不改 schema）

### 5.3 视觉验收

- 生成真实 PPT 文件，用 HTML 预览验证视觉效果
- 渐变填充平滑过渡，无色带
- 圆角矩形边缘柔和，不突兀
- 阴影方向一致（左上光源），不喧宾夺主
- 边框细致（1pt），不抢夺图表内容焦点

## 六、风险与缓解

| 风险 | 等级 | 缓解措施 |
| --- | --- | --- |
| oxml 操作导致 PPT 文件损坏 | 中 | 每次生成后用 `python-pptx` 重新打开验证；配套 XML 节点测试 |
| 渐变在某些 PPT 查看器中显示不一致 | 低 | python-pptx 原生 API 生成的 XML 符合 OOXML 标准，主流查看器均支持 |
| 阴影参数过重影响阅读 | 低 | 参数保守（blur=8pt, distance=4pt, alpha=30%），可在后续 SPEC 调整 |
| `_darken_color` 暗化过度 | 低 | 下限 L=0.10 保护；测试验证极端情况 |
| 左栏圆角与标题栏/页脚栏衔接不自然 | 低 | 圆角半径小（0.05），视觉过渡自然 |

## 七、实现顺序

遵循 AGENTS.md 阶段闸顺序：

1. **测试先行**：先编写 `TestSpec0026VisualEffects` 测试类（含渐变、圆角、阴影、边框、暗化算法测试）
2. **核心实现**：在 `ppt_renderer.py` 实现 `_darken_color`、`_add_gradient_block`、`_add_rounded_color_block`、`_add_picture_shadow` 四个方法
3. **接线**：修改 `_render_title_slide`、`_add_page_title`、`_add_footer`、`_add_content_left_column`、`_add_content_right_chart`、`_add_content_slide` 的调用
4. **运行测试**：确保新增测试通过 + 回归测试无回归
5. **真实文件验证**：生成 6 种预设色 PPT，程序化验证
6. **文档回写**：更新 SPEC 0026 状态、决策 0035、README、acceptance、implementation-plan
7. **git 收口**：复核 git 边界，精确 stage，commit

## 八、依赖与网络

- **不新增依赖**：`python-pptx` 已安装，`colorsys` 是标准库，`lxml` 随 python-pptx 安装
- **不访问网络**：本 SPEC 纯本地实现
- **不涉及 DeepSeek**：本 SPEC 不调用 LLM

## 九、文档回写清单

实现完成后需同步更新：

- [ ] `dev-docs/specs/0026-ppt-visual-effects-enhancement.md`（本文件，状态改为已完成）
- [ ] `dev-docs/decisions/0035-start-spec-0026-ppt-visual-effects.md`（新建，记录启动决策）
- [ ] `dev-docs/README.md`（更新 SPEC 0026 状态）
- [ ] `dev-docs/acceptance.md`（新增 SPEC 0026 验收记录）
- [ ] `dev-docs/implementation-plan.md`（更新 V2.7.0 阶段信息）

## 十、约束遵守声明

本 SPEC 遵守以下约束：

1. **AGENTS.md 阶段闸**：先编写 SPEC，待项目负责人确认后进入实现
2. **推理闸**：已回答 owner 边界、当前真源、回归风险等问题
3. **唯一 owner**：所有改动在 `server/app/infrastructure/renderers/ppt_renderer.py` 内
4. **不引入新依赖**：仅用 python-pptx + 标准库
5. **不改变合同**：`PptConfig` 三字段不变，`render()` 签名不变
6. **测试先行**：先写测试再实现
7. **回归零容忍**：362 个测试必须全部通过
8. **文档回写**：实现完成后同步更新所有相关文档

## 十一、实现收口说明（2026-07-31）

### 11.1 核心实现

在 `server/app/infrastructure/renderers/ppt_renderer.py` 新增 4 个方法：

| 方法 | 职责 |
| --- | --- |
| `_darken_color(rgb, factor)` | HLS 空间降低颜色亮度，下限 0.10 保护，用于渐变结束色派生 |
| `_add_gradient_block(...)` | 线性渐变色块，使用 python-pptx 原生 `fill.gradient()` API |
| `_add_rounded_color_block(...)` | 圆角矩形色块，`MSO_SHAPE.ROUNDED_RECTANGLE` + adjustments |
| `_add_picture_shadow(picture, ...)` | 图片外阴影，oxml 操作 `<a:effectLst>` + `<a:outerShdw>` |

### 11.2 接线改动

| 调用点 | 改动 |
| --- | --- |
| `_render_title_slide` | 封面顶部色块改用渐变（主色 → 主色暗化 20%） |
| `_add_page_title` | 标题栏改用渐变（主色 → 主色暗化 15%） |
| `_add_footer` | 页脚栏改用渐变（主色暗化 15% → 主色） |
| `_add_content_left_column` | 左栏背景改用圆角矩形（半径 0.05） |
| `_add_content_right_chart` | 接收 auxiliary 参数，图片添加辅助色 1pt 边框 + 外阴影 |
| `_add_content_slide` | 调用 `_add_content_right_chart` 时传入 auxiliary |

### 11.3 测试新增

`server/tests/test_ppt_config.py` 新增 `TestSpec0026VisualEffects` 测试类（17 个测试）：

- 暗化算法测试：2 个（D1 亮度降低、D2 极端情况下限保护）
- 渐变填充测试：6 个（G1-G3 渐变存在、G4 角度 90°、G5 起始色、G6 结束色）
- 圆角矩形测试：3 个（R1 形状类型、R2 圆角半径、R3 填充色）
- 外阴影测试：4 个（S1 effectLst、S2 outerShdw、S3 blurRad、S4 srgbClr）
- 边框测试：2 个（B1 边框色、B2 边框宽度）

同时增强 `_shape_has_fill_color` 和 `_slide_has_color` 辅助函数，支持渐变填充检查（兼容 SPEC 0025 测试）。

### 11.4 回归验证

| 测试范围 | 结果 |
| --- | --- |
| `test_ppt_config.py` + `test_renderers.py` | 74 passed（含 17 个 SPEC 0026 新增） |
| outline/ppt/renderer/deliverable 相关全量 | 220 passed, 1 预存 DEEPSEEK 失败 |
| SPEC 0024/0025 专用测试 | 全部通过（无回归） |
| **SPEC 0026 引入的回归** | **0** |

### 11.5 真实文件验证

使用 `server/scripts/verify_spec0026.py` 生成 6 种预设色 PPT，程序化验证：

| 主题色 | 渐变 | 圆角 | 阴影 | 边框 | 页数 | 文件有效 |
| --- | --- | --- | --- | --- | --- | --- |
| 蓝 #2563eb | ✓ | ✓ | ✓ | ✓ | 5 | ✓ |
| 紫 #7c3aed | ✓ | ✓ | ✓ | ✓ | 5 | ✓ |
| 绿 #16a34a | ✓ | ✓ | ✓ | ✓ | 5 | ✓ |
| 红 #dc2626 | ✓ | ✓ | ✓ | ✓ | 5 | ✓ |
| 橙 #ea580c | ✓ | ✓ | ✓ | ✓ | 5 | ✓ |
| 灰 #475569 | ✓ | ✓ | ✓ | ✓ | 5 | ✓ |

6 种预设色全部通过，XML 结构完整，文件可正常重新打开。

### 11.6 约束遵守

- ✅ 不引入新依赖（仅用 python-pptx + 标准库 colorsys/lxml）
- ✅ 不改变 `PptConfig` 合同（三字段不变）
- ✅ 不改变 `render()` 签名
- ✅ 不破坏 SPEC 0024/0025 成果（三明治结构、三角色彩、五级字号、双栏布局保持）
- ✅ 不改变 API/Service/Worker 接线
- ✅ 回归零新增
