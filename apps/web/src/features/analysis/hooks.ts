/** 分析方案 TanStack Query hooks。 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useRef, useCallback } from "react";
import {
  generateAnalysisPlan,
  streamGenerateAnalysisPlan,
  listAnalysisPlans,
  getAnalysisPlan,
  updateAnalysisPlan,
  confirmAnalysisPlan,
  rejectAnalysisPlan,
  completeAnalysis,
} from "./api";
import type { UpdateAnalysisPlanRequest } from "./types";

function analysisKey(projectId: string) {
  return ["analysis", projectId];
}

/** 分析方案列表。 */
export function useAnalysisPlans(
  projectId: string,
  filters?: { dataset_id?: string; status?: string }
) {
  return useQuery({
    queryKey: [...analysisKey(projectId), "list", filters ?? {}],
    queryFn: () => listAnalysisPlans(projectId, filters),
    staleTime: 5_000,
  });
}

/** 分析方案详情。 */
export function useAnalysisPlan(projectId: string, planId: string) {
  return useQuery({
    queryKey: [...analysisKey(projectId), planId],
    queryFn: () => getAnalysisPlan(projectId, planId),
    enabled: !!planId,
  });
}

/** 触发生成分析方案候选。 */
export function useGenerateAnalysisPlan(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (datasetId: string) => generateAnalysisPlan(projectId, datasetId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...analysisKey(projectId), "list"] });
    },
  });
}

// --- SPEC 0021 流式生成分析方案 ---

export interface StreamAnalysisState {
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

const INITIAL_STREAM_ANALYSIS_STATE: StreamAnalysisState = {
  streaming: false,
  chunks: "",
  result: null,
  error: null,
};

/**
 * 流式生成分析方案 hook。
 *
 * SPEC 0021 分析方案生成流式化。
 *
 * 管理 SSE 连接的生命周期：
 * - start(): 建立连接，逐 chunk 累积文本
 * - cancel(): 中断连接（AbortController.abort()）
 * - reset(): 重置状态
 *
 * 完成后自动 invalidate 分析方案列表 query，触发 GET 刷新最终结果。
 */
export function useStreamGenerateAnalysisPlan(
  projectId: string,
  datasetId: string
) {
  const qc = useQueryClient();
  const [state, setState] = useState<StreamAnalysisState>(
    INITIAL_STREAM_ANALYSIS_STATE
  );
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(async () => {
    // 重置状态并开始流式
    setState({ ...INITIAL_STREAM_ANALYSIS_STATE, streaming: true });
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const evt of streamGenerateAnalysisPlan(
        projectId,
        datasetId,
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
          // 刷新分析方案列表 query，获取后端保存的最终结果
          qc.invalidateQueries({
            queryKey: [...analysisKey(projectId), "list"],
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
  }, [projectId, datasetId, qc]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    setState(INITIAL_STREAM_ANALYSIS_STATE);
  }, []);

  return { ...state, start, cancel, reset };
}

/** 编辑分析方案。 */
export function useUpdateAnalysisPlan(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      planId,
      payload,
    }: {
      planId: string;
      payload: UpdateAnalysisPlanRequest;
    }) => updateAnalysisPlan(projectId, planId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...analysisKey(projectId), "list"] });
    },
  });
}

/** 确认分析方案。 */
export function useConfirmAnalysisPlan(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (planId: string) => confirmAnalysisPlan(projectId, planId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...analysisKey(projectId), "list"] });
    },
  });
}

/** 拒绝分析方案。 */
export function useRejectAnalysisPlan(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (planId: string) => rejectAnalysisPlan(projectId, planId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...analysisKey(projectId), "list"] });
    },
  });
}

/** 完成分析方案确认。 */
export function useCompleteAnalysis(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => completeAnalysis(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...analysisKey(projectId), "list"] });
      qc.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}
