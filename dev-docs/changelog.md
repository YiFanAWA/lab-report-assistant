# 实验报告助手 变更日志

> 本文件记录每个开发切片和版本的核心变更，方便后续回顾和交接。
> 内部治理历史进入 `decisions/`，验收证据进入 `acceptance.md`，本文件聚焦"做了什么"。

---

## V1.0 端到端验收阶段：技术债务清理 + Worker 验证 + 前端 UI 补充

**完成日期：** 2026-07-22  
**阶段：** V1.0 完整端到端验收阶段  
**依据：** [e2e-acceptance-report-v1.0.md](e2e-acceptance-report-v1.0.md)、[tech-debt-cleanup-plan.md](tech-debt-cleanup-plan.md)、[worker-e2e-log.md](worker-e2e-log.md)

### 一、技术债务清理（TD-001 + TD-002）

**目标：** 将 pytest warnings 从 21 条降至 0 条，确保 V1.0 发布前无遗留警告。

| 债务 | 清理方案 | 验证结果 |
| --- | --- | --- |
| TD-001（httpx 弃用提示） | 安装 `httpx2 2.7.0`（传递依赖 `httpcore2 2.7.0`、`truststore 0.10.4`）；`pyproject.toml` dev 依赖新增 `httpx2>=2.0.0` | pytest → 569 passed, **0 warnings** |
| TD-002（pandas datetime 推断） | `dataset_parser.py:96` 添加 `format="mixed"` 参数 | pytest → 569 passed, **0 warnings** |

**修改文件：**
- `server/pyproject.toml`：dev 依赖新增 `httpx2>=2.0.0`
- `server/app/infrastructure/parsers/dataset_parser.py`：`_infer_field_type` 中 `to_datetime` 添加 `format="mixed"`

### 二、Worker 端到端验证

**目标：** 启动 Worker 进程进行实际后台任务验证，确认状态机流转正常。

**验证脚本：** `server/worker_e2e_verify.py`  
**运行日志：** `dev-docs/worker-e2e-log.md`

**验证流程：**
1. alembic upgrade head 确保数据库最新
2. 创建项目 → 推进到 RESULT_CONFIRMED → 插入模拟 ExecutionRun
3. 触发大纲生成 → Worker `handle_generate_outline` 执行 → CANDIDATE
4. 确认大纲 → OUTLINE_CONFIRMED
5. 触发 Word 生成 → Worker `handle_generate_word` 执行 → Word 文件生成（37032 bytes）
6. 触发 PPT 生成 → Worker `handle_generate_ppt` 执行 → PPT 文件生成（32231 bytes）
7. 完成项目 → COMPLETED

**结果：** 项目 proj_6c52304bf9fb 完整流转 RESULT_CONFIRMED → COMPLETED，Word 和 PPT 文件均实际存在。

### 三、前端 UI 补充（V1.0 确认事项第 4 和第 9 项）

**目标：** 为 SPEC 0006 新增的 11 个 API 端点补充前端页面代码，让用户能在浏览器中走完"生成大纲 → 确认 → 生成 Word/PPT → 下载 → 完成项目"的完整流程。

#### 3.1 新增 outlines feature 模块

**`apps/web/src/features/outlines/types.ts`：**
- OutlineSection、OutlineStatus、DeliverableType、DeliverableStatus、DeliverableVersionStatus
- Outline、OutlineListResponse、UpdateOutlineRequest
- Deliverable、DeliverableListResponse
- DeliverableVersion、DeliverableVersionListResponse
- GenerateOutlineResponse、GenerateDeliverableResponse、CompleteProjectResponse

**`apps/web/src/features/outlines/api.ts`：** 12 个 API 函数
- generateOutline、listOutlines、getOutline、updateOutline、confirmOutline、rejectOutline
- generateWord、generatePpt
- listDeliverables、listDeliverableVersions、buildDeliverableDownloadUrl、completeProject

**`apps/web/src/features/outlines/hooks.ts`：** 11 个 TanStack Query hooks
- useOutlines、useOutline、useGenerateOutline、useUpdateOutline、useConfirmOutline、useRejectOutline
- useGenerateWord、useGeneratePpt
- useDeliverables（3s 轮询）、useDeliverableVersions（3s 轮询）、useCompleteProject

#### 3.2 新增工作区视图

**`apps/web/src/routes/OutlineWorkspaceView.tsx`：**
- 项目状态展示（含 RESULT_CONFIRMED/OUTLINE_CONFIRMED/GENERATING/COMPLETED 中文映射）
- 生成大纲候选按钮（仅 RESULT_CONFIRMED 状态可见）
- 大纲卡片：章节列表（含来源类型标签）、编辑模式（title/content/source_type/source_ids 可编辑）、确认/拒绝按钮
- STALE 提示
- 确认后显示 Word/PPT 生成按钮，跟踪生成任务状态（useJob 轮询）

**`apps/web/src/routes/DeliverableWorkspaceView.tsx`：**
- 交付物列表（Word 和 PPT 卡片，含状态中文映射）
- 版本列表（含状态、文件大小、耗时）
- 下载按钮（仅 SUCCEEDED 版本可下载）
- 失败版本错误信息展示
- 完成项目按钮（需至少一个 Word 和一个 PPT SUCCEEDED）
- 3 秒轮询交付物和版本状态

#### 3.3 路由和入口更新

**`apps/web/src/app/App.tsx`：** 新增 2 个路由
- `/projects/:projectId/outline` → OutlineWorkspaceView
- `/projects/:projectId/deliverables` → DeliverableWorkspaceView

**`apps/web/src/routes/ProjectDetailView.tsx`：**
- 状态中文映射新增 EXECUTING/EXECUTION_FAILED/RESULT_CONFIRMED/OUTLINE_CONFIRMED/GENERATING
- ORDERED_STATUSES 新增 5 个状态
- 大纲工作区入口（RESULT_CONFIRMED 及之后显示）
- 交付物工作区入口（OUTLINE_CONFIRMED 及之后显示）

**`apps/web/src/features/jobs/types.ts`：** JobType 新增 GENERATE_OUTLINE/GENERATE_WORD/GENERATE_PPT

#### 3.4 验收证据

| 验收项 | 命令 | 结果 |
| --- | --- | --- |
| 前端类型检查 | `npm run lint` | tsc --noEmit 通过 |
| 前端构建 | `npm run build` | Vite 构建通过，**110 模块**（原 106 + 新增 4），370.81 kB，gzip 103.39 kB |

### 四、文件变更统计

- **新增文件：** 6 个（outlines feature 3 + 工作区视图 2 + worker_e2e_verify.py 1）
- **修改文件：** 5 个（pyproject.toml、dataset_parser.py、App.tsx、ProjectDetailView.tsx、jobs/types.ts）
- **文档更新：** 4 个（acceptance.md、changelog.md、README.md、tech-debt-cleanup-plan.md）

### 五、V1.0 确认事项进展

| 确认事项 | 状态 |
| --- | --- |
| 第 4 项：V1.0 是否需要支持前端 UI 变更 | ✅ 已补充大纲和交付物前端页面 |
| 第 6 项：是否在 V1.0 清理 TD-001 | ✅ 已安装 httpx2，warnings 归零 |
| 第 7 项：是否在 V1.0 清理 TD-002 | ✅ 已添加 format="mixed"，warnings 归零 |
| 第 8 项：是否在 V1.0 启动 Worker 进程做端到端验证 | ✅ 已执行 Worker E2E 验证，状态机流转正常 |
| 第 9 项：是否需要为 V1.0 补充前端大纲/交付物页面 | ✅ 已补充 11 个 API 端点的前端页面代码 |

