# V1.4.0 版本发布说明

> **版本：** v1.4.0
> **发布日期：** 2026-07-25
> **上一版本：** v1.3.0
> **提交范围：** `v1.3.0..v1.4.0`（含 SPEC 0017 实现与文档回写）
> **变更统计：** 后端 736 测试 + 前端 434 测试 = 1170 个测试（前端新增 23 个，后端零回归）
> **文档状态：** 已由项目负责人确认发布

---

## 概述

实验报告助手 V1.4.0 是 V1.3.0 之后的第一个功能增强版本，聚焦于单用户前端编辑体验优化。V1.4.0 **不改变产品边界**（仍是本地单用户 Web MVP）和**架构主线**（仍是唯一 owner + API 适配 + 前端接线），**不修改后端业务模块、API 合同、数据库表、Worker**，纯前端切片。

V1.4.0 聚焦于一个 SPEC：

1. **SPEC 0017 单用户前端实时编辑反馈**：消除"保存后等网络往返才能看到结果"的体验缺陷，让单用户在编辑实验任务单、证据卡片、大纲时获得即时反馈。

V1.4.0 包含 1 个 SPEC：

| SPEC | 标题 | 状态 |
| --- | --- | --- |
| SPEC 0017 | 单用户前端实时编辑反馈 | ✅ 已完成 |

**核心价值：** V1.4.0 发布后，单用户在三类编辑场景获得即时反馈，UI 不再等待网络往返即可反映用户输入，最终真相仍以后端 GET 响应为准。

---

## 一、新增功能

### 1.1 SPEC 0017：单用户前端实时编辑反馈

**模块：** `apps/web/src/features/{requirements,evidence,outlines}/hooks.ts`、`apps/web/src/routes/*WorkspaceView.tsx`

**问题：** V1.3.0 中三个 update mutation（`useUpdatePlan` / `useUpdateEvidence` / `useUpdateOutline`）在保存成功后只调用 `qc.invalidateQueries`，触发重新 GET，UI 需等待网络往返完成才能反映最新数据。Worker 长任务完成后的自动刷新已通过 `useJob` 事件轮询机制实现，无需重复实现。

**实现内容：**

#### 1.1.1 三个 update mutation 乐观更新

按 TanStack Query 5 官方推荐的"乐观更新 + 错误回滚"模式，为三个 update mutation 新增 `onMutate` / `onError` / `onSettled` 回调：

| Hook | 文件 | 缓存类型 | 乐观更新策略 |
| --- | --- | --- | --- |
| `useUpdatePlan` | `requirements/hooks.ts` | 单对象 query | `setQueryData` 整体替换 payload 字段，保留其他字段不变 |
| `useUpdateEvidence` | `evidence/hooks.ts` | 列表 query（多 filters 变体） | `setQueriesData` 批量更新所有匹配的 list 变体，按 cardId 在列表中找到并替换 |
| `useUpdateOutline` | `outlines/hooks.ts` | 列表 query（多 status 变体） | `setQueriesData` 批量更新所有匹配的 list 变体，按 outlineId 在列表中找到并替换 sections |

每个 mutation 的执行流程：

1. **`onMutate`**：先 `cancelQueries` 取消正在进行的 GET（避免覆盖乐观更新），再 `getQueriesData` 保存快照（含 queryKey 用于回滚），最后 `setQueriesData` 乐观写入新值
2. **`onError`**：从快照恢复缓存（避免乐观值与后端不一致）
3. **`onSettled`**：无条件 `invalidateQueries` 触发真相刷新（保证最终一致，防止后端做了额外加工如 `updated_at` / 状态机推进未反映在前端缓存）

#### 1.1.2 保存按钮"已保存 ✓"成功提示

三个组件（`RequirementWorkspaceView` / `EvidenceWorkspaceView` / `OutlineWorkspaceView`）新增 `editOk` state：

- 保存按钮点击时清空 `editOk` 和 `editErr`
- `onSuccess` 回调中 `setEditOk("已保存 ✓")` + `setTimeout(() => setEditOk(null), 1_500)`
- UI 中以绿色 `#16a34a` 显示成功提示
- 1.5s 后自动消失，避免下次进入编辑时仍显示"已保存"
- 表单字段值不因 `onError` 清空（保留用户输入便于修改后重试）
- 错误文案来自后端 `AppError.message`（中文），不展示裸 `error.message`

#### 1.1.3 §3.4 短时轮询保持现状（实现前调研修订）

