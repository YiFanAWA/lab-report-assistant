# 调研报告：Python 构建 PPT 的高级视觉效果方法

**日期：** 2026-07-31
**调研目的：** 为 SPEC 0026（PPT 视觉效果增强）提供输入依据
**调研来源：** GitHub、PyPI、python-pptx 官方文档、Aspose.Slides 文档、第三方 skill 仓库
**状态：** 调研完成，作为 SPEC 0026 起草依据

## 一、调研背景

SPEC 0024（16:9 画布 + 双栏布局 + 五级字号）和 SPEC 0025（三角色彩系统 + 深浅对比三明治结构）已收口。项目负责人反馈"生成的还是有些不尽人意"，要求去 GitHub 搜集 Python 构建 PPT 相关的方法并尝试。

本次调研聚焦于：在不更换 `python-pptx` 基础库、不破坏现有 owner 边界和 `PptConfig` 合同的前提下，能够落地的高级视觉增强方法。

## 二、核心发现：python-pptx 原生支持的视觉特性

### 2.1 渐变填充（Gradient Fill）— 原生支持

**来源：** python-pptx 官方文档 [dml-gradient](https://python-pptx.readthedocs.io/en/stable/dev/analysis/dml-gradient.html)

python-pptx 自带渐变填充 API，无需 oxml 操作即可使用：

```python
fill = shape.fill
fill.gradient()                          # 应用默认两停止点线性渐变（底到顶 90°）
fill.gradient_angle = 45                 # 修改渐变角度
gradient_stops = fill.gradient_stops     # 访问停止点序列
gradient_stop = gradient_stops[0]
gradient_stop.color.rgb = RGBColor(...)  # 修改停止点颜色
gradient_stop.position = 0.5             # 修改停止点位置（0.0-1.0）
gradient_stops[1].remove()               # 删除停止点（至少保留 2 个）
```

**可落地场景：**
- 封面页顶部色块改为「主色 → 强调色」渐变，提升封面视觉冲击
- 标题栏背景改为「主色 → 主色暗化」渐变，增加层次感
- 页脚栏背景改为「主色暗化 → 主色」渐变，与标题栏呼应

**约束：** 初版仅支持线性路径（linear path），不支持径向（radial）渐变。对当前需求足够。

### 2.2 圆角矩形（Rounded Rectangle）— 原生支持

**来源：** python-pptx 官方文档 [autoshapes](https://python-pptx.readthedocs.io/en/latest/user/autoshapes.html)

```python
from pptx.enum.shapes import MSO_SHAPE
shape = shapes.add_shape(
    MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height,
)
# 通过 adjustments 调整圆角半径（0.0-1.0，相对短边比例）
shape.adjustments[0] = 0.1   # 小圆角
```

**可落地场景：**
- 左栏背景衬托改为圆角矩形，柔化三明治结构的硬边缘
- 图表容器边框改为圆角矩形
- 要点卡片改为圆角矩形，提升现代感

### 2.3 形状边框（Line Format）— 原生支持

```python
line = shape.line
line.color.rgb = RGBColor(...)
line.width = Pt(1.5)
# 虚线样式
from pptx.enum.dml import MSO_LINE_DASH_STYLE
line.dash_style = MSO_LINE_DASH_STYLE.DASH
```

**可落地场景：** 为图片容器、表格添加细边框，提升精致度。

## 三、需要 oxml 操作的高级特性

### 3.1 阴影效果（Outer Shadow）

**现状：** python-pptx 官方 API 未直接暴露 `effect_format`，需要通过 oxml 操作 `<a:effectLst>` 节点。

**参考实现（来自 Aspose.Slides 文档与 power-pptx 源码）：**

```python
from pptx.oxml.ns import qn

def add_outer_shadow(shape, blur_radius_pt=12, direction_deg=315, distance_pt=8):
    """为形状添加外阴影效果（通过 oxml 操作）。"""
    spPr = shape._element.spPr
    # 移除已有 effectLst
    for tag in ('a:effectLst',):
        existing = spPr.find(qn(tag))
        if existing is not None:
            spPr.remove(existing)
    effectLst = spPr.makeelement(qn('a:effectLst'), {})
    outerShdw = effectLst.makeelement(qn('a:outerShdw'), {
        'blurRad': str(int(blur_radius_pt * 12700)),     # Pt → EMU
        'dist': str(int(distance_pt * 12700)),
        'dir': str(int(direction_deg * 60000)),           # 度 → 1/60000 度
        'rotWithShape': '0',
    })
    clr = outerShdw.makeelement(qn('a:srgbClr'), {'val': '000000'})
    alpha = clr.makeelement(qn('a:alpha'), {'val': '40000'})  # 40% 不透明度
    clr.append(alpha)
    outerShdw.append(clr)
    effectLst.append(outerShdw)
    spPr.append(effectLst)
```

**可落地场景：**
- 封面主色块添加柔和外阴影，增加立体感
- 图表容器添加阴影，使图表与背景分离
- 要点卡片添加阴影，模拟「浮起」效果

**风险：** oxml 操作需谨慎，错误的 XML 结构会导致文件损坏。必须配套验证测试。

### 3.2 线条渐变与图案填充

python-pptx 支持但 API 较弱，需要 oxml 补充。本次 SPEC 0026 暂不纳入，作为后续方向。

## 四、相关 Python PPT 库对比

### 4.1 power-pptx（python-pptx 的 fork）

**来源：** [power-pptx 2.10.0](https://pypi.org/project/power-pptx/)（2026-07-13 发布）

**核心特性：**
- `TextFrame.fit_text(...)`：用 Pillow 字体度量，保存前把合适字号写入 XML
- `text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE`：PowerPoint 渲染时自动缩小
- `slide.lint()`：检测溢出和越界
- `slide.auto_fix()` / `slide.tidy()`：自动修复

**评估：** 解决了文本溢出痛点，但属于另一个 fork，引入会改变依赖基线。**SPEC 0026 不纳入**，作为后续债务记录。当前可在 ppt_renderer 内部实现简化版文本溢出检测（基于字符数和字号估算）。

### 4.2 EasyPPTX

**来源：** [EasyPPTX 0.4.0](https://pypi.org/project/EasyPPTX/0.4.0/)

**核心特性：** 百分比定位、网格布局、自动对齐、暗色主题。

**评估：** 属于 python-pptx 的封装层。本项目已有 ppt_renderer 作为唯一 owner，引入会破坏 owner 边界。**不纳入**。

### 4.3 Office-PowerPoint-MCP-Server

**来源：** [mcpcn-office-powerpoint-mcp-server 2.1.2](https://pypi.org/project/mcpcn-office-powerpoint-mcp-server/)（2026-02-05）

**核心特性：**
- 4 种专业配色方案（Modern Blue / Corporate Gray / Elegant Green / Warm Red）
- 25 个内置幻灯片模板
- 9 种图片效果（阴影、反射、发光、斜面等）
- 渐变背景

**评估：** 这是 MCP 服务器，不是库。其设计思路（预设配色方案、模板系统、图片效果预设）可借鉴，但不直接引入。本项目已有三角色彩派生系统（SPEC 0025），无需引入外部配色方案。

### 4.4 autoppt

**来源：** [autoppt 0.6.0](https://pypi.org/project/autoppt/)（2026-05-18）

**核心特性：** SlidePlan / SlideSpec / DeckSpec 中间模型、布局感知渲染、模板支持。

**评估：** 其「布局规划先于渲染」的思路与本项目一致（outline → 渲染）。其比较布局（comparison slide）、引用布局（quote slide）等富布局类型可借鉴。

### 4.5 Aspose.Slides（商业库）

**来源：** [Aspose.Slides for Python](https://docs.aspose.com/slides/python-net/)

**核心特性：** WordArt、阴影、发光、3D 斜面、渐变、图案填充，API 完整。

**评估：** 商业库，需要许可证。**不引入**。但其 API 设计和视觉效果实现思路可作为 oxml 操作的参考。

## 五、专业 PPT 设计原则（来自 GitHub skill 仓库）

### 5.1 60-30-10 色彩比例

**来源：** feedmob-presentations skill、Anthropic pptx skill

- 60% 主色（背景、大色块）
- 30% 辅助色（次级元素、分隔）
- 10% 强调色（重点、高亮）

**当前状态：** SPEC 0025 已实现三角色彩系统，但比例分配未显式约束。SPEC 0026 可补充比例指导。

### 5.2 6×6 规则

**来源：** feedmob-presentations skill

每页不超过 6 个要点，每个要点不超过 6 个词（中文可理解为不超过 12 个字）。

**当前状态：** SPEC 0024 已放宽文本截断到 500 字符，但未约束要点数量。SPEC 0026 可补充要点数量上限。

### 5.3 视觉层次与网格定位

**来源：** pptx-official skill、McKinsey PPT Design Framework

- 三分法则（Rule of Thirds）
- Z 型阅读路径
- 留白原则
- 网格对齐

**当前状态：** SPEC 0024 已实现双栏布局和五级字号，符合视觉层次原则。

## 六、可落地方案汇总（按优先级）

| 优先级 | 方案 | 实现方式 | 预期收益 | 风险 |
| --- | --- | --- | --- | --- |
| P0 | 渐变填充 | python-pptx 原生 `fill.gradient()` | 封面、标题栏、页脚栏视觉升级 | 低（原生 API） |
| P0 | 圆角矩形 | `MSO_SHAPE.ROUNDED_RECTANGLE` | 柔化硬边缘，提升现代感 | 低（原生 API） |
| P1 | 外阴影效果 | oxml 操作 `<a:effectLst>` | 图表、卡片立体感 | 中（XML 结构需验证） |
| P1 | 形状边框 | `shape.line` 原生 API | 图片容器精致度 | 低 |
| P2 | 文本溢出检测 | 简化版字符数估算 | 避免文字超出文本框 | 低（非精确方案） |
| P2 | 要点数量上限 | 业务逻辑约束 | 符合 6×6 规则 | 低 |

## 七、约束与边界

本次调研遵循以下约束：

1. **不引入新依赖**：仅使用 `python-pptx` + 标准库（`colorsys`、`lxml` 已随 python-pptx 安装）
2. **不改变 owner 边界**：所有改动在 `server/app/infrastructure/renderers/ppt_renderer.py` 内
3. **不改变 `PptConfig` 合同**：不新增配置字段（如需配置，留到后续 SPEC）
4. **不破坏 SPEC 0024/0025 成果**：三明治结构、三角色彩、五级字号、双栏布局保持
5. **回归零容忍**：现有 362 个测试必须全部通过

## 八、结论与建议

基于调研结果，建议起草 **SPEC 0026：PPT 视觉效果增强（渐变 + 圆角 + 阴影 + 边框）**，聚焦 P0 和 P1 方案：

1. **渐变填充**：封面顶部色块、标题栏背景、页脚栏背景改为渐变
2. **圆角矩形**：左栏背景、图表容器、要点卡片改为圆角矩形
3. **外阴影效果**：图表容器、要点卡片添加柔和阴影（oxml 操作）
4. **形状边框**：图片容器添加细边框

P2 方案（文本溢出检测、要点数量上限）作为可选增强，视实现复杂度决定是否纳入。

**下一步：** 起草 SPEC 0026 文档，提交项目负责人确认后进入实现。

## 参考来源

- [python-pptx Gradient Fill 文档](https://python-pptx.readthedocs.io/en/stable/dev/analysis/dml-gradient.html)
- [python-pptx AutoShapes 文档](https://python-pptx.readthedocs.io/en/latest/user/autoshapes.html)
- [power-pptx 2.10.0](https://pypi.org/project/power-pptx/)
- [EasyPPTX 0.4.0](https://pypi.org/project/EasyPPTX/0.4.0/)
- [Office-PowerPoint-MCP-Server 2.1.2](https://pypi.org/project/mcpcn-office-powerpoint-mcp-server/)
- [autoppt 0.6.0](https://pypi.org/project/autoppt/)
- [Aspose.Slides Shape Formatting](https://docs.aspose.com/slides/python-net/shape-formatting/)
- [Aspose.Slides WordArt Effects](https://docs.aspose.com/slides/python-net/wordart/)
- [Anthropic pptx skill（autumnsgrove）](https://raw.githubusercontent.com/aiskillstore/marketplace/main/skills/autumnsgrove/pptx/SKILL.md)
- [feedmob-presentations skill](https://www.skillmd.ai/pt/skills/feedmob-presentations/)
- [pptx-official skill](https://www.mdskills.ai/ko/skills/pptx-official)
