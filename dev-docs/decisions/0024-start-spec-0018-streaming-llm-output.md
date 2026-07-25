# 决策 0024：启动 SPEC 0018 流式 LLM 输出（任务单生成）切片

> **日期：** 2026-07-25
> **状态：** 已实现并由项目负责人确认收口。后端 783 passed（新增 47 测试）+ 前端 468 passed（新增 34 测试）+ lint/build 通过 + alembic 无变化 + 浏览器验收 PASS。已打 tag v2.0.0。
> **决策人：** 项目负责人

## 背景

V1.4.0 已发布并打 tag v1.4.0，SPEC 0017 单用户前端实时编辑反馈已收口。当前活跃可记录债务为 TD-009（非阻断，浏览器验收截图未持久化）。

项目负责人于 2026-07-25 规划 V2.0 阶段方向，明确要求"优先实现流式 LLM 输出功能"。当前任务单生成流程存在体验缺陷：

1. **同步阻塞等待**：用户点击"生成任务单"后，前端同步等待后端 LLM 调用 5-15s，期间 UI 无任何进度反馈。
2. **一次性显示**：LLM 生成完成后整个 JSON 一次性返回，缺乏"AI 正在思考"的实时感。
3. **取消能力缺失**：用户误触发后无法中途取消，必须等待完成或浏览器超时。

经架构调研，发现：

- **任务单生成**（`POST /plans/generate`）是同步 API 直连 LLM，最容易改造为 SSE 流式。
- **大纲生成**（`POST /outline/generate`）走 Worker 异步模式，Worker 是独立进程无法直接推送 SSE 到前端，改造架构风险高。
- **DeepSeekClient** 已支持同步调用 + SPEC 0014 LLM 缓存，新增流式方法可复用现有错误映射和缓存逻辑。
- **httpx** 已支持 `client.stream()`，**fetch + ReadableStream** 原生支持 SSE 解析，无需新增依赖。

## 决策

1. 启动 SPEC 0018 流式 LLM 输出切片，目标版本 v2.0.0。
2. **流式范围仅限任务单生成**：改造 `POST /plans/generate` 为新增 `POST /plans/stream-generate` SSE 端点，保留原同步端点兼容。大纲生成流式化推迟到 V2.1 SPEC 0019。
3. **架构选择 API SSE + Gateway 直调**：后端使用 `fastapi.responses.StreamingResponse` 推送 SSE 事件，前端使用 `fetch + ReadableStream` 解析，不引入 WebSocket / 长轮询基础设施。
4. **降级策略**：首 chunk 前失败降级到 `LocalRuleRequirementDraftProvider`（拆分多 chunk 模拟流式）；中途失败保留已生成 chunk + 推送 `error` 事件；中途失败不保存 RequirementPlan、不写入 LLM 缓存。
5. **流式期间分段持有 db session**：Phase 1 校验（持有 db）→ Phase 2 流式生成（关闭 db，不持有连接）→ Phase 3 完成后重新打开 db 保存。避免 SQLite 写锁阻塞其他请求。
6. **缓存策略**：流式与同步共享 SPEC 0014 LLM 缓存。缓存命中时一次性 yield 完整字符串（前端快速完成）；流式完成后写入缓存；中途失败不写入。
7. **不引入新依赖**：httpx + fetch 原生支持 SSE，无需新增 Python / npm 依赖。
8. **不修改数据库 schema**：流式 chunk 不持久化，无新增 Alembic 迁移。
9. **不破坏原同步端点**：保留 `POST /plans/generate` 不变，新增 `POST /plans/stream-generate` SSE 端点。
10. 浏览器验收使用 browser_use agent 执行，截图保存到 `dev-docs/e2e-screenshots/spec-0018/`（若工具限制则记录为 TD 延续）。
11. 实施完成后打 tag v2.0.0 并 push 到 origin/master。

## 理由

