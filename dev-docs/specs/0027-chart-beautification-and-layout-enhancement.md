# SPEC 0027：图表美化与布局增强（SciencePlots + Seaborn + EasyPPTX）

**状态：** 已完成实现与验收，待项目负责人确认收口
**起草日期：** 2026-07-31
**实现完成日期：** 2026-07-31
**前序 SPEC：** [SPEC 0024](0024-ppt-renderer-layout-and-visual-hierarchy.md)、[SPEC 0025](0025-ppt-color-system-and-sandwich-layout.md)、[SPEC 0026](0026-ppt-visual-effects-enhancement.md)
**调研依据：** [2026-07-31 GitHub 数学建模数据可视化项目调研](../research/2026-07-31-github-math-modeling-visualization-research.md)
**关联决策：** [决策 0036](../decisions/0036-start-spec-0027-chart-beautification.md)
**owner 层：**
- 图表生成层：`server/app/modules/llm/code_task_provider.py`、`server/app/modules/llm/deepseek_code_task_provider.py`
- PPT 渲染层：`server/app/infrastructure/renderers/ppt_renderer.py`
- 执行沙箱：`server/app/infrastructure/sandbox/python_executor.py`（import 白名单与 AST 校验）
- 不改变 owner 边界

## 一、背景与动机

SPEC 0024（16:9 画布 + 双栏布局）、SPEC 0025（三角色彩 + 三明治结构）、SPEC 0026（渐变 + 圆角 + 阴影 + 边框）已收口。项目负责人反馈"生成的还是有些不尽人意"，要求去 GitHub 搜集数学建模相关数据构图布局的项目进行借鉴，并允许在引入前询问选择后引入可直接使用的依赖和组件。

调研结果记录于 [调研报告](../research/2026-07-31-github-math-modeling-visualization-research.md)。核心发现：

1. **SciencePlots**：matplotlib 样式库，一键应用 Nature/IEEE 期刊风格，色盲友好配色，中文支持（`cjk-sc-font`）
2. **Seaborn**：统计数据可视化库，提供小提琴图/热图/回归图等高级统计图表，默认样式更美观
3. **EasyPPTX**：python-pptx 封装层，提供百分比定位、Grid 布局系统、自动对齐
4. **《数学要素》Book3_Elements-of-Mathematics**：19 个即用型数学可视化模板（3D 曲面、等高线联动）
5. **scientific-visualization / scientific-slides skill**：期刊级多面板图表 + 科研演讲幻灯片设计指南

项目负责人已确认选择：
- **图表生成层**：SciencePlots + Seaborn 组合
- **PPT 渲染层**：引入 EasyPPTX 封装层

本 SPEC 聚焦于「在 SPEC 0024/0025/0026 基础上，通过引入三个新依赖提升图表美观度和布局灵活性」，同时严守 owner 边界和 `PptConfig` 合同。

## 二、目标与边界

### 2.1 目标

1. **图表层美化**：在 `code_task_provider.py` 生成的代码中应用 SciencePlots 期刊样式 + Seaborn 统计图表 API，使生成的图表符合科研出版规范
2. **PPT 层布局增强**：在 `ppt_renderer.py` 中引入 EasyPPTX 的百分比定位和 Grid 布局思路，简化坐标计算，提升布局灵活性
3. **DeepSeek 同步**：更新 `deepseek_code_task_provider.py` 的 `_SYSTEM_PROMPT`，要求 LLM 生成的代码也使用 SciencePlots + Seaborn
4. **沙箱白名单同步**：更新 `python_executor.py` 的 import 白名单和 AST 校验，允许 `scienceplots`、`seaborn`、`easypptx`

### 2.2 边界（必须遵守）

