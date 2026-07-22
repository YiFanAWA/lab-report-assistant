import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useProject } from "../features/projects/hooks";
import { useAnalysisPlans } from "../features/analysis/hooks";
import {
  useCodeTasks,
  useGenerateCodeTask,
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

/** 项目状态展示中文映射。 */
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
    PENDING: "排队中",
    RUNNING: "执行中",
    SUCCEEDED: "已成功",
    FAILED: "失败",
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
    PENDING: "排队中",
    RUNNING: "执行中",
    SUCCEEDED: "已完成",
    FAILED: "失败",
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
      <div style={{ marginTop: "0.4rem" }}>
        <span style={{ fontSize: "0.75rem", color: "#9ca3af" }}>
          {label}：（空）
        </span>
      </div>
    );
  }

  const lineCount = text.split("\n").length;
  const previewLines = text.split("\n").slice(0, 5).join("\n");

  return (
    <div style={{ marginTop: "0.4rem" }}>
      <button
        onClick={() => setCollapsed(!collapsed)}
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          fontSize: "0.75rem",
          color,
          padding: 0,
        }}
      >
        {collapsed ? "▸" : "▾"} {label}（{lineCount} 行）
      </button>
      <pre
        style={{
          marginTop: "0.25rem",
          padding: "0.5rem",
          background: color === "#16a34a" ? "#f0fdf4" : "#fef2f2",
          border: `1px solid ${color === "#16a34a" ? "#bbf7d0" : "#fecaca"}`,
          borderRadius: "0.25rem",
          fontSize: "0.75rem",
          fontFamily: "monospace",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          maxHeight: collapsed ? "6rem" : "24rem",
          overflow: "auto",
          margin: 0,
        }}
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
      style={{
        padding: "0.75rem",
        border: `1px solid ${isStale ? "#fcd34d" : "#e5e7eb"}`,
        borderRadius: "0.5rem",
        marginBottom: "0.5rem",
        background: isStale ? "#fffbeb" : "#fff",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          gap: "0.5rem",
          flexWrap: "wrap",
        }}
      >
        <strong style={{ fontSize: "0.9rem" }}>
          代码任务 v{task.code_version} [{codeTaskStatusLabel(task.status)}]
          <span style={{ marginLeft: "0.5rem", fontSize: "0.75rem", color: "#6b7280" }}>
            · 来源：{candidateSourceLabel(task.candidate_source)}
          </span>
        </strong>
        <span style={{ fontSize: "0.75rem", color: "#9ca3af" }}>
          创建：{new Date(task.created_at).toLocaleString("zh-CN")}
          {task.confirmed_at &&
            ` · 确认：${new Date(task.confirmed_at).toLocaleString("zh-CN")}`}
        </span>
      </div>

      {isStale && (
        <div
          style={{
            marginTop: "0.5rem",
            padding: "0.4rem 0.5rem",
            background: "#fef3c7",
            borderRadius: "0.25rem",
            fontSize: "0.8rem",
            color: "#92400e",
          }}
        >
          关联的数据集或分析方案已变化，此代码任务已失效，请重新生成或编辑后确认。
        </div>
      )}

      {/* 代码编辑器 */}
      <div style={{ marginTop: "0.5rem" }}>
        {!isEditing ? (
          <pre
            style={{
              padding: "0.5rem",
              background: "#1e293b",
              color: "#e2e8f0",
              borderRadius: "0.25rem",
              fontSize: "0.78rem",
              fontFamily: "monospace",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              maxHeight: "20rem",
              overflow: "auto",
              margin: 0,
            }}
          >
            {task.code}
          </pre>
        ) : (
          <textarea
            value={codeDraft}
            onChange={(e) => setCodeDraft(e.target.value)}
            rows={16}
            spellCheck={false}
            style={{
              width: "100%",
              padding: "0.5rem",
              boxSizing: "border-box",
              fontSize: "0.78rem",
              fontFamily: "monospace",
              background: "#1e293b",
              color: "#e2e8f0",
              border: "1px solid #475569",
              borderRadius: "0.25rem",
              resize: "vertical",
              minHeight: "12rem",
            }}
          />
        )}
      </div>

      {editErr && (
        <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "#c00" }}>
          {editErr}
        </div>
      )}

      {/* 操作按钮 */}
      <div
        style={{
          marginTop: "0.5rem",
          display: "flex",
          gap: "0.5rem",
          flexWrap: "wrap",
        }}
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
              style={{
                padding: "0.25rem 0.6rem",
                fontSize: "0.8rem",
                background: "#e0e7ff",
                color: "#3730a3",
                border: "1px solid #c7d2fe",
                borderRadius: "0.25rem",
                cursor: "pointer",
              }}
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
                style={{
                  padding: "0.25rem 0.6rem",
                  fontSize: "0.8rem",
                  background: "#f3f4f6",
                  color: "#374151",
                  border: "1px solid #e5e7eb",
                  borderRadius: "0.25rem",
                  cursor: "pointer",
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
            style={{
              padding: "0.25rem 0.6rem",
              fontSize: "0.8rem",
              background: "#16a34a",
              color: "#fff",
              border: "none",
              borderRadius: "0.25rem",
              cursor: "pointer",
            }}
          >
            {confirmMutation.isPending ? "确认中…" : "确认代码"}
          </button>
        )}
        {canReject && (
          <button
            onClick={() => rejectMutation.mutate(task.id)}
            disabled={rejectMutation.isPending}
            style={{
              padding: "0.25rem 0.6rem",
              fontSize: "0.8rem",
              background: "#fee2e2",
              color: "#b91c1c",
              border: "1px solid #fecaca",
              borderRadius: "0.25rem",
              cursor: "pointer",
            }}
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
            style={{
              padding: "0.25rem 0.6rem",
              fontSize: "0.8rem",
              background: "#0ea5e9",
              color: "#fff",
              border: "none",
              borderRadius: "0.25rem",
              cursor: "pointer",
            }}
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
          style={{
            fontSize: "0.8rem",
            color: "#2563eb",
            marginTop: "0.5rem",
          }}
        >
          {jobTypeLabel(execJob.job_type)}：{jobStatusLabel(execJob.status)}
          {(execJob.status === "PENDING" || execJob.status === "RUNNING") &&
            "…"}
        </p>
      )}
      {execOk && (
        <p style={{ color: "#16a34a", fontSize: "0.8rem", marginTop: "0.5rem" }}>
          {execOk}
        </p>
      )}
      {execErr && (
        <p style={{ color: "#c00", fontSize: "0.8rem", marginTop: "0.5rem" }}>
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
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: "0.5rem",
        flexWrap: "wrap",
        padding: "0.4rem 0.5rem",
        background: "#f9fafb",
        borderRadius: "0.25rem",
        marginBottom: "0.3rem",
      }}
    >
      <div style={{ fontSize: "0.8rem" }}>
        <span
          style={{
            fontSize: "0.7rem",
            color: "#fff",
            background:
              artifact.artifact_type === "CHART_PNG" ? "#7c3aed" : "#0ea5e9",
            padding: "0.1rem 0.4rem",
            borderRadius: "0.25rem",
            marginRight: "0.5rem",
          }}
        >
          {artifactTypeLabel(artifact.artifact_type)}
        </span>
        <span style={{ wordBreak: "break-all" }}>{artifact.name}</span>
        <span style={{ marginLeft: "0.5rem", color: "#9ca3af" }}>
          ({formatFileSize(artifact.file_size_bytes)})
        </span>
      </div>
      <a
        href={buildArtifactDownloadUrl(projectId, runId, artifact.id)}
        style={{
          padding: "0.2rem 0.5rem",
          fontSize: "0.75rem",
          background: "#16a34a",
          color: "#fff",
          border: "none",
          borderRadius: "0.25rem",
          textDecoration: "none",
          cursor: "pointer",
        }}
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
      style={{
        padding: "0.75rem",
        border: `1px solid ${
          isFailed ? "#fecaca" : isStale ? "#fcd34d" : "#e5e7eb"
        }`,
        borderRadius: "0.5rem",
        marginBottom: "0.5rem",
        background: isStale ? "#fffbeb" : "#fff",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          gap: "0.5rem",
          flexWrap: "wrap",
        }}
      >
        <strong style={{ fontSize: "0.9rem" }}>
          执行记录 #{run.code_version} [{runStatusLabel(run.status)}]
          <span style={{ marginLeft: "0.5rem", fontSize: "0.75rem", color: "#6b7280" }}>
            {run.exit_code !== null && ` · exit=${run.exit_code}`}
            {run.duration_seconds !== null &&
              ` · 耗时 ${run.duration_seconds.toFixed(1)}s`}
          </span>
        </strong>
        <span style={{ fontSize: "0.75rem", color: "#9ca3af" }}>
          {run.started_at
            ? `开始：${new Date(run.started_at).toLocaleString("zh-CN")}`
            : "未开始"}
          {run.finished_at &&
            ` · 结束：${new Date(run.finished_at).toLocaleString("zh-CN")}`}
        </span>
      </div>

      {isStale && (
        <div
          style={{
            marginTop: "0.5rem",
            padding: "0.4rem 0.5rem",
            background: "#fef3c7",
            borderRadius: "0.25rem",
            fontSize: "0.8rem",
            color: "#92400e",
          }}
        >
          关联的代码已重新执行，此执行记录已失效。
        </div>
      )}

      {isRunning && (
        <div
          style={{
            marginTop: "0.5rem",
            padding: "0.4rem 0.5rem",
            background: "#eff6ff",
            borderRadius: "0.25rem",
            fontSize: "0.8rem",
            color: "#1e40af",
          }}
        >
          代码正在受控环境中执行，请稍候…（页面每 3 秒自动刷新）
        </div>
      )}

      {/* 失败错误信息 */}
      {isFailed && (
        <div
          style={{
            marginTop: "0.5rem",
            padding: "0.5rem",
            background: "#fee2e2",
            borderRadius: "0.25rem",
            fontSize: "0.8rem",
            color: "#b91c1c",
          }}
        >
          <strong>执行失败：</strong>
          {run.error_code}
          {run.error_message && ` — ${run.error_message}`}
          <div style={{ marginTop: "0.25rem", fontSize: "0.75rem" }}>
            请检查下方 stderr 输出，修正代码后重新触发执行。
          </div>
        </div>
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
        <div style={{ marginTop: "0.5rem" }}>
          <h4
            style={{
              margin: "0 0 0.3rem",
              fontSize: "0.8rem",
              color: "#374151",
            }}
          >
            执行产物（{run.artifacts.length} 个）
          </h4>
          {run.artifacts.length === 0 ? (
            <p style={{ fontSize: "0.8rem", color: "#888" }}>
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
  const { data: analysisPlans } = useAnalysisPlans(pid);
  const { data: codeTasks, isLoading: codeTasksLoading } = useCodeTasks(pid);
  const { data: executionRuns, isLoading: runsLoading } = useExecutionRuns(pid);

  const generate = useGenerateCodeTask(pid);
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

  if (projLoading) return <p style={{ padding: "2rem" }}>加载中…</p>;
  if (!project)
    return <p style={{ padding: "2rem", color: "#c00" }}>项目不存在</p>;

  const canGenerate = project.status === "ANALYSIS_CONFIRMED";
  // 已确认的分析方案，用于生成代码候选
  const confirmedPlans = (analysisPlans ?? []).filter(
    (p) => p.status === "CONFIRMED"
  );
  // 判断是否可完成结果确认：至少一个 SUCCEEDED 执行记录
  const hasSucceededRun = (executionRuns ?? []).some(
    (r) => r.status === "SUCCEEDED"
  );
  const canComplete =
    hasSucceededRun &&
    project.status !== "RESULT_CONFIRMED" &&
    project.status !== "COMPLETED";

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "1.5rem 1rem" }}>
      <Link
        to={`/projects/${pid}`}
        style={{ fontSize: "0.85rem", color: "#2563eb" }}
      >
        ← 项目详情
      </Link>
      <Link
        to={`/projects/${pid}/analysis`}
        style={{ marginLeft: "1rem", fontSize: "0.85rem", color: "#2563eb" }}
      >
        分析方案工作区
      </Link>
      <Link
        to={`/projects/${pid}/outline`}
        style={{ marginLeft: "1rem", fontSize: "0.85rem", color: "#2563eb" }}
      >
        大纲工作区
      </Link>

      <h1 style={{ fontSize: "1.3rem", marginTop: "0.75rem" }}>
        {project.name}{" "}
        <span style={{ fontSize: "0.8rem", color: "#888" }}>
          [{statusLabel(project.status)}]
        </span>
      </h1>
      <p
        style={{
          fontSize: "0.85rem",
          color: "#6b7280",
          marginTop: "0.25rem",
        }}
      >
        为已确认的分析方案生成 Python 代码候选，在受控环境中执行，
        生成表格和图表产物。确认结果后可进入大纲工作区。
      </p>

      {/* Section 1: 代码任务 */}
      <section style={{ marginTop: "1.5rem" }}>
        <h3 style={{ margin: "0 0 0.5rem" }}>代码任务</h3>

        {/* 生成代码候选 */}
        <div
          style={{
            padding: "1rem",
            border: "1px solid #e5e7eb",
            borderRadius: "0.5rem",
            marginBottom: "1rem",
          }}
        >
          <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.9rem" }}>
            生成代码候选
          </h4>
          {!canGenerate ? (
            <p style={{ fontSize: "0.85rem", color: "#6b7280" }}>
              项目当前状态为「{statusLabel(project.status)}」，
              需要先在分析方案工作区完成确认（推进到 ANALYSIS_CONFIRMED）才能生成代码。
            </p>
          ) : confirmedPlans.length === 0 ? (
            <p style={{ fontSize: "0.85rem", color: "#6b7280" }}>
              当前没有已确认的分析方案，请先在
              <Link
                to={`/projects/${pid}/analysis`}
                style={{ margin: "0 0.25rem", color: "#2563eb" }}
              >
                分析方案工作区
              </Link>
              确认一个方案。
            </p>
          ) : (
            <>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "#6b7280",
                  marginBottom: "0.5rem",
                }}
              >
                选择一个已确认的分析方案，生成 Python 代码候选：
              </p>
              <div
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  alignItems: "center",
                  flexWrap: "wrap",
                }}
              >
                <select
                  value={selectedPlanId}
                  onChange={(e) => setSelectedPlanId(e.target.value)}
                  style={{
                    padding: "0.4rem",
                    fontSize: "0.85rem",
                    minWidth: "16rem",
                  }}
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
                    !!genJobId
                  }
                  style={{
                    padding: "0.4rem 0.8rem",
                    fontSize: "0.85rem",
                    background: "#0ea5e9",
                    color: "#fff",
                    border: "none",
                    borderRadius: "0.375rem",
                    cursor: "pointer",
                  }}
                >
                  {generate.isPending || genJobId
                    ? "生成中…"
                    : "生成代码候选"}
                </button>
              </div>
              {genJobId && genJob && (
                <p
                  style={{
                    fontSize: "0.8rem",
                    color: "#2563eb",
                    marginTop: "0.5rem",
                  }}
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
                  style={{
                    color: "#c00",
                    fontSize: "0.85rem",
                    marginTop: "0.5rem",
                  }}
                >
                  {genErr}
                </p>
              )}
            </>
          )}
        </div>

        {/* 代码任务列表 */}
        {codeTasksLoading && (
          <p style={{ fontSize: "0.85rem", color: "#888" }}>加载中…</p>
        )}
        {!codeTasksLoading && (!codeTasks || codeTasks.length === 0) && (
          <p style={{ fontSize: "0.85rem", color: "#888" }}>
            还没有生成任何代码任务。
          </p>
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
      <section style={{ marginTop: "2rem" }}>
        <h3 style={{ margin: "0 0 0.5rem" }}>执行记录</h3>
        <p style={{ fontSize: "0.8rem", color: "#9ca3af", marginBottom: "0.5rem" }}>
          执行记录每 3 秒自动刷新状态。
        </p>
        {runsLoading && (
          <p style={{ fontSize: "0.85rem", color: "#888" }}>加载中…</p>
        )}
        {!runsLoading && (!executionRuns || executionRuns.length === 0) && (
          <p style={{ fontSize: "0.85rem", color: "#888" }}>
            还没有执行记录。确认代码任务后点击「触发执行」。
          </p>
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
      <section style={{ marginTop: "2rem" }}>
        <button
          onClick={() => {
            setCompleteErr(null);
            setCompleteOk(null);
            complete.mutate(undefined, {
              onSuccess: (data) => {
                setCompleteOk(
                  `项目状态已推进到「${statusLabel(data.status)}」`
                );
              },
              onError: (e) =>
                setCompleteErr(errorMessage(e, "完成失败")),
            });
          }}
          disabled={!canComplete || complete.isPending}
          style={{
            padding: "0.5rem 1rem",
            background: canComplete ? "#16a34a" : "#e5e7eb",
            color: canComplete ? "#fff" : "#9ca3af",
            border: "none",
            borderRadius: "0.375rem",
            cursor: canComplete ? "pointer" : "not-allowed",
          }}
        >
          {complete.isPending ? "推进中…" : "完成结果确认"}
        </button>
        <span
          style={{
            marginLeft: "0.5rem",
            fontSize: "0.8rem",
            color: "#6b7280",
          }}
        >
          需要至少一个已成功（SUCCEEDED）的执行记录
        </span>
        {completeOk && (
          <p
            style={{
              color: "#16a34a",
              fontSize: "0.85rem",
              marginTop: "0.5rem",
            }}
          >
            {completeOk}
          </p>
        )}
        {completeErr && (
          <p
            style={{
              color: "#c00",
              fontSize: "0.85rem",
              marginTop: "0.5rem",
            }}
          >
            {completeErr}
          </p>
        )}
      </section>
    </div>
  );
}
