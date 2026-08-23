import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useProject, useWorkspaceProjection } from "../features/projects/hooks";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";
import { EmptyState, ErrorPanel, LoadingState } from "../components/workspace/WorkspaceUI";
import { useSources } from "../features/sources/hooks";
import {
  useEvidenceCards,
  useGenerateEvidence,
  useStreamGenerateEvidence,
  useUpdateEvidence,
  useConfirmEvidence,
  useRejectEvidence,
  useCompleteEvidence,
} from "../features/evidence/hooks";
import { useJob } from "../features/jobs/hooks";
import type { EvidenceCard, EvidenceType } from "../features/evidence/types";
import type { Source } from "../features/sources/types";

/** 证据卡片状态中文映射。 */
function cardStatusLabel(s: string) {
  const m: Record<string, string> = {
    CANDIDATE: "候选",
    CONFIRMED: "已确认",
    REJECTED: "已拒绝",
    STALE: "已失效",
  };
  return m[s] ?? s;
}

/** 证据类型中文映射。 */
function evidenceTypeLabel(t: string) {
  const m: Record<string, string> = {
    BACKGROUND: "背景",
    METHOD: "方法",
    RESULT: "结果",
    CONCLUSION: "结论",
    LIMITATION: "局限性",
    REFERENCE: "参考",
  };
  return m[t] ?? t;
}

/** 来源状态中文映射（用于判断来源状态）。 */
function sourceStatusLabel(s: string) {
  const m: Record<string, string> = {
    PENDING: "等待处理",
    FETCHED: "已采集",
    PARSED: "已解析",
    FAILED: "需要处理",
    DELETED: "已删除",
  };
  return m[s] ?? s;
}

function errorMessage(e: unknown, fallback: string) {
  if (typeof e === "object" && e !== null && "message" in e) {
    const msg = (e as { message?: unknown }).message;
    if (typeof msg === "string" && msg.trim()) return msg;
  }
  return fallback;
}

const ALL_EVIDENCE_TYPES: EvidenceType[] = [
  "BACKGROUND",
  "METHOD",
  "RESULT",
  "CONCLUSION",
  "LIMITATION",
  "REFERENCE",
];

const STATUS_FILTERS = ["", "CANDIDATE", "CONFIRMED", "REJECTED", "STALE"] as const;

