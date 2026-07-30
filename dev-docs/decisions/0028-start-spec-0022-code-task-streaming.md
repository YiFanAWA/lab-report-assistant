# 决策 0028：启动 SPEC 0022 代码任务生成流式化切片

> **日期：** 2026-07-27
> **状态：** 已由项目负责人确认收口（2026-07-30）
> **决策人：** 项目负责人

## 背景

V2.3.0 已发布并打 tag v2.3.0（commit `9f7d274` + follow-up `7fccb90`），SPEC 0021 分析方案生成流式化已收口。前 4 个 LLM 生成环节（任务单、证据卡片、大纲、分析方案）均已完成流式化。

项目负责人于 2026-07-27 完成对 SPEC 0022 草案 0.3 的评审，结论为"有条件通过"，要求补齐 10 项关键内容后批准进入实现。草案 0.3 已纳入全部评审反馈（流式展示方案 A、服务端取消语义、错误分层、并发保护、Phase 3 状态复核、SSE 运行环境、可观测性、接口合同、AC 逐条展开、测试场景驱动）。

经架构调研，发现：

- **代码任务生成**（`POST /api/projects/{project_id}/analysis/{plan_id}/code/generate`）走 **Worker 异步模式**（与 SPEC 0021 相同），与 SSE 同步推送语义不兼容。
- **Provider 输入是已确认的 AnalysisPlan**（不跨模块聚合，比大纲简单），无需提取共享方法到 service 层。
- **单个产出**：一次生成一个 `CodeTaskDraft`（含 `code` 字段），LLM 返回单个 JSON，流式处理与 SPEC 0019/0021 完全一致。
- **DeepSeekClient.stream_chat_completion()** 已在 SPEC 0018 实现，**stream-sse.ts** 已在 SPEC 0018 实现，无需新增依赖。
- **CodeTaskDraft** 实际存在于 `code_task_provider.py:L20`，是 dataclass（含 `code: str`）；`DeepSeekCodeTaskResponse` 是 DeepSeek provider 内部校验模型。

## 决策

1. 启动 SPEC 0022 代码任务生成流式化切片，目标版本 v2.4.0。
2. **流式范围仅限代码任务生成**：改造为新增 `POST /analysis/{plan_id}/code/stream-generate` SSE 端点，保留原 Worker 异步端点兼容。多来源批量流式化推迟到 SPEC 0023。
3. **架构选择 SSE 端点绕过 Worker**（复用 SPEC 0018/0019/0020/0021 模式）：后端使用 `fastapi.responses.StreamingResponse` 推送 SSE 事件，前端使用 `fetch + ReadableStream` 解析，不引入 WebSocket / 长轮询。
4. **流式展示方案 A**（评审反馈一）：流式阶段展示模型原始 JSON 输出，done 事件后切换为格式化 code 展示。不引入增量 JSON 解析器，与 SPEC 0018/0019/0020/0021 一致。
5. **降级策略**（复用 SPEC 0018/0019/0020/0021 模式）：首 chunk 前失败降级到 `LocalRuleCodeTaskProvider`（拆分多 chunk 模拟流式）；中途失败保留已生成 chunk + 推送 `error` 事件；中途失败不保存 CodeTask、不写入 LLM 缓存。
6. **服务端取消语义**（评审反馈二）：`Request.is_disconnected()` 检测客户端断开；`asyncio.CancelledError` 静默处理；取消后不得保存 CodeTask、不得推送 done/error。
7. **错误分层**（评审反馈三）：流开始前错误用 HTTP 状态码（404/409/422）；流开始后错误用 SSE `error` 事件；`error` 后不得发送 `done`；`done` 必须是最后一个事件。
8. **并发保护**（评审反馈四）：服务端 `active_streams: dict[plan_id, str]` 内存字典，同一 AnalysisPlan 同一时刻只允许一个活动流式请求，冲突返回 409 `STREAM_ALREADY_ACTIVE`；超时 120s 自动清理。
9. **Phase 3 状态复核**（评审反馈六）：保存前重新校验项目存在、AnalysisPlan 存在、状态仍为 CONFIRMED、`updated_at` 一致、项目状态允许创建代码任务；复核失败不保存。
10. **流式期间分段持有 db session**（复用 SPEC 0019/0020/0021 模式）：Phase 1 校验（持有 db）→ Phase 2 流式生成（关闭 db，不持有连接）→ Phase 3 完成后重新打开 db 保存。避免 SQLite 写锁阻塞其他请求。
11. **SSE 运行环境要求**（评审反馈七）：响应头 `Content-Type: text/event-stream` + `Cache-Control: no-cache` + `Connection: keep-alive` + `X-Accel-Buffering: no`；部署链路验收必须验证 Nginx 代理配置。
12. **可观测性**（评审反馈八）：记录 16 项结构化日志指标（request_id / first_chunk_latency_ms / chunk_count / fallback_used / cancel_reason / saved / code_task_id 等）；不得记录完整代码内容。
13. **缓存策略**：流式与同步共享 SPEC 0014 LLM 缓存。缓存命中时一次性 yield 完整字符串；流式完成后写入缓存；中途失败不写入。
14. **不引入新依赖**：httpx + fetch 原生支持 SSE，无需新增 Python / npm 依赖。
15. **不修改数据库 schema**：流式 chunk 不持久化，无新增 Alembic 迁移。
16. **不破坏原同步端点**：保留 `POST /code/generate`（Worker 异步）不变。
17. **不修改 Worker handler**：`handle_generate_code_task` 保持不变（Provider 输入是已确认 AnalysisPlan，已极简，无需提取共享方法）。
18. **LocalRule 格式校验**（参考 SPEC 0021 收口经验）：新增 `test_local_rule_code_task_provider_format.py`，校验 LocalRule 输出 `CodeTaskDraft.code` 为字符串、可编译为合法 Python、`target_fields` 类型容错。
19. **实施完成后打 tag v2.4.0 并 push 到 origin/master**。
20. **测试先行原则**：先编写后端单元测试（Provider + Service + API + LocalRule 格式），再编写前端测试，最后实现代码并验证。