- **范围最小化降低风险**：仅改造任务单生成（同步直连 LLM）为流式，不触碰 Worker 架构、大纲模块、数据库。任务单生成是用户首次接触 LLM 的入口，体验提升最显著。
- **API SSE 单向推送足够**：LLM 流式输出是单向服务器推送，不需要双向通信、心跳、重连。SSE 是 HTML5 标准，浏览器原生支持，与 SPEC 0014 LLM 缓存兼容。
- **不违反 SPEC 0017 范围**：SPEC 0017 §1.3 "不引入 WebSocket/SSE 实时通信基础设施" 指的是"多用户协作的实时双向通信"。本切片的 SSE 是"LLM 流式输出的单向推送"，属于单用户场景，不违反产品边界。
- **降级策略保持业务连贯**：首 chunk 前降级与现有同步路径一致，用户体验连贯；中途失败保留已生成内容让用户看到部分进度，可决定是否重试。
- **分段持有 db 避免 SQLite 锁**：流式期间 db session 大部分时间空闲，长时间持有会阻塞其他请求。分段策略确保写锁只在保存阶段短暂持有。
- **缓存共享提升命中率**：流式与同步共享 LLM 缓存，缓存命中时直接走完整字符串，避免重新调 LLM。
- **保留同步端点兼容**：不破坏 SPEC 0002 锁定的 API 合同，同步端点仍可用于脚本调用、测试等非流式场景。
- **不引入新依赖**：httpx 已支持 stream，fetch 原生支持 ReadableStream，无需新增 Python / npm 依赖，符合 AGENTS.md "新增依赖前必须确认它属于当前已批准切片"原则。

## 影响范围

### 范围内（改动文件）

- `server/app/infrastructure/llm/deepseek_client.py`：新增 `stream_chat_completion()` 生成器方法。
- `server/app/modules/llm/deepseek_requirement_provider.py`：新增 `stream_draft()` 生成器方法。
- `server/app/modules/requirements/service.py`：新增 `StreamChunkEvent` / `StreamDoneEvent` / `StreamErrorEvent` 类型；新增 `stream_generate_plan()` 生成器方法。
- `server/app/api/routers/requirements.py`：新增 `POST /plans/stream-generate` SSE 端点；新增 `_serialize_sse_event()` 辅助函数。
- `apps/web/src/shared/stream-sse.ts`（新建）：通用 SSE 解析工具。
- `apps/web/src/features/requirements/api.ts`：新增 `streamGeneratePlan()` 异步生成器。
- `apps/web/src/features/requirements/hooks.ts`：新增 `useStreamGeneratePlan` hook。
- `apps/web/src/routes/RequirementWorkspaceView.tsx`：新增流式生成按钮 + 流式文本展示 + 取消按钮。
- `server/tests/unit/infrastructure/test_deepseek_client_stream.py`（新增）。
- `server/tests/unit/modules/test_deepseek_requirement_provider_stream.py`（新增）。
- `server/tests/unit/modules/test_requirements_service_stream.py`（新增）。
- `server/tests/unit/api/test_requirements_stream.py`（新增）。
- `apps/web/src/shared/stream-sse.test.ts`（新增）。
- `apps/web/src/features/requirements/hooks.test.tsx`（扩展，新增 ~7 个测试）。
- `dev-docs/specs/0018-streaming-llm-output.md`（新建，本切片 SPEC）。
- `dev-docs/decisions/0024-start-spec-0018-streaming-llm-output.md`（本文件）。
- `dev-docs/acceptance.md`：新增 SPEC 0018 收口记录。
- `dev-docs/implementation-plan.md`：同步 SPEC 0018 完成状态。
- `dev-docs/README.md`：真源索引新增 SPEC 0018 和决策 0024。
- `dev-docs/changelog-v2.0.0.md`（新建）：V2.0.0 变更日志。

### 范围外（不改动文件）

- `server/app/modules/outlines/**`：大纲模块（不动）。
- `server/app/modules/sources/**`：证据卡片（不动）。
- `server/app/modules/analysis/**`：分析方案（不动）。
- `server/app/modules/execution/**`：执行模块（不动）。
- `server/app/modules/llm/gateway.py`：Gateway 工厂（不动，复用现有 `get_provider()`）。
- `server/app/modules/llm/deepseek_outline_provider.py`：大纲 provider（不动）。
- `server/app/modules/llm/deepseek_evidence_provider.py`：证据卡片 provider（不动）。
- `server/app/modules/llm/deepseek_analysis_plan_provider.py`：分析方案 provider（不动）。
- `server/app/modules/llm/deepseek_code_task_provider.py`：代码任务 provider（不动）。
- `server/app/infrastructure/llm/llm_cache.py`：LLM 缓存（不动，复用现有 `get` / `set` / `compute_key`）。
- `server/worker/**`：Worker handler（不动）。
- `server/app/infrastructure/database/**`：数据库模型（不动）。
- `server/alembic/versions/**`：迁移文件（不动）。
- `server/app/core/config.py`：配置（不动，无需新增环境变量）。
- `apps/web/src/features/evidence/**`：证据卡片前端（不动）。
- `apps/web/src/features/outlines/**`：大纲前端（不动）。
- `apps/web/src/features/jobs/**`：任务轮询前端（不动）。
- `package.json` 和 `package-lock.json`：不新增前端依赖。
- `server/pyproject.toml`：不新增后端依赖。

