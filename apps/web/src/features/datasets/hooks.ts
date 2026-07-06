/** 数据集 TanStack Query hooks。 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  uploadDataset,
  createUrlDataset,
  listDatasets,
  getDataset,
  listDatasetVersions,
  deleteDataset,
  reuploadDataset,
  completeDatasets,
} from "./api";

function datasetsKey(projectId: string) {
  return ["datasets", projectId];
}

/** 数据集列表。 */
export function useDatasets(projectId: string) {
  return useQuery({
    queryKey: [...datasetsKey(projectId), "list"],
    queryFn: () => listDatasets(projectId),
    staleTime: 5_000,
  });
}

/** 数据集详情。 */
export function useDataset(projectId: string, datasetId: string) {
  return useQuery({
    queryKey: [...datasetsKey(projectId), datasetId],
    queryFn: () => getDataset(projectId, datasetId),
    enabled: !!datasetId,
  });
}

/** 数据集版本列表。 */
export function useDatasetVersions(projectId: string, datasetId: string) {
  return useQuery({
    queryKey: [...datasetsKey(projectId), datasetId, "versions"],
    queryFn: () => listDatasetVersions(projectId, datasetId),
    enabled: !!datasetId,
  });
}

/** 上传 CSV/Excel 数据集。 */
export function useUploadDataset(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      title,
      description,
    }: {
      file: File;
      title: string;
      description?: string;
    }) => uploadDataset(projectId, file, title, description),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...datasetsKey(projectId), "list"] });
    },
  });
}

/** 登记 URL 数据集。 */
export function useCreateUrlDataset(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      url,
      title,
      description,
    }: {
      url: string;
      title: string;
      description?: string;
    }) => createUrlDataset(projectId, url, title, description),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...datasetsKey(projectId), "list"] });
    },
  });
}

/** 删除数据集。 */
export function useDeleteDataset(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (datasetId: string) => deleteDataset(projectId, datasetId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...datasetsKey(projectId), "list"] });
      qc.invalidateQueries({ queryKey: ["analysis", projectId] });
    },
  });
}

/** 重新上传数据集（创建新版本）。 */
export function useReuploadDataset(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ datasetId, file }: { datasetId: string; file: File }) =>
      reuploadDataset(projectId, datasetId, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...datasetsKey(projectId), "list"] });
      qc.invalidateQueries({ queryKey: ["analysis", projectId] });
    },
  });
}

/** 完成数据集收集。 */
export function useCompleteDatasets(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => completeDatasets(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...datasetsKey(projectId), "list"] });
      qc.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}