## 理由

- **复用 SPEC 0018/0019/0020/0021 成熟模式降低风险**：SSE 绕过 Worker 架构已在 SPEC 0018/0019/0020/0021 验证通过（895 后端测试 + 551 前端测试），SPEC 0022 是第五次复用，风险最低。
- **Provider 输入比大纲更简单**：大纲需要从 5 个模块聚合上下文，代码任务只需已确认的 AnalysisPlan，无需提取 `gather_outline_context` 类似的共享方法。
- **单个产出无技术难点**：LLM 返回单个 JSON（含 code 字段），流式处理与 SPEC 0019/0021 完全一致，done 事件返回 `code_task_id` 即可。
- **不破坏 Worker 路径**：保留原 `POST /code/generate` 兼容，Worker handler 零改动，回归风险最低。
- **不引入新依赖**：完全复用 SPEC 0018/0019/0020/0021 已建立的流式基础设施（httpx stream / fetch ReadableStream / stream-sse.ts）。
- **评审反馈全面纳入**：10 项关键内容已全部补齐到草案 0.3，包括流式展示方案 A、服务端取消语义、错误分层、并发保护、Phase 3 状态复核、SSE 运行环境、可观测性、接口合同、AC 逐条展开、测试场景驱动。
- **测试先行**：SPEC 0018/0019/0020/0021 均采用"先写测试合同 → 再实现 → 最后验证"的模式，确保合同清晰、覆盖完整。

## 影响范围

### 范围内（改动文件）

