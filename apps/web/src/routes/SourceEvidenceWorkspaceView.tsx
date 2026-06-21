import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { useProject } from "../features/projects/hooks";
import {
  useAddUrlSource,
  useConfirmEvidence,
  useEvidenceCards,
  useGenerateEvidence,
  useParsedDocument,
  useParseSource,
  useRejectEvidence,
  useSourceRecords,
  useUpdateEvidence,
  useUploadSourceFile,
} from "../features/sources/hooks";
import type {
  CollectionStatus,
  EvidenceCard,
  EvidenceStatus,
  EvidenceType,
  SourceRecord,
} from "../features/sources/types";

const cardStyle = {
  border: "1px solid #e5e7eb",
  borderRadius: "0.5rem",
  padding: "1rem",
  background: "#fff",
} as const;

const buttonStyle = {
  padding: "0.45rem 0.85rem",
  border: "1px solid #d1d5db",
  borderRadius: "0.375rem",
  background: "#fff",
  cursor: "pointer",
} as const;

const evidenceTypes: EvidenceType[] = [
  "BACKGROUND",
  "METHOD",
  "DATA_SOURCE",
  "METRIC",
  "RESULT",
  "LIMITATION",
  "DEFINITION",
  "REFERENCE",
];

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === "object" && error !== null && "message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return fallback;
}

function projectStatusLabel(status: string) {
  const labels: Record<string, string> = {
    DRAFT: "草稿",
    REQUIREMENT_PARSED: "要求已解析",
    REQUIREMENT_CONFIRMED: "需求已确认",
    SOURCES_COLLECTED: "资料已收集",
    EVIDENCE_CONFIRMED: "证据已确认",
    DATASET_READY: "数据集已就绪",
    ANALYSIS_PLANNED: "分析方案已生成",
    ANALYSIS_CONFIRMED: "分析方案已确认",
    EXECUTING: "正在执行",
    EXECUTION_FAILED: "执行失败",
    RESULT_CONFIRMED: "结果已确认",
    OUTLINE_CONFIRMED: "大纲已确认",
    GENERATING: "正在生成交付物",
    COMPLETED: "已完成",
  };
  return labels[status] ?? status;
}

function collectionStatusLabel(status: CollectionStatus) {
  const labels: Record<CollectionStatus, string> = {
    REGISTERED: "已登记",
    FETCHED: "已获取",
    PARSED: "已解析",
    BLOCKED: "已拦截",
    FAILED: "失败",
    UNSUPPORTED: "不支持",
  };
  return labels[status];
}

function evidenceStatusLabel(status: EvidenceStatus) {
  const labels: Record<EvidenceStatus, string> = {
    CANDIDATE: "候选",
    CONFIRMED: "已确认",
    REJECTED: "已拒绝",
    STALE: "已过期",
  };
  return labels[status];
}

