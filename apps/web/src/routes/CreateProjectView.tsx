import { useState } from "react";
import { useCreateProject } from "../features/projects/hooks";

export function CreateProjectView({ onCreated }: { onCreated: (id: string) => void }) {
  const create = useCreateProject();
  const [name, setName] = useState("胃病数据分析");
  const [topic, setTopic] = useState("胃病数据分析");
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrMsg(null);
    create.mutate(
      { name, topic },
      {
        onSuccess: (project) => {
          onCreated(project.id);
        },
        onError: (err: unknown) => {
          const msg =
            (err as { message?: string })?.message ?? "创建失败，请稍后重试";
          setErrMsg(msg);
        },
      }
    );
  };

  return (
    <div style={{ maxWidth: 480, margin: "0 auto", padding: "2rem 1rem" }}>
      <h1 style={{ fontSize: "1.5rem", marginBottom: "1.5rem" }}>创建实验项目</h1>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: "1rem" }}>
          <label style={{ display: "block", marginBottom: "0.25rem", fontWeight: 500 }}>项目名称</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="例如：胃病数据分析"
            style={{ width: "100%", padding: "0.5rem", fontSize: "1rem", boxSizing: "border-box" }}
          />
        </div>
        <div style={{ marginBottom: "1rem" }}>
          <label style={{ display: "block", marginBottom: "0.25rem", fontWeight: 500 }}>课题</label>
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="老师指定的课题"
            style={{ width: "100%", padding: "0.5rem", fontSize: "1rem", boxSizing: "border-box" }}
          />
        </div>
        {errMsg && (
          <div style={{ color: "#c00", marginBottom: "1rem", fontSize: "0.9rem" }}>
            {errMsg}
          </div>
        )}
        <button
          type="submit"
          disabled={create.isPending}
          style={{
            padding: "0.5rem 1.5rem",
            fontSize: "1rem",
            cursor: create.isPending ? "not-allowed" : "pointer",
          }}
        >
          {create.isPending ? "创建中…" : "创建项目"}
        </button>
      </form>
    </div>
  );
}
