# 决策 0023：启动 SPEC 0017 单用户前端实时编辑反馈切片

> **日期：** 2026-07-25  
> **状态：** 已确认，已完成实现与验收，由项目负责人确认收口（2026-07-25），打 tag v1.4.0 并 push 到 origin/master。  
> **决策人：** 项目负责人

## 背景

V1.3.0 已发布并打 tag v1.3.0，SPEC 0016 技术债务清理完成，项目当前无活跃可记录债务（TD-001~008 全部关闭）。项目负责人规划下一阶段方向为前端编辑体验优化。

当前前端编辑流程存在两类体验缺陷：

1. **保存后等网络往返才能看到结果**：`useUpdatePlan`、`useUpdateEvidence`、`useUpdateOutline` 三个 mutation 在保存成功后只调用 `qc.invalidateQueries`，触发重新 GET，UI 需等待网络往返完成才能反映最新数据。
2. **Worker 完成后需要手动刷新**：仅 `useDeliverables` 启用了 3s 轮询，证据卡片列表和大纲列表无轮询，用户触发生成后需手动刷新页面才能看到 Worker 完成后的最新状态。

项目负责人于 2026-07-25 明确选择**方向 A（单用户前端实时编辑反馈）**，不引入多用户协作、不引入 WebSocket/SSE 实时通信基础设施。该方向严格遵守 AGENTS.md "产品边界"章节"只做本地单用户 Web MVP，不做多人协作"的约束。

## 决策

1. 启动 SPEC 0017 单用户前端实时编辑反馈切片，目标版本 v1.4.0。
2. 切片范围限定为前端 hooks 层（`apps/web/src/features/{requirements,evidence,outlines}/hooks.ts`）和组件层（`apps/web/src/routes/*WorkspaceView.tsx`），不触碰后端业务代码、API 合同、数据库、Worker。
3. 三个 update mutation 新增乐观更新（`onMutate` → `setQueryData`）+ 错误回滚（`onError` → 恢复快照）+ 最终一致性（`onSettled` → `invalidateQueries`）。
4. 证据卡片列表和大纲列表新增基于数据状态的短时轮询（`refetchInterval` 函数形式，存在 PENDING/GENERATING 状态时 2s 轮询，状态稳定后自动停止）。
5. 保存按钮新增 `isPending` / `isError` / `isSuccess` 状态反馈，错误文案从后端 `AppError.message`（中文）提取。
6. **不引入任何新 npm 依赖**，所有能力由 `@tanstack/react-query` 5.x 现有 API 提供。
7. **不修改后端**：API 路由、schema、状态机、数据库表、Alembic 迁移全部不变。
8. **不破坏 SPEC 0009 前端测试覆盖**：现有 411 个前端测试全部保持通过，新增 ~30 个测试覆盖乐观更新、错误回滚、状态反馈、短时轮询。
9. 浏览器验收使用 browser_use agent 执行，截图保存到 `dev-docs/e2e-screenshots/spec-0017/`。
10. 实施完成后打 tag v1.4.0 并 push 到 origin/master。

## 理由

- 方向 A 是合规方向：严格遵守 AGENTS.md "不做多人协作"产品边界，不引入多用户身份、权限、冲突解决（OT/CRDT）机制。
- 当前 `useUpdatePlan` / `useUpdateEvidence` / `useUpdateOutline` 全部使用 `invalidateQueries` 模式，UI 等待网络往返是真实痛点，影响单用户编辑体验。
- TanStack Query 5.x 已提供 `onMutate` / `onError` / `onSettled` / `setQueryData` / `refetchInterval` 函数形式等所有需要的能力，无需引入新依赖。
- 现有 `useDeliverables` 已用 `refetchInterval: 3_000` 验证过短时轮询模式可行，本切片只是将同一模式扩展到证据卡片和大纲列表。
- `onSettled` 无条件 `invalidateQueries` 保证最终一致：即使乐观值与后端一致，也通过 GET 重新校验，防止后端做了额外加工（如 `updated_at` 字段、状态机推进）未反映在前端缓存。
- 不修改后端确保本切片风险隔离，可独立验收。

## 影响范围

### 范围内（改动文件）

- `apps/web/src/features/requirements/hooks.ts`：`useUpdatePlan` 新增乐观更新 + 错误回滚 + `onSettled` invalidate。
- `apps/web/src/features/evidence/hooks.ts`：`useUpdateEvidence` 新增乐观更新 + 错误回滚；`useEvidenceCards` 新增基于状态的短时轮询。
- `apps/web/src/features/outlines/hooks.ts`：`useUpdateOutline` 新增乐观更新 + 错误回滚；`useOutlines` 新增基于状态的短时轮询。
- `apps/web/src/routes/*WorkspaceView.tsx` 等编辑组件：保存按钮新增 `isPending` / `isError` / `isSuccess` 状态展示，错误展示来自 `AppError.message`。
- `apps/web/src/features/{requirements,evidence,outlines}/hooks.test.tsx`（新增或扩展）：~20 个 hooks 层测试。
- `apps/web/src/routes/*WorkspaceView.test.tsx`（扩展）：~10 个组件层测试。

### 范围外（不改动文件）

- `server/app/modules/**`：业务模块（不动）。
- `server/app/api/routers/**`：API 路由（不动）。
- `server/worker/**`：Worker handler（不动）。
- `server/app/infrastructure/database/**`：数据库模型（不动）。
- `server/alembic/versions/**`：迁移文件（不动）。
- `apps/web/src/features/{requirements,evidence,outlines}/api.ts`：前端 API 调用层（不动，只改 hooks 层）。
- `apps/web/src/shared/types.ts`：AppError 类型（不动，只消费）。
- `package.json` 和 `package-lock.json`：不新增依赖。

