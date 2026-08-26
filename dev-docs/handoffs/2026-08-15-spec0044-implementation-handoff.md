# SPEC 0044 实现交接文档

> 交接日期：2026-08-15  
> 项目：实验报告助手  
> 当前工作区：`D:\\java_project\\lab-report-assistant`

## 1. 当前目标与已确认边界

本轮目标是把论文生成结果从“AI 工作流和工程追溯的展示”改成“标准化论文成品展示”。读者打开 Word/PDF 后，应优先看到格式规范、层级清晰、图表和正文自然部署的学术论文，而不是执行批次、产物索引、SHA-256、文件路径等工程追溯信息。

本轮已获项目负责人批准进入 SPEC 0044 实现。当前边界如下：

- 只实现 `ManuscriptPlan -> Word Renderer` 的论文成品化投影与排版；
- 不扩展 MCP；
- 不新增图表类型；
- 不改变统一大纲、证据卡片、执行记录和图表索引作为 Word/PPT 上游真源的原则；
- 工程追溯信息默认不进入读者正文，可作为后续显式审计附录能力保留配置入口；
- 本项目仍是本地单用户 Web MVP，不改变医学内容边界和受控 Python 执行边界。

## 2. 当前真源与文档状态

- 根级规则：`AGENTS.md`；
- 真源索引：`dev-docs/README.md`；
- SPEC：`dev-docs/specs/0044-standardized-paper-presentation-and-layout.md`；
- 启动决策：`dev-docs/decisions/0054-start-spec-0044-standardized-paper-presentation.md`；
- 相关前置实现：SPEC 0043 Word 论文生成与排版；
- 交接文档本身：本文件。

SPEC 0044 已进入实现阶段，但本轮尚未进行 git 提交或远程推送。完成最终验收后，应按项目规则更新 `dev-docs/acceptance.md`、`dev-docs/implementation-plan.md` 以及 SPEC 状态，再由项目负责人确认收口。

## 3. 已完成的实现

### 3.1 ManuscriptPlan 的读者优先投影

文件：`server/app/modules/outlines/document_planner.py`

- `PublicationProfile` 增加标准化论文版式参数：A4、页边距、标题/小标题/一级至三级标题字号、说明文字字号、正文颜色、灰度风格、读者优先开关和审计附录开关；
- 增加读者文本投影，将“本地执行产物”“执行批次”“执行产物”“结果索引”等工程化词汇转换为读者可理解的论文表达；
- 正式论文章节通过 `_project_reader_section()` 投影，输入结构不原地修改；
- 正式论文元数据过滤 `执行批次`、`execution_run_id`、`run_id`、`sha256`、`artifact_id`、`file_path`、JSON 路径等内部追溯字段；
- 正式论文仍保留正文需要的章节、表格、图表和引用关系；
- 非正式/兼容路径保留原有工程信息展示逻辑。

### 3.2 Word Renderer 的标准化论文成品输出

文件：`server/app/infrastructure/renderers/word_renderer.py`

- `render()` 先规划 `ManuscriptPlan`，再按正式论文 profile 配置文档；
- 正式论文默认使用统一黑白/灰度视觉，不再在页眉页脚展示“实验报告助手 ·”等产品/工程文案；
- 正式正文使用宋体/Times New Roman 组合、10.5pt、1.5 倍行距、首行两字符、两端对齐；
- 标题、一级至三级标题、图注、表注和图表说明使用独立样式；
- 封面、摘要、目录和主体章节按论文读者顺序组织；
- 正式正文默认隐藏 `Figure Lead`、`Artifact Source` 和工程追溯元数据；
- 图表使用动态 `SEQ Figure` / `SEQ Table` 编号；正文交叉引用使用 `REF` / `PAGEREF`；目录使用 Word `TOC` 字段；
- 正式图表说明改为读者可读的图注、表注和正文引用；
- 审计附录默认关闭，避免工程追溯重新污染论文成品；
- 正式前置部分增加“图表目录”方案，用于填充标准前置页并避免摘要/目录之后出现无意义空白页，同时保持前置页罗马数字和正文阿拉伯数字页码体系。

## 4. 测试与验收证据

已实际运行过的针对性命令：

```text
server/.venv/Scripts/python.exe -m py_compile server/app/modules/outlines/document_planner.py server/app/infrastructure/renderers/word_renderer.py
server/.venv/Scripts/python.exe -m pytest server/tests/test_spec0044_standardized_paper.py server/tests/test_spec0043_word_publication.py server/tests/test_spec0043_manuscript_rhythm.py -q
```

已知结果：针对性测试为 `10 passed`；Python 编译检查通过。

新测试文件：`server/tests/test_spec0044_standardized_paper.py`，覆盖：

- 正式论文隐藏工程字段和工程样式；
- 保留目录、`SEQ`、`REF`、`PAGEREF` 等正式 Word 字段；
- 正文、一级标题字号和正式文档 section 配置；
- ManuscriptPlan 读者投影不修改输入对象，并移除执行批次/执行产物等工程词汇。

真实生成命令：

