/**
 * requirements/hooks.ts TanStack Query hooks 测试（SPEC 0017）。
 *
 * 测试覆盖：
 * - useUpdatePlan 乐观更新：onMutate 后缓存立即反映新 payload
 * - useUpdatePlan 错误回滚：mutation reject 后缓存恢复为快照
 * - useUpdatePlan onSettled 无条件 invalidate：成功和失败均触发 invalidate
 * - useUpdatePlan 不影响其他 query：乐观更新不污染 evidence/outline 等其他 query
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import * as api from "../api";
import { useCurrentPlan, useUpdatePlan } from "../hooks";
import type { RequirementPlanResponse, RequirementPlanPayload } from "../types";

// --- 测试辅助 ---

function makePayload(overrides: Partial<RequirementPlanPayload> = {}): RequirementPlanPayload {
  return {
    topic: "胃病数据分析",
    experiment_type: "数据分析与可视化",
    research_subject: "胃病数据",
    required_tasks: [],
    recommended_tasks: [],
    optional_tasks: [],
    out_of_scope_tasks: [],
    unknown_items: [],
    data_requirements: ["CSV"],
    method_requirements: ["描述性统计"],
    chart_requirements: ["直方图"],
    report_requirements: ["实验报告"],
    presentation_requirements: ["PPT"],
    acceptance_criteria: ["可追溯"],
    replication_level: {
      level: "L0",
      label: "不复刻",
      supported_in_v1: true,
      reason: "无复刻要求",
      suggested_scope: "独立分析",
    },
    ...overrides,
  };
}

function makePlan(overrides: Partial<RequirementPlanResponse> = {}): RequirementPlanResponse {
  return {
    id: "plan_001",
    project_id: "proj_001",
    source_id: "src_001",
    status: "CANDIDATE",
    payload: makePayload(),
    candidate_source: "LOCAL_RULE",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T10:00:00Z",
    confirmed_at: null,
    ...overrides,
  };
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  }
  return { queryClient, Wrapper };
}

const PROJECT_ID = "proj_001";
const PLAN_ID = "plan_001";

beforeEach(() => {
  vi.restoreAllMocks();
});

// ============================================================
// useUpdatePlan - 乐观更新
// ============================================================

describe("useUpdatePlan - SPEC 0017 乐观更新", () => {
  it("onMutate 后缓存立即反映新 payload", async () => {
    const { queryClient, Wrapper } = createWrapper();
    const originalPlan = makePlan();
    const newPayload = makePayload({ topic: "修订后课题", research_subject: "新对象" });

    // 预填充缓存
    queryClient.setQueryData(["requirements", PROJECT_ID, "plan"], originalPlan);

    // mock api.updatePlan 返回更新后的 plan
    const updateSpy = vi
      .spyOn(api, "updatePlan")
      .mockImplementation(async () => makePlan({ payload: newPayload, updated_at: "2026-07-23T11:00:00Z" }));

    const { result } = renderHook(() => useUpdatePlan(PROJECT_ID), { wrapper: Wrapper });

    // 触发 mutate（不 await，因为我们要在 pending 期间检查缓存）
    let mutatePromise: Promise<unknown>;
    act(() => {
      mutatePromise = result.current.mutateAsync({ planId: PLAN_ID, payload: newPayload });
    });

    // 等待 onMutate 完成（async）
    await waitFor(() => {
      const cached = queryClient.getQueryData<RequirementPlanResponse>([
        "requirements",
        PROJECT_ID,
        "plan",
      ]);
      // 乐观更新应已写入新 payload
      expect(cached?.payload.topic).toBe("修订后课题");
      expect(cached?.payload.research_subject).toBe("新对象");
    });

    // 等待 mutation 完成
    await mutatePromise!;
    expect(updateSpy).toHaveBeenCalledWith(PROJECT_ID, PLAN_ID, newPayload);
  });

  it("mutation reject 后缓存恢复为 onMutate 前的快照", async () => {
    const { queryClient, Wrapper } = createWrapper();
    const originalPlan = makePlan({ payload: makePayload({ topic: "原始课题" }) });
    const newPayload = makePayload({ topic: "失败的修订" });

    queryClient.setQueryData(["requirements", PROJECT_ID, "plan"], originalPlan);

    // mock api.updatePlan 抛错
    const error = { error_code: "PLAN_UPDATE_FAILED", message: "保存失败：网络错误" };
    vi.spyOn(api, "updatePlan").mockRejectedValue(error);

    const { result } = renderHook(() => useUpdatePlan(PROJECT_ID), { wrapper: Wrapper });

    await expect(
      result.current.mutateAsync({ planId: PLAN_ID, payload: newPayload })
    ).rejects.toEqual(error);

    // onError 回滚后，缓存应恢复为原始快照
    await waitFor(() => {
      const cached = queryClient.getQueryData<RequirementPlanResponse>([
        "requirements",
        PROJECT_ID,
        "plan",
      ]);
      expect(cached?.payload.topic).toBe("原始课题");
    });
  });

  it("onSettled 在成功时触发 invalidateQueries", async () => {
    const { queryClient, Wrapper } = createWrapper();
    const originalPlan = makePlan();
    const newPayload = makePayload({ topic: "成功修订" });

    queryClient.setQueryData(["requirements", PROJECT_ID, "plan"], originalPlan);
    vi.spyOn(api, "updatePlan").mockResolvedValue(
      makePlan({ payload: newPayload, updated_at: "2026-07-23T12:00:00Z" })
    );

    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useUpdatePlan(PROJECT_ID), { wrapper: Wrapper });

    await result.current.mutateAsync({ planId: PLAN_ID, payload: newPayload });

    // onSettled 应触发 invalidateQueries，queryKey 为 plan 查询
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["requirements", PROJECT_ID, "plan"],
      })
    );
  });

  it("onSettled 在失败时也触发 invalidateQueries", async () => {
    const { queryClient, Wrapper } = createWrapper();
    const originalPlan = makePlan();
    const newPayload = makePayload({ topic: "失败修订" });

    queryClient.setQueryData(["requirements", PROJECT_ID, "plan"], originalPlan);
    vi.spyOn(api, "updatePlan").mockRejectedValue({ message: "失败" });

    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useUpdatePlan(PROJECT_ID), { wrapper: Wrapper });

    await expect(
      result.current.mutateAsync({ planId: PLAN_ID, payload: newPayload })
    ).rejects.toEqual({ message: "失败" });

    // 即使失败，onSettled 也应触发 invalidateQueries
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["requirements", PROJECT_ID, "plan"],
      })
    );
  });

  it("乐观更新不污染其他 queryKey", async () => {
    const { queryClient, Wrapper } = createWrapper();
    const originalPlan = makePlan();
    const newPayload = makePayload({ topic: "新课题" });

    queryClient.setQueryData(["requirements", PROJECT_ID, "plan"], originalPlan);
    // 另一个 query（如 sources 列表）应不受影响
    queryClient.setQueryData(["requirements", PROJECT_ID, "sources"], [{ id: "src_001" }]);

    vi.spyOn(api, "updatePlan").mockResolvedValue(
      makePlan({ payload: newPayload })
    );

    const { result } = renderHook(() => useUpdatePlan(PROJECT_ID), { wrapper: Wrapper });

    await result.current.mutateAsync({ planId: PLAN_ID, payload: newPayload });

    // sources 查询不应被修改
    const sourcesCache = queryClient.getQueryData(["requirements", PROJECT_ID, "sources"]);
    expect(sourcesCache).toEqual([{ id: "src_001" }]);
  });

  it("缓存为空时乐观更新不报错", async () => {
    const { queryClient, Wrapper } = createWrapper();
    const newPayload = makePayload({ topic: "空缓存测试" });

    // 不预填充缓存
    vi.spyOn(api, "updatePlan").mockResolvedValue(makePlan({ payload: newPayload }));

    const { result } = renderHook(() => useUpdatePlan(PROJECT_ID), { wrapper: Wrapper });

    // 不应抛错
    await result.current.mutateAsync({ planId: PLAN_ID, payload: newPayload });

    // 缓存仍应为空（onMutate 在 old 为 undefined 时不写入）
    const cached = queryClient.getQueryData(["requirements", PROJECT_ID, "plan"]);
    expect(cached).toBeUndefined();
  });
});

// ============================================================
// useCurrentPlan - 现有查询行为（回归保护）
// ============================================================

describe("useCurrentPlan - 现有查询行为（SPEC 0017 回归保护）", () => {
  it("调用 fetchCurrentPlan 并返回 plan", async () => {
    const { Wrapper } = createWrapper();
    const plan = makePlan();
    vi.spyOn(api, "fetchCurrentPlan").mockResolvedValue(plan);

    const { result } = renderHook(() => useCurrentPlan(PROJECT_ID), { wrapper: Wrapper });

    await waitFor(() => {
      expect(result.current.data).toEqual(plan);
    });
  });
});
