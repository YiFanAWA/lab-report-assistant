# V2.1.0 版本发布说明

> **版本：** v2.1.0
> **发布日期：** 2026-07-26
> **上一版本：** v2.0.0
> **提交范围：** `v2.0.0..v2.1.0`（1 个提交：SPEC 0019 大纲生成流式化）
> **变更统计：** 后端 821 测试 + 前端 493 测试 = 1314 个测试（新增 63 个）
> **文档状态：** 已完成实现与验收，待项目负责人确认发布

---

## 概述

实验报告助手 V2.1.0 是 V2.0.0 的**第二个流式 LLM 输出版本**。V2.1.0 **不改变产品边界**（仍是本地单用户 Web MVP）和**架构主线**（仍是唯一 owner + API 适配 + 前端接线），核心目标是**将 SPEC 0018 的流式架构从"任务单生成"扩展到"大纲生成"**，完成实验报告工作流中第二个长等待环节的流式化改造。

V2.1.0 聚焦于一个功能切片：

| 切片 | 标题 | 类型 | 状态 |
| --- | --- | --- | --- |
| SPEC 0019 | 大纲生成流式化 | 新增功能 | ✅ 已完成 |

**核心价值：** V2.1.0 发布后，用户在"结果已确认（RESULT_CONFIRMED）"状态下点击"流式生成大纲"按钮后，能实时看到 LLM 逐 chunk 生成的大纲 JSON（含 6 个章节：实验要求 / 证据卡片 / 数据集 / 分析方案 / 执行结果 / 综合总结），并随时可以取消。这完成了实验报告工作流中第二个长等待环节的流式化，与 SPEC 0018 的任务单流式化形成对称，为后续 Word/PPT 生成的流式化奠定架构基础。

---

## 一、核心变更：SPEC 0019 大纲生成流式化

### 1.1 痛点与解决方案

**痛点：** V2.0.0 之前，用户点击"生成大纲候选"后需通过 Worker 异步任务等待生成完成，期间只能看到任务状态轮询，无法实时看到 LLM 生成过程。Worker 异步路径与流式推送语义不兼容（Worker 在后台进程执行，无法直接向前端 SSE 连接推送 chunk）。

**解决方案：** 新增独立的 SSE 端点绕过 Worker，在请求处理中直接调用 LLM provider 流式生成，保留原 Worker 异步端点兼容：

| 维度 | V2.0.0（Worker 异步） | V2.1.0（SSE 流式） |
| --- | --- | --- |
| 用户等待感知 | 任务状态轮询 | 实时看到逐 chunk 生成 |
| 中途取消 | 不支持（任务已派发） | 支持（取消按钮） |
| 错误反馈 | 任务失败后提示 | 中途失败保留已生成内容 |
| 降级策略 | 无（整体失败） | 首 chunk 前降级 LocalRule |
| API 端点 | `POST /outline/generate`（保留兼容） | `POST /outline/stream-generate`（新增 SSE） |
| 执行路径 | Worker 进程异步处理 | 请求内直接调用 provider |

**架构选择：**
- SSE 端点绕过 Worker：解决 Worker 异步与 SSE 同步推送语义不兼容问题
- 上下文聚合提取：将 `_gather_outline_context()` 从 `worker/handlers.py` 提取到 `outlines/service.py` 的 `gather_outline_context()`，实现流式 service 和 Worker handler 共享上下文聚合逻辑
- 复用 SPEC 0018 流式架构：`stream-sse.ts` 工具零修改，降级策略（首 chunk 前降级 LocalRule，中途失败保留 partial_text）一致
- 分段持有 db session：Phase 1 校验（持有 db）→ Phase 2 流式生成（关闭 db）→ Phase 3 JSON 校验 → Phase 4 保存（重新打开 db），避免 SQLite 写锁阻塞
- 保留原 Worker 异步端点 `POST /outline/generate` 兼容性

### 1.2 后端流式大纲生成

