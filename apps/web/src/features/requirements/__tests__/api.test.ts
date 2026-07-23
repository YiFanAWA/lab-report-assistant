/**
 * requirements api 单元测试。
 *
 * 覆盖 7 个 API 函数：
 * - addTextSource: 添加文本来源
 * - addDocxSource: 添加 .docx 文件来源
 * - fetchSources: 获取来源列表
 * - generatePlan: 生成任务单
 * - fetchCurrentPlan: 获取当前任务单
 * - confirmPlan: 确认任务单
 * - updatePlan: 更新任务单
 *
 * 每个函数测试：
 * - 成功场景：验证 URL、HTTP method、请求体、响应解析
 * - 错误场景：验证非 ok 响应时抛出结构化错误
 *
 * 使用 vitest mock (globalThis as any).fetch。
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  addTextSource,
  addDocxSource,
  fetchSources,
  generatePlan,
  fetchCurrentPlan,
  confirmPlan,
  updatePlan,
} from "../api";
import type {
  RequirementSource,
  SourceListResponse,
  RequirementPlanResponse,
  RequirementPlanPayload,
} from "../types";

const BASE = "/api";
const PROJECT_ID = "proj_abc123";

/** 构造 mock fetch 的成功响应。 */
function mockOkResponse(data: unknown): Response {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    json: () => Promise.resolve(data),
  } as Response;
}

/** 构造 mock fetch 的失败响应。 */
function mockErrorResponse(status: number, errorBody: unknown): Response {
  return {
    ok: false,
    status,
    statusText: "Bad Request",
    json: () => Promise.resolve(errorBody),
  } as Response;
}

/** 构造测试用 RequirementSource 对象。 */
function makeSource(overrides: Partial<RequirementSource> = {}): RequirementSource {
  return {
    id: "src_001",
    project_id: PROJECT_ID,
    source_type: "TEXT",
    title: "实验要求",
    original_text: "分析胃病数据",
    original_file_path: null,
    content_hash: "abc123",
    created_at: "2026-07-23T10:00:00Z",
    ...overrides,
  };
}

/** 构造测试用 RequirementPlanResponse 对象。 */
function makePlanResponse(overrides: Partial<RequirementPlanResponse> = {}): RequirementPlanResponse {
  return {
    id: "plan_001",
    project_id: PROJECT_ID,
    source_id: "src_001",
    status: "DRAFT",
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

beforeEach(() => {
  vi.restoreAllMocks();
});

// ============================================================
// Sources 相关 API
// ============================================================

describe("addTextSource", () => {
  it("成功添加文本来源", async () => {
    const source = makeSource();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(source));

    const result = await addTextSource(PROJECT_ID, "实验要求", "分析胃病数据");

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/requirements/sources/text`);
    expect(opts.method).toBe("POST");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    const body = JSON.parse(opts.body);
    expect(body.title).toBe("实验要求");
    expect(body.text).toBe("分析胃病数据");
    expect(result.id).toBe("src_001");
  });

  it("项目 ID 被 URL 编码", async () => {
    const source = makeSource();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(source));

    await addTextSource("proj with space", "title", "text");

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("proj%20with%20space");
  });

  it("文本为空时抛出校验错误", async () => {
    const errorBody = { error: { code: "VALIDATION_ERROR", message: "text 不能为空" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(400, errorBody));

    await expect(
      addTextSource(PROJECT_ID, "实验要求", "")
    ).rejects.toEqual(errorBody.error);
  });
});

describe("addDocxSource", () => {
  it("成功添加 .docx 文件来源", async () => {
    const source = makeSource({ source_type: "DOCX", original_file_path: "/path/to/file.docx" });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(source));

    const file = new File(["docx content"], "requirement.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    const result = await addDocxSource(PROJECT_ID, "实验要求文档", file);

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/requirements/sources/docx`);
    expect(opts.method).toBe("POST");
    // FormData 不设置 Content-Type，浏览器自动添加 boundary
    expect(opts.body).toBeInstanceOf(FormData);
    expect(result.source_type).toBe("DOCX");
  });

  it("FormData 包含 file 和 title", async () => {
    const source = makeSource();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(source));

    const file = new File(["content"], "test.docx", { type: "application/octet-stream" });
    await addDocxSource(PROJECT_ID, "标题", file);

    const opts = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][1];
    const formData = opts.body as FormData;
    expect(formData.get("title")).toBe("标题");
    expect(formData.get("file")).toBeInstanceOf(File);
  });

  it("文件上传失败时抛出错误", async () => {
    const errorBody = { error: { code: "FILE_TOO_LARGE", message: "文件过大" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(413, errorBody));

    const file = new File(["x"], "big.docx");
    await expect(
      addDocxSource(PROJECT_ID, "大文件", file)
    ).rejects.toEqual(errorBody.error);
  });
});

