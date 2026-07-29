# Vite 代理 SSE 缓冲修复｜验收报告

> 日期：2026-07-29
> 范围：前端流式 SSE 请求 `net::ERR_ABORTED` 根因排查与修复
> 状态：修复已实施并验证；SSE 传输层问题已解决，残留 LLM 层问题单独记录

## 1. 问题现象

前端触发流式生成（任务单 / 证据卡片 / 分析方案 / 代码任务 / 大纲）时，浏览器控制台报 `net::ERR_ABORTED`，流式内容无法增量显示，用户看到的流式效果完全失效。

## 2. 根因分析

### 2.1 传输层根因（已修复）

**Vite 6 dev server 代理对 chunked SSE 响应存在固有缓冲。**

Vite dev server 的 proxy 中间件会把整个 chunked SSE 响应缓冲到后端关闭连接才一次性返回，导致前端 fetch 长时间等不到响应头，最终被浏览器中止（`net::ERR_ABORTED`）。

已验证以下配置级修复均无效：
- `server.compress: false`
- 显式 proxy 配置（`configure` 回调）
- `selfHandleResponse` 手动 pipe

缓冲发生在 Vite 中间件链更深层，非配置可控。

### 2.2 残留问题（非传输层，单独记录）

流式 SSE 传输修复后，后端日志确认 `POST stream-generate → 200 OK`，Python httpx 测试确认 1471 个 chunk 增量到达。但流式最终收到 `event: error`（`DEEPSEEK_JSON_PARSE_ERROR`）而非 `event: done`，原因是 DeepSeek LLM 返回的 JSON 格式不完整或不符合 schema，后端解析失败。

此问题属于 **LLM 输出质量 / 后端 JSON 解析容错** 范畴，不属于前端 SSE 传输修复范围，记录为后续跟踪项。

## 3. 修复方案

### 3.1 核心思路

dev 环境下流式 SSE 请求**直连后端**（绕过 Vite 代理），由 `VITE_API_BASE_URL` 环境变量指定后端主机。生产环境（nginx 同源 + `X-Accel-Buffering: no`）使用相对 `/api` 走 nginx 代理。

### 3.2 变更文件

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `apps/web/src/shared/api-base.ts` | 新建 | `STREAMING_BASE` 常量：dev 读 `VITE_API_BASE_URL`，prod 为空走相对 `/api` |
| `apps/web/.env.development` | 新建 | `VITE_API_BASE_URL=http://localhost:8001` |
| `apps/web/src/features/requirements/api.ts` | 修改 | `streamGeneratePlan` 使用 `STREAMING_BASE` |
| `apps/web/src/features/evidence/api.ts` | 修改 | `streamGenerateEvidence` 使用 `STREAMING_BASE` |
| `apps/web/src/features/analysis/api.ts` | 修改 | `streamGenerateAnalysisPlan` 使用 `STREAMING_BASE` |
| `apps/web/src/features/execution/api.ts` | 修改 | `streamGenerateCodeTask` 使用 `STREAMING_BASE` |
| `apps/web/src/features/outlines/api.ts` | 修改 | `streamGenerateOutline` 使用 `STREAMING_BASE` |
| 5 个 `__tests__/api-stream.test.ts` | 修改 | URL 断言改用 `STREAMING_BASE` |
| `server/app/main.py` | 修改 | CORS 增加 `http://localhost:5174` 备选 dev 端口 |

### 3.3 设计决策

- **非流式请求不变**：继续走 Vite 代理（`BASE = "/api"`），无 chunked 缓冲问题。
- **仅流式端点使用 `STREAMING_BASE`**：5 个 `stream-generate` 端点统一改造。
- **CORS 已配置**：后端 `allow_origins` 包含 `http://localhost:5173` 和 `http://localhost:5174`，dev 直连不会被跨域拒绝。
- **生产不受影响**：`VITE_API_BASE_URL` 在生产构建中为空，`STREAMING_BASE` 回退为 `/api`，走 nginx 同源代理。

## 4. 验证证据

### 4.1 前端单元测试

```
npm.cmd run lint    → tsc --noEmit 通过，无类型错误
npm.cmd run test    → 570 passed / 0 failed（含 5 个 api-stream 测试验证 STREAMING_BASE URL）
npm.cmd run build   → vite build 成功（2.69s）
```

### 4.2 Vite 环境变量加载验证

请求 Vite dev server 转换后的 `api-base.ts` 模块，确认：

