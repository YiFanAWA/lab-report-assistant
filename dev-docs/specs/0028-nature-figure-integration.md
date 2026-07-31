# SPEC 0028：Nature 风格图表集成（移除 SciencePlots，引入 nature-figure 设计规则）

**状态：** 已完成实现与验收，待项目负责人确认收口
**起草日期：** 2026-07-31
**实现完成日期：** 2026-07-31
**前序 SPEC：** [SPEC 0027](0027-chart-beautification-and-layout-enhancement.md)（图表美化与布局增强）
**调研依据：** [nature-skills GitHub 仓库](https://github.com/Yuan1z0825/nature-skills)（Apache-2.0 协议，265+ stars）
**关联决策：** [决策 0037](../decisions/0037-start-spec-0028-nature-figure.md)
**owner 层：**
- 图表生成层：`server/app/modules/llm/code_task_provider.py`、`server/app/modules/llm/deepseek_code_task_provider.py`
- 执行沙箱：`server/app/infrastructure/sandbox/python_executor.py`（import 白名单与 AST 校验）
- 依赖声明：`server/pyproject.toml`
- 不改变 owner 边界

## 一、背景与动机

### 1.1 SPEC 0027 现状

SPEC 0027 引入了 `scienceplots` + `seaborn` + `easypptx` 三个依赖，其中：
- `scienceplots` 提供 `plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])` 一键应用期刊样式
- `seaborn` 提供统计图表 API（`sns.histplot`、`sns.boxplot` 等）
- `easypptx` 提供 Grid 布局思路（已内化为 `_GridHelper` 辅助类）

SPEC 0027 已完成实现与验收（commit `958fc8e`），待项目负责人确认收口。

### 1.2 移除 SciencePlots 的动机

项目负责人要求调研 GitHub 上的 nature-skills 项目并评估技术栈替换。调研发现：

1. **SciencePlots 的局限性**：
   - 依赖外部样式注册机制，样式行为不可完全控制
   - `cjk-sc-font` 样式依赖系统字体配置，跨环境一致性差
   - `bright` 配色固定，无法按 nature-figure 设计规则自定义克制三色策略

2. **nature-figure skill 的优势**：
   - 通过手动 `rcParams` 配置实现 Nature 期刊风格，无外部样式库依赖
   - 设计规则系统化：图表契约 → 证据逻辑 → 原型分类 → 绘图
   - 基于 Nature Machine Intelligence 已发表论文的生产脚本
   - Apache-2.0 协议，允许借鉴和适配

3. **移除后影响面精确可控**：
   - 仅 5 个测试用例直接受影响（C1/C2/C3/S1/S4）
   - 6 处生产代码需修改（跨 3 个文件）
   - PPT 布局层（`_GridHelper`/`_pct_to_emu`）完全不受影响
   - Seaborn 图表 API 完全不受影响

### 1.3 技术路线选择

采用**方案 A**：移除 `scienceplots`，保留 `seaborn`，用 nature-figure 的 `rcParams` 替换 `plt.style.use(...)`。

选择理由：
- 减少一个外部依赖，`rcParams` 完全可控
- 保留 Seaborn 统计图表 API 的便利性
- 不影响 PPT 布局层和 Seaborn 相关测试（10 个测试无需修改）
- 改动面最小，回归风险最低

## 二、目标与边界

### 2.1 目标

1. **移除 SciencePlots 依赖**：从 `pyproject.toml`、沙箱白名单、生产代码中完全移除 `scienceplots`
2. **引入 nature-figure rcParams**：在 `code_task_provider.py` 的 `_HEADER` 中用 nature-figure 风格的 `rcParams` 替换 `plt.style.use(...)`
3. **DeepSeek prompt 同步**：更新 `deepseek_code_task_provider.py` 的 `_SYSTEM_PROMPT`，移除 SciencePlots 引用，追加 nature-figure 设计规则
4. **沙箱白名单同步**：从 `python_executor.py` 的 `DEFAULT_ALLOWED_IMPORTS` 中移除 `scienceplots`
5. **修复受影响测试**：修改 5 个直接引用 SciencePlots 的测试用例（C1/C2/C3/S1/S4）

### 2.2 边界（必须遵守）

- **不改变 owner 边界**：图表生成改动在 `code_task_provider.py` + `deepseek_code_task_provider.py` 内；沙箱校验改动在 `python_executor.py` 内
- **不改变 `PptConfig` 合同**：不新增配置字段；`target_slide_count` / `theme_color` / `include_charts` 三字段不变
- **不破坏 SPEC 0024/0025/0026/0027 成果**：
  - 三明治结构、三角色彩派生、五级字号、双栏布局保持（SPEC 0024/0025/0026）
  - `_GridHelper` 网格布局、`_pct_to_emu` 百分比定位保持（SPEC 0027）
  - Seaborn 统计图表 API 保持（SPEC 0027）
- **不引入新依赖**：本切片是移除依赖（`scienceplots`），不引入任何新 pip 包
- **保留 `seaborn` 和 `easypptx`**：这两个依赖不变
- **保留中文字体支持**：`rcParams` 中必须包含 `Microsoft YaHei`，确保中文正常显示
- **回归零容忍**：现有所有测试必须全部通过（修改的 5 个测试除外）
- **不改变 API / Service / Worker 接线**：`LocalRuleCodeTaskProvider.generate()` 签名不变

### 2.3 不纳入（留作后续方向）

- nature-figure 的 SVG 矢量输出 — PPT 嵌入仍需 PNG，SVG 留作后续可选导出
- nature-figure 的 `validate_figure.py` QA 预检 — 需要独立设计验证流程，留作后续 SPEC
- nature-figure 的图表契约系统（conclusion → evidence → archetype）— 需要改动 AnalysisPlan 合同，超出本切片范围
- nature-figure 的多面板 hero panel 布局 — 与现有 PPT 双栏布局冲突，留作后续评估
- 移除 `seaborn` — 方案 B 全面替换风险较高，不在本切片范围

## 三、实现方案

### 3.1 移除 SciencePlots 依赖

#### 3.1.1 pyproject.toml

从 `server/pyproject.toml` 中移除 `scienceplots>=2.1.0` 声明（第 39 行）。

**保留**：`seaborn>=0.13.0`（第 40 行）和 `easypptx>=0.5.0`（第 20 行）不变。

#### 3.1.2 沙箱白名单

从 `server/app/infrastructure/sandbox/python_executor.py` 的 `DEFAULT_ALLOWED_IMPORTS` 中移除 `"scienceplots"`（第 35 行）。

**保留**：`"seaborn"` 不变。

### 3.2 引入 nature-figure rcParams

#### 3.2.1 code_task_provider.py 的 `_HEADER` 改造

**当前实现（SPEC 0027，第 107-110 行）：**

```python
import scienceplots  # noqa: F401  # SPEC 0027：注册 science 样式
plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])
import seaborn as sns
sns.set_theme(style="whitegrid", palette="bright", font="Microsoft YaHei")
```

**新实现（SPEC 0028）：**

```python
# Nature 期刊风格 rcParams（nature-figure 设计规则，SPEC 0028）
# 参考：https://github.com/Yuan1z0825/nature-skills (Apache-2.0)
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'Arial', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['font.size'] = 16
matplotlib.rcParams['axes.spines.right'] = False       # 去右框（Nature 风格）
matplotlib.rcParams['axes.spines.top'] = False         # 去顶框（Nature 风格）
matplotlib.rcParams['axes.linewidth'] = 2.5            # 粗轴线（Nature 风格）
matplotlib.rcParams['legend.frameon'] = False          # 无图例边框
matplotlib.rcParams['figure.dpi'] = 100
matplotlib.rcParams['savefig.dpi'] = 300               # 高分辨率输出
matplotlib.rcParams['savefig.bbox'] = 'tight'
import seaborn as sns
sns.set_theme(style="whitegrid", palette="bright", font="Microsoft YaHei")
```

**设计要点：**

| rcParams | 值 | 来源 | 说明 |
| --- | --- | --- | --- |
| `font.sans-serif` | `['Microsoft YaHei', 'Arial', 'DejaVu Sans']` | nature-figure + 中文适配 | 首选微软雅黑（中文），其次 Arial（Nature 标准），最后 DejaVu Sans（兜底） |
| `font.size` | `16` | nature-figure | Nature 期刊标准正文字号 |
| `axes.spines.right` | `False` | nature-figure | 去除右侧轴线，减少视觉噪音 |
| `axes.spines.top` | `False` | nature-figure | 去除顶部轴线 |
| `axes.linewidth` | `2.5` | nature-figure | 粗轴线提升可读性 |
| `legend.frameon` | `False` | nature-figure | 无图例边框 |
| `savefig.dpi` | `300` | nature-figure | 300dpi 出版级分辨率 |
| `savefig.bbox` | `'tight'` | nature-figure | 紧凑裁剪 |

**与 SciencePlots 的等效性：**

| SciencePlots 样式 | nature-figure rcParams 等效 | 说明 |
| --- | --- | --- |
| `science` | `axes.spines.right/top=False` + `axes.linewidth=2.5` | 去框线 + 粗轴线 |
| `no-latex` | 无需配置（不使用 LaTeX） | nature-figure 不依赖 LaTeX |
| `cjk-sc-font` | `font.sans-serif=['Microsoft YaHei', ...]` | 直接指定中文字体 |
| `bright` | `sns.set_theme(palette="bright")` | 由 Seaborn 主题提供 |

#### 3.2.2 deepseek_code_task_provider.py 同步改造

**当前实现（第 68-69 行）：**

```python
import scienceplots  # noqa: F401
plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])
```

**新实现：**

```python
# Nature 期刊风格 rcParams（nature-figure 设计规则，SPEC 0028）
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'Arial', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['font.size'] = 16
matplotlib.rcParams['axes.spines.right'] = False
matplotlib.rcParams['axes.spines.top'] = False
matplotlib.rcParams['axes.linewidth'] = 2.5
matplotlib.rcParams['legend.frameon'] = False
matplotlib.rcParams['savefig.dpi'] = 300
matplotlib.rcParams['savefig.bbox'] = 'tight'
```

#### 3.2.3 _SYSTEM_PROMPT 更新

在 `_SYSTEM_PROMPT` 中：

1. **移除** `import scienceplots` 和 `plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])` 的引用
2. **移除** import 白名单中的 `- scienceplots`（第 85 行）
3. **追加** nature-figure 设计规则说明：

```python
_SYSTEM_PROMPT = """你是一个 Python 数据分析代码生成助手。...

6. matplotlib 必须配置 Nature 期刊风格 rcParams（SPEC 0028，参考 nature-figure skill）：
   import matplotlib
   matplotlib.use("Agg")
   matplotlib.rcParams['font.family'] = 'sans-serif'
   matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'Arial', 'DejaVu Sans']
   matplotlib.rcParams['axes.unicode_minus'] = False
   matplotlib.rcParams['font.size'] = 16
   matplotlib.rcParams['axes.spines.right'] = False
   matplotlib.rcParams['axes.spines.top'] = False
   matplotlib.rcParams['axes.linewidth'] = 2.5
   matplotlib.rcParams['legend.frameon'] = False
   matplotlib.rcParams['savefig.dpi'] = 300
   matplotlib.rcParams['savefig.bbox'] = 'tight'
   import matplotlib.pyplot as plt
   import seaborn as sns
   sns.set_theme(style="whitegrid", palette="bright", font="Microsoft YaHei")

7. 图表生成优先使用 seaborn API（统计图表更美观）：
   - 直方图：sns.histplot(data=df, x=field, kde=True)
   ...（保持 SPEC 0027 不变）

import 白名单（只允许以下模块，其他一律禁止）：
- pandas
- numpy
- matplotlib
- seaborn
- scipy
- sklearn
- openpyxl

严禁 import 以下模块（会被 AST 校验拦截导致执行失败）：
- os, sys, subprocess, shutil, pathlib, io, ctypes, signal
- socket, ssl, http, urllib, requests
"""
```

### 3.3 测试用例修复（5 个）

#### 3.3.1 test_local_rule_code_task_provider_format.py（3 个测试）

**C1：`test_HEADER包含scienceplots导入`（第 532 行）**

修改为验证 nature-figure rcParams：

```python
def test_HEADER包含nature_figure_rcParams(self):
    """C1：_HEADER 包含 nature-figure rcParams 配置（SPEC 0028）。"""
    from app.modules.llm.code_task_provider import _HEADER
    assert "matplotlib.rcParams" in _HEADER, "_HEADER 未配置 nature-figure rcParams"
    assert "axes.spines.right" in _HEADER, "_HEADER 未配置去右框 rcParams"
```

**C2：`test_HEADER包含science样式和no_latex`（第 537 行）**

修改为验证 nature-figure 核心设计规则：

```python
def test_HEADER包含nature_figure设计规则(self):
    """C2：_HEADER 包含 nature-figure 核心设计规则（SPEC 0028）。"""
    from app.modules.llm.code_task_provider import _HEADER
    assert "axes.spines.top" in _HEADER, "必须去除顶部轴线（Nature 风格）"
    assert "axes.linewidth" in _HEADER, "必须配置粗轴线（Nature 风格）"
    assert "2.5" in _HEADER, "轴线宽度必须为 2.5（Nature 标准）"
```

**C3：`test_HEADER包含cjk字体支持`（第 544 行）**

修改为验证中文字体在 rcParams 中保留：

```python
def test_HEADER包含中文字体配置(self):
    """C3：_HEADER 的 rcParams 包含 Microsoft YaHei 中文字体（SPEC 0028）。"""
    from app.modules.llm.code_task_provider import _HEADER
    assert "Microsoft YaHei" in _HEADER, "_HEADER 未配置 Microsoft YaHei 中文字体"
    assert "font.sans-serif" in _HEADER, "_HEADER 未配置 font.sans-serif"
```

#### 3.3.2 test_python_executor.py（2 个测试）

**S1：`test_scienceplots在默认白名单中`（第 587 行）**

修改为验证 scienceplots 已从白名单移除：

```python
def test_scienceplots已从默认白名单移除(self):
    """S1：scienceplots 不在 DEFAULT_ALLOWED_IMPORTS 中（SPEC 0028 移除）。"""
    assert "scienceplots" not in DEFAULT_ALLOWED_IMPORTS, (
        "scienceplots 应已从沙箱白名单移除（SPEC 0028）"
    )
```

**S4：`test_validate_code允许import_scienceplots`（第 605 行）**

修改为验证 scienceplots 被 AST 校验拦截（或至少不再是白名单成员）：

```python
def test_scienceplots不在白名单且不推荐(self):
    """S4：scienceplots 不在白名单中（SPEC 0028 移除）。"""
    assert "scienceplots" not in DEFAULT_ALLOWED_IMPORTS
    # scienceplots 不是被阻断的模块（_BLOCKED_MODULES），但不在白名单中
    # 如果用户代码尝试 import scienceplots，会因不在白名单而被拦截
```

### 3.4 不受影响项确认

| 项目 | 文件 | 说明 |
| --- | --- | --- |
| Seaborn 导入和 API | `code_task_provider.py` 第 109-110 行 | `import seaborn as sns` + `sns.set_theme(...)` 保持不变 |
| Seaborn 图表代码 | `code_task_provider.py` 第 276-314 行 | `sns.histplot/boxplot/countplot/scatterplot/heatmap` 保持不变 |
| `_GridHelper` | `ppt_renderer.py` | PPT 布局层与图表样式无关 |
| `_pct_to_emu` | `ppt_renderer.py` | 同上 |
| Seaborn 白名单 | `python_executor.py` 第 36 行 | `"seaborn"` 保持不变 |
| easypptx 依赖 | `pyproject.toml` 第 20 行 | 保持不变 |
| 10 个 Seaborn 相关测试 | test 文件 | C4-C10, S2, S5, S6 保持不变 |
| 18 个 PPT 布局测试 | `test_ppt_config.py` | 与 SciencePlots 无关 |

## 四、测试计划

### 4.1 修改的测试（5 个，红色→绿色）

| 测试 ID | 文件 | 原验证内容 | 新验证内容 |
| --- | --- | --- | --- |
| C1 | test_local_rule_code_task_provider_format.py | `import scienceplots` in _HEADER | `matplotlib.rcParams` + `axes.spines.right` in _HEADER |
| C2 | test_local_rule_code_task_provider_format.py | `science` + `no-latex` in _HEADER | `axes.spines.top` + `axes.linewidth` + `2.5` in _HEADER |
| C3 | test_local_rule_code_task_provider_format.py | `cjk-sc-font` in _HEADER | `Microsoft YaHei` + `font.sans-serif` in _HEADER |
| S1 | test_python_executor.py | `scienceplots` in DEFAULT_ALLOWED_IMPORTS | `scienceplots` not in DEFAULT_ALLOWED_IMPORTS |
| S4 | test_python_executor.py | validate_code 允许 `import scienceplots` | `scienceplots` not in DEFAULT_ALLOWED_IMPORTS |

### 4.2 回归测试

运行以下测试套件，确保无回归：

```text
server/.venv/Scripts/python.exe -m pytest server/tests/test_local_rule_code_task_provider_format.py -v
server/.venv/Scripts/python.exe -m pytest server/tests/test_ppt_config.py -v
server/.venv/Scripts/python.exe -m pytest server/tests/test_renderers.py -v
server/.venv/Scripts/python.exe -m pytest server/tests/test_python_executor.py -v
```

### 4.3 回归验证点

| 验证项 | 测试 ID | 预期结果 |
| --- | --- | --- |
| pandas 导入保留 | C11 | 通过 |
| matplotlib 导入保留 | C12 | 通过 |
| AST 语法检查 | C13 | 通过 |
| 中文字体配置保留 | C14 | 通过 |
| easypptx 不在白名单 | S3 | 通过 |
| 原有白名单模块可用 | S7 | 通过 |
| Seaborn 导入保留 | C4 | 通过 |
| Seaborn 主题保留 | C5 | 通过 |
| Seaborn 图表 API | C6-C10 | 通过 |
| Seaborn 白名单 | S2, S5, S6 | 通过 |
| PPT 布局 | 18 个测试 | 通过 |

### 4.4 真实文件验证

1. 生成包含 HISTOGRAM/BOXPLOT/BAR/SCATTER/HEATMAP 的测试代码，在沙箱中执行
2. 验证图表生成成功且 nature-figure rcParams 生效（去右框/顶框、粗轴线、中文字体）
3. 渲染 6 种预设色 PPT，验证与 SPEC 0024/0025/0026/0027 视觉效果保持一致

## 五、验收标准

### 5.1 功能验收

- [ ] `pyproject.toml` 中不再声明 `scienceplots` 依赖
- [ ] `code_task_provider.py` 的 `_HEADER` 不再包含 `import scienceplots` 和 `plt.style.use(['science', ...])`
- [ ] `code_task_provider.py` 的 `_HEADER` 包含 nature-figure rcParams（`axes.spines.right=False` 等）
- [ ] `deepseek_code_task_provider.py` 的 `_SYSTEM_PROMPT` 不再引用 `scienceplots`
- [ ] `python_executor.py` 的 `DEFAULT_ALLOWED_IMPORTS` 不再包含 `scienceplots`
- [ ] `scienceplots` 包仍可从虚拟环境中卸载（`pip uninstall scienceplots`）

### 5.2 回归验收

- [ ] `test_local_rule_code_task_provider_format.py` 全部通过（含修改的 C1/C2/C3）
- [ ] `test_python_executor.py` 全部通过（含修改的 S1/S4）
- [ ] `test_ppt_config.py` + `test_renderers.py` 全部通过（零回归）
- [ ] SPEC 0024/0025/0026/0027 专用测试全部通过（无回归）
- [ ] 前端 lint + build 通过

### 5.3 视觉验收

- [ ] 真实图表生成后，去右框/顶框效果可见
- [ ] 中文字体（微软雅黑）正常显示，无方框
- [ ] 轴线宽度 2.5pt 可见
- [ ] 6 种预设色 PPT 渲染成功，三明治结构和三角色彩系统保持

## 六、回滚策略

如果移除 SciencePlots 后图表质量明显下降：

1. **快速回滚**：`git revert` SPEC 0028 commit，恢复 SciencePlots 依赖
2. **部分回滚**：保留 nature-figure rcParams，同时恢复 `import scienceplots`（双重样式）
3. **降级处理**：将 nature-figure rcParams 中的关键参数（如 `axes.spines`）调整为更保守的值

回滚判断依据：
- 图表生成失败率 > 5%
- 中文字体显示异常
- PPT 视觉效果项目负责人不满意

## 七、风险分析

| 风险 | 概率 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| nature-figure rcParams 与 Seaborn 主题冲突 | 中 | 中 | `sns.set_theme` 在 rcParams 之后调用，Seaborn 会覆盖部分 rcParams；需验证最终效果 |
| 中文字体在 nature-figure rcParams 下显示异常 | 低 | 高 | `font.sans-serif` 首选 `Microsoft YaHei`，与 SPEC 0027 一致 |
| 移除 SciencePlots 后 `cjk-sc-font` 样式失效 | 低 | 中 | nature-figure 直接指定 `Microsoft YaHei`，不依赖 `cjk-sc-font` 样式 |
| 沙箱执行代码中 `import scienceplots` 报错 | 低 | 低 | 白名单移除后，用户代码不应 import scienceplots；DeepSeek prompt 已同步更新 |

## 八、依赖变更

### 8.1 移除的依赖

| 依赖 | 版本 | 移除原因 |
| --- | --- | --- |
| `scienceplots` | `>=2.1.0` | 被 nature-figure rcParams 替换，不再需要外部样式库 |

### 8.2 保留的依赖

| 依赖 | 版本 | 保留原因 |
| --- | --- | --- |
| `seaborn` | `>=0.13.0` | 统计图表 API，方案 A 保留 |
| `easypptx` | `>=0.5.0` | Grid 布局思路来源，已内化为 `_GridHelper` |

### 8.3 新增的依赖

无。本切片是纯移除 + rcParams 替换，不引入任何新依赖。

## 九、与 SPEC 0027 的关系

| SPEC 0027 内容 | SPEC 0028 处理 |
| --- | --- |
| `scienceplots` 依赖 | **移除** |
| `plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])` | **替换**为 nature-figure rcParams |
| `seaborn` 依赖 | **保留** |
| `sns.set_theme(...)` | **保留** |
| `sns.histplot/boxplot/countplot/scatterplot/heatmap` | **保留** |
| `_GridHelper` / `_pct_to_emu` | **保留**（不受影响） |
| `easypptx` 依赖 | **保留** |
| 沙箱白名单 `scienceplots` | **移除** |
| 沙箱白名单 `seaborn` | **保留** |

## 十、实现顺序

```text
1. 修改 5 个测试用例（红色阶段，验证测试失败）
2. 移除 pyproject.toml 中的 scienceplots 声明
3. 改造 code_task_provider.py 的 _HEADER（移除 scienceplots，加 nature-figure rcParams）
4. 改造 deepseek_code_task_provider.py 的 _SYSTEM_PROMPT
5. 从 python_executor.py 的 DEFAULT_ALLOWED_IMPORTS 移除 scienceplots
6. 运行测试（绿色阶段，验证测试通过）
7. 运行回归测试套件
8. 真实图表 + PPT 视觉验证
9. 卸载 scienceplots 包（pip uninstall scienceplots）
10. 文档回写 + git 收口
```

## 十一、文档回写清单

实现完成后需同步更新：

- [x] `dev-docs/README.md`：追加 V2.8.1 SPEC 0028 信息
- [x] `dev-docs/acceptance.md`：追加 SPEC 0028 验收记录
- [x] `dev-docs/implementation-plan.md`：追加 SPEC 0028 实现记录
- [x] `dev-docs/dependency-review.md`：移除 scienceplots 条目，更新 seaborn/easypptx 说明
- [x] `dev-docs/decisions/0037-start-spec-0028-nature-figure.md`：新建决策记录
- [x] 本 SPEC 文档：状态更新为"已完成实现与验收"

## 十二、约束遵守验证

实现完成后逐项确认：

- [x] 未改变 owner 边界
- [x] 未改变 `PptConfig` 合同
- [x] 未破坏 SPEC 0024/0025/0026/0027 成果（除 SciencePlots 外）
- [x] 未引入新依赖
- [x] 保留了中文字体支持
- [x] 保留了 Seaborn 图表 API
- [x] 保留了 `_GridHelper` 网格布局
- [x] 所有回归测试通过
- [x] API / Service / Worker 接线不变

## 十三、实现收口说明（2026-07-31）

### 13.1 实现完成情况

**图表层（nature-figure rcParams 集成）：**
- `code_task_provider.py` 的 `_HEADER` 移除 `import scienceplots` 和 `plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])`
- 新增 nature-figure rcParams：`axes.spines.right/top=False`、`axes.linewidth=2.5`、`legend.frameon=False`、`savefig.dpi=300`、`savefig.bbox='tight'`
- 保留 `font.sans-serif=['Microsoft YaHei', 'Arial', 'DejaVu Sans']` 中文字体支持
- 保留 `import seaborn as sns` 和 `sns.set_theme(style="whitegrid", palette="bright", font="Microsoft YaHei")`

**DeepSeek prompt 同步：**
- `deepseek_code_task_provider.py` 的 `_SYSTEM_PROMPT` 同步移除 SciencePlots 引用
- 追加 nature-figure rcParams 使用说明
- import 白名单文本移除 `- scienceplots`

**沙箱白名单更新：**
- `python_executor.py` 的 `DEFAULT_ALLOWED_IMPORTS` 移除 `"scienceplots"`
- 保留 `"seaborn"` 不变

**依赖声明：**
- `pyproject.toml` 移除 `scienceplots>=2.1.0`
- 保留 `seaborn>=0.13.0` 和 `easypptx>=0.5.0`

### 13.2 验收结果

**测试验收：**

| 验收项 | 命令 | 结果 |
| --- | --- | --- |
| SPEC 0027+0028 专项测试 | `pytest test_local_rule_code_task_provider_format.py test_python_executor.py -k "Spec0027"` | 26 passed |
| 受影响测试全套 | `pytest test_local_rule_code_task_provider_format.py test_ppt_config.py test_renderers.py test_python_executor.py` | 204 passed 零回归 |

**真实文件验收：**
- _HEADER 内容验证：10/10 检查通过（不含 scienceplots、含 nature-figure rcParams）
- 沙箱执行验证：成功生成 3 张图表 PNG + 1 张相关性 CSV（scienceplots 已卸载）
- 6 种预设色 PPT 渲染：blue/purple/green/red/orange/gray 全部成功
- PPT 文件保存在 `dev-docs/e2e-screenshots/spec0028/`

### 13.3 额外修复

- `test_python_executor.py` 的 `test_default_allowed_imports_content` 测试（第 168 行）同步更新，移除 `scienceplots` 断言（影响面分析中遗漏，回归测试中发现并修复）

### 13.4 约束遵守验证

| 约束 | 遵守情况 |
| --- | --- |
| 未改变 owner 边界 | ✅ 图表生成在 code_task_provider/deepseek_code_task_provider，沙箱在 python_executor |
| 未改变 PptConfig 合同 | ✅ target_slide_count/theme_color/include_charts 三字段不变 |
| 未破坏 SPEC 0024/0025/0026/0027 成果 | ✅ 三明治结构、三角色彩、GridHelper、Seaborn API 全部保留 |
| 未引入新依赖 | ✅ 纯移除 scienceplots，无新增 |
| 保留中文字体支持 | ✅ font.sans-serif 首选 Microsoft YaHei |
| 保留 Seaborn 图表 API | ✅ sns.histplot/boxplot/countplot/scatterplot/heatmap 不变 |
| 保留 _GridHelper 网格布局 | ✅ ppt_renderer.py 未修改 |
| API/Service/Worker 接线不变 | ✅ generate()/render() 签名不变 |
