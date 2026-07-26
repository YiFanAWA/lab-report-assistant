/**
 * AnalysisWorkspaceView 组件测试。
 *
 * 使用 React Testing Library 测试关键渲染路径和交互。
 * 通过 vi.mock 模拟 useProject + datasets hooks + analysis hooks + useJob 依赖。
 *
 * 测试覆盖：
 * - 加载中/项目不存在状态
 * - 无就绪数据集提示
 * - 有就绪数据集显示生成按钮
 * - 分析方案列表展示
 * - 数据集筛选下拉框
 * - 方案状态标签
 * - 编辑/确认/拒绝按钮门控
 * - STALE 状态提示
 * - 完成分析方案确认按钮门控
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
}));

vi.mock("../../features/analysis/hooks", () => ({
  useAnalysisPlans: vi.fn(),
  useAnalysisPlan: vi.fn(),
  useGenerateAnalysisPlan: vi.fn(),
  useUpdateAnalysisPlan: vi.fn(),
  useConfirmAnalysisPlan: vi.fn(),
  useRejectAnalysisPlan: vi.fn(),
  useCompleteAnalysis: vi.fn(),
  useStreamGenerateAnalysisPlan: vi.fn(),
}));

vi.mock("../../features/jobs/hooks", () => ({
  useJob: vi.fn(),
}));

import { useProject } from "../../features/projects/hooks";
import { useDatasets } from "../../features/datasets/hooks";
import {
  useAnalysisPlans,
  useGenerateAnalysisPlan,
  useUpdateAnalysisPlan,
  useConfirmAnalysisPlan,
  useRejectAnalysisPlan,
  useCompleteAnalysis,
  useStreamGenerateAnalysisPlan,
} from "../../features/analysis/hooks";
import { useJob } from "../../features/jobs/hooks";
import { AnalysisWorkspaceView } from "../AnalysisWorkspaceView";
import type { Project } from "../../shared/types";
import type { Dataset } from "../../features/datasets/types";
import type { AnalysisPlan } from "../../features/analysis/types";

const mockedUseProject = vi.mocked(useProject);
const mockedUseDatasets = vi.mocked(useDatasets);
const mockedUseAnalysisPlans = vi.mocked(useAnalysisPlans);
const mockedUseGenerateAnalysisPlan = vi.mocked(useGenerateAnalysisPlan);
const mockedUseUpdateAnalysisPlan = vi.mocked(useUpdateAnalysisPlan);
const mockedUseConfirmAnalysisPlan = vi.mocked(useConfirmAnalysisPlan);
const mockedUseRejectAnalysisPlan = vi.mocked(useRejectAnalysisPlan);
const mockedUseCompleteAnalysis = vi.mocked(useCompleteAnalysis);
const mockedUseStreamGenerateAnalysisPlan = vi.mocked(useStreamGenerateAnalysisPlan);
const mockedUseJob = vi.mocked(useJob);

// --- 测试辅助 ---

/** 构造测试用 Project。 */
function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "proj_001",
    name: "胃病数据分析",
    topic: "胃病数据",
    status: "DATASET_READY",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T10:00:00Z",
    ...overrides,
  };
}

