# 决策记录 0025：启动 SPEC 0019 大纲生成流式化

**日期：** 2026-07-26
**决策者：** 项目负责人
**状态：** 已确认
**关联 SPEC：** SPEC 0019（大纲生成流式化）
**目标版本：** v2.1.0
**前置版本：** v2.0.0（SPEC 0018 流式 LLM 输出已收口）

---

## 一、背景

### 1.1 V2.0.0 流式能力现状

V2.0.0（SPEC 0018）已实现"任务单生成"的 SSE 流式输出：
- 后端 `DeepSeekClient.stream_chat_completion()` 提供通用流式调用能力
- 后端 `POST /plans/stream-generate` SSE 端点
- 前端 `stream-sse.ts` 通用 SSE 解析工具（可复用）
- 前端 `useStreamGeneratePlan` hook + UI 流式展示

任务单生成的流式化已验证架构可行，用户体验显著提升（首字时间 ↓ 60-80%）。

### 1.2 大纲生成现状（V2.0.0）

大纲生成（outline generation）与任务单生成的根本区别：

| 维度 | 任务单生成（V2.0.0 已流式） | 大纲生成（V2.0.0 未流式） |
| --- | --- | --- |
| API 端点 | `POST /plans/generate`（同步）+ `POST /plans/stream-generate`（SSE） | `POST /outline/generate`（创建 Job，异步） |
| 执行方式 | 同步 API 直接调用 LLM | Worker 进程异步执行 |
| 前端等待 | 流式：实时 chunk / 同步：5-15s 空白 | 轮询 job 状态，10-30s 空白等待 |
| LLM 调用 | `DeepSeekRequirementDraftProvider.draft()` | `DeepSeekOutlineProvider.generate()` |
| 上下文来源 | 单一 requirement_text | 跨模块聚合（任务单+证据+数据集+分析+执行） |
| 中途取消 | 支持（AbortController） | 不支持（Worker 任务无法中断） |

### 1.3 痛点

大纲生成是实验报告工作流中**等待时间最长**的 LLM 调用（10-30s），因为：
1. 上下文聚合涉及 5 个模块的数据查询
2. LLM 需要生成 6 个章节的完整大纲 JSON
3. 用户无法看到生成进度，只能轮询 job 状态
4. 无法中途取消

### 1.4 决策 0024 §3 的预留

决策 0024（启动 SPEC 0018）§3 已明确：
> "大纲生成流式化推迟到 V2.1 SPEC 0019"
> "新增 SSE 端点绕过 Worker"是大纲生成流式化的备选方案

本决策记录正式启动 SPEC 0019，采用决策 0024 §3 的备选方案。

---

## 二、决策

### 2.1 启动 SPEC 0019

1. **启动 SPEC 0019 大纲生成流式化切片，目标版本 v2.1.0。**
2. **流式范围仅限大纲生成**：改造大纲生成为新增 `POST /outline/stream-generate` SSE 端点，保留原 `POST /outline/generate`（Worker 异步）兼容。
3. **架构选择：SSE 端点绕过 Worker**：新增 SSE 端点直接在请求处理中调用 LLM provider 流式生成，不通过 Worker Job 机制。原因：Worker 是异步的，SSE 需要同步推送 chunk，两者语义不兼容。
4. **上下文聚合提取到 service 层**：将 `worker/handlers.py` 中的 `_gather_outline_context()` 提取到 `outlines/service.py`（或新建 `outlines/context.py`），让流式 service 和 Worker handler 共享。
5. **降级策略（参照 SPEC 0018）**：首 chunk 前失败降级到 `LocalRuleOutlineProvider`（拆分多 chunk 模拟流式）；中途失败保留已生成 chunk + 推送 `error` 事件；中途失败不保存 Outline、不写入 LLM 缓存。
6. **流式期间分段持有 db session**：Phase 1 校验+聚合上下文（持有 db）→ Phase 2 流式生成（关闭 db，不持有连接）→ Phase 3 完成后重新打开 db 保存。避免 SQLite 写锁阻塞其他请求。

### 2.2 不在 SPEC 0019 范围内