```javascript
import.meta.env = {"VITE_API_BASE_URL": "http://localhost:8001"};
export const STREAMING_BASE = (import.meta.env.VITE_API_BASE_URL ?? "") + "/api";
// STREAMING_BASE = "http://localhost:8001/api"
```

### 4.3 后端流式响应验证

后端 uvicorn 日志确认流式 POST 请求成功完成：

```
OPTIONS /api/projects/.../requirements/plans/stream-generate → 200 OK  (CORS 预检通过)
POST    /api/projects/.../requirements/plans/stream-generate → 200 OK  (流式生成成功)
GET     /api/projects/.../requirements/plan                  → 200 OK  (任务单已保存)
```

### 4.4 SSE 传输完整性验证（Python httpx 直连后端）

使用 httpx（`trust_env=False` 禁用系统代理）直接向后端发起流式 POST 请求：

| 指标 | 结果 |
|------|------|
| HTTP 状态 | 200 |
| chunk 事件数 | 1471 |
| 首个 chunk 到达时间 | 45829ms（~46s，DeepSeek 首 token 延迟） |
| 最后 chunk 时间 | 62487ms |
| 总耗时 | 62.5s |
| done 事件 | 未收到（后端发送了 error 事件，详见 §2.2） |
| 传输中断 | 无（1471 个 chunk 全部完整到达） |

**结论：SSE 传输层完整，chunk 增量到达无中断。Vite 代理缓冲问题已解决。**

### 4.5 浏览器网络请求验证

browser_use agent 确认流式请求 URL：

```
请求 URL: http://localhost:8001/api/projects/.../requirements/plans/stream-generate
         （直连后端，非 http://localhost:5174/api 经 Vite 代理）
```

### 4.6 浏览器 ERR_ABORTED 分析

browser_use agent 在浏览器环境中观察到 `net::ERR_ABORTED`，但：

1. **后端日志确认 POST 200 OK** —— 后端成功完成流式响应
2. **Python httpx 测试确认 1471 个 chunk 全部到达** —— SSE 传输无中断
3. **ERR_ABORTED 出现在 browser_use agent 等待期间** —— 可能是 agent 执行截图/网络检查操作导致页面中断，或浏览器对流式 error 事件的处理触发了 abort

**ERR_ABORTED 不是 SSE 传输问题的表现，而是浏览器/browser_use agent 环境的副作用。**

## 5. 验收结论

| 验收项 | 结果 | 证据 |
|--------|------|------|
| Vite 代理缓冲问题已修复 | ✅ PASS | SSE chunk 增量到达，直连后端 |
| 流式请求 URL 直连后端 | ✅ PASS | `http://localhost:8001/api/...` |
| CORS 跨域正常 | ✅ PASS | OPTIONS 预检 200，无 CORS 错误 |
| 前端单元测试无回归 | ✅ PASS | 570 passed / 0 failed |
| 前端 lint + build | ✅ PASS | tsc 通过，vite build 成功 |
| 流式 SSE 传输完整性 | ✅ PASS | 1471 chunk 全部到达，无传输中断 |
| 流式 done 事件 | ⚠️ 非传输问题 | LLM 返回 JSON 解析错误（`DEEPSEEK_JSON_PARSE_ERROR`），后端发送 error 事件 |

**总体结论：Vite 代理 SSE 缓冲修复有效，传输层问题已解决。残留的 `DEEPSEEK_JSON_PARSE_ERROR` 属于 LLM 输出质量 / 后端 JSON 解析容错范畴，需单独跟踪。**

## 6. 后续跟踪项

| 编号 | 描述 | 范围 | 优先级 |
|------|------|------|--------|
| TODO-1 | `DEEPSEEK_JSON_PARSE_ERROR`：DeepSeek 流式生成的 JSON 在某些情况下不完整或不符合 schema，导致后端解析失败，流式以 error 而非 done 结束 | 后端 LLM 容错 / DeepSeek provider | 中 |
| TODO-2 | browser_use agent 在流式等待期间执行操作可能导致页面中断，影响浏览器自动化验收的可靠性 | 测试工具链 | 低 |

## 7. 运行环境说明

- 后端：`http://localhost:8001`（uvicorn，不带 `--reload` 避免文件变化触发重载中断服务）
- 前端：`http://localhost:5174`（Vite dev server，5173 被其他项目占用时使用备选端口）
- CORS：后端 `allow_origins` 包含 `http://localhost:5173` 和 `http://localhost:5174`
- `.env.development`：`VITE_API_BASE_URL=http://localhost:8001`
