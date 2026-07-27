# V2.4.0 版本发布说明

> **版本：** v2.4.0
> **发布日期：** 2026-07-28
> **上一版本：** v2.3.0
> **提交范围：** `v2.3.0..v2.4.0`（1 个提交：SPEC 0022 代码任务生成流式化）
> **变更统计：** 后端 975 测试 + 前端 570 测试 = 1545 个测试（新增 99 个，含 SPEC 0022 流式 97 个 + 收口复核新增 target_fields 类型回归测试 2 个）
> **文档状态：** 已完成实现与验收，待项目负责人确认发布

---

## 概述

实验报告助手 V2.4.0 是 V2.0.0 的**第五个流式 LLM 输出版本**。V2.4.0 **不改变产品边界**（仍是本地单用户 Web MVP）和**架构主线**（仍是唯一 owner + API 适配 + 前端接线），核心目标是**将 SPEC 0018 的流式架构从"任务单生成 / 大纲生成 / 证据卡片生成 / 分析方案生成"扩展到"代码任务生成"**，完成实验报告工作流中第五个长等待环节的流式化改造。

V2.4.0 聚焦于一个功能切片：

| 切片 | 标题 | 类型 | 状态 |
| --- | --- | --- | --- |
| SPEC 0022 | 代码任务生成流式化 | 新增功能 | ✅ 已完成 |

**核心价值：** V2.4.0 发布后，用户在"分析方案已确认（ANALYSIS_CONFIRMED）"状态下点击"流式生成"按钮后，能实时看到 LLM 逐 chunk 生成的代码任务 JSON（包含 `code` 字段的 Python 代码），并随时可以取消。这完成了实验报告工作流中第五个长等待环节的流式化，与 SPEC 0018 的任务单流式化、SPEC 0019 的大纲流式化、SPEC 0020 的证据卡片流式化、SPEC 0021 的分析方案流式化形成对称，将流式能力覆盖到证据化工作流的五个 LLM 生成场景。

---

## 一、核心变更：SPEC 0022 代码任务生成流式化

### 1.1 痛点与解决方案

**痛点：** V2.3.0 之前，用户确认分析方案后，点击"生成代码候选"按钮需通过 Worker 异步任务等待代码任务生成完成，期间只能看到任务状态轮询，无法实时看到 LLM 生成过程。Worker 异步路径与流式推送语义不兼容。

**解决方案：** 新增独立的 SSE 端点绕过 Worker，在请求处理中直接调用 LLM provider 流式生成，保留原 Worker 异步端点兼容：

| 维度 | V2.3.0（Worker 异步） | V2.4.0（SSE 流式） |
| --- | --- | --- |
| 用户等待感知 | 任务状态轮询 | 实时看到逐 chunk 生成 |
| 中途取消 | 不支持（任务已派发） | 支持（取消按钮 + 服务端断开检测） |
| 错误反馈 | 任务失败后提示 | 中途失败保留已生成内容（partial_text） |
| 降级策略 | 无（整体失败） | 首 chunk 前降级 LocalRule |
| API 端点 | `POST /analysis/{plan_id}/code/generate`（保留兼容） | `POST /analysis/{plan_id}/code/stream-generate`（新增 SSE） |
| 执行路径 | Worker 进程异步处理 | 请求内直接调用 provider |

**架构选择：**
- SSE 端点绕过 Worker：解决 Worker 异步与 SSE 同步推送语义不兼容问题（复用 SPEC 0019/0020/0021 模式）
- 复用 SPEC 0018/0019/0020/0021 流式架构：`stream-sse.ts` 工具零修改，降级策略一致
- 分段持有 db session：Phase 1 校验（持有 db）→ Phase 2 流式生成（关闭 db）→ Phase 3 JSON 校验 → Phase 4 保存（重新打开 db），避免 SQLite 写锁阻塞
- 保留原 Worker 异步端点 `POST /analysis/{plan_id}/code/generate` 兼容性
- Worker handler 零改动：Provider 输入是 AnalysisPlan，无需提取共享方法

### 1.2 后端流式代码任务生成

