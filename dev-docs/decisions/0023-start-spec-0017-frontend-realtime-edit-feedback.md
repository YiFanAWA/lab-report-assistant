# 决策 0023：启动 SPEC 0017 单用户前端实时编辑反馈切片

> **日期：** 2026-07-25  
> **状态：** 已确认，进入实现阶段  
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

待实现完成后回写。

## 后续方向

SPEC 0017 完成后，v1.4.0 后续 SPEC 待项目负责人规划。可能的候选方向：
- 方向 B：单用户多标签页同步（BroadcastChannel / localStorage 事件）。
- 其他前端体验优化（如自动保存草稿、撤销/重做栈）。
- 后端能力增强（如流式 LLM 输出、OCR 与扫描文档支持）。

上述方向均需先编写并确认对应 SPEC，不得直接进入实现。
