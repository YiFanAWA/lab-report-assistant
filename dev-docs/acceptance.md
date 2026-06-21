# 实验报告助手｜验收与漂移控制

> 状态：SPEC 0003 已完成干净分支复验，并于 2026-06-22 由项目负责人确认收口
> 依据：[project-charter.md](project-charter.md)、[architecture.md](architecture.md)  
> 当前限制：下一切片尚未批准；Skill、Orchestrator、feasibility、Alembic 0004、数据集、Python 执行和交付物不属于 SPEC 0003 已验收范围。

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

第一切片已获项目负责人批准进入代码阶段后执行。SPEC 0001、SPEC 0002、SPEC 0003 均已完成实现、复核验收并由项目负责人确认收口。下一切片必须重新经过 SPEC 与批准门禁。

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
- 上一切片 SPEC 0001 的代码结构、后端测试、数据库迁移、前端构建和前后端代理验收已通过。
- SPEC 0002 的需求来源、结构化任务单、L0-L3、编辑确认、状态推进和最小变更记录已通过当前命令/API/代理验收，并已由项目负责人确认收口。
- SPEC 0003 已完成测试、迁移、API、前端、Browser 分段证据复核并由项目负责人确认收口；这不构成下一切片或 Skill 扩展批准。

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
| 2026-06-17 | SPEC 0003 早期实现记录 | 曾记录 37 tests 和迁移通过；2026-06-18 复核发现 URL 主链路、SSRF、API 合同、状态推进、UI 和当前 Python 环境未闭合 | 已撤回完成结论 |
| 2026-06-17 | Skill 层早期记录 | 41 个测试函数中只有 4 个浅层 Skill 测试，未覆盖正式注册、run_skill、审计和 Orchestrator 执行闸 | 未验收 |
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
| 2026-06-17 | SPEC 0003 编写 | 创建 `dev-docs/specs/0003-public-sources-and-evidence-workflow.md`，限定公开 URL、本地辅助资料登记、解析文本和证据卡片工作流；未创建业务代码、未安装依赖 | 历史记录 |
| 2026-06-18 | SPEC 0003 风险测试 RED | `server/.venv/Scripts/python.exe -m pytest` 运行五个来源测试文件并使用仓库内 `--basetemp`；结果 `10 failed, 15 passed, 1 warning`，失败对应重定向安全、解析位置、Provider 合同和 evidence_type 校验 | 预期失败 |
| 2026-06-18 | SPEC 0003 针对性 GREEN | 来源、解析、证据、来源 API 与既有要求 API 共 `32 passed, 1 warning`；后续 DOCX 位置与访问限制测试分别先失败再通过 | 通过 |
| 2026-06-18 | SPEC 0003 候选分支回归 | 候选分支曾输出 `58 passed, 1 warning`，其中混有 4 个浅层 Skill 测试；该结果只作为发现范围污染的历史证据，不作为最终收口门禁 | 历史记录 |
| 2026-06-18 | SPEC 0003 候选分支迁移 | 候选分支曾迁移到 0004；干净收口分支明确排除迁移 0004，并在 2026-06-22 单独复验迁移 0003 | 历史记录 |
| 2026-06-18 | SPEC 0003 前端类型检查 | `apps/web` 下执行 `npm.cmd run lint`，退出码 0，TypeScript 无错误 | 前端代码门禁通过 |
| 2026-06-18 | SPEC 0003 前端构建 | 沙箱首次因 Windows ACL 无法读取 `vite.config.ts`；按权限流程在宿主权限下原命令 `npm.cmd run build` 重跑，退出码 0，Vite 转换 95 modules，无构建 warning | 前端构建门禁通过 |
| 2026-06-18 | 稳定化阶段确认 | 项目暂停新功能进入稳定化阶段，并开始拆分 SPEC 0003 与未验收 Skill/Orchestrator/0004 污染范围 | 历史记录 |
| 2026-06-18 | 稳定化 Provider 合同审计 | 唯一 draft(EvidenceDraftDocument) 接口，Service、Provider、测试全部一致 | 沙箱通过 |
| 2026-06-18 | 稳定化 SQLite 路径修复 | 基于稳定根目录绝对路径，自动创建父目录，默认值在启动时打印路径 | 沙箱验证通过 |
| 2026-06-18 | 稳定化前端 | 前端 TypeScript 与构建通过；后续 Browser 复核确认来源工作区路由和入口已连接 | 历史代码门禁 |
| 2026-06-18 | 稳定化污染扫描 | 候选分支识别出 Skill、Orchestrator、0004 和浅层 Skill 测试；最终干净收口分支全部排除 | 污染边界已识别 |
| 2026-06-21 | SPEC 0003 Browser 关键交互 | 真实页面验证私网 URL 错误展示、来源解析、候选生成、证据类型与摘要编辑保存、刷新保持、证据确认、项目状态推进、项目详情入口与工作台导航；控制台无 error/warn | 关键交互通过 |
| 2026-06-21 | SPEC 0003 Browser 截图 | 确认态截图保存于忽略目录 `.tmp/spec0003-browser-evidence-confirmed-20260621.png`，不纳入 git | 通过 |
| 2026-06-22 | SPEC 0003 干净后端回归 | 隔离 worktree 执行 `server/.venv/Scripts/python.exe -m pytest --basetemp ./.tmp/pytest-spec0003-clean-20260622`，结果 `54 passed, 1 warning`；4 个 Skill 浅层测试未进入测试集 | 代码门禁通过 |
| 2026-06-22 | SPEC 0003 干净数据库迁移 | 全新 `.tmp/spec0003-clean-20260622.db` 执行 Alembic `upgrade head` 与 `current`，依次经过 0001—0003，current 为 `0003 (head)` | 迁移门禁通过 |
| 2026-06-22 | SPEC 0003 干净前端复验 | 隔离 worktree 执行 `npm.cmd run lint` 与 `npm.cmd run build`，退出码均为 0，Vite 转换 95 modules | 前端代码门禁通过 |
| 2026-06-22 | SPEC 0003 干净代理主链路 | 使用迁移到 0003 的全新数据库，经 Vite `/api` 完成需求确认、TXT 上传、解析、候选生成、证据确认、刷新读取，最终项目状态 `EVIDENCE_CONFIRMED`；私网 URL 返回 HTTP 400 与 `SOURCE_URL_BLOCKED_PRIVATE_NETWORK` | 合同链路通过 |
| 2026-06-22 | SPEC 0003 项目负责人确认 | 项目负责人明确回复“确认 SPEC 0003 收口”，接受“API 文件上传合同 + Browser 下游真实交互”的分段证据 | 确认收口 |

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
- 在下一切片 SPEC 未批准前扩展 Skill、Orchestrator、feasibility、数据集、Python 执行或交付物能力。

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
