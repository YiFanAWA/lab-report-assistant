# SPEC 0017：单用户前端实时编辑反馈

> **状态：** 草案，待项目负责人确认  
> **日期：** 2026-07-25  
> **前置：** V1.3.0 已发布并打 tag v1.3.0（SPEC 0016 技术债务清理 TD-004/005/006/008 全部收口）；当前无活跃可记录债务  
> **目标版本：** v1.4.0  
> **方向确认：** 项目负责人于 2026-07-25 明确选择方向 A（单用户前端实时编辑反馈），不引入多用户协作、不引入 WebSocket/SSE 实时通信基础设施

---

## 一、目标与边界

### 1.1 目标

在不改变产品边界（仍是本地单用户 Web MVP）和架构主线（前端只展示状态、收集输入、触发命令，不私造业务状态机）的前提下，消除当前编辑流程的"保存后等网络往返才能看到结果"和"Worker 完成后需要手动刷新"两类体验缺陷，让单用户在以下三类编辑场景获得即时反馈：

1. **实验要求 / 结构化任务单编辑**：保存后 UI 立即反映最新内容。
2. **证据卡片编辑**：保存后 UI 立即反映最新字段；Worker 生成完成后列表自动刷新。
3. **大纲编辑**：保存后 UI 立即反映最新章节；Worker 生成 Word/PPT 完成后交付物列表自动刷新。

### 1.2 范围内

| 改动点 | 当前行为 | 目标行为 | 影响层 |
| --- | --- | --- | --- |
| `useUpdatePlan` | 保存后 `invalidateQueries` 触发重新 GET，UI 等待网络往返 | `onMutate` 乐观更新缓存，UI 立即反映；`onError` 回滚；`onSettled` 统一 invalidate | 前端 hooks |
| `useUpdateEvidence` | 同上 | 同上 | 前端 hooks |
| `useUpdateOutline` | 同上 | 同上 | 前端 hooks |
| 保存状态 UI 反馈 | mutation 进行中无任何视觉提示 | 保存按钮展示"保存中…"disabled；失败展示红色错误文案；成功展示 1.5s 绿色"已保存"提示 | 前端组件（RequirementsWorkspace / EvidenceWorkspace / OutlineWorkspace 等） |
| Worker 长任务完成自动刷新 | 仅交付物列表启用 3s 轮询；证据卡片、大纲列表无轮询，用户需手动刷新 | 证据卡片生成、大纲生成、Word/PPT 生成触发的 mutation `onSuccess` 后对相关 query 启用短时轮询（最多 60s 或直到状态稳定） | 前端 hooks |
| 错误反馈 | mutation `onError` 缺失，失败时 UI 静默 | 所有 update mutation 新增 `onError`，从 `AppError` 结构化错误中提取 `error_code` 和 `message`，展示给用户 | 前端 hooks + 组件 |
| 跨组件状态联动 | 同项目下不同 query 之间状态不联动（编辑大纲时若已打开交付物视图不会看到状态推进） | 通过精确 `invalidateQueries` 的 `queryKey` 范围控制，让保存后相关联的 query 同步刷新（但不破坏 owner 边界：前端只刷新后端返回的真相，不私造状态） | 前端 hooks |

### 1.3 范围外（不做清单）

| 不做项 | 原因 | 后续入口 |
| --- | --- | --- |
| 不引入 WebSocket / SSE / 长轮询基础设施 | 方向 A 明确不引入实时通信；TanStack Query 的 `refetchInterval` 短时轮询已足够覆盖 Worker 长任务完成场景 | 多用户协作版本（产品边界变更后） |
| 不引入多用户身份、权限、冲突解决（OT/CRDT） | 违反 AGENTS.md "不做多人协作"产品边界 | 永久不做（V1 范围内） |
| 不修改后端 API 路由、schema、状态机、数据库表 | 后端合同已在 SPEC 0002~0006 锁定，本轮纯前端体验优化 | 永久不做（本轮范围） |
| 不引入新的状态管理库（Zustand / Redux / Jotai 等） | TanStack Query 的 `queryClient.setQueryData` 已能满足乐观更新需求，引入新库增加心智负担 | 永久不做 |
| 不修改 `python_executor`、Worker handler、`LLMGateway` 等后端业务模块 | 本轮纯前端切片 | 永久不做（本轮范围） |
| 不重构前端路由结构和组件树 | 本轮聚焦 hooks 和组件内的保存反馈，不破坏 SPEC 0009 已建立的前端测试覆盖 | V2.0 |
| 不引入新的 npm 依赖 | TanStack Query 5 已提供所有需要的能力 | 永久不做 |
| 不引入新的 LLM 缓存层、新的 Docker 配置、新的 CI 步骤 | 本轮不涉及基础设施 | V2.0 |
| 不修改前端测试框架（仍用 Vitest + React Testing Library） | SPEC 0009 已锁定前端测试框架 | 永久不做 |
| 不实现"撤销/重做"栈 | 方向 A 只做单步保存的乐观更新和回滚，不维护编辑历史 | V2.0 |
| 不实现"自动保存草稿" | 本轮只在用户显式触发保存时做乐观更新；自动保存涉及防抖策略和后端 API 改动 | V2.0 |
| 不实现多标签页同步（BroadcastChannel / localStorage 事件） | 这属于方向 B（多端同步），方向 A 不覆盖 | 待项目负责人决定是否进入方向 B |