---

## SPEC 0006 大纲与交付物（V0.4 里程碑）

**完成日期：** 2026-07-22  
**切片编号：** SPEC 0006  
**里程碑：** V0.4 大纲与交付物（Word/PPT 生成闭环）  
**决策记录：** [0017-start-spec-0006-outline-and-deliverables.md](decisions/0017-start-spec-0006-outline-and-deliverables.md)  
**SPEC 文档：** [0006-outline-and-deliverables.md](specs/0006-outline-and-deliverables.md)

### 一、切片目标

为已确认执行结果的实验项目生成统一实验大纲候选，用户确认后从同一份已确认大纲渲染 Word 和 PPT 交付物文件，建立"执行结果 → 统一大纲 → Word/PPT 交付物"的完整闭环，推进项目状态到 COMPLETED。

### 二、范围决策

| 决策项 | 选择 | 理由 |
| --- | --- | --- |
| 统一大纲 | Outline 作为 Word/PPT 的唯一中间锚点 | 确保同一份已确认大纲生成两份交付物，不各自从模型临时上下文生成 |
| 章节来源标记 | sections_json 存储每章节 source_type 和 source_ids | 追溯链可从 Word/PPT 章节回溯到 requirement/evidence/dataset/analysis/execution |
| LLM 接入 | 本地规则提供者 `LocalRuleOutlineProvider` | 真实 DeepSeek 推迟到后续切片 |
| Word 渲染 | python-docx 1.2.0 原生 API（复用 SPEC 0002 依赖） | 不引入外部模板引擎 |
| PPT 渲染 | python-pptx 1.0.2 母版驱动 | 不引入外部 PPT 模板引擎 |
| 版本管理 | 每次生成创建新版本，旧版本保留，失败不覆盖成功 | 追溯和回滚能力 |
| STALE 传播 | ExecutionRun 重新执行 → Outline STALE；Outline 编辑/重新确认 → Deliverable STALE | 保持状态一致性 |

### 三、核心变更

#### 新增 owner 模块：outlines

- `server/app/modules/outlines/status.py`：OutlineStatus、DeliverableStatus、DeliverableType、DeliverableVersionStatus、OutlineChangeType、DeliverableChangeType 枚举。
- `server/app/modules/outlines/models.py`：Outline、Deliverable、DeliverableVersion ORM 实体。
- `server/app/modules/outlines/contracts.py`：OutlineSection、UpdateOutlineRequest、各响应 schema。
- `server/app/modules/outlines/service.py`：大纲生成触发、查询、编辑、确认、拒绝、Word/PPT 生成触发、完成项目、STALE 传播、Worker 调用方法。

#### 新增 LLM 提供者

- `server/app/modules/llm/outline_provider.py`：OutlineDraftProvider ABC、LocalRuleOutlineProvider（从 5 个 owner 聚合上下文生成 6 个章节）、FakeOutlineProvider。

#### 新增渲染器基础设施

- `server/app/infrastructure/renderers/word_renderer.py`：WordRenderer（封面、章节、CSV 表格嵌入、PNG 图片嵌入、附录产物索引）。
- `server/app/infrastructure/renderers/ppt_renderer.py`：PptRenderer（标题页、课题与问题、方法与数据、关键图表、主要发现、总结页）。

#### 新增 API 路由

- `server/app/api/routers/outlines.py`：7 个端点（generate、list、detail、update、confirm、reject、word/ppt generate）。
- `server/app/api/routers/deliverables.py`：4 个端点（list、versions、download、complete）。

#### 数据库迁移

- `server/alembic/versions/0006_create_outline_and_deliverable_tables.py`：创建 outlines、deliverables、deliverable_versions 三张表及索引。

#### 扩展现有模块

- `server/app/modules/jobs/status.py`：JobType 新增 GENERATE_OUTLINE、GENERATE_WORD、GENERATE_PPT。
- `server/app/modules/llm/gateway.py`：新增 get_outline_provider() 工厂方法。
- `server/app/core/config.py`：Settings 新增 outline_provider、word_template_path、ppt_template_path、deliverable_max_size_bytes。
- `server/app/modules/execution/service.py`：execute_code_task 新增 STALE 传播到 Outline。
- `server/app/main.py`：注册 outlines 和 deliverables 路由，新增 not_found_codes。
- `server/tests/conftest.py`：注册 Outline、Deliverable、DeliverableVersion ORM 模型。
- `server/worker/handlers.py`：新增 _gather_outline_context（聚合 5 个 owner 上下文）、handle_generate_outline、_gather_execution_artifacts_for_render、handle_generate_word、handle_generate_ppt。

### 四、状态机推进

```
RESULT_CONFIRMED → 生成大纲候选（保持 RESULT_CONFIRMED）
  → 确认大纲 → OUTLINE_CONFIRMED
  → 触发 Word/PPT 生成 → GENERATING
  → 生成完成（Word+PPT 均 SUCCEEDED）→ COMPLETED
```

STALE 传播链：
- ExecutionRun 重新执行 → Outline STALE
- Outline 编辑 → Deliverable STALE
- Outline 重新确认 → 旧 Deliverable STALE

### 五、测试覆盖

新增 4 个测试文件，共 113 个测试：

| 测试文件 | 测试数 | 覆盖内容 |
| --- | --- | --- |
| test_outline_provider.py | 21 | LocalRuleOutlineProvider 章节生成、source_type 标记、空上下文回退、_truncate、FakeOutlineProvider 确定性 |
| test_renderers.py | 18 | WordRenderer（docx 生成、可重开、CSV 表格嵌入、PNG 图片嵌入、附录）、PptRenderer（pptx 生成、可重开、标题页、内容页、图表页、总结页） |
| test_outlines_service.py | 40 | generate_outline、list/get、update（版本递增、STALE 传播）、confirm、reject、generate_word/ppt、下载校验（路径穿越防护）、complete_project、mark_outlines_stale、Worker 方法（版本递增、失败不覆盖成功） |
| test_outlines_api.py | 21 | 11 个 API 端点的成功/失败/状态机路径 |
| test_outline_worker_handlers.py | 13 | handle_generate_outline（成功、缺输入、无执行记录、重新生成 STALE）、handle_generate_word（成功、文件生成、状态推进、多版本）、handle_generate_ppt（成功）、HANDLERS 注册表 |

### 六、实际安装依赖

| 依赖 | 实际安装版本 | 用途 |
| --- | --- | --- |
| python-pptx | 1.0.2 | PPT 生成（从已确认大纲渲染 .pptx 文件） |
| XlsxWriter | 3.2.9 | python-pptx 传递依赖 |

### 七、验收证据

- 后端测试：`python -m pytest` → 569 passed, 21 warnings（原 456 + 新增 113）
- 数据库迁移：`python -m alembic upgrade head` → 成功迁移到 0006，创建 3 张表
- 前端类型检查：`npm run lint` → tsc --noEmit 通过
- 前端构建：`npm run build` → Vite 构建通过，106 模块转换

### 八、非阻断债务

