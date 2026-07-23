/**
 * DatasetWorkspaceView 组件测试。
 *
 * 使用 React Testing Library 测试关键渲染路径和交互。
 * 通过 vi.mock 模拟 useProject + datasets hooks + useJob 依赖。
 *
 * 测试覆盖：
 * - 加载中/项目不存在状态
 * - 项目状态门控（未确认证据时不允许登记）
 * - 文件上传表单
 * - URL 登记表单
 * - 数据集列表展示（空/有数据/状态标签）
 * - 完成数据集收集门控（需 READY 数据集）
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// --- Mock hooks 依赖 ---

vi.mock("../../features/projects/hooks", () => ({
  useProject: vi.fn(),
}));

vi.mock("../../features/datasets/hooks", () => ({
  useDatasets: vi.fn(),
  useDataset: vi.fn(),
  useDatasetVersions: vi.fn(),
  useUploadDataset: vi.fn(),
  useCreateUrlDataset: vi.fn(),
  useDeleteDataset: vi.fn(),
  useReuploadDataset: vi.fn(),
  useCompleteDatasets: vi.fn(),
}));

vi.mock("../../features/jobs/hooks", () => ({
  useJob: vi.fn(),
}));

import { useProject } from "../../features/projects/hooks";
import {
  useDatasets,
  useDatasetVersions,
  useUploadDataset,
  useCreateUrlDataset,
  useDeleteDataset,
  useReuploadDataset,
  useCompleteDatasets,
} from "../../features/datasets/hooks";
import { useJob } from "../../features/jobs/hooks";
import { DatasetWorkspaceView } from "../DatasetWorkspaceView";
import type { Project } from "../../shared/types";
import type { Dataset, DatasetVersion } from "../../features/datasets/types";

const mockedUseProject = vi.mocked(useProject);
const mockedUseDatasets = vi.mocked(useDatasets);
const mockedUseDatasetVersions = vi.mocked(useDatasetVersions);
const mockedUseUploadDataset = vi.mocked(useUploadDataset);
const mockedUseCreateUrlDataset = vi.mocked(useCreateUrlDataset);
const mockedUseDeleteDataset = vi.mocked(useDeleteDataset);
const mockedUseReuploadDataset = vi.mocked(useReuploadDataset);
const mockedUseCompleteDatasets = vi.mocked(useCompleteDatasets);
const mockedUseJob = vi.mocked(useJob);

// --- 测试辅助 ---

/** 构造测试用 Project。 */
function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "proj_001",
    name: "胃病数据分析",
    topic: "胃病数据",
    status: "EVIDENCE_CONFIRMED",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T10:00:00Z",
    ...overrides,
  };
}

/** 构造测试用 Dataset。 */
function makeDataset(overrides: Partial<Dataset> = {}): Dataset {
  return {
    id: "ds_001",
    project_id: "proj_001",
    dataset_kind: "FILE",
    title: "胃病数据集",
    description: "示例数据集",
    status: "READY",
    error_code: null,
    error_message: null,
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T10:01:00Z",
    job_id: null,
    ...overrides,
  };
}

/** 构造测试用 DatasetVersion。 */
function makeVersion(overrides: Partial<DatasetVersion> = {}): DatasetVersion {
  return {
    id: "ver_001",
    dataset_id: "ds_001",
    project_id: "proj_001",
    version: 1,
    status: "PARSED",
    file_path: "/data/ds.csv",
    file_size_bytes: 1024,
    row_count: 100,
    column_count: 5,
    profile_json: null,
    error_code: null,
    error_message: null,
    created_at: "2026-07-23T10:00:00Z",
    parsed_at: "2026-07-23T10:00:30Z",
    ...overrides,
  };
}

/** 设置所有 hooks 的默认 mock 值。 */
function setupMocks(options: {
  project?: Project | null | undefined;
  datasets?: Dataset[];
  versions?: DatasetVersion[];
  projectLoading?: boolean;
  datasetsLoading?: boolean;
  versionsLoading?: boolean;
}) {
  const {
    project = makeProject(),
    datasets = [],
    versions = [],
    projectLoading = false,
    datasetsLoading = false,
    versionsLoading = false,
  } = options;

  mockedUseProject.mockReturnValue({
    data: project,
    isLoading: projectLoading,
    isError: false,
    error: null,
  } as any);

  mockedUseDatasets.mockReturnValue({
    data: datasets,
    isLoading: datasetsLoading,
  } as any);

  mockedUseDatasetVersions.mockReturnValue({
    data: versions,
    isLoading: versionsLoading,
  } as any);

  // useJob 默认无数据，避免轮询副作用
  mockedUseJob.mockReturnValue({ data: undefined } as any);

  // mutation hooks 默认非 pending
  const makeMutationMock = () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    isError: false,
    isSuccess: false,
    data: null,
  });

  mockedUseUploadDataset.mockReturnValue(makeMutationMock() as any);
  mockedUseCreateUrlDataset.mockReturnValue(makeMutationMock() as any);
  mockedUseDeleteDataset.mockReturnValue(makeMutationMock() as any);
  mockedUseReuploadDataset.mockReturnValue(makeMutationMock() as any);
  mockedUseCompleteDatasets.mockReturnValue(makeMutationMock() as any);
}

