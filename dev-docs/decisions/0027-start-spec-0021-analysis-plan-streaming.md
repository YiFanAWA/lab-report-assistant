# 决策 0027：启动 SPEC 0021 分析方案生成流式化切片

> **日期：** 2026-07-26
> **状态：** 已完成实现与验收，待项目负责人确认收口
> **决策人：** 项目负责人

## 背景

V2.2.0 已发布并打 tag v2.2.0，SPEC 0020 证据卡片生成流式化已收口。当前活跃可记录债务为 TD-009（非阻断，浏览器验收截图未持久化，已在 SPEC 0020/0021 验收中部分缓解）。

项目负责人于 2026-07-26 批准 SPEC 0021 分析方案生成流式化草案，要求按测试先行原则进入实现。

经架构调研，发现：

- **分析方案生成**（`POST /api/datasets/{dataset_id}/analysis/generate`）走 **Worker 异步模式**（与证据卡片生成相同），与 SSE 同步推送语义不兼容。
- **Provider 输入是 DatasetProfile**（不是跨模块上下文聚合，比大纲简单），无需提取共享方法到 service 层。
- **单个产出**：一次生成一个 AnalysisPlanDraft（含 `cleaning_plan` + `analysis_plan` + `chart_plan` 三个列表），LLM 返回单个 JSON，流式处理与 SPEC 0019 完全一致，区别仅在 done 事件返回 `plan_id` 而非 `outline_id`。
- **DeepSeekClient.stream_chat_completion()** 已在 SPEC 0018 实现，**stream-sse.ts** 已在 SPEC 0018 实现，无需新增依赖。

## 决策

1. 启动 SPEC 0021 分析方案生成流式化切片，目标版本 v2.3.0。
2. **流式范围仅限分析方案生成**：改造为新增 `POST /datasets/{dataset_id}/analysis/stream-generate` SSE 端点，保留原 Worker 异步端点兼容。代码任务流式化、多来源批量流式化推迟到后续 SPEC。
3. **架构选择 SSE 端点绕过 Worker**（复用 SPEC 0019/0020 模式）：后端使用 `fastapi.responses.StreamingResponse` 推送 SSE 事件，前端使用 `fetch + ReadableStream` 解析，不引入 WebSocket / 长轮询。
4. **降级策略**（复用 SPEC 0018/0019/0020 模式）：首 chunk 前失败降级到 `LocalRuleAnalysisPlanProvider`（拆分多 chunk 模拟流式）；中途失败保留已生成 chunk + 推送 `error` 事件；中途失败不保存 AnalysisPlan、不写入 LLM 缓存。
5. **流式期间分段持有 db session**（复用 SPEC 0019/0020 模式）：Phase 1 校验（持有 db）→ Phase 2 流式生成（关闭 db，不持有连接）→ Phase 3 完成后重新打开 db 保存。避免 SQLite 写锁阻塞其他请求。
6. **缓存策略**：流式与同步共享 SPEC 0014 LLM 缓存。缓存命中时一次性 yield 完整字符串；流式完成后写入缓存；中途失败不写入。
7. **不引入新依赖**：httpx + fetch 原生支持 SSE，无需新增 Python / npm 依赖。
8. **不修改数据库 schema**：流式 chunk 不持久化，无新增 Alembic 迁移。
9. **不破坏原同步端点**：保留 `POST /analysis/generate`（Worker 异步）不变。
10. **不修改 Worker handler**：`handle_generate_analysis_plan` 保持不变（Provider 输入是 DatasetProfile，已极简，无需提取共享方法）。
11. **实施完成后打 tag v2.3.0 并 push 到 origin/master**。
12. **测试先行原则**：先编写后端单元测试（Provider + Service + API），再编写前端测试，最后实现代码并验证。

## 理由

- **复用 SPEC 0019/0020 成熟模式降低风险**：SSE 绕过 Worker 架构已在 SPEC 0019/0020 验证通过（821 + 858 后端测试），SPEC 0021 是第四次复用，风险最低。
- **Provider 输入比大纲更简单**：大纲需要从 5 个模块聚合上下文，分析方案只需 DatasetProfile，无需提取 `gather_outline_context` 类似的共享方法。
- **单个产出无技术难点**：LLM 返回单个 JSON（含三个列表），流式处理与 SPEC 0019 完全一致，done 事件返回 `plan_id` 即可。
- **不破坏 Worker 路径**：保留原 `POST /analysis/generate` 兼容，Worker handler 零改动，回归风险最低。
- **不引入新依赖**：完全复用 SPEC 0018/0019/0020 已建立的流式基础设施（httpx stream / fetch ReadableStream / stream-sse.ts）。
- **测试先行**：SPEC 0018/0019/0020 均采用"先写测试合同 → 再实现 → 最后验证"的模式，确保合同清晰、覆盖完整。

## 影响范围

### 范围内（改动文件）

