/** 资料来源 TanStack Query hooks。 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createUrlSource,
  createPdfSource,
  listSources,
  getSource,
  deleteSource,
  completeSources,
} from "./api";

function sourcesKey(projectId: string) {
  return ["sources", projectId];
}

/** 来源列表。 */
export function useSources(projectId: string) {
  return useQuery({
    queryKey: [...sourcesKey(projectId), "list"],
    queryFn: () => listSources(projectId),
    staleTime: 5_000,
  });
}

/** 来源详情。 */
export function useSource(projectId: string, sourceId: string) {
  return useQuery({
    queryKey: [...sourcesKey(projectId), sourceId],
    queryFn: () => getSource(projectId, sourceId),
    enabled: !!sourceId,
  });
}

/** 登记 URL 来源。 */
export function useCreateUrlSource(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ url, title }: { url: string; title: string }) =>
      createUrlSource(projectId, url, title),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...sourcesKey(projectId), "list"] });
    },
  });
}

/** 上传 PDF 来源。 */
export function useCreatePdfSource(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, title }: { file: File; title: string }) =>
      createPdfSource(projectId, file, title),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...sourcesKey(projectId), "list"] });
    },
  });
}

/** 删除来源。 */
export function useDeleteSource(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) => deleteSource(projectId, sourceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...sourcesKey(projectId), "list"] });
      qc.invalidateQueries({ queryKey: ["evidence", projectId] });
    },
  });
}

/** 完成来源收集。 */
export function useCompleteSources(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => completeSources(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...sourcesKey(projectId), "list"] });
      qc.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}
