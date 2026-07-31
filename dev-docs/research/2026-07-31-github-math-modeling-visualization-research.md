# 调研报告：GitHub 数学建模数据可视化项目借鉴

**日期：** 2026-07-31
**调研目的：** 为 SPEC 0027（图表美化与布局增强）提供输入依据
**调研来源：** GitHub、PyPI、python-pptx 官方文档、第三方 skill 仓库、技术博客
**状态：** 调研完成，作为 SPEC 0027 起草依据

## 一、调研背景

项目负责人反馈 PPT 生成效果"还是有些不尽人意"，要求：
1. 去 GitHub 搜集数学建模相关数据构图布局的项目进行借鉴
2. 可以引入别的可直接使用的依赖和组件，但使用前需询问选择
3. 重点参考科研绘图、数学建模、数据可视化方向的开源项目

本次调研覆盖三个方向：
- **A. 图表生成层**：matplotlib/seaborn 科研样式库
- **B. PPT 渲染层**：python-pptx 封装层与布局工具
- **C. 数学建模可视化**：数学要素、3D 可视化等专项模板

## 二、核心发现：图表生成层（A 方向）

### 2.1 SciencePlots ⭐ 推荐

**来源：** [garrettj403/SciencePlots](https://github.com/garrettj403/SciencePlots)（GitHub）
**PyPI：** `pip install SciencePlots`
**特点：**
- 专为科研人员设计的 Matplotlib 样式库
- 内置 Nature/IEEE/Science 等顶级期刊样式
- 色盲友好配色（bright/high-vis/vibrant/muted）
- 多语言字体支持（含 `cjk-sc-font` 简体中文）
- Paul Tol 离散彩虹色系（23 种）
- 使用 `no-latex` 样式可避免 LaTeX 依赖

**示例：**
```python
import scienceplots
plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])
```

**适用性评估：** ✅ 完全匹配本 SPEC 需求
- 期刊级图表样式
- 中文支持
- 无 LaTeX 依赖（使用 `no-latex`）
- 与现有 matplotlib 配置兼容

### 2.2 Seaborn ⭐ 推荐

**来源：** [mwaskom/seaborn](https://github.com/mwaskom/seaborn)（GitHub）
**PyPI：** `pip install seaborn`
**特点：**
- 统计数据可视化库
- 提供小提琴图、热图、回归图、 pairplot 等高级统计图表
- 默认样式更美观（whitegrid/darkgrid/white/dark/ticks）
- 与 pandas DataFrame 深度集成
- 支持 hue 分组、自动图例

**示例：**
```python
import seaborn as sns
sns.set_theme(style="whitegrid", palette="bright")
sns.histplot(data=df, x='age', kde=True)
sns.heatmap(df.corr(), annot=True, cmap='coolwarm')
```

**适用性评估：** ✅ 完全匹配本 SPEC 需求
- 统计图表更美观
- 与 SciencePlots 样式互补
- API 更简洁

### 2.3 matplotlib_for_papers

**来源：** [matplotlib_for_papers](https://github.com/jbmouret/matplotlib_for_papers)
**特点：**
- 科研图表项目，手动 rcParams 配置范式
- 包含箱线图、中位数计算、颜色优化等示例
- 使用 palettable 配色方案

**适用性评估：** ⚠️ 不引入，作为参考
- 已被 SciencePlots 一键样式覆盖
- 手动 rcParams 配置可借鉴，但不必引入

### 2.4 pyplotutil

**来源：** [hrshtst/pyplotutil](https://github.com/hrshtst/pyplotutil)
**PyPI：** `pip install pyplotutil`
**特点：**
- 学术绘图工具，封装 SciencePlots
- 支持 CSV/Parquet/JSON/Excel 加载
- 时间序列分组绘图
- 方向箭头、时间跨度高亮

**适用性评估：** ⚠️ 不引入
- 功能与 SciencePlots 重叠
- 偏时间序列场景，不适合本 SPEC 通用数据分析

### 2.5 rwthplots

**来源：** [RWTH-IAEW/rwthplots](https://github.com/RWTH-IAEW/rwthplots)
**PyPI：** `pip install rwthplots`
**特点：**
- RWTH Aachen 大学企业设计
- 38 色 colormap
- IEEE/Nature/Elsevier/Springer/APS/ACM 期刊预设
- 含 `rwth-pptx` 专用 PowerPoint 样式
- CVD 色盲模拟工具

**适用性评估：** ❌ 不引入
- 偏欧式学术风，与现有主题色系统冲突
- 企业设计约束过强

### 2.6 matplotlabs

**来源：** [lvvittor/matplotlabs](https://github.com/lvvittor/matplotlabs)
**PyPI：** `pip install matplotlabs`
**特点：**
- 科研出版样式
- Arial/Helvetica 字体、trimmed spines、constrained layout
- 8 色 qualitative cycle

**适用性评估：** ❌ 不引入
- 与 SciencePlots 功能重叠
- Stars 数量少（1），不够成熟

### 2.7 prettyplotlib

**来源：** [prettyplotlib](https://github.com/olgabot/prettyplotlib)
**特点：**
- publication-ready 散点图
- ColorBrewer Set2 调色板
- 空心标记 + 半透明效果

**适用性评估：** ❌ 不引入
- 已停止维护
- 功能被 Seaborn 覆盖

### 2.8 mplcyberpunk / Matplotx

**来源：** [mplcyberpunk](https://github.com/dhaitz/mplcyberpunk)、[Matplotx](https://github.com/nownolf/matplotx)
**特点：**
- 赛博朋克霓虹风格、深色主题

**适用性评估：** ❌ 不引入
- 不符合教学实验报告严肃风格

## 三、核心发现：PPT 渲染层（B 方向）

### 3.1 EasyPPTX ⭐ 推荐

**来源：** [Ameyanagi/EasyPPTX](https://github.com/Ameyanagi/EasyPPTX)（GitHub）
**PyPI：** `pip install easypptx`
**特点：**
- python-pptx 封装层
- 百分比定位（`x="10%"`, `y="20%"`）
- Grid 布局系统（N×M 自动对齐）
- 默认 16:9 画布
- 暗色主题支持
- TOML 模板文件支持
- 为 AI/LLM 优化

**示例：**
```python
from easypptx import Presentation
pres = Presentation()
slide = pres.add_slide(title="Demo")
slide.add_text(text="Hello", x="10%", y="20%", width="80%", height="10%")
```

**适用性评估：** ✅ 部分采纳
- 百分比定位思路有价值
- Grid 布局系统可借鉴
- **但不全面替换**现有 `PptRenderer`（会破坏 SPEC 0024/0025/0026 成果）
- 仅引入辅助方法（`_pct_to_emu` + `_GridHelper`）

### 3.2 python-pptx 官方 API

**来源：** [python-pptx 文档](https://python-pptx.readthedocs.io/)
**特点：**
- 原生支持图表（XL_CHART_TYPE）
- 原生支持形状、图片、表格
- 渐变填充（SPEC 0026 已用）
- 圆角矩形（SPEC 0026 已用）

**适用性评估：** ✅ 继续使用
- SPEC 0024/0025/0026 已基于原生 API
- EasyPPTX 底层也是 python-pptx

### 3.3 scientific-slides skill

**来源：** [scientific-slides SKILL.md](https://raw.githubusercontent.com/jimmc414/Kosmos/master/kosmos-reference/kosmos-claude-scientific-writer/.claude/skills/scientific-slides/SKILL.md)
**特点：**
- 科研演讲幻灯片设计指南
- 视觉优先（60-70% 视觉 + 30-40% 文本）
- 大字号（24-28pt 正文，36-44pt 标题）
- 高对比度（4.5:1 最低，7:1 推荐）
- 期刊级色彩方案
- 故事驱动结构

**适用性评估：** ✅ 借鉴设计原则
- 视觉层次、留白、色彩比例原则可借鉴
- 本 SPEC 已部分实现（SPEC 0024 五级字号、SPEC 0025 三角色彩）

### 3.4 pptx skill (aiskillstore)

**来源：** [pptx SKILL.md](https://raw.githubusercontent.com/aiskillstore/marketplace/main/skills/autumnsgrove/pptx/SKILL.md)
**特点：**
- python-pptx 全面使用指南
- 包含图表、表格、图片、SmartArt 工作流
- 业务演示、图表添加、图片处理、表格创建

**适用性评估：** ✅ 借鉴工作流
- 图表添加工作流可借鉴
- 已通过 SPEC 0024/0025/0026 落地

## 四、核心发现：数学建模可视化（C 方向）

### 4.1 《数学要素》Book3_Elements-of-Mathematics

**来源：** [Book3_Elements-of-Mathematics](https://github.com/bo/Book3_Elements-of-Mathematics)
**特点：**
- 19 个即用型数学可视化模板
- 3D 曲面图、等高线联动
- 公式渲染与数据联动
- 适合数学建模场景

**示例：**
```python
# 3D曲面 + 等高线联动
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
X = np.arange(-5, 5, 0.25)
Y = np.arange(-5, 5, 0.25)
X, Y = np.meshgrid(X, Y)
Z = np.sin(np.sqrt(X**2 + Y**2))
fig = plt.figure()
ax = fig.add_subplot(projection='3d')
ax.plot_surface(X, Y, Z, cmap=cm.coolwarm)
plt.contour(X, Y, Z, zdir='z', offset=-1, cmap=cm.coolwarm)
```

**适用性评估：** ⚠️ 不纳入本 SPEC，留作后续
- 3D 曲面/等高线需特定数据形态
- 本 SPEC 聚焦 2D 统计图表美化
- 留作后续 SPEC（如数学建模专项支持）

### 4.2 AI-Scientist 数据可视化库

**来源：** [AI-Scientist](https://github.com/SakanaAI/AI-Scientist)
**特点：**
- 10 种科研图表自动生成工具
- 小提琴图、热图、散点图回归、柱状图
- seaborn + matplotlib 组合

**适用性评估：** ✅ 借鉴图表类型
- 小提琴图、热图、回归图纳入本 SPEC 新增图表类型
- seaborn API 使用方式可借鉴

### 4.3 scientific-visualization skill

**来源：** [scientific-visualization SKILL.md](https://raw.githubusercontent.com/NeverSight/skills_feed/main/data/skills-md/ovachiever/droid-tings/scientific-visualization/SKILL.md)
**特点：**
- 期刊级多面板图表
- 误差线、显著性标记、色盲安全调色板
- Okabe-Ito 色盲友好配色
- PDF/EPS/TIFF 多格式导出
- Nature/Science/Cell/PLOS 期刊规范

**适用性评估：** ✅ 借鉴色盲友好配色
- Okabe-Ito 色盲友好配色可借鉴
- 多面板布局原则可借鉴
- 已通过 SciencePlots `bright` 样式部分实现

### 4.4 mpl-interactions

**来源：** [mpl-interactions](https://github.com/ianhi/mpl-interactions)
**特点：**
- 交互式 Matplotlib 图表
- 滑块、控件动态控制

**适用性评估：** ❌ 不引入
- 交互式不适合 PPT 静态嵌入

## 五、设计原则借鉴汇总

从以上调研中提炼的设计原则，已融入 SPEC 0027：

| 原则 | 来源 | SPEC 0027 落地方式 |
| --- | --- | --- |
| 期刊级图表样式 | SciencePlots | `plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])` |
| 色盲友好配色 | SciencePlots `bright`、scientific-visualization Okabe-Ito | 使用 `bright` 样式 |
| 统计图表 API | Seaborn、AI-Scientist | `sns.histplot/boxplot/countplot/scatterplot/heatmap/violinplot/regplot` |
| 中文支持 | SciencePlots `cjk-sc-font` | 与现有 `Microsoft YaHei` 配置互补 |
| 百分比定位 | EasyPPTX | `_pct_to_emu` 辅助方法 |
| Grid 布局系统 | EasyPPTX | `_GridHelper` 内部类 |
| 视觉优先 | scientific-slides skill | 已在 SPEC 0024 双栏布局落地 |
| 高对比度 | scientific-slides skill | 已在 SPEC 0025 三角色彩落地 |
| 大字号 | scientific-slides skill | 已在 SPEC 0024 五级字号落地 |
| 故事驱动 | scientific-slides skill | 已在 SPEC 0024 章节结构落地 |

## 六、依赖选择决策

### 6.1 项目负责人确认选择

通过 AskUserQuestion 询问，项目负责人确认：

| 决策点 | 选择 | 理由 |
| --- | --- | --- |
| 图表生成层依赖 | SciencePlots + Seaborn 组合 | 期刊级样式 + 统计图表 API，科研绘图主流方案 |
| PPT 渲染层方案 | 引入 EasyPPTX 封装层 | 百分比定位 + Grid 布局，简化坐标计算 |

### 6.2 不引入的依赖及原因

| 依赖 | 不引入原因 |
| --- | --- |
| rwthplots | 偏欧式学术风，与现有主题色系统冲突 |
| matplotlabs | 与 SciencePlots 功能重叠，不够成熟 |
| prettyplotlib | 已停止维护，功能被 Seaborn 覆盖 |
| pyplotutil | 偏时间序列场景，功能与 SciencePlots 重叠 |
| mplcyberpunk | 赛博朋克风格不符合教学实验报告 |
| Matplotx | 深色主题，与现有三明治结构冲突 |
| Plotly | 交互式不适合 PPT 静态嵌入 |
| mpl-interactions | 交互式不适合 PPT 静态嵌入 |

## 七、结论与建议

### 7.1 调研结论

1. **SciencePlots + Seaborn 组合**是科研绘图的主流方案，可显著提升图表美观度
2. **EasyPPTX** 的百分比定位和 Grid 布局思路可简化 PPT 坐标计算，但不适合全面替换
3. **《数学要素》** 的 3D 可视化模板适合数学建模专项，留作后续 SPEC
4. **scientific-slides skill** 的设计原则已在 SPEC 0024/0025/0026 部分落地

### 7.2 SPEC 0027 建议

基于调研结果，建议 SPEC 0027：
1. **图表层**：引入 SciencePlots + Seaborn，升级 `_HEADER` 和 `_build_chart_code`
2. **PPT 层**：引入 EasyPPTX 作为辅助方法（`_pct_to_emu` + `_GridHelper`），不全面重写
3. **沙箱层**：更新 import 白名单，允许 `scienceplots`、`seaborn`
4. **不引入**：rwthplots/matplotlabs/prettyplotlib/Plotly/mplcyberpunk 等不匹配依赖
5. **LaTeX**：使用 `no-latex` 样式，沙箱不安装 LaTeX

### 7.3 后续方向

本 SPEC 完成后，可考虑的后续方向：
- 3D 曲面图/等高线联动（数学建模专项，来自《数学要素》）
- 误差线/显著性标记（来自 scientific-visualization skill）
- 多面板布局（来自 scientific-visualization skill）
- 期刊预设适配（Nature/IEEE/Science）

这些方向需新 SPEC 确认后实施。