### 1.4 与 V1.3.0 的关系

V1.3.0 已完成 SPEC 0016 技术债务清理，债务清零。本切片是 V1.3.0 之后的第一个功能增强切片，属于 v1.4.0 版本。按 AGENTS.md 阶段闸，进入 v1.4.0 实现前必须先确认本 SPEC。

### 1.5 与产品边界的关系

本切片严格遵守 [AGENTS.md](../../AGENTS.md) "产品边界" 章节：

- **只做本地单用户 Web MVP**：不引入任何多用户身份、账号、权限、冲突解决机制。
- **不做多人协作**：所有"实时反馈"均指单用户在单浏览器标签页内的编辑体验优化，不涉及跨用户、跨设备同步。
- **不绕过 owner 边界**：前端只展示后端返回的真相，乐观更新只在缓存层临时反映用户输入，最终真相仍以后端 `invalidateQueries` 后的 GET 响应为准。

---

## 二、架构设计

### 2.1 分层影响

```text
SPEC 0017 改动层
  ↓
apps/web/src/features/{requirements,evidence,outlines}/hooks.ts
  → 新增 onMutate / onError / onSettled 回调
  → 新增 refetchInterval 短时轮询（仅 Worker 长任务相关 query）
  ↓ 影响层
apps/web/src/routes/*WorkspaceView.tsx
  → 保存按钮新增 isPending / isError / isSuccess 状态展示
  → 失败时展示 AppError 结构化错误
  ↓ 影响层
apps/web/src/shared/* (错误展示组件、Toast 等)
  → 复用现有 AppError 消费机制（SPEC 0009 已建立）
  ↓ 不影响层
server/app/**                → 后端业务模块、API、数据库、Worker 全部不动
```

### 2.2 唯一 Owner 边界

| 层 | Owner 文件 | 职责 | 本轮改动 |
| --- | --- | --- | --- |
| 前端 hooks | `apps/web/src/features/requirements/hooks.ts` | 实验要求/任务单的 TanStack Query 调用 | `useUpdatePlan` 新增乐观更新 |
| 前端 hooks | `apps/web/src/features/evidence/hooks.ts` | 证据卡片的 TanStack Query 调用 | `useUpdateEvidence` 新增乐观更新；`useGenerateEvidence` 后启用短时轮询 |
| 前端 hooks | `apps/web/src/features/outlines/hooks.ts` | 大纲与交付物的 TanStack Query 调用 | `useUpdateOutline` 新增乐观更新；`useGenerateOutline` / `useGenerateWord` / `useGeneratePpt` 后启用短时轮询 |
| 前端组件 | `apps/web/src/routes/*WorkspaceView.tsx` 等 | 编辑 UI 与保存反馈 | 按钮状态、错误展示、成功提示 |
| 前端共享 | `apps/web/src/shared/` | AppError 类型与展示组件 | 复用现有，不新增 |
| 后端业务模块 | `server/app/modules/` | 业务真相 owner | **不改动** |
| 后端 API | `server/app/api/routers/` | HTTP 协议映射 | **不改动** |
| 后端 Worker | `server/worker/` | 后台任务执行 | **不改动** |
| 数据库 | `server/app/infrastructure/database/` | 业务表 | **不改动** |
| Alembic 迁移 | `server/alembic/versions/` | 迁移文件 | **不改动** |

### 2.3 关键决策 1：乐观更新而非乐观 UI

**决策：** 在 TanStack Query mutation 的 `onMutate` 阶段调用 `qc.setQueryData` 直接修改缓存，让所有订阅该 query 的组件立即重渲染；而非在组件本地 state 中临时保存编辑值再覆盖显示。

