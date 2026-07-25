import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useRef, useCallback } from "react";
import {
  fetchSources,
  addTextSource,
  addDocxSource,
  generatePlan,
  streamGeneratePlan,
  fetchCurrentPlan,
  confirmPlan,
  updatePlan,
} from "./api";
import type { RequirementPlanPayload } from "./types";

function projectKey(projectId: string) {
  return ["requirements", projectId];
}

export function useSources(projectId: string) {
  return useQuery({
    queryKey: [...projectKey(projectId), "sources"],
    queryFn: () => fetchSources(projectId),
    staleTime: 5_000,
  });
}

export function useAddTextSource(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ title, text }: { title: string; text: string }) =>
      addTextSource(projectId, title, text),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...projectKey(projectId), "sources"] });
    },
  });
}

export function useAddDocxSource(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ title, file }: { title: string; file: File }) =>
      addDocxSource(projectId, title, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...projectKey(projectId), "sources"] });
    },
  });
}

export function useCurrentPlan(projectId: string) {
  return useQuery({
    queryKey: [...projectKey(projectId), "plan"],
    queryFn: () => fetchCurrentPlan(projectId),
  });
}

export function useGeneratePlan(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) => generatePlan(projectId, sourceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...projectKey(projectId), "plan"] });
    },
  });
}

export function useConfirmPlan(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (planId: string) => confirmPlan(projectId, planId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...projectKey(projectId), "plan"] });
      qc.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}

export function useUpdatePlan(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ planId, payload }: { planId: string; payload: RequirementPlanPayload }) =>
      updatePlan(projectId, planId, payload),
    onMutate: async ({ planId, payload }) => {
      // SPEC 0017 §3.1：取消正在进行的 GET，避免覆盖乐观更新
      const planKey = [...projectKey(projectId), "plan"];
      await qc.cancelQueries({ queryKey: planKey });
      // 保存快照用于回滚
      const snapshot = qc.getQueryData(planKey);
      // 乐观写入：仅更新 payload 字段，保留其他字段不变
      qc.setQueryData(planKey, (old: any) => {
        if (!old) return old;
        return { ...old, payload, id: planId };
      });
      return { snapshot };
    },
    onError: (_err, _vars, context) => {
      // SPEC 0017 §2.4：错误时回滚到 onMutate 前的快照
      if (context?.snapshot) {
        qc.setQueryData(
          [...projectKey(projectId), "plan"],
          context.snapshot
        );
      }
    },
    onSettled: () => {
      // SPEC 0017 §2.4：无论成功失败，最终都 invalidate 触发真相刷新
      qc.invalidateQueries({ queryKey: [...projectKey(projectId), "plan"] });
    },
  });
}

// --- SPEC 0018 流式生成任务单 ---

export interface StreamPlanState {
  /** 是否正在流式生成 */
  streaming: boolean;
  /** 已生成的完整文本（chunk 累积） */
  chunks: string;
  /** 完成事件返回的结果 */
  result: {
    plan_id: string;
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

const INITIAL_STREAM_STATE: StreamPlanState = {
  streaming: false,
  chunks: "",
  result: null,
  error: null,
};

/**
 * 流式生成任务单 hook。
 *
 * SPEC 0018 流式 LLM 输出。
 *
 * 管理 SSE 连接的生命周期：
 * - start(sourceId): 建立连接，逐 chunk 累积文本
 * - cancel(): 中断连接（AbortController.abort()）
 * - reset(): 重置状态
 *
 * 完成后自动 invalidate 任务单 query，触发 GET 刷新最终结果。
 */
export function useStreamGeneratePlan(projectId: string) {
  const qc = useQueryClient();
  const [state, setState] = useState<StreamPlanState>(INITIAL_STREAM_STATE);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(
    async (sourceId: string) => {
      // 重置状态并开始流式
      setState({ ...INITIAL_STREAM_STATE, streaming: true });
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        for await (const evt of streamGeneratePlan(
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
            // 刷新任务单 query，获取后端保存的最终结果
            qc.invalidateQueries({
              queryKey: [...projectKey(projectId), "plan"],
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
    },
    [projectId, qc]
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    setState(INITIAL_STREAM_STATE);
  }, []);

  return { ...state, start, cancel, reset };
}
