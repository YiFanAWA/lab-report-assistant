# V2.2.0 版本发布说明

> **版本：** v2.2.0
> **发布日期：** 2026-07-26
> **上一版本：** v2.1.0
> **提交范围：** `v2.1.0..v2.2.0`（1 个提交：SPEC 0020 证据卡片生成流式化）
> **变更统计：** 后端 858 测试 + 前端 519 测试 = 1377 个测试（新增 63 个）
> **文档状态：** 已完成实现与验收，待项目负责人确认发布

---

## 概述

实验报告助手 V2.2.0 是 V2.0.0 的**第三个流式 LLM 输出版本**。V2.2.0 **不改变产品边界**（仍是本地单用户 Web MVP）和**架构主线**（仍是唯一 owner + API 适配 + 前端接线），核心目标是**将 SPEC 0018 的流式架构从"任务单生成 / 大纲生成"扩展到"证据卡片生成"**，完成实验报告工作流中第三个长等待环节的流式化改造。

V2.2.0 聚焦于一个功能切片：

| 切片 | 标题 | 类型 | 状态 |
| --- | --- | --- | --- |
| SPEC 0020 | 证据卡片生成流式化 | 新增功能 | ✅ 已完成 |

**核心价值：** V2.2.0 发布后，用户在"来源已解析（PARSED）"状态下点击"流式生成"按钮后，能实时看到 LLM 逐 chunk 生成的证据卡片 JSON，并随时可以取消。这完成了实验报告工作流中第三个长等待环节的流式化，与 SPEC 0018 的任务单流式化、SPEC 0019 的大纲流式化形成对称，将流式能力覆盖到证据化工作流的三个 LLM 生成场景。

---

## 一、核心变更：SPEC 0020 证据卡片生成流式化

### 1.1 痛点与解决方案

**痛点：** V2.1.0 之前，用户上传/登记来源并解析完成后，点击"生成候选"按钮需通过 Worker 异步任务等待证据卡片生成完成，期间只能看到任务状态轮询，无法实时看到 LLM 生成过程。Worker 异步路径与流式推送语义不兼容。

**解决方案：** 新增独立的 SSE 端点绕过 Worker，在请求处理中直接调用 LLM provider 流式生成，保留原 Worker 异步端点兼容：

| 维度 | V2.1.0（Worker 异步） | V2.2.0（SSE 流式） |
| --- | --- | --- |
| 用户等待感知 | 任务状态轮询 | 实时看到逐 chunk 生成 |
| 中途取消 | 不支持（任务已派发） | 支持（取消按钮） |
| 错误反馈 | 任务失败后提示 | 中途失败保留已生成内容 |
| 降级策略 | 无（整体失败） | 首 chunk 前降级 LocalRule |
| API 端点 | `POST /evidence/generate`（保留兼容） | `POST /evidence/stream-generate`（新增 SSE） |
| 执行路径 | Worker 进程异步处理 | 请求内直接调用 provider |

**架构选择：**
- SSE 端点绕过 Worker：解决 Worker 异步与 SSE 同步推送语义不兼容问题（复用 SPEC 0019 模式）
- 复用 SPEC 0018/0019 流式架构：`stream-sse.ts` 工具零修改，降级策略一致
- 分段持有 db session：Phase 1 校验（持有 db）→ Phase 2 流式生成（关闭 db）→ Phase 3 JSON 校验 → Phase 4 保存（重新打开 db），避免 SQLite 写锁阻塞
- 保留原 Worker 异步端点 `POST /evidence/generate` 兼容性
- Worker handler 零改动：Provider 输入是纯文本，无需提取共享方法

### 1.2 后端流式证据卡片生成

| 文件 | 变更类型 | 说明 |
| --- | --- | --- |
| `server/app/modules/llm/deepseek_evidence_provider.py` | 新增方法 | `stream_draft()` 生成器：HTTP 流式调用、首 chunk 前失败降级 LocalRule（拆分多 chunk yield fallback JSON）、中途失败抛异常保留已 yield chunks |
| `server/app/modules/sources/service.py` | 新增方法 | `stream_generate_evidence_cards()` 生成器（4 阶段：校验 → 流式 → JSON 校验 → 保存）、`StreamEvidenceChunkEvent` / `StreamEvidenceDoneEvent` / `StreamEvidenceErrorEvent` 事件类型 |
| `server/app/api/routers/evidence.py` | 新增端点 | `POST /sources/{source_id}/evidence/stream-generate` SSE 端点：`_serialize_evidence_sse_event()` 序列化、`StreamingResponse` + `text/event-stream`、预校验项目和来源存在（确保 404 而非 SSE 错误流）、`X-Accel-Buffering: no` 禁用 nginx 缓冲 |

