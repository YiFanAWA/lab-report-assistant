/**
 * outlines/hooks.ts TanStack Query hooks 测试（SPEC 0017）。
 *
 * 测试覆盖：
 * - useUpdateOutline 乐观更新：onMutate 后列表缓存中对应 outlineId 立即反映新 sections
 * - useUpdateOutline 错误回滚：mutation reject 后列表缓存恢复为快照
 * - useUpdateOutline onSettled 无条件 invalidate：成功和失败均触发 invalidate
 * - useUpdateOutline 多 status 列表变体同时更新（setQueriesData 批量）
 * - useUpdateOutline 列表为空时不报错
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import * as api from "../api";
import { useOutlines, useUpdateOutline } from "../hooks";
import type { Outline, OutlineSection, UpdateOutlineRequest } from "../types";

// --- 测试辅助 ---

function makeSection(overrides: Partial<OutlineSection> = {}): OutlineSection {
  return {
    id: "sec_001",
    title: "实验背景",
    content: "原始内容",
    source_type: "REQUIREMENT",
    source_ids: ["src_001"],
    ...overrides,
  };
}

function makeOutline(overrides: Partial<Outline> = {}): Outline {
  return {
    id: "out_001",
    project_id: "proj_001",
    sections: [makeSection()],
    status: "CANDIDATE",
    candidate_source: "MODEL",
    version: 1,
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T10:00:00Z",
    confirmed_at: null,
    ...overrides,
  };
}

function makeUpdatePayload(
  overrides: Partial<UpdateOutlineRequest> = {}
): UpdateOutlineRequest {
  return {
    sections: [makeSection({ title: "修订后标题", content: "修订后内容" })],
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
const OUTLINE_ID = "out_001";

beforeEach(() => {
  vi.restoreAllMocks();
});

// ============================================================
// useUpdateOutline - 乐观更新
// ============================================================

describe("useUpdateOutline - SPEC 0017 乐观更新", () => {
  it("onMutate 后列表缓存中对应 outlineId 立即反映新 sections", async () => {
    const { queryClient, Wrapper } = createWrapper();
    const outA = makeOutline({ id: "out_001", sections: [makeSection({ title: "原 A" })] });
    const outB = makeOutline({ id: "out_002", sections: [makeSection({ title: "原 B" })] });
    const listKey = ["outlines", PROJECT_ID, "list", "all"];
    queryClient.setQueryData(listKey, [outA, outB]);

    const newPayload = makeUpdatePayload({
      sections: [makeSection({ title: "修订后 A", content: "新内容 A" })],
    });
    vi.spyOn(api, "updateOutline").mockResolvedValue(
      makeOutline({ sections: newPayload.sections, updated_at: "2026-07-23T11:00:00Z" })
    );

    const { result } = renderHook(() => useUpdateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

    let mutatePromise: Promise<unknown>;
    act(() => {
      mutatePromise = result.current.mutateAsync({
        outlineId: OUTLINE_ID,
        payload: newPayload,
      });
    });

    // onMutate 后立刻查询缓存：out_001 应被替换，out_002 保持不变
    await waitFor(() => {
      const cached = queryClient.getQueryData<Outline[]>(listKey);
      const target = cached?.find((o) => o.id === "out_001");
      const other = cached?.find((o) => o.id === "out_002");
      expect(target?.sections[0].title).toBe("修订后 A");
      expect(target?.sections[0].content).toBe("新内容 A");
      expect(other?.sections[0].title).toBe("原 B");
    });

    await mutatePromise!;
  });

  it("mutation reject 后列表缓存恢复为 onMutate 前的快照", async () => {
    const { queryClient, Wrapper } = createWrapper();
    const outA = makeOutline({ id: "out_001", sections: [makeSection({ title: "原 A" })] });
    const listKey = ["outlines", PROJECT_ID, "list", "all"];
    queryClient.setQueryData(listKey, [outA]);

    const error = { error_code: "OUTLINE_UPDATE_FAILED", message: "网络错误" };
    vi.spyOn(api, "updateOutline").mockRejectedValue(error);

    const { result } = renderHook(() => useUpdateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

    await expect(
      result.current.mutateAsync({
        outlineId: OUTLINE_ID,
        payload: makeUpdatePayload({
          sections: [makeSection({ title: "失败的修订" })],
        }),
      })
    ).rejects.toEqual(error);

    await waitFor(() => {
      const cached = queryClient.getQueryData<Outline[]>(listKey);
      expect(cached?.find((o) => o.id === "out_001")?.sections[0].title).toBe("原 A");
    });
  });

  it("onSettled 在成功时触发 invalidateQueries（outlines list 范围）", async () => {
    const { queryClient, Wrapper } = createWrapper();
    const listKey = ["outlines", PROJECT_ID, "list", "all"];
    queryClient.setQueryData(listKey, [makeOutline()]);

    vi.spyOn(api, "updateOutline").mockResolvedValue(makeOutline());
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useUpdateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

    await result.current.mutateAsync({
      outlineId: OUTLINE_ID,
      payload: makeUpdatePayload(),
    });

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["outlines", PROJECT_ID, "list"],
      })
    );
  });

  it("onSettled 在失败时也触发 invalidateQueries", async () => {
    const { queryClient, Wrapper } = createWrapper();
    const listKey = ["outlines", PROJECT_ID, "list", "all"];
    queryClient.setQueryData(listKey, [makeOutline()]);

    vi.spyOn(api, "updateOutline").mockRejectedValue({ message: "失败" });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useUpdateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

    await expect(
      result.current.mutateAsync({
        outlineId: OUTLINE_ID,
        payload: makeUpdatePayload(),
      })
    ).rejects.toEqual({ message: "失败" });

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["outlines", PROJECT_ID, "list"],
      })
    );
  });

  it("乐观更新同时更新多个 status 列表变体（setQueriesData 批量）", async () => {
    const { queryClient, Wrapper } = createWrapper();
    // 两个不同的 status 变体，都包含 out_001
    const allListKey = ["outlines", PROJECT_ID, "list", "all"];
    const candidateListKey = ["outlines", PROJECT_ID, "list", "CANDIDATE"];
    const out = makeOutline({ id: "out_001", status: "CANDIDATE" });
    queryClient.setQueryData(allListKey, [out]);
    queryClient.setQueryData(candidateListKey, [out]);

    vi.spyOn(api, "updateOutline").mockResolvedValue(
      makeOutline({ sections: [makeSection({ title: "新标题" })] })
    );

    const { result } = renderHook(() => useUpdateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

    let mutatePromise: Promise<unknown>;
    act(() => {
      mutatePromise = result.current.mutateAsync({
        outlineId: OUTLINE_ID,
        payload: makeUpdatePayload({
          sections: [makeSection({ title: "新标题" })],
        }),
      });
    });

    // 两个变体的缓存都应被更新
    await waitFor(() => {
      const allCached = queryClient.getQueryData<Outline[]>(allListKey);
      const candCached = queryClient.getQueryData<Outline[]>(candidateListKey);
      expect(allCached?.find((o) => o.id === "out_001")?.sections[0].title).toBe("新标题");
      expect(candCached?.find((o) => o.id === "out_001")?.sections[0].title).toBe("新标题");
    });

    await mutatePromise!;
  });

  it("列表缓存为空时乐观更新不报错", async () => {
    const { queryClient, Wrapper } = createWrapper();
    // 不预填充缓存

    vi.spyOn(api, "updateOutline").mockResolvedValue(makeOutline());

    const { result } = renderHook(() => useUpdateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

    await result.current.mutateAsync({
      outlineId: OUTLINE_ID,
      payload: makeUpdatePayload(),
    });

    const cached = queryClient.getQueryData<Outline[]>([
      "outlines",
      PROJECT_ID,
      "list",
      "all",
    ]);
    expect(cached).toBeUndefined();
  });
});

// ============================================================
// useOutlines - 现有查询行为（回归保护）
// ============================================================

describe("useOutlines - 现有查询行为（SPEC 0017 回归保护）", () => {
  it("调用 listOutlines 并返回大纲列表", async () => {
    const { Wrapper } = createWrapper();
    const outlines = [makeOutline({ id: "o1" }), makeOutline({ id: "o2" })];
    vi.spyOn(api, "listOutlines").mockResolvedValue(outlines);

    const { result } = renderHook(() => useOutlines(PROJECT_ID), {
      wrapper: Wrapper,
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(outlines);
    });
  });

  it("带 status 过滤时传给 listOutlines", async () => {
    const { Wrapper } = createWrapper();
    const spy = vi.spyOn(api, "listOutlines").mockResolvedValue([makeOutline()]);

    renderHook(() => useOutlines(PROJECT_ID, "CONFIRMED"), {
      wrapper: Wrapper,
    });

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith(PROJECT_ID, "CONFIRMED");
    });
  });
});
