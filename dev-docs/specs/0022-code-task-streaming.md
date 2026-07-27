# SPEC 0022：代码任务生成流式化

**版本：** 1.0（已完成实现与验收）
**日期：** 2026-07-26（初稿）/ 2026-07-27（草案 0.2 同步 SPEC 0021 收口 + 草案 0.3 纳入评审反馈）/ 2026-07-28（完成实现与验收）
**状态：** 已完成（2026-07-28 实现与验收完成，待项目负责人确认收口）
**评审结论：** 有条件通过（2026-07-27 项目负责人评审，2026-07-28 批准进入实现阶段）
**目标版本：** v2.4.0（SPEC 0021 已独立收口为 v2.3.0，本切片为独立新切片）
**前置版本：** v2.3.0（SPEC 0021 分析方案生成流式化，已完成并打 tag v2.3.0，commit 9f7d274 + follow-up 7fccb90）
**关联决策：** [决策 0028](../decisions/0028-start-spec-0022-code-task-streaming.md)

---

## 实现收口说明（2026-07-28）

SPEC 0022 已完成实现与验收，关键结果：

- **后端测试**：975 passed（895 原有 + 80 新增含 SPEC 0022 流式 78 + 回归 2），0 warnings
- **前端测试**：570 passed（551 原有 + 19 新增），lint + build 通过
- **浏览器验收**：6 个关键验证点全部 PASS（流式按钮/原始 JSON 累积/取消按钮/完成提示/列表刷新/CANDIDATE 状态）
- **收口复核修复 1 项阻断问题**：`LocalRuleCodeTaskProvider._build_analysis_code` 中 FREQUENCY 类型 `target_fields.split()` 在 list 上报错，新增 `_first_field_name()` 辅助函数兼容 list/str/None，新增 2 个回归测试覆盖
- **约束遵守**：不引入新依赖、不修改数据库 schema、复用 stream-sse.ts、保留原 Worker 异步端点兼容、Worker handler 零改动
- **发布说明**：详见 [changelog-v2.4.0.md](../changelog-v2.4.0.md)

---

## 一、背景与目标

### 1.1 痛点

代码任务生成是实验报告工作流中**第五个也是最后一个高等待**的 LLM 调用（3-10s）。当前实现（V2.2.0）通过 Worker 异步执行：

1. 前端调用 `POST /api/projects/{project_id}/analysis/{plan_id}/code/generate` → 创建 Job → 返回 `job_id`
2. 前端 `useJob` 轮询 job 状态（默认 2s 间隔）
3. Worker 进程领取 Job → 取已确认的 `AnalysisPlan` → 调用 `provider.generate(analysis_plan)` 生成代码候选 → 保存为 CANDIDATE
4. Job 完成后，前端轮询发现状态变化 → 刷新代码任务列表

用户痛点：
- 3-10s 空白等待，无进度反馈
- 无法看到 LLM 生成代码的过程
- 无法中途取消
- Worker 异步与 SSE 同步推送语义不兼容

### 1.2 目标

将代码任务生成改造为 SSE 流式输出，复用 SPEC 0018/0019/0020/0021 的流式架构：
- 新增 `POST /api/projects/{project_id}/analysis/{plan_id}/code/stream-generate` SSE 端点（绕过 Worker）
- 后端流式调用 LLM，逐 chunk 推送
- 前端实时显示生成内容（含代码高亮），支持取消
- 保留原 `POST /code/generate`（Worker 异步）兼容

### 1.3 与 SPEC 0018/0019/0020/0021 的关系

SPEC 0022 是流式能力的**第五次复用**，架构已完全成熟：

| 维度 | SPEC 0018（任务单） | SPEC 0019（大纲） | SPEC 0020（证据卡片） | SPEC 0021（分析方案） | SPEC 0022（代码任务） |
| --- | --- | --- | --- | --- | --- |
| 流式架构 | SSE + Gateway 直调 | 复用 | 复用 | 复用 | 复用 |
| Provider 输入 | requirement_text | 跨模块聚合 | parsed_text | DatasetProfile | **analysis_plan（已确认）** |
| 产出 | 单个 JSON | 单个 JSON | 批量 list | 单个 JSON | **单个 CodeTaskDraft（含 code）** |
| 前端展示 | JSON 文本 | JSON 文本 | JSON 文本 | JSON 文本 | **代码文本（可考虑语法高亮）** |
| 原同步路径 | 保留 | 保留 | 保留 | 保留 | `POST /code/generate`（保留） |

**关键差异**：代码任务的产出是 `CodeTaskDraft`（含 `code` 字段），LLM 返回单个 JSON，流式处理与 SPEC 0019 一致。前端展示的是代码内容，可考虑在流式展示区使用 `<pre><code>` 标签或简单的代码高亮。

