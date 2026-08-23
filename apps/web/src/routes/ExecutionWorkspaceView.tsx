import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useProject, useWorkspaceProjection } from "../features/projects/hooks";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";
import { EmptyState, ErrorPanel, LoadingState } from "../components/workspace/WorkspaceUI";
import { useAnalysisPlans } from "../features/analysis/hooks";
import {
  useCodeTasks,
  useGenerateCodeTask,
  useStreamGenerateCodeTask,
  useUpdateCodeTask,
  useConfirmCodeTask,
  useRejectCodeTask,
  useExecuteCodeTask,
  useExecutionRuns,
  useCompleteExecution,
} from "../features/execution/hooks";
import { buildArtifactDownloadUrl } from "../features/execution/api";
import { useJob } from "../features/jobs/hooks";
import type {
  CodeTask,
  ExecutionRun,
  ExecutionArtifact,
} from "../features/execution/types";

/** 代码任务状态中文映射。 */
function codeTaskStatusLabel(s: string) {
  const m: Record<string, string> = {
    CANDIDATE: "候选",
    CONFIRMED: "已确认",
    REJECTED: "已拒绝",
    STALE: "已失效",
  };
  return m[s] ?? s;
}

/** 执行记录状态中文映射。 */
function runStatusLabel(s: string) {
  const m: Record<string, string> = {
    PENDING: "等待处理",
    RUNNING: "正在处理",
    SUCCEEDED: "已完成",
    FAILED: "需要处理",
    STALE: "已失效",
  };
  return m[s] ?? s;
}

/** 产物类型中文映射。 */
function artifactTypeLabel(t: string) {
  const m: Record<string, string> = {
    TABLE_CSV: "表格 CSV",
    CHART_PNG: "图表 PNG",
  };
  return m[t] ?? t;
}

/** 候选来源中文映射。 */
function candidateSourceLabel(s: string) {
  const m: Record<string, string> = {
    MODEL: "模型",
    LOCAL_RULE: "本地规则",
    MANUAL: "手动",
  };
  return m[s] ?? s;
}

/** 任务类型中文映射。 */
function jobTypeLabel(t: string) {
  const m: Record<string, string> = {
    GENERATE_CODE_TASK: "生成代码",
    EXECUTE_CODE_TASK: "执行代码",
  };
  return m[t] ?? t;
}

/** 任务状态中文映射。 */
function jobStatusLabel(s: string) {
  const m: Record<string, string> = {
    PENDING: "等待处理",
    RUNNING: "正在处理",
    SUCCEEDED: "已完成",
    FAILED: "需要处理",
    CANCELLED: "已取消",
  };
  return m[s] ?? s;
}

/** 从 unknown 错误中提取后端结构化 message。 */
function errorMessage(e: unknown, fallback: string) {
  if (typeof e === "object" && e !== null && "message" in e) {
    const msg = (e as { message?: unknown }).message;
    if (typeof msg === "string" && msg.trim()) return msg;
  }
  return fallback;
}

