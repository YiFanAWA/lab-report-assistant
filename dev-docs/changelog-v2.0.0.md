# V2.0.0 变更日志

> **发布日期：** 2026-07-25
> **版本：** v2.0.0
> **上一版本：** v1.4.0（SPEC 0017 单用户前端实时编辑反馈）
> **本版切片：** SPEC 0018 流式 LLM 输出（任务单生成 SSE 流式化）
> **commit：** 待提交后补全
> **tag：** v2.0.0

---

## 一、本版核心变更

### SPEC 0018：流式 LLM 输出（任务单生成 SSE 流式化）

**痛点**：V1.4.0 之前，用户点击"生成任务单"后需同步等待后端 LLM 调用 5-15s，期间 UI 无任何进度反馈，且无法中途取消。LLM 生成完成后整个 JSON 一次性返回，缺乏"AI 正在思考"的实时感。

**解决方案**：将"任务单生成"这一 LLM 调用从同步阻塞改造为 SSE（Server-Sent Events）流式输出，让用户在前端实时看到 LLM 逐 chunk 生成的任务单 JSON，并支持中途取消。

**架构选择**：
- 后端使用 `fastapi.responses.StreamingResponse` 推送 SSE 事件
- 前端使用 `fetch + ReadableStream` 原生解析（不引入 EventSource，以支持 POST + body）
- 不引入 WebSocket / 长轮询基础设施
- 保留原同步端点 `POST /plans/generate` 兼容性，新增 `POST /plans/stream-generate` SSE 端点

**降级策略**：
- 首 chunk 前失败：降级到 `LocalRuleRequirementDraftProvider`（拆分多 chunk 模拟流式）
- 中途失败：保留已生成 chunk + 推送 `error` 事件（不保存 RequirementPlan、不写入 LLM 缓存）
- 网络异常：前端映射为 `STREAM_NETWORK_ERROR`，保留 `partial_text`

**分段持有 db session**：
- Phase 1：校验（持有 db）→ Phase 2：流式生成（关闭 db，不持有连接）→ Phase 3：完成后重新打开 db 保存
- 避免 SQLite 写锁长时间阻塞其他请求

**缓存策略**：
- 流式与同步共享 SPEC 0014 LLM 缓存
- 缓存命中时一次性 yield 完整字符串（前端快速完成）
- 流式完成后写入缓存；中途失败不写入

---

## 二、新增功能

### 2.1 后端流式 LLM 调用

| 文件 | 变更 |
| --- | --- |
| `server/app/infrastructure/llm/deepseek_client.py` | 新增 `stream_chat_completion()` 生成器方法：缓存查询（命中一次性 yield）、HTTP 流式调用（`httpx.Client.stream()`）、SSE 行解析、错误映射、完成后写缓存 |
| `server/app/modules/llm/deepseek_requirement_provider.py` | 新增 `stream_draft()` 生成器方法：调用 `stream_chat_completion`、首 chunk 前失败降级到 LocalRule（拆分多 chunk 模拟流式）、中途失败抛异常、完成后校验 JSON |
| `server/app/modules/requirements/service.py` | 新增 `StreamChunkEvent` / `StreamDoneEvent` / `StreamErrorEvent` 类型；新增 `stream_generate_plan()` 生成器方法：分段持有 db session（Phase 1 校验 → Phase 2 流式 → Phase 3 保存）、兼容 LocalRule provider（一次性 yield）、失败推送 error 事件 |
| `server/app/api/routers/requirements.py` | 新增 `POST /plans/stream-generate` SSE 端点（`StreamingResponse` + `text/event-stream`）；新增 `_serialize_sse_event()` 辅助函数（chunk/done/error 事件序列化） |

### 2.2 前端流式展示

| 文件 | 变更 |
| --- | --- |
| `apps/web/src/shared/stream-sse.ts`（新建） | 通用 SSE 解析工具：`streamSSE()` 异步生成器，使用 `fetch + ReadableStream` 解析 SSE 文本块；处理 `event:` / `data:` 行、注释行、多行 data 拼接、跨 chunk 不完整块拼接；HTTP 错误透传后端结构化错误 |
| `apps/web/src/features/requirements/api.ts` | 新增 `streamGeneratePlan()` 异步生成器，委托给 `streamSSE` |
| `apps/web/src/features/requirements/hooks.ts` | 新增 `useStreamGeneratePlan` hook：管理 `streaming` / `chunks` / `result` / `error` 状态；`start(sourceId)` 建立连接逐 chunk 累积；`cancel()` 通过 AbortController 中断；`reset()` 重置状态；done 事件后 `invalidateQueries` 刷新任务单 |
| `apps/web/src/routes/RequirementWorkspaceView.tsx` | UI 改造：新增"流式生成任务单"按钮（与原"生成任务单候选"并列）；流式展示区（带边框灰色背景 + "取消"按钮 + `<pre>` chunk 累积 + 等宽字体）；完成提示"流式生成完成 ✓ [源]"；错误展示 + 降级标记 |

### 2.3 SSE 事件合同

```text
event: chunk
data: {"text": "实验"}

event: chunk
data: {"text": "目的"}

event: done
data: {"plan_id": "plan_xxx", "candidate_source": "DEEPSEEK", "fallback_used": false}

event: error
data: {"error_code": "DEEPSEEK_TIMEOUT", "message": "流式请求超时", "partial_text": "实验目的..."}
```

---

## 三、测试覆盖

### 3.1 后端新增测试（47 个）

