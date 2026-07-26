# V2.3.0 版本发布说明

> **版本：** v2.3.0
> **发布日期：** 2026-07-26
> **上一版本：** v2.2.0
> **提交范围：** `v2.2.0..v2.3.0`（1 个提交：SPEC 0021 分析方案生成流式化）
> **变更统计：** 后端 895 测试 + 前端 546 测试 = 1441 个测试（新增 64 个）
> **文档状态：** 已完成实现与验收，待项目负责人确认发布

---

## 概述

实验报告助手 V2.3.0 是 V2.0.0 的**第四个流式 LLM 输出版本**。V2.3.0 **不改变产品边界**（仍是本地单用户 Web MVP）和**架构主线**（仍是唯一 owner + API 适配 + 前端接线），核心目标是**将 SPEC 0018 的流式架构从"任务单生成 / 大纲生成 / 证据卡片生成"扩展到"分析方案生成"**，完成实验报告工作流中第四个长等待环节的流式化改造。

V2.3.0 聚焦于一个功能切片：

| 切片 | 标题 | 类型 | 状态 |
| --- | --- | --- | --- |
| SPEC 0021 | 分析方案生成流式化 | 新增功能 | ✅ 已完成 |

**核心价值：** V2.3.0 发布后，用户在"数据集就绪（DATASET_READY）"状态下点击"流式生成"按钮后，能实时看到 LLM 逐 chunk 生成的分析方案 JSON（包含 cleaning_plan / analysis_plan / chart_plan 三个列表），并随时可以取消。这完成了实验报告工作流中第四个长等待环节的流式化，与 SPEC 0018 的任务单流式化、SPEC 0019 的大纲流式化、SPEC 0020 的证据卡片流式化形成对称，将流式能力覆盖到证据化工作流的四个 LLM 生成场景。

---

## 一、核心变更：SPEC 0021 分析方案生成流式化

### 1.1 痛点与解决方案

**痛点：** V2.2.0 之前，用户上传数据集并解析完成后，点击"生成候选"按钮需通过 Worker 异步任务等待分析方案生成完成，期间只能看到任务状态轮询，无法实时看到 LLM 生成过程。Worker 异步路径与流式推送语义不兼容。

**解决方案：** 新增独立的 SSE 端点绕过 Worker，在请求处理中直接调用 LLM provider 流式生成，保留原 Worker 异步端点兼容：

| 维度 | V2.2.0（Worker 异步） | V2.3.0（SSE 流式） |
| --- | --- | --- |
| 用户等待感知 | 任务状态轮询 | 实时看到逐 chunk 生成 |
| 中途取消 | 不支持（任务已派发） | 支持（取消按钮） |
| 错误反馈 | 任务失败后提示 | 中途失败保留已生成内容 |
| 降级策略 | 无（整体失败） | 首 chunk 前降级 LocalRule |
| API 端点 | `POST /analysis/generate`（保留兼容） | `POST /datasets/{dataset_id}/analysis/stream-generate`（新增 SSE） |
| 执行路径 | Worker 进程异步处理 | 请求内直接调用 provider |

**架构选择：**
- SSE 端点绕过 Worker：解决 Worker 异步与 SSE 同步推送语义不兼容问题（复用 SPEC 0019/0020 模式）
- 复用 SPEC 0018/0019/0020 流式架构：`stream-sse.ts` 工具零修改，降级策略一致
- 分段持有 db session：Phase 1 校验（持有 db）→ Phase 2 流式生成（关闭 db）→ Phase 3 JSON 校验 → Phase 4 保存（重新打开 db），避免 SQLite 写锁阻塞
- 保留原 Worker 异步端点 `POST /analysis/generate` 兼容性
- Worker handler 零改动：Provider 输入是 DatasetProfile，无需提取共享方法

### 1.2 后端流式分析方案生成

