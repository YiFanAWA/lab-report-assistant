/**
 * DeliverableWorkspaceView 组件测试。
 *
 * 使用 React Testing Library 测试关键渲染路径和交互。
 * 通过 vi.mock 模拟 useProject + outlines hooks 依赖。
 *
 * 测试覆盖：
 * - 加载中/项目不存在状态
 * - 无交付物提示
 * - 交付物列表展示
 * - Word/PPT 类型标签
 * - 交付物状态标签
 * - 版本列表展示
 * - 下载链接（成功版本）
 * - 失败版本错误展示
 * - STALE 交付物提示
 * - 完成项目按钮门控
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// --- Mock hooks 依赖 ---

vi.mock("../../features/projects/hooks", () => ({
  useProject: vi.fn(),
}));

vi.mock("../../features/outlines/hooks", () => ({
  useDeliverables: vi.fn(),
  useDeliverableVersions: vi.fn(),
  useCompleteProject: vi.fn(),
}));

import { useProject } from "../../features/projects/hooks";
import {
  useDeliverables,
  useDeliverableVersions,
  useCompleteProject,
} from "../../features/outlines/hooks";
import { DeliverableWorkspaceView } from "../DeliverableWorkspaceView";
import type { Project } from "../../shared/types";
import type {
  Deliverable,
  DeliverableVersion,
} from "../../features/outlines/types";

const mockedUseProject = vi.mocked(useProject);
const mockedUseDeliverables = vi.mocked(useDeliverables);
const mockedUseDeliverableVersions = vi.mocked(useDeliverableVersions);
const mockedUseCompleteProject = vi.mocked(useCompleteProject);

// --- 测试辅助 ---

/** 构造测试用 Project。 */
function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "proj_001",
    name: "胃病数据分析",
    topic: "胃病数据",
    status: "OUTLINE_CONFIRMED",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T10:00:00Z",
    ...overrides,
  };
}

/** 构造测试用 Deliverable。 */
function makeDeliverable(overrides: Partial<Deliverable> = {}): Deliverable {
  return {
    id: "del_001",
    project_id: "proj_001",
    outline_id: "outline_001",
    deliverable_type: "WORD",
    status: "SUCCEEDED",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: null,
    ...overrides,
  };
}

/** 构造测试用 DeliverableVersion。 */
function makeVersion(overrides: Partial<DeliverableVersion> = {}): DeliverableVersion {
  return {
    id: "ver_001",
    deliverable_id: "del_001",
    version: 1,
    status: "SUCCEEDED",
    file_path: "/deliverables/word.docx",
    file_size_bytes: 20480,
    error_code: null,
    error_message: null,
    started_at: "2026-07-23T10:00:00Z",
    finished_at: "2026-07-23T10:00:30Z",
    duration_seconds: 30.0,
    created_at: "2026-07-23T10:00:00Z",
    ...overrides,
  };
}

/** 设置所有 hooks 的默认 mock 值。 */
function setupMocks(options: {
  project?: Project | null | undefined;
  deliverables?: Deliverable[];
  versions?: DeliverableVersion[];
  projectLoading?: boolean;
  deliverablesLoading?: boolean;
  versionsLoading?: boolean;
}) {
  const {
    project = makeProject(),
    deliverables = [],
    versions = [],
    projectLoading = false,
    deliverablesLoading = false,
    versionsLoading = false,
  } = options;

  mockedUseProject.mockReturnValue({
    data: project,
    isLoading: projectLoading,
    isError: false,
    error: null,
  } as any);

  mockedUseDeliverables.mockReturnValue({
    data: deliverables,
    isLoading: deliverablesLoading,
  } as any);

  mockedUseDeliverableVersions.mockReturnValue({
    data: versions,
    isLoading: versionsLoading,
  } as any);

  // mutation hooks 默认非 pending
  mockedUseCompleteProject.mockReturnValue({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    isError: false,
    isSuccess: false,
    data: null,
  } as any);
}

