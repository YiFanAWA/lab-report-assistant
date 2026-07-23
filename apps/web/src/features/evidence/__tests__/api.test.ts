/**
 * evidence api 单元测试。
 *
 * 覆盖 6 个 API 函数：
 * - generateEvidence: 生成证据卡片候选
 * - listEvidence: 获取证据卡片列表（含 source_id/status 筛选）
 * - updateEvidence: 更新证据卡片
 * - confirmEvidence: 确认证据卡片
 * - rejectEvidence: 拒绝证据卡片
 * - completeEvidence: 完成证据确认
 *
 * 使用 vitest mock (globalThis as any).fetch。
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  generateEvidence,
  listEvidence,
  updateEvidence,
  confirmEvidence,
  rejectEvidence,
  completeEvidence,
} from "../api";
import type {
  EvidenceCard,
  EvidenceCardListResponse,
  UpdateEvidenceCardRequest,
  CompleteEvidenceResponse,
} from "../types";

const BASE = "/api";
const PROJECT_ID = "proj_001";
const SOURCE_ID = "src_001";

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

/** 构造测试用 EvidenceCard。 */
function makeCard(overrides: Partial<EvidenceCard> = {}): EvidenceCard {
  return {
    id: "card_001",
    project_id: PROJECT_ID,
    source_id: SOURCE_ID,
    parsed_document_id: "doc_001",
    summary: "这是背景信息",
    evidence_type: "BACKGROUND",
    locator: "第 3 段",
    source_quote: "原文引用",
    status: "CANDIDATE",
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
// generateEvidence
// ============================================================

describe("generateEvidence", () => {
  it("成功生成证据卡片候选", async () => {
    const responseBody = { job_id: "job_001" };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await generateEvidence(PROJECT_ID, SOURCE_ID);

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(
      `${BASE}/projects/${PROJECT_ID}/sources/${SOURCE_ID}/evidence/generate`
    );
    expect(opts.method).toBe("POST");
    expect(result.job_id).toBe("job_001");
  });

  it("来源 ID 被 URL 编码", async () => {
    const responseBody = { job_id: "job_001" };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    await generateEvidence(PROJECT_ID, "src with space");

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("src%20with%20space");
  });

  it("来源不存在时抛出错误", async () => {
    const errorBody = { error: { code: "SOURCE_NOT_FOUND", message: "来源不存在" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(generateEvidence(PROJECT_ID, "src_nonexistent")).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// listEvidence
// ============================================================

describe("listEvidence", () => {
  it("成功获取证据卡片列表", async () => {
    const cards = [makeCard(), makeCard({ id: "card_002" })];
    const responseBody: EvidenceCardListResponse = { items: cards };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listEvidence(PROJECT_ID);

    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/evidence`
    );
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe("card_001");
  });

  it("空列表返回空数组", async () => {
    const responseBody: EvidenceCardListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await listEvidence(PROJECT_ID);

    expect(result).toEqual([]);
  });

  it("按 source_id 筛选", async () => {
    const responseBody: EvidenceCardListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    await listEvidence(PROJECT_ID, { source_id: "src_001" });

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("source_id=src_001");
  });

  it("按 status 筛选", async () => {
    const responseBody: EvidenceCardListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    await listEvidence(PROJECT_ID, { status: "CANDIDATE" });

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("status=CANDIDATE");
  });

  it("同时按 source_id 和 status 筛选", async () => {
    const responseBody: EvidenceCardListResponse = { items: [] };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    await listEvidence(PROJECT_ID, { source_id: "src_001", status: "CONFIRMED" });

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("source_id=src_001");
    expect(url).toContain("status=CONFIRMED");
  });
});

// ============================================================
// updateEvidence
// ============================================================

describe("updateEvidence", () => {
  it("成功更新证据卡片", async () => {
    const updatedCard = makeCard({ summary: "更新后的摘要" });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(updatedCard));

    const payload: UpdateEvidenceCardRequest = {
      summary: "更新后的摘要",
      evidence_type: "METHOD",
      locator: "第 5 段",
      source_quote: "新引用",
    };
    const result = await updateEvidence(PROJECT_ID, "card_001", payload);

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/evidence/card_001`);
    expect(opts.method).toBe("PUT");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    const body = JSON.parse(opts.body);
    expect(body.summary).toBe("更新后的摘要");
    expect(body.evidence_type).toBe("METHOD");
    expect(body.locator).toBe("第 5 段");
    expect(body.source_quote).toBe("新引用");
    expect(result.summary).toBe("更新后的摘要");
  });

  it("更新已确认卡片时抛出错误", async () => {
    const errorBody = { error: { code: "INVALID_STATUS", message: "已确认卡片不可更新" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    const payload: UpdateEvidenceCardRequest = {
      summary: "新摘要",
      evidence_type: "BACKGROUND",
      locator: "第 1 段",
      source_quote: null,
    };
    await expect(updateEvidence(PROJECT_ID, "card_001", payload)).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// confirmEvidence
// ============================================================

describe("confirmEvidence", () => {
  it("成功确认证据卡片", async () => {
    const confirmedCard = makeCard({
      status: "CONFIRMED",
      confirmed_at: "2026-07-23T11:00:00Z",
    });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(confirmedCard));

    const result = await confirmEvidence(PROJECT_ID, "card_001");

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/evidence/card_001/confirm`);
    expect(opts.method).toBe("POST");
    expect(result.status).toBe("CONFIRMED");
    expect(result.confirmed_at).not.toBeNull();
  });

  it("卡片 ID 被 URL 编码", async () => {
    const card = makeCard();
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(card));

    await confirmEvidence(PROJECT_ID, "card with space");

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("card%20with%20space");
  });

  it("确认已确认卡片时抛出错误", async () => {
    const errorBody = { error: { code: "INVALID_STATUS", message: "卡片已确认" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    await expect(confirmEvidence(PROJECT_ID, "card_001")).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// rejectEvidence
// ============================================================

describe("rejectEvidence", () => {
  it("成功拒绝证据卡片", async () => {
    const rejectedCard = makeCard({ status: "REJECTED" });
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(rejectedCard));

    const result = await rejectEvidence(PROJECT_ID, "card_001");

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/evidence/card_001/reject`);
    expect(opts.method).toBe("POST");
    expect(result.status).toBe("REJECTED");
  });

  it("拒绝已确认卡片时抛出错误", async () => {
    const errorBody = { error: { code: "INVALID_STATUS", message: "已确认卡片不可拒绝" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(409, errorBody));

    await expect(rejectEvidence(PROJECT_ID, "card_001")).rejects.toEqual(errorBody.error);
  });
});

// ============================================================
// completeEvidence
// ============================================================

describe("completeEvidence", () => {
  it("成功完成证据确认", async () => {
    const responseBody: CompleteEvidenceResponse = {
      project_id: PROJECT_ID,
      status: "EVIDENCE_CONFIRMED",
    };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse(responseBody));

    const result = await completeEvidence(PROJECT_ID);

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/evidence/complete`);
    expect(opts.method).toBe("POST");
    expect(result.status).toBe("EVIDENCE_CONFIRMED");
  });

  it("无确认证据卡片时抛出错误", async () => {
    const errorBody = { error: { code: "NO_CONFIRMED_EVIDENCE", message: "无确认的证据卡片" } };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(400, errorBody));

    await expect(completeEvidence(PROJECT_ID)).rejects.toEqual(errorBody.error);
  });
});
