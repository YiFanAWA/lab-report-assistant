# SPEC 0021：分析方案生成流式化

**版本：** 1.0（已完成实现与验收）
**日期：** 2026-07-26
**状态：** 已完成实现与验收，待项目负责人确认收口
**目标版本：** v2.3.0
**前置版本：** v2.2.0（SPEC 0020 证据卡片生成流式化）
**关联决策：** [decisions/0027-start-spec-0021-analysis-plan-streaming.md](../decisions/0027-start-spec-0021-analysis-plan-streaming.md)

---

## 实现收口说明（2026-07-26 回写）

SPEC 0021 已完成实现与全部 AC-1~41 验收：

- **后端测试**：895 passed, 0 warnings（858 原有 + 37 新增：Provider 流式 13 + Service 流式 15 + API SSE 9）
- **前端测试**：546 passed（519 原有 + 27 新增：api-stream 6 + hooks-stream 12 + AnalysisWorkspaceView 流式 9）
- **回归测试**：原同步端点 `POST /analysis/generate` 零回归；Worker handler 零改动；TypeScript 类型检查通过；Vite 构建通过
- **浏览器验收**：PASS（9 张截图保存至 `dev-docs/e2e-screenshots/e2e-spec0021-*.png`，报告见 `dev-docs/e2e-acceptance-report-spec0021.md`）
- **收口复核修复**：LocalRuleAnalysisPlanProvider 输出 `target_fields` 为字符串导致前端 PlanCard TypeError 阻断问题，修复 6 处输出为数组（5 处 LocalRule + 1 处 Fake），清理 1 条已保存的旧错误数据
- **约束遵守**：不引入新依赖、不修改数据库 schema、不引入 WebSocket、复用 stream-sse.ts、owner 边界清晰、保留原端点兼容、Worker handler 零改动
- **文档回写**：changelog-v2.3.0.md / acceptance.md / implementation-plan.md / README.md / decisions 0027 / specs 0021 均已同步
- **版本收口**：commit `v2.3.0: 完成 SPEC 0021 分析方案流式化` + tag v2.3.0 + push origin master --tags（待项目负责人确认后执行）

---

## 一、背景与目标

### 1.1 痛点

分析方案生成是实验报告工作流中**第四个高等待**的 LLM 调用（3-10s）。当前实现（V2.2.0）通过 Worker 异步执行：

1. 前端调用 `POST /api/datasets/{dataset_id}/analysis/generate` → 创建 `JobType.GENERATE_ANALYSIS_PLAN` 任务 → 返回 `job_id`
2. 前端 `useJob` 轮询 job 状态（默认 2s 间隔）
3. Worker 进程领取 Job → 取 `DatasetProfile` → 调用 `provider.generate(profile)` 批量生成分析方案 → 保存为 CANDIDATE
4. Job 完成后，前端轮询发现状态变化 → 刷新分析方案列表

用户痛点：
- 3-10s 空白等待，无进度反馈
- 无法看到 LLM 生成分析方案的过程
- 无法中途取消
- Worker 异步与 SSE 同步推送语义不兼容（与前三个流式化切片相同问题）

### 1.2 目标

将分析方案生成改造为 SSE 流式输出，复用 SPEC 0018/0019/0020 的流式架构：
- 新增 `POST /api/datasets/{dataset_id}/analysis/stream-generate` SSE 端点（绕过 Worker）
- 后端流式调用 LLM，逐 chunk 推送
- 前端实时显示生成内容，支持取消
- 保留原 `POST /analysis/generate`（Worker 异步）兼容

### 1.3 与 SPEC 0018/0019/0020 的关系

SPEC 0021 是流式能力的**第四次复用**，架构已完全成熟：

| 维度 | SPEC 0018（任务单） | SPEC 0019（大纲） | SPEC 0020（证据卡片） | SPEC 0021（分析方案） |
| --- | --- | --- | --- | --- |
| 流式架构 | SSE + Gateway 直调 | SSE + Gateway 直调（复用） | SSE + Gateway 直调（复用） | SSE + Gateway 直调（复用） |
| Provider 输入 | 单一 requirement_text | 跨模块聚合（5 模块） | 单文档 parsed_text | **DatasetProfile（不跨模块）** |
| 产出 | 单个任务单 JSON | 单个大纲 JSON（6 章节） | 批量卡片 list | **单个 AnalysisPlanDraft（含 3 个列表）** |
| 原同步路径 | `POST /plans/generate`（保留） | `POST /outline/generate`（保留） | `POST /evidence/generate`（保留） | `POST /analysis/generate`（保留） |
| 降级策略 | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule（复用） |