1. **fastapi.testclient httpx 弃用提示**：第三方弃用警告，自 SPEC 0002 起持续保留。
2. **pandas datetime 推断 UserWarning**：自 SPEC 0004 起持续保留。
3. **浏览器点击截图验收未执行**：当前会话未暴露可调用的 in-app Browser 工具，以 API 测试套件（21 个测试覆盖 11 个端点）和 Worker handler 测试（13 个测试）作为替代证据。
4. **outline_provider 字段类型 bug 修复**：LocalRuleOutlineProvider.generate 中 `f"  - {name}（{type}）：样例 {sample}"` 误用 Python 内置 `type` 替代局部变量 `ftype`，已在测试前修复为 `{ftype}`。

### 九、文件变更统计

- **新增文件：** 15 个（outlines 模块 5 + renderers 3 + API 路由 2 + 迁移 1 + provider 1 + 测试 4，不含 __init__）
- **修改文件：** 7 个（jobs/status.py、gateway.py、config.py、execution/service.py、main.py、conftest.py、worker/handlers.py）
- **测试新增：** 113 个（原 456 → 569）

### 十、明确不做的内容

- 不接入真实 DeepSeek API（继续本地规则提供者）
- 不做前端 UI 变更（前端工作台接线推迟到后续切片）
- 不引入外部 Word/PPT 模板引擎
- 不做交付物版本对比（diff）
- 不做大纲自动确认（必须用户手动确认）
- 不做交付物在线预览（只支持下载）

---

## SPEC 0005 受控 Python 执行（V0.3 里程碑第二部分）

**完成日期：** 2026-07-07  
**切片编号：** SPEC 0005  
**里程碑：** V0.3 受控 Python 执行（数据分析与 Python 执行第二部分）  
**决策记录：** [0016-start-spec-0005-controlled-python-execution.md](decisions/0016-start-spec-0005-controlled-python-execution.md)  
**SPEC 文档：** [0005-controlled-python-execution.md](specs/0005-controlled-python-execution.md)

### 一、切片目标

为已确认分析方案的实验项目生成可执行 Python 代码候选，用户编辑确认后在受控环境中执行，保存 stdout、stderr、退出状态、表格和图表产物，建立"代码 → 执行 → 结果"的完整追踪链，推进项目状态到 RESULT_CONFIRMED。

### 二、范围决策

| 决策项 | 选择 | 理由 |
| --- | --- | --- |
| 执行引擎 | subprocess + 临时脚本文件 + AST import 白名单 | V1 最简方案，无需容器或沙箱库 |
| 网络禁用 | AST 黑名单（socket/ssl/http/urllib/requests 等）+ 动态导入拦截 | 用户确认扩展拉黑列表，防止 ssl/http.client 绕过 |
| 内存限制 | psutil 进程树总 RSS 软监控，0.5s 轮询 | 跨平台硬限制 ROI 过低，进程树监控解决 Windows venv launcher 问题 |
| 字段截断 | AnalysisPlan 阶段为唯一截断点 | 用户确认避免双重截断，CodeTask 直接透传 |
| LLM 接入 | 本地规则提供者 `LocalRuleCodeTaskProvider` | 真实 DeepSeek 推迟到后续切片 |
| 产物收集 | 扫描 work_dir 下 .csv 和 .png | 不递归子目录，按名称排序确保稳定 |

### 三、新增文件

| 文件 | 用途 |
| --- | --- |
| `server/app/infrastructure/sandbox/__init__.py` | sandbox 包初始化 |
| `server/app/infrastructure/sandbox/python_executor.py` | 核心执行引擎（AST 校验 + subprocess + psutil 监控） |
| `server/app/modules/execution/__init__.py` | execution 模块初始化 |
| `server/app/modules/execution/models.py` | CodeTask/ExecutionRun/ExecutionArtifact ORM 模型 |
| `server/app/modules/execution/status.py` | 枚举定义 |
| `server/app/modules/execution/contracts.py` | Pydantic 请求/响应合同 |
| `server/app/modules/execution/service.py` | 执行核心服务（500+ 行） |
| `server/app/modules/llm/code_task_provider.py` | 代码任务提供者（LocalRule + Fake） |
| `server/alembic/versions/0005_create_execution_tables.py` | Alembic 迁移（3 表 + 6 索引） |
| `server/app/api/routers/code_tasks.py` | 代码任务 API（7 端点） |
| `server/app/api/routers/execution_runs.py` | 执行记录 API（4 端点） |
| `server/tests/conftest.py` | 测试全局 ORM 模型注册 |
| `server/tests/test_python_executor.py` | 执行引擎单元测试（48 个） |
| `server/tests/test_execution_api.py` | 执行 API 测试（33 个） |

### 四、修改文件

| 文件 | 变更 |
| --- | --- |
| `server/app/core/config.py` | 新增 execution_timeout_seconds、execution_memory_limit_mb、execution_output_max_bytes、code_task_provider 配置项 |
| `server/app/modules/jobs/status.py` | 新增 GENERATE_CODE_TASK、EXECUTE_CODE_TASK 枚举值 |
| `server/app/modules/llm/gateway.py` | 新增 get_code_task_provider() 工厂方法 |
| `server/app/modules/analysis/service.py` | confirm_analysis_plan 新增 STALE 传播到 CodeTask |
| `server/worker/handlers.py` | 新增 handle_generate_code_task、handle_execute_code_task |
| `server/alembic/env.py` | 导入 execution ORM 模型 |
| `server/app/main.py` | 注册 code_tasks/execution_runs 路由，扩展错误码映射 |

### 五、状态机

```
CodeTask: CANDIDATE → CONFIRMED / REJECTED
         CONFIRMED 编辑 → CANDIDATE（code_version 递增）
         AnalysisPlan 重新确认 → STALE

ExecutionRun: PENDING → RUNNING → SUCCEEDED / FAILED
              CodeTask 编辑 → STALE

Project: ANALYSIS_CONFIRMED → EXECUTING → RESULT_CONFIRMED
                            → EXECUTION_FAILED（可重试）
```

### 六、受控执行环境安全限制

- **import 白名单**：pandas、numpy、matplotlib、scipy、sklearn、openpyxl
- **import 黑名单**：socket、ssl、http、http.client、http.server、urllib、requests、telnetlib、smtplib、poplib、ftplib、imaplib、nntplib、socketserver、xmlrpc、webbrowser、asyncore、asynchat、os、sys、subprocess、shutil、ctypes、signal、select、resource、fcntl、pathlib、io、multiprocessing、threading、asyncio、concurrent、pickle、email
- **动态导入拦截**：`__import__()` 调用 + `importlib.import_module()` 调用
- **资源限制**：限时 30s（硬限制）、限输出 10MB（截断+标记）、限内存 1024MB（psutil 进程树 0.5s 轮询软监控）
- **错误码**：EXECUTION_IMPORT_FORBIDDEN、EXECUTION_TIMEOUT、EXECUTION_MEMORY_LIMIT、EXECUTION_OUTPUT_TOO_LARGE、EXECUTION_SCRIPT_ERROR

### 七、验收结果

- 后端测试：456 passed（原 375 + 新增 81）
- 数据库迁移：0004 → 0005 成功
- 前端类型检查：通过
- 前端构建：通过（106 模块，347.19 kB）
- API 测试：33 个测试覆盖 11 个端点
- 执行引擎测试：48 个测试覆盖安全限制、超时、内存、产物收集

---

## SPEC 0004 数据集工作区（V0.3 里程碑第一部分）

