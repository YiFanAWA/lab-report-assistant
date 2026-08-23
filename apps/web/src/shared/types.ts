/** 项目合同 — 与后端 ProjectResponse 对应。 */
export interface Project {
  id: string;
  name: string;
  topic: string;
  status: string;
  created_at: string;
  updated_at: string;
}

/** 项目列表响应。 */
export interface ProjectListResponse {
  items: Project[];
}

/** 创建项目请求体。 */
export interface ProjectCreateRequest {
  name: string;
  topic: string;
}

/** 后端结构化错误。 */
export interface ApiError {
  error: {
    code: string;
    message: string;
    field: string | null;
  };
}

export interface WorkspaceBlockingReason {
  code: string;
  message: string;
  source: string;
  /** 规范合同字段；旧客户端 fixture 可省略。 */
  kind?: "LOCKED" | "BLOCKED" | "FAILED";
  display_message?: string | null;
}

export interface WorkspaceStageProjection {
  id: string;
  label: string;
  route: string;
  state: string;
  phase_id: string;
  phase_label: string;
  is_substep: boolean;
  blocking_reasons: WorkspaceBlockingReason[];
}

export type WorkspaceProgressStatus =
  | "LOCKED"
  | "READY"
  | "IN_PROGRESS"
  | "BLOCKED"
  | "FAILED"
  | "COMPLETED";

export interface WorkspaceProgressAction {
  id: string;
  kind: "NAVIGATE" | "COMMAND";
  label: string;
  description: string;
  enabled: boolean;
  disabled_reason: WorkspaceBlockingReason | null;
  route: string | null;
  command_id: string | null;
}

export interface WorkspaceProgressDisplay {
  status_label: string;
  next_step_text: string;
}

export interface WorkspaceProgressStep {
  id: string;
  label: string;
  description: string;
  is_substep: boolean;
  status: WorkspaceProgressStatus;
  is_open: boolean;
  open_reason: WorkspaceBlockingReason | null;
  blocking_reasons: WorkspaceBlockingReason[];
  display: WorkspaceProgressDisplay;
  route: string;
  command_id: string;
  actions: WorkspaceProgressAction[];
  recovery_action: WorkspaceProgressAction | null;
}

export interface WorkspaceProgressPhase {
  id: string;
  label: string;
  description: string;
  status: WorkspaceProgressStatus;
  is_open: boolean;
  open_reason: WorkspaceBlockingReason | null;
  blocking_reasons: WorkspaceBlockingReason[];
  display: WorkspaceProgressDisplay;
  steps: WorkspaceProgressStep[];
  actions: WorkspaceProgressAction[];
}

export interface WorkspaceProgressCurrent {
  phase_id: string;
  phase_label: string;
  step_id: string;
  label: string;
  status: WorkspaceProgressStatus;
}

export interface WorkspaceProjection {
  project_id: string;
  project: {
    id: string;
    name: string;
    topic: string;
    status: string;
    status_label: string;
    updated_at: string;
  };
  current: WorkspaceProgressCurrent;
  phases: WorkspaceProgressPhase[];
  recommended_next_action: WorkspaceProgressAction | null;

  // 兼容旧客户端的同接口字段。
  current_stage: WorkspaceStageProjection;
  next_action: {
    stage_id: string;
    label: string;
    route: string;
    reason: string;
  } | null;
  stages: WorkspaceStageProjection[];
  projection_generated_at: string;
}