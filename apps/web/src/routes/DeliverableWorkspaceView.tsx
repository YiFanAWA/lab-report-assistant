import { useState } from "react";
import { useParams, Link } from "react-router";
import { useProject, useWorkspaceProjection } from "../features/projects/hooks";
import {
  useDeliverables,
  useDeliverableVersions,
  useCompleteProject,
  useDeliveryReview,
  useGeneratePdf,
} from "../features/outlines/hooks";
import { buildDeliverableDownloadUrl } from "../features/outlines/api";
import type {
  Deliverable,
  DeliverableVersion,
} from "../features/outlines/types";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";
import { ErrorPanel, LoadingState } from "../components/workspace/WorkspaceUI";

/** 交付物类型中文映射。 */
function deliverableTypeLabel(t: string) {
  const m: Record<string, string> = {
    WORD: "Word 文档",
    PDF: "PDF 报告",
    PPT: "PPT 演示",
  };
  return m[t] ?? t;
}

/** 交付物状态中文映射。 */
function deliverableStatusLabel(s: string) {
  const m: Record<string, string> = {
    PENDING: "等待处理",
    RUNNING: "正在处理",
    SUCCEEDED: "已完成",
    FAILED: "需要处理",
    STALE: "已失效",
  };
  return m[s] ?? s;
}