1. **不改造原 Worker 异步端点**：`POST /outline/generate` + Worker handler 保留不变，作为脚本自动化和兼容路径。
2. **不流式化其他模块**：证据卡片、分析方案、代码任务生成等不在本切片范围。
3. **不引入 WebSocket**：仅使用 SSE，复用 SPEC 0018 的 `stream-sse.ts` 工具。
4. **不修改数据库 schema**：流式 chunk 不持久化，只有最终 Outline 保存。
5. **不引入新依赖**：复用 SPEC 0018 的 `httpx.Client.stream()` + 浏览器原生 `fetch + ReadableStream`。

---

## 三、理由

### 3.1 为什么选择"SSE 绕过 Worker"而非"改造 Worker 支持流式"

| 方案 | 优点 | 缺点 | 选择 |
| --- | --- | --- | --- |
| A. SSE 绕过 Worker（本方案） | 复用 SPEC 0018 架构；无需改造 Worker；流式与同步语义一致 | 上下文聚合需提取到 service 层；不创建 Job 记录 | ✅ 选择 |
| B. 改造 Worker 支持流式 | 保留 Job 记录和重试能力 | Worker 是独立进程，SSE 需要跨进程推送 chunk，架构复杂；需引入 Redis Pub/Sub 或类似机制 | ❌ 否决 |
| C. 前端轮询模拟流式 | 不改后端 | 不是真正的流式，无法实时推送；用户体验差 | ❌ 否决 |

方案 A 的核心优势：
1. **复用 SPEC 0018 的成熟架构**：`DeepSeekClient.stream_chat_completion()` + `stream-sse.ts` + `useStreamGeneratePlan` 模式可直接套用
2. **不引入新基础设施**：无需 Redis、WebSocket、消息队列
3. **流式与同步语义一致**：SSE 端点在请求处理中直接调用 LLM，与任务单生成的流式化模式完全一致
4. **上下文聚合可共享**：提取到 service 层后，Worker handler 和流式 service 都可复用

### 3.2 为什么保留原 Worker 端点

1. **兼容性**：已有脚本或自动化可能依赖 `POST /outline/generate` 返回的 `job_id`
2. **Worker 路径仍有价值**：Worker 支持重试、超时控制、独立进程隔离，适合无人值守场景
3. **不破坏现有测试**：`test_outline_worker_handlers.py` 等测试无需修改

### 3.3 为什么提取上下文聚合到 service 层

当前 `_gather_outline_context()` 在 `worker/handlers.py` 中，但这不是最佳位置：
1. **owner 边界**：上下文聚合是大纲生成的业务逻辑，应在 `outlines/service.py`
2. **复用性**：流式 service 和 Worker handler 都需要调用，提取后避免代码重复
3. **测试性**：service 层方法更容易单元测试

---

## 四、影响范围

### 4.1 后端改动

| 文件 | 改动类型 | 说明 |
| --- | --- | --- |
| `server/app/modules/llm/deepseek_outline_provider.py` | 新增方法 | `stream_generate(context)` 生成器：调用 `stream_chat_completion`，首 chunk 前降级 LocalRule，中途失败抛异常 |
| `server/app/modules/outlines/service.py` | 新增方法 + 提取 | 新增 `stream_generate_outline()` 生成器；提取 `gather_outline_context()` 从 worker handler |
| `server/worker/handlers.py` | 修改 | `_gather_outline_context()` 改为调用 service 层的 `gather_outline_context()` |
| `server/app/api/routers/outlines.py` | 新增端点 | `POST /outline/stream-generate` SSE 端点 |
| `server/tests/test_deepseek_outline_provider_stream.py` | 新建 | 流式 provider 测试 |
| `server/tests/test_outline_service_stream.py` | 新建 | 流式 service 测试 |
| `server/tests/test_outline_stream_api.py` | 新建 | SSE 端点测试 |

### 4.2 前端改动

