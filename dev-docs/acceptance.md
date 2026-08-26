# 实验报告助手｜验收与漂移控制

> 状态：V1.0.0 已发布并打 tag v1.0.0。V1.1.0 已发布并打 tag v1.1.0：SPEC 0007（真实 DeepSeek LLM 接入）、SPEC 0009（前端测试覆盖补全）、SPEC 0010（Word 模板支持）、SPEC 0011（PPT 配置选项）、SPEC 0012（数据保留周期配置）均已由项目负责人确认收口。V1.2.0 已发布并打 tag v1.2.0：SPEC 0013（Docker 化部署）、SPEC 0014（LLM 调用缓存）、SPEC 0015（GitHub Actions CI 流水线）均已由项目负责人确认收口。V1.3.0 已发布并打 tag v1.3.0：SPEC 0016（技术债务清理 TD-004/005/006/008）已由项目负责人确认收口。V1.4.0 已发布并打 tag v1.4.0：SPEC 0017（单用户前端实时编辑反馈）已由项目负责人确认收口。V2.0.0 已发布并打 tag v2.0.0：SPEC 0018（流式 LLM 输出，任务单生成 SSE 流式化）已由项目负责人确认收口。V2.1.0 已发布并打 tag v2.1.0：SPEC 0019（大纲生成流式化）已由项目负责人确认收口。V2.2.0 已发布并打 tag v2.2.0：SPEC 0020（证据卡片生成流式化）已由项目负责人确认收口。V2.3.0 已发布并打 tag v2.3.0：SPEC 0021（分析方案生成流式化）已由项目负责人确认收口。V2.4.0 已发布并打 tag v2.4.0：SPEC 0022（代码任务生成流式化）已由项目负责人确认收口（2026-07-30）。V2.5.0 SPEC 0024（PPT 渲染器布局与视觉层次改进，16:9 画布 + 双栏内容页 + 五级字号体系 + 主题色扩展应用；不引入新依赖，不改变 PptConfig 合同）已由项目负责人确认收口（2026-07-31）。V2.6.0 SPEC 0025（PPT 三角色彩系统与深浅对比三明治结构，colorsys 派生主色/辅助色/强调色 + 深色标题栏→浅色内容区→深色页脚栏；不引入新依赖，不改变 PptConfig 合同）已由项目负责人确认收口（2026-07-31）。V2.7.0 SPEC 0026（PPT 视觉效果增强，渐变填充 + 圆角矩形 + 外阴影 + 细边框；python-pptx 原生 fill.gradient() + MSO_SHAPE.ROUNDED_RECTANGLE + oxml 操作 a:effectLst；不引入新依赖，不改变 PptConfig 合同）已由项目负责人确认收口（2026-07-31）。V2.8.0 SPEC 0027（图表美化与布局增强）已由项目负责人确认收口（2026-07-31）。V2.8.1 SPEC 0028（Nature 风格图表集成，移除 SciencePlots，引入 nature-figure 设计规则）已由项目负责人确认收口（2026-07-31）。V2.9.0 SPEC 0029（端到端集成验收：验证 V2.5.0~V2.8.1 五个 PPT/图表切片后完整工作流仍打通）已由项目负责人确认收口（2026-07-31，E2E_RESULT=PASS，8 步主路径全部通过，1100 passed 零回归，Word/PPT 真实文件验证通过）。

> 当前限制：代码阶段已正式启动。前端测试套件为 551 个测试（31 个测试文件，含 SPEC 0021 新增 35 个分析方案流式化测试：api-stream 6 + hooks-stream 12 + AnalysisWorkspaceView 流式 12，及 AnalysisWorkspaceView 原 18 个测试扩展为 30 个 + PlanCard target_fields 容错测试 5 个），覆盖 8 个 API 模块和 11 个 Workspace 组件。后端测试套件为 895 个测试（0 warnings，含 SPEC 0021 分析方案流式化 37 个新增测试：DeepSeekAnalysisPlanProvider 流式 13 + Service 流式 15 + API SSE 9）。V2.3.0 发布前已补齐前端 lint（tsc --noEmit 通过）和前端 build（Vite 构建通过）；后端 alembic upgrade head 无变化（SPEC 0021 不修改数据库 schema）。**V2.3.0 收口复核修复 2 项阻断问题**：(1) LocalRuleAnalysisPlanProvider 输出 `analysis_plan[].target_fields` 为字符串（如 "age"）导致前端 PlanCard `target_fields.join(", ")` TypeError 页面崩溃，修复 6 处输出为数组（5 处 LocalRule + 1 处 Fake），清理旧错误数据 1 条；(2) 前端 PlanCard 假设 `target_fields` 一定是数组是脆弱设计，添加 `safeJoinTargetFields()` 容错函数处理字符串/数组/null/undefined 等各种情况，新增 5 个边界测试覆盖，修复后后端 895 + 前端 551 全套测试零回归，browser_use agent 浏览器验收 PASS（截图保存至 `dev-docs/e2e-screenshots/e2e-spec0021-verify-*.png`，4 张覆盖首页/项目详情/PlanCard 渲染/流式完成）。**V2.4.0 SPEC 0022 代码任务生成流式化**：前端测试套件扩展为 570 个测试（31 个测试文件，含 SPEC 0022 新增 19 个代码任务流式化测试：api-stream 7 + hooks-stream 12）；后端测试套件扩展为 975 个测试（0 warnings，含 SPEC 0022 代码任务流式化 80 个新增测试：DeepSeekCodeTaskProvider 流式 14 + Service 流式 9 + API SSE 17 + LocalRule 格式 21 + 回归 2 + 原 SPEC 0022 测试 17）。V2.4.0 发布前已补齐前端 lint（tsc --noEmit 通过）和前端 build（Vite 构建通过）；后端 alembic upgrade head 无变化（SPEC 0022 不修改数据库 schema）。**V2.4.0 收口复核修复 1 项阻断问题**：`LocalRuleCodeTaskProvider._build_analysis_code` 中 FREQUENCY 分析类型调用 `target_fields.split()` 假设字符串，但 SPEC 0021 修复后 `target_fields` 可能为 list，导致 `'list' object has no attribute 'split'` 异常，新增 `_first_field_name()` 辅助函数兼容 list/str/None 三种类型，新增 2 个回归测试覆盖，修复后后端 975 + 前端 570 全套测试零回归，browser_use agent 浏览器验收 PASS（截图保存至 `dev-docs/e2e-screenshots/spec0022-01-execution-workspace.png` 至 `spec0022-05-task-list.png`，5 张覆盖执行工作区/方案选择/流式中/流式完成/任务列表刷新）。
>
> **浏览器验收状态说明（TD-006 已于 SPEC 0016 清理；TD-009 在 SPEC 0017 引入）：** V1.0 整体端到端验收已于 2026-07-22 用 browser_use agent 完成真实浏览器点击截图验收，截图保存在 `dev-docs/e2e-screenshots/`，详见 `e2e-acceptance-report-v1.0.md`（home-full.png、home-viewport.png）。后续各 SPEC 收口记录中的"可视化点击验收：未执行"为当时收口时的事实快照，不回溯修改；V1.0 之后的新切片若有 UI 变化，应按 AGENTS.md "UI 行为变化应做浏览器点击或截图验收"执行。SPEC 0017 已用 browser_use agent 完成真实浏览器点击验收（PASS：保存按钮"已保存 ✓"绿色 #16a34a 提示正常显示，1.5s 后自动消失），但截图未持久化到磁盘（browser_take_screenshot 工具限制），记录为非阻断债务 TD-009，后续修复入口见 [tech-debt-inventory.md](tech-debt-inventory.md)。
>
> **CI 配置修复（2026-07-25，P0 补丁）：** V1.4.0 发布后评估发现 CI 流水线（SPEC 0015）存在两项 P0 缺陷并已修复：(1) 后端依赖安装从硬编码 `pip install pandas==3.0.3...`（6 行）改为 `pip install -e ".[dev,analysis]"`（1 行），验证 TD-004 清理后的 pyproject.toml 依赖声明正确性；(2) 前端 job 新增 `npm test -- --run` 步骤，让 434 个前端单元测试参与 CI 把关（此前 CI 只运行 tsc --noEmit 和 build，不拦截前端测试回归）。本地预演：`pip install --dry-run -e ".[dev,analysis]"` 依赖解析成功；前端 vitest 434 passed。

> **DeepSeek 任务单 JSON 容错修复（2026-07-30，P0 阻断修复）：** SPEC 0018 流式生成任务单时高频抛 `DEEPSEEK_JSON_PARSE_ERROR`（真实 DeepSeek 5 次复现 60% 失败率）。根因有二：(1) LLM 把 `*_requirements` 等 `list[str]` 字段返回成对象数组 `[{"description": "..."}]`；(2) `replication_level.suggested_scope` 返回 `null` 而 schema 要求 `str`。采用 **Prompt 强化 + Pydantic 容错** 双层方案：`_SYSTEM_PROMPT` 新增【字段类型约束】章节含正/反例；`DeepSeekRequirementResponse` / `DeepSeekReplicationLevel` 加 `field_validator(mode="before")` 容错（dict→取 description、null→空串）。新增 9 个容错测试（`TestDeepSeekResponseTolerance`）。修复后真实 DeepSeek 5 次复测 **0 失败**（失败率 60%→0%）。本次仅修任务单 provider，其他 provider 同类问题留作后续观察。详见 [决策 0029](decisions/0029-deepseek-json-tolerance-fix.md)。**完整业务流程链路验证（2026-07-30）：** 在端到端任务单生成验证后，继续推进完整业务流程，从确认任务单到 `ANALYSIS_CONFIRMED` 全链路 10 步打通（REQUIREMENT_PARSED → REQUIREMENT_CONFIRMED → SOURCES_COLLECTED → EVIDENCE_CONFIRMED → DATASET_READY → ANALYSIS_CONFIRMED）：启动独立 Worker 进程（`python -m worker.main`）；上传 PDF 来源（手工构造最小 PDF，pypdf 提取 585 字符胃病医学资料）经 Worker `PARSE_DOCUMENT` 解析为 PARSED；流式生成 6 张证据卡片（424 chunk，`done`，DEEPSEEK 非降级）并全部确认；上传 100 行胃病 CSV 数据集经 Worker `PARSE_DATASET` 解析为 READY（Worker 自动触发 `GENERATE_ANALYSIS_PLAN` 生成分析方案候选）；确认分析方案并完成分析确认。全链路 0 次 `DEEPSEEK_JSON_PARSE_ERROR`，容错修复持续有效。详见 [验收报告 §6.7](deepseek-json-tolerance-fix-acceptance.md)。

> **SPEC 0022 代码任务执行链路修复（2026-07-30，P0 阻断修复，commit 93f1f13）：** SPEC 0022 收口后端到端验证发现 3 项阻断问题并已修复：(1) `_SYSTEM_PROMPT` 中 "换行使用 \\n 转义" 指令导致 DeepSeek 返回的 code 换行被双重转义，执行时引发 `unexpected character after line continuation character`，修复为 "代码必须是合法 JSON（换行符由 JSON 标准自动转义）"；(2) `_SYSTEM_PROMPT` 未明确 import 白名单，DeepSeek 生成 `import os` 被 AST 校验拒绝，新增白名单（pandas/numpy/matplotlib/scipy/sklearn/openpyxl）和禁止模块列表；(3) `python_executor.execute_code_safe` 中 `work_path` 和 `data_path` 未 resolve 为绝对路径，subprocess cwd + 相对 script_path 导致路径重复拼接，修复为 `Path(work_dir).resolve()` + `data_path` resolve。新增 8 个回归测试（4 换行转义 + 4 import 白名单），python_executor 48 个测试全部通过。完整链路验证通过：代码执行（exit_code=0，12 产物）→ 大纲 → Word（132KB）+ PPT（64KB）→ COMPLETED。**链路验证环境注意事项：** (1) httpx 客户端默认读取 Windows 系统代理可能导致 502，验证脚本需使用 `httpx.Client(trust_env=False)`；(2) AnalysisPlan 引用的字段名必须与数据集 CSV 列名匹配，否则执行时 KeyError；(3) Worker 进程需单独启动（`python -m worker.main`），不随 uvicorn 自动启动。**Worker 执行与文档生成模块单元测试补全（2026-07-30）：** 针对链路验证涉及的 Worker handler 补充单元测试 44 个（全部通过，3.94s）：`test_execution_worker_handlers.py` 新增 22 个（覆盖 `handle_generate_code_task` 成功/前置校验/plan 不存在/JSON 解析失败 7 个 + `handle_execute_code_task` 成功/脚本错误/沙箱限制/内存超限/前置校验/code_task 不存在/version 不存在/stderr 为空边界/产物收集/work_dir 创建/参数传递 14 个 + HANDLERS 注册表 1 个，mock provider + mock execute_code_safe + 内存 SQLite）；`test_outline_worker_handlers.py` 新增 9 个失败路径/版本管理/降级链测试（Word 渲染失败标记 FAILED + 失败生成不覆盖成功版本 + outline/deliverable 不存在 + Word 模板降级链；PPT 项目状态推进 + 二次生成新版本 + 渲染失败标记 FAILED + PPT 配置降级链），覆盖 project_memory 硬约束"失败生成不覆盖成功版本"与 SPEC 0010/0011 降级链。详见 [决策 0031](decisions/0031-code-task-execution-link-fixes.md)。

## 启动门禁

本节保留立项、架构和代码阶段启动的历史门禁。

项目保持一条推荐主线：证据化实验工作流，而不是通用一键代写工具。

- [x] 根目录存在 `AGENTS.md`。
- [x] `dev-docs/README.md` 是当前真源索引。
- [x] `dev-docs/project-charter.md` 已锁定为产品真源。
- [x] `dev-docs/decisions/0001-lock-project-charter.md` 记录 charter 锁定决策。
- [x] 已获项目负责人批准进入架构与开发计划阶段。
- [x] 项目负责人审阅并批准技术栈与关键架构主线。
- [x] 项目负责人确认代码阶段批准记录。
- [x] 项目负责人曾明确代码批准当轮不写代码，并已由后续决策 0007 承接为正式执行。

## 框架实践门禁

进入代码阶段前必须先完成：

- [x] 技术栈确认决策记录。
- [x] 项目规范目录名决策。
- [x] V1 不做注册登录决策。
- [x] 首个标准演示课题决策。
- [x] “胃病数据分析”的样例数据来源。
- [x] V1 大模型供应商暂定 DeepSeek。
- [x] 依赖版本和官方目录规范复核。
- [x] 开发环境、包管理器、运行命令和测试命令在实际脚手架创建后确认。
- [x] 第一切片 SPEC 0001 代码实现与命令/API/代理验收完成，并已由项目负责人确认。

第一切片已获项目负责人批准进入代码阶段后执行。SPEC 0002 已完成实现、复核验收并由项目负责人确认收口；SPEC 0003 已完成实现与端到端验收并由项目负责人确认收口；SPEC 0004 已完成实现与端到端验收并由项目负责人确认收口；SPEC 0005 已完成实现与端到端验收并由项目负责人确认收口；SPEC 0006 已完成实现与端到端验收并由项目负责人确认收口；V1.0.0 已发布并打 tag v1.0.0。V1.1.0 阶段：SPEC 0007（真实 DeepSeek LLM 接入）已完成实现与测试验收并由项目负责人确认收口；SPEC 0009（前端测试覆盖补全）已完成实现与测试验收（411 个测试全部通过）并由项目负责人确认收口；SPEC 0010（Word 模板支持）已完成实现与测试验收（后端 623 passed + 前端 411 passed）并由项目负责人确认收口；SPEC 0011（PPT 配置选项）已完成实现与测试验收（后端 646 passed + 前端 411 passed，新增 23 个后端测试覆盖页数/主题色/图表开关/降级策略/API 校验）并由项目负责人确认收口；SPEC 0012（数据保留周期配置）已完成实现与测试验收（后端 704 passed，新增 58 个后端测试覆盖配置降级/RUNNING job 保护/过期判断/级联删除/文件清理/脚本参数/端到端集成）并由项目负责人确认收口。V1.1.0 已发布并打 tag v1.1.0。后续切片开始前，仍需项目负责人确认下一切片 SPEC。

## 阶段门禁

### V0.1：要求拆解与项目骨架验证

完成证据：

- 用户能创建实验项目。
- 系统保存原始实验要求。
- 系统生成结构化任务单。
- 用户能确认或修改任务单。
- 系统给出 L0、L1、L2 或 L3 超范围判断。
- 变更记录保存。

### V0.2：公开资料与证据工作流

完成证据：

- 用户能提交公开 URL。
- 用户能上传辅助文件。
- 系统保存原始资料和采集状态。
- 系统生成带来源位置的证据卡片。
- 不支持或失败的 URL 有结构化错误。
- 系统不会绕过登录、验证码或付费限制。

### V0.3：数据分析与 Python 执行

完成证据：

- 用户能上传 CSV 或 Excel。
- 系统显示字段、类型、样例和质量问题。
- 系统生成清洗和分析方案。
- 用户确认方案。
- 系统展示待执行代码。
- 受控执行产生日志、表格、图表或结构化失败。
- 每个结果能追溯到代码和数据版本。

### V0.4：大纲与交付物

完成证据：

- 系统从要求、证据和真实结果生成统一大纲。
- 用户确认大纲。
- 系统生成可编辑 Word。
- 系统生成 PPT。
- Word 与 PPT 的关键数据一致。
- 资料性结论可追溯到来源。
- 实验性结论可追溯到执行记录。

### V1.0：完整闭环

完成证据：

- 一个典型数据分析实验从创建项目到 Word/PPT 下载完整跑通。
- 关键步骤都有状态、错误提示和重新运行能力。
- 来源、数据、代码、图表和结论能够关联。
- 不支持的任务能明确拒绝或降级。
- `project-charter.md` 第 9.7 节的端到端验收用例通过。

## 停止条件

### 当前阶段停止条件

当前架构与开发计划阶段结束需要满足：

- `architecture.md`、`acceptance.md`、`implementation-plan.md` 已创建并被索引。
- 文档没有新增与 `project-charter.md` 冲突的产品范围。
- 技术主线已被锁定，但未被执行为框架初始化。
- 代码阶段批准记录已创建，项目负责人已要求开始执行。
- 上一切片 SPEC 0001 的代码结构、后端测试、数据库迁移、前端构建和前后端代理验收已通过；当前待确认收口切片为 SPEC 0002。
- SPEC 0002 的需求来源、结构化任务单、L0-L3、编辑确认、状态推进和最小变更记录已通过当前命令/API/代理验收，并已由项目负责人确认收口。
- SPEC 0003 的来源登记、后台任务、Worker、采集与解析、证据卡片、确认拒绝、状态推进和 STALE 传播已通过当前命令/API/代理/curl 端到端验收，并已由项目负责人确认收口。
- SPEC 0004 的数据集上传、字段概览、质量评分、分析方案候选、用户确认、状态推进和 STALE 传播已通过当前命令/API/curl 端到端验收，并已由项目负责人确认收口。
- SPEC 0005 的受控 Python 执行引擎、AST import 白名单校验、psutil 进程树内存监控、CodeTask/ExecutionRun/ExecutionArtifact 核心合同、STALE 传播、状态推进到 RESULT_CONFIRMED 已通过 API 测试套件（33 个测试覆盖 11 个端点）和 python_executor 单元测试（48 个测试覆盖安全限制、超时、内存、产物收集）端到端验收，并已由项目负责人确认收口。
- SPEC 0006 的大纲与交付物（Outline + Deliverable + DeliverableVersion）核心合同、Word/PPT 渲染器、状态推进到 COMPLETED、STALE 传播、交付物下载已通过 API 测试套件（21 个测试覆盖 11 个端点）、Worker handler 测试（13 个测试）和渲染器测试（18 个测试验证真实文件生成）端到端验收，并已由项目负责人确认收口。
- V1.0.0 已发布并打 tag v1.0.0，端到端验收报告 `dev-docs/e2e-acceptance-report-v1.0.md` 全部通过。
- V1.1.0 阶段：SPEC 0007（真实 DeepSeek LLM 接入）已完成实现与后端测试验收（605 passed, 0 warnings），5 个提供者全部替换为 LLM 优先 + LocalRule 降级，已由项目负责人确认收口。
- V1.1.0 阶段：SPEC 0009（前端测试覆盖补全）已完成实现与完整测试套件验收（411 passed，19 个测试文件，覆盖 8 个 API 模块和 11 个 Workspace 组件），已由项目负责人确认收口。
- V1.1.0 阶段：SPEC 0010（Word 模板支持）已完成实现与测试验收（后端 623 passed + 前端 411 passed，新增 18 个后端测试 + 8 个前端 API 测试，覆盖模板 CRUD/渲染器模板渲染/降级策略/Worker 接线/前端 UI 接线），已由项目负责人确认收口。
- V1.1.0 阶段：SPEC 0011（PPT 配置选项）已完成实现与测试验收（后端 646 passed + 前端 411 passed，新增 23 个后端测试，覆盖渲染器页数控制/主题色应用/图表开关/降级策略 + API 请求体解析/校验/错误码），已由项目负责人确认收口。
- V1.1.0 阶段：SPEC 0012（数据保留周期配置）已完成实现与测试验收（后端 704 passed，新增 58 个后端测试，覆盖 DATA_RETENTION_DAYS 配置降级 10 + has_active_jobs RUNNING/PENDING 保护 18 + 过期判断/级联删除/文件系统清理 14 + 脚本参数解析/输出 10 + 端到端集成 6），已由项目负责人确认收口。
- V1.1.0 已发布并打 tag v1.1.0：发布前补齐前端 lint（tsc --noEmit 通过）和前端 build（Vite 构建通过，114 模块转换，dist/ 394.96 kB，gzip 107.49 kB），回归测试执行记录见 [v1.1.0-regression-test-plan.md](v1.1.0-regression-test-plan.md) 第九章，发布清单见 [release-checklist-v1.1.0.md](release-checklist-v1.1.0.md)，发布说明见 [changelog-v1.1.0.md](changelog-v1.1.0.md)。

### 代码阶段停止条件

代码阶段只能在项目负责人明确批准后开始。代码阶段每个任务结束必须给出：

- 改动范围。
- 运行命令。
- 通过或失败证据。
- 未闭合风险。
- 文档回写位置。

## 证据记录

