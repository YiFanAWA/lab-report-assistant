# SPEC 0009：前端测试覆盖补全

> **状态：** 规划阶段，待项目负责人确认  
> **日期：** 2026-07-23  
> **前置：** SPEC 0007 已完成（commit `36e39f9`）  
> **目标版本：** v1.1.0

---

## 一、当前测试现状

### 1.1 已有测试覆盖

| 模块 | API 测试 | 组件测试 | 测试数 | 状态 |
| --- | --- | --- | --- | --- |
| execution | ✅ api.test.ts | ✅ ExecutionWorkspaceView.test.tsx | 37 | 已完成 |
| **其余 8 个模块** | ❌ 无 | ❌ 无 | 0 | 待补全 |

**当前总计：** 2 个测试文件，37 个测试，覆盖率约 11%（1/9 模块）

### 1.2 前端测试运行结果

```
Test Files  2 passed (2)
     Tests  37 passed (37)
  Duration  34.55s
```

现状：前端测试套件运行正常，但覆盖率严重不足。

---

## 二、待补全模块清单

### 2.1 API 层测试（api.test.ts）

每个模块的 `features/xxx/api.ts` 需要对应的 `features/xxx/__tests__/api.test.ts`。

| # | 模块 | API 函数数 | 预计测试数 | 优先级 | 依赖 |
| --- | --- | --- | --- | --- | --- |
| 1 | projects | 3 | ~8 | 🔴 高 | 无（基础模块） |
| 2 | requirements | 7 | ~18 | 🔴 高 | projects |
| 3 | sources | 6 | ~15 | 🟡 中 | projects |
| 4 | evidence | 6 | ~15 | 🟡 中 | projects |
| 5 | datasets | 8 | ~20 | 🟡 中 | projects |
| 6 | analysis | 7 | ~18 | 🟡 中 | datasets |
| 7 | outlines | 2 | ~5 | 🟢 低 | analysis |
| 8 | jobs | 1 | ~3 | 🟢 低 | 无 |

**API 层预计新增：** 8 个测试文件，约 102 个测试

### 2.2 组件层测试（*.test.tsx）

每个 `routes/xxx.tsx` 视图需要对应的 `routes/__tests__/xxx.test.tsx`。

| # | 视图组件 | 预计测试数 | 优先级 | 说明 |
| --- | --- | --- | --- | --- |
| 1 | ProjectListView | ~5 | 🔴 高 | 项目列表，基础页面 |
| 2 | ProjectDetailView | ~8 | 🔴 高 | 项目详情，状态机展示 |
| 3 | RequirementWorkspaceView | ~12 | 🔴 高 | 实验要求输入 |
| 4 | SourcesWorkspaceView | ~10 | 🟡 中 | 公开资料采集 |
| 5 | EvidenceWorkspaceView | ~10 | 🟡 中 | 证据卡片 |
| 6 | DatasetWorkspaceView | ~12 | 🟡 中 | 数据集上传 |
| 7 | AnalysisWorkspaceView | ~10 | 🟡 中 | 分析方案 |
| 8 | OutlineWorkspaceView | ~12 | 🟡 中 | 大纲生成 |
| 9 | DeliverableWorkspaceView | ~8 | 🟢 低 | 交付物下载 |

**组件层预计新增：** 9 个测试文件，约 87 个测试

### 2.3 总计

| 层 | 测试文件数 | 预计测试数 |
| --- | --- | --- |
| API 层 | 8 | ~102 |
| 组件层 | 9 | ~87 |
| **合计新增** | **17** | **~189** |
| 现有 | 2 | 37 |
| **目标总计** | **19** | **~226** |

---

## 三、优先级分组与实施顺序

### 第一批：核心链路（优先级 🔴 高）

**目标：** 覆盖项目创建 → 实验要求输入 → 状态推进的核心链路。

| 顺序 | 文件 | 预计测试数 | 说明 |
| --- | --- | --- | --- |
| 1 | `features/projects/__tests__/api.test.ts` | ~8 | 基础模块，其他测试依赖 |
| 2 | `features/requirements/__tests__/api.test.ts` | ~18 | 实验要求核心 |
| 3 | `routes/__tests__/ProjectListView.test.tsx` | ~5 | 项目列表页 |
| 4 | `routes/__tests__/ProjectDetailView.test.tsx` | ~8 | 项目详情 + 状态机 |
| 5 | `routes/__tests__/RequirementWorkspaceView.test.tsx` | ~12 | 实验要求工作区 |

**第一批预计：** 5 个文件，约 51 个测试

### 第二批：数据与分析链路（优先级 🟡 中）

**目标：** 覆盖公开资料 → 证据 → 数据集 → 分析方案链路。

