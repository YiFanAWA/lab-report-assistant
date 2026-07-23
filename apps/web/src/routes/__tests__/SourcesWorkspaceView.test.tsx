/**
 * SourcesWorkspaceView 组件测试。
 *
 * 使用 React Testing Library 测试关键渲染路径和交互。
 * 通过 vi.mock 模拟 useProject + sources hooks + useJob 依赖。
 *
 * 测试覆盖：
 * - 加载中/项目不存在状态
 * - 项目状态门控（未确认需求时不允许登记）
 * - URL 登记表单
 * - PDF 上传表单
 * - 来源列表展示（空/有数据/状态标签）
 * - 删除按钮
 * - 完成来源收集门控（需 PARSED 来源）
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// --- Mock hooks 依赖 ---

vi.mock("../../features/projects/hooks", () => ({
  useProject: vi.fn(),
}));

vi.mock("../../features/sources/hooks", () => ({
  useSources: vi.fn(),
  useSource: vi.fn(),
  useCreateUrlSource: vi.fn(),
  useCreatePdfSource: vi.fn(),
  useDeleteSource: vi.fn(),
  useCompleteSources: vi.fn(),
}));

vi.mock("../../features/jobs/hooks", () => ({
  useJob: vi.fn(),
}));

import { useProject } from "../../features/projects/hooks";
import {
  useSources,
  useCreateUrlSource,
  useCreatePdfSource,
  useDeleteSource,
  useCompleteSources,
} from "../../features/sources/hooks";
import { useJob } from "../../features/jobs/hooks";
import { SourcesWorkspaceView } from "../SourcesWorkspaceView";
import type { Project } from "../../shared/types";
import type { Source } from "../../features/sources/types";

const mockedUseProject = vi.mocked(useProject);
const mockedUseSources = vi.mocked(useSources);
const mockedUseCreateUrlSource = vi.mocked(useCreateUrlSource);
const mockedUseCreatePdfSource = vi.mocked(useCreatePdfSource);
const mockedUseDeleteSource = vi.mocked(useDeleteSource);
const mockedUseCompleteSources = vi.mocked(useCompleteSources);
const mockedUseJob = vi.mocked(useJob);

// --- 测试辅助 ---

/** 构造测试用 Project。 */
function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "proj_001",
    name: "胃病数据分析",
    topic: "胃病数据",
    status: "REQUIREMENT_CONFIRMED",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T10:00:00Z",
    ...overrides,
  };
}

/** 构造测试用 Source。 */
function makeSource(overrides: Partial<Source> = {}): Source {
  return {
    id: "src_001",
    project_id: "proj_001",
    source_kind: "URL",
    title: "公开资料",
    url: "https://example.com/article",
    file_path: null,
    content_type: "text/html",
    content_hash: "abc123",
    status: "PARSED",
    error_code: null,
    error_message: null,
    created_at: "2026-07-23T10:00:00Z",
    fetched_at: "2026-07-23T10:00:05Z",
    parsed_at: "2026-07-23T10:00:10Z",
    job_id: null,
    ...overrides,
  };
}