| 文件 | 变更类型 | 说明 |
| --- | --- | --- |
| `server/app/modules/llm/deepseek_analysis_plan_provider.py` | 新增方法 | `stream_generate()` 生成器：HTTP 流式调用、首 chunk 前失败降级 LocalRule（拆分多 chunk yield fallback JSON）、中途失败抛异常保留已 yield chunks、流式完成后做 JSON 校验失败抛 DeepSeekError |
| `server/app/modules/analysis/service.py` | 新增方法 | `stream_generate_analysis_plan()` 生成器（3 阶段：校验 → 流式 → 保存）、`StreamAnalysisChunkEvent` / `StreamAnalysisDoneEvent` / `StreamAnalysisErrorEvent` 事件类型 |
| `server/app/api/routers/analysis.py` | 新增端点 | `POST /datasets/{dataset_id}/analysis/stream-generate` SSE 端点：`_serialize_analysis_sse_event()` 序列化、`StreamingResponse` + `text/event-stream`、预校验项目和数据集存在（确保 404 而非 SSE 错误流） |

### 1.3 前端流式分析方案生成

| 文件 | 变更类型 | 说明 |
| --- | --- | --- |
| `apps/web/src/features/analysis/api.ts` | 新增函数 | `streamGenerateAnalysisPlan(projectId, datasetId, signal?)` 异步生成器：调用 `streamSSE()` 工具（复用，零修改），URL 为 `/datasets/{dataset_id}/analysis/stream-generate`，body 为空对象 |
| `apps/web/src/features/analysis/hooks.ts` | 新增 hook | `useStreamGenerateAnalysisPlan(projectId, datasetId)`：`StreamAnalysisState` 状态结构（streaming / chunks / result / error）、`start()` 建立 SSE 连接逐 chunk 累积、`cancel()` 通过 AbortController 中断、`reset()` 重置状态、done 事件后 `invalidateQueries` 刷新分析方案列表 |
| `apps/web/src/routes/AnalysisWorkspaceView.tsx` | UI 改造 | 在分析方案生成区新增"流式生成"按钮（紫色 #6366f1，与原"生成候选"按钮并列，互斥禁用）+ 流式展示区（带边框 + "正在逐 chunk 生成…"提示 + "取消"按钮 + `<pre>` chunk 累积）+ "流式生成完成 ✓ [源]（降级）· plan_id=..."完成提示 + 错误展示（含 partial_text 详情） |

### 1.4 SSE 事件协议

SSE 端点返回 `text/event-stream`，事件格式与 SPEC 0018/0019/0020 一致：

```
event: chunk
data: {"text":"..."}

event: done
data: {"plan_id":"...", "candidate_source":"DEEPSEEK", "fallback_used":false}

event: error
data: {"error_code":"...", "message":"...", "partial_text":"..."}
```

### 1.5 降级策略

与 SPEC 0018/0019/0020 一致的降级链：

| 场景 | 降级策略 | 用户感知 |
| --- | --- | --- |
| 首 chunk 前失败（网络/超时/鉴权） | 降级到 LocalRuleAnalysisPlanProvider，拼装 AnalysisPlanDraft JSON，拆分为多 chunk yield | 流式正常完成，done 事件 `fallback_used=true`，`candidate_source=LOCAL_RULE` |
| 中途失败（HTTP 流中断） | 抛异常，已 yield chunks 保留，不降级 | error 事件，含 `partial_text`，不保存 AnalysisPlan |
| JSON 校验失败 | yield error 事件，不保存 AnalysisPlan | error 事件，含 `partial_text` 为完整 raw JSON |
| 保存失败 | yield error 事件，含 `partial_text` | error 事件，`error_code=ANALYSIS_PLAN_SAVE_FAILED` |

---

## 二、收口复核修复：LocalRuleAnalysisPlanProvider 输出 target_fields 类型不一致阻断问题

### 2.1 问题发现

V2.3.0 浏览器验收期间发现阻断问题：LocalRuleAnalysisPlanProvider 的 `_build_analysis_plan_items` 函数输出 `analysis_plan[].target_fields` 为字符串（如 "age"、"gender 分组 vs age"），而前端 `AnalysisPlanItem.target_fields` 期望 `string[]`，导致 PlanCard 组件调用 `target_fields.join(", ")` 时抛出 TypeError，整个分析工作区页面崩溃。

