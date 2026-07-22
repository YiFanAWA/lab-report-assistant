/**
 * ExecutionWorkspaceView 组件测试。
 *
 * 使用 React Testing Library 测试关键渲染路径和交互。
 * 通过 vi.mock 模拟所有 hooks 依赖。
 *
 * 注意：vi.mock 路径必须与被测试组件实际 import 的模块路径一致。
 * ExecutionWorkspaceView.tsx 位于 src/routes/，import 路径为 ../features/xxx/hooks。
 * 测试文件位于 src/routes/__tests__/，使用相同相对路径或绝对路径。
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// --- Mock hooks 依赖 ---
// 路径与 ExecutionWorkspaceView.tsx 中的 import 路径一致

vi.mock("../../features/projects/hooks", () => ({
  useProject: vi.fn(),
}));

vi.mock("../../features/analysis/hooks", () => ({
  useAnalysisPlans: vi.fn(),
}));

vi.mock("../../features/execution/hooks", () => ({
  useCodeTasks: vi.fn(),
  useGenerateCodeTask: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
  useUpdateCodeTask: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
  useConfirmCodeTask: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
  useRejectCodeTask: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
  useExecuteCodeTask: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
  useExecutionRuns: vi.fn(),
  useCompleteExecution: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
}));

vi.mock("../../features/jobs/hooks", () => ({
  useJob: vi.fn(() => ({ data: undefined })),
}));

import { useProject } from "../../features/projects/hooks";
import { useAnalysisPlans } from "../../features/analysis/hooks";
import {
  useCodeTasks,
  useExecutionRuns,
} from "../../features/execution/hooks";
import { ExecutionWorkspaceView } from "../ExecutionWorkspaceView";
import type { CodeTask, ExecutionRun } from "../../features/execution/types";

const mockedUseProject = vi.mocked(useProject);
const mockedUseAnalysisPlans = vi.mocked(useAnalysisPlans);
const mockedUseCodeTasks = vi.mocked(useCodeTasks);
const mockedUseExecutionRuns = vi.mocked(useExecutionRuns);

// --- 测试数据 ---

const PROJECT_ID = "proj_test_001";

const mockProject = {
  id: PROJECT_ID,
  name: "胃病数据分析",
  status: "ANALYSIS_CONFIRMED",
  created_at: "2026-07-20T00:00:00Z",
};

const mockCodeTask: CodeTask = {
  id: "task_001",
  project_id: PROJECT_ID,
  analysis_plan_id: "plan_001",
  dataset_id: "ds_001",
  dataset_version_id: "dv_001",
  code: "import pandas as pd\nprint('hello')",
  code_version: 1,
  status: "CANDIDATE",
  candidate_source: "LOCAL_RULE",
  created_at: "2026-07-23T00:00:00Z",
  updated_at: null,
  confirmed_at: null,
};

const mockConfirmedCodeTask: CodeTask = {
  ...mockCodeTask,
  status: "CONFIRMED",
  confirmed_at: "2026-07-23T01:00:00Z",
};

const mockStaleCodeTask: CodeTask = {
  ...mockCodeTask,
  status: "STALE",
};

const mockExecutionRun: ExecutionRun = {
  id: "run_001",
  project_id: PROJECT_ID,
  code_task_id: "task_001",
  dataset_version_id: "dv_001",
  code_version: 1,
  status: "SUCCEEDED",
  stdout: "分析完成\n行数：100",
  stderr: "",
  exit_code: 0,
  started_at: "2026-07-23T00:00:00Z",
  finished_at: "2026-07-23T00:00:05Z",
  duration_seconds: 5.0,
  error_code: null,
  error_message: null,
  created_at: "2026-07-23T00:00:00Z",
  artifacts: [
    {
      id: "art_001",
      execution_run_id: "run_001",
      artifact_type: "TABLE_CSV",
      file_path: "/data/output.csv",
      file_size_bytes: 1024,
      name: "output.csv",
      created_at: "2026-07-23T00:00:05Z",
    },
  ],
};

const mockFailedRun: ExecutionRun = {
  ...mockExecutionRun,
  id: "run_002",
  status: "FAILED",
  stdout: "",
  stderr: "SyntaxError: invalid syntax",
  exit_code: 1,
  duration_seconds: 2.0,
  error_code: "EXECUTION_FAILED",
  error_message: "Python 进程退出码非零",
  artifacts: [],
};

const mockConfirmedPlan = {
  id: "plan_001",
  project_id: PROJECT_ID,
  dataset_id: "ds_001",
  dataset_version_id: "dv_001",
  cleaning_plan: "[]",
  analysis_plan: "[]",
  chart_plan: "[]",
  status: "CONFIRMED" as const,
  candidate_source: "LOCAL_RULE" as const,
  created_at: "2026-07-23T00:00:00Z",
  updated_at: null,
  confirmed_at: "2026-07-23T00:00:00Z",
};

// --- 辅助函数 ---

function renderWithProviders(element: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/projects/${PROJECT_ID}/execution`]}>
        <Routes>
          <Route path="/projects/:projectId/execution" element={element} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedUseProject.mockReturnValue({
    data: mockProject,
    isLoading: false,
    isError: false,
    error: null,
  } as any);
  mockedUseAnalysisPlans.mockReturnValue({
    data: [],
    isLoading: false,
  } as any);
  mockedUseCodeTasks.mockReturnValue({
    data: [],
    isLoading: false,
  } as any);
  mockedUseExecutionRuns.mockReturnValue({
    data: [],
    isLoading: false,
  } as any);
});

// --- 渲染测试 ---

describe("ExecutionWorkspaceView 渲染", () => {
  it("项目加载中时显示'加载中…'", () => {
    mockedUseProject.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    } as any);

    renderWithProviders(<ExecutionWorkspaceView />);

    expect(screen.getByText("加载中…")).toBeInTheDocument();
  });

  it("项目不存在时显示错误信息", () => {
    mockedUseProject.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: null,
    } as any);

    renderWithProviders(<ExecutionWorkspaceView />);

    expect(screen.getByText("项目不存在")).toBeInTheDocument();
  });

  it("正常渲染时显示项目名称和状态", () => {
    renderWithProviders(<ExecutionWorkspaceView />);

    expect(screen.getByText(/胃病数据分析/)).toBeInTheDocument();
    expect(screen.getByText(/\[分析方案已确认\]/)).toBeInTheDocument();
  });

  it("渲染代码任务和执行记录两个 section", () => {
    renderWithProviders(<ExecutionWorkspaceView />);

    expect(screen.getByText("代码任务")).toBeInTheDocument();
    expect(screen.getByText("执行记录")).toBeInTheDocument();
  });
});

// --- 生成代码候选区域 ---

describe("生成代码候选区域", () => {
  it("ANALYSIS_CONFIRMED 状态下显示生成按钮（无已确认方案时）", () => {
    renderWithProviders(<ExecutionWorkspaceView />);

    // 有方案确认区域标题
    expect(screen.getByText("生成代码候选")).toBeInTheDocument();
    // 但无已确认方案时显示提示
    expect(
      screen.getByText(/当前没有已确认的分析方案/)
    ).toBeInTheDocument();
  });

  it("非 ANALYSIS_CONFIRMED 状态下显示状态提示", () => {
    mockedUseProject.mockReturnValue({
      data: { ...mockProject, status: "DATASET_READY" },
      isLoading: false,
    } as any);

    renderWithProviders(<ExecutionWorkspaceView />);

    expect(
      screen.getByText(/需要先在分析方案工作区完成确认/)
    ).toBeInTheDocument();
  });

  it("有已确认分析方案时显示下拉选择器和生成按钮", () => {
    mockedUseAnalysisPlans.mockReturnValue({
      data: [mockConfirmedPlan],
      isLoading: false,
    } as any);

    renderWithProviders(<ExecutionWorkspaceView />);

    expect(
      screen.getByRole("button", { name: /生成代码候选/ })
    ).toBeInTheDocument();
    // 下拉选择器存在
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });
});

// --- 代码任务卡片 ---

describe("代码任务卡片", () => {
  it("CANDIDATE 任务显示候选状态和编辑/确认/拒绝按钮", () => {
    mockedUseCodeTasks.mockReturnValue({
      data: [mockCodeTask],
      isLoading: false,
    } as any);

    renderWithProviders(<ExecutionWorkspaceView />);

    // 编辑/确认/拒绝按钮（CANDIDATE 状态可操作）
    expect(screen.getByText("编辑代码")).toBeInTheDocument();
    expect(screen.getByText("确认代码")).toBeInTheDocument();
    expect(screen.getByText("拒绝代码")).toBeInTheDocument();
    // CANDIDATE 状态不能触发执行
    expect(screen.queryByText("触发执行")).not.toBeInTheDocument();
  });

  it("CONFIRMED 任务显示触发执行按钮", () => {
    mockedUseCodeTasks.mockReturnValue({
      data: [mockConfirmedCodeTask],
      isLoading: false,
    } as any);

    renderWithProviders(<ExecutionWorkspaceView />);

    expect(screen.getByText("触发执行")).toBeInTheDocument();
  });

  it("STALE 任务显示失效提示", () => {
    mockedUseCodeTasks.mockReturnValue({
      data: [mockStaleCodeTask],
      isLoading: false,
    } as any);

    renderWithProviders(<ExecutionWorkspaceView />);

    expect(screen.getByText(/此代码任务已失效/)).toBeInTheDocument();
  });

  it("代码内容以 monospace 展示", () => {
    mockedUseCodeTasks.mockReturnValue({
      data: [mockCodeTask],
      isLoading: false,
    } as any);

    renderWithProviders(<ExecutionWorkspaceView />);

    expect(screen.getByText(/import pandas as pd/)).toBeInTheDocument();
  });
});

// --- 执行记录卡片 ---

describe("执行记录卡片", () => {
  it("SUCCEEDED 执行记录显示成功状态和产物下载", () => {
    mockedUseExecutionRuns.mockReturnValue({
      data: [mockExecutionRun],
      isLoading: false,
    } as any);

    renderWithProviders(<ExecutionWorkspaceView />);

    // 已成功状态可能多处出现，用 getAllByText
    expect(screen.getAllByText(/已成功/).length).toBeGreaterThan(0);
    // 产物下载链接
    expect(screen.getByText("下载")).toBeInTheDocument();
    // 产物名称
    expect(screen.getByText(/output\.csv/)).toBeInTheDocument();
  });

  it("FAILED 执行记录显示错误信息", () => {
    mockedUseExecutionRuns.mockReturnValue({
      data: [mockFailedRun],
      isLoading: false,
    } as any);

    renderWithProviders(<ExecutionWorkspaceView />);

    // 失败状态可能多处出现（项目状态映射），用 getAllByText
    expect(screen.getAllByText(/失败/).length).toBeGreaterThan(0);
    // 错误码和错误信息
    expect(screen.getByText(/EXECUTION_FAILED/)).toBeInTheDocument();
    expect(screen.getByText(/Python 进程退出码非零/)).toBeInTheDocument();
  });

  it("无执行记录时显示空提示", () => {
    renderWithProviders(<ExecutionWorkspaceView />);

    expect(screen.getByText(/还没有执行记录/)).toBeInTheDocument();
  });
});

// --- 完成结果确认 ---

describe("完成结果确认按钮", () => {
  it("无 SUCCEEDED 执行记录时按钮禁用", () => {
    renderWithProviders(<ExecutionWorkspaceView />);

    const button = screen.getByRole("button", { name: /完成结果确认/ });
    expect(button).toBeDisabled();
  });

  it("有 SUCCEEDED 执行记录时按钮启用", () => {
    mockedUseExecutionRuns.mockReturnValue({
      data: [mockExecutionRun],
      isLoading: false,
    } as any);

    renderWithProviders(<ExecutionWorkspaceView />);

    const button = screen.getByRole("button", { name: /完成结果确认/ });
    expect(button).toBeEnabled();
  });

  it("RESULT_CONFIRMED 状态下按钮禁用", () => {
    mockedUseProject.mockReturnValue({
      data: { ...mockProject, status: "RESULT_CONFIRMED" },
      isLoading: false,
    } as any);
    mockedUseExecutionRuns.mockReturnValue({
      data: [mockExecutionRun],
      isLoading: false,
    } as any);

    renderWithProviders(<ExecutionWorkspaceView />);

    const button = screen.getByRole("button", { name: /完成结果确认/ });
    expect(button).toBeDisabled();
  });
});
