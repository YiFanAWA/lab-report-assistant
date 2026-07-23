/**
 * RequirementWorkspaceView 组件测试。
 *
 * 使用 React Testing Library 测试关键渲染路径和交互。
 * 通过 vi.mock 模拟 useProject + useSources + useCurrentPlan 等 hooks 依赖。
 *
 * 测试覆盖：
 * - 加载中/项目不存在状态
 * - 粘贴要求区域（输入、保存、校验、成功/失败提示）
 * - Word 上传区域（文件选择、校验）
 * - 已保存来源列表（展示、无来源提示）
 * - 任务单展示（CANDIDATE/CONFIRMED 状态、字段展示）
 * - 任务单编辑/保存/确认按钮门控
 * - 复刻层级不支持提示
 * - 任务列表展示
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// --- Mock hooks 依赖 ---

vi.mock("../../features/projects/hooks", () => ({
  useProject: vi.fn(),
}));

vi.mock("../../features/requirements/hooks", () => ({
  useSources: vi.fn(),
  useAddTextSource: vi.fn(),
  useAddDocxSource: vi.fn(),
  useCurrentPlan: vi.fn(),
  useGeneratePlan: vi.fn(),
  useUpdatePlan: vi.fn(),
  useConfirmPlan: vi.fn(),
}));

import { useProject } from "../../features/projects/hooks";
import {
  useSources,
  useAddTextSource,
  useAddDocxSource,
  useCurrentPlan,
  useGeneratePlan,
  useUpdatePlan,
  useConfirmPlan,
} from "../../features/requirements/hooks";
import { RequirementWorkspaceView } from "../RequirementWorkspaceView";
import type { Project } from "../../shared/types";
import type {
  RequirementSource,
  RequirementPlanResponse,
  RequirementTask,
} from "../../features/requirements/types";

const mockedUseProject = vi.mocked(useProject);
const mockedUseSources = vi.mocked(useSources);
const mockedUseAddTextSource = vi.mocked(useAddTextSource);
const mockedUseAddDocxSource = vi.mocked(useAddDocxSource);
const mockedUseCurrentPlan = vi.mocked(useCurrentPlan);
const mockedUseGeneratePlan = vi.mocked(useGeneratePlan);
const mockedUseUpdatePlan = vi.mocked(useUpdatePlan);
const mockedUseConfirmPlan = vi.mocked(useConfirmPlan);

// --- 测试辅助 ---

/** 构造测试用 Project。 */
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

/** 构造测试用 RequirementSource。 */
function makeSource(overrides: Partial<RequirementSource> = {}): RequirementSource {
  return {
    id: "src_001",
    project_id: "proj_001",
    source_type: "TEXT",
    title: "实验要求",
    original_text: "分析胃病数据",
    original_file_path: null,
    content_hash: "abc123",
    created_at: "2026-07-23T10:00:00Z",
    ...overrides,
  };
}

/** 构造测试用 RequirementTask。 */
function makeTask(overrides: Partial<RequirementTask> = {}): RequirementTask {
  return {
    title: "数据清洗",
    description: "处理缺失值",
    task_type: "REQUIRED",
    source_quote: "原文引用",
    ...overrides,
  };
}

/** 构造测试用 RequirementPlanResponse。 */
function makePlan(overrides: Partial<RequirementPlanResponse> = {}): RequirementPlanResponse {
  return {
    id: "plan_001",
    project_id: "proj_001",
    source_id: "src_001",
    status: "CANDIDATE",
    payload: {
      topic: "胃病数据分析",
      experiment_type: "数据分析与可视化",
      research_subject: "胃病数据",
      required_tasks: [],
      recommended_tasks: [],
      optional_tasks: [],
      out_of_scope_tasks: [],
      unknown_items: [],
      data_requirements: ["CSV"],
      method_requirements: ["描述性统计"],
      chart_requirements: ["直方图"],
      report_requirements: ["实验报告"],
      presentation_requirements: ["PPT"],
      acceptance_criteria: ["可追溯"],
      replication_level: {
        level: "L0",
        label: "不复刻",
        supported_in_v1: true,
        reason: "无复刻要求",
        suggested_scope: "独立分析",
      },
    },
    candidate_source: "LOCAL_RULE",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T10:00:00Z",
    confirmed_at: null,
    ...overrides,
  };
}