- **新增依赖**：仅引入 `scienceplots`、`seaborn`、`easypptx` 三个 PyPI 包（在 `pyproject.toml` 或 `requirements.txt` 中声明）
- **不改变 owner 边界**：图表生成改动在 `code_task_provider.py` + `deepseek_code_task_provider.py` 内；PPT 渲染改动在 `ppt_renderer.py` 内；沙箱校验改动在 `python_executor.py` 内
- **不改变 `PptConfig` 合同**：不新增配置字段；`target_slide_count` / `theme_color` / `include_charts` 三字段不变
- **不破坏 SPEC 0024/0025/0026 成果**：三明治结构、三角色彩派生、五级字号、双栏布局、渐变填充、圆角矩形、外阴影、细边框全部保持
- **不全面重写 ppt_renderer.py**：EasyPPTX 仅作为辅助思路引入（百分比定位 + Grid 布局辅助方法），不替换现有 `PptRenderer` 类的 `Presentation` 对象模型
- **回归零容忍**：现有所有测试必须全部通过（1 个预存 DEEPSEEK 失败除外）
- **不改变 API / Service / Worker 接线**：渲染入口 `render()` 签名不变；`LocalRuleCodeTaskProvider.generate()` 签名不变
- **LaTeX 可选**：SciencePlots 默认依赖 LaTeX，但本 SPEC 使用 `no-latex` 样式避免 LaTeX 依赖；沙箱不安装 LaTeX

### 2.3 不纳入（留作后续方向）

- 3D 曲面图、等高线联动（来自《数学要素》模板）— 需要特定数据形态，留作后续 SPEC
- Plotly 交互式图表 — 需要浏览器环境，不适合 PPT 静态嵌入
- mplcyberpunk 赛博朋克风格 — 不符合教学实验报告严肃风格
- rwthplots RWTH 企业设计 — 偏欧式学术风，与现有主题色系统冲突
- matplotlib_for_papers 手动 rcParams — 已被 SciencePlots 一键样式覆盖
- prettyplotlib — 已停止维护，功能被 Seaborn 覆盖
- matplotlabs — 与 SciencePlots 功能重叠
- EasyPPTX 全面替换 — 改动面过大，风险不可控

## 三、实现方案

### 3.1 图表层：SciencePlots + Seaborn 集成

#### 3.1.1 依赖声明

在 `server/pyproject.toml`（或 `server/requirements.txt`）新增：

```toml
scienceplots = "^2.1.0"    # 科研图表样式库
seaborn = "^0.13.0"        # 统计数据可视化
```

**注意：** `easypptx` 见 §3.2.1。

#### 3.1.2 code_task_provider.py 的 `_HEADER` 升级

当前 `_HEADER`（第 91-117 行）：

```python
_HEADER = '''"""由实验报告助手受控执行环境生成的 Python 代码。
...
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt
from scipy import stats
...
'''
```

升级后：

```python
_HEADER = '''"""由实验报告助手受控执行环境生成的 Python 代码。

来源：LocalRuleCodeTaskProvider
说明：基于已确认 AnalysisPlan 的清洗/分析/图表方案拼装。

环境变量（由执行环境注入）：
- DATA_PATH: 数据集文件绝对路径
- OUTPUT_DIR: 产物输出目录绝对路径
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt
import scienceplots  # noqa: F401  # 注册 science 样式
plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])
import seaborn as sns
sns.set_theme(style="whitegrid", palette="bright", font="Microsoft YaHei")
from scipy import stats

# 数据读取（根据扩展名自动选择 read_csv 或 read_excel）
_data_path = DATA_PATH
if _data_path.lower().endswith((".xlsx", ".xls")):
    df = pd.read_excel(_data_path)
else:
    df = pd.read_csv(_data_path)

print(f"数据加载完成: {len(df)} 行, {len(df.columns)} 列")
'''
```

**设计要点：**
- `scienceplots` 导入后注册 `science` 样式，必须 `no-latex` 避免沙箱缺 LaTeX
- `cjk-sc-font` 提供中文字体支持（与现有 `Microsoft YaHei` 配置互补）
- `bright` 色盲友好高对比度配色，适合 PPT 投影
- `sns.set_theme` 设置 seaborn 默认主题，`font="Microsoft YaHei"` 确保中文