### 1.4 战略意义

SPEC 0022 完成后，实验报告工作流中**全部 5 个 LLM 生成环节**都将完成流式化：

1. ✅ 任务单生成（SPEC 0018，V2.0.0）
2. ✅ 证据卡片生成（SPEC 0020，V2.2.0）
3. ✅ 大纲生成（SPEC 0019，V2.1.0）
4. ✅ 分析方案生成（SPEC 0021，V2.3.0，2026-07-26 已收口）
5. ⏳ 代码任务生成（SPEC 0022，V2.4.0，本切片）

前 4 个环节已完成流式化，本切片完成后标志着流式化改造的**全面完成**。

---

## 二、范围与边界

### 2.1 在范围内

1. 后端 `DeepSeekCodeTaskProvider.stream_generate()` 流式方法
2. 后端 `execution_service.stream_generate_code_task()` 流式 service 方法（含分段 db session）
3. 后端 `POST /api/projects/{project_id}/analysis/{plan_id}/code/stream-generate` SSE 端点
4. 前端 `streamGenerateCodeTask()` API 函数
5. 前端 `useStreamGenerateCodeTask()` hook
6. 前端代码任务生成 UI 改造（流式按钮 + 展示区 + 取消）
7. 后端单元测试（Provider + Service + API）
8. 前端单元测试（API + Hook + UI）
9. 浏览器验收

### 2.2 不在范围内

1. 不改造原 Worker 异步端点（`POST /code/generate` 保留不变）
2. 不流式化代码执行（`ExecutionRun` 是 Python 执行，非 LLM 调用）
3. 不引入 WebSocket / 长轮询
4. 不修改数据库 schema
5. 不引入新依赖
6. 不修改 `stream-sse.ts`（复用 SPEC 0018）
7. 不修改 `DeepSeekClient.stream_chat_completion()`（复用 SPEC 0018）
8. 不修改 `handle_generate_code_task` Worker handler（保留兼容）
9. 不实现代码语法高亮库（使用 `<pre>` 展示即可，高亮留待后续优化）

---

## 三、架构设计

### 3.1 整体架构

```text
前端 useStreamGenerateCodeTask
    │
    ▼ fetch + ReadableStream
POST /projects/{project_id}/analysis/{plan_id}/code/stream-generate (SSE)
    │
    ▼ StreamingResponse
execution_service.stream_generate_code_task()
    │
    ├──▶ Phase 1: 校验（持有 db）
    │       └──▶ _ensure_project + _ensure_analysis_plan_confirmed
    │       └──▶ 取 AnalysisPlan（cleaning_plan + analysis_plan + chart_plan）
    │       └──▶ db.close()
    │
    ├──▶ Phase 2: 流式生成（不持有 db）
    │       └──▶ DeepSeekCodeTaskProvider.stream_generate(analysis_plan)
    │               └──▶ DeepSeekClient.stream_chat_completion()
    │
    └──▶ Phase 3: 保存（重新打开 db）
            └──▶ save_code_task_draft()
```

### 3.2 SSE 事件合同（复用 SPEC 0018/0019/0020/0021 格式 + 错误分层）

**事件序列契约**：

```text
event: chunk
data: {"text": "{\"code\":\"import pandas"}

event: chunk
data: {"text": " as pd\\ndf = pd.read_csv("}

event: done
data: {"code_task_id": "...", "candidate_source": "DEEPSEEK", "fallback_used": false}
```

**done 事件字段说明**：
- `code_task_id`：保存的 CodeTask ID
- `candidate_source`：DEEPSEEK / LOCAL_RULE
- `fallback_used`：是否使用了降级路径

#### 3.2.1 错误分层（评审反馈三：流前 vs 流后）

**流开始前错误**（响应头未发送，使用标准 HTTP 状态码，不进入 SSE 流）：

| 错误场景 | HTTP 状态码 | 错误码 | 说明 |
| --- | --- | --- | --- |
| 项目不存在 | 404 | `PROJECT_NOT_FOUND` | Phase 1 校验失败 |
| AnalysisPlan 不存在 | 404 | `ANALYSIS_PLAN_NOT_FOUND` | Phase 1 校验失败 |
| AnalysisPlan 未确认 | 409 | `ANALYSIS_PLAN_NOT_CONFIRMED` | Phase 1 校验失败，状态非 CONFIRMED |
| 请求参数非法 | 422 | `VALIDATION_ERROR` | Pydantic 校验失败 |
| 并发冲突（已有活动流式请求） | 409 | `STREAM_ALREADY_ACTIVE` | 见 §3.7 并发保护 |

**流开始后错误**（响应头已发送，必须使用 SSE `error` 事件）：

```text
event: error
data: {"error_code": "DEEPSEEK_TIMEOUT", "message": "流式请求超时", "partial_text": "..."}
```

