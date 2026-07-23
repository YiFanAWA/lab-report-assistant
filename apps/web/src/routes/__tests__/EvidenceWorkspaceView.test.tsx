/**
 * EvidenceWorkspaceView 组件测试。
 *
 * 使用 React Testing Library 测试关键渲染路径和交互。
 * 通过 vi.mock 模拟 useProject + sources hooks + evidence hooks + useJob 依赖。
 *
 * 测试覆盖：
 * - 加载中/项目不存在状态
 * - 无已解析来源提示
 * - 有已解析来源显示生成按钮
 * - 证据卡片列表展示
 * - 状态筛选下拉框
 * - 卡片状态标签
 * - 编辑/确认/拒绝按钮门控
 * - STALE 状态提示
 * - 完成证据确认按钮
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// --- Mock hooks 依赖 ---

vi.mock("../../features/projects/hooks", () => ({
  useProject: vi.fn(),
}));

vi.mock("../../features/sources/hooks", () => ({
  useSources: vi.fn(),
}));

vi.mock("../../features/evidence/hooks", () => ({
  useEvidenceCards: vi.fn(),
  useGenerateEvidence: vi.fn(),
  useUpdateEvidence: vi.fn(),
  useConfirmEvidence: vi.fn(),
  useRejectEvidence: vi.fn(),
  useCompleteEvidence: vi.fn(),
}));

vi.mock("../../features/jobs/hooks", () => ({
  useJob: vi.fn(),
}));

import { useProject } from "../../features/projects/hooks";
import { useSources } from "../../features/sources/hooks";
import {
  useEvidenceCards,
  useGenerateEvidence,
  useUpdateEvidence,
  useConfirmEvidence,
  useRejectEvidence,
  useCompleteEvidence,
} from "../../features/evidence/hooks";
import { useJob } from "../../features/jobs/hooks";
import { EvidenceWorkspaceView } from "../EvidenceWorkspaceView";
import type { Project } from "../../shared/types";
import type { Source } from "../../features/sources/types";
import type { EvidenceCard } from "../../features/evidence/types";

const mockedUseProject = vi.mocked(useProject);
const mockedUseSources = vi.mocked(useSources);
const mockedUseEvidenceCards = vi.mocked(useEvidenceCards);
const mockedUseGenerateEvidence = vi.mocked(useGenerateEvidence);
const mockedUseUpdateEvidence = vi.mocked(useUpdateEvidence);
const mockedUseConfirmEvidence = vi.mocked(useConfirmEvidence);
const mockedUseRejectEvidence = vi.mocked(useRejectEvidence);
const mockedUseCompleteEvidence = vi.mocked(useCompleteEvidence);
const mockedUseJob = vi.mocked(useJob);

// --- 测试辅助 ---

/** 构造测试用 Project。 */
function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "proj_001",
    name: "胃病数据分析",
    topic: "胃病数据",
    status: "SOURCES_COLLECTED",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T10:00:00Z",
    ...overrides,
  };
}