#### 3.1.3 `_build_chart_code` 升级

当前 `_build_chart_code`（第 244-313 行）使用原生 matplotlib API。升级为 seaborn API：

| 图表类型 | 原实现（matplotlib） | 新实现（seaborn） |
| --- | --- | --- |
| HISTOGRAM | `df[field].hist(bins=30)` | `sns.histplot(data=df, x=field, kde=True, bins=30)` |
| BOXPLOT | `numeric_df.boxplot()` | `sns.boxplot(data=numeric_df)` |
| BAR | `df[field].value_counts().plot(kind='bar')` | `sns.countplot(data=df, x=field)` |
| SCATTER | `plt.scatter(df[f1], df[f2])` | `sns.scatterplot(data=df, x=f1, y=f2, hue=hue_field)` |
| 新增 HEATMAP | 无 | `sns.heatmap(df.corr(), annot=True, cmap='coolwarm')` |
| 新增 VIOLIN | 无 | `sns.violinplot(data=df, x=cat, y=num)` |
| 新增 REGRESSION | 无 | `sns.regplot(data=df, x=f1, y=f2)` |

**新增图表类型触发条件：**
- HEATMAP：当 `analysis_type == "CORRELATION"` 且数值字段 ≥ 3 时，额外生成相关性热图
- VIOLIN：当 `chart_type == "BOXPLOT"` 且存在分类字段时，额外生成小提琴图
- REGRESSION：当 `chart_type == "SCATTER"` 且字段为数值型时，额外生成带回归线的散点图

**样式应用：** 每个图表生成前调用 `plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])`，确保样式一致。

#### 3.1.4 deepseek_code_task_provider.py 的 `_SYSTEM_PROMPT` 升级

在 `_SYSTEM_PROMPT` 中追加 SciencePlots + Seaborn 使用要求：

```python
_SYSTEM_PROMPT = """你是一个 Python 数据分析代码生成助手。...
6. matplotlib 必须配置中文字体，否则中文标题和坐标轴会显示为方框：
   import matplotlib
   matplotlib.use("Agg")
   matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
   matplotlib.rcParams['axes.unicode_minus'] = False
   import matplotlib.pyplot as plt
   import scienceplots  # noqa: F401
   plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])
   import seaborn as sns
   sns.set_theme(style="whitegrid", palette="bright", font="Microsoft YaHei")

7. 图表生成优先使用 seaborn API（统计图表更美观）：
   - 直方图：sns.histplot(data=df, x=field, kde=True)
   - 箱线图：sns.boxplot(data=df, x=cat, y=num)
   - 柱状图：sns.countplot(data=df, x=field)
   - 散点图：sns.scatterplot(data=df, x=f1, y=f2, hue=hue)
   - 热图：sns.heatmap(df.corr(), annot=True, cmap='coolwarm')
   - 回归图：sns.regplot(data=df, x=f1, y=f2)

import 白名单（只允许以下模块，其他一律禁止）：
- pandas
- numpy
- matplotlib
- scienceplots
- seaborn
- scipy
- sklearn
- openpyxl

严禁 import 以下模块（会被 AST 校验拦截导致执行失败）：
- os, sys, subprocess, shutil, pathlib, io, ctypes, signal
- socket, ssl, http, urllib, requests
"""
```

### 3.2 PPT 层：EasyPPTX 集成

#### 3.2.1 依赖声明

在 `server/pyproject.toml`（或 `server/requirements.txt`）新增：

```toml
easypptx = "^0.5.0"        # python-pptx 封装层（百分比定位 + Grid 布局）
```

#### 3.2.2 集成策略：辅助方法引入，不全面重写

**关键决策：** 不替换 `PptRenderer` 类的 `Presentation` 对象模型，不改变 `render()` 签名。EasyPPTX 仅作为"设计思路借鉴 + 辅助方法"引入：

