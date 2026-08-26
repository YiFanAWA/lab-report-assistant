# SPEC 0043：论文出版级结构、排版与交付物统一系统

**状态：** 已由项目负责人确认进入实现  
**日期：** 2026-08-13  
**前序 SPEC：** SPEC 0042 开放许可科研图形资产库与科研示意图组件系统  
**owner：** `server/app/modules/outlines/document_planner.py` 拥有论文语义结构、内容充分性、出版 profile 与答辩叙事合同；`figure_planner.py` 继续拥有图形语义；Word/PDF/PPT renderer 只负责确定性呈现。

## 1. 背景与问题

SPEC 0038—0042 已解决正式 A4 外观、图形语义、论证图、异构编排和开放科研组件，但当前成品仍更像“技术验收报告套论文样式”：章节按 `source_type` 分组，摘要和正文内容不足，目录、题注和交叉引用为静态文本，工程追溯信息侵入正文；PDF 与 Word 可能形成两套排版真相；PPT 则把论文段落压缩到小图加小字页面，缺少独立答辩叙事。

本 SPEC 不回档，不推翻 SPEC 0039—0042。它把既有图形与资产能力纳入一条出版级内容链，解决“像论文”和“能投稿/答辩阅读”之间的结构性差距。

## 2. 目标

1. 新增 `ManuscriptPlan`，以论文修辞角色而非来源类型决定摘要、绪论、方法、结果、讨论、结论和附录。
2. 新增内容充分性门禁：缺少研究问题、数据、方法、结果证据、讨论或引用时，返回结构化问题，不用空章节和套话补齐。
3. 新增一个明确的 `PublicationProfile`：首期只支持“中文高校正式学术论文通用版式”，确定 A4、页边距、字体、字号、行距、缩进、标题层级、题注、三线表、页眉页脚、页码和参考文献规则。
4. Word 使用真实字段和结构：动态 TOC、`SEQ Figure/Table`、`REF/PAGEREF`、多级标题编号、节分隔、前置罗马页码与正文阿拉伯页码、图表目录和参考文献。
5. PDF 只由最终 DOCX 导出，不再独立排正文；若当前环境不能完成 DOCX→PDF，则明确报告缺失，不伪造第二份 PDF。
6. 工程追溯信息移入附录、文档属性、speaker notes 或 manifest，正文只保留论文读者需要的来源、方法、样本量、统计口径和解释边界。
7. 结果章节形成“段落引导 → 图/表 → 正式题注 → 结果解释 → 边界”的阅读节奏，并支持多面板主结果、分层、敏感性和机制/假设图。
8. `DefenseDeckPlan` 独立规划 12—15 页答辩叙事，图形占页面主视觉 60%—75%，标题不小于 35 pt、正文不小于 18 pt、图注/来源不小于 12 pt。

## 3. 非目标与边界

- 不自动声称满足某一具体期刊或学校未提供的官方模板；首期只实现明确命名的通用 profile。
- 不让 DeepSeek 或其他 LLM 决定统计真相、许可证、因果关系、章节归属或验收结果；模型只可生成可校验的文字候选。
- 不新增数据库 schema、公开 API、Worker 路线或运行时在线排版服务。
- 不修改、回滚或删除 SPEC 0039—0042 的图形合同、资产库、安全门禁和追溯能力。
- 不保留 Word/PDF 两套独立正文布局，不把工程 manifest 伪装成论文正文。
- 不以缩小字体、堆叠卡片或增加装饰替代内容结构和证据充分性。

## 4. 核心合同

### 4.1 ManuscriptPlan

```text
ManuscriptPlan
  title: str
  abstract: ManuscriptAbstract
  keywords: tuple[str, ...]
  chapters: tuple[ManuscriptChapter, ...]
  references: tuple[ReferenceEntry, ...]
  appendices: tuple[ManuscriptAppendix, ...]
  publication_profile: PublicationProfile
  sufficiency: ContentSufficiencyReport
```

章节归属由明确的 `manuscript_role` 或稳定的论文语义映射决定。`source_type` 只参与证据追溯；它不得成为章节 owner。标题中已有编号必须标准化，避免 `3.1 3结果` 等双重编号。

### 4.2 内容充分性门禁

```text
ContentSufficiencyReport
  publishable: bool
  issues: tuple[ContentIssue, ...]

ContentIssue
  code: str
  severity: blocking | warning
  manuscript_role: str
  message: str
  source_ids: tuple[str, ...]
```

