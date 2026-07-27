/** 执行核心侧 TanStack Query hooks。

12 个 hooks：
- 代码任务（8 个）：useCodeTasks/useCodeTask/useGenerateCodeTask/useStreamGenerateCodeTask/useUpdateCodeTask/useConfirmCodeTask/useRejectCodeTask/useExecuteCodeTask
- 执行记录（4 个）：useExecutionRuns/useExecutionRun/useCompleteExecution + buildArtifactDownloadUrl（纯函数，无 hook）
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useRef, useCallback } from "react";
import {
  generateCodeTask,
  streamGenerateCodeTask,
  listCodeTasks,
  getCodeTask,
  updateCodeTask,
  confirmCodeTask,
  rejectCodeTask,
  executeCodeTask,
  listExecutionRuns,
  getExecutionRun,
  completeExecution,
} from "./api";
import type { UpdateCodeTaskRequest } from "./types";

function codeTasksKey(projectId: string) {
  return ["code-tasks", projectId];
}

function executionRunsKey(projectId: string) {
  return ["execution-runs", projectId];
}

// --- 代码任务 ---

/** 代码任务列表（支持 status 过滤）。 */
export function useCodeTasks(projectId: string, status?: string) {
  return useQuery({
    queryKey: [...codeTasksKey(projectId), "list", status ?? "all"],
    queryFn: () => listCodeTasks(projectId, status),
    staleTime: 5_000,
  });
}

/** 代码任务详情。 */
export function useCodeTask(projectId: string, taskId: string) {
  return useQuery({
    queryKey: [...codeTasksKey(projectId), taskId],
    queryFn: () => getCodeTask(projectId, taskId),
    enabled: !!taskId,
  });
}

/** 触发生成代码候选。 */
export function useGenerateCodeTask(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (planId: string) => generateCodeTask(projectId, planId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...codeTasksKey(projectId), "list"] });
    },
  });
}

// --- SPEC 0022 流式生成代码任务 ---

export interface StreamCodeTaskState {
  /** 是否正在流式生成 */
  streaming: boolean;
  /** 已生成的完整文本（chunk 累积，模型原始输出） */
  chunks: string;
  /** 完成事件返回的结果 */
  result: {
    code_task_id: string;
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

const INITIAL_STREAM_CODE_TASK_STATE: StreamCodeTaskState = {
  streaming: false,
  chunks: "",
  result: null,
  error: null,
};

/**
 * 流式生成代码任务 hook。
 *
 * SPEC 0022 代码任务生成流式化。
 *
 * 管理 SSE 连接的生命周期：
 * - start(planId): 建立连接，逐 chunk 累积文本
 * - cancel(): 中断连接（AbortController.abort()）
 * - reset(): 重置状态
 *
 * 完成后自动 invalidate 代码任务列表 query，触发 GET 刷新最终结果。
 */
export function useStreamGenerateCodeTask(projectId: string) {
  const qc = useQueryClient();
  const [state, setState] = useState<StreamCodeTaskState>(
    INITIAL_STREAM_CODE_TASK_STATE
  );
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(
    async (planId: string) => {
      // 重置状态并开始流式
      setState({ ...INITIAL_STREAM_CODE_TASK_STATE, streaming: true });
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        for await (const evt of streamGenerateCodeTask(
          projectId,
          planId,
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
            // 刷新代码任务列表 query，获取后端保存的最终结果
            qc.invalidateQueries({
              queryKey: [...codeTasksKey(projectId), "list"],
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
    setState(INITIAL_STREAM_CODE_TASK_STATE);
  }, []);

  return { ...state, start, cancel, reset };
}

/** 编辑代码任务。 */
export function useUpdateCodeTask(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      taskId,
      payload,
    }: {
      taskId: string;
      payload: UpdateCodeTaskRequest;
    }) => updateCodeTask(projectId, taskId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...codeTasksKey(projectId), "list"] });
    },
  });
}

/** 确认代码任务。 */
export function useConfirmCodeTask(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => confirmCodeTask(projectId, taskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...codeTasksKey(projectId), "list"] });
    },
  });
}

/** 拒绝代码任务。 */
export function useRejectCodeTask(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => rejectCodeTask(projectId, taskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...codeTasksKey(projectId), "list"] });
    },
  });
}

/** 触发代码执行。 */
export function useExecuteCodeTask(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => executeCodeTask(projectId, taskId),
    onSuccess: () => {
      // 执行触发后，执行记录列表会新增条目
      qc.invalidateQueries({ queryKey: [...executionRunsKey(projectId), "list"] });
    },
  });
}

// --- 执行记录 ---

/** 执行记录列表（含 artifacts）。
 *
 * 启用 3s 轮询：执行任务可能持续较长时间（受控 Python 执行），
 * 前端需要实时反映 PENDING → RUNNING → SUCCEEDED/FAILED 的状态变化。
 */
export function useExecutionRuns(projectId: string, status?: string) {
  return useQuery({
    queryKey: [...executionRunsKey(projectId), "list", status ?? "all"],
    queryFn: () => listExecutionRuns(projectId, status),
    refetchInterval: 3_000,
  });
}

/** 执行记录详情（含 stdout/stderr/artifacts）。 */
export function useExecutionRun(projectId: string, runId: string) {
  return useQuery({
    queryKey: [...executionRunsKey(projectId), runId],
    queryFn: () => getExecutionRun(projectId, runId),
    enabled: !!runId,
  });
}

/** 完成结果确认，推进项目状态到 RESULT_CONFIRMED。 */
export function useCompleteExecution(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => completeExecution(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["project", projectId] });
      qc.invalidateQueries({ queryKey: [...executionRunsKey(projectId), "list"] });
    },
  });
}
