import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useProject } from "../features/projects/hooks";
import {
  useDatasets,
  useDatasetVersions,
  useUploadDataset,
  useCreateUrlDataset,
  useDeleteDataset,
  useReuploadDataset,
  useCompleteDatasets,
} from "../features/datasets/hooks";
import { useJob } from "../features/jobs/hooks";
import type {
  Dataset,
  DatasetVersion,
  DatasetProfile,
  FieldProfile,
} from "../features/datasets/types";

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

/** 数据集状态中文映射。 */
function datasetStatusLabel(s: string) {
  const m: Record<string, string> = {
    PENDING: "待解析",
    READY: "就绪",
    FAILED: "失败",
    DELETED: "已删除",
  };
  return m[s] ?? s;
}

/** 数据集版本状态中文映射。 */
function versionStatusLabel(s: string) {
  const m: Record<string, string> = {
    PENDING: "待解析",
    PARSING: "解析中",
    PARSED: "已解析",
    FAILED: "失败",
    SUPERSEDED: "已废弃",
  };
  return m[s] ?? s;
}

/** 数据集类型中文映射。 */
function datasetKindLabel(k: string) {
  const m: Record<string, string> = {
    FILE: "文件",
    URL: "URL",
  };
  return m[k] ?? k;
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

/** 解析 profile_json 字符串为 DatasetProfile。 */
function parseProfile(profileJson: string | null): DatasetProfile | null {
  if (!profileJson) return null;
  try {
    return JSON.parse(profileJson) as DatasetProfile;
  } catch {
    return null;
  }
}

/** 格式化文件大小。 */
function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

/** 字段类型中文映射。 */
function fieldTypeLabel(t: string) {
  const m: Record<string, string> = {
    int: "整数",
    float: "浮点",
    string: "字符串",
    datetime: "日期时间",
    bool: "布尔",
  };
  return m[t] ?? t;
}

/** 单个字段概览行。 */
function FieldProfileRow({ field }: { field: FieldProfile }) {
  return (
    <tr style={{ borderBottom: "1px solid #f3f4f6" }}>
      <td style={{ padding: "0.4rem 0.5rem", fontSize: "0.8rem", wordBreak: "break-all" }}>
        {field.name}
      </td>
      <td style={{ padding: "0.4rem 0.5rem", fontSize: "0.8rem" }}>
        {fieldTypeLabel(field.inferred_type)}
      </td>
      <td style={{ padding: "0.4rem 0.5rem", fontSize: "0.8rem" }}>
        {(field.null_rate * 100).toFixed(1)}%
      </td>
      <td style={{ padding: "0.4rem 0.5rem", fontSize: "0.8rem" }}>{field.unique_count}</td>
      <td style={{ padding: "0.4rem 0.5rem", fontSize: "0.8rem", color: "#6b7280", wordBreak: "break-all" }}>
        {field.sample_values.slice(0, 3).join(", ")}
      </td>
    </tr>
  );
}

/** 数据集卡片，集成任务轮询、版本列表、字段概览、质量指标。 */
function DatasetCard({
  projectId,
  dataset,
}: {
  projectId: string;
  dataset: Dataset;
}) {
  const qc = useQueryClient();
  const deleteMutation = useDeleteDataset(projectId);
  const reuploadMutation = useReuploadDataset(projectId);

  const [expanded, setExpanded] = useState(false);
  const [reuploadFile, setReuploadFile] = useState<File | null>(null);
  const [reuploadErr, setReuploadErr] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  // 跟踪当前活跃 job_id：上传/重新上传时返回
  const jobId = dataset.job_id;
  const { data: job } = useJob(projectId, jobId);

  const prevJobStatusRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!job) return;
    const prev = prevJobStatusRef.current;
    const curr = job.status;
    if (
      prev &&
      prev !== curr &&
      (curr === "SUCCEEDED" || curr === "FAILED" || curr === "CANCELLED")
    ) {
      qc.invalidateQueries({ queryKey: ["datasets", projectId, "list"] });
      if (expanded) {
        qc.invalidateQueries({
          queryKey: ["datasets", projectId, dataset.id, "versions"],
        });
      }
    }
    prevJobStatusRef.current = curr;
  }, [job?.status, job, qc, projectId, dataset.id, expanded]);

  // 展开时加载版本列表
  const { data: versions, isLoading: versionsLoading } = useDatasetVersions(
    projectId,
    expanded ? dataset.id : ""
  );

  const isDeleted = dataset.status === "DELETED";
  const latestVersion = versions && versions.length > 0 ? versions[0] : null;
  const profile = parseProfile(latestVersion?.profile_json ?? null);

  return (
    <div
      style={{
        padding: "0.75rem",
        border: "1px solid #e5e7eb",
        borderRadius: "0.5rem",
        marginBottom: "0.5rem",
        background: isDeleted ? "#f9fafb" : "#fff",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          gap: "0.5rem",
        }}
      >
        <strong style={{ wordBreak: "break-all" }}>{dataset.title}</strong>
        <span style={{ fontSize: "0.75rem", color: "#6b7280", whiteSpace: "nowrap" }}>
          [{datasetKindLabel(dataset.dataset_kind)}]
        </span>
      </div>
      <div style={{ fontSize: "0.85rem", color: "#374151", marginTop: "0.25rem" }}>
        状态：<strong>{datasetStatusLabel(dataset.status)}</strong>
        {job && (
          <span style={{ marginLeft: "0.5rem", color: "#2563eb" }}>
            · {jobTypeLabel(job.job_type)}：{jobStatusLabel(job.status)}
            {(job.status === "PENDING" || job.status === "RUNNING") && "…"}
          </span>
        )}
      </div>
      {dataset.description && (
        <div style={{ fontSize: "0.8rem", color: "#6b7280", marginTop: "0.25rem" }}>
          {dataset.description}
        </div>
      )}
      {latestVersion && (
        <div style={{ fontSize: "0.8rem", color: "#6b7280", marginTop: "0.25rem" }}>
          {latestVersion.row_count !== null && `行数：${latestVersion.row_count}`}
          {latestVersion.column_count !== null &&
            ` · 字段数：${latestVersion.column_count}`}
          {` · 大小：${formatBytes(latestVersion.file_size_bytes)}`}
        </div>
      )}
      {dataset.error_code && (
        <div
          style={{
            marginTop: "0.5rem",
            padding: "0.5rem",
            background: "#fef2f2",
            borderRadius: "0.25rem",
            fontSize: "0.8rem",
          }}
        >
          <div style={{ color: "#b91c1c", fontWeight: 600 }}>
            失败原因码：{dataset.error_code}
          </div>
          {dataset.error_message && (
            <div style={{ color: "#b91c1c", marginTop: "0.25rem" }}>
              {dataset.error_message}
            </div>
          )}
        </div>
      )}
      <div style={{ fontSize: "0.75rem", color: "#9ca3af", marginTop: "0.25rem" }}>
        创建：{new Date(dataset.created_at).toLocaleString("zh-CN")}
        {dataset.updated_at &&
          ` · 更新：${new Date(dataset.updated_at).toLocaleString("zh-CN")}`}
      </div>

      {!isDeleted && (
        <div
          style={{
            marginTop: "0.5rem",
            display: "flex",
            gap: "0.5rem",
            flexWrap: "wrap",
            alignItems: "center",
          }}
        >
          <button
            onClick={() => setExpanded((v) => !v)}
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
            {expanded ? "收起详情" : "查看详情"}
          </button>
          <label
            style={{
              padding: "0.25rem 0.6rem",
              fontSize: "0.8rem",
              background: "#e0e7ff",
              color: "#3730a3",
              border: "1px solid #c7d2fe",
              borderRadius: "0.25rem",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "0.25rem",
            }}
          >
            重新上传
            <input
              type="file"
              accept=".csv,.xlsx"
              style={{ display: "none" }}
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null;
                setReuploadFile(f);
                setReuploadErr(null);
                if (f) {
                  reuploadMutation.mutate(
                    { datasetId: dataset.id, file: f },
                    {
                      onSuccess: () => {
                        setReuploadFile(null);
                        setExpanded(true);
                      },
                      onError: (e) =>
                        setReuploadErr(errorMessage(e, "重新上传失败")),
                    }
                  );
                }
              }}
              disabled={reuploadMutation.isPending}
            />
          </label>
          <button
            onClick={() => {
              if (confirming) return;
              setConfirming(true);
              deleteMutation.mutate(dataset.id, {
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
            {confirming ? "删除中…" : "删除数据集"}
          </button>
          {reuploadMutation.isPending && (
            <span style={{ fontSize: "0.75rem", color: "#2563eb" }}>
              上传中…
            </span>
          )}
          {dataset.status === "READY" && (
            <Link
              to={`/projects/${projectId}/analysis`}
              style={{
                padding: "0.25rem 0.6rem",
                fontSize: "0.8rem",
                background: "#0ea5e9",
                color: "#fff",
                textDecoration: "none",
                borderRadius: "0.25rem",
              }}
            >
              查看分析方案
            </Link>
          )}
        </div>
      )}

      {reuploadErr && (
        <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "#c00" }}>
          {reuploadErr}
        </div>
      )}

      {expanded && (
        <div
          style={{
            marginTop: "0.75rem",
            paddingTop: "0.75rem",
            borderTop: "1px solid #e5e7eb",
          }}
        >
          <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.9rem" }}>版本列表</h4>
          {versionsLoading && (
            <p style={{ fontSize: "0.8rem", color: "#888" }}>加载中…</p>
          )}
          {!versionsLoading && (!versions || versions.length === 0) && (
            <p style={{ fontSize: "0.8rem", color: "#888" }}>暂无版本。</p>
          )}
          {versions && versions.length > 0 && (
            <div style={{ marginBottom: "1rem" }}>
              {versions.map((v: DatasetVersion) => (
                <div
                  key={v.id}
                  style={{
                    padding: "0.4rem",
                    background: "#f9fafb",
                    borderRadius: "0.25rem",
                    marginBottom: "0.25rem",
                    fontSize: "0.8rem",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>
                      <strong>v{v.version}</strong> [{versionStatusLabel(v.status)}]
                    </span>
                    <span style={{ color: "#6b7280" }}>
                      {formatBytes(v.file_size_bytes)}
                    </span>
                  </div>
                  {v.row_count !== null && (
                    <div style={{ color: "#6b7280", marginTop: "0.2rem" }}>
                      行：{v.row_count} · 列：{v.column_count}
                    </div>
                  )}
                  {v.error_code && (
                    <div style={{ color: "#b91c1c", marginTop: "0.2rem" }}>
                      {v.error_code}
                      {v.error_message ? `：${v.error_message}` : ""}
                    </div>
                  )}
                  <div style={{ color: "#9ca3af", marginTop: "0.2rem" }}>
                    创建：{new Date(v.created_at).toLocaleString("zh-CN")}
                    {v.parsed_at &&
                      ` · 解析：${new Date(v.parsed_at).toLocaleString("zh-CN")}`}
                  </div>
                </div>
              ))}
            </div>
          )}

          {profile ? (
            <>
              <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.9rem" }}>质量概览</h4>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, 1fr)",
                  gap: "0.5rem",
                  marginBottom: "1rem",
                }}
              >
                <QualityCard label="总行数" value={profile.row_count} />
                <QualityCard
                  label="缺失行数"
                  value={profile.incomplete_row_count}
                />
                <QualityCard
                  label="重复行数"
                  value={profile.duplicate_row_count}
                />
                <QualityCard
                  label="质量评分"
                  value={`${profile.quality_score.toFixed(1)} / 100`}
                />
              </div>

              <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.9rem" }}>
                字段概览
              </h4>
              <div style={{ overflowX: "auto" }}>
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    fontSize: "0.8rem",
                  }}
                >
                  <thead>
                    <tr style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left" }}>
                      <th style={{ padding: "0.4rem 0.5rem" }}>字段名</th>
                      <th style={{ padding: "0.4rem 0.5rem" }}>类型</th>
                      <th style={{ padding: "0.4rem 0.5rem" }}>缺失率</th>
                      <th style={{ padding: "0.4rem 0.5rem" }}>唯一值</th>
                      <th style={{ padding: "0.4rem 0.5rem" }}>样例</th>
                    </tr>
                  </thead>
                  <tbody>
                    {profile.field_profiles.map((f) => (
                      <FieldProfileRow key={f.name} field={f} />
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            latestVersion &&
            latestVersion.status !== "PARSED" && (
              <p style={{ fontSize: "0.8rem", color: "#888" }}>
                数据集尚未解析完成，暂无字段概览。
              </p>
            )
          )}
        </div>
      )}
    </div>
  );
}

