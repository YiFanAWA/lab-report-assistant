import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useProject } from "../features/projects/hooks";
import {
  useOutlines,
  useGenerateOutline,
  useUpdateOutline,
  useConfirmOutline,
  useRejectOutline,
  useGenerateWord,
  useGeneratePpt,
} from "../features/outlines/hooks";
import { useJob } from "../features/jobs/hooks";
import type { Outline, OutlineSection } from "../features/outlines/types";

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

/** 大纲状态中文映射。 */
function outlineStatusLabel(s: string) {
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

/** 章节来源类型中文映射。 */
function sourceTypeLabel(s: string) {
  const m: Record<string, string> = {
    REQUIREMENT: "实验要求",
    EVIDENCE: "证据卡片",
    DATASET: "数据集",
    ANALYSIS: "分析方案",
    EXECUTION: "执行结果",
    SUMMARY: "综合总结",
  };
  return m[s] ?? s;
}

/** 任务类型中文映射。 */
function jobTypeLabel(t: string) {
  const m: Record<string, string> = {
    GENERATE_OUTLINE: "生成大纲",
    GENERATE_WORD: "生成 Word",
    GENERATE_PPT: "生成 PPT",
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

/** 单个大纲卡片，含编辑、确认、拒绝、Word/PPT 生成、STALE 提示。 */
function OutlineCard({
  projectId,
  outline,
}: {
  projectId: string;
  outline: Outline;
}) {
  const updateMutation = useUpdateOutline(projectId);
  const confirmMutation = useConfirmOutline(projectId);
  const rejectMutation = useRejectOutline(projectId);
  const wordMutation = useGenerateWord(projectId);
  const pptMutation = useGeneratePpt(projectId);

  const [isEditing, setIsEditing] = useState(false);
  const [sectionsDraft, setSectionsDraft] = useState<OutlineSection[]>([]);
  const [editErr, setEditErr] = useState<string | null>(null);
  const [wordErr, setWordErr] = useState<string | null>(null);
  const [pptErr, setPptErr] = useState<string | null>(null);
  const [wordOk, setWordOk] = useState<string | null>(null);
  const [pptOk, setPptOk] = useState<string | null>(null);

  // 跟踪 Word/PPT 生成任务
  const [wordJobId, setWordJobId] = useState<string | null>(null);
  const [pptJobId, setPptJobId] = useState<string | null>(null);
  const { data: wordJob } = useJob(projectId, wordJobId);
  const { data: pptJob } = useJob(projectId, pptJobId);
  const prevWordStatusRef = useRef<string | undefined>(undefined);
  const prevPptStatusRef = useRef<string | undefined>(undefined);
  const qc = useQueryClient();

  // 同步编辑态
  useEffect(() => {
    setSectionsDraft(outline.sections.map((s) => ({ ...s })));
    setIsEditing(false);
    setEditErr(null);
  }, [outline.id, outline.updated_at, outline.sections]);

  // Word 生成任务完成时刷新
  useEffect(() => {
    if (!wordJob) return;
    const prev = prevWordStatusRef.current;
    const curr = wordJob.status;
    if (
      prev &&
      prev !== curr &&
      (curr === "SUCCEEDED" || curr === "FAILED" || curr === "CANCELLED")
    ) {
      qc.invalidateQueries({ queryKey: ["deliverables", projectId, "list"] });
      qc.invalidateQueries({ queryKey: ["project", projectId] });
      setWordJobId(null);
      prevWordStatusRef.current = undefined;
      if (curr === "SUCCEEDED") {
        setWordOk("Word 交付物已生成，可在交付物工作区查看和下载。");
      } else {
        setWordErr(`Word 生成任务${jobStatusLabel(curr)}`);
      }
    } else {
      prevWordStatusRef.current = curr;
    }
  }, [wordJob?.status, wordJob, qc, projectId]);

  // PPT 生成任务完成时刷新
  useEffect(() => {
    if (!pptJob) return;
    const prev = prevPptStatusRef.current;
    const curr = pptJob.status;
    if (
      prev &&
      prev !== curr &&
      (curr === "SUCCEEDED" || curr === "FAILED" || curr === "CANCELLED")
    ) {
      qc.invalidateQueries({ queryKey: ["deliverables", projectId, "list"] });
      qc.invalidateQueries({ queryKey: ["project", projectId] });
      setPptJobId(null);
      prevPptStatusRef.current = undefined;
      if (curr === "SUCCEEDED") {
        setPptOk("PPT 交付物已生成，可在交付物工作区查看和下载。");
      } else {
        setPptErr(`PPT 生成任务${jobStatusLabel(curr)}`);
      }
    } else {
      prevPptStatusRef.current = curr;
    }
  }, [pptJob?.status, pptJob, qc, projectId]);

  const isStale = outline.status === "STALE";
  const isCandidate = outline.status === "CANDIDATE";
  const isConfirmed = outline.status === "CONFIRMED";
  const canEdit = isCandidate || isStale;
  const canConfirm = isCandidate;
  const canReject = isCandidate;
  const canGenerate = isConfirmed;

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
          大纲 v{outline.version} [{outlineStatusLabel(outline.status)}]
          <span style={{ marginLeft: "0.5rem", fontSize: "0.75rem", color: "#6b7280" }}>
            · 来源：{candidateSourceLabel(outline.candidate_source)}
          </span>
        </strong>
        <span style={{ fontSize: "0.75rem", color: "#9ca3af" }}>
          创建：{new Date(outline.created_at).toLocaleString("zh-CN")}
          {outline.confirmed_at &&
            ` · 确认：${new Date(outline.confirmed_at).toLocaleString("zh-CN")}`}
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
          关联执行结果已变化，此大纲已失效，请重新生成或编辑后确认。
        </div>
      )}

      {/* 章节列表 */}
      <div style={{ marginTop: "0.5rem" }}>
        {!isEditing ? (
          outline.sections.map((sec, i) => (
            <SectionView key={sec.id ?? i} section={sec} />
          ))
        ) : (
          <div
            style={{
              padding: "0.5rem",
              background: "#f9fafb",
              borderRadius: "0.25rem",
            }}
          >
            {sectionsDraft.map((sec, i) => (
              <div key={sec.id ?? i} style={{ marginBottom: "0.75rem" }}>
                <input
                  value={sec.title}
                  onChange={(e) => {
                    const next = [...sectionsDraft];
                    next[i] = { ...sec, title: e.target.value };
                    setSectionsDraft(next);
                  }}
                  placeholder="章节标题"
                  style={{
                    width: "100%",
                    padding: "0.4rem",
                    boxSizing: "border-box",
                    fontSize: "0.85rem",
                    marginBottom: "0.25rem",
                  }}
                />
                <select
                  value={sec.source_type}
                  onChange={(e) => {
                    const next = [...sectionsDraft];
                    next[i] = { ...sec, source_type: e.target.value };
                    setSectionsDraft(next);
                  }}
                  style={{
                    padding: "0.25rem 0.4rem",
                    fontSize: "0.8rem",
                    marginBottom: "0.25rem",
                  }}
                >
                  {[
                    "REQUIREMENT",
                    "EVIDENCE",
                    "DATASET",
                    "ANALYSIS",
                    "EXECUTION",
                    "SUMMARY",
                  ].map((t) => (
                    <option key={t} value={t}>
                      {sourceTypeLabel(t)}
                    </option>
                  ))}
                </select>
                <textarea
                  value={sec.content}
                  onChange={(e) => {
                    const next = [...sectionsDraft];
                    next[i] = { ...sec, content: e.target.value };
                    setSectionsDraft(next);
                  }}
                  rows={4}
                  placeholder="章节内容"
                  style={{
                    width: "100%",
                    padding: "0.4rem",
                    boxSizing: "border-box",
                    fontSize: "0.8rem",
                  }}
                />
                <input
                  value={sec.source_ids.join(", ")}
                  onChange={(e) => {
                    const next = [...sectionsDraft];
                    next[i] = {
                      ...sec,
                      source_ids: e.target.value
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean),
                    };
                    setSectionsDraft(next);
                  }}
                  placeholder="来源 ID 列表（逗号分隔）"
                  style={{
                    width: "100%",
                    padding: "0.4rem",
                    boxSizing: "border-box",
                    fontSize: "0.75rem",
                    color: "#6b7280",
                  }}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {editErr && (
        <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "#c00" }}>
          {editErr}
        </div>
      )}

      {/* 操作按钮 */}
      <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        {canEdit && (
          <>
            <button
              onClick={() => {
                if (isEditing) {
                  setEditErr(null);
                  // 校验：每个章节必须有 id、title、content
                  const invalid = sectionsDraft.find(
                    (s) => !s.id.trim() || !s.title.trim() || !s.content.trim()
                  );
                  if (invalid) {
                    setEditErr("每个章节必须包含 id、title 和 content");
                    return;
                  }
                  updateMutation.mutate(
                    {
                      outlineId: outline.id,
                      payload: { sections: sectionsDraft },
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
                  : "保存修改"
                : "编辑大纲"}
            </button>
            {isEditing && (
              <button
                onClick={() => {
                  setSectionsDraft(outline.sections.map((s) => ({ ...s })));
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
            onClick={() => confirmMutation.mutate(outline.id)}
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
            {confirmMutation.isPending ? "确认中…" : "确认大纲"}
          </button>
        )}
        {canReject && (
          <button
            onClick={() => rejectMutation.mutate(outline.id)}
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
            {rejectMutation.isPending ? "拒绝中…" : "拒绝大纲"}
          </button>
        )}
      </div>

      {/* Word/PPT 生成 */}
      {canGenerate && (
        <div
          style={{
            marginTop: "0.75rem",
            paddingTop: "0.75rem",
            borderTop: "1px dashed #e5e7eb",
          }}
        >
          <h4 style={{ margin: "0 0 0.4rem", fontSize: "0.85rem", color: "#374151" }}>
            触发交付物生成
          </h4>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <button
              onClick={() => {
                setWordErr(null);
                setWordOk(null);
                wordMutation.mutate(outline.id, {
                  onSuccess: (data) => {
                    setWordJobId(data.job_id);
                  },
                  onError: (e) => setWordErr(errorMessage(e, "触发 Word 生成失败")),
                });
              }}
              disabled={wordMutation.isPending || !!wordJobId}
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
              {wordMutation.isPending
                ? "提交中…"
                : wordJobId
                ? "Word 生成中…"
                : "生成 Word"}
            </button>
            <button
              onClick={() => {
                setPptErr(null);
                setPptOk(null);
                pptMutation.mutate(outline.id, {
                  onSuccess: (data) => {
                    setPptJobId(data.job_id);
                  },
                  onError: (e) => setPptErr(errorMessage(e, "触发 PPT 生成失败")),
                });
              }}
              disabled={pptMutation.isPending || !!pptJobId}
              style={{
                padding: "0.25rem 0.6rem",
                fontSize: "0.8rem",
                background: "#7c3aed",
                color: "#fff",
                border: "none",
                borderRadius: "0.25rem",
                cursor: "pointer",
              }}
            >
              {pptMutation.isPending
                ? "提交中…"
                : pptJobId
                ? "PPT 生成中…"
                : "生成 PPT"}
            </button>
          </div>
          {wordJobId && wordJob && (
            <p style={{ fontSize: "0.8rem", color: "#2563eb", marginTop: "0.5rem" }}>
              {jobTypeLabel(wordJob.job_type)}：{jobStatusLabel(wordJob.status)}
              {(wordJob.status === "PENDING" || wordJob.status === "RUNNING") && "…"}
            </p>
          )}
          {pptJobId && pptJob && (
            <p style={{ fontSize: "0.8rem", color: "#2563eb", marginTop: "0.5rem" }}>
              {jobTypeLabel(pptJob.job_type)}：{jobStatusLabel(pptJob.status)}
              {(pptJob.status === "PENDING" || pptJob.status === "RUNNING") && "…"}
            </p>
          )}
          {wordOk && (
            <p style={{ color: "#16a34a", fontSize: "0.8rem", marginTop: "0.5rem" }}>
              {wordOk}
            </p>
          )}
          {wordErr && (
            <p style={{ color: "#c00", fontSize: "0.8rem", marginTop: "0.5rem" }}>
              {wordErr}
            </p>
          )}
          {pptOk && (
            <p style={{ color: "#16a34a", fontSize: "0.8rem", marginTop: "0.5rem" }}>
              {pptOk}
            </p>
          )}
          {pptErr && (
            <p style={{ color: "#c00", fontSize: "0.8rem", marginTop: "0.5rem" }}>
              {pptErr}
            </p>
          )}
          <Link
            to={`/projects/${projectId}/deliverables`}
            style={{
              display: "inline-block",
              marginTop: "0.5rem",
              fontSize: "0.8rem",
              color: "#2563eb",
            }}
          >
            前往交付物工作区查看和下载 →
          </Link>
        </div>
      )}
    </div>
  );
}

/** 章节只读展示。 */
function SectionView({ section }: { section: OutlineSection }) {
  return (
    <div
      style={{
        padding: "0.5rem",
        background: "#f9fafb",
        borderRadius: "0.25rem",
        marginBottom: "0.5rem",
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
        <strong style={{ fontSize: "0.85rem" }}>{section.title}</strong>
        <span
          style={{
            fontSize: "0.7rem",
            color: "#fff",
            background: "#6b7280",
            padding: "0.1rem 0.4rem",
            borderRadius: "0.25rem",
          }}
        >
          {sourceTypeLabel(section.source_type)}
        </span>
      </div>
      <p
        style={{
          margin: "0.4rem 0 0",
          fontSize: "0.8rem",
          color: "#374151",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {section.content}
      </p>
      {section.source_ids.length > 0 && (
        <p style={{ margin: "0.3rem 0 0", fontSize: "0.7rem", color: "#9ca3af" }}>
          来源 ID：{section.source_ids.join(", ")}
        </p>
      )}
    </div>
  );
}

export function OutlineWorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const pid = projectId!;
  const { data: project, isLoading: projLoading } = useProject(pid);
  const { data: outlines, isLoading: outlinesLoading } = useOutlines(pid);

  const generate = useGenerateOutline(pid);

  // 跟踪生成任务
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const { data: genJob } = useJob(pid, activeJobId);
  const prevGenJobStatusRef = useRef<string | undefined>(undefined);
  const qc = useQueryClient();

  const [genErr, setGenErr] = useState<string | null>(null);

  useEffect(() => {
    if (!genJob) return;
    const prev = prevGenJobStatusRef.current;
    const curr = genJob.status;
    if (
      prev &&
      prev !== curr &&
      (curr === "SUCCEEDED" || curr === "FAILED" || curr === "CANCELLED")
    ) {
      qc.invalidateQueries({ queryKey: ["outlines", pid, "list"] });
      setActiveJobId(null);
      prevGenJobStatusRef.current = undefined;
      if (curr === "FAILED") {
        setGenErr(`大纲生成任务失败`);
      }
    } else {
      prevGenJobStatusRef.current = curr;
    }
  }, [genJob?.status, genJob, qc, pid]);

  if (projLoading) return <p style={{ padding: "2rem" }}>加载中…</p>;
  if (!project) return <p style={{ padding: "2rem", color: "#c00" }}>项目不存在</p>;

  const canGenerate = project.status === "RESULT_CONFIRMED";
  const hasCandidate = (outlines ?? []).some(
    (o) => o.status === "CANDIDATE" || o.status === "CONFIRMED" || o.status === "STALE"
  );

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "1.5rem 1rem" }}>
      <Link to={`/projects/${pid}`} style={{ fontSize: "0.85rem", color: "#2563eb" }}>
        ← 项目详情
      </Link>
      <Link
        to={`/projects/${pid}/deliverables`}
        style={{ marginLeft: "1rem", fontSize: "0.85rem", color: "#2563eb" }}
      >
        交付物工作区
      </Link>

      <h1 style={{ fontSize: "1.3rem", marginTop: "0.75rem" }}>
        {project.name}{" "}
        <span style={{ fontSize: "0.8rem", color: "#888" }}>
          [{statusLabel(project.status)}]
        </span>
      </h1>
      <p style={{ fontSize: "0.85rem", color: "#6b7280", marginTop: "0.25rem" }}>
        基于已确认的实验要求、证据卡片、数据概览、分析方案和执行结果生成统一大纲。
        Word 和 PPT 必须从同一份已确认大纲生成。
      </p>

      {/* 生成大纲候选 */}
      <section
        style={{
          marginTop: "1.5rem",
          padding: "1rem",
          border: "1px solid #e5e7eb",
          borderRadius: "0.5rem",
        }}
      >
        <h3 style={{ margin: "0 0 0.5rem" }}>生成大纲候选</h3>
        {!canGenerate ? (
          <p style={{ fontSize: "0.85rem", color: "#6b7280" }}>
            项目当前状态为「{statusLabel(project.status)}」，
            需要先推进到「结果已确认（RESULT_CONFIRMED）」才能生成大纲。
            请先在分析方案工作区完成确认并执行代码任务。
          </p>
        ) : hasCandidate ? (
          <p style={{ fontSize: "0.85rem", color: "#6b7280" }}>
            当前已有候选或已确认大纲，可在下方编辑或确认。如需重新生成，请先拒绝现有候选。
          </p>
        ) : (
          <>
            <p style={{ fontSize: "0.85rem", color: "#6b7280", marginBottom: "0.5rem" }}>
              点击下方按钮生成大纲候选（本地规则提供者拼装 6 个章节）：
            </p>
            <button
              onClick={() => {
                setGenErr(null);
                generate.mutate(undefined, {
                  onSuccess: (data) => setActiveJobId(data.job_id),
                  onError: (e) => setGenErr(errorMessage(e, "触发生成失败")),
                });
              }}
              disabled={generate.isPending || !!activeJobId}
              style={{
                padding: "0.5rem 1rem",
                fontSize: "0.9rem",
                background: "#0ea5e9",
                color: "#fff",
                border: "none",
                borderRadius: "0.375rem",
                cursor: "pointer",
              }}
            >
              {generate.isPending || activeJobId
                ? "生成中…"
                : "生成大纲候选"}
            </button>
            {activeJobId && genJob && (
              <p style={{ fontSize: "0.8rem", color: "#2563eb", marginTop: "0.5rem" }}>
                {jobTypeLabel(genJob.job_type)}：{jobStatusLabel(genJob.status)}
                {(genJob.status === "PENDING" || genJob.status === "RUNNING") && "…"}
              </p>
            )}
            {genErr && (
              <p style={{ color: "#c00", fontSize: "0.85rem", marginTop: "0.5rem" }}>
                {genErr}
              </p>
            )}
          </>
        )}
      </section>

      {/* 大纲列表 */}
      <section style={{ marginTop: "1.5rem" }}>
        <h3 style={{ margin: "0 0 0.5rem" }}>大纲列表</h3>
        {outlinesLoading && (
          <p style={{ fontSize: "0.85rem", color: "#888" }}>加载中…</p>
        )}
        {!outlinesLoading && (!outlines || outlines.length === 0) && (
          <p style={{ fontSize: "0.85rem", color: "#888" }}>
            还没有生成任何大纲。
          </p>
        )}
        {outlines && outlines.length > 0 && (
          <div>
            {outlines.map((o) => (
              <OutlineCard key={o.id} projectId={pid} outline={o} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
