import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useProject, useWorkspaceProjection } from "../features/projects/hooks";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";
import { EmptyState, ErrorPanel, LoadingState } from "../components/workspace/WorkspaceUI";
import {
  useOutlines,
  useGenerateOutline,
  useStreamGenerateOutline,
  useUpdateOutline,
  useConfirmOutline,
  useRejectOutline,
  useGenerateWord,
  useGeneratePpt,
  useWordTemplate,
  useUploadWordTemplate,
  useDeleteWordTemplate,
} from "../features/outlines/hooks";
import { buildWordTemplateDownloadUrl } from "../features/outlines/api";
import { useJob } from "../features/jobs/hooks";
import type { Outline, OutlineSection, PptConfig } from "../features/outlines/types";
import { PPT_THEME_COLORS, PPT_WORKFLOWS } from "../features/outlines/types";

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
    PENDING: "等待处理",
    RUNNING: "正在处理",
    SUCCEEDED: "已完成",
    FAILED: "需要处理",
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
  const [editOk, setEditOk] = useState<string | null>(null);
  const [wordErr, setWordErr] = useState<string | null>(null);
  const [pptErr, setPptErr] = useState<string | null>(null);
  const [wordOk, setWordOk] = useState<string | null>(null);
  const [pptOk, setPptOk] = useState<string | null>(null);

  // SPEC 0011：PPT 配置状态
  const [pptTargetSlideCount, setPptTargetSlideCount] = useState<string>("");
  const [pptThemeColor, setPptThemeColor] = useState<string | null>(null);
  const [pptIncludeCharts, setPptIncludeCharts] = useState(true);
  const [pptWorkflow, setPptWorkflow] = useState<PptConfig["ppt_workflow"]>(
    "academic",
  );

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
    setEditOk(null);
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
  const outlineStepOpen = isConfirmed;

  return (
    <div

    >
      <div

      >
        <strong >
          大纲 v{outline.version} [{outlineStatusLabel(outline.status)}]
          <span >
            · 来源：{candidateSourceLabel(outline.candidate_source)}
          </span>
        </strong>
        <span >
          创建：{new Date(outline.created_at).toLocaleString("zh-CN")}
          {outline.confirmed_at &&
            ` · 确认：${new Date(outline.confirmed_at).toLocaleString("zh-CN")}`}
        </span>
      </div>

      {isStale && (
        <div

        >
          关联执行结果已变化，此大纲已失效，请重新生成或编辑后确认。
        </div>
      )}

      {/* 章节列表 */}
      <div >
        {!isEditing ? (
          outline.sections.map((sec, i) => (
            <SectionView key={sec.id ?? i} section={sec} />
          ))
        ) : (
          <div

          >
            {sectionsDraft.map((sec, i) => (
              <div key={sec.id ?? i} >
                <input
                  value={sec.title}
                  onChange={(e) => {
                    const next = [...sectionsDraft];
                    next[i] = { ...sec, title: e.target.value };
                    setSectionsDraft(next);
                  }}
                  placeholder="章节标题"

                />
                <select
                  value={sec.source_type}
                  onChange={(e) => {
                    const next = [...sectionsDraft];
                    next[i] = { ...sec, source_type: e.target.value };
                    setSectionsDraft(next);
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

                />
              </div>
            ))}
          </div>
        )}
      </div>

      {editErr && (
        <div >
          {editErr}
        </div>
      )}
      {editOk && (
        <div >
          {editOk}
        </div>
      )}

      {/* 操作按钮 */}
      <div >
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
                : "编辑大纲"}
            </button>
            {isEditing && (
              <button
                onClick={() => {
                  setSectionsDraft(outline.sections.map((s) => ({ ...s })));
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
            onClick={() => confirmMutation.mutate(outline.id)}
            disabled={confirmMutation.isPending}

          >
            {confirmMutation.isPending ? "确认中…" : "确认大纲"}
          </button>
        )}
        {canReject && (
          <button
            onClick={() => rejectMutation.mutate(outline.id)}
            disabled={rejectMutation.isPending}

          >
            {rejectMutation.isPending ? "拒绝中…" : "拒绝大纲"}
          </button>
        )}
      </div>

      {/* Word/PPT 生成 */}
      {outlineStepOpen && (
        <div

        >
          <h4 >
            触发交付物生成
          </h4>
          <div >
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
                const config: PptConfig = {
                  target_slide_count: pptTargetSlideCount
                    ? Number(pptTargetSlideCount)
                    : null,
                  theme_color: pptThemeColor,
                  include_charts: pptIncludeCharts,
                  ppt_workflow: pptWorkflow,
                };
                pptMutation.mutate(
                  { outlineId: outline.id, config },
                  {
                    onSuccess: (data) => {
                      setPptJobId(data.job_id);
                    },
                    onError: (e) =>
                      setPptErr(errorMessage(e, "触发 PPT 生成失败")),
                  }
                );
              }}
              disabled={pptMutation.isPending || !!pptJobId}

            >
              {pptMutation.isPending
                ? "提交中…"
                : pptJobId
                ? "PPT 生成中…"
                : "生成 PPT"}
            </button>
          </div>
          {/* SPEC 0011：PPT 配置表单 */}
          {outline.status === "CONFIRMED" && !pptJobId && (
            <div

            >
              <div >
                PPT 配置
              </div>
              <label >
                目标页数（5-20，留空默认）：
                <input
                  type="number"
                  min={5}
                  max={20}
                  value={pptTargetSlideCount}
                  onChange={(e) => setPptTargetSlideCount(e.target.value)}
                  placeholder="如 10"

                />
              </label>
              <label >
                PPT 工作流：
                <select
                  value={pptWorkflow ?? "academic"}
                  onChange={(e) =>
                    setPptWorkflow(
                      e.target.value as PptConfig["ppt_workflow"],
                    )
                  }

                >
                  {PPT_WORKFLOWS.map((workflow) => (
                    <option key={workflow.id} value={workflow.id}>
                      {workflow.label}
                    </option>
                  ))}
                </select>
              </label>
              <label >
                主题色：
                <span >
                  {PPT_THEME_COLORS.map((color) => (
                    <span
                      key={color}
                      role="button"
                      aria-label={`选择主题色 ${color}`}
                      onClick={() =>
                        setPptThemeColor(pptThemeColor === color ? null : color)
                      }

                    />
                  ))}
                </span>
              </label>
              <label >
                <input
                  type="checkbox"
                  checked={pptIncludeCharts}
                  onChange={(e) => setPptIncludeCharts(e.target.checked)}
                />
                包含图表页
              </label>
            </div>
          )}
          {wordJobId && wordJob && (
            <p >
              {jobTypeLabel(wordJob.job_type)}：{jobStatusLabel(wordJob.status)}
              {(wordJob.status === "PENDING" || wordJob.status === "RUNNING") && "…"}
            </p>
          )}
          {pptJobId && pptJob && (
            <p >
              {jobTypeLabel(pptJob.job_type)}：{jobStatusLabel(pptJob.status)}
              {(pptJob.status === "PENDING" || pptJob.status === "RUNNING") && "…"}
            </p>
          )}
          {wordOk && (
            <p >
              {wordOk}
            </p>
          )}
          {wordErr && (
            <p >
              {wordErr}
            </p>
          )}
          {pptOk && (
            <p >
              {pptOk}
            </p>
          )}
          {pptErr && (
            <p >
              {pptErr}
            </p>
          )}
          <Link
            to={`/projects/${projectId}/deliverables`}

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

    >
      <div

      >
        <strong >{section.title}</strong>
        <span

        >
          {sourceTypeLabel(section.source_type)}
        </span>
      </div>
      <p

      >
        {section.content}
      </p>
      {section.source_ids.length > 0 && (
        <p >
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
  const { data: projection } = useWorkspaceProjection(pid);
  const { data: outlines, isLoading: outlinesLoading } = useOutlines(pid);

  const generate = useGenerateOutline(pid);
  // SPEC 0019：流式生成大纲
  const streamOutline = useStreamGenerateOutline(pid);

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

  if (projLoading) return <LoadingState />;
  if (!project) return <ErrorPanel message="项目不存在" />;

    const outlineStep = projection?.phases
    .flatMap((phase) => phase.steps)
    .find((step) => step.id === "outline");
  const outlineStepOpen = outlineStep?.is_open === true;
  const hasCandidate = (outlines ?? []).some(
    (o) => o.status === "CANDIDATE" || o.status === "CONFIRMED" || o.status === "STALE"
  );

  return (
    <WorkspaceShell project={project} projection={projection} title="报告大纲工作区">
      <div className="workspace-legacy-page">
      <Link to={`/projects/${pid}`} >
        ← 项目详情
      </Link>
      <Link
        to={`/projects/${pid}/deliverables`}

      >
        交付物工作区
      </Link>

      <h1 >
        工作区{" "}
        <span >
          [{projection?.project.status_label ?? project.status}]
        </span>
      </h1>
      <p >
        基于已确认的实验要求、证据卡片、数据概览、分析方案和执行结果生成统一大纲。
        Word 和 PPT 必须从同一份已确认大纲生成。
      </p>

      {/* 生成大纲候选 */}
      <section

      >
        <h3 >生成大纲候选</h3>
        {!outlineStepOpen ? (
          <p >
            项目当前状态为「{projection?.project.status_label ?? project.status}」，
            需要先推进到「结果已确认（RESULT_CONFIRMED）」才能生成大纲。
            请先在分析方案工作区完成确认并执行代码任务。
          </p>
        ) : hasCandidate ? (
          <p >
            当前已有候选或已确认大纲，可在下方编辑或确认。如需重新生成，请先拒绝现有候选。
          </p>
        ) : (
          <>
            <p >
              点击下方按钮生成大纲候选（本地规则提供者拼装 6 个章节）。
              流式按钮可实时看到 LLM 输出过程。
            </p>
            <div >
              <button
                onClick={() => {
                  setGenErr(null);
                  generate.mutate(undefined, {
                    onSuccess: (data) => setActiveJobId(data.job_id),
                    onError: (e) => setGenErr(errorMessage(e, "触发生成失败")),
                  });
                }}
                disabled={generate.isPending || !!activeJobId || streamOutline.streaming}

              >
                {generate.isPending || activeJobId
                  ? "生成中…"
                  : "生成大纲候选"}
              </button>
              {/* SPEC 0019：流式生成按钮 */}
              <button
                onClick={() => {
                  setGenErr(null);
                  streamOutline.start();
                }}
                disabled={generate.isPending || !!activeJobId || streamOutline.streaming}

              >
                {streamOutline.streaming ? "流式生成中…" : "流式生成大纲"}
              </button>
            </div>
            {activeJobId && genJob && (
              <p >
                {jobTypeLabel(genJob.job_type)}：{jobStatusLabel(genJob.status)}
                {(genJob.status === "PENDING" || genJob.status === "RUNNING") && "…"}
              </p>
            )}
            {genErr && (
              <p >
                {genErr}
              </p>
            )}

            {/* SPEC 0019：流式生成展示区 */}
            {streamOutline.streaming && (
              <div

              >
                <div

                >
                  <span >
                    正在逐 chunk 生成…
                  </span>
                  <button
                    onClick={streamOutline.cancel}

                  >
                    取消
                  </button>
                </div>
                <pre

                >
                  {streamOutline.chunks}
                </pre>
              </div>
            )}
            {streamOutline.result && (
              <p >
                流式生成完成 ✓ [{streamOutline.result.candidate_source}
                {streamOutline.result.fallback_used ? "（降级）" : ""}]
              </p>
            )}
            {streamOutline.error && (
              <div >
                <p >
                  流式生成失败：{streamOutline.error.message}
                  {streamOutline.error.partial_text && (
                    <span >（已保留部分生成内容）</span>
                  )}
                </p>
                {streamOutline.error.partial_text && (
                  <details >
                    <summary >
                      查看已生成内容
                    </summary>
                    <pre

                    >
                      {streamOutline.error.partial_text}
                    </pre>
                  </details>
                )}
              </div>
            )}
          </>
        )}
      </section>

      {/* 大纲列表 */}
      <section >
        <h3 >大纲列表</h3>
        {outlinesLoading && (
          <p >加载中…</p>
        )}
        {!outlinesLoading && (!outlines || outlines.length === 0) && (
          <EmptyState title="还没有生成任何大纲。" description="确认结果后生成报告大纲候选。" />
        )}
        {outlines && outlines.length > 0 && (
          <div>
            {outlines.map((o) => (
              <OutlineCard key={o.id} projectId={pid} outline={o} />
            ))}
          </div>
        )}
      </section>

      {/* SPEC 0010 Word 模板管理 */}
      <WordTemplateSection projectId={pid} />
    </div>
    </WorkspaceShell>
  );
}

/** Word 模板管理区域（SPEC 0010）。 */
function WordTemplateSection({ projectId }: { projectId: string }) {
  const { data: template, isLoading } = useWordTemplate(projectId);
  const uploadMutation = useUploadWordTemplate(projectId);
  const deleteMutation = useDeleteWordTemplate(projectId);
  const [uploadErr, setUploadErr] = useState<string | null>(null);
  const [deleteErr, setDeleteErr] = useState<string | null>(null);

  return (
    <section

    >
      <h3 >Word 模板</h3>
      <p >
        上传 .docx 模板后，生成 Word 时会使用该模板替代默认格式。
        模板支持占位符：{`{{project_name}}`}、{`{{project_topic}}`}、
        {`{{generated_date}}`}、{`{{#sections}}...{{/sections}}`} 章节循环。
        模板解析失败会自动降级到默认格式。
      </p>

      {isLoading && (
        <p >加载中…</p>
      )}

      {template && (
        <div

        >
          <div >
            <strong>{template.original_filename}</strong>
            <span >
              ({(template.file_size_bytes / 1024).toFixed(1)} KB)
            </span>
          </div>
          <div >
            上传时间：{new Date(template.created_at).toLocaleString("zh-CN")}
          </div>
          <div >
            <a
              href={buildWordTemplateDownloadUrl(projectId)}

            >
              下载模板
            </a>
            <button
              onClick={() => {
                setDeleteErr(null);
                deleteMutation.mutate(undefined, {
                  onError: (e) =>
                    setDeleteErr(errorMessage(e, "删除失败")),
                });
              }}
              disabled={deleteMutation.isPending}

            >
              {deleteMutation.isPending ? "删除中…" : "删除模板"}
            </button>
          </div>
          {deleteErr && (
            <p >
              {deleteErr}
            </p>
          )}
        </div>
      )}

      {!template && !isLoading && (
        <p >
          当前未上传 Word 模板，生成 Word 时使用默认格式。
        </p>
      )}

      {/* 上传表单 */}
      <div >
        <input
          type="file"
          accept=".docx"
          onChange={(e) => {
            setUploadErr(null);
            const file = e.target.files?.[0];
            if (!file) return;
            if (!file.name.toLowerCase().endsWith(".docx")) {
              setUploadErr("请选择 .docx 文件");
              return;
            }
            uploadMutation.mutate(file, {
              onError: (e) => setUploadErr(errorMessage(e, "上传失败")),
            });
          }}
          disabled={uploadMutation.isPending}

        />
        {uploadMutation.isPending && (
          <span >上传中…</span>
        )}
        {uploadMutation.isSuccess && (
          <span >已上传 ✓</span>
        )}
      </div>
      {uploadErr && (
        <p >
          {uploadErr}
        </p>
      )}
    </section>
  );
}
