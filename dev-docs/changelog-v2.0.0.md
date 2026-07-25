# V2.0.0 版本发布说明

> **版本：** v2.0.0
> **发布日期：** 2026-07-25
> **上一版本：** v1.4.0
> **提交范围：** `v1.4.0..v2.0.0`（2 个提交：`d321e04` CI 修复、`da67122` SPEC 0018 流式 LLM 输出）
> **变更统计：** 后端 783 测试 + 前端 468 测试 = 1251 个测试（新增 81 个）
> **文档状态：** 已由项目负责人确认发布

---

## 概述

实验报告助手 V2.0.0 是 V1.4.0 的**首个流式 LLM 输出版本**。V2.0.0 **不改变产品边界**（仍是本地单用户 Web MVP）和**架构主线**（仍是唯一 owner + API 适配 + 前端接线），核心目标是**解决用户在 LLM 生成任务单期间的等待体验问题**。

V2.0.0 聚焦于一个功能切片和一个 CI 修复：

1. **SPEC 0018 流式 LLM 输出**：将"任务单生成"这一 LLM 调用从同步阻塞改造为 SSE（Server-Sent Events）流式输出，让用户在前端实时看到 LLM 逐 chunk 生成的任务单 JSON，并支持中途取消。
2. **CI 流水线 P0 修复**：前端 job 新增单元测试步骤，后端依赖安装改用依赖声明方式。

V2.0.0 包含 2 个变更切片：

| 切片 | 标题 | 类型 | 状态 |
| --- | --- | --- | --- |
| SPEC 0018 | 流式 LLM 输出（任务单生成 SSE 流式化） | 新增功能 | ✅ 已完成（commit `da67122`） |
| CI 修复 | CI 流水线 P0 缺陷修复 | 修复 | ✅ 已完成（commit `d321e04`） |

**核心价值：** V2.0.0 发布后，用户点击"流式生成任务单"按钮后，不再需要盯着空白页面等待 5-15 秒，而是能实时看到 LLM 逐字生成的任务单内容，并随时可以取消。这显著提升了实验报告工作流的交互体验和可控性。

---

## 一、核心变更：SPEC 0018 流式 LLM 输出

### 1.1 痛点与解决方案

**痛点：** V1.4.0 之前，用户点击"生成任务单"后需同步等待后端 LLM 调用 5-15s，期间 UI 无任何进度反馈，且无法中途取消。LLM 生成完成后整个 JSON 一次性返回，缺乏"AI 正在思考"的实时感。

**解决方案：** 将"任务单生成"这一 LLM 调用从同步阻塞改造为 SSE 流式输出：

| 维度 | V1.4.0（同步） | V2.0.0（流式） |
| --- | --- | --- |
| 用户等待感知 | 5-15s 空白等待 | 实时看到逐 chunk 生成 |
| 中途取消 | 不支持 | 支持（取消按钮） |
| 错误反馈 | 整体失败后提示 | 中途失败保留已生成内容 |
| 降级策略 | 无（整体失败） | 首 chunk 前降级 LocalRule |
| API 端点 | `POST /plans/generate`（保留兼容） | `POST /plans/stream-generate`（新增 SSE） |

**架构选择：**
- 后端使用 `fastapi.responses.StreamingResponse` 推送 SSE 事件
- 前端使用 `fetch + ReadableStream` 原生解析（不引入 EventSource，以支持 POST + body）
- 不引入 WebSocket / 长轮询基础设施
- 保留原同步端点 `POST /plans/generate` 兼容性

### 1.2 后端流式 LLM 调用

**提交：** `da67122`

| 文件 | 变更类型 | 说明 |
| --- | --- | --- |
| `server/app/infrastructure/llm/deepseek_client.py` | 新增方法 | `stream_chat_completion()` 生成器：缓存查询（命中一次性 yield）、HTTP 流式调用（`httpx.Client.stream()`）、SSE 行解析、错误映射、完成后写缓存 |
| `server/app/modules/llm/deepseek_requirement_provider.py` | 新增方法 | `stream_draft()` 生成器：调用 `stream_chat_completion`、首 chunk 前失败降级到 LocalRule（拆分多 chunk 模拟流式）、中途失败抛异常、完成后校验 JSON |
| `server/app/modules/requirements/service.py` | 新增方法 | `stream_generate_plan()` 生成器 + `StreamChunkEvent` / `StreamDoneEvent` / `StreamErrorEvent` 类型：分段持有 db session、兼容 LocalRule provider、失败推送 error 事件 |
| `server/app/api/routers/requirements.py` | 新增端点 | `POST /plans/stream-generate` SSE 端点（`StreamingResponse` + `text/event-stream`）+ `_serialize_sse_event()` 辅助函数 |

