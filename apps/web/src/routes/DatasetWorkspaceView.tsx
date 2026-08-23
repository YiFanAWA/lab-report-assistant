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

/** 数据集状态中文映射。 */
function datasetStatusLabel(s: string) {
  const m: Record<string, string> = {
    PENDING: "等待处理",
    READY: "就绪",
    FAILED: "需要处理",
    DELETED: "已删除",
  };
  return m[s] ?? s;
}

/** 数据集版本状态中文映射。 */
function versionStatusLabel(s: string) {
  const m: Record<string, string> = {
    PENDING: "等待处理",
    PARSING: "正在处理",
    PARSED: "已解析",
    FAILED: "需要处理",
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
    <tr >
      <td >
        {field.name}
      </td>
      <td >
        {fieldTypeLabel(field.inferred_type)}
      </td>
      <td >
        {(field.null_rate * 100).toFixed(1)}%
      </td>
      <td >{field.unique_count}</td>
      <td >
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

    >
      <div

      >
        <strong >{dataset.title}</strong>
        <span >
          [{datasetKindLabel(dataset.dataset_kind)}]
        </span>
      </div>
      <div >
        状态：<strong>{datasetStatusLabel(dataset.status)}</strong>
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
      {dataset.description && (
        <div >
          {dataset.description}
        </div>
      )}
      {latestVersion && (
        <div >
          {latestVersion.row_count !== null && `行数：${latestVersion.row_count}`}
          {latestVersion.column_count !== null &&
            ` · 字段数：${latestVersion.column_count}`}
          {` · 大小：${formatBytes(latestVersion.file_size_bytes)}`}
        </div>
      )}
      {dataset.error_code && (
        <ErrorPanel
          className="workspace-inline-error"
          message={dataset.error_message ?? "数据集处理失败，请检查文件后重试。"}
          code={dataset.error_code}
          jobId={dataset.job_id}
        />
      )}
      <div >
        创建：{new Date(dataset.created_at).toLocaleString("zh-CN")}
        {dataset.updated_at &&
          ` · 更新：${new Date(dataset.updated_at).toLocaleString("zh-CN")}`}
      </div>

      {!isDeleted && (
        <div

        >
          <button
            onClick={() => setExpanded((v) => !v)}

          >
            {expanded ? "收起详情" : "查看详情"}
          </button>
          <label

          >
            重新上传
            <input
              type="file"
              accept=".csv,.xlsx"

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

          >
            {confirming ? "删除中…" : "删除数据集"}
          </button>
          {reuploadMutation.isPending && (
            <span >
              上传中…
            </span>
          )}
          {dataset.status === "READY" && (
            <Link
              to={`/projects/${projectId}/analysis`}

            >
              查看分析方案
            </Link>
          )}
        </div>
      )}

      {reuploadErr && (
        <ErrorPanel className="workspace-inline-error" message={reuploadErr} />
      )}

      {expanded && (
        <div

        >
          <h4 >版本列表</h4>
          {versionsLoading && (
            <p >加载中…</p>
          )}
          {!versionsLoading && (!versions || versions.length === 0) && (
            <p >暂无版本。</p>
          )}
          {versions && versions.length > 0 && (
            <div >
              {versions.map((v: DatasetVersion) => (
                <div
                  key={v.id}

                >
                  <div >
                    <span>
                      <strong>v{v.version}</strong> [{versionStatusLabel(v.status)}]
                    </span>
                    <span >
                      {formatBytes(v.file_size_bytes)}
                    </span>
                  </div>
                  {v.row_count !== null && (
                    <div >
                      行：{v.row_count} · 列：{v.column_count}
                    </div>
                  )}
                  {v.error_code && (
                    <ErrorPanel
                      className="workspace-inline-error"
                      message={v.error_message ?? "数据版本解析失败，请检查文件后重试。"}
                      code={v.error_code}
                    />
                  )}
                  <div >
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
              <h4 >质量概览</h4>
              <div

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

              <h4 >
                字段概览
              </h4>
              <div >
                <table

                >
                  <thead>
                    <tr >
                      <th >字段名</th>
                      <th >类型</th>
                      <th >缺失率</th>
                      <th >唯一值</th>
                      <th >样例</th>
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
              <p >
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

    >
      <div >{label}</div>
      <div >
        {value}
      </div>
    </div>
  );
}

export function DatasetWorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const pid = projectId!;
  const { data: project, isLoading: projLoading } = useProject(pid);
  const { data: projection } = useWorkspaceProjection(pid);
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

  if (projLoading) return <LoadingState />;
  if (!project) return <ErrorPanel message="项目不存在" />;

  const datasetStep = projection?.phases
    .flatMap((phase) => phase.steps)
    .find((step) => step.id === "datasets");
  const datasetsStepOpen = datasetStep?.is_open === true;
  const hasReadyDataset = (datasets ?? []).some((d) => d.status === "READY");
  const projectStatusLabel = projection?.project.status_label ?? project.status;

  return (
    <WorkspaceShell project={project} projection={projection} title="数据集工作区">
      <div className="workspace-legacy-page">
      <Link to={`/projects/${pid}`} >
        ← 项目详情
      </Link>

      <h1 >
        工作区{" "}
        <span >
          [{projectStatusLabel}]
        </span>
      </h1>
      <p >
        上传 CSV/Excel 文件或登记公开 URL，系统会自动解析字段概览和质量指标。
      </p>

      {!datasetsStepOpen && (
        <div>
          当前工作区尚未开放。
          {datasetStep?.open_reason?.display_message ??
            datasetStep?.open_reason?.message ??
            "请按阶段进度完成前置工作后再继续。"}
        </div>
      )}

      {/* 文件上传 */}
      <section

      >
        <h3 >上传 CSV/Excel 文件</h3>
        <input
          value={fileTitle}
          onChange={(e) => setFileTitle(e.target.value)}
          placeholder="数据集标题（可选）"
          disabled={!datasetsStepOpen}

        />
        <input
          value={fileDesc}
          onChange={(e) => setFileDesc(e.target.value)}
          placeholder="数据集说明（可选）"
          disabled={!datasetsStepOpen}

        />
        <input
          type="file"
          accept=".csv,.xlsx"
          disabled={!datasetsStepOpen}
          onChange={(e) => setDatasetFile(e.target.files?.[0] ?? null)}

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
          disabled={!datasetsStepOpen || upload.isPending}

        >
          {upload.isPending ? "上传中…" : "上传文件"}
        </button>
        {uploadErr && (
          <p >
            {uploadErr}
          </p>
        )}
      </section>

      {/* URL 登记 */}
      <section

      >
        <h3 >登记公开 CSV/Excel URL</h3>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com/data.csv"
          disabled={!datasetsStepOpen}

        />
        <input
          value={urlTitle}
          onChange={(e) => setUrlTitle(e.target.value)}
          placeholder="数据集标题（可选）"
          disabled={!datasetsStepOpen}

        />
        <input
          value={urlDesc}
          onChange={(e) => setUrlDesc(e.target.value)}
          placeholder="数据集说明（可选）"
          disabled={!datasetsStepOpen}

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
          disabled={!datasetsStepOpen || createUrl.isPending}

        >
          {createUrl.isPending ? "登记中…" : "登记 URL"}
        </button>
        {urlErr && (
          <p >
            {urlErr}
          </p>
        )}
      </section>

      {/* 数据集列表 */}
      <section >
        <h3>数据集列表</h3>
        {dsLoading && (
          <p >加载中…</p>
        )}
        {!dsLoading && (!datasets || datasets.length === 0) && (
          <EmptyState title="还没有登记任何数据集。" description="上传 CSV 或 Excel 文件后，这里会显示数据版本和解析状态。" />
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
          disabled={!hasReadyDataset || complete.isPending}

        >
          {complete.isPending ? "推进中…" : "完成数据集收集"}
        </button>
        {!hasReadyDataset && (
          <span >
            至少需要一个已就绪（READY）的数据集才能完成收集
          </span>
        )}
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