/** 证据卡片项，集成生成任务轮询。 */
function EvidenceCardItem({
  projectId,
  card,
}: {
  projectId: string;
  card: EvidenceCard;
}) {
  const qc = useQueryClient();
  const updateMutation = useUpdateEvidence(projectId);
  const confirmMutation = useConfirmEvidence(projectId);
  const rejectMutation = useRejectEvidence(projectId);

  const [isEditing, setIsEditing] = useState(false);
  const [summary, setSummary] = useState(card.summary);
  const [evidenceType, setEvidenceType] = useState<EvidenceType>(card.evidence_type);
  const [locator, setLocator] = useState(card.locator);
  const [sourceQuote, setSourceQuote] = useState(card.source_quote ?? "");
  const [editErr, setEditErr] = useState<string | null>(null);
  const [editOk, setEditOk] = useState<string | null>(null);

  // 当卡片数据变化时同步编辑态
  useEffect(() => {
    setSummary(card.summary);
    setEvidenceType(card.evidence_type);
    setLocator(card.locator);
    setSourceQuote(card.source_quote ?? "");
    setIsEditing(false);
    setEditErr(null);
    setEditOk(null);
  }, [card.id, card.updated_at]);

  const isStale = card.status === "STALE";
  const canEdit = card.status === "CANDIDATE" || card.status === "STALE";
  const canConfirm = card.status === "CANDIDATE";
  const canReject = card.status === "CANDIDATE";

  return (
    <div

    >
      <div >
        <strong >
          [{evidenceTypeLabel(card.evidence_type)}] {card.locator}
        </strong>
        <span >
          [{cardStatusLabel(card.status)}]
          {card.candidate_source === "LOCAL_RULE" && " · 本地规则"}
          {card.candidate_source === "MODEL" && " · 模型"}
        </span>
      </div>
      {!isEditing ? (
        <div >
          {card.summary}
        </div>
      ) : (
        <div >
          <label >摘要</label>
          <textarea
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            rows={3}

          />
          <label >证据类型</label>
          <select
            value={evidenceType}
            onChange={(e) => setEvidenceType(e.target.value as EvidenceType)}

          >
            {ALL_EVIDENCE_TYPES.map((t) => (
              <option key={t} value={t}>
                {evidenceTypeLabel(t)}（{t}）
              </option>
            ))}
          </select>
          <label >来源位置</label>
          <input
            value={locator}
            onChange={(e) => setLocator(e.target.value)}

          />
          <label >原文摘录（可选）</label>
          <textarea
            value={sourceQuote}
            onChange={(e) => setSourceQuote(e.target.value)}
            rows={2}

          />
        </div>
      )}
      {card.source_quote && !isEditing && (
        <div >
          原文：{card.source_quote}
        </div>
      )}
      <div >
        来源 ID：{card.source_id}
        {card.confirmed_at && ` · 确认于 ${new Date(card.confirmed_at).toLocaleString("zh-CN")}`}
      </div>
      {isStale && (
        <div >
          原始来源已变化，此卡片已失效，请重新评估或编辑后确认。
        </div>
      )}
      {editErr && (
        <div >{editErr}</div>
      )}
      {editOk && (
        <div >{editOk}</div>
      )}
      <div >
        {canEdit && (
          <>
            <button
              onClick={() => {
                if (isEditing) {
                  setEditErr(null);
                  setEditOk(null);
                  updateMutation.mutate(
                    {
                      cardId: card.id,
                      payload: {
                        summary: summary.trim(),
                        evidence_type: evidenceType,
                        locator: locator.trim(),
                        source_quote: sourceQuote.trim() || null,
                      },
                    },
                    {
                      onSuccess: () => {
                        setIsEditing(false);
                        setEditOk("已保存 ✓");
                        setTimeout(() => setEditOk(null), 1_500);
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
                  : "保存修改"
                : "编辑卡片"}
            </button>
            {isEditing && (
              <button
                onClick={() => {
                  setSummary(card.summary);
                  setEvidenceType(card.evidence_type);
                  setLocator(card.locator);
                  setSourceQuote(card.source_quote ?? "");
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
            onClick={() => confirmMutation.mutate(card.id)}
            disabled={confirmMutation.isPending}

          >
            {confirmMutation.isPending ? "确认中…" : "确认"}
          </button>
        )}
        {canReject && (
          <button
            onClick={() => rejectMutation.mutate(card.id)}
            disabled={rejectMutation.isPending}

          >
            {rejectMutation.isPending ? "拒绝中…" : "拒绝"}
          </button>
        )}
      </div>
    </div>
  );
}

export function EvidenceWorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const pid = projectId!;
  const { data: project, isLoading: projLoading } = useProject(pid);
  const { data: projection } = useWorkspaceProjection(pid);
  const { data: sources } = useSources(pid);

  const [statusFilter, setStatusFilter] = useState<string>("");
  const { data: cards, isLoading: cardsLoading } = useEvidenceCards(pid, {
    status: statusFilter || undefined,
  });

  const generate = useGenerateEvidence(pid);
  const complete = useCompleteEvidence(pid);

  const [genErr, setGenErr] = useState<string | null>(null);
  const [genOk, setGenOk] = useState<string | null>(null);
  const [completeErr, setCompleteErr] = useState<string | null>(null);
  const [completeOk, setCompleteOk] = useState<string | null>(null);

  // 跟踪生成任务并轮询：useGenerateEvidence 返回 job_id 后启用轮询
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const { data: genJob } = useJob(pid, activeJobId);
  const prevGenJobStatusRef = useRef<string | undefined>(undefined);
  const qc = useQueryClient();

  useEffect(() => {
    if (!genJob) return;
    const prev = prevGenJobStatusRef.current;
    const curr = genJob.status;
    if (prev && prev !== curr && (curr === "SUCCEEDED" || curr === "FAILED" || curr === "CANCELLED")) {
      // 任务完成后刷新证据卡片列表
      qc.invalidateQueries({ queryKey: ["evidence", pid, "list"] });
      if (curr === "SUCCEEDED") {
        setGenOk("证据卡片候选已生成");
      } else {
        const msg = genJob.error_message ?? "生成失败";
        setGenErr(`${msg}（${genJob.error_code ?? "UNKNOWN"}）`);
      }
      setActiveJobId(null);
      prevGenJobStatusRef.current = undefined;
    } else {
      prevGenJobStatusRef.current = curr;
    }
  }, [genJob?.status, genJob, qc, pid]);

  if (projLoading) return <LoadingState />;
  if (!project) return <ErrorPanel message="项目不存在" />;

  const parsedSources = (sources ?? []).filter((s) => s.status === "PARSED");

  return (
    <WorkspaceShell project={project} projection={projection} title="证据卡片工作区">
      <div className="workspace-legacy-page">
      <Link to={`/projects/${pid}`} >
        ← 项目详情
      </Link>
      <Link
        to={`/projects/${pid}/sources`}

      >
        资料来源工作区
      </Link>

      <h1 >
        工作区{" "}
        <span >[{projection?.project.status_label ?? project.status}]</span>
      </h1>
      <p >
        从已解析的来源生成证据卡片候选，可编辑、确认或拒绝。
      </p>

      {/* 生成证据卡片 */}
      <section

      >
        <h3 >生成证据卡片候选</h3>
        {parsedSources.length === 0 ? (
          <p >
            当前没有已解析的来源。请先在
            <Link to={`/projects/${pid}/sources`} >
              资料来源工作区
            </Link>
            登记来源并等待解析完成。
          </p>
        ) : (
          <>
            <p >
              可对以下已解析来源生成证据卡片候选（本地规则提供者）：
            </p>
            <div >
              {parsedSources.map((s) => (
                <GenerateEvidenceRow
                  key={s.id}
                  projectId={pid}
                  source={s}
                  disabled={generate.isPending || !!activeJobId}
                  onJobStarted={(jobId) => {
                    setActiveJobId(jobId);
                    setGenErr(null);
                    setGenOk(null);
                  }}
                />
              ))}
            </div>
          </>
        )}
        {genOk && (
          <p >{genOk}</p>
        )}
        {genErr && (
          <p >{genErr}</p>
        )}
      </section>

      {/* 状态筛选 */}
      <section >
        <div >
          <h3 >证据卡片</h3>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}

          >
            {STATUS_FILTERS.map((s) => (
              <option key={s} value={s}>
                {s === "" ? "全部状态" : cardStatusLabel(s)}
              </option>
            ))}
          </select>
        </div>
        {cardsLoading && <p >加载中…</p>}
        {!cardsLoading && (!cards || cards.length === 0) && (
          <EmptyState title="没有匹配的证据卡片。" description="先生成或确认资料来源的证据卡片。" />
        )}
        {cards && cards.length > 0 && (
          <div>
            {cards.map((c) => (
              <EvidenceCardItem key={c.id} projectId={pid} card={c} />
            ))}
          </div>
        )}
      </section>

      {/* 完成证据确认 */}
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
          disabled={complete.isPending}

        >
          {complete.isPending ? "推进中…" : "完成证据确认"}
        </button>
        <span >
          需要至少一张已确认（CONFIRMED）的证据卡片
        </span>
        {completeOk && (
          <p >{completeOk}</p>
        )}
        {completeErr && (
          <p >{completeErr}</p>
        )}
      </section>
    </div>
    </WorkspaceShell>
  );
}

/** 单个来源的"生成证据卡片"操作行。 */
function GenerateEvidenceRow({
  projectId,
  source,
  disabled,
  onJobStarted,
}: {
  projectId: string;
  source: Source;
  disabled: boolean;
  onJobStarted: (jobId: string) => void;
}) {
  const generate = useGenerateEvidence(projectId);
  // SPEC 0020：流式生成证据卡片（按来源独立触发）
  const stream = useStreamGenerateEvidence(projectId, source.id);
  const [err, setErr] = useState<string | null>(null);

  // 任一生成路径进行中时禁用另一路径，避免并发冲突
  const busy = disabled || generate.isPending || stream.streaming;

  return (
    <div

    >
      <div >
        <span >
          <strong>{source.title}</strong>
          <span >
            [{sourceStatusLabel(source.status)}]
          </span>
        </span>
        <div >
          <button
            onClick={() => {
              setErr(null);
              generate.mutate(source.id, {
                onSuccess: (data) => onJobStarted(data.job_id),
                onError: (e) => setErr(errorMessage(e, "生成失败")),
              });
            }}
            disabled={busy}

          >
            {generate.isPending ? "提交中…" : "生成候选"}
          </button>
          {/* SPEC 0020：流式生成按钮 */}
          <button
            onClick={() => {
              setErr(null);
              stream.start();
            }}
            disabled={busy}

          >
            {stream.streaming ? "流式生成中…" : "流式生成"}
          </button>
        </div>
      </div>
      {err && (
        <div >{err}</div>
      )}

      {/* SPEC 0020：流式生成展示区 */}
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
          {stream.result.fallback_used ? "（降级）" : ""}] · 共 {stream.result.card_count} 张卡片
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