**关键差异**：分析方案的产出是单个 `AnalysisPlanDraft`（含 `cleaning_plan` + `analysis_plan` + `chart_plan` 三个列表），LLM 返回单个 JSON，流式处理与 SPEC 0019 一致。

---

## 二、范围与边界

### 2.1 在范围内

1. 后端 `DeepSeekAnalysisPlanProvider.stream_generate()` 流式方法
2. 后端 `analysis_service.stream_generate_analysis_plan()` 流式 service 方法（含分段 db session）
3. 后端 `POST /api/datasets/{dataset_id}/analysis/stream-generate` SSE 端点
4. 前端 `streamGenerateAnalysisPlan()` API 函数
5. 前端 `useStreamGenerateAnalysisPlan()` hook
6. 前端分析方案生成 UI 改造（流式按钮 + 展示区 + 取消）
7. 后端单元测试（Provider + Service + API）
8. 前端单元测试（API + Hook + UI）
9. 浏览器验收

### 2.2 不在范围内

1. 不改造原 Worker 异步端点（`POST /analysis/generate` 保留不变）
2. 不流式化代码任务生成（留待 SPEC 0022）
3. 不引入 WebSocket / 长轮询
4. 不修改数据库 schema
5. 不引入新依赖
6. 不修改 `stream-sse.ts`（复用 SPEC 0018）
7. 不修改 `DeepSeekClient.stream_chat_completion()`（复用 SPEC 0018）
8. 不修改 `handle_generate_analysis_plan` Worker handler（保留兼容）
9. 不实现"多数据集批量流式生成"

---

## 三、架构设计

### 3.1 整体架构

```text
前端 useStreamGenerateAnalysisPlan
    │
    ▼ fetch + ReadableStream
POST /datasets/{dataset_id}/analysis/stream-generate (SSE)
    │
    ▼ StreamingResponse
analysis_service.stream_generate_analysis_plan()
    │
    ├──▶ Phase 1: 校验（持有 db）
    │       └──▶ _ensure_dataset + 取 DatasetProfile
    │       └──▶ db.close()
    │
    ├──▶ Phase 2: 流式生成（不持有 db）
    │       └──▶ DeepSeekAnalysisPlanProvider.stream_generate(profile)
    │               └──▶ DeepSeekClient.stream_chat_completion()
    │
    └──▶ Phase 3: 保存（重新打开 db）
            └──▶ save_analysis_plan_drafts()
```

### 3.2 SSE 事件合同（复用 SPEC 0018/0019/0020 格式）

```text
event: chunk
data: {"text": "{\"cleaning_plan\":[..."}

event: chunk
data: {"text": "],\"analysis_plan\":["}

event: done
data: {"plan_id": "...", "candidate_source": "DEEPSEEK", "fallback_used": false}

event: error
data: {"error_code": "DEEPSEEK_TIMEOUT", "message": "流式请求超时", "partial_text": "..."}
```

**done 事件字段说明**：
- `plan_id`：保存的 AnalysisPlan ID（与 SPEC 0019 的 `outline_id` 对称）
- `candidate_source`：DEEPSEEK / LOCAL_RULE
- `fallback_used`：是否使用了降级路径

### 3.3 降级策略（复用 SPEC 0018/0019/0020 模式）

| 失败时机 | 降级行为 | 用户可见 | 是否保存 |
| --- | --- | --- | --- |
| 首 chunk 前 | 降级到 LocalRule，拆分多 chunk 模拟流式 | 是 | 是 |
| 中途失败 | 保留已生成 chunk + 推送 error 事件 | 是（部分内容） | 否 |
| JSON 校验失败 | 推送 error 事件 + partial_text | 是（错误提示） | 否 |
| 用户取消 | AbortController.abort() | 是（流式停止） | 否 |

### 3.4 分段 db session（复用 SPEC 0018/0019/0020 模式）

- **Phase 1**：校验数据集状态 + 取 DatasetProfile（持有 db）→ `db.close()`
- **Phase 2**：流式生成（不持有 db）
- **Phase 3**：完成后重新打开 db → 保存 → `db2.close()`

---

## 四、关键调研结论

### 4.1 当前实现路径

- **API 端点**：`POST /api/datasets/{dataset_id}/analysis/generate`（`server/app/api/routers/analysis.py:L51-L56`）
- **Worker handler**：`handle_generate_analysis_plan`（`server/worker/handlers.py:L297-L347`）
- **Service 层**：`generate_analysis_plan`（`server/app/modules/analysis/service.py:L110-L153`），创建 `JobType.GENERATE_ANALYSIS_PLAN`
- **Provider 接口**：`generate(profile: DatasetProfile)` → `AnalysisPlanDraft`（`server/app/modules/llm/deepseek_analysis_plan_provider.py:L103-L122`）
- **Provider 输入**：`DatasetProfile`（包含字段概览），**不跨模块聚合**（与证据卡片类似，比大纲简单）
- **产出**：单个 `AnalysisPlanDraft`（含 `cleaning_plan` + `analysis_plan` + `chart_plan` 三个列表）
- **数据库模型**：`AnalysisPlan`（`server/app/modules/analysis/models.py:L1-L60`），状态机 CANDIDATE/STALE/CONFIRMED/REJECTED
- **前端**：`generateAnalysisPlan`（`apps/web/src/features/analysis/api.ts:L26-L36`），调用 API + 轮询 job 状态

