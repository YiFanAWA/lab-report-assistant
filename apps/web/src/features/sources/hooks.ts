import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addUrlSource,
  confirmEvidence,
  fetchEvidence,
  fetchParsedDocument,
  fetchSourceRecords,
  generateEvidence,
  parseSource,
  rejectEvidence,
  updateEvidence,
  uploadSourceFile,
} from "./api";
import type { EvidencePatch, EvidenceStatus } from "./types";

const sourceKeys = {
  root: (projectId: string) => ["sources", projectId] as const,
  list: (projectId: string) => ["sources", projectId, "list"] as const,
  parsed: (projectId: string, sourceId: string) => ["sources", projectId, "parsed", sourceId] as const,
  evidence: (projectId: string) => ["sources", projectId, "evidence"] as const,
};

function useWorkspaceInvalidation(projectId: string) {
  const queryClient = useQueryClient();
  return {
    sourceList: () => queryClient.invalidateQueries({ queryKey: sourceKeys.list(projectId) }),
    parsed: (sourceId: string) => queryClient.invalidateQueries({ queryKey: sourceKeys.parsed(projectId, sourceId) }),
    evidence: () => queryClient.invalidateQueries({ queryKey: sourceKeys.evidence(projectId) }),
    project: () => queryClient.invalidateQueries({ queryKey: ["project", projectId] }),
  };
}

export function useSourceRecords(projectId: string) {
  return useQuery({
    queryKey: sourceKeys.list(projectId),
    queryFn: () => fetchSourceRecords(projectId),
    enabled: !!projectId,
  });
}

export function useParsedDocument(projectId: string, sourceId: string, enabled: boolean) {
  return useQuery({
    queryKey: sourceKeys.parsed(projectId, sourceId),
    queryFn: () => fetchParsedDocument(projectId, sourceId),
    enabled: !!projectId && !!sourceId && enabled,
  });
}

export function useEvidenceCards(
  projectId: string,
  filters: { sourceId?: string; status?: EvidenceStatus } = {}
) {
  return useQuery({
    queryKey: [...sourceKeys.evidence(projectId), filters.sourceId ?? "all", filters.status ?? "all"],
    queryFn: () => fetchEvidence(projectId, filters),
    enabled: !!projectId,
  });
}

export function useAddUrlSource(projectId: string) {
  const invalidate = useWorkspaceInvalidation(projectId);
  return useMutation({
    mutationFn: ({ url, title }: { url: string; title: string }) => addUrlSource(projectId, url, title),
    onSuccess: async () => {
      await Promise.all([invalidate.sourceList(), invalidate.project()]);
    },
  });
}

export function useUploadSourceFile(projectId: string) {
  const invalidate = useWorkspaceInvalidation(projectId);
  return useMutation({
    mutationFn: ({ file, title }: { file: File; title: string }) => uploadSourceFile(projectId, file, title),
    onSuccess: async () => {
      await Promise.all([invalidate.sourceList(), invalidate.project()]);
    },
  });
}

export function useParseSource(projectId: string) {
  const invalidate = useWorkspaceInvalidation(projectId);
  return useMutation({
    mutationFn: (sourceId: string) => parseSource(projectId, sourceId),
    onSuccess: async (_, sourceId) => {
      await Promise.all([invalidate.sourceList(), invalidate.parsed(sourceId), invalidate.project()]);
    },
  });
}

export function useGenerateEvidence(projectId: string) {
  const invalidate = useWorkspaceInvalidation(projectId);
  return useMutation({
    mutationFn: (sourceId: string) => generateEvidence(projectId, sourceId),
    onSuccess: async (_, sourceId) => {
      await Promise.all([invalidate.parsed(sourceId), invalidate.evidence(), invalidate.project()]);
    },
  });
}

export function useUpdateEvidence(projectId: string) {
  const invalidate = useWorkspaceInvalidation(projectId);
  return useMutation({
    mutationFn: ({ evidenceId, patch }: { evidenceId: string; patch: EvidencePatch }) =>
      updateEvidence(projectId, evidenceId, patch),
    onSuccess: invalidate.evidence,
  });
}

export function useConfirmEvidence(projectId: string) {
  const invalidate = useWorkspaceInvalidation(projectId);
  return useMutation({
    mutationFn: (evidenceId: string) => confirmEvidence(projectId, evidenceId),
    onSuccess: async () => {
      await Promise.all([invalidate.evidence(), invalidate.project()]);
    },
  });
}

export function useRejectEvidence(projectId: string) {
  const invalidate = useWorkspaceInvalidation(projectId);
  return useMutation({
    mutationFn: (evidenceId: string) => rejectEvidence(projectId, evidenceId),
    onSuccess: invalidate.evidence,
  });
}