function EvidenceEditor({ projectId, card }: { projectId: string; card: EvidenceCard }) {
  const update = useUpdateEvidence(projectId);
  const confirm = useConfirmEvidence(projectId);
  const reject = useRejectEvidence(projectId);
  const [summary, setSummary] = useState(card.summary);
  const [evidenceType, setEvidenceType] = useState<EvidenceType>(card.evidence_type);
  const [relevance, setRelevance] = useState(card.relevance_to_requirement);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSummary(card.summary);
    setEvidenceType(card.evidence_type);
    setRelevance(card.relevance_to_requirement);
  }, [card.id, card.summary, card.evidence_type, card.relevance_to_requirement]);

  const isCandidate = card.status === "CANDIDATE";
  const pending = update.isPending || confirm.isPending || reject.isPending;

  return (
    <article style={{ ...cardStyle, marginTop: "0.75rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "baseline" }}>
        <strong>{evidenceStatusLabel(card.status)}证据</strong>
        <span style={{ color: "#6b7280", fontSize: "0.8rem" }}>
          {card.location_label} · {card.candidate_source}
        </span>
      </div>
      {isCandidate && (
        <p style={{ margin: "0.5rem 0", color: "#92400e", fontSize: "0.85rem" }}>
          候选证据需要人工核对。
        </p>
      )}

      <label style={{ display: "block", marginTop: "0.65rem", fontSize: "0.85rem" }}>
        证据类型
        <select
          value={evidenceType}
          onChange={(event) => setEvidenceType(event.target.value as EvidenceType)}
          disabled={!isCandidate}
          style={{ display: "block", width: "100%", padding: "0.45rem", marginTop: "0.25rem" }}
        >
          {evidenceTypes.map((type) => <option key={type} value={type}>{type}</option>)}
        </select>
      </label>
      <label style={{ display: "block", marginTop: "0.65rem", fontSize: "0.85rem" }}>
        摘要
        <textarea
          value={summary}
          onChange={(event) => setSummary(event.target.value)}
          disabled={!isCandidate}
          rows={3}
          style={{ display: "block", width: "100%", padding: "0.45rem", marginTop: "0.25rem", boxSizing: "border-box" }}
        />
      </label>
      <div style={{ marginTop: "0.65rem", padding: "0.75rem", background: "#f9fafb", borderLeft: "3px solid #9ca3af", whiteSpace: "pre-wrap" }}>
        <div style={{ color: "#6b7280", fontSize: "0.78rem", marginBottom: "0.25rem" }}>原文摘录（只读）</div>
        {card.source_quote}
      </div>
      <label style={{ display: "block", marginTop: "0.65rem", fontSize: "0.85rem" }}>
        与任务单的相关性
        <textarea
          value={relevance}
          onChange={(event) => setRelevance(event.target.value)}
          disabled={!isCandidate}
          rows={2}
          style={{ display: "block", width: "100%", padding: "0.45rem", marginTop: "0.25rem", boxSizing: "border-box" }}
        />
      </label>

      {isCandidate && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.75rem" }}>
          <button
            type="button"
            disabled={pending}
            style={buttonStyle}
            onClick={() => {
              setError(null);
              update.mutate(
                { evidenceId: card.id, patch: { summary, evidence_type: evidenceType, relevance_to_requirement: relevance } },
                { onError: (caught) => setError(errorMessage(caught, "保存证据失败")) }
              );
            }}
          >
            {update.isPending ? "保存中…" : "保存修改"}
          </button>
          <button
            type="button"
            disabled={pending}
            style={{ ...buttonStyle, background: "#166534", color: "#fff", borderColor: "#166534" }}
            onClick={() => {
              setError(null);
              confirm.mutate(card.id, { onError: (caught) => setError(errorMessage(caught, "确认证据失败")) });
            }}
          >
            {confirm.isPending ? "确认中…" : "确认证据"}
          </button>
          <button
            type="button"
            disabled={pending}
            style={{ ...buttonStyle, color: "#b91c1c" }}
            onClick={() => {
              setError(null);
              reject.mutate(card.id, { onError: (caught) => setError(errorMessage(caught, "拒绝证据失败")) });
            }}
          >
            {reject.isPending ? "处理中…" : "拒绝"}
          </button>
        </div>
      )}
      {error && <p style={{ color: "#b91c1c", fontSize: "0.85rem" }}>{error}</p>}
    </article>
  );
}

