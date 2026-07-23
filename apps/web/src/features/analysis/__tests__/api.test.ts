/**
 * analysis api 单元测试。
 *
 * 覆盖 7 个 API 函数：
 * - generateAnalysisPlan: 触发生成分析方案候选
 * - listAnalysisPlans: 获取分析方案列表（含筛选）
 * - getAnalysisPlan: 获取分析方案详情
 * - updateAnalysisPlan: 编辑分析方案
 * - confirmAnalysisPlan: 确认分析方案
 * - rejectAnalysisPlan: 拒绝分析方案
 * - completeAnalysis: 完成分析方案确认
 *
 * 使用 vitest mock (globalThis as any).fetch。
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  generateAnalysisPlan,
  listAnalysisPlans,
  getAnalysisPlan,
  updateAnalysisPlan,
  confirmAnalysisPlan,
  rejectAnalysisPlan,
  completeAnalysis,
} from "../api";
import type {
  AnalysisPlan,
  AnalysisPlanListResponse,
  UpdateAnalysisPlanRequest,
  CompleteAnalysisResponse,
} from "../types";
import type { GenerateAnalysisResponse } from "../../jobs/types";

const BASE = "/api";
const PROJECT_ID = "proj_001";

/** 构造 mock fetch 成功响应。 */
function mockOkResponse(data: unknown): Response {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    json: () => Promise.resolve(data),
  } as Response;
}

/** 构造 mock fetch 失败响应。 */
function mockErrorResponse(status: number, errorBody: unknown): Response {
  return {
    ok: false,
    status,
    statusText: "Bad Request",
    json: () => Promise.resolve(errorBody),
  } as Response;
}