/** 设置所有 hooks 的默认 mock 值。 */
function setupMocks(options: {
  project?: Project | null;
  sources?: RequirementSource[];
  plan?: RequirementPlanResponse | null;
  projectLoading?: boolean;
}) {
  const {
    project = makeProject(),
    sources = [],
    plan = null,
    projectLoading = false,
  } = options;

  mockedUseProject.mockReturnValue({
    data: project,
    isLoading: projectLoading,
    isError: false,
    error: null,
  } as any);

  mockedUseSources.mockReturnValue({
    data: sources,
    isLoading: false,
  } as any);

  mockedUseCurrentPlan.mockReturnValue({
    data: plan,
    isLoading: false,
  } as any);

  // mutation hooks 默认非 pending
  const makeMutationMock = (data: unknown = null) => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    isError: false,
    isSuccess: false,
    data,
  });

  mockedUseAddTextSource.mockReturnValue(makeMutationMock() as any);
  mockedUseAddDocxSource.mockReturnValue(makeMutationMock() as any);
  mockedUseGeneratePlan.mockReturnValue(makeMutationMock() as any);
  mockedUseUpdatePlan.mockReturnValue(makeMutationMock() as any);
  mockedUseConfirmPlan.mockReturnValue(makeMutationMock() as any);
}

