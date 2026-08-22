import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { useProject } from "../features/projects/hooks";
import {
  useSources,
  useAddTextSource,
  useAddDocxSource,
  useCurrentPlan,
  useGeneratePlan,
  useStreamGeneratePlan,
  useUpdatePlan,
  useConfirmPlan,
} from "../features/requirements/hooks";
import type {
  RequirementTask,
  RequirementPlanPayload,
  RequirementSource,
} from "../features/requirements/types";

function statusLabel(s: string) {
  const m: Record<string, string> = {
    DRAFT: "草稿",
    REQUIREMENT_PARSED: "要求已解析",
    REQUIREMENT_CONFIRMED: "需求已确认",
    COMPLETED: "已完成",
  };
  return m[s] ?? s;
}

function taskTypeLabel(t: string) {
  const m: Record<string, string> = {
    REQUIRED: "必须",
    RECOMMENDED: "推荐",
    OPTIONAL: "可选",
    OUT_OF_SCOPE: "超范围",
    UNKNOWN: "待确认",
  };
  return m[t] ?? t;
}

function errorMessage(e: unknown, fallback: string) {
  if (typeof e === "object" && e !== null && "message" in e) {
    const message = (e as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return fallback;
}

function TaskList({
  tasks,
  label,
  tone,
}: {
  tasks: RequirementTask[];
  label: string;
  tone: "primary" | "success" | "muted" | "danger" | "warning";
}) {
  if (!tasks.length) return null;

  return (
    <section className={"requirement-task-group requirement-task-group--" + tone}>
      <div className="requirement-task-group__heading">
        <h3>{label}</h3>
        <span>{tasks.length} 项</span>
      </div>
      <div className="requirement-task-list">
        {tasks.map((task, index) => (
          <article className="requirement-task" key={index}>
            <div className="requirement-task__title-row">
              <strong>{task.title}</strong>
              <span className="requirement-task__type">
                {taskTypeLabel(task.task_type)}
              </span>
            </div>
            <p>{task.description}</p>
            {task.source_quote && (
              <div className="requirement-task__source">
                来源: {task.source_quote}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

function RequirementList({
  label,
  items,
}: {
  label: string;
  items: string[];
}) {
  if (!items.length) return null;

  return (
    <div className="requirement-plan-list">
      <span className="requirement-plan-list__label">{label}</span>
      <ul>
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function SourceItem({ source }: { source: RequirementSource }) {
  return (
    <article className="requirement-source-item">
      <div className="requirement-source-item__heading">
        <div>
          <strong>{source.title}</strong>
          <span>{source.source_type}</span>
        </div>
        <time dateTime={source.created_at}>
          {new Date(source.created_at).toLocaleDateString("zh-CN")}
        </time>
      </div>
      <p>
        {source.original_text.slice(0, 200)}
        {source.original_text.length > 200 ? "…" : ""}
      </p>
    </article>
  );
}

export function RequirementWorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const pid = projectId!;
  const { data: project, isLoading: projLoading } = useProject(pid);
  const { data: sources, isLoading: srcLoading } = useSources(pid);
  const { data: plan, isLoading: planLoading } = useCurrentPlan(pid);

  const [pasteTitle, setPasteTitle] = useState("老师实验要求");
  const [pasteText, setPasteText] = useState("");
  const [textErr, setTextErr] = useState<string | null>(null);
  const [docxTitle, setDocxTitle] = useState("老师实验要求文档");
  const [docxFile, setDocxFile] = useState<File | null>(null);
  const [docxErr, setDocxErr] = useState<string | null>(null);

  const addSource = useAddTextSource(pid);
  const addDocx = useAddDocxSource(pid);
  const generate = useGeneratePlan(pid);
  const streamGenerate = useStreamGeneratePlan(pid);
  const updatePlan = useUpdatePlan(pid);
  const confirm = useConfirmPlan(pid);

  const [genErr, setGenErr] = useState<string | null>(null);
  const [streamErr, setStreamErr] = useState<string | null>(null);
  const [editErr, setEditErr] = useState<string | null>(null);
  const [editOk, setEditOk] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editPayload, setEditPayload] = useState<RequirementPlanPayload | null>(null);

  useEffect(() => {
    setEditPayload(plan?.payload ?? null);
    setIsEditing(false);
    setEditErr(null);
  }, [plan?.id, plan?.updated_at]);

  if (projLoading) {
    return (
      <div className="requirement-state">
        <p className="sr-only">加载中…</p>
        <div className="requirement-loading-panel" aria-hidden="true" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="requirement-state">
        <div className="requirement-state__panel requirement-state__panel--error">
          <p>项目不存在</p>
          <Link to={"/projects/" + pid}>返回项目详情</Link>
        </div>
      </div>
    );
  }

  const hasSources = Boolean(sources?.length);
  const shownPayload = isEditing && editPayload ? editPayload : plan?.payload;

  return (
    <div className="requirement-page">
      <div className="requirement-container">
        <nav className="requirement-topbar" aria-label="实验要求导航">
          <span className="requirement-topbar__brand">实验报告助手</span>
          <Link className="requirement-topbar__back" to={"/projects/" + pid}>
            ← 项目详情
          </Link>
          <span className="requirement-topbar__label">实验要求</span>
        </nav>

        <header className="requirement-header">
          <div>
            <p className="requirement-eyebrow">阶段 01 / 06 · 建立任务单</p>
            <h1 className="requirement-title">实验要求工作区</h1>
            <p className="requirement-subtitle">
              先保存老师给出的原始要求，再生成一份可检查、可确认的实验任务单。
            </p>
          </div>
          <div className="requirement-header__status">
            <span className="requirement-status-chip">[{statusLabel(project.status)}]</span>
            <span>项目状态</span>
          </div>
        </header>

        <div className="requirement-project-meta">
          <span>
            <small>项目</small>
            {project.name}
          </span>
          <span>
            <small>课题</small>
            {project.topic}
          </span>
          <span>
            <small>当前目标</small>
            保存要求 → 生成任务单 → 确认
          </span>
        </div>

        <main className="requirement-main">
          <div className="requirement-top-grid">
            <section className="requirement-card requirement-input-card">
              <div className="requirement-card__heading">
                <div>
                  <p className="requirement-card__eyebrow">Step 1 · 输入资料</p>
                  <h2>添加实验要求</h2>
                  <p>支持直接粘贴文字，也可以上传老师提供的 Word 文档。</p>
                </div>
                <span className="requirement-card__index">01</span>
              </div>

              <div className="requirement-form-section">
                <div className="requirement-form-section__title">
                  <span className="requirement-form-section__marker">A</span>
                  <div>
                    <h3>粘贴文字要求</h3>
                    <p>适合从课程群、作业说明或网页中复制内容。</p>
                  </div>
                </div>
                <label className="requirement-field">
                  <span>来源标题</span>
                  <input
                    value={pasteTitle}
                    onChange={(e) => setPasteTitle(e.target.value)}
                    placeholder="来源标题"
                  />
                </label>
                <label className="requirement-field">
                  <span>原始要求</span>
                  <textarea
                    value={pasteText}
                    onChange={(e) => setPasteText(e.target.value)}
                    placeholder="粘贴老师给的实验要求…"
                    rows={6}
                  />
                </label>
                <div className="requirement-form-actions">
                  <button
                    className="button button--primary"
                    onClick={() => {
                      setTextErr(null);
                      if (!pasteText.trim()) return;
                      addSource.mutate(
                        { title: pasteTitle, text: pasteText },
                        {
                          onSuccess: () => setPasteText(""),
                          onError: (e) => setTextErr(errorMessage(e, "保存失败")),
                        },
                      );
                    }}
                    disabled={addSource.isPending}
                  >
                    {addSource.isPending ? "保存中…" : "保存要求"}
                  </button>
                  {addSource.data && (
                    <span className="requirement-feedback requirement-feedback--success">
                      已保存 ✓
                    </span>
                  )}
                  {textErr && (
                    <span className="requirement-feedback requirement-feedback--error">
                      {textErr}
                    </span>
                  )}
                </div>
              </div>

              <div className="requirement-form-divider">
                <span>或</span>
              </div>

              <div className="requirement-form-section requirement-form-section--upload">
                <div className="requirement-form-section__title">
                  <span className="requirement-form-section__marker">B</span>
                  <div>
                    <h3>Word 要求来源</h3>
                    <p>仅接受 .docx 文件，上传后会保留原始内容。</p>
                  </div>
                </div>
                <label className="requirement-field">
                  <span>Word 来源标题</span>
                  <input
                    value={docxTitle}
                    onChange={(e) => setDocxTitle(e.target.value)}
                    placeholder="Word 来源标题"
                  />
                </label>
                <label className="requirement-file-field">
                  <span className="requirement-file-field__dropzone">
                    <strong>{docxFile ? docxFile.name : "选择 .docx 文件"}</strong>
                    <small>点击选择本地 Word 文件</small>
                    <input
                      type="file"
                      accept=".docx"
                      onChange={(e) => setDocxFile(e.target.files?.[0] ?? null)}
                    />
                  </span>
                </label>
                <div className="requirement-form-actions">
                  <button
                    className="button button--secondary"
                    onClick={() => {
                      setDocxErr(null);
                      if (!docxFile) {
                        setDocxErr("请选择 .docx 文件");
                        return;
                      }
                      addDocx.mutate(
                        { title: docxTitle, file: docxFile },
                        {
                          onSuccess: () => setDocxFile(null),
                          onError: (e) => setDocxErr(errorMessage(e, "上传失败")),
                        },
                      );
                    }}
                    disabled={addDocx.isPending}
                  >
                    {addDocx.isPending ? "上传中…" : "上传 Word 要求"}
                  </button>
                  {addDocx.data && (
                    <span className="requirement-feedback requirement-feedback--success">
                      Word 要求已保存 ✓
                    </span>
                  )}
                  {docxErr && (
                    <span className="requirement-feedback requirement-feedback--error">
                      {docxErr}
                    </span>
                  )}
                </div>
              </div>
            </section>

            <aside className="requirement-side-column">
              <section className="requirement-next-card">
                <p className="requirement-next-card__eyebrow">本阶段目标</p>
                <h2>把老师的要求变成可执行任务</h2>
                <div className="requirement-next-card__steps">
                  <div className={hasSources ? "is-done" : "is-current"}>
                    <span>01</span>
                    <p>
                      <strong>保存原始要求</strong>
                      <small>{hasSources ? "已完成" : "等待输入"}</small>
                    </p>
                  </div>
                  <div className={plan ? "is-done" : hasSources ? "is-current" : ""}>
                    <span>02</span>
                    <p>
                      <strong>整理任务单候选</strong>
                      <small>{plan ? "已生成" : "需要先保存要求"}</small>
                    </p>
                  </div>
                  <div className={plan?.status === "CONFIRMED" ? "is-done" : ""}>
                    <span>03</span>
                    <p>
                      <strong>确认并进入下一阶段</strong>
                      <small>{plan?.status === "CONFIRMED" ? "已确认" : "待确认"}</small>
                    </p>
                  </div>
                </div>
              </section>

              <section className="requirement-guide-card">
                <p className="requirement-card__eyebrow">使用提示</p>
                <h2>先保留原文，再做结构化整理</h2>
                <p>
                  原始要求会作为后续任务单、资料来源和交付物的追溯依据。不要只保留模型整理后的摘要。
                </p>
              </section>
            </aside>
          </div>

          <section className="requirement-card requirement-sources-card">
            <div className="requirement-card__heading">
              <div>
                <p className="requirement-card__eyebrow">Step 2 · 保留证据</p>
                <h2>{hasSources ? "已保存的原始要求" : "要求来源"}</h2>
                <p>这些内容不会被任务单覆盖，后续可以回看来源。</p>
              </div>
              <span className="requirement-count">{sources?.length ?? 0} 个来源</span>
            </div>

            {srcLoading && <p className="requirement-inline-loading">正在读取来源…</p>}
            {!srcLoading && !hasSources && (
              <div className="requirement-empty-state">
                <span className="requirement-empty-state__icon">＋</span>
                <div>
                  <strong>还没有保存的要求</strong>
                  <p>在上方粘贴文字或上传 Word 文件后，这里会显示原始来源。</p>
                </div>
              </div>
            )}

            {hasSources && (
              <>
                <div className="requirement-source-list">
                  {sources!.map((source) => (
                    <SourceItem key={source.id} source={source} />
                  ))}
                </div>
                <div className="requirement-generation">
                  <div>
                    <h3>生成结构化任务单</h3>
                    <p>从第一个来源生成候选任务单，确认前仍可以编辑。</p>
                  </div>
                  <div className="requirement-generation__actions">
                    <button
                      className="button button--secondary"
                      onClick={() => {
                        setGenErr(null);
                        const srcId = sources![0].id;
                        generate.mutate(srcId, {
                          onError: (e) => setGenErr(errorMessage(e, "生成失败")),
                        });
                      }}
                      disabled={generate.isPending || streamGenerate.streaming}
                    >
                      {generate.isPending ? "生成中…" : "生成任务单候选"}
                    </button>
                    <button
                      className="button button--primary"
                      onClick={() => {
                        setStreamErr(null);
                        const srcId = sources![0].id;
                        streamGenerate.start(srcId);
                      }}
                      disabled={generate.isPending || streamGenerate.streaming}
                    >
                      {streamGenerate.streaming ? "流式生成中…" : "流式生成任务单"}
                    </button>
                  </div>
                </div>
                {genErr && (
                  <p className="requirement-feedback requirement-feedback--error">{genErr}</p>
                )}
              </>
            )}

            {streamGenerate.streaming && (
              <div className="requirement-stream-card">
                <div className="requirement-stream-card__heading">
                  <div>
                    <strong>正在逐 chunk 生成…</strong>
                    <span>生成内容会实时显示在这里</span>
                  </div>
                  <button className="button button--danger-ghost" onClick={streamGenerate.cancel}>
                    取消
                  </button>
                </div>
                <pre>{streamGenerate.chunks}</pre>
              </div>
            )}
            {streamGenerate.result && (
              <p className="requirement-feedback requirement-feedback--success requirement-result-message">
                流式生成完成 ✓ [{streamGenerate.result.candidate_source}
                {streamGenerate.result.fallback_used ? "（降级）" : ""}]
              </p>
            )}
            {streamGenerate.error && (
              <p className="requirement-feedback requirement-feedback--error requirement-result-message">
                流式生成失败：{streamGenerate.error.message}
                {streamGenerate.error.partial_text && (
                  <span className="requirement-partial-note">（已保留部分生成内容）</span>
                )}
              </p>
            )}
            {streamErr && (
              <p className="requirement-feedback requirement-feedback--error">{streamErr}</p>
            )}
          </section>

          {plan && shownPayload && (
            <section
              className={
                "requirement-card requirement-plan-card " +
                (plan.status === "CONFIRMED"
                  ? "requirement-plan-card--confirmed"
                  : "requirement-plan-card--candidate")
              }
            >
              <div className="requirement-card__heading requirement-plan-card__heading">
                <div>
                  <p className="requirement-card__eyebrow">Step 3 · 检查并确认</p>
                  <h2>任务单</h2>
                  <div className="requirement-plan-card__tags">
                    <span className="requirement-plan-status">
                      [{plan.status === "CANDIDATE" ? "待确认" : "已确认"}]
                    </span>
                    <span className="requirement-plan-source">[{plan.candidate_source}]</span>
                  </div>
                </div>
                {plan.status === "CANDIDATE" && (
                  <div className="requirement-plan-actions">
                    <button
                      className="button button--ghost"
                      onClick={() => {
                        setEditPayload(plan.payload);
                        setIsEditing((v) => !v);
                        setEditErr(null);
                      }}
                    >
                      {isEditing ? "取消编辑" : "编辑任务单"}
                    </button>
                    {isEditing && editPayload && (
                      <button
                        className="button button--secondary"
                        onClick={() => {
                          setEditErr(null);
                          setEditOk(null);
                          updatePlan.mutate(
                            { planId: plan.id, payload: editPayload },
                            {
                              onSuccess: () => {
                                setIsEditing(false);
                                setEditOk("已保存 ✓");
                                setTimeout(() => setEditOk(null), 1_500);
                              },
                              onError: (e) => setEditErr(errorMessage(e, "保存任务单失败")),
                            },
                          );
                        }}
                        disabled={updatePlan.isPending}
                      >
                        {updatePlan.isPending ? "保存中…" : "保存修改"}
                      </button>
                    )}
                    <button
                      className="button button--primary"
                      onClick={() => confirm.mutate(plan.id)}
                      disabled={confirm.isPending || updatePlan.isPending}
                    >
                      {confirm.isPending ? "确认中…" : "确认任务单"}
                    </button>
                  </div>
                )}
              </div>

              {plan.status === "CANDIDATE" && (
                <p className="requirement-plan-notice">
                  确认前仍可修改；确认后项目状态将推进为需求已确认。
                </p>
              )}
              {editErr && (
                <p className="requirement-feedback requirement-feedback--error">{editErr}</p>
              )}
              {editOk && (
                <p className="requirement-feedback requirement-feedback--success">{editOk}</p>
              )}

              {isEditing && editPayload && (
                <div className="requirement-edit-panel">
                  <label className="requirement-field">
                    <span>课题</span>
                    <input
                      value={editPayload.topic}
                      onChange={(e) => setEditPayload({ ...editPayload, topic: e.target.value })}
                    />
                  </label>
                  <label className="requirement-field">
                    <span>实验类型</span>
                    <input
                      value={editPayload.experiment_type}
                      onChange={(e) =>
                        setEditPayload({ ...editPayload, experiment_type: e.target.value })
                      }
                    />
                  </label>
                  <label className="requirement-field">
                    <span>研究对象</span>
                    <textarea
                      value={editPayload.research_subject}
                      onChange={(e) =>
                        setEditPayload({ ...editPayload, research_subject: e.target.value })
                      }
                      rows={3}
                    />
                  </label>
                </div>
              )}

              <div className="requirement-plan-summary">
                <div className="requirement-plan-summary__item">
                  <span>课题</span>
                  <strong>{shownPayload.topic}</strong>
                </div>
                <div className="requirement-plan-summary__item">
                  <span>实验类型</span>
                  <strong>{shownPayload.experiment_type}</strong>
                </div>
                <div className="requirement-plan-summary__item requirement-plan-summary__item--wide">
                  <span>研究对象</span>
                  <strong>{shownPayload.research_subject}</strong>
                </div>
              </div>

              {shownPayload.replication_level && (
                <div
                  className={
                    "requirement-replication-callout " +
                    (!shownPayload.replication_level.supported_in_v1
                      ? "requirement-replication-callout--danger"
                      : "")
                  }
                >
                  <div>
                    <strong>论文复刻层级</strong>
                    <span>
                      {shownPayload.replication_level.level} —{" "}
                      {shownPayload.replication_level.label}
                    </span>
                  </div>
                  {!shownPayload.replication_level.supported_in_v1 && (
                    <span className="requirement-unsupported">（第一版不支持）</span>
                  )}
                  <p>{shownPayload.replication_level.reason}</p>
                </div>
              )}

              <div className="requirement-plan-lists">
                <RequirementList label="数据要求" items={shownPayload.data_requirements} />
                <RequirementList label="方法要求" items={shownPayload.method_requirements} />
                <RequirementList label="图表要求" items={shownPayload.chart_requirements} />
                <RequirementList label="报告要求" items={shownPayload.report_requirements} />
                <RequirementList label="PPT 要求" items={shownPayload.presentation_requirements} />
              </div>

              <div className="requirement-task-groups">
                <TaskList tasks={shownPayload.required_tasks} label="必须任务" tone="primary" />
                <TaskList tasks={shownPayload.recommended_tasks} label="推荐任务" tone="success" />
                <TaskList tasks={shownPayload.optional_tasks} label="可选任务" tone="muted" />
                <TaskList tasks={shownPayload.out_of_scope_tasks} label="超范围任务" tone="danger" />
                <TaskList tasks={shownPayload.unknown_items} label="待确认" tone="warning" />
              </div>

              {shownPayload.acceptance_criteria.length > 0 && (
                <div className="requirement-acceptance">
                  <h3>验收条件:</h3>
                  <ul>
                    {shownPayload.acceptance_criteria.map((criterion, index) => (
                      <li key={index}>{criterion}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          )}

          {planLoading && (
            <section className="requirement-card requirement-plan-loading">
              <span className="requirement-inline-loading">正在读取任务单…</span>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