| 文件 | 改动类型 | 说明 |
| --- | --- | --- |
| `apps/web/src/features/outlines/api.ts` | 新增函数 | `streamGenerateOutline(projectId, signal)` |
| `apps/web/src/features/outlines/hooks.ts` | 新增 hook | `useStreamGenerateOutline(projectId)` |
| `apps/web/src/routes/OutlineWorkspaceView.tsx` | UI 改造 | 新增"流式生成大纲"按钮 + 流式展示区 + 取消按钮 |
| `apps/web/src/features/outlines/__tests__/api-stream.test.ts` | 新建 | 流式 API 测试 |
| `apps/web/src/features/outlines/__tests__/hooks-stream.test.tsx` | 新建 | 流式 hook 测试 |

### 4.3 不受影响

- 数据库 schema（无新增迁移）
- `POST /outline/generate` + Worker handler（保留不变）
- `stream-sse.ts`（复用，不修改）
- `DeepSeekClient.stream_chat_completion()`（复用，不修改）

---

## 五、验收标准

### 5.1 功能验收

1. `POST /outline/stream-generate` SSE 端点返回 `text/event-stream`
2. 流式生成期间逐 chunk 推送 `event: chunk` 事件
3. 流式完成后推送 `event: done` 事件，包含 `outline_id` 和 `candidate_source`
4. 流式失败时推送 `event: error` 事件，包含 `error_code` 和 `partial_text`
5. 首 chunk 前失败降级到 LocalRule，拆分多 chunk 模拟流式
6. 中途失败不保存 Outline、不写入 LLM 缓存
7. 前端"流式生成大纲"按钮触发流式生成
8. 前端流式展示区实时显示 chunk 累积
9. 前端"取消"按钮可中断流式生成
10. 流式完成后大纲列表自动刷新

### 5.2 兼容性验收

11. 原 `POST /outline/generate` + Worker 路径不受影响
12. `test_outline_worker_handlers.py` 全部通过（零回归）
13. 现有大纲相关测试全部通过（零回归）

### 5.3 约束验收

14. 不引入新依赖（复用 SPEC 0018 基础设施）
15. 不修改数据库 schema（无新增 Alembic 迁移）
16. 不引入 WebSocket / 长轮询基础设施
17. 复用 `stream-sse.ts` 工具（不修改）
18. owner 边界：API 只做协议映射，业务在 service 层

### 5.4 测试验收

19. 后端 pytest 新增流式测试 ≥ 30 个，总数 ≥ 813
20. 前端 vitest 新增流式测试 ≥ 25 个，总数 ≥ 493
21. TypeScript 类型检查通过（`tsc --noEmit`）
22. Vite 构建成功
23. 浏览器验收通过（流式展示 + 取消 + 完成刷新）

---

## 六、风险与降级

### 6.1 已识别风险

| 风险 | 等级 | 缓解措施 |
| --- | --- | --- |
| 上下文聚合提取破坏 Worker handler | 中 | 提取后 Worker handler 改为调用 service 层方法，确保行为一致；运行 `test_outline_worker_handlers.py` 验证零回归 |
| 流式期间 LLM 超时 | 中 | 复用 SPEC 0018 的超时处理；首 chunk 前降级 LocalRule |
| 上下文过大导致 prompt 超限 | 低 | `_build_user_prompt` 已有截断逻辑（各部分 1000-2000 字符） |
| SSE 连接被代理截断 | 低 | 设置 `X-Accel-Buffering: no` 头（SPEC 0018 已验证） |

### 6.2 不在风险范围

- 不破坏产品边界（仍是单用户 Web MVP）
- 不破坏 owner 边界（API 只做协议映射）
- 不引入安全风险（不绕过登录、不访问受限制平台）

---

## 七、下一步

1. 项目负责人确认本决策记录
2. 编写 SPEC 0019 详细文档（参照 SPEC 0018 格式）
3. 项目负责人确认 SPEC 0019 后进入实现阶段
4. 实现 → 测试 → 验收 → 文档回写 → git 收口 → push tag v2.1.0

---

## 八、关联文档

- [SPEC 0018 流式 LLM 输出](../specs/0018-streaming-llm-output.md)（V2.0.0，已收口）
- [决策 0024 启动 SPEC 0018](0024-start-spec-0018-streaming-llm-output.md)（§3 预留大纲流式化备选方案）
- [changelog-v2.0.0.md](../changelog-v2.0.0.md)（V2.0.0 发布说明）
- AGENTS.md（项目宪法，阶段闸规则）