/** 交付物版本状态中文映射。 */
function versionStatusLabel(s: string) {
  const m: Record<string, string> = {
    PENDING: "等待处理",
    RUNNING: "正在处理",
    SUCCEEDED: "已完成",
    FAILED: "需要处理",
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
function formatFileSize(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

/** 单个交付物卡片，含版本列表和下载。 */
function DeliverableCard({
  projectId,
  deliverable,
}: {
  projectId: string;
  deliverable: Deliverable;
}) {
  const { data: versions, isLoading } = useDeliverableVersions(
    projectId,
    deliverable.id
  );

  const isStale = deliverable.status === "STALE";
  const typeColor =
    deliverable.deliverable_type === "WORD" ? "#0ea5e9" :
    deliverable.deliverable_type === "PDF" ? "#0f766e" : "#7c3aed";

  return (
    <div

    >
      <div

      >
        <strong >
          {deliverableTypeLabel(deliverable.deliverable_type)}
          <span >
            [{deliverableStatusLabel(deliverable.status)}]
          </span>
        </strong>
        <span >
          创建：{new Date(deliverable.created_at).toLocaleString("zh-CN")}
        </span>
      </div>

      {isStale && (
        <div

        >
          关联大纲已变更，此交付物已失效。请回到大纲工作区重新确认大纲后再生成。
        </div>
      )}

      {/* 版本列表 */}
      <div >
        <h4 >
          版本记录
        </h4>
        {isLoading && (
          <p >加载中…</p>
        )}
        {!isLoading && (!versions || versions.length === 0) && (
          <p >暂无版本记录。</p>
        )}
        {versions && versions.length > 0 && (
          <div >
            {versions.map((v) => (
              <VersionRow
                key={v.id}
                projectId={projectId}
                deliverable={deliverable}
                version={v}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/** 单个版本行。 */
function VersionRow({
  projectId,
  deliverable,
  version,
}: {
  projectId: string;
  deliverable: Deliverable;
  version: DeliverableVersion;
}) {
  const canDownload = version.status === "SUCCEEDED" && version.file_path;
  const isFailed = version.status === "FAILED";

  return (
    <div

    >
      <div>
        <span >v{version.version}</span>
        <span >
          [{versionStatusLabel(version.status)}]
        </span>
        <span >
          {new Date(version.created_at).toLocaleString("zh-CN")}
        </span>
        {version.file_size_bytes !== null && (
          <span >
            · {formatFileSize(version.file_size_bytes)}
          </span>
        )}
        {version.duration_seconds !== null && (
          <span >
            · 耗时 {version.duration_seconds.toFixed(1)}s
          </span>
        )}
      </div>
      <div>
        {canDownload && (
          <a
            href={buildDeliverableDownloadUrl(
              projectId,
              deliverable.id,
              version.id
            )}

          >
            下载
          </a>
        )}
      </div>
      {isFailed && (
        <ErrorPanel
          className="workspace-inline-error"
          message={version.error_message ?? "此版本生成失败，请重试。"}
          code={version.error_code}
        />
      )}
    </div>
  );
}

export function DeliverableWorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const pid = projectId!;
  const { data: project, isLoading: projLoading } = useProject(pid);
  const { data: projection } = useWorkspaceProjection(pid);
  const { data: deliverables, isLoading: deliverablesLoading } =
    useDeliverables(pid);
  const { data: review } = useDeliveryReview(pid);

  const complete = useCompleteProject(pid);
  const generatePdf = useGeneratePdf(pid);
  const [completeErr, setCompleteErr] = useState<string | null>(null);
  const [completeOk, setCompleteOk] = useState<string | null>(null);
  const [pdfErr, setPdfErr] = useState<string | null>(null);

  if (projLoading) return <LoadingState />;
  if (!project) return <ErrorPanel message="项目不存在" />;

  const reviewCanComplete = review?.available_actions.can_complete ?? false;
  const outlineId = review?.traceability?.outline_id;

  return (
    <WorkspaceShell project={project} projection={projection} title="交付物审阅台">
      <div className="workspace-legacy-page">
      <Link to={`/projects/${pid}`} >
        ← 项目详情
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
      <p >
        Word、PDF 和 PPT 交付物从同一份已确认大纲生成。
        每次生成创建新版本，旧版本保留不删除，可追溯。
      </p>


      <section >
        <h2 >交付质量门禁</h2>
        <p >
          以下状态来自后端审阅投影；未运行的门禁不会被显示为通过。
        </p>
        {!review && <p >正在读取审阅状态…</p>}
        {review && (
          <>
            <div >
              {review.quality_gates.map((gate) => (
                <span
                  key={gate.code}
                  title={gate.reason ?? gate.source}

                >
                  {gate.status === "PASS" ? "✓" : gate.status === "BLOCKED" ? "!" : "·"} {gate.label}
                </span>
              ))}
            </div>
            {outlineId && review.deliverables.some(
              (item) => item.type === "PDF" && item.status === "FAILED"
            ) && (
              <div >
                <button
                  type="button"
                  onClick={() => {
                    setPdfErr(null);
                    generatePdf.mutate(outlineId, {
                      onError: (error) => setPdfErr(errorMessage(error, "PDF 重试失败")),
                    });
                  }}
                  disabled={generatePdf.isPending}

                >
                  {generatePdf.isPending ? "正在重试 PDF…" : "重试 PDF 生成"}
                </button>
                {pdfErr && <p >{pdfErr}</p>}
              </div>
            )}
          </>
        )}
      </section>

      {/* 交付物列表 */}
      <section >
        <h3 >交付物列表</h3>
        {deliverablesLoading && (
          <p >加载中…</p>
        )}
        {!deliverablesLoading && (!deliverables || deliverables.length === 0) && (
          <div

          >
            当前还没有任何交付物。请先在
            <Link
              to={`/projects/${pid}/outline`}

            >
              大纲工作区
            </Link>
            确认大纲后触发生成。
          </div>
        )}
        {deliverables && deliverables.length > 0 && (
          <div>
            {deliverables.map((d) => (
              <DeliverableCard key={d.id} projectId={pid} deliverable={d} />
            ))}
          </div>
        )}
      </section>

      {/* 完成项目 */}
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
                setCompleteErr(errorMessage(e, "完成项目失败")),
            });
          }}
          disabled={!reviewCanComplete || complete.isPending}

        >
          {complete.isPending ? "推进中…" : "完成项目"}
        </button>
        <span >
          需要 Word、PDF 和 PPT 三类正式交付物均有成功版本
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