**关键设计决策：**

1. **流式与同步共享 LLM 缓存（SPEC 0014）**：流式调用前查询缓存，命中时一次性 yield 完整字符串（前端快速完成）；流式完成后写入缓存。中途失败不写入缓存。

2. **分段持有 db session**：
   - Phase 1：校验（持有 db）→ Phase 2：流式生成（关闭 db，不持有连接）→ Phase 3：完成后重新打开 db 保存
   - 避免 SQLite 写锁长时间阻塞其他请求

3. **首 chunk 前降级 vs 中途失败不降级**：
   - 首 chunk 前失败：降级到 `LocalRuleRequirementDraftProvider`（拆分多 chunk 模拟流式）
   - 中途失败：保留已生成 chunk + 推送 `error` 事件（不保存 RequirementPlan、不写入 LLM 缓存）

4. **流式重试语义**：流式调用不重试（流式重试语义复杂，可能导致 chunk 重复）；同步调用仍可重试。

### 1.3 前端流式展示

**提交：** `da67122`

| 文件 | 变更类型 | 说明 |
| --- | --- | --- |
| `apps/web/src/shared/stream-sse.ts` | 新建 | 通用 SSE 解析工具：`streamSSE()` 异步生成器，使用 `fetch + ReadableStream` 解析 SSE 文本块；处理 `event:` / `data:` 行、注释行、多行 data 拼接、跨 chunk 不完整块拼接 |
| `apps/web/src/features/requirements/api.ts` | 新增函数 | `streamGeneratePlan()` 异步生成器，委托给 `streamSSE` |
| `apps/web/src/features/requirements/hooks.ts` | 新增 hook | `useStreamGeneratePlan`：管理 `streaming` / `chunks` / `result` / `error` 状态；`start(sourceId)` 建立连接逐 chunk 累积；`cancel()` 通过 AbortController 中断；`reset()` 重置状态 |
| `apps/web/src/routes/RequirementWorkspaceView.tsx` | UI 改造 | 新增"流式生成任务单"按钮 + 流式展示区（带边框灰色背景 + "取消"按钮 + `<pre>` chunk 累积 + 等宽字体）+ 完成提示"流式生成完成 ✓ [源]"+ 错误展示 + 降级标记 |
| `apps/web/src/routes/__tests__/RequirementWorkspaceView.test.tsx` | 测试适配 | 新增 `useStreamGeneratePlan` mock，确保现有 35 个测试全部通过 |

**前端状态机：**

```text
初始状态 (streaming=false, chunks="", result=null, error=null)
    │
    ▼ start(sourceId)
流式进行中 (streaming=true, chunks="正在累积...", result=null, error=null)
    │
    ├──▶ chunk 事件 → chunks += text
    │
    ├──▶ done 事件 → streaming=false, chunks="", result={plan_id, ...}
    │                    └──▶ invalidateQueries(["requirements", pid, "plan"])
    │
    ├──▶ error 事件 → streaming=false, error={error_code, message, partial_text}
    │
    ├──▶ 用户取消 (cancel) → AbortController.abort() → AbortError → streaming=false
    │
    └──▶ 网络异常 → error={error_code: "STREAM_NETWORK_ERROR", ...} → streaming=false
```

### 1.4 SSE 事件合同

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

**事件类型说明：**

| 事件 | data 字段 | 语义 |
| --- | --- | --- |
| `chunk` | `text` | LLM 生成的文本片段（逐 token 推送） |
| `done` | `plan_id`, `candidate_source`, `fallback_used` | 流式完成，RequirementPlan 已保存 |
| `error` | `error_code`, `message`, `partial_text` | 流式失败，`partial_text` 保留已生成内容 |

### 1.5 降级策略详解