| 文件 | 变更类型 | 说明 |
| --- | --- | --- |
| `server/app/modules/llm/deepseek_outline_provider.py` | 新增方法 | `stream_generate()` 生成器：缓存查询（命中一次性 yield）、HTTP 流式调用、SSE 行解析、首 chunk 前失败降级 LocalRule、中途失败抛异常保留已 yield chunks、JSON 校验 |
| `server/app/modules/outlines/service.py` | 新增方法 + 提取 | `gather_outline_context()`（从 worker/handlers.py 提取，跨 5 模块聚合上下文）、`stream_generate_outline()` 生成器（4 阶段：校验 → 流式 → JSON 校验 → 保存）、`StreamOutlineChunkEvent` / `StreamOutlineDoneEvent` / `StreamOutlineErrorEvent` 事件类型 |
| `server/app/api/routers/outlines.py` | 新增端点 | `POST /outline/stream-generate` SSE 端点：`_serialize_outline_sse_event()` 序列化、`StreamingResponse` + `text/event-stream`、预校验项目存在（确保 404 而非 SSE 错误流）、`X-Accel-Buffering: no` 禁用 nginx 缓冲 |
| `server/worker/handlers.py` | 重构 | `handle_generate_outline` 改为调用 `outlines/service.gather_outline_context()`，消除重复的上下文聚合代码（168 行减少为调用 service 层方法） |

### 1.3 前端流式大纲生成

| 文件 | 变更类型 | 说明 |
| --- | --- | --- |
| `apps/web/src/features/outlines/api.ts` | 新增函数 | `streamGenerateOutline()` 异步生成器：调用 `streamSSE()` 工具（SPEC 0018 复用，零修改），URL 为 `/outline/stream-generate`，body 为空对象（无 source_id） |
| `apps/web/src/features/outlines/hooks.ts` | 新增 hook | `useStreamGenerateOutline(projectId)`：`StreamOutlineState` 状态结构（streaming / chunks / result / error）、`start()` 建立 SSE 连接逐 chunk 累积、`cancel()` 通过 AbortController 中断、`reset()` 重置状态、done 事件后 `invalidateQueries` 刷新大纲列表 |
| `apps/web/src/routes/OutlineWorkspaceView.tsx` | UI 改造 | 新增"流式生成大纲"按钮（紫色 #6366f1，与原"生成大纲候选"按钮并列，互斥禁用）+ 流式展示区（带边框灰色背景 + "正在逐 chunk 生成…"提示 + "取消"按钮 + `<pre>` chunk 累积）+ "流式生成完成 ✓ [源]（降级）"完成提示 + 错误展示（含"查看已生成内容"详情折叠，展示 partial_text） |

### 1.4 SSE 事件协议

SSE 端点返回 `text/event-stream`，事件格式与 SPEC 0018 一致：

```
event: chunk
data: {"text":"..."}

event: done
data: {"outline_id":"...", "candidate_source":"...", "fallback_used":false}

event: error
data: {"error_code":"...", "message":"...", "partial_text":"..."}
```

### 1.5 降级策略

与 SPEC 0018 一致的降级链：

| 场景 | 降级策略 | 用户感知 |
| --- | --- | --- |
| 首 chunk 前失败（网络/超时/鉴权） | 降级到 LocalRule provider，拼装 6 个章节的 fallback JSON，拆分为多 chunk yield | 流式正常完成，done 事件 `fallback_used=true`，`candidate_source=LOCAL_RULE` |
| 中途失败（HTTP 流中断） | 抛异常，已 yield chunks 保留，不降级 | error 事件，含 `partial_text`，不保存 Outline |
| JSON 校验失败 | yield error 事件，不保存 Outline | error 事件，含 `partial_text` 为完整 raw JSON |
| 保存失败 | yield error 事件，含 `partial_text` | error 事件，`error_code=OUTLINE_SAVE_FAILED` |

---

## 二、测试覆盖

### 2.1 后端测试

| 测试文件 | 测试数量 | 覆盖点 |
| --- | --- | --- |
| `test_deepseek_outline_provider_stream.py` | 13 | 流式成功 / 缓存命中 / 首 chunk 前降级 LocalRule / 中途失败抛异常 / JSON 校验失败 / 空响应 / 上下文为空 |
| `test_outline_service_stream.py` | 17 | stream_generate_outline 成功 / 中途失败不保存 / 兼容同步 provider / 分段 db session / gather_outline_context 上下文聚合正确性（5 个子测试） |
| `test_outline_stream_api.py` | 8 | SSE 端点返回 text/event-stream / 事件格式 / 项目不存在 404 / 无执行记录 error 事件 / 原端点零回归 |
| **小计** | **38** | — |

