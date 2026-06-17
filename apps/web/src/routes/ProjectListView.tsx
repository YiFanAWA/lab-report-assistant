import { Link } from "react-router";
import { useProjects } from "../features/projects/hooks";
import type { Project } from "../shared/types";

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    DRAFT: "草稿",
    REQUIREMENT_CONFIRMED: "需求已确认",
    COMPLETED: "已完成",
  };
  return labels[status] ?? status;
}

export function ProjectListView() {
  const { data: projects, isLoading, isError, error } = useProjects();

  return (
    <div style={{ maxWidth: 640, margin: "0 auto", padding: "2rem 1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <h1 style={{ fontSize: "1.5rem", margin: 0 }}>实验报告助手</h1>
        <Link
          to="/projects/new"
          style={{
            padding: "0.5rem 1rem",
            background: "#2563eb",
            color: "#fff",
            textDecoration: "none",
            borderRadius: "0.25rem",
            fontSize: "0.9rem",
          }}
        >
          新建项目
        </Link>
      </div>

      {isLoading && <p>加载中…</p>}

      {isError && (
        <p style={{ color: "#c00" }}>
          {(error as { message?: string })?.message ?? "无法加载项目列表"}
        </p>
      )}

      {projects && projects.length === 0 && (
        <p style={{ color: "#666" }}>还没有实验项目，点击"新建项目"开始。</p>
      )}

      {projects && projects.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {projects.map((p) => (
            <ProjectCard key={p.id} project={p} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProjectCard({ project: p }: { project: Project }) {
  return (
    <Link
      to={`/projects/${p.id}`}
      style={{
        display: "block",
        padding: "1rem",
        border: "1px solid #e5e7eb",
        borderRadius: "0.5rem",
        textDecoration: "none",
        color: "inherit",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontWeight: 600, fontSize: "1.05rem" }}>{p.name}</span>
        <span style={{ fontSize: "0.8rem", color: "#6b7280" }}>{statusLabel(p.status)}</span>
      </div>
      <div style={{ fontSize: "0.85rem", color: "#4b5563", marginTop: "0.25rem" }}>{p.topic}</div>
      <div style={{ fontSize: "0.75rem", color: "#9ca3af", marginTop: "0.5rem" }}>
        创建于 {new Date(p.created_at).toLocaleDateString("zh-CN")}
      </div>
    </Link>
  );
}
