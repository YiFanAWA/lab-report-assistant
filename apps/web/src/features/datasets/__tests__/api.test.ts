/**
 * datasets api 单元测试。
 *
 * 覆盖 8 个 API 函数：
 * - uploadDataset: 上传 CSV/Excel 文件数据集
 * - createUrlDataset: 登记公开 CSV/Excel URL 数据集
 * - listDatasets: 获取数据集列表
 * - getDataset: 获取数据集详情
 * - listDatasetVersions: 获取数据集版本列表
 * - deleteDataset: 软删除数据集
 * - reuploadDataset: 重新上传数据集（创建新版本）
 * - completeDatasets: 完成数据集收集
 *
 * 使用 vitest mock (globalThis as any).fetch。
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  uploadDataset,
  createUrlDataset,
  listDatasets,
  getDataset,
  listDatasetVersions,
  deleteDataset,
  reuploadDataset,
  completeDatasets,
} from "../api";
import type {
  Dataset,
  DatasetListResponse,
  DatasetVersion,
  DatasetVersionListResponse,
  CompleteDatasetsResponse,
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

/** 构造测试用 Dataset。 */
function makeDataset(overrides: Partial<Dataset> = {}): Dataset {
  return {
    id: "ds_001",
    project_id: PROJECT_ID,
    dataset_kind: "FILE",
    title: "胃病数据集",
    description: "示例数据集",
    status: "READY",
    error_code: null,
    error_message: null,
    created_at: "2026-07-23T10:00:00Z",
    updated_at: "2026-07-23T10:01:00Z",
    job_id: "job_001",
    ...overrides,
  };
}