/** 构造测试用 Source（已解析状态）。 */
function makeParsedSource(overrides: Partial<Source> = {}): Source {
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

/** 构造测试用 EvidenceCard。 */
function makeCard(overrides: Partial<EvidenceCard> = {}): EvidenceCard {
  return {
    id: "ev_001",
    project_id: "proj_001",
    source_id: "src_001",
    parsed_document_id: "pd_001",
    summary: "这是证据卡片摘要内容",
    evidence_type: "METHOD",
    locator: "第 3 段",
    source_quote: "原文引用内容",
    status: "CANDIDATE",
    candidate_source: "LOCAL_RULE",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T10:00:00Z",
    confirmed_at: null,
    ...overrides,
  };
}

/** 设置所有 hooks 的默认 mock 值。 */
function setupMocks(options: {
  project?: Project | null | undefined;
  sources?: Source[];
  cards?: EvidenceCard[];
  projectLoading?: boolean;
  cardsLoading?: boolean;
}) {
  const {
    project = makeProject(),
    sources = [],
    cards = [],
    projectLoading = false,
    cardsLoading = false,
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

  mockedUseEvidenceCards.mockReturnValue({
    data: cards,
    isLoading: cardsLoading,
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

  mockedUseGenerateEvidence.mockReturnValue(makeMutationMock() as any);
  mockedUseUpdateEvidence.mockReturnValue(makeMutationMock() as any);
  mockedUseConfirmEvidence.mockReturnValue(makeMutationMock() as any);
  mockedUseRejectEvidence.mockReturnValue(makeMutationMock() as any);
  mockedUseCompleteEvidence.mockReturnValue(makeMutationMock() as any);
}

/** 用路由上下文渲染组件。 */
function renderWithRoute(projectId: string = "proj_001") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/projects/${projectId}/evidence`]}>
        <Routes>
          <Route path="/projects/:projectId/evidence" element={<EvidenceWorkspaceView />} />
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

describe("EvidenceWorkspaceView - 加载和错误状态", () => {
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
// 生成证据卡片区域
// ============================================================

describe("EvidenceWorkspaceView - 生成证据卡片区域", () => {
  it("无已解析来源时显示提示", () => {
    setupMocks({ sources: [] });

    renderWithRoute();

    expect(screen.getByText(/当前没有已解析的来源/)).toBeInTheDocument();
  });

  it("有已解析来源时显示生成候选按钮", () => {
    setupMocks({ sources: [makeParsedSource()] });

    renderWithRoute();

    expect(screen.getByText("生成候选")).toBeInTheDocument();
  });

  it("显示可生成来源的标题", () => {
    setupMocks({
      sources: [makeParsedSource({ title: "胃病研究文献" })],
    });

    renderWithRoute();

    expect(screen.getByText("胃病研究文献")).toBeInTheDocument();
  });
});

// ============================================================
// 证据卡片列表
// ============================================================

describe("EvidenceWorkspaceView - 证据卡片列表", () => {
  it("无卡片时显示空提示", () => {
    setupMocks({ cards: [] });

    renderWithRoute();

    expect(screen.getByText("没有匹配的证据卡片。")).toBeInTheDocument();
  });

  it("显示证据类型标签", () => {
    setupMocks({
      sources: [makeParsedSource()],
      cards: [makeCard({ evidence_type: "METHOD" })],
    });

    renderWithRoute();

    expect(screen.getByText(/方法/)).toBeInTheDocument();
  });

  it("显示卡片摘要", () => {
    setupMocks({
      sources: [makeParsedSource()],
      cards: [makeCard({ summary: "自定义摘要内容" })],
    });

    renderWithRoute();

    expect(screen.getByText("自定义摘要内容")).toBeInTheDocument();
  });

  it("CANDIDATE 状态显示候选标签", () => {
    setupMocks({
      sources: [makeParsedSource()],
      cards: [makeCard({ status: "CANDIDATE" })],
    });

    renderWithRoute();

    expect(screen.getByText(/\[候选\]/)).toBeInTheDocument();
  });

  it("CONFIRMED 状态显示已确认标签", () => {
    setupMocks({
      sources: [makeParsedSource()],
      cards: [makeCard({ status: "CONFIRMED" })],
    });

    renderWithRoute();

    expect(screen.getByText(/\[已确认\]/)).toBeInTheDocument();
  });

  it("显示候选来源标签（本地规则）", () => {
    setupMocks({
      sources: [makeParsedSource()],
      cards: [makeCard({ candidate_source: "LOCAL_RULE" })],
    });

    renderWithRoute();

    expect(screen.getAllByText(/本地规则/).length).toBeGreaterThanOrEqual(1);
  });

  it("显示候选来源标签（模型）", () => {
    setupMocks({
      sources: [makeParsedSource()],
      cards: [makeCard({ candidate_source: "MODEL" })],
    });

    renderWithRoute();

    expect(screen.getByText(/模型/)).toBeInTheDocument();
  });
});

// ============================================================
// 卡片操作按钮门控
// ============================================================

describe("EvidenceWorkspaceView - 卡片操作按钮门控", () => {
  it("CANDIDATE 状态显示编辑/确认/拒绝按钮", () => {
    setupMocks({
      sources: [makeParsedSource()],
      cards: [makeCard({ status: "CANDIDATE" })],
    });

    renderWithRoute();

    expect(screen.getByText("编辑卡片")).toBeInTheDocument();
    expect(screen.getByText("确认")).toBeInTheDocument();
    expect(screen.getByText("拒绝")).toBeInTheDocument();
  });

  it("CONFIRMED 状态不显示操作按钮", () => {
    setupMocks({
      sources: [makeParsedSource()],
      cards: [makeCard({ status: "CONFIRMED" })],
    });

    renderWithRoute();

    expect(screen.queryByText("编辑卡片")).not.toBeInTheDocument();
    expect(screen.queryByText("确认")).not.toBeInTheDocument();
    expect(screen.queryByText("拒绝")).not.toBeInTheDocument();
  });

  it("REJECTED 状态不显示操作按钮", () => {
    setupMocks({
      sources: [makeParsedSource()],
      cards: [makeCard({ status: "REJECTED" })],
    });

    renderWithRoute();

    expect(screen.queryByText("编辑卡片")).not.toBeInTheDocument();
    expect(screen.queryByText("确认")).not.toBeInTheDocument();
  });
});

// ============================================================
// STALE 状态
// ============================================================

describe("EvidenceWorkspaceView - STALE 状态", () => {
  it("STALE 状态显示失效提示", () => {
    setupMocks({
      sources: [makeParsedSource()],
      cards: [makeCard({ status: "STALE" })],
    });

    renderWithRoute();

    expect(screen.getByText(/此卡片已失效/)).toBeInTheDocument();
  });

  it("STALE 状态显示编辑按钮", () => {
    setupMocks({
      sources: [makeParsedSource()],
      cards: [makeCard({ status: "STALE" })],
    });

    renderWithRoute();

    expect(screen.getByText("编辑卡片")).toBeInTheDocument();
  });

  it("STALE 状态不显示确认按钮", () => {
    setupMocks({
      sources: [makeParsedSource()],
      cards: [makeCard({ status: "STALE" })],
    });

    renderWithRoute();

    expect(screen.queryByText("确认")).not.toBeInTheDocument();
  });
});

// ============================================================
// 状态筛选
// ============================================================

describe("EvidenceWorkspaceView - 状态筛选", () => {
  it("显示状态筛选下拉框", () => {
    setupMocks({});

    renderWithRoute();

    expect(screen.getByText("证据卡片")).toBeInTheDocument();
    expect(screen.getByText("全部状态")).toBeInTheDocument();
  });
});

// ============================================================
// 完成证据确认
// ============================================================

describe("EvidenceWorkspaceView - 完成证据确认", () => {
  it("显示完成证据确认按钮", () => {
    setupMocks({});

    renderWithRoute();

    expect(screen.getByText("完成证据确认")).toBeInTheDocument();
    expect(screen.getByText(/需要至少一张已确认（CONFIRMED）的证据卡片/)).toBeInTheDocument();
  });

  it("完成中按钮显示推进中", () => {
    setupMocks({});
    mockedUseCompleteEvidence.mockReturnValue({
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

describe("EvidenceWorkspaceView - 项目状态标签", () => {
  it("显示项目状态中文标签", () => {
    setupMocks({ project: makeProject({ status: "EVIDENCE_CONFIRMED" }) });

    renderWithRoute();

    expect(screen.getByText("[证据已确认]")).toBeInTheDocument();
  });
});