**理由：**
- `setQueryData` 是 TanStack Query 官方推荐的乐观更新方式，与现有 `queryKey` 组织方式天然兼容。
- 组件本地 state 方案需要每个编辑组件单独维护"乐观值 vs 真相值"两套 state，违反 DRY，且容易在 `onError` 回滚时遗漏分支。
- 缓存层方案让所有订阅同一 `queryKey` 的组件自动同步（例如大纲编辑面板和侧边栏大纲列表），无需手动传递 state。

**风险：**
- 若后端返回结构与前端缓存结构不一致（例如后端返回 `{id, content, updated_at}` 但前端缓存的是 `{id, content, status}`），`setQueryData` 后会写入不一致数据。
- **缓解：** 实现时必须验证每个 mutation 的响应 schema 与 query 缓存 schema 完全一致；若不一致，在 `onMutate` 中只更新共同字段，在 `onSettled` 中 invalidate 触发完整 GET 刷新。

### 2.4 关键决策 2：错误回滚使用 `onError` + 快照恢复

**决策：** `onMutate` 中先 `qc.getQueryData` 保存当前快照，再 `setQueryData` 写入乐观值；`onError` 中 `qc.setQueryData(snapshot)` 恢复；`onSettled` 中无条件 `invalidateQueries` 触发最终真相刷新。