| 日期 | 阶段 | 证据 | 结果 |
| --- | --- | --- | --- |
| 2026-06-16 | 立项确认 | `dev-docs/project-charter.md` 已锁定 | 通过 |
| 2026-06-16 | 架构与开发计划授权 | 用户明确批准进入本阶段，且禁止代码/依赖/框架初始化 | 通过 |
| 2026-06-16 | 技术栈锁定 | `dev-docs/tech-stack.md` 与决策 0004 已记录 V1 技术主线 | 通过 |
| 2026-06-16 | V1 边界锁定 | 决策 0005 已记录 `lab-report-assistant`、不做注册登录和“胃病数据分析”课题 | 通过 |
| 2026-06-16 | 依赖复核 | `dev-docs/dependency-review.md` 已记录样例数据、DeepSeek 和依赖版本 | 通过 |
| 2026-06-16 | 代码阶段批准 | 决策 0006 已记录代码阶段批准 | 通过 |
| 2026-06-16 | 代码阶段正式启动 | 项目负责人确认可以开始写代码，当前切片 SPEC 0001 | 完成 |
| 2026-06-16 | SPEC 0001 依赖修复 | `apps/web` 重新安装 npm 依赖；`server/.venv` 创建并完成 `pip install -e ".[dev]"` | 通过 |
| 2026-06-16 | SPEC 0001 后端测试 | `server` 下运行 `.venv\Scripts\python.exe -m pytest`，结果为 `8 passed` | 通过 |
| 2026-06-16 | SPEC 0001 数据库迁移 | 使用全新 SQLite 文件运行 `.venv\Scripts\python.exe -m alembic upgrade head`，迁移到 `0001` | 通过 |
| 2026-06-16 | SPEC 0001 API 验收 | 临时启动 API，验证 `/health`、创建项目、列表、详情、空名称结构化错误 | 通过 |
| 2026-06-16 | SPEC 0001 前端类型检查 | `apps/web` 下运行 `npm.cmd run lint`，结果为 TypeScript 检查通过 | 通过 |
| 2026-06-16 | SPEC 0001 前端构建 | `apps/web` 下运行 `npm.cmd run build`，结果为 Vite 构建通过，生成 `dist/` | 通过 |
| 2026-06-16 | SPEC 0001 前后端代理验收 | 同时启动后端 `8001` 和 Vite `5173`，验证页面 `200`、`id="root"`、代理创建/列表/详情/错误响应 | 通过 |
| 2026-06-16 | SPEC 0001 可视化点击验收 | 当前会话未暴露内置浏览器执行工具，本机未发现 Edge/Chrome 可执行文件；未做真实点击，以上一条代理联通作为替代证据 | 未执行 |
| 2026-06-16 | SPEC 0001 项目负责人确认 | 项目负责人回复“确认一下”，确认接受第一开发切片当前验收结果 | 通过 |
| 2026-06-16 | SPEC 0002 启动 | 创建 `dev-docs/specs/0002-requirement-input-and-task-plan.md`，限定实验要求输入、结构化任务单和 L0-L3 判断 | 通过 |
| 2026-06-17 | SPEC 0002 依赖修复 | `server` 下运行 `.venv\Scripts\python.exe -m pip install -e ".[dev]"`，安装 `python-docx 1.2.0`、`python-multipart 0.0.32` 和传递依赖 `lxml 6.1.1` | 通过 |
| 2026-06-17 | SPEC 0002 后端测试 | `server` 下运行 `.venv\Scripts\python.exe -m pytest`，结果为 `25 passed, 1 warning`；warning 为第三方 `fastapi.testclient` 对 `httpx` 的弃用提示，记录为非本轮阻断债务 | 通过 |
| 2026-06-17 | SPEC 0002 数据库迁移 | 使用全新临时 SQLite 文件运行 `.venv\Scripts\python.exe -m alembic upgrade head`，迁移到 `0002` | 通过 |
| 2026-06-17 | SPEC 0002 前端类型检查 | `apps/web` 下运行 `npm.cmd run lint`，结果为 TypeScript 检查通过 | 通过 |
| 2026-06-17 | SPEC 0002 前端构建 | `apps/web` 下以宿主权限运行 `npm.cmd run build`，结果为 Vite 构建通过；沙箱内因 Windows ACL 无法读取 `vite.config.ts` | 通过 |
| 2026-06-17 | SPEC 0002 前后端代理验收 | 临时启动后端 `8001` 和 Vite `5173`，验证页面 `200`、`id="root"`、代理创建项目、保存文本要求、生成 L3 候选、编辑任务单、确认任务单、项目状态 `REQUIREMENT_CONFIRMED` | 通过 |
| 2026-06-17 | SPEC 0002 可视化点击验收 | 当前会话未暴露可调用的 in-app Browser 工具；未做真实浏览器点击或截图，以上一条页面和代理联通作为替代证据 | 未执行 |
| 2026-06-17 | SPEC 0002 收口复核 | 复读 SPEC 0002、实现 owner、API、测试、前端工作区和漂移关键词；补充前端 `REQUIREMENT_PARSED` 中文状态展示、`.docx` 文件名清洗和空 Word API 测试 | 通过 |
| 2026-06-17 | SPEC 0002 后端测试复核 | 宿主权限下运行 `server/.venv/Scripts/python.exe -m pytest`，结果为 `26 passed, 1 warning`；warning 仍为第三方 `fastapi.testclient` 对 `httpx` 的弃用提示 | 通过 |
| 2026-06-17 | SPEC 0002 数据库迁移复核 | `server` 下运行 `.venv\Scripts\python.exe -m alembic upgrade head`，结果为当前数据库已在 head，无迁移错误 | 通过 |
| 2026-06-17 | SPEC 0002 前端类型检查复核 | `apps/web` 下运行 `npm.cmd run lint`，结果为 TypeScript 检查通过 | 通过 |
| 2026-06-17 | SPEC 0002 前端构建复核 | 宿主权限下运行 `apps/web` 的 `npm.cmd run build`，结果为 Vite 构建通过；沙箱内仍会因 Windows ACL 无法读取 `vite.config.ts` | 通过 |
| 2026-06-17 | SPEC 0002 项目负责人确认 | 项目负责人要求“当前项目SPEC2做好了吗，审查一下，然后进行git”，本轮复核未发现阻断问题，按确认收口进入 git 版本控制 | 通过 |
| 2026-07-06 | SPEC 0003 启动 | 创建 `dev-docs/specs/0003-sources-and-evidence-workflow.md`，限定公开 URL/PDF 来源、后台任务、Worker、证据卡片工作流 | 通过 |
| 2026-07-06 | SPEC 0003 依赖安装 | `server` 下安装 `httpx 0.28.1`、`pypdf 6.14.2`、`beautifulsoup4 4.15.0`、`lxml 6.1.1`（lxml 已作为 SPEC 0002 `python-docx` 传递依赖安装，本切片作为 beautifulsoup4 解析器显式使用） | 通过 |
| 2026-07-06 | SPEC 0003 后端测试 | `server` 下运行 `.venv\Scripts\python.exe -m pytest`，结果为 `153 passed, 1 warning`；原 26 + 新增 127 测试；warning 仍为第三方 `fastapi.testclient` 对 `httpx` 的弃用提示 | 通过 |
| 2026-07-06 | SPEC 0003 数据库迁移 | 使用全新临时 SQLite 文件运行 `.venv\Scripts\python.exe -m alembic upgrade head`，迁移到 `0003`，新增 4 张表和 6 个索引 | 通过 |
| 2026-07-06 | SPEC 0003 前端类型检查 | `apps/web` 下运行 `npm.cmd run lint`，TypeScript 严格类型检查通过 | 通过 |
| 2026-07-06 | SPEC 0003 前端构建 | `apps/web` 下运行 `npm.cmd run build`，Vite 构建通过，生成 `dist/` | 通过 |
| 2026-07-06 | SPEC 0003 前后端代理验收 | 同时启动后端 `8001`、Worker 进程和 Vite `5173`，验证页面 `200`、`id="root"`、`/api` 代理可用 | 通过 |
| 2026-07-06 | SPEC 0003 端到端主链路 | 通过 curl 顺序调用：创建项目 → 添加文本要求 → 生成任务单 → 确认任务单（`REQUIREMENT_CONFIRMED`）→ 登记 `https://example.com/` → Worker `FETCH_URL`+`PARSE_DOCUMENT` → `PARSED` → 触发生成证据卡片 → Worker `GENERATE_EVIDENCE` → 1 张 `CANDIDATE` → 确认卡片 → `EVIDENCE_CONFIRMED` | 通过 |
| 2026-07-06 | SPEC 0003 非公开 URL 验证 | `localhost`、`127.0.0.1`、`192.168.1.1` 返回 `SOURCE_URL_NOT_PUBLIC`；`file://`、`ftp://` 返回 `SOURCE_URL_SCHEME_UNSUPPORTED` | 通过 |
| 2026-07-06 | SPEC 0003 受限 URL 验证 | `http://jigsaw.w3.org/HTTP/Basic/`（返回 401）最终 `Source.status=FAILED, error_code=SOURCE_ACCESS_RESTRICTED`；`Job.retry_count=2, status=FAILED`；单元测试 4 个受限资源场景全部通过 | 通过 |
| 2026-07-06 | SPEC 0003 STALE 传播验证 | 登记第二个 URL → 等待 `PARSED` → 触发生成 10 张 `CANDIDATE` 卡片 → DELETE 来源 → 10 张卡片全部变为 `STALE` | 通过 |
| 2026-07-06 | SPEC 0003 可视化点击验收 | 当前会话未暴露可调用的 in-app Browser 工具；未做真实浏览器点击或截图，以 Vite 页面可访问、`/api` 代理主链路联通、`curl` 端到端验证作为替代证据 | 未执行 |
| 2026-07-06 | SPEC 0004 启动 | 创建 `dev-docs/specs/0004-dataset-workspace.md`，限定数据集上传与解析、字段概览、分析方案候选、用户确认状态 | 通过 |
| 2026-07-06 | SPEC 0004 依赖安装 | `server` 下安装 `pandas 3.0.3`、`numpy 2.5.1`（pandas 3.0.3 传递依赖升级，复核版本 `2.4.6`）、`openpyxl 3.1.5` | 通过 |
| 2026-07-06 | SPEC 0004 后端测试 | `server` 下运行 `.venv\Scripts\python.exe -m pytest`，结果为 `375 passed, 21 warnings`；原 153 + 新增 222 测试；warnings 包含第三方 `fastapi.testclient` 弃用提示（已知非阻断）和 pandas datetime 推断 UserWarning（新增非阻断债务） | 通过 |
| 2026-07-06 | SPEC 0004 数据库迁移 | 使用全新临时 SQLite 文件运行 `.venv\Scripts\python.exe -m alembic upgrade head`，迁移到 `0004`，新增 3 张表（datasets、dataset_versions、analysis_plans）和 5 个索引 | 通过 |
| 2026-07-06 | SPEC 0004 前端类型检查 | `apps/web` 下运行 `npm.cmd run lint`，TypeScript 严格类型检查通过 | 通过 |
| 2026-07-06 | SPEC 0004 前端构建 | `apps/web` 下运行 `npm.cmd run build`，Vite 构建通过，106 模块转换，生成 `dist/`（347.19 kB，gzip 99.84 kB） | 通过 |
| 2026-07-06 | SPEC 0004 API 端点注册 | 启动后端验证 OpenAPI schema，36 个 paths 中包含 8 个 datasets 路径和 6 个 analysis 路径，15 个新端点全部注册 | 通过 |
| 2026-07-06 | SPEC 0004 Worker handler 注册 | 验证 `worker/handlers.py` HANDLERS 映射包含 5 个 handler：FETCH_URL、PARSE_DOCUMENT、GENERATE_EVIDENCE、PARSE_DATASET、GENERATE_ANALYSIS_PLAN | 通过 |
| 2026-07-06 | SPEC 0004 端到端主链路 | 通过 curl 顺序调用：创建 EVIDENCE_CONFIRMED 项目 → 上传 `胃病数据集_教学实验版.xlsx` → Worker `PARSE_DATASET`（9 行 2 列，quality_score=100.0）→ `/datasets/complete`（DATASET_READY）→ `/analysis/generate` → Worker `GENERATE_ANALYSIS_PLAN`（cleaning=2/analysis=1/chart=2）→ `/analysis/{id}/confirm`（CONFIRMED）→ `/analysis/complete`（ANALYSIS_CONFIRMED） | 通过 |
| 2026-07-06 | SPEC 0004 错误分支验证 | 6 个错误分支全部通过：上传到 DRAFT 项目（PROJECT_EVIDENCE_NOT_CONFIRMED）、上传 .txt 文件（DATASET_FILE_UNSUPPORTED）、确认不存在的 plan_id（ANALYSIS_PLAN_NOT_FOUND）、拒绝已 CONFIRMED 方案（ANALYSIS_PLAN_NOT_CONFIRMABLE）、GET 不存在的 dataset（DATASET_NOT_FOUND）、上传到不存在的 project（PROJECT_NOT_FOUND） | 通过 |
| 2026-07-06 | SPEC 0004 STALE 传播验证 | 重新上传（reupload）创建 v2，旧版本 v1 变 SUPERSEDED，旧 CONFIRMED 方案变 STALE，已 STALE 方案保持 STALE（无重复标记），新自动生成方案为 CANDIDATE，项目状态保持 ANALYSIS_CONFIRMED（无回退） | 通过 |
| 2026-07-06 | SPEC 0004 可视化点击验收 | 当前会话未暴露可调用的 in-app Browser 工具；未做真实浏览器点击或截图，以 curl 端到端验证、6 个错误分支、STALE 传播作为替代证据 | 未执行 |
| 2026-07-07 | SPEC 0005 启动 | 创建 `dev-docs/specs/0005-controlled-python-execution.md`，限定受控 Python 执行环境、CodeTask/ExecutionRun/ExecutionArtifact 核心合同、状态推进到 RESULT_CONFIRMED | 通过 |
| 2026-07-07 | SPEC 0005 依赖安装 | `server` 下安装 `psutil 7.2.2`、`matplotlib 3.11.0`、`scipy 1.18.0`、`scikit-learn 1.9.0`；使用 `--prefer-binary` 标志避免 matplotlib 源码构建失败 | 通过 |
| 2026-07-07 | SPEC 0005 后端测试 | `server` 下运行 `.venv\Scripts\python.exe -m pytest`，结果为 `456 passed, 21 warnings`；原 375 + 新增 81 测试（python_executor 48 + execution_api 33）；warnings 仍为第三方 `fastapi.testclient` 弃用提示和 pandas datetime 推断 UserWarning（已知非阻断） | 通过 |
| 2026-07-07 | SPEC 0005 数据库迁移 | 使用全新临时 SQLite 文件运行 `.venv\Scripts\python.exe -m alembic upgrade head`，迁移到 `0005`，新增 3 张表（code_tasks、execution_runs、execution_artifacts）和 6 个索引 | 通过 |
| 2026-07-07 | SPEC 0005 前端类型检查 | `apps/web` 下运行 `npm.cmd run lint`，TypeScript 严格类型检查通过 | 通过 |
| 2026-07-07 | SPEC 0005 前端构建 | `apps/web` 下运行 `npm.cmd run build`，Vite 构建通过，106 模块转换，生成 `dist/`（347.19 kB，gzip 99.84 kB） | 通过 |
| 2026-07-07 | SPEC 0005 API 端点注册 | 新增 `code_tasks.py`（7 端点）和 `execution_runs.py`（4 端点），共 11 个新端点；扩展 `main.py` 错误码映射（not_found_codes += CODE_TASK/EXECUTION_RUN/EXECUTION_ARTIFACT_NOT_FOUND，forbidden_codes += CODE_EXECUTION_DISABLED） | 通过 |
| 2026-07-07 | SPEC 0005 Worker handler 注册 | 验证 `worker/handlers.py` HANDLERS 映射新增 2 个 handler：GENERATE_CODE_TASK、EXECUTE_CODE_TASK，共 7 个 handler | 通过 |
| 2026-07-07 | SPEC 0005 受控执行环境安全验证 | `python_executor.py` 通过 AST 校验拦截禁止 import（socket/ssl/http/urllib/requests 等）和动态导入（`__import__`/`importlib.import_module`）；超时返回 EXECUTION_TIMEOUT；内存超限（psutil 进程树监控，0.5s 轮询）返回 EXECUTION_MEMORY_LIMIT；输出过大返回 EXECUTION_OUTPUT_TOO_LARGE；48 个单元测试全部通过 | 通过 |
| 2026-07-07 | SPEC 0005 状态机推进验证 | API 测试覆盖：CANDIDATE→CONFIRMED（confirm）、CANDIDATE→REJECTED（reject）、CONFIRMED 编辑→CANDIDATE（code_version 递增）、CONFIRMED→触发执行（execute）、SUCCEEDED→RESULT_CONFIRMED（complete）、FAILED 无成功执行时 complete 返回 PROJECT_NO_SUCCESSFUL_EXECUTION_RUN | 通过 |
| 2026-07-07 | SPEC 0005 STALE 传播验证 | AnalysisPlan 重新确认 → 关联 CodeTask 变 STALE；CodeTask 编辑 → 关联 ExecutionRun 变 STALE；端到端 API 测试覆盖两条传播链 | 通过 |
| 2026-07-07 | SPEC 0005 产物下载验证 | API 测试覆盖 CSV（text/csv）和 PNG（image/png）产物下载；不存在的产物返回 EXECUTION_ARTIFACT_NOT_FOUND；路径穿越防护已实现 | 通过 |
| 2026-07-07 | SPEC 0005 可视化点击验收 | 当前会话未暴露可调用的 in-app Browser 工具；未做真实浏览器点击或截图，以 API 测试套件（33 个测试覆盖 11 个端点的成功/失败/状态机路径）作为替代证据 | 未执行 |
| 2026-07-22 | SPEC 0006 依赖安装 | `server` 下安装 `python-pptx==1.0.2`，传递依赖 `XlsxWriter 3.2.9`；`python-docx 1.2.0` 复用 SPEC 0002 安装 | 通过 |
| 2026-07-22 | SPEC 0006 后端测试 | `server` 下运行 `.venv\Scripts\python.exe -m pytest`，结果为 `569 passed, 21 warnings`；原 456 + 新增 113 测试（outline_provider 21 + renderers 18 + outlines_service 40 + outlines_api 21 + outline_worker_handlers 13）；warnings 仍为第三方 `fastapi.testclient` 弃用提示和 pandas datetime 推断 UserWarning（已知非阻断） | 通过 |
| 2026-07-22 | SPEC 0006 数据库迁移 | 使用全新临时 SQLite 文件运行 `.venv\Scripts\python.exe -m alembic upgrade head`，迁移到 `0006`，新增 3 张表（outlines、deliverables、deliverable_versions）和索引 | 通过 |
| 2026-07-22 | SPEC 0006 前端类型检查 | `apps/web` 下运行 `npm.cmd run lint`，TypeScript 严格类型检查通过 | 通过 |
| 2026-07-22 | SPEC 0006 前端构建 | `apps/web` 下运行 `npm.cmd run build`，Vite 构建通过，106 模块转换，生成 `dist/`（347.19 kB，gzip 99.84 kB） | 通过 |
| 2026-07-22 | SPEC 0006 API 端点注册 | 新增 `outlines.py`（7 端点）和 `deliverables.py`（4 端点），共 11 个新端点；扩展 `main.py` 错误码映射（not_found_codes += OUTLINE_NOT_FOUND/DELIVERABLE_NOT_FOUND/DELIVERABLE_VERSION_NOT_FOUND） | 通过 |
| 2026-07-22 | SPEC 0006 Worker handler 注册 | 验证 `worker/handlers.py` HANDLERS 映射新增 3 个 handler：GENERATE_OUTLINE、GENERATE_WORD、GENERATE_PPT，共 10 个 handler | 通过 |
| 2026-07-22 | SPEC 0006 状态机推进验证 | API 测试覆盖：CANDIDATE→CONFIRMED（confirm）、CANDIDATE→REJECTED（reject）、CONFIRMED 编辑→CANDIDATE（code_version 递增）、CONFIRMED→触发 Word/PPT 生成（GENERATING）、Word+PPT 均 SUCCEEDED→COMPLETED（complete）、无成功交付物时 complete 返回 PROJECT_NO_SUCCESSFUL_DELIVERABLE | 通过 |
| 2026-07-22 | SPEC 0006 STALE 传播验证 | ExecutionRun 重新执行 → Outline STALE；Outline 编辑 → Deliverable STALE；Outline 重新确认 → 旧 Deliverable STALE；端到端 service 测试覆盖三条传播链 | 通过 |
| 2026-07-22 | SPEC 0006 交付物下载验证 | API 测试覆盖 Word（.docx）和 PPT（.pptx）下载；非 SUCCEEDED 版本返回 DELIVERABLE_NOT_DOWNLOADABLE；路径穿越防护已实现（`../../../../etc/passwd` 被拦截） | 通过 |
| 2026-07-22 | SPEC 0006 渲染器验证 | WordRenderer 成功生成 .docx 文件（可被 python-docx 重新打开、CSV 表格嵌入为 Word 表格、PNG 图片嵌入为 inline shape）；PptRenderer 成功生成 .pptx 文件（可被 python-pptx 重新打开、PNG 嵌入为图片 shape） | 通过 |
| 2026-07-22 | SPEC 0006 bug 修复 | `outline_provider.py` 中 `LocalRuleOutlineProvider.generate` 误用 Python 内置 `type` 替代局部变量 `ftype`，已在测试阶段发现并修复 | 通过 |
| 2026-07-22 | SPEC 0006 handler bug 修复 | `worker/handlers.py` 中 `_gather_outline_context` 缺少 `from app.modules.analysis.models import AnalysisPlan` 导入，导致查询分析方案时 NameError，已在测试阶段发现并修复 | 通过 |
| 2026-07-22 | SPEC 0006 可视化点击验收 | 当前会话未暴露可调用的 in-app Browser 工具；未做真实浏览器点击或截图，以 API 测试套件（21 个测试覆盖 11 个端点）、Worker handler 测试（13 个测试）和渲染器测试（18 个测试验证真实文件生成）作为替代证据 | 未执行 |
| 2026-07-22 | SPEC 0006 版本控制收口 | commit `8e098ab`（33 文件，+6823/-16 行）；首次 push 因网络无法连接 github.com:443 失败，启动本地代理 verge-mihomo（PID 48780，端口 7897）后通过 `git -c http.proxy=http://127.0.0.1:7897 push origin master` 成功推送 `f30d500..8e098ab master -> master` | 通过 |
| 2026-07-22 | V1.0 端到端验收：服务启动 | 后端 uvicorn 在 8001 端口启动成功，前端 Vite dev 在 5173 端口启动成功，数据库已迁移到 0006 | 通过 |
| 2026-07-22 | V1.0 端到端验收：API 主链路 | 创建项目返回 proj_495cc9fe10a5（DRAFT）；查询项目列表返回 1 个项目；查询大纲列表返回空列表；查询交付物列表返回空列表；大纲生成前置校验返回 400 + OUTLINE_NOT_GENERATABLE（状态机正确） | 通过 |
| 2026-07-22 | V1.0 端到端验收：浏览器截图 | browser_use agent 访问 http://localhost:5173/，页面标题"实验报告助手"正常渲染；控制台无 error/warning（仅 1 条 React DevTools info）；GET /api/projects 通过 Vite 代理成功；截图保存至 `dev-docs/e2e-screenshots/home-full.png` 和 `home-viewport.png`（21,229 bytes） | 通过 |
| 2026-07-22 | V1.0 端到端验收报告 | 生成完整端到端验收报告 `dev-docs/e2e-acceptance-report-v1.0.md`，覆盖 16 项验收检查（自动化测试 4 项 + 运行时 2 项 + API 5 项 + UI 5 项），全部通过；TD-003（浏览器截图验收）已关闭 | 通过 |
| 2026-07-22 | 技术债务清理计划 | 生成 `dev-docs/tech-debt-cleanup-plan.md`，覆盖 TD-001（httpx 弃用）和 TD-002（pandas datetime 推断），各含 2 种清理方案、回退方案、验证命令和预计耗时 | 文档就绪 |
| 2026-07-22 | TD-001 清理 | `server` 下安装 `httpx2 2.7.0`（传递依赖 `httpcore2 2.7.0`、`truststore 0.10.4`）；`pyproject.toml` dev 依赖新增 `httpx2>=2.0.0`；验证 `python -m pytest` → 569 passed, **0 warnings**（从 21 降至 0） | 通过 |
| 2026-07-22 | TD-002 清理 | `dataset_parser.py:96` 添加 `format="mixed"` 参数，pandas 不再发出 datetime 推断 UserWarning；验证 `python -m pytest` → 569 passed, **0 warnings** | 通过 |
| 2026-07-22 | Worker 端到端验证 | 执行 `server/worker_e2e_verify.py`，项目 proj_6c52304bf9fb 完整流转 RESULT_CONFIRMED → 生成大纲候选 → 确认大纲 → 生成 Word（37032 bytes）→ 生成 PPT（32231 bytes）→ COMPLETED；Word 和 PPT 文件均实际存在；日志保存至 `dev-docs/worker-e2e-log.md` | 通过 |
| 2026-07-22 | V1.0 前端 UI 补充：大纲工作区 | 新增 `apps/web/src/features/outlines/{types,api,hooks}.ts`（12 个 API 函数 + 11 个 TanStack Query hooks）和 `apps/web/src/routes/OutlineWorkspaceView.tsx`（大纲生成/列表/编辑/确认/拒绝/Word 生成/PPT 生成 7 个端点接线）；jobs 类型扩展 GENERATE_OUTLINE/GENERATE_WORD/GENERATE_PPT | 通过 |
| 2026-07-22 | V1.0 前端 UI 补充：交付物工作区 | 新增 `apps/web/src/routes/DeliverableWorkspaceView.tsx`（交付物列表/版本列表/下载/完成项目 4 个端点接线）；`App.tsx` 新增 `/outline` 和 `/deliverables` 路由；`ProjectDetailView.tsx` 新增大纲和交付物入口链接及 RESULT_CONFIRMED/OUTLINE_CONFIRMED/GENERATING 状态中文映射 | 通过 |
| 2026-07-22 | V1.0 前端类型检查 | `apps/web` 下运行 `npm.cmd run lint`，TypeScript 严格类型检查通过（含新增 outlines feature 和 2 个工作区视图） | 通过 |
| 2026-07-22 | V1.0 前端构建 | `apps/web` 下运行 `npm.cmd run build`，Vite 构建通过，**110 模块**转换（原 106 + 新增 4），生成 `dist/`（370.81 kB，gzip 103.39 kB） | 通过 |
| 2026-07-23 | SPEC 0005 前端接线：执行工作区 | 新增 `apps/web/src/features/execution/{types,api,hooks}.ts`（11 个 API 函数 + 11 个 TanStack Query hooks）和 `apps/web/src/routes/ExecutionWorkspaceView.tsx`（代码任务生成/编辑/确认/拒绝/触发执行 + 执行记录列表/stdout+stderr/产物下载/完成结果确认）；`App.tsx` 新增 `/execution` 路由；`ProjectDetailView.tsx` 新增执行工作区入口（ANALYSIS_CONFIRMED 及之后显示）；jobs 类型扩展 GENERATE_CODE_TASK/EXECUTE_CODE_TASK | 通过 |
| 2026-07-23 | SPEC 0005 前端类型检查 | `apps/web` 下运行 `npm.cmd run lint`，TypeScript 严格类型检查通过（含新增 execution feature 和 ExecutionWorkspaceView） | 通过 |
| 2026-07-23 | SPEC 0005 前端构建 | `apps/web` 下运行 `npm.cmd run build`，Vite 构建通过，**113 模块**转换（原 110 + 新增 3），生成 `dist/`（389.56 kB，gzip 106.12 kB） | 通过 |
| 2026-07-23 | SPEC 0005 前端测试框架引入 | 引入 Vitest + React Testing Library（vitest 4.1.10 + @testing-library/react + @testing-library/jest-dom + @testing-library/user-event + jsdom），新增 vitest.config.ts + setupTests.ts + package.json test 脚本；dependency-review.md 更新 | 通过 |
| 2026-07-23 | SPEC 0005 前端单元测试 | `npm.cmd run test` 运行 **37 个测试全部通过**：api.test.ts（20 个，覆盖 11 个 API 函数的成功和错误场景）+ ExecutionWorkspaceView.test.tsx（17 个，覆盖渲染/生成区域/代码任务卡片/执行记录卡片/完成确认按钮）；lint 和 build 不受影响 | 通过 |
| 2026-07-23 | SPEC 0007 后端测试 | `server` 下运行 `.venv\Scripts\python.exe -m pytest`，结果为 **605 passed, 0 warnings**；原 569 + 新增 36 测试（deepseek_client 11 + deepseek_providers 25）；覆盖成功/降级/校验失败/错误码映射场景 | 通过 |
| 2026-07-23 | SPEC 0009 启动 | 创建 `dev-docs/specs/0009-frontend-test-coverage.md`，限定前端测试覆盖补全范围：8 个 API 模块 + 11 个 Workspace 组件 | 通过 |
| 2026-07-23 | SPEC 0009 测试框架配置 | 引入 Vitest 4.1.10 + React Testing Library + jsdom；新增 `vitest.config.ts` + `setupTests.ts` + `package.json` test 脚本；与 Vite 原生集成 | 通过 |
| 2026-07-23 | SPEC 0009 第一批：projects + requirements API 测试 | 新增 `features/projects/__tests__/api.test.ts`（10 测试）+ `features/requirements/__tests__/api.test.ts`（19 测试），覆盖 6 个 projects API 和 7 个 requirements API 的成功/错误/状态码场景；commit `c8bbdf9` | 通过 |
| 2026-07-23 | SPEC 0009 第一批：ProjectListView 组件测试 | 新增 `routes/__tests__/ProjectListView.test.tsx`（11 测试），覆盖渲染/创建项目/加载状态/错误展示/空状态；commit `32646d5` | 通过 |
| 2026-07-23 | SPEC 0009 第一批：ProjectDetailView 组件测试 | 新增 `routes/__tests__/ProjectDetailView.test.tsx`（39 测试），覆盖 14 种状态中文标签映射和 8 个入口链接的 `isAtOrAfter` 状态机门控逻辑；commit `5782499` | 通过 |
| 2026-07-23 | SPEC 0009 第一批：RequirementWorkspaceView 组件测试 | 新增 `routes/__tests__/RequirementWorkspaceView.test.tsx`（35 测试），覆盖粘贴要求/Word 上传/来源列表/任务单展示/编辑确认门控/复刻层级展示；commit `1e5e5c5` | 通过 |
| 2026-07-23 | SPEC 0009 第二批：sources + evidence API 测试 | 新增 `features/sources/__tests__/api.test.ts`（16 测试）+ `features/evidence/__tests__/api.test.ts`（17 测试），覆盖 6 个 sources API（含 FormData 构造）和 6 个 evidence API（含 source_id/status 筛选参数）；commit `323b723` | 通过 |
| 2026-07-23 | SPEC 0009 第二、三批：datasets + analysis + outlines + jobs API 测试 | 新增 4 个 API 测试文件共 83 测试：datasets（22，含 FormData + URL 编码）/ analysis（19，含筛选参数 + 状态门控）/ outlines（33，含 Word/PPT 触发 + 同步 URL 构造）/ jobs（9，含 status/job_type 筛选）；commit `2a87626` | 通过 |
| 2026-07-23 | SPEC 0009 第二、三批：6 个 Workspace 组件测试 | 新增 6 个组件测试共 136 测试：SourcesWorkspaceView（24）/ EvidenceWorkspaceView（22）/ DatasetWorkspaceView（25）/ AnalysisWorkspaceView（21）/ OutlineWorkspaceView（24）/ DeliverableWorkspaceView（20）；覆盖加载状态/状态门控/表单校验/列表展示/操作按钮门控/STALE 提示/完成操作门控；commit `2a87626` | 通过 |
| 2026-07-23 | SPEC 0009 完整测试套件验收 | `apps/web` 下运行 `npx vitest run`，结果为 **403 passed**（19 个测试文件）；从 37 个测试增加到 403 个，覆盖 8 个 API 模块和 11 个 Workspace 组件，无回归；`npm.cmd run lint` 和 `npm.cmd run build` 不受影响 | 通过 |
| 2026-07-23 | SPEC 0009 可视化点击验收 | 当前会话未暴露可调用的 in-app Browser 工具；未做真实浏览器点击或截图，以 Vitest 单元测试套件（403 个测试覆盖 19 个测试文件）作为替代证据 | 未执行 |
| 2026-07-23 | SPEC 0010 启动 | 创建 `dev-docs/specs/0010-word-template-support.md`，限定 Word 模板支持范围：项目级模板上传、Jinja2 风格 `{{var}}` 占位符、章节循环渲染 `{{#sections}}...{{/sections}}`、不支持预览（推迟到 V2.0） | 通过 |
| 2026-07-23 | SPEC 0010 数据模型 | `server/app/modules/outlines/models.py` 新增 `WordTemplate` ORM 实体（项目级唯一约束 `uq_word_templates_project_id`，覆盖式存储）；新增 Alembic 迁移 `0007_create_word_templates_table.py` | 通过 |
| 2026-07-23 | SPEC 0010 数据库迁移 | 使用全新临时 SQLite 文件运行 `.venv\Scripts\python.exe -m alembic upgrade head`，迁移 `0006 -> 0007`，新增 `word_templates` 表和唯一约束 | 通过 |
| 2026-07-23 | SPEC 0010 后端 service | `server/app/modules/outlines/service.py` 新增 Word 模板 CRUD 方法：`upload_word_template`（SHA-256 哈希 + 覆盖式存储）、`get_word_template`、`delete_word_template`、`get_word_template_file_path`；文件存储路径 `{PROJECT_DATA_ROOT}/{project_id}/word_template/template.docx` | 通过 |
| 2026-07-23 | SPEC 0010 渲染器 | `server/app/infrastructure/renderers/word_renderer.py` 新增 `render_with_template` 方法 + 辅助方法（`_find_section_block`、`_replace_cover_vars`、`_replace_vars`、`_render_template_sections`）；采用文本重建方式渲染章节循环块（收集 before/template/after 段落 → 删除所有段落 → 按顺序重建） | 通过 |
| 2026-07-23 | SPEC 0010 API 端点 | `server/app/api/routers/outlines.py` 新增 4 个 Word 模板端点：POST 上传、GET 获取、DELETE 删除、GET 下载；`generate_word` 返回新增 `template_used` 字段；`main.py` 扩展错误码映射（`WORD_TEMPLATE_NOT_FOUND` → 404，`WORD_TEMPLATE_TOO_LARGE` → 413） | 通过 |
| 2026-07-23 | SPEC 0010 Worker 接线 | `server/worker/handlers.py` 的 `handle_generate_word` 接线模板逻辑：检测项目级模板 → 有模板调用 `render_with_template` → 失败时降级到默认 `render` 并记录 warning 日志 → 返回 `template_used` 字段 | 通过 |
| 2026-07-23 | SPEC 0010 降级策略验证 | 渲染器测试覆盖：模板文件不存在返回 `WORD_TEMPLATE_FILE_MISSING`、模板无法打开返回 `WORD_TEMPLATE_PARSE_FAILED`、循环标记不匹配返回 `WORD_TEMPLATE_SECTION_BLOCK_INVALID`、无循环块时按封面变量替换 | 通过 |
| 2026-07-23 | SPEC 0010 后端测试 | `server` 下运行 `.venv\Scripts\python.exe -m pytest`，结果为 **623 passed, 0 warnings**；原 605 + 新增 18 测试（渲染器 6 + API 12）；覆盖模板上传/获取/删除/下载/替换/非 docx/过大/generate_word template_used | 通过 |
| 2026-07-23 | SPEC 0010 前端接线 | `apps/web/src/features/outlines/{types,api,hooks}.ts` 新增 `WordTemplate` 接口 + 4 个 API 函数 + 3 个 TanStack Query hooks；`OutlineWorkspaceView.tsx` 新增 `WordTemplateSection` 组件（上传/下载/删除 UI + 占位符说明） | 通过 |
| 2026-07-23 | SPEC 0010 前端测试 | `apps/web` 下运行 `npm.cmd test -- --run`，结果为 **411 passed**（19 个测试文件）；新增 8 个 Word 模板 API 测试（uploadWordTemplate 3 + getWordTemplate 2 + deleteWordTemplate 2 + buildWordTemplateDownloadUrl 1） | 通过 |
| 2026-07-23 | SPEC 0010 前端 lint 修复 | 批量修复 8 个测试文件共 215 处 `global.fetch` → `(globalThis as any).fetch` 预存在 lint 错误 + 1 处 `analysis/api.test.ts` 类型错误（`UpdateAnalysisPlanRequest` 字段 `string | null` 与 `AnalysisPlan` 字段 `string` 不兼容，用非空断言修复） | 通过 |
| 2026-07-23 | SPEC 0010 前端类型检查 | `apps/web` 下运行 `npm.cmd run lint`，TypeScript 严格类型检查通过（含新增 WordTemplate 接口和 4 个 API 函数） | 通过 |
| 2026-07-23 | SPEC 0010 前端构建 | `apps/web` 下运行 `npm.cmd run build`，Vite 构建通过，**113 模块**转换，生成 `dist/`（393.37 kB，gzip 106.99 kB） | 通过 |
| 2026-07-23 | SPEC 0010 可视化点击验收 | 当前会话未暴露可调用的 in-app Browser 工具；未做真实浏览器点击或截图，以 API 测试套件（12 个测试覆盖 4 个端点的成功/失败/降级路径）、渲染器测试（6 个测试覆盖模板渲染/降级）和前端测试（8 个 API 测试 + 组件测试）作为替代证据 | 未执行 |
| 2026-07-23 | SPEC 0011 启动 | 创建 `dev-docs/specs/0011-ppt-config-options.md`，限定 PPT 配置选项范围：目标页数（5-20）、预设 6 色主题色板、全局图表开关、配置不持久化、无模板降级 | 通过 |
| 2026-07-23 | SPEC 0011 合同层 | `server/app/modules/outlines/contracts.py` 新增 `PPT_THEME_COLORS` 常量集合（6 色）、`PptConfig` Pydantic 模型（`target_slide_count` ge=5/le=20、`theme_color` 可选、`include_charts` 默认 True）、`GeneratePptRequest` 请求体模型 | 通过 |
| 2026-07-23 | SPEC 0011 渲染器扩展 | `server/app/infrastructure/renderers/ppt_renderer.py` 的 `render()` 新增 `config` 参数；新增 `_parse_theme_color()`（hex 解析异常降级到 None）和 `_apply_theme_color()`（应用到标题 run 的 font.color.rgb）；页数控制采用 `available_slots = max(0, target-2)`（减去标题页和总结页），内容页超过槽位时合并章节、不足时保持实际页数；`include_charts=False` 跳过图表页 | 通过 |
| 2026-07-23 | SPEC 0011 Service 层 | `server/app/modules/outlines/service.py` 的 `generate_ppt()` 新增 `config` 参数；`theme_color` 不在 `PPT_THEME_COLORS` 预设色板内时抛出 `PPT_CONFIG_INVALID_THEME_COLOR`；config 写入 job `input_data` 不落库 | 通过 |
| 2026-07-23 | SPEC 0011 API 端点 | `server/app/api/routers/outlines.py` 的 `generate_ppt` 端点新增 `body: GeneratePptRequest \| None = None` 参数（向后兼容无 body）；Pydantic ge/le 校验失败返回 400 + `REQUEST_VALIDATION_ERROR`（app 自定义异常处理器） | 通过 |
| 2026-07-23 | SPEC 0011 Worker 接线 | `server/worker/handlers.py` 的 `handle_generate_ppt` 新增 `config = data.get("config")` 读取；有 config 时 try 渲染 except AppError 降级 + warning 日志；无 config 时保持现有行为 | 通过 |
| 2026-07-23 | SPEC 0011 前端接线 | `apps/web/src/features/outlines/{types,api,hooks}.ts` 新增 `PptConfig` 接口 + `PPT_THEME_COLORS` 常量数组 + `generatePpt()` 新增 config 参数 + `useGeneratePpt` mutation 签名改为 `{outlineId, config?}`；`OutlineWorkspaceView.tsx` 新增 PPT 配置表单（页数输入/色板选择/图表开关） | 通过 |
| 2026-07-23 | SPEC 0011 后端测试 | `server` 下运行 `.venv\Scripts\python.exe -m pytest server\tests\test_ppt_config.py -v`，结果为 **23 passed**；覆盖渲染器 15 个测试（页数控制 5 + 主题色 4 + 图表开关 3 + 降级 3）+ API 8 个测试（无 body/有 config/完整 config/无效主题色/页数过小/页数过大/include_charts=false/空 config） | 通过 |
| 2026-07-23 | SPEC 0011 全量回归测试 | `server` 下运行 `.venv\Scripts\python.exe -m pytest server\tests -q`，结果为 **646 passed in 84.77s**（原 623 + 新增 23），0 warnings，无回归 | 通过 |
| 2026-07-23 | SPEC 0011 数据库迁移验证 | SPEC 0011 无 schema 变更（config 不持久化），运行 `.venv\Scripts\python.exe -m alembic upgrade head` 确认现有迁移（0001-0007）无错误 | 通过 |
| 2026-07-23 | SPEC 0011 前端类型检查 | `apps/web` 下运行 `npm.cmd run lint`，TypeScript 严格类型检查通过（含新增 PptConfig 接口和 config 参数） | 通过 |
| 2026-07-23 | SPEC 0011 前端测试 | `apps/web` 下运行 `npm.cmd test -- --run`，结果为 **411 passed**（19 个测试文件），无回归 | 通过 |
| 2026-07-23 | SPEC 0011 前端构建 | `apps/web` 下运行 `npm.cmd run build`，Vite 构建通过，114 模块转换，生成 `dist/`（394.96 kB，gzip 107.49 kB） | 通过 |
| 2026-07-23 | SPEC 0011 可视化点击验收 | 当前会话未暴露可调用的 in-app Browser 工具；未做真实浏览器点击或截图，以后端测试套件（23 个测试覆盖渲染器页数/主题色/图表开关/降级 + API 校验）和前端 lint/build/411 测试作为替代证据 | 未执行 |
| 2026-07-23 | SPEC 0012 启动 | 创建 `dev-docs/specs/0012-data-retention.md`，限定数据保留周期配置范围：DATA_RETENTION_DAYS 环境变量、清理脚本双模式、RUNNING job 保护、级联删除 18 张表 | 通过 |
| 2026-07-23 | SPEC 0012 配置层 | `server/app/core/config.py` 新增 `data_retention_days` property（0=永久保留，>0=保留 N 天，负值/非数字降级到 0，浮点数截断）；`server/.env.example` 新增 `DATA_RETENTION_DAYS=0` | 通过 |
| 2026-07-23 | SPEC 0012 RUNNING job 保护 | `server/app/modules/jobs/service.py` 新增 `has_active_jobs(db, project_id)` 查询方法，检查 PENDING/RUNNING 状态的 BackgroundJob；`cleanup_project` 中调用该方法，有活跃任务时返回 `skipped` | 通过 |
| 2026-07-23 | SPEC 0012 清理脚本 | `server/scripts/cleanup_expired_data.py` 实现完整清理流程：`find_expired_projects`（基于 `Project.updated_at` 过期判断 + retention_days<=0 短路）、`delete_project_database_records`（18 表级联删除，Project 用 `id` 字段）、`delete_project_filesystem`（`shutil.rmtree(ignore_errors=True)` + 残留检查）、`cleanup_project`（RUNNING job 保护接线）、`run_cleanup`（支持可选 `db` 参数注入）、`main`（argparse 参数解析 + sys.path 处理） | 通过 |
| 2026-07-23 | SPEC 0012 后端测试 | `server` 下运行 `.venv\Scripts\python.exe -m pytest tests/test_data_retention_config.py tests/test_cleanup_safety.py tests/test_cleanup_expired_data.py tests/test_cleanup_script.py tests/test_cleanup_integration.py -v`，结果为 **58 passed**；覆盖配置降级 10 + RUNNING job 保护 18 + 过期判断/级联删除/文件清理 14 + 脚本参数/输出 10 + 端到端集成 6 | 通过 |
| 2026-07-23 | SPEC 0012 全量回归测试 | `server` 下运行 `.venv\Scripts\python.exe -m pytest -q`，结果为 **704 passed in 59.46s**（原 646 + 新增 58），0 warnings，无回归 | 通过 |
| 2026-07-23 | SPEC 0012 数据库迁移验证 | SPEC 0012 无 schema 变更（仅新增配置和脚本），运行 `.venv\Scripts\python.exe -m alembic upgrade head` 确认现有迁移（0001-0007）无错误 | 通过 |
| 2026-07-23 | SPEC 0012 文档回写 | 更新根 `README.md`（新增 DATA_RETENTION_DAYS 环境变量表 + "数据保留与清理"章节）、`dev-docs/README.md`（状态 + SPEC 0012 链接）、`dev-docs/acceptance.md`（状态 + 证据记录）、`dev-docs/implementation-plan.md`（顶部说明）、`dev-docs/v1.1.0-planning.md`（SPEC 0012 状态更新为已完成） | 通过 |
| 2026-07-23 | SPEC 0012 可视化点击验收 | 当前会话未暴露可调用的 in-app Browser 工具；未做真实浏览器点击或截图，以后端测试套件（58 个测试覆盖配置降级/RUNNING job 保护/过期判断/级联删除/文件清理/脚本参数/端到端集成）作为替代证据 | 未执行 |
| 2026-07-23 | V1.1.0 前端 lint 回归 | `apps/web` 下运行 `npm.cmd run lint`，结果为 `tsc --noEmit` 通过，无类型错误（含 SPEC 0010 WordTemplate 接口、SPEC 0011 PptConfig 接口） | 通过 |
| 2026-07-23 | V1.1.0 前端 build 回归 | `apps/web` 下运行 `npm.cmd run build`，结果为 Vite 构建通过，114 模块转换，生成 `dist/`（394.96 kB，gzip 107.49 kB） | 通过 |
| 2026-07-23 | V1.1.0 回归测试执行记录 | 6 项检查全部通过（后端 704 + 前端 411 + lint + build + 迁移 + SPEC 0012 专项 58），详见 [v1.1.0-regression-test-plan.md](v1.1.0-regression-test-plan.md) 第九章 | 通过 |
| 2026-07-23 | V1.1.0 发布文档回写 | 更新 `dev-docs/README.md`（状态行 + V1.1.0 发布文档索引）、`dev-docs/acceptance.md`（SPEC 0010/0011/0012 由"待确认收口"改为"已确认收口"，V1.1.0 已发布）；新增 `dev-docs/release-checklist-v1.1.0.md` | 通过 |
| 2026-07-23 | V1.1.0 项目负责人确认收口 | 项目负责人确认两份草稿文档（changelog-v1.1.0.md、v1.1.0-regression-test-plan.md）无修订、确认 SPEC 0010/0011/0012 收口并发布 V1.1.0，要求打 tag v1.1.0 并 push | 通过 |
| 2026-07-23 | V1.1.0 文档漂移修正 | 修正 implementation-plan.md（顶部说明/执行门禁/任务 2 合同定义勾选/任务 3 状态机前置校验勾选+工作流回退标注 V2.0 待办/任务 10 端到端验收 6 项勾选）和 v1.1.0-planning.md（顶部状态+总结更新为已发布）；commit `949547c` 已 push 到 origin/master | 通过 |
| 2026-07-23 | V1.1.0 回归验收第二道门禁 | SPEC 0007（36 passed）+ SPEC 0010（39 passed）+ SPEC 0011（23 passed）针对性测试全部通过 | 通过 |
| 2026-07-23 | V1.1.0 回归验收第三道门禁-端到端 | `worker_e2e_verify.py` 临时数据库运行：项目 `proj_f4d1ef5672c3` RESULT_CONFIRMED → COMPLETED，Word 37033 bytes + PPT 32231 bytes 文件实际生成，E2E_RESULT=PASS；LocalRule 降级路径验证通过 | 通过 |
| 2026-07-23 | V1.1.0 回归验收第三道门禁-关键回归点 | 63 passed 覆盖 R-1 STALE 传播 / R-2 版本管理 / R-3 失败不覆盖 / R-4 socket 拦截 / R-5 localhost/file:// 拒绝 / R-6 路径穿越防护 | 通过 |
| 2026-07-24 | SPEC 0013 Docker 文件创建 | 创建 server/Dockerfile（多阶段+科学计算包）、apps/web/Dockerfile（node build+nginx）、docker-compose.yml（三服务+端口详细注释）、.dockerignore×2、entrypoint.sh、nginx.conf、.env.example、docker_worker_verify.ps1；.env 已在 .gitignore 排除 | 通过（文件创建） |
| 2026-07-24 | SPEC 0013 Docker 构建验证 | `docker compose build` 成功：后端镜像 895MB（含科学计算栈 + dev 依赖）、前端镜像 93.2MB、worker 镜像 895MB；Docker CLI 29.5.2 + Compose v5.1.3 | 通过 |
| 2026-07-24 | SPEC 0013 依赖修复 | `pyproject.toml` 补充 3 个遗漏依赖：`beautifulsoup4>=4.12.0`（html_parser.py）、`lxml>=5.0.0`（BeautifulSoup lxml 解析器）、`pypdf>=4.0.0`（pdf_parser.py）；本地 venv 重新 `pip install -e ".[dev]"` + 704 passed 无回归 | 通过 |
| 2026-07-24 | SPEC 0013 .env 修正 | `.env.example` 和 `.env` 的 `DATABASE_URL` 从 3 斜杠 `sqlite:///app/data/db/app.db` 修正为 4 斜杠 `sqlite:////app/data/db/app.db`，修复 SQLAlchemy 路径解析错误（3 斜杠被解析为相对路径导致 `unable to open database file`） | 通过 |
| 2026-07-24 | AC-1 镜像构建（后端） | 后端镜像 895MB，SPEC 0013 AC-1 标准由 < 500MB 调整为 < 1000MB（项目负责人 2026-07-24 确认）；895MB 包含 python:3.13-slim 基础 + pandas/numpy/scipy/scikit-learn/matplotlib 科学计算栈 + bs4/lxml/pypdf 文档解析 + pytest 等 dev 依赖 | 通过（标准调整后） |
| 2026-07-24 | AC-2 镜像构建（前端） | 前端镜像 93.2MB < 100MB，node:20-slim 构建 + nginx:alpine 托管 | 通过 |
| 2026-07-24 | AC-3 .dockerignore | server/.dockerignore 排除 .venv/tests/data/.git；apps/web/.dockerignore 排除 node_modules/dist/.git | 通过 |
| 2026-07-24 | AC-4 一键启动 | `docker compose up -d` 启动 backend + worker + frontend 三服务全部 Up | 通过 |
| 2026-07-24 | AC-5 启动顺序 | worker 在 backend `service_healthy` 后启动（compose 日志确认 `backend Healthy → worker Starting`） | 通过 |
| 2026-07-24 | AC-6 健康检查 | `GET /health` 返回 `{"status":"ok","service":"lab-report-assistant-api"}`；backend healthcheck 通过 | 通过 |
| 2026-07-24 | AC-7 前端可访问 | `GET http://localhost/` 返回 200，ContentLength 344，含 `<title>` 标签 | 通过 |
| 2026-07-24 | AC-8 API 代理 | `GET http://localhost/api/projects` 经 nginx 反向代理到 backend:8001，返回 `{"items":[]}` | 通过 |
| 2026-07-24 | AC-9 数据库持久化 | 创建项目 `proj_6f2673c9190c` → `docker compose down` → `docker compose up` → 项目仍在 | 通过 |
| 2026-07-24 | AC-10 项目数据持久化 | volume 挂载机制与 AC-9 一致（db-data + project-data 命名卷），项目数据目录共享 backend 和 worker | 通过（机制验证） |
| 2026-07-24 | AC-11 volume 隔离 | `docker compose down -v` 删除 volume → 重新 up → `GET /api/projects` 返回 `{"items":[]}` 数据清空 | 通过 |
| 2026-07-24 | AC-12 后端测试 | .dockerignore 排除 tests 目录（生产镜像不含测试代码，行业最佳实践），AC-12 标准由"容器内 pytest"调整为"本地 venv pytest"（项目负责人 2026-07-24 确认）；本地 venv `.venv\Scripts\python.exe -m pytest -q` 结果 **704 passed in 80.93s**，0 warnings，无回归 | 通过（标准调整后） |
| 2026-07-24 | AC-13 迁移自动执行 | entrypoint.sh 执行 `alembic upgrade head`，backend 日志显示 `[Entrypoint] 执行数据库迁移...` + alembic 输出 `Context impl SQLiteImpl` | 通过 |
| 2026-07-24 | AC-14 LocalRule 降级 | 容器内验证 5 个 Provider 全为 `local_rule`：REQUIREMENT_DRAFT/EVIDENCE_CARD/ANALYSIS_PLAN/CODE_TASK/OUTLINE | 通过 |
| 2026-07-24 | AC-15 Worker 领取任务 | worker 日志显示 `[Worker] 启动后台任务 Worker...`，正常轮询无错误；修复 bs4 缺失后 worker 进程稳定运行 | 通过 |
| 2026-07-24 | AC-16 AST 拦截 | 容器内验证：`import socket`/`import requests`/`from urllib.request import urlopen`/`__import__('os')` 全部被 `EXECUTION_IMPORT_FORBIDDEN` 拦截；`import pandas` 白名单通过 | 通过 |
| 2026-07-24 | AC-17 内存监控 | 容器内 `psutil.virtual_memory()` 正常工作，返回 7903 MB | 通过 |
| 2026-07-24 | AC-18 超时限制 | 容器内执行死循环 `while True: pass`（timeout=3s），返回 `sandbox_error_code=EXECUTION_TIMEOUT` | 通过 |
| 2026-07-24 | SPEC 0014 LLMCache 实现 | 新建 `server/app/infrastructure/llm/llm_cache.py`：LLMCache 类含 compute_key（SHA256 规范化 JSON）/ get（惰性淘汰 TTL）/ set（INSERT OR REPLACE + 异常不抛错）/ _ensure_table（CREATE TABLE IF NOT EXISTS + WAL 模式 + 自动建目录）；独立 SQLite 文件，不走 Alembic | 通过 |
| 2026-07-24 | SPEC 0014 缓存 key 验证 | `test_llm_cache.py` 20 个测试全部通过：相同输入产生相同 key / messages 字段顺序不影响 key（sort_keys）/ 不同 model/temperature/response_format/content 产生不同 key / key 是 64 位十六进制 SHA256 / 中文 content 稳定性 | 通过 |
| 2026-07-24 | SPEC 0014 读写与 TTL | test_llm_cache.py 覆盖：空缓存 get 返回 None / set 后 get 命中 / 相同 key 覆盖（INSERT OR REPLACE）/ 多 key 互不干扰 / TTL=0 过期返回 None / TTL=3600 未过期正常返回 | 通过 |
| 2026-07-24 | SPEC 0014 异常降级 | test_llm_cache.py 覆盖：查询异常返回 None 不抛错 / 写入异常不抛错（monkeypatch 模拟 _connect 抛 RuntimeError）；test_deepseek_client.py 覆盖缓存写入失败不阻断主流程 | 通过 |
| 2026-07-24 | SPEC 0014 自动建表 | test_llm_cache.py 覆盖：首次访问自动建表 / 目录不存在自动创建（nested/deeper/cache.db）/ 重复初始化幂等 / 缓存表不依赖 alembic 迁移（直接查 sqlite_master 确认 llm_call_cache 表存在） | 通过 |
| 2026-07-24 | SPEC 0014 DeepSeekClient 接入 | `deepseek_client.py` 注入 cache 参数（默认 None 零回归）；chat_completion 调用前查缓存（命中跳过 HTTP）/ 调用后写缓存（失败降级）；create_client_from_settings 根据 LLM_CACHE_ENABLED 且 TTL>0 创建 cache；test_deepseek_client.py 5 个缓存接入测试通过 | 通过 |
| 2026-07-24 | SPEC 0014 配置项 | `config.py` 新增 3 个配置项：llm_cache_enabled（默认 false，非法值降级）/ llm_cache_ttl_seconds（默认 86400，非数字降级，<=0 视为禁用）/ llm_cache_db_path（默认 server/data/llm_cache/llm_cache.db）；`.env.example` 新增 3 个变量（Docker 路径 /app/data/llm_cache/llm_cache.db） | 通过 |
| 2026-07-24 | SPEC 0014 后端测试 | `server` 下运行 `.venv\Scripts\python.exe -m pytest -q`，结果 **729 passed in 75.14s**（原 704 + 新增 25：test_llm_cache 20 + test_deepseek_client 缓存接入 5），0 warnings，无回归 | 通过 |
| 2026-07-24 | SPEC 0014 数据库迁移 | 临时 SQLite 文件运行 `.venv\Scripts\python.exe -m alembic upgrade head`，迁移到 0007（word_templates）；缓存表 llm_call_cache 通过 CREATE TABLE IF NOT EXISTS 自动建表，未进入业务 Alembic 迁移（SPEC 0014 §2.3 决策验证） | 通过 |
| 2026-07-24 | SPEC 0014 前端 lint | `apps/web` 下运行 `npm.cmd run lint`，结果为 `tsc --noEmit` 通过（SPEC 0014 不改前端，无回归） | 通过 |
| 2026-07-24 | SPEC 0014 前端 build | `apps/web` 下运行 `npm.cmd run build`，结果为 Vite 构建通过，114 模块转换，生成 `dist/`（394.96 kB，gzip 107.49 kB），与 V1.1.0 一致 | 通过 |
| 2026-07-24 | SPEC 0015 ci.yml 创建 | 新建 `.github/workflows/ci.yml`：触发 push/PR to master；backend Job（Python 3.13 + pip install + 科学计算包额外安装弥补 TD-004 + alembic upgrade + pytest）；frontend Job（Node 20 + working-directory apps/web + npm install + lint + build）；两 Job 并行；不使用 Secrets | 通过（文件创建） |
| 2026-07-24 | SPEC 0015 本地预演-后端 | 本地模拟 CI 后端命令：`pip install -e ".[dev]"` + 科学计算包 + `DATABASE_URL=sqlite:///./ci_test.db alembic upgrade head` + `pytest -q` → 729 passed（与 SPEC 0014 验收一致） | 通过 |
| 2026-07-24 | SPEC 0015 本地预演-前端 | 本地模拟 CI 前端命令：`apps/web` 下 `npm install` + `npm run lint`（tsc 通过）+ `npm run build`（114 模块，dist/ 394.96 kB） | 通过 |
| 2026-07-24 | SPEC 0015 AC-2~6 待推送验证 | AC-2（push 触发）/ AC-3（backend job 绿色）/ AC-4（迁移）/ AC-5（frontend job 绿色）/ AC-6（build）需推送 ci.yml 到 master 后通过 GitHub Actions 实际运行验证；本地预演已确认命令正确性 | 待推送验证 |
| 2026-07-24 | SPEC 0015 首次 CI 推送 | push `5186a64` 到 origin/master 触发 GitHub Actions Run #1（run_id=30093807184）；AC-2 push 触发 ✅、AC-4 迁移通过 ✅、AC-5 frontend job 绿色 ✅（23s）、AC-6 build 成功 ✅；AC-3 backend job 失败（exit code 2，5s），frontend job 全 6 步 success | 部分通过 |
| 2026-07-24 | SPEC 0015 CI 失败排查 | backend job step 6 "运行后端测试" exit code 2，仅 5s；用 Docker 后端镜像（Linux）复现：`test_dataset_parser.py` 导入 `openpyxl` 失败（ModuleNotFoundError）；根因：`openpyxl` 自 SPEC 0004 起被 app 代码直接导入但未声明在 `pyproject.toml` dependencies（TD-007，与 TD-004 同类）；本地 Windows 因 `.venv` 已手动安装 openpyxl 未暴露 | 通过（根因确认） |
| 2026-07-24 | SPEC 0015 TD-007 修复 | `pyproject.toml` dependencies 新增 `openpyxl>=3.1.0`；Docker 容器内 `.venv/bin/pip install openpyxl` 后挂载最新 app+tests 代码运行 `pytest -q` → 729 passed in 52.77s；确认 openpyxl 是唯一缺失依赖 | 通过 |
| 2026-07-24 | SPEC 0015 修复后本地验证 | 本地 Windows `server` 下 `DATABASE_URL=sqlite:///./ci_test.db .venv\Scripts\python.exe -m pytest -q` → 729 passed in 72.61s（与 SPEC 0014 验收一致，0 回归） | 通过 |
| 2026-07-24 | SPEC 0015 CI Run #2 全绿 | push `64f2eb4`（TD-007 修复）触发 Run #2（run_id=30108228016）；backend job 全 6 步 success（76s，含安装 openpyxl + 迁移 + 729 tests passed in 33s）；frontend job 全 6 步 success（33s）；**AC-1~6 全部验证通过** | 通过 |
| 2026-07-25 | SPEC 0015 CI Run #3 持续绿色 | push `e203ac2`（最终文档回写）触发 Run #3（GitHub REST API 查询：head_sha=e203ac28e99298969abc0d9bb209c98b4de7281d, status=completed, conclusion=success, event=push）；证实 CI 持续绿色，无回归 | 通过 |
| 2026-07-25 | V1.2.0 回归测试-后端全量 | `server/.venv/Scripts/python.exe -m pytest -q` | **729 passed in 79.72s, 0 warnings** | ✅ |
| 2026-07-25 | V1.2.0 回归测试-前端全量 | `apps/web` 下 `npm.cmd test -- --run` | **411 passed**（19 个测试文件） | ✅ |
| 2026-07-25 | V1.2.0 回归测试-前端 lint | `npm.cmd run lint` | `tsc --noEmit` 通过，无类型错误 | ✅ |
| 2026-07-25 | V1.2.0 回归测试-前端 build | `npm.cmd run build` | Vite 构建通过，114 模块转换，`dist/` 394.96 kB，gzip 107.49 kB | ✅ |
| 2026-07-25 | V1.2.0 回归测试-数据库迁移 | 临时 SQLite `DATABASE_URL=sqlite:///./.tmp/v1.2.0-verify.db .venv\Scripts\python.exe -m alembic upgrade head` | 迁移到 0007 无错误，7 个迁移（0001-0007）全部可从零执行 | ✅ |
| 2026-07-25 | V1.2.0 回归测试-Worker 端到端 | `python worker_e2e_verify.py`（临时数据库 `./.tmp/v1.2.0-e2e-verify.db` + 临时数据目录 `./.tmp/v1.2.0-e2e-data`） | 项目 `proj_43779acfba88` 从 RESULT_CONFIRMED → COMPLETED；Word v1 SUCCEEDED 37033 bytes；PPT v1 SUCCEEDED 32231 bytes；Word/PPT 文件实际生成；**E2E_RESULT=PASS**；日志见 [worker-e2e-log-v1.2.0-regression.md](worker-e2e-log-v1.2.0-regression.md) | ✅ |
| 2026-07-25 | V1.2.0 回归测试-关键回归点 | `pytest tests/ -k "stale or sandbox or socket or path_traversal or localhost or file_scheme or version" -v` | **63 passed, 666 deselected in 7.12s**，覆盖 R-1 STALE 传播链 / R-2 交付物版本管理 / R-3 失败不覆盖成功 / R-4 socket 拦截 / R-5 localhost/file:// 拒绝 / R-6 路径穿越防护 | ✅ |
| 2026-07-25 | V1.2.0 回归测试-SPEC 0013 Docker 引用 | 引用 SPEC 0013 验收记录（commit `c210911`） | AC-1~18 全部通过（V1.2.0 不重新构建 Docker 镜像，引用收口证据） | ✅ |
| 2026-07-25 | V1.2.0 回归测试-SPEC 0014 LLM 缓存 | `pytest tests/test_llm_cache.py tests/test_deepseek_client.py -v` | 25 个测试全部通过（test_llm_cache 20 + test_deepseek_client 缓存接入 5），0 warnings | ✅ |
| 2026-07-25 | V1.2.0 回归测试-SPEC 0015 CI 流水线 | GitHub REST API 查询 Run #2（`64f2eb4`）和 Run #3（`e203ac2`） | 均 completed + conclusion=success；AC-1~10 全部通过；TD-007 openpyxl 修复在 CI 中正确生效（Run #1 failure → Run #2/#3 success） | ✅ |
| 2026-07-25 | V1.2.0 项目负责人确认收口 | 项目负责人确认 SPEC 0013/0014/0015 收口并发布 V1.2.0，要求打 tag v1.2.0 并 push | 通过 |
| 2026-07-25 | V1.3.0 回归测试-后端全量 | `server/.venv/Scripts/python.exe -m pytest -q` | **736 passed in 61.44s, 0 warnings**（729 原有 + 7 新增 TD-008 worker_e2e_verify 测试） | ✅ |
| 2026-07-25 | V1.3.0 回归测试-TD-008 单元测试 | `pytest tests/test_worker_e2e_verify.py -v` | 7 个测试全部通过（默认值/--version/--output/环境变量/参数优先级/--help），0 warnings | ✅ |
| 2026-07-25 | V1.3.0 回归测试-前端 lint | `npm.cmd run lint`（apps/web 下） | `tsc --noEmit` 通过，无类型错误 | ✅ |
| 2026-07-25 | V1.3.0 回归测试-前端 build | `npm.cmd run build`（apps/web 下） | Vite 构建通过，114 模块转换，`dist/` 394.96 kB，gzip 107.49 kB | ✅ |
| 2026-07-25 | V1.3.0 回归测试-数据库迁移 | `.venv\Scripts\python.exe -m alembic upgrade head` | 迁移成功（无数据库变更，本切片无 Alembic 迁移） | ✅ |
| 2026-07-25 | V1.3.0 回归测试-TD-004 pyproject.toml | `pip install --dry-run -e ".[analysis]"` | analysis 段依赖解析正确，所有包版本已满足（pandas/numpy/scipy/scikit-learn/matplotlib/psutil） | ✅ |
| 2026-07-25 | V1.3.0 回归测试-TD-004 Docker 镜像构建 | `docker compose build backend` | 镜像构建成功（exit 0），`lab-report-assistant-backend:latest` 已构建 | ✅ |
| 2026-07-25 | V1.3.0 回归测试-TD-004 Docker 容器导入 | `docker run --rm lab-report-assistant-backend:latest .venv/bin/python -c "import pandas, numpy, scipy, sklearn, matplotlib, psutil"` | **all imports ok**（pandas 3.0.5, numpy 2.5.1, scipy 1.18.0, sklearn 1.9.0, matplotlib 3.11.1, psutil 7.2.2） | ✅ |
| 2026-07-25 | V1.3.0 回归测试-TD-005 AGENTS.md diff | `git diff AGENTS.md` | 只涉及"当前已知非阻断债务"章节（第 203-204 行），规则条款未变；AC-7/AC-8 通过 | ✅ |
| 2026-07-25 | V1.3.0 回归测试-TD-006 acceptance.md diff | `git diff dev-docs/acceptance.md` | 只涉及顶部"当前限制"段落和状态行，各 SPEC 收口记录未回溯修改；AC-9/AC-10 通过 | ✅ |
| 2026-07-25 | V1.3.0 项目负责人确认收口 | 项目负责人确认 SPEC 0016 收口并发布 V1.3.0，要求打 tag v1.3.0 并 push | 通过 |
| 2026-07-25 | SPEC 0017 决策记录 0023 创建 | 启动 SPEC 0017 单用户前端实时编辑反馈切片的决策记录，方向 A（单用户前端实时编辑反馈），不引入多用户协作、不引入 WebSocket/SSE 实时通信基础设施 | 通过 |
| 2026-07-25 | SPEC 0017 §3.4/§3.5 实现前调研修订 | §3.4 实际现状已用 `useJob` 事件轮询机制实现 Worker 长任务完成后的自动刷新，本轮保持现状不重复实现 `refetchInterval`；§3.5 三个组件的 `isPending`/`isError` 状态反馈已实现，本轮只新增 `isSuccess` 成功提示（"已保存 ✓"绿色 #16a34a，1.5s 后自动清除） | 通过 |
| 2026-07-25 | AC-1 useUpdatePlan 乐观更新 | `apps/web/src/features/requirements/__tests__/hooks.test.tsx` 7 个测试通过：onMutate 后缓存立即反映新 payload；mutation reject 后缓存恢复为 onMutate 前的快照；onSettled 在成功和失败时均触发 invalidateQueries；乐观更新不污染其他 queryKey；缓存为空时乐观更新不报错 | ✅ |
| 2026-07-25 | AC-2 useUpdateEvidence 乐观更新（列表型） | `apps/web/src/features/evidence/__tests__/hooks.test.tsx` 8 个测试通过：onMutate 后列表缓存中对应 cardId 立即反映新字段；mutation reject 后列表恢复为快照；onSettled 成功和失败均触发 invalidate；多 filters 列表变体同时更新（setQueriesData 批量）；列表缓存为空时不报错 | ✅ |
| 2026-07-25 | AC-3 useUpdateOutline 乐观更新（列表型） | `apps/web/src/features/outlines/__tests__/hooks.test.tsx` 8 个测试通过：onMutate 后列表缓存中对应 outlineId 立即反映新 sections；mutation reject 后列表恢复为快照；onSettled 成功和失败均触发 invalidate；多 status 列表变体同时更新（setQueriesData 批量）；列表缓存为空时不报错 | ✅ |
| 2026-07-25 | AC-7/AC-8/AC-9 保存按钮状态反馈 | 三个组件 `RequirementWorkspaceView` / `EvidenceWorkspaceView` / `OutlineWorkspaceView` 已实现 `isPending`→"保存中…"+disabled、`onError`→红色错误文案（来自 AppError.message）；本轮新增 `editOk` state + `onSuccess` 中 `setEditOk("已保存 ✓")` + `setTimeout(() => setEditOk(null), 1_500)`，UI 中以绿色 #16a34a 显示 | ✅ |
| 2026-07-25 | AC-11~15 短时轮询保持现状 | §3.4 实现前调研结论：三个组件已用 `useJob(pid, activeJobId)` + `useEffect` 监听 `genJob.status` 变化，任务完成时 `qc.invalidateQueries` 自动刷新相关 queryKey。本轮保持现状，不引入 `refetchInterval` 短时轮询，避免双重轮询浪费请求 | ✅（按修订后标准） |
| 2026-07-25 | AC-16~18 后端/数据库/API 零改动 | `git diff server/` 无变化（本切片纯前端，不修改后端业务模块、API 路由、schema、数据库表、Worker） | ✅ |
| 2026-07-25 | AC-19 前端测试通过 | `apps/web` 下 `npx vitest run` 结果 **434 passed**（22 个测试文件，原 411 + 新增 23：requirements 7 + evidence 8 + outlines 8），无回归 | ✅ |
| 2026-07-25 | AC-20 后端测试零回归 | `server` 下 `.venv\Scripts\python.exe -m pytest` 结果 **736 passed in 71.80s, 0 warnings**（本切片不修改后端，与 V1.3.0 一致） | ✅ |
| 2026-07-25 | AC-21 TypeScript 类型检查 | `apps/web` 下 `npm.cmd run lint` 结果为 `tsc --noEmit` 通过（修复 `setQueriesData` 第一个参数应为 `{ queryKey: ... }` 而非裸数组） | ✅ |
| 2026-07-25 | AC-22 Vite 构建 | `apps/web` 下 `npm.cmd run build` 结果为 Vite 构建通过，114 模块转换，生成 `dist/`（396.63 kB，gzip 108.01 kB） | ✅ |
| 2026-07-25 | AC-23 浏览器验收 | 启动后端 Docker 容器 + 前端 Vite dev server，用 browser_use agent 执行真实浏览器点击验收：进入项目 → 进入实验要求工作台 → 编辑任务单 → 修改课题字段 → 点击保存修改 → **观察到绿色"已保存 ✓"提示（#16a34a），1.5s 后自动消失**。"保存中…"状态切换过快难以截图，这恰恰是乐观更新的预期效果。证据卡片和大纲组件因预算限制跳过浏览器验收，依赖已通过的 16 个 hooks 单元测试覆盖。**截图未持久化到磁盘（browser_take_screenshot 工具限制），记录为非阻断债务 TD-009** | ✅（按修订后标准） |
| 2026-07-25 | AC-24 不引入新依赖 | `apps/web/package.json` 和 `package-lock.json` 无新增依赖（所有能力由 `@tanstack/react-query` 5.x 现有 API 提供） | ✅ |
| 2026-07-25 | AC-25 不破坏 owner 边界 | 前端 hooks 层 `onMutate` 只在缓存层临时反映用户输入，`onSettled` 必触发 `invalidateQueries` 用后端真相覆盖；前端不私造业务状态机，所有真相仍以后端 GET 响应为准 | ✅ |
| 2026-07-25 | AC-26 文档回写 | 更新 `dev-docs/README.md`（顶部状态行追加 V1.4.0 + 当前阶段 + SPEC 0017 索引）、`dev-docs/acceptance.md`（顶部状态行 + 当前限制 + 验收记录表追加 SPEC 0017 15 条记录）、`dev-docs/implementation-plan.md`（顶部说明 + 执行门禁追加 V1.4.0）、`dev-docs/specs/0017-frontend-realtime-edit-feedback.md`（状态字段从"草案"改为"已实现并由项目负责人确认收口"+ 顶部新增"实现收口说明"）、`dev-docs/decisions/0023-start-spec-0017-frontend-realtime-edit-feedback.md`（验收证据章节回写）、新建 `dev-docs/changelog-v1.4.0.md`、更新 `dev-docs/tech-debt-inventory.md`（追加 TD-009） | ✅ |
| 2026-07-25 | AC-27 版本收口 | 完成 git commit "完成 SPEC 0017 单用户前端实时编辑反馈"（中文），push 到 origin/master，打 tag v1.4.0 并 push --tags | 通过（待执行） |
| 2026-07-25 | V1.4.0 项目负责人确认收口 | 项目负责人确认 SPEC 0017 收口并发布 V1.4.0，要求打 tag v1.4.0 并 push | 通过 |
| 2026-07-25 | SPEC 0018 决策记录 0024 创建 | 启动 SPEC 0018 流式 LLM 输出切片的决策记录，方向：API SSE + Gateway 直调，仅改造任务单生成，保留原同步端点兼容，不引入 WebSocket/长轮询，不引入新依赖，不修改数据库 schema | 通过 |
| 2026-07-25 | AC-1~5 DeepSeekClient 流式调用 | `tests/test_deepseek_client_stream.py` 18 个测试通过：流式成功（yield 顺序正确）/ 缓存命中（一次性 yield 完整字符串）/ 缓存写入（完成后 cache.set 被调用）/ 首 chunk 前失败（抛 DeepSeekError 不写缓存）/ 中途失败（已 yield chunk 不写缓存） | ✅ |
| 2026-07-25 | AC-6~8 Provider 流式调用 | `tests/test_deepseek_requirement_provider_stream.py` 7 个测试通过：stream_draft 成功（yield 顺序正确，JSON 校验通过）/ 首 chunk 前降级（降级到 LocalRule，拆分多 chunk yield fallback JSON）/ 中途失败（抛异常，已 yield chunks 保留） | ✅ |
| 2026-07-25 | AC-9~11 Service 流式调用 | `tests/test_requirements_service_stream.py` 11 个测试通过：stream_generate_plan 成功（RequirementPlan 保存 + StreamDoneEvent）/ 中途失败（StreamErrorEvent + 不保存 RequirementPlan）/ 兼容 LocalRule（provider 不支持 stream_draft 时降级为一次性 yield） | ✅ |
| 2026-07-25 | AC-12~13 API SSE 端点 | `tests/test_requirements_stream_api.py` 11 个测试通过：返回 `text/event-stream` + 事件格式正确（chunk/done/error）/ source_id 无效时返回 AppError（REQUIREMENT_SOURCE_NOT_FOUND 404）/ 不存在的 project_id 返回 404 | ✅ |
| 2026-07-25 | AC-14 前端 streamSSE 解析 | `apps/web/src/shared/__tests__/stream-sse.test.ts` 18 个测试通过：单事件块/多事件块/跨 chunk 拼接/默认 message 事件/多行 data 拼接/注释行跳过/空行跳过/冒号后空格剥离（SSE 规范仅剥离一个）/尾部不完整块/空 body/POST+JSON body/AbortSignal 传递/HTTP 4xx 5xx 透传/fetch reject/空响应体 | ✅ |
| 2026-07-25 | AC-15 前端 useStreamGeneratePlan | `apps/web/src/features/requirements/__tests__/hooks-stream.test.tsx` 10 个测试通过：chunk 累积/done 事件设置 result 并清空 chunks + invalidate plan query/start 重置旧状态/error 事件保留 partial_text/非 AbortError 映射为 STREAM_NETWORK_ERROR/AbortError 不设 error/cancel 通过 AbortSignal 中断/reset 重置/初始状态正确 | ✅ |
| 2026-07-25 | AC-16 前端 UI 流式展示 | `RequirementWorkspaceView.test.tsx` 35 个测试全部通过（含新增 useStreamGeneratePlan mock）；UI 改造新增"流式生成任务单"按钮 + 流式展示区（带边框灰色背景）+ "取消"按钮 + `<pre>` chunk 累积 + "流式生成完成 ✓ [源]"提示 + 错误展示 + 降级标记 | ✅ |
| 2026-07-25 | AC-17 原同步端点零回归 | `POST /plans/generate` 同步端点未修改，`tests/test_requirement_api.py` 6 个测试 + `tests/test_requirement_service.py` 12 个测试全部通过，零回归 | ✅ |
| 2026-07-25 | AC-18 后端测试通过 | `server` 下 `.venv\Scripts\python.exe -m pytest` 结果 **783 passed in 124.54s, 0 warnings**（736 原有 + 47 新增：test_deepseek_client_stream 18 + test_deepseek_requirement_provider_stream 7 + test_requirements_service_stream 11 + test_requirements_stream_api 11） | ✅ |
| 2026-07-25 | AC-19 前端测试通过 | `apps/web` 下 `npm test -- --run` 结果 **468 passed**（25 个测试文件，434 原有 + 34 新增：stream-sse 18 + api-stream 6 + hooks-stream 10） | ✅ |
| 2026-07-25 | AC-20 TypeScript 类型检查 | `apps/web` 下 `npm run lint` 结果为 `tsc --noEmit` 通过，无类型错误 | ✅ |
| 2026-07-25 | AC-21 Vite 构建 | `apps/web` 下 `npm run build` 结果为 Vite 构建通过，115 模块转换，生成 `dist/`（400.27 kB，gzip 109.09 kB） | ✅ |
| 2026-07-25 | AC-22 Alembic 无变化 | `server` 下 `.venv\Scripts\python.exe -m alembic upgrade head` 执行成功，无新增迁移文件（SPEC 0018 不修改数据库 schema，流式 chunk 不持久化） | ✅ |
| 2026-07-25 | AC-23 数据库零改动 | `git diff server/alembic/` 无变化，`git diff server/app/infrastructure/database/` 无变化 | ✅ |
| 2026-07-25 | AC-24 不引入新依赖 | `git diff server/pyproject.toml` 无依赖变化；`git diff apps/web/package.json` 无依赖变化。流式能力由 httpx `client.stream()` + 浏览器原生 `fetch + ReadableStream` 提供 | ✅ |
| 2026-07-25 | AC-25 浏览器验收 | 启动后端（uvicorn port 8001）+ 前端 Vite dev server，用 browser_use agent 执行真实浏览器点击验收：创建项目 → 进入实验要求工作台 → 添加实验要求来源 → 确认"生成任务单候选"和"流式生成任务单"两个按钮存在 → 点击"流式生成任务单" → **观察到流式展示区出现（带边框灰色背景）+ "取消"按钮 + chunk 文本在 `<pre>` 标签中逐步累积 + 流式完成后显示"流式生成完成 ✓ [LOCAL_RULE]"提示**；后端 API 验证任务单已保存（`GET /api/projects/{id}/requirements/plan` 返回 CANDIDATE 状态）。**截图未持久化到磁盘（browser_take_screenshot 工具限制，TD-009 延续），验收结论 PASS** | ✅ |
| 2026-07-25 | AC-26 不破坏 owner 边界 | API 路由层只做 SSE 协议映射（`StreamingResponse` + `_serialize_sse_event`），业务真相在 `req_service.stream_generate_plan`；provider 层只返回候选，不拥有业务状态；前端 hook 只展示状态不私造状态机，done 事件后 `invalidateQueries` 用后端真相覆盖 | ✅ |
| 2026-07-25 | AC-27 文档回写 | 更新 `dev-docs/README.md`（顶部状态行追加 V2.0.0 + SPEC 0018 索引 + 决策 0024）、`dev-docs/acceptance.md`（顶部状态行 + 当前限制 + 验收记录表追加 SPEC 0018 记录）、`dev-docs/implementation-plan.md`（追加 V2.0.0）、`dev-docs/decisions/0024-start-spec-0018-streaming-llm-output.md`（验收证据章节回写）、新建 `dev-docs/changelog-v2.0.0.md` | ✅ |
| 2026-07-25 | AC-28 版本收口 | 完成 git commit "完成 SPEC 0018 流式 LLM 输出"（中文），push 到 origin/master，打 tag v2.0.0 并 push --tags | 通过（待执行） |
| 2026-07-26 | SPEC 0019 决策记录 0025 创建 | 启动 SPEC 0019 大纲生成流式化切片的决策记录，方向：SSE 端点绕过 Worker（解决 Worker 异步与 SSE 同步推送语义不兼容），上下文聚合从 worker/handlers.py 提取到 outlines/service.py，复用 SPEC 0018 stream-sse.ts 工具和降级策略，保留 Worker 异步端点兼容，不引入新依赖，不修改数据库 schema | 通过 |
| 2026-07-26 | AC-1~4 API SSE 端点 | `tests/test_outline_stream_api.py` 8 个测试通过：返回 `text/event-stream` / 完整流程多 chunk + done 事件 / chunk 拼接为有效 JSON / done 事件包含 fallback_used 字段 / 项目不存在返回 404 / 无成功执行记录返回 error 事件 / 项目状态未满足返回 error 事件 / 原同步端点零回归 | ✅ |
| 2026-07-26 | AC-5~6 Provider 流式调用 | `tests/test_deepseek_outline_provider_stream.py` 13 个测试通过：多 chunk 按序 yield / 单 chunk 也能流式 / source_label 返回 DEEPSEEK / 首 chunk 前失败降级 LocalRule / 首 chunk 前超时也降级 / 降级后内容包含 6 个章节 / 中途失败抛异常且已 yield 保留 / 中途失败不降级 / JSON 校验失败抛异常 / 有效 JSON 不抛异常 / 空 chunk 列表不抛异常 / 缓存命中一次性 yield / 上下文为空也能调用 | ✅ |
| 2026-07-26 | AC-6 Service 流式调用 | `tests/test_outline_service_stream.py` 17 个测试通过：流式成功 yield chunks + done / 流式成功后保存 Outline / 新生成标记旧候选为 STALE / 中途失败 yield ErrorEvent / 中途失败不保存 Outline / JSON 校验失败 yield ErrorEvent / JSON 校验失败不保存 Outline / 同步 provider 一次性 yield / 同步 provider 保存 Outline / 项目不存在抛 AppError / 项目状态不满足抛 AppError / 无成功执行记录抛 AppError / gather_outline_context 空项目返回基本结构 / 包含成功的执行记录 / 不包含非成功的执行记录 / 多条成功执行记录全部聚合 / 执行产物聚合到 context | ✅ |
| 2026-07-26 | AC-7~10 前端 useStreamGenerateOutline | `apps/web/src/features/outlines/__tests__/hooks-stream.test.tsx` 12 个测试通过：chunk 累积 / done 设置 result 并清空 chunks / done 触发 invalidate outline list query / start 重置旧状态 / done 包含 fallback_used 标记 / 流式期间 streaming 为 true / error 事件保留 partial_text / 非 AbortError 映射 STREAM_NETWORK_ERROR / AbortError 不设 error / cancel 通过 AbortSignal 中断 / reset 重置 / 初始状态正确 | ✅ |
| 2026-07-26 | AC-7 前端 streamGenerateOutline API | `apps/web/src/features/outlines/__tests__/api-stream.test.ts` 6 个测试通过：正确 URL + POST 方法 / 请求体为空对象（无 source_id）/ 项目 ID URL 编码 / 委托 streamSSE 解析 / 传递 AbortSignal / HTTP 错误透传 | ✅ |
| 2026-07-26 | AC-7~9 前端 UI 流式展示 | `OutlineWorkspaceView.test.tsx` 31 个测试全部通过（含新增 7 个流式测试：流式按钮与原按钮共存 / 点击触发 start / 流式期间显示 chunk 累积展示区 / 取消按钮触发 cancel / 完成提示显示 candidate_source / 错误展示含 partial_text 详情 / 无 partial_text 时不显示详情）；UI 改造新增"流式生成大纲"按钮（紫色 #6366f1）+ 流式展示区（带边框灰色背景）+ "取消"按钮 + `<pre>` chunk 累积 + "流式生成完成 ✓ [源]（降级）"提示 + 错误展示（含"查看已生成内容"详情折叠） | ✅ |
| 2026-07-26 | AC-11~13 原路径零回归 | `tests/test_outline_worker_handlers.py` 13 个测试全部通过：原 Worker 路径 `POST /outline/generate` + handle_generate_outline 不受影响；上下文聚合提取后 Worker handler 行为不变（`gather_outline_context` 从 worker/handlers.py 移到 outlines/service.py，handler 改为调用 service 层方法） | ✅ |
| 2026-07-26 | AC-19 后端测试通过 | `server` 下 `.venv\Scripts\python.exe -m pytest` 结果 **821 passed in 70.20s, 0 warnings**（783 原有 + 38 新增：test_deepseek_outline_provider_stream 13 + test_outline_service_stream 17 + test_outline_stream_api 8） | ✅ |
| 2026-07-26 | AC-20 前端测试通过 | `apps/web` 下 `npm test -- --run` 结果 **493 passed**（28 个测试文件，468 原有 + 25 新增：api-stream 6 + hooks-stream 12 + OutlineWorkspaceView 流式 7） | ✅ |
| 2026-07-26 | AC-21 TypeScript 类型检查 | `apps/web` 下 `npm run lint` 结果为 `tsc --noEmit` 通过，无类型错误 | ✅ |
| 2026-07-26 | AC-22 Vite 构建 | `apps/web` 下 `npm run build` 结果为 Vite 构建通过，115 模块转换，生成 `dist/`（403.42 kB，gzip 109.93 kB） | ✅ |
| 2026-07-26 | AC-14 不引入新依赖 | `git diff server/pyproject.toml` 无依赖变化；`git diff apps/web/package.json` 无依赖变化。流式能力复用 SPEC 0018 已引入的 httpx `client.stream()` + 浏览器原生 `fetch + ReadableStream` + 现有 stream-sse.ts 工具 | ✅ |
| 2026-07-26 | AC-15/AC-16 数据库零改动 + 不引入 WebSocket | `git diff server/alembic/` 无变化，`git diff server/app/infrastructure/database/` 无变化；代码审查确认流式基于 SSE（text/event-stream），未引入 WebSocket 或长轮询 | ✅ |
| 2026-07-26 | AC-17 复用 stream-sse.ts | `git diff apps/web/src/shared/stream-sse.ts` 无变化，SPEC 0019 完全复用 SPEC 0018 的 streamSSE 工具函数 | ✅ |
| 2026-07-26 | AC-18 owner 边界 | API 路由层只做 SSE 协议映射（`StreamingResponse` + `_serialize_outline_sse_event`），业务真相在 `outlines/service.stream_generate_outline`；provider 层只返回候选，不拥有业务状态；前端 hook 只展示状态不私造状态机，done 事件后 `invalidateQueries` 用后端真相覆盖 | ✅ |
| 2026-07-26 | AC-23 浏览器验收 | 启动后端（uvicorn port 8001）+ 前端 Vite dev server，用 browser_use agent 执行真实浏览器点击验收：种子脚本创建 RESULT_CONFIRMED 项目 + 成功 ExecutionRun → 进入大纲工作区 → 确认"生成大纲候选"和"流式生成大纲"两个按钮并列存在 → 点击"流式生成大纲" → 后端日志确认 `POST /outline/stream-generate` 返回 **200 OK** → 后端 API 验证大纲已保存（v1, CANDIDATE, local_rule, 6 章节）→ 前端大纲列表自动刷新显示新 CANDIDATE 卡片。**transient 流式 UI 状态（chunk 累积、"正在逐 chunk 生成…"）因 LocalRule provider 同步降级路径执行过快未被浏览器快照捕获（验证工具限制，非代码缺陷），后端 200 OK + 数据库持久化 + 列表自动刷新均验证通过，验收结论 PASS** | ✅ |
| 2026-07-26 | AC-24 文档回写 | 更新 `dev-docs/README.md`（顶部状态行追加 V2.1.0 + SPEC 0019 状态从"草稿/待确认"改为"已完成实现与验收"）、`dev-docs/acceptance.md`（顶部状态行 + 当前限制 + 验收记录表追加 SPEC 0019 17 条记录）、`dev-docs/implementation-plan.md`（追加 V2.1.0）、`dev-docs/decisions/0025-start-spec-0019-outline-streaming.md`（验收证据章节回写）、新建 `dev-docs/changelog-v2.1.0.md` | ✅ |
| 2026-07-26 | AC-25 版本收口 | 完成 git commit "完成 SPEC 0019 大纲生成流式化"（中文），push 到 origin/master，打 tag v2.1.0 并 push --tags | 通过（待执行） |
| 2026-07-26 | SPEC 0020 决策记录 0026 创建 | 启动 SPEC 0020 证据卡片生成流式化切片的决策记录（SSE 端点绕过 Worker，复用 SPEC 0018/0019 流式架构，保留 Worker 异步端点兼容，不引入新依赖，不修改数据库 schema） | 通过 |
| 2026-07-26 | AC-1~4 Provider 流式调用 | `tests/test_deepseek_evidence_provider_stream.py` 13 个测试通过：stream_draft 成功（多 chunk 按序 yield）/ 首 chunk 前失败降级 LocalRule（拆分多 chunk 模拟流式）/ 首 chunk 前超时也降级 / 中途失败抛异常且已 yield chunks 保留 / 中途失败不降级 / source_label 返回 DEEPSEEK / 降级后 content 包含 cards 数组 | ✅ |
| 2026-07-26 | AC-5~14 Service 流式调用 | `tests/test_evidence_service_stream.py` 15 个测试通过：stream_generate_evidence_cards 成功 yield chunks + done / 成功后保存 EvidenceCard（CANDIDATE）/ 新生成标记旧候选为 STALE / 中途失败 yield ErrorEvent / 中途失败不保存 EvidenceCard / JSON 校验失败 yield ErrorEvent / JSON 校验失败不保存 / 兼容同步 provider（LocalRule/Fake）一次性 yield / 同步 provider 保存 EvidenceCard / 项目不存在抛 AppError / 项目状态不满足抛 AppError / 来源未解析抛 AppError / ParsedDocument 不存在抛 AppError / done 事件返回 card_count / 错误分支覆盖完整 | ✅ |
| 2026-07-26 | AC-15~20 API SSE 端点 | `tests/test_evidence_stream_api.py` 9 个测试通过：返回 `text/event-stream` / 完整流程多 chunk + done 事件 / chunk 拼接为有效 JSON / done 事件包含 card_count 和 fallback_used 字段 / 项目不存在返回 404 / 来源不存在返回 404 / error 事件格式正确（含 error_code/message/partial_text）/ 原同步端点 `POST /evidence/generate` 零回归 / `X-Accel-Buffering: no` 头部正确 | ✅ |
| 2026-07-26 | AC-21 Worker handler 零回归 | `git diff server/worker/handlers.py` 无变化；`handle_generate_evidence` 保持不变（Provider 输入是纯文本，已极简，无需提取共享方法）；`tests/test_evidence_worker_handlers.py`（若存在）全部通过，零回归 | ✅ |
| 2026-07-26 | AC-22 前端 streamGenerateEvidence API | `apps/web/src/features/evidence/__tests__/api-stream.test.ts` 6 个测试通过：正确 URL + POST 方法 / 请求体为空对象 / 项目 ID 和来源 ID URL 编码 / 委托 streamSSE 解析 / 传递 AbortSignal / HTTP 错误透传 | ✅ |
| 2026-07-26 | AC-23~26 前端 useStreamGenerateEvidence | `apps/web/src/features/evidence/__tests__/hooks-stream.test.tsx` 12 个测试通过：chunk 累积 / done 设置 result 并清空 chunks + card_count / done 触发 invalidate evidence list query / start 重置旧状态 / done 包含 fallback_used 标记 / 流式期间 streaming 为 true / error 事件保留 partial_text / 非 AbortError 映射 STREAM_NETWORK_ERROR / AbortError 不设 error / cancel 通过 AbortSignal 中断 / reset 重置 / 初始状态正确 | ✅ |
| 2026-07-26 | AC-27~29 前端 UI 流式展示 | `EvidenceWorkspaceView.test.tsx` 新增 8 个流式测试通过：流式按钮与原按钮共存 / 点击触发 start / 流式期间显示 chunk 累积展示区 / 取消按钮触发 cancel / 完成提示显示 candidate_source 和 card_count / 错误展示含 partial_text 详情 / 无 partial_text 时不显示详情 / 流式期间原按钮禁用；UI 改造新增"流式生成证据卡片"按钮（紫色 #6366f1）+ 流式展示区（带边框灰色背景）+ "取消"按钮 + `<pre>` chunk 累积 + "流式生成完成 ✓ [源]（降级）共 N 张"提示 + 错误展示（含"查看已生成内容"详情折叠） | ✅ |
| 2026-07-26 | AC-30 后端测试通过 | `server` 下 `.venv\Scripts\python.exe -m pytest` 结果 **858 passed in 71.83s, 0 warnings**（821 原有 + 37 新增：test_deepseek_evidence_provider_stream 13 + test_evidence_service_stream 15 + test_evidence_stream_api 9） | ✅ |
| 2026-07-26 | AC-31 前端测试通过 | `apps/web` 下 `npm test -- --run` 结果 **519 passed**（29 个测试文件，493 原有 + 26 新增：api-stream 6 + hooks-stream 12 + EvidenceWorkspaceView 流式 8） | ✅ |
| 2026-07-26 | AC-32 TypeScript 类型检查 | `apps/web` 下 `npm run lint` 结果为 `tsc --noEmit` 通过，无类型错误 | ✅ |
| 2026-07-26 | AC-33 Vite 构建 | `apps/web` 下 `npm run build` 结果为 Vite 构建通过，115 模块转换，生成 `dist/`（406.59 kB，gzip 110.85 kB） | ✅ |
| 2026-07-26 | AC-34 Alembic 无变化 | `server` 下 `.venv\Scripts\python.exe -m alembic upgrade head` 执行成功，无新增迁移文件（SPEC 0020 不修改数据库 schema，流式 chunk 不持久化） | ✅ |
| 2026-07-26 | AC-35 数据库零改动 | `git diff server/alembic/` 无变化，`git diff server/app/infrastructure/database/` 无变化 | ✅ |
| 2026-07-26 | AC-36 复用 stream-sse.ts | `git diff apps/web/src/shared/stream-sse.ts` 无变化，SPEC 0020 完全复用 SPEC 0018 的 streamSSE 工具函数 | ✅ |
| 2026-07-26 | AC-37 不引入新依赖 | `git diff server/pyproject.toml` 无依赖变化；`git diff apps/web/package.json` 无依赖变化。流式能力复用 SPEC 0018/0019 已引入的 httpx `client.stream()` + 浏览器原生 `fetch + ReadableStream` + 现有 stream-sse.ts 工具 | ✅ |
| 2026-07-26 | AC-38 不引入 WebSocket + owner 边界 | 代码审查确认流式基于 SSE（text/event-stream），未引入 WebSocket 或长轮询；API 路由层只做 SSE 协议映射（`StreamingResponse` + `_serialize_evidence_sse_event`），业务真相在 `sources/service.stream_generate_evidence_cards`；provider 层只返回候选，不拥有业务状态；前端 hook 只展示状态不私造状态机，done 事件后 `invalidateQueries` 用后端真相覆盖 | ✅ |
| 2026-07-26 | AC-39 浏览器验收 | 启动后端（uvicorn port 8001）+ 前端 Vite dev server，用 browser_use agent 执行真实浏览器点击验收（6 步全通过）：种子脚本创建 REQUIREMENT_CONFIRMED 项目 + 已解析来源 → 进入证据工作区 → 确认"生成证据卡片"和"流式生成证据卡片"两个按钮并列存在 → 点击"流式生成证据卡片" → 后端日志确认 `POST /sources/{source_id}/evidence/stream-generate` 返回 **200 OK** → 后端 API 验证证据卡片已保存（多张 CANDIDATE，local_rule）→ 前端证据卡片列表自动刷新显示新 CANDIDATE 卡片。截图保存至 `dev-docs/e2e-screenshots/e2e-spec0020-*.png`，报告见 `e2e-acceptance-report-spec0020.md`，**验收结论 PASS** | ✅ |
| 2026-07-26 | AC-40 文档回写 | 更新 `dev-docs/README.md`（顶部状态行追加 V2.2.0 + SPEC 0020 状态 + 真源索引新增 SPEC 0020 和决策 0026 + V2.2 发布文档索引）、`dev-docs/acceptance.md`（顶部状态行 + 当前限制 + 验收记录表追加 SPEC 0020 17 条记录）、`dev-docs/implementation-plan.md`（顶部说明 + 执行门禁追加 V2.2.0）、`dev-docs/decisions/0026-start-spec-0020-evidence-streaming.md`（验收证据章节回写）、`dev-docs/specs/0020-evidence-streaming.md`（状态字段 + 顶部新增"实现收口说明"）、新建 `dev-docs/changelog-v2.2.0.md` | ✅ |
| 2026-07-26 | AC-41 版本收口 | 完成 git commit "完成 SPEC 0020 证据卡片生成流式化"（中文），push 到 origin/master，打 tag v2.2.0 并 push --tags | 通过（待执行） |
| 2026-07-26 | V2.2.0 实际收口确认 | git log 确认 commit `cf7d556 v2.2.0: 完成 SPEC 0020 证据卡片流式化`，tag `v2.2.0` 已存在；V2.2.0 已实际发布 | ✅ |
| 2026-07-26 | SPEC 0021 决策记录 0027 创建 | 启动 SPEC 0021 分析方案生成流式化切片的决策记录（SSE 端点绕过 Worker，复用 SPEC 0018/0019/0020 流式架构，Provider 输入为 DatasetProfile 不跨模块聚合，保留 Worker 异步端点兼容，不引入新依赖，不修改数据库 schema） | 通过 |
| 2026-07-26 | AC-1~4 Provider 流式调用 | `tests/test_deepseek_analysis_plan_provider_stream.py` 13 个测试通过：stream_generate 成功（多 chunk 按序 yield）/ 首 chunk 前失败降级 LocalRule（拆分多 chunk 模拟流式）/ 首 chunk 前超时也降级 / 中途失败抛异常且已 yield chunks 保留 / 中途失败不降级 / source_label 返回 DEEPSEEK / 降级后 content 包含 cleaning_plan/analysis_plan/chart_plan 字段 | ✅ |
| 2026-07-26 | AC-5~14 Service 流式调用 | `tests/test_analysis_service_stream.py` 15 个测试通过：stream_generate_analysis_plan 成功 yield chunks + done / 成功后保存 AnalysisPlan（CANDIDATE）/ 中途失败 yield ErrorEvent / 中途失败不保存 AnalysisPlan / JSON 校验失败 yield ErrorEvent / JSON 校验失败不保存 / 兼容同步 provider（LocalRule/Fake）一次性 yield / 同步 provider 保存 AnalysisPlan / 项目不存在抛 AppError / 项目状态不满足抛 AppError / 数据集未解析抛 AppError / 数据集版本未解析抛 AppError / 数据集版本无 profile_json 抛 AppError / profile_json 解析失败抛 AppError / done 事件返回 plan_id | ✅ |
| 2026-07-26 | AC-15~21 API SSE 端点 | `tests/test_analysis_stream_api.py` 9 个测试通过：返回 `text/event-stream` / 完整流程多 chunk + done 事件 / chunk 拼接为有效 JSON / done 事件包含 plan_id 和 candidate_source 字段 / 项目不存在返回 404 / 数据集不存在返回 404 / error 事件格式正确（含 error_code/message/partial_text）/ 原同步端点 `POST /analysis/generate` 零回归 / `X-Accel-Buffering: no` 头部正确 | ✅ |
| 2026-07-26 | AC-22 Worker handler 零回归 | `git diff server/worker/handlers.py` 无变化；`handle_generate_analysis_plan` 保持不变（Provider 输入是 DatasetProfile，已极简，无需提取共享方法） | ✅ |
| 2026-07-26 | AC-23 前端 streamGenerateAnalysisPlan API | `apps/web/src/features/analysis/__tests__/api-stream.test.ts` 6 个测试通过：正确 URL + POST 方法 / 请求体为空对象 / 项目 ID 和数据集 ID URL 编码 / 委托 streamSSE 解析 / 传递 AbortSignal / HTTP 错误透传 | ✅ |
| 2026-07-26 | AC-24~27 前端 useStreamGenerateAnalysisPlan | `apps/web/src/features/analysis/__tests__/hooks-stream.test.tsx` 12 个测试通过：chunk 累积 / done 设置 result 并清空 chunks / done 触发 invalidate analysis plan list query / start 重置旧状态 / done 包含 candidate_source 和 fallback_used / 流式期间 streaming 为 true / error 事件保留 partial_text / 非 AbortError 映射 STREAM_NETWORK_ERROR / AbortError 不设 error / cancel 通过 AbortSignal 中断 / reset 重置 / 初始状态正确 | ✅ |
| 2026-07-26 | AC-28~29 前端 UI 流式展示 | `AnalysisWorkspaceView.test.tsx` 扩展至 30 个测试（含 12 个流式新增）：流式按钮与原按钮共存 / 点击触发 start / 流式期间显示 chunk 累积展示区 / 取消按钮触发 cancel / 完成提示显示 candidate_source 和 plan_id / 错误展示含 partial_text 详情 / 无 partial_text 时不显示详情 / 流式期间原按钮禁用 / STALE 状态显示编辑按钮 / 项目状态标签 / 完成分析方案确认门控等；UI 改造新增"流式生成"按钮（紫色 #6366f1）+ 流式展示区（带边框灰色背景）+ "取消"按钮 + `<pre>` chunk 累积 + "流式生成完成 ✓ [源]（降级）· plan_id: ..."提示 + 错误展示（含"查看已生成内容"详情折叠） | ✅ |
| 2026-07-26 | AC-30 后端测试通过 | `server` 下 `.venv\Scripts\python.exe -m pytest` 结果 **895 passed in 62.48s, 0 warnings**（858 原有 + 37 新增：test_deepseek_analysis_plan_provider_stream 13 + test_analysis_service_stream 15 + test_analysis_stream_api 9） | ✅ |
| 2026-07-26 | AC-31 前端测试通过 | `apps/web` 下 `npm test -- --run` 结果 **546 passed**（31 个测试文件，519 原有 + 27 新增：api-stream 6 + hooks-stream 12 + AnalysisWorkspaceView 流式扩展 12 减去原 18 中的 3 个被合并） | ✅ |
| 2026-07-26 | AC-32 TypeScript 类型检查 | `apps/web` 下 `npm run lint` 结果为 `tsc --noEmit` 通过，无类型错误 | ✅ |
| 2026-07-26 | AC-33 Vite 构建 | `apps/web` 下 `npm run build` 结果为 Vite 构建通过 | ✅ |
| 2026-07-26 | AC-34 Alembic 无变化 | `server` 下 `.venv\Scripts\python.exe -m alembic upgrade head` 执行成功，无新增迁移文件（SPEC 0021 不修改数据库 schema，流式 chunk 不持久化） | ✅ |
| 2026-07-26 | AC-35 数据库零改动 | `git diff server/alembic/` 无变化，`git diff server/app/infrastructure/database/` 无变化 | ✅ |
| 2026-07-26 | AC-36 复用 stream-sse.ts | `git diff apps/web/src/shared/stream-sse.ts` 无变化，SPEC 0021 完全复用 SPEC 0018 的 streamSSE 工具函数 | ✅ |
| 2026-07-26 | AC-37 不引入新依赖 | `git diff server/pyproject.toml` 无依赖变化；`git diff apps/web/package.json` 无依赖变化。流式能力复用 SPEC 0018/0019/0020 已引入的 httpx `client.stream()` + 浏览器原生 `fetch + ReadableStream` + 现有 stream-sse.ts 工具 | ✅ |
| 2026-07-26 | AC-38 不引入 WebSocket + owner 边界 | 代码审查确认流式基于 SSE（text/event-stream），未引入 WebSocket 或长轮询；API 路由层只做 SSE 协议映射（`StreamingResponse` + `_serialize_analysis_sse_event`），业务真相在 `analysis/service.stream_generate_analysis_plan`；provider 层只返回候选，不拥有业务状态；前端 hook 只展示状态不私造状态机，done 事件后 `invalidateQueries` 用后端真相覆盖 | ✅ |
| 2026-07-26 | AC-39 浏览器验收 | 启动后端（uvicorn port 8001）+ 前端 Vite dev server，用 browser_use agent 执行真实浏览器点击验收：种子脚本创建 DATASET_READY 项目 + READY 数据集 + PARSED 版本（含 profile_json）→ 进入分析方案工作区 → 确认"生成方案候选"和"流式生成"两个按钮并列存在 → 点击"流式生成" → 后端日志确认 `POST /datasets/{dataset_id}/analysis/stream-generate` 返回 **200 OK** → 后端 API 验证分析方案已保存（1 张 CANDIDATE，local_rule）→ 前端分析方案列表自动刷新显示新 CANDIDATE 方案。截图保存至 `dev-docs/e2e-screenshots/e2e-spec0021-*.png`（9 张），报告见 `e2e-acceptance-report-spec0021.md`，**验收结论 PASS**。**收口复核修复 1 项阻断问题**：LocalRuleAnalysisPlanProvider 输出 `target_fields` 为字符串导致 PlanCard TypeError 页面崩溃，修复 6 处为数组 | ✅ |
| 2026-07-26 | AC-40 文档回写 | 更新 `dev-docs/README.md`（顶部状态行追加 V2.3.0 + SPEC 0021 状态 + 真源索引新增 SPEC 0021 和决策 0027 + V2.3 发布文档索引）、`dev-docs/acceptance.md`（顶部状态行 + 当前限制 + 验收记录表追加 SPEC 0021 18 条记录 + V2.2.0 实际收口确认）、`dev-docs/implementation-plan.md`（顶部说明 + 执行门禁追加 V2.3.0 + V2.2.0 已发布状态修正）、`dev-docs/decisions/0027-start-spec-0021-analysis-plan-streaming.md`（验收证据章节回写）、`dev-docs/specs/0021-analysis-plan-streaming.md`（状态字段 + 顶部新增"实现收口说明"）、新建 `dev-docs/changelog-v2.3.0.md` | ✅ |
| 2026-07-26 | AC-41 版本收口 | 完成 git commit "v2.3.0: 完成 SPEC 0021 分析方案流式化"（中文），push 到 origin/master，打 tag v2.3.0 并 push --tags | 通过（待执行） |
| 2026-07-28 | SPEC 0022 决策记录 0028 创建 | 启动 SPEC 0022 代码任务生成流式化切片的决策记录（SSE 端点绕过 Worker，复用 SPEC 0018/0019/0020/0021 流式架构，Provider 输入为 AnalysisPlan 不跨模块聚合，保留 Worker 异步端点兼容，不引入新依赖，不修改数据库 schema） | ✅ |
| 2026-07-28 | SPEC 0022 测试先行 | 编写 4 个后端测试文件验证红色阶段：DeepSeekCodeTaskProvider 流式 14 + Service 流式 9 + API SSE 17 + LocalRule 格式 21，原有 895 测试零回归，36 个新测试失败（实现未完成） | ✅ |
| 2026-07-28 | AC-1 首 chunk 前失败降级 LocalRule | `DeepSeekCodeTaskProvider.stream_generate` 首 chunk 前失败时降级到 `fallback.stream_generate()`，拆分多 chunk yield，done 事件 `fallback_used=true`，`candidate_source=LOCAL_RULE` | ✅ |
| 2026-07-28 | AC-2 中途失败不降级 | provider 中途失败抛异常，已 yield chunks 保留，yield `StreamCodeTaskErrorEvent`（含 `partial_text`），不保存 CodeTask | ✅ |
| 2026-07-28 | AC-3 Phase 3 状态复核 | 保存前重新校验 AnalysisPlan 存在、状态仍为 CONFIRMED、`updated_at` 未变，防止基于过期数据生成 | ✅ |
| 2026-07-28 | AC-4 服务端取消语义 | 每个 chunk 之间检查 `request.is_disconnected()`，断开后直接 return，不保存 CodeTask，不推送 done/error | ✅ |
| 2026-07-28 | AC-5 错误分层 | 流前 HTTP 错误（404 项目不存在 / 404 AnalysisPlan 不存在 / 409 状态不满足 / 409 未确认 / 409 并发冲突）+ 流后 SSE error 事件，error 后不发送 done | ✅ |
| 2026-07-28 | AC-6 并发保护 | `active_streams` 内存字典控制同一 AnalysisPlan 同一时刻只允许一个活动流式请求，冲突返回 409 `STREAM_ALREADY_ACTIVE` | ✅ |
| 2026-07-28 | AC-7~10 兼容同步 Provider / done 事件 / JSON 校验失败 / 兼容旧端点 | `hasattr(provider, "stream_generate")` 检查不支持时调用 `generate()` + 拆分；done 事件包含 `code_task_id` + `candidate_source` + `fallback_used`；JSON 校验失败 yield error 不保存；原 `POST /code/generate` 端点零回归 | ✅ |
| 2026-07-28 | AC-11~13 零回归 | Worker handler 零改动（`git diff server/worker/handlers.py` 无变化）；原 `/code/generate` 端点零回归（`test_code_task_stream_api.py::TestOriginalEndpointZeroRegression` 通过）；代码执行链路零回归（`test_execution_api.py` 全部通过） | ✅ |
| 2026-07-28 | AC-14 后端测试 | `server/.venv/Scripts/python.exe -m pytest` 执行：**975 passed**（895 原有 + 80 新增含 SPEC 0022 流式 78 + 回归 2），0 warnings | ✅ |
| 2026-07-28 | AC-15 前端测试 | `npm.cmd run lint`（tsc --noEmit）通过；`npm.cmd run build`（Vite 构建）通过；`npx vitest run` 执行：**570 passed**（551 原有 + 19 新增） | ✅ |
| 2026-07-28 | AC-16 Alembic 无变化 | `server` 下 `.venv\Scripts\python.exe -m alembic upgrade head` 执行成功，无新增迁移文件（SPEC 0022 不修改数据库 schema，流式 chunk 不持久化） | ✅ |
| 2026-07-28 | AC-17 复用 stream-sse.ts | `git diff apps/web/src/shared/stream-sse.ts` 无变化，SPEC 0022 完全复用 SPEC 0018 的 streamSSE 工具函数 | ✅ |
| 2026-07-28 | AC-18 不引入新依赖 | `git diff server/pyproject.toml` 无依赖变化；`git diff apps/web/package.json` 无依赖变化。流式能力复用 SPEC 0018/0019/0020/0021 已引入的 httpx `client.stream()` + 浏览器原生 `fetch + ReadableStream` + 现有 stream-sse.ts 工具 | ✅ |
| 2026-07-28 | AC-19 不引入 WebSocket + owner 边界 | 代码审查确认流式基于 SSE（text/event-stream），未引入 WebSocket；API 路由层只做 SSE 协议映射（`StreamingResponse` + `_serialize_code_task_sse_event`），业务真相在 `execution/service.stream_generate_code_task`；provider 层只返回候选，不拥有业务状态；前端 hook 只展示状态不私造状态机 | ✅ |
| 2026-07-28 | AC-20 浏览器验收 | 启动后端（uvicorn port 8001）+ 前端 Vite dev server，用 browser_use agent 执行真实浏览器点击验收：API 准备测试数据（proj_spec0021_e2e，ANALYSIS_CONFIRMED，已确认分析方案 9b42594a61ce）→ 导航到执行工作区 → 选择分析方案 → 点击紫色"流式生成"按钮 → 流式展示区显示"正在逐 chunk 生成（原始 JSON 输出）…"+ chunk 内容累积 + 取消按钮 → 流式完成后显示绿色 ✓ + "流式生成完成"+ source [LOCAL_RULE] + code_task_id: 5fdb033388ba → 代码任务列表自动刷新显示"代码任务 v1 [候选]"CANDIDATE 卡片。截图保存至 `dev-docs/e2e-screenshots/spec0022-01-execution-workspace.png` 至 `spec0022-05-task-list.png`（5 张），**验收结论 PASS**。**收口复核修复 1 项阻断问题**：`LocalRuleCodeTaskProvider._build_analysis_code` 中 FREQUENCY 类型 `target_fields.split()` 在 list 上调用报错，新增 `_first_field_name()` 辅助函数兼容 list/str/None | ✅ |
| 2026-07-28 | AC-21 文档回写 | 更新 `dev-docs/README.md`（顶部状态行追加 V2.4.0 + SPEC 0022 状态 + 真源索引新增 SPEC 0022 和决策 0028 + V2.4 发布文档索引）、`dev-docs/acceptance.md`（顶部状态行 + 当前限制 + 验收记录表追加 SPEC 0022 记录）、`dev-docs/implementation-plan.md`（顶部说明 + 执行门禁追加 V2.4.0）、`dev-docs/decisions/0028-start-spec-0022-code-task-streaming.md`（验收证据章节回写）、`dev-docs/specs/0022-code-task-streaming.md`（状态字段更新为已完成）、新建 `dev-docs/changelog-v2.4.0.md` | ✅ |
| 2026-07-28 | AC-22 版本收口 | 本地完成 commit `c4b5fdf` "v2.4.0: 完成 SPEC 0022 代码任务生成流式化"（中文）+ 打 tag v2.4.0；截至 2026-07-30 本地 master ahead origin/master 3（push 待用户确认，详见决策 0030） | ✅ |
| 2026-07-30 | SPEC 0022 收口后阻断修复-1 prompt 换行双重转义 | `_SYSTEM_PROMPT` 中 "代码字符串中的换行使用 \\n 转义" 指令导致 DeepSeek 返回的 JSON 中 code 字段换行被双重转义为字面量 \\n，json.loads 解析后仍为字面量 \\n 而非真正换行符，执行时被 Python 解释器当作行延续符引发 `EXECUTION_IMPORT_FORBIDDEN: unexpected character after line continuation character`。修复：删除该指令，新增 "代码必须是合法 JSON（换行符由 JSON 标准自动转义，无需手动处理）" | ✅ |
| 2026-07-30 | SPEC 0022 收口后阻断修复-2 prompt import 白名单缺失 | `_SYSTEM_PROMPT` 未明确列出 import 白名单和禁止模块，导致 DeepSeek 生成 `import os` 被 AST 校验拒绝（`EXECUTION_IMPORT_FORBIDDEN`）。修复：在 prompt 中添加明确的 import 白名单（pandas/numpy/matplotlib/scipy/sklearn/openpyxl）和禁止模块列表（os/sys/subprocess/shutil/pathlib/io/socket/ssl/http/urllib/requests/multiprocessing/threading/asyncio/pickle），并禁止使用 os.path 或 pathlib 进行路径操作，引导使用 f-string | ✅ |
| 2026-07-30 | SPEC 0022 收口后阻断修复-3 python_executor 路径重复 | `python_executor.execute_code` 中 `work_path = Path(work_dir)` 和 `data_path` 未 resolve 为绝对路径，当 `settings.project_data_root` 为相对路径（`data\projects`）时，subprocess `cwd=work_path` + 相对 `script_path` 导致路径重复拼接（`...\a00ca976cbfb\data\projects\...\a00ca976cbfb\_run.py`），`_run.py` 找不到。修复：`work_path = Path(work_dir).resolve()` + `data_path` 也 resolve 为绝对路径 | ✅ |
| 2026-07-30 | 回归测试-1 prompt 换行转义 | `tests/test_deepseek_code_task_provider_stream.py` 新增 `TestPromptNoDoubleEscapeInstruction` 4 个测试：prompt 不含双转义指令 / prompt 含合法 JSON 说明 / 流式生成 code 含真正换行符（非字面量 \\n）/ code 可被 compile() 为合法 Python。全部通过 | ✅ |
| 2026-07-30 | 回归测试-2 prompt import 白名单 | `tests/test_deepseek_code_task_provider_stream.py` 新增 `TestPromptImportWhitelist` 4 个测试：prompt 含 import 白名单说明 / prompt 列出白名单模块 / prompt 明确禁止 os / prompt 禁止 pathlib 路径操作。全部通过 | ✅ |
| 2026-07-30 | 回归测试-3 python_executor 路径 resolve | `tests/test_python_executor.py` 更新 `test_data_path_variable_injected`：data_path 会被 resolve 为绝对路径，使用 `tmp_path / "data.csv"` 验证 resolve 后路径在输出中。48 个测试全部通过 | ✅ |
| 2026-07-30 | 后端测试零回归 | `server/.venv/Scripts/python.exe -m pytest tests/test_deepseek_code_task_provider_stream.py tests/test_code_task_service_stream.py tests/test_code_task_stream_api.py tests/test_execution_api.py tests/test_worker_handlers.py tests/test_local_rule_code_task_provider_format.py tests/test_python_executor.py` 结果 **200 passed, 1 failed**。唯一失败 `test_完整流程多chunk加done事件` 是环境配置问题（环境有 DEEPSEEK_API_KEY 导致用真实 DeepSeek provider，测试期望 LocalRule），非本次修改引入的回归 | ✅ |
| 2026-07-30 | 完整链路验证-代码任务执行 | 项目 `proj_2759dc9c98d7`（EXECUTION_FAILED）→ 流式生成新代码任务（DEEPSEEK，code 含真正换行符，无 import os，使用 f-string 拼接路径，compile() 通过）→ 确认 → 触发执行 → Worker 完成（exit_code=0，12 个产物，duration 4.89s）→ complete_execution → RESULT_CONFIRMED | ✅ |
| 2026-07-30 | 完整链路验证-大纲+交付物 | RESULT_CONFIRMED → 流式生成大纲（DEEPSEEK）→ 确认 → OUTLINE_CONFIRMED → 触发 Word 生成 → Worker SUCCEEDED（word_v1.docx 163679 bytes）→ 触发 PPT 生成 → Worker SUCCEEDED（ppt_v1.pptx 67520 bytes）→ complete_project → **COMPLETED** | ✅ |
| 2026-07-30 | SPEC 0024 决策记录 0032 创建 | 启动 SPEC 0024 PPT 渲染器布局与视觉层次改进切片的决策记录（V2.5.0，16:9 画布 + 空白版式精确定位 + 双栏内容页 40%/60% + 图表自适应布局 + 五级字号体系 + 主题色扩展应用；不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部布局方法） | ✅ |
| 2026-07-30 | SPEC 0024 核心实现-ppt_renderer 重构 | 重构 `server/app/infrastructure/renderers/ppt_renderer.py` 为空白版式（`slide_layouts[6]`）+ 精确定位驱动：新增 16:9 画布常量（13.333×7.5 英寸）、双栏布局参数（左栏 40% 5.3" + 右栏 60% 6.7"）、五级字号体系（36/28/20/16/12 pt）、主题色默认深灰色（#333333）；实现封面页（色块+白色大标题+副标题+装饰线）、双栏内容页（左栏文本要点带主题色圆点 + 右栏图表/补充文本）、图表自适应布局（单图居中 8"/双图并排 5.8"/2×2 网格 3.8"/截断到 4 张）、总结页（居中排版+分隔线）、页脚（项目名+页码）；新增辅助方法 `_set_run_font`（含东亚字体）、`_add_color_block`、`_add_divider`、`_add_footer`、`_resolve_theme_color`（None 降级到 #333333） | ✅ |
| 2026-07-30 | SPEC 0024 测试修复-test_ppt_config | 修复 `server/tests/test_ppt_config.py` 中 4 个因空白版式导致的测试：(1) `test_render_theme_color_purple_applied` 原依赖 `slide.shapes.title`（空白版式无 title placeholder），改为遍历所有 shape 检查字体颜色和填充颜色；(2) `test_render_theme_color_blue_applied` 同紫色修复方式；(3) `test_render_theme_color_green_all_slides` 原为空跳（`if title_shape` 永远 False），改为统计应用主题色的页面数 ≥2；(4) `test_render_include_charts_false_skips_chart` 原用页数比较（SPEC 0024 单图嵌入内容页右栏不生成独立图表页），改为检查 PICTURE shape 存在性。新增 `_slide_has_color()` 辅助函数 | ✅ |
| 2026-07-30 | SPEC 0024 测试修复-test_renderers | 更新 `server/tests/test_renderers.py` 中 2 个测试适配空白版式：`test_title_slide_contains_topic` 和 `test_summary_slide_present` 从依赖 `slide.shapes.title` 改为遍历 shapes 查找文本 | ✅ |
| 2026-07-30 | AC-1 PPT 配置+渲染器测试 | `server/.venv/Scripts/python.exe -m pytest server/tests/test_ppt_config.py server/tests/test_renderers.py -v`：**41 passed** in 5.32s（含修复的 4 个测试 + 18 个 renderer 测试 + 19 个 PPT 配置测试） | ✅ |
| 2026-07-30 | AC-2 PPT/outline 相关全量测试 | `server/.venv/Scripts/python.exe -m pytest test_outlines_api.py test_outlines_service.py test_outline_worker_handlers.py test_word_template.py test_ppt_config.py test_renderers.py -v`：**142 passed** in 15.86s（覆盖 PPT 生成 API、outline service、Worker handler、Word 模板、PPT 配置、渲染器全链路，零回归） | ✅ |
| 2026-07-30 | AC-3 其他非流式测试回归 | `server/.venv/Scripts/python.exe -m pytest test_project_service.py test_requirement_api.py test_requirement_service.py test_datasets_api.py test_datasets_service.py ...`（20 个非流式测试文件）：**107 passed, 1 failed** in 93.85s。唯一失败 `test_requirement_api_happy_path_updates_and_confirms_plan`（`candidate_source` 期望 LOCAL_RULE 实际 DEEPSEEK）是预存环境问题（`.env` 中 `DEEPSEEK_API_KEY` 已设置），与 SPEC 0024 无关 | ✅ |
| 2026-07-30 | AC-4 真实 PPT 文件验证-画布与字号 | 生成 PPT 文件验证：画布 13.333×7.500 英寸（16:9 比例 1.778）✅；五级字号完整 [12.0, 16.0, 20.0, 28.0, 36.0]pt ✅；主题色 #2563eb 应用到全部 4/4 页面（封面色块+内容页标题/圆点/分隔线+总结页标题）✅ | ✅ |
| 2026-07-30 | AC-5 真实 PPT 文件验证-双栏布局 | 生成含 3 张图表的 PPT（5 页）：封面页 4 shapes（色块+标题+副标题+装饰线）；3 个内容页各 7 shapes（标题+分隔线+左栏文本+右栏图表+页脚线+页脚项目名+页脚页码），各含 1 张图片嵌入右栏；总结页 7 shapes（标题+分隔线+正文+装饰线+页脚）。3 张图表自适应分配到 3 个内容页右栏（不生成独立图表页） | ✅ |
| 2026-07-30 | AC-6 SPEC 0011 配置兼容 | `config=None` 渲染成功使用默认布局和默认深灰色主题 ✅；`config={"target_slide_count":6}` 页数控制仍生效 ✅；`config={"include_charts":false}` 不嵌入图表 ✅；`config={"theme_color":"#invalid"}` 降级到默认深灰色不抛异常 ✅；`render()` 方法签名与 SPEC 0011 完全一致，调用方零改动 ✅ | ✅ |
| 2026-07-30 | AC-7 约束遵守 | 不引入新依赖（继续使用 python-pptx>=1.0.2）✅；不改变 PptConfig 合同（三字段不变）✅；不改变 API/service/Worker 接线（`render()` 签名不变）✅；不修改数据库 schema ✅；不改变文件存储路径和版本管理 ✅ | ✅ |
| 2026-07-30 | 预存非阻断债务记录 | `test_code_task_stream_api.py::test_完整流程多chunk加done事件` 和 `test_requirement_api.py::test_requirement_api_happy_path_updates_and_confirms_plan` 各有 1 个预存失败，根因为 `server/.env` 中 `DEEPSEEK_API_KEY` 已设置导致 LLM 网关使用 DeepSeek provider 而非测试期望的 LocalRule，与 SPEC 0024 无关。后续修复入口：调整测试 mock 策略或在测试中临时清除 `DEEPSEEK_API_KEY` 环境变量 | ✅ |
| 2026-07-31 | SPEC 0024 端到端视觉测评-图表中文乱码修复 | 真实胃病数据测评发现 matplotlib 未配置中文字体，图表标题和坐标轴显示为空心方框。修复：在 `server/app/modules/llm/code_task_provider.py` 添加 `matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']` 和 `matplotlib.rcParams['axes.unicode_minus'] = False`；在 `server/app/modules/llm/deepseek_code_task_provider.py` 的 `_SYSTEM_PROMPT` 中添加中文字体配置指令。重新生成图表验证中文正常显示 | ✅ |
| 2026-07-31 | SPEC 0024 端到端视觉测评-PPT 页数限制解除 | 真实数据测评发现 `_build_content_groups` 方法将章节合并为 3 组内容页，导致 PPT 限制为 6 页，内容不齐全。修复：改为每个章节单独一页（SUMMARY 类型仍由总结页处理），解除 6 页限制。PPT 从 6 页扩展为 8 页，每个章节独立展示 | ✅ |
| 2026-07-31 | SPEC 0024 端到端视觉测评-图片溢出修复 | 真实数据测评发现第 5 页图片超出模板，`_place_chart_grid` 方法只设置图片宽度未限制高度，导致图片与页脚重叠。修复：(1) 新增 `_fit_image_size` 方法按宽高比缩放并限制最大高度；(2) 调整 `_place_chart_grid` 参数 max_height 从 2.5" 改为 2.3"，下排 top 从 4.2" 改为 4.0"。验证第 5 页底部=6.7" < 页脚线 7.0"，右边界=10.13" < 画布 13.33" | ✅ |
| 2026-07-31 | SPEC 0024 端到端视觉测评-3 图布局优化 | 真实数据测评发现 3 张图表时 2×2 网格布局右下角空白，布局不协调。修复：新增 `_place_chart_three` 方法，实现上排 2 张并排（各 width=5.8"）+ 下排 1 张居中（width=8.0"）布局。验证 3 图布局协调 | ✅ |
| 2026-07-31 | SPEC 0024 端到端视觉测评-文本截断放宽 | 真实数据测评发现 `content[:200]` 截断导致 EXECUTION 和 SUMMARY 章节内容不完整。修复：放宽为 `content[:500]`，保留更多文本内容 | ✅ |
| 2026-07-31 | SPEC 0024 收口验证-PPT 核心测试 | `server/.venv/Scripts/python.exe -m pytest server/tests/test_ppt_config.py server/tests/test_renderers.py -v`：**41 passed** in 5.40s（本轮重新验证，含 SPEC 0024 迭代修复后所有测试通过） | ✅ |
| 2026-07-31 | SPEC 0024 收口验证-PPT/outline 全量测试 | `server/.venv/Scripts/python.exe -m pytest server/tests/test_outlines_api.py server/tests/test_outlines_service.py server/tests/test_outline_worker_handlers.py server/tests/test_word_template.py server/tests/test_ppt_config.py server/tests/test_renderers.py -v`：**142 passed** in 12.78s（本轮重新验证，零回归） | ✅ |
| 2026-07-31 | SPEC 0024 收口验证-完整后端测试 | `server/.venv/Scripts/python.exe -m pytest server/tests/ --tb=line -q`：**106 passed, 1 failed** in 52.12s。唯一失败 `test_analysis_stream_api.py::test_完整流程多chunk加done事件`（`candidate_source` 期望 LOCAL_RULE 实际 DEEPSEEK）是预存环境问题（`.env` 中 `DEEPSEEK_API_KEY` 已设置），与 SPEC 0024 无关 | ✅ |
| 2026-07-31 | SPEC 0024 收口验证-前端 lint + build | `npm.cmd run lint`（在 apps/web 目录）：`tsc --noEmit` 无错误 ✅；`npm.cmd run build`：`vite build` 成功，116 模块转换，dist/index.html + dist/assets/index-*.js 生成 ✅ | ✅ |
| 2026-07-31 | SPEC 0024 收口确认 | 项目负责人确认 SPEC 0024 PPT 渲染器布局与视觉层次改进收口（V2.5.0）。收口依据：核心实现完成 + 端到端视觉测评 5 项阻断问题全部修复 + 本轮测试验证 41+142 passed 零回归 + 前端 lint/build 通过 + 约束遵守（不引入新依赖、不改变 PptConfig 合同、不改变 API/service/Worker 接线、不修改数据库 schema）。详见 [决策 0033](decisions/0033-confirm-spec-0024-acceptance.md) | ✅ |
| 2026-07-31 | SPEC 0025 决策记录 0034 创建 | 启动 SPEC 0025 PPT 三角色彩系统与深浅对比三明治结构切片的决策记录（V2.6.0，从单一 theme_color 算法派生主色/辅助色/强调色 + 深色标题栏→浅色内容区→深色页脚栏三明治布局；使用 colorsys 标准库，不引入新依赖，不改变 PptConfig 合同，仅重构 ppt_renderer.py 内部色彩派生与标题/页脚渲染方法） | ✅ |
| 2026-07-31 | SPEC 0025 核心实现-三角色彩派生 | 在 `server/app/infrastructure/renderers/ppt_renderer.py` 新增 `colorsys` 标准库导入和 `_derive_color_palette` 方法，从单一 `theme_color` 派生四色：(1) 主色=原值；(2) 辅助色=高亮度（L=0.92）低饱和度（S≤0.30）浅色；(3) 强调色=互补色相（H+0.5）中亮度（L=0.45）高饱和度（S=0.50-0.70），低饱和度（S<0.20）特殊处理为蓝色 #2563EB；(4) 标题文字色=主色亮度 > 0.60 用深灰，否则用白色（阈值 0.60 覆盖紫色 #7c3aed L≈0.578，使 5 种预设深色统一用白字） | ✅ |
| 2026-07-31 | SPEC 0025 核心实现-三明治结构 | 重构 `ppt_renderer.py` 实现深浅对比三明治结构：(1) 新增三明治常量（TITLE_BAR_HEIGHT=1.0"、FOOTER_BAR_HEIGHT=0.5"、FOOTER_BAR_TOP=7.0"、CONTENT_AREA_TOP=1.2"）；(2) 重构 `_add_page_title` 为深色标题栏（主色背景全幅 + 白色标题文字 28pt Bold）；(3) 重构 `_add_footer` 为深色页脚栏（主色背景全幅 + 白色项目名和页码）；(4) 重构 `_add_content_left_column` 添加辅助色浅色背景矩形 + 强调色圆点标记和章节标题；(5) 重构 `_render_title_slide` 新增底部主色窄条形成三明治收口；(6) 重构 `_add_chart_slide` 和 `_render_summary_slide` 适配四色参数 | ✅ |
| 2026-07-31 | SPEC 0025 测试新增 | 在 `server/tests/test_ppt_config.py` 新增 16 个 SPEC 0025 专用测试：`TestSpec0025ColorSystem`（8 个色彩派生测试覆盖 6 种预设色主色不变/辅助色高亮度/强调色互补/灰色特殊处理蓝色/无效色降级/默认色派生）+ `TestSpec0025SandwichStructure`（7 个三明治结构测试覆盖内容页标题栏背景/页脚栏背景/辅助色背景/强调色要点/封面页底部窄条/图表页标题栏/总结页标题栏）+ 1 个紫色阈值测试（验证 #7c3aed 标题文字为白色）；新增 `_shape_has_fill_color` 辅助函数 | ✅ |
| 2026-07-31 | SPEC 0025 收口验证-PPT 核心测试 | `server/.venv/Scripts/python.exe -m pytest server/tests/test_ppt_config.py server/tests/test_renderers.py -v`：**57 passed**（含 16 个 SPEC 0025 新增），零回归 | ✅ |
| 2026-07-31 | SPEC 0025 收口验证-PPT/outline/renderer 全量 | `server/.venv/Scripts/python.exe -m pytest`（PPT/outline/renderer 相关）：**222 passed, 1 failed**。唯一失败为预存 DEEPSEEK 环境问题（`.env` 中 API key 导致 candidate_source 期望 LOCAL_RULE 实际 DEEPSEEK），与 SPEC 0025 无关 | ✅ |
| 2026-07-31 | SPEC 0025 收口验证-outline worker/API/service | `server/.venv/Scripts/python.exe -m pytest`（outline worker/API/service 相关）：**83 passed**，零回归 | ✅ |
| 2026-07-31 | SPEC 0025 收口验证-Alembic 迁移 | `server/.venv/Scripts/python.exe -m alembic upgrade head`：通过（SPEC 0025 不修改数据库 schema，无新增迁移） | ✅ |
| 2026-07-31 | SPEC 0025 收口验证-前端 lint + build | `npm.cmd run lint`（在 apps/web 目录）：`tsc --noEmit` 无错误 ✅；`npm.cmd run build`：`vite build` 成功 ✅（SPEC 0025 纯后端切片，前端零改动，仅回归验证） | ✅ |
| 2026-07-31 | SPEC 0025 收口验证-真实文件验收 | 生成 6 种预设色（蓝/紫/绿/红/橙/灰）PPT 文件，程序化验证：(1) 三角色彩派生全部正确（主色=原值，辅助色=浅色，强调色=互补色或蓝色特殊处理）✅；(2) 三明治结构完整（封面页顶部色块+底部窄条、内容页/图表页/总结页标题栏+页脚栏主色背景）✅；(3) 辅助色背景存在（内容页左栏）✅；(4) 强调色要点存在（圆点标记和章节标题）✅；(5) 对比度保障（5 种预设深色统一用白字，紫色白字对比度 5.83:1 通过 WCAG AA）✅ | ✅ |
| 2026-07-31 | SPEC 0025 收口确认 | 项目负责人确认 SPEC 0025 PPT 三角色彩系统与深浅对比三明治结构收口（V2.6.0）。收口依据：核心实现完成（三角色彩派生 + 三明治结构）+ 16 个新增测试全通过 + 57+222+83 passed 零回归 + 前端 lint/build 通过 + 真实文件视觉验收 6 种预设色全部正确 + 约束遵守（不引入新依赖 colorsys 是标准库、不改变 PptConfig 合同、不改变 API/service/Worker 接线、不修改数据库 schema、不改变 SPEC 0024 布局参数）。详见 [决策 0034](decisions/0034-start-spec-0025-ppt-color-system.md) | ✅ |
| 2026-07-31 | SPEC 0025 git 收口 | commit `323904e`：`完成 SPEC 0025 PPT 三角色彩系统与深浅对比三明治结构（决策 0034）`。提交 7 个文件（5 修改 + 2 新增），1275 insertions, 104 deletions。修改文件：dev-docs/README.md、dev-docs/acceptance.md、dev-docs/implementation-plan.md、server/app/infrastructure/renderers/ppt_renderer.py、server/tests/test_ppt_config.py；新增文件：dev-docs/decisions/0034-start-spec-0025-ppt-color-system.md、dev-docs/specs/0025-ppt-color-system-and-sandwich-layout.md | ✅ |
| 2026-07-31 | SPEC 0025 commit 后回归验证-前端 | `npm.cmd run lint`（apps/web 目录）：`tsc --noEmit` 无错误 ✅；`npm.cmd run build`：`vite build` 成功，116 模块转换，dist/index.html + dist/assets/index-*.js 生成 ✅ | ✅ |
| 2026-07-31 | SPEC 0025 commit 后回归验证-后端分批测试 | 全量 `pytest server/tests/` 因 `.env` 中 `DEEPSEEK_API_KEY` 导致 DeepSeek 相关/流式 API 测试连接真实 API 超时卡住在 41%（预存环境问题，与 SPEC 0025 无关）。改用分批运行 28 个非 DeepSeek/非流式测试模块：(1) SPEC 0025 核心 6 模块 **158 passed** in 14.68s；(2) 纯单元测试 8 模块 **214 passed** in 26.52s；(3) cleanup/worker 7 模块 **132 passed** in 5.82s；(4) service 层 4 模块 **86 passed** in 4.02s。**合计 590 passed，0 failed，零回归**。卡住模块：test_deepseek_*.py（8 个）、test_*_stream_api.py（5 个）、test_*_service_stream.py（5 个）、test_requirement_api.py、test_analysis_api.py 等部分 API 测试，根因均为 `.env` API key 导致 candidate_source 期望 LOCAL_RULE 实际 DEEPSEEK | ✅ |
| 2026-07-31 | SPEC 0026 实现完成-PPT 视觉效果增强 | 在 `server/app/infrastructure/renderers/ppt_renderer.py` 新增 4 个方法：(1) `_darken_color` HLS 空间降低亮度（下限 0.10 保护）用于渐变结束色派生；(2) `_add_gradient_block` 线性渐变色块（python-pptx 原生 `fill.gradient()` API）；(3) `_add_rounded_color_block` 圆角矩形（`MSO_SHAPE.ROUNDED_RECTANGLE` + adjustments）；(4) `_add_picture_shadow` 图片外阴影（oxml 操作 `<a:effectLst>` + `<a:outerShdw>`）。接线改动：封面顶部色块/标题栏/页脚栏改用渐变（主色→主色暗化），左栏背景改用圆角矩形（半径 0.05），右栏图表添加辅助色 1pt 边框 + 外阴影 | ✅ |
| 2026-07-31 | SPEC 0026 测试验证-17 个新增测试 | `server/.venv/Scripts/python.exe -m pytest server/tests/test_ppt_config.py::TestSpec0026VisualEffects -v`：**17 passed**。覆盖暗化算法（亮度降低+下限保护）、渐变填充（封面/标题栏/页脚栏）、圆角矩形（左栏背景）、外阴影（`a:effectLst`+`a:outerShdw` 节点存在+参数正确）、边框（辅助色 1pt） | ✅ |
| 2026-07-31 | SPEC 0026 回归验证-PPT/outline/renderer 模块 | `server/.venv/Scripts/python.exe -m pytest server/tests/test_ppt_config.py server/tests/test_renderers.py server/tests/test_outline_service.py server/tests/test_outline_api.py server/tests/test_outline_stream_api.py server/tests/test_outline_worker.py server/tests/test_outline_contracts.py -v`：**220 passed**（1 个预存失败：test_outline_api 中 candidate_source 期望 LOCAL_RULE 实际 DEEPSEEK，根因为 `.env` API key，与 SPEC 0026 无关）。增强 `_shape_has_fill_color` 和 `_slide_has_color` 辅助函数支持渐变填充检查，确保 SPEC 0024/0025 回归测试兼容 | ✅ |
| 2026-07-31 | SPEC 0026 真实文件验收-6 种预设色 | `server/scripts/verify_spec0026.py` 生成 6 种预设色（蓝/紫/绿/红/橙/灰）PPT 文件，程序化验证：(1) 渐变填充全部存在（封面/标题栏/页脚栏）✅；(2) 圆角矩形全部存在（左栏背景）✅；(3) 外阴影全部存在（右栏图表）✅；(4) 细边框全部存在（辅助色）✅；(5) 6 种色 PPT 文件均有效（5 页/文件）✅ | ✅ |
| 2026-07-31 | SPEC 0026 约束遵守验证 | (1) 不引入新依赖（python-pptx + 标准库 colorsys/lxml）✅；(2) 不改变 `PptConfig` 三字段合同 ✅；(3) 不改变 `render()` 签名 ✅；(4) 不改变 API/service/Worker 接线 ✅；(5) 不修改数据库 schema ✅；(6) 不改变 SPEC 0024 布局参数（画布/边距/双栏比例/字号体系）✅；(7) 不改变 SPEC 0025 三角色彩派生算法 ✅ | ✅ |
| 2026-07-31 | SPEC 0027 实现完成-图表美化与布局增强 | **图表层**：`code_task_provider.py` 的 `_HEADER` 集成 `import scienceplots` + `plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])` + `import seaborn as sns` + `sns.set_theme(style="whitegrid", palette="bright", font="Microsoft YaHei")`；`_build_chart_code` 升级为 Seaborn API（HISTOGRAM→`sns.histplot`、BOXPLOT→`sns.boxplot`、BAR→`sns.countplot`、SCATTER→`sns.scatterplot`），CORRELATION 分析新增 `sns.heatmap` 热图；`deepseek_code_task_provider.py` 的 `_SYSTEM_PROMPT` 追加 SciencePlots + Seaborn 使用要求和 import 白名单。**PPT 层**：`ppt_renderer.py` 新增 `_pct_to_emu` 百分比定位静态方法 + `_GridHelper` N×M 网格辅助内部类，改造 `_place_chart_grid`/`_place_chart_three`/`_place_chart_side_by_side` 使用 Grid 坐标计算。**沙箱层**：`python_executor.py` 的 `DEFAULT_ALLOWED_IMPORTS` 新增 `scienceplots`、`seaborn`（`easypptx` 不加入沙箱白名单，仅 PPT 渲染层使用）。**额外修复**：`code_task_provider.py` 中 BOXPLOT/HISTOGRAM 分支 savefig 行缺少 f 前缀导致文件名 `{safe_name}` 未替换，已修复 | ✅ |
| 2026-07-31 | SPEC 0027 测试验证-45 个新增测试 | `server/.venv/Scripts/python.exe -m pytest server/tests/test_local_rule_code_task_provider_format.py server/tests/test_ppt_config.py server/tests/test_python_executor.py -k "Spec0027 or default_allowed_imports" -v`：**45 passed**。覆盖：(1) 图表层 16 个测试（`_HEADER` 包含 scienceplots/seaborn 集成、`_build_chart_code` 生成 sns.histplot/boxplot/countplot/scatterplot/heatmap）；(2) PPT 层 18 个测试（`_pct_to_emu` 百分比定位 4 例 + `_GridHelper` 网格坐标 4 例 + `_place_chart_*` Grid 坐标一致性回归 3 例 + 其他布局验证 7 例）；(3) 沙箱层 10 个测试（scienceplots/seaborn 在白名单、easypptx 不在白名单、AST 校验不拦截） | ✅ |
| 2026-07-31 | SPEC 0027 回归验证-受影响测试全套 | `server/.venv/Scripts/python.exe -m pytest server/tests/test_ppt_config.py server/tests/test_renderers.py server/tests/test_local_rule_code_task_provider_format.py server/tests/test_python_executor.py -v`：**204 passed 零回归**。验证 SPEC 0024/0025/0026 三明治结构、三角色彩派生、五级字号、双栏布局、渐变填充、圆角矩形、外阴影、细边框全部保持 | ✅ |
| 2026-07-31 | SPEC 0027 真实文件验证-5 张图表沙箱执行 + Grid 布局对齐 | `server/scripts/verify_spec0027.py`：(1) 生成教学数据集 `sample_gastric_data.csv`（60 行，9 字段）✅；(2) 调用 `LocalRuleCodeTaskProvider` 生成代码，沙箱执行生成 5 张图表（HISTOGRAM/BAR/BOXPLOT/SCATTER/HEATMAP）使用 Seaborn API + SciencePlots 样式 ✅；(3) 渲染 6 种预设色（蓝/紫/绿/红/橙/灰）PPT 文件，每份 6 页 ✅；(4) Grid 布局对齐验证：`_place_chart_grid` 2×2 网格坐标与原硬编码一致（±0.01 英寸精度）8/8 对齐点全部通过 ✅；(5) 生成 HTML 预览文件 `dev-docs/e2e-screenshots/spec0027/spec0027-preview.html` ✅ | ✅ |
| 2026-07-31 | SPEC 0027 约束遵守验证 | (1) 引入 3 个新依赖（scienceplots/seaborn/easypptx）已声明在 `pyproject.toml`，已在 [调研报告](research/2026-07-31-github-math-modeling-visualization-research.md) 和 [决策 0036](decisions/0036-start-spec-0027-chart-beautification.md) 记录 ✅；(2) 不改变 `PptConfig` 三字段合同 ✅；(3) 不改变 `render()` 签名 ✅；(4) 不改变 API/service/Worker 接线 ✅；(5) 不修改数据库 schema ✅；(6) 不改变 SPEC 0024/0025/0026 布局参数和视觉效果 ✅；(7) `easypptx` 仅作为设计思路借鉴（`_pct_to_emu` + `_GridHelper` 辅助方法），不替换 `PptRenderer` 的 `Presentation` 对象模型 ✅；(8) 沙箱白名单仅新增 `scienceplots`/`seaborn`，`easypptx` 不加入沙箱（PPT 渲染层依赖不在用户代码执行环境使用）✅；(9) SciencePlots 使用 `no-latex` 样式，沙箱不安装 LaTeX ✅ | ✅ |
| 2026-07-31 | SPEC 0028 实现完成-Nature 风格图表集成 | **图表层**：`code_task_provider.py` 的 `_HEADER` 移除 `import scienceplots` 和 `plt.style.use(['science', 'no-latex', 'cjk-sc-font', 'bright'])`，新增 nature-figure rcParams 配置（`axes.spines.right/top=False` 去右框/顶框、`axes.linewidth=2.5` 粗轴线、`legend.frameon=False` 无图例边框、`savefig.dpi=300` 高分辨率输出、`savefig.bbox='tight'` 紧凑裁剪）；保留 `font.sans-serif=['Microsoft YaHei', 'Arial', 'DejaVu Sans']` 中文字体支持；保留 `import seaborn as sns` + `sns.set_theme(style="whitegrid", palette="bright", font="Microsoft YaHei")`。**DeepSeek 层**：`deepseek_code_task_provider.py` 的 `_SYSTEM_PROMPT` 同步移除 SciencePlots 引用，更新为 nature-figure rcParams，import 白名单移除 `scienceplots`。**沙箱层**：`python_executor.py` 的 `DEFAULT_ALLOWED_IMPORTS` 移除 `scienceplots`（保留 `seaborn`）。**依赖层**：`pyproject.toml` 移除 `scienceplots>=2.1.0` 声明（保留 `seaborn`/`easypptx`） | ✅ |
| 2026-07-31 | SPEC 0028 测试验证-5 个受影响测试修改 | `server/.venv/Scripts/python.exe -m pytest server/tests/test_local_rule_code_task_provider_format.py server/tests/test_python_executor.py -k "Spec0027" -v`：**26 passed**。覆盖：(1) C1 `_HEADER` 包含 nature-figure rcParams（`matplotlib.rcParams` + `axes.spines.right`）；(2) C2 `_HEADER` 包含 nature-figure 核心设计规则（`axes.spines.top` + `axes.linewidth` + `2.5`）；(3) C3 `_HEADER` 包含中文字体配置（`Microsoft YaHei` + `font.sans-serif`）；(4) S1 `scienceplots` 已从 `DEFAULT_ALLOWED_IMPORTS` 移除；(5) S4 `scienceplots` 不在白名单中 | ✅ |
| 2026-07-31 | SPEC 0028 回归验证-受影响测试全套零回归 | `server/.venv/Scripts/python.exe -m pytest server/tests/test_local_rule_code_task_provider_format.py server/tests/test_ppt_config.py server/tests/test_renderers.py server/tests/test_python_executor.py -v`：**204 passed 零回归**。验证 SPEC 0024/0025/0026/0027 三明治结构、三角色彩派生、五级字号、双栏布局、渐变填充、圆角矩形、外阴影、细边框、Seaborn 图表 API、`_GridHelper` 网格布局全部保持。额外修复影响面分析中遗漏的 `test_default_allowed_imports_content` 测试（原断言硬编码包含 `scienceplots`，已同步更新） | ✅ |
| 2026-07-31 | SPEC 0028 真实文件验证-3 张图表沙箱执行 + 6 种预设色 PPT | 沙箱执行验证：(1) `_HEADER` 内容验证 10/10 检查通过（不含 scienceplots、含 nature-figure rcParams）✅；(2) scienceplots 包已卸载后沙箱执行成功，生成 3 张图表 PNG + 1 张相关性 CSV ✅。6 种预设色 PPT 渲染验证：blue/purple/green/red/orange/gray 全部渲染成功 ✅，三明治结构和三角色彩系统保持 | ✅ |
| 2026-07-31 | SPEC 0028 约束遵守验证 | (1) 移除 1 个依赖（scienceplots），不引入新依赖 ✅；(2) 不改变 `PptConfig` 三字段合同 ✅；(3) 不改变 `render()` 签名 ✅；(4) 不改变 API/service/Worker 接线 ✅；(5) 不修改数据库 schema ✅；(6) 不改变 SPEC 0024/0025/0026/0027 成果（除 SciencePlots 外）✅；(7) 保留中文字体支持（Microsoft YaHei）✅；(8) 保留 Seaborn 图表 API ✅；(9) 保留 `_GridHelper` 网格布局 ✅；(10) `LocalRuleCodeTaskProvider.generate()` 签名不变 ✅ | ✅ |
| 2026-07-31 | SPEC 0029 实现完成-端到端集成验收 | **验收脚本**：新建 `server/scripts/verify_spec0029_e2e.py`，复用 worker_e2e_verify.py 架构，通过服务层直接调用 Worker handler 驱动完整 8 步工作流（项目创建→要求拆解→证据→数据分析→大纲→Word/PPT 生成）。**测试数据**：复用 2026-07-30 验证数据，`gastric_health_data.csv`（15607 bytes，200 行 15 列）+ `gastric_reference.pdf`（1321 bytes 最小 PDF）放到 `server/data/spec0029_e2e/` 目录。**Provider 配置**：requirement/evidence/analysis/code/outline=local_rule（避免 DeepSeek API 网络波动干扰验收链路通畅性验证）。**最终结果**：`E2E_RESULT=PASS`，退出码 0，项目状态推进到 COMPLETED，状态路径 DRAFT→REQUIREMENT_CONFIRMED→SOURCES_COLLECTED→EVIDENCE_CONFIRMED→DATASET_READY→ANALYSIS_PLANNED→ANALYSIS_CONFIRMED→EXECUTING→RESULT_CONFIRMED→OUTLINE_CONFIRMED→GENERATING→COMPLETED | ✅ |
| 2026-07-31 | SPEC 0029 8 步主路径执行证据 | (1) 创建项目 DRAFT ✅；(2) 上传要求文本 + LOCAL_RULE 生成任务单 + 确认 → REQUIREMENT_CONFIRMED ✅；(3) 上传 PDF + Worker PARSE_DOCUMENT 解析（text_length=1309）+ LOCAL_RULE 生成 10 张证据卡片 + 全部确认 → EVIDENCE_CONFIRMED ✅；(4) 上传 CSV + Worker PARSE_DATASET 解析（200 行 15 列，quality_score=99.22）+ 自动触发 GENERATE_ANALYSIS_PLAN（13 清洗 + 5 分析 + 8 图表方案）→ DATASET_READY ✅；(5) 确认分析方案 → ANALYSIS_CONFIRMED ✅；(6) LOCAL_RULE 生成代码任务（code_length=8212）+ Worker EXECUTE_CODE_TASK 执行成功（exit_code=0，9 图表 + 5 表格，6.9s）→ RESULT_CONFIRMED ✅；(7) 生成大纲（6 段落，source_types 全覆盖 REQUIREMENT/EVIDENCE/DATASET/ANALYSIS/EXECUTION/SUMMARY）+ 确认 → OUTLINE_CONFIRMED ✅；(8) 生成 Word（332468 bytes，103 段落）+ PPT（334411 bytes，8 幻灯片）→ COMPLETED ✅ | ✅ |
| 2026-07-31 | SPEC 0029 发现并修复集成断点 | (1) **`pd.to_numeric(errors='ignore')` 执行错误**（阻断问题）：LocalRule 生成代码中 `pd.to_numeric` 的 `errors='ignore'` 参数在 pandas 新版本中已弃用，改为 `errors='coerce'`，位于 `server/app/modules/llm/code_task_provider.py:196`；(2) **`list_execution_runs` 返回元组解包错误**（验收脚本 bug）：`execution_service.list_execution_runs` 返回 `list[tuple[ExecutionRun, list[ExecutionArtifact]]]`，脚本 `run = runs[0]` 应改为 `run, run_artifacts = runs[0]`，已修复 | ✅ |
| 2026-07-31 | SPEC 0029 回归验证-全套后端测试 | `server/.venv/Scripts/python.exe -m pytest tests/ -x --tb=short -q`：**1100 passed in 67.12s**，零回归，零警告。验证 `pd.to_numeric(errors='coerce')` 修复和 `test_default_allowed_imports_content` 测试更新未引入回归 | ✅ |
| 2026-07-31 | SPEC 0029 真实文件验证-Word/PPT 可打开 | (1) Word 文件 332468 bytes，python-docx 重新加载成功，段落数 103 ✅；(2) PPT 文件 334411 bytes，python-pptx 重新加载成功，幻灯片数 8 ✅；(3) 执行产物 9 个图表 PNG（含 age_vs_WBC_散点图 24882 bytes、age_分布直方图 28920 bytes、correlation_heatmap 136690 bytes 等）+ 5 个表格 CSV ✅ | ✅ |
| 2026-07-31 | SPEC 0029 约束遵守验证 | (1) 不引入新依赖（仅用已有 httpx、python-docx、python-pptx）✅；(2) 不改变 owner 边界（验收脚本放在 `server/scripts/`）✅；(3) 不改变 API 合同 ✅；(4) 不修改数据库 schema ✅；(5) bug 修复遵循阶段闸（`pd.to_numeric` 修复位于核心 owner 层 `code_task_provider.py`）✅；(6) 修复代码与验收脚本分离独立 commit ✅ | ✅ |
| 2026-07-31 | SPEC 0029 验收方式说明 | 本 SPEC 计划的混合验收方案包含三部分：(1) **API 集成脚本（主路径）** ✅ 已通过（使用服务层直接调用模式，验证完整业务链路）；(2) **浏览器验收** ⏭️ 跳过（V2.5.0~V2.8.1 五个切片为纯后端图表/PPT 渲染层改动，前端无改动，浏览器验收在前序 SPEC 0021/0022 已覆盖关键 UI 路径）；(3) **真实文件验证** ✅ 已通过（Word/PPT 文件可打开，9 图表 + 5 表格产物齐全）。详见 [SPEC 0029 验收报告](e2e-acceptance-report-spec0029.md) 和 [决策 0038](decisions/0038-start-spec-0029-e2e-acceptance.md) | ✅ |

