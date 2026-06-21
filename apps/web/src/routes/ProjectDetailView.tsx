import { useParams, Link } from "react-router";
import { useProject } from "../features/projects/hooks";

const sourceWorkspaceStatuses = new Set([
  "REQUIREMENT_CONFIRMED",
  "SOURCES_COLLECTED",
  "EVIDENCE_CONFIRMED",
  "DATASET_READY",
  "ANALYSIS_PLANNED",
  "ANALYSIS_CONFIRMED",
  "EXECUTING",
  "EXECUTION_FAILED",
  "RESULT_CONFIRMED",
  "OUTLINE_CONFIRMED",
  "GENERATING",
  "COMPLETED",
]);

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    DRAFT: "草稿",
    REQUIREMENT_PARSED: "要求已解析",
    REQUIREMENT_CONFIRMED: "需求已确认",
    SOURCES_COLLECTED: "资料已收集",
    EVIDENCE_CONFIRMED: "证据已确认",
    COMPLETED: "已完成",
  };
  return labels[status] ?? status;
}

export function ProjectDetailView() {
  const { projectId } = useParams<{ projectId: string }>();
  const { data: project, isLoading, isError, error } = useProject(projectId ?? "");

  if (isLoading) return <p style={{ padding: "2rem" }}>加载中…</p>;

  if (isError) {
    return (
      <div style={{ padding: "2rem", maxWidth: 480, margin: "0 auto" }}>
        <p style={{ color: "#c00" }}>
          {(error as { message?: string })?.message ?? "无法加载项目"}
        </p>
        <Link to="/">返回项目列表</Link>
      </div>
    );
  }

  if (!project) return null;

  return (
    <div style={{ maxWidth: 480, margin: "0 auto", padding: "2rem 1rem" }}>
      <Link to="/" style={{ fontSize: "0.85rem", color: "#2563eb" }}>
        ← 返回项目列表
      </Link>
      <h1 style={{ fontSize: "1.5rem", marginTop: "1rem" }}>{project.name}</h1>
      <div style={{ marginTop: "1rem", lineHeight: 1.8 }}>
        <div><strong>课题：</strong>{project.topic}</div>
        <div><strong>状态：</strong>{statusLabel(project.status)}</div>
        <div><strong>创建时间：</strong>{new Date(project.created_at).toLocaleString("zh-CN")}</div>
        <div><strong>更新时间：</strong>{new Date(project.updated_at).toLocaleString("zh-CN")}</div>
      </div>
      <Link
        to={`/projects/${project.id}/requirements`}
        style={{
          display: "inline-block",
          marginTop: "1rem",
          padding: "0.5rem 0.9rem",
          background: "#2563eb",
          color: "#fff",
          borderRadius: "0.375rem",
          textDecoration: "none",
        }}
      >
        进入实验要求工作区
      </Link>
      {sourceWorkspaceStatuses.has(project.status) && (
        <Link
          to={`/projects/${project.id}/sources`}
          style={{
            display: "inline-block",
            marginTop: "1rem",
            marginLeft: "0.5rem",
            padding: "0.5rem 0.9rem",
            border: "1px solid #2563eb",
            color: "#2563eb",
            borderRadius: "0.375rem",
            textDecoration: "none",
          }}
        >
          进入公开资料与证据工作区
        </Link>
      )}
    </div>
  );
}
