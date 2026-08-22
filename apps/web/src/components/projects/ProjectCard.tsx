import { Link } from "react-router";
import type { Project } from "../../shared/types";
import { getProjectStagePresentation, ProjectStatusBadge } from "./ProjectStatusBadge";

function formatUpdatedAt(value: string): string {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "更新时间未知";

  const date = new Date(timestamp);
  const now = new Date();
  const isSameDay = date.toDateString() === now.toDateString();
  if (isSameDay) {
    return `今天 ${date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
  }

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return `昨天 ${date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
  }

  return date.toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });
}

export function ProjectCard({ project }: { project: Project }) {
  const presentation = getProjectStagePresentation(project.status);
  const isFailed = project.status === "EXECUTION_FAILED";

  return (
    <Link
      className={`project-card${isFailed ? " project-card--failed" : ""}`}
      to={`/projects/${project.id}`}
      aria-label={`打开项目 ${project.name}`}
    >
      <div className="project-card__topline">
        <ProjectStatusBadge status={project.status} />
        <span className="project-card__updated">最近更新 {formatUpdatedAt(project.updated_at)}</span>
      </div>

      <div className="project-card__body">
        <h2 className="project-card__title">{project.name}</h2>
        <p className="project-card__topic">{project.topic}</p>
      </div>

      <div className={`project-card__next${isFailed ? " project-card__next--failed" : ""}`}>
        <div>
          <span className="project-card__next-label">下一步</span>
          <strong>{presentation.nextAction}</strong>
        </div>
        <span className="project-card__arrow" aria-hidden="true">→</span>
      </div>

      {isFailed && <p className="project-card__hint">列表页不展示内部错误详情，请进入项目查看失败原因。</p>}
    </Link>
  );
}