### 1.3 前端流式证据卡片生成

| 文件 | 变更类型 | 说明 |
| --- | --- | --- |
| `apps/web/src/features/evidence/api.ts` | 新增函数 | `streamGenerateEvidence(projectId, sourceId, signal?)` 异步生成器：调用 `streamSSE()` 工具（复用，零修改），URL 为 `/sources/{source_id}/evidence/stream-generate`，body 为空对象 |
| `apps/web/src/features/evidence/hooks.ts` | 新增 hook | `useStreamGenerateEvidence(projectId, sourceId)`：`StreamEvidenceState` 状态结构（streaming / chunks / result / error）、`start()` 建立 SSE 连接逐 chunk 累积、`cancel()` 通过 AbortController 中断、`reset()` 重置状态、done 事件后 `invalidateQueries` 刷新证据卡片列表 |
| `apps/web/src/routes/EvidenceWorkspaceView.tsx` | UI 改造 | 在 `GenerateEvidenceRow` 组件中新增"流式生成"按钮（紫色 #6366f1，与原"生成候选"按钮并列，互斥禁用）+ 流式展示区（带边框 + "正在逐 chunk 生成…"提示 + "取消"按钮 + `<pre>` chunk 累积）+ "流式生成完成 ✓ [源]（降级）· 共 N 张卡片"完成提示 + 错误展示（含"查看已生成内容"详情折叠，展示 partial_text） |

### 1.4 SSE 事件协议

SSE 端点返回 `text/event-stream`，事件格式与 SPEC 0018/0019 一致：

```
event: chunk
data: {"text":"..."}

event: done
data: {"card_count":3, "candidate_source":"DEEPSEEK", "fallback_used":false}

event: error
data: {"error_code":"...", "message":"...", "partial_text":"..."}
```

### 1.5 降级策略

与 SPEC 0018/0019 一致的降级链：

| 场景 | 降级策略 | 用户感知 |
| --- | --- | --- |
| 首 chunk 前失败（网络/超时/鉴权） | 降级到 LocalRuleEvidenceCardProvider，拼装多张卡片 fallback JSON，拆分为多 chunk yield | 流式正常完成，done 事件 `fallback_used=true`，`candidate_source=LOCAL_RULE` |
| 中途失败（HTTP 流中断） | 抛异常，已 yield chunks 保留，不降级 | error 事件，含 `partial_text`，不保存 EvidenceCard |
| JSON 校验失败 | yield error 事件，不保存 EvidenceCard | error 事件，含 `partial_text` 为完整 raw JSON |
| 保存失败 | yield error 事件，含 `partial_text` | error 事件，`error_code=EVIDENCE_SAVE_FAILED` |

---

## 二、测试覆盖

### 2.1 后端测试

| 测试文件 | 测试数量 | 覆盖点 |
| --- | --- | --- |
| `test_deepseek_evidence_provider_stream.py` | 13 | 流式成功 / 单 chunk / source_label 返回 DEEPSEEK / 首 chunk 前降级 LocalRule / 降级后多张卡片 / 中途失败抛异常 / 中途失败不降级 / JSON 校验失败 / 有效 JSON / 空响应 / 缓存命中 / 空 text |
| `test_evidence_service_stream.py` | 15 | stream_generate_evidence_cards 成功 yield chunks + done / 保存 EvidenceCard / 写变更记录 / 中途失败 yield ErrorEvent / 中途失败不保存 / JSON 校验失败 / 同步 provider 兼容 / 项目不存在 / 项目状态不满足 / 来源不存在 / 来源未解析 / ParsedDocument 不存在 |
| `test_evidence_stream_api.py` | 9 | SSE 端点返回 text/event-stream / 完整流程多 chunk + done / chunk 拼接为有效 JSON / done 事件包含 card_count / fallback_used / 项目不存在 404 / 来源不存在 404 / 来源未解析 error 事件 / 项目状态未满足 error 事件 / 原端点零回归 |
| **小计** | **37** | — |

后端总数：**858 passed**（821 原有 + 37 新增），0 warnings。

### 2.2 前端测试