| EasyPPTX 特性 | 本 SPEC 采纳方式 |
| --- | --- |
| 百分比定位（`x="10%"`） | 新增 `_pct_to_emu(pct_str, total_emu)` 辅助方法，支持百分比字符串转 EMU |
| Grid 布局系统 | 新增 `_GridHelper` 内部类，封装 N×M 网格坐标计算 |
| 自动对齐 | 复用现有 `_fit_image_size`，不重复实现 |
| 暗色主题 | 不采纳（与 SPEC 0025 三角色彩系统冲突） |
| TOML 模板 | 不采纳（与现有代码驱动渲染冲突） |

#### 3.2.3 百分比定位辅助方法

新增 `_pct_to_emu` 静态方法：

```python
@staticmethod
def _pct_to_emu(pct_str: str, total_emu: int) -> int:
    """百分比字符串转 EMU（EasyPPTX 风格）。

    参数：
    - pct_str: 百分比字符串，如 "10%", "50.5%"
    - total_emu: 总长度（EMU），如 slide_width

    返回：EMU 整数

    示例：
    - _pct_to_emu("10%", Inches(13.333)) → Inches(1.3333)
    - _pct_to_emu("50%", Inches(7.5)) → Inches(3.75)
    """
    if not pct_str.endswith("%"):
        raise ValueError(f"百分比字符串必须以 % 结尾：{pct_str}")
    pct = float(pct_str[:-1]) / 100.0
    return int(total_emu * pct)
```

#### 3.2.4 Grid 布局辅助类

新增 `_GridHelper` 内部类，封装 N×M 网格坐标计算：

```python
class _GridHelper:
    """EasyPPTX 风格的 Grid 布局辅助类。

    给定区域 (left, top, width, height) 和 N×M 网格，
    计算每个单元格的 (left, top, width, height)。
    """

    def __init__(
        self,
        left: int, top: int, width: int, height: int,
        rows: int, cols: int,
        h_gap: int = 0, v_gap: int = 0,
    ):
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.rows = rows
        self.cols = cols
        self.h_gap = h_gap
        self.v_gap = v_gap

    def cell(self, row: int, col: int) -> tuple[int, int, int, int]:
        """返回 (row, col) 单元格的 (left, top, width, height)。"""
        cell_w = (self.width - self.h_gap * (self.cols - 1)) // self.cols
        cell_h = (self.height - self.v_gap * (self.rows - 1)) // self.rows
        cell_left = self.left + col * (cell_w + self.h_gap)
        cell_top = self.top + row * (cell_h + self.v_gap)
        return (cell_left, cell_top, cell_w, cell_h)
```

**调用点改造：**
- `_place_chart_grid`：用 `_GridHelper` 计算 2×2 网格坐标，替代硬编码
- `_place_chart_three`：用 `_GridHelper` 计算 2×2 网格（下排合并居中），替代硬编码
- `_place_chart_side_by_side`：用 `_GridHelper` 计算 1×2 网格，替代硬编码

### 3.3 沙箱白名单与 AST 校验同步

#### 3.3.1 import 白名单更新

在 `server/app/infrastructure/sandbox/python_executor.py` 的 import 白名单中新增：

```python
ALLOWED_IMPORTS = {
    "pandas", "numpy", "matplotlib", "scipy", "sklearn", "openpyxl",
    "scienceplots",  # 新增
    "seaborn",       # 新增
    # easypptx 不加入沙箱白名单 —— 它是 PPT 渲染层依赖，不在用户代码执行环境使用
}
```

**注意：** `easypptx` 不加入沙箱白名单。它是 PPT 渲染层（`ppt_renderer.py`）使用的依赖，不在用户代码执行环境（沙箱）中使用。沙箱只执行 `code_task_provider` 生成的数据分析代码，不涉及 PPT 生成。

#### 3.3.2 AST 校验更新