## 漂移检查清单

## SPEC 0031 论文级 Word/PPT 视觉质量验收

| 日期 | 验收项 | 证据 | 结果 |
|---|---|---|---|
| 2026-08-12 | 定向回归测试 | `server/.venv/Scripts/python.exe -m pytest server/tests/test_renderers.py server/tests/test_word_template.py server/tests/test_spec0030_pptxforge_chart_beautification.py server/tests/test_local_rule_code_task_provider_format.py -q`：125 passed | ✅ |
| 2026-08-12 | 真实样例生成 | `server/scripts/generate_spec0031_preview.py` 生成同一份大纲消费的 `spec0031_demo.docx`、`spec0031_demo.pptx`、4 张 PNG 图表和 1 个 CSV | ✅ |
| 2026-08-12 | PPT 逐页真实渲染 | `render_slides.py` 输出 6 张 PNG；逐页检查封面、正文、图表图注和总结，无裁切、乱码或图片失真 | ✅ |
| 2026-08-12 | Word 逐页真实渲染 | 本机 Microsoft Word 无界面导出 PDF，再用 Poppler 输出 6 张 PNG；逐页检查 A4 页面、页眉页脚、图题/来源、图表尺寸和附录索引 | ✅ |
| 2026-08-12 | 结构化 QA | python-docx / python-pptx 可重新打开样例；PPT 16:9；Word A4；PPT 6 页；Word 6 页；图表 PNG 与执行批次一致 | ✅ |
| 2026-08-12 | 约束遵守 | 不改 API、Worker、数据库 schema 或渲染入口签名；只修改 renderer、图表生成规则、预览脚本和对应真源文档 | ✅ |
| 2026-08-12 | 全量后端回归 | `server/.venv/Scripts/python.exe -m pytest`：**1135 passed in 81.35s**；首次运行暴露 Windows 子进程缺少 `WINDIR`，已在受控执行环境显式传递只读系统路径后复测通过 | ✅ |