**理由：**
- 这是 TanStack Query 官方推荐的"乐观更新 + 错误回滚"模式（[官方文档](https://tanstack.com/query/latest/docs/framework/react/guides/optimistic-updates)）。
- `onSettled` 无条件 invalidate 保证最终一致：即使乐观值与后端一致，也通过 GET 重新校验，防止后端做了额外加工（如 `updated_at` 字段、状态机推进）未反映在前端缓存。
- 回滚到 `onMutate` 时保存的快照而非"上一个 GET 响应"，避免竞态（用户在 mutation 进行中又触发了别的 mutation）。

### 2.5 关键决策 3：Worker 长任务用短时轮询而非事件推送

**决策：** 对以下 query 在触发生成 mutation 成功后启用 `refetchInterval` 短时轮询，而非引入 SSE/WebSocket：

| Query | 触发条件 | 轮询间隔 | 停止条件 |
| --- | --- | --- | --- |
| 证据卡片列表 `["evidence", projectId, "list"]` | `useGenerateEvidence` `onSuccess` | 2_000ms | 列表中存在 `status === "CANDIDATE"` 或 `"STALE"` 的卡片时停止；或轮询超过 60 次后停止（2 分钟上限） |
| 大纲列表 `["outlines", projectId, "list"]` | `useGenerateOutline` `onSuccess` | 2_000ms | 列表中存在 `status === "CANDIDATE"` 的最新大纲时停止；或 60 次上限 |
| 交付物列表 `["deliverables", projectId, "list"]` | `useGenerateWord` / `useGeneratePpt` `onSuccess` | 保持现有 3_000ms 轮询 | 维持现状（已实现） |

**理由：**
- 证据卡片和大纲的 Worker 生成耗时通常在 5~30s 内，短时轮询实现简单、无新依赖。
- 现有 `useDeliverables` 已用 `refetchInterval: 3_000` 验证过该模式可行，本切片只是将同一模式扩展到证据卡片和大纲。
- 引入 SSE/WebSocket 需要后端基础设施改动（事件总线、连接管理），违反"不修改后端"范围。
- 60 次上限（2 分钟）作为兜底，避免 Worker 卡死时前端无限轮询。

**实现要点：**
- 不在 query 定义中硬编码 `refetchInterval`（否则会一直轮询），而是在 mutation `onSuccess` 中通过 `qc.setQueryDefaults(queryKey, { refetchInterval: 2_000 })` 动态启用。
- 在停止条件满足后通过 `qc.setQueryDefaults(queryKey, { refetchInterval: false })` 关闭。
- 或使用 `useQuery` 的 `refetchInterval` 函数形式：`refetchInterval: (query) => shouldStop(query) ? false : 2_000`。

### 2.6 关键决策 4：保存状态 UI 反馈使用 mutation 内置状态

**决策：** 使用 TanStack Query mutation 的 `isPending` / `isError` / `isSuccess` / `error` 内置状态，不在组件本地额外维护 `useState`。

**理由：**
- TanStack Query 已维护这些状态，无需重复造轮子。
- `isSuccess` 短暂展示后通过 `reset()` 重置（避免下次进入编辑时仍显示"已保存"）。
- `error` 字段已是 `AppError` 结构化错误（后端 SPEC 0001~0006 已统一错误格式），直接消费即可。

**UI 规范：**
- `isPending === true`：保存按钮显示"保存中…"，`disabled`，避免重复提交。
- `isError === true`：保存按钮恢复可点击，按钮下方展示红色错误文案，文案来自 `error.message`（中文）。
- `isSuccess === true`：保存按钮短暂显示绿色"已保存"1.5s 后自动 `reset()`。
- 表单字段值不因 `isError` 清空（保留用户输入便于修改后重试）。

### 2.7 关键决策 5：不破坏 SPEC 0009 前端测试覆盖

**决策：** 现有 `apps/web/src/**/*.test.tsx` 中 411 个测试全部保持通过；新增测试覆盖乐观更新、错误回滚、状态反馈、短时轮询四类场景。

**理由：**
- SPEC 0009 已建立完整前端测试覆盖，本轮改动若导致测试回归即破坏 SPEC 0009 验收。
- 新增测试必须用 React Testing Library 的 `waitFor`、`findBy*` 等异步断言，避免用 `getBy*` 在乐观更新未渲染时报错。

---

## 三、实现细节

### 3.1 `useUpdatePlan` 改造（实验要求 / 任务单）

**文件：** `apps/web/src/features/requirements/hooks.ts`

**当前实现（第 75-84 行）：**

```typescript
export function useUpdatePlan(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ planId, payload }: { planId: string; payload: RequirementPlanPayload }) =>
      updatePlan(projectId, planId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...projectKey(projectId), "plan"] });
    },
  });
}
```

**改动后：**

```typescript
export function useUpdatePlan(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ planId, payload }: { planId: string; payload: RequirementPlanPayload }) =>
      updatePlan(projectId, planId, payload),
    onMutate: async ({ planId, payload }) => {
      // 取消正在进行的 GET，避免覆盖乐观更新
      await qc.cancelQueries({ queryKey: [...projectKey(projectId), "plan"] });
      // 保存快照用于回滚
      const snapshot = qc.getQueryData([...projectKey(projectId), "plan"]);
      // 乐观写入（仅更新 payload 中的字段，保留其他字段不变）
      qc.setQueryData([...projectKey(projectId), "plan"], (old: any) => {
        if (!old) return old;
        return { ...old, ...payload, id: planId };
      });
      return { snapshot };
    },
    onError: (error, _vars, context) => {
      // 回滚到快照
      if (context?.snapshot) {
        qc.setQueryData([...projectKey(projectId), "plan"], context.snapshot);
      }
    },
    onSettled: () => {
      // 无论成功失败，最终都 invalidate 触发真相刷新
      qc.invalidateQueries({ queryKey: [...projectKey(projectId), "plan"] });
    },
  });
}
```

**测试要点：**
- `onMutate` 后 `getQueryData` 返回的应是包含新 payload 的对象。
- 模拟 `updatePlan` reject 后，`getQueryData` 应恢复为 `snapshot`。
- `onSettled` 后应触发一次 `invalidateQueries`。

### 3.2 `useUpdateEvidence` 改造（证据卡片）

**文件：** `apps/web/src/features/evidence/hooks.ts`

**关键差异：** 证据卡片是列表 query（`["evidence", projectId, "list", filters]`），乐观更新需要在列表中找到对应 `cardId` 的项进行替换，而非整体替换。

**改动后核心：**

```typescript
export function useUpdateEvidence(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ cardId, payload }) => updateEvidence(projectId, cardId, payload),
    onMutate: async ({ cardId, payload }) => {
      await qc.cancelQueries({ queryKey: [...evidenceKey(projectId), "list"] });
      const snapshot = qc.getQueryData([...evidenceKey(projectId), "list"]);
      qc.setQueryData([...evidenceKey(projectId), "list"], (old: any) => {
        if (!old || !Array.isArray(old)) return old;
        return old.map((card: any) =>
          card.id === cardId ? { ...card, ...payload } : card
        );
      });
      return { snapshot };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.snapshot) {
        qc.setQueryData([...evidenceKey(projectId), "list"], ctx.snapshot);
      }
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: [...evidenceKey(projectId), "list"] });
    },
  });
}
```

**注意：** 列表 query 可能带 `filters`（如 `{source_id, status}`），乐观更新时需要同时更新所有缓存的列表变体。实现时使用 `qc.setQueriesData({ queryKey: ["evidence", projectId] }, updater)` 批量更新所有匹配的列表。

### 3.3 `useUpdateOutline` 改造（大纲）

**文件：** `apps/web/src/features/outlines/hooks.ts`

**与 §3.2 同型：** 大纲也是列表 query，需要 `setQueriesData` 批量更新。

### 3.4 短时轮询实现

**文件：** `apps/web/src/features/evidence/hooks.ts`、`apps/web/src/features/outlines/hooks.ts`

**证据卡片列表 query 改造：**

```typescript
export function useEvidenceCards(
  projectId: string,
  filters?: { source_id?: string; status?: string }
) {
  return useQuery({
    queryKey: [...evidenceKey(projectId), "list", filters ?? {}],
    queryFn: () => listEvidence(projectId, filters),
    staleTime: 5_000,
    // SPEC 0017：动态轮询，由 useGenerateEvidence 的 onSuccess 启用
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!Array.isArray(data)) return false;
      // 存在 PENDING/GENERATING 状态的卡片时继续轮询
      const hasPending = data.some(
        (c: any) => c.status === "PENDING" || c.status === "GENERATING"
      );
      return hasPending ? 2_000 : false;
    },
  });
}
```

**`useGenerateEvidence` 改造：**

```typescript
export function useGenerateEvidence(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) => generateEvidence(projectId, sourceId),
    onSuccess: () => {
      // invalidate 后 query 重新拉取，refetchInterval 函数会根据返回的状态判断是否继续轮询
      qc.invalidateQueries({ queryKey: [...evidenceKey(projectId), "list"] });
    },
  });
}
```

**实现要点：**
- `refetchInterval` 函数形式让 query 自身根据数据状态决定是否继续轮询，无需在 mutation 中手动启停。
- 一旦列表中所有卡片都达到稳定状态（`CANDIDATE` / `CONFIRMED` / `REJECTED` / `STALE` / `FAILED`），轮询自动停止。
- 兜底：若 Worker 卡死导致状态永远不变化，需在 query options 中加入 `refetchInterval: false` 的最大次数限制（实现时通过自定义 hook 包装或在 `refetchInterval` 中加入计数器，需在实现时细化，草案阶段先标注为已知风险）。

### 3.5 保存状态 UI 反馈

**文件：** `apps/web/src/routes/*WorkspaceView.tsx` 等编辑组件

**示例（RequirementWorkspaceView 中的保存按钮）：**

```tsx
const updatePlan = useUpdatePlan(projectId);

// 保存按钮
<button
  type="submit"
  disabled={updatePlan.isPending}
  className={updatePlan.isError ? "btn-error" : updatePlan.isSuccess ? "btn-success" : "btn-primary"}
>
  {updatePlan.isPending ? "保存中…" : updatePlan.isSuccess ? "已保存" : "保存"}
</button>

{updatePlan.isError && (
  <p className="text-red-600 text-sm">
    保存失败：{(updatePlan.error as AppError)?.message ?? "未知错误"}
  </p>
)}

// 成功提示 1.5s 后自动重置
useEffect(() => {
  if (updatePlan.isSuccess) {
    const t = setTimeout(() => updatePlan.reset(), 1_500);
    return () => clearTimeout(t);
  }
}, [updatePlan.isSuccess]);
```

**UI 规范：**
- 不引入 Toast 库（避免新增依赖）；用内联状态展示。
- 错误文案必须来自后端 `AppError.message`（中文），不展示裸 `error.message`（避免英文堆栈）。
- 表单字段值不因 `isError` 清空（保留用户输入）。

### 3.6 AppError 类型复用

**文件：** `apps/web/src/shared/types.ts`（已存在）

本切片**不修改** `AppError` 类型，只在编辑组件中消费。已有 `AppError` 结构：

```typescript
interface AppError {
  error_code: string;  // 例如 "REQUIREMENT_PLAN_NOT_FOUND"
  message: string;     // 中文用户可读消息
  details?: Record<string, unknown>;
}
```

---

## 四、API 合同

### 4.1 不修改任何现有 API

V1.4.0 **不修改任何现有 API 路由合同**。本切片是前端体验优化，不涉及业务模块、API 路由或 schema 变更。

### 4.2 不新增 API

本轮**不新增**任何 API 端点。

### 4.3 不修改前端 API 调用层

`apps/web/src/features/{requirements,evidence,outlines}/api.ts` 中的 `fetchXxx` / `updateXxx` 函数签名**不变**。本轮只改 hooks 层的 `useMutation` 配置和组件层的 UI 反馈。

---

## 五、测试策略

### 5.1 新增前端单元测试

**文件：**
- `apps/web/src/features/requirements/hooks.test.tsx`（新增或扩展）
- `apps/web/src/features/evidence/hooks.test.tsx`（新增或扩展）
- `apps/web/src/features/outlines/hooks.test.tsx`（新增或扩展）
- `apps/web/src/routes/*WorkspaceView.test.tsx`（扩展保存按钮状态测试）

**测试覆盖矩阵：**

| 测试场景 | 覆盖点 | 预期 |
| --- | --- | --- |
| 乐观更新成功 | `useUpdatePlan` 调用后，mutation pending 期间 `getQueryData` 已反映新值 | 通过 |
| 乐观更新失败回滚 | `updatePlan` reject 后，`getQueryData` 恢复为原值 | 通过 |
| `onSettled` 无条件 invalidate | 无论成功失败，`invalidateQueries` 被调用一次 | 通过 |
| 错误展示 | mutation 失败后组件展示 `AppError.message` | 通过 |
| 成功提示自动重置 | `isSuccess` 后 1.5s `reset()` 被调用 | 通过 |
| 按钮禁用 | `isPending` 时按钮 `disabled` | 通过 |
| 列表型乐观更新 | `useUpdateEvidence` 在列表中正确替换对应 cardId 项 | 通过 |
| 列表型乐观更新失败回滚 | 列表恢复为 snapshot | 通过 |
| 短时轮询启用 | `useGenerateEvidence` 成功后，列表 query 的 `refetchInterval` 返回 2_000 | 通过 |
| 短时轮询停止 | 列表中所有卡片状态稳定后，`refetchInterval` 返回 false | 通过 |
| 不影响其他 query | 乐观更新 evidence 不影响 outline query | 通过 |

**预计新增测试：** ~30 个（hooks 层 ~20 + 组件层 ~10）

### 5.2 现有测试零回归

**要求：** SPEC 0009 已建立的 411 个前端测试全部保持通过。实现完成后必须运行：

```bash
cd apps/web
npm run test
```

预期：411 + ~30 = ~441 passed。

### 5.3 后端测试零回归

本切片不修改后端，但实现完成后仍需运行后端测试确认无回归：

```bash
cd server
.venv\Scripts\python.exe -m pytest
```

预期：736 passed, 0 warnings（与 V1.3.0 一致）。

### 5.4 验收命令

按 AGENTS.md 基础验收命令：

```text
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
```

**预期：**
- pytest: 736 passed, 0 warnings（无后端改动）
- alembic: 迁移无变化（本切片无数据库变更）
- lint: TypeScript 通过
- build: Vite 构建通过

### 5.5 UI 浏览器验收

按 AGENTS.md "UI 行为变化应做浏览器点击或截图验收"（SPEC 0016 已明确 V1.0 之后的新切片若有 UI 变化需做浏览器验收），本切片涉及保存按钮状态和错误文案展示，必须做浏览器验收：

- 启动后端 + Worker + 前端
- 在 RequirementWorkspaceView 编辑任务单并保存，截图"保存中…"状态
- 模拟网络失败（断开后端），保存后截图红色错误文案
- 在 EvidenceWorkspaceView 触发生成证据卡片，截图列表自动刷新过程

**证据保存路径：** `dev-docs/e2e-screenshots/spec-0017/`

---

## 六、依赖

### 6.1 不新增依赖

本切片**不引入任何新 npm 依赖**。所有能力由 `@tanstack/react-query` 5.x 现有 API 提供：
- `useMutation` 的 `onMutate` / `onError` / `onSettled`
- `useQuery` 的 `refetchInterval` 函数形式
- `queryClient.setQueryData` / `getQueryData` / `setQueriesData` / `cancelQueries` / `invalidateQueries`

### 6.2 依赖版本

| 依赖 | 当前版本 | 本轮改动 |
| --- | --- | --- |
| `@tanstack/react-query` | 5.101.0 | 不升级 |
| `react` | 19.2.7 | 不升级 |
| `typescript` | 6.0.3 | 不升级 |
| `vitest` | 4.1.10 | 不升级 |
| `@testing-library/react` | ^16.0.0 | 不升级 |

---

## 七、验收标准

| AC # | 验收项 | 通过标准 |
| --- | --- | --- |
| AC-1 | `useUpdatePlan` 乐观更新 | `onMutate` 后 `getQueryData` 立即反映新 payload；mock API 成功响应后 `onSettled` 触发 invalidate |
| AC-2 | `useUpdatePlan` 错误回滚 | mock API reject 后，`getQueryData` 恢复为 `onMutate` 前的快照 |
| AC-3 | `useUpdateEvidence` 乐观更新 | 列表中对应 cardId 的项被替换为新 payload；其他项不变 |
| AC-4 | `useUpdateEvidence` 错误回滚 | 列表恢复为 snapshot |
| AC-5 | `useUpdateOutline` 乐观更新 | 同 AC-3 模式 |
| AC-6 | `useUpdateOutline` 错误回滚 | 同 AC-4 模式 |
| AC-7 | 保存按钮 isPending 状态 | 保存中按钮 `disabled`，文案"保存中…" |
| AC-8 | 保存错误展示 | 失败时按钮下方展示红色 `AppError.message`（中文） |
| AC-9 | 保存成功提示 | 成功后按钮短暂绿色"已保存"1.5s 后 `reset()` |
| AC-10 | 表单字段不清空 | 失败后用户输入保留 |
| AC-11 | 证据卡片列表短时轮询 | `useGenerateEvidence` 成功后列表 query 启用 2s 轮询 |
| AC-12 | 证据卡片轮询停止 | 列表中所有卡片状态稳定后轮询停止 |
| AC-13 | 大纲列表短时轮询 | `useGenerateOutline` 成功后列表 query 启用 2s 轮询 |
| AC-14 | 大纲轮询停止 | 列表中存在 CANDIDATE 状态大纲时停止 |
| AC-15 | 交付物列表轮询维持现状 | 不修改 `useDeliverables` 的 `refetchInterval: 3_000` |
| AC-16 | 后端零改动 | `git diff server/` 无变化（除可能的 dev-docs 引用） |
| AC-17 | 数据库零改动 | 无新增 Alembic 迁移 |
| AC-18 | API 零改动 | `git diff server/app/api/` 无变化 |
| AC-19 | 前端测试通过 | 411 + 新增 ~30 = ~441 passed |
| AC-20 | 后端测试零回归 | 736 passed, 0 warnings |
| AC-21 | TypeScript 类型检查 | `npm run lint`（tsc --noEmit）通过 |
| AC-22 | Vite 构建 | `npm run build` 通过 |
| AC-23 | 浏览器验收 | 截图保存到 `dev-docs/e2e-screenshots/spec-0017/`，覆盖保存中/失败/成功三种状态和列表自动刷新 |
| AC-24 | 不引入新依赖 | `package.json` 和 `package-lock.json` 无新增依赖 |
| AC-25 | 不破坏 owner 边界 | 前端不私造业务状态机，所有真相仍以后端 GET 响应为准（`onSettled` 必触发 invalidate） |
| AC-26 | 文档回写 | `acceptance.md` 新增 SPEC 0017 收口记录；`implementation-plan.md` 同步；`README.md` 用户文档无需改动（纯体验优化）；新增决策记录 `decisions/0023-start-spec-0017-frontend-realtime-edit-feedback.md` |
| AC-27 | 版本收口 | 完成中文 commit "完成 SPEC 0017 单用户前端实时编辑反馈"，push 到 origin/master，打 tag v1.4.0 |

---

## 八、实施顺序

按 AGENTS.md 阶段闸：

1. **SPEC 0017 文档确认**（本文件，待项目负责人批准）
2. **新增决策记录** `dev-docs/decisions/0023-start-spec-0017-frontend-realtime-edit-feedback.md`
3. **测试先行**：编写 hooks 层和组件层的新增测试（先红）
4. **hooks 层实现**：`useUpdatePlan` / `useUpdateEvidence` / `useUpdateOutline` 乐观更新 + 错误回滚
5. **hooks 层实现**：`useEvidenceCards` / `useOutlines` 短时轮询
6. **组件层实现**：保存按钮状态、错误展示、成功提示
7. **本地测试**：`npm run test` 全部通过
8. **类型检查与构建**：`npm run lint` + `npm run build`
9. **浏览器验收**：截图保存到 `dev-docs/e2e-screenshots/spec-0017/`
10. **后端回归验证**：`pytest` + `alembic upgrade head`（确认无后端改动）
11. **文档回写**：`acceptance.md`、`implementation-plan.md`、`decisions/0023`
12. **git 边界复核 → 精确 stage → commit → push → git tag v1.4.0 → push --tags**

---

## 九、风险与回退

### 9.1 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| 乐观更新写入不一致数据 | 中 | UI 短暂显示错误数据 | `onSettled` 必触发 invalidate 用后端真相覆盖；实现时核对 mutation 响应 schema 与 query 缓存 schema |
| 列表型乐观更新漏掉某些 filter 变体 | 中 | 部分列表 UI 未更新 | 使用 `setQueriesData` 批量更新所有匹配 `["evidence", projectId]` 前缀的 query |
| 短时轮询不停止 | 低 | 浏览器性能损耗 | `refetchInterval` 函数形式根据数据状态返回 false；实现时验证停止条件 |
| 后端 `AppError` 格式不一致 | 低 | 错误文案展示异常 | 复用 SPEC 0009 已建立的 AppError 类型；测试覆盖 |
| 现有 411 个前端测试回归 | 中 | SPEC 0009 验收被破坏 | 实现后必须运行完整测试套件；逐个排查失败用例 |
| 浏览器验收工具不可用 | 低 | 无法截图 | 若 browser_use agent 不可用，记录替代证据（如手动截图或控制台日志） |

### 9.2 回退方案

如本切片引入阻断问题，可通过以下方式回退：

1. **hooks 层回退：** 还原 `hooks.ts` 文件（git revert），恢复 `onSuccess: () => invalidateQueries` 模式
2. **组件层回退：** 还原 `*WorkspaceView.tsx` 中保存按钮的状态展示代码
3. **轮询回退：** 移除 `refetchInterval` 函数形式，恢复为不轮询

回退后用户体验回到 V1.3.0 状态（保存后等网络往返、Worker 完成后需手动刷新），不阻断核心功能。

### 9.3 最大回归风险

**最大风险：** 乐观更新逻辑写错导致 UI 显示与后端真相不一致，用户误以为已保存但实际未保存。

**阻断证据：**
- AC-1~AC-6 通过 hooks 测试覆盖乐观更新和回滚
- AC-25 通过 `onSettled` 必触发 invalidate 保证最终一致
- AC-23 浏览器验收人工复核保存后 UI 与刷新后 UI 一致

---

## 十、确认事项（待项目负责人确认）

> 本章节的技术决策需项目负责人确认后方可进入实现。

### 10.1 乐观更新使用 `setQueryData` 而非组件本地 state

**决策：** 见 §2.3。

**理由：** TanStack Query 官方推荐模式，与现有 queryKey 组织方式兼容。

### 10.2 Worker 长任务用短时轮询而非事件推送

**决策：** 见 §2.5。

**理由：** 不引入 WebSocket/SSE 基础设施，符合方向 A 范围。

### 10.3 保存状态 UI 反馈使用 mutation 内置状态

**决策：** 见 §2.6。

**理由：** 不引入额外 state 库或 Toast 库。

### 10.4 不引入新依赖

**决策：** 见 §6.1。

**理由：** TanStack Query 5.x 现有能力足够。

### 10.5 v1.4.0 版本号

**决策：** 本切片发布为 v1.4.0。

**理由：** 按 V1.0/V1.1.0/V1.2.0/V1.3.0 的版本号惯例，功能增强切片作为新版本发布。如项目负责人认为不应升级版本号，可改为 v1.3.1 或不打 tag。

### 10.6 浏览器验收执行方式

**决策：** 使用 browser_use agent 执行浏览器点击截图验收。

**理由：** AGENTS.md "UI 行为变化应做浏览器点击或截图验收"（SPEC 0016 TD-006 已明确 V1.0 之后的新切片若有 UI 变化需做浏览器验收）。

---

## 十一、与 v1.4.0 整体规划的关系

本切片是 v1.4.0 的第一个 SPEC（前端体验优化切片）。按 AGENTS.md "多 SPEC 版本规划时需保证各 SPEC 关注点正交、风险隔离、独立验收"：

| SPEC | 关注点 | owner 层 | 风险隔离 |
| --- | --- | --- | --- |
| SPEC 0017 | 单用户前端实时编辑反馈 | 前端 hooks + 组件 | 不触碰后端业务代码、API 合同、数据库 |

本切片不依赖 v1.4.0 后续 SPEC，可独立验收。v1.4.0 后续 SPEC 待项目负责人规划。

---

## 十二、停止条件

本切片完成的停止条件：

1. AC-1~AC-27 全部通过
2. 前端测试 ~441 passed（411 + 新增 ~30）
3. 后端测试 736 passed, 0 warnings（零回归）
4. TypeScript 类型检查通过
5. Vite 构建通过
6. 浏览器验收截图保存到 `dev-docs/e2e-screenshots/spec-0017/`
7. 项目负责人确认收口
8. 完成 git commit + push + tag v1.4.0

---

## 十三、未在本切片处理的已知问题

| 问题 | 不处理原因 | 后续入口 |
| --- | --- | --- |
| 多标签页同步（同一用户在多个浏览器标签页编辑同一项目） | 属于方向 B，本切片不覆盖 | 待项目负责人决定是否进入方向 B |
| 自动保存草稿 | 涉及防抖策略和后端 API 改动 | V2.0 |
| 撤销/重做栈 | 超出方向 A 范围 | V2.0 |
| 短时轮询的 60 次上限兜底实现细节 | 草案阶段先标注为已知风险，实现时细化（可通过 `refetchInterval` 函数中维护计数器或在 `useQuery` 外层包装 hook） | 实现时细化，不阻塞 SPEC 确认 |
| 前端编辑组件完全重构 | 本轮聚焦 hooks 和保存反馈，不破坏 SPEC 0009 测试覆盖 | V2.0 |