| 测试文件 | 测试数量 | 覆盖点 |
| --- | --- | --- |
| `api-stream.test.ts` | 6 | 正确 URL / POST 方法 / 空 body / URL 编码 / 委托 streamSSE / AbortSignal / HTTP 错误透传 |
| `hooks-stream.test.tsx` | 12 | chunk 累积 / done + invalidate / start 重置 / fallback_used 标记 / streaming 状态 / error + partial_text / STREAM_NETWORK_ERROR / AbortError / cancel / reset / 初始状态 |
| `EvidenceWorkspaceView.test.tsx`（新增流式块） | 8 | 流式按钮与原按钮共存 / 点击触发 start / 流式展示区显示 / 取消按钮触发 cancel / 完成提示显示 candidate_source / 降级完成提示 / 错误展示含 partial_text 详情 / 无 partial_text 时不显示详情 |
| **小计** | **26** | — |

前端总数：**519 passed**（493 原有 + 26 新增），29 个测试文件。

### 2.3 回归测试

- 原同步端点 `POST /evidence/generate` 零回归（`test_evidence_stream_api.py::TestOriginalEndpointZeroRegression` 通过）
- TypeScript 类型检查（`tsc --noEmit`）：通过
- Vite 构建：成功（115 模块转换，dist/ 406.59 kB，gzip 110.85 kB）

---

## 三、约束遵守

| 约束 | 验证方法 | 结果 |
| --- | --- | --- |
| 不引入新依赖 | `git diff server/pyproject.toml` + `git diff apps/web/package.json` | ✅ 无变化 |
| 不修改数据库 schema | `git diff server/alembic/` + `git diff server/app/infrastructure/database/` | ✅ 无变化 |
| 不引入 WebSocket | 代码审查 | ✅ 仅使用 SSE（text/event-stream） |
| 复用 stream-sse.ts | `git diff apps/web/src/shared/stream-sse.ts` | ✅ 无变化 |
| owner 边界 | 代码审查 | ✅ API 只做协议映射，业务真相在 service 层 |
| 保留原端点兼容 | `test_evidence_stream_api.py::TestOriginalEndpointZeroRegression` | ✅ 零回归 |
| Worker handler 零改动 | `git diff server/worker/handlers.py` | ✅ 无变化 |

---

## 四、浏览器验收

启动后端（uvicorn port 8001）+ 前端 Vite dev server，用 browser_use agent 执行真实浏览器点击验收：

1. ✅ 首页加载，项目列表显示"SPEC0020 流式证据卡片验收项目"
2. ✅ 进入项目详情页，URL 跳转至 `/projects/proj_spec0020_e2e`
3. ✅ 进入证据卡片工作区，来源"胃病数据分析参考文档（验收用）"显示"已解析"状态
4. ✅ 确认"生成候选"和"流式生成"两个按钮并列存在
5. ✅ 点击"流式生成"按钮，按钮变为"流式生成中…"，出现 chunk 累积展示区 + "取消"按钮
6. ✅ 流式完成后显示绿色提示"流式生成完成 ✓ [LOCAL_RULE（降级）] · 共 3 张卡片"
7. ✅ 证据卡片列表自动刷新，显示 3 张新生成的卡片（BACKGROUND / METHOD / RESULT）
8. ✅ 控制台无 SPEC 0020 相关 error

**验收结论：PASS**。截图保存至 `dev-docs/e2e-screenshots/e2e-spec0020-*.png`（6 张），完整报告见 `dev-docs/e2e-acceptance-report-spec0020.md`。

---

## 五、与 SPEC 0018/0019 的对比

| 维度 | SPEC 0018（任务单流式） | SPEC 0019（大纲流式） | SPEC 0020（证据卡片流式） |
| --- | --- | --- | --- |
| Provider | `DeepSeekRequirementDraftProvider` | `DeepSeekOutlineProvider` | `DeepSeekEvidenceCardProvider` |
| 上下文来源 | 单一 requirement_text | 跨模块聚合（5 模块） | 单一 parsed_text |
| 原同步路径 | `POST /plans/generate`（保留） | `POST /outline/generate`（Worker，保留） | `POST /evidence/generate`（Worker，保留） |
| 前端工具 | `stream-sse.ts`（新建） | `stream-sse.ts`（复用） | `stream-sse.ts`（复用） |
| 上下文聚合 | 无 | `gather_outline_context()`（提取到 service） | 无（Provider 输入是纯文本） |
| Worker 关系 | 不涉及 Worker | SSE 端点绕过 Worker，保留兼容 | SSE 端点绕过 Worker，保留兼容 |
| Worker handler | 不涉及 | 重构（调用 service 层方法） | 零改动 |
| done 事件 | plan_id | outline_id | card_count |
| 降级策略 | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule |
| 分段 db session | 是 | 是 | 是 |

