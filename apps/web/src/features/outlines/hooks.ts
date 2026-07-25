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
  uploadWordTemplate,
  getWordTemplate,
  deleteWordTemplate,
} from "./api";
import type { UpdateOutlineRequest, PptConfig } from "./types";

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
    onMutate: async ({ outlineId, payload }) => {
      // SPEC 0017 §3.3：取消正在进行的 GET，避免覆盖乐观更新
      const listKeyPrefix = [...outlinesKey(projectId), "list"];
      await qc.cancelQueries({ queryKey: listKeyPrefix });
      // 保存所有匹配 list 变体的快照（含 queryKey）用于回滚
      const snapshots = qc.getQueriesData<any>({ queryKey: listKeyPrefix });
      // 乐观更新所有匹配的列表变体（status 不同也会被批量更新）
      qc.setQueriesData<any>({ queryKey: listKeyPrefix }, (old: any) => {
        if (!old) return old;
        const items = Array.isArray(old) ? old : old.items;
        if (!Array.isArray(items)) return old;
        const next = items.map((outline: any) =>
          outline.id === outlineId
            ? { ...outline, sections: payload.sections }
            : outline
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

/** 触发 PPT 生成。SPEC 0011：支持可选 config 配置。 */
export function useGeneratePpt(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { outlineId: string; config?: PptConfig }) =>
      generatePpt(projectId, args.outlineId, args.config),
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

// --- SPEC 0010 Word 模板 ---

function wordTemplateKey(projectId: string) {
  return ["word-template", projectId];
}

/** 获取 Word 模板信息。 */
export function useWordTemplate(projectId: string) {
  return useQuery({
    queryKey: [...wordTemplateKey(projectId)],
    queryFn: () => getWordTemplate(projectId),
    staleTime: 5_000,
  });
}

/** 上传或替换 Word 模板。 */
export function useUploadWordTemplate(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadWordTemplate(projectId, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...wordTemplateKey(projectId)] });
    },
  });
}

/** 删除 Word 模板。 */
export function useDeleteWordTemplate(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => deleteWordTemplate(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...wordTemplateKey(projectId)] });
    },
  });
}