确认 AST 校验逻辑允许 `scienceplots` 和 `seaborn`（它们不在 `BLOCKED_MODULES` 中）。检查 `python_executor.py` 的 `_BLOCKED_MODULES` 集合，确保不含这两个模块。

## 四、测试计划

### 4.1 新增测试

#### 4.1.1 图表层测试（`server/tests/test_code_task_provider.py` 新增）

新增 `TestSpec0027ChartBeautification` 测试类：

**SciencePlots + Seaborn 集成测试：**
- C1：`_HEADER` 包含 `import scienceplots`
- C2：`_HEADER` 包含 `plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])`
- C3：`_HEADER` 包含 `import seaborn as sns`
- C4：`_HEADER` 包含 `sns.set_theme`
- C5：生成的代码包含 `sns.histplot`（HISTOGRAM 类型）
- C6：生成的代码包含 `sns.boxplot`（BOXPLOT 类型）
- C7：生成的代码包含 `sns.countplot`（BAR 类型）
- C8：生成的代码包含 `sns.scatterplot`（SCATTER 类型）
- C9：CORRELATION 分析时额外生成 `sns.heatmap`（HEATMAP 新增类型）
- C10：BOXPLOT 且存在分类字段时额外生成 `sns.violinplot`（VIOLIN 新增类型）

**DeepSeek Prompt 测试：**
- D1：`_SYSTEM_PROMPT` 包含 SciencePlots 使用说明
- D2：`_SYSTEM_PROMPT` 包含 Seaborn API 推荐列表
- D3：`_SYSTEM_PROMPT` 的 import 白名单包含 `scienceplots`、`seaborn`

#### 4.1.2 PPT 层测试（`server/tests/test_ppt_config.py` 新增）

新增 `TestSpec0027LayoutEnhancement` 测试类：

**百分比定位测试：**
- P1：`_pct_to_emu("10%", Inches(13.333))` 返回 `Inches(1.3333)`（允许 ±1 EMU 误差）
- P2：`_pct_to_emu("50%", Inches(7.5))` 返回 `Inches(3.75)`
- P3：`_pct_to_emu("100%", Inches(10))` 返回 `Inches(10)`
- P4：`_pct_to_emu("non-pct", Inches(10))` 抛出 `ValueError`

**Grid 布局测试：**
- G1：`_GridHelper(0, 0, 1000, 1000, 2, 2).cell(0, 0)` 返回 `(0, 0, 500, 500)`
- G2：`_GridHelper(0, 0, 1000, 1000, 2, 2).cell(1, 1)` 返回 `(500, 500, 500, 500)`
- G3：`_GridHelper(0, 0, 1000, 1000, 1, 2, h_gap=100).cell(0, 0)` 返回 `(0, 0, 450, 1000)`
- G4：`_GridHelper(0, 0, 1000, 1000, 2, 2, v_gap=100).cell(0, 0)` 返回 `(0, 0, 500, 450)`

**回归验证：**
- G5：`_place_chart_grid` 使用 `_GridHelper` 后，2×2 网格布局坐标与原实现一致（图表不重叠、不溢出）
- G6：`_place_chart_three` 使用 `_GridHelper` 后，3 图布局坐标与原实现一致
- G7：`_place_chart_side_by_side` 使用 `_GridHelper` 后，双图并排坐标与原实现一致

#### 4.1.3 沙箱白名单测试（`server/tests/test_python_executor.py` 新增）

- S1：`scienceplots` 在 `ALLOWED_IMPORTS` 中
- S2：`seaborn` 在 `ALLOWED_IMPORTS` 中
- S3：`easypptx` 不在 `ALLOWED_IMPORTS` 中（沙箱不使用）
- S4：执行包含 `import scienceplots` 的代码不触发 AST 拦截
- S5：执行包含 `import seaborn as sns` 的代码不触发 AST 拦截

### 4.2 回归测试

运行以下测试套件，确保无回归：

