/**
 * OutlineWorkspaceView 组件测试。
 *
 * 使用 React Testing Library 测试关键渲染路径和交互。
 * 通过 vi.mock 模拟 useProject + outlines hooks + useJob 依赖。
 *
 * 测试覆盖：
 * - 加载中/项目不存在状态
 * - 项目状态门控（未到 RESULT_CONFIRMED 不可生成）
 * - 已有候选时不显示生成按钮
 * - 大纲列表展示
 * - 大纲状态标签
 * - 编辑/确认/拒绝按钮门控
 * - STALE 状态提示
 * - CONFIRMED 状态显示 Word/PPT 生成按钮
 * - 章节展示
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
  useOutlines: vi.fn(),
  useOutline: vi.fn(),
  useGenerateOutline: vi.fn(),
  useUpdateOutline: vi.fn(),
  useConfirmOutline: vi.fn(),
  useRejectOutline: vi.fn(),
  useGenerateWord: vi.fn(),
  useGeneratePpt: vi.fn(),
  useDeliverables: vi.fn(),
  useDeliverableVersions: vi.fn(),
  useCompleteProject: vi.fn(),
  useWordTemplate: vi.fn(),
  useUploadWordTemplate: vi.fn(),
  useDeleteWordTemplate: vi.fn(),
}));

vi.mock("../../features/jobs/hooks", () => ({
  useJob: vi.fn(),
}));

import { useProject } from "../../features/projects/hooks";
import {
  useOutlines,
  useGenerateOutline,
  useUpdateOutline,
  useConfirmOutline,
  useRejectOutline,
  useGenerateWord,
  useGeneratePpt,
  useWordTemplate,
  useUploadWordTemplate,
  useDeleteWordTemplate,
} from "../../features/outlines/hooks";
import { useJob } from "../../features/jobs/hooks";
import { OutlineWorkspaceView } from "../OutlineWorkspaceView";
import type { Project } from "../../shared/types";
import type { Outline } from "../../features/outlines/types";

const mockedUseProject = vi.mocked(useProject);
const mockedUseOutlines = vi.mocked(useOutlines);
const mockedUseGenerateOutline = vi.mocked(useGenerateOutline);
const mockedUseUpdateOutline = vi.mocked(useUpdateOutline);
const mockedUseConfirmOutline = vi.mocked(useConfirmOutline);
const mockedUseRejectOutline = vi.mocked(useRejectOutline);
const mockedUseGenerateWord = vi.mocked(useGenerateWord);
const mockedUseGeneratePpt = vi.mocked(useGeneratePpt);
const mockedUseWordTemplate = vi.mocked(useWordTemplate);
const mockedUseUploadWordTemplate = vi.mocked(useUploadWordTemplate);
const mockedUseDeleteWordTemplate = vi.mocked(useDeleteWordTemplate);
const mockedUseJob = vi.mocked(useJob);

// --- 测试辅助 ---

/** 构造测试用 Project。 */
function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "proj_001",
    name: "胃病数据分析",
    topic: "胃病数据",
    status: "RESULT_CONFIRMED",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T10:00:00Z",
    ...overrides,
  };
}

/** 构造测试用 Outline。 */
function makeOutline(overrides: Partial<Outline> = {}): Outline {
  return {
    id: "outline_001",
    project_id: "proj_001",
    sections: [
      {
        id: "sec_001",
        title: "引言",
        content: "这是引言内容",
        source_type: "REQUIREMENT",
        source_ids: ["src_001"],
      },
    ],
    status: "CANDIDATE",
    candidate_source: "LOCAL_RULE",
    version: 1,
    created_at: "2026-07-23T10:00:00Z",
    updated_at: null,
    confirmed_at: null,
    ...overrides,
  };
}