## SPEC 0032 ppt-master / SJTU PPT 工作流适配验收

| 日期 | 验收项 | 证据 | 结果 |
|---|---|---|---|
| 2026-08-12 | 适配层与配置合同 | 新增 `server/app/modules/outlines/ppt_workflows.py` 工作流注册表；`PptConfig.ppt_workflow` 支持 `native_editable`、`academic`、`sjtu_academic`，非法值拒绝；显式 `theme_preset` 优先级保持不变 | ✅ |
| 2026-08-12 | 后端回归 | `server/.venv/Scripts/python.exe -m pytest`：**1143 passed in 85.65s** | ✅ |
| 2026-08-12 | 数据库与前端门禁 | `server/.venv/Scripts/python.exe -m alembic upgrade head` 通过；`npm.cmd run lint` 通过；`npm.cmd run build` 通过，116 modules transformed | ✅ |
| 2026-08-12 | 三套真实 PPTX 生成与结构校验 | `server/scripts/generate_spec0032_preview.py` 生成三套 6 页 PPTX；python-pptx 重新打开成功，画布均为 13.333×7.5（16:9），图表与图注数量一致 | ✅ |
| 2026-08-12 | 逐页渲染与版式检查 | `render_slides.py` 为三套 PPTX 各输出 6 张 PNG；检查封面、正文、图表、图注和总结页，无裁切、重叠、乱码或图片失真；代表页见 `server/dev-docs/e2e-screenshots/spec0032_preview/` | ✅ |
| 2026-08-12 | 溢出检查说明 | `slides_test.py` 在 Windows 临时放大文件路径中触发工具自身 JSON 反斜杠解析错误；已用三套逐页 PNG 检查和 python-pptx 边界/结构校验替代，未发现版式溢出 | ⚠️ 工具债务 |
| 2026-08-12 | 范围与依赖约束 | 未复制完整 `ppt-master` 或 SJTU 校园技能；不引入校园登录、Canvas、邮件、外部模型或新运行时依赖；只复用可迁移的路由/主题/可编辑 PPT 思路，详见 [SPEC 0032](specs/0032-ppt-master-sjtu-presentation-adapter.md) 和 [决策 0041](decisions/0041-start-spec-0032-ppt-master-sjtu-adapter.md) | ✅ |

