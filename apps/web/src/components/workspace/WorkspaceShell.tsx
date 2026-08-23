import type { ReactNode } from "react";
import { Link } from "react-router";
import type {
  Project,
  WorkspaceProgressCurrent,
  WorkspaceProgressPhase,
  WorkspaceProgressStep,
  WorkspaceProjection,
} from "../../shared/types";
import { StatusBadge } from "./WorkspaceUI";

interface WorkspaceShellProps {
  project: Project;
  projection?: WorkspaceProjection | null;
  children: ReactNode;
  title: string;
  eyebrow?: string;
}

function stageTone(status: WorkspaceProgressStep["status"]) {
  if (status === "FAILED" || status === "BLOCKED") return "danger";
  if (status === "COMPLETED") return "success";
  if (status === "IN_PROGRESS" || status === "READY") return "accent";
  return "neutral";
}

function findCurrentStep(
  phases: WorkspaceProgressPhase[],
  current?: WorkspaceProgressCurrent,
) {
  if (!current) return undefined;
  return phases
    .flatMap((phase) => phase.steps)
    .find((step) => step.id === current.step_id);
}

function currentStatusLabel(
  current: WorkspaceProgressCurrent,
  step?: WorkspaceProgressStep,
) {
  return step?.display.status_label ?? current.status;
}

export function WorkspaceShell({
  project,
  projection,
  children,
  title,
  eyebrow = "项目工作台",
}: WorkspaceShellProps) {
  const phases = projection?.phases ?? [];
  const current = projection?.current;
  const currentStep = findCurrentStep(phases, current);
  const nextAction = projection?.recommended_next_action;
  const projectStatusLabel = projection?.project.status_label ?? project.status;

  return (
    <div className="workspace-shell">
      <header className="workspace-shell__header">
        <div className="workspace-shell__topline">
          <Link className="workspace-shell__brand" to="/">
            实验报告助手
          </Link>
          <span className="workspace-shell__project-name">{project.name}</span>
          <Link className="workspace-shell__back" to={"/projects/" + project.id}>
            返回项目总览
          </Link>
        </div>

        <div className="workspace-shell__identity">
          <div>
            <p className="workspace-shell__eyebrow">{eyebrow}</p>
            <h1 className="workspace-shell__title">{title}</h1>
            {project.topic && <p className="workspace-shell__topic">{project.topic}</p>}
          </div>
          <div className="workspace-shell__status">
            <StatusBadge status={project.status} label={projectStatusLabel} />
            <span className="workspace-shell__updated">
              {project.updated_at
                ? "更新于 " + new Date(project.updated_at).toLocaleString("zh-CN")
                : "更新时间不可用"}
            </span>
          </div>
        </div>

        {current && (
          <div className="workspace-shell__current">
            <span>当前阶段</span>
            <strong>{current.phase_label}</strong>
            {currentStep?.is_substep && <em>{currentStep.label}</em>}
            <StatusBadge
              status={current.status}
              label={currentStatusLabel(current, currentStep)}
            />
          </div>
        )}

        {nextAction?.route && (
          <div className="workspace-shell__next">
            <span className="workspace-shell__next-label">下一步</span>
            <Link to={nextAction.route}>{nextAction.label}</Link>
            <span className="workspace-shell__next-reason">
              {nextAction.description}
            </span>
          </div>
        )}
      </header>

      {phases.length > 0 && (
        <nav className="workspace-shell__nav" aria-label="项目阶段进度">
          <div className="workspace-shell__nav-inner">
            {phases.map((phase) => (
              <div
                key={phase.id}
                className={[
                  "workspace-shell__nav-group",
                  phase.steps.length > 1
                    ? "workspace-shell__nav-group--compound"
                    : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                <span className="workspace-shell__nav-group-label">
                  {phase.label}
                </span>
                <div className="workspace-shell__nav-items">
                  {phase.steps.map((step) => {
                    const className = [
                      "workspace-shell__nav-item",
                      "workspace-shell__nav-item--" + step.status.toLowerCase(),
                      "workspace-shell__nav-item--" + stageTone(step.status),
                    ].join(" ");
                    const title =
                      step.open_reason?.display_message ??
                      step.open_reason?.message ??
                      step.blocking_reasons[0]?.display_message ??
                      step.blocking_reasons[0]?.message;

                    const content = (
                      <>
                        <span className="workspace-shell__nav-label">
                          {step.label}
                        </span>
                        <span className="workspace-shell__nav-state">
                          {step.display.status_label}
                        </span>
                      </>
                    );

                    return step.is_open ? (
                      <Link
                        key={step.id}
                        className={className}
                        to={step.route}
                        aria-current={
                          current?.step_id === step.id ? "step" : undefined
                        }
                        title={title}
                      >
                        {content}
                      </Link>
                    ) : (
                      <span
                        key={step.id}
                        className={
                          className +
                          " workspace-shell__nav-item--locked"
                        }
                        aria-disabled="true"
                        title={title}
                      >
                        {content}
                      </span>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </nav>
      )}

      <main className="workspace-shell__content">{children}</main>
    </div>
  );
}