/**
 * jobs api 单元测试。
 *
 * 覆盖 2 个 API 函数：
 * - fetchJob: 获取任务详情
 * - listJobs: 获取任务列表（含 status / job_type 筛选）
 *
 * 使用 vitest mock (globalThis as any).fetch。
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchJob, listJobs } from "../api";
import type { BackgroundJob, JobListResponse } from "../types";

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

/** 构造测试用 BackgroundJob。 */
function makeJob(overrides: Partial<BackgroundJob> = {}): BackgroundJob {
  return {
    id: "job_001",
    project_id: PROJECT_ID,
    job_type: "FETCH_URL",
    status: "SUCCEEDED",
    input_json: '{"url":"https://example.com"}',
    output_json: '{"status":"ok"}',
    error_code: null,
    error_message: null,
    retry_count: 0,
    max_retries: 3,
    created_at: "2026-07-23T10:00:00Z",
    started_at: "2026-07-23T10:00:01Z",
    finished_at: "2026-07-23T10:00:05Z",
    next_retry_at: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

// ============================================================
// fetchJob
// ============================================================

describe("fetchJob", () => {
  it("成功获取任务详情", async () => {
    const job = makeJob();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(job));

    const result = await fetchJob(PROJECT_ID, "job_001");

    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/jobs/job_001`
    );
    expect(result.id).toBe("job_001");
    expect(result.job_type).toBe("FETCH_URL");
    expect(result.status).toBe("SUCCEEDED");
  });

  it("任务 ID 被 URL 编码", async () => {
    const job = makeJob();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(job));

    await fetchJob(PROJECT_ID, "job with space");

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("job%20with%20space");
  });

  it("任务不存在时抛出错误", async () => {
    const errorBody = { error: { code: "JOB_NOT_FOUND", message: "任务不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(fetchJob(PROJECT_ID, "job_nonexistent")).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// listJobs
// ============================================================

describe("listJobs", () => {
  it("成功获取任务列表（无筛选）", async () => {
    const jobs = [makeJob(), makeJob({ id: "job_002", job_type: "PARSE_DOCUMENT" })];
    const responseBody: JobListResponse = { items: jobs };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listJobs(PROJECT_ID);

    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/jobs`
    );
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe("job_001");
  });

  it("按 status 筛选", async () => {
    const responseBody: JobListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    await listJobs(PROJECT_ID, { status: "RUNNING" });

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("status=RUNNING");
  });

  it("按 job_type 筛选", async () => {
    const responseBody: JobListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    await listJobs(PROJECT_ID, { job_type: "FETCH_URL" });

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("job_type=FETCH_URL");
  });

  it("同时按 status 和 job_type 筛选", async () => {
    const responseBody: JobListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    await listJobs(PROJECT_ID, { status: "FAILED", job_type: "PARSE_DOCUMENT" });

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("status=FAILED");
    expect(url).toContain("job_type=PARSE_DOCUMENT");
  });

  it("空列表返回空数组", async () => {
    const responseBody: JobListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listJobs(PROJECT_ID);

    expect(result).toEqual([]);
  });

  it("项目不存在时抛出错误", async () => {
    const errorBody = { error: { code: "PROJECT_NOT_FOUND", message: "项目不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(listJobs("proj_nonexistent")).rejects.toEqual(errorBody.error);
  });
});