/** 格式化文件大小。 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

/** 可折叠文本块（用于 stdout/stderr 展示）。 */
function CollapsibleText({
  label,
  text,
  color,
  defaultCollapsed = true,
}: {
  label: string;
  text: string;
  color: string;
  defaultCollapsed?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const isEmpty = !text || text.trim() === "";

  if (isEmpty) {
    return (
      <div >
        <span >
          {label}：（空）
        </span>
      </div>
    );
  }

  const lineCount = text.split("\n").length;
  const previewLines = text.split("\n").slice(0, 5).join("\n");

  return (
    <div >
      <button
        onClick={() => setCollapsed(!collapsed)}

      >
        {collapsed ? "▸" : "▾"} {label}（{lineCount} 行）
      </button>
      <pre

      >
        {collapsed ? previewLines + (lineCount > 5 ? "\n…" : "") : text}
      </pre>
    </div>
  );
}

/** 代码任务卡片，含代码编辑器、确认/拒绝、触发执行。 */
function CodeTaskCard({
  projectId,
  task,
}: {
  projectId: string;
  task: CodeTask;
}) {
  const updateMutation = useUpdateCodeTask(projectId);
  const confirmMutation = useConfirmCodeTask(projectId);
  const rejectMutation = useRejectCodeTask(projectId);
  const executeMutation = useExecuteCodeTask(projectId);

  const [isEditing, setIsEditing] = useState(false);
  const [codeDraft, setCodeDraft] = useState(task.code);
  const [editErr, setEditErr] = useState<string | null>(null);
  const [execErr, setExecErr] = useState<string | null>(null);
  const [execOk, setExecOk] = useState<string | null>(null);

  // 跟踪执行任务状态
  const [execJobId, setExecJobId] = useState<string | null>(null);
  const { data: execJob } = useJob(projectId, execJobId);
  const prevExecStatusRef = useRef<string | undefined>(undefined);
  const qc = useQueryClient();

  // 同步编辑态
  useEffect(() => {
    setCodeDraft(task.code);
    setIsEditing(false);
    setEditErr(null);
  }, [task.id, task.updated_at, task.code]);

  // 执行任务完成时刷新
  useEffect(() => {
    if (!execJob) return;
    const prev = prevExecStatusRef.current;
    const curr = execJob.status;
    if (
      prev &&
      prev !== curr &&
      (curr === "SUCCEEDED" || curr === "FAILED" || curr === "CANCELLED")
    ) {
      qc.invalidateQueries({ queryKey: ["execution-runs", projectId, "list"] });
      setExecJobId(null);
      prevExecStatusRef.current = undefined;
      if (curr === "SUCCEEDED") {
        setExecOk("代码执行已完成，请在下方查看执行结果。");
      } else {
        setExecErr(`代码执行任务${jobStatusLabel(curr)}`);
      }
    } else {
      prevExecStatusRef.current = curr;
    }
  }, [execJob?.status, execJob, qc, projectId]);

  const isStale = task.status === "STALE";
  const isCandidate = task.status === "CANDIDATE";
  const isConfirmed = task.status === "CONFIRMED";
  const canEdit = isCandidate || isStale;
  const canConfirm = isCandidate;
  const canReject = isCandidate;
  const canExecute = isConfirmed;

  return (
    <div

    >
      <div

      >
        <strong >
          代码任务 v{task.code_version} [{codeTaskStatusLabel(task.status)}]
          <span >
            · 来源：{candidateSourceLabel(task.candidate_source)}
          </span>
        </strong>
        <span >
          创建：{new Date(task.created_at).toLocaleString("zh-CN")}
          {task.confirmed_at &&
            ` · 确认：${new Date(task.confirmed_at).toLocaleString("zh-CN")}`}
        </span>
      </div>

      {isStale && (
        <div

        >
          关联的数据集或分析方案已变化，此代码任务已失效，请重新生成或编辑后确认。
        </div>
      )}

      {/* 代码编辑器 */}
      <div >
        {!isEditing ? (
          <pre

          >
            {task.code}
          </pre>
        ) : (
          <textarea
            value={codeDraft}
            onChange={(e) => setCodeDraft(e.target.value)}
            rows={16}
            spellCheck={false}

          />
        )}
      </div>

      {editErr && (
        <div >
          {editErr}
        </div>
      )}

      {/* 操作按钮 */}
      <div

      >
        {canEdit && (
          <>
            <button
              onClick={() => {
                if (isEditing) {
                  setEditErr(null);
                  if (!codeDraft.trim()) {
                    setEditErr("代码不能为空");
                    return;
                  }
                  updateMutation.mutate(
                    {
                      taskId: task.id,
                      payload: { code: codeDraft },
                    },
                    {
                      onSuccess: () => {
                        setIsEditing(false);
                        setEditErr(null);
                      },
                      onError: (e) => setEditErr(errorMessage(e, "保存失败")),
                    }
                  );
                } else {
                  setIsEditing(true);
                }
              }}
              disabled={updateMutation.isPending}

            >
              {isEditing
                ? updateMutation.isPending
                  ? "保存中…"
                  : "保存代码"
                : "编辑代码"}
            </button>
            {isEditing && (
              <button
                onClick={() => {
                  setCodeDraft(task.code);
                  setIsEditing(false);
                  setEditErr(null);
                }}

              >
                取消
              </button>
            )}
          </>
        )}
        {canConfirm && (
          <button
            onClick={() => confirmMutation.mutate(task.id)}
            disabled={confirmMutation.isPending}

          >
            {confirmMutation.isPending ? "确认中…" : "确认代码"}
          </button>
        )}
        {canReject && (
          <button
            onClick={() => rejectMutation.mutate(task.id)}
            disabled={rejectMutation.isPending}

          >
            {rejectMutation.isPending ? "拒绝中…" : "拒绝代码"}
          </button>
        )}
        {canExecute && (
          <button
            onClick={() => {
              setExecErr(null);
              setExecOk(null);
              executeMutation.mutate(task.id, {
                onSuccess: (data) => {
                  setExecJobId(data.job_id);
                },
                onError: (e) => setExecErr(errorMessage(e, "触发执行失败")),
              });
            }}
            disabled={executeMutation.isPending || !!execJobId}

          >
            {executeMutation.isPending
              ? "提交中…"
              : execJobId
              ? "执行中…"
              : "触发执行"}
          </button>
        )}
      </div>

      {/* 执行任务状态 */}
      {execJobId && execJob && (
        <p

        >
          {jobTypeLabel(execJob.job_type)}：{jobStatusLabel(execJob.status)}
          {(execJob.status === "PENDING" || execJob.status === "RUNNING") &&
            "…"}
        </p>
      )}
      {execOk && (
        <p >
          {execOk}
        </p>
      )}
      {execErr && (
        <p >
          {execErr}
        </p>
      )}
    </div>
  );
}

/** 单个执行产物行。 */
function ArtifactRow({
  projectId,
  runId,
  artifact,
}: {
  projectId: string;
  runId: string;
  artifact: ExecutionArtifact;
}) {
  return (
    <div

    >
      <div >
        <span

        >
          {artifactTypeLabel(artifact.artifact_type)}
        </span>
        <span >{artifact.name}</span>
        <span >
          ({formatFileSize(artifact.file_size_bytes)})
        </span>
      </div>
      <a
        href={buildArtifactDownloadUrl(projectId, runId, artifact.id)}

      >
        下载
      </a>
    </div>
  );
}

/** 单个执行记录卡片，含 stdout/stderr/产物下载。 */
function ExecutionRunCard({
  projectId,
  run,
}: {
  projectId: string;
  run: ExecutionRun;
}) {
  const isStale = run.status === "STALE";
  const isFailed = run.status === "FAILED";
  const isSucceeded = run.status === "SUCCEEDED";
  const isRunning = run.status === "RUNNING" || run.status === "PENDING";

  return (
    <div

    >
      <div

      >
        <strong >
          执行记录 #{run.code_version} [{runStatusLabel(run.status)}]
          <span >
            {run.exit_code !== null && ` · exit=${run.exit_code}`}
            {run.duration_seconds !== null &&
              ` · 耗时 ${run.duration_seconds.toFixed(1)}s`}
          </span>
        </strong>
        <span >
          {run.started_at
            ? `开始：${new Date(run.started_at).toLocaleString("zh-CN")}`
            : "未开始"}
          {run.finished_at &&
            ` · 结束：${new Date(run.finished_at).toLocaleString("zh-CN")}`}
        </span>
      </div>

      {isStale && (
        <div

        >
          关联的代码已重新执行，此执行记录已失效。
        </div>
      )}

      {isRunning && (
        <div

        >
          代码正在受控环境中执行，请稍候…（页面每 3 秒自动刷新）
        </div>
      )}

      {/* 失败错误信息 */}
      {isFailed && (
        <ErrorPanel
          className="workspace-inline-error"
          message={run.error_message ?? "执行失败，请检查下方 stderr 输出，修正代码后重新触发执行。"}
          code={run.error_code}
        />
      )}

      {/* stdout / stderr */}
      <CollapsibleText
        label="stdout"
        text={run.stdout}
        color="#16a34a"
        defaultCollapsed={isSucceeded}
      />
      <CollapsibleText
        label="stderr"
        text={run.stderr}
        color="#c00"
        defaultCollapsed={isSucceeded}
      />

      {/* 产物列表 */}
      {isSucceeded && (
        <div >
          <h4

          >
            执行产物（{run.artifacts.length} 个）
          </h4>
          {run.artifacts.length === 0 ? (
            <p >
              本次执行未生成产物文件。
            </p>
          ) : (
            run.artifacts.map((a) => (
              <ArtifactRow
                key={a.id}
                projectId={projectId}
                runId={run.id}
                artifact={a}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

export function ExecutionWorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const pid = projectId!;
  const { data: project, isLoading: projLoading } = useProject(pid);
  const { data: projection } = useWorkspaceProjection(pid);
  const { data: analysisPlans } = useAnalysisPlans(pid);
  const { data: codeTasks, isLoading: codeTasksLoading } = useCodeTasks(pid);
  const { data: executionRuns, isLoading: runsLoading } = useExecutionRuns(pid);

  const generate = useGenerateCodeTask(pid);
  const stream = useStreamGenerateCodeTask(pid);
  const complete = useCompleteExecution(pid);

  // 跟踪生成代码任务
  const [genJobId, setGenJobId] = useState<string | null>(null);
  const { data: genJob } = useJob(pid, genJobId);
  const prevGenStatusRef = useRef<string | undefined>(undefined);
  const qc = useQueryClient();

  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [genErr, setGenErr] = useState<string | null>(null);
  const [completeErr, setCompleteErr] = useState<string | null>(null);
  const [completeOk, setCompleteOk] = useState<string | null>(null);

  // 生成代码任务完成时刷新
  useEffect(() => {
    if (!genJob) return;
    const prev = prevGenStatusRef.current;
    const curr = genJob.status;
    if (
      prev &&
      prev !== curr &&
      (curr === "SUCCEEDED" || curr === "FAILED" || curr === "CANCELLED")
    ) {
      qc.invalidateQueries({ queryKey: ["code-tasks", pid, "list"] });
      setGenJobId(null);
      prevGenStatusRef.current = undefined;
      if (curr === "FAILED") {
        setGenErr("生成代码任务失败");
      }
    } else {
      prevGenStatusRef.current = curr;
    }
  }, [genJob?.status, genJob, qc, pid]);

  if (projLoading) return <LoadingState />;
  if (!project) return <ErrorPanel message="项目不存在" />;

    const executionStep = projection?.phases
    .flatMap((phase) => phase.steps)
    .find((step) => step.id === "execution");
  const executionStepOpen = executionStep?.is_open === true;
  // 已确认的分析方案，用于生成代码候选
  const confirmedPlans = (analysisPlans ?? []).filter(
    (p) => p.status === "CONFIRMED"
  );
  // 判断是否可完成结果确认：至少一个 SUCCEEDED 执行记录
  const hasSucceededRun = (executionRuns ?? []).some(
    (r) => r.status === "SUCCEEDED"
  );


  return (
    <WorkspaceShell project={project} projection={projection} title="结果执行工作区">
      <div className="workspace-legacy-page">
      <Link
        to={`/projects/${pid}`}

      >
        ← 项目详情
      </Link>
      <Link
        to={`/projects/${pid}/analysis`}

      >
        分析方案工作区
      </Link>
      <Link
        to={`/projects/${pid}/outline`}

      >
        大纲工作区
      </Link>

      <h1 >
        工作区{" "}
        <span >
          [{projection?.project.status_label ?? project.status}]
        </span>
      </h1>
      <p

      >
        为已确认的分析方案生成 Python 代码候选，在受控环境中执行，
        生成表格和图表产物。确认结果后可进入大纲工作区。
      </p>

      {/* Section 1: 代码任务 */}
      <section >
        <h3 >代码任务</h3>

        {/* 生成代码候选 */}
        <div

        >
          <h4 >
            生成代码候选
          </h4>
          {!executionStepOpen ? (
            <p >
              当前执行工作区尚未开放，请按阶段进度完成前置工作后再继续。
            </p>
          ) : confirmedPlans.length === 0 ? (
            <p >
              当前没有已确认的分析方案，请先在
              <Link
                to={`/projects/${pid}/analysis`}

              >
                分析方案工作区
              </Link>
              确认一个方案。
            </p>
          ) : (
            <>
              <p

              >
                选择一个已确认的分析方案，生成 Python 代码候选：
              </p>
              <div

              >
                <select
                  value={selectedPlanId}
                  onChange={(e) => setSelectedPlanId(e.target.value)}

                >
                  <option value="">— 选择分析方案 —</option>
                  {confirmedPlans.map((p) => (
                    <option key={p.id} value={p.id}>
                      方案（数据集 {p.dataset_id.slice(-8)}）
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => {
                    setGenErr(null);
                    if (!selectedPlanId) {
                      setGenErr("请先选择一个分析方案");
                      return;
                    }
                    generate.mutate(selectedPlanId, {
                      onSuccess: (data) => setGenJobId(data.job_id),
                      onError: (e) =>
                        setGenErr(errorMessage(e, "触发生成失败")),
                    });
                  }}
                  disabled={
                    !selectedPlanId ||
                    generate.isPending ||
                    !!genJobId ||
                    stream.streaming
                  }

                >
                  {generate.isPending || genJobId
                    ? "生成中…"
                    : "生成代码候选"}
                </button>
                {/* SPEC 0022：流式生成按钮（方案 A：流式展示原始 JSON，完成后解析展示代码） */}
                <button
                  onClick={() => {
                    setGenErr(null);
                    if (!selectedPlanId) {
                      setGenErr("请先选择一个分析方案");
                      return;
                    }
                    stream.start(selectedPlanId);
                  }}
                  disabled={
                    !selectedPlanId ||
                    stream.streaming ||
                    generate.isPending ||
                    !!genJobId
                  }

                >
                  {stream.streaming ? "流式生成中…" : "流式生成"}
                </button>
              </div>
              {genJobId && genJob && (
                <p

                >
                  {jobTypeLabel(genJob.job_type)}：
                  {jobStatusLabel(genJob.status)}
                  {(genJob.status === "PENDING" ||
                    genJob.status === "RUNNING") &&
                    "…"}
                </p>
              )}
              {genErr && (
                <p

                >
                  {genErr}
                </p>
              )}

              {/* SPEC 0022：流式生成展示区（方案 A） */}
              {stream.streaming && (
                <div

                >
                  <div

                  >
                    <span >
                      正在逐 chunk 生成（原始 JSON 输出）…
                    </span>
                    <button
                      onClick={stream.cancel}

                    >
                      取消
                    </button>
                  </div>
                  <pre

                  >
                    {stream.chunks}
                  </pre>
                </div>
              )}
              {stream.result && (
                <p

                >
                  流式生成完成 ✓ [{stream.result.candidate_source}
                  {stream.result.fallback_used ? "（降级）" : ""}] · code_task_id:{" "}
                  {stream.result.code_task_id}
                </p>
              )}
              {stream.error && (
                <div

                >
                  <p >
                    流式生成失败：{stream.error.message}
                    {stream.error.partial_text && (
                      <span >
                        （已保留部分生成内容）
                      </span>
                    )}
                  </p>
                  {stream.error.partial_text && (
                    <details >
                      <summary

                      >
                        查看已生成内容
                      </summary>
                      <pre

                      >
                        {stream.error.partial_text}
                      </pre>
                    </details>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* 代码任务列表 */}
        {codeTasksLoading && (
          <p >加载中…</p>
        )}
        {!codeTasksLoading && (!codeTasks || codeTasks.length === 0) && (
          <EmptyState title="还没有生成任何代码任务。" description="先确认分析方案，再生成受控执行代码。" />
        )}
        {codeTasks && codeTasks.length > 0 && (
          <div>
            {codeTasks.map((t) => (
              <CodeTaskCard key={t.id} projectId={pid} task={t} />
            ))}
          </div>
        )}
      </section>

      {/* Section 2: 执行记录 */}
      <section >
        <h3 >执行记录</h3>
        <p >
          执行记录每 3 秒自动刷新状态。
        </p>
        {runsLoading && (
          <p >加载中…</p>
        )}
        {!runsLoading && (!executionRuns || executionRuns.length === 0) && (
          <EmptyState title="还没有执行记录。" description="确认代码任务后点击「触发执行」。" />
        )}
        {executionRuns && executionRuns.length > 0 && (
          <div>
            {executionRuns.map((r) => (
              <ExecutionRunCard key={r.id} projectId={pid} run={r} />
            ))}
          </div>
        )}
      </section>

      {/* 完成结果确认 */}
      <section >
        <button
          onClick={() => {
            setCompleteErr(null);
            setCompleteOk("项目状态已推进，请返回项目总览确认最新阶段。");
            complete.mutate(undefined, {
              onSuccess: (data) => {
                setCompleteOk("项目状态已推进，请返回项目总览确认最新阶段。");
              },
              onError: (e) =>
                setCompleteErr(errorMessage(e, "完成失败")),
            });
          }}
          disabled={!hasSucceededRun || complete.isPending}

        >
          {complete.isPending ? "推进中…" : "完成结果确认"}
        </button>
        <span

        >
          需要至少一个已成功（SUCCEEDED）的执行记录
        </span>
        {completeOk && (
          <p

          >
            {completeOk}
          </p>
        )}
        {completeErr && (
          <p

          >
            {completeErr}
          </p>
        )}
      </section>
    </div>
    </WorkspaceShell>
  );
}