- `server/app/modules/llm/deepseek_code_task_provider.py`：新增 `stream_generate()` 异步生成器方法。
- `server/app/modules/llm/code_task_provider.py`：`CodeTaskDraftProvider` 抽象基类新增 `stream_generate()` 抽象方法；`LocalRuleCodeTaskProvider` 实现 `stream_generate()`（同步生成后拆分多 chunk）；`FakeCodeTaskProvider` 实现 `stream_generate()` 用于测试。
- `server/app/modules/execution/service.py`：新增 `StreamCodeTaskChunkEvent` / `StreamCodeTaskDoneEvent` / `StreamCodeTaskErrorEvent` 类型；新增 `stream_generate_code_task()` 异步生成器方法；新增 `active_streams` 并发保护字典；新增 Phase 3 状态复核逻辑。
- `server/app/api/routers/code_tasks.py`：新增 `POST /analysis/{plan_id}/code/stream-generate` SSE 端点；新增 `_serialize_code_task_sse_event()` 辅助函数；新增流前 HTTP 错误返回（404/409/422）。
- `apps/web/src/features/execution/api.ts`：新增 `streamGenerateCodeTask()` 异步生成器。
- `apps/web/src/features/execution/hooks.ts`：新增 `useStreamGenerateCodeTask()` hook + `StreamCodeTaskState` 接口。
- `apps/web/src/routes/ExecutionWorkspaceView.tsx`：新增流式生成按钮 + 流式展示区（方案 A：streaming 展示原始 JSON，done 后切换 code）+ 取消按钮 + 完成提示 + 错误展示。
- `server/tests/test_deepseek_code_task_provider_stream.py`（新增）：Provider 流式方法测试（不少于 6 个场景）。
- `server/tests/test_code_task_service_stream.py`（新增）：Service 流式方法测试（不少于 12 个场景）。
- `server/tests/test_code_task_stream_api.py`（新增）：API SSE 端点测试（不少于 10 个场景）。
- `server/tests/test_local_rule_code_task_provider_format.py`（新增）：LocalRule 输出格式校验测试（不少于 4 个场景）。
- `apps/web/src/features/execution/__tests__/api-stream.test.ts`（新增）：前端 API 测试（不少于 6 个场景）。
- `apps/web/src/features/execution/__tests__/hooks-stream.test.tsx`（新增）：前端 hook 测试（不少于 7 个场景）。
- `apps/web/src/routes/__tests__/ExecutionWorkspaceView.test.tsx`（扩展）：新增不少于 7 个流式 UI 测试。
- `dev-docs/specs/0022-code-task-streaming.md`（已创建，本切片 SPEC，草案 0.3）。
- `dev-docs/decisions/0028-start-spec-0022-code-task-streaming.md`（本文件）。
- `dev-docs/acceptance.md`：新增 SPEC 0022 收口记录。
- `dev-docs/implementation-plan.md`：同步 SPEC 0022 完成状态。
- `dev-docs/README.md`：真源索引新增 SPEC 0022 和决策 0028。
- `dev-docs/changelog-v2.4.0.md`（新建）：V2.4.0 变更日志。

### 范围外（不改动文件）

- `server/app/modules/sources/**`：来源与证据模块（不动，SPEC 0020 已完成）。
- `server/app/modules/analysis/**`：分析方案模块（不动，SPEC 0021 已完成）。
- `server/app/modules/llm/gateway.py`：Gateway 工厂（不动，复用现有 `get_code_task_provider()`）。
- `server/app/modules/llm/deepseek_outline_provider.py`：大纲 provider（不动）。
- `server/app/modules/llm/deepseek_requirement_provider.py`：任务单 provider（不动）。
- `server/app/modules/llm/deepseek_evidence_provider.py`：证据卡片 provider（不动）。
- `server/app/modules/llm/deepseek_analysis_plan_provider.py`：分析方案 provider（不动）。
- `server/app/infrastructure/llm/llm_cache.py`：LLM 缓存（不动，复用现有 `get` / `set` / `compute_key`）。
- `server/worker/handlers.py`：Worker handler（不动，`handle_generate_code_task` 保持不变）。
- `server/app/infrastructure/database/**`：数据库模型（不动）。
- `server/alembic/versions/**`：迁移文件（不动）。
- `server/app/core/config.py`：配置（不动，无需新增环境变量）。
- `apps/web/src/features/outlines/**`：大纲前端（不动）。
- `apps/web/src/features/evidence/**`：证据卡片前端（不动）。
- `apps/web/src/features/analysis/**`：分析方案前端（不动）。
- `apps/web/src/features/requirements/**`：任务单前端（不动）。
- `apps/web/src/features/jobs/**`：任务轮询前端（不动）。
- `apps/web/src/shared/stream-sse.ts`：SSE 解析工具（不动，复用 SPEC 0018）。
- `package.json` 和 `package-lock.json`：不新增前端依赖。
- `server/pyproject.toml`：不新增后端依赖。

## 验收标准（关键 15 项 + 完整 ~50 项，详见 SPEC 0022 §六）

### 关键验收项（必须逐条通过）

