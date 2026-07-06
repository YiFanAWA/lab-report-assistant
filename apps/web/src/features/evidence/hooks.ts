/** 证据卡片 TanStack Query hooks。 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  generateEvidence,
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
    onSuccess: () => {
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