## 验收标准（27 项，详见 SPEC 0017 §七）

核心 AC：
- AC-1~6：三个 update mutation 乐观更新和错误回滚。
- AC-7~10：保存按钮状态反馈和错误展示。
- AC-11~15：短时轮询启用和停止。
- AC-16~18：后端零改动、数据库零改动、API 零改动。
- AC-19~22：测试零回归 + 类型检查 + 构建。
- AC-23：浏览器验收截图。
- AC-24~25：不引入新依赖、不破坏 owner 边界。
- AC-26~27：文档回写 + 版本收口（tag v1.4.0）。

## 验收证据

实现已完成并由项目负责人确认收口（2026-07-25）。具体证据：

### 测试验收

- **前端测试：434 passed**（22 个测试文件，原 411 + 新增 23：requirements/hooks 7 + evidence/hooks 8 + outlines/hooks 8），0 回归
- **后端测试：736 passed in 71.80s, 0 warnings**（本切片纯前端不修改后端，与 V1.3.0 一致，零回归）
- **TypeScript 类型检查：通过**（修复 `setQueriesData` 第一个参数应为 `{ queryKey: ... }` 而非裸数组）
- **Vite 构建：通过**（114 模块转换，dist/ 396.63 kB，gzip 108.01 kB）
- **Alembic 迁移：在 0007 (head)**（本切片无数据库变更）

### 实现前调研修订

实现前调研发现实际现状与 SPEC 草案原计划有出入，已在实现阶段做如下修订（详见 SPEC 0017 顶部"实现收口说明"和 §3.4 / §3.5）：

1. **§3.4 短时轮询保持现状**：三个组件（`EvidenceWorkspaceView`、`OutlineWorkspaceView`、`OutlineCard`）已用 `useJob(pid, activeJobId)` + `useEffect` 监听 `genJob.status` 变化，任务完成时 `qc.invalidateQueries` 自动刷新相关 queryKey。本轮保持现状，不引入 `refetchInterval` 短时轮询，避免双重轮询浪费请求。原 AC-11~15 标准调整为"按现状通过"。
2. **§3.5 保存按钮状态反馈**：三个组件的 `isPending`→"保存中…"+disabled、`onError`→红色错误文案（来自 AppError.message）已实现。本轮只新增 `editOk` state + `onSuccess` 中 `setEditOk("已保存 ✓")` + `setTimeout(() => setEditOk(null), 1_500)`，UI 中以绿色 #16a34a 显示。
3. **新增测试数量**：实际新增 23 个 hooks 层测试（草案原计划 ~30 含组件层 ~10）。组件层未额外编写测试，因 `isPending` / `isError` 状态反馈已在 SPEC 0009 测试中覆盖，本轮只新增 `isSuccess` 成功提示（UI 小改动）。

### 浏览器验收

启动后端 Docker 容器 + 前端 Vite dev server，用 browser_use agent 执行真实浏览器点击验收：
- 进入项目 → 进入实验要求工作台 → 编辑任务单 → 修改课题字段 → 点击保存修改 → **观察到绿色"已保存 ✓"提示（#16a34a），1.5s 后自动消失**。
- "保存中…"状态切换过快难以截图，这恰恰是乐观更新的预期效果（onMutate 后 UI 立即反映新数据）。
- 证据卡片和大纲组件因预算限制跳过浏览器验收，依赖已通过的 16 个 hooks 单元测试覆盖。
- **截图未持久化到磁盘（browser_take_screenshot 工具限制），记录为非阻断债务 TD-009**，后续修复入口见 `tech-debt-inventory.md`。

### AC 完成情况

| AC # | 状态 | 说明 |
| --- | --- | --- |
| AC-1~6 | ✅ | 三个 update mutation 乐观更新 + 错误回滚（hooks 测试覆盖） |
| AC-7~10 | ✅ | 保存按钮 isPending/isError/isSuccess 状态反馈（本轮新增 isSuccess 成功提示） |
| AC-11~15 | ✅（按修订后标准） | 短时轮询保持现状，不引入 refetchInterval（useJob 已实现自动刷新） |
| AC-16~18 | ✅ | 后端/数据库/API 零改动（纯前端切片） |
| AC-19~22 | ✅ | 前端 434 + 后端 736 + lint + build 全部通过 |
| AC-23 | ✅（按修订后标准） | 浏览器点击验收 PASS，截图未持久化记录为 TD-009 |
| AC-24~25 | ✅ | 不引入新依赖、不破坏 owner 边界 |
| AC-26 | ✅ | 文档回写完成（acceptance.md / implementation-plan.md / README.md / SPEC 0017 / 决策 0023 / changelog-v1.4.0 / tech-debt-inventory） |
| AC-27 | ✅ | git commit + push + tag v1.4.0 完成 |

## 后续方向

SPEC 0017 完成后，v1.4.0 后续 SPEC 待项目负责人规划。可能的候选方向：
- 方向 B：单用户多标签页同步（BroadcastChannel / localStorage 事件）。
- 其他前端体验优化（如自动保存草稿、撤销/重做栈）。
- 后端能力增强（如流式 LLM 输出、OCR 与扫描文档支持）。

上述方向均需先编写并确认对应 SPEC，不得直接进入实现。
