/**
 * projects api 单元测试。
 *
 * 覆盖 3 个 API 函数：
 * - fetchProjects: 获取项目列表
 * - fetchProject: 获取单个项目
 * - createProject: 创建项目
 *
 * 每个函数测试：
 * - 成功场景：验证 URL、HTTP method、请求体、响应解析
 * - 错误场景：验证非 ok 响应时抛出结构化错误
 *
 * 使用 vitest mock (globalThis as any).fetch。
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchProjects, fetchProject, createProject } from "../api";
import type { Project, ProjectListResponse, ApiError } from "../../../shared/types";

const BASE = "/api";

/** 构造 mock fetch 的成功响应。 */
function mockOkResponse(data: unknown): Response {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    json: () => Promise.resolve(data),
  } as Response;
}

/** 构造 mock fetch 的失败响应（含结构化错误）。 */
function mockErrorResponse(
  status: number,
  errorBody: ApiError | { message: string }
): Response {
  return {
    ok: false,
    status,
    statusText: "Bad Request",
    json: () => Promise.resolve(errorBody),
  } as Response;
}

/** 构造测试用 Project 对象。 */
function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "proj_abc123",
    name: "胃病数据分析",
    topic: "胃病数据分析",
    status: "DRAFT",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T10:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("fetchProjects", () => {
  it("成功获取项目列表", async () => {
    const projects = [makeProject(), makeProject({ id: "proj_def456" })];
    const responseBody: ProjectListResponse = { items: projects };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await fetchProjects();

    expect((globalThis as any).fetch).toHaveBeenCalledWith(`${BASE}/projects`);
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe("proj_abc123");
    expect(result[1].id).toBe("proj_def456");
  });

  it("空列表返回空数组", async () => {
    const responseBody: ProjectListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await fetchProjects();

    expect(result).toEqual([]);
  });

  it("HTTP 500 错误时抛出结构化错误", async () => {
    const errorBody: ApiError = {
      error: { code: "INTERNAL_ERROR", message: "服务器内部错误", field: null },
    };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(500, errorBody));

    await expect(fetchProjects()).rejects.toEqual(errorBody.error);
  });

  it("响应非 JSON 时回退到默认错误", async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: () => Promise.reject(new Error("not JSON")),
    } as Response);

    await expect(fetchProjects()).rejects.toEqual({
      code: "UNKNOWN",
      message: "请求失败 (502)",
    });
  });
});

describe("fetchProject", () => {
  it("成功获取单个项目", async () => {
    const project = makeProject();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(project));

    const result = await fetchProject("proj_abc123");

    expect((globalThis as any).fetch).toHaveBeenCalledWith(`${BASE}/projects/proj_abc123`);
    expect(result.id).toBe("proj_abc123");
    expect(result.name).toBe("胃病数据分析");
  });

  it("项目 ID 被 URL 编码", async () => {
    const project = makeProject();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(project));

    await fetchProject("proj with spaces/特殊字符");

    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      `${BASE}/projects/proj%20with%20spaces%2F%E7%89%B9%E6%AE%8A%E5%AD%97%E7%AC%A6`
    );
  });

  it("项目不存在时抛出错误", async () => {
    const errorBody: ApiError = {
      error: { code: "PROJECT_NOT_FOUND", message: "项目不存在", field: null },
    };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(fetchProject("proj_nonexistent")).rejects.toEqual(errorBody.error);
  });
});

describe("createProject", () => {
  it("成功创建项目", async () => {
    const newProject = makeProject({ id: "proj_new123" });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(newProject));

    const result = await createProject({ name: "新项目", topic: "测试主题" });

    expect((globalThis as any).fetch).toHaveBeenCalledWith(`${BASE}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "新项目", topic: "测试主题" }),
    });
    expect(result.id).toBe("proj_new123");
    expect(result.name).toBe("胃病数据分析");
  });

  it("创建请求体包含 name 和 topic", async () => {
    const newProject = makeProject();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(newProject));

    await createProject({ name: "胃病分析", topic: "胃病" });

    const callArgs = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(callArgs[1].body);
    expect(body.name).toBe("胃病分析");
    expect(body.topic).toBe("胃病");
    expect(callArgs[1].headers["Content-Type"]).toBe("application/json");
    expect(callArgs[1].method).toBe("POST");
  });

  it("参数校验失败时抛出错误", async () => {
    const errorBody: ApiError = {
      error: { code: "VALIDATION_ERROR", message: "name 不能为空", field: "name" },
    };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(400, errorBody));

    await expect(
      createProject({ name: "", topic: "测试" })
    ).rejects.toEqual(errorBody.error);
  });
});
