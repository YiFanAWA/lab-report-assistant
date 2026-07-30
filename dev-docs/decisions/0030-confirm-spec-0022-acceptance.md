# 决策 0030：确认 SPEC 0022 代码任务生成流式化收口

> **日期：** 2026-07-30
> **状态：** 已确认收口
> **决策人：** 项目负责人
> **类型：** 开发切片收口确认

## 背景

SPEC 0022（代码任务生成流式化，V2.4.0）已于 2026-07-28 完成实现与测试验收（启动决策见 [决策 0028](0028-start-spec-0022-code-task-streaming.md)），但版本收口状态在 `dev-docs/README.md`、`dev-docs/acceptance.md`、`dev-docs/implementation-plan.md` 和决策 0028 中仍标记为"待项目负责人确认收口"。

2026-07-30 期间，项目负责人在 DeepSeek JSON 容错修复（[决策 0029](0029-deepseek-json-tolerance-fix.md)）完成后，用真实 DeepSeek API 完成了端到端任务单流式生成验收（`deepseek-json-tolerance-fix-acceptance.md` §6.6）和完整业务流程链路验证（§6.7，确认任务单 → ANALYSIS_CONFIRMED 全链路 10 步打通）。链路中代码任务生成相关基础设施（SSE 端点、`stream-sse.ts`、并发保护 `active_streams`、Phase 3 状态复核）均经实际运行未见回归。

基于上述补充验证，项目负责人于 2026-07-30 正式确认 SPEC 0022 收口。

## 收口确认依据

### 实现与测试验收（2026-07-28，引用决策 0028）

- **后端测试**：975 passed（895 原有 + 80 新增），0 warnings
- **前端测试**：570 passed（551 原有 + 19 新增），lint + build 通过
- **浏览器验收**：6 个关键验证点全部 PASS（流式按钮 / 原始 JSON 累积 / 取消按钮 / 完成提示 / 列表刷新 / CANDIDATE 状态），截图保存至 `dev-docs/e2e-screenshots/spec0022-01-execution-workspace.png` 至 `spec0022-05-task-list.png`
- **收口复核修复 1 项阻断问题**：`LocalRuleCodeTaskProvider._build_analysis_code` 中 FREQUENCY 类型 `target_fields.split()` 在 list 上报错，新增 `_first_field_name()` 辅助函数兼容 list/str/None，新增 2 个回归测试覆盖

### 约束遵守

- 不引入新依赖（复用 SPEC 0018/0019/0020/0021 已建立的 httpx `client.stream()` + 浏览器原生 `fetch + ReadableStream` + `stream-sse.ts`）
- 不修改数据库 schema（流式 chunk 不持久化，无新增 Alembic 迁移）
- 保留原 Worker 异步端点 `POST /code/generate` 兼容，Worker handler 零改动
- API 路由层只做 SSE 协议映射，业务真相在 `execution/service.stream_generate_code_task`

### 同期补充验证（2026-07-30，决策 0029 关联）

- 真实 DeepSeek API 端到端流式生成任务单验收 PASS（§6.6，`done` 事件，任务单落库 `plan_id=8f3379669144`，`candidate_source=DEEPSEEK` 非降级）
- 完整业务流程链路验证 PASS（§6.7，确认任务单 → ANALYSIS_CONFIRMED 全链路 10 步，6 状态节点，0 次 `DEEPSEEK_JSON_PARSE_ERROR`）
- 链路中证据卡片流式生成（424 chunk，`done`）、分析方案生成（Worker 自动触发 `GENERATE_ANALYSIS_PLAN`）均以真实 DeepSeek 完成，未见 SPEC 0022 流式基础设施回归

## 版本收口状态

- **本地 commit**：`c4b5fdf` "v2.4.0: 完成 SPEC 0022 代码任务生成流式化"（中文）已存在
- **本地 tag**：`v2.4.0` 已存在
- **远程 push 状态**：截至 2026-07-30，本地 `master` ahead `origin/master` 3 个 commit（含 Vite SSE 修复 `740aedf`、DeepSeek 容错修复 `4d6bf5e`、链路验证文档补充 `1de0bea` 等），因用户决策"不自动 push"保留本地，待项目负责人明确指令后上传
- **远程 tag 状态**：`git ls-remote --tags origin` 因沙箱网络受限无法确认，待 push 时一并上传 `v2.4.0` tag

> 注：`c4b5fdf` 与 `40bb318` 是否已在 `origin/master` 上，需在 push 前用 `git log origin/master` 复核；本次收口确认不强制要求立即 push。

## 文档回写（本次收口同步更新）

- `dev-docs/README.md`：顶部状态行 V2.4.0 从"待确认收口"改为"已发布并打 tag v2.4.0：已由项目负责人确认收口"；下一阶段入口行更新 SPEC 0022 收口状态与 DeepSeek 端到端验收完成状态；真源索引新增决策 0030
- `dev-docs/acceptance.md`：顶部状态行 V2.4.0 收口确认；AC-22 版本收口状态从"通过（待执行）"更新为反映本地 commit + tag 已完成、push 待确认
- `dev-docs/implementation-plan.md`：V2.4.0 阶段表述从"待确认收口；待发布"更新为"已确认收口；已发布并打 tag v2.4.0"
- `dev-docs/decisions/0028-start-spec-0022-code-task-streaming.md`：状态行从"已批准进入实现，测试先行"更新为"已由项目负责人确认收口（2026-07-30）"
- `dev-docs/decisions/0030-confirm-spec-0022-acceptance.md`（本文件）：新增收口确认决策记录

## 已知漂移（可记录债务，不在本次范围）

- `dev-docs/implementation-plan.md` 中 V2.3.0 阶段表述仍为"待项目负责人确认收口；V2.3.0 待发布并打 tag v2.3.0"，与 `README.md` / `acceptance.md` 中"V2.3.0 已发布并打 tag v2.3.0：已收口"不一致。这是 V2.3.0 收口时的文档回写遗漏，非本次 SPEC 0022 引入，留作后续文档同步债务处理入口。

## 后续方向

- SPEC 0022 收口后，V2.4 后续 SPEC 待项目负责人规划
- 已有草案：SPEC 0023 多来源证据批量流式生成（待审批）
- 真实 DeepSeek API 端到端验收已于 2026-07-30 完成（决策 0029），不再阻塞后续切片
- 上述方向均需先编写并确认对应 SPEC，不得直接进入实现