| 文件 | 变更类型 | 说明 |
| --- | --- | --- |
| `server/app/modules/llm/code_task_provider.py` | 修改 | 抽象基类 `CodeTaskDraftProvider` 新增 `stream_generate()` 抽象方法；`LocalRuleCodeTaskProvider.stream_generate()` 调用 `generate()` 后序列化为 JSON 拆分多 chunk yield；`FakeCodeTaskProvider.stream_generate()` 同上；新增 `_first_field_name()` 辅助函数兼容 `target_fields` 为 list/str 的情况 |
| `server/app/modules/llm/deepseek_code_task_provider.py` | 新增方法 | `stream_generate()` 生成器：HTTP 流式调用、首 chunk 前失败降级 `fallback.stream_generate()`（拆分多 chunk yield）、中途失败抛异常保留已 yield chunks、流式完成后做 JSON 校验失败抛 DeepSeekError |
| `server/app/modules/execution/service.py` | 新增方法 | `stream_generate_code_task()` 生成器（4 阶段：校验 → 流式 → JSON 校验 → 保存）、`StreamCodeTaskChunkEvent` / `StreamCodeTaskDoneEvent` / `StreamCodeTaskErrorEvent` 事件类型、`_is_disconnected()` 辅助函数兼容同步/异步 `request.is_disconnected()` |
| `server/app/api/routers/code_tasks.py` | 新增端点 | `POST /analysis/{plan_id}/code/stream-generate` SSE 端点：`_serialize_code_task_sse_event()` 序列化、`StreamingResponse` + `text/event-stream`、`active_streams` 并发保护（返回 409 STREAM_ALREADY_ACTIVE）、预校验项目和 AnalysisPlan 存在（确保 404 而非 SSE 错误流） |
| `server/app/main.py` | 修改 | 添加 `conflict_codes` 集合（仅含 `STREAM_ALREADY_ACTIVE`），流式端点专用错误码映射为 409 |

### 1.3 前端流式代码任务生成

| 文件 | 变更类型 | 说明 |
| --- | --- | --- |
| `apps/web/src/features/execution/api.ts` | 新增函数 | `streamGenerateCodeTask(projectId, planId, signal?)` 异步生成器：调用 `streamSSE()` 工具（复用，零修改），URL 为 `/analysis/{plan_id}/code/stream-generate`，body 为空对象 |
| `apps/web/src/features/execution/hooks.ts` | 新增 hook | `useStreamGenerateCodeTask(projectId)`：`StreamCodeTaskState` 状态结构（streaming / chunks / result / error）、`start(planId)` 建立 SSE 连接逐 chunk 累积、`cancel()` 通过 AbortController 中断、`reset()` 重置状态、done 事件后 `invalidateQueries(["code-tasks", projectId, "list"])` 刷新代码任务列表 |
| `apps/web/src/routes/ExecutionWorkspaceView.tsx` | UI 改造 | 在代码任务生成区新增"流式生成"按钮（紫色 #6366f1，与原"生成代码候选"按钮并列，互斥禁用）+ 流式展示区（带边框 + "正在逐 chunk 生成（原始 JSON 输出）…"提示 + "取消"按钮 + `<pre>` chunk 累积）+ "流式生成完成 ✓ [源]（降级）· code_task_id=..."完成提示 + 错误展示（含 partial_text 详情） |

### 1.4 SSE 事件协议

SSE 端点返回 `text/event-stream`，事件格式与 SPEC 0018/0019/0020/0021 一致：

```
event: chunk
data: {"text":"..."}

event: done
data: {"code_task_id":"...", "candidate_source":"DEEPSEEK", "fallback_used":false}

event: error
data: {"error_code":"...", "message":"...", "partial_text":"..."}
```

### 1.5 降级策略

与 SPEC 0018/0019/0020/0021 一致的降级链：