```text
cd server
.venv/Scripts/python.exe scripts/generate_spec0035_paper_review.py
```

真实生成物：

- `server/dev-docs/e2e-screenshots/spec0035_paper_review/spec0043_publication.docx`
- `server/dev-docs/e2e-screenshots/spec0035_paper_review/spec0043_publication.pdf`
- `server/dev-docs/e2e-screenshots/spec0035_paper_review/publication_manifest.json`

已有静态检查证据：

- DOCX 含正式论文样式、目录字段、图表动态编号和交叉引用字段；
- 正式文档中未发现 `附录：执行产物索引`、`科研资产`、`SHA-256`、`渲染追溯`、`论证：`、`正文引用：`、`来源：执行产物` 等工程追溯展示；
- `执行批次`、`执行产物` 等词在生成 DOCX 中已清零；
- 之前生成结果约 20 页，包含封面、摘要、目录、图表目录和正文；具体页数需在图表目录最终补丁落盘后重新确认。

PDF 由项目的 `DocxPdfExporter` 生成并写入 manifest，未使用 LibreOffice。文档 skill 的 `render_docx.py` 因环境缺少 LibreOffice 无法执行；Poppler 直接渲染 PNG 可用，但伴随 `nameToUnicode` 字体资源警告，PNG 仍成功生成。最终交接前应重新生成一次，并完成关键页视觉检查。

## 5. 当前未闭合事项

以下事项是下一位 Agent 的优先工作，按顺序处理：

1. 核对“图表目录”补丁是否确实写入 `word_renderer.py`：搜索 `figure_table_catalog` 和 `图表目录`，并重新运行 `py_compile`；若补丁未落盘，用 `apply_patch` 或受控文本补丁补齐，避免直接在 PowerShell 中写入中文导致编码损坏。
2. 重新运行 SPEC 0044 定向测试和 SPEC 0043 定向测试。
3. 重新执行真实论文生成脚本，确认最终 DOCX/PDF/manifest 是同一版本。
4. 对最终 DOCX 做静态检查：无工程词汇、存在 `TOC`/`SEQ`/`REF`/`PAGEREF`、图表目录存在、正式样式存在、前置罗马页码与正文阿拉伯页码连续。
5. 对最终 PDF 做页数和关键页检查：封面、摘要、目录、图表目录、正文首章；确认目录后没有空白页，正文首章页码从 1 开始。
6. 用 Poppler 生成最终 PDF PNG，并查看至少第 1 页、第 4 页和正文前几页；若出现字体名异常、中文乱码或图表溢出，先定位 XML/renderer 源头再修复。
7. 检查 DOCX XML 中 `w:eastAsia` 字体名。历史实验产物中曾出现疑似编码异常的 `ثخجه`，需要确认当前正式生成物是否仍存在；若存在，修复字体写入路径后重新生成，不能只依赖 PDF 视觉结果。
8. 更新 `dev-docs/acceptance.md`、`dev-docs/implementation-plan.md` 和 SPEC 0044 的实现/验收状态，记录 LibreOffice 不可用及替代 PDF 证据。
9. 运行完整后端测试：

```text
server/.venv/Scripts/python.exe -m pytest
```

10. 最后只做 git 边界复核，不提交、不推送，等待项目负责人确认收口。检查：

```text
git status --short --untracked-files=all
git diff -- server/app/modules/outlines/document_planner.py server/app/infrastructure/renderers/word_renderer.py server/tests/test_spec0044_standardized_paper.py
```

## 6. 当前工作区与禁止事项

工作区存在大量用户已有修改和未跟踪生成物。必须保留，不得使用 `git reset --hard`、`git checkout --`、递归删除或大范围清理。尤其不要删除 `server/dev-docs/e2e-screenshots/spec0035_paper_review/` 下已有资料；只在必要时新增独立最终视觉检查目录。

本轮未授权：

- 不要 stage、commit 或 push；
- 不要扩展 MCP、DeepSeek 接入或新图表类型；
- 不要把审计字段重新塞回正文；
- 不要修改根级 `AGENTS.md`；
- 不要绕过 `ManuscriptPlan` 直接在 API/UI/prompt 中拼装论文真相；
- 不要把 LibreOffice 缺失伪装成已完成的 Word 渲染验收。

## 7. 推荐下一步与停止条件

推荐下一步是完成第 5 节的最终生成、静态检查、视觉检查和文档回写。若发现当前源码与 SPEC 0044、项目根规则或已有用户修改发生冲突，应先报告证据和影响，不要擅自删除旧字段、改变公共合同或重构无关模块。

只有在以下条件全部满足后，才可向项目负责人报告“SPEC 0044 实现验收完成”：

- 定向测试和完整后端测试通过；
- 最终 DOCX/PDF 来自同一份 ManuscriptPlan 版本；
- 正文不再展示 AI 工作流/工程追溯；
- 图表、图注、表注、目录和交叉引用可读且布局正常；
- 前置罗马页码、正文阿拉伯页码和章节分页正确；
- 验收文档和实施计划已回写；
- git 边界已复核，且未吸入用户无关改动。