## 验收标准（28 项，详见 SPEC 0018 §七）

核心 AC：

- AC-1~5：DeepSeekClient 流式调用（成功 / 缓存命中 / 缓存写入 / 首 chunk 前失败 / 中途失败）。
- AC-6~8：Provider 流式调用（成功 / 首 chunk 前降级 / 中途失败）。
- AC-9~11：Service 流式调用（成功 / 中途失败 / 兼容 LocalRule）。
- AC-12~13：API SSE 端点（事件格式 / 错误响应）。
- AC-14~16：前端流式解析（SSE 解析 / Hook 状态 / UI 流式展示）。
- AC-17：原同步端点零回归。
- AC-18~21：测试通过（后端 ~756 + 前端 ~444 + lint + build）。
- AC-22~23：Alembic 无变化 / 数据库零改动。
- AC-24~25：不引入新依赖 / 浏览器验收截图。
- AC-26~28：不破坏 owner 边界 / 文档回写 / 版本收口（tag v2.0.0）。

## 验收证据

SPEC 0018 已完成实现与验收（2026-07-25），AC-1~28 全部通过：

- **后端测试**：`server` 下 `.venv\Scripts\python.exe -m pytest` 结果 **783 passed in 124.54s, 0 warnings**（736 原有 + 47 新增：test_deepseek_client_stream 18 + test_deepseek_requirement_provider_stream 7 + test_requirements_service_stream 11 + test_requirements_stream_api 11）。
- **前端测试**：`apps/web` 下 `npm test -- --run` 结果 **468 passed**（25 个测试文件，434 原有 + 34 新增：stream-sse 18 + api-stream 6 + hooks-stream 10）。
- **TypeScript 类型检查**：`npm run lint` 通过（tsc --noEmit 无错误）。
- **Vite 构建**：`npm run build` 通过，115 模块转换，dist/ 400.27 kB，gzip 109.09 kB。
- **Alembic 迁移**：无变化（SPEC 0018 不修改数据库 schema，流式 chunk 不持久化）。
- **数据库零改动**：`git diff server/alembic/` 和 `git diff server/app/infrastructure/database/` 均无变化。
- **不引入新依赖**：`git diff server/pyproject.toml` 和 `git diff apps/web/package.json` 均无依赖变化。
- **浏览器验收**：browser_use agent 执行真实浏览器点击验收 PASS——创建项目 → 添加实验要求来源 → 点击"流式生成任务单" → 观察到流式展示区出现（带边框灰色背景）+ "取消"按钮 + chunk 文本在 `<pre>` 标签中逐步累积 + 流式完成后显示"流式生成完成 ✓ [LOCAL_RULE]"提示；后端 API 验证任务单已保存（CANDIDATE 状态）。**截图未持久化到磁盘（TD-009 延续）**。
- **原同步端点零回归**：`POST /plans/generate` 同步端点未修改，test_requirement_api.py 和 test_requirement_service.py 全部通过。
- **owner 边界**：API 路由层只做 SSE 协议映射，业务真相在 service 层；前端 hook 只展示状态不私造状态机，done 事件后 invalidateQueries 用后端真相覆盖。

详细验收记录见 [acceptance.md](../acceptance.md) SPEC 0018 章节。

## 后续方向

SPEC 0018 完成后，V2.0 后续 SPEC 待项目负责人规划。可能的候选方向：

- **V2.1 SPEC 0019**：大纲生成流式化。采用"新增 SSE 端点绕过 Worker"方案（本切片已确认 V2.1 备选方向）。
- **V2.1+**：证据卡片 / 分析方案 / 代码任务流式化。
- TD-009 浏览器验收截图持久化修复（评估 puppeteer 等替代工具）。

上述方向均需先编写并确认对应 SPEC，不得直接进入实现。
