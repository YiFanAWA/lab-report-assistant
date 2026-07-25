/**
 * evidence/hooks.ts TanStack Query hooks 测试（SPEC 0017）。
 *
 * 测试覆盖：
 * - useUpdateEvidence 乐观更新：onMutate 后列表缓存中对应 cardId 立即反映新字段
 * - useUpdateEvidence 错误回滚：mutation reject 后列表缓存恢复为快照
 * - useUpdateEvidence onSettled 无条件 invalidate：成功和失败均触发 invalidate
 * - useUpdateEvidence 多 filters 列表变体同时更新（setQueriesData 批量）
 * - useUpdateEvidence 列表为空时不报错
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import * as api from "../api";
import { useEvidenceCards, useUpdateEvidence } from "../hooks";
import type {
  EvidenceCard,
  EvidenceCardListResponse,
  UpdateEvidenceCardRequest,
} from "../types";

// --- 测试辅助 ---

function makeCard(overrides: Partial<EvidenceCard> = {}): EvidenceCard {
  return {
    id: "card_001",
    project_id: "proj_001",
    source_id: "src_001",
    parsed_document_id: "pdoc_001",
    summary: "原始摘要",
    evidence_type: "BACKGROUND",
    locator: "§1.2",
    source_quote: "原始引用",
    status: "CANDIDATE",
    candidate_source: "MODEL",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T10:00:00Z",
    confirmed_at: null,
    ...overrides,
  };
}

function makeUpdatePayload(
  overrides: Partial<UpdateEvidenceCardRequest> = {}
): UpdateEvidenceCardRequest {
  return {
    summary: "修订后摘要",
    evidence_type: "METHOD",
    locator: "§2.3",
    source_quote: "修订后引用",
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
const CARD_ID = "card_001";

beforeEach(() => {
  vi.restoreAllMocks();
});

// ============================================================
// useUpdateEvidence - 乐观更新
// ============================================================

describe("useUpdateEvidence - SPEC 0017 乐观更新", () => {
  it("onMutate 后列表缓存中对应 cardId 立即反映新字段", async () => {
    const { queryClient, Wrapper } = createWrapper();
    const cardA = makeCard({ id: "card_001", summary: "原 A" });
    const cardB = makeCard({ id: "card_002", summary: "原 B" });
    const listKey = ["evidence", PROJECT_ID, "list", {}];
    queryClient.setQueryData(listKey, [cardA, cardB]);

    const newPayload = makeUpdatePayload({ summary: "修订后 A" });
    const updatedCard = { ...cardA, ...newPayload, updated_at: "2026-07-23T11:00:00Z" };
    vi.spyOn(api, "updateEvidence").mockResolvedValue(updatedCard);

    const { result } = renderHook(() => useUpdateEvidence(PROJECT_ID), {
      wrapper: Wrapper,
    });

    let mutatePromise: Promise<unknown>;
    act(() => {
      mutatePromise = result.current.mutateAsync({
        cardId: CARD_ID,
        payload: newPayload,
      });
    });

    // onMutate 后立刻查询缓存：card_001 应被替换，card_002 保持不变
    await waitFor(() => {
      const cached = queryClient.getQueryData<EvidenceCard[]>(listKey);
      const target = cached?.find((c) => c.id === "card_001");
      const other = cached?.find((c) => c.id === "card_002");
      expect(target?.summary).toBe("修订后 A");
      expect(target?.evidence_type).toBe("METHOD");
      expect(other?.summary).toBe("原 B");
    });

    await mutatePromise!;
  });

  it("mutation reject 后列表缓存恢复为 onMutate 前的快照", async () => {
    const { queryClient, Wrapper } = createWrapper();
    const cardA = makeCard({ id: "card_001", summary: "原 A" });
    const listKey = ["evidence", PROJECT_ID, "list", {}];
    queryClient.setQueryData(listKey, [cardA]);

    const error = { error_code: "EVIDENCE_UPDATE_FAILED", message: "网络错误" };
    vi.spyOn(api, "updateEvidence").mockRejectedValue(error);

    const { result } = renderHook(() => useUpdateEvidence(PROJECT_ID), {
      wrapper: Wrapper,
    });

    await expect(
      result.current.mutateAsync({
        cardId: CARD_ID,
        payload: makeUpdatePayload({ summary: "失败的修订" }),
      })
    ).rejects.toEqual(error);

    await waitFor(() => {
      const cached = queryClient.getQueryData<EvidenceCard[]>(listKey);
      expect(cached?.find((c) => c.id === "card_001")?.summary).toBe("原 A");
    });
  });

  it("onSettled 在成功时触发 invalidateQueries（evidence list 范围）", async () => {
    const { queryClient, Wrapper } = createWrapper();
    const listKey = ["evidence", PROJECT_ID, "list", {}];
    queryClient.setQueryData(listKey, [makeCard()]);

    vi.spyOn(api, "updateEvidence").mockResolvedValue(makeCard({ summary: "新" }));
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useUpdateEvidence(PROJECT_ID), {
      wrapper: Wrapper,
    });

    await result.current.mutateAsync({
      cardId: CARD_ID,
      payload: makeUpdatePayload(),
    });

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["evidence", PROJECT_ID, "list"],
      })
    );
  });

  it("onSettled 在失败时也触发 invalidateQueries", async () => {
    const { queryClient, Wrapper } = createWrapper();
    const listKey = ["evidence", PROJECT_ID, "list", {}];
    queryClient.setQueryData(listKey, [makeCard()]);

    vi.spyOn(api, "updateEvidence").mockRejectedValue({ message: "失败" });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useUpdateEvidence(PROJECT_ID), {
      wrapper: Wrapper,
    });

    await expect(
      result.current.mutateAsync({
        cardId: CARD_ID,
        payload: makeUpdatePayload(),
      })
    ).rejects.toEqual({ message: "失败" });

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["evidence", PROJECT_ID, "list"],
      })
    );
  });

  it("乐观更新同时更新多个 filters 列表变体（setQueriesData 批量）", async () => {
    const { queryClient, Wrapper } = createWrapper();
    // 两个不同的 filters 变体，都包含 card_001
    const allListKey = ["evidence", PROJECT_ID, "list", {}];
    const filteredListKey = ["evidence", PROJECT_ID, "list", { status: "CANDIDATE" }];
    const card = makeCard({ id: "card_001", summary: "原" });
    queryClient.setQueryData(allListKey, [card]);
    queryClient.setQueryData(filteredListKey, [card]);

    vi.spyOn(api, "updateEvidence").mockResolvedValue(
      makeCard({ summary: "新" })
    );

    const { result } = renderHook(() => useUpdateEvidence(PROJECT_ID), {
      wrapper: Wrapper,
    });

    let mutatePromise: Promise<unknown>;
    act(() => {
      mutatePromise = result.current.mutateAsync({
        cardId: CARD_ID,
        payload: makeUpdatePayload({ summary: "新" }),
      });
    });

    // 两个变体的缓存都应被更新
    await waitFor(() => {
      const allCached = queryClient.getQueryData<EvidenceCard[]>(allListKey);
      const filteredCached = queryClient.getQueryData<EvidenceCard[]>(filteredListKey);
      expect(allCached?.find((c) => c.id === "card_001")?.summary).toBe("新");
      expect(filteredCached?.find((c) => c.id === "card_001")?.summary).toBe("新");
    });

    await mutatePromise!;
  });

  it("列表缓存为空时乐观更新不报错", async () => {
    const { queryClient, Wrapper } = createWrapper();
    // 不预填充缓存

    vi.spyOn(api, "updateEvidence").mockResolvedValue(makeCard({ summary: "新" }));

    const { result } = renderHook(() => useUpdateEvidence(PROJECT_ID), {
      wrapper: Wrapper,
    });

    await result.current.mutateAsync({
      cardId: CARD_ID,
      payload: makeUpdatePayload(),
    });

    // 没有缓存时不抛错，最终通过 onSettled invalidate 触发 GET
    const cached = queryClient.getQueryData<EvidenceCard[]>([
      "evidence",
      PROJECT_ID,
      "list",
      {},
    ]);
    expect(cached).toBeUndefined();
  });
});

// ============================================================
// useEvidenceCards - 现有查询行为（回归保护）
// ============================================================

describe("useEvidenceCards - 现有查询行为（SPEC 0017 回归保护）", () => {
  it("调用 listEvidence 并返回卡片列表", async () => {
    const { Wrapper } = createWrapper();
    const cards = [makeCard({ id: "c1" }), makeCard({ id: "c2" })];
    vi.spyOn(api, "listEvidence").mockResolvedValue(cards);

    const { result } = renderHook(() => useEvidenceCards(PROJECT_ID), {
      wrapper: Wrapper,
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(cards);
    });
  });

  it("带 filters 时传给 listEvidence", async () => {
    const { Wrapper } = createWrapper();
    const filters = { status: "CANDIDATE", source_id: "src_001" };
    const spy = vi
      .spyOn(api, "listEvidence")
      .mockResolvedValue([makeCard()]);

    renderHook(() => useEvidenceCards(PROJECT_ID, filters), {
      wrapper: Wrapper,
    });

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith(PROJECT_ID, filters);
    });
  });
});