#### 3.2.2 事件终止契约（评审反馈三补充）

- `error` 事件发送后必须**立即结束流**，不得再发送任何事件
- `error` 后**不得再发送 `done`**
- `done` 必须是成功流的**最后一个事件**
- 单个请求**最多出现一个终止事件**：`done` 或 `error` 二选一，不可同时出现
- 客户端断开后服务端不得继续推送事件（见 §3.3）

### 3.3 降级与取消策略（复用 SPEC 0018/0019/0020/0021 模式 + 服务端取消语义）

| 失败时机 | 降级行为 | 用户可见 | 是否保存 |
| --- | --- | --- | --- |
| 首 chunk 前 | 降级到 LocalRule，拆分多 chunk 模拟流式 | 是 | 是 |
| 中途失败 | 保留已生成 chunk + 推送 error 事件 | 是（部分代码） | 否 |
| JSON 校验失败 | 推送 error 事件 + partial_text | 是（错误提示） | 否 |
| 用户主动取消（前端 AbortController.abort()） | 见 §3.3.1 服务端取消语义 | 是（流式停止） | 否 |
| 客户端连接断开（网络中断/页面卸载） | 见 §3.3.1 服务端取消语义 | 是（连接关闭） | 否 |

#### 3.3.1 服务端取消语义（评审反馈二）

**客户端取消 ≠ 服务端立即停止**。需要明确服务端如何检测并响应取消：

| 检测机制 | 实现方式 | 说明 |
| --- | --- | --- |
| 客户端连接断开检测 | FastAPI `Request.is_disconnected()` 在生成器循环中轮询 | 每 chunk 之间检查一次，延迟 ≤ 单 chunk 生成时间 |
| AbortSignal 传播 | Service 层将 `Request` 传入生成器，Provider 在 `stream_chat_completion()` 调用时传入 | 复用 httpx 的 `TimeoutException` / `asyncio.CancelledError` |
| 异步生成器关闭 | 检测到断开后，Service 层 `async with` 退出时自动 `aclose()` 生成器 | Python 异步生成器标准行为 |
| CancelledError 处理 | 在 Service 层 `try/except asyncio.CancelledError` 中静默吞掉，不作为系统错误上报 | 取消是用户意图，非异常 |
| 日志记录 | 记录 `CANCELLED` 状态到 §3.8 可观测性日志，不记录为 ERROR | 区分用户取消与系统错误 |

**取消后的强约束**：

- 取消后**不得保存 CodeTask 候选**（与 SPEC 0021 一致）
- 取消后**不得推送 `done` 事件**（连接已断开，推送无意义）
- 取消后**不得推送 `error` 事件**（用户主动取消不是错误）
- 取消后**不得触发 LocalRule 降级**（取消即终止，不重试）
- 取消时**已累积的 partial_text 直接丢弃**，不持久化

**客户端断开 vs 用户取消的区别**：
- 用户取消：前端显式调用 `AbortController.abort()`，可显示"已取消"提示
- 客户端断开：网络中断或页面卸载，前端无法显示提示，服务端通过 `is_disconnected()` 检测

两者在服务端处理上等价（都不保存、都终止流式），仅前端 UX 不同。

### 3.4 分段 db session（复用 SPEC 0018/0019/0020/0021 模式 + Phase 3 状态复核）

- **Phase 1**：校验项目状态 + 校验 AnalysisPlan 已确认 + 取分析方案内容 + 记录 AnalysisPlan 版本号 `plan.updated_at`（持有 db）→ `db.close()`
- **Phase 2**：流式生成（不持有 db）
- **Phase 3**：完成后重新打开 db → **重新校验 AnalysisPlan 状态**（见 §3.4.1）→ 保存 CodeTask → `db2.close()`

#### 3.4.1 Phase 3 保存前状态复核（评审反馈六）

LLM 生成可能持续 3-10s，期间 AnalysisPlan 可能被修改、删除、重新生成或变为非 CONFIRMED 状态。Phase 3 保存前必须重新校验：

| 复核项 | 失败时行为 |
| --- | --- |
| 项目仍然存在 | 推送 `error` 事件（`PROJECT_NOT_FOUND`），放弃保存 |
| AnalysisPlan 仍然存在 | 推送 `error` 事件（`ANALYSIS_PLAN_NOT_FOUND`），放弃保存 |
| AnalysisPlan 状态仍为 `CONFIRMED` | 推送 `error` 事件（`ANALYSIS_PLAN_STATUS_CHANGED`），放弃保存 |
| AnalysisPlan 的 `updated_at` 与 Phase 1 读取时一致 | 推送 `error` 事件（`ANALYSIS_PLAN_MODIFIED`），放弃保存 |
| 项目当前状态允许创建代码任务 | 推送 `error` 事件（`PROJECT_STATE_INVALID`），放弃保存 |

