# 决策 0036：启动 SPEC 0027 图表美化与布局增强

**日期：** 2026-07-31
**决策类型：** 启动新切片
**状态：** 已完成实现与验收，待项目负责人确认收口
**关联 SPEC：** [SPEC 0027](../specs/0027-chart-beautification-and-layout-enhancement.md)
**前序决策：** [决策 0035](0035-start-spec-0026-ppt-visual-effects.md)（SPEC 0026 已完成实现与验收）

## 一、背景

SPEC 0024（16:9 画布 + 双栏布局）、SPEC 0025（三角色彩 + 三明治结构）、SPEC 0026（渐变 + 圆角 + 阴影 + 边框）已连续完成 PPT 视觉效果三层增强。项目负责人反馈"生成的还是有些不尽人意"，要求去 GitHub 搜集数学建模相关数据构图布局的项目进行借鉴，并允许在引入前询问选择后引入可直接使用的依赖和组件。

调研结果记录于 [调研报告](../research/2026-07-31-github-math-modeling-visualization-research.md)。核心发现：

1. **SciencePlots**：matplotlib 样式库，一键应用 Nature/IEEE 期刊风格，色盲友好配色，中文支持
2. **Seaborn**：统计数据可视化库，提供小提琴图/热图/回归图等高级统计图表
3. **EasyPPTX**：python-pptx 封装层，提供百分比定位、Grid 布局系统
4. **《数学要素》项目**：19 个即用型数学可视化模板
5. **scientific-visualization / scientific-slides skill**：期刊级图表 + 科研演讲设计指南

项目负责人已通过 AskUserQuestion 确认选择：
- **图表生成层**：SciencePlots + Seaborn 组合（推荐）
- **PPT 渲染层**：引入 EasyPPTX 封装层

基于调研结果和项目负责人选择，起草 SPEC 0027，聚焦两层增强：图表层美化（SciencePlots + Seaborn）和 PPT 层布局增强（EasyPPTX 辅助方法）。

## 二、决策

启动 SPEC 0027「图表美化与布局增强（SciencePlots + Seaborn + EasyPPTX）」。

### 2.1 范围

- **owner 层**：
  - 图表生成层：`server/app/modules/llm/code_task_provider.py`、`server/app/modules/llm/deepseek_code_task_provider.py`
  - PPT 渲染层：`server/app/infrastructure/renderers/ppt_renderer.py`
  - 执行沙箱：`server/app/infrastructure/sandbox/python_executor.py`（import 白名单）
- **新增依赖**：`scienceplots`、`seaborn`、`easypptx`（在 `pyproject.toml` 声明）
- **合同**：不改变 `PptConfig` 三字段，不改变 `render()` 签名，不改变 `LocalRuleCodeTaskProvider.generate()` 签名
- **API/Service/Worker 接线**：不改动

### 2.2 两层增强

1. **图表层美化**：
   - `code_task_provider.py` 的 `_HEADER` 集成 SciencePlots + Seaborn
   - `_build_chart_code` 升级为 seaborn API（histplot/boxplot/countplot/scatterplot）
   - 新增 HEATMAP/VIOLIN/REGRESSION 图表类型
   - `deepseek_code_task_provider.py` 的 `_SYSTEM_PROMPT` 同步升级

2. **PPT 层布局增强**：
   - `ppt_renderer.py` 新增 `_pct_to_emu` 百分比定位辅助方法（EasyPPTX 风格）
   - 新增 `_GridHelper` 内部类（N×M 网格坐标计算）
   - 改造 `_place_chart_grid/three/side_by_side` 使用 Grid 布局
   - 不全面重写，保留 SPEC 0024/0025/0026 所有视觉成果

### 2.3 不纳入

- 3D 曲面图、等高线联动（《数学要素》模板）— 需特定数据形态，留作后续 SPEC
- Plotly 交互式图表 — 需浏览器环境，不适合 PPT 静态嵌入
- mplcyberpunk 赛博朋克风格 — 不符合教学实验报告严肃风格
- rwthplots RWTH 企业设计 — 偏欧式学术风，与现有主题色系统冲突
- EasyPPTX 全面替换 — 改动面过大，风险不可控
- LaTeX 依赖 — 使用 `no-latex` 样式，沙箱不安装 LaTeX

## 三、风险与缓解

| 风险 | 等级 | 缓解 |
| --- | --- | --- |
| SciencePlots 依赖 LaTeX（沙箱未安装） | 高 | 使用 `no-latex` 样式；测试验证沙箱内样式应用成功 |
| Seaborn 与 matplotlib 样式冲突 | 中 | `sns.set_theme` 在 `plt.style.use` 之后调用 |
| EasyPPTX 全面替换风险 | 高 | 不全面替换，仅引入辅助方法；保留现有 `PptRenderer` 结构 |
| 新依赖增加 Docker 镜像体积 | 中 | `Dockerfile` 同步安装；验证镜像大小可接受 |
| Grid 布局改造引入坐标偏差 | 中 | 测试 G5/G6/G7 验证改造后坐标与原实现一致 |
| 沙箱 AST 误拦截 scienceplots/seaborn | 低 | 测试 S4/S5 验证不触发拦截 |

