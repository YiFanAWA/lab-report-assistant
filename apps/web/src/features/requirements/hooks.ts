import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchSources,
  addTextSource,
  addDocxSource,
  generatePlan,
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
