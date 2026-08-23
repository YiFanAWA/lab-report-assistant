import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useProject, useWorkspaceProjection } from "../features/projects/hooks";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";
import {
  EmptyState,
  ErrorPanel,
  JobProgress,
  LoadingState,
} from "../components/workspace/WorkspaceUI";
import {
  useSources,
  useCreateUrlSource,
  useCreatePdfSource,
  useDeleteSource,
  useCompleteSources,
} from "../features/sources/hooks";
import { useJob } from "../features/jobs/hooks";
import type { Source } from "../features/sources/types";

/** 来源状态中文映射。 */
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

    >
      <div >
        <strong >{source.title}</strong>
        <span >
          [{sourceKindLabel(source.source_kind)}]
        </span>
      </div>
      <div >
        状态：<strong>{sourceStatusLabel(source.status)}</strong>
        {job && (
          <JobProgress
            status={job.status}
            label={jobTypeLabel(job.job_type)}
            jobId={job.id}
            errorCode={job.error_code}
            errorMessage={job.error_message}
          />
        )}
      </div>
      {source.url && (
        <div >
          URL：<a href={source.url} target="_blank" rel="noreferrer noopener">{source.url}</a>
        </div>
      )}
      {source.file_path && (
        <div >
          文件：{source.file_path}
        </div>
      )}
      {source.content_type && (
        <div >
          类型：{source.content_type}
        </div>
      )}
      {source.error_code && (
        <ErrorPanel
          className="workspace-inline-error"
          message={source.error_message ?? "资料来源处理失败，请检查来源后重试。"}
          code={source.error_code}
          jobId={source.job_id}
        />
      )}
      <div >
        创建：{new Date(source.created_at).toLocaleString("zh-CN")}
        {source.fetched_at && ` · 采集：${new Date(source.fetched_at).toLocaleString("zh-CN")}`}
        {source.parsed_at && ` · 解析：${new Date(source.parsed_at).toLocaleString("zh-CN")}`}
      </div>
      {source.status !== "DELETED" && (
        <div >
          {source.status === "PARSED" && (
            <Link
              to={`/projects/${projectId}/evidence`}

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
  const { data: projection } = useWorkspaceProjection(pid);
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

  if (projLoading) return <LoadingState />;
  if (!project) return <ErrorPanel message="项目不存在" />;

  const sourceStep = projection?.phases
    .flatMap((phase) => phase.steps)
    .find((step) => step.id === "sources");
  const sourcesStepOpen = sourceStep?.is_open === true;
  const hasParsedSource = (sources ?? []).some((s) => s.status === "PARSED");
  const projectStatusLabel = projection?.project.status_label ?? project.status;

  return (
    <WorkspaceShell project={project} projection={projection} title="资料来源工作区">
      <div className="workspace-legacy-page">
      <Link to={`/projects/${pid}`} >
        ← 项目详情
      </Link>

      <h1 >
        工作区{" "}
        <span >[{projectStatusLabel}]</span>
      </h1>
      <p >
        在此登记公开 URL 或上传 PDF 辅助文件，系统会自动采集和解析，生成可确认的证据卡片。
      </p>

      {!sourcesStepOpen && (
        <div>
          当前工作区尚未开放。
          {sourceStep?.open_reason?.display_message ??
            sourceStep?.open_reason?.message ??
            "请按阶段进度完成前置工作后再继续。"}
        </div>
      )}

      {/* URL 登记表单 */}
      <section

      >
        <h3 >登记公开 URL</h3>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com/article.html"
          disabled={!sourcesStepOpen}

        />
        <input
          value={urlTitle}
          onChange={(e) => setUrlTitle(e.target.value)}
          placeholder="来源标题（可选）"
          disabled={!sourcesStepOpen}

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
          disabled={!sourcesStepOpen || createUrl.isPending}

        >
          {createUrl.isPending ? "登记中…" : "登记 URL"}
        </button>
        {createUrl.data && (
          <p >
            已登记，正在采集…
          </p>
        )}
        {urlErr && <p >{urlErr}</p>}
      </section>

      {/* PDF 上传 */}
      <section

      >
        <h3 >上传 PDF 辅助文件</h3>
        <input
          value={pdfTitle}
          onChange={(e) => setPdfTitle(e.target.value)}
          placeholder="文件标题（可选）"
          disabled={!sourcesStepOpen}

        />
        <input
          type="file"
          accept="application/pdf,.pdf"
          disabled={!sourcesStepOpen}
          onChange={(e) => setPdfFile(e.target.files?.[0] ?? null)}

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
          disabled={!sourcesStepOpen || createPdf.isPending}

        >
          {createPdf.isPending ? "上传中…" : "上传 PDF"}
        </button>
        {pdfErr && <p >{pdfErr}</p>}
      </section>

      {/* 来源列表 */}
      <section >
        <h3>资料来源</h3>
        {srcLoading && <p >加载中…</p>}
        {!srcLoading && (!sources || sources.length === 0) && (
          <EmptyState title="还没有登记任何资料来源。" description="登记公开 URL 或上传 PDF 后，这里会显示来源处理状态。" />
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
          disabled={!hasParsedSource || complete.isPending}

        >
          {complete.isPending ? "推进中…" : "完成来源收集"}
        </button>
        {!hasParsedSource && (
          <span >
            至少需要一个已解析（PARSED）的来源才能完成收集
          </span>
        )}
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