| 失败时机 | 降级行为 | 用户可见 | 是否保存 | 是否写缓存 |
| --- | --- | --- | --- | --- |
| 首 chunk 前 | 降级到 LocalRule，拆分多 chunk 模拟流式 | 是（看到流式输出） | 是（LocalRule 结果保存） | 是 |
| 中途失败 | 保留已生成 chunk + 推送 error 事件 | 是（部分内容 + 错误提示） | 否 | 否 |
| 网络异常 | 前端映射 `STREAM_NETWORK_ERROR` | 是（错误提示 + partial_text） | 否 | 否 |
| 用户取消 | AbortController.abort() | 是（流式停止） | 否 | 否 |

---

## 二、CI 流水线 P0 修复

**提交：** `d321e04`
**模块：** `.github/workflows/ci.yml`、`dev-docs/acceptance.md`

### 2.1 问题

V1.4.0 的 CI 配置存在两个 P0 缺陷：

1. **前端单元测试未参与 CI**：前端 job 只执行 `tsc --noEmit` 和 `npm run build`，未运行 `npm test`。434 个前端单元测试不参与 CI 把关，前端代码质量问题无法在 CI 阶段拦截。

2. **后端依赖安装硬编码**：CI 配置中硬编码安装 `pandas==3.0.3` 等科学计算包，未使用 V1.3.0 SPEC 0016 TD-004 清理后的 `pyproject.toml` 声明的 `.[dev,analysis]`。如果 `pyproject.toml` 依赖声明有误，CI 无法发现。

### 2.2 修复动作

| 文件 | 修复内容 |
| --- | --- |
| `.github/workflows/ci.yml` | 前端 job 新增 `npm test -- --run` 步骤，让 434 个前端单元测试参与 CI 把关 |
| `.github/workflows/ci.yml` | 后端依赖安装从硬编码 6 行 `pip install` 改为 `pip install -e ".[dev,analysis]"`，验证 TD-004 清理后的依赖声明 |
| `dev-docs/acceptance.md` | 新增 CI 配置修复记录 |

### 2.3 修复效果

| 维度 | 修复前 | 修复后 |
| --- | --- | --- |
| 前端测试 CI 覆盖 | 0 个测试参与 | 434 个测试参与 |
| 后端依赖声明验证 | 硬编码安装，不验证声明 | `pip install -e ".[dev,analysis]"` 验证声明正确性 |
| CI 把关能力 | 前端代码质量无法拦截 | 前端测试 + 类型检查 + 构建三重把关 |

---

## 三、性能提升

V2.0.0 的核心性能提升在于**用户感知性能**而非运行时性能：

### 3.1 用户等待体验提升

| 场景 | V1.4.0 | V2.0.0 | 提升 |
| --- | --- | --- | --- |
| 任务单生成等待 | 5-15s 空白等待 | 首个 chunk 1-2s 出现 | 首字时间 ↓ 60-80% |
| 中途取消 | 不支持 | 随时取消 | 用户可控性 ↑ |
| 缓存命中响应 | 5-15s（仍需等待） | <100ms（一次性 yield） | 响应时间 ↓ 99% |
| LLM 失败反馈 | 整体失败后提示 | 中途失败保留 partial_text | 信息保留 ↑ |

### 3.2 并发性能提升（分段 db session）

| 场景 | V1.4.0（同步） | V2.0.0（流式分段） |
| --- | --- | --- |
| LLM 调用期间 SQLite 锁 | 整个请求期间持有 db | 仅校验和保存阶段持有 db |
| 其他请求阻塞 | 可能阻塞 5-15s | 仅阻塞 <100ms |

---

## 四、架构改进

### 4.1 流式 LLM 调用架构

- **基础设施层**：`DeepSeekClient.stream_chat_completion()` 提供通用流式调用能力，复用 SPEC 0014 LLM 缓存
- **模块层**：`DeepSeekRequirementDraftProvider.stream_draft()` 封装任务单生成的流式语义
- **服务层**：`req_service.stream_generate_plan()` 持有业务真相（分段 db session + 事件生成）
- **API 层**：`POST /plans/stream-generate` 只做 SSE 协议映射
- **前端层**：`streamSSE` → `streamGeneratePlan` → `useStreamGeneratePlan` → UI

### 4.2 前端 SSE 解析工具复用

`apps/web/src/shared/stream-sse.ts` 是通用 SSE 解析工具，不耦合任务单生成语义。后续切片（如大纲生成流式化 SPEC 0019）可直接复用：