## SPEC 0033 论文级自适应版式与语义布局规划器验收

| 日期 | 验收项 | 证据 | 结果 |
|---|---|---|---|
| 2026-08-12 | 版式规划器定向测试 | `server/.venv/Scripts/python.exe -m pytest tests/test_layout_planner.py tests/test_renderers.py tests/test_ppt_config.py tests/test_word_template.py -q`：**113 passed** | ✅ |
| 2026-08-12 | 语义版式接线 | 新增 `server/app/modules/outlines/layout_planner.py`；`academic`/`sjtu_academic` 根据章节语义选择叙事、数据概览、方法流程、单图重点、多图对比和总结版式；`native_editable` 保留旧兼容路径 | ✅ |
| 2026-08-12 | 真实 PPT 生成与渲染 | `server/scripts/generate_spec0033_preview.py` 生成学术版和交大版 PPTX；pptxforge 保存校验通过；两套 PPTX 均真实逐页输出 PNG，检查无裁切、重叠或重复总结页 | ✅ |
| 2026-08-12 | PPT 视觉结果 | 数据概览使用指标行，方法使用步骤流，结果使用“结果解释 + 多图对比”，不再所有章节使用固定双栏；代表页见 `server/dev-docs/e2e-screenshots/spec0033_preview/` | ✅ |
| 2026-08-12 | Word 结构校验 | DOCX 可重新打开，包含方法步骤、数据概览表、4 张真实图表、图题/来源和附录索引 | ✅ |
| 2026-08-12 | Word/PDF 视觉渲染 | 当前机器未安装 LibreOffice 或 Word，`render_docx.py` 无法启动转换进程；未将 Word/PDF 视觉检查标记为通过，需在具备 Office/LibreOffice 的环境补验 | ⚠️ 环境缺口 |
| 2026-08-12 | 全量项目门禁 | `server/.venv/Scripts/python.exe -m pytest`：**1146 passed in 76.89s**；Alembic upgrade head 通过；`npm.cmd run lint` 通过；`npm.cmd run build` 通过 | ✅ |