**完成日期：** 2026-07-06  
**切片编号：** SPEC 0004  
**里程碑：** V0.3 数据集工作区（数据分析与 Python 执行第一部分）  
**决策记录：** [0015-start-spec-0004-dataset-workspace.md](decisions/0015-start-spec-0004-dataset-workspace.md)  
**SPEC 文档：** [0004-dataset-workspace.md](specs/0004-dataset-workspace.md)

### 一、切片目标

让用户为已确认证据的实验项目上传 CSV/Excel 数据集或登记公开 URL，由 Worker 异步解析生成字段概览与质量评分，通过本地规则提供者生成清洗、分析、可视化三类方案候选，用户确认方案后建立"数据 → 方案 → 执行 → 结果"的追踪链入口。

本切片是 V0.3 里程碑第一部分，只覆盖数据集工作区，不引入 Python 执行（推迟到 SPEC 0005）。

### 二、范围决策

| 决策项 | 选择 | 理由 |
| --- | --- | --- |
| 数据解析依赖 | pandas + numpy + openpyxl | 复核版本已在 dependency-review.md §6 确认 |
| LLM 接入方式 | 继续本地规则提供者 `LocalRuleAnalysisPlanProvider` | 真实 DeepSeek 推迟到后续切片 |
| URL 下载方式 | API 层同步下载（复用 SPEC 0003 `fetch_url`） | URL 错误直接返回用户，与 sources PDF 上传模式一致 |
| 字段过多处理 | 字段数 > 50 截断到前 20 | 避免方案爆炸，保留主要字段 |
| 工作表选择 | 默认解析第一个工作表 | SPEC 范围限制，工作表选择推迟到后续切片 |
| 自动触发 vs 显式触发 | Worker 解析成功后自动触发 GENERATE_ANALYSIS_PLAN，但状态推进仅在 DATASET_READY 时生效 | 避免在 EVIDENCE_CONFIRMED 状态下错误推进 |

### 三、核心变更

#### 3.1 后端新增核心 owner 模块

**数据集核心**（`server/app/modules/datasets/`）：
- `status.py`：4 个枚举（DatasetKind、DatasetStatus、DatasetVersionStatus、DatasetChangeType）
- `contracts.py`：7 个 Pydantic 合同（DatasetUploadRequest、DatasetUrlRequest、DatasetResponse、DatasetListResponse、DatasetVersionResponse、DatasetVersionListResponse、CompleteDatasetsResponse）
- `models.py`：2 个 ORM 模型（Dataset、DatasetVersion）
- `service.py`：完整服务层，含文件/URL 登记、版本管理、查询、软删除、完成收集、Worker 调用方法（mark_dataset_parsing/parsed/failed、trigger_analysis_plan_generation）、STALE 传播（_mark_analysis_stale）

**分析方案核心**（`server/app/modules/analysis/`）：
- `status.py`：2 个枚举（AnalysisPlanStatus、AnalysisChangeType）
- `contracts.py`：4 个 Pydantic 合同（UpdateAnalysisPlanRequest、AnalysisPlanResponse、AnalysisPlanListResponse、CompleteAnalysisResponse）
- `models.py`：1 个 ORM 模型（AnalysisPlan）
- `service.py`：完整服务层，含生成、列表、查询、更新（CONFIRMED 编辑回到 CANDIDATE）、确认、拒绝、完成、save_analysis_plan_draft（旧 CANDIDATE 变 STALE）、advance_project_to_planned（幂等，仅在 DATASET_READY 推进）

#### 3.2 后端新增基础设施适配器

**数据集解析器**（`server/app/infrastructure/parsers/dataset_parser.py`）：
- `FieldProfile` dataclass：字段名、推断类型（int/float/string/datetime/bool）、非空数、缺失数、缺失率、唯一值数、样例值、数值统计（min/max/mean/median/std/q1/q3）、字符串 top_values
- `DatasetProfile` dataclass：行数、列数、完整行数、缺失行数、重复行数、字段概览列表、quality_score（0-100）
- `DatasetParseResult` dataclass：profile + raw_dataframe
- `DatasetParseError` 异常：code（DATASET_EMPTY/DATASET_PARSE_FAILED/DATASET_TOO_LARGE）
- `parse_dataset` 函数：CSV/Excel 解析、字段类型推断、数值统计、top_values、质量评分
- `profile_to_dict` / `profile_from_dict`：序列化辅助

#### 3.3 LLM 网关扩展

- `server/app/modules/llm/analysis_plan_provider.py`：
  - `AnalysisPlanDraft` dataclass：cleaning_plan、analysis_plan、chart_plan
  - `AnalysisPlanDraftProvider` ABC
  - `LocalRuleAnalysisPlanProvider`：按字段类型生成方案，字段数 > 50 截断到前 20
  - `FakeAnalysisPlanProvider`：测试用确定性提供者
- `server/app/modules/llm/gateway.py`：新增 `get_analysis_plan_provider()` 工厂方法

#### 3.4 Worker handler 扩展

`server/worker/handlers.py` 新增：
- `handle_parse_dataset`：解析数据集 → mark_dataset_parsed → 自动触发 GENERATE_ANALYSIS_PLAN
- `handle_generate_analysis_plan`：反序列化 profile → 调用 provider → save_analysis_plan_draft → advance_project_to_planned
- HANDLERS 映射新增 PARSE_DATASET、GENERATE_ANALYSIS_PLAN，共 5 个 handler

#### 3.5 API 路由层（15 个新端点）

**数据集 API**（`server/app/api/routers/datasets.py`）：
- POST `/api/projects/{project_id}/datasets/upload` - 上传 CSV/Excel 文件
- POST `/api/projects/{project_id}/datasets/url` - 登记 CSV/Excel 公开 URL
- GET `/api/projects/{project_id}/datasets` - 数据集列表
- GET `/api/projects/{project_id}/datasets/{dataset_id}` - 数据集详情
- GET `/api/projects/{project_id}/datasets/{dataset_id}/versions` - 版本列表
- DELETE `/api/projects/{project_id}/datasets/{dataset_id}` - 软删除
- POST `/api/projects/{project_id}/datasets/{dataset_id}/reupload` - 重新上传（创建新版本）
- POST `/api/projects/{project_id}/datasets/complete` - 完成数据集收集

**分析方案 API**（`server/app/api/routers/analysis.py`）：
- POST `/api/projects/{project_id}/datasets/{dataset_id}/analysis/generate` - 触发生成
- GET `/api/projects/{project_id}/analysis` - 列表（支持 dataset_id 和 status 过滤）
- GET `/api/projects/{project_id}/analysis/{plan_id}` - 详情
- PUT `/api/projects/{project_id}/analysis/{plan_id}` - 编辑
- POST `/api/projects/{project_id}/analysis/{plan_id}/confirm` - 确认
- POST `/api/projects/{project_id}/analysis/{plan_id}/reject` - 拒绝
- POST `/api/projects/{project_id}/analysis/complete` - 完成方案确认

#### 3.6 数据库迁移

迁移文件 `server/alembic/versions/0004_create_datasets_and_analysis_tables.py`（revision=`0004`，down_revision=`0003`）：
- 3 张表：datasets、dataset_versions、analysis_plans
- 5 个索引：ix_datasets_project_id、ix_dataset_versions_dataset_id、ix_dataset_versions_project_id、ix_analysis_plans_project_id、ix_analysis_plans_dataset_id

