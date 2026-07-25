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