| 测试文件 | 测试数 | 覆盖点 |
| --- | --- | --- |
| `tests/test_deepseek_client_stream.py` | 18 | 流式成功 / 缓存命中一次性 yield / 缓存写入 / 首 chunk 前失败抛 DeepSeekError / 中途失败已 yield chunk 不写缓存 / HTTP 状态码映射（401/403/429/500） |
| `tests/test_deepseek_requirement_provider_stream.py` | 7 | stream_draft 成功 / 首 chunk 前降级到 LocalRule（拆分多 chunk）/ 中途失败抛异常 / JSON 校验 |
| `tests/test_requirements_service_stream.py` | 11 | stream_generate_plan 成功（保存 + StreamDoneEvent）/ 中途失败（StreamErrorEvent + 不保存）/ 兼容 LocalRule provider / 分段 db session |
| `tests/test_requirements_stream_api.py` | 11 | SSE 端点返回 text/event-stream / 事件格式正确 / source_id 无效返回 404 / project_id 无效返回 404 |

**后端总计**：736 → 783 passed（+47），0 warnings。

### 3.2 前端新增测试（34 个）

| 测试文件 | 测试数 | 覆盖点 |
| --- | --- | --- |
| `src/shared/__tests__/stream-sse.test.ts` | 18 | 单事件块 / 多事件块 / 跨 chunk 拼接 / 默认 message 事件 / 多行 data 拼接 / 注释行跳过 / 空行跳过 / 冒号后空格剥离（SSE 规范）/ 尾部不完整块 / 空 body / POST+JSON body / AbortSignal 传递 / HTTP 4xx 5xx 透传 / fetch reject / 空响应体 |
| `src/features/requirements/__tests__/api-stream.test.ts` | 6 | 正确 URL / POST 方法 / 请求体 / URL 编码 / 委托 streamSSE 解析 / AbortSignal / HTTP 错误透传 |
| `src/features/requirements/__tests__/hooks-stream.test.tsx` | 10 | chunk 累积 / done 事件设置 result 并清空 chunks + invalidate / start 重置旧状态 / error 事件保留 partial_text / 非 AbortError 映射 STREAM_NETWORK_ERROR / AbortError 不设 error / cancel 通过 AbortSignal 中断 / reset 重置 / 初始状态正确 |

**前端总计**：434 → 468 passed（+34）。

### 3.3 现有测试零回归

- 原同步端点 `POST /plans/generate` 测试全部通过（test_requirement_api.py 6 + test_requirement_service.py 12）
- 所有现有前端组件测试通过（含 RequirementWorkspaceView 35 个测试，已更新 mock 适配 useStreamGeneratePlan）

---

## 四、验收证据

| 验收项 | 命令 | 结果 |
| --- | --- | --- |
| 后端测试 | `.venv\Scripts\python.exe -m pytest` | 783 passed, 0 warnings |
| 前端测试 | `npm test -- --run` | 468 passed |
| TypeScript 类型检查 | `npm run lint` | tsc --noEmit 通过 |
| Vite 构建 | `npm run build` | 115 模块, dist/ 400.27 kB, gzip 109.09 kB |
| Alembic 迁移 | `alembic upgrade head` | 无变化（无新增迁移） |
| 浏览器验收 | browser_use agent | PASS（流式展示区 + 取消按钮 + chunk 累积 + 完成提示） |

---

## 五、约束遵守

- ✅ 不引入新依赖（httpx `client.stream()` + 浏览器原生 `fetch + ReadableStream`）
- ✅ 不修改数据库 schema（无新增 Alembic 迁移）
- ✅ 不破坏原同步端点（`POST /plans/generate` 保留不变）
- ✅ 不引入 WebSocket / 长轮询基础设施
- ✅ 不违反 SPEC 0017 范围（SSE 是单用户 LLM 流式输出，非多用户协作）
- ✅ 不破坏 owner 边界（API 只做协议映射，业务在 service 层）
- ✅ 复用 SPEC 0014 LLM 缓存（流式与同步共享缓存）

---

## 六、已知债务

- **TD-009**（延续，非阻断）：浏览器验收截图未持久化到磁盘（browser_take_screenshot 工具限制）。SPEC 0018 浏览器验收结论为 PASS，但截图未保存到 `dev-docs/e2e-screenshots/spec-0018/`。后续修复入口：评估 puppeteer 等替代工具。

---

## 七、升级指南

### 7.1 无破坏性变更

V2.0.0 是**向后兼容**的版本：
- 原同步端点 `POST /plans/generate` 保留不变，现有脚本和测试不受影响
- 数据库 schema 无变化，无需运行迁移
- 无新增依赖，无需 `pip install` 或 `npm install`

### 7.2 使用流式生成

前端用户现在有两个按钮：
- **"生成任务单候选"**：原同步行为（等待 5-15s 后一次性显示）
- **"流式生成任务单"**（新增）：实时显示 LLM 逐 chunk 生成内容，支持中途取消

### 7.3 配置

无需新增环境变量。流式生成复用现有配置：
- `DEEPSEEK_API_KEY`：未配置时自动降级到 LocalRule provider（流式拆分多 chunk 模拟）
- `LLM_CACHE_ENABLED`：缓存命中时一次性 yield 完整字符串（快速完成）

---

## 八、下一阶段方向

V2.0.0 SPEC 0018 已收口。下一阶段方向待项目负责人规划。候选方向：

- **V2.1 SPEC 0019**：大纲生成流式化。采用"新增 SSE 端点绕过 Worker"方案（本切片已确认 V2.1 备选方向）。
- **V2.1+**：证据卡片 / 分析方案 / 代码任务流式化。
- TD-009 浏览器验收截图持久化修复。

上述方向均需先编写并确认对应 SPEC，不得直接进入实现。