### 4.2 流式化复杂度评估

- **Provider 输入**：`DatasetProfile`，不跨模块聚合 → **比大纲简单**（无需提取 `gather_outline_context` 类共享方法）
- **产出形式**：单个 JSON 对象 → **与 SPEC 0019 一致**（不是批量列表）
- **Worker handler**：已极简（Provider 输入是 DatasetProfile），无需提取共享方法
- **降级路径**：LocalRule provider 已存在，可直接复用

---

## 五、测试策略

### 5.1 后端测试（预期 ~35 测试）

| 测试文件 | 预期数量 | 覆盖点 |
| --- | --- | --- |
| `test_deepseek_analysis_plan_provider_stream.py` | ~13 | stream_generate 成功 / 首 chunk 前降级 / 中途失败抛异常 / source_label |
| `test_analysis_service_stream.py` | ~15 | 成功保存 / 中途失败不保存 / JSON 校验失败 / 兼容同步 provider / 错误分支 |
| `test_analysis_stream_api.py` | ~9 | SSE 端点 / 事件格式 / plan_id / 404 / error 事件 / 原端点零回归 |

### 5.2 前端测试（预期 ~26 测试）

| 测试文件 | 预期数量 | 覆盖点 |
| --- | --- | --- |
| `api-stream.test.ts` | ~6 | URL / POST / body / streamSSE / AbortSignal / HTTP 错误 |
| `hooks-stream.test.tsx` | ~12 | 状态管理 / invalidate / AbortSignal / STREAM_NETWORK_ERROR / AbortError |
| `AnalysisWorkspaceView.test.tsx`（扩展） | ~8 | 流式按钮 / chunk 展示 / 取消 / 完成提示 / 错误详情 |

### 5.3 回归测试

- Worker handler 零改动（`git diff server/worker/handlers.py` 无变化）
- 原同步端点 `POST /analysis/generate` 零回归

---

## 六、验收标准（预期 ~41 项）

| AC 范围 | 内容 |
| --- | --- |
| AC-1~4 | Provider 流式调用（成功 / 首 chunk 前降级 / 中途失败 / source_label） |
| AC-5~14 | Service 流式调用（成功保存 / 中途失败不保存 / JSON 校验失败 / 兼容 LocalRule / 错误分支） |
| AC-15~21 | API SSE 端点（事件格式 / 错误响应 / 原同步端点零回归 / Worker handler 零回归） |
| AC-22~29 | 前端流式解析（API / Hook 状态 / UI 流式展示） |
| AC-30~38 | 测试通过（后端 ~895 + 前端 ~545 + lint + build）+ Alembic 无变化 + 不引入新依赖 + owner 边界 |
| AC-39~41 | 浏览器验收 / 文档回写 / 版本收口（tag v2.3.0） |

---

## 七、风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| Provider `generate()` 接口与流式不兼容 | 低 | 中 | 调研确认 `generate(profile: DatasetProfile)` 是同步方法，可轻松改造为 `stream_generate()` |
| `AnalysisPlanDraft` 序列化问题 | 低 | 低 | 是 Pydantic 模型，可直接用 `model_dump_json()`（与 SPEC 0019 一致） |
| 数据集状态校验遗漏 | 中 | 中 | 复用 SPEC 0020 的 Phase 1 校验模式，确保数据集存在且已 profiled |
| LocalRule 降级路径测试覆盖不足 | 中 | 低 | 参考 SPEC 0020 的 LocalRule 测试模式，确保降级后产出有效 JSON |

---

## 八、与 SPEC 0022 的关系

SPEC 0021（分析方案流式化）是 SPEC 0022（代码任务流式化）的**前置依赖**：
- 代码任务生成的输入是已确认的 `AnalysisPlan`
- 用户必须先生成并确认分析方案，才能触发代码任务生成
- 因此 V2.3.0 应**先实现 SPEC 0021，再实现 SPEC 0022**

建议 V2.3.0 分两次收口：
1. **v2.3.0**：SPEC 0021 分析方案流式化
2. **v2.4.0**：SPEC 0022 代码任务流式化

或合并为一次 v2.3.0 收口（两个 SPEC 一次性完成），取决于项目负责人偏好。
