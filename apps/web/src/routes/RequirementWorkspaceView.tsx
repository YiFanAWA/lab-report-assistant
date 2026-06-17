import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { useProject } from "../features/projects/hooks";
import {
  useSources,
  useAddTextSource,
  useAddDocxSource,
  useCurrentPlan,
  useGeneratePlan,
  useUpdatePlan,
  useConfirmPlan,
} from "../features/requirements/hooks";
import type { RequirementTask, RequirementPlanPayload } from "../features/requirements/types";

function statusLabel(s: string) {
  const m: Record<string, string> = {
    DRAFT: "草稿",
    REQUIREMENT_PARSED: "要求已解析",
    REQUIREMENT_CONFIRMED: "需求已确认",
    COMPLETED: "已完成",
  };
  return m[s] ?? s;
}

function taskTypeLabel(t: string) {
  const m: Record<string, string> = {
    REQUIRED: "必须",
    RECOMMENDED: "推荐",
    OPTIONAL: "可选",
    OUT_OF_SCOPE: "超范围",
    UNKNOWN: "待确认",
  };
  return m[t] ?? t;
}

function errorMessage(e: unknown, fallback: string) {
  if (typeof e === "object" && e !== null && "message" in e) {
    const message = (e as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return fallback;
}

function TaskList({ tasks, label, color }: { tasks: RequirementTask[]; label: string; color: string }) {
  if (!tasks.length) return null;
  return (
    <div style={{ marginBottom: "1rem" }}>
      <h4 style={{ margin: "0 0 0.25rem", color }}>{label}</h4>
      {tasks.map((t, i) => (
        <div key={i} style={{ marginLeft: "1rem", marginBottom: "0.5rem" }}>
          <strong>{t.title}</strong>
          <div style={{ fontSize: "0.85rem", color: "#666" }}>{t.description}</div>
          {t.source_quote && (
            <div style={{ fontSize: "0.8rem", color: "#999" }}>来源: {t.source_quote}</div>
          )}
        </div>
      ))}
    </div>
  );
}

export function RequirementWorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const pid = projectId!;
  const { data: project, isLoading: projLoading } = useProject(pid);
  const { data: sources, isLoading: srcLoading } = useSources(pid);
  const { data: plan, isLoading: planLoading } = useCurrentPlan(pid);

  const [pasteTitle, setPasteTitle] = useState("老师实验要求");
  const [pasteText, setPasteText] = useState("");
  const [textErr, setTextErr] = useState<string | null>(null);
  const [docxTitle, setDocxTitle] = useState("老师实验要求文档");
  const [docxFile, setDocxFile] = useState<File | null>(null);
  const [docxErr, setDocxErr] = useState<string | null>(null);

  const addSource = useAddTextSource(pid);
  const addDocx = useAddDocxSource(pid);
  const generate = useGeneratePlan(pid);
  const updatePlan = useUpdatePlan(pid);
  const confirm = useConfirmPlan(pid);

  const [genErr, setGenErr] = useState<string | null>(null);
  const [editErr, setEditErr] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editPayload, setEditPayload] = useState<RequirementPlanPayload | null>(null);

  useEffect(() => {
    setEditPayload(plan?.payload ?? null);
    setIsEditing(false);
    setEditErr(null);
  }, [plan?.id, plan?.updated_at]);

  if (projLoading) return <p style={{ padding: "2rem" }}>加载中…</p>;
  if (!project) return <p style={{ padding: "2rem", color: "#c00" }}>项目不存在</p>;

  const hasSources = sources && sources.length > 0;
  const shownPayload = isEditing && editPayload ? editPayload : plan?.payload;

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "1.5rem 1rem" }}>
      <Link to={`/projects/${pid}`} style={{ fontSize: "0.85rem", color: "#2563eb" }}>
        ← 项目详情
      </Link>

      <h1 style={{ fontSize: "1.3rem", marginTop: "0.75rem" }}>
        {project.name} <span style={{ fontSize: "0.8rem", color: "#888" }}>[{statusLabel(project.status)}]</span>
      </h1>

      {/* 粘贴要求 */}
      <section style={{ marginTop: "1.5rem", padding: "1rem", border: "1px solid #e5e7eb", borderRadius: "0.5rem" }}>
        <h3 style={{ margin: "0 0 0.5rem" }}>添加实验要求</h3>
        <input
          value={pasteTitle}
          onChange={(e) => setPasteTitle(e.target.value)}
          placeholder="来源标题"
          style={{ width: "100%", padding: "0.4rem", marginBottom: "0.5rem", boxSizing: "border-box" }}
        />
        <textarea
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
          placeholder="粘贴老师给的实验要求…"
          rows={5}
          style={{ width: "100%", padding: "0.4rem", boxSizing: "border-box" }}
        />
        <button
          onClick={() => {
            setTextErr(null);
            if (!pasteText.trim()) return;
            addSource.mutate(
              { title: pasteTitle, text: pasteText },
              {
                onSuccess: () => setPasteText(""),
                onError: (e) => setTextErr(errorMessage(e, "保存失败")),
              }
            );
          }}
          disabled={addSource.isPending}
          style={{ marginTop: "0.5rem", padding: "0.4rem 1rem" }}
        >
          {addSource.isPending ? "保存中…" : "保存要求"}
        </button>
        {addSource.data && <p style={{ color: "#16a34a", fontSize: "0.85rem" }}>已保存 ✓</p>}
        {textErr && <p style={{ color: "#c00", fontSize: "0.85rem" }}>{textErr}</p>}

        <div style={{ marginTop: "1rem", borderTop: "1px solid #e5e7eb", paddingTop: "1rem" }}>
          <input
            value={docxTitle}
            onChange={(e) => setDocxTitle(e.target.value)}
            placeholder="Word 来源标题"
            style={{ width: "100%", padding: "0.4rem", marginBottom: "0.5rem", boxSizing: "border-box" }}
          />
          <input
            type="file"
            accept=".docx"
            onChange={(e) => setDocxFile(e.target.files?.[0] ?? null)}
            style={{ display: "block", marginBottom: "0.5rem" }}
          />
          <button
            onClick={() => {
              setDocxErr(null);
              if (!docxFile) {
                setDocxErr("请选择 .docx 文件");
                return;
              }
              addDocx.mutate(
                { title: docxTitle, file: docxFile },
                {
                  onSuccess: () => setDocxFile(null),
                  onError: (e) => setDocxErr(errorMessage(e, "上传失败")),
                }
              );
            }}
            disabled={addDocx.isPending}
            style={{ padding: "0.4rem 1rem" }}
          >
            {addDocx.isPending ? "上传中…" : "上传 Word 要求"}
          </button>
          {addDocx.data && <p style={{ color: "#16a34a", fontSize: "0.85rem" }}>Word 要求已保存 ✓</p>}
          {docxErr && <p style={{ color: "#c00", fontSize: "0.85rem" }}>{docxErr}</p>}
        </div>
      </section>

      {/* 已保存的来源 */}
      {hasSources && (
        <section style={{ marginTop: "1rem" }}>
          <h3>已保存的原始要求</h3>
          {sources!.map((s) => (
            <div key={s.id} style={{ padding: "0.5rem", borderBottom: "1px solid #eee", fontSize: "0.85rem" }}>
              <strong>{s.title}</strong> ({s.source_type})
              <div style={{ color: "#666", whiteSpace: "pre-wrap", maxHeight: 100, overflow: "auto" }}>
                {s.original_text.slice(0, 200)}{s.original_text.length > 200 ? "…" : ""}
              </div>
            </div>
          ))}

          {/* 生成任务单 */}
          <div style={{ marginTop: "1rem" }}>
            <button
              onClick={() => {
                setGenErr(null);
                const srcId = sources![0].id;
                generate.mutate(srcId, {
                  onError: (e) => setGenErr(errorMessage(e, "生成失败")),
                });
              }}
              disabled={generate.isPending}
              style={{ padding: "0.5rem 1rem" }}
            >
              {generate.isPending ? "生成中…" : "生成任务单候选"}
            </button>
            {genErr && <p style={{ color: "#c00", fontSize: "0.85rem" }}>{genErr}</p>}
          </div>
        </section>
      )}

      {/* 任务单 */}
      {plan && shownPayload && (
        <section
          style={{
            marginTop: "1.5rem",
            padding: "1rem",
            border: `1px solid ${plan.status === "CONFIRMED" ? "#16a34a" : "#f59e0b"}`,
            borderRadius: "0.5rem",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0 }}>
              任务单
              <span style={{ fontSize: "0.8rem", marginLeft: "0.5rem", color: "#888" }}>
                [{plan.status === "CANDIDATE" ? "待确认" : "已确认"}] [{plan.candidate_source}]
              </span>
            </h3>
            {plan.status === "CANDIDATE" && (
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button
                  onClick={() => {
                    setEditPayload(plan.payload);
                    setIsEditing((v) => !v);
                    setEditErr(null);
                  }}
                  style={{ padding: "0.4rem 0.8rem", fontSize: "0.85rem" }}
                >
                  {isEditing ? "取消编辑" : "编辑任务单"}
                </button>
                {isEditing && editPayload && (
                  <button
                    onClick={() => {
                      setEditErr(null);
                      updatePlan.mutate(
                        { planId: plan.id, payload: editPayload },
                        {
                          onSuccess: () => setIsEditing(false),
                          onError: (e) => setEditErr(errorMessage(e, "保存任务单失败")),
                        }
                      );
                    }}
                    disabled={updatePlan.isPending}
                    style={{ padding: "0.4rem 0.8rem", fontSize: "0.85rem" }}
                  >
                    {updatePlan.isPending ? "保存中…" : "保存修改"}
                  </button>
                )}
                <button
                  onClick={() => confirm.mutate(plan.id)}
                  disabled={confirm.isPending || updatePlan.isPending}
                  style={{ padding: "0.4rem 0.8rem", fontSize: "0.85rem" }}
                >
                  {confirm.isPending ? "确认中…" : "确认任务单"}
                </button>
              </div>
            )}
          </div>

          {plan.status === "CANDIDATE" && (
            <p style={{ color: "#92400e", fontSize: "0.85rem", marginBottom: 0 }}>
              确认前仍可修改；确认后项目状态将推进为需求已确认。
            </p>
          )}
          {editErr && <p style={{ color: "#c00", fontSize: "0.85rem" }}>{editErr}</p>}

          {isEditing && editPayload && (
            <div style={{ marginTop: "0.75rem", padding: "0.75rem", background: "#f9fafb", borderRadius: "0.375rem" }}>
              <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.5rem" }}>
                课题
                <input
                  value={editPayload.topic}
                  onChange={(e) => setEditPayload({ ...editPayload, topic: e.target.value })}
                  style={{ display: "block", width: "100%", padding: "0.4rem", boxSizing: "border-box" }}
                />
              </label>
              <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.5rem" }}>
                实验类型
                <input
                  value={editPayload.experiment_type}
                  onChange={(e) => setEditPayload({ ...editPayload, experiment_type: e.target.value })}
                  style={{ display: "block", width: "100%", padding: "0.4rem", boxSizing: "border-box" }}
                />
              </label>
              <label style={{ display: "block", fontSize: "0.85rem" }}>
                研究对象
                <textarea
                  value={editPayload.research_subject}
                  onChange={(e) => setEditPayload({ ...editPayload, research_subject: e.target.value })}
                  rows={3}
                  style={{ display: "block", width: "100%", padding: "0.4rem", boxSizing: "border-box" }}
                />
              </label>
            </div>
          )}

          <div style={{ marginTop: "0.75rem" }}>
            <div><strong>课题:</strong> {shownPayload.topic}</div>
            <div><strong>实验类型:</strong> {shownPayload.experiment_type}</div>
            <div><strong>研究对象:</strong> {shownPayload.research_subject}</div>

            {shownPayload.replication_level && (
              <div style={{ padding: "0.5rem", background: "#f0f9ff", borderRadius: "0.25rem", marginTop: "0.5rem" }}>
                <strong>论文复刻层级:</strong> {shownPayload.replication_level.level} —{" "}
                {shownPayload.replication_level.label}
                {!shownPayload.replication_level.supported_in_v1 && (
                  <span style={{ color: "#c00" }}>（第一版不支持）</span>
                )}
                <div style={{ fontSize: "0.85rem", color: "#666" }}>
                  {shownPayload.replication_level.reason}
                </div>
              </div>
            )}
          </div>

          <div style={{ marginTop: "1rem" }}>
            <TaskList tasks={shownPayload.required_tasks} label="必须任务" color="#2563eb" />
            <TaskList tasks={shownPayload.recommended_tasks} label="推荐任务" color="#16a34a" />
            <TaskList tasks={shownPayload.optional_tasks} label="可选任务" color="#6b7280" />
            <TaskList tasks={shownPayload.out_of_scope_tasks} label="超范围任务" color="#dc2626" />
            <TaskList tasks={shownPayload.unknown_items} label="待确认" color="#f59e0b" />
          </div>

          {shownPayload.acceptance_criteria.length > 0 && (
            <div style={{ marginTop: "0.5rem" }}>
              <strong>验收条件:</strong>
              <ul style={{ margin: "0.25rem 0", fontSize: "0.85rem" }}>
                {shownPayload.acceptance_criteria.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
