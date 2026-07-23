/**
 * ProjectDetailView 组件测试。
 *
 * 使用 React Testing Library 测试关键渲染路径和状态机门控。
 * 通过 vi.mock 模拟 useProject hook 依赖。
 *
 * 测试覆盖：
 * - 加载中/错误/项目不存在状态
 * - 项目详情字段展示（名称、课题、状态、时间）
 * - 14 种状态中文标签映射
 * - 8 个入口链接的状态机门控（isAtOrAfter 逻辑）
 * - 返回项目列表链接
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// --- Mock hooks 依赖 ---

vi.mock("../../features/projects/hooks", () => ({
  useProject: vi.fn(),
}));

import { useProject } from "../../features/projects/hooks";
import { ProjectDetailView } from "../ProjectDetailView";
import type { Project } from "../../shared/types";

const mockedUseProject = vi.mocked(useProject);

// --- 测试辅助 ---

/** 构造测试用 Project 对象。 */
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

/** 用路由上下文渲染组件。 */
function renderWithRoute(projectId: string = "proj_001") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/projects/${projectId}`]}>
        <Routes>
          <Route path="/projects/:projectId" element={<ProjectDetailView />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ============================================================
// 加载、错误、空状态
// ============================================================

describe("ProjectDetailView - 加载和错误状态", () => {
  it("加载中时显示加载提示", () => {
    mockedUseProject.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    } as any);

    renderWithRoute();

    expect(screen.getByText("加载中…")).toBeInTheDocument();
  });

  it("错误时显示默认错误消息和返回链接", () => {
    mockedUseProject.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: null,
    } as any);

    renderWithRoute();

    expect(screen.getByText("无法加载项目")).toBeInTheDocument();
    expect(screen.getByText("返回项目列表")).toBeInTheDocument();
  });

  it("错误时显示自定义错误消息", () => {
    mockedUseProject.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: { message: "项目不存在" },
    } as any);

    renderWithRoute();

    expect(screen.getByText("项目不存在")).toBeInTheDocument();
  });

  it("项目数据为空时不渲染内容", () => {
    mockedUseProject.mockReturnValue({
      data: null,
      isLoading: false,
      isError: false,
      error: null,
    } as any);

    const { container } = renderWithRoute();

    expect(container.innerHTML).toBe("");
  });
});

// ============================================================
// 项目详情字段展示
// ============================================================

describe("ProjectDetailView - 详情字段展示", () => {
  it("显示项目名称和课题", () => {
    mockedUseProject.mockReturnValue({
      data: makeProject({ name: "胃病分析", topic: "胃病数据" }),
      isLoading: false,
      isError: false,
      error: null,
    } as any);

    renderWithRoute();

    expect(screen.getByText("胃病分析")).toBeInTheDocument();
    expect(screen.getByText("胃病数据")).toBeInTheDocument();
  });

  it("显示返回项目列表链接", () => {
    mockedUseProject.mockReturnValue({
      data: makeProject(),
      isLoading: false,
      isError: false,
      error: null,
    } as any);

    renderWithRoute();

    expect(screen.getByText("← 返回项目列表")).toBeInTheDocument();
  });

  it("显示状态标签", () => {
    mockedUseProject.mockReturnValue({
      data: makeProject({ status: "DRAFT" }),
      isLoading: false,
      isError: false,
      error: null,
    } as any);

    renderWithRoute();

    expect(screen.getByText("草稿")).toBeInTheDocument();
  });
});

// ============================================================
// 状态中文标签映射
// ============================================================

describe("ProjectDetailView - 状态标签映射", () => {
  const statusCases: Array<[string, string]> = [
    ["DRAFT", "草稿"],
    ["REQUIREMENT_PARSED", "要求已解析"],
    ["REQUIREMENT_CONFIRMED", "需求已确认"],
    ["SOURCES_COLLECTED", "来源已收集"],
    ["EVIDENCE_CONFIRMED", "证据已确认"],
    ["DATASET_READY", "数据集已就绪"],
    ["ANALYSIS_PLANNED", "分析方案已生成"],
    ["ANALYSIS_CONFIRMED", "分析方案已确认"],
    ["EXECUTING", "执行中"],
    ["EXECUTION_FAILED", "执行失败"],
    ["RESULT_CONFIRMED", "结果已确认"],
    ["OUTLINE_CONFIRMED", "大纲已确认"],
    ["GENERATING", "交付物生成中"],
    ["COMPLETED", "已完成"],
  ];

  statusCases.forEach(([status, label]) => {
    it(`${status} 状态显示为"${label}"`, () => {
      mockedUseProject.mockReturnValue({
        data: makeProject({ status }),
        isLoading: false,
        isError: false,
        error: null,
      } as any);

      renderWithRoute();

      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  it("未知状态显示原状态字符串", () => {
    mockedUseProject.mockReturnValue({
      data: makeProject({ status: "UNKNOWN_STATUS" }),
      isLoading: false,
      isError: false,
      error: null,
    } as any);

    renderWithRoute();

    expect(screen.getByText("UNKNOWN_STATUS")).toBeInTheDocument();
  });
});

// ============================================================
// 入口链接状态机门控
// ============================================================

describe("ProjectDetailView - 入口链接门控", () => {
  /** 设置 mock 并渲染。 */
  function renderWithStatus(status: string) {
    mockedUseProject.mockReturnValue({
      data: makeProject({ status }),
      isLoading: false,
      isError: false,
      error: null,
    } as any);
    return renderWithRoute();
  }

  describe("实验要求入口（始终显示）", () => {
    it("DRAFT 状态显示实验要求入口", () => {
      renderWithStatus("DRAFT");
      expect(screen.getByText("进入实验要求工作区")).toBeInTheDocument();
    });

    it("COMPLETED 状态仍显示实验要求入口", () => {
      renderWithStatus("COMPLETED");
      expect(screen.getByText("进入实验要求工作区")).toBeInTheDocument();
    });
  });

  describe("资料来源入口（REQUIREMENT_CONFIRMED 及之后）", () => {
    it("DRAFT 状态不显示资料来源入口", () => {
      renderWithStatus("DRAFT");
      expect(screen.queryByText("进入资料来源工作区")).not.toBeInTheDocument();
    });

    it("REQUIREMENT_CONFIRMED 状态显示资料来源入口", () => {
      renderWithStatus("REQUIREMENT_CONFIRMED");
      expect(screen.getByText("进入资料来源工作区")).toBeInTheDocument();
    });
  });

  describe("数据集入口（EVIDENCE_CONFIRMED 及之后）", () => {
    it("SOURCES_COLLECTED 状态不显示数据集入口", () => {
      renderWithStatus("SOURCES_COLLECTED");
      expect(screen.queryByText("进入数据集工作区")).not.toBeInTheDocument();
    });

    it("EVIDENCE_CONFIRMED 状态显示数据集入口", () => {
      renderWithStatus("EVIDENCE_CONFIRMED");
      expect(screen.getByText("进入数据集工作区")).toBeInTheDocument();
    });
  });

  describe("分析方案入口（DATASET_READY 及之后）", () => {
    it("EVIDENCE_CONFIRMED 状态不显示分析方案入口", () => {
      renderWithStatus("EVIDENCE_CONFIRMED");
      expect(screen.queryByText("进入分析方案工作区")).not.toBeInTheDocument();
    });

    it("DATASET_READY 状态显示分析方案入口", () => {
      renderWithStatus("DATASET_READY");
      expect(screen.getByText("进入分析方案工作区")).toBeInTheDocument();
    });
  });

  describe("执行入口（ANALYSIS_CONFIRMED 及之后）", () => {
    it("ANALYSIS_PLANNED 状态不显示执行入口", () => {
      renderWithStatus("ANALYSIS_PLANNED");
      expect(screen.queryByText("进入执行工作区")).not.toBeInTheDocument();
    });

    it("ANALYSIS_CONFIRMED 状态显示执行入口", () => {
      renderWithStatus("ANALYSIS_CONFIRMED");
      expect(screen.getByText("进入执行工作区")).toBeInTheDocument();
    });

    it("EXECUTION_FAILED 状态仍显示执行入口（允许重试）", () => {
      renderWithStatus("EXECUTION_FAILED");
      expect(screen.getByText("进入执行工作区")).toBeInTheDocument();
    });
  });

  describe("大纲入口（RESULT_CONFIRMED 及之后）", () => {
    it("EXECUTING 状态不显示大纲入口", () => {
      renderWithStatus("EXECUTING");
      expect(screen.queryByText("进入大纲工作区")).not.toBeInTheDocument();
    });

    it("RESULT_CONFIRMED 状态显示大纲入口", () => {
      renderWithStatus("RESULT_CONFIRMED");
      expect(screen.getByText("进入大纲工作区")).toBeInTheDocument();
    });
  });

  describe("交付物入口（OUTLINE_CONFIRMED 及之后）", () => {
    it("RESULT_CONFIRMED 状态不显示交付物入口", () => {
      renderWithStatus("RESULT_CONFIRMED");
      expect(screen.queryByText("进入交付物工作区")).not.toBeInTheDocument();
    });

    it("OUTLINE_CONFIRMED 状态显示交付物入口", () => {
      renderWithStatus("OUTLINE_CONFIRMED");
      expect(screen.getByText("进入交付物工作区")).toBeInTheDocument();
    });

    it("COMPLETED 状态仍显示交付物入口（查看历史交付物）", () => {
      renderWithStatus("COMPLETED");
      expect(screen.getByText("进入交付物工作区")).toBeInTheDocument();
    });
  });

  describe("COMPLETED 状态显示全部入口", () => {
    it("完成状态显示所有 8 个入口", () => {
      renderWithStatus("COMPLETED");

      expect(screen.getByText("进入实验要求工作区")).toBeInTheDocument();
      expect(screen.getByText("进入资料来源工作区")).toBeInTheDocument();
      expect(screen.getByText("进入证据卡片工作区")).toBeInTheDocument();
      expect(screen.getByText("进入数据集工作区")).toBeInTheDocument();
      expect(screen.getByText("进入分析方案工作区")).toBeInTheDocument();
      expect(screen.getByText("进入执行工作区")).toBeInTheDocument();
      expect(screen.getByText("进入大纲工作区")).toBeInTheDocument();
      expect(screen.getByText("进入交付物工作区")).toBeInTheDocument();
    });
  });
});
