# 决策 0026：启动 SPEC 0020 证据卡片生成流式化切片

> **日期：** 2026-07-26
> **状态：** 已完成实现与验收，待项目负责人确认收口
> **决策人：** 项目负责人

## 背景

V2.1.0 已发布并打 tag v2.1.0，SPEC 0019 大纲生成流式化已收口。当前活跃可记录债务为 TD-009（非阻断，浏览器验收截图未持久化，已输出评估报告建议方案 A 文档化降级为非债务，待项目负责人确认）。

项目负责人于 2026-07-26 批准 SPEC 0020 证据卡片生成流式化草案，要求按测试先行原则进入实现。

经架构调研，发现：

- **证据卡片生成**（`POST /api/projects/{project_id}/sources/{source_id}/evidence/generate`）走 **Worker 异步模式**（与大纲生成相同），与 SSE 同步推送语义不兼容。
- **Provider 输入是单文档 parsed_text**（不是跨模块上下文聚合，比大纲简单），无需提取共享方法到 service 层。
- **批量产出**：一次生成多张卡片，但 LLM 仍返回单个 JSON `{"cards": [...]}`，流式处理与 SPEC 0019 完全一致，区别仅在 done 事件返回 `card_count` 而非 `outline_id`。
- **DeepSeekClient.stream_chat_completion()** 已在 SPEC 0018 实现，**stream-sse.ts** 已在 SPEC 0018 实现，无需新增依赖。

## 决策

1. 启动 SPEC 0020 证据卡片生成流式化切片，目标版本 v2.2.0。
2. **流式范围仅限证据卡片生成**：改造为新增 `POST /sources/{source_id}/evidence/stream-generate` SSE 端点，保留原 Worker 异步端点兼容。分析方案、代码任务流式化推迟到后续 SPEC。
3. **架构选择 SSE 端点绕过 Worker**（复用 SPEC 0019 模式）：后端使用 `fastapi.responses.StreamingResponse` 推送 SSE 事件，前端使用 `fetch + ReadableStream` 解析，不引入 WebSocket / 长轮询。
4. **降级策略**（复用 SPEC 0018/0019 模式）：首 chunk 前失败降级到 `LocalRuleEvidenceCardProvider`（拆分多 chunk 模拟流式）；中途失败保留已生成 chunk + 推送 `error` 事件；中途失败不保存 EvidenceCard、不写入 LLM 缓存。
5. **流式期间分段持有 db session**（复用 SPEC 0019 模式）：Phase 1 校验（持有 db）→ Phase 2 流式生成（关闭 db，不持有连接）→ Phase 3 完成后重新打开 db 保存。避免 SQLite 写锁阻塞其他请求。
6. **缓存策略**：流式与同步共享 SPEC 0014 LLM 缓存。缓存命中时一次性 yield 完整字符串；流式完成后写入缓存；中途失败不写入。
7. **不引入新依赖**：httpx + fetch 原生支持 SSE，无需新增 Python / npm 依赖。
8. **不修改数据库 schema**：流式 chunk 不持久化，无新增 Alembic 迁移。
9. **不破坏原同步端点**：保留 `POST /evidence/generate`（Worker 异步）不变。
10. **不修改 Worker handler**：`handle_generate_evidence` 保持不变（Provider 输入是纯文本，已极简，无需提取共享方法）。
11. **实施完成后打 tag v2.2.0 并 push 到 origin/master**。
12. **测试先行原则**：先编写后端单元测试（Provider + Service + API），再编写前端测试，最后实现代码并验证。

## 理由

- **复用 SPEC 0019 成熟模式降低风险**：SSE 绕过 Worker 架构已在 SPEC 0019 验证通过（821 后端测试 + 493 前端测试），SPEC 0020 是第三次复用，风险最低。
- **Provider 输入比大纲更简单**：大纲需要从 5 个模块聚合上下文，证据卡片只需 `ParsedDocument.parsed_text`，无需提取 `gather_outline_context` 类似的共享方法。
- **批量产出无技术难点**：LLM 仍返回单个 JSON `{"cards": [...]}`，流式处理与 SPEC 0019 完全一致，done 事件返回 `card_count` 即可。
- **不破坏 Worker 路径**：保留原 `POST /evidence/generate` 兼容，Worker handler 零改动，回归风险最低。
- **不引入新依赖**：完全复用 SPEC 0018/0019 已建立的流式基础设施（httpx stream / fetch ReadableStream / stream-sse.ts）。
- **测试先行**：SPEC 0018/0019 均采用"先写测试合同 → 再实现 → 最后验证"的模式，确保合同清晰、覆盖完整。

