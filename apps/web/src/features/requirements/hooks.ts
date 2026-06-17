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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...projectKey(projectId), "plan"] });
    },
  });
}
