import { useState } from "react";
import { useParams, Link } from "react-router";
import { useProject } from "../features/projects/hooks";
import {
  useDeliverables,
  useDeliverableVersions,
  useCompleteProject,
} from "../features/outlines/hooks";
import { buildDeliverableDownloadUrl } from "../features/outlines/api";
import type {
  Deliverable,
  DeliverableVersion,
} from "../features/outlines/types";

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

/** 交付物类型中文映射。 */
function deliverableTypeLabel(t: string) {
  const m: Record<string, string> = {
    WORD: "Word 文档",
    PPT: "PPT 演示",
  };
  return m[t] ?? t;
}

/** 交付物状态中文映射。 */
function deliverableStatusLabel(s: string) {
  const m: Record<string, string> = {
    PENDING: "排队中",
    RUNNING: "生成中",
    SUCCEEDED: "已生成",
    FAILED: "失败",
    STALE: "已失效",
  };
  return m[s] ?? s;
}

/** 交付物版本状态中文映射。 */
function versionStatusLabel(s: string) {
  const m: Record<string, string> = {
    PENDING: "排队中",
    RUNNING: "生成中",
    SUCCEEDED: "已生成",
    FAILED: "失败",
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
    deliverable.deliverable_type === "WORD" ? "#0ea5e9" : "#7c3aed";

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
        <strong style={{ fontSize: "0.9rem", color: typeColor }}>
          {deliverableTypeLabel(deliverable.deliverable_type)}
          <span style={{ marginLeft: "0.5rem", fontSize: "0.75rem", color: "#6b7280" }}>
            [{deliverableStatusLabel(deliverable.status)}]
          </span>
        </strong>
        <span style={{ fontSize: "0.75rem", color: "#9ca3af" }}>
          创建：{new Date(deliverable.created_at).toLocaleString("zh-CN")}
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
          关联大纲已变更，此交付物已失效。请回到大纲工作区重新确认大纲后再生成。
        </div>
      )}

      {/* 版本列表 */}
      <div style={{ marginTop: "0.5rem" }}>
        <h4 style={{ margin: "0 0 0.3rem", fontSize: "0.8rem", color: "#374151" }}>
          版本记录
        </h4>
        {isLoading && (
          <p style={{ fontSize: "0.8rem", color: "#888" }}>加载中…</p>
        )}
        {!isLoading && (!versions || versions.length === 0) && (
          <p style={{ fontSize: "0.8rem", color: "#888" }}>暂无版本记录。</p>
        )}
        {versions && versions.length > 0 && (
          <div style={{ fontSize: "0.8rem" }}>
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
      style={{
        padding: "0.5rem",
        background: "#f9fafb",
        borderRadius: "0.25rem",
        marginBottom: "0.3rem",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: "0.5rem",
        flexWrap: "wrap",
      }}
    >
      <div>
        <span style={{ fontWeight: 600 }}>v{version.version}</span>
        <span style={{ marginLeft: "0.5rem", color: "#6b7280" }}>
          [{versionStatusLabel(version.status)}]
        </span>
        <span style={{ marginLeft: "0.5rem", color: "#9ca3af" }}>
          {new Date(version.created_at).toLocaleString("zh-CN")}
        </span>
        {version.file_size_bytes !== null && (
          <span style={{ marginLeft: "0.5rem", color: "#9ca3af" }}>
            · {formatFileSize(version.file_size_bytes)}
          </span>
        )}
        {version.duration_seconds !== null && (
          <span style={{ marginLeft: "0.5rem", color: "#9ca3af" }}>
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
            style={{
              padding: "0.25rem 0.6rem",
              fontSize: "0.8rem",
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
        )}
      </div>
      {isFailed && (
        <div
          style={{
            width: "100%",
            marginTop: "0.3rem",
            padding: "0.3rem 0.5rem",
            background: "#fee2e2",
            borderRadius: "0.25rem",
            fontSize: "0.75rem",
            color: "#b91c1c",
          }}
        >
          失败：{version.error_code}
          {version.error_message && ` - ${version.error_message}`}
        </div>
      )}
    </div>
  );
}

export function DeliverableWorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const pid = projectId!;
  const { data: project, isLoading: projLoading } = useProject(pid);
  const { data: deliverables, isLoading: deliverablesLoading } =
    useDeliverables(pid);

  const complete = useCompleteProject(pid);
  const [completeErr, setCompleteErr] = useState<string | null>(null);
  const [completeOk, setCompleteOk] = useState<string | null>(null);

  if (projLoading) return <p style={{ padding: "2rem" }}>加载中…</p>;
  if (!project) return <p style={{ padding: "2rem", color: "#c00" }}>项目不存在</p>;

  // 判断是否可完成：至少一个 Word 和一个 PPT 的最新版本为 SUCCEEDED
  const wordDeliverables = (deliverables ?? []).filter(
    (d) => d.deliverable_type === "WORD"
  );
  const pptDeliverables = (deliverables ?? []).filter(
    (d) => d.deliverable_type === "PPT"
  );
  // 交付物状态为 SUCCEEDED 即代表最新版本成功
  const hasWordSuccess = wordDeliverables.some(
    (d) => d.status === "SUCCEEDED"
  );
  const hasPptSuccess = pptDeliverables.some((d) => d.status === "SUCCEEDED");
  const canComplete =
    hasWordSuccess && hasPptSuccess && project.status !== "COMPLETED";

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "1.5rem 1rem" }}>
      <Link to={`/projects/${pid}`} style={{ fontSize: "0.85rem", color: "#2563eb" }}>
        ← 项目详情
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
      <p style={{ fontSize: "0.85rem", color: "#6b7280", marginTop: "0.25rem" }}>
        Word 和 PPT 交付物从同一份已确认大纲生成。
        每次生成创建新版本，旧版本保留不删除，可追溯。
      </p>

      {/* 交付物列表 */}
      <section style={{ marginTop: "1.5rem" }}>
        <h3 style={{ margin: "0 0 0.5rem" }}>交付物列表</h3>
        {deliverablesLoading && (
          <p style={{ fontSize: "0.85rem", color: "#888" }}>加载中…</p>
        )}
        {!deliverablesLoading && (!deliverables || deliverables.length === 0) && (
          <div
            style={{
              padding: "1rem",
              background: "#f9fafb",
              borderRadius: "0.5rem",
              fontSize: "0.85rem",
              color: "#6b7280",
            }}
          >
            当前还没有任何交付物。请先在
            <Link
              to={`/projects/${pid}/outline`}
              style={{ margin: "0 0.25rem", color: "#2563eb" }}
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
      <section style={{ marginTop: "1.5rem" }}>
        <button
          onClick={() => {
            setCompleteErr(null);
            setCompleteOk(null);
            complete.mutate(undefined, {
              onSuccess: (data) => {
                setCompleteOk(`项目状态已推进到「${statusLabel(data.status)}」`);
              },
              onError: (e) =>
                setCompleteErr(errorMessage(e, "完成项目失败")),
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
          {complete.isPending ? "推进中…" : "完成项目"}
        </button>
        <span style={{ marginLeft: "0.5rem", fontSize: "0.8rem", color: "#6b7280" }}>
          需要至少一个成功的 Word 交付物和一个成功的 PPT 交付物
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