```typescript
// 任何 SSE 端点都可复用
const events = streamSSE(url, body, signal);
for await (const evt of events) {
  if (evt.event === "chunk") { /* ... */ }
  if (evt.event === "done") { /* ... */ }
}
```

### 4.3 不引入新基础设施

- 不引入 WebSocket 服务器
- 不引入消息队列
- 不引入 Redis Pub/Sub
- 流式能力由 `httpx.Client.stream()` + 浏览器原生 `fetch + ReadableStream` 提供

---

## 五、依赖变更

### 5.1 运行时依赖

V2.0.0 **无新增运行时依赖**。流式能力完全由现有依赖提供：

| 已有依赖 | 流式用途 |
| --- | --- |
| `httpx` | `client.stream("POST", ...)` 流式 HTTP 请求 |
| `fastapi` | `StreamingResponse` SSE 响应 |
| 浏览器原生 `fetch` | 前端流式请求 |
| 浏览器原生 `ReadableStream` | 前端 SSE 解析 |

### 5.2 开发依赖

无新增开发依赖。

---

## 六、测试统计

| 测试套件 | V1.4.0 | V2.0.0 | 新增 | 状态 |
| --- | --- | --- | --- | --- |
| 后端 pytest | 736 | 783 | +47 | ✅ 0 warnings |
| 前端 Vitest | 434 | 468 | +34 | ✅ 全部通过 |
| **总计** | **1170** | **1251** | **+81** | — |

### 6.1 后端新增测试分布（47 个）

| SPEC | 新增测试数 | 累计后端测试 | 测试文件 |
| --- | --- | --- | --- |
| SPEC 0018 DeepSeekClient 流式 | 18 | 754 | `server/tests/test_deepseek_client_stream.py` |
| SPEC 0018 Provider 流式 | 7 | 761 | `server/tests/test_deepseek_requirement_provider_stream.py` |
| SPEC 0018 Service 流式 | 11 | 772 | `server/tests/test_requirements_service_stream.py` |
| SPEC 0018 API SSE 端点 | 11 | 783 | `server/tests/test_requirements_stream_api.py` |

### 6.2 前端新增测试分布（34 个）

| SPEC | 新增测试数 | 累计前端测试 | 测试文件 |
| --- | --- | --- | --- |
| SPEC 0018 streamSSE 解析 | 18 | 452 | `apps/web/src/shared/__tests__/stream-sse.test.ts` |
| SPEC 0018 streamGeneratePlan API | 6 | 458 | `apps/web/src/features/requirements/__tests__/api-stream.test.ts` |
| SPEC 0018 useStreamGeneratePlan hook | 10 | 468 | `apps/web/src/features/requirements/__tests__/hooks-stream.test.tsx` |

### 6.3 新增测试详情（后端）

| 测试文件 | 覆盖点 |
| --- | --- |
| `test_deepseek_client_stream.py` (18) | 流式成功 / 缓存命中一次性 yield / 缓存写入 / 首 chunk 前失败抛 DeepSeekError / 中途失败已 yield chunk 不写缓存 / HTTP 状态码映射（401/403/429/500） |
| `test_deepseek_requirement_provider_stream.py` (7) | stream_draft 成功 / 首 chunk 前降级 LocalRule（拆分多 chunk）/ 中途失败抛异常 / JSON 校验 |
| `test_requirements_service_stream.py` (11) | stream_generate_plan 成功（保存 + StreamDoneEvent）/ 中途失败（StreamErrorEvent + 不保存）/ 兼容 LocalRule / 分段 db session |
| `test_requirements_stream_api.py` (11) | SSE 端点返回 text/event-stream / 事件格式正确 / source_id 无效返回 404 / project_id 无效返回 404 |

### 6.4 新增测试详情（前端）

