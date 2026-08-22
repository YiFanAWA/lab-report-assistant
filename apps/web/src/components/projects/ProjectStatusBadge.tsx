type ProjectStatusTone = "neutral" | "info" | "accent" | "success" | "warning" | "danger";

export interface ProjectStagePresentation {
  label: string;
  nextAction: string;
  tone: ProjectStatusTone;
}

const STAGE_PRESENTATIONS: Record<string, ProjectStagePresentation> = {
  DRAFT: { label: "草稿", nextAction: "录入实验要求", tone: "neutral" },
  REQUIREMENT_PARSED: { label: "要求已解析", nextAction: "确认实验要求", tone: "info" },
  REQUIREMENT_CONFIRMED: { label: "需求已确认", nextAction: "整理资料来源", tone: "info" },
  SOURCES_COLLECTED: { label: "来源已收集", nextAction: "确认证据卡片", tone: "info" },
  EVIDENCE_CONFIRMED: { label: "证据已确认", nextAction: "上传数据集", tone: "accent" },
  DATASET_READY: { label: "数据集已就绪", nextAction: "制定分析方案", tone: "accent" },
  ANALYSIS_PLANNED: { label: "分析方案已生成", nextAction: "确认分析方案", tone: "accent" },
  ANALYSIS_CONFIRMED: { label: "分析方案已确认", nextAction: "执行分析代码", tone: "accent" },
  EXECUTING: { label: "执行中", nextAction: "等待分析结果", tone: "warning" },
  EXECUTION_FAILED: { label: "执行失败", nextAction: "进入执行工作区查看失败原因", tone: "danger" },
  RESULT_CONFIRMED: { label: "结果已确认", nextAction: "确认报告大纲", tone: "info" },
  OUTLINE_CONFIRMED: { label: "大纲已确认", nextAction: "生成 Word / PPT 交付物", tone: "accent" },
  GENERATING: { label: "交付物生成中", nextAction: "等待 Word / PPT 完成", tone: "warning" },
  COMPLETED: { label: "已完成", nextAction: "查看项目交付物", tone: "success" },
};

export function getProjectStagePresentation(status: string): ProjectStagePresentation {
  return (
    STAGE_PRESENTATIONS[status] ?? {
      label: status,
      nextAction: "打开项目查看下一步",
      tone: "neutral",
    }
  );
}

export function ProjectStatusBadge({ status }: { status: string }) {
  const presentation = getProjectStagePresentation(status);

  return (
    <span className={`project-status-badge project-status-badge--${presentation.tone}`}>
      <span className="project-status-badge__dot" aria-hidden="true" />
      {presentation.label}
    </span>
  );
}