## 影响范围

### 范围内（改动文件）

- `server/app/modules/llm/deepseek_evidence_provider.py`：新增 `stream_draft()` 生成器方法。
- `server/app/modules/sources/service.py`：新增 `StreamEvidenceChunkEvent` / `StreamEvidenceDoneEvent` / `StreamEvidenceErrorEvent` 类型；新增 `stream_generate_evidence_cards()` 生成器方法。
- `server/app/api/routers/evidence.py`：新增 `POST /sources/{source_id}/evidence/stream-generate` SSE 端点；新增 `_serialize_evidence_sse_event()` 辅助函数。
- `apps/web/src/features/evidence/api.ts`：新增 `streamGenerateEvidence()` 异步生成器。
- `apps/web/src/features/evidence/hooks.ts`：新增 `useStreamGenerateEvidence()` hook + `StreamEvidenceState` 接口。
- `apps/web/src/routes/EvidenceWorkspaceView.tsx`：新增流式生成按钮 + 流式展示区 + 取消按钮 + 完成提示 + 错误展示。
- `server/tests/test_deepseek_evidence_provider_stream.py`（新增）：Provider 流式方法测试（~13 测试）。
- `server/tests/test_evidence_service_stream.py`（新增）：Service 流式方法测试（~15 测试）。
- `server/tests/test_evidence_stream_api.py`（新增）：API SSE 端点测试（~11 测试）。
- `apps/web/src/features/evidence/__tests__/api-stream.test.ts`（新增）：前端 API 测试（~6 测试）。
- `apps/web/src/features/evidence/__tests__/hooks-stream.test.tsx`（新增）：前端 hook 测试（~12 测试）。
- `apps/web/src/routes/__tests__/EvidenceWorkspaceView.test.tsx`（扩展）：新增 ~7 个流式 UI 测试。
- `dev-docs/specs/0020-evidence-streaming.md`（已创建，本切片 SPEC）。
- `dev-docs/decisions/0026-start-spec-0020-evidence-streaming.md`（本文件）。
- `dev-docs/acceptance.md`：新增 SPEC 0020 收口记录。
- `dev-docs/implementation-plan.md`：同步 SPEC 0020 完成状态。
- `dev-docs/README.md`：真源索引新增 SPEC 0020 和决策 0026。
- `dev-docs/changelog-v2.2.0.md`（新建）：V2.2.0 变更日志。

### 范围外（不改动文件）

- `server/app/modules/analysis/**`：分析方案模块（不动，留待后续 SPEC）。
- `server/app/modules/execution/**`：执行模块（不动）。
- `server/app/modules/llm/gateway.py`：Gateway 工厂（不动，复用现有 `get_evidence_card_provider()`）。
- `server/app/modules/llm/deepseek_outline_provider.py`：大纲 provider（不动）。
- `server/app/modules/llm/deepseek_requirement_provider.py`：任务单 provider（不动）。
- `server/app/modules/llm/deepseek_analysis_plan_provider.py`：分析方案 provider（不动）。
- `server/app/modules/llm/deepseek_code_task_provider.py`：代码任务 provider（不动）。
- `server/app/infrastructure/llm/llm_cache.py`：LLM 缓存（不动，复用现有 `get` / `set` / `compute_key`）。
- `server/worker/handlers.py`：Worker handler（不动，`handle_generate_evidence` 保持不变）。
- `server/app/infrastructure/database/**`：数据库模型（不动）。
- `server/alembic/versions/**`：迁移文件（不动）。
- `server/app/core/config.py`：配置（不动，无需新增环境变量）。
- `apps/web/src/features/outlines/**`：大纲前端（不动）。
- `apps/web/src/features/requirements/**`：任务单前端（不动）。
- `apps/web/src/features/jobs/**`：任务轮询前端（不动）。
- `apps/web/src/shared/stream-sse.ts`：SSE 解析工具（不动，复用 SPEC 0018）。
- `package.json` 和 `package-lock.json`：不新增前端依赖。
- `server/pyproject.toml`：不新增后端依赖。

## 验收标准（41 项，详见 SPEC 0020 §七）

核心 AC：

