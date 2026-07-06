import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useProject } from "../features/projects/hooks";
import { useSources } from "../features/sources/hooks";
import {
  useEvidenceCards,
  useGenerateEvidence,
  useUpdateEvidence,
  useConfirmEvidence,
  useRejectEvidence,
  useCompleteEvidence,
} from "../features/evidence/hooks";
import { useJob } from "../features/jobs/hooks";
import type { EvidenceCard, EvidenceType } from "../features/evidence/types";
import type { Source } from "../features/sources/types";

/** 项目状态展示中文映射。 */
function statusLabel(s: string) {
  const m: Record<string, string> = {
    DRAFT: "草稿",
    REQUIREMENT_PARSED: "要求已解析",
    REQUIREMENT_CONFIRMED: "需求已确认",
    SOURCES_COLLECTED: "来源已收集",
    EVIDENCE_CONFIRMED: "证据已确认",
    COMPLETED: "已完成",
  };
  return m[s] ?? s;
}

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
    PENDING: "待处理",
    FETCHED: "已采集",
    PARSED: "已解析",
    FAILED: "失败",
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

  // 当卡片数据变化时同步编辑态
  useEffect(() => {
    setSummary(card.summary);
    setEvidenceType(card.evidence_type);
    setLocator(card.locator);
    setSourceQuote(card.source_quote ?? "");
    setIsEditing(false);
    setEditErr(null);
  }, [card.id, card.updated_at]);

  const isStale = card.status === "STALE";
  const canEdit = card.status === "CANDIDATE" || card.status === "STALE";
  const canConfirm = card.status === "CANDIDATE";
  const canReject = card.status === "CANDIDATE";

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
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "0.5rem" }}>
        <strong style={{ fontSize: "0.85rem" }}>
          [{evidenceTypeLabel(card.evidence_type)}] {card.locator}
        </strong>
        <span style={{ fontSize: "0.75rem", color: "#6b7280", whiteSpace: "nowrap" }}>
          [{cardStatusLabel(card.status)}]
          {card.candidate_source === "LOCAL_RULE" && " · 本地规则"}
          {card.candidate_source === "MODEL" && " · 模型"}
        </span>
      </div>
      {!isEditing ? (
        <div style={{ marginTop: "0.5rem", fontSize: "0.9rem", color: "#1f2937", whiteSpace: "pre-wrap" }}>
          {card.summary}
        </div>
      ) : (
        <div style={{ marginTop: "0.5rem", padding: "0.5rem", background: "#f9fafb", borderRadius: "0.25rem" }}>
          <label style={{ display: "block", fontSize: "0.8rem", marginBottom: "0.25rem" }}>摘要</label>
          <textarea
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            rows={3}
            style={{ width: "100%", padding: "0.4rem", boxSizing: "border-box", fontSize: "0.85rem" }}
          />
          <label style={{ display: "block", fontSize: "0.8rem", marginBottom: "0.25rem", marginTop: "0.5rem" }}>证据类型</label>
          <select
            value={evidenceType}
            onChange={(e) => setEvidenceType(e.target.value as EvidenceType)}
            style={{ width: "100%", padding: "0.4rem", boxSizing: "border-box", fontSize: "0.85rem" }}
          >
            {ALL_EVIDENCE_TYPES.map((t) => (
              <option key={t} value={t}>
                {evidenceTypeLabel(t)}（{t}）
              </option>
            ))}
          </select>
          <label style={{ display: "block", fontSize: "0.8rem", marginBottom: "0.25rem", marginTop: "0.5rem" }}>来源位置</label>
          <input
            value={locator}
            onChange={(e) => setLocator(e.target.value)}
            style={{ width: "100%", padding: "0.4rem", boxSizing: "border-box", fontSize: "0.85rem" }}
          />
          <label style={{ display: "block", fontSize: "0.8rem", marginBottom: "0.25rem", marginTop: "0.5rem" }}>原文摘录（可选）</label>
          <textarea
            value={sourceQuote}
            onChange={(e) => setSourceQuote(e.target.value)}
            rows={2}
            style={{ width: "100%", padding: "0.4rem", boxSizing: "border-box", fontSize: "0.85rem" }}
          />
        </div>
      )}
      {card.source_quote && !isEditing && (
        <div style={{ marginTop: "0.25rem", fontSize: "0.8rem", color: "#6b7280", fontStyle: "italic" }}>
          原文：{card.source_quote}
        </div>
      )}
      <div style={{ fontSize: "0.75rem", color: "#9ca3af", marginTop: "0.25rem" }}>
        来源 ID：{card.source_id}
        {card.confirmed_at && ` · 确认于 ${new Date(card.confirmed_at).toLocaleString("zh-CN")}`}
      </div>
      {isStale && (
        <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "#92400e" }}>
          原始来源已变化，此卡片已失效，请重新评估或编辑后确认。
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
            onClick={() => confirmMutation.mutate(card.id)}
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
            {confirmMutation.isPending ? "确认中…" : "确认"}
          </button>
        )}
        {canReject && (
          <button
            onClick={() => rejectMutation.mutate(card.id)}
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

  if (projLoading) return <p style={{ padding: "2rem" }}>加载中…</p>;
  if (!project) return <p style={{ padding: "2rem", color: "#c00" }}>项目不存在</p>;

  const parsedSources = (sources ?? []).filter((s) => s.status === "PARSED");

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "1.5rem 1rem" }}>
      <Link to={`/projects/${pid}`} style={{ fontSize: "0.85rem", color: "#2563eb" }}>
        ← 项目详情
      </Link>
      <Link
        to={`/projects/${pid}/sources`}
        style={{ marginLeft: "1rem", fontSize: "0.85rem", color: "#2563eb" }}
      >
        资料来源工作区
      </Link>

      <h1 style={{ fontSize: "1.3rem", marginTop: "0.75rem" }}>
        {project.name}{" "}
        <span style={{ fontSize: "0.8rem", color: "#888" }}>[{statusLabel(project.status)}]</span>
      </h1>
      <p style={{ fontSize: "0.85rem", color: "#6b7280", marginTop: "0.25rem" }}>
        从已解析的来源生成证据卡片候选，可编辑、确认或拒绝。
      </p>

      {/* 生成证据卡片 */}
      <section
        style={{
          marginTop: "1.5rem",
          padding: "1rem",
          border: "1px solid #e5e7eb",
          borderRadius: "0.5rem",
        }}
      >
        <h3 style={{ margin: "0 0 0.5rem" }}>生成证据卡片候选</h3>
        {parsedSources.length === 0 ? (
          <p style={{ fontSize: "0.85rem", color: "#6b7280" }}>
            当前没有已解析的来源。请先在
            <Link to={`/projects/${pid}/sources`} style={{ margin: "0 0.25rem", color: "#2563eb" }}>
              资料来源工作区
            </Link>
            登记来源并等待解析完成。
          </p>
        ) : (
          <>
            <p style={{ fontSize: "0.85rem", color: "#6b7280", marginBottom: "0.5rem" }}>
              可对以下已解析来源生成证据卡片候选（本地规则提供者）：
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
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
          <p style={{ color: "#16a34a", fontSize: "0.85rem", marginTop: "0.5rem" }}>{genOk}</p>
        )}
        {genErr && (
          <p style={{ color: "#c00", fontSize: "0.85rem", marginTop: "0.5rem" }}>{genErr}</p>
        )}
      </section>

      {/* 状态筛选 */}
      <section style={{ marginTop: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
          <h3 style={{ margin: 0 }}>证据卡片</h3>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: "0.25rem 0.4rem", fontSize: "0.85rem" }}
          >
            {STATUS_FILTERS.map((s) => (
              <option key={s} value={s}>
                {s === "" ? "全部状态" : cardStatusLabel(s)}
              </option>
            ))}
          </select>
        </div>
        {cardsLoading && <p style={{ fontSize: "0.85rem", color: "#888" }}>加载中…</p>}
        {!cardsLoading && (!cards || cards.length === 0) && (
          <p style={{ fontSize: "0.85rem", color: "#888" }}>没有匹配的证据卡片。</p>
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
          disabled={complete.isPending}
          style={{
            padding: "0.5rem 1rem",
            background: "#16a34a",
            color: "#fff",
            border: "none",
            borderRadius: "0.375rem",
            cursor: "pointer",
          }}
        >
          {complete.isPending ? "推进中…" : "完成证据确认"}
        </button>
        <span style={{ marginLeft: "0.5rem", fontSize: "0.8rem", color: "#6b7280" }}>
          需要至少一张已确认（CONFIRMED）的证据卡片
        </span>
        {completeOk && (
          <p style={{ color: "#16a34a", fontSize: "0.85rem", marginTop: "0.5rem" }}>{completeOk}</p>
        )}
        {completeErr && (
          <p style={{ color: "#c00", fontSize: "0.85rem", marginTop: "0.5rem" }}>{completeErr}</p>
        )}
      </section>
    </div>
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
  const [err, setErr] = useState<string | null>(null);

  return (
    <div
      style={{
        padding: "0.5rem 0.75rem",
        background: "#f9fafb",
        borderRadius: "0.25rem",
        fontSize: "0.85rem",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem" }}>
        <span style={{ wordBreak: "break-all" }}>
          <strong>{source.title}</strong>
          <span style={{ color: "#6b7280", marginLeft: "0.5rem" }}>
            [{sourceStatusLabel(source.status)}]
          </span>
        </span>
        <button
          onClick={() => {
            setErr(null);
            generate.mutate(source.id, {
              onSuccess: (data) => onJobStarted(data.job_id),
              onError: (e) => setErr(errorMessage(e, "生成失败")),
            });
          }}
          disabled={disabled || generate.isPending}
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
          {generate.isPending ? "提交中…" : "生成候选"}
        </button>
      </div>
      {err && (
        <div style={{ marginTop: "0.25rem", color: "#c00", fontSize: "0.8rem" }}>{err}</div>
      )}
    </div>
  );
}