### 2.2 修复方案

修改 LocalRule 中 5 处 `target_fields` 输出为数组，FakeAnalysisPlanProvider 中 1 处输出为数组：

```python
# 修改前（字符串）
"target_fields": "age"

# 修改后（数组）
"target_fields": ["age"]
```

### 2.3 修复验证

- 后端 895 测试全部通过（包括 Provider 单元测试验证 `target_fields` 类型）
- 前端 546 测试全部通过（包括 PlanCard 渲染测试）
- 浏览器验收 PlanCard 渲染正常，无 TypeError
- 清理 1 条已保存的旧错误格式数据

---

## 三、测试覆盖

### 3.1 后端测试

| 测试文件 | 测试数量 | 覆盖点 |
| --- | --- | --- |
| `test_deepseek_analysis_plan_provider_stream.py` | 13 | stream_generate 成功 / 首 chunk 前降级 LocalRule / 降级后产出有效 JSON / 中途失败抛异常 / 中途失败不降级 / JSON 校验失败 / 有效 JSON / 空响应 / 缓存命中 / source_label 返回 DEEPSEEK / 单 chunk / 多 chunk 累积 |
| `test_analysis_service_stream.py` | 15 | stream_generate_analysis_plan 成功 yield chunks + done / 保存 AnalysisPlan / 中途失败 yield ErrorEvent / 中途失败不保存 / JSON 校验失败 / 同步 provider 兼容 / 项目不存在 / 项目状态不满足 / 数据集不存在 / 数据集未就绪 / DatasetVersion 不存在 / profile_json 损坏 / 多次调用幂等 |
| `test_analysis_stream_api.py` | 9 | SSE 端点返回 text/event-stream / 完整流程多 chunk + done / chunk 拼接为有效 JSON / done 事件包含 plan_id / fallback_used / 项目不存在 404 / 数据集不存在 404 / 数据集状态未满足 error 事件 / 原端点零回归 |
| **小计** | **37** | — |

后端总数：**895 passed**（858 原有 + 37 新增），0 warnings。

### 3.2 前端测试

| 测试文件 | 测试数量 | 覆盖点 |
| --- | --- | --- |
| `api-stream.test.ts` | 6 | 正确 URL / POST 方法 / 空 body / URL 编码 / 委托 streamSSE / AbortSignal / HTTP 错误透传 |
| `hooks-stream.test.tsx` | 12 | chunk 累积 / done + invalidate / start 重置 / fallback_used 标记 / streaming 状态 / error + partial_text / STREAM_NETWORK_ERROR / AbortError / cancel / reset / 初始状态 |
| `AnalysisWorkspaceView.test.tsx`（新增流式块） | 9 | 流式按钮与原按钮共存 / 点击触发 start / 流式展示区显示 / 取消按钮触发 cancel / 完成提示显示 candidate_source / 降级完成提示 / 错误展示含 partial_text 详情 / 无 partial_text 时不显示详情 / 流式按钮禁用状态 |
| **小计** | **27** | — |

前端总数：**546 passed**（519 原有 + 27 新增），31 个测试文件。

### 3.3 回归测试

- 原同步端点 `POST /analysis/generate` 零回归（`test_analysis_stream_api.py::TestOriginalEndpointZeroRegression` 通过）
- TypeScript 类型检查（`tsc --noEmit`）：通过
- Vite 构建：成功

---

## 四、约束遵守

| 约束 | 验证方法 | 结果 |
| --- | --- | --- |
| 不引入新依赖 | `git diff server/pyproject.toml` + `git diff apps/web/package.json` | ✅ 无变化 |
| 不修改数据库 schema | `git diff server/alembic/` + `git diff server/app/infrastructure/database/` | ✅ 无变化 |
| 不引入 WebSocket | 代码审查 | ✅ 仅使用 SSE（text/event-stream） |
| 复用 stream-sse.ts | `git diff apps/web/src/shared/stream-sse.ts` | ✅ 无变化 |
| owner 边界 | 代码审查 | ✅ API 只做协议映射，业务真相在 service 层 |
| 保留原端点兼容 | `test_analysis_stream_api.py::TestOriginalEndpointZeroRegression` | ✅ 零回归 |
| Worker handler 零改动 | `git diff server/worker/handlers.py` | ✅ 无变化 |

