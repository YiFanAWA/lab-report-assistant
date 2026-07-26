/**
 * streamGenerateAnalysisPlan API 单元测试（SPEC 0021 分析方案生成流式化）。
 *
 * 测试覆盖：
 * - 成功路径：正确 URL、POST 方法、空 JSON body
 * - 项目 ID 和数据集 ID 都被 URL 编码
 * - 委托给 streamSSE 解析事件
 * - 传递 AbortSignal
 * - HTTP 错误透传后端结构化错误
 *
 * 通过 mock (globalThis as any).fetch + ReadableStream 模拟 SSE 响应。
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { streamGenerateAnalysisPlan } from "../api";
import type { SSEEvent } from "../../../shared/stream-sse";

const BASE = "/api";
const PROJECT_ID = "proj_abc123";
const DATASET_ID = "ds_def456";

/** 构造一个 mock ReadableStream，按顺序推送 chunks。 */
function makeMockStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

/** 构造一个成功的 SSE 响应。 */
function mockSSEResponse(chunks: string[]): Response {
  return {
    ok: true,
    status: 200,
    body: makeMockStream(chunks),
  } as unknown as Response;
}

/** 构造一个失败的响应。 */
function mockErrorResponse(status: number, errorBody: unknown): Response {
  return {
    ok: false,
    status,
    statusText: "Bad Request",
    json: () => Promise.resolve(errorBody),
  } as unknown as Response;
}

/** 收集所有 SSE 事件。 */
async function collectAll(
  gen: AsyncGenerator<SSEEvent, void, unknown>
): Promise<SSEEvent[]> {
  const events: SSEEvent[] = [];
  for await (const evt of gen) {
    events.push(evt);
  }
  return events;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("streamGenerateAnalysisPlan - SPEC 0021", () => {
  it("使用正确的 URL 和 POST 方法", async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockSSEResponse([""]));

    await collectAll(streamGenerateAnalysisPlan(PROJECT_ID, DATASET_ID));

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe(
      `${BASE}/projects/${PROJECT_ID}/datasets/${DATASET_ID}/analysis/stream-generate`
    );
    expect(opts.method).toBe("POST");
    expect(opts.headers["Content-Type"]).toBe("application/json");
  });

  it("请求体为空对象（dataset_id 在 URL 中而非 body）", async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockSSEResponse([""]));

    await collectAll(streamGenerateAnalysisPlan(PROJECT_ID, DATASET_ID));

    const opts = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][1];
    const body = JSON.parse(opts.body);
    // 分析方案流式：dataset_id 在 URL 路径中，body 应为空对象
    expect(body).toEqual({});
    expect(body.dataset_id).toBeUndefined();
  });

  it("项目 ID 和数据集 ID 都被 URL 编码", async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockSSEResponse([""]));

    await collectAll(
      streamGenerateAnalysisPlan("proj with space", "ds with slash")
    );

    const url = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toContain("proj%20with%20space");
    expect(url).toContain("ds%20with%20slash");
  });

  it("委托给 streamSSE 解析 SSE 事件", async () => {
    const sseText =
      'event: chunk\ndata: {"text":"hello"}\n\nevent: done\ndata: {"plan_id":"plan_001"}\n\n';
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockSSEResponse([sseText]));

    const events = await collectAll(streamGenerateAnalysisPlan(PROJECT_ID, DATASET_ID));

    expect(events).toHaveLength(2);
    expect(events[0].event).toBe("chunk");
    expect(events[0].data).toBe('{"text":"hello"}');
    expect(events[1].event).toBe("done");
    expect(events[1].data).toBe('{"plan_id":"plan_001"}');
  });

  it("传递 AbortSignal", async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockSSEResponse([""]));

    const controller = new AbortController();
    await collectAll(streamGenerateAnalysisPlan(PROJECT_ID, DATASET_ID, controller.signal));

    const opts = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][1];
    expect(opts.signal).toBe(controller.signal);
  });

  it("HTTP 错误透传后端结构化错误", async () => {
    const errorBody = {
      error: { code: "DATASET_NOT_FOUND", message: "数据集不存在" },
    };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(
      collectAll(streamGenerateAnalysisPlan("proj_missing", "ds_missing"))
    ).rejects.toEqual(errorBody.error);
  });
});