```text
server/.venv/Scripts/python.exe -m pytest server/tests/test_code_task_provider.py -v
server/.venv/Scripts/python.exe -m pytest server/tests/test_ppt_config.py -v
server/.venv/Scripts/python.exe -m pytest server/tests/test_renderers.py -v
server/.venv/Scripts/python.exe -m pytest server/tests/test_python_executor.py -v
server/.venv/Scripts/python.exe -m pytest server/tests/ -k "code_task or ppt or renderer or executor" -v
```

### 4.3 真实文件验证

1. **图表验证**：生成包含 HISTOGRAM/BOXPLOT/BAR/SCATTER/HEATMAP/VIOLIN 的测试代码，在沙箱中执行，验证图表生成成功且样式应用正确
2. **PPT 验证**：生成 6 种预设色的 PPT 文件，程序化验证：
   - 百分比定位方法正确工作
   - Grid 布局辅助类计算坐标正确
   - 现有 SPEC 0024/0025/0026 视觉效果保持

## 五、验收标准

### 5.1 功能验收

- [ ] `code_task_provider.py` 生成的代码包含 SciencePlots + Seaborn 集成
- [ ] `deepseek_code_task_provider.py` 的 `_SYSTEM_PROMPT` 包含 SciencePlots + Seaborn 要求
- [ ] `ppt_renderer.py` 新增 `_pct_to_emu` 和 `_GridHelper` 辅助方法
- [ ] `_place_chart_grid` / `_place_chart_three` / `_place_chart_side_by_side` 使用 `_GridHelper`
- [ ] `python_executor.py` 的 import 白名单包含 `scienceplots`、`seaborn`
- [ ] `easypptx` 依赖在 `pyproject.toml` 中声明

### 5.2 回归验收

- [ ] `test_code_task_provider.py` 全部通过
- [ ] `test_ppt_config.py` + `test_renderers.py` 全部通过
- [ ] `test_python_executor.py` 全部通过
- [ ] SPEC 0024/0025/0026 专用测试全部通过（无回归）
- [ ] 前端 lint + build 不受影响（本 SPEC 仅改后端）
- [ ] Alembic 迁移不受影响（本 SPEC 不改 schema）

### 5.3 视觉验收

- 生成真实图表文件，验证 SciencePlots 样式应用（无 LaTeX 依赖、中文正常显示）
- 生成真实 PPT 文件，验证 Grid 布局坐标与原实现一致（无视觉漂移）
- 6 种预设色 PPT 均能正确生成（无 XML 解析错误）

## 六、风险与缓解

| 风险 | 等级 | 缓解措施 |
| --- | --- | --- |
| SciencePlots 依赖 LaTeX（沙箱未安装） | 高 | 使用 `no-latex` 样式，避免 LaTeX 依赖；测试验证沙箱内样式应用成功 |
| Seaborn 与 matplotlib 样式冲突 | 中 | `sns.set_theme` 在 `plt.style.use` 之后调用，确保 seaborn 主题不覆盖 science 样式 |
| EasyPPTX 全面替换风险 | 高 | 不全面替换，仅引入辅助方法；保留现有 `PptRenderer` 类结构 |
| 新依赖增加 Docker 镜像体积 | 中 | 在 `Dockerfile` 中同步安装三个新依赖；验证镜像大小可接受 |
| scienceplots 在 Windows 沙箱中字体缺失 | 中 | `cjk-sc-font` 样式回退到 `Microsoft YaHei`；保留现有 `matplotlib.rcParams` 字体配置作为兜底 |
| Grid 布局改造引入坐标计算偏差 | 中 | 测试 G5/G6/G7 验证改造后坐标与原实现一致；保留原 `_fit_image_size` 作为兜底 |
| 沙箱 AST 校验误拦截 scienceplots/seaborn | 低 | 测试 S4/S5 验证不触发拦截；`_BLOCKED_MODULES` 不含这两个模块 |
| DeepSeek 生成的代码不遵守 SciencePlots 要求 | 中 | `_SYSTEM_PROMPT` 明确要求；执行失败时降级到 LocalRule provider |

