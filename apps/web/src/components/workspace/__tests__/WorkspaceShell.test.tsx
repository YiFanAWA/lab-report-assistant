import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { WorkspaceShell } from "../WorkspaceShell";
import type { Project, WorkspaceProgressAction, WorkspaceProjection } from "../../../shared/types";

const project: Project = {
  id: "proj_001",
  name: "胃病数据分析",
  topic: "胃病数据",
  status: "REQUIREMENT_CONFIRMED",
  created_at: "2026-07-23T10:00:00Z",
  updated_at: "2026-07-23T10:00:00Z",
};

const openEvidenceAction: WorkspaceProgressAction = {
  id: "open_evidence",
  kind: "NAVIGATE",
  label: "进入证据卡片工作区",
  description: "从已解析资料中确认可追溯的证据卡片。",
  enabled: true,
  disabled_reason: null,
  route: "/projects/proj_001/evidence",
  command_id: "workspace.open.evidence",
};

const projection: WorkspaceProjection = {
  project_id: project.id,
  project: {
    id: project.id,
    name: project.name,
    topic: project.topic,
    status: project.status,
    status_label: "实验要求已确认",
    updated_at: project.updated_at,
  },
  current: {
    phase_id: "sources_evidence",
    phase_label: "资料与证据",
    step_id: "evidence",
    label: "证据卡片",
    status: "READY",
  },
  phases: [
    {
      id: "sources_evidence",
      label: "资料与证据",
      description: "整理资料来源并确认可追溯证据卡片。",
      status: "READY",
      is_open: true,
      open_reason: null,
      blocking_reasons: [],
      display: {
        status_label: "待开始",
        next_step_text: "进入资料与证据工作区开始处理。",
      },
      steps: [
        {
          id: "sources",
          label: "资料来源",
          description: "登记公开 URL 或本地辅助资料，等待采集和解析。",
          is_substep: true,
          status: "COMPLETED",
          is_open: true,
          open_reason: null,
          blocking_reasons: [],
          display: { status_label: "已完成", next_step_text: "该步骤已完成。" },
          route: "/projects/proj_001/sources",
          command_id: "workspace.open.sources",
          actions: [],
          recovery_action: null,
        },
        {
          id: "evidence",
          label: "证据卡片",
          description: "从已解析资料中确认可追溯的证据卡片。",
          is_substep: true,
          status: "READY",
          is_open: true,
          open_reason: null,
          blocking_reasons: [],
          display: { status_label: "待开始", next_step_text: "进入证据卡片工作区开始处理。" },
          route: "/projects/proj_001/evidence",
          command_id: "workspace.open.evidence",
          actions: [openEvidenceAction],
          recovery_action: null,
        },
      ],
      actions: [openEvidenceAction],
    },
    {
      id: "datasets",
      label: "数据上传",
      description: "上传原始数据并完成数据预览与基本检查。",
      status: "LOCKED",
      is_open: false,
      open_reason: {
        code: "WORKSPACE_LOCKED",
        message: "请先完成前置阶段后再进入数据上传。",
        source: "projects",
        kind: "LOCKED",
        display_message: "请先完成前置阶段后再进入数据上传。",
      },
      blocking_reasons: [],
      display: { status_label: "未开放", next_step_text: "完成前置阶段后开放。" },
      steps: [],
      actions: [],
    },
  ],
  recommended_next_action: openEvidenceAction,
  current_stage: {
    id: "evidence",
    label: "证据卡片",
    route: "/projects/proj_001/evidence",
    state: "READY",
    phase_id: "sources_evidence",
    phase_label: "资料与证据",
    is_substep: true,
    blocking_reasons: [],
  },
  next_action: {
    stage_id: "evidence",
    label: "进入证据卡片工作区",
    route: "/projects/proj_001/evidence",
    reason: "进入证据卡片工作区开始处理。",
  },
  stages: [
    {
      id: "sources",
      label: "资料来源",
      route: "/projects/proj_001/sources",
      state: "COMPLETED",
      phase_id: "sources_evidence",
      phase_label: "资料与证据",
      is_substep: true,
      blocking_reasons: [],
    },
    {
      id: "evidence",
      label: "证据卡片",
      route: "/projects/proj_001/evidence",
      state: "READY",
      phase_id: "sources_evidence",
      phase_label: "资料与证据",
      is_substep: true,
      blocking_reasons: [],
    },
    {
      id: "datasets",
      label: "数据上传",
      route: "/projects/proj_001/datasets",
      state: "LOCKED",
      phase_id: "datasets",
      phase_label: "数据上传",
      is_substep: false,
      blocking_reasons: [],
    },
  ],
  projection_generated_at: "2026-08-23T04:00:00Z",
};

describe("WorkspaceShell", () => {
  it("显示项目上下文、当前阶段、下一步和资料/证据子步骤", () => {
    render(
      <MemoryRouter>
        <WorkspaceShell project={project} projection={projection} title="证据卡片工作区">
          <p>工作区内容</p>
        </WorkspaceShell>
      </MemoryRouter>,
    );

    expect(screen.getByText("胃病数据分析")).toBeInTheDocument();
    expect(screen.getByText("返回项目总览")).toBeInTheDocument();
    expect(screen.getByText("当前阶段")).toBeInTheDocument();
    expect(screen.getAllByText("资料与证据").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("资料来源")).toBeInTheDocument();
    expect(screen.getAllByText("证据卡片").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("进入证据卡片工作区")).toBeInTheDocument();
    expect(screen.getByText("数据上传")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "数据上传" })).not.toBeInTheDocument();
  });
});