| 场景 | 降级策略 | 用户感知 |
| --- | --- | --- |
| 首 chunk 前失败（网络/超时/鉴权） | 降级到 `fallback.stream_generate()`，拼装 CodeTaskDraft JSON，拆分为多 chunk yield | 流式正常完成，done 事件 `fallback_used=true`，`candidate_source=LOCAL_RULE` |
| 中途失败（HTTP 流中断） | 抛异常，已 yield chunks 保留，不降级 | error 事件，含 `partial_text`，不保存 CodeTask |
| JSON 校验失败 | yield error 事件，不保存 CodeTask | error 事件，含 `partial_text` 为完整 raw JSON |
| 保存失败 | yield error 事件，含 `partial_text` | error 事件，`error_code=CODE_TASK_STREAM_FAILED` |

### 1.6 错误分层（SPEC 0022 评审反馈三）

| 错误类型 | HTTP 状态码 | 实现方式 |
| --- | --- | --- |
| 项目不存在 | 404 | 抛 `AppError(PROJECT_NOT_FOUND)` → handler 映射 |
| AnalysisPlan 不存在 | 404 | 抛 `AppError(ANALYSIS_PLAN_NOT_FOUND)` → handler 映射 |
| 项目状态不满足 | 409 | `_make_conflict_response(409)` 直接返回 |
| AnalysisPlan 未确认 | 409 | `_make_conflict_response(409)` 直接返回 |
| 并发冲突 | 409 | 抛 `AppError(STREAM_ALREADY_ACTIVE)` → conflict_codes 映射 |
| 流式期间错误 | SSE error 事件 | service 层 yield `StreamCodeTaskErrorEvent` |

---

## 二、收口复核修复：target_fields 类型兼容（1 项阻断问题）

### 2.1 问题发现

V2.4.0 浏览器验收期间发现阻断问题：`LocalRuleCodeTaskProvider._build_analysis_code` 函数在处理 FREQUENCY 分析类型时调用 `target_fields.split()`，假设 `target_fields` 是字符串。但 SPEC 0021 修复后 `target_fields` 可能为 list（如 `["diagnosis", "gender"]`），导致 `'list' object has no attribute 'split'` 异常，SSE 端点返回 error 事件，前端展示"流式生成失败：流式连接失败"。

### 2.2 修复方案

