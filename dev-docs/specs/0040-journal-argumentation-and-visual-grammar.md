# SPEC 0040：期刊级论证图表与论文视觉语法改造

**状态：** 已实现，待项目负责人确认收口  
**日期：** 2026-08-13  
**前序 SPEC：** SPEC 0039 论文级多语义图形系统  
**owner：** `server/app/modules/outlines/figure_planner.py` 负责论证语义、证据引用和边界合同；Word/PDF 与 PPT renderer 只负责适配呈现。

## 1. 问题

SPEC 0039 已经解决“非数值内容不再默认画成树状图”，但图形仍缺少期刊论文常见的论证结构：读者需要同时看到主张、证据、方法、结果、解释边界以及正文引用位置。只有图形种类而没有论证合同，容易出现“图好看但不知道证明什么”、把观察性关联误读为因果关系、或把本地复核误认为原论文复现的问题。

## 2. 目标

1. 在共享 `FigurePlan` 上增加可校验的 `ArgumentPlan`，统一描述 `claim`、`evidence_refs`、`method`、`result`、`boundary`、`body_reference`。
2. 让每张论证图可以回到真实来源、公开数据、执行批次或图表产物；缺少证据、结果或边界时拒绝生成。
3. 将研究证据链、数据处理管线和变量关系图改造成“论证图”，不再只是节点与连接线的装饰。
4. 保留 SPEC 0037 已确认的统计图选择：构成图、Dumbbell、点估计区间图、趋势图、森林图等仍按数据语义使用。
5. Word/PDF 呈现完整题注、论证摘要、来源、限制和正文引用；PPT 复用已有 `pptxforge` 的 `Callout`、`Text`、`Image` 等组件，以“一页一个主张”组织论证，复杂多面板图采用图形主导的自适应版式。
6. 变量关系图明确区分暴露、结局和协变量，观察性关系不使用因果语义；连接线采用无交叉结构，保证正式论文可读性。

## 3. 设计合同

### 3.1 `ArgumentPlan`

```text
ArgumentPlan
  claim: str
  evidence_refs: tuple[str, ...]
  method: str
  result: str
  boundary: str
  body_reference: str
  evidence_status: EvidenceStatus
```

- `claim` 是图形要支持的主张，不是装饰性标题；
- `evidence_refs` 至少包含一个可追溯来源或执行产物；
- `result` 必须说明图中实际呈现的结果；
- `boundary` 必须说明不能从图中推出的结论；
- `body_reference` 指向正文中的对应章节；
- `out_of_scope` 论证状态拒绝生成，未知状态只能安全降级。

### 3.2 视觉语法

| 内容 | 视觉语法 | 论证职责 |
|---|---|---|
| 证据链 | A 原论文主张；B 数据口径；C 本地复核；D 证据对照与边界 | 同时呈现研究问题、原文方法/结论、公开数据血缘、本地结果和不可等同的解释边界 |
| 数据管线 | 原始记录 → 缺失结构 → 分组 → 结局 → 模型复核 | 说明结果如何由数据处理路径产生 |
| 变量关系 | 暴露 → 结局；协变量置于独立复核层 | 表达观察性关联，不暗示因果 |
| 统计比较 | 条形图、构成图、Dumbbell、点区间图、趋势图、森林图 | 表达大小、构成、比较、趋势和不确定性 |

### 3.3 双交付物适配

- Word/PDF：保留完整论证摘要、来源、边界和正文引用；图题按章节编号。
- PPT：标题、短主张、图形、结论边界组成单页；长文本压缩为可讲述的短句。
- 两者必须消费同一份 `FigurePlan`/`ArgumentPlan`，禁止 renderer 各自创造研究事实。

### 3.4 多面板证据论证合同

`FigureKind.EVIDENCE_CHAIN` 不再接受“4 个节点 + 线性箭头”的简化流程图，必须满足：

- 至少 8 个语义节点，覆盖研究问题、论文主张、数据口径、本地结果、结果对照和解释边界；
- 至少 4 个 `panel_labels`，分别对应 A 原论文、B 数据口径、C 本地复核、D 证据对照；
- 关系集合必须包含 `supports`、`contains`、`produces`、`compared_with`、`bounded_by`；
- 复杂度来自证据分层与可比性关系，不通过无来源装饰节点或树状层级伪造复杂度。

## 4. 案例范围

继续使用 Diabetes 130-US Hospitals 与 Strack 等 2014 年开放论文案例，保留真实口径：公开 CSV 101,766 条、论文最终样本 69,984 条、HbA1c 已检测 17,018 条。三张核心论证图分别呈现证据链、数据处理路径和变量关系；统计图继续使用真实执行产物。

明确不做：L3 原论文完整模型复现、医学诊疗建议、无来源机制图、把观察性关联写成因果结论、自由拖拽图形编辑器、新增外部渲染服务或新的运行时依赖。

## 5. 验收标准

- `ArgumentPlan` 对缺少主张、证据、结果或边界的输入有拒绝测试；
- 三张核心论证图含真实计数/字段/执行批次，并可回到 `analysis_summary.json`；
- 变量关系图无交叉连接线，图注明确“观察性关联，不代表因果关系”；
- 生成 `spec0040_argumentation.docx`、`spec0040_argumentation.pdf`、两套 16 页 PPT；
- Word/PDF 真实打印为 A4 18 页，Poppler 逐页检查无裁切、重叠、不可读文本和题注错位；
- 证据链 PNG 为 2×2 多面板论证图，Word/PDF 中保持论文式题注与论证摘要，PPT 中由图形主导并避免缩略图化；
- PowerPoint 原生界面检查封面、证据链、数据管线、变量关系和统计结果页，无乱码、溢出和过度拥挤；
- 不新增运行时依赖，不修改数据库 schema、API、LLM Gateway、Worker 或产品边界。

## 6. 实施与边界记录

实现位于 `figure_planner.py`、`ppt_renderer.py` 和论文案例生成脚本。PPT 继续复用现有 `pptxforge` 组件；证据链页使用图形主导的 `Stack(Image, Text)` 自适应版式。本机缺少 `@oai/artifact-tool` 和 LibreOffice，因此分别使用 PowerPoint 原生界面、Word 内置“创建 PDF/XPS 文档”及 Poppler 作为替代视觉证据。