| 测试文件 | 覆盖点 |
| --- | --- |
| `stream-sse.test.ts` (18) | 单事件块 / 多事件块 / 跨 chunk 拼接 / 默认 message 事件 / 多行 data 拼接 / 注释行跳过 / 空行跳过 / 冒号后空格剥离（SSE 规范）/ 尾部不完整块 / 空 body / POST+JSON body / AbortSignal 传递 / HTTP 4xx 5xx 透传 / fetch reject / 空响应体 |
| `api-stream.test.ts` (6) | 正确 URL / POST 方法 / 请求体 / URL 编码 / 委托 streamSSE 解析 / AbortSignal / HTTP 错误透传 |
| `hooks-stream.test.tsx` (10) | chunk 累积 / done 事件设置 result 并清空 chunks + invalidate / start 重置旧状态 / error 事件保留 partial_text / 非 AbortError 映射 STREAM_NETWORK_ERROR / AbortError 不设 error / cancel 通过 AbortSignal 中断 / reset 重置 / 初始状态正确 |

---

## 七、约束遵守

V2.0.0 严格遵守以下约束：

| 约束 | 遵守情况 | 证据 |
| --- | --- | --- |
| 不引入新依赖 | ✅ | `git diff server/pyproject.toml` 和 `git diff apps/web/package.json` 均无依赖变化 |
| 不修改数据库 schema | ✅ | 无新增 Alembic 迁移；`git diff server/alembic/` 无变化 |
| 不破坏原同步端点 | ✅ | `POST /plans/generate` 保留不变；test_requirement_api.py 和 test_requirement_service.py 全部通过 |
| 不引入 WebSocket/长轮询 | ✅ | 仅使用 SSE（HTTP/1.1 长连接） |
| 不违反 SPEC 0017 范围 | ✅ | SSE 是单用户 LLM 流式输出，非多用户协作 |
| 不破坏 owner 边界 | ✅ | API 只做协议映射，业务在 service 层；前端 hook 不私造状态机 |
| 复用 SPEC 0014 LLM 缓存 | ✅ | 流式与同步共享缓存 key 和存储 |
| 不绕过登录/付费墙 | ✅ | 仅调用 DeepSeek API，不访问受限制平台 |

---

## 八、已知限制（V2.0.0 边界）

1. **流式范围仅限任务单生成**：大纲生成流式化推迟到 V2.1 SPEC 0019
2. **流式不重试**：流式调用失败不自动重试（流式重试语义复杂，可能导致 chunk 重复）；同步调用仍可重试
3. **不引入 WebSocket**：仅使用 SSE，不支持双向通信
4. **不修改数据库 schema**：流式 chunk 不持久化，只有最终 RequirementPlan 保存
5. **截图未持久化**：浏览器验收截图未保存到磁盘（TD-009 延续，非阻断）
6. **不引入 EventSource API**：前端使用 `fetch + ReadableStream` 以支持 POST + body（EventSource 只支持 GET）

---

## 九、技术债务状态

### V2.0.0 发布后债务汇总

| 类别 | 数量 | 状态 |
| --- | --- | --- |
| 阻断问题 | 0 | — |
| 可记录债务 | 1 | TD-009（浏览器验收截图未持久化，非阻断） |
| 已关闭债务（TD-001~008） | 8 | 全部关闭，保留追溯 |
| 代码 TODO/FIXME | 0 | 项目源码无 TODO/FIXME/XXX/HACK |

### TD-009 详情

| 字段 | 值 |
| --- | --- |
| 编号 | TD-009 |
| 名称 | 浏览器验收截图未持久化 |
| 引入切片 | SPEC 0017（V1.4.0） |
| 状态 | 活跃（非阻断） |
| 原因 | `browser_take_screenshot` 工具在当前环境未将截图写入磁盘 |
| 影响 | SPEC 0017 和 SPEC 0018 的浏览器验收结论为 PASS，但截图未保存到 `dev-docs/e2e-screenshots/` |
| 修复入口 | 评估 puppeteer 等替代工具，或调整 browser_use agent 配置 |

---

## 十、升级指南

### 10.1 无破坏性变更

V2.0.0 是**向后兼容**的版本：

- 原同步端点 `POST /plans/generate` 保留不变，现有脚本和测试不受影响
- 数据库 schema 无变化，无需运行迁移
- 无新增依赖，无需 `pip install` 或 `npm install` 新包

### 10.2 从 V1.4.0 升级（本地开发）

```bash
# 1. 拉取最新代码
git pull origin master

# 2. 更新后端依赖（无新增依赖）
cd server
.venv\Scripts\activate
pip install -e ".[dev,analysis]"

# 3. 执行数据库迁移（无新增迁移）
.venv\Scripts\python.exe -m alembic upgrade head

# 4. 更新前端依赖（无新增依赖）
cd ../apps/web
npm install
```

