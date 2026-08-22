import { Link } from "react-router";
import { ProjectCard } from "../components/projects/ProjectCard";
import { useProjects } from "../features/projects/hooks";
import type { Project } from "../shared/types";

function sortByUpdatedAt(projects: Project[]): Project[] {
  return [...projects].sort((a, b) => {
    const left = new Date(a.updated_at).getTime();
    const right = new Date(b.updated_at).getTime();
    if (!Number.isFinite(left) && !Number.isFinite(right)) return 0;
    if (!Number.isFinite(left)) return 1;
    if (!Number.isFinite(right)) return -1;
    return right - left;
  });
}

function ProjectCardSkeleton() {
  return (
    <div className="project-card project-card--skeleton" aria-hidden="true">
      <div className="skeleton-line skeleton-line--short" />
      <div className="skeleton-line skeleton-line--title" />
      <div className="skeleton-line skeleton-line--topic" />
      <div className="skeleton-block" />
    </div>
  );
}

export function ProjectListView() {
  const { data: projects, isLoading, isError, error } = useProjects();
  const sortedProjects = projects ? sortByUpdatedAt(projects) : [];

  return (
    <main className="app-shell project-list-page">
      <div className="page-container">
        <header className="page-header">
          <div>
            <p className="eyebrow">实验分析工作台</p>
            <h1 className="page-title">实验报告助手</h1>
            <p className="page-subtitle">管理实验项目，并继续完成实验报告分析流程。</p>
          </div>
          <Link className="button button--primary" to="/projects/new">
            <span aria-hidden="true">+</span>
            新建项目
          </Link>
        </header>

        <section className="project-list-section" aria-labelledby="project-list-title">
          <div className="section-heading">
            <div>
              <h2 id="project-list-title" className="section-title">全部项目</h2>
              <p className="section-description">
                {projects && projects.length > 0
                  ? `共 ${projects.length} 个项目，最近更新的项目优先显示。`
                  : "从一个实验项目开始，逐步完成要求、资料、数据和交付物。"}
              </p>
            </div>
          </div>

          {isLoading && (
            <div className="project-grid" aria-label="正在加载项目" aria-live="polite">
              <span className="sr-only">加载中…</span>
              <ProjectCardSkeleton />
              <ProjectCardSkeleton />
              <ProjectCardSkeleton />
            </div>
          )}

          {isError && (
            <div className="state-panel state-panel--error" role="alert">
              <div className="state-panel__icon" aria-hidden="true">!</div>
              <div>
                <h3>项目列表加载失败</h3>
                <p>{(error as { message?: string })?.message ?? "无法加载项目列表"}</p>
                <span className="state-panel__hint">请确认本地服务正在运行，然后重新打开页面。</span>
              </div>
            </div>
          )}

          {projects && projects.length === 0 && (
            <div className="state-panel state-panel--empty">
              <div className="empty-state__mark" aria-hidden="true">+</div>
              <h3>还没有实验项目</h3>
              <p>创建第一个实验项目，开始整理要求、资料和数据。</p>
              <Link className="button button--primary" to="/projects/new">创建第一个项目</Link>
            </div>
          )}

          {sortedProjects.length > 0 && (
            <div className="project-grid">
              {sortedProjects.map((project) => (
                <ProjectCard key={project.id} project={project} />
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