#### 3.7 前端工作台

**datasets 模块**（`apps/web/src/features/datasets/`）：
- `types.ts`：Dataset、DatasetKind、DatasetStatus、DatasetVersionStatus、DatasetVersion、DatasetProfile、FieldProfile、CompleteDatasetsResponse
- `api.ts`：8 个 API 函数（uploadDataset、createUrlDataset、listDatasets、getDataset、listDatasetVersions、deleteDataset、reuploadDataset、completeDatasets）
- `hooks.ts`：8 个 TanStack Query hooks

**analysis 模块**（`apps/web/src/features/analysis/`）：
- `types.ts`：AnalysisPlan、AnalysisPlanStatus、UpdateAnalysisPlanRequest、AnalysisPlanListResponse、CompleteAnalysisResponse
- `api.ts`：7 个 API 函数（generateAnalysisPlan、listAnalysisPlans、getAnalysisPlan、updateAnalysisPlan、confirmAnalysisPlan、rejectAnalysisPlan、completeAnalysis）
- `hooks.ts`：6 个 TanStack Query hooks

**工作台视图**：
- `apps/web/src/routes/DatasetWorkspaceView.tsx`：数据集列表、CSV/Excel 上传、URL 登记、版本列表、字段概览、质量概览、删除、重新上传、完成收集
- `apps/web/src/routes/AnalysisWorkspaceView.tsx`：数据集选择、方案列表、详情三栏（清洗/分析/图表）、编辑/确认/拒绝、STALE 标记、完成确认

**路由注册**（`apps/web/src/app/App.tsx`）：
- `/projects/:projectId/datasets` → DatasetWorkspaceView
- `/projects/:projectId/analysis` → AnalysisWorkspaceView

**项目详情页**（`apps/web/src/routes/ProjectDetailView.tsx`）：
- 新增 DATASET_READY、ANALYSIS_PLANNED、ANALYSIS_CONFIRMED 状态中文展示
- 当项目状态为 DATASET_READY 或之后时显示数据集和分析工作台入口链接

**jobs 类型扩展**（`apps/web/src/features/jobs/types.ts`）：
- JobType 联合类型新增 PARSE_DATASET、GENERATE_ANALYSIS_PLAN
- 新增 GenerateAnalysisResponse 接口

#### 3.8 配置扩展

`server/app/core/config.py` 新增 2 个 Settings properties：
- `dataset_max_size_bytes`（默认 50 MB）
- `analysis_plan_provider`（默认 `local_rule`）

`server/app/main.py` 扩展错误码映射：
- `DATASET_NOT_FOUND`、`DATASET_VERSION_NOT_FOUND`、`ANALYSIS_PLAN_NOT_FOUND` → 404
- `DATASET_ACCESS_RESTRICTED` → 403
- `DATASET_FILE_TOO_LARGE` → 413

### 四、状态机推进

```text
DRAFT
  → REQUIREMENT_PARSED（SPEC 0002）
  → REQUIREMENT_CONFIRMED（SPEC 0002）
  → SOURCES_COLLECTED（SPEC 0003）
  → EVIDENCE_CONFIRMED（SPEC 0003）
  → DATASET_READY（SPEC 0004 新增：至少一个 Dataset.status=READY）
  → ANALYSIS_PLANNED（SPEC 0004 新增：AnalysisPlan 生成成功，仅在 DATASET_READY 推进）
  → ANALYSIS_CONFIRMED（SPEC 0004 新增：用户确认至少一个 AnalysisPlan）
  → [后续切片：受控 Python 执行]
```

### 五、错误码与结构化拒绝

新增错误码（部分）：

| 错误码 | HTTP 状态码 | 触发条件 |
| --- | --- | --- |
| PROJECT_EVIDENCE_NOT_CONFIRMED | 400 | 项目证据未确认，无法登记数据集 |
| DATASET_URL_REQUIRED | 400 | URL 为空 |
| DATASET_URL_INVALID | 400 | URL 格式不正确 |
| DATASET_URL_SCHEME_UNSUPPORTED | 400 | 非 http/https 协议 |
| DATASET_URL_NOT_PUBLIC | 400 | localhost、127.0.0.1、私有 IP 段 |
| DATASET_FILE_UNSUPPORTED | 400 | 仅支持 CSV 和 XLSX |
| DATASET_FILE_EMPTY | 400 | 上传文件为空 |
| DATASET_FILE_TOO_LARGE | 413 | 文件超过 50 MB |
| DATASET_NOT_FOUND | 404 | 数据集不存在或不属于该项目 |
| DATASET_VERSION_NOT_FOUND | 404 | 数据集版本不存在 |
| DATASET_EMPTY | 400 | 数据集无数据行 |
| DATASET_PARSE_FAILED | 400 | 数据集解析失败 |
| DATASET_TOO_LARGE | 400 | 数据集超过解析上限 |
| DATASET_ACCESS_RESTRICTED | 403 | URL 需要登录或付费 |
| DATASET_NOT_PARSED | 400 | 数据集未解析，无法生成分析方案 |
| ANALYSIS_PLAN_NOT_FOUND | 404 | 分析方案不存在 |
| ANALYSIS_PLAN_NOT_EDITABLE | 400 | 只能修改候选或过期方案 |
| ANALYSIS_PLAN_NOT_CONFIRMABLE | 400 | 只能确认候选方案 |
| PROJECT_NO_READY_DATASET | 400 | 没有已就绪的数据集 |
| PROJECT_NO_CONFIRMED_ANALYSIS_PLAN | 400 | 没有已确认的分析方案 |

### 六、STALE 传播机制

- **数据集重新上传**（reupload）：旧版本变 SUPERSEDED，关联 AnalysisPlan（CANDIDATE/CONFIRMED/REJECTED）全部变 STALE
- **数据集软删除**：关联 AnalysisPlan 全部变 STALE
- **同版本重新生成方案**：旧 CANDIDATE 变 STALE，避免候选累积
- **STALE 方案幂等**：已是 STALE 的方案保持 STALE，不重复标记
- **项目状态不回退**：reupload 后即使关联方案变 STALE，project.status 保持 ANALYSIS_CONFIRMED（需用户重新确认）

### 七、测试覆盖

新增 7 个测试文件（6 个新建 + 1 个扩展），共 222 个测试用例：

| 测试文件 | 测试数 | 覆盖范围 |
| --- | --- | --- |
| test_datasets_service.py | 49 | 文件/URL 登记、版本管理、查询、软删除、STALE 传播、完成收集、Worker helpers |
| test_datasets_api.py | 33 | 8 个 API 端点成功与失败路径 |
| test_analysis_service.py | 33 | 方案生成、列表、更新、确认、拒绝、完成、save_draft、状态推进 |
| test_analysis_api.py | 26 | 7 个 API 端点 |
| test_dataset_parser.py | 29 | CSV/Excel 解析、字段类型推断、统计、top_values、序列化往返、错误分支 |
| test_analysis_plan_provider.py | 31 | LocalRule 生成、字段截断、Fake 提供者、数据结构 |
| test_worker_handlers.py（扩展） | 36（原 15 + 新增 21） | PARSE_DATASET、GENERATE_ANALYSIS_PLAN handler 成功/失败/状态推进 |

加上原 SPEC 0001/0002/0003 的 153 个测试，总计 **375 个测试全部通过**。