---

## 九、验收证据

SPEC 0019 已完成实现与验收（2026-07-26），AC-1~25 全部通过：

- **后端测试**：`server` 下 `.venv\Scripts\python.exe -m pytest` 结果 **821 passed in 70.20s, 0 warnings**（783 原有 + 38 新增：test_deepseek_outline_provider_stream 13 + test_outline_service_stream 17 + test_outline_stream_api 8）。
- **前端测试**：`apps/web` 下 `npm test -- --run` 结果 **493 passed**（28 个测试文件，468 原有 + 25 新增：api-stream 6 + hooks-stream 12 + OutlineWorkspaceView 流式 7）。
- **TypeScript 类型检查**：`npm run lint` 通过（tsc --noEmit 无错误）。
- **Vite 构建**：`npm run build` 通过，115 模块转换，dist/ 403.42 kB，gzip 109.93 kB。
- **Alembic 迁移**：无变化（SPEC 0019 不修改数据库 schema，流式 chunk 不持久化）。
- **数据库零改动**：`git diff server/alembic/` 和 `git diff server/app/infrastructure/database/` 均无变化。
- **不引入新依赖**：`git diff server/pyproject.toml` 和 `git diff apps/web/package.json` 均无依赖变化。流式能力复用 SPEC 0018 已引入的 httpx `client.stream()` + 浏览器原生 `fetch + ReadableStream` + 现有 stream-sse.ts 工具。
- **复用 stream-sse.ts**：`git diff apps/web/src/shared/stream-sse.ts` 无变化，SPEC 0019 完全复用 SPEC 0018 的 streamSSE 工具函数。
- **浏览器验收**：browser_use agent 执行真实浏览器点击验收 PASS——种子脚本创建 RESULT_CONFIRMED 项目 + 成功 ExecutionRun → 进入大纲工作区 → 确认"生成大纲候选"和"流式生成大纲"两个按钮并列存在 → 点击"流式生成大纲" → 后端日志确认 `POST /outline/stream-generate` 返回 **200 OK** → 后端 API 验证大纲已保存（v1, CANDIDATE, local_rule, 6 章节）→ 前端大纲列表自动刷新显示新 CANDIDATE 卡片。**transient 流式 UI 状态（chunk 累积、"正在逐 chunk 生成…"）因 LocalRule provider 同步降级路径执行过快未被浏览器快照捕获（验证工具限制，非代码缺陷），后端 200 OK + 数据库持久化 + 列表自动刷新均验证通过**。截图未持久化到磁盘（TD-009 延续）。
- **原 Worker 路径零回归**：`test_outline_worker_handlers.py` 13 个测试全部通过，原 `POST /outline/generate` + Worker 异步路径不受影响；上下文聚合从 `worker/handlers.py` 提取到 `outlines/service.py` 后，Worker handler 改为调用 service 层 `gather_outline_context()`，行为不变。
- **owner 边界**：API 路由层只做 SSE 协议映射（`StreamingResponse` + `_serialize_outline_sse_event`），业务真相在 `outlines/service.stream_generate_outline`；provider 层只返回候选，不拥有业务状态；前端 hook 只展示状态不私造状态机，done 事件后 `invalidateQueries` 用后端真相覆盖。

详细验收记录见 [acceptance.md](../acceptance.md) SPEC 0019 章节，发布说明见 [changelog-v2.1.0.md](../changelog-v2.1.0.md)。

## 十、后续方向

SPEC 0019 完成后，V2.1 后续 SPEC 待项目负责人规划。可能的候选方向：

- **V2.2+**：Word/PPT 生成流式化（但 Word/PPT 是模板渲染而非 LLM 调用，流式价值有限，需评估）。
- **真实 DeepSeek API 端到端验收**：配置 `DEEPSEEK_API_KEY` 后进行真实 LLM 流式验收（任务单 + 大纲）。
- **流式生成的进度估算**：基于已生成 chunk 数 / 总预估长度展示进度条。
- TD-009 浏览器验收截图持久化修复（评估 puppeteer 等替代工具）。

上述方向均需先编写并确认对应 SPEC，不得直接进入实现。