**复核失败后的处理**：
- 已生成的代码内容作为 `partial_text` 推送 `error` 事件
- **不得保存 CodeTask 记录**（避免基于过期分析方案生成代码任务）
- 日志记录复核失败原因和当前 AnalysisPlan 状态（见 §3.8）

**与 SPEC 0021 的差异**：SPEC 0021 Phase 3 只校验项目状态，SPEC 0022 额外校验 AnalysisPlan 版本一致性，因为代码任务强依赖 AnalysisPlan 内容。

### 3.5 前端展示设计（评审反馈一：方案 A 低风险）

**方案选择：方案 A — 流式阶段展示模型原始输出，完成后解析展示 code**

#### 3.5.1 问题背景

SSE 推送的是模型生成的原始 JSON 文本，例如：

```text
event: chunk
data: {"text": "{\"code\":\"import pandas"}
```

如果前端直接累积 chunk 并渲染到 `<pre><code>`，用户看到的将是带有 `{"code":"`、转义换行 `\n`、转义引号 `\"` 的 JSON 文本，而不是正常格式的 Python 代码。

#### 3.5.2 方案 A 实现

| 阶段 | 展示内容 | 数据来源 |
| --- | --- | --- |
| 流式中（chunk 累积） | 模型原始输出（JSON 文本，含转义字符） | `chunks` 状态累积 |
| 流式完成（done 事件后） | 解析后的 `code` 字段（正常 Python 代码） | `result.code` |
| 流式失败（error 事件后） | 错误提示 + partial_text（如有） | `error.partial_text` |

**前端状态机**：

```typescript
type StreamPhase = "idle" | "streaming" | "done" | "error";

// streaming 阶段：展示 chunks（原始 JSON 文本）
// done 阶段：切换到展示 result.code（解析后代码）
// error 阶段：展示 error.message + partial_text
```

**渲染策略**：
- `streaming` 阶段：`<pre><code>{chunks}</code></pre>`（原始文本，可能含 JSON 转义）
- `done` 阶段：`<pre><code>{result.code}</code></pre>`（正常代码格式）
- 切换时使用 React `key` 强制重新挂载，避免文本残留

**需求描述调整**：
- ❌ 原："实时逐行显示代码"
- ✅ 新："实时显示模型生成内容，完成后切换为格式化代码展示"

#### 3.5.3 方案 A 的优势与限制

**优势**：
- 实现简单、稳定，不需要编写增量 JSON 解析器
- 与 SPEC 0018/0019/0020/0021 完全一致（都是累积原始文本，完成后解析）
- 回归风险最低

**限制**：
- 流式阶段用户看到的是 JSON 文本而非纯代码（可接受，因为用户能感知"正在生成"）
- 未来如需"逐行代码"体验，可升级到方案 B（`code_chunk` 事件 + 增量 JSON 解析器），但本次切片不实现

#### 3.5.4 不引入语法高亮库

- 使用 `<pre><code>` 纯文本展示，保持代码格式（缩进、换行）
- 不引入 Prism.js / highlight.js 等高亮库（增加打包体积，本切片范围外）
- 高亮留待后续优化切片

### 3.6 SSE 运行环境要求（评审反馈七）

#### 3.6.1 响应头要求

SSE 端点必须设置以下响应头：

```text
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no    # 禁止 Nginx 缓冲（关键）
```

#### 3.6.2 部署链路验证要求

如果部署环境包含 Nginx、网关或反向代理，必须验证：

| 验证项 | 要求 | 验证方式 |
| --- | --- | --- |
| 代理缓冲 | 禁止代理缓冲 SSE 响应 | Nginx 配置 `proxy_buffering off` 或 `X-Accel-Buffering: no` |
| 响应压缩 | 确认压缩不影响流式刷新（或关闭压缩） | Nginx `gzip off` for SSE 路径 |
| 超时时间 | 大于最大 LLM 生成时长（建议 ≥ 120s） | Nginx `proxy_read_timeout 120s` |
| Chunk 刷新 | Chunk 能够及时刷新到浏览器 | 浏览器验收观察 chunk 实时性 |
| Heartbeat | 如代理需要保活，可每 15s 发送 `: ping\n\n` 注释行 | 复用 SPEC 0018 heartbeat 模式（如已实现） |
| 客户端断开传递 | 客户端断开能及时传递到应用服务 | 通过 §3.3.1 `is_disconnected()` 检测 |

#### 3.6.3 浏览器验收要求

- 本地开发环境验收（Vite dev server，无代理）
- **实际部署链路验收**（至少一次）：通过 Docker Compose 或生产环境验证 SSE 流式刷新正常
- 验收记录保存截图 + 部署环境版本号

