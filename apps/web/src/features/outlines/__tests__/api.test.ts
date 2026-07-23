/**
 * outlines api 单元测试。
 *
 * 覆盖 12 个 API 函数：
 * - generateOutline: 触发生成大纲候选
 * - listOutlines: 获取大纲列表（含 status 过滤）
 * - getOutline: 获取大纲详情
 * - updateOutline: 编辑大纲
 * - confirmOutline: 确认大纲
 * - rejectOutline: 拒绝大纲
 * - generateWord: 触发 Word 生成
 * - generatePpt: 触发 PPT 生成
 * - listDeliverables: 获取交付物列表（含 status 过滤）
 * - listDeliverableVersions: 获取交付物版本列表
 * - buildDeliverableDownloadUrl: 构造下载 URL（同步）
 * - completeProject: 完成项目
 *
 * 使用 vitest mock (globalThis as any).fetch。
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  generateOutline,
  listOutlines,
  getOutline,
  updateOutline,
  confirmOutline,
  rejectOutline,
  generateWord,
  generatePpt,
  listDeliverables,
  listDeliverableVersions,
  buildDeliverableDownloadUrl,
  completeProject,
} from "../api";
import type {
  Outline,
  OutlineListResponse,
  UpdateOutlineRequest,
  Deliverable,
  DeliverableListResponse,
  DeliverableVersion,
  DeliverableVersionListResponse,
  GenerateOutlineResponse,
  GenerateDeliverableResponse,
  CompleteProjectResponse,
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

/** 构造测试用 Outline。 */
function makeOutline(overrides: Partial<Outline> = {}): Outline {
  return {
    id: "outline_001",
    project_id: PROJECT_ID,
    sections: [
      {
        id: "sec_001",
        title: "引言",
        content: "引言内容",
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

/** 构造测试用 Deliverable。 */
function makeDeliverable(overrides: Partial<Deliverable> = {}): Deliverable {
  return {
    id: "del_001",
    project_id: PROJECT_ID,
    outline_id: "outline_001",
    deliverable_type: "WORD",
    status: "SUCCEEDED",
    created_at: "2026-07-23T10:00:00Z",
    updated_at: null,
    ...overrides,
  };
}

/** 构造测试用 DeliverableVersion。 */
function makeVersion(overrides: Partial<DeliverableVersion> = {}): DeliverableVersion {
  return {
    id: "ver_001",
    deliverable_id: "del_001",
    version: 1,
    status: "SUCCEEDED",
    file_path: "/deliverables/word.docx",
    file_size_bytes: 20480,
    error_code: null,
    error_message: null,
    started_at: "2026-07-23T10:00:00Z",
    finished_at: "2026-07-23T10:00:30Z",
    duration_seconds: 30.0,
    created_at: "2026-07-23T10:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

// ============================================================
// generateOutline
// ============================================================

describe("generateOutline", () => {
  it("成功触发生成大纲", async () => {
    const responseBody: GenerateOutlineResponse = { job_id: "job_001" };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await generateOutline(PROJECT_ID);

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/outline/generate`);
    expect(opts.method).toBe("POST");
    expect(result.job_id).toBe("job_001");
  });

  it("项目状态不允许生成时抛出错误", async () => {
    const errorBody = { error: { code: "INVALID_STATUS", message: "项目状态不允许生成大纲" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    await expect(generateOutline(PROJECT_ID)).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// listOutlines
// ============================================================

describe("listOutlines", () => {
  it("成功获取大纲列表（无筛选）", async () => {
    const outlines = [makeOutline(), makeOutline({ id: "outline_002" })];
    const responseBody: OutlineListResponse = { items: outlines };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listOutlines(PROJECT_ID);

    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/outline`
    );
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe("outline_001");
  });

  it("按 status 筛选", async () => {
    const responseBody: OutlineListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    await listOutlines(PROJECT_ID, "CONFIRMED");

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("status=CONFIRMED");
  });

  it("空列表返回空数组", async () => {
    const responseBody: OutlineListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listOutlines(PROJECT_ID);

    expect(result).toEqual([]);
  });

  it("项目不存在时抛出错误", async () => {
    const errorBody = { error: { code: "PROJECT_NOT_FOUND", message: "项目不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(listOutlines("proj_nonexistent")).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// getOutline
// ============================================================

describe("getOutline", () => {
  it("成功获取大纲详情", async () => {
    const outline = makeOutline();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(outline));

    const result = await getOutline(PROJECT_ID, "outline_001");

    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/outline/outline_001`
    );
    expect(result.id).toBe("outline_001");
    expect(result.sections).toHaveLength(1);
  });

  it("大纲 ID 被 URL 编码", async () => {
    const outline = makeOutline();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(outline));

    await getOutline(PROJECT_ID, "outline with space");

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("outline%20with%20space");
  });

  it("大纲不存在时抛出错误", async () => {
    const errorBody = { error: { code: "OUTLINE_NOT_FOUND", message: "大纲不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(
      getOutline(PROJECT_ID, "outline_nonexistent")
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// updateOutline
// ============================================================

describe("updateOutline", () => {
  it("成功更新大纲章节", async () => {
    const payload: UpdateOutlineRequest = {
      sections: [
        {
          id: "sec_001",
          title: "新标题",
          content: "新内容",
          source_type: "EVIDENCE",
          source_ids: ["ev_001"],
        },
      ],
    };
    const updated = makeOutline({ ...payload, status: "CANDIDATE" });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(updated));

    const result = await updateOutline(PROJECT_ID, "outline_001", payload);

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/outline/outline_001`);
    expect(opts.method).toBe("PUT");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    const body = JSON.parse(opts.body);
    expect(body.sections).toHaveLength(1);
    expect(body.sections[0].title).toBe("新标题");
    expect(result.sections[0].title).toBe("新标题");
  });

  it("CONFIRMED 状态编辑后回到 CANDIDATE", async () => {
    const payload: UpdateOutlineRequest = { sections: [] };
    const updated = makeOutline({ status: "CANDIDATE", sections: [] });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(updated));

    const result = await updateOutline(PROJECT_ID, "outline_001", payload);

    expect(result.status).toBe("CANDIDATE");
  });

  it("REJECTED 状态编辑时抛出错误", async () => {
    const errorBody = { error: { code: "INVALID_STATUS", message: "已拒绝大纲不可编辑" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    await expect(
      updateOutline(PROJECT_ID, "outline_001", { sections: [] })
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// confirmOutline
// ============================================================

describe("confirmOutline", () => {
  it("成功确认大纲", async () => {
    const confirmed = makeOutline({
      status: "CONFIRMED",
      confirmed_at: "2026-07-23T11:00:00Z",
    });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(confirmed));

    const result = await confirmOutline(PROJECT_ID, "outline_001");

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/outline/outline_001/confirm`);
    expect(opts.method).toBe("POST");
    expect(result.status).toBe("CONFIRMED");
    expect(result.confirmed_at).not.toBeNull();
  });

  it("非 CANDIDATE 状态确认时抛出错误", async () => {
    const errorBody = { error: { code: "INVALID_STATUS", message: "只能确认候选大纲" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    await expect(
      confirmOutline(PROJECT_ID, "outline_001")
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// rejectOutline
// ============================================================

describe("rejectOutline", () => {
  it("成功拒绝大纲", async () => {
    const rejected = makeOutline({ status: "REJECTED" });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(rejected));

    const result = await rejectOutline(PROJECT_ID, "outline_001");

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/outline/outline_001/reject`);
    expect(opts.method).toBe("POST");
    expect(result.status).toBe("REJECTED");
  });

  it("非 CANDIDATE 状态拒绝时抛出错误", async () => {
    const errorBody = { error: { code: "INVALID_STATUS", message: "只能拒绝候选大纲" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    await expect(
      rejectOutline(PROJECT_ID, "outline_001")
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// generateWord
// ============================================================

describe("generateWord", () => {
  it("成功触发 Word 生成", async () => {
    const responseBody: GenerateDeliverableResponse = {
      job_id: "job_word",
      deliverable_id: "del_001",
    };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await generateWord(PROJECT_ID, "outline_001");

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(
      `${BASE}/projects/${PROJECT_ID}/outline/outline_001/word/generate`
    );
    expect(opts.method).toBe("POST");
    expect(result.job_id).toBe("job_word");
    expect(result.deliverable_id).toBe("del_001");
  });

  it("大纲未确认时抛出错误", async () => {
    const errorBody = { error: { code: "OUTLINE_NOT_CONFIRMED", message: "大纲未确认" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    await expect(
      generateWord(PROJECT_ID, "outline_001")
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// generatePpt
// ============================================================

describe("generatePpt", () => {
  it("成功触发 PPT 生成", async () => {
    const responseBody: GenerateDeliverableResponse = {
      job_id: "job_ppt",
      deliverable_id: "del_002",
    };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await generatePpt(PROJECT_ID, "outline_001");

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(
      `${BASE}/projects/${PROJECT_ID}/outline/outline_001/ppt/generate`
    );
    expect(opts.method).toBe("POST");
    expect(result.job_id).toBe("job_ppt");
    expect(result.deliverable_id).toBe("del_002");
  });

  it("大纲未确认时抛出错误", async () => {
    const errorBody = { error: { code: "OUTLINE_NOT_CONFIRMED", message: "大纲未确认" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    await expect(
      generatePpt(PROJECT_ID, "outline_001")
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// listDeliverables
// ============================================================

describe("listDeliverables", () => {
  it("成功获取交付物列表（无筛选）", async () => {
    const deliverables = [
      makeDeliverable(),
      makeDeliverable({ id: "del_002", deliverable_type: "PPT" }),
    ];
    const responseBody: DeliverableListResponse = { items: deliverables };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listDeliverables(PROJECT_ID);

    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/deliverables`
    );
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe("del_001");
  });

  it("按 status 筛选", async () => {
    const responseBody: DeliverableListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    await listDeliverables(PROJECT_ID, "SUCCEEDED");

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("status=SUCCEEDED");
  });

  it("空列表返回空数组", async () => {
    const responseBody: DeliverableListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listDeliverables(PROJECT_ID);

    expect(result).toEqual([]);
  });

  it("项目不存在时抛出错误", async () => {
    const errorBody = { error: { code: "PROJECT_NOT_FOUND", message: "项目不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(listDeliverables("proj_nonexistent")).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// listDeliverableVersions
// ============================================================

describe("listDeliverableVersions", () => {
  it("成功获取交付物版本列表", async () => {
    const versions = [
      makeVersion({ version: 2 }),
      makeVersion({ id: "ver_002", version: 1 }),
    ];
    const responseBody: DeliverableVersionListResponse = { items: versions };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listDeliverableVersions(PROJECT_ID, "del_001");

    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/deliverables/del_001/versions`
    );
    expect(result).toHaveLength(2);
    expect(result[0].version).toBe(2);
  });

  it("无版本时返回空数组", async () => {
    const responseBody: DeliverableVersionListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listDeliverableVersions(PROJECT_ID, "del_001");

    expect(result).toEqual([]);
  });

  it("交付物 ID 被 URL 编码", async () => {
    const responseBody: DeliverableVersionListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    await listDeliverableVersions(PROJECT_ID, "del with space");

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("del%20with%20space");
  });

  it("交付物不存在时抛出错误", async () => {
    const errorBody = { error: { code: "DELIVERABLE_NOT_FOUND", message: "交付物不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(
      listDeliverableVersions(PROJECT_ID, "del_nonexistent")
    ).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// buildDeliverableDownloadUrl
// ============================================================

describe("buildDeliverableDownloadUrl", () => {
  it("构造下载 URL", () => {
    const url = buildDeliverableDownloadUrl(PROJECT_ID, "del_001", "ver_001");
    expect(url).toBe(
      `${BASE}/projects/${PROJECT_ID}/deliverables/del_001/versions/ver_001/download`
    );
  });

  it("ID 中特殊字符被 URL 编码", () => {
    const url = buildDeliverableDownloadUrl(
      "proj with space",
      "del with space",
      "ver with space"
    );
    expect(url).toContain("proj%20with%20space");
    expect(url).toContain("del%20with%20space");
    expect(url).toContain("ver%20with%20space");
  });

  it("不发起网络请求", () => {
    const fetchSpy = vi.fn();
    (globalThis as any).fetch = fetchSpy;

    buildDeliverableDownloadUrl(PROJECT_ID, "del_001", "ver_001");

    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

// ============================================================
// completeProject
// ============================================================

describe("completeProject", () => {
  it("成功完成项目", async () => {
    const responseBody: CompleteProjectResponse = { status: "COMPLETED" };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await completeProject(PROJECT_ID);

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/complete`);
    expect(opts.method).toBe("POST");
    expect(result.status).toBe("COMPLETED");
  });

  it("交付物不齐全时抛出错误", async () => {
    const errorBody = { error: { code: "DELIVERABLES_INCOMPLETE", message: "交付物不齐全" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    await expect(completeProject(PROJECT_ID)).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// SPEC 0010 Word 模板 API
// ============================================================

import {
  uploadWordTemplate,
  getWordTemplate,
  deleteWordTemplate,
  buildWordTemplateDownloadUrl,
} from "../api";
import type { WordTemplate } from "../types";

describe("SPEC 0010 Word 模板 API", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  // --- uploadWordTemplate ---

  describe("uploadWordTemplate", () => {
    it("成功上传模板返回模板信息", async () => {
      const responseBody: WordTemplate = {
        id: "wt_001",
        project_id: PROJECT_ID,
        original_filename: "template.docx",
        file_size_bytes: 12345,
        content_hash: "abc123",
        created_at: "2026-07-23T00:00:00Z",
        updated_at: null,
      };
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

      const file = new File(["content"], "template.docx", {
        type: "application/octet-stream",
      });
      const result = await uploadWordTemplate(PROJECT_ID, file);

      expect(result.id).toBe("wt_001");
      expect(result.original_filename).toBe("template.docx");

      const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/word-template`);
      expect(opts.method).toBe("POST");
      expect(opts.body).toBeInstanceOf(FormData);
    });

    it("非 .docx 文件返回错误", async () => {
      const errorBody = {
        error: { code: "WORD_TEMPLATE_FILE_UNSUPPORTED", message: "仅支持 .docx 文件" },
      };
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(400, errorBody));

      const file = new File(["content"], "template.txt", { type: "text/plain" });
      await expect(uploadWordTemplate(PROJECT_ID, file)).rejects.toEqual(errorBody.error);
    });

    it("文件过大返回错误", async () => {
      const errorBody = {
        error: { code: "WORD_TEMPLATE_TOO_LARGE", message: "模板文件过大" },
      };
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(413, errorBody));

      const file = new File([new Array(6000000).join("x")], "big.docx");
      await expect(uploadWordTemplate(PROJECT_ID, file)).rejects.toEqual(errorBody.error);
    });
  });

  // --- getWordTemplate ---

  describe("getWordTemplate", () => {
    it("有模板时返回模板信息", async () => {
      const responseBody: WordTemplate = {
        id: "wt_001",
        project_id: PROJECT_ID,
        original_filename: "template.docx",
        file_size_bytes: 12345,
        content_hash: "abc123",
        created_at: "2026-07-23T00:00:00Z",
        updated_at: null,
      };
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

      const result = await getWordTemplate(PROJECT_ID);

      expect(result).not.toBeNull();
      expect(result!.id).toBe("wt_001");
      const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/word-template`);
    });

    it("无模板时返回 null", async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(null));

      const result = await getWordTemplate(PROJECT_ID);

      expect(result).toBeNull();
    });
  });

  // --- deleteWordTemplate ---

  describe("deleteWordTemplate", () => {
    it("成功删除模板", async () => {
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 204,
      } as Response);

      await deleteWordTemplate(PROJECT_ID);

      const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/word-template`);
      expect(opts.method).toBe("DELETE");
    });

    it("模板不存在时抛出错误", async () => {
      const errorBody = {
        error: { code: "WORD_TEMPLATE_NOT_FOUND", message: "项目未上传 Word 模板" },
      };
      (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

      await expect(deleteWordTemplate(PROJECT_ID)).rejects.toEqual(errorBody.error);
    });
  });

  // --- buildWordTemplateDownloadUrl ---

  describe("buildWordTemplateDownloadUrl", () => {
    it("返回正确的下载 URL", () => {
      const url = buildWordTemplateDownloadUrl(PROJECT_ID);
      expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/word-template/download`);
    });
  });
});