- `server/app/modules/llm/deepseek_analysis_plan_provider.py`：新增 `stream_generate()` 生成器方法。
- `server/app/modules/llm/analysis_plan_provider.py`：修复 LocalRuleAnalysisPlanProvider 中 5 处 `target_fields` 输出为数组（原为字符串，导致前端 TypeError），FakeAnalysisPlanProvider 中 1 处同样修复。
- `server/app/modules/analysis/service.py`：新增 `StreamAnalysisChunkEvent` / `StreamAnalysisDoneEvent` / `StreamAnalysisErrorEvent` 类型；新增 `stream_generate_analysis_plan()` 生成器方法。
- `server/app/api/routers/analysis.py`：新增 `POST /datasets/{dataset_id}/analysis/stream-generate` SSE 端点；新增 `_serialize_analysis_sse_event()` 辅助函数。
- `apps/web/src/features/analysis/api.ts`：新增 `streamGenerateAnalysisPlan()` 异步生成器。
- `apps/web/src/features/analysis/hooks.ts`：新增 `useStreamGenerateAnalysisPlan()` hook + `StreamAnalysisState` 接口。
- `apps/web/src/routes/AnalysisWorkspaceView.tsx`：新增流式生成按钮 + 流式展示区 + 取消按钮 + 完成提示 + 错误展示。
- `server/tests/test_deepseek_analysis_plan_provider_stream.py`（新增）：Provider 流式方法测试（13 测试）。
- `server/tests/test_analysis_service_stream.py`（新增）：Service 流式方法测试（15 测试）。
- `server/tests/test_analysis_stream_api.py`（新增）：API SSE 端点测试（9 测试）。
- `apps/web/src/features/analysis/__tests__/api-stream.test.ts`（新增）：前端 API 测试（6 测试）。
- `apps/web/src/features/analysis/__tests__/hooks-stream.test.tsx`（新增）：前端 hook 测试（12 测试）。
- `apps/web/src/routes/__tests__/AnalysisWorkspaceView.test.tsx`（扩展）：新增 9 个流式 UI 测试。
- `server/scripts/setup_spec0021_e2e.py`（新建）：e2e 验收测试数据准备脚本。
- `dev-docs/specs/0021-analysis-plan-streaming.md`（已创建，本切片 SPEC）。
- `dev-docs/decisions/0027-start-spec-0021-analysis-plan-streaming.md`（本文件）。
- `dev-docs/acceptance.md`：新增 SPEC 0021 收口记录。
- `dev-docs/implementation-plan.md`：同步 SPEC 0021 完成状态。
- `dev-docs/README.md`：真源索引新增 SPEC 0021 和决策 0027。
- `dev-docs/changelog-v2.3.0.md`（新建）：V2.3.0 变更日志。
- `dev-docs/e2e-acceptance-report-spec0021.md`（新建）：浏览器验收报告。
- `dev-docs/e2e-screenshots/e2e-spec0021-*.png`（新建）：9 张浏览器验收截图。

### 范围外（不改动文件）

- `server/app/modules/sources/**`：来源与证据模块（不动，SPEC 0020 已完成）。
- `server/app/modules/execution/**`：执行模块（不动，留待 SPEC 0022）。
- `server/app/modules/llm/gateway.py`：Gateway 工厂（不动，复用现有 `get_analysis_plan_provider()`）。
- `server/app/modules/llm/deepseek_outline_provider.py`：大纲 provider（不动）。
- `server/app/modules/llm/deepseek_requirement_provider.py`：任务单 provider（不动）。
- `server/app/modules/llm/deepseek_evidence_provider.py`：证据卡片 provider（不动）。
- `server/app/modules/llm/deepseek_code_task_provider.py`：代码任务 provider（不动）。
- `server/app/infrastructure/llm/llm_cache.py`：LLM 缓存（不动，复用现有 `get` / `set` / `compute_key`）。
- `server/worker/handlers.py`：Worker handler（不动，`handle_generate_analysis_plan` 保持不变）。
- `server/app/infrastructure/database/**`：数据库模型（不动）。
- `server/alembic/versions/**`：迁移文件（不动）。
- `server/app/core/config.py`：配置（不动，无需新增环境变量）。
- `apps/web/src/features/outlines/**`：大纲前端（不动）。
- `apps/web/src/features/evidence/**`：证据卡片前端（不动）。
- `apps/web/src/features/requirements/**`：任务单前端（不动）。
- `apps/web/src/features/jobs/**`：任务轮询前端（不动）。
- `apps/web/src/shared/stream-sse.ts`：SSE 解析工具（不动，复用 SPEC 0018）。
- `package.json` 和 `package-lock.json`：不新增前端依赖。
- `server/pyproject.toml`：不新增后端依赖。

## 验收标准（41 项，详见 SPEC 0021 §六）

核心 AC：