覆盖率（基于 sys.settrace 测量）：

| 模块 | 覆盖率 |
| --- | --- |
| datasets/service.py | 83.2% |
| analysis/service.py | 85.3% |
| dataset_parser.py | 88.4% |
| analysis_plan_provider.py | 81.6% |
| contracts/models/status | 100.0% |
| **总计** | **86.2%** |

### 八、验收证据

| 验收项 | 命令 | 结果 |
| --- | --- | --- |
| 后端测试 | `pytest server/tests` | 375 passed, 21 warnings |
| 数据库迁移 | `alembic upgrade head`（全新临时 SQLite） | 0001 → 0002 → 0003 → 0004 全部成功 |
| 前端类型检查 | `npm run lint` | TypeScript 严格类型检查通过 |
| 前端构建 | `npm run build` | Vite 构建通过，106 模块，347.19 kB |
| API 端点注册 | OpenAPI schema 验证 | 15 个新端点全部注册（8 datasets + 7 analysis） |
| Worker handler 注册 | HANDLERS 映射验证 | 5 个 handler 全部注册 |
| 端到端主链路 | curl 顺序调用 11 步 | EVIDENCE_CONFIRMED → DATASET_READY → ANALYSIS_PLANNED → ANALYSIS_CONFIRMED 全链路跑通 |
| 错误分支验证 | 6 个错误分支 curl | PROJECT_EVIDENCE_NOT_CONFIRMED、DATASET_FILE_UNSUPPORTED、ANALYSIS_PLAN_NOT_FOUND、ANALYSIS_PLAN_NOT_CONFIRMABLE、DATASET_NOT_FOUND、PROJECT_NOT_FOUND 全部正确返回 |
| STALE 传播 | reupload + 查询方案 | 旧 CONFIRMED 变 STALE，已 STALE 保持，新方案 CANDIDATE，项目状态不回退 |
| 浏览器点击验收 | （未执行） | 当前会话无 in-app Browser 工具，用 curl 端到端作为替代证据 |

### 九、实际安装依赖

| 依赖 | 复核版本 | 实际安装版本 | 用途 |
| --- | --- | --- | --- |
| pandas | 3.0.3 | 3.0.3 | 表格数据处理与字段类型推断 |
| numpy | 2.4.6 | 2.5.1 | 数值计算（pandas 3.0.3 传递依赖升级，无破坏性变更） |
| openpyxl | 3.1.5 | 3.1.5 | Excel 读取 |

### 十、非阻断债务

1. **fastapi.testclient httpx 弃用提示**：第三方 `starlette.testclient` 对 `httpx` 的弃用警告，SPEC 0002 已记录，继续保留。
2. **pandas datetime 推断 UserWarning**：`dataset_parser.py:96` 在推断字符串字段是否为 datetime 时触发 `UserWarning: Could not infer format`，因字符串列无法推断统一格式而回退逐元素解析。最终推断类型为 string（正确），不影响功能，但日志噪音值得后续清理（可在推断时用 `warnings.catch_warnings()` 抑制）。新增非阻断债务。
3. **浏览器点击截图验收未执行**：当前会话未暴露可调用的 in-app Browser 工具，已用 curl 端到端验证、6 个错误分支、STALE 传播作为替代证据。
4. **样例 xlsx 首 sheet 为封面表**：`胃病数据集_教学实验版.xlsx` 第一个工作表是元数据/封面表（9 行 2 列），实际 600 行数据在 `胃病数据` sheet。Parser 按 SPEC "默认解析第一个工作表" 行为正确执行，但解析的是封面而非实际数据。这不是实现 bug，是 SPEC 范围限制。真实演示需要选用首 sheet 即数据的文件，或在后续 SPEC 支持工作表选择。
5. **Worker 启动命令文档**：正确命令是 `python -m worker.main`（worker 包无 `__main__.py`），`commands.md` §7 中规划的 `python -m worker` 需在后续文档更新中修正。

### 十一、文件变更统计

- **新增文件：** 22 个（后端 17 + 前端 8 + 文档 3 + 测试 7 - 部分重叠）
- **修改文件：** 9 个（后端 6 + 前端 3）
- **测试新增：** 222 个（原 153 → 375）

### 十二、明确不做的内容

- 不引入 `scipy`、`scikit-learn`、`matplotlib`（推迟到 SPEC 0005 Python 执行切片）
- 不接入真实 DeepSeek API（继续本地规则提供者）
- 不执行 Python 代码（只生成方案候选）
- 不生成图表（只生成图表方案描述）
- 不生成 Word/PPT 大纲
- 不做数据脱敏或匿名化
- 不支持数据库直连导入
- 不做数据版本对比（diff）
- 不做自动化数据清洗（只生成建议）
- 不支持工作表选择（默认第一个）
- 不做数据预览或行级编辑
- 不做 L3 完整论文复现
- 不提供医疗诊断或治疗建议

### 十三、设计观察（非阻断）

1. **自动触发与显式触发的"双重方案"行为**：Worker 解析成功后自动触发 GENERATE_ANALYSIS_PLAN，但此时 project 还在 EVIDENCE_CONFIRMED，`advance_project_to_planned` 是 no-op，生成的 CANDIDATE 方案"悬空"。当用户调用 `/datasets/complete` 再调用 `/analysis/generate` 显式触发时，旧 CANDIDATE 变 STALE，生成新 CANDIDATE 并推进状态。这导致每个数据集通常会留下 1 个无用的 STALE 方案。这是 SPEC 自动触发设计 + 状态机推进条件的副作用，不是 bug，可在后续切片考虑只在 status≥DATASET_READY 时自动触发。

---

## SPEC 0003 公开资料与证据工作流（V0.2 里程碑）

**完成日期：** 2026-07-06  
**Commit：** `ba683db 完成 SPEC 0003 公开资料与证据工作流`  
**切片编号：** SPEC 0003  
**里程碑：** V0.2 公开资料与证据工作流  
**决策记录：** [0014-start-spec-0003-sources-and-evidence.md](decisions/0014-start-spec-0003-sources-and-evidence.md)  
**SPEC 文档：** [0003-sources-and-evidence-workflow.md](specs/0003-sources-and-evidence-workflow.md)

### 一、切片目标

让用户为已确认要求的实验项目登记公开 URL 和 PDF 辅助文件，通过独立 Worker 异步完成采集与解析，生成可审阅、可确认的证据卡片，并保存完整的来源位置和采集状态，建立"资料事实有来源"的核心追踪链入口。

### 二、范围决策

在 SPEC 编写阶段通过 AskUserQuestion 确认了 4 个关键范围决策：

| 决策项 | 选择 | 理由 |
| --- | --- | --- |
| Worker 引入 | 引入最小 Worker（数据库任务表 + 轮询） | 不引入 Celery/RQ/Redis 等额外组件，保持 V1 简单 |
| LLM 接入方式 | 继续本地规则提供者 | 真实 DeepSeek 推迟到后续切片 |
| 文件格式支持 | PDF + HTML 网页 | Word/TXT/CSV/Excel 推迟到数据集工作流切片 |
| Playwright | 不引入 | 动态网页检测后建议用户手动上传 PDF |

### 三、核心变更

#### 3.1 后端新增核心 owner 模块