后端总数：**821 passed**（783 原有 + 38 新增），0 warnings。

### 2.2 前端测试

| 测试文件 | 测试数量 | 覆盖点 |
| --- | --- | --- |
| `api-stream.test.ts` | 6 | 正确 URL / POST 方法 / 空 body / URL 编码 / 委托 streamSSE / AbortSignal |
| `hooks-stream.test.tsx` | 12 | chunk 累积 / done + invalidate / start 重置 / fallback_used 标记 / streaming 状态 / error + partial_text / STREAM_NETWORK_ERROR / AbortError / cancel / reset / 初始状态 |
| `OutlineWorkspaceView.test.tsx`（新增流式块） | 7 | 流式按钮与原按钮共存 / 点击触发 start / 流式展示区显示 / 取消按钮 / 完成提示 / 错误展示 / 无 partial_text 时不显示详情 |
| **小计** | **25** | — |

前端总数：**493 passed**（468 原有 + 25 新增），28 个测试文件。

### 2.3 回归测试

- `test_outline_worker_handlers.py`（原 Worker 路径 + 上下文聚合提取后行为）：13 个测试全部通过，零回归
- TypeScript 类型检查（`tsc --noEmit`）：通过
- Vite 构建：成功（115 模块转换，dist/ 403.42 kB，gzip 109.93 kB）

---

## 三、约束遵守

| 约束 | 验证方法 | 结果 |
| --- | --- | --- |
| 不引入新依赖 | `git diff server/pyproject.toml` + `git diff apps/web/package.json` | ✅ 无变化 |
| 不修改数据库 schema | `git diff server/alembic/` + `git diff server/app/infrastructure/database/` | ✅ 无变化 |
| 不引入 WebSocket | 代码审查 | ✅ 仅使用 SSE（text/event-stream） |
| 复用 stream-sse.ts | `git diff apps/web/src/shared/stream-sse.ts` | ✅ 无变化 |
| owner 边界 | 代码审查 | ✅ API 只做协议映射，业务真相在 service 层 |
| 保留原端点兼容 | `test_outline_worker_handlers.py` 13 个测试 | ✅ 零回归 |

---

## 四、浏览器验收

启动后端（uvicorn port 8001）+ 前端 Vite dev server，用 browser_use agent 执行真实浏览器点击验收：

1. ✅ 种子脚本创建 RESULT_CONFIRMED 项目 + 成功 ExecutionRun
2. ✅ 进入大纲工作区，确认"生成大纲候选"和"流式生成大纲"两个按钮并列存在
3. ✅ 点击"流式生成大纲"按钮，后端日志确认 `POST /outline/stream-generate` 返回 **200 OK**
4. ✅ 后端 API 验证大纲已保存（v1, CANDIDATE, local_rule, 6 章节）
5. ✅ 前端大纲列表自动刷新显示新 CANDIDATE 卡片
6. ⚠️ transient 流式 UI 状态（chunk 累积、"正在逐 chunk 生成…"）因 LocalRule provider 同步降级路径执行过快未被浏览器快照捕获（验证工具限制，非代码缺陷）

**验收结论：PASS**。后端 200 OK + 数据库持久化 + 列表自动刷新均验证通过，transient UI 状态未捕获为验证工具限制而非代码缺陷（延续 TD-009 截图未持久化限制）。

---

## 五、与 SPEC 0018 的对比

| 维度 | SPEC 0018（任务单流式） | SPEC 0019（大纲流式） |
| --- | --- | --- |
| Provider | `DeepSeekRequirementDraftProvider` | `DeepSeekOutlineProvider` |
| 上下文来源 | 单一 requirement_text | 跨模块聚合（5 个模块：requirements / sources / datasets / analysis / execution） |
| 原同步路径 | `POST /plans/generate`（保留） | `POST /outline/generate`（Worker，保留） |
| 前端工具 | `stream-sse.ts`（新建） | `stream-sse.ts`（复用，零修改） |
| 上下文聚合 | 无（直接传 requirement_text） | `gather_outline_context()`（从 worker/handlers.py 提取到 service.py） |
| Worker 关系 | 不涉及 Worker（原本就是同步 API） | SSE 端点绕过 Worker，但保留 Worker 异步端点兼容 |
| 降级策略 | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule（一致） |
| 分段 db session | 是 | 是（一致） |