### 3.7 并发与重复生成策略（评审反馈四）

#### 3.7.1 前端防护

| 防护点 | 实现 |
| --- | --- |
| 流式生成期间禁用重复点击 | `streaming === true` 时按钮 `disabled` |
| 同一页面只允许一个活动请求 | `useStreamGenerateCodeTask` hook 单例，新请求前 `cancel()` 旧请求 |
| 页面卸载取消旧请求 | `useEffect` cleanup 中调用 `cancel()` |
| 重新生成前取消旧请求 | 点击"重新生成"时先 `cancel()` 再 `start()` |

#### 3.7.2 服务端并发保护

**问题**：仅依赖前端禁用按钮不能完全防止多标签页、重复请求或接口直接调用。

**方案**：服务端在 Phase 1 校验时检查是否存在活动流式请求。

| 检查项 | 实现 | 冲突时行为 |
| --- | --- | --- |
| 同一 AnalysisPlan 是否已有活动流式请求 | 内存中的 `active_streams: dict[plan_id, str]`（请求 ID） | 返回 409 `STREAM_ALREADY_ACTIVE`（流前错误，见 §3.2.1） |
| 活动请求超时自动清理 | 请求完成或断开后从 `active_streams` 移除；超时 120s 自动清理 | 防止异常退出导致永久占用 |

**与 SPEC 0021 的差异**：SPEC 0021 未实现服务端并发保护（分析方案生成允许多候选）。SPEC 0022 引入并发保护，因为代码任务生成成本更高（3-10s LLM 调用），重复生成浪费资源。

**允许并发的场景**：
- 同一项目不同 AnalysisPlan 可并发流式生成（不同 plan_id 不冲突）
- 同一 AnalysisPlan 流式完成后可立即重新生成（旧请求已清理）

#### 3.7.3 多候选策略

- 允许同一 AnalysisPlan 生成多个 CodeTask 候选（重新生成时旧的变 STALE，与现有同步路径一致）
- 但**同一时刻只允许一个活动流式请求**（见 §3.7.2）
- 候选列表按 `created_at` 倒序展示

### 3.8 可观测性要求（评审反馈八）

#### 3.8.1 日志指标清单

每次流式生成必须记录以下指标（结构化日志）：

| 指标 | 说明 | 示例 |
| --- | --- | --- |
| `request_id` | 请求唯一标识（UUID） | `req_abc123` |
| `project_id` | 项目 ID | `proj_001` |
| `analysis_plan_id` | 分析方案 ID | `plan_001` |
| `start_time` | 请求开始时间（ISO 8601） | `2026-07-27T10:00:00Z` |
| `first_chunk_latency_ms` | 首 chunk 延迟（毫秒） | `850` |
| `total_duration_ms` | 总生成耗时（毫秒） | `5230` |
| `chunk_count` | chunk 数量 | `42` |
| `output_length` | 完整输出长度（字符数） | `1856` |
| `fallback_used` | 是否触发 LocalRule 降级 | `false` |
| `cancel_reason` | 取消原因（`USER_CANCELLED` / `CLIENT_DISCONNECTED` / `null`） | `null` |
| `json_validation_failed` | 是否发生 JSON 校验失败 | `false` |
| `phase3_validation_failed` | 是否触发 Phase 3 状态复核失败 | `false` |
| `saved` | 是否成功保存 CodeTask | `true` |
| `code_task_id` | 保存的 CodeTask ID（如成功） | `ct_001` |
| `error_code` | 错误码（如失败） | `null` |
| `provider_source` | Provider 来源（`DEEPSEEK` / `LOCAL_RULE`） | `DEEPSEEK` |

#### 3.8.2 日志脱敏要求

- **不得记录完整生成代码**（避免日志过大或包含数据内容）
- **不得记录 AnalysisPlan 完整内容**（仅记录 `plan_id`）
- **不得记录 LLM 请求/响应原始 payload**
- 错误堆栈可记录，但需脱敏 API Key 等敏感信息

#### 3.8.3 指标聚合（可选，留待后续优化）

- 首 chunk 延迟 P50/P95
- 总生成耗时 P50/P95
- 降级率（fallback_used / total）
- 取消率（cancelled / total）
- JSON 校验失败率
- Phase 3 复核失败率

本切片不实现指标聚合，仅记录结构化日志，留待后续监控切片。

---

## 四、关键调研结论

### 4.1 当前实现路径

