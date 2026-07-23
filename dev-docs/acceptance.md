# 实验报告助手｜验收与漂移控制

> 状态：SPEC 0005 受控 Python 执行已完成实现与端到端验收，待项目负责人确认收口  
> 依据：[project-charter.md](project-charter.md)、[architecture.md](architecture.md)  
> 当前限制：代码阶段已正式启动。SPEC 0005 已完成端到端验收（含主链路、错误分支、STALE 传播、受控执行环境安全限制）。当前会话未暴露可调用的 in-app Browser 工具，SPEC 0005 已用 API 测试套件（33 个测试覆盖 11 个端点）作为替代证据，未完成真实浏览器点击截图验收。

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

第一切片已获项目负责人批准进入代码阶段后执行。SPEC 0002 已完成实现、复核验收并由项目负责人确认收口；SPEC 0003 已完成实现与端到端验收并由项目负责人确认收口；SPEC 0004 已完成实现与端到端验收并由项目负责人确认收口；SPEC 0005 已完成实现与端到端验收，待项目负责人确认收口；后续切片开始前，仍需项目负责人确认下一切片 SPEC。

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
- SPEC 0005 的受控 Python 执行引擎、AST import 白名单校验、psutil 进程树内存监控、CodeTask/ExecutionRun/ExecutionArtifact 核心合同、STALE 传播、状态推进到 RESULT_CONFIRMED 已通过 API 测试套件（33 个测试覆盖 11 个端点）和 python_executor 单元测试（48 个测试覆盖安全限制、超时、内存、产物收集）端到端验收，待项目负责人确认收口。

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

## 漂移检查清单

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