function SourceRow({
  source,
  selected,
  onSelect,
  onParse,
  onGenerate,
  pending,
}: {
  source: SourceRecord;
  selected: boolean;
  onSelect: () => void;
  onParse: () => void;
  onGenerate: () => void;
  pending: boolean;
}) {
  return (
    <article style={{ ...cardStyle, marginTop: "0.75rem", borderColor: selected ? "#2563eb" : "#e5e7eb" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
        <div>
          <strong>{source.title}</strong>
          <div style={{ color: "#6b7280", fontSize: "0.82rem", marginTop: "0.2rem" }}>
            {source.source_kind === "PUBLIC_URL" ? "公开 URL" : "本地文件"} · {source.source_type} · {collectionStatusLabel(source.collection_status)}
          </div>
        </div>
        {source.size_bytes !== null && <span style={{ color: "#6b7280", fontSize: "0.78rem" }}>{source.size_bytes} bytes</span>}
      </div>
      {source.url && <div style={{ marginTop: "0.5rem", overflowWrap: "anywhere", fontSize: "0.82rem" }}>{source.url}</div>}
      {source.access_reason && <p style={{ color: "#b91c1c", fontSize: "0.85rem" }}>{source.access_reason}</p>}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.75rem" }}>
        {source.collection_status === "FETCHED" && source.source_type !== "CSV" && source.source_type !== "EXCEL" && (
          <button type="button" disabled={pending} style={buttonStyle} onClick={onParse}>解析文本</button>
        )}
        {source.collection_status === "PARSED" && (
          <>
            <button type="button" disabled={pending} style={buttonStyle} onClick={onSelect}>查看解析文本</button>
            <button
              type="button"
              disabled={pending}
              style={{ ...buttonStyle, background: "#2563eb", color: "#fff", borderColor: "#2563eb" }}
              onClick={onGenerate}
            >
              生成证据候选
            </button>
          </>
        )}
      </div>
    </article>
  );
}

export function SourceEvidenceWorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const pid = projectId ?? "";
  const projectQuery = useProject(pid);
  const sourceQuery = useSourceRecords(pid);
  const evidenceQuery = useEvidenceCards(pid);
  const addUrl = useAddUrlSource(pid);
  const uploadFile = useUploadSourceFile(pid);
  const parse = useParseSource(pid);
  const generate = useGenerateEvidence(pid);

  const [url, setUrl] = useState("");
  const [urlTitle, setUrlTitle] = useState("公开资料");
  const [file, setFile] = useState<File | null>(null);
  const [fileTitle, setFileTitle] = useState("本地辅助资料");
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [operationError, setOperationError] = useState<string | null>(null);

  const selectedSource = sourceQuery.data?.find((source) => source.id === selectedSourceId);
  const parsedQuery = useParsedDocument(
    pid,
    selectedSourceId,
    selectedSource?.collection_status === "PARSED"
  );

  useEffect(() => {
    if (!selectedSourceId) {
      const firstParsed = sourceQuery.data?.find((source) => source.collection_status === "PARSED");
      if (firstParsed) setSelectedSourceId(firstParsed.id);
    }
  }, [selectedSourceId, sourceQuery.data]);

  if (projectQuery.isLoading) return <p style={{ padding: "2rem" }}>加载中…</p>;
  if (projectQuery.isError || !projectQuery.data) {
    return <p style={{ padding: "2rem", color: "#b91c1c" }}>{errorMessage(projectQuery.error, "项目不存在")}</p>;
  }

  const project = projectQuery.data;
  const planConfirmed = !["DRAFT", "REQUIREMENT_PARSED"].includes(project.status);
  const pending = addUrl.isPending || uploadFile.isPending || parse.isPending || generate.isPending;

  return (
    <main style={{ maxWidth: 860, margin: "0 auto", padding: "1.5rem 1rem 3rem", color: "#111827" }}>
      <Link to={`/projects/${pid}`} style={{ color: "#2563eb", fontSize: "0.85rem" }}>← 项目详情</Link>
      <h1 style={{ fontSize: "1.45rem", margin: "0.75rem 0 0.25rem" }}>{project.name} · 公开资料与证据</h1>
      <p style={{ margin: 0, color: "#6b7280" }}>项目状态：{projectStatusLabel(project.status)}</p>
      {!planConfirmed && (
        <div style={{ marginTop: "1rem", padding: "0.8rem", background: "#fff7ed", color: "#9a3412", borderRadius: "0.5rem" }}>
          请先在实验要求工作区确认任务单；后端会阻止未确认项目登记来源。
        </div>
      )}

      <section style={{ ...cardStyle, marginTop: "1.25rem" }}>
        <h2 style={{ fontSize: "1.05rem", margin: 0 }}>1. 添加公开 URL</h2>
        <p style={{ color: "#6b7280", fontSize: "0.85rem" }}>仅支持无需登录、验证码或付费即可访问的 http/https 资料。</p>
        <input value={urlTitle} onChange={(event) => setUrlTitle(event.target.value)} placeholder="来源标题" style={{ width: "100%", padding: "0.5rem", boxSizing: "border-box", marginBottom: "0.5rem" }} />
        <input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://example.com/public" style={{ width: "100%", padding: "0.5rem", boxSizing: "border-box" }} />
        <button
          type="button"
          disabled={pending || !planConfirmed}
          style={{ ...buttonStyle, marginTop: "0.65rem" }}
          onClick={() => {
            setOperationError(null);
            if (!url.trim()) {
              setOperationError("请输入公开 URL");
              return;
            }
            addUrl.mutate(
              { url, title: urlTitle },
              {
                onSuccess: () => setUrl(""),
                onError: (caught) => setOperationError(errorMessage(caught, "URL 登记失败")),
              }
            );
          }}
        >
          {addUrl.isPending ? "获取中…" : "登记并获取"}
        </button>
      </section>

      <section style={{ ...cardStyle, marginTop: "1rem" }}>
        <h2 style={{ fontSize: "1.05rem", margin: 0 }}>2. 上传本地辅助资料</h2>
        <p style={{ color: "#6b7280", fontSize: "0.85rem" }}>支持 .pdf、.docx、.txt、.csv、.xlsx，单文件上限 20 MB。</p>
        <input value={fileTitle} onChange={(event) => setFileTitle(event.target.value)} placeholder="来源标题" style={{ width: "100%", padding: "0.5rem", boxSizing: "border-box", marginBottom: "0.5rem" }} />
        <input type="file" accept=".pdf,.docx,.txt,.csv,.xlsx" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        <button
          type="button"
          disabled={pending || !planConfirmed}
          style={{ ...buttonStyle, display: "block", marginTop: "0.65rem" }}
          onClick={() => {
            setOperationError(null);
            if (!file) {
              setOperationError("请选择本地辅助文件");
              return;
            }
            uploadFile.mutate(
              { file, title: fileTitle },
              {
                onSuccess: () => setFile(null),
                onError: (caught) => setOperationError(errorMessage(caught, "文件上传失败")),
              }
            );
          }}
        >
          {uploadFile.isPending ? "上传中…" : "上传资料"}
        </button>
      </section>

      {operationError && <p style={{ color: "#b91c1c", fontSize: "0.88rem" }}>{operationError}</p>}

      <section style={{ marginTop: "1.5rem" }}>
        <h2 style={{ fontSize: "1.1rem" }}>3. 来源与解析</h2>
        {sourceQuery.isLoading && <p>来源加载中…</p>}
        {sourceQuery.isError && <p style={{ color: "#b91c1c" }}>{errorMessage(sourceQuery.error, "来源加载失败")}</p>}
        {sourceQuery.data?.length === 0 && <p style={{ color: "#6b7280" }}>尚未添加资料。</p>}
        {sourceQuery.data?.map((source) => (
          <SourceRow
            key={source.id}
            source={source}
            selected={selectedSourceId === source.id}
            pending={pending}
            onSelect={() => setSelectedSourceId(source.id)}
            onParse={() => {
              setOperationError(null);
              parse.mutate(source.id, {
                onSuccess: () => setSelectedSourceId(source.id),
                onError: (caught) => setOperationError(errorMessage(caught, "来源解析失败")),
              });
            }}
            onGenerate={() => {
              setOperationError(null);
              setSelectedSourceId(source.id);
              generate.mutate(source.id, {
                onError: (caught) => setOperationError(errorMessage(caught, "证据候选生成失败")),
              });
            }}
          />
        ))}
      </section>

      {selectedSource?.collection_status === "PARSED" && (
        <section style={{ ...cardStyle, marginTop: "1rem", background: "#f9fafb" }}>
          <h3 style={{ marginTop: 0, fontSize: "1rem" }}>解析文本 · {selectedSource.title}</h3>
          {parsedQuery.isLoading && <p>解析文本加载中…</p>}
          {parsedQuery.isError && <p style={{ color: "#b91c1c" }}>{errorMessage(parsedQuery.error, "解析文本加载失败")}</p>}
          {parsedQuery.data && (
            <pre style={{ whiteSpace: "pre-wrap", maxHeight: 320, overflow: "auto", fontFamily: "inherit", fontSize: "0.85rem", lineHeight: 1.6 }}>
              {parsedQuery.data.parsed_text}
            </pre>
          )}
        </section>
      )}

      <section style={{ marginTop: "1.5rem" }}>
        <h2 style={{ fontSize: "1.1rem" }}>4. 证据卡片</h2>
        {evidenceQuery.isLoading && <p>证据加载中…</p>}
        {evidenceQuery.isError && <p style={{ color: "#b91c1c" }}>{errorMessage(evidenceQuery.error, "证据加载失败")}</p>}
        {evidenceQuery.data?.length === 0 && <p style={{ color: "#6b7280" }}>解析来源后，可生成需要人工核对的证据候选。</p>}
        {evidenceQuery.data?.map((card) => <EvidenceEditor key={card.id} projectId={pid} card={card} />)}
      </section>
    </main>
  );
}