- **API 端点**：`POST /api/projects/{project_id}/analysis/{plan_id}/code/generate`（`server/app/api/routers/code_tasks.py:L52-L59`）
- **Worker handler**：`handle_generate_code_task`（`server/worker/handlers.py:L350-L409`）
- **Service 层**：`generate_code_task`（`server/app/modules/execution/service.py:L191-L228`），创建 Job
- **Provider 接口**：`generate(analysis_plan, dataset_profile=None)` → `DeepSeekCodeTaskResponse`（`server/app/modules/llm/deepseek_code_task_provider.py:L89-L106`）
- **Provider 输入**：`analysis_plan`（已确认的分析方案 dict）+ 可选 `dataset_profile`，**不跨模块聚合**
- **产出类型**：`CodeTaskDraft`（`code_task_provider.py:L20`，dataclass，含 `code: str` 字段）；`DeepSeekCodeTaskResponse`（`deepseek_code_task_provider.py:L30`）是 DeepSeek provider 内部用于校验 LLM 返回 JSON 的 Pydantic 模型，最终产出仍为 `CodeTaskDraft`
- **数据库模型**：`CodeTask`（`server/app/modules/execution/models.py:L23`），状态机 CANDIDATE/CONFIRMED/REJECTED/STALE
- **前端**：`generateCodeTask`（`apps/web/src/features/execution/api.ts:L37`），调用 API + 轮询 job 状态
- **执行关系**：确认后通过 `execute_code_task` → `ExecutionRun` → `handle_execute_code_task` 实际执行

### 4.2 流式化复杂度评估

- **Provider 输入**：`analysis_plan`（已确认），不跨模块聚合 → **比大纲简单**
- **产出形式**：单个 JSON 对象（含 code 字段）→ **与 SPEC 0019 一致**
- **Worker handler**：已极简，无需提取共享方法
- **降级路径**：LocalRule provider 已存在（`server/app/modules/llm/code_task_provider.py`），可直接复用
- **前置条件**：需要 AnalysisPlan 状态为 CONFIRMED（与当前同步路径一致）

### 4.3 Provider/Service/API/Hook 接口合同（评审反馈五）

#### 4.3.1 方法签名

**DeepSeekCodeTaskProvider 流式接口**：

```python
async def stream_generate(
    self,
    analysis_plan: dict,
    dataset_profile: dict | None = None,
) -> AsyncIterator[str]:
    """
    流式生成代码任务，逐 chunk yield 原始文本（不解析 JSON）。
    复用 DeepSeekClient.stream_chat_completion()。
    失败时抛出异常，由 Service 层捕获并决定降级。
    """
    ...
```

**LocalRuleCodeTaskProvider 流式接口**（降级路径，必须实现相同接口）：

```python
async def stream_generate(
    self,
    analysis_plan: dict,
    dataset_profile: dict | None = None,
) -> AsyncIterator[str]:
    """
    LocalRule 降级流式：同步生成完整 JSON 后，拆分为多 chunk yield 模拟流式。
    复用现有 generate() 逻辑，仅包装为异步迭代器。
    """
    ...
```

**Service 层流式接口**：

```python
async def stream_generate_code_task(
    db: Session,
    request: Request,
    project_id: str,
    plan_id: str,
) -> AsyncIterator[StreamCodeTaskEvent]:
    """
    流式生成代码任务，yield StreamCodeTaskEvent（chunk/done/error）。
    负责：业务校验、降级判断、JSON 解析、CodeTask 保存、状态复核。
    """
    ...
```

**API 层 SSE 端点**：

```python
@router.post("/analysis/{plan_id}/code/stream-generate")
async def stream_generate_code_task(
    project_id: str,
    plan_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    SSE 端点，只做协议转换。返回 StreamingResponse(media_type="text/event-stream")。
    不持有业务状态，不直接调用 Provider。
    """
    ...
```

#### 4.3.2 职责单一约定（评审反馈五）

| 层 | 职责 | 禁止 |
| --- | --- | --- |
| Provider | 生成内容（流式 yield 原始 chunk）；不累积、不解析、不保存 | 不得做业务校验；不得保存数据库；不得构造 `candidate_source` |
| Service | 业务校验（Phase 1/3）；降级判断；累积完整文本；JSON 解析；`CodeTaskDraft` 校验；构造 `candidate_source` 和 `fallback_used`；保存 CodeTask | 不得直接调用 LLM SDK；不得做 HTTP 协议转换 |
| API | SSE 协议转换（StreamingResponse + 事件序列化）；流前 HTTP 错误返回 | 不得持有业务状态；不得直接调用 Provider |
| 前端 Hook | 请求状态管理；AbortSignal 生命周期；缓存刷新（invalidate） | 不得解析 SSE 事件格式（由 streamSSE 负责）；不得做业务校验 |

#### 4.3.3 兼容性约定

- **同步 `generate()` 保留**：DeepSeekCodeTaskProvider 和 LocalRuleCodeTaskProvider 的同步 `generate()` 方法保留不变，供 Worker 异步路径调用
- **流式兼容同步 Provider**：如果某 Provider 只实现 `generate()` 未实现 `stream_generate()`，Service 层应检测并降级为"同步生成后拆分多 chunk"（与 LocalRule 降级路径一致）
- **LocalRule 必须实现 `stream_generate()`**：作为降级路径，必须与 DeepSeek provider 接口一致

