import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useProject } from "../features/projects/hooks";
import {
  useSources,
  useCreateUrlSource,
  useCreatePdfSource,
  useDeleteSource,
  useCompleteSources,
} from "../features/sources/hooks";
import { useJob } from "../features/jobs/hooks";
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

/** 来源状态中文映射。 */
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

/** 来源类型中文映射。 */
function sourceKindLabel(k: string) {
  const m: Record<string, string> = {
    URL: "URL",
    FILE: "PDF 文件",
  };
  return m[k] ?? k;
}

/** 任务类型中文映射。 */
function jobTypeLabel(t: string) {
  const m: Record<string, string> = {
    FETCH_URL: "采集 URL",
    PARSE_DOCUMENT: "解析文档",
    GENERATE_EVIDENCE: "生成证据卡片",
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

/** 单个来源卡片，集成任务状态轮询。 */
function SourceCard({
  projectId,
  source,
}: {
  projectId: string;
  source: Source;
}) {
  const qc = useQueryClient();
  const deleteMutation = useDeleteSource(projectId);

  // 跟踪当前活跃 job_id：来源创建/采集/解析时都会产生任务
  // 来源 job_id 仅创建时返回；之后通过轮询 list 不再带 job_id
  // 因此这里只在 status 为 PENDING/FETCHED（采集/解析进行中）时尝试拉最近任务
  // 简化方案：仅当 source.job_id 存在时轮询；其余依赖列表刷新
  const jobId = source.job_id;
  const { data: job } = useJob(projectId, jobId);

  const prevJobStatusRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!job) return;
    const prev = prevJobStatusRef.current;
    const curr = job.status;
    if (prev && prev !== curr && (curr === "SUCCEEDED" || curr === "FAILED" || curr === "CANCELLED")) {
      // 任务完成时刷新来源列表，确保看到最新状态
      qc.invalidateQueries({ queryKey: ["sources", projectId, "list"] });
    }
    prevJobStatusRef.current = curr;
  }, [job?.status, qc, projectId, job]);

  const [confirming, setConfirming] = useState(false);

  return (
    <div
      style={{
        padding: "0.75rem",
        border: "1px solid #e5e7eb",
        borderRadius: "0.5rem",
        marginBottom: "0.5rem",
        background: source.status === "DELETED" ? "#f9fafb" : "#fff",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "0.5rem" }}>
        <strong style={{ wordBreak: "break-all" }}>{source.title}</strong>
        <span style={{ fontSize: "0.75rem", color: "#6b7280", whiteSpace: "nowrap" }}>
          [{sourceKindLabel(source.source_kind)}]
        </span>
      </div>
      <div style={{ fontSize: "0.85rem", color: "#374151", marginTop: "0.25rem" }}>
        状态：<strong>{sourceStatusLabel(source.status)}</strong>
        {job && (
          <span style={{ marginLeft: "0.5rem", color: "#2563eb" }}>
            · {jobTypeLabel(job.job_type)}：{jobStatusLabel(job.status)}
            {(job.status === "PENDING" || job.status === "RUNNING") && "…"}
          </span>
        )}
      </div>
      {source.url && (
        <div style={{ fontSize: "0.8rem", color: "#6b7280", marginTop: "0.25rem", wordBreak: "break-all" }}>
          URL：<a href={source.url} target="_blank" rel="noreferrer noopener">{source.url}</a>
        </div>
      )}
      {source.file_path && (
        <div style={{ fontSize: "0.8rem", color: "#6b7280", marginTop: "0.25rem", wordBreak: "break-all" }}>
          文件：{source.file_path}
        </div>
      )}
      {source.content_type && (
        <div style={{ fontSize: "0.75rem", color: "#9ca3af", marginTop: "0.25rem" }}>
          类型：{source.content_type}
        </div>
      )}
      {source.error_code && (
        <div style={{ marginTop: "0.5rem", padding: "0.5rem", background: "#fef2f2", borderRadius: "0.25rem", fontSize: "0.8rem" }}>
          <div style={{ color: "#b91c1c", fontWeight: 600 }}>失败原因码：{source.error_code}</div>
          {source.error_message && (
            <div style={{ color: "#b91c1c", marginTop: "0.25rem" }}>{source.error_message}</div>
          )}
        </div>
      )}
      <div style={{ fontSize: "0.75rem", color: "#9ca3af", marginTop: "0.25rem" }}>
        创建：{new Date(source.created_at).toLocaleString("zh-CN")}
        {source.fetched_at && ` · 采集：${new Date(source.fetched_at).toLocaleString("zh-CN")}`}
        {source.parsed_at && ` · 解析：${new Date(source.parsed_at).toLocaleString("zh-CN")}`}
      </div>
      {source.status !== "DELETED" && (
        <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          {source.status === "PARSED" && (
            <Link
              to={`/projects/${projectId}/evidence`}
              style={{
                padding: "0.25rem 0.6rem",
                fontSize: "0.8rem",
                background: "#0ea5e9",
                color: "#fff",
                textDecoration: "none",
                borderRadius: "0.25rem",
              }}
            >
              查看证据卡片
            </Link>
          )}
          <button
            onClick={() => {
              if (confirming) return;
              setConfirming(true);
              deleteMutation.mutate(source.id, {
                onSettled: () => setConfirming(false),
              });
            }}
            disabled={deleteMutation.isPending}
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
            {confirming ? "删除中…" : "删除来源"}
          </button>
        </div>
      )}
    </div>
  );
}

