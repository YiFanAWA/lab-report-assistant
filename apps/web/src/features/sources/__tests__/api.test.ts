/**
 * sources api 单元测试。
 *
 * 覆盖 6 个 API 函数：
 * - createUrlSource: 登记公开 URL 来源
 * - createPdfSource: 上传 PDF 文件来源
 * - listSources: 获取来源列表
 * - getSource: 获取来源详情
 * - deleteSource: 删除来源
 * - completeSources: 完成来源收集
 *
 * 使用 vitest mock global.fetch。
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  createUrlSource,
  createPdfSource,
  listSources,
  getSource,
  deleteSource,
  completeSources,
} from "../api";
import type {
  Source,
  SourceListResponse,
  CompleteSourcesResponse,
} from "../types";

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

/** 构造测试用 Source。 */
function makeSource(overrides: Partial<Source> = {}): Source {
  return {
    id: "src_001",
    project_id: PROJECT_ID,
    source_kind: "URL",
    title: "公开资料",
    url: "https://example.com/article",
    file_path: null,
    content_type: "text/html",
    content_hash: "abc123",
    status: "FETCHED",
    error_code: null,
    error_message: null,
    created_at: "2026-07-23T10:00:00Z",
    fetched_at: "2026-07-23T10:00:05Z",
    parsed_at: "2026-07-23T10:00:10Z",
    job_id: "job_001",
    ...overrides,
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

// ============================================================
// createUrlSource
// ============================================================

describe("createUrlSource", () => {
  it("成功登记 URL 来源", async () => {
    const source = makeSource();
    global.fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(source));

    const result = await createUrlSource(PROJECT_ID, "https://example.com/article", "公开资料");

    const [url, opts] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/sources/url`);
    expect(opts.method).toBe("POST");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    const body = JSON.parse(opts.body);
    expect(body.url).toBe("https://example.com/article");
    expect(body.title).toBe("公开资料");
    expect(result.id).toBe("src_001");
    expect(result.job_id).toBe("job_001");
  });

  it("项目 ID 被 URL 编码", async () => {
    const source = makeSource();
    global.fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(source));

    await createUrlSource("proj with space", "https://example.com", "title");

    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("proj%20with%20space");
  });

  it("URL 格式无效时抛出校验错误", async () => {
    const errorBody = { error: { code: "VALIDATION_ERROR", message: "URL 格式无效" } };
    global.fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(400, errorBody));

    await expect(
      createUrlSource(PROJECT_ID, "not-a-url", "标题")
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// createPdfSource
// ============================================================

describe("createPdfSource", () => {
  it("成功上传 PDF 文件来源", async () => {
    const source = makeSource({
      source_kind: "FILE",
      url: null,
      file_path: "/path/to/file.pdf",
      content_type: "application/pdf",
    });
    global.fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(source));

    const file = new File(["pdf content"], "doc.pdf", { type: "application/pdf" });
    const result = await createPdfSource(PROJECT_ID, file, "PDF 文档");

    const [url, opts] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/sources/pdf`);
    expect(opts.method).toBe("POST");
    expect(opts.body).toBeInstanceOf(FormData);
    expect(result.source_kind).toBe("FILE");
    expect(result.job_id).toBe("job_001");
  });

  it("FormData 包含 file 和 title", async () => {
    const source = makeSource();
    global.fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(source));

    const file = new File(["content"], "test.pdf", { type: "application/pdf" });
    await createPdfSource(PROJECT_ID, file, "标题");

    const opts = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1];
    const formData = opts.body as FormData;
    expect(formData.get("title")).toBe("标题");
    expect(formData.get("file")).toBeInstanceOf(File);
  });

  it("文件上传失败时抛出错误", async () => {
    const errorBody = { error: { code: "FILE_TOO_LARGE", message: "文件过大" } };
    global.fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(413, errorBody));

    const file = new File(["x"], "big.pdf");
    await expect(
      createPdfSource(PROJECT_ID, file, "大文件")
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// listSources
// ============================================================

describe("listSources", () => {
  it("成功获取来源列表", async () => {
    const sources = [makeSource(), makeSource({ id: "src_002" })];
    const responseBody: SourceListResponse = { items: sources };
    global.fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listSources(PROJECT_ID);

    expect(global.fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/sources`
    );
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe("src_001");
  });

  it("空列表返回空数组", async () => {
    const responseBody: SourceListResponse = { items: [] };
    global.fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listSources(PROJECT_ID);

    expect(result).toEqual([]);
  });

  it("项目不存在时抛出错误", async () => {
    const errorBody = { error: { code: "PROJECT_NOT_FOUND", message: "项目不存在" } };
    global.fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(listSources("proj_nonexistent")).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// getSource
// ============================================================

describe("getSource", () => {
  it("成功获取来源详情", async () => {
    const source = makeSource();
    global.fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(source));

    const result = await getSource(PROJECT_ID, "src_001");

    expect(global.fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/sources/src_001`
    );
    expect(result.id).toBe("src_001");
  });

  it("来源 ID 被 URL 编码", async () => {
    const source = makeSource();
    global.fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(source));

    await getSource(PROJECT_ID, "src with space");

    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("src%20with%20space");
  });

  it("来源不存在时抛出错误", async () => {
    const errorBody = { error: { code: "SOURCE_NOT_FOUND", message: "来源不存在" } };
    global.fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(getSource(PROJECT_ID, "src_nonexistent")).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// deleteSource
// ============================================================

describe("deleteSource", () => {
  it("成功删除来源", async () => {
    const deletedSource = makeSource({ status: "DELETED" });
    global.fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(deletedSource));

    const result = await deleteSource(PROJECT_ID, "src_001");

    const [url, opts] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/sources/src_001`);
    expect(opts.method).toBe("DELETE");
    expect(result.status).toBe("DELETED");
  });

  it("删除已删除来源时抛出状态冲突", async () => {
    const errorBody = { error: { code: "INVALID_STATUS", message: "来源已删除" } };
    global.fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    await expect(deleteSource(PROJECT_ID, "src_001")).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// completeSources
// ============================================================

describe("completeSources", () => {
  it("成功完成来源收集", async () => {
    const responseBody: CompleteSourcesResponse = {
      project_id: PROJECT_ID,
      status: "SOURCES_COLLECTED",
    };
    global.fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await completeSources(PROJECT_ID);

    const [url, opts] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/sources/complete`);
    expect(opts.method).toBe("POST");
    expect(result.status).toBe("SOURCES_COLLECTED");
  });

  it("无来源时完成收集抛出错误", async () => {
    const errorBody = { error: { code: "NO_SOURCES", message: "无来源可完成" } };
    global.fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(400, errorBody));

    await expect(completeSources(PROJECT_ID)).rejects.toEqual(errorBody.error);
  });
});