| 顺序 | 文件 | 预计测试数 | 说明 |
| --- | --- | --- | --- |
| 6 | `features/sources/__tests__/api.test.ts` | ~15 | URL 采集 |
| 7 | `features/evidence/__tests__/api.test.ts` | ~15 | 证据卡片 |
| 8 | `features/datasets/__tests__/api.test.ts` | ~20 | 数据集上传 |
| 9 | `features/analysis/__tests__/api.test.ts` | ~18 | 分析方案 |
| 10 | `routes/__tests__/SourcesWorkspaceView.test.tsx` | ~10 | 来源工作区 |
| 11 | `routes/__tests__/EvidenceWorkspaceView.test.tsx` | ~10 | 证据工作区 |
| 12 | `routes/__tests__/DatasetWorkspaceView.test.tsx` | ~12 | 数据集工作区 |
| 13 | `routes/__tests__/AnalysisWorkspaceView.test.tsx` | ~10 | 分析方案工作区 |

**第二批预计：** 8 个文件，约 110 个测试

### 第三批：交付物链路（优先级 🟢 低）

**目标：** 覆盖大纲、交付物、作业模块。

| 顺序 | 文件 | 预计测试数 | 说明 |
| --- | --- | --- | --- |
| 14 | `features/outlines/__tests__/api.test.ts` | ~5 | 大纲 API |
| 15 | `features/jobs/__tests__/api.test.ts` | ~3 | 作业 API |
| 16 | `routes/__tests__/OutlineWorkspaceView.test.tsx` | ~12 | 大纲工作区 |
| 17 | `routes/__tests__/DeliverableWorkspaceView.test.tsx` | ~8 | 交付物工作区 |

**第三批预计：** 4 个文件，约 28 个测试

---

## 四、测试模式参考

### 4.1 API 层测试模式

参照现有 [execution/api.test.ts](file:///d:/java_project/lab-report-assistant/apps/web/src/features/execution/__tests__/api.test.ts) 模式：

```typescript
// 每个 API 函数测试覆盖：
// 1. 成功调用（URL + method + body 校验）
// 2. 响应解析（JSON 字段映射）
// 3. 错误场景（HTTP 错误、网络错误、空响应）
// 4. 特殊参数（query params、path params）

import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchProjects } from "../api";

global.fetch = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
});

describe("fetchProjects", () => {
  it("成功获取项目列表", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ([{ id: "p1", name: "test" }]),
    });
    const result = await fetchProjects();
    expect(global.fetch).toHaveBeenCalledWith("/api/projects", expect.any(Object));
    expect(result).toHaveLength(1);
  });

  it("HTTP错误时抛出", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
    });
    await expect(fetchProjects()).rejects.toThrow();
  });
});
```

### 4.2 组件层测试模式

参照现有 [ExecutionWorkspaceView.test.tsx](file:///d:/java_project/lab-report-assistant/apps/web/src/routes/__tests__/ExecutionWorkspaceView.test.tsx) 模式：

```typescript
// 组件测试覆盖：
// 1. 加载状态渲染
// 2. 错误状态渲染（项目不存在）
// 3. 正常数据渲染
// 4. 用户交互（按钮点击、表单提交）
// 5. 状态机门控（按项目状态控制 UI 可见性）

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../../features/projects/api", () => ({
  fetchProject: vi.fn(),
}));

// ... 测试用例
```

### 4.3 注意事项

- 使用 `vi.mock` 时，路径必须与组件实际 import 路径一致
- 使用 `monkeypatch` 风格的 `vi.stubGlobal` 全局 mock，测试后自动清理
- 组件测试中使用 `getAllByText` 而非 `getByText` 避免多元素匹配错误
- `afterEach(() => { cleanup(); })` 自动清理 DOM

---

## 五、验收标准

### 5.1 测试数量目标

| 指标 | 当前 | 目标 | 增量 |
| --- | --- | --- | --- |
| 测试文件数 | 2 | 19 | +17 |
| 测试用例数 | 37 | ~226 | +189 |
| 模块覆盖率 | 1/9（11%） | 9/9（100%） | +8 模块 |

### 5.2 验收命令

```text
npm.cmd run test        # 全部测试通过
npm.cmd run lint        # tsc --noEmit 通过
npm.cmd run build       # Vite 构建通过
```

### 5.3 质量要求

- 每个 API 函数至少有 1 个成功测试 + 1 个错误测试
- 每个组件至少有加载/错误/正常 3 个渲染测试
- 状态机相关组件必须有状态门控测试
- 0 warnings
- 测试运行时间不超过 120 秒

---

## 六、实施顺序

按 AGENTS.md 阶段闸，建议以下顺序：

```
第一批（核心链路，~51 测试）
  → projects API → requirements API
  → ProjectListView → ProjectDetailView → RequirementWorkspaceView

第二批（数据与分析链路，~110 测试）
  → sources/evidence/datasets/analysis API
  → 对应 4 个工作区视图

第三批（交付物链路，~28 测试）
  → outlines/jobs API
  → OutlineWorkspaceView → DeliverableWorkspaceView
```

**每批完成后运行 `npm run test` 验收，确保无回归后再进入下一批。**

**预计总工作量：** 2-3 天（按规划文档估算）