---

## 五、浏览器验收

启动后端（uvicorn port 8001）+ 前端 Vite dev server，用 browser_use agent 执行真实浏览器点击验收：

1. ✅ 首页加载，项目列表显示"SPEC0021 流式分析方案验收项目"
2. ✅ 进入项目详情页，URL 跳转至 `/projects/proj_spec0021_e2e`
3. ✅ 进入分析方案工作区，数据集"胃病数据集（验收用）"显示 READY 状态
4. ✅ 确认"生成候选"和"流式生成"两个按钮并列存在
5. ✅ 点击"流式生成"按钮，按钮变为"流式生成中…"，出现 chunk 累积展示区 + "取消"按钮
6. ✅ 流式完成后显示绿色提示"流式生成完成 ✓ [LOCAL_RULE（降级）] · plan_id=..."
7. ✅ 分析方案列表自动刷新，显示新生成的方案
8. ✅ 点击"取消"按钮验证中断流式生成
9. ✅ 控制台无 SPEC 0021 相关 error

**验收结论：PASS**。截图保存至 `dev-docs/e2e-screenshots/e2e-spec0021-*.png`（9 张），完整报告见 `dev-docs/e2e-acceptance-report-spec0021.md`。

---

## 六、与 SPEC 0018/0019/0020 的对比

| 维度 | SPEC 0018（任务单流式） | SPEC 0019（大纲流式） | SPEC 0020（证据卡片流式） | SPEC 0021（分析方案流式） |
| --- | --- | --- | --- | --- |
| Provider | `DeepSeekRequirementDraftProvider` | `DeepSeekOutlineProvider` | `DeepSeekEvidenceCardProvider` | `DeepSeekAnalysisPlanProvider` |
| 上下文来源 | 单一 requirement_text | 跨模块聚合（5 模块） | 单一 parsed_text | DatasetProfile（字段概览） |
| 原同步路径 | `POST /plans/generate`（保留） | `POST /outline/generate`（Worker，保留） | `POST /evidence/generate`（Worker，保留） | `POST /analysis/generate`（Worker，保留） |
| 前端工具 | `stream-sse.ts`（新建） | `stream-sse.ts`（复用） | `stream-sse.ts`（复用） | `stream-sse.ts`（复用） |
| 上下文聚合 | 无 | `gather_outline_context()`（提取到 service） | 无（Provider 输入是纯文本） | 无（Provider 输入是 DatasetProfile） |
| Worker 关系 | 不涉及 Worker | SSE 端点绕过 Worker，保留兼容 | SSE 端点绕过 Worker，保留兼容 | SSE 端点绕过 Worker，保留兼容 |
| Worker handler | 不涉及 | 重构（调用 service 层方法） | 零改动 | 零改动 |
| done 事件 | plan_id | outline_id | card_count | plan_id |
| 降级策略 | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule |
| 分段 db session | 是 | 是 | 是 | 是 |

---

## 七、文件变更清单

### 后端

| 文件 | 变更类型 |
| --- | --- |
| `server/app/modules/llm/analysis_plan_provider.py` | 修改（修复 LocalRule 的 5 处 target_fields 输出为数组 + Fake 的 1 处） |
| `server/app/modules/llm/deepseek_analysis_plan_provider.py` | 修改（新增 stream_generate 方法） |
| `server/app/modules/analysis/service.py` | 修改（新增 stream_generate_analysis_plan + 事件类型） |
| `server/app/api/routers/analysis.py` | 修改（新增 SSE 端点 + 序列化函数） |
| `server/tests/test_deepseek_analysis_plan_provider_stream.py` | 新建（13 测试） |
| `server/tests/test_analysis_service_stream.py` | 新建（15 测试） |
| `server/tests/test_analysis_stream_api.py` | 新建（9 测试） |

### 前端

