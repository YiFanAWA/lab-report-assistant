import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

const STATUS_LABELS: Record<string, string> = {
  PENDING: "等待处理",
  RUNNING: "正在处理",
  SUCCEEDED: "已完成",
  FAILED: "需要处理",
  STALE: "已失效",
  CANCELLED: "已取消",
  DRAFT: "草稿",
  REQUIREMENT_PARSED: "要求已解析",
  REQUIREMENT_CONFIRMED: "需求已确认",
  SOURCES_COLLECTED: "来源已收集",
  EVIDENCE_CONFIRMED: "证据已确认",
  DATASET_READY: "数据集已就绪",
  ANALYSIS_PLANNED: "分析方案已生成",
  ANALYSIS_CONFIRMED: "分析方案已确认",
  EXECUTING: "正在执行",
  EXECUTION_FAILED: "需要处理",
  RESULT_CONFIRMED: "结果已确认",
  OUTLINE_CONFIRMED: "大纲已确认",
  GENERATING: "正在生成",
  COMPLETED: "已完成",
};

const STATUS_TONES: Record<string, string> = {
  PENDING: "neutral",
  RUNNING: "accent",
  SUCCEEDED: "success",
  FAILED: "danger",
  STALE: "warning",
  CANCELLED: "neutral",
  DRAFT: "neutral",
  REQUIREMENT_PARSED: "info",
  REQUIREMENT_CONFIRMED: "accent",
  SOURCES_COLLECTED: "accent",
  EVIDENCE_CONFIRMED: "success",
  DATASET_READY: "success",
  ANALYSIS_PLANNED: "info",
  ANALYSIS_CONFIRMED: "success",
  EXECUTING: "accent",
  EXECUTION_FAILED: "danger",
  RESULT_CONFIRMED: "success",
  OUTLINE_CONFIRMED: "success",
  GENERATING: "accent",
  COMPLETED: "success",
};

export function statusLabel(status: string, fallback = status) {
  return STATUS_LABELS[status] ?? fallback;
}

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
}) {
  return (
    <button
      {...props}
      className={["button", "workspace-ui-button", `workspace-ui-button--${variant}`, `workspace-ui-button--${size}`, className]
        .filter(Boolean)
        .join(" ")}
    />
  );
}

export function StatusBadge({
  status,
  label,
  className = "",
}: {
  status: string;
  label?: string;
  className?: string;
}) {
  const tone = STATUS_TONES[status] ?? "neutral";
  return (
    <span className={[`workspace-ui-status workspace-ui-status--${tone}`, className].filter(Boolean).join(" ")}>
      <span className="workspace-ui-status__dot" aria-hidden="true" />
      {label ?? statusLabel(status)}
    </span>
  );
}

export function Card({
  as: Component = "section",
  className = "",
  children,
}: {
  as?: "section" | "div" | "article";
  className?: string;
  children: ReactNode;
}) {
  return <Component className={[`workspace-ui-card`, className].filter(Boolean).join(" ")}>{children}</Component>;
}

export function EmptyState({
  title,
  description,
  action,
  className = "",
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={[`workspace-ui-empty`, className].filter(Boolean).join(" ")}>
      <span className="workspace-ui-empty__mark" aria-hidden="true">＋</span>
      <div>
        <h3>{title}</h3>
        {description && <p>{description}</p>}
        {action && <div className="workspace-ui-empty__action">{action}</div>}
      </div>
    </div>
  );
}

export function ErrorPanel({
  title = "需要处理",
  message,
  code,
  jobId,
  className = "",
}: {
  title?: string;
  message: string;
  code?: string | null;
  jobId?: string | null;
  className?: string;
}) {
  return (
    <div className={[`workspace-ui-error`, className].filter(Boolean).join(" ")} role="alert">
      <div className="workspace-ui-error__mark" aria-hidden="true">!</div>
      <div className="workspace-ui-error__body">
        <h3>{title}</h3>
        <p>{message}</p>
        {(code || jobId) && (
          <details>
            <summary>技术详情</summary>
            {code && <div>错误码：{code}</div>}
            {jobId && <div>任务 ID：{jobId}</div>}
          </details>
        )}
      </div>
    </div>
  );
}

export function LoadingState({
  label = "加载中…",
  className = "",
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div className={[`workspace-ui-loading`, className].filter(Boolean).join(" ")} role="status" aria-live="polite">
      <span className="workspace-ui-loading__bar" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function JobProgress({
  status,
  label = "后台任务",
  jobId,
  errorCode,
  errorMessage,
}: {
  status: string;
  label?: string;
  jobId?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
}) {
  const needsDetails = Boolean(jobId || errorCode);
  return (
    <div className={[`workspace-ui-job`, `workspace-ui-job--${(STATUS_TONES[status] ?? "neutral")}`].join(" ")}>
      <StatusBadge status={status} label={`${label}：${statusLabel(status)}`} />
      {errorMessage && <p>{errorMessage}</p>}
      {needsDetails && (
        <details>
          <summary>技术详情</summary>
          {errorCode && <div>错误码：{errorCode}</div>}
          {jobId && <div>任务 ID：{jobId}</div>}
        </details>
      )}
    </div>
  );
}

export function ConfirmFooter({
  actionLabel,
  pendingLabel = "处理中…",
  disabled = false,
  pending = false,
  helper,
  error,
  success,
  onConfirm,
}: {
  actionLabel: string;
  pendingLabel?: string;
  disabled?: boolean;
  pending?: boolean;
  helper?: string;
  error?: string | null;
  success?: string | null;
  onConfirm: () => void;
}) {
  return (
    <footer className="workspace-ui-confirm-footer">
      <div>
        {helper && <p>{helper}</p>}
        {error && <p className="workspace-ui-confirm-footer__error" role="alert">{error}</p>}
        {success && <p className="workspace-ui-confirm-footer__success">{success}</p>}
      </div>
      <Button onClick={onConfirm} disabled={disabled || pending}>
        {pending ? pendingLabel : actionLabel}
      </Button>
    </footer>
  );
}

export function Field({
  label,
  hint,
  error,
  required = false,
  children,
}: {
  label: string;
  hint?: string;
  error?: string | null;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <label className={[`workspace-ui-field`, error ? "workspace-ui-field--error" : ""].filter(Boolean).join(" ")}>
      <span className="workspace-ui-field__label">
        {label}{required && <em aria-hidden="true">*</em>}
      </span>
      {children}
      {hint && !error && <span className="workspace-ui-field__hint">{hint}</span>}
      {error && <FieldError message={error} />}
    </label>
  );
}

export function FieldError({ message }: { message: string }) {
  return <span className="workspace-ui-field__error" role="alert">{message}</span>;
}

export type FieldControlProps =
  | InputHTMLAttributes<HTMLInputElement>
  | TextareaHTMLAttributes<HTMLTextAreaElement>
  | SelectHTMLAttributes<HTMLSelectElement>;