- AC-1~4：Provider 流式调用（成功 / 首 chunk 前降级 / 中途失败 / source_label）。
- AC-5~14：Service 流式调用（成功保存 / 中途失败不保存 / JSON 校验失败 / 兼容 LocalRule / 错误分支）。
- AC-15~21：API SSE 端点（事件格式 / 错误响应 / 原同步端点零回归 / Worker handler 零回归）。
- AC-22~29：前端流式解析（API / Hook 状态 / UI 流式展示）。
- AC-30~38：测试通过（后端 ~860 + 前端 ~525 + lint + build）+ Alembic 无变化 + 不引入新依赖 + owner 边界。
- AC-39~41：浏览器验收 / 文档回写 / 版本收口（tag v2.2.0）。

## 后续方向

SPEC 0020 完成后，V2.2 后续 SPEC 待项目负责人规划。可能候选方向：

- **V2.3 SPEC 0022**：分析方案流式化（同步直连 LLM，复用 SPEC 0018 模式）。
- **V2.3 SPEC 0023**：代码任务流式化（同步直连 LLM，复用 SPEC 0018 模式）。
- **TD-009 修复**：按评估结论处理（建议方案 A 文档化，或方案 B 引入 Playwright）。
- **多来源批量流式**：扩展 SPEC 0020 支持跨来源批量流式生成。

上述方向均需先编写并确认对应 SPEC，不得直接进入实现。

---

## 验收证据（2026-07-26 回写）

### 后端测试

| AC | 结果 | 证据 |
| --- | --- | --- |
| AC-1~4 | ✅ | `test_deepseek_evidence_provider_stream.py` 13 个测试通过（stream_draft 成功 / 首 chunk 前降级 / 中途失败抛异常 / source_label） |
| AC-5~14 | ✅ | `test_evidence_service_stream.py` 15 个测试通过（成功保存 / 中途失败不保存 / JSON 校验失败 / 同步 provider 兼容 / 错误分支） |
| AC-15~20 | ✅ | `test_evidence_stream_api.py` 9 个测试通过（SSE 端点 / 事件格式 / card_count / 404 / error 事件 / 原端点零回归） |
| AC-21 | ✅ | Worker handler 零改动，`git diff server/worker/handlers.py` 无变化 |

### 前端测试

| AC | 结果 | 证据 |
| --- | --- | --- |
| AC-22 | ✅ | `api-stream.test.ts` 6 个测试通过（URL / POST / body / URL 编码 / streamSSE / AbortSignal / HTTP 错误透传） |
| AC-23~26 | ✅ | `hooks-stream.test.tsx` 12 个测试通过（状态管理 / invalidate / AbortSignal / STREAM_NETWORK_ERROR / AbortError） |
| AC-27~29 | ✅ | `EvidenceWorkspaceView.test.tsx` 新增 8 个流式测试通过（流式按钮 / chunk 展示 / 取消 / 完成提示 / 错误详情） |

### 质量验收

| AC | 结果 | 证据 |
| --- | --- | --- |
| AC-30 | ✅ | 后端 858 passed in 71.83s, 0 warnings（821 原有 + 37 新增） |
| AC-31 | ✅ | 前端 519 passed（493 原有 + 26 新增），29 个测试文件 |
| AC-32 | ✅ | `tsc --noEmit` 通过，无类型错误 |
| AC-33 | ✅ | Vite 构建通过，115 模块转换，dist/ 406.59 kB，gzip 110.85 kB |
| AC-34 | ✅ | `git diff server/alembic/` 无变化 |
| AC-35 | ✅ | `git diff server/pyproject.toml` + `git diff apps/web/package.json` 无变化 |
| AC-36 | ✅ | `git diff apps/web/src/shared/stream-sse.ts` 无变化 |
| AC-37 | ✅ | 代码审查确认仅使用 SSE，未引入 WebSocket 或长轮询 |
| AC-38 | ✅ | API 路由层只做 SSE 协议映射，业务真相在 `sources/service.stream_generate_evidence_cards` |

### 浏览器与版本验收

| AC | 结果 | 证据 |
| --- | --- | --- |
| AC-39 | ✅ | browser_use agent 浏览器验收 PASS（6 步全通过，截图保存至 `dev-docs/e2e-screenshots/e2e-spec0020-*.png`，报告见 `e2e-acceptance-report-spec0020.md`） |
| AC-40 | ✅ | 文档回写完成：changelog-v2.2.0.md / acceptance.md / implementation-plan.md / README.md / decisions 0026 / specs 0020 |
| AC-41 | 待执行 | 版本收口：commit 中文 + tag v2.2.0 + push（待项目负责人确认后执行） |
