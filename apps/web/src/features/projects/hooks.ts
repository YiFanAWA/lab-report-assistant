import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { Project, ProjectCreateRequest } from "../../shared/types";
import { fetchProjects, fetchProject, createProject } from "./api";

export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
    staleTime: 10_000,
  });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: ["project", id],
    queryFn: () => fetchProject(id),
    enabled: !!id,
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: ProjectCreateRequest) => createProject(req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}