阻断项至少包括：无研究问题/目标、无真实数据说明、无方法、结果无执行产物或证据、讨论不回应结果、外部主张无引用、章节为空。观察性证据不得生成因果结论。

### 4.3 PublicationProfile

首期 profile：`zh_academic_thesis`

- A4 纵向；正文双面阅读规则；封面、摘要/目录、正文、参考文献和附录使用显式节。
- 中文正文宋体 10.5 pt，英文/数字 Times New Roman；1.5 倍行距，首行缩进 2 字符，两端对齐。
- 一级/二级/三级标题采用稳定多级编号和段前后距；禁止正文手工拼接编号。
- 图题置图下、表题置表上；采用 `SEQ` 字段；正文交叉引用采用 `REF/PAGEREF`。
- 表格使用三线表、重复表头、显式列宽和单元格边距；图、题注和首段尽量保持同页。
- 前置部分使用罗马页码，正文起使用阿拉伯页码；奇偶页页眉与章节标题按 profile 控制。

### 4.4 单一出版链

```text
confirmed outline + evidence + executions + figure portfolio
  -> ManuscriptPlan
  -> DOCX renderer
  -> final DOCX
  -> DOCX-to-PDF adapter
  -> final PDF
```

PDF adapter 不接受第二份正文模型，也不重排章节。DOCX 与 PDF 的标题、段落、图表、引用和页码以同一最终 DOCX 为真源。

### 4.5 DefenseDeckPlan

PPT 与论文共享事实、图表、引用和结论边界，但不共享页面结构。建议叙事：封面、研究问题、证据缺口、数据与队列、研究设计、数据质量、主结果 1—3、分层/敏感性、机制或关系解释、讨论、局限、结论、致谢/提问，共 12—15 页。

每页一个可讲述主张；复杂图形占主视觉 60%—75%；长段落必须压缩为论点，不得直接截断；来源写入 speaker notes，页面只保留必要短来源。

## 5. 实施顺序与并行边界

1. 主线程先定义 `ManuscriptPlan`、`PublicationProfile`、内容门禁和迁移兼容边界。
2. Word/PDF 线程只修改 Word renderer、DOCX→PDF adapter 及其专项测试。
3. 图形与内容节奏线程只修改论文图形/章节编排投影及其专项测试，不改 Word/PPT renderer。
4. PPT 线程只修改 `DefenseDeckPlan` 投影、PPT renderer 和专项测试。
5. 主线程统一集成真实 Diabetes 公开论文/数据案例，生成 DOCX/PDF/PPT，执行全量与逐页视觉验收。

任何线程不得重写其他线程的 owner 文件；子线程结论必须由主线程通过 diff、测试和真实成品复核。

## 6. 验收标准

- 章节不再按 `source_type` 直接分组；同一来源可支持多个论文修辞角色，且标题无双重编号。
- 内容门禁对六类核心缺口给出结构化阻断；真实案例通过门禁，缺失 fixture 被拒绝。
- DOCX 包含真实 TOC、SEQ、REF/PAGEREF、多级编号、节和两套页码；图表题注、三线表和参考文献可在 Word 中更新。
- 最终 PDF 由最终 DOCX 导出；内容哈希/结构审计证明不存在第二份正文计划。
- 正文不显示资产 id、SHA-256、JSON 路径等工程信息；这些信息仍可在附录/manifest/notes 追溯。
- 结果章节至少展示主结果、多面板或互补图、分层/敏感性和边界说明，且图文顺序符合论文阅读节奏。
- PPT 为 12—15 页，图形主视觉比例、字号和每页一主张通过结构检查；不得出现小图缩略化、公式化占位文案、重复“解释边界”等问题。
- DOCX/PDF 每页和 PPT 每页完成真实渲染检查，无裁切、重叠、乱码、错误分页、孤立题注和不可读图注。
- 定向测试、后端全量测试、Alembic、前端 lint/build 全部通过；文档真源与验收记录同步更新。

## 7. 停止条件

- 若现有已确认大纲无法提供通过内容门禁的真实证据，不生成“看似完整”的正式论文，只交付结构化缺口报告。
- 若 DOCX→PDF 转换器不可用，不启用独立 PDF 排版回退；明确保留 DOCX 成品和待转换状态。
- 若 PPT 必须依赖小于最低字号或低于 60% 主视觉才能容纳内容，回到 `DefenseDeckPlan` 减少页面内容或增加页面，不缩字硬塞。
- 当共享合同、三条呈现链、真实案例、逐页视觉 QA、全量门禁和真源回写全部通过，并由项目负责人确认视觉效果后，本 SPEC 才可收口。