## 四、验收入口

- 新增 `TestSpec0027ChartBeautification` 测试类（图表层 10 + DeepSeek prompt 3 = 13 个测试）
- 新增 `TestSpec0027LayoutEnhancement` 测试类（百分比定位 4 + Grid 布局 7 = 11 个测试）
- 新增沙箱白名单测试 5 个
- 回归测试：现有所有测试全部通过（1 预存 DEEPSEEK 失败除外）
- 真实文件验证：图表生成 + 6 种预设色 PPT 程序化验证
- Docker 镜像构建验证（含三个新依赖）

## 五、阶段闸遵守

本决策遵守 AGENTS.md 阶段闸：

1. SPEC 0026 已完成实现与测试验收（commit 8b41bc1），待项目负责人确认收口
2. 本决策仅起草 SPEC 0027 草案，不进入实现
3. 待项目负责人确认本决策后，方可进入 SPEC 0027 实现（含安装依赖）
4. 实现完成后，按 SPEC 0027 测试计划验收
5. 验收通过后，更新文档并执行 git 收口

## 六、与前序 SPEC 的关系

| SPEC | 状态 | 本 SPEC 关系 |
| --- | --- | --- |
| SPEC 0024（16:9 画布 + 双栏布局） | 已收口 | 保持布局结构，Grid 辅助方法复用 |
| SPEC 0025（三角色彩 + 三明治） | 已收口 | 保持色彩系统，图表样式与主题色协调 |
| SPEC 0026（渐变 + 圆角 + 阴影 + 边框） | 待确认收口 | 保持视觉效果，不破坏现有渲染逻辑 |
| **SPEC 0027（本决策）** | **已完成实现与验收，待确认收口** | **在 0024/0025/0026 基础上增强图表层和布局层** |

## 七、验收证据（2026-07-31 实现收口回写）

### 7.1 测试验收

| 验收项 | 命令 | 结果 |
| --- | --- | --- |
| SPEC 0027 专项测试 | `pytest test_local_rule_code_task_provider_format.py test_ppt_config.py test_python_executor.py -k "Spec0027 or default_allowed_imports"` | 45 passed |
| 受影响测试全套 | `pytest test_ppt_config.py test_renderers.py test_local_rule_code_task_provider_format.py test_python_executor.py` | 204 passed 零回归 |
| Grid 布局坐标对齐 | `verify_spec0027.py` 程序化验证 | 8/8 单元格全部对齐（精度 ±0.01 英寸） |
| _pct_to_emu 百分比定位 | `verify_spec0027.py` 程序化验证 | 5/5 用例全部通过 |

### 7.2 真实文件验收

| 验收项 | 结果 |
| --- | --- |
| SciencePlots + Seaborn 代码集成检查 | 9/9 项全部通过（import scienceplots / plt.style.use / sns.set_theme / sns.histplot / sns.boxplot / sns.countplot / sns.scatterplot / sns.heatmap） |
| 沙箱执行真实图表生成 | exit_code=0, 8.19s，生成 5 张图表（HISTOGRAM/BAR/BOXPLOT/SCATTER/HEATMAP） |
| 6 种预设色 PPT 渲染 | 6/6 全部通过（蓝/紫/绿/红/橙/灰），每色 6 页 4 图，渐变/圆角/阴影/边框全部保持 |
| HTML 预览文件 | `dev-docs/e2e-screenshots/spec0027/spec0027-preview.html`（176.8 KB，含真实图表 base64） |

### 7.3 实现过程中额外修复

1. **改造 `_place_chart_*` 方法使用 `_GridHelper`**：SPEC 0027 §3.2.4 要求，实现过程中发现三个方法仍为硬编码坐标，已重构，坐标与原硬编码完全一致
2. **修复 BOXPLOT `savefig` f-string bug**（`code_task_provider.py:296`）：缺少 `f` 前缀导致文件名为 `{safe_name}.png`
3. **修复 HISTOGRAM 无 data_fields 分支 `savefig` f-string bug**（`code_task_provider.py:288`）：同类问题

### 7.4 约束遵守验证

- 不改变 `PptConfig` 三字段合同 ✓
- 不改变 `render()` / `generate()` 签名 ✓
- 不改变 API/service/Worker 接线 ✓
- 不修改数据库 schema ✓
- SPEC 0024/0025/0026 视觉效果全部保持 ✓
- LaTeX 不需要（使用 `no-latex` 样式）✓
- 新增依赖受控（仅 scienceplots/seaborn/easypptx 三个 PyPI 包）✓