/** 用路由上下文渲染组件。 */
function renderWithRoute(projectId: string = "proj_001") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/projects/${projectId}/requirements`]}>
        <Routes>
          <Route path="/projects/:projectId/requirements" element={<RequirementWorkspaceView />} />
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

describe("RequirementWorkspaceView - 加载和错误状态", () => {
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
// 粘贴要求区域
// ============================================================

describe("RequirementWorkspaceView - 粘贴要求区域", () => {
  it("显示添加实验要求区域", () => {
    setupMocks({});

    renderWithRoute();

    expect(screen.getByText("添加实验要求")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("来源标题")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("粘贴老师给的实验要求…")).toBeInTheDocument();
  });

  it("显示保存要求按钮", () => {
    setupMocks({});

    renderWithRoute();

    expect(screen.getByText("保存要求")).toBeInTheDocument();
  });

  it("保存中时按钮显示保存中", () => {
    setupMocks({});
    mockedUseAddTextSource.mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
      data: null,
    } as any);

    renderWithRoute();

    expect(screen.getByText("保存中…")).toBeInTheDocument();
  });
});

// ============================================================
// Word 上传区域
// ============================================================

describe("RequirementWorkspaceView - Word 上传区域", () => {
  it("显示 Word 上传区域", () => {
    setupMocks({});

    renderWithRoute();

    expect(screen.getByText("上传 Word 要求")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Word 来源标题")).toBeInTheDocument();
  });

  it("未选择文件时点击上传显示校验错误", () => {
    setupMocks({});

    renderWithRoute();

    fireEvent.click(screen.getByText("上传 Word 要求"));

    expect(screen.getByText("请选择 .docx 文件")).toBeInTheDocument();
  });

  it("上传中时按钮显示上传中", () => {
    setupMocks({});
    mockedUseAddDocxSource.mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
      data: null,
    } as any);

    renderWithRoute();

    expect(screen.getByText("上传中…")).toBeInTheDocument();
  });
});

// ============================================================
// 已保存来源列表
// ============================================================

describe("RequirementWorkspaceView - 已保存来源列表", () => {
  it("无来源时不显示来源列表和生成按钮", () => {
    setupMocks({ sources: [] });

    renderWithRoute();

    expect(screen.queryByText("已保存的原始要求")).not.toBeInTheDocument();
    expect(screen.queryByText("生成任务单候选")).not.toBeInTheDocument();
  });

  it("有来源时显示来源列表", () => {
    const sources = [
      makeSource({ id: "src_001", title: "要求一", original_text: "文本内容一" }),
      makeSource({ id: "src_002", title: "要求二", original_text: "文本内容二" }),
    ];
    setupMocks({ sources });

    renderWithRoute();

    expect(screen.getByText("已保存的原始要求")).toBeInTheDocument();
    expect(screen.getByText("要求一")).toBeInTheDocument();
    expect(screen.getByText("要求二")).toBeInTheDocument();
    expect(screen.getByText("文本内容一")).toBeInTheDocument();
    expect(screen.getByText("文本内容二")).toBeInTheDocument();
  });

  it("长文本被截断显示省略号", () => {
    const longText = "x".repeat(300);
    setupMocks({ sources: [makeSource({ original_text: longText })] });

    renderWithRoute();

    expect(screen.getByText(/…$/)).toBeInTheDocument();
  });

  it("有来源时显示生成任务单按钮", () => {
    setupMocks({ sources: [makeSource()] });

    renderWithRoute();

    expect(screen.getByText("生成任务单候选")).toBeInTheDocument();
  });

  it("生成中时按钮显示生成中", () => {
    setupMocks({ sources: [makeSource()] });
    mockedUseGeneratePlan.mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
      data: null,
    } as any);

    renderWithRoute();

    expect(screen.getByText("生成中…")).toBeInTheDocument();
  });
});

// ============================================================
// 任务单展示
// ============================================================

describe("RequirementWorkspaceView - 任务单展示", () => {
  it("无任务单时不显示任务单区域", () => {
    setupMocks({ plan: null });

    renderWithRoute();

    expect(screen.queryByText("任务单")).not.toBeInTheDocument();
  });

  it("CANDIDATE 状态显示待确认标签", () => {
    setupMocks({ plan: makePlan({ status: "CANDIDATE" }) });

    renderWithRoute();

    expect(screen.getByText(/\[待确认\]/)).toBeInTheDocument();
  });

  it("CONFIRMED 状态显示已确认标签", () => {
    setupMocks({ plan: makePlan({ status: "CONFIRMED" }) });

    renderWithRoute();

    expect(screen.getByText(/\[已确认\]/)).toBeInTheDocument();
  });

  it("显示任务单字段", () => {
    setupMocks({
      plan: makePlan({
        payload: {
          ...makePlan().payload,
          topic: "自定义课题",
          experiment_type: "自定义类型",
          research_subject: "自定义对象",
        },
      }),
    });

    renderWithRoute();

    expect(screen.getByText("自定义课题")).toBeInTheDocument();
    expect(screen.getByText("自定义类型")).toBeInTheDocument();
    expect(screen.getByText("自定义对象")).toBeInTheDocument();
  });

  it("显示候选来源标签", () => {
    setupMocks({ plan: makePlan({ candidate_source: "LOCAL_RULE" }) });

    renderWithRoute();

    expect(screen.getByText(/\[LOCAL_RULE\]/)).toBeInTheDocument();
  });
});

// ============================================================
// 任务单按钮门控
// ============================================================

describe("RequirementWorkspaceView - 任务单按钮门控", () => {
  it("CANDIDATE 状态显示编辑/确认按钮", () => {
    setupMocks({ plan: makePlan({ status: "CANDIDATE" }) });

    renderWithRoute();

    expect(screen.getByText("编辑任务单")).toBeInTheDocument();
    expect(screen.getByText("确认任务单")).toBeInTheDocument();
  });

  it("CONFIRMED 状态不显示编辑/确认按钮", () => {
    setupMocks({ plan: makePlan({ status: "CONFIRMED" }) });

    renderWithRoute();

    expect(screen.queryByText("编辑任务单")).not.toBeInTheDocument();
    expect(screen.queryByText("确认任务单")).not.toBeInTheDocument();
  });

  it("确认中时按钮显示确认中", () => {
    setupMocks({ plan: makePlan({ status: "CANDIDATE" }) });
    mockedUseConfirmPlan.mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
      data: null,
    } as any);

    renderWithRoute();

    expect(screen.getByText("确认中…")).toBeInTheDocument();
  });

  it("CANDIDATE 状态显示确认前提示", () => {
    setupMocks({ plan: makePlan({ status: "CANDIDATE" }) });

    renderWithRoute();

    expect(screen.getByText(/确认前仍可修改/)).toBeInTheDocument();
  });

  it("CONFIRMED 状态不显示确认前提示", () => {
    setupMocks({ plan: makePlan({ status: "CONFIRMED" }) });

    renderWithRoute();

    expect(screen.queryByText(/确认前仍可修改/)).not.toBeInTheDocument();
  });
});

// ============================================================
// 复刻层级展示
// ============================================================

describe("RequirementWorkspaceView - 复刻层级", () => {
  it("显示复刻层级标签和原因", () => {
    setupMocks({
      plan: makePlan({
        payload: {
          ...makePlan().payload,
          replication_level: {
            level: "L1",
            label: "方法参考",
            supported_in_v1: true,
            reason: "仅参考方法",
            suggested_scope: "方法借鉴",
          },
        },
      }),
    });

    renderWithRoute();

    expect(screen.getByText(/L1/)).toBeInTheDocument();
    expect(screen.getByText(/方法参考/)).toBeInTheDocument();
    expect(screen.getByText("仅参考方法")).toBeInTheDocument();
  });

  it("不支持的复刻层级显示警告", () => {
    setupMocks({
      plan: makePlan({
        payload: {
          ...makePlan().payload,
          replication_level: {
            level: "L3",
            label: "完整复现",
            supported_in_v1: false,
            reason: "V1 不支持完整复现",
            suggested_scope: "降级为 L1",
          },
        },
      }),
    });

    renderWithRoute();

    expect(screen.getByText("（第一版不支持）")).toBeInTheDocument();
  });

  it("支持的复刻层级不显示警告", () => {
    setupMocks({ plan: makePlan() });

    renderWithRoute();

    expect(screen.queryByText("（第一版不支持）")).not.toBeInTheDocument();
  });
});

// ============================================================
// 任务列表展示
// ============================================================

describe("RequirementWorkspaceView - 任务列表", () => {
  it("显示必须任务", () => {
    const task = makeTask({ title: "数据清洗", task_type: "REQUIRED" });
    setupMocks({
      plan: makePlan({
        payload: {
          ...makePlan().payload,
          required_tasks: [task],
        },
      }),
    });

    renderWithRoute();

    expect(screen.getByText("必须任务")).toBeInTheDocument();
    expect(screen.getByText("数据清洗")).toBeInTheDocument();
  });

  it("显示推荐任务", () => {
    const task = makeTask({ title: "可视化探索", task_type: "RECOMMENDED" });
    setupMocks({
      plan: makePlan({
        payload: {
          ...makePlan().payload,
          recommended_tasks: [task],
        },
      }),
    });

    renderWithRoute();

    expect(screen.getByText("推荐任务")).toBeInTheDocument();
    expect(screen.getByText("可视化探索")).toBeInTheDocument();
  });

  it("显示超范围任务", () => {
    const task = makeTask({ title: "完整论文复现", task_type: "OUT_OF_SCOPE" });
    setupMocks({
      plan: makePlan({
        payload: {
          ...makePlan().payload,
          out_of_scope_tasks: [task],
        },
      }),
    });

    renderWithRoute();

    expect(screen.getByText("超范围任务")).toBeInTheDocument();
    expect(screen.getByText("完整论文复现")).toBeInTheDocument();
  });

  it("任务展示来源引用", () => {
    const task = makeTask({ title: "分析任务", source_quote: "原文引用内容" });
    setupMocks({
      plan: makePlan({
        payload: {
          ...makePlan().payload,
          required_tasks: [task],
        },
      }),
    });

    renderWithRoute();

    expect(screen.getByText("来源: 原文引用内容")).toBeInTheDocument();
  });

  it("无任务的列表不渲染", () => {
    setupMocks({ plan: makePlan() });

    renderWithRoute();

    // payload 中所有任务列表均为空，不显示任何任务列表标题
    expect(screen.queryByText("必须任务")).not.toBeInTheDocument();
    expect(screen.queryByText("推荐任务")).not.toBeInTheDocument();
  });
});

// ============================================================
// 验收条件
// ============================================================

describe("RequirementWorkspaceView - 验收条件", () => {
  it("显示验收条件列表", () => {
    setupMocks({
      plan: makePlan({
        payload: {
          ...makePlan().payload,
          acceptance_criteria: ["可追溯", "数据完整"],
        },
      }),
    });

    renderWithRoute();

    expect(screen.getByText("验收条件:")).toBeInTheDocument();
    expect(screen.getByText("可追溯")).toBeInTheDocument();
    expect(screen.getByText("数据完整")).toBeInTheDocument();
  });

  it("无验收条件时不显示验收条件区域", () => {
    setupMocks({
      plan: makePlan({
        payload: {
          ...makePlan().payload,
          acceptance_criteria: [],
        },
      }),
    });

    renderWithRoute();

    expect(screen.queryByText("验收条件:")).not.toBeInTheDocument();
  });
});

// ============================================================
// 项目状态标签
// ============================================================

describe("RequirementWorkspaceView - 项目状态标签", () => {
  it("显示项目状态中文标签", () => {
    setupMocks({ project: makeProject({ status: "REQUIREMENT_CONFIRMED" }) });

    renderWithRoute();

    expect(screen.getByText("[需求已确认]")).toBeInTheDocument();
  });

  it("未知状态显示原状态字符串", () => {
    setupMocks({ project: makeProject({ status: "UNKNOWN_STATUS" }) });

    renderWithRoute();

    expect(screen.getByText("[UNKNOWN_STATUS]")).toBeInTheDocument();
  });
});
