import { Link, useParams } from "react-router";
import {
  getProjectStagePresentation,
  ProjectStatusBadge,
} from "../components/projects/ProjectStatusBadge";
import { useProject } from "../features/projects/hooks";

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

const STAGES = [
  { key: "requirements", label: "实验要求", completeAt: "REQUIREMENT_CONFIRMED" },
  { key: "sources", label: "资料整理", completeAt: "EVIDENCE_CONFIRMED" },
  { key: "datasets", label: "数据上传", completeAt: "DATASET_READY" },
  { key: "analysis", label: "分析方案", completeAt: "RESULT_CONFIRMED" },
  { key: "results", label: "结果确认", completeAt: "OUTLINE_CONFIRMED" },
  { key: "deliverables", label: "交付物", completeAt: "COMPLETED" },
] as const;

type StageState = "completed" | "current" | "failed" | "upcoming";

function getStageState(status: string, stageIndex: number): StageState {
  const currentIndex = STAGES.findIndex(
    (stage) => !isAtOrAfter(status, stage.completeAt),
  );

  if (currentIndex < 0) return "completed";
  if (stageIndex < currentIndex) return "completed";
  if (stageIndex === currentIndex) {
    return status === "EXECUTION_FAILED" ? "failed" : "current";
  }
  return "upcoming";
}

const WORKSPACE_DEFINITIONS = [
  {
    key: "requirements",
    label: "进入实验要求工作区",
    description: "确认实验目的、变量和交付要求",
    route: "requirements",
  },
  {
    key: "sources",
    label: "进入资料来源工作区",
    description: "整理公开资料和参考来源",
    route: "sources",
  },
  {
    key: "evidence",
    label: "进入证据卡片工作区",
    description: "确认资料中的可追溯证据",
    route: "evidence",
  },
  {
    key: "datasets",
    label: "进入数据集工作区",
    description: "上传数据并检查字段质量",
    route: "datasets",
  },
  {
    key: "analysis",
    label: "进入分析方案工作区",
    description: "明确变量、方法和分析路径",
    route: "analysis",
  },
  {
    key: "execution",
    label: "进入执行工作区",
    description: "运行代码并查看执行记录",
    route: "execution",
  },
  {
    key: "outline",
    label: "进入大纲工作区",
    description: "确认报告和演示文稿结构",
    route: "outline",
  },
  {
    key: "deliverables",
    label: "进入交付物工作区",
    description: "导出 Word / PPT 并回看版本",
    route: "deliverables",
  },
] as const;