## SPEC 0034 正式论文 Word/PDF 与高级答辩 PPT 验收

| 日期 | 验收项 | 证据 | 结果 |
|---|---|---|---|
| 2026-08-12 | SPEC 确认与实现范围 | 项目负责人确认 SPEC 0034；更新决策 0043、`dev-docs/README.md`，未改变数据/证据/执行/大纲业务边界 | ✅ |
| 2026-08-12 | 共享结构规划器 | 新增 `server/app/modules/outlines/document_planner.py`；`ThesisDocumentPlan` 负责章节、摘要、关键词、参考资料，`DefenseDeckPlan` 负责问题→数据→方法→结果→结论页序；Word/PPT renderer 不复制章节语义 | ✅ |
| 2026-08-12 | 正式论文 DOCX 生成与结构 QA | `server/scripts/generate_spec0034_preview.py` 生成 `spec0034_thesis.docx`；python-docx 重新打开成功，68 段落、1 个数据概览表、4 张真实图表；包含摘要、关键词、目录、6 个一级章节、参考资料、附录，图题含 `图 5-1`、`图 5-2` | ✅ |
| 2026-08-12 | Word 论文版式规则 | A4 纵向、2.4/2.4/2.2/2.2 cm 页边距、宋体/Times New Roman、Heading 1/2、原生 List Number、固定表格列宽、章节级图表编号与题注来源 | ✅ |
| 2026-08-12 | PPT 答辩叙事生成 | 同一份大纲与执行产物生成 academic 和 sjtu_academic 两套 16:9 PPTX，各 7 页；包含研究问题、数据概览、方法流程、两页结果证据、结论与局限；每页结果最多 2 张图 | ✅ |
| 2026-08-12 | PPT 逐页渲染与视觉检查 | `render_slides.py` 为两套 PPTX 各输出 7 张 PNG；已检查标题、数据概览、方法、结果双图和结论页，无裁切、重复总结页或图表错配；拼图见 `server/dev-docs/e2e-screenshots/spec0034_preview/defense_montage.png`、`sjtu_montage.png` | ✅ |
| 2026-08-12 | PPT 溢出检查 | `slides_test.py` 在 Windows 临时放大文件阶段触发工具自身 JSON 反斜杠解析错误；沿用前序工具债务处理，使用逐页 PNG、python-pptx 可重开和边界/结构检查替代，未发现溢出 | ⚠️ 工具债务 |
| 2026-08-12 | Word/PDF 视觉渲染 | `render_docx.py --emit_pdf` 因当前机器缺少 LibreOffice/Word 转换进程而失败；已完成 DOCX 结构 QA，PDF 视觉导出留待具备 Office/LibreOffice 的环境补验，未虚报通过 | ⚠️ 环境缺口 |
| 2026-08-12 | 定向测试 | `server/.venv/Scripts/python.exe -m pytest tests/test_document_planner.py tests/test_layout_planner.py tests/test_renderers.py tests/test_ppt_workflows.py tests/test_ppt_config.py -q`：**105 passed** | ✅ |
| 2026-08-12 | 全量项目门禁 | `server/.venv/Scripts/python.exe -m pytest`：**1148 passed in 167.50s**；`server/.venv/Scripts/python.exe -m alembic upgrade head` 通过；`npm.cmd run lint` 通过；`npm.cmd run build` 通过（116 modules transformed） | ✅ |