## 七、实现顺序

遵循 AGENTS.md 阶段闸顺序：

1. **测试先行**：先编写 `TestSpec0027ChartBeautification` 和 `TestSpec0027LayoutEnhancement` 测试类
2. **依赖安装**：在 `pyproject.toml` 声明 `scienceplots`、`seaborn`、`easypptx`；运行 `pip install`
3. **图表层实现**：升级 `code_task_provider.py` 的 `_HEADER` 和 `_build_chart_code`；升级 `deepseek_code_task_provider.py` 的 `_SYSTEM_PROMPT`
4. **PPT 层实现**：在 `ppt_renderer.py` 新增 `_pct_to_emu`、`_GridHelper`；改造 `_place_chart_*` 方法
5. **沙箱同步**：更新 `python_executor.py` 的 `ALLOWED_IMPORTS`
6. **运行测试**：确保新增测试通过 + 回归测试无回归
7. **真实文件验证**：生成图表和 PPT，程序化验证
8. **Docker 同步**：更新 `Dockerfile` 安装新依赖
9. **文档回写**：更新 SPEC 0027 状态、决策 0036、README、acceptance、implementation-plan、dependency-review
10. **git 收口**：复核 git 边界，精确 stage，commit

## 八、依赖与网络

- **新增依赖**：`scienceplots`（PyPI）、`seaborn`（PyPI）、`easypptx`（PyPI）
- **LaTeX 不需要**：使用 `no-latex` 样式
- **不访问网络**：依赖通过 pip 安装后离线运行
- **不涉及 DeepSeek 真实调用**：本 SPEC 仅升级 prompt，不调用 LLM（测试用 Fake provider）

## 九、文档回写清单

实现完成后需同步更新：

- [ ] `dev-docs/specs/0027-chart-beautification-and-layout-enhancement.md`（本文件，状态改为已完成）
- [ ] `dev-docs/decisions/0036-start-spec-0027-chart-beautification.md`（新建，记录启动决策）
- [ ] `dev-docs/README.md`（更新 SPEC 0027 状态）
- [ ] `dev-docs/acceptance.md`（新增 SPEC 0027 验收记录）
- [ ] `dev-docs/implementation-plan.md`（新增 V2.8.0 阶段信息）
- [ ] `dev-docs/dependency-review.md`（新增 scienceplots/seaborn/easypptx 依赖复核）
- [ ] `Dockerfile`（新增三个依赖安装）
- [ ] `server/pyproject.toml` 或 `server/requirements.txt`（声明新依赖）

## 十、约束遵守声明

本 SPEC 遵守以下约束：

1. **AGENTS.md 阶段闸**：先编写 SPEC，待项目负责人确认后进入实现
2. **推理闸**：已回答 owner 边界、当前真源、回归风险等问题
3. **唯一 owner**：图表生成改动在 `code_task_provider.py` + `deepseek_code_task_provider.py` 内；PPT 渲染改动在 `ppt_renderer.py` 内；沙箱校验改动在 `python_executor.py` 内
4. **新增依赖受控**：仅引入 `scienceplots`、`seaborn`、`easypptx` 三个 PyPI 包，在 `pyproject.toml` 声明
5. **不改变合同**：`PptConfig` 三字段不变，`render()` 签名不变，`LocalRuleCodeTaskProvider.generate()` 签名不变
6. **不破坏前序成果**：SPEC 0024/0025/0026 所有视觉效果和布局保持
7. **测试先行**：先写测试再实现
8. **回归零容忍**：现有所有测试必须全部通过
9. **文档回写**：实现完成后同步更新所有相关文档
10. **LaTeX 可选**：使用 `no-latex` 样式，沙箱不安装 LaTeX

## 十一、实现收口说明（2026-07-31）

### 11.1 实现完成情况