function formatDate(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getWorkspaceVisibility(status: string) {
  return {
    requirements: true,
    sources: isAtOrAfter(status, "REQUIREMENT_CONFIRMED"),
    evidence: isAtOrAfter(status, "REQUIREMENT_CONFIRMED"),
    datasets: isAtOrAfter(status, "EVIDENCE_CONFIRMED"),
    analysis: isAtOrAfter(status, "DATASET_READY"),
    execution: isAtOrAfter(status, "ANALYSIS_CONFIRMED"),
    outline: isAtOrAfter(status, "RESULT_CONFIRMED"),
    deliverables: isAtOrAfter(status, "OUTLINE_CONFIRMED"),
  };
}

function getNextWorkspace(status: string) {
  if (status === "DRAFT" || status === "REQUIREMENT_PARSED") return WORKSPACE_DEFINITIONS[0];
  if (status === "REQUIREMENT_CONFIRMED") return WORKSPACE_DEFINITIONS[1];
  if (status === "SOURCES_COLLECTED") return WORKSPACE_DEFINITIONS[2];
  if (status === "EVIDENCE_CONFIRMED") return WORKSPACE_DEFINITIONS[3];
  if (status === "DATASET_READY" || status === "ANALYSIS_PLANNED") return WORKSPACE_DEFINITIONS[4];
  if (status === "ANALYSIS_CONFIRMED" || status === "EXECUTING" || status === "EXECUTION_FAILED") {
    return WORKSPACE_DEFINITIONS[5];
  }
  if (status === "RESULT_CONFIRMED") return WORKSPACE_DEFINITIONS[6];
  return WORKSPACE_DEFINITIONS[7];
}

export function ProjectDetailView() {
  const { projectId } = useParams<{ projectId: string }>();
  const { data: project, isLoading, isError, error } = useProject(projectId ?? "");

  if (isLoading) {
    return (
      <div className="project-detail-loading">
        <p className="sr-only">加载中…</p>
        <div className="project-detail-loading__panel" aria-hidden="true" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="project-detail-state">
        <div className="project-detail-state__panel project-detail-state__panel--error">
          <p className="project-detail-state__message">
            {(error as { message?: string })?.message ?? "无法加载项目"}
          </p>
          <Link className="project-detail-state__back" to="/">
            返回项目列表
          </Link>
        </div>
      </div>
    );
  }

  if (!project) return null;

  const visibility = getWorkspaceVisibility(project.status);
  const presentation = getProjectStagePresentation(project.status);
  const nextWorkspace = getNextWorkspace(project.status);
  const visibleWorkspaces = WORKSPACE_DEFINITIONS.filter(
    (workspace) => visibility[workspace.key as keyof typeof visibility],
  );

  return (
    <div className="project-detail-page">
      <div className="project-detail-container">
        <nav className="project-detail-topbar" aria-label="项目导航">
          <span className="project-detail-topbar__brand">实验报告助手</span>
          <Link className="project-detail-back" to="/">
            ← 返回项目列表
          </Link>
          <span className="project-detail-topbar__label">项目详情</span>
        </nav>

        <header className="project-detail-header">
          <div className="project-detail-header__identity">
            <p className="project-detail-eyebrow">学生实验工作台</p>
            <h1 className="project-detail-title">{project.name}</h1>
            <p className="project-detail-topic">
              <strong>课题</strong>
              {project.topic}
            </p>
          </div>
          <div className="project-detail-header__status">
            <ProjectStatusBadge status={project.status} />
            <span className="project-detail-header__status-label">当前项目阶段</span>
          </div>
        </header>

        <div className="project-detail-meta">
          <div className="project-detail-meta__item">
            <span className="project-detail-meta__label">创建时间</span>
            <span className="project-detail-meta__value">{formatDate(project.created_at)}</span>
          </div>
          <div className="project-detail-meta__item">
            <span className="project-detail-meta__label">最近更新</span>
            <span className="project-detail-meta__value">{formatDate(project.updated_at)}</span>
          </div>
          <div className="project-detail-meta__item">
            <span className="project-detail-meta__label">建议下一步</span>
            <span className="project-detail-meta__value">{presentation.nextAction}</span>
          </div>
        </div>

        {project.status === "EXECUTION_FAILED" && (
          <div className="project-detail-failure" role="alert">
            <span aria-hidden="true">!</span>
            <div>
              <strong>执行任务需要处理</strong>
              进入执行工作区查看具体失败原因，并在确认后重试。
            </div>
          </div>
        )}

        <main className="project-detail-content-grid">
          <section className="project-detail-card project-detail-roadmap" aria-labelledby="project-roadmap-title">
            <h2 className="project-detail-card__title" id="project-roadmap-title">实验流程</h2>
            <p className="project-detail-card__description">
              按顺序完成每个阶段，已确认的内容会保留在项目工作区中。
            </p>
            <ol className="project-detail-stage-list">
              {STAGES.map((stage, index) => {
                const state = getStageState(project.status, index);
                const stateLabel =
                  state === "completed" ? "完成" :
                  state === "current" ? "进行中" :
                  state === "failed" ? "需处理" : "待开始";

                return (
                  <li
                    className={"project-detail-stage project-detail-stage--" + state}
                    key={stage.key}
                  >
                    <span className="project-detail-stage__number">{String(index + 1).padStart(2, "0")}</span>
                    <span className="project-detail-stage__name">{stage.label}</span>
                    <span className="project-detail-stage__state">{stateLabel}</span>
                  </li>
                );
              })}
            </ol>
          </section>

          <aside className="project-detail-side">
            <Link
              className="project-detail-next-card"
              to={"/projects/" + project.id + "/" + nextWorkspace.route}
            >
              <span className="project-detail-next-card__eyebrow">下一步</span>
              <span className="project-detail-next-card__title">{presentation.nextAction}</span>
              <span className="project-detail-next-card__description">
                打开对应工作区，继续完成当前项目的关键任务。
              </span>
              <span className="project-detail-next-card__action">打开工作区 →</span>
            </Link>

            <section className="project-detail-card project-detail-data-card">
              <h2 className="project-detail-card__title">数据分析准备</h2>
              <p className="project-detail-card__description">
                分析开始前，依次准备数据、字段和方法。
              </p>
              <div className="project-detail-data-list">
                <div className="project-detail-data-row">
                  <span className="project-detail-data-row__number">01</span>
                  <span>上传数据文件</span>
                </div>
                <div className="project-detail-data-row">
                  <span className="project-detail-data-row__number">02</span>
                  <span>检查字段质量</span>
                </div>
                <div className="project-detail-data-row">
                  <span className="project-detail-data-row__number">03</span>
                  <span>准备分析方案</span>
                </div>
              </div>
            </section>
          </aside>
        </main>

        <section className="project-detail-workspaces" aria-labelledby="project-workspaces-title">
          <div className="project-detail-section-heading">
            <div>
              <h2 className="project-detail-card__title" id="project-workspaces-title">项目工作区</h2>
              <p className="project-detail-card__description">已开放的入口会根据项目状态逐步出现。</p>
            </div>
          </div>
          <div className="project-detail-workspace-grid">
            {visibleWorkspaces.map((workspace) => (
              <Link
                className="project-detail-workspace-link"
                key={workspace.key}
                to={"/projects/" + project.id + "/" + workspace.route}
              >
                <span className="project-detail-workspace-link__copy">
                  <span className="project-detail-workspace-link__label">{workspace.label}</span>
                  <span className="project-detail-workspace-link__description">{workspace.description}</span>
                </span>
                <span className="project-detail-workspace-link__arrow" aria-hidden="true">→</span>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