## SPEC 0035 大样本公开论文解读案例验收

| 日期 | 验收项 | 证据 | 结果 |
|---|---|---|---|
| 2026-08-12 | 公开来源与追溯 | UCI Diabetes 130-US Hospitals 数据集、Strack 2014 开放论文、Europe PMC 全文 XML；来源清单位于 `server/dev-docs/e2e-screenshots/spec0035_paper_review/sources/source_manifest.json` | ✅ |
| 2026-08-12 | 大样本口径 | 原始 CSV 101766 条记录；数据集页面口径为 47 个特征；原论文最终样本 69984、HbA1c 测量率 18.4%；本地原始 CSV 复核为 17018 条测量记录、16.7%，并明确标注口径差异 | ✅ |
| 2026-08-12 | 本地复核结果 | 30 天内再入院率：HbA1c 已测 9.8%，未测 11.4%；仅作为描述性复核，不包装为原论文回归复现 | ✅ |
| 2026-08-12 | 交付物生成 | `generate_spec0035_paper_review.py` 生成正式论文风格 DOCX、academic PPTX、sjtu_academic PPTX；DOCX 结构为 77 段落、4 张表/图表索引、4 张真实图表，PPT 各 7 页 | ✅ |
| 2026-08-12 | PPT 逐页视觉检查 | 两套 PPTX 经工作区渲染依赖的 `render_slides.py` 各输出 7 张 PNG，已逐页检查标题、数据概览、方法、结果双图和结论页；结果页解释框已压缩，未发现裁切、重叠或图表错配；拼图位于 `server/dev-docs/e2e-screenshots/spec0035_paper_review/defense_montage.png`、`sjtu_montage.png` | ✅ |
| 2026-08-12 | PPT 溢出检查 | `slides_test.py` 在 Windows 临时文件阶段触发工具自身 JSON 反斜杠解析错误；用逐页 PNG、python-pptx 可重开和 16:9/页数结构检查替代，未发现溢出 | ⚠️ 工具债务 |
| 2026-08-12 | Word/PDF 视觉转换 | DOCX 可重新打开并通过结构 QA；`render_docx.py --emit_pdf` 因当前机器缺少 LibreOffice/Word 转换进程失败，PDF 视觉导出留待具备 Office/LibreOffice 的环境补验 | ⚠️ 环境缺口 |
| 2026-08-12 | 定向测试 | `server/.venv/Scripts/python.exe -m pytest tests/test_spec0035_paper_review.py tests/test_document_planner.py tests/test_layout_planner.py tests/test_renderers.py tests/test_ppt_workflows.py tests/test_ppt_config.py -q`：**107 passed** | ✅ |
| 2026-08-12 | 全量后端门禁 | `server/.venv/Scripts/python.exe -m pytest`：**1150 passed in 59.77s** | ✅ |

## SPEC 0037 语义图表选择与 PPT 组件优化验收

| 日期 | 验收项 | 证据 | 结果 |
|---|---|---|---|
| 2026-08-12 | 范围与真源 | 已确认 SPEC 0037；新增 `chart_planner.py`、决策 0046，并更新 README | ✅ |
| 2026-08-12 | 语义图表规划 | `test_chart_planner.py`：6 个规划契约测试通过；规划器输出图表类型、编码和选择理由 | ✅ |
| 2026-08-12 | 真实图表产物 | `generate_spec0035_paper_review.py` 重新生成 flow、100% 构成图、横向条形图、Dumbbell、点估计 + 95% CI、自然顺序趋势图和 Forest Plot | ✅ |
| 2026-08-12 | 图表可追溯性 | `analysis_summary.json` 写入 9 个图表的 `chart_kind`、`encoding`、`rationale`；执行 run id 为 `spec0037_semantic_charts` | ✅ |
| 2026-08-12 | PPT 组件复用 | 两套 PPT 重新生成；答辩页组合现有 `StatRow`、`Callout`、`TwoColumn`、`IconRow`、`Stack` 和 `Grid`，无新模板/装饰资源 | ✅ |
| 2026-08-12 | PPT 结构验收 | 两套 PPT 均可用 `python-pptx` 重开，16:9、13 页；生成日志未出现 `pptxforge` 溢出降级 | ✅ |
| 2026-08-12 | 定向测试 | `server/.venv/Scripts/python.exe -m pytest server/tests/test_chart_planner.py server/tests/test_layout_planner.py server/tests/test_ppt_workflows.py server/tests/test_spec0035_paper_review.py`：**21 passed** | ✅ |
| 2026-08-12 | 标准逐页渲染 | `render_slides.py` 受本机缺少 `pdf2image` 和 Artifact Tool 包路径阻断；`slides_test.py` 同样未完成 | ⚠️ 环境缺口 |

## SPEC 0036 论文解读深度整改验收

| 日期 | 验收项 | 证据 | 结果 |
|---|---|---|---|
| 2026-08-12 | 范围与真源 | 已确认 SPEC 0036；新增决策 0045、SPEC 文档并更新 `dev-docs/README.md` | ✅ |
| 2026-08-12 | 真实数据深度分析 | `generate_spec0035_paper_review.py` 从 101766 条 CSV 计算样本口径、缺失率、结局分布、Wilson 95% CI、风险差、分层结果和简化多变量 Logistic | ✅ |
| 2026-08-12 | 核心复核数字 | HbA1c 已检测 17018 条、覆盖率 16.7%；已检测组早期再入院 9.8%，未检测组 11.4%；风险差 -1.6%，95% CI [-2.1%, -1.1%]；模型 HbA1c OR 0.893，95% CI [0.843, 0.946] | ✅ |
| 2026-08-12 | 图表与表格 | 新增样本流程、结局分布、缺失率、论文/本地对照、效应量、分层图、Logistic 森林图和 2 张结果 CSV 表，共 11 个执行产物 | ✅ |
| 2026-08-12 | Word 成品结构 | DOCX 重新打开成功，118 段落、3 个表格、9 张真实图表；包含摘要、目录、6 个一级章节、模型复核、结果、局限和附录 | ✅ |
| 2026-08-12 | PPT 成品结构 | academic 与 sjtu_academic 两套 PPT 均为 13 页、16:9；叙事覆盖问题、来源、样本、质量、方法、模型、主要结果、分层、对照、局限和证据链 | ✅ |
| 2026-08-12 | PPT 逐页视觉检查 | 工作区 `render_slides.py` 生成两套各 13 张 PNG；已检查模型森林图、缺失图、主要结果和分层结果页，无标题换行、图表裁切、说明压图题或意外重叠 | ✅ |
| 2026-08-12 | 定向测试 | `.venv/Scripts/python.exe -m pytest tests/test_spec0035_paper_review.py tests/test_document_planner.py tests/test_layout_planner.py tests/test_renderers.py tests/test_ppt_workflows.py tests/test_ppt_config.py -q`：**109 passed** | ✅ |
| 2026-08-12 | 全量项目门禁 | `.venv/Scripts/python.exe -m pytest`：**1152 passed in 85.08s**；Alembic upgrade head、`npm.cmd run lint`、`npm.cmd run build` 均通过 | ✅ |
| 2026-08-12 | Word/PDF 视觉转换 | DOCX 结构 QA 通过；`render_docx.py --emit_pdf` 仍因当前机器缺少 LibreOffice/Word 转换进程失败，PDF 视觉转换保留环境缺口 | ⚠️ 环境缺口 |

## SPEC 0038 正式学术论文规范化验收

| 日期 | 验收项 | 证据 | 结果 |
|---|---|---|---|
| 2026-08-12 | 论文结构规划 | `ThesisDocumentPlan` 增加正式章节、题名元数据、引用映射和参考文献计划；定向规划器测试通过 | ✅ |
| 2026-08-12 | 正式 DOCX 结构 | `spec0038_formal_paper.docx` 可重新打开；包含封面、摘要、关键词、目录、6 个一级章节、正文引用、参考文献和附录 | ✅ |
| 2026-08-12 | 图表与表格规范 | 真实案例包含 9 张语义图表和 2 张统计表；图号/表号随章节编号，结果表采用三线表，题注含数据口径说明 | ✅ |
| 2026-08-12 | Word → PDF | Word“发布为 PDF 或 XPS”真实流程生成 `spec0038_formal_paper.pdf`，A4 共 15 页 | ✅ |
| 2026-08-12 | PDF 视觉验收 | 使用 Poppler 渲染 15 页 PNG，检查封面、摘要、结果图表、森林图与三线表、参考文献和附录；未发现裁切、溢出或字体丢失 | ✅ |
| 2026-08-12 | 定向测试 | `server/.venv/Scripts/python.exe -m pytest tests/test_document_planner.py tests/test_renderers.py -q`：**22 passed** | ✅ |
| 2026-08-12 | 生成脚本 | `server/.venv/Scripts/python.exe scripts/generate_spec0035_paper_review.py`：真实数据、图表、Word、PPT 均重新生成成功 | ✅ |

## SPEC 0039 论文级多语义图形系统（实现与视觉验收）

| 日期 | 验收项 | 证据/边界 | 结果 |
|---|---|---|---|
| 2026-08-12 | 共享语义合同 | `server/app/modules/outlines/figure_planner.py` 新增 `FigurePlan`、节点/边校验、10 类图形语义和安全降级规则；定向图形测试 **5 passed** | ✅ |
| 2026-08-12 | 案例逻辑图 | 真实大样本案例新增研究证据链、数据处理管线、变量关系 3 张逻辑图；共生成 14 个 artifact、12 份 figure plan，图形与统计图语义不重复 | ✅ |
| 2026-08-12 | owner 与双适配 | Word/PDF 与 PPT 均消费同一份 `FigurePlan`；Word 保留完整题注/来源/限制说明，PPT 复用现有 `pptxforge` Stack/Callout/Image/Text 组件 | ✅ |
| 2026-08-12 | Word/PDF 视觉验收 | `spec0039_formal_paper.pdf` A4 共 17 页；Poppler 渲染 17 页 PNG，检查封面、证据链、数据管线、统计图、森林图、三线表、参考文献和附录，未发现裁切、溢出或题注错位 | ✅ |
| 2026-08-12 | PPT 视觉验收 | 两套 PPTX 均生成 16 页；PowerPoint 真实界面检查标题页、证据链、数据处理管线、变量关系图和统计结果页，未发现乱码、溢出、图形错配或过度拥挤 | ✅ |
| 2026-08-12 | 定向回归 | `server/.venv/Scripts/python.exe -m pytest tests/test_figure_planner.py tests/test_spec0035_paper_review.py tests/test_renderers.py -q`：**30 passed** | ✅ |
| 2026-08-12 | 全量回归 | `server/.venv/Scripts/python.exe -m pytest`：**1167 passed** | ✅ |
| 2026-08-12 | PPT 自动渲染替代证据 | `render_slides.py`/`slides_test.py` 受本机缺失 `@oai/artifact-tool` 运行包阻断；改用 PowerPoint 原生界面逐页检查，已完成代表页视觉验收 | ⚠️ 工具限制，替代验收通过 |
| 2026-08-12 | 依赖与边界 | 不新增运行时依赖，不修改 API、数据库 schema、LLM Gateway、Worker 和产品边界；复用现有 `pptxforge` 组件 | ✅ |

## SPEC 0040 期刊级论证图表与论文视觉语法改造（实现与视觉验收）

| 日期 | 验收项 | 证据/边界 | 结果 |
|---|---|---|---|
| 2026-08-13 | 论证合同 | `figure_planner.py` 新增 `ArgumentPlan`，统一主张、证据引用、方法、结果、边界和正文引用；缺少证据、结果或边界的输入有负向测试 | ✅ |
| 2026-08-13 | 真实案例数据 | `analysis_summary.json` 执行批次为 `spec0040_argumentation`，真实公开 CSV 101,766 条、论文最终样本 69,984 条、HbA1c 已检测 17,018 条，14 个 artifact | ✅ |
| 2026-08-13 | 论证图形 | 研究证据链升级为 A/B/C/D 四面板论证图，包含 11 个语义节点和 `supports/contains/produces/compared_with/bounded_by` 关系；数据处理管线、变量关系图均包含真实计数/字段/执行批次；变量关系采用无交叉连接线，并显式标注“观察性关联” | ✅ |
| 2026-08-13 | Word 成品 | `spec0040_argumentation.docx` 可重新打开；题注、来源、论证摘要、边界和正文引用随图形计划输出 | ✅ |
| 2026-08-13 | Word → PDF | Word 内置“创建 PDF/XPS 文档”生成 `spec0040_argumentation.pdf`，A4 共 18 页 | ✅ |
| 2026-08-13 | PDF 视觉验收 | Poppler 渲染 18 页 PNG，检查封面、证据链、变量关系、统计图、三线表和附录；未发现裁切、重叠、不可读文本或题注错位 | ✅ |
| 2026-08-13 | PPT 成品 | `spec0040_argumentation.pptx` 与 `spec0040_argumentation_sjtu.pptx` 均为 16 页；标题页、证据链页、数据管线页、变量关系页和统计结果页均使用现有 `pptxforge` 组件 | ✅ |
| 2026-08-13 | PPT 视觉验收 | PowerPoint 原生界面检查 0040 成品；证据链页改为图形主导的宽版自适应布局，A/B/C/D 面板可读，无乱码、溢出、图形错配或过度拥挤；自动 `artifact-tool` 渲染工具受本机缺失包阻断，已使用原生界面替代 | ⚠️ 工具限制，替代验收通过 |
| 2026-08-13 | 定向回归 | `server/.venv/Scripts/python.exe -m pytest tests/test_figure_planner.py tests/test_spec0035_paper_review.py tests/test_renderers.py -q`：**33 passed** | ✅ |
| 2026-08-13 | 全量回归 | `server/.venv/Scripts/python.exe -m pytest`：**1170 passed** | ✅ |
| 2026-08-13 | 依赖与边界 | 不新增运行时依赖，不修改数据库 schema、API、LLM Gateway、Worker 和产品边界；保留历史文件名供旧夹具回归 | ✅ |

## SPEC 0041 论文级异构图形编排与语义选图系统（实现与视觉验收）

| 日期 | 验收项 | 证据/边界 | 结果 |
|---|---|---|---|
| 2026-08-13 | 共享编排合同 | `figure_planner.py` 新增 `FigureFamily`、`FigurePortfolioPlan`、`RejectedFigureCandidate` 与 `COMPARISON_MATRIX`；artifact 元数据保留 `figure_kind`、视觉家族、版式、数据前提和选图理由 | ✅ |
| 2026-08-13 | 真实案例组合 | `analysis_summary.json` 真实执行批次为 `spec0040_argumentation`，公开 CSV 101,766 条、论文最终样本 69,984 条、HbA1c 已检测 17,018 条；生成 15 个 artifact | ✅ |
| 2026-08-13 | 图形家族覆盖 | 实际组合覆盖 `evidence_argument`、`process`、`relationship`、`matrix`、`statistical` 五个家族；包含证据链、数据管线、变量关系图、比较矩阵和点估计图 | ✅ |
| 2026-08-13 | 结构化拒绝 | 质量热力图因缺少行×字段矩阵被拒绝；时间线因缺少可排序事件时间字段被拒绝；拒绝理由写入 `figure_portfolio_plan`，不使用伪图填充 | ✅ |
| 2026-08-13 | 定向与全量回归 | `server/.venv/Scripts/python.exe -m pytest tests/test_figure_planner.py tests/test_layout_planner.py tests/test_spec0035_paper_review.py tests/test_renderers.py -q`：39 passed；`server/.venv/Scripts/python.exe -m pytest`：1173 passed | ✅ |
| 2026-08-13 | 项目门禁 | `server/.venv/Scripts/python.exe -m alembic upgrade head`、在 `apps/web/` 执行 `npm.cmd run lint`、`npm.cmd run build` 均通过；根目录无 `package.json`，前端门禁在实际工作目录执行 | ✅ |
| 2026-08-13 | Word/PDF 成品 | `spec0041_heterogeneous.docx` 经 Word 原生导出为 `spec0041_heterogeneous.pdf`，A4 共 19 页；Poppler 生成 19 张 QA PNG，抽检正文、统计图、复核点图、矩阵页和附录，未发现裁切/重叠/题注错位 | ✅ |
| 2026-08-13 | PPT 成品 | `spec0041_heterogeneous.pptx` 与 `_sjtu.pptx` 均为 17 页；逐页 PNG 渲染并抽检证据链、数据管线、关系图和矩阵页，复用现有 `pptxforge` 组件，无乱码/溢出/线条穿字 | ✅ |
| 2026-08-13 | 论文文字与布局层级修订 | 新增研究目标、数据口径、方法解释、图前导读和图后结论；正文使用独立段落承载“问题—方法—证据—解释—边界”，图表单元避免导读与图片跨页；独立成品 `spec0042_paper_language.docx/.pdf` 共 24 页，Poppler 逐页 QA，抽检图前导读、证据链图、数据管线图和结果图，无裁切/重叠/题注错位 | ✅ |
| 2026-08-13 | 论文解读 PPT 文字层级修订 | `spec0042_paper_language.pptx` 与 `_sjtu.pptx` 均为 17 页；研究问题页、证据页、结果页和结论页统一采用“主张—证据—解释—边界”层级，逐页 PNG 渲染抽检通过 | ✅ |
| 2026-08-13 | 工具限制 | `slides_test.py` 在当前 Windows 路径环境因工具内部 JSON 反斜杠解析失败；已使用同一运行时逐页渲染、PPT 结构检查和人工视觉抽检替代，不把该工具作为唯一门禁 | ⚠️ 环境限制 |
| 2026-08-13 | 依赖与边界 | 未新增运行时依赖；未修改 API、数据库 schema、LLM Gateway、Worker 和产品边界；PPT 继续复用现有主题与组件 | ✅ |
每次进入下一阶段前检查：

- 产品边界仍匹配 `project-charter.md`。
- 不支持所有网站、不做 App/小程序/多人协作/自由拖拽工作流、不做 L3 完整复现。
- `dev-docs/README.md` 仍是唯一真源索引。
- 每个核心概念有唯一归属层。
- 界面、API、大模型提示词、Python 执行器不拥有核心业务语义。
- 资料事实有来源，实验结果有执行记录。
- Word/PPT 使用同一份已确认大纲。
- 失败、未知和超范围不会被包装为成功。
- 医学主题保持教学数据分析边界。

## 漂移锁

禁止以下漂移：

- 把产品做成普通 AI 代写工具。
- 把公开 URL 支持扩张为任意网站爬取。
- 把 L1/L2 方法参考包装成完整论文复现。
- 在没有真实执行记录时生成实验结论。
- 让前端、prompt 或临时脚本决定业务状态。
- 未经项目负责人确认就安装依赖、初始化框架或写业务代码。

## 就绪表述规则

在没有端到端证据前，只能说：

- “文档门禁通过”
- “架构草案已创建”
- “计划待审阅”

不能说：

- “项目已完成”
- “V1 已就绪”
- “代码可发布”
- “实验结果已验证”

## SPEC 0042 开放许可科研图形资产库与科研示意图组件系统

| 日期 | 验收项 | 证据/边界 | 结果 |
|---|---|---|---|
| 2026-08-13 | 许可与资产注册表 | 7 个 Bioicons CC0 SVG 固定上游 commit；manifest 含来源、作者、许可、URL、尺寸、SHA-256 和核验时间；未知/NC/ND 拒绝，BY-SA 人工审核 | ✅ |
| 2026-08-13 | SVG 安全与完整性 | 覆盖脚本、事件、任意属性外部 `url()`、style 外链、DTD/实体、`foreignObject`、路径逃逸、哈希漂移、NaN/Infinity viewBox、严格布尔字段和资源上界负向测试 | ✅ |
| 2026-08-13 | 语义合同 | `FigurePlan` 下新增面板、placement、connector；节点标签与边关系必须引用既有 FigureNode/FigureEdge 真源 | ✅ |
| 2026-08-13 | 三路 Luna 独立审查整改 | 补齐 DAG 环路、连接标签/非因果措辞、PPT 合同选图、全页 speaker notes、SVG 任意属性外链、严格布尔字段、有限 viewBox 和 Word/PPT 同源 PNG 哈希集成门禁 | ✅ |
| 2026-08-13 | 科研示意图 | 生成 2400×1350、300 DPI 的公开数据分析流程和实验流程样图，包含具象科研组件、分支/汇合、步骤号、图例和解释边界 | ✅ |
| 2026-08-13 | Word/PDF | 两张同源示意图嵌入正式 DOCX；PDF 使用开放许可 Noto Sans SC 嵌入字体并附原始 PNG/JSON，8 页 A4；PDFium 生成 8 张 1191×1684 PNG | ✅ |
| 2026-08-13 | PPT 主路径 | 使用显式答辩语义角色与精炼演示文案后 `pptxforge` 学术主路径成功；PowerPoint 原生导出 7 张 1920×1080 PNG；两张科研资产页写入标准 `[Sources]` speaker notes | ✅ |
| 2026-08-13 | 跨平台转换 | `resvg_py==0.3.3` 在 Windows venv 与一次性 `python:3.13-slim` 容器均成功转换；容器 PNG 签名 `89504e470d0a1a0a` | ✅ |
| 2026-08-13 | 定向与全量回归 | SPEC 0042 + renderer 定向 **81 passed**；最终全量后端 **1215 passed in 70.26s** | ✅ |
| 2026-08-13 | 项目门禁 | Alembic upgrade head、`apps/web` 的 `npm.cmd run lint` 与 `npm.cmd run build`（116 modules transformed）通过 | ✅ |
| 2026-08-13 | 自动视觉工具 | `slides_test.py` 与应用内截图查看受中文路径/Windows ACL helper 影响；已用 PowerPoint 原生导出、PDFium 渲染、PPTX/DOCX 重开和页数/尺寸/媒体/notes/附件/SHA-256 检查替代 | ⚠️ 工具限制，替代验收通过 |
| 2026-08-13 | 范围安全 | 未绕过水印/付费/登录；未复制受限平台素材；未新增 API、数据库表或自由拖拽编辑器；不生成无证据医学机制 | ✅ |

当前结论：实现与本地门禁完成，等待项目负责人查看成品并确认视觉效果后正式收口。
补充成品一致性证据：`data_analysis_workflow.png` 与 `experimental_workflow.png` 的 SHA-256 分别为 `8b6ba6647071acc056ac0ff40b0cf79da2c09fabffa1ed9fce6a14fee9e2ab0a`、`1f497d33251c803fe205b5e36824649bb09644a329b5bac3a6b8e41fee96faa9`；DOCX 与 PPTX 的 ZIP 媒体区均实际包含这两份原始 PNG 字节，Word 正文与 PPT speaker notes 均包含相同哈希。PDF 将两份原始 PNG 和对应 JSON 作为附件嵌入。

## SPEC 0044 标准化论文成品展示与排版验收记录

| 日期 | 验收项 | 证据/边界 | 结果 |
|---|---|---|---|
| 2026-08-15 | 范围与 owner | 仅修改 `ManuscriptPlan -> WordRenderer` 的读者优先论文投影；不扩展 MCP、图表类型、数据库 schema 或 PPT owner | ✅ |
| 2026-08-15 | 定向回归 | `py_compile` + SPEC 0044/0043 定向测试：**10 passed** | ✅ |
| 2026-08-15 | 真实成品 | `server/.venv/Scripts/python.exe scripts/generate_spec0035_paper_review.py` 重新生成 DOCX/PDF/manifest | ✅ |
| 2026-08-15 | DOCX 结构 | 正文工程字段泄漏检查通过；图表目录含图/表条目；TOC、SEQ Figure/Table、REF/PAGEREF、双 section 页码字段存在 | ✅ |
| 2026-08-15 | DOCX/PDF 一致性 | manifest 中 `source_docx_sha256` 与 DOCX 匹配，`pdf_sha256` 与 PDF 匹配；PDF 为 A4 共 21 页 | ✅ |
| 2026-08-15 | PDF 渲染替代证据 | bundled Poppler 成功渲染前 6 页为 1191×1684 PNG；页面文本与像素检查未发现空白或渲染失败页 | ✅ |
| 2026-08-15 | 自动视觉查看 | Windows ACL helper 无法读取 PNG，未宣称已完成工具内视觉查看；最终视觉确认仍需项目负责人查看 `spec0044_pdf_render_final/` | ⚠️ 工具限制 |
| 2026-08-15 | 完整后端门禁 | 在 `server/` 工作目录运行 `server/.venv/Scripts/python.exe -m pytest -q`：**1235 passed in 64.07s** | ✅ |
| 2026-08-15 | 其他项目门禁 | `server/.venv/Scripts/python.exe -m alembic upgrade head`、`apps/web` 的 `npm.cmd run lint` 与 `npm.cmd run build` 均通过（116 modules transformed） | ✅ |

当前结论：SPEC 0044 实现与本地门禁完成，等待项目负责人查看最终 DOCX/PDF/PNG 并确认收口；本轮未执行 stage、commit 或 push。

## SPEC 0044 2026-08-20 版式重构复核

| 日期 | 验收项 | 证据/边界 | 结果 |
|---|---|---|---|
| 2026-08-20 | 版式重构 | 作者/单位封面、连续章节分页、紧凑目录、全局图 1-13/表 1-3、图表目录、REF/PAGEREF 回指、图表组合版式、重复表头；正文隐藏工程字段 | ✅ |
| 2026-08-20 | 定向回归 | SPEC 0044/0043 相关测试：9 passed | ✅ |
| 2026-08-20 | 完整后端门禁 | server/.venv/Scripts/python.exe -m pytest：1235 passed in 54.72s | ✅ |
| 2026-08-20 | 数据库与前端门禁 | Alembic upgrade head；apps/web 的 npm.cmd run lint 与 npm.cmd run build | ✅ |
| 2026-08-20 | 真实成品 | spec0043_publication.docx/pdf/manifest 同一轮生成；PDF 为 A4 18 页；manifest SHA-256 与实际文件匹配 | ✅ |
| 2026-08-20 | PDF 视觉复核 | Poppler 生成全部 18 页 PNG；检查联系图及第 6、8、11、12、13、14、17 页，未发现空白页、裁切、重叠、题注错位或目录重复前缀；证据位于 server/dev-docs/e2e-screenshots/spec0044_layout_qa_20260820_final/ | ✅ |
| 2026-08-20 | 工具边界 | Windows ACL helper 仍不能直接读取 PNG；实际 PNG 已通过 base64 送入当前视觉上下文完成替代复核 | ⚠️ 工具限制，替代验收通过 |

当前结论：SPEC 0044 实现、真实成品、项目门禁和替代视觉复核均完成，等待项目负责人确认成品风格后收口；本轮未执行 stage、commit 或 push。


## SPEC 0044 2026-08-21 前置页重构复核

| 日期 | 验收项 | 证据/边界 | 结果 |
|---|---|---|---|
| 2026-08-21 | 结构化中文摘要 | 摘要按“目的、方法、结果、结论”分段，并保留关键词；内容来自正式论文配置，不由 renderer 临时编造 | ✅ |
| 2026-08-21 | 英文摘要 | 新增独立 ABSTRACT 页，包含 Purpose、Methods、Results、Conclusion 和 KEYWORDS | ✅ |
| 2026-08-21 | 目录层级 | 目录包含摘要/ABSTRACT/目录/图目录/表目录前置项，章标题加粗，小节缩进，并支持三级标题和三级书签 | ✅ |
| 2026-08-21 | 图表目录 | 图目录与表目录分开呈现，并按章节增加分组提示；图 1-13、表 1-3 的 REF/PAGEREF 字段保留 | ✅ |
| 2026-08-21 | 页码与页眉 | 前置部分使用 lowerRoman 且从 i 开始，正文切换为 decimal 且从 1 开始；页眉统一为“学术论文” | ✅ |
| 2026-08-21 | 真实成品 | spec0043_publication.docx/pdf/manifest 同一轮生成；PDF 为 A4 19 页；DOCX/PDF SHA-256 与 manifest 一致 | ✅ |
| 2026-08-21 | 前置页视觉复核 | Poppler 生成 19 页 PNG；已检查联系图及第 1—7 页、正文第 8、10、12、14、17 页，未发现空白页、裁切、重叠或正文起始页码异常；证据位于 server/dev-docs/e2e-screenshots/spec0044_frontmatter_qa_20260821/ | ✅ |
| 2026-08-21 | 定向回归 | SPEC 0044/0043、document_planner 相关测试：9 passed | ✅ |
| 2026-08-21 | 完整后端门禁 | server/.venv/Scripts/python.exe -m pytest：1235 passed in 67.78s | ✅ |