/** 设置所有 hooks 的默认 mock 值。 */
function setupMocks(options: {
  project?: Project | null | undefined;
  outlines?: Outline[];
  projectLoading?: boolean;
  outlinesLoading?: boolean;
}) {
  const {
    project = makeProject(),
    outlines = [],
    projectLoading = false,
    outlinesLoading = false,
  } = options;

  mockedUseProject.mockReturnValue({
    data: project,
    isLoading: projectLoading,
    isError: false,
    error: null,
  } as any);

  mockedUseOutlines.mockReturnValue({
    data: outlines,
    isLoading: outlinesLoading,
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

  mockedUseGenerateOutline.mockReturnValue(makeMutationMock() as any);
  mockedUseUpdateOutline.mockReturnValue(makeMutationMock() as any);
  mockedUseConfirmOutline.mockReturnValue(makeMutationMock() as any);
  mockedUseRejectOutline.mockReturnValue(makeMutationMock() as any);
  mockedUseGenerateWord.mockReturnValue(makeMutationMock() as any);
  mockedUseGeneratePpt.mockReturnValue(makeMutationMock() as any);
  mockedUseUploadWordTemplate.mockReturnValue(makeMutationMock() as any);
  mockedUseDeleteWordTemplate.mockReturnValue(makeMutationMock() as any);

  // Word 模板查询默认返回 null（无模板）
  mockedUseWordTemplate.mockReturnValue({
    data: null,
    isLoading: false,
  } as any);
}

/** 用路由上下文渲染组件。 */
function renderWithRoute(projectId: string = "proj_001") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/projects/${projectId}/outline`]}>
        <Routes>
          <Route path="/projects/:projectId/outline" element={<OutlineWorkspaceView />} />
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

describe("OutlineWorkspaceView - 加载和错误状态", () => {
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
// 生成大纲门控
// ============================================================

describe("OutlineWorkspaceView - 生成大纲门控", () => {
  it("项目状态未到 RESULT_CONFIRMED 时显示提示", () => {
    setupMocks({ project: makeProject({ status: "ANALYSIS_CONFIRMED" }) });

    renderWithRoute();

    expect(screen.getByText(/需要先推进到「结果已确认/)).toBeInTheDocument();
  });

  it("项目状态为 RESULT_CONFIRMED 且无候选时显示生成按钮", () => {
    setupMocks({
      project: makeProject({ status: "RESULT_CONFIRMED" }),
      outlines: [],
    });

    renderWithRoute();

    // h3 标题和按钮文本都是"生成大纲候选"，需按按钮角色精确匹配
    expect(screen.getByRole("button", { name: "生成大纲候选" })).toBeInTheDocument();
  });

  it("已有候选大纲时不显示生成按钮", () => {
    setupMocks({
      project: makeProject({ status: "RESULT_CONFIRMED" }),
      outlines: [makeOutline({ status: "CANDIDATE" })],
    });

    renderWithRoute();

    // h3 标题"生成大纲候选"仍存在，但按钮不渲染
    expect(screen.queryByRole("button", { name: "生成大纲候选" })).not.toBeInTheDocument();
    expect(screen.getByText(/当前已有候选或已确认大纲/)).toBeInTheDocument();
  });
});

// ============================================================
// 大纲列表展示
// ============================================================

describe("OutlineWorkspaceView - 大纲列表展示", () => {
  it("无大纲时显示空提示", () => {
    setupMocks({ outlines: [] });

    renderWithRoute();

    expect(screen.getByText("还没有生成任何大纲。")).toBeInTheDocument();
  });

  it("显示大纲版本号", () => {
    setupMocks({
      outlines: [makeOutline({ version: 1 })],
    });

    renderWithRoute();

    expect(screen.getByText(/v1/)).toBeInTheDocument();
  });

  it("显示大纲状态标签（候选）", () => {
    setupMocks({
      outlines: [makeOutline({ status: "CANDIDATE" })],
    });

    renderWithRoute();

    expect(screen.getByText(/\[候选\]/)).toBeInTheDocument();
  });

  it("显示大纲状态标签（已确认）", () => {
    setupMocks({
      outlines: [makeOutline({ status: "CONFIRMED" })],
    });

    renderWithRoute();

    expect(screen.getByText(/\[已确认\]/)).toBeInTheDocument();
  });

  it("显示候选来源标签", () => {
    setupMocks({
      outlines: [makeOutline({ candidate_source: "LOCAL_RULE" })],
    });

    renderWithRoute();

    expect(screen.getByText(/本地规则/)).toBeInTheDocument();
  });

  it("显示大纲章节标题", () => {
    setupMocks({
      outlines: [
        makeOutline({
          sections: [
            {
              id: "sec_001",
              title: "实验方法",
              content: "方法内容",
              source_type: "EVIDENCE",
              source_ids: ["ev_001"],
            },
          ],
        }),
      ],
    });

    renderWithRoute();

    expect(screen.getByText("实验方法")).toBeInTheDocument();
  });

  it("显示章节内容", () => {
    setupMocks({
      outlines: [
        makeOutline({
          sections: [
            {
              id: "sec_001",
              title: "结论",
              content: "这是实验结论内容",
              source_type: "SUMMARY",
              source_ids: [],
            },
          ],
        }),
      ],
    });

    renderWithRoute();

    expect(screen.getByText("这是实验结论内容")).toBeInTheDocument();
  });

  it("显示章节来源类型标签", () => {
    setupMocks({
      outlines: [
        makeOutline({
          sections: [
            {
              id: "sec_001",
              title: "分析",
              content: "分析内容",
              source_type: "ANALYSIS",
              source_ids: [],
            },
          ],
        }),
      ],
    });

    renderWithRoute();

    expect(screen.getByText("分析方案")).toBeInTheDocument();
  });
});

// ============================================================
// 大纲操作按钮门控
// ============================================================

describe("OutlineWorkspaceView - 大纲操作按钮门控", () => {
  it("CANDIDATE 状态显示编辑/确认/拒绝按钮", () => {
    setupMocks({
      outlines: [makeOutline({ status: "CANDIDATE" })],
    });

    renderWithRoute();

    expect(screen.getByText("编辑大纲")).toBeInTheDocument();
    expect(screen.getByText("确认大纲")).toBeInTheDocument();
    expect(screen.getByText("拒绝大纲")).toBeInTheDocument();
  });

  it("CONFIRMED 状态不显示编辑/确认/拒绝按钮", () => {
    setupMocks({
      outlines: [makeOutline({ status: "CONFIRMED" })],
    });

    renderWithRoute();

    expect(screen.queryByText("编辑大纲")).not.toBeInTheDocument();
    expect(screen.queryByText("确认大纲")).not.toBeInTheDocument();
    expect(screen.queryByText("拒绝大纲")).not.toBeInTheDocument();
  });

  it("REJECTED 状态不显示操作按钮", () => {
    setupMocks({
      outlines: [makeOutline({ status: "REJECTED" })],
    });

    renderWithRoute();

    expect(screen.queryByText("编辑大纲")).not.toBeInTheDocument();
    expect(screen.queryByText("确认大纲")).not.toBeInTheDocument();
  });
});

// ============================================================
// STALE 状态
// ============================================================

describe("OutlineWorkspaceView - STALE 状态", () => {
  it("STALE 状态显示失效提示", () => {
    setupMocks({
      outlines: [makeOutline({ status: "STALE" })],
    });

    renderWithRoute();

    expect(screen.getByText(/此大纲已失效/)).toBeInTheDocument();
  });

  it("STALE 状态显示编辑按钮", () => {
    setupMocks({
      outlines: [makeOutline({ status: "STALE" })],
    });

    renderWithRoute();

    expect(screen.getByText("编辑大纲")).toBeInTheDocument();
  });

  it("STALE 状态不显示确认按钮", () => {
    setupMocks({
      outlines: [makeOutline({ status: "STALE" })],
    });

    renderWithRoute();

    expect(screen.queryByText("确认大纲")).not.toBeInTheDocument();
  });
});

// ============================================================
// CONFIRMED 状态的 Word/PPT 生成
// ============================================================

describe("OutlineWorkspaceView - Word/PPT 生成", () => {
  it("CONFIRMED 状态显示生成 Word 和 PPT 按钮", () => {
    setupMocks({
      outlines: [makeOutline({ status: "CONFIRMED" })],
    });

    renderWithRoute();

    expect(screen.getByText("生成 Word")).toBeInTheDocument();
    expect(screen.getByText("生成 PPT")).toBeInTheDocument();
  });

  it("CANDIDATE 状态不显示 Word/PPT 生成按钮", () => {
    setupMocks({
      outlines: [makeOutline({ status: "CANDIDATE" })],
    });

    renderWithRoute();

    expect(screen.queryByText("生成 Word")).not.toBeInTheDocument();
    expect(screen.queryByText("生成 PPT")).not.toBeInTheDocument();
  });

  it("CONFIRMED 状态显示前往交付物工作区链接", () => {
    setupMocks({
      outlines: [makeOutline({ status: "CONFIRMED" })],
    });

    renderWithRoute();

    expect(screen.getByText(/前往交付物工作区查看和下载/)).toBeInTheDocument();
  });
});

// ============================================================
// 项目状态标签
// ============================================================

describe("OutlineWorkspaceView - 项目状态标签", () => {
  it("显示项目状态中文标签", () => {
    setupMocks({ project: makeProject({ status: "OUTLINE_CONFIRMED" }) });

    renderWithRoute();

    expect(screen.getByText("[大纲已确认]")).toBeInTheDocument();
  });

  it("未知状态显示原状态字符串", () => {
    setupMocks({ project: makeProject({ status: "UNKNOWN_STATUS" }) });

    renderWithRoute();

    expect(screen.getByText("[UNKNOWN_STATUS]")).toBeInTheDocument();
  });
});
