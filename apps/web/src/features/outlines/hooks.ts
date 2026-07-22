/** 大纲与交付物 TanStack Query hooks。 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  generateOutline,
  listOutlines,
  getOutline,
  updateOutline,
  confirmOutline,
  rejectOutline,
  generateWord,
  generatePpt,
  listDeliverables,
  listDeliverableVersions,
  completeProject,
} from "./api";
import type { UpdateOutlineRequest } from "./types";

function outlinesKey(projectId: string) {
  return ["outlines", projectId];
}

function deliverablesKey(projectId: string) {
  return ["deliverables", projectId];
}

// --- 大纲 ---

/** 大纲列表（支持 status 过滤）。 */
export function useOutlines(projectId: string, status?: string) {
  return useQuery({
    queryKey: [...outlinesKey(projectId), "list", status ?? "all"],
    queryFn: () => listOutlines(projectId, status),
    staleTime: 5_000,
  });
}

/** 大纲详情。 */
export function useOutline(projectId: string, outlineId: string) {
  return useQuery({
    queryKey: [...outlinesKey(projectId), outlineId],
    queryFn: () => getOutline(projectId, outlineId),
    enabled: !!outlineId,
  });
}

/** 触发生成大纲候选。 */
export function useGenerateOutline(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => generateOutline(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...outlinesKey(projectId), "list"] });
    },
  });
}

/** 编辑大纲。 */
export function useUpdateOutline(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      outlineId,
      payload,
    }: {
      outlineId: string;
      payload: UpdateOutlineRequest;
    }) => updateOutline(projectId, outlineId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...outlinesKey(projectId), "list"] });
    },
  });
}

/** 确认大纲。 */
export function useConfirmOutline(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (outlineId: string) => confirmOutline(projectId, outlineId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...outlinesKey(projectId), "list"] });
      qc.invalidateQueries({ queryKey: ["project", projectId] });
      qc.invalidateQueries({ queryKey: [...deliverablesKey(projectId), "list"] });
    },
  });
}

/** 拒绝大纲。 */
export function useRejectOutline(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (outlineId: string) => rejectOutline(projectId, outlineId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...outlinesKey(projectId), "list"] });
    },
  });
}

/** 触发 Word 生成。 */
export function useGenerateWord(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (outlineId: string) => generateWord(projectId, outlineId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...deliverablesKey(projectId), "list"] });
      qc.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}

/** 触发 PPT 生成。 */
export function useGeneratePpt(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (outlineId: string) => generatePpt(projectId, outlineId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...deliverablesKey(projectId), "list"] });
      qc.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}

// --- 交付物 ---

/** 交付物列表。 */
export function useDeliverables(projectId: string, status?: string) {
  return useQuery({
    queryKey: [...deliverablesKey(projectId), "list", status ?? "all"],
    queryFn: () => listDeliverables(projectId, status),
    // 交付物状态会随 Worker 推进变化，启用轮询
    refetchInterval: 3_000,
  });
}

/** 交付物版本列表。 */
export function useDeliverableVersions(
  projectId: string,
  deliverableId: string
) {
  return useQuery({
    queryKey: [...deliverablesKey(projectId), deliverableId, "versions"],
    queryFn: () => listDeliverableVersions(projectId, deliverableId),
    enabled: !!deliverableId,
    // 版本状态会随 Worker 推进变化，启用轮询
    refetchInterval: 3_000,
  });
}

/** 完成项目。 */
export function useCompleteProject(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => completeProject(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["project", projectId] });
      qc.invalidateQueries({ queryKey: [...deliverablesKey(projectId), "list"] });
    },
  });
}