- AC-1：首 chunk 前失败允许降级到 LocalRule
- AC-2：已发送 chunk 后失败不得再降级（保留 partial_text + 推送 error）
- AC-3：中途失败不得保存 CodeTask
- AC-4：JSON 校验失败不得保存 CodeTask
- AC-5：用户取消不得保存 CodeTask
- AC-6：客户端断开不得保存 CodeTask
- AC-7：`done` 必须是成功流的最后一个事件
- AC-8：`error` 后不得发送 `done`
- AC-9：单个请求只能保存一个 CodeTask（并发保护）
- AC-10：保存前重新校验 AnalysisPlan 状态（Phase 3 复核）
- AC-11：原 Worker handler 保持零改动
- AC-12：原 `/code/generate` 端点回归通过
- AC-13：代码执行链路回归通过（`execute_code_task` → `ExecutionRun`）
- AC-14：不产生 Alembic 变更
- AC-15：不引入新依赖

## 后续方向

SPEC 0022 完成后，V2.4 后续 SPEC 待项目负责人规划。已有草案：

- **SPEC 0023**：多来源证据批量流式生成（扩展 SPEC 0020 支持跨来源批量流式生成）。
- **真实 DeepSeek API 端到端验收**：配置 `DEEPSEEK_API_KEY` 后进行真实 LLM 流式验收。
- **TD-009 修复**：按评估结论处理（建议方案 A 文档化，或方案 B 引入 Playwright）。

上述方向均需先编写并确认对应 SPEC，不得直接进入实现。

---

## 实施记录

### 测试先行阶段（2026-07-27 启动）

按测试先行原则，先编写后端测试文件验证合同，再实现代码到绿色阶段：

1. `test_deepseek_code_task_provider_stream.py`（Provider 流式）
2. `test_code_task_service_stream.py`（Service 流式）
3. `test_code_task_stream_api.py`（API SSE 端点）
4. `test_local_rule_code_task_provider_format.py`（LocalRule 格式校验）

预期红色阶段：测试失败，因为 `stream_generate()` 等方法尚未实现。

### 实现阶段（2026-07-28 完成）

按 Provider → Service → API → 前端的顺序实现，每层完成后验证测试通过：

1. **Provider 层**（`code_task_provider.py` + `deepseek_code_task_provider.py`）：抽象基类新增 `stream_generate()`，LocalRule/Fake/DeepSeek 三套实现，新增 `_first_field_name()` 辅助函数兼容 target_fields 为 list/str/None
2. **Service 层**（`execution/service.py`）：`stream_generate_code_task()` 4 阶段生成器（校验→流式→JSON 校验→保存），`StreamCodeTaskChunkEvent/DoneEvent/ErrorEvent` 事件类型，`_is_disconnected()` 辅助函数兼容同步/异步 `request.is_disconnected()`
3. **API 层**（`code_tasks.py` + `main.py`）：`POST /analysis/{plan_id}/code/stream-generate` SSE 端点，`_serialize_code_task_sse_event()` 序列化，`active_streams` 并发保护（409 STREAM_ALREADY_ACTIVE），`_make_conflict_response()` 流前 409 错误
4. **前端**（`api.ts` + `hooks.ts` + `ExecutionWorkspaceView.tsx`）：`streamGenerateCodeTask()` API 函数，`useStreamGenerateCodeTask(projectId)` hook，方案 A UI 改造（流式展示原始 JSON，完成后解析展示代码）

### 验收证据（2026-07-28）

- **后端测试**：975 passed（895 原有 + 80 新增含 SPEC 0022 流式 78 + 回归 2），0 warnings
- **前端测试**：570 passed（551 原有 + 19 新增），lint + build 通过
- **浏览器验收**：6 个关键验证点全部 PASS（流式按钮/原始 JSON 累积/取消按钮/完成提示/列表刷新/CANDIDATE 状态），截图保存至 `dev-docs/e2e-screenshots/spec0022-01-execution-workspace.png` 至 `spec0022-05-task-list.png`
- **收口复核修复 1 项阻断问题**：`LocalRuleCodeTaskProvider._build_analysis_code` 中 FREQUENCY 类型 `target_fields.split()` 在 list 上报错，新增 `_first_field_name()` 辅助函数兼容 list/str/None，新增 2 个回归测试覆盖
- **约束遵守**：不引入新依赖、不修改数据库 schema、复用 stream-sse.ts、保留原 Worker 异步端点兼容、Worker handler 零改动
- **发布说明**：详见 [changelog-v2.4.0.md](../changelog-v2.4.0.md)