**来源与证据核心**（`server/app/modules/sources/`）：
- `status.py`：定义 6 个枚举（SourceKind、SourceStatus、EvidenceType、EvidenceCardStatus、CandidateSource、SourceChangeType）
- `contracts.py`：7 个 Pydantic 合同（UrlSourceRequest、UpdateEvidenceCardRequest、SourceResponse、SourceListResponse、ParsedDocumentResponse、EvidenceCardResponse、EvidenceCardListResponse）
- `models.py`：3 个 ORM 模型（Source、ParsedDocument、EvidenceCard）
- `service.py`：来源登记（URL + PDF）、来源查询、来源软删除、完成来源收集、证据卡片生成/列表/更新/确认/拒绝/完成、Worker 调用方法（mark_source_fetched、mark_source_failed、mark_source_parsed、create_parsed_document、save_evidence_card_drafts）

**后台任务核心**（`server/app/modules/jobs/`）：
- `status.py`：JobType（FETCH_URL、PARSE_DOCUMENT、GENERATE_EVIDENCE）、JobStatus（PENDING、RUNNING、SUCCEEDED、FAILED、CANCELLED）
- `contracts.py`：JobResponse、JobListResponse
- `models.py`：BackgroundJob ORM 模型（retry_count default=0、max_retries default=2）
- `service.py`：create_job、claim_pending_job（原子性领取）、mark_running、mark_succeeded、mark_failed（重试逻辑）、get_job、list_jobs

#### 3.2 后端新增基础设施适配器

**HTTP 采集适配器**（`server/app/infrastructure/fetchers/http_fetcher.py`）：
- FetchResult dataclass（content、content_type、status_code、url）
- FetchError 异常（code、message）
- fetch_url 函数：超时 30s、大小上限 10MB、401/403/登录表单检测

**文档解析适配器**（`server/app/infrastructure/parsers/`）：
- `html_parser.py`：parse_html（用 BeautifulSoup + lxml 提取 title、text、metadata）、detect_dynamic_page
- `pdf_parser.py`：parse_pdf（用 pypdf 提取文本和页数）

#### 3.3 LLM 网关扩展

- `server/app/modules/llm/evidence_card_provider.py`：EvidenceCardDraftProvider ABC、LocalRuleEvidenceCardProvider（按段落和关键词分类，最多 10 张）、FakeEvidenceCardProvider（固定 3 张确定性候选）
- `server/app/modules/llm/gateway.py`：新增 get_evidence_card_provider() 工厂方法

#### 3.4 独立 Worker 进程

- `server/worker/handlers.py`：handle_fetch_url、handle_parse_document、handle_generate_evidence 三个处理器 + HANDLERS 映射
- `server/worker/main.py`：Worker 主循环（claim_pending_job → 调用 handler → mark_succeeded/mark_failed）

#### 3.5 API 路由层（14 个新端点）

**来源 API**（`server/app/api/routers/sources.py`）：
- POST `/api/projects/{project_id}/sources/url` - 登记 URL 来源
- POST `/api/projects/{project_id}/sources/pdf` - 上传 PDF 文件
- GET `/api/projects/{project_id}/sources` - 来源列表
- GET `/api/projects/{project_id}/sources/{source_id}` - 来源详情
- DELETE `/api/projects/{project_id}/sources/{source_id}` - 软删除来源
- POST `/api/projects/{project_id}/sources/complete` - 完成来源收集

**证据卡片 API**（`server/app/api/routers/evidence.py`）：
- POST `/api/projects/{project_id}/sources/{source_id}/evidence/generate` - 触发生成
- GET `/api/projects/{project_id}/evidence` - 列表（支持 source_id 和 status 过滤）
- PUT `/api/projects/{project_id}/evidence/{card_id}` - 更新
- POST `/api/projects/{project_id}/evidence/{card_id}/confirm` - 确认
- POST `/api/projects/{project_id}/evidence/{card_id}/reject` - 拒绝
- POST `/api/projects/{project_id}/evidence/complete` - 完成证据确认

**任务 API**（`server/app/api/routers/jobs.py`）：
- GET `/api/projects/{project_id}/jobs/{job_id}` - 任务详情
- GET `/api/projects/{project_id}/jobs` - 任务列表

#### 3.6 数据库迁移

迁移文件 `server/alembic/versions/0003_create_sources_and_jobs_tables.py`（revision=`0003`，down_revision=`0002`）：
- 4 张表：sources、parsed_documents、evidence_cards、background_jobs
- 6 个索引：ix_sources_project_id、ix_sources_status、ix_parsed_documents_source_id、ix_evidence_cards_project_id、ix_evidence_cards_source_id、ix_background_jobs_status

#### 3.7 前端工作台

**sources 模块**（`apps/web/src/features/sources/`）：
- `types.ts`：Source、SourceKind、SourceStatus、ParsedDocument、SourceListResponse、CompleteSourcesResponse
- `api.ts`：createUrlSource、createPdfSource、listSources、getSource、deleteSource、completeSources
- `hooks.ts`：useSources、useSource、useCreateUrlSource、useCreatePdfSource、useDeleteSource、useCompleteSources

**evidence 模块**（`apps/web/src/features/evidence/`）：
- `types.ts`：EvidenceCard、EvidenceType、EvidenceCardStatus、CandidateSource、UpdateEvidenceCardRequest、CompleteEvidenceResponse
- `api.ts`：generateEvidence、listEvidence、updateEvidence、confirmEvidence、rejectEvidence、completeEvidence
- `hooks.ts`：useEvidenceCards、useGenerateEvidence、useUpdateEvidence、useConfirmEvidence、useRejectEvidence、useCompleteEvidence

**jobs 模块**（`apps/web/src/features/jobs/`）：
- `types.ts`：BackgroundJob、JobType、JobStatus、JobListResponse、GenerateEvidenceResponse
- `api.ts`：fetchJob、listJobs
- `hooks.ts`：useJob（带 refetchInterval 仅在 PENDING/RUNNING 时 2 秒轮询）、useJobs

**工作台视图**：
- `apps/web/src/routes/SourcesWorkspaceView.tsx`：URL 登记表单、PDF 上传、来源列表、状态展示、任务进度轮询、删除按钮、完成收集按钮
- `apps/web/src/routes/EvidenceWorkspaceView.tsx`：生成候选、状态筛选、卡片列表、编辑表单、确认/拒绝按钮、STALE 标记、完成确认按钮

**路由注册**（`apps/web/src/app/App.tsx`）：
- `/projects/:projectId/sources` → SourcesWorkspaceView
- `/projects/:projectId/evidence` → EvidenceWorkspaceView

**项目详情页**（`apps/web/src/routes/ProjectDetailView.tsx`）：
- 当项目状态为 REQUIREMENT_CONFIRMED 或之后时显示来源工作台和证据工作台入口链接

#### 3.8 配置扩展

`server/app/core/config.py` 新增 6 个 Settings properties：
- source_fetch_timeout_seconds（默认 30）
- source_fetch_max_size_bytes（默认 10MB）
- job_max_retries（默认 2）
- job_retry_backoff_seconds（默认 5）
- worker_poll_interval_seconds（默认 2）
- evidence_card_provider（默认 local_rule）

### 四、状态机推进

```text
DRAFT
  → REQUIREMENT_PARSED（SPEC 0002）
  → REQUIREMENT_CONFIRMED（SPEC 0002）
  → SOURCES_COLLECTED（SPEC 0003 新增：至少一个来源 status=PARSED）
  → EVIDENCE_CONFIRMED（SPEC 0003 新增：至少一张证据卡片 status=CONFIRMED）
  → [后续切片：DATASET_READY、ANALYSIS_PLANNED、...]
```