describe("fetchSources", () => {
  it("成功获取来源列表", async () => {
    const sources = [makeSource(), makeSource({ id: "src_002" })];
    const responseBody: SourceListResponse = { items: sources };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await fetchSources(PROJECT_ID);

    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/requirements/sources`
    );
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe("src_001");
  });

  it("空列表返回空数组", async () => {
    const responseBody: SourceListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await fetchSources(PROJECT_ID);

    expect(result).toEqual([]);
  });

  it("项目不存在时抛出错误", async () => {
    const errorBody = { error: { code: "PROJECT_NOT_FOUND", message: "项目不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(fetchSources("proj_nonexistent")).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// Plan 相关 API
// ============================================================

describe("generatePlan", () => {
  it("成功生成任务单", async () => {
    const plan = makePlanResponse();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(plan));

    const result = await generatePlan(PROJECT_ID, "src_001");

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/requirements/plans/generate`);
    expect(opts.method).toBe("POST");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    const body = JSON.parse(opts.body);
    expect(body.source_id).toBe("src_001");
    expect(result.id).toBe("plan_001");
  });

  it("来源 ID 不存在时抛出错误", async () => {
    const errorBody = { error: { code: "SOURCE_NOT_FOUND", message: "来源不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(generatePlan(PROJECT_ID, "src_nonexistent")).rejects.toEqual(errorBody.error);
  });
});

describe("fetchCurrentPlan", () => {
  it("成功获取当前任务单", async () => {
    const plan = makePlanResponse({ status: "CONFIRMED" });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(plan));

    const result = await fetchCurrentPlan(PROJECT_ID);

    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/requirements/plan`
    );
    expect(result.status).toBe("CONFIRMED");
  });

  it("任务单不存在时抛出错误", async () => {
    const errorBody = { error: { code: "PLAN_NOT_FOUND", message: "任务单不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(fetchCurrentPlan(PROJECT_ID)).rejects.toEqual(errorBody.error);
  });
});

describe("confirmPlan", () => {
  it("成功确认任务单", async () => {
    const confirmedPlan = makePlanResponse({ status: "CONFIRMED", confirmed_at: "2026-07-23T11:00:00Z" });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(confirmedPlan));

    const result = await confirmPlan(PROJECT_ID, "plan_001");

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/requirements/plans/plan_001/confirm`);
    expect(opts.method).toBe("POST");
    expect(result.status).toBe("CONFIRMED");
    expect(result.confirmed_at).not.toBeNull();
  });

  it("plan ID 被 URL 编码", async () => {
    const plan = makePlanResponse();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(plan));

    await confirmPlan(PROJECT_ID, "plan with space");

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("plan%20with%20space");
  });

  it("任务单已确认时抛出状态冲突错误", async () => {
    const errorBody = { error: { code: "INVALID_STATUS", message: "任务单已确认" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    await expect(confirmPlan(PROJECT_ID, "plan_001")).rejects.toEqual(errorBody.error);
  });
});

describe("updatePlan", () => {
  it("成功更新任务单", async () => {
    const updatedPlan = makePlanResponse({
      status: "DRAFT",
      payload: {
        ...makePlanResponse().payload,
        topic: "更新后的主题",
      },
    });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(updatedPlan));

    const payload: RequirementPlanPayload = makePlanResponse().payload;
    payload.topic = "更新后的主题";
    const result = await updatePlan(PROJECT_ID, "plan_001", payload);

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/requirements/plans/plan_001`);
    expect(opts.method).toBe("PUT");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    const body = JSON.parse(opts.body);
    expect(body.payload).toBeDefined();
    expect(body.payload.topic).toBe("更新后的主题");
    expect(result.payload.topic).toBe("更新后的主题");
  });

  it("更新已确认任务单时抛出错误", async () => {
    const errorBody = { error: { code: "INVALID_STATUS", message: "已确认任务单不可更新" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    const payload = makePlanResponse().payload;
    await expect(updatePlan(PROJECT_ID, "plan_001", payload)).rejects.toEqual(errorBody.error);
  });

  it("payload 被包裹在对象中发送", async () => {
    const plan = makePlanResponse();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(plan));

    const payload = makePlanResponse().payload;
    await updatePlan(PROJECT_ID, "plan_001", payload);

    const opts = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][1];
    const body = JSON.parse(opts.body);
    // 后端期望 { payload: {...} } 结构
    expect(body.payload).toBeDefined();
    expect(body.payload.topic).toBe("胃病数据分析");
    expect(body.payload.required_tasks).toEqual([]);
  });
});