在 [code_task_provider.py](file:///d:/java_project/lab-report-assistant/server/app/modules/llm/code_task_provider.py) 中新增 `_first_field_name()` 辅助函数，兼容 list/str/None 三种类型：

```python
def _first_field_name(target_fields) -> str:
    """从 target_fields 提取第一个字段名。

    兼容 SPEC 0021 修复后 target_fields 可能为 list 的情况：
    - list：取第一个元素（如 ["age", "gender"] → "age"）
    - str：用 split() 取第一个字段（如 "age 分组 vs age" → "age"）
    - 其他类型或空：返回空字符串
    """
    if isinstance(target_fields, list):
        if target_fields:
            return str(target_fields[0])
        return ""
    if isinstance(target_fields, str):
        if target_fields:
            return target_fields.split()[0] if target_fields.split() else ""
        return ""
    return ""
```

修改 `_build_analysis_code` 中 FREQUENCY 分支调用 `_first_field_name()` 替代直接 `target_fields.split()[0]`。

### 2.3 修复验证

新增 2 个回归测试覆盖：
- `test_FREQUENCY类型target_fields为数组不崩溃`：list 类型 `target_fields` + FREQUENCY 分析类型，验证不崩溃且代码包含 `value_counts` 调用
- `test_FREQUENCY类型target_fields为字符串不崩溃`：string 类型 `target_fields` + FREQUENCY 分析类型，验证兼容旧格式

后端 975 测试全部通过（含 2 个新增回归测试），浏览器验收 PASS。

---

## 三、测试覆盖

### 3.1 后端测试

| 测试文件 | 测试数量 | 覆盖点 |
| --- | --- | --- |
| `test_deepseek_code_task_provider_stream.py` | 14 | stream_generate 成功 / 首 chunk 前降级 LocalRule / 降级后产出有效 JSON / 中途失败抛异常 / 中途失败不降级 / JSON 校验失败 / 有效 JSON / 空响应 / 缓存命中 / source_label 返回 DEEPSEEK / 单 chunk / 多 chunk 累积 / LocalRule 接口一致性 |
| `test_code_task_service_stream.py` | 9 | stream_generate_code_task 成功 yield chunks + done / 保存 CodeTask / 中途失败 yield ErrorEvent / 中途失败不保存 / JSON 校验失败 / 同步 provider 兼容 / 项目不存在 / AnalysisPlan 未确认 / 取消与断开 |
| `test_code_task_stream_api.py` | 17 | SSE 端点返回 text/event-stream / 完整流程多 chunk + done / chunk 拼接为有效 JSON / done 事件包含 code_task_id / fallback_used / 项目不存在 404 / AnalysisPlan 不存在 404 / 项目状态不满足 409 / AnalysisPlan 未确认 409 / 并发冲突 409 / error 后无 done / 原端点零回归 / Worker handler 零回归 |
| `test_local_rule_code_task_provider_format.py`（新增 SPEC 0022） | 21 | LocalRule 格式校验 / FREQUENCY 类型 target_fields 为数组不崩溃 / FREQUENCY 类型 target_fields 为字符串不崩溃 / stream_generate 方法存在 / stream_generate 返回迭代器 / stream_generate 拼接为有效 JSON / stream_generate 拼接代码可编译为合法 Python / stream_generate 兼容同步 generate 输出 |
| `test_local_rule_code_task_provider_format.py`（新增回归） | 2 | FREQUENCY 类型 target_fields 为数组不崩溃 / FREQUENCY 类型 target_fields 为字符串不崩溃 |
| **小计** | **63** | — |

后端总数：**975 passed**（895 原有 + 80 新增含 SPEC 0022 流式 + 回归测试），0 warnings。

### 3.2 前端测试

| 测试文件 | 测试数量 | 覆盖点 |
| --- | --- | --- |
| `api-stream.test.ts` | 7 | 正确 URL / POST 方法 / 空 body / URL 编码 / 委托 streamSSE / AbortSignal / HTTP 错误透传 |
| `hooks-stream.test.tsx` | 12 | chunk 累积 / done + invalidate / start 重置 / fallback_used 标记 / streaming 状态 / error + partial_text / STREAM_NETWORK_ERROR / AbortError / cancel / reset / 初始状态 |
| **小计** | **19** | — |

前端总数：**570 passed**（551 原有 + 19 新增），31 个测试文件。

### 3.3 回归测试

- 原同步端点 `POST /analysis/{plan_id}/code/generate` 零回归（`test_code_task_stream_api.py::TestOriginalEndpointZeroRegression` 通过）
- TypeScript 类型检查（`tsc --noEmit`）：通过
- Vite 构建：成功
- Worker handler 零回归

---

## 四、约束遵守

| 约束 | 验证方法 | 结果 |
| --- | --- | --- |
| 不引入新依赖 | `git diff server/pyproject.toml` + `git diff apps/web/package.json` | ✅ 无变化 |
| 不修改数据库 schema | `git diff server/alembic/` + `git diff server/app/infrastructure/database/` | ✅ 无变化 |
| 不引入 WebSocket | 代码审查 | ✅ 仅使用 SSE（text/event-stream） |
| 复用 stream-sse.ts | `git diff apps/web/src/shared/stream-sse.ts` | ✅ 无变化 |
| owner 边界 | 代码审查 | ✅ API 只做协议映射，业务真相在 service 层 |
| 保留原端点兼容 | `test_code_task_stream_api.py::TestOriginalEndpointZeroRegression` | ✅ 零回归 |
| Worker handler 零改动 | `git diff server/worker/handlers.py` | ✅ 无变化 |

---

## 五、浏览器验收

启动后端（uvicorn port 8001）+ 前端 Vite dev server，用 browser_use agent 执行真实浏览器点击验收：

1. ✅ 导航到执行工作区，URL 为 `/projects/proj_spec0021_e2e/execution`
2. ✅ 页面显示分析方案下拉选择器 + "生成代码候选"和"流式生成"两个按钮
3. ✅ 选择已确认分析方案（9b42594a61ce），按钮变为可用
4. ✅ 点击紫色"流式生成"按钮，按钮变为"流式生成中…"并禁用，出现取消按钮
5. ✅ 流式展示区显示"正在逐 chunk 生成（原始 JSON 输出）…"文字及 chunk 内容累积
6. ✅ 流式完成后显示绿色 ✓ 标记 + "流式生成完成"文字 + source [LOCAL_RULE] + code_task_id: 5fdb033388ba
7. ✅ 代码任务列表自动刷新，顶部新增"代码任务 v1 [候选]"卡片
8. ✅ 新生成的 CodeTask 状态为 CANDIDATE

**验收结论：PASS**。截图保存至 `dev-docs/e2e-screenshots/spec0022-01-execution-workspace.png` 至 `spec0022-05-task-list.png`（5 张），覆盖执行工作区/方案选择/流式中/流式完成/任务列表刷新。

---

## 六、与 SPEC 0018/0019/0020/0021 的对比

| 维度 | SPEC 0018（任务单） | SPEC 0019（大纲） | SPEC 0020（证据卡片） | SPEC 0021（分析方案） | SPEC 0022（代码任务） |
| --- | --- | --- | --- | --- | --- |
| Provider | `DeepSeekRequirementDraftProvider` | `DeepSeekOutlineProvider` | `DeepSeekEvidenceCardProvider` | `DeepSeekAnalysisPlanProvider` | `DeepSeekCodeTaskProvider` |
| 上下文来源 | 单一 requirement_text | 跨模块聚合（5 模块） | 单一 parsed_text | DatasetProfile（字段概览） | AnalysisPlan（已确认方案） |
| 原同步路径 | `POST /plans/generate`（保留） | `POST /outline/generate`（Worker，保留） | `POST /evidence/generate`（Worker，保留） | `POST /analysis/generate`（Worker，保留） | `POST /analysis/{plan_id}/code/generate`（Worker，保留） |
| 前端工具 | `stream-sse.ts`（新建） | `stream-sse.ts`（复用） | `stream-sse.ts`（复用） | `stream-sse.ts`（复用） | `stream-sse.ts`（复用） |
| 上下文聚合 | 无 | `gather_outline_context()` | 无 | 无 | 无（Provider 输入是 AnalysisPlan） |
| Worker 关系 | 不涉及 Worker | SSE 绕过 Worker，保留兼容 | SSE 绕过 Worker，保留兼容 | SSE 绕过 Worker，保留兼容 | SSE 绕过 Worker，保留兼容 |
| Worker handler | 不涉及 | 重构 | 零改动 | 零改动 | 零改动 |
| done 事件 | plan_id | outline_id | card_count | plan_id | code_task_id |
| 降级策略 | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule |
| 分段 db session | 是 | 是 | 是 | 是 | 是 |
| 错误分层 | 无 | 无 | 无 | 无 | 是（评审反馈三：流前 HTTP 404/409 + 流后 SSE error） |
| 并发保护 | 无 | 无 | 无 | 无 | 是（`active_streams` 字典） |
| 服务端取消 | 无 | 无 | 无 | 无 | 是（`request.is_disconnected()` 检测） |

---

## 七、文件变更清单

### 后端

| 文件 | 变更类型 |
| --- | --- |
| `server/app/modules/llm/code_task_provider.py` | 修改（抽象基类新增 stream_generate + LocalRule/Fake 实现 + `_first_field_name` 辅助函数） |
| `server/app/modules/llm/deepseek_code_task_provider.py` | 修改（新增 stream_generate 方法） |
| `server/app/modules/execution/service.py` | 修改（新增 stream_generate_code_task + 事件类型 + `_is_disconnected` 辅助函数） |
| `server/app/api/routers/code_tasks.py` | 修改（新增 SSE 端点 + 序列化函数 + `_make_conflict_response`） |
| `server/app/main.py` | 修改（添加 conflict_codes 集合） |
| `server/tests/test_deepseek_code_task_provider_stream.py` | 新建（14 测试） |
| `server/tests/test_code_task_service_stream.py` | 新建（9 测试） |
| `server/tests/test_code_task_stream_api.py` | 新建（17 测试） |
| `server/tests/test_local_rule_code_task_provider_format.py` | 新建（21 测试 + 2 回归测试） |

### 前端

| 文件 | 变更类型 |
| --- | --- |
| `apps/web/src/features/execution/api.ts` | 修改（新增 streamGenerateCodeTask） |
| `apps/web/src/features/execution/hooks.ts` | 修改（新增 useStreamGenerateCodeTask + StreamCodeTaskState） |
| `apps/web/src/routes/ExecutionWorkspaceView.tsx` | 修改（UI 改造：流式按钮 + 展示区 + 取消 + 完成提示 + 错误展示） |
| `apps/web/src/features/execution/__tests__/api-stream.test.ts` | 新建（7 测试） |
| `apps/web/src/features/execution/__tests__/hooks-stream.test.tsx` | 新建（12 测试） |
| `apps/web/src/routes/__tests__/ExecutionWorkspaceView.test.tsx` | 修改（新增 useStreamGenerateCodeTask mock） |

### 文档

| 文件 | 变更类型 |
| --- | --- |
| `dev-docs/specs/0022-code-task-streaming.md` | 修改（更新状态为已完成） |
| `dev-docs/decisions/0028-start-spec-0022-code-task-streaming.md` | 修改（添加验收证据） |
| `dev-docs/README.md` | 修改（顶部状态行 + SPEC 0022 索引 + 决策 0028 索引 + V2.4 发布文档索引） |
| `dev-docs/acceptance.md` | 修改（顶部状态行 + 当前限制 + 验收记录表追加 SPEC 0022 记录） |
| `dev-docs/implementation-plan.md` | 修改（顶部说明 + 执行门禁追加 V2.4.0） |
| `dev-docs/changelog-v2.4.0.md` | 新建（本文件） |

---

## 八、已知限制

1. **TD-009 延续**：本次 SPEC 0022 浏览器验收截图已通过 browser_use agent 持久化到磁盘（5 张截图保存成功），TD-009 作为历史债务仍延续。
2. **DEEPSEEK_API_KEY 未设置**：本次浏览器验收在 LocalRule 降级路径下完成，未覆盖 DeepSeek 真实流式调用路径。真实 LLM 流式调用路径已在后端单元测试（mock DeepSeekClient）中覆盖，待后续配置真实 API_KEY 后补充真实 LLM 流式验收。
3. **LocalRule 降级路径过快**：在无 DeepSeek API key 时，provider 降级为 LocalRule 同步生成，chunk 拆分为 50 字符片段快速 yield。本次浏览器验收因 LocalRule 拆分了较长的 CodeTaskDraft JSON（含完整 Python 代码）成功捕获了流式 UI 中间状态。
4. **本次 SPEC 0022 引入 1 项阻断问题已修复**：`LocalRuleCodeTaskProvider._build_analysis_code` 中 FREQUENCY 分析类型调用 `target_fields.split()` 假设字符串，但 SPEC 0021 修复后 `target_fields` 可能为 list，导致 `'list' object has no attribute 'split'` 异常。已通过新增 `_first_field_name()` 辅助函数修复，新增 2 个回归测试覆盖。问题在浏览器验收阶段被捕获并修复，未流入正式发布版本。

---

## 九、下一阶段

V2.4.0 完成后，实验报告工作流中五个 LLM 生成环节（任务单 + 大纲 + 证据卡片 + 分析方案 + 代码任务）均已完成流式化。后续可选方向：

- **SPEC 0023**：多来源证据批量流式生成（扩展 SPEC 0020 支持跨来源批量）
- **真实 DeepSeek API 端到端验收**：配置 `DEEPSEEK_API_KEY` 后进行真实 LLM 流式验收
- **前端流式状态持久化**：流式中刷新页面时恢复流式状态（当前刷新会丢失流式进度）

下一阶段方向待项目负责人规划。后续新切片开始前仍需先编写并确认新 SPEC。
