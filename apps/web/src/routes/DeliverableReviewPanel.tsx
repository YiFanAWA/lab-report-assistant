import { useState } from "react";
import { Link, useParams } from "react-router";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";
import {
  Button,
  Card,
  EmptyState,
  ErrorPanel,
  LoadingState,
  StatusBadge,
} from "../components/workspace/WorkspaceUI";
import { useProject, useWorkspaceProjection } from "../features/projects/hooks";
import {
  useCompleteProject,
  useDeliverableVersions,
  useDeliverables,
  useDeliveryReview,
  useGeneratePdf,
} from "../features/outlines/hooks";
import { buildDeliverableDownloadUrl } from "../features/outlines/api";
import type {
  Deliverable,
  DeliverableVersion,
  DeliveryReviewDeliverable,
  DeliveryVersionReview,
  DeliveryReviewProjection,
  ReviewCheck,
} from "../features/outlines/types";

const TYPE_LABELS: Record<string, string> = {
  WORD: "Word 文档",
  PDF: "PDF 报告",
  PPT: "PPT 演示",
};
const STATUS_LABELS: Record<string, string> = {
  PENDING: "等待处理",
  RUNNING: "正在处理",
  SUCCEEDED: "已完成",
  FAILED: "需要处理",
  STALE: "已失效",
  PASS: "通过",
  WARN: "需留意",
  BLOCKED: "需要处理",
  NOT_RUN: "尚未检查",
};

function typeLabel(value: string) {
  return TYPE_LABELS[value] ?? value;
}
function statusLabel(value: string) {
  return STATUS_LABELS[value] ?? value;
}
function formatSize(bytes: number | null | undefined) {
  if (bytes === null || bytes === undefined) return "N/A";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}
function errorMessage(error: unknown, fallback: string) {
  if (typeof error === "object" && error !== null && "message" in error) {
    const value = (error as { message?: unknown }).message;
    if (typeof value === "string" && value.trim()) return value;
  }
  return fallback;
}

