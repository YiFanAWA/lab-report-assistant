import { Link, useParams } from "react-router";
import { StatusBadge } from "../components/workspace/WorkspaceUI";
import {
  useProject,
  useWorkspaceProjection,
} from "../features/projects/hooks";
import type {
  WorkspaceProgressPhase,
  WorkspaceProgressStatus,
} from "../shared/types";

function formatDate(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function phaseVisualState(status: WorkspaceProgressStatus) {
  if (status === "COMPLETED") return "completed";
  if (status === "FAILED" || status === "BLOCKED") return "failed";
  if (status === "LOCKED") return "upcoming";
  return "current";
}

function phaseRoute(phase: WorkspaceProgressPhase) {
  return (
    phase.actions.find((action) => action.enabled && action.route)?.route ??
    phase.steps.find((step) => step.is_open)?.route
  );
}

export function ProjectDetailView() {
  const { projectId } = useParams<{ projectId: string }>();
  const {
    data: project,
    isLoading: projectLoading,
    isError: projectError,
    error,
  } = useProject(projectId ?? "");
  const {
    data: projection,
    isLoading: projectionLoading,
    isError: projectionError,
  } = useWorkspaceProjection(projectId ?? "");

  if (projectLoading || projectionLoading) {
    return (
      <div className="project-detail-loading">
        <p className="sr-only">加载中…</p>
        <div className="project-detail-loading__panel" aria-hidden="true" />
      </div>
    );
  }

  if (projectError || projectionError) {
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

  if (!project || !projection) return null;

  const phases = projection.phases;
  const steps = phases.flatMap((phase) => phase.steps);
  const current = projection.current;
  const nextAction = projection.recommended_next_action;
  const projectStatusLabel = projection.project.status_label;
  const openSteps = steps.filter((step) => step.is_open);

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
              {projection.project.topic}
            </p>
          </div>
          <div className="project-detail-header__status">
            <StatusBadge status={project.status} label={projectStatusLabel} />
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
            <span className="project-detail-meta__value">
              {nextAction?.label ?? "项目已完成"}
            </span>
          </div>
        </div>

        {current.status === "FAILED" && (
          <div className="project-detail-failure" role="alert">
            <span aria-hidden="true">!</span>
            <div>
              <strong>{current.label}需要处理</strong>
              请进入当前工作区查看失败原因，并使用现有页面操作恢复。
            </div>
          </div>
        )}

        <main className="project-detail-content-grid">
          <section
            className="project-detail-card project-detail-roadmap"
            aria-labelledby="project-roadmap-title"
          >
            <h2 className="project-detail-card__title" id="project-roadmap-title">
              实验流程
            </h2>
            <p className="project-detail-card__description">
              阶段状态和入口均来自项目进度投影，已确认的内容会保留在项目工作区中。
            </p>
            <ol className="project-detail-stage-list">
              {phases.map((phase, index) => {
                const route = phaseRoute(phase);
                const isOpen = phase.is_open && Boolean(route);
                const visualState = phaseVisualState(phase.status);
                const stageClassName =
                  "project-detail-stage project-detail-stage--" + visualState;
                const stageContent = (
                  <>
                    <span className="project-detail-stage__number">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="project-detail-stage__copy">
                      <span className="project-detail-stage__name">{phase.label}</span>
                      <span className="project-detail-stage__description">
                        {phase.description}
                      </span>
                      {phase.steps.length > 1 && (
                        <span className="project-detail-stage__description">
                          子步骤：{phase.steps.map((step) => step.label).join("、")}
                        </span>
                      )}
                    </span>
                    <span className="project-detail-stage__state">
                      {phase.display.status_label}
                    </span>
                    <span className="project-detail-stage__arrow" aria-hidden="true">
                      →
                    </span>
                  </>
                );

                return (
                  <li className="project-detail-stage__item" key={phase.id}>
                    {isOpen ? (
                      <Link
                        className={stageClassName}
                        to={route as string}
                        aria-label={"进入" + phase.label + "阶段"}
                      >
                        {stageContent}
                      </Link>
                    ) : (
                      <div
                        className={stageClassName}
                        aria-disabled="true"
                        title={
                          phase.open_reason?.display_message ??
                          phase.open_reason?.message ??
                          phase.display.next_step_text
                        }
                      >
                        {stageContent}
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>
          </section>

          <aside className="project-detail-side">
            {nextAction?.route ? (
              <Link
                className="project-detail-next-card"
                to={nextAction.route}
              >
                <span className="project-detail-next-card__eyebrow">下一步</span>
                <span className="project-detail-next-card__title">
                  {nextAction.label}
                </span>
                <span className="project-detail-next-card__description">
                  {nextAction.description}
                </span>
                <span className="project-detail-next-card__action">
                  打开工作区 →
                </span>
              </Link>
            ) : (
              <div className="project-detail-next-card">
                <span className="project-detail-next-card__eyebrow">项目状态</span>
                <span className="project-detail-next-card__title">项目已完成</span>
                <span className="project-detail-next-card__description">
                  当前没有需要继续推进的项目级动作。
                </span>
              </div>
            )}

            <section className="project-detail-card project-detail-data-card">
              <h2 className="project-detail-card__title">数据分析准备</h2>
              <p className="project-detail-card__description">
                分析开始前，依次准备数据、字段和方法。
              </p>
              <div className="project-detail-data-list">
                <div className="project-detail-data-row">
                  <span className="project-detail-data-row__number">01</span>
                  <span className="project-detail-data-row__copy">
                    <strong>上传数据文件</strong>
                    <small>支持 CSV、Excel、JSON 等格式</small>
                  </span>
                  <span className="project-detail-data-row__arrow" aria-hidden="true">→</span>
                </div>
                <div className="project-detail-data-row">
                  <span className="project-detail-data-row__number">02</span>
                  <span className="project-detail-data-row__copy">
                    <strong>检查字段质量</strong>
                    <small>识别缺失值、异常值与数据类型</small>
                  </span>
                  <span className="project-detail-data-row__arrow" aria-hidden="true">→</span>
                </div>
                <div className="project-detail-data-row">
                  <span className="project-detail-data-row__number">03</span>
                  <span className="project-detail-data-row__copy">
                    <strong>准备分析方案</strong>
                    <small>选择分析方法与设定评估指标</small>
                  </span>
                  <span className="project-detail-data-row__arrow" aria-hidden="true">→</span>
                </div>
              </div>
            </section>
          </aside>
        </main>

        <section className="project-detail-workspaces" aria-labelledby="project-workspaces-title">
          <div className="project-detail-section-heading">
            <div>
              <h2 className="project-detail-card__title" id="project-workspaces-title">
                项目工作区
              </h2>
              <p className="project-detail-card__description">
                可访问入口由后端进度投影提供，锁定步骤不会伪装成可点击入口。
              </p>
            </div>
          </div>
          <div className="project-detail-workspace-grid">
            {openSteps.map((step, index) => (
              <Link
                className="project-detail-workspace-link"
                key={step.id}
                to={step.route}
                aria-label={step.actions[0]?.label ?? "进入" + step.label + "工作区"}
              >
                <span className="project-detail-workspace-link__marker" aria-hidden="true">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="project-detail-workspace-link__copy">
                  <span className="project-detail-workspace-link__label">
                    {step.label}
                  </span>
                  <span className="project-detail-workspace-link__description">
                    {step.description}
                  </span>
                  <span className="sr-only">{step.display.next_step_text}</span>
                </span>
                <span className="project-detail-workspace-link__arrow" aria-hidden="true">
                  →
                </span>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}