/** 构造测试用 Dataset（就绪状态）。 */
function makeReadyDataset(overrides: Partial<Dataset> = {}): Dataset {
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

/** 构造测试用 AnalysisPlan。 */
function makePlan(overrides: Partial<AnalysisPlan> = {}): AnalysisPlan {
  return {
    id: "plan_001",
    project_id: "proj_001",
    dataset_id: "ds_001",
    dataset_version_id: "ver_001",
    cleaning_plan: "[]",
    analysis_plan: "[]",
    chart_plan: "[]",
    status: "CANDIDATE",
    candidate_source: "LOCAL_RULE",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: null,
    confirmed_at: null,
    ...overrides,
  };
}

/** 设置所有 hooks 的默认 mock 值。 */
function setupMocks(options: {
  project?: Project | null | undefined;
  datasets?: Dataset[];
  plans?: AnalysisPlan[];
  projectLoading?: boolean;
  plansLoading?: boolean;
}) {
  const {
    project = makeProject(),
    datasets = [],
    plans = [],
    projectLoading = false,
    plansLoading = false,
  } = options;

  mockedUseProject.mockReturnValue({
    data: project,
    isLoading: projectLoading,
    isError: false,
    error: null,
  } as any);

  mockedUseDatasets.mockReturnValue({
    data: datasets,
    isLoading: false,
  } as any);

  mockedUseAnalysisPlans.mockReturnValue({
    data: plans,
    isLoading: plansLoading,
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

  mockedUseGenerateAnalysisPlan.mockReturnValue(makeMutationMock() as any);
  mockedUseUpdateAnalysisPlan.mockReturnValue(makeMutationMock() as any);
  mockedUseConfirmAnalysisPlan.mockReturnValue(makeMutationMock() as any);
  mockedUseRejectAnalysisPlan.mockReturnValue(makeMutationMock() as any);
  mockedUseCompleteAnalysis.mockReturnValue(makeMutationMock() as any);

  // SPEC 0021：流式生成 hook 默认值
  const makeStreamMock = () => ({
    streaming: false,
    chunks: "",
    result: null,
    error: null,
    start: vi.fn(),
    cancel: vi.fn(),
    reset: vi.fn(),
  });
  mockedUseStreamGenerateAnalysisPlan.mockReturnValue(makeStreamMock() as any);
}

/** 用路由上下文渲染组件。 */
function renderWithRoute(projectId: string = "proj_001") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/projects/${projectId}/analysis`]}>
        <Routes>
          <Route path="/projects/:projectId/analysis" element={<AnalysisWorkspaceView />} />
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

describe("AnalysisWorkspaceView - 加载和错误状态", () => {
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
// 生成分析方案区域
// ============================================================

describe("AnalysisWorkspaceView - 生成分析方案区域", () => {
  it("无就绪数据集时显示提示", () => {
    setupMocks({ datasets: [] });

    renderWithRoute();

    expect(screen.getByText(/当前没有已就绪（READY）的数据集/)).toBeInTheDocument();
  });

  it("有就绪数据集时显示生成方案候选按钮", () => {
    setupMocks({ datasets: [makeReadyDataset()] });

    renderWithRoute();

    expect(screen.getByText("生成方案候选")).toBeInTheDocument();
  });

  it("显示就绪数据集的标题", () => {
    setupMocks({
      datasets: [makeReadyDataset({ title: "胃病研究数据" })],
    });

    renderWithRoute();

    expect(screen.getAllByText("胃病研究数据").length).toBeGreaterThanOrEqual(1);
  });
});

// ============================================================
// 分析方案列表展示
// ============================================================

describe("AnalysisWorkspaceView - 分析方案列表展示", () => {
  it("无方案时显示空提示", () => {
    setupMocks({ plans: [] });

    renderWithRoute();

    expect(screen.getByText("还没有生成任何分析方案。")).toBeInTheDocument();
  });

  it("显示方案状态标签", () => {
    setupMocks({
      datasets: [makeReadyDataset()],
      plans: [makePlan({ status: "CANDIDATE" })],
    });

    renderWithRoute();

    expect(screen.getByText(/\[候选\]/)).toBeInTheDocument();
  });

  it("显示候选来源标签（本地规则）", () => {
    setupMocks({
      datasets: [makeReadyDataset()],
      plans: [makePlan({ candidate_source: "LOCAL_RULE" })],
    });

    renderWithRoute();

    expect(screen.getAllByText(/本地规则/).length).toBeGreaterThanOrEqual(1);
  });

  it("显示候选来源标签（模型）", () => {
    setupMocks({
      datasets: [makeReadyDataset()],
      plans: [makePlan({ candidate_source: "MODEL" })],
    });

    renderWithRoute();

    expect(screen.getByText(/模型/)).toBeInTheDocument();
  });

  it("显示数据集筛选下拉框", () => {
    setupMocks({
      datasets: [makeReadyDataset({ title: "数据集 A" })],
    });

    renderWithRoute();

    expect(screen.getByText("分析方案列表")).toBeInTheDocument();
    expect(screen.getByText("全部数据集")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "数据集 A" })).toBeInTheDocument();
  });
});

// ============================================================
// PlanCard target_fields 容错处理（V2.3.0 收口修复）
//
// 后端 LocalRule provider 在 V2.3.0 之前曾输出 target_fields 为字符串，
// 已保存的旧错误格式记录或用户手动编辑的 JSON 可能包含非数组值。
// PlanCard 不应该因为单个字段类型异常而崩溃整个页面。
// ============================================================

describe("AnalysisWorkspaceView - PlanCard target_fields 容错", () => {
  it("target_fields 为数组时正常显示", () => {
    const plan = makePlan({
      analysis_plan: JSON.stringify([
        {
          analysis_type: "DESCRIPTIVE_STATISTICS",
          target_fields: ["age", "gender"],
          method: "计算均值",
          expected_output: "统计表",
        },
      ]),
    });
    setupMocks({ datasets: [makeReadyDataset()], plans: [plan] });

    renderWithRoute();

    expect(screen.getByText(/DESCRIPTIVE_STATISTICS/)).toBeInTheDocument();
    expect(screen.getByText(/目标字段：age, gender/)).toBeInTheDocument();
  });

  it("target_fields 为字符串时不崩溃，容错展示", () => {
    const plan = makePlan({
      analysis_plan: JSON.stringify([
        {
          analysis_type: "FREQUENCY",
          target_fields: "gender",
          method: "统计频次",
          expected_output: "频次表",
        },
      ]),
    });
    setupMocks({ datasets: [makeReadyDataset()], plans: [plan] });

    // 不应该抛出 TypeError
    expect(() => renderWithRoute()).not.toThrow();

    expect(screen.getByText(/FREQUENCY/)).toBeInTheDocument();
    expect(screen.getByText(/目标字段：gender/)).toBeInTheDocument();
  });

  it("target_fields 为 null 时不崩溃，不显示目标字段", () => {
    const plan = makePlan({
      analysis_plan: JSON.stringify([
        {
          analysis_type: "CORRELATION",
          target_fields: null,
          method: "计算相关系数",
          expected_output: "相关矩阵",
        },
      ]),
    });
    setupMocks({ datasets: [makeReadyDataset()], plans: [plan] });

    expect(() => renderWithRoute()).not.toThrow();

    expect(screen.getByText(/CORRELATION/)).toBeInTheDocument();
    expect(screen.queryByText(/目标字段/)).not.toBeInTheDocument();
  });

  it("target_fields 为 undefined 时不崩溃", () => {
    const plan = makePlan({
      analysis_plan: JSON.stringify([
        {
          analysis_type: "MISSING_PATTERN",
          // 故意不设置 target_fields
          method: "分析缺失模式",
          expected_output: "缺失报告",
        },
      ]),
    });
    setupMocks({ datasets: [makeReadyDataset()], plans: [plan] });

    expect(() => renderWithRoute()).not.toThrow();

    expect(screen.getByText(/MISSING_PATTERN/)).toBeInTheDocument();
    expect(screen.queryByText(/目标字段/)).not.toBeInTheDocument();
  });

  it("多个条目混合数组/字符串 target_fields 时全部容错展示", () => {
    const plan = makePlan({
      analysis_plan: JSON.stringify([
        {
          analysis_type: "DESCRIPTIVE_STATISTICS",
          target_fields: ["age"],
          method: "计算均值",
          expected_output: "统计表",
        },
        {
          analysis_type: "FREQUENCY",
          target_fields: "gender",
          method: "统计频次",
          expected_output: "频次表",
        },
        {
          analysis_type: "GROUP_STATISTICS",
          target_fields: ["gender", "age"],
          method: "分组聚合",
          expected_output: "分组表",
        },
      ]),
    });
    setupMocks({ datasets: [makeReadyDataset()], plans: [plan] });

    expect(() => renderWithRoute()).not.toThrow();

    expect(screen.getByText(/DESCRIPTIVE_STATISTICS/)).toBeInTheDocument();
    expect(screen.getByText(/FREQUENCY/)).toBeInTheDocument();
    expect(screen.getByText(/GROUP_STATISTICS/)).toBeInTheDocument();
    // 数组形式：age；字符串形式：gender；数组形式：gender, age
    // 不崩溃 + 至少出现一次目标字段渲染即通过容错验证
    expect(screen.getAllByText(/目标字段：age/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/目标字段：gender/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/目标字段：gender, age/)).toBeInTheDocument();
  });
});

// ============================================================
// 方案操作按钮门控
// ============================================================

describe("AnalysisWorkspaceView - 方案操作按钮门控", () => {
  it("CANDIDATE 状态显示编辑/确认/拒绝按钮", () => {
    setupMocks({
      datasets: [makeReadyDataset()],
      plans: [makePlan({ status: "CANDIDATE" })],
    });

    renderWithRoute();

    expect(screen.getByText("编辑方案")).toBeInTheDocument();
    expect(screen.getByText("确认方案")).toBeInTheDocument();
    expect(screen.getByText("拒绝方案")).toBeInTheDocument();
  });

  it("CONFIRMED 状态不显示操作按钮", () => {
    setupMocks({
      datasets: [makeReadyDataset()],
      plans: [makePlan({ status: "CONFIRMED" })],
    });

    renderWithRoute();

    expect(screen.queryByText("编辑方案")).not.toBeInTheDocument();
    expect(screen.queryByText("确认方案")).not.toBeInTheDocument();
    expect(screen.queryByText("拒绝方案")).not.toBeInTheDocument();
  });

  it("REJECTED 状态不显示操作按钮", () => {
    setupMocks({
      datasets: [makeReadyDataset()],
      plans: [makePlan({ status: "REJECTED" })],
    });

    renderWithRoute();

    expect(screen.queryByText("编辑方案")).not.toBeInTheDocument();
    expect(screen.queryByText("确认方案")).not.toBeInTheDocument();
  });
});

// ============================================================
// STALE 状态
// ============================================================

describe("AnalysisWorkspaceView - STALE 状态", () => {
  it("STALE 状态显示失效提示", () => {
    setupMocks({
      datasets: [makeReadyDataset()],
      plans: [makePlan({ status: "STALE" })],
    });

    renderWithRoute();

    expect(screen.getByText(/此方案已失效/)).toBeInTheDocument();
  });

  it("STALE 状态显示编辑按钮", () => {
    setupMocks({
      datasets: [makeReadyDataset()],
      plans: [makePlan({ status: "STALE" })],
    });

    renderWithRoute();

    expect(screen.getByText("编辑方案")).toBeInTheDocument();
  });

  it("STALE 状态不显示确认按钮", () => {
    setupMocks({
      datasets: [makeReadyDataset()],
      plans: [makePlan({ status: "STALE" })],
    });

    renderWithRoute();

    expect(screen.queryByText("确认方案")).not.toBeInTheDocument();
  });
});

// ============================================================
// 完成分析方案确认
// ============================================================

describe("AnalysisWorkspaceView - 完成分析方案确认", () => {
  it("无已确认方案时完成按钮被禁用", () => {
    setupMocks({
      plans: [makePlan({ status: "CANDIDATE" })],
    });

    renderWithRoute();

    const completeBtn = screen.getByText("完成分析方案确认");
    expect(completeBtn).toBeDisabled();
  });

  it("有已确认方案时完成按钮可用", () => {
    setupMocks({
      plans: [makePlan({ status: "CONFIRMED" })],
    });

    renderWithRoute();

    const completeBtn = screen.getByText("完成分析方案确认");
    expect(completeBtn).not.toBeDisabled();
  });

  it("完成中按钮显示推进中", () => {
    setupMocks({
      plans: [makePlan({ status: "CONFIRMED" })],
    });
    mockedUseCompleteAnalysis.mockReturnValue({
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

describe("AnalysisWorkspaceView - 项目状态标签", () => {
  it("显示项目状态中文标签", () => {
    setupMocks({ project: makeProject({ status: "ANALYSIS_CONFIRMED" }) });

    renderWithRoute();

    expect(screen.getByText("[分析方案已确认]")).toBeInTheDocument();
  });

  it("未知状态显示原状态字符串", () => {
    setupMocks({ project: makeProject({ status: "UNKNOWN_STATUS" }) });

    renderWithRoute();

    expect(screen.getByText("[UNKNOWN_STATUS]")).toBeInTheDocument();
  });
});

// ============================================================
// SPEC 0021 流式生成 UI
// ============================================================

describe("AnalysisWorkspaceView - SPEC 0021 流式生成 UI", () => {
  it("有就绪数据集时显示流式生成按钮", () => {
    setupMocks({ datasets: [makeReadyDataset()] });

    renderWithRoute();

    expect(screen.getByText("流式生成")).toBeInTheDocument();
  });

  it("流式生成中按钮显示流式生成中", () => {
    setupMocks({ datasets: [makeReadyDataset()] });
    mockedUseStreamGenerateAnalysisPlan.mockReturnValue({
      streaming: true,
      chunks: "",
      result: null,
      error: null,
      start: vi.fn(),
      cancel: vi.fn(),
      reset: vi.fn(),
    } as any);

    renderWithRoute();

    expect(screen.getByText("流式生成中…")).toBeInTheDocument();
  });

  it("流式生成中显示 chunk 展示区", () => {
    setupMocks({ datasets: [makeReadyDataset()] });
    mockedUseStreamGenerateAnalysisPlan.mockReturnValue({
      streaming: true,
      chunks: '{"cleaning_plan":[',
      result: null,
      error: null,
      start: vi.fn(),
      cancel: vi.fn(),
      reset: vi.fn(),
    } as any);

    renderWithRoute();

    expect(screen.getByText(/正在逐 chunk 生成/)).toBeInTheDocument();
    expect(screen.getByText('{"cleaning_plan":[')).toBeInTheDocument();
  });

  it("流式生成中显示取消按钮", () => {
    setupMocks({ datasets: [makeReadyDataset()] });
    const cancelSpy = vi.fn();
    mockedUseStreamGenerateAnalysisPlan.mockReturnValue({
      streaming: true,
      chunks: "部分",
      result: null,
      error: null,
      start: vi.fn(),
      cancel: cancelSpy,
      reset: vi.fn(),
    } as any);

    renderWithRoute();

    const cancelBtn = screen.getByText("取消");
    expect(cancelBtn).toBeInTheDocument();
    fireEvent.click(cancelBtn);
    expect(cancelSpy).toHaveBeenCalled();
  });

  it("流式生成完成后显示完成提示", () => {
    setupMocks({ datasets: [makeReadyDataset()] });
    mockedUseStreamGenerateAnalysisPlan.mockReturnValue({
      streaming: false,
      chunks: "",
      result: {
        plan_id: "plan_001",
        candidate_source: "DEEPSEEK",
        fallback_used: false,
      },
      error: null,
      start: vi.fn(),
      cancel: vi.fn(),
      reset: vi.fn(),
    } as any);

    renderWithRoute();

    expect(screen.getByText(/流式生成完成 ✓/)).toBeInTheDocument();
    expect(screen.getByText(/DEEPSEEK/)).toBeInTheDocument();
    expect(screen.getByText(/plan_001/)).toBeInTheDocument();
  });

  it("流式生成降级时完成提示显示降级标记", () => {
    setupMocks({ datasets: [makeReadyDataset()] });
    mockedUseStreamGenerateAnalysisPlan.mockReturnValue({
      streaming: false,
      chunks: "",
      result: {
        plan_id: "plan_002",
        candidate_source: "LOCAL_RULE",
        fallback_used: true,
      },
      error: null,
      start: vi.fn(),
      cancel: vi.fn(),
      reset: vi.fn(),
    } as any);

    renderWithRoute();

    expect(screen.getByText(/降级/)).toBeInTheDocument();
    expect(screen.getByText(/LOCAL_RULE/)).toBeInTheDocument();
  });

  it("流式生成失败显示错误详情", () => {
    setupMocks({ datasets: [makeReadyDataset()] });
    mockedUseStreamGenerateAnalysisPlan.mockReturnValue({
      streaming: false,
      chunks: "",
      result: null,
      error: {
        error_code: "ANALYSIS_PLAN_JSON_PARSE_ERROR",
        message: "JSON 校验失败",
        partial_text: '{"cleaning_plan":[',
      },
      start: vi.fn(),
      cancel: vi.fn(),
      reset: vi.fn(),
    } as any);

    renderWithRoute();

    expect(screen.getByText(/流式生成失败/)).toBeInTheDocument();
    expect(screen.getByText(/JSON 校验失败/)).toBeInTheDocument();
  });

  it("流式生成失败时展示 partial_text 详情", () => {
    setupMocks({ datasets: [makeReadyDataset()] });
    mockedUseStreamGenerateAnalysisPlan.mockReturnValue({
      streaming: false,
      chunks: "",
      result: null,
      error: {
        error_code: "ANALYSIS_PLAN_JSON_PARSE_ERROR",
        message: "JSON 校验失败",
        partial_text: '{"cleaning_plan":[',
      },
      start: vi.fn(),
      cancel: vi.fn(),
      reset: vi.fn(),
    } as any);

    renderWithRoute();

    expect(screen.getByText("查看已生成内容")).toBeInTheDocument();
  });

  it("点击流式生成按钮调用 start()", () => {
    setupMocks({ datasets: [makeReadyDataset()] });
    const startSpy = vi.fn();
    mockedUseStreamGenerateAnalysisPlan.mockReturnValue({
      streaming: false,
      chunks: "",
      result: null,
      error: null,
      start: startSpy,
      cancel: vi.fn(),
      reset: vi.fn(),
    } as any);

    renderWithRoute();

    const streamBtn = screen.getByText("流式生成");
    fireEvent.click(streamBtn);
    expect(startSpy).toHaveBeenCalled();
  });
});
