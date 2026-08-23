import type {
  Project,
  WorkspaceProgressAction,
  WorkspaceProgressPhase,
  WorkspaceProgressStatus,
  WorkspaceProgressStep,
  WorkspaceProjection,
} from "../../shared/types";

const STEP_DEFINITIONS = [
  ["requirements", "实验要求", "requirements", "requirements"],
  ["sources", "资料来源", "sources_evidence", "sources"],
  ["evidence", "证据卡片", "sources_evidence", "evidence"],
  ["datasets", "数据上传", "datasets", "datasets"],
  ["analysis", "分析方案", "analysis", "analysis"],
  ["execution", "结果执行", "execution", "execution"],
  ["outline", "报告大纲", "outline", "outline"],
  ["deliverables", "正式交付物", "deliverables", "deliverables"],
] as const;

const PHASE_LABELS: Record<string, string> = {
  requirements: "实验要求",
  sources_evidence: "资料与证据",
  datasets: "数据上传",
  analysis: "分析方案",
  execution: "结果执行",
  outline: "报告大纲",
  deliverables: "正式交付物",
};

const STATUS_LABELS: Record<string, string> = {
  DRAFT: "草稿",
  REQUIREMENT_PARSED: "要求已解析",
  REQUIREMENT_CONFIRMED: "实验要求已确认",
  SOURCES_COLLECTED: "资料来源已收集",
  EVIDENCE_CONFIRMED: "证据卡片已确认",
  DATASET_READY: "数据集已就绪",
  ANALYSIS_PLANNED: "分析方案已生成",
  ANALYSIS_CONFIRMED: "分析方案已确认",
  EXECUTING: "正在执行",
  EXECUTION_FAILED: "执行需要处理",
  RESULT_CONFIRMED: "分析结果已确认",
  OUTLINE_CONFIRMED: "报告大纲已确认",
  GENERATING: "交付物正在生成",
  COMPLETED: "项目已完成",
};

const STATUS_TEXT: Record<WorkspaceProgressStatus, string> = {
  LOCKED: "未开放",
  READY: "待开始",
  IN_PROGRESS: "进行中",
  BLOCKED: "需处理",
  FAILED: "需要恢复",
  COMPLETED: "已完成",
};

function actionFor(
  project: Project,
  stepId: string,
  label: string,
  enabled: boolean,
): WorkspaceProgressAction {
  return {
    id: "open_" + stepId,
    kind: "NAVIGATE",
    label: "进入" + label + "工作区",
    description: "测试用导航动作",
    enabled,
    disabled_reason: enabled
      ? null
      : {
          code: "WORKSPACE_LOCKED",
          message: "请先完成前置阶段。",
          source: "projects",
          kind: "LOCKED",
          display_message: "请先完成前置阶段。",
        },
    route: "/projects/" + project.id + "/" + stepId,
    command_id: "workspace.open." + stepId,
  };
}

