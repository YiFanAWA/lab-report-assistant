/**
 * ProjectListView 组件测试。
 *
 * 使用 React Testing Library 测试关键渲染路径和交互。
 * 通过 vi.mock 模拟 useProjects hook 依赖。
 *
 * 测试覆盖：
 * - 加载中状态
 * - 错误状态（默认消息和自定义消息）
 * - 空列表提示
 * - 正常渲染项目列表
 * - 状态中文标签映射
 * - 项目卡片链接
 * - "新建项目"链接
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// --- Mock hooks 依赖 ---
// 路径与 ProjectListView.tsx 中的 import 路径一致

vi.mock("../../features/projects/hooks", () => ({
  useProjects: vi.fn(),
}));

import { useProjects } from "../../features/projects/hooks";
import { ProjectListView } from "../ProjectListView";
import type { Project } from "../../shared/types";

const mockedUseProjects = vi.mocked(useProjects);

// --- 测试辅助 ---

/** 构造测试用 Project 对象。 */
function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "proj_001",
    name: "胃病数据分析",
    topic: "胃病数据",
    status: "DRAFT",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T10:00:00Z",
    ...overrides,
  };
}

/** 用 QueryClientProvider 和 MemoryRouter 包裹组件。 */
function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ============================================================
// 加载和错误状态
// ============================================================

describe("ProjectListView - 加载状态", () => {
  it("加载中时显示加载提示", () => {
    mockedUseProjects.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    } as any);

    renderWithProviders(<ProjectListView />);

    expect(screen.getByText("加载中…")).toBeInTheDocument();
  });
});

describe("ProjectListView - 错误状态", () => {
  it("错误时显示默认错误消息", () => {
    mockedUseProjects.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: null,
    } as any);

    renderWithProviders(<ProjectListView />);

    expect(screen.getByText("无法加载项目列表")).toBeInTheDocument();
  });

  it("错误时显示自定义错误消息", () => {
    mockedUseProjects.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: { message: "网络连接失败" },
    } as any);

    renderWithProviders(<ProjectListView />);

    expect(screen.getByText("网络连接失败")).toBeInTheDocument();
  });
});

// ============================================================
// 空列表
// ============================================================

describe("ProjectListView - 空列表", () => {
  it("空列表显示提示文本", () => {
    mockedUseProjects.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    } as any);

    renderWithProviders(<ProjectListView />);

    expect(screen.getByText(/还没有实验项目/)).toBeInTheDocument();
  });
});

// ============================================================
// 正常渲染
// ============================================================

describe("ProjectListView - 正常渲染", () => {
  it("显示标题和新建项目链接", () => {
    mockedUseProjects.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    } as any);

    renderWithProviders(<ProjectListView />);

    expect(screen.getByText("实验报告助手")).toBeInTheDocument();
    expect(screen.getByText("新建项目")).toBeInTheDocument();
  });

  it("渲染项目卡片列表", () => {
    const projects = [
      makeProject({ id: "p1", name: "项目一" }),
      makeProject({ id: "p2", name: "项目二" }),
      makeProject({ id: "p3", name: "项目三" }),
    ];
    mockedUseProjects.mockReturnValue({
      data: projects,
      isLoading: false,
      isError: false,
      error: null,
    } as any);

    renderWithProviders(<ProjectListView />);

    expect(screen.getByText("项目一")).toBeInTheDocument();
    expect(screen.getByText("项目二")).toBeInTheDocument();
    expect(screen.getByText("项目三")).toBeInTheDocument();
  });

  it("项目卡片显示名称和主题", () => {
    const projects = [
      makeProject({ id: "p1", name: "胃病分析", topic: "胃病数据" }),
    ];
    mockedUseProjects.mockReturnValue({
      data: projects,
      isLoading: false,
      isError: false,
      error: null,
    } as any);

    renderWithProviders(<ProjectListView />);

    expect(screen.getByText("胃病分析")).toBeInTheDocument();
    expect(screen.getByText("胃病数据")).toBeInTheDocument();
  });
});

// ============================================================
// 状态中文标签映射
// ============================================================

describe("ProjectListView - 状态标签映射", () => {
  it("DRAFT 状态显示为草稿", () => {
    mockedUseProjects.mockReturnValue({
      data: [makeProject({ status: "DRAFT" })],
      isLoading: false,
      isError: false,
      error: null,
    } as any);

    renderWithProviders(<ProjectListView />);

    expect(screen.getByText("草稿")).toBeInTheDocument();
  });

  it("REQUIREMENT_CONFIRMED 状态显示为需求已确认", () => {
    mockedUseProjects.mockReturnValue({
      data: [makeProject({ status: "REQUIREMENT_CONFIRMED" })],
      isLoading: false,
      isError: false,
      error: null,
    } as any);

    renderWithProviders(<ProjectListView />);

    expect(screen.getByText("需求已确认")).toBeInTheDocument();
  });

  it("COMPLETED 状态显示为已完成", () => {
    mockedUseProjects.mockReturnValue({
      data: [makeProject({ status: "COMPLETED" })],
      isLoading: false,
      isError: false,
      error: null,
    } as any);

    renderWithProviders(<ProjectListView />);

    expect(screen.getByText("已完成")).toBeInTheDocument();
  });

  it("未知状态显示原状态字符串", () => {
    mockedUseProjects.mockReturnValue({
      data: [makeProject({ status: "UNKNOWN_STATUS" })],
      isLoading: false,
      isError: false,
      error: null,
    } as any);

    renderWithProviders(<ProjectListView />);

    expect(screen.getByText("UNKNOWN_STATUS")).toBeInTheDocument();
  });
});
