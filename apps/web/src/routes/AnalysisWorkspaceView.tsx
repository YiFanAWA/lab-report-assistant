import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useProject } from "../features/projects/hooks";
import { useDatasets } from "../features/datasets/hooks";
import {
  useAnalysisPlans,
  useGenerateAnalysisPlan,
  useUpdateAnalysisPlan,
  useConfirmAnalysisPlan,
  useRejectAnalysisPlan,
  useCompleteAnalysis,
} from "../features/analysis/hooks";
import { useJob } from "../features/jobs/hooks";
import type {
  AnalysisPlan,
  CleaningPlanItem,
  AnalysisPlanItem,
  ChartPlanItem,
} from "../features/analysis/types";
import type { Dataset } from "../features/datasets/types";

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
    COMPLETED: "已完成",
  };
  return m[s] ?? s;
}

/** 分析方案状态中文映射。 */
function planStatusLabel(s: string) {
  const m: Record<string, string> = {
    CANDIDATE: "候选",
    CONFIRMED: "已确认",
    REJECTED: "已拒绝",
    STALE: "已失效",
  };
  return m[s] ?? s;
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
    FETCH_URL: "采集 URL",
    PARSE_DOCUMENT: "解析文档",
    GENERATE_EVIDENCE: "生成证据卡片",
    PARSE_DATASET: "解析数据集",
    GENERATE_ANALYSIS_PLAN: "生成分析方案",
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

/** 安全解析 JSON 字符串，失败返回 null。 */
function parseJsonSafe<T>(raw: string): T | null {
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

/** 格式化 JSON 字符串用于显示在 textarea 中。 */
function prettyJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

/** 单个分析方案卡片，含编辑、确认、拒绝、STALE 提示。 */
function PlanCard({
  projectId,
  plan,
}: {
  projectId: string;
  plan: AnalysisPlan;
}) {
  const updateMutation = useUpdateAnalysisPlan(projectId);
  const confirmMutation = useConfirmAnalysisPlan(projectId);
  const rejectMutation = useRejectAnalysisPlan(projectId);

  const [isEditing, setIsEditing] = useState(false);
  const [cleaningDraft, setCleaningDraft] = useState("");
  const [analysisDraft, setAnalysisDraft] = useState("");
  const [chartDraft, setChartDraft] = useState("");
  const [editErr, setEditErr] = useState<string | null>(null);

  // 同步编辑态：plan 数据变化时重置
  useEffect(() => {
    setCleaningDraft(prettyJson(plan.cleaning_plan));
    setAnalysisDraft(prettyJson(plan.analysis_plan));
    setChartDraft(prettyJson(plan.chart_plan));
    setIsEditing(false);
    setEditErr(null);
  }, [plan.id, plan.updated_at, plan.cleaning_plan, plan.analysis_plan, plan.chart_plan]);

  const isStale = plan.status === "STALE";
  const canEdit = plan.status === "CANDIDATE" || plan.status === "STALE";
  const canConfirm = plan.status === "CANDIDATE";
  const canReject = plan.status === "CANDIDATE";

  const cleaningItems = parseJsonSafe<CleaningPlanItem[]>(plan.cleaning_plan);
  const analysisItems = parseJsonSafe<AnalysisPlanItem[]>(plan.analysis_plan);
  const chartItems = parseJsonSafe<ChartPlanItem[]>(plan.chart_plan);

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
          方案 [{planStatusLabel(plan.status)}]
          <span style={{ marginLeft: "0.5rem", fontSize: "0.75rem", color: "#6b7280" }}>
            · 来源：{candidateSourceLabel(plan.candidate_source)}
          </span>
        </strong>
        <span style={{ fontSize: "0.75rem", color: "#9ca3af" }}>
          创建：{new Date(plan.created_at).toLocaleString("zh-CN")}
          {plan.confirmed_at &&
            ` · 确认：${new Date(plan.confirmed_at).toLocaleString("zh-CN")}`}
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
          关联数据集已变化，此方案已失效，请重新生成或编辑后确认。
        </div>
      )}

      {!isEditing ? (
        <>
          {/* 清洗方案 */}
          <Section title="清洗方案">
            {cleaningItems && cleaningItems.length > 0 ? (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left" }}>
                      <th style={{ padding: "0.4rem 0.5rem" }}>字段</th>
                      <th style={{ padding: "0.4rem 0.5rem" }}>问题类型</th>
                      <th style={{ padding: "0.4rem 0.5rem" }}>建议动作</th>
                      <th style={{ padding: "0.4rem 0.5rem" }}>理由</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cleaningItems.map((c, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid #f3f4f6" }}>
                        <td style={{ padding: "0.4rem 0.5rem", wordBreak: "break-all" }}>{c.field}</td>
                        <td style={{ padding: "0.4rem 0.5rem" }}>{c.issue_type}</td>
                        <td style={{ padding: "0.4rem 0.5rem" }}>{c.action}</td>
                        <td style={{ padding: "0.4rem 0.5rem", color: "#6b7280" }}>{c.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p style={{ fontSize: "0.8rem", color: "#888" }}>无清洗建议。</p>
            )}
          </Section>

          {/* 分析方案 */}
          <Section title="分析方案">
            {analysisItems && analysisItems.length > 0 ? (
              <ul style={{ margin: 0, paddingLeft: "1.2rem", fontSize: "0.85rem" }}>
                {analysisItems.map((a, i) => (
                  <li key={i} style={{ marginBottom: "0.4rem" }}>
                    <strong>{a.analysis_type}</strong>
                    {a.target_fields.length > 0 && (
                      <span style={{ color: "#6b7280" }}>
                        {" "}（目标字段：{a.target_fields.join(", ")}）
                      </span>
                    )}
                    <div style={{ color: "#374151" }}>方法：{a.method}</div>
                    <div style={{ color: "#6b7280" }}>预期输出：{a.expected_output}</div>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ fontSize: "0.8rem", color: "#888" }}>无分析建议。</p>
            )}
          </Section>

          {/* 图表方案 */}
          <Section title="图表方案">
            {chartItems && chartItems.length > 0 ? (
              <ul style={{ margin: 0, paddingLeft: "1.2rem", fontSize: "0.85rem" }}>
                {chartItems.map((c, i) => (
                  <li key={i} style={{ marginBottom: "0.4rem" }}>
                    <strong>{c.title}</strong>
                    <span style={{ color: "#6b7280" }}> [{c.chart_type}]</span>
                    {c.data_fields.length > 0 && (
                      <span style={{ color: "#6b7280" }}>
                        {" "}（数据字段：{c.data_fields.join(", ")}）
                      </span>
                    )}
                    <div style={{ color: "#6b7280" }}>{c.description}</div>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ fontSize: "0.8rem", color: "#888" }}>无图表建议。</p>
            )}
          </Section>
        </>
      ) : (
        <div
          style={{
            marginTop: "0.5rem",
            padding: "0.5rem",
            background: "#f9fafb",
            borderRadius: "0.25rem",
          }}
        >
          <label style={{ display: "block", fontSize: "0.8rem", marginBottom: "0.25rem" }}>
            清洗方案（JSON）
          </label>
          <textarea
            value={cleaningDraft}
            onChange={(e) => setCleaningDraft(e.target.value)}
            rows={6}
            style={{
              width: "100%",
              padding: "0.4rem",
              boxSizing: "border-box",
              fontSize: "0.8rem",
              fontFamily: "monospace",
            }}
          />
          <label style={{ display: "block", fontSize: "0.8rem", marginBottom: "0.25rem", marginTop: "0.5rem" }}>
            分析方案（JSON）
          </label>
          <textarea
            value={analysisDraft}
            onChange={(e) => setAnalysisDraft(e.target.value)}
            rows={6}
            style={{
              width: "100%",
              padding: "0.4rem",
              boxSizing: "border-box",
              fontSize: "0.8rem",
              fontFamily: "monospace",
            }}
          />
          <label style={{ display: "block", fontSize: "0.8rem", marginBottom: "0.25rem", marginTop: "0.5rem" }}>
            图表方案（JSON）
          </label>
          <textarea
            value={chartDraft}
            onChange={(e) => setChartDraft(e.target.value)}
            rows={6}
            style={{
              width: "100%",
              padding: "0.4rem",
              boxSizing: "border-box",
              fontSize: "0.8rem",
              fontFamily: "monospace",
            }}
          />
        </div>
      )}

      {editErr && (
        <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "#c00" }}>{editErr}</div>
      )}

      <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        {canEdit && (
          <>
            <button
              onClick={() => {
                if (isEditing) {
                  setEditErr(null);
                  // 校验 JSON 格式
                  try {
                    JSON.parse(cleaningDraft);
                    JSON.parse(analysisDraft);
                    JSON.parse(chartDraft);
                  } catch (err) {
                    setEditErr(
                      `JSON 格式错误：${(err as Error).message}`
                    );
                    return;
                  }
                  updateMutation.mutate(
                    {
                      planId: plan.id,
                      payload: {
                        cleaning_plan: cleaningDraft,
                        analysis_plan: analysisDraft,
                        chart_plan: chartDraft,
                      },
                    },
                    {
                      onSuccess: () => setIsEditing(false),
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
                  : "保存修改"
                : "编辑方案"}
            </button>
            {isEditing && (
              <button
                onClick={() => {
                  setCleaningDraft(prettyJson(plan.cleaning_plan));
                  setAnalysisDraft(prettyJson(plan.analysis_plan));
                  setChartDraft(prettyJson(plan.chart_plan));
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
            onClick={() => confirmMutation.mutate(plan.id)}
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
            {confirmMutation.isPending ? "确认中…" : "确认方案"}
          </button>
        )}
        {canReject && (
          <button
            onClick={() => rejectMutation.mutate(plan.id)}
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
            {rejectMutation.isPending ? "拒绝中…" : "拒绝方案"}
          </button>
        )}
      </div>
    </div>
  );
}

/** 区块包装。 */
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginTop: "0.75rem" }}>
      <h4 style={{ margin: "0 0 0.4rem", fontSize: "0.85rem", color: "#374151" }}>
        {title}
      </h4>
      {children}
    </div>
  );
}

/** 单个数据集的"生成分析方案"操作行。 */
function GeneratePlanRow({
  projectId,
  dataset,
  disabled,
  onJobStarted,
}: {
  projectId: string;
  dataset: Dataset;
  disabled: boolean;
  onJobStarted: (jobId: string) => void;
}) {
  const generate = useGenerateAnalysisPlan(projectId);
  const [err, setErr] = useState<string | null>(null);

  return (
    <div
      style={{
        padding: "0.5rem 0.75rem",
        background: "#f9fafb",
        borderRadius: "0.25rem",
        fontSize: "0.85rem",
        marginBottom: "0.5rem",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "0.5rem",
        }}
      >
        <span style={{ wordBreak: "break-all" }}>
          <strong>{dataset.title}</strong>
          <span style={{ color: "#6b7280", marginLeft: "0.5rem" }}>
            [{dataset.status === "READY" ? "已就绪" : dataset.status}]
          </span>
        </span>
        <button
          onClick={() => {
            setErr(null);
            generate.mutate(dataset.id, {
              onSuccess: (data) => onJobStarted(data.job_id),
              onError: (e) => setErr(errorMessage(e, "生成失败")),
            });
          }}
          disabled={disabled || generate.isPending || dataset.status !== "READY"}
          style={{
            padding: "0.25rem 0.6rem",
            fontSize: "0.8rem",
            background: "#0ea5e9",
            color: "#fff",
            border: "none",
            borderRadius: "0.25rem",
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          {generate.isPending ? "提交中…" : "生成方案候选"}
        </button>
      </div>
      {err && (
        <div style={{ marginTop: "0.25rem", color: "#c00", fontSize: "0.8rem" }}>{err}</div>
      )}
    </div>
  );
}

export function AnalysisWorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const pid = projectId!;
  const { data: project, isLoading: projLoading } = useProject(pid);
  const { data: datasets } = useDatasets(pid);

  const [datasetFilter, setDatasetFilter] = useState<string>("");
  const { data: plans, isLoading: plansLoading } = useAnalysisPlans(pid, {
    dataset_id: datasetFilter || undefined,
  });

  const complete = useCompleteAnalysis(pid);

  const [completeErr, setCompleteErr] = useState<string | null>(null);
  const [completeOk, setCompleteOk] = useState<string | null>(null);

  // 跟踪生成任务并轮询
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const { data: genJob } = useJob(pid, activeJobId);
  const prevGenJobStatusRef = useRef<string | undefined>(undefined);
  const qc = useQueryClient();

  useEffect(() => {
    if (!genJob) return;
    const prev = prevGenJobStatusRef.current;
    const curr = genJob.status;
    if (
      prev &&
      prev !== curr &&
      (curr === "SUCCEEDED" || curr === "FAILED" || curr === "CANCELLED")
    ) {
      qc.invalidateQueries({ queryKey: ["analysis", pid, "list"] });
      setActiveJobId(null);
      prevGenJobStatusRef.current = undefined;
    } else {
      prevGenJobStatusRef.current = curr;
    }
  }, [genJob?.status, genJob, qc, pid]);

  if (projLoading) return <p style={{ padding: "2rem" }}>加载中…</p>;
  if (!project) return <p style={{ padding: "2rem", color: "#c00" }}>项目不存在</p>;

  const readyDatasets = (datasets ?? []).filter((d) => d.status === "READY");
  const canComplete = (plans ?? []).some((p) => p.status === "CONFIRMED");

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "1.5rem 1rem" }}>
      <Link to={`/projects/${pid}`} style={{ fontSize: "0.85rem", color: "#2563eb" }}>
        ← 项目详情
      </Link>
      <Link
        to={`/projects/${pid}/datasets`}
        style={{ marginLeft: "1rem", fontSize: "0.85rem", color: "#2563eb" }}
      >
        数据集工作区
      </Link>

      <h1 style={{ fontSize: "1.3rem", marginTop: "0.75rem" }}>
        {project.name}{" "}
        <span style={{ fontSize: "0.8rem", color: "#888" }}>
          [{statusLabel(project.status)}]
        </span>
      </h1>
      <p style={{ fontSize: "0.85rem", color: "#6b7280", marginTop: "0.25rem" }}>
        为已就绪的数据集生成清洗、分析和图表方案候选，可编辑、确认或拒绝。
      </p>

      {/* 生成方案 */}
      <section
        style={{
          marginTop: "1.5rem",
          padding: "1rem",
          border: "1px solid #e5e7eb",
          borderRadius: "0.5rem",
        }}
      >
        <h3 style={{ margin: "0 0 0.5rem" }}>生成分析方案候选</h3>
        {readyDatasets.length === 0 ? (
          <p style={{ fontSize: "0.85rem", color: "#6b7280" }}>
            当前没有已就绪（READY）的数据集。请先在
            <Link
              to={`/projects/${pid}/datasets`}
              style={{ margin: "0 0.25rem", color: "#2563eb" }}
            >
              数据集工作区
            </Link>
            上传文件并完成解析。
          </p>
        ) : (
          <>
            <p style={{ fontSize: "0.85rem", color: "#6b7280", marginBottom: "0.5rem" }}>
              选择一个已就绪的数据集生成方案候选（本地规则提供者）：
            </p>
            {readyDatasets.map((d) => (
              <GeneratePlanRow
                key={d.id}
                projectId={pid}
                dataset={d}
                disabled={!!activeJobId}
                onJobStarted={(jobId) => setActiveJobId(jobId)}
              />
            ))}
            {activeJobId && genJob && (
              <p style={{ fontSize: "0.8rem", color: "#2563eb", marginTop: "0.5rem" }}>
                {jobTypeLabel(genJob.job_type)}：{jobStatusLabel(genJob.status)}
                {(genJob.status === "PENDING" || genJob.status === "RUNNING") && "…"}
              </p>
            )}
          </>
        )}
      </section>

      {/* 数据集筛选 */}
      <section style={{ marginTop: "1.5rem" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            marginBottom: "0.5rem",
          }}
        >
          <h3 style={{ margin: 0 }}>分析方案列表</h3>
          <select
            value={datasetFilter}
            onChange={(e) => setDatasetFilter(e.target.value)}
            style={{ padding: "0.25rem 0.4rem", fontSize: "0.85rem" }}
          >
            <option value="">全部数据集</option>
            {(datasets ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.title}
              </option>
            ))}
          </select>
        </div>
        {plansLoading && (
          <p style={{ fontSize: "0.85rem", color: "#888" }}>加载中…</p>
        )}
        {!plansLoading && (!plans || plans.length === 0) && (
          <p style={{ fontSize: "0.85rem", color: "#888" }}>
            还没有生成任何分析方案。
          </p>
        )}
        {plans && plans.length > 0 && (
          <div>
            {plans.map((p) => (
              <PlanCard key={p.id} projectId={pid} plan={p} />
            ))}
          </div>
        )}
      </section>

      {/* 完成分析方案确认 */}
      <section style={{ marginTop: "1.5rem" }}>
        <button
          onClick={() => {
            setCompleteErr(null);
            setCompleteOk(null);
            complete.mutate(undefined, {
              onSuccess: (data) => {
                setCompleteOk(`项目状态已推进到「${statusLabel(data.status)}」`);
              },
              onError: (e) => setCompleteErr(errorMessage(e, "完成失败")),
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
          {complete.isPending ? "推进中…" : "完成分析方案确认"}
        </button>
        <span style={{ marginLeft: "0.5rem", fontSize: "0.8rem", color: "#6b7280" }}>
          需要至少一个已确认（CONFIRMED）的分析方案
        </span>
        {completeOk && (
          <p style={{ color: "#16a34a", fontSize: "0.85rem", marginTop: "0.5rem" }}>
            {completeOk}
          </p>
        )}
        {completeErr && (
          <p style={{ color: "#c00", fontSize: "0.85rem", marginTop: "0.5rem" }}>
            {completeErr}
          </p>
        )}
      </section>
    </div>
  );
}
