import { useParams, Link } from "react-router";
import { useProject } from "../features/projects/hooks";

/** 项目状态中文映射。 */
function statusLabel(s: string) {
  const m: Record<string, string> = {
    DRAFT: "草稿",
    REQUIREMENT_PARSED: "要求已解析",
    REQUIREMENT_CONFIRMED: "需求已确认",
    SOURCES_COLLECTED: "来源已收集",
    EVIDENCE_CONFIRMED: "证据已确认",
    DATASET_READY: "数据集已就绪",
    ANALYSIS_PLANNED: "分析方案已生成",
    ANALYSIS_CONFIRMED: "分析方案已确认",
    EXECUTING: "执行中",
    EXECUTION_FAILED: "执行失败",
    RESULT_CONFIRMED: "结果已确认",
    OUTLINE_CONFIRMED: "大纲已确认",
    GENERATING: "交付物生成中",
    COMPLETED: "已完成",
  };
  return m[s] ?? s;
}

/** 项目状态顺序，用于判断入口可见性。 */
const ORDERED_STATUSES = [
  "DRAFT",
  "REQUIREMENT_PARSED",
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
];

function isAtOrAfter(status: string, target: string) {
  const a = ORDERED_STATUSES.indexOf(status);
  const b = ORDERED_STATUSES.indexOf(target);
  if (a < 0 || b < 0) return false;
  return a >= b;
}

const linkStyle: React.CSSProperties = {
  display: "inline-block",
  marginTop: "0.5rem",
  padding: "0.5rem 0.9rem",
  background: "#2563eb",
  color: "#fff",
  borderRadius: "0.375rem",
  textDecoration: "none",
  fontSize: "0.9rem",
};

const secondaryLinkStyle: React.CSSProperties = {
  display: "inline-block",
  marginTop: "0.5rem",
  padding: "0.5rem 0.9rem",
  background: "#0ea5e9",
  color: "#fff",
  borderRadius: "0.375rem",
  textDecoration: "none",
  fontSize: "0.9rem",
};

const accentLinkStyle: React.CSSProperties = {
  display: "inline-block",
  marginTop: "0.5rem",
  padding: "0.5rem 0.9rem",
  background: "#7c3aed",
  color: "#fff",
  borderRadius: "0.375rem",
  textDecoration: "none",
  fontSize: "0.9rem",
};

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

  const showRequirementEntry = true;
  const showSourcesEntry = isAtOrAfter(project.status, "REQUIREMENT_CONFIRMED");
  const showEvidenceEntry = isAtOrAfter(project.status, "REQUIREMENT_CONFIRMED");
  const showDatasetsEntry = isAtOrAfter(project.status, "EVIDENCE_CONFIRMED");
  const showAnalysisEntry = isAtOrAfter(project.status, "DATASET_READY");
  const showOutlineEntry = isAtOrAfter(project.status, "RESULT_CONFIRMED");
  const showDeliverablesEntry = isAtOrAfter(project.status, "OUTLINE_CONFIRMED");

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

      {showRequirementEntry && (
        <div style={{ marginTop: "1rem" }}>
          <Link to={`/projects/${project.id}/requirements`} style={linkStyle}>
            进入实验要求工作区
          </Link>
        </div>
      )}

      {showSourcesEntry && (
        <div style={{ marginTop: "0.5rem" }}>
          <Link to={`/projects/${project.id}/sources`} style={secondaryLinkStyle}>
            进入资料来源工作区
          </Link>
        </div>
      )}

      {showEvidenceEntry && (
        <div style={{ marginTop: "0.5rem" }}>
          <Link to={`/projects/${project.id}/evidence`} style={secondaryLinkStyle}>
            进入证据卡片工作区
          </Link>
        </div>
      )}

      {showDatasetsEntry && (
        <div style={{ marginTop: "0.5rem" }}>
          <Link to={`/projects/${project.id}/datasets`} style={secondaryLinkStyle}>
            进入数据集工作区
          </Link>
        </div>
      )}

      {showAnalysisEntry && (
        <div style={{ marginTop: "0.5rem" }}>
          <Link to={`/projects/${project.id}/analysis`} style={secondaryLinkStyle}>
            进入分析方案工作区
          </Link>
        </div>
      )}

      {showOutlineEntry && (
        <div style={{ marginTop: "0.5rem" }}>
          <Link to={`/projects/${project.id}/outline`} style={accentLinkStyle}>
            进入大纲工作区
          </Link>
        </div>
      )}

      {showDeliverablesEntry && (
        <div style={{ marginTop: "0.5rem" }}>
          <Link to={`/projects/${project.id}/deliverables`} style={accentLinkStyle}>
            进入交付物工作区
          </Link>
        </div>
      )}
    </div>
  );
}
