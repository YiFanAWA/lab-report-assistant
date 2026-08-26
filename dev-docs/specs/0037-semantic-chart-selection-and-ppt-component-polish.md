# SPEC 0037：语义图表选择与论文级 PPT 组件优化

**状态：** 实现完成，待项目负责人确认收口  
**日期：** 2026-08-12  
**前序 SPEC：** SPEC 0036 论文解读深度整改  
**owner：** `server/app/modules/outlines/chart_planner.py` 负责交付物层图表语义规划；案例脚本负责真实统计与绘图；`ppt_renderer.py` 负责复用现有 PPT 组件。

## 1. 问题

SPEC 0036 案例虽然增加了数据量和分析深度，但多个结果仍被同一个柱状图函数生成，造成“所有图都长得一样”。PPT renderer 已经集成 `pptxforge` 的布局原语，但论文解读案例没有按页面表达任务组合这些组件，导致页面节奏单一。

## 2. 目标

1. 按数据类型、分析目的、自然顺序和置信区间选择图表。
2. 将图表类型、编码方式和选择理由写入真实图表 artifact 元数据与分析摘要。
3. 复用已有 `pptxforge` 组件和主题，不新增手绘装饰体系。
4. 保持 Word/PPT 继续消费同一份大纲、图表索引和执行产物。

## 3. 语义图表规则

| 分析目的 | 图表 | 本案例落地 |
|---|---|---|
| 样本口径转移 | 流程图 | 公开 CSV → 本地口径 → 论文样本 |
| 结局构成 | 100% 堆叠构成图 | NO、>30 天、<30 天 |
| 缺失字段排序 | 横向条形图 | Top 8 缺失率 |
| 配对结果比较 | Dumbbell | 论文 18.4% vs 本地 16.7% |
| 组间比例 + 不确定性 | 点估计 + 95% CI | HbA1c 检测组 vs 未检测组 |
| 有自然顺序的分层 | 点线趋势图 | 年龄组、住院天数 |
| 多变量调整效应 | Forest Plot | 简化 Logistic 复核 |

规划器无法安全表达时回退到标签可读性优先的横向条形图，不为了形式多样而强行使用复杂图形。

## 4. PPT 组件复用

答辩工作流继续使用现有 `pptxforge` 主题，并组合已有组件：

- `StatRow`：样本规模、论文/本地检测率等核心数字；
- `Callout`：先读结论、口径边界、局限和结果解释；
- `TwoColumn`：论文来源与本地数据、结果解释与图表；
- `IconRow`：分析方法流程；
- 原有 `Grid`/`Stack`：双图结果和图表说明。

本轮不复制 `ppt-master` 或上海交大仓库资源，不新增字体、图片或模板文件。

## 5. 改动范围

- 新增 `server/app/modules/outlines/chart_planner.py`；
- 更新 `server/scripts/generate_spec0035_paper_review.py`；
- 更新 `server/app/infrastructure/renderers/ppt_renderer.py`；
- 新增图表规划测试并扩展案例产物追溯测试；
- 回写 `dev-docs/README.md`、`dev-docs/acceptance.md` 和 `dev-docs/dependency-review.md`。

不改变 API、数据库 schema、LLM Gateway、沙箱白名单和运行时依赖。

## 6. 完成标准

- 真实案例至少包含 flow、stacked composition、Dumbbell、point + CI、ordered line 和 forest 六类图表；
- 每个图表 artifact 有 `chart_kind`、`chart_encoding` 和 `chart_rationale`；
- academic 与 sjtu_academic 两套 PPT 可被 `python-pptx` 重新打开，均为 16:9、13 页；
- PPT 关键页面消费已有 `StatRow`、`Callout`、`TwoColumn`、`IconRow` 等组件；
- 定向测试与全量后端测试通过；
- 视觉工具缺失时，必须如实记录替代证据和未执行项。

## 7. 未闭合风险

- 当前机器缺少 `pdf2image` 和可用的 Artifact Tool 包路径，无法用标准 `render_slides.py` 完成最新 PPT 的逐页真实渲染；已用图表 PNG、`python-pptx` 重开和产物元数据检查替代。
- 当前机器缺少 LibreOffice/Word，DOCX 到 PDF 的视觉转换仍需在具备 Office 转换器的环境补验。