| 文件 | 变更类型 |
| --- | --- |
| `apps/web/src/features/analysis/api.ts` | 修改（新增 streamGenerateAnalysisPlan） |
| `apps/web/src/features/analysis/hooks.ts` | 修改（新增 useStreamGenerateAnalysisPlan + StreamAnalysisState） |
| `apps/web/src/routes/AnalysisWorkspaceView.tsx` | 修改（UI 改造：流式按钮 + 展示区 + 取消 + 完成提示 + 错误展示） |
| `apps/web/src/features/analysis/__tests__/api-stream.test.ts` | 新建（6 测试） |
| `apps/web/src/features/analysis/__tests__/hooks-stream.test.tsx` | 新建（12 测试） |
| `apps/web/src/routes/__tests__/AnalysisWorkspaceView.test.tsx` | 修改（新增 9 个流式测试） |

### 验收脚本

| 文件 | 变更类型 |
| --- | --- |
| `server/scripts/setup_spec0021_e2e.py` | 新建（e2e 验收测试数据准备脚本，幂等创建项目 + 数据集 + 版本） |

### 文档

| 文件 | 变更类型 |
| --- | --- |
| `dev-docs/specs/0021-analysis-plan-streaming.md` | 新建（SPEC 草案，更新状态为已完成） |
| `dev-docs/decisions/0027-start-spec-0021-analysis-plan-streaming.md` | 新建（决策记录） |
| `dev-docs/e2e-acceptance-report-spec0021.md` | 新建（浏览器验收报告） |
| `dev-docs/README.md` | 修改（顶部状态行 + SPEC 0021 索引 + 决策 0027 索引 + V2.3 发布文档索引） |
| `dev-docs/acceptance.md` | 修改（顶部状态行 + 当前限制 + 验收记录表追加 SPEC 0021 记录） |
| `dev-docs/implementation-plan.md` | 修改（顶部说明 + 执行门禁追加 V2.3.0） |
| `dev-docs/changelog-v2.3.0.md` | 新建（本文件） |

---

## 八、已知限制

1. **TD-009 延续**：本次 SPEC 0021 浏览器验收截图已通过 browser_use agent 主动持久化到磁盘（9 张截图保存成功），TD-009 作为历史债务仍延续（之前 SPEC 0017/0018 的截图未持久化）。本次截图持久化部分缓解了 TD-009 限制。
2. **DEEPSEEK_API_KEY 未设置**：本次浏览器验收在 LocalRule 降级路径下完成，未覆盖 DeepSeek 真实流式调用路径。真实 LLM 流式调用路径已在后端单元测试（mock DeepSeekClient）中覆盖，待后续配置真实 API_KEY 后补充真实 LLM 流式验收。
3. **LocalRule 降级路径过快**：在无 DeepSeek API key 时，provider 降级为 LocalRule 同步生成，chunk 拆分为 50 字符片段快速 yield。本次浏览器验收因 LocalRule 拆分了较长的 AnalysisPlanDraft JSON（含 cleaning_plan + analysis_plan + chart_plan 三个列表）成功捕获了流式 UI 中间状态。
4. **本次 SPEC 0021 引入阻断问题已修复**：LocalRuleAnalysisPlanProvider 输出 `target_fields` 为字符串导致前端 PlanCard TypeError，已修复 6 处输出为数组，并清理 1 条已保存的旧错误数据。该问题在收口复核阶段被捕获并修复，未流入正式发布版本。

---

## 九、下一阶段

V2.3.0 完成后，实验报告工作流中四个 LLM 生成环节（任务单 + 大纲 + 证据卡片 + 分析方案）均已完成流式化。后续可选方向（已有草案待审批）：

- **SPEC 0022**：代码任务流式化（复用 SPEC 0018 模式，SSE 端点绕过 Worker）
- **SPEC 0023**：多来源证据批量流式生成（扩展 SPEC 0020 支持跨来源批量）
- **真实 DeepSeek API 端到端验收**：配置 `DEEPSEEK_API_KEY` 后进行真实 LLM 流式验收

下一阶段方向待项目负责人规划。后续新切片开始前仍需先编写并确认新 SPEC。