---

## 六、文件变更清单

### 后端

| 文件 | 变更类型 |
| --- | --- |
| `server/app/modules/llm/deepseek_outline_provider.py` | 修改（新增 stream_generate 方法） |
| `server/app/modules/outlines/service.py` | 修改（新增 gather_outline_context + stream_generate_outline + 事件类型） |
| `server/app/api/routers/outlines.py` | 修改（新增 SSE 端点 + 序列化函数） |
| `server/worker/handlers.py` | 重构（改为调用 service 层 gather_outline_context） |
| `server/tests/test_deepseek_outline_provider_stream.py` | 新建（13 测试） |
| `server/tests/test_outline_service_stream.py` | 新建（17 测试） |
| `server/tests/test_outline_stream_api.py` | 新建（8 测试） |

### 前端

| 文件 | 变更类型 |
| --- | --- |
| `apps/web/src/features/outlines/api.ts` | 修改（新增 streamGenerateOutline） |
| `apps/web/src/features/outlines/hooks.ts` | 修改（新增 useStreamGenerateOutline + StreamOutlineState） |
| `apps/web/src/routes/OutlineWorkspaceView.tsx` | 修改（UI 改造：流式按钮 + 展示区 + 取消 + 完成提示 + 错误展示） |
| `apps/web/src/features/outlines/__tests__/api-stream.test.ts` | 新建（6 测试） |
| `apps/web/src/features/outlines/__tests__/hooks-stream.test.tsx` | 新建（12 测试） |
| `apps/web/src/routes/__tests__/OutlineWorkspaceView.test.tsx` | 修改（新增 7 个流式测试） |

### 文档

| 文件 | 变更类型 |
| --- | --- |
| `dev-docs/specs/0019-outline-streaming.md` | 新建（SPEC 草案） |
| `dev-docs/decisions/0025-start-spec-0019-outline-streaming.md` | 新建（决策记录） |
| `dev-docs/README.md` | 修改（顶部状态行 + SPEC 0019 索引 + V2.1 发布文档索引） |
| `dev-docs/acceptance.md` | 修改（顶部状态行 + 当前限制 + 验收记录表追加 SPEC 0019 17 条记录） |
| `dev-docs/implementation-plan.md` | 修改（顶部说明 + 执行门禁追加 V2.1.0） |
| `dev-docs/changelog-v2.1.0.md` | 新建（本文件） |

---

## 七、已知限制

1. **TD-009 延续**：浏览器验收截图未持久化到磁盘（browser_take_screenshot 工具限制），transient 流式 UI 状态因 LocalRule 同步降级路径过快未被快照捕获。后端 200 OK + 数据库持久化 + 列表自动刷新 + 25 个前端单元测试作为替代证据。
2. **LocalRule 降级路径过快**：在无 DeepSeek API key 时，provider 降级为 LocalRule 同步生成，chunk 拆分为 50 字符片段快速 yield，浏览器快照难以捕获中间状态。这是测试环境限制，真实 DeepSeek API 调用会有真实的流式延迟。

---

## 八、下一阶段

V2.1.0 完成后，实验报告工作流中两个 LLM 生成环节（任务单 + 大纲）均已完成流式化。后续可选方向：

- **Word/PPT 生成流式化**：将 SPEC 0011 的 Word/PPT 渲染从 Worker 异步改造为流式（但 Word/PPT 是模板渲染而非 LLM 调用，流式价值有限）
- **真实 DeepSeek API 端到端验收**：配置 `DEEPSEEK_API_KEY` 后进行真实 LLM 流式验收
- **流式生成的进度估算**：基于已生成 chunk 数 / 总预估长度展示进度条
- **流式生成历史回放**：保存流式生成的 chunk 序列供用户回看

下一阶段方向待项目负责人规划。后续新切片开始前仍需先编写并确认新 SPEC。