- AC-1~4：Provider 流式调用（成功 / 首 chunk 前降级 / 中途失败 / source_label）。
- AC-5~14：Service 流式调用（成功保存 / 中途失败不保存 / JSON 校验失败 / 兼容 LocalRule / 错误分支）。
- AC-15~21：API SSE 端点（事件格式 / 错误响应 / 原同步端点零回归 / Worker handler 零回归）。
- AC-22~29：前端流式解析（API / Hook 状态 / UI 流式展示）。
- AC-30~38：测试通过（后端 ~895 + 前端 ~545 + lint + build）+ Alembic 无变化 + 不引入新依赖 + owner 边界。
- AC-39~41：浏览器验收 / 文档回写 / 版本收口（tag v2.3.0）。

## 后续方向

SPEC 0021 完成后，V2.3 后续 SPEC 待项目负责人规划。已有草案：

- **SPEC 0022**：代码任务流式化（同步直连 LLM，复用 SPEC 0018 模式）。
- **SPEC 0023**：多来源证据批量流式生成（扩展 SPEC 0020 支持跨来源批量流式生成）。
- **真实 DeepSeek API 端到端验收**：配置 `DEEPSEEK_API_KEY` 后进行真实 LLM 流式验收。
- **TD-009 修复**：按评估结论处理（建议方案 A 文档化，或方案 B 引入 Playwright；本次 SPEC 0021 已通过 browser_use agent 主动持久化截图部分缓解）。

上述方向均需先编写并确认对应 SPEC，不得直接进入实现。

---

## 验收证据（2026-07-26 回写）

### 后端测试

| AC | 结果 | 证据 |
| --- | --- | --- |
| AC-1~4 | ✅ | `test_deepseek_analysis_plan_provider_stream.py` 13 个测试通过（stream_generate 成功 / 首 chunk 前降级 / 中途失败抛异常 / source_label） |
| AC-5~14 | ✅ | `test_analysis_service_stream.py` 15 个测试通过（成功保存 / 中途失败不保存 / JSON 校验失败 / 同步 provider 兼容 / 错误分支） |
| AC-15~20 | ✅ | `test_analysis_stream_api.py` 9 个测试通过（SSE 端点 / 事件格式 / plan_id / 404 / error 事件 / 原端点零回归） |
| AC-21 | ✅ | Worker handler 零改动，`git diff server/worker/handlers.py` 无变化 |

### 前端测试

| AC | 结果 | 证据 |
| --- | --- | --- |
| AC-22 | ✅ | `api-stream.test.ts` 6 个测试通过（URL / POST / body / URL 编码 / streamSSE / AbortSignal / HTTP 错误透传） |
| AC-23~26 | ✅ | `hooks-stream.test.tsx` 12 个测试通过（状态管理 / invalidate / AbortSignal / STREAM_NETWORK_ERROR / AbortError） |
| AC-27~29 | ✅ | `AnalysisWorkspaceView.test.tsx` 新增 9 个流式测试通过（流式按钮 / chunk 展示 / 取消 / 完成提示 / 错误详情） |

### 质量验收

| AC | 结果 | 证据 |
| --- | --- | --- |
| AC-30 | ✅ | 后端 895 passed, 0 warnings（858 原有 + 37 新增） |
| AC-31 | ✅ | 前端 546 passed（519 原有 + 27 新增），31 个测试文件 |
| AC-32 | ✅ | `tsc --noEmit` 通过，无类型错误 |
| AC-33 | ✅ | Vite 构建通过 |
| AC-34 | ✅ | `git diff server/alembic/` 无变化 |
| AC-35 | ✅ | `git diff server/pyproject.toml` + `git diff apps/web/package.json` 无变化 |
| AC-36 | ✅ | `git diff apps/web/src/shared/stream-sse.ts` 无变化 |
| AC-37 | ✅ | 代码审查确认仅使用 SSE，未引入 WebSocket 或长轮询 |
| AC-38 | ✅ | API 路由层只做 SSE 协议映射，业务真相在 `analysis/service.stream_generate_analysis_plan` |

### 收口复核修复

| 修复项 | 结果 | 证据 |
| --- | --- | --- |
| LocalRuleAnalysisPlanProvider 输出 target_fields 为字符串导致前端 PlanCard TypeError | ✅ 已修复 | 修复 6 处输出为数组（5 处 LocalRule + 1 处 Fake），清理 1 条已保存的旧错误数据，后端 895 + 前端 546 全套测试零回归 |

### 浏览器与版本验收

| AC | 结果 | 证据 |
| --- | --- | --- |
| AC-39 | ✅ | browser_use agent 浏览器验收 PASS（9 张截图保存至 `dev-docs/e2e-screenshots/e2e-spec0021-*.png`，报告见 `e2e-acceptance-report-spec0021.md`） |
| AC-40 | ✅ | 文档回写完成：changelog-v2.3.0.md / acceptance.md / implementation-plan.md / README.md / decisions 0027 / specs 0021 |
| AC-41 | 待执行 | 版本收口：commit 中文 + tag v2.3.0 + push（待项目负责人确认后执行） |
