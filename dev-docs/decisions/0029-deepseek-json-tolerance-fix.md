# 决策 0029：DeepSeek 任务单 JSON 解析失败容错修复

> **日期：** 2026-07-30
> **状态：** 已实现并验证，待项目负责人确认收口
> **决策人：** 项目负责人
> **类型：** 已实现切片阻断问题修复（SPEC 0018 流式输出）

## 背景

V2.0.0（SPEC 0018 任务单生成流式化）发布后，端到端验收发现后端流式生成任务单时高频抛 `DEEPSEEK_JSON_PARSE_ERROR`，导致前端 `net::ERR_ABORTED`（流式 SSE 传输完整，但最终 JSON 校验失败）。

前期已确认 SSE 传输层无误（Vite 代理缓冲问题已通过直连方案修复，详见 `vite-proxy-sse-fix-acceptance.md`），本次聚焦后端 JSON 解析失败的根因。

## 根因（真实 DeepSeek API 5 次复现）

用真实 DeepSeek API（`deepseek-v4-pro`，temperature=0.3）对项目 `proj_2759dc9c98d7` 的相同输入连续调用 5 次：

- **失败率 60%（3 失败 / 5 总）**，问题是高频间歇性的，不是偶发。
- **两类 schema 不匹配**：
  - **根因 A**：`replication_level.suggested_scope` 字段 schema 要求 `str`（非 Optional），但 LLM 有时返回 `null`。
  - **根因 B**：`data_requirements` / `method_requirements` / `chart_requirements` / `report_requirements` 等 schema 要求 `list[str]`，但 LLM 有时返回 `list[dict]`（`[{"description": "..."}]`）。同一份输出内 `acceptance_criteria` 却返回正确的字符串数组——LLM 行为在同一份输出内都不一致。

### 根本原因

1. **Prompt 约束不足**：原 `_SYSTEM_PROMPT` 只列字段名，没有明确元素类型约束（"字符串数组"vs"对象数组"），也没给出正/反例。
2. **LLM 输出不稳定**：`temperature=0.3` 下 LLM 对 `*_requirements` 字段的返回格式在 `list[str]` 和 `list[dict]` 之间摇摆；对 `suggested_scope` 在 `str` 和 `null` 之间摇摆。
3. **无容错层**：provider `_parse_and_validate` 严格 `model_validate`，一旦不符直接抛 `DEEPSEEK_JSON_PARSE_ERROR`，流式场景下已 yield 的 chunk 无法撤回，用户体验是"流了半天最后报错"。

### 排除项

- **LLM 缓存污染排除**：`LLM_CACHE_ENABLED` 默认 `false`，`.env` 未启用，缓存不参与本次问题。
- **传输层排除**：前期已确认 SSE 传输完整（1471 chunk 到达），`DEEPSEEK_JSON_PARSE_ERROR` 是 provider 校验层抛出。

## 决策

采用 **Prompt 强化 + 轻量容错** 双层方案（项目负责人于 2026-07-30 确认）：

1. **Prompt 强化（根治主路径）**：在 `_SYSTEM_PROMPT` 中新增【字段类型约束】章节，明确：
   - `*_requirements` / `chart_requirements` / `acceptance_criteria` 每个元素必须是「字符串」，不得是对象，并给出 ✅ 正确示例与 ❌ 错误示例。
   - `replication_level.suggested_scope` 必须是「非空字符串」，不得为 null，给出正/反例。

2. **Pydantic 容错 validator（吸收 LLM 不稳定，减少真实复杂度）**：
   - 新增模块级函数 `_coerce_str_list(v)`：对 `list[str]` 字段，dict 元素优先取 `description`，否则取首个 str 值，都没有则跳过；其他类型 `str()` 转换。
   - 新增模块级函数 `_coerce_none_to_empty(v)`：`None` 转空串。
   - 在 `DeepSeekRequirementResponse` 上对 6 个 `list[str]` 字段（`data/method/chart/report/presentation_requirements` + `acceptance_criteria`）加 `@field_validator(mode="before")`。
   - 在 `DeepSeekReplicationLevel` 上对 `suggested_scope` 加 `@field_validator(mode="before")`。
   - 使用 Pydantic v2 `field_validator(mode="before")` 在校验前转换，不污染业务 payload。