---

## 五、测试策略（评审反馈九：场景驱动，取消精确数量）

### 5.1 后端测试（新增不少于 35 个测试，覆盖以下场景）

| 测试文件 | 必须覆盖场景 |
| --- | --- |
| `test_deepseek_code_task_provider_stream.py` | stream_generate 成功 / 首 chunk 前失败抛异常 / 中途失败抛异常 / source_label 正确 / dataset_profile 可选参数 / LocalRule provider stream_generate 接口一致 |
| `test_code_task_service_stream.py` | 成功保存 CodeTask / 中途失败不保存 / JSON 校验失败不保存 / 兼容只实现 generate() 的 Provider / AnalysisPlan 未确认校验 / Phase 3 状态复核成功 / Phase 3 状态复核失败（项目删除/plan 删除/状态变化/版本变化）/ 客户端断开不保存 / 用户取消不保存 / 首 chunk 前降级 / candidate_source 构造 / fallback_used 构造 |
| `test_code_task_stream_api.py` | SSE 端点响应头正确 / 事件格式正确 / done 事件 code_task_id / 流前 404 错误 / 流前 409 错误（未确认）/ 流前 422 错误（参数非法）/ 流前 409 错误（并发冲突）/ error 事件后无 done / 原同步端点零回归 / Worker handler 零回归 |
| `test_local_rule_code_task_provider_format.py`（新增，参考 SPEC 0021 收口经验） | LocalRule 输出 CodeTaskDraft.code 为字符串 / code 内容可编译为合法 Python / target_fields 类型容错（字符串/数组/null）/ 不因 AnalysisPlan 字段类型异常崩溃 |

### 5.2 前端测试（新增不少于 26 个测试，覆盖以下场景）

| 测试文件 | 必须覆盖场景 |
| --- | --- |
| `api-stream.test.ts` | URL 构造 / POST 方法 / streamSSE 调用 / AbortSignal 传递 / HTTP 错误处理 / 流前错误状态码 |
| `hooks-stream.test.tsx` | streaming 状态管理 / done 后 invalidate queries / AbortSignal 生命周期 / AbortError 静默处理 / 页面卸载 cancel / 重新生成 cancel 旧请求 / streaming 期间禁用按钮 |
| `ExecutionWorkspaceView.test.tsx`（扩展） | 流式按钮显示 / chunk 展示（原始 JSON 文本）/ done 后切换为 code 展示 / 取消按钮触发 cancel / 完成提示显示 candidate_source / 错误详情含 partial_text / streaming 期间禁用重复点击 |

### 5.3 回归测试

- Worker handler 零改动（`git diff server/worker/handlers.py` 无变化）
- 原同步端点 `POST /code/generate` 零回归
- 代码执行链路零回归（`execute_code_task` → `ExecutionRun` 不受影响）
- LocalRule code task provider 输出格式校验（参考 SPEC 0021 收口经验，避免类型不一致问题）

---

## 六、验收标准（评审反馈九：关键 AC 逐条展开）

### 6.1 关键验收项（必须逐条通过，共 15 项）

| AC | 验收项 | 验证方式 |
| --- | --- | --- |
| AC-1 | 首 chunk 前失败允许降级到 LocalRule | 后端测试 + 浏览器验收 |
| AC-2 | 已发送 chunk 后失败不得再降级（保留 partial_text + 推送 error） | 后端测试 |
| AC-3 | 中途失败不得保存 CodeTask | 后端测试 + 数据库验证 |
| AC-4 | JSON 校验失败不得保存 CodeTask | 后端测试 + 数据库验证 |
| AC-5 | 用户取消不得保存 CodeTask | 后端测试 + 前端测试 |
| AC-6 | 客户端断开不得保存 CodeTask | 后端测试（模拟 is_disconnected） |
| AC-7 | `done` 必须是成功流的最后一个事件 | 后端测试 + 前端测试 |
| AC-8 | `error` 后不得发送 `done` | 后端测试 |
| AC-9 | 单个请求只能保存一个 CodeTask（并发保护） | 后端测试 + 并发场景测试 |
| AC-10 | 保存前重新校验 AnalysisPlan 状态（Phase 3 复核） | 后端测试（5 种失败场景） |
| AC-11 | 原 Worker handler 保持零改动 | `git diff server/worker/handlers.py` 无变化 |
| AC-12 | 原 `/code/generate` 端点回归通过 | 后端测试 |
| AC-13 | 代码执行链路回归通过（`execute_code_task` → `ExecutionRun`） | 后端测试 |
| AC-14 | 不产生 Alembic 变更 | `git diff server/alembic/versions/` 无变化 |
| AC-15 | 不引入新依赖 | `git diff server/pyproject.toml apps/web/package.json` 无新增依赖 |

