/** 分析方案 TanStack Query hooks。 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  generateAnalysisPlan,
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