/** 构造测试用 DatasetVersion。 */
function makeVersion(overrides: Partial<DatasetVersion> = {}): DatasetVersion {
  return {
    id: "ver_001",
    dataset_id: "ds_001",
    project_id: PROJECT_ID,
    version: 1,
    status: "PARSED",
    file_path: "/data/ds.csv",
    file_size_bytes: 1024,
    row_count: 100,
    column_count: 5,
    profile_json: null,
    error_code: null,
    error_message: null,
    created_at: "2026-07-23T10:00:00Z",
    parsed_at: "2026-07-23T10:00:30Z",
    ...overrides,
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

// ============================================================
// uploadDataset
// ============================================================

describe("uploadDataset", () => {
  it("成功上传文件数据集（含描述）", async () => {
    const dataset = makeDataset();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(dataset));

    const file = new File(["col1,col2\n1,2"], "data.csv", { type: "text/csv" });
    const result = await uploadDataset(PROJECT_ID, file, "标题", "描述");

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/datasets/upload`);
    expect(opts.method).toBe("POST");
    expect(opts.body).toBeInstanceOf(FormData);
    const formData = opts.body as FormData;
    expect(formData.get("title")).toBe("标题");
    expect(formData.get("description")).toBe("描述");
    expect(formData.get("file")).toBeInstanceOf(File);
    expect(result.id).toBe("ds_001");
    expect(result.job_id).toBe("job_001");
  });

  it("未传 description 时不附加该字段", async () => {
    const dataset = makeDataset();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(dataset));

    const file = new File(["x"], "data.csv");
    await uploadDataset(PROJECT_ID, file, "标题");

    const opts = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][1];
    const formData = opts.body as FormData;
    expect(formData.get("title")).toBe("标题");
    expect(formData.has("description")).toBe(false);
  });

  it("项目 ID 被 URL 编码", async () => {
    const dataset = makeDataset();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(dataset));

    const file = new File(["x"], "data.csv");
    await uploadDataset("proj with space", file, "标题");

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("proj%20with%20space");
  });

  it("上传失败时抛出错误", async () => {
    const errorBody = { error: { code: "FILE_TOO_LARGE", message: "文件过大" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(413, errorBody));

    const file = new File(["x"], "big.csv");
    await expect(
      uploadDataset(PROJECT_ID, file, "标题")
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// createUrlDataset
// ============================================================

describe("createUrlDataset", () => {
  it("成功登记 URL 数据集", async () => {
    const dataset = makeDataset({ dataset_kind: "URL" });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(dataset));

    const result = await createUrlDataset(
      PROJECT_ID,
      "https://example.com/data.csv",
      "URL 数据集",
      "描述"
    );

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/datasets/url`);
    expect(opts.method).toBe("POST");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    const body = JSON.parse(opts.body);
    expect(body.url).toBe("https://example.com/data.csv");
    expect(body.title).toBe("URL 数据集");
    expect(body.description).toBe("描述");
    expect(result.dataset_kind).toBe("URL");
  });

  it("未传 description 时 body 中 description 为 undefined", async () => {
    const dataset = makeDataset();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(dataset));

    await createUrlDataset(PROJECT_ID, "https://example.com/data.csv", "标题");

    const opts = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][1];
    const body = JSON.parse(opts.body);
    expect(body.description).toBeUndefined();
  });

  it("URL 无效时抛出校验错误", async () => {
    const errorBody = { error: { code: "VALIDATION_ERROR", message: "URL 格式无效" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(400, errorBody));

    await expect(
      createUrlDataset(PROJECT_ID, "not-a-url", "标题")
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// listDatasets
// ============================================================

describe("listDatasets", () => {
  it("成功获取数据集列表", async () => {
    const datasets = [makeDataset(), makeDataset({ id: "ds_002" })];
    const responseBody: DatasetListResponse = { items: datasets };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listDatasets(PROJECT_ID);

    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/datasets`
    );
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe("ds_001");
  });

  it("空列表返回空数组", async () => {
    const responseBody: DatasetListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listDatasets(PROJECT_ID);

    expect(result).toEqual([]);
  });

  it("项目不存在时抛出错误", async () => {
    const errorBody = { error: { code: "PROJECT_NOT_FOUND", message: "项目不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(listDatasets("proj_nonexistent")).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// getDataset
// ============================================================

describe("getDataset", () => {
  it("成功获取数据集详情", async () => {
    const dataset = makeDataset();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(dataset));

    const result = await getDataset(PROJECT_ID, "ds_001");

    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/datasets/ds_001`
    );
    expect(result.id).toBe("ds_001");
  });

  it("数据集 ID 被 URL 编码", async () => {
    const dataset = makeDataset();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(dataset));

    await getDataset(PROJECT_ID, "ds with space");

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("ds%20with%20space");
  });

  it("数据集不存在时抛出错误", async () => {
    const errorBody = { error: { code: "DATASET_NOT_FOUND", message: "数据集不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(getDataset(PROJECT_ID, "ds_nonexistent")).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// listDatasetVersions
// ============================================================

describe("listDatasetVersions", () => {
  it("成功获取版本列表", async () => {
    const versions = [
      makeVersion({ version: 2 }),
      makeVersion({ id: "ver_002", version: 1, status: "SUPERSEDED" }),
    ];
    const responseBody: DatasetVersionListResponse = { items: versions };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listDatasetVersions(PROJECT_ID, "ds_001");

    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/datasets/ds_001/versions`
    );
    expect(result).toHaveLength(2);
    expect(result[0].version).toBe(2);
  });

  it("无版本时返回空数组", async () => {
    const responseBody: DatasetVersionListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listDatasetVersions(PROJECT_ID, "ds_001");

    expect(result).toEqual([]);
  });

  it("数据集不存在时抛出错误", async () => {
    const errorBody = { error: { code: "DATASET_NOT_FOUND", message: "数据集不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(
      listDatasetVersions(PROJECT_ID, "ds_nonexistent")
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// deleteDataset
// ============================================================

describe("deleteDataset", () => {
  it("成功软删除数据集", async () => {
    const deleted = makeDataset({ status: "DELETED" });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(deleted));

    const result = await deleteDataset(PROJECT_ID, "ds_001");

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/datasets/ds_001`);
    expect(opts.method).toBe("DELETE");
    expect(result.status).toBe("DELETED");
  });

  it("删除已删除数据集抛出状态冲突", async () => {
    const errorBody = { error: { code: "INVALID_STATUS", message: "数据集已删除" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    await expect(deleteDataset(PROJECT_ID, "ds_001")).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// reuploadDataset
// ============================================================

describe("reuploadDataset", () => {
  it("成功重新上传数据集创建新版本", async () => {
    const dataset = makeDataset({ job_id: "job_002" });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(dataset));

    const file = new File(["col1,col2\n3,4"], "data_v2.csv", { type: "text/csv" });
    const result = await reuploadDataset(PROJECT_ID, "ds_001", file);

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/datasets/ds_001/reupload`);
    expect(opts.method).toBe("POST");
    expect(opts.body).toBeInstanceOf(FormData);
    const formData = opts.body as FormData;
    expect(formData.get("file")).toBeInstanceOf(File);
    expect(result.job_id).toBe("job_002");
  });

  it("数据集不存在时抛出错误", async () => {
    const errorBody = { error: { code: "DATASET_NOT_FOUND", message: "数据集不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    const file = new File(["x"], "data.csv");
    await expect(
      reuploadDataset(PROJECT_ID, "ds_nonexistent", file)
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// completeDatasets
// ============================================================

describe("completeDatasets", () => {
  it("成功完成数据集收集", async () => {
    const responseBody: CompleteDatasetsResponse = { status: "DATASET_READY" };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await completeDatasets(PROJECT_ID);

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/datasets/complete`);
    expect(opts.method).toBe("POST");
    expect(result.status).toBe("DATASET_READY");
  });

  it("无就绪数据集时抛出错误", async () => {
    const errorBody = { error: { code: "NO_READY_DATASET", message: "无就绪数据集" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(400, errorBody));

    await expect(completeDatasets(PROJECT_ID)).rejects.toEqual(errorBody.error);
  });
});