function CheckList({ title, checks }: { title: string; checks: ReviewCheck[] | undefined }) {
  if (!checks || checks.length === 0) {
    return (
      <Card className="deliverable-review__check-card">
        <h2>{title}</h2>
        <p className="deliverable-review__muted">N/A：后端尚未提供检查结果。</p>
      </Card>
    );
  }
  return (
    <Card className="deliverable-review__check-card">
      <div className="deliverable-review__section-heading"><h2>{title}</h2><span>{checks.length} 项</span></div>
      <div className="deliverable-review__check-list">
        {checks.map((check) => (
          <div className="deliverable-review__check" key={check.code}>
            <StatusBadge status={check.status} label={statusLabel(check.status)} />
            <div>
              <strong>{check.label}</strong>
              {check.reason && <p>{check.reason}</p>}
              {check.recovery_action && <small>修复动作：{check.recovery_action}</small>}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function Provenance({ provenance }: { provenance: DeliveryReviewDeliverable["provenance"] }) {
  const value = (id: string | null | undefined, reason?: string | null) =>
    id ?? `N/A${reason ? `（${reason}）` : ""}`;
  return (
    <details className="deliverable-review__trace">
      <summary>来源与执行追溯</summary>
      <dl>
        <div><dt>大纲版本</dt><dd>{value(provenance.outline_version?.toString(), provenance.unavailable_reason)}</dd></div>
        <div><dt>数据集版本</dt><dd>{provenance.dataset_version_ids.length ? provenance.dataset_version_ids.join("、") : value(null, provenance.unavailable_reason)}</dd></div>
        <div><dt>分析方案</dt><dd>{provenance.analysis_plan_ids.length ? provenance.analysis_plan_ids.join("、") : value(null, provenance.unavailable_reason)}</dd></div>
        <div><dt>执行记录</dt><dd>{provenance.execution_run_ids.length ? provenance.execution_run_ids.join("、") : value(null, provenance.unavailable_reason)}</dd></div>
        <div><dt>文件 SHA-256</dt><dd>{value(provenance.file_sha256, provenance.file_sha256 ? null : "生成链未保存 hash")}</dd></div>
        {provenance.source_word_version_id && <div><dt>PDF 源 Word 版本</dt><dd>{provenance.source_word_version_id}</dd></div>}
      </dl>
    </details>
  );
}

function VersionRow({
  projectId,
  deliverableId,
  legacy,
  reviewVersion,
}: {
  projectId: string;
  deliverableId: string;
  legacy?: DeliverableVersion;
  reviewVersion?: DeliveryVersionReview;
}) {
  const id = reviewVersion?.id ?? legacy?.id;
  if (!id) return null;
  const status = reviewVersion?.status ?? legacy?.status ?? "NOT_RUN";
  const canDownload = status === "SUCCEEDED" && Boolean(reviewVersion?.id ?? legacy?.file_path);
  const failure = reviewVersion?.failure ?? (
    legacy?.status === "FAILED" ? { code: legacy.error_code, message: legacy.error_message } : null
  );
  return (
    <div className="deliverable-review__version">
      <div className="deliverable-review__version-main">
        <strong>v{reviewVersion?.version ?? legacy?.version}</strong>
        <StatusBadge status={status} label={statusLabel(status)} />
        {reviewVersion?.is_recommended && <span className="deliverable-review__recommended">推荐下载</span>}
        {reviewVersion?.is_stale && <span className="deliverable-review__stale">已失效</span>}
        <span className="deliverable-review__version-meta">
          {new Date(reviewVersion?.created_at ?? legacy?.created_at ?? "").toLocaleString("zh-CN")}
          · {formatSize(reviewVersion?.file_size_bytes ?? legacy?.file_size_bytes)}
        </span>
      </div>
      {canDownload && (
        <a className="workspace-ui-button workspace-ui-button--secondary workspace-ui-button--sm"
          href={buildDeliverableDownloadUrl(projectId, deliverableId, id)}>下载</a>
      )}
      {reviewVersion?.visual_inspection && (
        <p className="deliverable-review__inspection">
          视觉检查：{reviewVersion.visual_inspection.label}
          {reviewVersion.visual_inspection.reason && ` · ${reviewVersion.visual_inspection.reason}`}
        </p>
      )}
      {reviewVersion?.diff_summary && <p className="deliverable-review__diff">版本差异：{reviewVersion.diff_summary}</p>}
      {failure && <ErrorPanel className="workspace-inline-error" message={failure.message ?? "此版本生成失败，请按恢复动作重试。"} code={failure.code} />}
      {reviewVersion?.recovery_action && <p className="deliverable-review__recovery">恢复动作：{reviewVersion.recovery_action}</p>}
    </div>
  );
}

function DeliverableCard({
  projectId,
  deliverable,
  reviewItem,
}: {
  projectId: string;
  deliverable: Deliverable;
  reviewItem?: DeliveryReviewDeliverable;
}) {
  const versionsQuery = useDeliverableVersions(projectId, deliverable.id);
  const versions = versionsQuery.data ?? [];
  const reviewVersions = reviewItem?.versions ?? [];
  const isStale = reviewItem?.is_stale || deliverable.status === "STALE";
  return (
    <Card className="deliverable-review__deliverable">
      <div className="deliverable-review__deliverable-heading">
        <div><p className="deliverable-review__eyebrow">正式交付物</p><h3>{typeLabel(deliverable.deliverable_type)}</h3></div>
        <StatusBadge status={deliverable.status} label={`[${statusLabel(deliverable.status)}]`} />
      </div>
      <p className="deliverable-review__muted">生成于 {new Date(deliverable.created_at).toLocaleString("zh-CN")} · 大纲 {deliverable.outline_id}</p>
      {isStale && <div className="deliverable-review__stale-panel">此交付物已失效。关联大纲已变更，请回到大纲工作区重新确认后再生成。</div>}
      {reviewItem && <Provenance provenance={reviewItem.provenance} />}
      <div className="deliverable-review__preview"><strong>预览</strong><span>{reviewItem?.versions[0]?.preview.label ?? "N/A：尚未提供真实预览"}</span><small>没有真实视觉检查时不会显示“通过”。</small></div>
      <div className="deliverable-review__versions">
        <div className="deliverable-review__section-heading"><h4>版本记录</h4><span>{reviewVersions.length || versions.length} 个版本</span></div>
        {versionsQuery.isLoading && <LoadingState label="正在读取版本记录…" />}
        {versionsQuery.isError && <ErrorPanel message={errorMessage(versionsQuery.error, "版本记录读取失败")} />}
        {!versionsQuery.isLoading && !versionsQuery.isError && reviewVersions.length === 0 && versions.length === 0 && <p className="deliverable-review__muted">暂无版本记录。</p>}
        {reviewVersions.map((version) => <VersionRow key={version.id} projectId={projectId} deliverableId={deliverable.id} reviewVersion={version} />)}
        {reviewVersions.length === 0 && versions.map((version) => <VersionRow key={version.id} projectId={projectId} deliverableId={deliverable.id} legacy={version} />)}
      </div>
    </Card>
  );
}

export function DeliverableReviewPanel() {
  const { projectId } = useParams<{ projectId: string }>();
  const pid = projectId!;
  const { data: project, isLoading: projectLoading, isError: projectError, error: projectQueryError } = useProject(pid);
  const { data: projection } = useWorkspaceProjection(pid);
  const deliverablesQuery = useDeliverables(pid);
  const reviewQuery = useDeliveryReview(pid);
  const complete = useCompleteProject(pid);
  const generatePdf = useGeneratePdf(pid);
  const [completeError, setCompleteError] = useState<string | null>(null);
  const [completeSuccess, setCompleteSuccess] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);

  if (projectLoading) return <LoadingState />;
  if (projectError) return <ErrorPanel message={errorMessage(projectQueryError, "项目读取失败")} />;
  if (!project) return <ErrorPanel message="项目不存在" />;
  if (deliverablesQuery.isError) return <ErrorPanel message={errorMessage(deliverablesQuery.error, "交付物列表读取失败")} />;

  const review = reviewQuery.data as DeliveryReviewProjection | undefined;
  const reviewDeliverables = review?.deliverables ?? [];
  const deliverables = deliverablesQuery.data ?? [];
  const outlineId = review?.traceability.outline_id;
  const failedPdf = reviewDeliverables.some((item) => item.type === "PDF" && item.status === "FAILED");

  return (
    <WorkspaceShell project={project} projection={projection} title="交付物审阅台">
      <div className="deliverable-review">
        <div className="deliverable-review__intro">
          <div><p className="deliverable-review__eyebrow">交付前检查</p><h2>确认最终成果是否可交</h2><p>下载前核对内容质量、统计边界、版本来源和真实视觉检查状态。</p><span className="deliverable-review__project-status">[{projection?.project.status_label ?? project.status}]</span></div>
          <Link className="workspace-ui-button workspace-ui-button--ghost" to={`/projects/${pid}/outline`}>返回大纲工作区</Link>
        </div>
        {reviewQuery.isLoading && <LoadingState label="正在读取交付审阅状态…" />}
        {reviewQuery.isError && <ErrorPanel message={errorMessage(reviewQuery.error, "交付审阅状态读取失败")} />}
        {review && (
          <>
            <Card className="deliverable-review__summary">
              <div><span>审阅状态</span><StatusBadge status={review.review_status} label={statusLabel(review.review_status)} /></div>
              <div><span>推荐下载</span><strong>{review.recommended_downloads?.length ?? 0} 类</strong></div>
              <div><span>视觉检查</span><strong>尚未检查</strong></div>
            </Card>
            <div className="deliverable-review__quality-grid">
              <CheckList title="内容质量" checks={review.content_quality} />
              <CheckList title="统计与边界" checks={review.boundary_checks} />
            </div>
            <Card className="deliverable-review__gates">
              <div className="deliverable-review__section-heading"><h2>质量门禁</h2><span>由后端投影计算</span></div>
              <div className="deliverable-review__gate-list">
                {review.quality_gates.map((gate) => <div key={gate.code}><StatusBadge status={gate.status} label={statusLabel(gate.status)} /><span>{gate.label}</span>{gate.reason && <small>{gate.reason}</small>}{gate.recovery_action && <small>修复动作：{gate.recovery_action}</small>}</div>)}
              </div>
            </Card>
            <Card className="deliverable-review__trace-summary">
              <div className="deliverable-review__section-heading"><h2>全局追溯</h2><span>真实绑定</span></div>
              <p>大纲：{review.traceability.outline_id ?? "N/A"} · 数据集：{review.traceability.dataset_version_ids?.join("、") || "N/A"} · 分析方案：{review.traceability.analysis_plan_ids?.join("、") || "N/A"} · 执行：{review.traceability.execution_run_ids?.join("、") || "N/A"}</p>
              {review.traceability.unavailable_reason && <small>{review.traceability.unavailable_reason}</small>}
            </Card>
          </>
        )}
        {failedPdf && outlineId && (
          <Card className="deliverable-review__action-card">
            <strong>PDF 生成失败</strong><p>可以在确认 Word 源版本后重新生成 PDF。</p>
            <Button variant="secondary" onClick={() => { setPdfError(null); generatePdf.mutate(outlineId, { onError: (error) => setPdfError(errorMessage(error, "PDF 重试失败")) }); }} disabled={generatePdf.isPending}>
              {generatePdf.isPending ? "正在重试 PDF…" : "重试 PDF 生成"}
            </Button>
            {pdfError && <p className="deliverable-review__action-error">{pdfError}</p>}
          </Card>
        )}
        <section className="deliverable-review__list">
          <div className="deliverable-review__section-heading"><div><p className="deliverable-review__eyebrow">正式交付物</p><h2>Word · PDF · PPT</h2></div><span>{deliverables.length} 项</span></div>
          {deliverables.length === 0 && !deliverablesQuery.isLoading && <EmptyState title="当前还没有任何交付物" description="请先在大纲工作区确认大纲后触发生成。" action={<Link to={`/projects/${pid}/outline`}>进入大纲工作区</Link>} />}
          <div className="deliverable-review__deliverable-grid">
            {deliverables.map((item) => <DeliverableCard key={item.id} projectId={pid} deliverable={item} reviewItem={reviewDeliverables.find((reviewItem) => reviewItem.id === item.id)} />)}
          </div>
        </section>
        <Card className="deliverable-review__complete">
          <div><h2>项目完成确认</h2><p>只有 Word、PDF 和 PPT 当前都有成功且未失效版本时，后端才允许完成项目。</p>{completeSuccess && <p className="deliverable-review__success">{completeSuccess}</p>}{completeError && <p className="deliverable-review__action-error">{completeError}</p>}</div>
          <Button onClick={() => { setCompleteError(null); setCompleteSuccess(null); complete.mutate(undefined, { onSuccess: () => setCompleteSuccess("项目状态已推进，请返回项目总览确认最新阶段。"), onError: (error) => setCompleteError(errorMessage(error, "完成项目失败")) }); }} disabled={!(review?.available_actions.can_complete ?? false) || complete.isPending}>
            {complete.isPending ? "推进中…" : "完成项目"}
          </Button>
        </Card>
      </div>
    </WorkspaceShell>
  );
}