---

## 六、文件变更清单

### 后端

| 文件 | 变更类型 |
| --- | --- |
| `server/app/modules/llm/deepseek_evidence_provider.py` | 修改（新增 stream_draft 方法） |
| `server/app/modules/sources/service.py` | 修改（新增 stream_generate_evidence_cards + 事件类型） |
| `server/app/api/routers/evidence.py` | 修改（新增 SSE 端点 + 序列化函数） |
| `server/tests/test_deepseek_evidence_provider_stream.py` | 新建（13 测试） |
| `server/tests/test_evidence_service_stream.py` | 新建（15 测试） |
| `server/tests/test_evidence_stream_api.py` | 新建（9 测试） |

### 前端

| 文件 | 变更类型 |
| --- | --- |
| `apps/web/src/features/evidence/api.ts` | 修改（新增 streamGenerateEvidence） |
| `apps/web/src/features/evidence/hooks.ts` | 修改（新增 useStreamGenerateEvidence + StreamEvidenceState） |
| `apps/web/src/routes/EvidenceWorkspaceView.tsx` | 修改（UI 改造：流式按钮 + 展示区 + 取消 + 完成提示 + 错误展示） |
| `apps/web/src/features/evidence/__tests__/api-stream.test.ts` | 新建（6 测试） |
| `apps/web/src/features/evidence/__tests__/hooks-stream.test.tsx` | 新建（12 测试） |
| `apps/web/src/routes/__tests__/EvidenceWorkspaceView.test.tsx` | 修改（新增 8 个流式测试） |

### 文档

| 文件 | 变更类型 |
| --- | --- |
| `dev-docs/specs/0020-evidence-streaming.md` | 新建（SPEC 草案） |
| `dev-docs/decisions/0026-start-spec-0020-evidence-streaming.md` | 新建（决策记录） |
| `dev-docs/e2e-acceptance-report-spec0020.md` | 新建（浏览器验收报告） |
| `dev-docs/README.md` | 修改（顶部状态行 + SPEC 0020 索引 + V2.2 发布文档索引） |
| `dev-docs/acceptance.md` | 修改（顶部状态行 + 当前限制 + 验收记录表追加 SPEC 0020 记录） |
| `dev-docs/implementation-plan.md` | 修改（顶部说明 + 执行门禁追加 V2.2.0） |
| `dev-docs/changelog-v2.2.0.md` | 新建（本文件） |

---

## 七、已知限制

1. **TD-009 延续**：浏览器验收截图已持久化到磁盘（本次 SPEC 0020 截图保存成功），但 TD-009 作为历史债务仍延续（之前 SPEC 0017/0018/0019 的截图未持久化）。
2. **DEEPSEEK_API_KEY 未设置**：本次浏览器验收在 LocalRule 降级路径下完成，未覆盖 DeepSeek 真实流式调用路径。真实 LLM 流式调用路径已在后端单元测试（mock DeepSeekClient）中覆盖，待后续配置真实 API_KEY 后补充真实 LLM 流式验收。
3. **LocalRule 降级路径过快**：在无 DeepSeek API key 时，provider 降级为 LocalRule 同步生成，chunk 拆分为 50 字符片段快速 yield。本次浏览器验收因使用了多段落文本（每段 ≥ 30 字符）成功捕获了流式 UI 中间状态。

---

## 八、下一阶段

V2.2.0 完成后，实验报告工作流中三个 LLM 生成环节（任务单 + 大纲 + 证据卡片）均已完成流式化。后续可选方向：

- **SPEC 0021**：分析方案流式化（复用 SPEC 0018 模式）
- **SPEC 0022**：代码任务流式化（复用 SPEC 0018 模式）
- **真实 DeepSeek API 端到端验收**：配置 `DEEPSEEK_API_KEY` 后进行真实 LLM 流式验收
- **多来源批量流式**：扩展 SPEC 0020 支持跨来源批量流式生成

下一阶段方向待项目负责人规划。后续新切片开始前仍需先编写并确认新 SPEC。