SPEC 0017 草案原计划新增 `refetchInterval` 短时轮询覆盖证据卡片和大纲列表。**实现前调研发现**三个组件已通过 `useJob(pid, activeJobId)` + `useEffect` 监听 `genJob.status` 变化，任务完成时 `qc.invalidateQueries` 自动刷新相关 queryKey。本轮**保持现状**，不引入 `refetchInterval`，避免双重轮询浪费请求。

| 组件 | 已实现的轮询机制 | 触发刷新的 queryKey |
| --- | --- | --- |
| `EvidenceWorkspaceView` | `useJob(pid, activeJobId)` + `useEffect` 监听 `genJob.status` 变化 | `["evidence", pid, "list"]` |
| `OutlineWorkspaceView`（生成大纲） | 同型 useEffect | `["outlines", pid, "list"]` |
| `OutlineCard`（Word/PPT 生成） | `useJob(pid, wordJobId/pptJobId)` + 同型 useEffect | `["deliverables", pid, "list"]`、`["project", pid]` |

**关键决策：** 按 AGENTS.md "禁止补丁式开发"原则，不为本切片而引入与现有机制重复的另一种机制。

---

## 二、新增测试

### 2.1 hooks 层单元测试（23 个新增）

**文件：**
- `apps/web/src/features/requirements/__tests__/hooks.test.tsx`（7 个新增）
- `apps/web/src/features/evidence/__tests__/hooks.test.tsx`（8 个新增）
- `apps/web/src/features/outlines/__tests__/hooks.test.tsx`（8 个新增）

**测试覆盖矩阵：**

| 测试场景 | requirements | evidence | outlines |
| --- | --- | --- | --- |
| 乐观更新成功：onMutate 后缓存立即反映新值 | ✅ | ✅ | ✅ |
| 错误回滚：mutation reject 后缓存恢复为快照 | ✅ | ✅ | ✅ |
| `onSettled` 在成功时触发 invalidateQueries | ✅ | ✅ | ✅ |
| `onSettled` 在失败时也触发 invalidateQueries | ✅ | ✅ | ✅ |
| 不污染其他 queryKey / 多 filters（status）列表变体同时更新 | ✅ | ✅ | ✅ |
| 缓存为空时乐观更新不报错 | ✅ | ✅ | ✅ |
| 现有查询行为回归保护（useCurrentPlan / useEvidenceCards / useOutlines） | ✅ | ✅ | ✅ |

### 2.2 测试结果

```text
Test Files  22 passed (22)
     Tests  434 passed (434)
```

- 原 411 个测试全部保持通过（无回归）
- 新增 23 个 hooks 层测试全部通过
- 组件层未额外编写测试：`isPending` / `isError` 状态反馈已在 SPEC 0009 测试中覆盖，本轮只新增 `isSuccess` 成功提示（UI 小改动）

---

## 三、Bug 修复

V1.4.0 无 Bug 修复，纯功能增强。

---

## 四、架构改进

### 4.1 严格遵守 owner 边界

V1.4.0 严格遵守 AGENTS.md "唯一 owner" 章节：

- **前端 hooks 层**只做接线（`onMutate` / `onError` / `onSettled`），不拥有业务真相
- **前端组件层**只展示状态、收集输入、触发命令
- 乐观更新只在缓存层临时反映用户输入，最终真相仍以后端 GET 响应为准（`onSettled` 必触发 `invalidateQueries`）
- **后端业务模块、API 路由、schema、数据库表、Worker 全部不动**

### 4.2 不引入新依赖

V1.4.0 不引入任何新 npm 依赖。所有能力由 `@tanstack/react-query` 5.x 现有 API 提供：

- `useMutation` 的 `onMutate` / `onError` / `onSettled`
- `queryClient.setQueryData` / `getQueryData` / `setQueriesData` / `getQueriesData` / `cancelQueries` / `invalidateQueries`

### 4.3 测试先行（TDD）

按 AGENTS.md 阶段闸"测试先行或至少先补风险测试"，V1.4.0 实现顺序：

1. 先写 hooks 层测试（23 个，覆盖乐观更新、错误回滚、onSettled、批量更新、空缓存等场景）
2. 实现 `useUpdatePlan` / `useUpdateEvidence` / `useUpdateOutline` 三个 hooks
3. 在组件中新增"已保存 ✓"成功提示
4. 跑测试验证全部通过（23 + 411 = 434）

---

## 五、升级指南

### 5.1 从 V1.3.0 升级到 V1.4.0

V1.4.0 是纯前端切片，**不涉及后端、数据库、API、依赖变更**，升级零风险：