3. **测试先行**：先写 9 个容错场景测试（`TestDeepSeekResponseTolerance`）定义期望行为，确认测试如预期失败（8 失败 1 通过），再实现 validator。

4. **范围限定**：本次仅修复任务单 provider（`deepseek_requirement_provider.py`）。其他 provider（证据卡片、分析方案、代码任务、大纲）的同类问题留作后续观察——若出现同样 schema 不匹配，可复用本决策的容错模式，但不预先扩大改动范围。

## 不采用方案及理由

- **仅 Prompt 强化**：最小改动，但 LLM 仍有概率不遵守（temperature=0.3 有随机性），无法 100% 根除，用户体验不可接受。
- **仅模型容错**：不改 prompt，靠校验层吸收。但 prompt 不约束会导致 LLM 持续返回非预期格式，容错逻辑会越堆越多，有补丁式开发风险。
- **不用散落 if 容错**：宪法禁止补丁式开发。本方案用统一的 `field_validator` + 模块级函数，是结构化容错，符合"抽象只在减少真实复杂度时引入"。

## 影响范围

### 范围内（改动文件）

- `server/app/modules/llm/deepseek_requirement_provider.py`：
  - 新增 `_coerce_str_list()` 和 `_coerce_none_to_empty()` 模块级容错函数。
  - `DeepSeekReplicationLevel` 新增 `suggested_scope` 的 `field_validator(mode="before")`。
  - `DeepSeekRequirementResponse` 新增 6 个 `list[str]` 字段的统一 `field_validator(mode="before")`。
  - 强化 `_SYSTEM_PROMPT`：新增【字段类型约束】章节，含正/反例。
- `server/tests/test_deepseek_requirement_provider_stream.py`：新增 `TestDeepSeekResponseTolerance` 测试类，9 个容错场景测试。

### 范围外（不改动）

- 其他 provider（证据卡片、分析方案、代码任务、大纲）：不动，留作后续观察。
- `deepseek_client.py`：不动（client 不负责 schema 校验）。
- 数据库 schema / Alembic 迁移：不动。
- 前端：不动（错误处理已在前次 Vite 代理修复中完成）。
- 不引入新依赖（`field_validator` 是 Pydantic v2 内置）。

## 验收证据（2026-07-30）

### 单元测试

- `test_deepseek_requirement_provider_stream.py`：16 passed（含 9 个新增容错测试），0.36s。
- 相关目录测试（llm + requirements）：用 `local_rule` provider 环境（正确的单元测试环境）跑，17 passed，2.85s。
- 全量后端测试中 4 个失败为 `.env` 配置 `REQUIREMENT_DRAFT_PROVIDER=deepseek` 导致测试真实调用 DeepSeek（非本改动回归），用 `local_rule` 重跑全过。

### alembic 迁移

- 临时 SQLite 全量迁移 0001→0007 成功（本修复不改 schema）。

### 前端

- `tsc --noEmit` 通过。
- `vite build` 成功（116 modules）。

### 真实 DeepSeek 复测（核心证据）

修复前 5 次调用：成功 2 次，失败 3 次（**60% 失败率**）。
修复后 5 次调用：成功 5 次，失败 0 次（**0% 失败率**）。

失败模式 A（`suggested_scope: null`）和失败模式 B（`*_requirements` 返回对象数组）均被容错吸收或 prompt 强化规避。

### 证据文件

- `.tmp/deepseek_raw_run2.json`：`suggested_scope: null` 失败样本
- `.tmp/deepseek_raw_run4.json`：`*_requirements` 返回对象数组失败样本
- `.tmp/deepseek_raw_run5.json`：`chart_requirements` 返回对象数组失败样本
- `.tmp/diagnose_post_fix.log`：修复后 5 次全过证据

## 后续方向

- 若其他 provider（证据卡片、分析方案、代码任务、大纲）出现同类 schema 不匹配，复用本决策的 `_coerce_str_list` / `_coerce_none_to_empty` 容错模式。
- 考虑将容错函数提取到共享模块（如 `app/modules/llm/tolerance.py`），供所有 provider 复用。但需先确认至少 2 个 provider 有同类问题才提取，避免过度抽象。