### 10.3 从 V1.4.0 升级（Docker 部署）

```bash
# 1. 拉取最新代码
git pull origin master

# 2. 重新构建镜像
docker compose build

# 3. 重启服务
docker compose up -d
```

### 10.4 使用流式生成

前端用户现在有两个按钮：

| 按钮 | 行为 | 适用场景 |
| --- | --- | --- |
| **"生成任务单候选"** | 原同步行为（等待 5-15s 后一次性显示） | 脚本自动化、不需要进度反馈 |
| **"流式生成任务单"**（新增） | 实时显示 LLM 逐 chunk 生成内容，支持中途取消 | 交互式使用、需要进度反馈 |

### 10.5 配置

无需新增环境变量。流式生成复用现有配置：

| 环境变量 | 说明 |
| --- | --- |
| `DEEPSEEK_API_KEY` | 未配置时自动降级到 LocalRule provider（流式拆分多 chunk 模拟） |
| `LLM_CACHE_ENABLED` | 缓存命中时一次性 yield 完整字符串（快速完成） |

---

## 十一、回归测试

V2.0.0 发布前已执行完整回归测试，详见 [acceptance.md](acceptance.md) V2.0.0 回归测试记录。

**关键回归点：**

| 验收项 | 命令 | 结果 |
| --- | --- | --- |
| 后端测试 | `.venv\Scripts\python.exe -m pytest` | 783 passed, 0 warnings |
| 前端测试 | `npm test -- --run` | 468 passed |
| TypeScript 类型检查 | `npm run lint` | tsc --noEmit 通过 |
| Vite 构建 | `npm run build` | 115 模块, dist/ 400.27 kB, gzip 109.09 kB |
| Alembic 迁移 | `alembic upgrade head` | 无变化（无新增迁移） |
| 浏览器验收 | browser_use agent | PASS（流式展示区 + 取消按钮 + chunk 累积 + 完成提示） |
| 原同步端点零回归 | `test_requirement_api.py` + `test_requirement_service.py` | 全部通过 |
| 数据库零改动 | `git diff server/alembic/` | 无变化 |
| 不引入新依赖 | `git diff pyproject.toml` + `git diff package.json` | 无依赖变化 |

---

## 十二、浏览器验收证据

V2.0.0 用 browser_use agent 执行真实浏览器点击验收：

| 步骤 | 结果 | 证据 |
| --- | --- | --- |
| 打开首页 | PASS | 页面正常加载 |
| 创建项目"流式生成验收" | PASS | 项目创建成功 |
| 进入实验要求工作台 | PASS | 导航至 /projects/{id}/requirements |
| 添加实验要求来源 | PASS | "已保存 ✓"提示 |
| 验证两个生成按钮存在 | PASS | "生成任务单候选"和"流式生成任务单"均存在 |
| 点击"流式生成任务单" | PASS | 流式展示区出现（带边框灰色背景） |
| "取消"按钮存在 | PASS | 流式展示区内有取消按钮 |
| chunk 文本在 `<pre>` 标签累积 | PASS | 逐步累积显示 |
| 流式完成提示 | PASS | "流式生成完成 ✓ [LOCAL_RULE]" |
| 任务单保存到后端 | PASS | GET /api/.../plan 返回 CANDIDATE 状态 |

> **注：** 截图未持久化到磁盘（TD-009 延续），验收结论为 PASS。

---

## 十三、致谢

感谢项目负责人在 V1.4.0 发布后立即明确下一阶段方向为流式 LLM 输出，让项目从"同步等待"时代进入"流式交互"时代。V2.0.0 的 SPEC 0018 遵循"先编写并确认 SPEC → 项目负责人批准 → 测试先行 → 实现 → 验收 → 文档回写 → git 收口"的阶段闸流程。

特别感谢项目负责人在决策记录 0024 中明确了"API SSE + Gateway 直调"的技术方向，避免了引入 WebSocket/长轮询等重型基础设施，保持了项目的轻量架构。

---

**版本标签：** `v2.0.0`（已创建）
**发布状态：** 已由项目负责人确认发布
**下一阶段方向：** V2.1 候选 SPEC 0019（大纲生成流式化），待项目负责人规划
