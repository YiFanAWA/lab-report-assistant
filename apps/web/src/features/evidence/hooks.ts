/** 证据卡片 TanStack Query hooks。 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useRef, useCallback } from "react";
import {
  generateEvidence,
  streamGenerateEvidence,
  listEvidence,
  updateEvidence,
  confirmEvidence,
  rejectEvidence,
  completeEvidence,
} from "./api";
import type { UpdateEvidenceCardRequest } from "./types";

function evidenceKey(projectId: string) {
  return ["evidence", projectId];
}

/** 证据卡片列表。 */
export function useEvidenceCards(
  projectId: string,
  filters?: { source_id?: string; status?: string }
) {
  return useQuery({
    queryKey: [...evidenceKey(projectId), "list", filters ?? {}],
    queryFn: () => listEvidence(projectId, filters),
    staleTime: 5_000,
  });
}

/** 生成证据卡片候选。 */
export function useGenerateEvidence(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) => generateEvidence(projectId, sourceId),
    onSuccess: () => {
      // 任务完成后由轮询逻辑触发刷新；这里先 invalidate 列表查询
      qc.invalidateQueries({ queryKey: [...evidenceKey(projectId), "list"] });
    },
  });
}

// --- SPEC 0020 流式生成证据卡片 ---

export interface StreamEvidenceState {
  /** 是否正在流式生成 */
  streaming: boolean;
  /** 已生成的完整文本（chunk 累积） */
  chunks: string;
  /** 完成事件返回的结果 */
  result: {
    card_count: number;
    candidate_source: string;
    fallback_used: boolean;
  } | null;
  /** 错误事件返回的信息 */
  error: {
    error_code: string;
    message: string;
    partial_text: string;
  } | null;
}

const INITIAL_STREAM_EVIDENCE_STATE: StreamEvidenceState = {
  streaming: false,
  chunks: "",
  result: null,
  error: null,
};

/**
 * 流式生成证据卡片 hook。
 *
 * SPEC 0020 证据卡片生成流式化。
 *
 * 管理 SSE 连接的生命周期：
 * - start(): 建立连接，逐 chunk 累积文本
 * - cancel(): 中断连接（AbortController.abort()）
 * - reset(): 重置状态
 *
 * 完成后自动 invalidate 证据卡片列表 query，触发 GET 刷新最终结果。
 */
export function useStreamGenerateEvidence(
  projectId: string,
  sourceId: string
) {
  const qc = useQueryClient();
  const [state, setState] = useState<StreamEvidenceState>(
    INITIAL_STREAM_EVIDENCE_STATE
  );
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(async () => {
    // 重置状态并开始流式
    setState({ ...INITIAL_STREAM_EVIDENCE_STATE, streaming: true });
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const evt of streamGenerateEvidence(
        projectId,
        sourceId,
        controller.signal
      )) {
        if (evt.event === "chunk") {
          const { text } = JSON.parse(evt.data);
          setState((s) => ({ ...s, chunks: s.chunks + text }));
        } else if (evt.event === "done") {
          const data = JSON.parse(evt.data);
          setState({
            streaming: false,
            chunks: "",
            result: data,
            error: null,
          });
          // 刷新证据卡片列表 query，获取后端保存的最终结果
          qc.invalidateQueries({
            queryKey: [...evidenceKey(projectId), "list"],
          });
        } else if (evt.event === "error") {
          const data = JSON.parse(evt.data);
          setState((s) => ({
            ...s,
            error: data,
            streaming: false,
          }));
        }
      }
    } catch (e: unknown) {
      // AbortError 是用户主动取消，不算错误
      const err = e as { name?: string; message?: string };
      if (err?.name === "AbortError") {
        setState((s) => ({ ...s, streaming: false }));
      } else {
        setState((s) => ({
          ...s,
          error: {
            error_code: "STREAM_NETWORK_ERROR",
            message: err?.message ?? "流式连接失败",
            partial_text: s.chunks,
          },
          streaming: false,
        }));
      }
    } finally {
      abortRef.current = null;
    }
  }, [projectId, sourceId, qc]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    setState(INITIAL_STREAM_EVIDENCE_STATE);
  }, []);

  return { ...state, start, cancel, reset };
}

/** 更新证据卡片。 */
export function useUpdateEvidence(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      cardId,
      payload,
    }: {
      cardId: string;
      payload: UpdateEvidenceCardRequest;
    }) => updateEvidence(projectId, cardId, payload),
    onMutate: async ({ cardId, payload }) => {
      // SPEC 0017 §3.2：取消正在进行的 GET，避免覆盖乐观更新
      const listKeyPrefix = [...evidenceKey(projectId), "list"];
      await qc.cancelQueries({ queryKey: listKeyPrefix });
      // 保存所有匹配 list 变体的快照（含 queryKey）用于回滚
      // getQueriesData 返回 [queryKey, data][]
      const snapshots = qc.getQueriesData<any>({ queryKey: listKeyPrefix });
      // 乐观更新所有匹配的列表变体（filters 不同也会被批量更新）
      qc.setQueriesData<any>({ queryKey: listKeyPrefix }, (old: any) => {
        if (!old) return old;
        // 缓存结构统一为 EvidenceCard[]；如未来变更为 { items: [] } 也兼容
        const items = Array.isArray(old) ? old : old.items;
        if (!Array.isArray(items)) return old;
        const next = items.map((card: any) =>
          card.id === cardId ? { ...card, ...payload } : card
        );
        return Array.isArray(old) ? next : { ...old, items: next };
      });
      return { snapshots };
    },
    onError: (_err, _vars, context) => {
      // SPEC 0017 §2.4：错误时回滚到 onMutate 前的快照
      if (context?.snapshots) {
        for (const [queryKey, snapshot] of context.snapshots) {
          qc.setQueryData(queryKey, snapshot);
        }
      }
    },
    onSettled: () => {
      // SPEC 0017 §2.4：无论成功失败，最终都 invalidate 触发真相刷新
      qc.invalidateQueries({ queryKey: [...evidenceKey(projectId), "list"] });
    },
  });
}

/** 确认证据卡片。 */
export function useConfirmEvidence(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (cardId: string) => confirmEvidence(projectId, cardId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...evidenceKey(projectId), "list"] });
    },
  });
}

/** 拒绝证据卡片。 */
export function useRejectEvidence(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (cardId: string) => rejectEvidence(projectId, cardId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...evidenceKey(projectId), "list"] });
    },
  });
}

/** 完成证据确认。 */
export function useCompleteEvidence(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => completeEvidence(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...evidenceKey(projectId), "list"] });
      qc.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}