### 6.2 完整 AC 范围（预期 ~50 项，含上述 15 项关键 + 其他场景覆盖）

| AC 范围 | 内容 |
| --- | --- |
| AC-1~15 | 关键验收项（见 §6.1） |
| AC-16~22 | Provider 流式调用（成功 / 首 chunk 前降级 / 中途失败 / source_label / dataset_profile 可选 / LocalRule 接口一致） |
| AC-23~32 | Service 流式调用（成功保存 / 中途失败不保存 / JSON 校验失败 / AnalysisPlan 未确认校验 / Phase 3 状态复核 5 种场景 / 客户端断开 / 用户取消 / 兼容 LocalRule） |
| AC-33~42 | API SSE 端点（响应头正确 / 事件格式 / done 事件 / 流前 404/409/422 错误 / error 后无 done / 原同步端点零回归 / Worker handler 零回归） |
| AC-43~48 | 前端流式解析（API / Hook 状态 / UI 流式展示含 `<pre><code>` / streaming 阶段展示原始 JSON / done 后切换为 code 展示 / 取消按钮） |
| AC-49~50 | 测试通过（后端 ~930 + 前端 ~577 + lint + build）+ owner 边界 |
| AC-51~53 | 浏览器验收（本地 + 部署链路）/ 文档回写 / 版本收口 |

---

## 七、风险评估（评审反馈补充新风险）

| 风险 | 概率 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| Provider `generate()` 接口与流式不兼容 | 低 | 中 | 调研确认 `generate(analysis_plan)` 是同步方法，可改造为 `stream_generate()` |
| `CodeTaskDraft` 序列化问题 | 低 | 低 | 是 dataclass，含单个 `code: str` 字段，序列化简单 |
| AnalysisPlan 未确认状态校验遗漏 | 中 | 中 | Phase 1 必须校验 AnalysisPlan.status == CONFIRMED |
| 代码内容中的特殊字符（引号、换行）破坏 JSON | 中 | 中 | LLM 返回的 JSON 中 code 字段已转义，JSON 校验会捕获 |
| 前端代码展示格式问题 | 低 | 低 | 使用 `<pre><code>` 保持格式，不引入高亮库 |
| **partial JSON chunk 解析失败**（新增） | 中 | 中 | chunk 阶段只做字符串累积，不解析；done 阶段才 `JSON.parse()`；与 SPEC 0021 一致 |
| **客户端断开检测延迟**（新增） | 中 | 中 | `is_disconnected()` 在 chunk 之间轮询，延迟 ≤ 单 chunk 生成时间（通常 < 1s）；超时 120s 强制清理 |
| **并发保护误判**（新增） | 低 | 中 | `active_streams` 超时自动清理（120s）；请求完成立即移除；测试覆盖异常退出场景 |
| **Phase 3 状态复核误判**（新增） | 低 | 中 | 仅校验 `updated_at` 一致性，不校验内容哈希；测试覆盖 5 种失败场景 |
| **Nginx 代理缓冲 SSE**（新增） | 中 | 高 | 响应头设置 `X-Accel-Buffering: no`；部署链路验收必须验证 |
| **日志泄露代码内容**（新增） | 低 | 中 | §3.8.2 明确不得记录完整代码；Code Review 检查日志语句 |

---

## 八、前置依赖

SPEC 0022 依赖于 SPEC 0021 的完成（**前置依赖已满足**，SPEC 0021 已于 2026-07-26 收口为 v2.3.0）：
- 代码任务生成的输入是已确认的 `AnalysisPlan`，SPEC 0021 已实现分析方案的流式生成与确认路径
- AnalysisPlan 的同步生成路径仍然可用作为兜底，本切片实现不受阻塞

**收口策略决策（2026-07-27 同步）：**

SPEC 0021 已按"分两次收口"策略独立收口为 v2.3.0（commit `9f7d274` + follow-up `7fccb90`，含 PlanCard 容错修复）。原草案中"合并 vs 分两次收口"的讨论已收敛为**分两次收口**：

- ✅ SPEC 0021 → v2.3.0（已完成）
- ⏳ SPEC 0022 → v2.4.0（本切片，独立 commit，独立 tag）

分次收口的优势在 SPEC 0021 实施过程中得到验证：
- 收口复核能聚焦单一切片，PlanCard 阻断问题在 SPEC 0021 收口阶段即被捕获并修复，未流入 SPEC 0022 范围
- 每次收口范围更小，回滚成本更低
- 可根据前一切片的实际情况调整后继切片设计（如 SPEC 0022 草案 0.2 即基于 SPEC 0021 收口经验同步）