export function SourcesWorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const pid = projectId!;
  const { data: project, isLoading: projLoading } = useProject(pid);
  const { data: sources, isLoading: srcLoading } = useSources(pid);

  const createUrl = useCreateUrlSource(pid);
  const createPdf = useCreatePdfSource(pid);
  const complete = useCompleteSources(pid);

  const [url, setUrl] = useState("");
  const [urlTitle, setUrlTitle] = useState("");
  const [urlErr, setUrlErr] = useState<string | null>(null);
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [pdfTitle, setPdfTitle] = useState("");
  const [pdfErr, setPdfErr] = useState<string | null>(null);
  const [completeErr, setCompleteErr] = useState<string | null>(null);
  const [completeOk, setCompleteOk] = useState<string | null>(null);

  if (projLoading) return <p style={{ padding: "2rem" }}>加载中…</p>;
  if (!project) return <p style={{ padding: "2rem", color: "#c00" }}>项目不存在</p>;

  // 仅在 REQUIREMENT_CONFIRMED 或之后状态允许登记来源
  const orderedStatuses = [
    "DRAFT",
    "REQUIREMENT_PARSED",
    "REQUIREMENT_CONFIRMED",
    "SOURCES_COLLECTED",
    "EVIDENCE_CONFIRMED",
    "COMPLETED",
  ];
  const currentIndex = orderedStatuses.indexOf(project.status);
  const allowedIndex = orderedStatuses.indexOf("REQUIREMENT_CONFIRMED");
  const canRegister = currentIndex >= allowedIndex;
  const canComplete = (sources ?? []).some((s) => s.status === "PARSED");

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "1.5rem 1rem" }}>
      <Link to={`/projects/${pid}`} style={{ fontSize: "0.85rem", color: "#2563eb" }}>
        ← 项目详情
      </Link>

      <h1 style={{ fontSize: "1.3rem", marginTop: "0.75rem" }}>
        {project.name}{" "}
        <span style={{ fontSize: "0.8rem", color: "#888" }}>[{statusLabel(project.status)}]</span>
      </h1>
      <p style={{ fontSize: "0.85rem", color: "#6b7280", marginTop: "0.25rem" }}>
        在此登记公开 URL 或上传 PDF 辅助文件，系统会自动采集和解析，生成可确认的证据卡片。
      </p>

      {!canRegister && (
        <div style={{ marginTop: "1rem", padding: "0.75rem", background: "#fef3c7", border: "1px solid #fde68a", borderRadius: "0.5rem", fontSize: "0.85rem", color: "#92400e" }}>
          当前项目状态为「{statusLabel(project.status)}」，需要先完成实验要求确认才能登记资料来源。
          <Link to={`/projects/${pid}/requirements`} style={{ marginLeft: "0.5rem", color: "#2563eb" }}>
            前往实验要求工作区
          </Link>
        </div>
      )}

      {/* URL 登记表单 */}
      <section
        style={{
          marginTop: "1.5rem",
          padding: "1rem",
          border: "1px solid #e5e7eb",
          borderRadius: "0.5rem",
        }}
      >
        <h3 style={{ margin: "0 0 0.5rem" }}>登记公开 URL</h3>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com/article.html"
          disabled={!canRegister}
          style={{
            width: "100%",
            padding: "0.4rem",
            marginBottom: "0.5rem",
            boxSizing: "border-box",
          }}
        />
        <input
          value={urlTitle}
          onChange={(e) => setUrlTitle(e.target.value)}
          placeholder="来源标题（可选）"
          disabled={!canRegister}
          style={{
            width: "100%",
            padding: "0.4rem",
            marginBottom: "0.5rem",
            boxSizing: "border-box",
          }}
        />
        <button
          onClick={() => {
            setUrlErr(null);
            if (!url.trim()) {
              setUrlErr("请输入 URL");
              return;
            }
            createUrl.mutate(
              { url: url.trim(), title: urlTitle.trim() },
              {
                onSuccess: () => {
                  setUrl("");
                  setUrlTitle("");
                },
                onError: (e) => setUrlErr(errorMessage(e, "登记失败")),
              }
            );
          }}
          disabled={!canRegister || createUrl.isPending}
          style={{ padding: "0.4rem 1rem" }}
        >
          {createUrl.isPending ? "登记中…" : "登记 URL"}
        </button>
        {createUrl.data && (
          <p style={{ color: "#16a34a", fontSize: "0.85rem", marginTop: "0.5rem" }}>
            已登记，正在采集…
          </p>
        )}
        {urlErr && <p style={{ color: "#c00", fontSize: "0.85rem", marginTop: "0.5rem" }}>{urlErr}</p>}
      </section>

      {/* PDF 上传 */}
      <section
        style={{
          marginTop: "1rem",
          padding: "1rem",
          border: "1px solid #e5e7eb",
          borderRadius: "0.5rem",
        }}
      >
        <h3 style={{ margin: "0 0 0.5rem" }}>上传 PDF 辅助文件</h3>
        <input
          value={pdfTitle}
          onChange={(e) => setPdfTitle(e.target.value)}
          placeholder="文件标题（可选）"
          disabled={!canRegister}
          style={{
            width: "100%",
            padding: "0.4rem",
            marginBottom: "0.5rem",
            boxSizing: "border-box",
          }}
        />
        <input
          type="file"
          accept="application/pdf,.pdf"
          disabled={!canRegister}
          onChange={(e) => setPdfFile(e.target.files?.[0] ?? null)}
          style={{ display: "block", marginBottom: "0.5rem" }}
        />
        <button
          onClick={() => {
            setPdfErr(null);
            if (!pdfFile) {
              setPdfErr("请选择 PDF 文件");
              return;
            }
            createPdf.mutate(
              { file: pdfFile, title: pdfTitle.trim() },
              {
                onSuccess: () => {
                  setPdfFile(null);
                  setPdfTitle("");
                },
                onError: (e) => setPdfErr(errorMessage(e, "上传失败")),
              }
            );
          }}
          disabled={!canRegister || createPdf.isPending}
          style={{ padding: "0.4rem 1rem" }}
        >
          {createPdf.isPending ? "上传中…" : "上传 PDF"}
        </button>
        {pdfErr && <p style={{ color: "#c00", fontSize: "0.85rem", marginTop: "0.5rem" }}>{pdfErr}</p>}
      </section>

      {/* 来源列表 */}
      <section style={{ marginTop: "1.5rem" }}>
        <h3>资料来源</h3>
        {srcLoading && <p style={{ fontSize: "0.85rem", color: "#888" }}>加载中…</p>}
        {!srcLoading && (!sources || sources.length === 0) && (
          <p style={{ fontSize: "0.85rem", color: "#888" }}>还没有登记任何资料来源。</p>
        )}
        {sources && sources.length > 0 && (
          <div>
            {sources.map((s) => (
              <SourceCard key={s.id} projectId={pid} source={s} />
            ))}
          </div>
        )}
      </section>

      {/* 完成来源收集 */}
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
          {complete.isPending ? "推进中…" : "完成来源收集"}
        </button>
        {!canComplete && (
          <span style={{ marginLeft: "0.5rem", fontSize: "0.8rem", color: "#6b7280" }}>
            至少需要一个已解析（PARSED）的来源才能完成收集
          </span>
        )}
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