/** 用路由上下文渲染组件。 */
function renderWithRoute(projectId: string = "proj_001") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/projects/${projectId}/deliverables`]}>
        <Routes>
          <Route path="/projects/:projectId/deliverables" element={<DeliverableWorkspaceView />} />
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

describe("DeliverableWorkspaceView - 加载和错误状态", () => {
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
// 交付物列表展示
// ============================================================

describe("DeliverableWorkspaceView - 交付物列表展示", () => {
  it("无交付物时显示空提示", () => {
    setupMocks({ deliverables: [] });

    renderWithRoute();

    expect(screen.getByText(/当前还没有任何交付物/)).toBeInTheDocument();
  });

  it("显示 Word 交付物类型标签", () => {
    setupMocks({
      deliverables: [makeDeliverable({ deliverable_type: "WORD" })],
      versions: [makeVersion()],
    });

    renderWithRoute();

    expect(screen.getByText("Word 文档")).toBeInTheDocument();
  });

  it("显示 PPT 交付物类型标签", () => {
    setupMocks({
      deliverables: [makeDeliverable({ id: "del_002", deliverable_type: "PPT" })],
      versions: [makeVersion({ deliverable_id: "del_002" })],
    });

    renderWithRoute();

    expect(screen.getByText("PPT 演示")).toBeInTheDocument();
  });

  it("显示交付物状态标签（已生成）", () => {
    setupMocks({
      deliverables: [makeDeliverable({ status: "SUCCEEDED" })],
      versions: [makeVersion()],
    });

    renderWithRoute();

    expect(screen.getAllByText("[已生成]").length).toBeGreaterThanOrEqual(1);
  });

  it("显示交付物状态标签（生成中）", () => {
    setupMocks({
      deliverables: [makeDeliverable({ status: "RUNNING" })],
      versions: [],
    });

    renderWithRoute();

    expect(screen.getByText("[生成中]")).toBeInTheDocument();
  });

  it("STALE 交付物显示失效提示", () => {
    setupMocks({
      deliverables: [makeDeliverable({ status: "STALE" })],
      versions: [],
    });

    renderWithRoute();

    expect(screen.getByText(/此交付物已失效/)).toBeInTheDocument();
  });
});

// ============================================================
// 版本列表展示
// ============================================================

describe("DeliverableWorkspaceView - 版本列表展示", () => {
  it("无版本时显示空提示", () => {
    setupMocks({
      deliverables: [makeDeliverable()],
      versions: [],
    });

    renderWithRoute();

    expect(screen.getByText("暂无版本记录。")).toBeInTheDocument();
  });

  it("显示版本号", () => {
    setupMocks({
      deliverables: [makeDeliverable()],
      versions: [makeVersion({ version: 1 }), makeVersion({ id: "ver_002", version: 2 })],
    });

    renderWithRoute();

    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByText("v2")).toBeInTheDocument();
  });

  it("成功版本显示下载链接", () => {
    setupMocks({
      deliverables: [makeDeliverable()],
      versions: [makeVersion({ status: "SUCCEEDED", file_path: "/deliverables/word.docx" })],
    });

    renderWithRoute();

    expect(screen.getByText("下载")).toBeInTheDocument();
  });

  it("失败版本显示错误信息", () => {
    setupMocks({
      deliverables: [makeDeliverable()],
      versions: [
        makeVersion({
          status: "FAILED",
          file_path: null,
          error_code: "GEN_ERROR",
          error_message: "生成失败原因",
        }),
      ],
    });

    renderWithRoute();

    expect(screen.getByText(/失败：GEN_ERROR/)).toBeInTheDocument();
    expect(screen.getByText(/生成失败原因/)).toBeInTheDocument();
  });

  it("失败版本不显示下载链接", () => {
    setupMocks({
      deliverables: [makeDeliverable()],
      versions: [
        makeVersion({
          status: "FAILED",
          file_path: null,
          error_code: "GEN_ERROR",
          error_message: "失败",
        }),
      ],
    });

    renderWithRoute();

    expect(screen.queryByText("下载")).not.toBeInTheDocument();
  });

  it("显示版本文件大小", () => {
    setupMocks({
      deliverables: [makeDeliverable()],
      versions: [makeVersion({ file_size_bytes: 20480 })],
    });

    renderWithRoute();

    expect(screen.getByText(/20.0 KB/)).toBeInTheDocument();
  });
});

// ============================================================
// 完成项目按钮门控
// ============================================================

describe("DeliverableWorkspaceView - 完成项目按钮门控", () => {
  it("只有 Word 成功时完成按钮被禁用", () => {
    setupMocks({
      deliverables: [makeDeliverable({ deliverable_type: "WORD", status: "SUCCEEDED" })],
      versions: [makeVersion()],
    });

    renderWithRoute();

    const completeBtn = screen.getByText("完成项目");
    expect(completeBtn).toBeDisabled();
  });

  it("只有 PPT 成功时完成按钮被禁用", () => {
    setupMocks({
      deliverables: [makeDeliverable({ id: "del_002", deliverable_type: "PPT", status: "SUCCEEDED" })],
      versions: [makeVersion({ deliverable_id: "del_002" })],
    });

    renderWithRoute();

    const completeBtn = screen.getByText("完成项目");
    expect(completeBtn).toBeDisabled();
  });

  it("Word 和 PPT 都成功时完成按钮可用", () => {
    setupMocks({
      deliverables: [
        makeDeliverable({ id: "del_001", deliverable_type: "WORD", status: "SUCCEEDED" }),
        makeDeliverable({ id: "del_002", deliverable_type: "PPT", status: "SUCCEEDED" }),
      ],
      versions: [makeVersion()],
    });

    renderWithRoute();

    const completeBtn = screen.getByText("完成项目");
    expect(completeBtn).not.toBeDisabled();
  });

  it("项目已 COMPLETED 时完成按钮被禁用", () => {
    setupMocks({
      project: makeProject({ status: "COMPLETED" }),
      deliverables: [
        makeDeliverable({ id: "del_001", deliverable_type: "WORD", status: "SUCCEEDED" }),
        makeDeliverable({ id: "del_002", deliverable_type: "PPT", status: "SUCCEEDED" }),
      ],
      versions: [makeVersion()],
    });

    renderWithRoute();

    const completeBtn = screen.getByText("完成项目");
    expect(completeBtn).toBeDisabled();
  });

  it("完成中按钮显示推进中", () => {
    setupMocks({
      deliverables: [
        makeDeliverable({ id: "del_001", deliverable_type: "WORD", status: "SUCCEEDED" }),
        makeDeliverable({ id: "del_002", deliverable_type: "PPT", status: "SUCCEEDED" }),
      ],
      versions: [makeVersion()],
    });
    mockedUseCompleteProject.mockReturnValue({
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

describe("DeliverableWorkspaceView - 项目状态标签", () => {
  it("显示项目状态中文标签", () => {
    setupMocks({
      project: makeProject({ status: "GENERATING" }),
      deliverables: [],
    });

    renderWithRoute();

    expect(screen.getByText("[交付物生成中]")).toBeInTheDocument();
  });
});
