/**
 * ProjectDetailView 组件测试。
 *
 * 项目阶段、入口可用性和下一步均由 ProjectProgressProjection 提供；
 * 本文件只验证页面展示和 projection 接线，不复制项目状态机。
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";

vi.mock("../../features/projects/hooks", () => ({
  useProject: vi.fn(),
  useWorkspaceProjection: vi.fn(),
}));

import {
  useProject,
  useWorkspaceProjection,
} from "../../features/projects/hooks";
import { ProjectDetailView } from "../ProjectDetailView";
import type { Project, WorkspaceProjection } from "../../shared/types";
import { makeWorkspaceProjectionForStatus } from "./workspaceProjectionFixture";

const mockedUseProject = vi.mocked(useProject);
const mockedUseWorkspaceProjection = vi.mocked(useWorkspaceProjection);

function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "proj_001",
    name: "胃病数据分析",
    topic: "胃病数据",
    status: "DRAFT",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T11:00:00Z",
    ...overrides,
  };
}

function setupMocks(options: {
  project?: Project | null | undefined;
  projection?: WorkspaceProjection | null;
  projectLoading?: boolean;
  projectionLoading?: boolean;
  projectError?: boolean;
  projectionError?: boolean;
  error?: { message?: string } | null;
}) {
  const {
    project = makeProject(),
    projection = project
      ? makeWorkspaceProjectionForStatus(project)
      : makeWorkspaceProjectionForStatus(makeProject()),
    projectLoading = false,
    projectionLoading = false,
    projectError = false,
    projectionError = false,
    error = null,
  } = options;

  mockedUseProject.mockReturnValue({
    data: project,
    isLoading: projectLoading,
    isError: projectError,
    error,
  } as any);
  mockedUseWorkspaceProjection.mockReturnValue({
    data: projection,
    isLoading: projectionLoading,
    isError: projectionError,
    error,
  } as any);
}

function renderWithRoute() {
  return render(
    <MemoryRouter initialEntries={["/projects/proj_001"]}>
      <Routes>
        <Route path="/projects/:projectId" element={<ProjectDetailView />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ProjectDetailView - 加载和错误状态", () => {
  it("项目或进度投影加载中时显示加载提示", () => {
    setupMocks({ projectLoading: true, projectionLoading: true });
    renderWithRoute();
    expect(screen.getByText("加载中…")).toBeInTheDocument();
  });

  it("项目加载错误时显示返回项目列表", () => {
    setupMocks({ projectError: true, error: null });
    renderWithRoute();
    expect(screen.getByText("无法加载项目")).toBeInTheDocument();
    expect(screen.getByText("返回项目列表")).toBeInTheDocument();
  });

  it("投影加载错误时也显示返回项目列表", () => {
    setupMocks({ projectionError: true, error: { message: "进度投影不可用" } });
    renderWithRoute();
    expect(screen.getByText("进度投影不可用")).toBeInTheDocument();
  });

  it("项目数据为空时不渲染内容", () => {
    setupMocks({ project: null, projection: null });
    const { container } = renderWithRoute();
    expect(container.innerHTML).toBe("");
  });
});

describe("ProjectDetailView - projection 展示", () => {
  it("显示项目名称、课题和后端提供的状态文案", () => {
    const project = makeProject({ name: "胃病分析", topic: "胃病数据" });
    setupMocks({ project });
    renderWithRoute();

    expect(screen.getByText("胃病分析")).toBeInTheDocument();
    expect(screen.getByText("胃病数据")).toBeInTheDocument();
    expect(screen.getByText("草稿")).toBeInTheDocument();
  });

  it("锁定步骤展示为不可点击入口", () => {
    setupMocks({ project: makeProject({ status: "DRAFT" }) });
    renderWithRoute();

    expect(screen.getByRole("link", { name: "进入实验要求阶段" })).toHaveAttribute(
      "href",
      "/projects/proj_001/requirements",
    );
    expect(
      screen.queryByRole("link", { name: "进入资料与证据阶段" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("资料与证据")).toBeInTheDocument();
  });

  it("资料来源和证据卡片由同一个顶层阶段承载", () => {
    setupMocks({ project: makeProject({ status: "REQUIREMENT_CONFIRMED" }) });
    renderWithRoute();

    expect(screen.getByText("资料与证据")).toBeInTheDocument();
    expect(screen.getByText(/子步骤：资料来源、证据卡片/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "进入资料与证据阶段" })).toHaveAttribute(
      "href",
      "/projects/proj_001/sources",
    );
  });

  it("完成项目时不渲染项目级下一步链接", () => {
    setupMocks({ project: makeProject({ status: "COMPLETED" }) });
    renderWithRoute();

    expect(screen.getAllByText("项目已完成").length).toBeGreaterThan(0);
    expect(screen.queryByText("打开工作区 →")).not.toBeInTheDocument();
    expect(screen.getAllByText("正式交付物").length).toBeGreaterThan(0);
  });
});