/** 用路由上下文渲染组件。 */
function renderWithRoute(projectId: string = "proj_001") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/projects/${projectId}/datasets`]}>
        <Routes>
          <Route path="/projects/:projectId/datasets" element={<DatasetWorkspaceView />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ============================================================
// 加载和错误状态
// ============================================================

describe("DatasetWorkspaceView - 加载和错误状态", () => {
  it("项目加载中时显示加载提示", () => {
    setupMocks({ projectLoading: true, project: undefined });

    renderWithRoute();

    expect(screen.getByText("加载中…")).toBeInTheDocument();
  });

  it("项目不存在时显示错误提示", () => {
    setupMocks({ project: null });

    renderWithRoute();

    expect(screen.getByText("项目不存在")).toBeInTheDocument();
  });
});

// ============================================================
// 项目状态门控
// ============================================================

describe("DatasetWorkspaceView - 项目状态门控", () => {
  it("未确认证据时显示需要先完成证据确认的提示", () => {
    setupMocks({ project: makeProject({ status: "SOURCES_COLLECTED" }) });

    renderWithRoute();

    expect(screen.getByText(/需要先完成证据确认才能登记数据集/)).toBeInTheDocument();
  });

  it("已确认证据时不显示门控提示", () => {
    setupMocks({ project: makeProject({ status: "EVIDENCE_CONFIRMED" }) });

    renderWithRoute();

    expect(screen.queryByText(/需要先完成证据确认/)).not.toBeInTheDocument();
  });

  it("未确认证据时文件上传输入框被禁用", () => {
    setupMocks({ project: makeProject({ status: "DRAFT" }) });

    renderWithRoute();

    // 文件上传和 URL 登记区域都有"数据集标题（可选）"placeholder
    const titleInputs = screen.getAllByPlaceholderText("数据集标题（可选）");
    titleInputs.forEach((input) => expect(input).toBeDisabled());
  });

  it("已确认证据时文件上传输入框可用", () => {
    setupMocks({ project: makeProject({ status: "EVIDENCE_CONFIRMED" }) });

    renderWithRoute();

    const titleInputs = screen.getAllByPlaceholderText("数据集标题（可选）");
    titleInputs.forEach((input) => expect(input).not.toBeDisabled());
  });
});

// ============================================================
// 文件上传表单
// ============================================================

describe("DatasetWorkspaceView - 文件上传表单", () => {
  it("显示文件上传区域", () => {
    setupMocks({});

    renderWithRoute();

    expect(screen.getByText("上传 CSV/Excel 文件")).toBeInTheDocument();
    expect(screen.getByText("上传文件")).toBeInTheDocument();
  });

  it("未选择文件点击上传显示校验错误", () => {
    setupMocks({});

    renderWithRoute();

    fireEvent.click(screen.getByText("上传文件"));

    expect(screen.getByText("请选择 CSV 或 Excel 文件")).toBeInTheDocument();
  });

  it("上传中按钮显示上传中", () => {
    setupMocks({});
    mockedUseUploadDataset.mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
      data: null,
    } as any);

    renderWithRoute();

    expect(screen.getByText("上传中…")).toBeInTheDocument();
  });
});

// ============================================================
// URL 登记表单
// ============================================================

describe("DatasetWorkspaceView - URL 登记表单", () => {
  it("显示 URL 登记区域", () => {
    setupMocks({});

    renderWithRoute();

    expect(screen.getByText("登记公开 CSV/Excel URL")).toBeInTheDocument();
    expect(screen.getByText("登记 URL")).toBeInTheDocument();
  });

  it("未输入 URL 点击登记显示校验错误", () => {
    setupMocks({});

    renderWithRoute();

    fireEvent.click(screen.getByText("登记 URL"));

    expect(screen.getByText("请输入 URL")).toBeInTheDocument();
  });

  it("登记中按钮显示登记中", () => {
    setupMocks({});
    mockedUseCreateUrlDataset.mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
      data: null,
    } as any);

    renderWithRoute();

    expect(screen.getByText("登记中…")).toBeInTheDocument();
  });
});

// ============================================================
// 数据集列表展示
// ============================================================

describe("DatasetWorkspaceView - 数据集列表展示", () => {
  it("无数据集时显示空提示", () => {
    setupMocks({ datasets: [] });

    renderWithRoute();

    expect(screen.getByText("还没有登记任何数据集。")).toBeInTheDocument();
  });

  it("有数据集时显示数据集标题", () => {
    setupMocks({
      datasets: [
        makeDataset({ id: "ds_001", title: "数据集一" }),
        makeDataset({ id: "ds_002", title: "数据集二" }),
      ],
    });

    renderWithRoute();

    expect(screen.getByText("数据集一")).toBeInTheDocument();
    expect(screen.getByText("数据集二")).toBeInTheDocument();
  });

  it("显示数据集类型标签", () => {
    setupMocks({
      datasets: [makeDataset({ dataset_kind: "FILE" })],
    });

    renderWithRoute();

    expect(screen.getByText("[文件]")).toBeInTheDocument();
  });

  it("URL 数据集显示 URL 标签", () => {
    setupMocks({
      datasets: [makeDataset({ dataset_kind: "URL" })],
    });

    renderWithRoute();

    expect(screen.getByText("[URL]")).toBeInTheDocument();
  });

  it("READY 状态显示就绪标签", () => {
    setupMocks({
      datasets: [makeDataset({ status: "READY" })],
    });

    renderWithRoute();

    expect(screen.getByText(/就绪/)).toBeInTheDocument();
  });

  it("FAILED 数据集显示失败原因", () => {
    setupMocks({
      datasets: [
        makeDataset({
          status: "FAILED",
          error_code: "PARSE_ERROR",
          error_message: "解析失败",
        }),
      ],
    });

    renderWithRoute();

    expect(screen.getByText(/失败原因码：PARSE_ERROR/)).toBeInTheDocument();
    expect(screen.getByText("解析失败")).toBeInTheDocument();
  });

  it("DELETED 数据集不显示操作按钮", () => {
    setupMocks({
      datasets: [makeDataset({ status: "DELETED" })],
    });

    renderWithRoute();

    expect(screen.queryByText("查看详情")).not.toBeInTheDocument();
    expect(screen.queryByText("删除数据集")).not.toBeInTheDocument();
  });

  it("READY 数据集显示查看分析方案链接", () => {
    setupMocks({
      datasets: [makeDataset({ status: "READY" })],
    });

    renderWithRoute();

    expect(screen.getByText("查看分析方案")).toBeInTheDocument();
  });
});

// ============================================================
// 完成数据集收集
// ============================================================

describe("DatasetWorkspaceView - 完成数据集收集", () => {
  it("无 READY 数据集时完成按钮被禁用", () => {
    setupMocks({
      datasets: [makeDataset({ status: "PENDING" })],
    });

    renderWithRoute();

    const completeBtn = screen.getByText("完成数据集收集");
    expect(completeBtn).toBeDisabled();
    expect(screen.getByText(/至少需要一个已就绪（READY）的数据集/)).toBeInTheDocument();
  });

  it("有 READY 数据集时完成按钮可用", () => {
    setupMocks({
      datasets: [makeDataset({ status: "READY" })],
    });

    renderWithRoute();

    const completeBtn = screen.getByText("完成数据集收集");
    expect(completeBtn).not.toBeDisabled();
  });

  it("完成收集中按钮显示推进中", () => {
    setupMocks({
      datasets: [makeDataset({ status: "READY" })],
    });
    mockedUseCompleteDatasets.mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
      data: null,
    } as any);

    renderWithRoute();

    expect(screen.getByText("推进中…")).toBeInTheDocument();
  });
});

// ============================================================
// 项目状态标签
// ============================================================

describe("DatasetWorkspaceView - 项目状态标签", () => {
  it("显示项目状态中文标签", () => {
    setupMocks({ project: makeProject({ status: "DATASET_READY" }) });

    renderWithRoute();

    expect(screen.getByText("[数据集已就绪]")).toBeInTheDocument();
  });

  it("未知状态显示原状态字符串", () => {
    setupMocks({ project: makeProject({ status: "UNKNOWN_STATUS" }) });

    renderWithRoute();

    expect(screen.getByText("[UNKNOWN_STATUS]")).toBeInTheDocument();
  });
});
