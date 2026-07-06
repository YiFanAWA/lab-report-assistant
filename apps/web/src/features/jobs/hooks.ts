/** 后台任务 TanStack Query hooks。

关键：useJob 带 refetchInterval，仅当任务状态为 PENDING 或 RUNNING 时每 2 秒轮询，
其它状态（SUCCEEDED/FAILED/CANCELLED）停止轮询。
*/

import { useQuery } from "@tanstack/react-query";
import { fetchJob, listJobs } from "./api";

/** 任务轮询 hook。当 jobId 为 null 时不启用。 */
export function useJob(projectId: string, jobId: string | null) {
  return useQuery({
    queryKey: ["jobs", projectId, jobId],
    queryFn: () => fetchJob(projectId, jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "PENDING" || status === "RUNNING") return 2000;
      return false;
    },
  });
}

/** 任务列表 hook。 */
export function useJobs(
  projectId: string,
  filters?: { status?: string; job_type?: string }
) {
  return useQuery({
    queryKey: ["jobs", projectId, "list", filters ?? {}],
    queryFn: () => listJobs(projectId, filters),
    staleTime: 5_000,
  });
}
