import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useProject, useWorkspaceProjection } from "../features/projects/hooks";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";
import { EmptyState, ErrorPanel, LoadingState } from "../components/workspace/WorkspaceUI";
import { useDatasets } from "../features/datasets/hooks";
import {
  useAnalysisPlans,
  useGenerateAnalysisPlan,
  useStreamGenerateAnalysisPlan,
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

/**
 * 安全拼接 target_fields，容错处理字符串/数组/null/undefined 等情况。
 *
 * 后端 LocalRule provider 在 V2.3.0 之前曾输出 target_fields 为字符串，
 * 已保存的旧错误格式记录可能仍存在于数据库中；同时用户手动编辑 JSON
 * 也可能输入非数组值。PlanCard 不应该因为单个字段类型异常而崩溃整个页面，
 * 这里做防御性容错展示。
 */
function safeJoinTargetFields(fields: unknown): string {
  if (Array.isArray(fields)) {
    return fields.map((f) => String(f)).filter(Boolean).join(", ");
  }
  if (fields == null) return "";
  if (typeof fields === "string") return fields;
  return String(fields);
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

    >
      <div

      >
        <strong >
          方案 [{planStatusLabel(plan.status)}]
          <span >
            · 来源：{candidateSourceLabel(plan.candidate_source)}
          </span>
        </strong>
        <span >
          创建：{new Date(plan.created_at).toLocaleString("zh-CN")}
          {plan.confirmed_at &&
            ` · 确认：${new Date(plan.confirmed_at).toLocaleString("zh-CN")}`}
        </span>
      </div>

      {isStale && (
        <div

        >
          关联数据集已变化，此方案已失效，请重新生成或编辑后确认。
        </div>
      )}

      {!isEditing ? (
        <>
          {/* 清洗方案 */}
          <Section title="清洗方案">
            {cleaningItems && cleaningItems.length > 0 ? (
              <div >
                <table >
                  <thead>
                    <tr >
                      <th >字段</th>
                      <th >问题类型</th>
                      <th >建议动作</th>
                      <th >理由</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cleaningItems.map((c, i) => (
                      <tr key={i} >
                        <td >{c.field}</td>
                        <td >{c.issue_type}</td>
                        <td >{c.action}</td>
                        <td >{c.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p >无清洗建议。</p>
            )}
          </Section>

          {/* 分析方案 */}
          <Section title="分析方案">
            {analysisItems && analysisItems.length > 0 ? (
              <ul >
                {analysisItems.map((a, i) => (
                  <li key={i} >
                    <strong>{a.analysis_type}</strong>
                    {safeJoinTargetFields(a.target_fields) && (
                      <span >
                        {" "}（目标字段：{safeJoinTargetFields(a.target_fields)}）
                      </span>
                    )}
                    <div >方法：{a.method}</div>
                    <div >预期输出：{a.expected_output}</div>
                  </li>
                ))}
              </ul>
            ) : (
              <p >无分析建议。</p>
            )}
          </Section>

          {/* 图表方案 */}
          <Section title="图表方案">
            {chartItems && chartItems.length > 0 ? (
              <ul >
                {chartItems.map((c, i) => (
                  <li key={i} >
                    <strong>{c.title}</strong>
                    <span > [{c.chart_type}]</span>
                    {c.data_fields.length > 0 && (
                      <span >
                        {" "}（数据字段：{c.data_fields.join(", ")}）
                      </span>
                    )}
                    <div >{c.description}</div>
                  </li>
                ))}
              </ul>
            ) : (
              <p >无图表建议。</p>
            )}
          </Section>
        </>
      ) : (
        <div

        >
          <label >
            清洗方案（JSON）
          </label>
          <textarea
            value={cleaningDraft}
            onChange={(e) => setCleaningDraft(e.target.value)}
            rows={6}

          />
          <label >
            分析方案（JSON）
          </label>
          <textarea
            value={analysisDraft}
            onChange={(e) => setAnalysisDraft(e.target.value)}
            rows={6}

          />
          <label >
            图表方案（JSON）
          </label>
          <textarea
            value={chartDraft}
            onChange={(e) => setChartDraft(e.target.value)}
            rows={6}

          />
        </div>
      )}

      {editErr && (
        <div >{editErr}</div>
      )}

      <div >
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

          >
            {confirmMutation.isPending ? "确认中…" : "确认方案"}
          </button>
        )}
        {canReject && (
          <button
            onClick={() => rejectMutation.mutate(plan.id)}
            disabled={rejectMutation.isPending}

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
    <div >
      <h4 >
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
  // SPEC 0021：流式生成分析方案（按数据集独立触发）
  const stream = useStreamGenerateAnalysisPlan(projectId, dataset.id);
  const [err, setErr] = useState<string | null>(null);

  // 任一生成路径进行中时禁用另一路径，避免并发冲突
  const busy = disabled || generate.isPending || stream.streaming;

  return (
    <div

    >
      <div

      >
        <span >
          <strong>{dataset.title}</strong>
          <span >
            [{dataset.status === "READY" ? "已就绪" : dataset.status}]
          </span>
        </span>
        <div >
          <button
            onClick={() => {
              setErr(null);
              generate.mutate(dataset.id, {
                onSuccess: (data) => onJobStarted(data.job_id),
                onError: (e) => setErr(errorMessage(e, "生成失败")),
              });
            }}
            disabled={busy || dataset.status !== "READY"}

          >
            {generate.isPending ? "提交中…" : "生成方案候选"}
          </button>
          {/* SPEC 0021：流式生成按钮 */}
          <button
            onClick={() => {
              setErr(null);
              stream.start();
            }}
            disabled={busy || dataset.status !== "READY"}

          >
            {stream.streaming ? "流式生成中…" : "流式生成"}
          </button>
        </div>
      </div>
      {err && (
        <div >{err}</div>
      )}

      {/* SPEC 0021：流式生成展示区 */}
      {stream.streaming && (
        <div

        >
          <div

          >
            <span >
              正在逐 chunk 生成…
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
        <p >
          流式生成完成 ✓ [{stream.result.candidate_source}
          {stream.result.fallback_used ? "（降级）" : ""}] · plan_id: {stream.result.plan_id}
        </p>
      )}
      {stream.error && (
        <div >
          <p >
            流式生成失败：{stream.error.message}
            {stream.error.partial_text && (
              <span >（已保留部分生成内容）</span>
            )}
          </p>
          {stream.error.partial_text && (
            <details >
              <summary >
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
    </div>
  );
}

export function AnalysisWorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const pid = projectId!;
  const { data: project, isLoading: projLoading } = useProject(pid);
  const { data: projection } = useWorkspaceProjection(pid);
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

  if (projLoading) return <LoadingState />;
  if (!project) return <ErrorPanel message="项目不存在" />;

  const readyDatasets = (datasets ?? []).filter((d) => d.status === "READY");
  const hasConfirmedPlan = (plans ?? []).some((p) => p.status === "CONFIRMED");

  return (
    <WorkspaceShell project={project} projection={projection} title="分析方案工作区">
      <div className="workspace-legacy-page">
      <Link to={`/projects/${pid}`} >
        ← 项目详情
      </Link>
      <Link
        to={`/projects/${pid}/datasets`}

      >
        数据集工作区
      </Link>

      <h1 >
        工作区{" "}
        <span >
          [{projection?.project.status_label ?? project.status}]
        </span>
      </h1>
      <p >
        为已就绪的数据集生成清洗、分析和图表方案候选，可编辑、确认或拒绝。
      </p>

      {/* 生成方案 */}
      <section

      >
        <h3 >生成分析方案候选</h3>
        {readyDatasets.length === 0 ? (
          <p >
            当前没有已就绪（READY）的数据集。请先在
            <Link
              to={`/projects/${pid}/datasets`}

            >
              数据集工作区
            </Link>
            上传文件并完成解析。
          </p>
        ) : (
          <>
            <p >
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
              <p >
                {jobTypeLabel(genJob.job_type)}：{jobStatusLabel(genJob.status)}
                {(genJob.status === "PENDING" || genJob.status === "RUNNING") && "…"}
              </p>
            )}
          </>
        )}
      </section>

      {/* 数据集筛选 */}
      <section >
        <div

        >
          <h3 >分析方案列表</h3>
          <select
            value={datasetFilter}
            onChange={(e) => setDatasetFilter(e.target.value)}

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
          <p >加载中…</p>
        )}
        {!plansLoading && (!plans || plans.length === 0) && (
          <EmptyState title="还没有生成任何分析方案。" description="先准备可用数据集，再生成分析方案候选。" />
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
      <section >
        <button
          onClick={() => {
            setCompleteErr(null);
            setCompleteOk("项目状态已推进，请返回项目总览确认最新阶段。");
            complete.mutate(undefined, {
              onSuccess: (data) => {
                setCompleteOk("项目状态已推进，请返回项目总览确认最新阶段。");
              },
              onError: (e) => setCompleteErr(errorMessage(e, "完成失败")),
            });
          }}
          disabled={!hasConfirmedPlan || complete.isPending}

        >
          {complete.isPending ? "推进中…" : "完成分析方案确认"}
        </button>
        <span >
          需要至少一个已确认（CONFIRMED）的分析方案
        </span>
        {completeOk && (
          <p >
            {completeOk}
          </p>
        )}
        {completeErr && (
          <p >
            {completeErr}
          </p>
        )}
      </section>
    </div>
    </WorkspaceShell>
  );
}
