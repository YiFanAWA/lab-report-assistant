/** 执行核心侧 TanStack Query hooks。

11 个 hooks：
- 代码任务（7 个）：useCodeTasks/useCodeTask/useGenerateCodeTask/useUpdateCodeTask/useConfirmCodeTask/useRejectCodeTask/useExecuteCodeTask
- 执行记录（4 个）：useExecutionRuns/useExecutionRun/useCompleteExecution + buildArtifactDownloadUrl（纯函数，无 hook）
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  generateCodeTask,
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