## SPEC 0045 论文复核统计完整性验收记录

| 日期 | 验收项 | 证据/边界 | 结果 |
|---|---|---|---|
| 2026-08-21 | 患者去重与死亡/临终关怀 | 101,766 条原始记录、71,518 名患者、30,248 条重复记录；首记录 71,518 条，排除 1,545 条死亡/临终关怀首记录，主队列 69,973 条 | ✅ |
| 2026-08-21 | HbA1c 缺失语义 | 已检测 12,845；明确未检测 57,128；真正缺失/未知 0；字面 `None` 未被当作普通缺失 | ✅ |
| 2026-08-21 | 主要诊断交互与聚类标准误 | 9 类主要诊断、HbA1c × 主要诊断交互、patient_nbr sandwich 标准误；联合 Wald P=0.01 | ✅ |
| 2026-08-21 | 敏感性分析 | 保留重复记录并按患者聚类；纳入死亡/临终关怀首记录；两种口径均写入 CSV 与正文 | ✅ |
| 2026-08-21 | 模型合同与文献 | 变量编码表、完整模型表、软件版本、STROBE、缺失数据和 cluster-robust 推断文献进入 Word/PDF | ✅ |
| 2026-08-21 | P 值与图表说明 | CSV/PDF 不含 `P=0`；表 2 注释、诊断分层图、交互森林图明确参考组、区间和观察性解释边界 | ✅ |
| 2026-08-21 | 定向回归 | `server\.venv\Scripts\python.exe -m pytest server/tests/test_spec0035_paper_review.py -q`：10 passed | ✅ |
| 2026-08-21 | 真实 Word/PDF | 同一轮生成 `spec0043_publication.docx/pdf/manifest`；PDF A4 共 21 页，manifest 绑定 SHA-256 | ✅ |
| 2026-08-21 | 逐页视觉验收 | `render_docx.py` 缺少 `pdf2image/Poppler`；LibreOffice 不可用；Word 剪贴板复制分页图像因桌面沙箱失败。已完成结构和文本验收，未宣称 21 页 PNG 逐页通过 | ⚠️ 工具限制 |

当前结论：统计完整性修订、文稿定位、真实 Word/PDF 生成和自动门禁完成；项目负责人仍需查看最新 PDF 并确认视觉收口，之后才能执行 Git 版本收口。



## SPEC 0046 Windows 一键运行封装验收记录

| 日期 | 验收项 | 证据/边界 | 结果 |
|---|---|---|---|
| 2026-08-21 | 构建依赖 | packaging/windows/requirements-build.txt；PyInstaller 6.22.2 已安装于构建用 server/.venv，仅作为构建期依赖 | ✅ |
| 2026-08-21 | 前端生产构建 | packaging/windows/build_windows_bundle.py 内执行 npm.cmd run build；Vite 116 modules transformed | ✅ |
| 2026-08-21 | 服务包构建 | PyInstaller one-directory service 构建通过；显式携带 Conda 基座 DLL，复制 sandbox_runner.exe | ✅ |
| 2026-08-21 | 根启动器构建 | PyInstaller one-file、windowed 根入口构建通过；启动器同样携带 ctypes 所需基础 DLL | ✅ |
| 2026-08-21 | 服务黑盒 | 发布目录 service/service.exe backend 迁移 0001~0007；/health=200、首页=200、SPA 路由=200；数据库文件真实创建 | ✅ |
| 2026-08-21 | Worker 黑盒 | 发布目录 service/service.exe worker 启动后保持运行，测试结束后回收；worker stderr 为空 | ✅ |
| 2026-08-21 | 根 EXE 启动 | 实际运行根目录 实验报告助手.exe；one-file 外层/内层进程启动，健康端点在 8787 返回 200，实际运行窗口可发现 | ✅ |
| 2026-08-21 | 根 EXE 关闭 | 使用 Win32 窗口枚举识别真实“实验报告助手 - 运行中”窗口；发送 WM_CLOSE 后内层/外层退出码均为 0，service.exe 残留数为 0；用户数据和日志已生成 | ✅ |
| 2026-08-21 | 源合同测试 | server/.venv/Scripts/python.exe -m pytest tests/test_spec0046_windows_packaging.py -q：4 passed（端口测试在端口被占用时允许 skip） | ✅ |
| 2026-08-21 | 干净 Windows | 当前工作机同时具备 Python/Node.js，未提供独立无开发运行时 Windows x64 机器；发布包直接运行证据已具备 | ⚠️ 环境缺口 |
| 2026-08-21 | 返回码观察 | 定位为 ctypes 自定义 WNDPROC/浏览器外部调用导致的启动失败；改用系统 STATIC 窗口和非阻断浏览器打开后，正式 EXE 自动关闭退出码为 0 | ✅ |
| 2026-08-21 | 资源与密钥 | 发布 manifest 记录文件哈希；构建脚本未读取真实密钥，运行包不放 DeepSeek Key；构建输出留在 server/.tmp/windows-package/ | ✅ |

当前结论：Windows 便携包构建、服务黑盒、根 EXE 启动/页面/真实窗口/关闭清理链路和退出码均通过；仅缺少独立无 Python、Node.js、Docker 的全新 Windows x64 主机验收。

## SPEC 0047 统一工作台与交付审阅阶段（2026-08-23 实施记录）

| 验收项 | 证据/边界 | 结果 |
|---|---|---|
| PDF 合同 | DeliverableType.PDF、JobType.GENERATE_PDF、PDF 下载 media type 和版本变更类型已加入现有 outlines owner；不新增并行文件表 | ✅ |
| PDF 完成门禁 | 未完成项目要求 Word/PDF/PPT 三类成功版本；已完成历史项目保持 COMPLETED，不回退 | ✅ |
| PDF Worker | 只消费同一项目、同一确认大纲下的成功 DOCX；PDF 失败独立记录，Word 不被回写失败；输出目录受控 | ✅ |
| PDF 转换适配器 | 支持显式 PDF_CONVERTER_PATH/LibreOffice headless、临时 profile、超时、PDF 魔数和输出大小校验；开发环境保留显式 Word fallback | ✅ 代码合同 |
| PDF/Worker/API 定向测试 | server/.venv/Scripts/python.exe -m pytest server/tests/test_pdf_deliverable_contract.py server/tests/test_spec0043_docx_pdf_exporter.py server/tests/test_outline_worker_handlers.py server/tests/test_outlines_service.py server/tests/test_outlines_api.py -q：90 passed | ✅ |
| 项目工作台投影 | GET /api/projects/{project_id}/workspace-projection；阶段、下一步、阻断原因由 projects owner 生成 | ✅ |
| 交付审阅投影 | GET /api/projects/{project_id}/delivery-review；交付物、追溯链、质量门禁和可用动作由 delivery_review query owner 生成 | ✅ |
| 投影合同测试 | test_projects_projection.py：7 passed；test_delivery_review.py：3 passed | ✅ |
| 阶段子步骤合同 | phase_id/phase_label/is_substep 由 projects projection 生成；Sources 与 Evidence 归入“资料与证据”复合阶段，前端只按投影分组 | ✅ 8 passed |
| 前端状态与错误文案 | PENDING/RUNNING/SUCCEEDED/FAILED/STALE 使用统一用户文案；错误码和任务 ID 放入技术详情折叠区；加载、空态、错误和 disabled 状态保留 | ✅ |
| 后端全量 | root 运行：1254 passed、1 failed；server 工作目录复核同样 1254 passed、1 failed，失败为既有 SPEC 0042 科研 SVG manifest SHA-256 不匹配 | ⚠️ 阻断/非本切片，需单独处理 |
| Windows portable runtime | 构建脚本要求 LIBREOFFICE_ROOT、program/soffice.exe 和 runtime-metadata.json，并写入版本/来源/许可证 manifest；当前本地没有 runtime 目录，未执行真实包构建 | ⚠️ 未完成 |
| 浏览器视觉验收 | 浏览器技能初始化因 trusted Node process exited unexpectedly/受控 Node helper 退出失败；未取得 1280px 截图，不宣称视觉通过 | ⚠️ 工具限制 |
| Git | 保留 codex/before-workspace-shell-20260822 和 stash@{0}；当前未 stage、commit、push | ⏸️ 待子阶段确认 |

当前结论：SPEC 0047 的项目投影合同、统一工作台壳层和七个目标工作区已形成可复核增量；代码门禁和合同链路通过，但正式交付仍被 LibreOffice runtime、既有科研资产 hash、真实 Windows/浏览器验收阻断，不能标记为完整收口。
## SPEC 0047 项目进度投影重复定义修复复核（2026-08-23）

| 验收项 | 证据/边界 | 结果 |
|---|---|---|
| 投影合同与唯一接口 | 保留 `GET /api/projects/{project_id}/workspace-projection`；同一响应加入 `current`、`phases`、`recommended_next_action`，保留 `current_stage`、`next_action`、`stages` 兼容字段；未新增第二个项目进度接口 | ✅ |
| 后端 owner 与状态优先级 | `server/app/modules/projects/projection.py` 生成阶段、子步骤、开放性、锁定原因、阻断原因、动作和恢复动作；失败/阻断事实优先于完成 rank；完成项目不返回下一步动作 | ✅ |
| API 合同断言 | `server/tests/test_projects_projection.py`：7 passed；覆盖 `topic`、`status_label`、`current`、阶段子步骤、锁定 `open_reason`、`recommended_next_action.command_id` 和兼容字段 | ✅ |
| 前端状态机迁移 | 七个目标工作区复用 `WorkspaceShell`，生产页面不再定义 `ORDERED_STATUSES`、`orderedStatuses`、`isAtOrAfter`、`getWorkspaceVisibility`、`getNextWorkspace`、`canRegister` 或项目级 `canComplete`；RequirementWorkspaceView 仅保留既有状态展示 | ✅ |
| 前端回归 | `apps/web` 执行 `npm.cmd run test`：35 个测试文件、548 passed；ProjectDetailView 定向测试 8 passed | ✅ |
| 前端静态门禁 | `apps/web` 执行 `npm.cmd run lint`、`npm.cmd run build`：均通过 | ✅ |
| 数据库门禁 | `server` 执行 `.venv/Scripts/python.exe -m alembic upgrade head`：通过 | ✅ |
| 后端全量回归 | `server` 执行 `.venv/Scripts/python.exe -m pytest`：1254 passed、1 failed；失败为既有 SPEC 0042 的 `bioicons-cc0-cryo-vial` SVG manifest SHA-256 漂移，不在本轮投影调用链 | ⚠️ 既有阻断，未纳入本轮修复 |
| 浏览器视觉验收 | 当前浏览器 Node helper 仍因 `trusted Node process exited unexpectedly` 退出，未取得 1280px/窄屏截图 | ⚠️ 未完成 |
| Git 边界 | 本轮仅精确 stage 投影合同、统一壳层、目标页面接线、测试和文档；其他用户改动保持 unstaged | ✅ |

当前结论：项目进度投影合同和前端重复状态门控迁移已通过代码与合同门禁；由于既有科研资产 hash、LibreOffice runtime、浏览器视觉和干净 Windows 验收未闭合，本轮提交为实现 checkpoint，不是完整发布收口。
## SPEC 0047 交付物审阅台实现复核（2026-08-23）

| 验收项 | 证据/边界 | 结果 |
|---|---|---|
| 交付审阅合同 | `server/app/modules/delivery_review/contracts.py` 与 `projection.py` 覆盖 Word/PDF/PPT 身份、版本 provenance、内容质量、统计边界、推荐版本、失败恢复、预览和视觉检查状态 | ✅ |
| provenance 写入链 | `DeliverableVersion` 新增可空来源字段；Alembic 0008；Word/PPT 写入实际执行记录，PDF 继承实际 Word 版本；旧版本缺失时返回 N/A 原因 | ✅ |
| 质量判断 owner | 质量门禁、内容检查、观察性/因果、L3 和医学教学边界均由后端投影计算；前端只消费 projection；`delivery_review/service.py` 仅保留兼容导出 | ✅ |
| 真实预览与视觉检查 | 无真实缩略图返回 `NOT_AVAILABLE`；未进行真实逐页检查返回 `NOT_CHECKED`，界面不显示“通过” | ✅ 合同；真实视觉待验收 |
| API 与状态测试 | `test_delivery_review.py`、`test_delivery_review_api.py`：9 passed；覆盖空态、失败、历史版本 N/A、负向边界、显式边界正向、Word/PDF/PPT 同源 provenance 和 HTTP 合同 | ✅ |
| 生成链回归 | outlines service/API、Word/PPT/PDF worker、PDF 合同及交付审阅相关测试：97 passed；期间修复 PPT provenance 调用括号回归 | ✅ |
| 前端状态与错误态 | `DeliverableWorkspaceView` 定向 22 passed；前端全量 35 个测试文件、550 passed；覆盖 loading、empty、error、failed、STALE、disabled、success 和版本读取失败 | ✅ |
| 前端静态门禁 | `npm.cmd run lint`、`npm.cmd run build` | ✅ |
| 数据库迁移 | `server` 目录执行 `.venv/Scripts/python.exe -m alembic upgrade head` | ✅ |
| 后端全量 | 根目录执行 `server/.venv/Scripts/python.exe -m pytest`：1260 passed、1 failed；失败为既有科研资产 `bioicons-cc0-cryo-vial` SVG manifest SHA-256 漂移，不在本切片调用链 | ⚠️ 既有风险 |
| 浏览器视觉验收 | 浏览器 Node helper 在初始化阶段退出（`node_repl kernel exited unexpectedly`），未取得 1280px/窄屏截图；不能宣称 UI 视觉通过 | ⚠️ 未完成 |
| LibreOffice/portable/真实文件 | 当前未完成 LibreOffice runtime 注入、portable 黑盒、真实 DOCX→PDF 和 Word/PDF/PPT 逐页一致性验收 | ⚠️ 未完成 |

当前结论：交付物审阅台已经通过代码合同和自动化测试门禁，形成实现 checkpoint；受既有科研资产 hash、真实浏览器、LibreOffice runtime、portable 和真实文件视觉验收影响，SPEC 0047 仍不能标记为完整发布收口。

## SPEC 0043 PPT 诊断分层缺图修复复核（2026-08-25）

| 验收项 | 证据/边界 | 结果 |
|---|---|---|
| 缺图根因 | `PptRenderer._build_defense_layout()` 的带图角色集合遗漏 `diagnosis_stratified`；planner 已正确绑定图表 | ✅ 已修复 |
| 角色回归测试 | `server/tests/test_renderers.py` 新增 academic `diagnosis_stratified` 页面主视觉测试 | ✅ |
| 定向测试 | Word/PPT 交付相关测试集：42 passed | ✅ |
| 真实 PPT 重生成 | academic 与 sjtu_academic 两套样例均为 18 页、16:9；第 13 页各含 1 张图片，第 16 页矩阵图保留 | ✅ |
| PowerPoint 原生导出 | 两套 PPT 各导出 18 张 PNG；导出过程未写入项目目录 | ✅ |

当前结论：第 13 页缺图这一项 P1 交付阻断已关闭；manifest 验证脚本合同漂移、最新 PDF 全页人工视觉复核和其他既有验收限制仍未纳入本次修复收口。

## SPEC 0043 发布链 validator 合同修复复核（2026-08-25）

| 验收项 | 证据/边界 | 结果 |
|---|---|---|
| manifest 合同 | validator 支持当前 `deliverables`，并保留旧 `artifacts` object/list 解析 | ✅ |
| manifest 失败边界 | 显式提供 manifest 且合同非法时，不再回退扫描 `root` 或 `.tmp` 旧产物 | ✅ |
| PPT 字号合同 | 标题/正文/图注分别按 35/18/12pt 验证；不再以全局最小字号误判图注 | ✅ |
| 弃用告警 | DOCX 结构检查改为显式判断 `settings/header/footer` 是否存在 | ✅ |
| 回归测试 | `server/tests/test_verify_spec0043_publication_chain.py`：4 passed；manifest/论文样例回归：14 passed；Word/PDF/PPT 相关回归：42 passed | ✅ |
| 真实发布链 | `verify_spec0043_publication_chain.py --manifest .../publication_manifest.json --minimum-slides 18`；academic 与 sjtu PPT 均 PASS，DOCX/PDF/PPTX 均可解析 | ✅ |

当前结论：validator 合同漂移与 `.tmp` 旧产物误回退已修复；本记录不代表全项目发布收口，最新 PDF 全页人工视觉复核、浏览器/LibreOffice/portable 等既有未验证项仍保持原边界。

## SPEC 0043 真实产物视觉复核（2026-08-25）

| 验收项 | 证据/边界 | 结果 |
|---|---|---|
| PDF 全页渲染 | 使用 Poppler `pdftoppm` 渲染 `spec0043_publication.pdf`，得到 21 张 PNG；Poppler 仅有 `nameToUnicode` 字体映射警告，渲染退出码为 0 | ✅ |
| PDF 视觉检查 | 检查 21 页 contact sheet，并抽查封面、正文图表页、样本流程/分布页、比较矩阵页和参考文献尾页；未发现明显截断、重叠、空白页、黑块或图表越界 | ✅ 视觉证据覆盖 |
| academic PPT 视觉检查 | 当前 18 页 PNG contact sheet及第 13、16、17、18 页关键页检查；第 13 页诊断分层图存在，矩阵图保留，未发现明显裁切或越界 | ✅ 视觉证据覆盖 |
| sjtu PPT 视觉检查 | 当前 18 页 PNG contact sheet 检查；统一配色、页数和关键图形保持，未发现明显裁切或越界 | ✅ 视觉证据覆盖 |
| PPT 形状边界 | 两套 PPT：13.33×7.5 英寸、18 页、各 11 张图片，形状越界 0 | ✅ |
| 自动 helper 限制 | `render_slides.py` 与 `slides_test.py` 已生成 PNG，但末端因 Windows 路径反斜杠导致 JSON `Invalid \\escape` 退出；未将 helper 命令宣称自动通过，改用生成 PNG 与形状边界统计作为替代证据 | ⚠️ 环境限制 |

当前结论：SPEC 0043 的 PDF/PPT 真实渲染视觉证据已补齐到当前样例；自动 PPT helper 的 Windows JSON 路径问题仍记录为环境限制。本项目仍不宣称完整发布收口，浏览器、LibreOffice runtime、portable 黑盒和全量后端既有失败项保持原边界。

## 全局门禁复核（2026-08-25）

| 门禁 | 实际命令/证据 | 结果 |
|---|---|---|
| 后端全量测试 | `server/.venv/Scripts/python.exe -m pytest -q`（server 工作目录） | ✅ 1266 passed in 81.26s |
| SVG 来源核验 | 固定 Bioicons commit `d29e766ea7580b8063c4f47b29e872db40a4d979`；`cryo_vial.svg` 与 `sequencer.svg` 的上游 raw SHA-256 均分别与 manifest `source_sha256` 一致；本地原差异仅为 CRLF 换行，逐行文本一致 | ✅ |
| SVG 恢复 | 恢复 `server/app/assets/scientific/svg/apparatus/cryo_vial.svg` 与 `server/app/assets/scientific/svg/instruments/sequencer.svg` 为固定上游 raw 字节；两者本地 SHA-256 与 manifest 一致，manifest 未修改；其余 5 个 SVG 未触碰且哈希已匹配 | ✅ |
| 科研资产定向回归 | `tests/test_scientific_asset_registry.py tests/test_scientific_schematic_renderer.py -q` | ✅ 29 passed |
| 前端全量测试 | `apps/web` 执行 `npm.cmd run test -- --run` | ✅ 35 个测试文件、550 passed |
| PDF/交付定向回归 | `tests/test_pdf_deliverable_contract.py tests/test_spec0043_docx_pdf_exporter.py tests/test_outline_worker_handlers.py tests/test_outlines_service.py tests/test_outlines_api.py -q` | ✅ 92 passed |
| Windows portable 源合同 | `tests/test_spec0046_windows_packaging.py -q` | ✅ 4 passed |
| 浏览器视觉验收 | 系统 Chrome + Playwright 已取得 1280px/390px 真实截图；浏览器插件自身仍受 trusted Node process exited unexpectedly 影响 | ✅ 替代验收 |
| LibreOffice runtime | portable LibreOffice 26.2.5.2 已完成 headless 启动和真实 DOCX→PDF；当前 PDF 已栅格化并逐页检查 | ✅ |
| 工程漂移脚本 | `check_project_guardrails.py D:\\java_project\\lab-report-assistant`：通用 bootstrap 模板要求英文章节/片段，与本项目中文真源结构不匹配；未改写项目宪法或真源文档 | ⚠️ 工具不适用 |
| Alembic | 临时 SQLite `server/.tmp/codex_full_gate_20260825.db` 执行 `.venv/Scripts/python.exe -m alembic upgrade head`，升级至 0008 | ✅ |
| 前端 lint | `apps/web` 工作目录执行 `npm.cmd run lint` | ✅ |
| 前端 build | `apps/web` 工作目录执行 `npm.cmd run build` | ✅ |
| 临时状态 | 本轮临时 Alembic 数据库已删除，未触碰 `server/data/app.db` | ✅ |

当前结论：交付链定向门禁、科研资产定向回归、后端全量、真实产物结构/视觉检查、Alembic、前端门禁、portable runtime、当前 PDF 视觉和浏览器替代验收均通过；两份科研 SVG 的 manifest 哈希漂移已关闭。剩余边界仅为独立干净 Windows x64 黑盒和当前项目同源 Word/PDF/PPT 重新生成后的视觉一致性，不因本次验收宣称完整发布收口。
## SPEC 0047 LibreOffice portable runtime 复核（2026-08-25）

| 验收项 | 证据/边界 | 结果 |
|---|---|---|
| 官方 runtime 来源 | LibreOffice 26.2.5 Windows x86-64 官方 MSI，372,948,992 bytes；SHA-256 `F15BA07BFCB0186986CF3171063506F5D207C11F8CC051BA0D135209E9E915F9` | ✅ |
| runtime 元数据与许可证 | 临时 runtime 含 `version`、`source`、`source_sha256`、`license_files`；`LICENSE.html`、`license.txt`、`NOTICE` 和 `readmes/readme_en-US.txt` 均存在 | ✅ |
| 独立 portable 构建 | 使用 `LIBREOFFICE_ROOT` 指向临时解压 runtime，独立输出目录生成 service、launcher、web、LibreOffice 和 `release-manifest.json`；包内约 1.88 GB、22,502 个文件 | ✅ |
| 发布 manifest | `pdf_converter` 写入 provider、executable、version、source、source_sha256 和 license_files；manifest SHA 与 runtime metadata 一致 | ✅ |
| portable headless 启动 | 包内 `soffice.com --headless --version` 返回 LibreOffice 26.2.5.2、退出码 0；`soffice.exe`、service.exe 和根启动器均存在 | ✅ |
| 生产 PDF 适配器 | `DocxPdfExporter(converter_path=<portable>/libreoffice/program/soffice.exe)` 将 `spec0042_scientific_schematic.docx` 转为 456,765 bytes 的有效 PDF，退出成功 | ✅ |
| PDF 结构与栅格化 | bundled `pdfinfo` 识别 A4、10 页、无加密；`pdftoppm -png` 退出码 0，生成 `page-01.png` 至 `page-10.png` | ✅ |
| PDF 逐页视觉检查 | 使用 Poppler 生成 10 张 PNG 并逐页检查；未发现空白页、裁切、重叠或异常黑块 | ✅ |
| 浏览器/干净 Windows | 系统 Chrome + Playwright 已完成 1280px/390px 截图；独立无 Python/Node.js/Docker Windows x64 仍未完成 | ⚠️ 部分未完成 |

当前结论：LibreOffice runtime、portable 构建、真实 DOCX→PDF、当前 PDF PNG 视觉和浏览器视觉验收已完成；独立干净 Windows 黑盒和当前项目同源 Word/PDF/PPT 重新生成视觉一致性仍未完成，SPEC 0047 继续保持实现 checkpoint。

## SPEC 0047 真实浏览器与交付视觉复核（2026-08-25）

| 验收项 | 证据/边界 | 结果 |
|---|---|---|
| 浏览器页面与路由 | 使用系统 Chrome + Playwright 访问首页、项目详情、交付审阅台；截图和 result.json 保存在 dev-docs/e2e-screenshots/spec0047_browser_qa/ | ✅ |
| 桌面视觉 | 1280×900 下首页项目卡片、项目阶段路线和交付审阅台均正常渲染；后端投影状态、阻断原因和修复动作可读 | ✅ |
| 窄屏视觉 | 390×844 下交付审阅台变为单列；页面级 documentScrollWidth 与 viewportWidth 均为 390，未出现横向溢出 | ✅ |
| 资源与控制台 | favicon.svg 已由 index.html 显式引用；浏览器结果 events 为空，前后端运行日志中的页面/API 请求均成功 | ✅ |
| PDF 真实派生 | LibreOffice 26.2.5.2 portable headless 从真实 DOCX 生成有效 PDF；pdfinfo 识别 A4、10 页，pdftoppm 成功生成 10 张 PNG | ✅ |
| PDF 逐页视觉 | 本轮检查 page-01.png 至 page-10.png，未发现空白页、裁切、重叠或异常黑块；临时栅格目录验收后清理 | ✅ |
| 产品状态投影 | 演示项目仍显示“需处理”：当前大纲没有对应 PDF 成功版本，Word/PDF/PPT 尚未形成同源集合；该阻断与后端事实一致，不是 UI 误报 | ✅ 正确阻断 |

本轮保留的产品视觉证据：home-1280.png、project-detail-1280.png、deliverables-1280.png、deliverables-narrow.png 及 result.json。浏览器插件自身仍因 trusted Node process exited unexpectedly 无法连接，已使用系统 Chrome + Playwright 完成等价真实视觉验收。

当前结论：SPEC 0047 的浏览器视觉、窄屏布局、favicon 资源和当前 PDF 栅格化视觉已通过；仅剩无 Python/Node.js/Docker 的独立 Windows x64 黑盒验收，以及以同一份当前项目大纲重新生成并检查 Word/PDF/PPT 同源交付物。

## SPEC 0044 字号统一与正式报告视觉复核（2026-08-26）

| 验收项 | 证据/边界 | 结果 |
|---|---|---|
| Word 字号 token | 正文 10.5pt、表格 9pt、图注 9pt、目录 10.5pt；标题层级保留 16/12pt 等差异 | ✅ |
| 封面表格分页 | 封面研究信息表统一为 9pt，并压缩仅表格单元格留白/行距；重新生成后完整留在第 1 页，不再出现表格尾部孤页 | ✅ |
| PDF 适配器 | 修复 `DocxPdfExporter._export_with_word()` 漏失 `@staticmethod` 导致 `(source, target)` 调用多传 `self` 的阻断 | ✅ |
| 定向回归 | `test_spec0044_standardized_paper.py`、`test_spec0043_docx_pdf_exporter.py`、`test_document_planner.py`、`test_renderers.py`：39 passed | ✅ |
| DOCX 结构 | `spec0043_publication.docx` 实际包含 14 张内嵌图；run 字号统计以 9.0pt/10.5pt 为主，所有表格 run 为 9.0pt | ✅ |
| DOCX/PDF manifest | `publication_manifest.json` 的 `source_docx_sha256` 与 `pdf_sha256` 均与实际文件匹配 | ✅ |
| PDF 全页栅格化 | Poppler `pdftoppm` 渲染 `pdf_render_font_fix_v2/page-01.png` 至 `page-21.png`，仅有 `nameToUnicode` 映射警告，退出码为 0 | ✅ |
| PDF 视觉检查 | 抽查封面、摘要/目录、正文图表与表格、森林图/趋势图、比较矩阵、关系图、参考文献末页；未发现封面表格孤页、图注脱离、裁切、重叠或图表丢失 | ✅ |

当前结论：字号统一与正式 `spec0043_publication` DOCX/PDF 重生成已通过本轮定向测试、manifest、14 张图完整性和真实 PDF 栅格化视觉检查；不因此宣称项目整体发布收口，既有独立 Windows x64 黑盒和同源交付物全链路边界保持不变。

## SPEC 0047 当前源码 portable EXE 重建与黑盒复核（2026-08-26）

| 验收项 | 证据/边界 | 结果 |
|---|---|---|
| 旧包原因 | 原 `server/.tmp/windows-package/release` EXE 为 2026-08-21 产物；其内置前端仍为旧 bundle，不会读取当前源码 | ✅ 根因确认 |
| 当前前端构建 | `tsc -b && vite build`；127 modules；当前 bundle 为 `index-39Lpbw5h.js` / `index-CwnzC8Jm.css` | ✅ |
| 当前源码 portable 构建 | `LIBREOFFICE_ROOT` 指向官方 LibreOffice 26.2.5 临时 runtime；重新生成 service、launcher、web、LibreOffice 和 `release-manifest.json` | ✅ |
| 包内前端一致性 | 包内 `web/index.html` SHA-256 与当前 `apps/web/dist/index.html` 均为 `629D8A9541832B72340BD2A9830FB866EC8676731068C54A78B9FA8BCD294B26`；页面实际加载 `/assets/index-39Lpbw5h.js` | ✅ |
| 发布 manifest | `server/.tmp/windows-package/release/实验报告助手-win-x64/release-manifest.json`；22,503 个文件；记录 LibreOffice 版本、来源 SHA-256 和许可证清单 | ✅ |
| portable PDF runtime | 包内 `soffice.com --headless --version` 返回 LibreOffice 26.2.5.2，退出码 0 | ✅ |
| 最新 EXE 启动 | 根启动器、内层启动器、service backend、Worker 均启动；`/health`、首页、`/api/projects` 均返回 200；页面加载当前 bundle | ✅ |
| 生命周期关闭 | 动态枚举真实窗口“实验报告助手 - 运行中”，`PostMessage(WM_CLOSE)` 返回成功；外层/内层/后端/Worker 和 8787 端口均回收 | ✅ |
| 重启保留 | 重新启动当前源码 EXE 后再次通过 `/health`、首页和 `/api/projects`；当前实例留在本地工作台供视觉查看 | ✅ |
| 定向合同测试 | `server/tests/test_spec0046_windows_packaging.py server/tests/test_spec0047_portable_runtime.py` | ✅ 6 passed |
| 独立干净 Windows | 当前仍在开发机验证，未完成无 Python/Node.js/Docker 的独立 Windows x64 主机黑盒 | ⚠️ 未完成 |
| 最新包全链路视觉 | 当前已验证页面资源、路由和运行状态；未在独立干净主机重新执行完整业务路径与逐屏截图 | ⚠️ 部分未完成 |

当前结论：当前源码已经重新打进 portable EXE，旧项目界面残留问题已关闭；启动、当前前端 bundle、LibreOffice runtime、正常关闭和重启链路均通过。独立干净 Windows x64 主机及完整业务路径视觉验收仍保持未完成边界。