/** 质量指标卡片。 */
function QualityCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div
      style={{
        padding: "0.5rem",
        background: "#f0f9ff",
        border: "1px solid #bae6fd",
        borderRadius: "0.25rem",
      }}
    >
      <div style={{ fontSize: "0.75rem", color: "#0369a1" }}>{label}</div>
      <div style={{ fontSize: "1.1rem", fontWeight: 600, color: "#0c4a6e" }}>
        {value}
      </div>
    </div>
  );
}

export function DatasetWorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const pid = projectId!;
  const { data: project, isLoading: projLoading } = useProject(pid);
  const { data: datasets, isLoading: dsLoading } = useDatasets(pid);

  const upload = useUploadDataset(pid);
  const createUrl = useCreateUrlDataset(pid);
  const complete = useCompleteDatasets(pid);

  const [fileTitle, setFileTitle] = useState("");
  const [fileDesc, setFileDesc] = useState("");
  const [datasetFile, setDatasetFile] = useState<File | null>(null);
  const [uploadErr, setUploadErr] = useState<string | null>(null);

  const [url, setUrl] = useState("");
  const [urlTitle, setUrlTitle] = useState("");
  const [urlDesc, setUrlDesc] = useState("");
  const [urlErr, setUrlErr] = useState<string | null>(null);

  const [completeErr, setCompleteErr] = useState<string | null>(null);
  const [completeOk, setCompleteOk] = useState<string | null>(null);

  if (projLoading) return <p style={{ padding: "2rem" }}>加载中…</p>;
  if (!project) return <p style={{ padding: "2rem", color: "#c00" }}>项目不存在</p>;

  // 项目状态顺序，用于判断入口可用性
  const orderedStatuses = [
    "DRAFT",
    "REQUIREMENT_PARSED",
    "REQUIREMENT_CONFIRMED",
    "SOURCES_COLLECTED",
    "EVIDENCE_CONFIRMED",
    "DATASET_READY",
    "ANALYSIS_PLANNED",
    "ANALYSIS_CONFIRMED",
    "COMPLETED",
  ];
  const currentIndex = orderedStatuses.indexOf(project.status);
  const evidenceIndex = orderedStatuses.indexOf("EVIDENCE_CONFIRMED");
  const canRegister = currentIndex >= evidenceIndex;
  const canComplete = (datasets ?? []).some((d) => d.status === "READY");

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "1.5rem 1rem" }}>
      <Link to={`/projects/${pid}`} style={{ fontSize: "0.85rem", color: "#2563eb" }}>
        ← 项目详情
      </Link>

      <h1 style={{ fontSize: "1.3rem", marginTop: "0.75rem" }}>
        {project.name}{" "}
        <span style={{ fontSize: "0.8rem", color: "#888" }}>
          [{statusLabel(project.status)}]
        </span>
      </h1>
      <p style={{ fontSize: "0.85rem", color: "#6b7280", marginTop: "0.25rem" }}>
        上传 CSV/Excel 文件或登记公开 URL，系统会自动解析字段概览和质量指标。
      </p>

      {!canRegister && (
        <div
          style={{
            marginTop: "1rem",
            padding: "0.75rem",
            background: "#fef3c7",
            border: "1px solid #fde68a",
            borderRadius: "0.5rem",
            fontSize: "0.85rem",
            color: "#92400e",
          }}
        >
          当前项目状态为「{statusLabel(project.status)}」，需要先完成证据确认才能登记数据集。
          <Link
            to={`/projects/${pid}/evidence`}
            style={{ marginLeft: "0.5rem", color: "#2563eb" }}
          >
            前往证据卡片工作区
          </Link>
        </div>
      )}

      {/* 文件上传 */}
      <section
        style={{
          marginTop: "1.5rem",
          padding: "1rem",
          border: "1px solid #e5e7eb",
          borderRadius: "0.5rem",
        }}
      >
        <h3 style={{ margin: "0 0 0.5rem" }}>上传 CSV/Excel 文件</h3>
        <input
          value={fileTitle}
          onChange={(e) => setFileTitle(e.target.value)}
          placeholder="数据集标题（可选）"
          disabled={!canRegister}
          style={{
            width: "100%",
            padding: "0.4rem",
            marginBottom: "0.5rem",
            boxSizing: "border-box",
          }}
        />
        <input
          value={fileDesc}
          onChange={(e) => setFileDesc(e.target.value)}
          placeholder="数据集说明（可选）"
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
          accept=".csv,.xlsx"
          disabled={!canRegister}
          onChange={(e) => setDatasetFile(e.target.files?.[0] ?? null)}
          style={{ display: "block", marginBottom: "0.5rem" }}
        />
        <button
          onClick={() => {
            setUploadErr(null);
            if (!datasetFile) {
              setUploadErr("请选择 CSV 或 Excel 文件");
              return;
            }
            upload.mutate(
              {
                file: datasetFile,
                title: fileTitle.trim() || datasetFile.name,
                description: fileDesc.trim() || undefined,
              },
              {
                onSuccess: () => {
                  setDatasetFile(null);
                  setFileTitle("");
                  setFileDesc("");
                },
                onError: (e) => setUploadErr(errorMessage(e, "上传失败")),
              }
            );
          }}
          disabled={!canRegister || upload.isPending}
          style={{ padding: "0.4rem 1rem" }}
        >
          {upload.isPending ? "上传中…" : "上传文件"}
        </button>
        {uploadErr && (
          <p style={{ color: "#c00", fontSize: "0.85rem", marginTop: "0.5rem" }}>
            {uploadErr}
          </p>
        )}
      </section>

      {/* URL 登记 */}
      <section
        style={{
          marginTop: "1rem",
          padding: "1rem",
          border: "1px solid #e5e7eb",
          borderRadius: "0.5rem",
        }}
      >
        <h3 style={{ margin: "0 0 0.5rem" }}>登记公开 CSV/Excel URL</h3>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com/data.csv"
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
          placeholder="数据集标题（可选）"
          disabled={!canRegister}
          style={{
            width: "100%",
            padding: "0.4rem",
            marginBottom: "0.5rem",
            boxSizing: "border-box",
          }}
        />
        <input
          value={urlDesc}
          onChange={(e) => setUrlDesc(e.target.value)}
          placeholder="数据集说明（可选）"
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
              {
                url: url.trim(),
                title: urlTitle.trim() || url.trim(),
                description: urlDesc.trim() || undefined,
              },
              {
                onSuccess: () => {
                  setUrl("");
                  setUrlTitle("");
                  setUrlDesc("");
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
        {urlErr && (
          <p style={{ color: "#c00", fontSize: "0.85rem", marginTop: "0.5rem" }}>
            {urlErr}
          </p>
        )}
      </section>

      {/* 数据集列表 */}
      <section style={{ marginTop: "1.5rem" }}>
        <h3>数据集列表</h3>
        {dsLoading && (
          <p style={{ fontSize: "0.85rem", color: "#888" }}>加载中…</p>
        )}
        {!dsLoading && (!datasets || datasets.length === 0) && (
          <p style={{ fontSize: "0.85rem", color: "#888" }}>
            还没有登记任何数据集。
          </p>
        )}
        {datasets && datasets.length > 0 && (
          <div>
            {datasets.map((d) => (
              <DatasetCard key={d.id} projectId={pid} dataset={d} />
            ))}
          </div>
        )}
      </section>

      {/* 完成数据集收集 */}
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
          {complete.isPending ? "推进中…" : "完成数据集收集"}
        </button>
        {!canComplete && (
          <span style={{ marginLeft: "0.5rem", fontSize: "0.8rem", color: "#6b7280" }}>
            至少需要一个已就绪（READY）的数据集才能完成收集
          </span>
        )}
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
