import { useParams, Link } from "react-router";
import { useProject } from "../features/projects/hooks";

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
        <div><strong>状态：</strong>{project.status}</div>
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
    </div>
  );
}