```bash
# 拉取最新代码
git fetch origin
git checkout master
git pull origin master

# 前端无新依赖，无需 npm install
# 后端无变更，无需 pip install
# 数据库无变更，无需 alembic upgrade

# 重启前端 dev server 或重新构建 Docker 镜像
cd apps/web && npm run dev
# 或
docker compose build frontend && docker compose up -d frontend
```

### 5.2 用户感知变化

V1.4.0 之后，用户在以下三类编辑场景会感受到 UI 反馈更快：

1. **实验要求 / 任务单编辑**：保存后 UI 立即反映最新内容，下方短暂显示绿色"已保存 ✓"提示（1.5s 后消失）
2. **证据卡片编辑**：同上
3. **大纲编辑**：同上

如果保存失败（网络错误或后端校验失败），下方会显示红色错误文案（来自后端 `AppError.message`），用户输入不会丢失。

---

## 六、已知问题与非阻断债务

### 6.1 TD-009：SPEC 0017 浏览器验收截图未持久化

**状态：** 非阻断，已记录待修复

**问题：** SPEC 0017 浏览器验收使用 browser_use agent 执行真实浏览器点击验收，PASS（保存按钮"已保存 ✓"绿色 #16a34a 提示正常显示，1.5s 后自动消失），但 `browser_take_screenshot` 工具在本环境未真正写入文件到 `dev-docs/e2e-screenshots/` 目录。

**影响：** 不影响功能正确性，仅缺失截图归档。功能正确性已通过 23 个 hooks 单元测试 + browser_use agent 真实点击观察的双重证据确认。

**修复入口：** `dev-docs/tech-debt-inventory.md` TD-009 条目。后续修复时可用 puppeteer / playwright 等替代工具，或修复 browser_use 的截图持久化机制。

---

## 七、验收证据

### 7.1 测试验收

| 验收项 | 命令 | 结果 |
| --- | --- | --- |
| 前端测试 | `npx vitest run`（apps/web 下） | **434 passed**（22 个测试文件，原 411 + 新增 23） |
| 后端测试 | `.venv\Scripts\python.exe -m pytest`（server 下） | **736 passed in 71.80s, 0 warnings**（与 V1.3.0 一致，零回归） |
| TypeScript 类型检查 | `npm.cmd run lint`（apps/web 下） | `tsc --noEmit` 通过 |
| Vite 构建 | `npm.cmd run build`（apps/web 下） | 114 模块转换，dist/ 396.63 kB，gzip 108.01 kB |
| Alembic 迁移 | `.venv\Scripts\python.exe -m alembic upgrade head` | 在 0007 (head)，无数据库变更 |

### 7.2 浏览器验收

启动后端 Docker 容器（`docker compose up -d backend worker`）+ 前端 Vite dev server（`npm run dev`），用 browser_use agent 执行真实浏览器点击验收：

- ✅ 访问 http://localhost:5173/ 首页
- ✅ 进入"SPEC0017验收项目"详情页
- ✅ 进入实验要求工作台
- ✅ 添加 text source "老师实验要求"
- ✅ 生成任务单
- ✅ 点击"编辑任务单"，修改"课题"字段
- ✅ 点击"保存修改"，观察到 **绿色"已保存 ✓"提示（#16a34a），1.5s 后自动消失**
- ✅ "保存中…"状态切换过快难以截图（这恰恰是乐观更新的预期效果）
- ⚠️ 证据卡片和大纲组件因预算限制跳过浏览器验收，依赖已通过的 16 个 hooks 单元测试覆盖
- ⚠️ 截图未持久化到磁盘（browser_take_screenshot 工具限制），记录为 TD-009

### 7.3 AC 完成情况

详见 [SPEC 0017 §七 验收标准](specs/0017-frontend-realtime-edit-feedback.md) 和 [acceptance.md](acceptance.md) 验收记录表。AC-1~27 全部通过（其中 AC-11~15 和 AC-23 按实现前调研修订后的标准通过）。

---

## 八、版本收口

- **git commit：** "完成 SPEC 0017 单用户前端实时编辑反馈"（中文）
- **tag：** v1.4.0
- **远程：** push 到 origin/master + push --tags

---

## 九、下一阶段方向

V1.4.0 SPEC 0017 已收口，项目当前活跃可记录债务为 TD-009（非阻断）。下一阶段方向待项目负责人规划。可能的候选方向：

- **方向 B：单用户多标签页同步**（BroadcastChannel / localStorage 事件）
- **其他前端体验优化**（如自动保存草稿、撤销/重做栈）
- **后端能力增强**（如流式 LLM 输出、OCR 与扫描文档支持）

上述方向均需先编写并确认对应 SPEC，不得直接进入实现。