/** 构造测试用 AnalysisPlan。 */
function makePlan(overrides: Partial<AnalysisPlan> = {}): AnalysisPlan {
  return {
    id: "plan_001",
    project_id: PROJECT_ID,
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

beforeEach(() => {
  vi.restoreAllMocks();
});

// ============================================================
// generateAnalysisPlan
// ============================================================

describe("generateAnalysisPlan", () => {
  it("成功触发生成分析方案", async () => {
    const responseBody: GenerateAnalysisResponse = { job_id: "job_001" };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await generateAnalysisPlan(PROJECT_ID, "ds_001");

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(
      `${BASE}/projects/${PROJECT_ID}/datasets/ds_001/analysis/generate`
    );
    expect(opts.method).toBe("POST");
    expect(result.job_id).toBe("job_001");
  });

  it("数据集未就绪时抛出错误", async () => {
    const errorBody = { error: { code: "DATASET_NOT_READY", message: "数据集未就绪" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(400, errorBody));

    await expect(
      generateAnalysisPlan(PROJECT_ID, "ds_001")
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// listAnalysisPlans
// ============================================================

describe("listAnalysisPlans", () => {
  it("成功获取分析方案列表（无筛选）", async () => {
    const plans = [makePlan(), makePlan({ id: "plan_002" })];
    const responseBody: AnalysisPlanListResponse = { items: plans };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listAnalysisPlans(PROJECT_ID);

    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/analysis`
    );
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe("plan_001");
  });

  it("按 dataset_id 筛选", async () => {
    const responseBody: AnalysisPlanListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    await listAnalysisPlans(PROJECT_ID, { dataset_id: "ds_001" });

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("dataset_id=ds_001");
  });

  it("按 status 筛选", async () => {
    const responseBody: AnalysisPlanListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    await listAnalysisPlans(PROJECT_ID, { status: "CONFIRMED" });

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("status=CONFIRMED");
  });

  it("空列表返回空数组", async () => {
    const responseBody: AnalysisPlanListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listAnalysisPlans(PROJECT_ID);

    expect(result).toEqual([]);
  });

  it("项目不存在时抛出错误", async () => {
    const errorBody = { error: { code: "PROJECT_NOT_FOUND", message: "项目不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(listAnalysisPlans("proj_nonexistent")).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// getAnalysisPlan
// ============================================================

describe("getAnalysisPlan", () => {
  it("成功获取分析方案详情", async () => {
    const plan = makePlan();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(plan));

    const result = await getAnalysisPlan(PROJECT_ID, "plan_001");

    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/analysis/plan_001`
    );
    expect(result.id).toBe("plan_001");
  });

  it("方案 ID 被 URL 编码", async () => {
    const plan = makePlan();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(plan));

    await getAnalysisPlan(PROJECT_ID, "plan with space");

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("plan%20with%20space");
  });

  it("方案不存在时抛出错误", async () => {
    const errorBody = { error: { code: "PLAN_NOT_FOUND", message: "方案不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(
      getAnalysisPlan(PROJECT_ID, "plan_nonexistent")
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// updateAnalysisPlan
// ============================================================

describe("updateAnalysisPlan", () => {
  it("成功更新分析方案", async () => {
    const payload: UpdateAnalysisPlanRequest = {
      cleaning_plan: '[{"field":"age"}]',
      analysis_plan: '[{"analysis_type":"ttest"}]',
      chart_plan: '[{"chart_type":"bar"}]',
    };
    const updated = makePlan({
      cleaning_plan: payload.cleaning_plan!,
      analysis_plan: payload.analysis_plan!,
      chart_plan: payload.chart_plan!,
      status: "CANDIDATE",
    });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(updated));

    const result = await updateAnalysisPlan(PROJECT_ID, "plan_001", payload);

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/analysis/plan_001`);
    expect(opts.method).toBe("PUT");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    const body = JSON.parse(opts.body);
    expect(body.cleaning_plan).toBe(payload.cleaning_plan);
    expect(body.analysis_plan).toBe(payload.analysis_plan);
    expect(body.chart_plan).toBe(payload.chart_plan);
    expect(result.cleaning_plan).toBe(payload.cleaning_plan);
  });

  it("CONFIRMED 状态编辑后返回 CANDIDATE", async () => {
    const payload: UpdateAnalysisPlanRequest = { cleaning_plan: "[]" };
    const updated = makePlan({ status: "CANDIDATE", cleaning_plan: "[]" });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(updated));

    const result = await updateAnalysisPlan(PROJECT_ID, "plan_001", payload);

    expect(result.status).toBe("CANDIDATE");
  });

  it("REJECTED 状态编辑时抛出错误", async () => {
    const errorBody = { error: { code: "INVALID_STATUS", message: "已拒绝方案不可编辑" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    await expect(
      updateAnalysisPlan(PROJECT_ID, "plan_001", { cleaning_plan: "[]" })
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// confirmAnalysisPlan
// ============================================================

describe("confirmAnalysisPlan", () => {
  it("成功确认分析方案", async () => {
    const confirmed = makePlan({ status: "CONFIRMED", confirmed_at: "2026-07-23T11:00:00Z" });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(confirmed));

    const result = await confirmAnalysisPlan(PROJECT_ID, "plan_001");

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/analysis/plan_001/confirm`);
    expect(opts.method).toBe("POST");
    expect(result.status).toBe("CONFIRMED");
    expect(result.confirmed_at).not.toBeNull();
  });

  it("非 CANDIDATE 状态确认时抛出错误", async () => {
    const errorBody = { error: { code: "INVALID_STATUS", message: "只能确认候选方案" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    await expect(
      confirmAnalysisPlan(PROJECT_ID, "plan_001")
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// rejectAnalysisPlan
// ============================================================

describe("rejectAnalysisPlan", () => {
  it("成功拒绝分析方案", async () => {
    const rejected = makePlan({ status: "REJECTED" });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(rejected));

    const result = await rejectAnalysisPlan(PROJECT_ID, "plan_001");

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/analysis/plan_001/reject`);
    expect(opts.method).toBe("POST");
    expect(result.status).toBe("REJECTED");
  });

  it("非 CANDIDATE 状态拒绝时抛出错误", async () => {
    const errorBody = { error: { code: "INVALID_STATUS", message: "只能拒绝候选方案" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    await expect(
      rejectAnalysisPlan(PROJECT_ID, "plan_001")
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// completeAnalysis
// ============================================================

describe("completeAnalysis", () => {
  it("成功完成分析方案确认", async () => {
    const responseBody: CompleteAnalysisResponse = { status: "ANALYSIS_CONFIRMED" };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await completeAnalysis(PROJECT_ID);

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/analysis/complete`);
    expect(opts.method).toBe("POST");
    expect(result.status).toBe("ANALYSIS_CONFIRMED");
  });

  it("无已确认方案时抛出错误", async () => {
    const errorBody = { error: { code: "NO_CONFIRMED_PLAN", message: "无已确认方案" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(400, errorBody));

    await expect(completeAnalysis(PROJECT_ID)).rejects.toEqual(errorBody.error);
  });
});