### 五、错误码与结构化拒绝

| 错误码 | HTTP 状态码 | 触发条件 |
| --- | --- | --- |
| PROJECT_REQUIREMENT_NOT_CONFIRMED | 400 | 项目状态未达 REQUIREMENT_CONFIRMED |
| SOURCE_URL_REQUIRED | 400 | URL 为空 |
| SOURCE_URL_INVALID | 400 | URL 格式不正确 |
| SOURCE_URL_SCHEME_UNSUPPORTED | 400 | 非 http/https 协议（file://、ftp://） |
| SOURCE_URL_NOT_PUBLIC | 400 | localhost、127.0.0.1、私有 IP 段 |
| SOURCE_FILE_EMPTY | 400 | 上传文件为空 |
| SOURCE_FILE_TOO_LARGE | 413 | 文件超过大小上限 |
| SOURCE_NOT_FOUND | 404 | 来源不存在或不属于该项目 |
| SOURCE_ACCESS_RESTRICTED | 403 | 401/403 响应或检测到登录表单 |
| FETCH_TIMEOUT | 400 | 采集超时 |
| FETCH_TOO_LARGE | 400 | 响应体超过大小上限 |
| PROJECT_NO_PARSED_SOURCE | 400 | 完成来源收集时无已解析来源 |
| EVIDENCE_SOURCE_NOT_PARSED | 400 | 来源未解析时触发生成证据卡片 |
| EVIDENCE_CARD_NOT_FOUND | 404 | 证据卡片不存在 |
| PROJECT_NO_CONFIRMED_EVIDENCE | 400 | 完成证据确认时无已确认卡片 |
| JOB_NOT_FOUND | 404 | 任务不存在 |

### 六、STALE 传播机制

- 来源删除（soft delete）时，关联的 CANDIDATE/CONFIRMED/REJECTED 证据卡片全部变为 STALE
- 来源重新采集时，旧证据卡片变为 STALE（需后续切片实现重新采集逻辑）
- STALE 卡片仍可查看，但需用户重新评估

### 七、测试覆盖

新增 8 个测试文件，共 127 个测试用例：

| 测试文件 | 测试数 | 覆盖范围 |
| --- | --- | --- |
| test_sources_service.py | 24 | URL/PDF 来源登记、URL 公开性校验、列表、软删除、STALE 传播、完成收集、Worker helpers |
| test_sources_api.py | 18 | 6 个 API 端点的成功与失败路径（含 404/400） |
| test_evidence_service.py | 17 | 证据卡片生成、列表、更新、确认、拒绝、完成、save_drafts |
| test_evidence_api.py | 15 | 证据卡片 6 个 API 端点 |
| test_worker_handlers.py | 15 | 三个处理器成功/失败路径、错误处理、HANDLERS 注册表 |
| test_jobs_service.py | 13 | create_job、claim_pending_job、mark_succeeded、mark_failed 重试逻辑、list_jobs |
| test_parsers.py | 14 | HTML 解析（标签清理、元数据、动态页面检测）、PDF 解析（文本提取、空文本） |
| test_http_fetcher.py | 11 | fetch_url 成功路径、超时、过大文件、401/403、登录表单检测 |

加上原 SPEC 0001/0002 的 26 个测试，总计 **153 个测试全部通过**。

### 八、验收证据

| 验收项 | 命令 | 结果 |
| --- | --- | --- |
| 后端测试 | `pytest server/tests` | 153 passed, 1 warning |
| 数据库迁移 | `alembic upgrade head`（全新临时 SQLite） | 0001 → 0002 → 0003 全部成功 |
| 前端类型检查 | `npm run lint` | TypeScript 严格类型检查通过 |
| 前端构建 | `npm run build` | Vite 构建通过，dist/ 生成 |
| 端到端主链路 | curl 顺序调用 14 个 API | 项目创建 → EVIDENCE_CONFIRMED 全链路跑通 |
| 非公开 URL 拒绝 | curl POST 非公开 URL | SOURCE_URL_NOT_PUBLIC（400） |
| 受限 URL 拒绝 | curl + Worker 执行 | SOURCE_ACCESS_RESTRICTED（Source.status=FAILED） |
| STALE 传播 | DELETE 来源后查询证据卡片 | 10 张 CANDIDATE 全部变为 STALE |
| 浏览器点击验收 | （未执行） | 当前会话无 in-app Browser 工具，用 curl 端到端作为替代证据 |

### 九、实际安装依赖

| 依赖 | 复核版本 | 实际安装版本 | 用途 |
| --- | --- | --- | --- |
| httpx | 0.28.1 | 0.28.1 | HTTP 采集适配器 |
| pypdf | 6.13.2 | 6.14.2 | PDF 文档解析（小版本升级，无破坏性变更） |
| beautifulsoup4 | 4.15.0 | 4.15.0 | HTML 文档解析 |
| lxml | 6.1.1 | 6.1.1 | beautifulsoup4 解析器（SPEC 0002 已作为传递依赖安装） |

### 十、非阻断债务

1. **fastapi.testclient httpx 弃用提示**：第三方 `starlette.testclient` 对 `httpx` 的弃用警告，SPEC 0002 已记录，继续保留。
2. **浏览器点击截图验收未执行**：当前会话未暴露可调用的 in-app Browser 工具，已用 Vite 页面可访问、`/api` 代理主链路联通、curl 端到端验证作为替代证据。
3. **httpbin.org 外部服务行为差异**：`https://httpbin.org/status/403` 在 curl 中返回 403，但 httpx 实际收到 503（httpbin 前置代理对 Python User-Agent 差异化响应）。这是外部服务行为，与本项目代码无关，已用 `jigsaw.w3.org/HTTP/Basic/` 验证 `SOURCE_ACCESS_RESTRICTED` 路径。

### 十一、文件变更统计

- **新增文件：** 52 个
- **修改文件：** 10 个
- **代码行数：** 8196 行新增，34 行删除
- **Commit：** `ba683db`

### 十二、明确不做的内容

- 不绕过登录、验证码、付费墙或访问控制
- 不自动登录知网等受限平台
- 不使用 Playwright 渲染动态网页
- 不接入真实 DeepSeek API
- 不支持 Word、TXT、CSV、Excel 文件上传
- 不上传或解析样例数据集
- 不生成数据清洗或分析方案
- 不执行 Python 代码
- 不生成 Word/PPT
- 不做 OCR 或扫描件解析
- 不做 L3 完整论文复现
- 不提供医疗诊断或治疗建议

---

## SPEC 0002 实验要求输入与结构化任务单（V0.1 里程碑）

**完成日期：** 2026-06-17  
**Commit：** `14450a6 完成 SPEC 0002 实验要求输入与结构化任务单`  
**详情：** 见 [acceptance.md](acceptance.md) 和 [specs/0002-requirement-input-and-task-plan.md](specs/0002-requirement-input-and-task-plan.md)

---

## SPEC 0001 项目工作区与脚手架（V0.0 里程碑）

**完成日期：** 2026-06-16  
**详情：** 见 [acceptance.md](acceptance.md) 和 [specs/0001-project-workspace-and-scaffold.md](specs/0001-project-workspace-and-scaffold.md)