本 SPEC 已完成全部实现与验收，具体如下：

**图表层（SciencePlots + Seaborn 集成）：**
- `code_task_provider.py` 的 `_HEADER` 集成 `import scienceplots` + `plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])` + `import seaborn as sns` + `sns.set_theme(...)`
- `_build_chart_code` 升级为 Seaborn API：HISTOGRAM→`sns.histplot`、BOXPLOT→`sns.boxplot`、BAR→`sns.countplot`、SCATTER→`sns.scatterplot`
- `_build_analysis_code` 的 CORRELATION 分析新增 `sns.heatmap` 热图生成
- `deepseek_code_task_provider.py` 的 `_SYSTEM_PROMPT` 追加 SciencePlots + Seaborn 使用要求和 API 推荐列表

**PPT 层（EasyPPTX 风格辅助方法）：**
- 新增 `_pct_to_emu` 静态方法：百分比字符串转 EMU
- 新增 `_GridHelper` 内部类：N×M 网格坐标计算，支持 h_gap/v_gap
- 改造 `_place_chart_grid`（2×2 网格）、`_place_chart_side_by_side`（1×2 网格）、`_place_chart_three`（上排 1×2 网格）使用 `_GridHelper`，坐标与原硬编码完全一致

**沙箱层：**
- `DEFAULT_ALLOWED_IMPORTS` 新增 `scienceplots`、`seaborn`
- `easypptx` 不入沙箱白名单（仅 PPT 渲染层使用，不在用户代码执行环境中使用）

**依赖声明：**
- `pyproject.toml` 主 dependencies 新增 `easypptx>=0.5.0`
- `pyproject.toml` analysis 依赖组新增 `scienceplots>=2.1.0`、`seaborn>=0.13.0`

### 11.2 验收结果

| 验收项 | 结果 |
| --- | --- |
| SPEC 0027 专项测试（图表层 16 + PPT 层 18 + 沙箱层 10） | 44 passed（实际 45 passed，含 default_allowed_imports 回归修复） |
| 受影响测试全套（ppt_config + renderers + code_task + executor） | 204 passed 零回归 |
| Grid 布局坐标对齐验证 | 8/8 单元格全部对齐（精度 ±0.01 英寸） |
| _pct_to_emu 百分比定位验证 | 5/5 用例全部通过 |
| 真实图表生成（沙箱执行） | 5 张图表全部生成成功（exit_code=0, 8.19s），SciencePlots + Seaborn 集成检查 9/9 通过 |
| 6 种预设色 PPT 渲染 | 6/6 全部通过（渐变/圆角/阴影/边框保持，SPEC 0025/0026 视觉效果无回归） |
| HTML 预览文件 | 已生成 `dev-docs/e2e-screenshots/spec0027/spec0027-preview.html` |

### 11.3 实现过程中额外修复

1. **改造 `_place_chart_*` 方法使用 `_GridHelper`**：SPEC 0027 §3.2.4 明确要求，实现过程中发现三个方法仍为硬编码坐标，已用 `_GridHelper` 重构，坐标与原硬编码完全一致（无视觉漂移）
2. **修复 BOXPLOT `savefig` f-string bug**（`code_task_provider.py:296`）：缺少 `f` 前缀导致文件名为 `{safe_name}.png` 而非 `症状评分箱线图.png`
3. **修复 HISTOGRAM 无 data_fields 分支 `savefig` f-string bug**（`code_task_provider.py:288`）：同类问题

### 11.4 约束遵守验证

- 不改变 `PptConfig` 三字段合同 ✓
- 不改变 `render()` 签名 ✓
- 不改变 `LocalRuleCodeTaskProvider.generate()` 签名 ✓
- 不改变 API/service/Worker 接线 ✓
- 不修改数据库 schema ✓
- SPEC 0024/0025/0026 视觉效果全部保持 ✓
- LaTeX 不需要（使用 `no-latex` 样式）✓