export function makeWorkspaceProjection(
  project: Project,
  openStepIds: string[] = STEP_DEFINITIONS.map(([id]) => id),
): WorkspaceProjection {
  const steps = STEP_DEFINITIONS.map(
    ([id, label, phaseId, workspace]): WorkspaceProgressStep => {
      const isOpen = openStepIds.includes(id);
      const status: WorkspaceProgressStatus = isOpen ? "READY" : "LOCKED";
      const route = "/projects/" + project.id + "/" + workspace;
      const action = actionFor(project, id, label, isOpen);
      return {
        id,
        label,
        description: "测试用工作区步骤",
        is_substep: phaseId === "sources_evidence",
        status,
        is_open: isOpen,
        open_reason: isOpen ? null : action.disabled_reason,
        blocking_reasons: [],
        display: {
          status_label: STATUS_TEXT[status],
          next_step_text: isOpen ? "进入工作区开始处理。" : "完成前置阶段后开放。",
        },
        route,
        command_id: "workspace.open." + id,
        actions: [action],
        recovery_action: null,
      };
    },
  );

  const phases: WorkspaceProgressPhase[] = [];
  for (const [id, label] of Object.entries(PHASE_LABELS)) {
    const phaseSteps = steps.filter((step) => {
      const definition = STEP_DEFINITIONS.find((item) => item[0] === step.id);
      return definition?.[2] === id;
    });
    const isOpen = phaseSteps.some((step) => step.is_open);
    const status: WorkspaceProgressStatus = isOpen ? "READY" : "LOCKED";
    phases.push({
      id,
      label,
      description: "测试用阶段",
      status,
      is_open: isOpen,
      open_reason: isOpen
        ? null
        : {
            code: "WORKSPACE_LOCKED",
            message: "请先完成前置阶段。",
            source: "projects",
            kind: "LOCKED",
            display_message: "请先完成前置阶段。",
          },
      blocking_reasons: [],
      display: {
        status_label: STATUS_TEXT[status],
        next_step_text: isOpen ? "进入工作区开始处理。" : "完成前置阶段后开放。",
      },
      steps: phaseSteps,
      actions: isOpen ? [phaseSteps.find((step) => step.is_open)!.actions[0]] : [],
    });
  }

  const currentStep = steps.find((step) => step.is_open) ?? steps[steps.length - 1];
  const currentPhase = phases.find((phase) =>
    phase.steps.some((step) => step.id === currentStep.id),
  )!;
  const recommendedNextAction =
    project.status === "COMPLETED" ? null : currentStep.actions[0];

  return {
    project_id: project.id,
    project: {
      id: project.id,
      name: project.name,
      topic: project.topic,
      status: project.status,
      status_label: STATUS_LABELS[project.status] ?? project.status,
      updated_at: project.updated_at,
    },
    current: {
      phase_id: currentPhase.id,
      phase_label: currentPhase.label,
      step_id: currentStep.id,
      label: currentStep.label,
      status: currentStep.status,
    },
    phases,
    recommended_next_action: recommendedNextAction,
    current_stage: {
      id: currentStep.id,
      label: currentStep.label,
      route: currentStep.route,
      state: currentStep.status,
      phase_id: currentPhase.id,
      phase_label: currentPhase.label,
      is_substep: currentStep.is_substep,
      blocking_reasons: [],
    },
    next_action: recommendedNextAction
      ? {
          stage_id: currentStep.id,
          label: recommendedNextAction.label,
          route: currentStep.route,
          reason: currentStep.display.next_step_text,
        }
      : null,
    stages: steps.map((step) => {
      const phase = phases.find((candidate) =>
        candidate.steps.some((phaseStep) => phaseStep.id === step.id),
      )!;
      return {
        id: step.id,
        label: step.label,
        route: step.route,
        state: step.status,
        phase_id: phase.id,
        phase_label: phase.label,
        is_substep: step.is_substep,
        blocking_reasons: [],
      };
    }),
    projection_generated_at: "2026-08-23T04:00:00Z",
  };
}
const STATUS_RANK: Record<string, number> = {
  DRAFT: 0,
  REQUIREMENT_PARSED: 1,
  REQUIREMENT_CONFIRMED: 2,
  SOURCES_COLLECTED: 3,
  EVIDENCE_CONFIRMED: 4,
  DATASET_READY: 5,
  ANALYSIS_PLANNED: 6,
  ANALYSIS_CONFIRMED: 7,
  EXECUTING: 8,
  EXECUTION_FAILED: 8,
  RESULT_CONFIRMED: 9,
  OUTLINE_CONFIRMED: 10,
  GENERATING: 11,
  COMPLETED: 12,
};

const STEP_UNLOCK_RANK: Record<string, number> = {
  requirements: 0,
  sources: 2,
  evidence: 3,
  datasets: 4,
  analysis: 5,
  execution: 7,
  outline: 9,
  deliverables: 10,
};

export function makeWorkspaceProjectionForStatus(
  project: Project,
): WorkspaceProjection {
  const rank = STATUS_RANK[project.status] ?? 0;
  const openStepIds = Object.entries(STEP_UNLOCK_RANK)
    .filter(([, unlockRank]) => rank >= unlockRank)
    .map(([stepId]) => stepId);
  return makeWorkspaceProjection(project, openStepIds);
}