/** 设置所有 hooks 的默认 mock 值。 */
function setupMocks(options: {
  project?: Project | null | undefined;
  sources?: Source[];
  projectLoading?: boolean;
  sourcesLoading?: boolean;
}) {
  const {
    project = makeProject(),
    sources = [],
    projectLoading = false,
    sourcesLoading = false,
  } = options;

  mockedUseProject.mockReturnValue({
    data: project,
    isLoading: projectLoading,
    isError: false,
    error: null,
  } as any);

  mockedUseSources.mockReturnValue({
    data: sources,
    isLoading: sourcesLoading,
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

  mockedUseCreateUrlSource.mockReturnValue(makeMutationMock() as any);
  mockedUseCreatePdfSource.mockReturnValue(makeMutationMock() as any);
  mockedUseDeleteSource.mockReturnValue(makeMutationMock() as any);
  mockedUseCompleteSources.mockReturnValue(makeMutationMock() as any);
}

/** 用路由上下文渲染组件。 */
function renderWithRoute(projectId: string = "proj_001") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/projects/${projectId}/sources`]}>
        <Routes>
          <Route path="/projects/:projectId/sources" element={<SourcesWorkspaceView />} />
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

describe("SourcesWorkspaceView - 加载和错误状态", () => {
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

describe("SourcesWorkspaceView - 项目状态门控", () => {
  it("未确认需求时显示需要先完成实验要求确认的提示", () => {
    setupMocks({ project: makeProject({ status: "DRAFT" }) });

    renderWithRoute();

    expect(screen.getByText(/需要先完成实验要求确认才能登记资料来源/)).toBeInTheDocument();
    expect(screen.getByText("前往实验要求工作区")).toBeInTheDocument();
  });

  it("已确认需求时不显示门控提示", () => {
    setupMocks({ project: makeProject({ status: "REQUIREMENT_CONFIRMED" }) });

    renderWithRoute();

    expect(screen.queryByText(/需要先完成实验要求确认/)).not.toBeInTheDocument();
  });

  it("未确认需求时 URL 输入框被禁用", () => {
    setupMocks({ project: makeProject({ status: "DRAFT" }) });

    renderWithRoute();

    const urlInput = screen.getByPlaceholderText("https://example.com/article.html");
    expect(urlInput).toBeDisabled();
  });

  it("已确认需求时 URL 输入框可用", () => {
    setupMocks({ project: makeProject({ status: "REQUIREMENT_CONFIRMED" }) });

    renderWithRoute();

    const urlInput = screen.getByPlaceholderText("https://example.com/article.html");
    expect(urlInput).not.toBeDisabled();
  });
});

// ============================================================
// URL 登记表单
// ============================================================

describe("SourcesWorkspaceView - URL 登记表单", () => {
  it("显示 URL 登记区域", () => {
    setupMocks({});

    renderWithRoute();

    expect(screen.getByText("登记公开 URL")).toBeInTheDocument();
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
    mockedUseCreateUrlSource.mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
      data: null,
    } as any);

    renderWithRoute();

    expect(screen.getByText("登记中…")).toBeInTheDocument();
  });
});

// ============================================================
// PDF 上传表单
// ============================================================

describe("SourcesWorkspaceView - PDF 上传表单", () => {
  it("显示 PDF 上传区域", () => {
    setupMocks({});

    renderWithRoute();

    expect(screen.getByText("上传 PDF 辅助文件")).toBeInTheDocument();
    expect(screen.getByText("上传 PDF")).toBeInTheDocument();
  });

  it("未选择文件点击上传显示校验错误", () => {
    setupMocks({});

    renderWithRoute();

    fireEvent.click(screen.getByText("上传 PDF"));

    expect(screen.getByText("请选择 PDF 文件")).toBeInTheDocument();
  });
});

// ============================================================
// 来源列表展示
// ============================================================

describe("SourcesWorkspaceView - 来源列表展示", () => {
  it("无来源时显示空提示", () => {
    setupMocks({ sources: [] });

    renderWithRoute();

    expect(screen.getByText("还没有登记任何资料来源。")).toBeInTheDocument();
  });

  it("有来源时显示来源标题", () => {
    setupMocks({
      sources: [
        makeSource({ id: "src_001", title: "来源一" }),
        makeSource({ id: "src_002", title: "来源二" }),
      ],
    });

    renderWithRoute();

    expect(screen.getByText("来源一")).toBeInTheDocument();
    expect(screen.getByText("来源二")).toBeInTheDocument();
  });

  it("显示来源类型标签", () => {
    setupMocks({
      sources: [makeSource({ source_kind: "URL" })],
    });

    renderWithRoute();

    expect(screen.getByText("[URL]")).toBeInTheDocument();
  });

  it("PDF 来源显示 PDF 文件标签", () => {
    setupMocks({
      sources: [
        makeSource({
          source_kind: "FILE",
          url: null,
          file_path: "/path/to/file.pdf",
          content_type: "application/pdf",
        }),
      ],
    });

    renderWithRoute();

    expect(screen.getByText("[PDF 文件]")).toBeInTheDocument();
    expect(screen.getByText(/文件：/)).toBeInTheDocument();
  });

  it("FAILED 来源显示失败原因", () => {
    setupMocks({
      sources: [
        makeSource({
          status: "FAILED",
          error_code: "FETCH_TIMEOUT",
          error_message: "采集超时",
        }),
      ],
    });

    renderWithRoute();

    expect(screen.getByText(/失败原因码：FETCH_TIMEOUT/)).toBeInTheDocument();
    expect(screen.getByText("采集超时")).toBeInTheDocument();
  });
});

// ============================================================
// 删除和完成操作
// ============================================================

describe("SourcesWorkspaceView - 删除和完成操作", () => {
  it("非 DELETED 状态来源显示删除按钮", () => {
    setupMocks({
      sources: [makeSource({ status: "PARSED" })],
    });

    renderWithRoute();

    expect(screen.getByText("删除来源")).toBeInTheDocument();
  });

  it("DELETED 状态来源不显示删除按钮", () => {
    setupMocks({
      sources: [makeSource({ status: "DELETED" })],
    });

    renderWithRoute();

    expect(screen.queryByText("删除来源")).not.toBeInTheDocument();
  });

  it("PARSED 状态来源显示查看证据卡片链接", () => {
    setupMocks({
      sources: [makeSource({ status: "PARSED" })],
    });

    renderWithRoute();

    expect(screen.getByText("查看证据卡片")).toBeInTheDocument();
  });

  it("无 PARSED 来源时完成收集按钮被禁用", () => {
    setupMocks({
      sources: [makeSource({ status: "PENDING" })],
    });

    renderWithRoute();

    const completeBtn = screen.getByText("完成来源收集");
    expect(completeBtn).toBeDisabled();
    expect(screen.getByText(/至少需要一个已解析（PARSED）的来源/)).toBeInTheDocument();
  });

  it("有 PARSED 来源时完成收集按钮可用", () => {
    setupMocks({
      sources: [makeSource({ status: "PARSED" })],
    });

    renderWithRoute();

    const completeBtn = screen.getByText("完成来源收集");
    expect(completeBtn).not.toBeDisabled();
  });

  it("完成收集中按钮显示推进中", () => {
    setupMocks({
      sources: [makeSource({ status: "PARSED" })],
    });
    mockedUseCompleteSources.mockReturnValue({
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

describe("SourcesWorkspaceView - 项目状态标签", () => {
  it("显示项目状态中文标签", () => {
    setupMocks({ project: makeProject({ status: "SOURCES_COLLECTED" }) });

    renderWithRoute();

    expect(screen.getByText("[来源已收集]")).toBeInTheDocument();
  });

  it("未知状态显示原状态字符串", () => {
    setupMocks({ project: makeProject({ status: "UNKNOWN_STATUS" }) });

    renderWithRoute();

    expect(screen.getByText("[UNKNOWN_STATUS]")).toBeInTheDocument();
  });
});
