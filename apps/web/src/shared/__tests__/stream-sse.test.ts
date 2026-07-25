/**
 * stream-sse.ts SSE 解析工具单元测试（SPEC 0018）。
 *
 * 测试覆盖：
 * - 成功场景：单事件块、多事件块、跨 chunk 的事件块拼接
 * - 事件字段：event / data 行解析，多 data 行用 \n 拼接
 * - 注释行：以 ":" 开头的行跳过
 * - 默认事件：无 event 行时使用 "message"
 * - 错误场景：HTTP 非 2xx 透传后端结构化错误
 * - 网络异常：fetch reject 时透传异常
 * - 取消：通过 AbortSignal 中断
 * - 空 body：抛出 "响应体为空"
 *
 * 通过 mock ReadableStream 模拟 SSE 数据流。
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { streamSSE, type SSEEvent } from "../stream-sse";

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

/** 构造一个成功的 fetch 响应。 */
function mockOkResponse(chunks: string[]): Response {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    body: makeMockStream(chunks),
  } as unknown as Response;
}

/** 构造一个失败的 fetch 响应（带 JSON 错误体）。 */
function mockErrorResponse(status: number, errorBody: unknown): Response {
  return {
    ok: false,
    status,
    statusText: "Bad Request",
    json: () => Promise.resolve(errorBody),
  } as unknown as Response;
}

/** 收集异步迭代器的所有事件。 */
async function collectAll(gen: AsyncGenerator<SSEEvent, void, unknown>): Promise<SSEEvent[]> {
  const events: SSEEvent[] = [];
  for await (const evt of gen) {
    events.push(evt);
  }
  return events;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

// ============================================================
// 成功场景
// ============================================================

describe("streamSSE - 成功解析", () => {
  it("解析单事件块", async () => {
    const sseText = "event: chunk\ndata: {\"text\":\"hello\"}\n\n";
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse([sseText]));

    const events = await collectAll(streamSSE("/api/test", {}));

    expect(events).toHaveLength(1);
    expect(events[0].event).toBe("chunk");
    expect(events[0].data).toBe('{"text":"hello"}');
  });

  it("解析多事件块", async () => {
    const sseText =
      "event: chunk\ndata: chunk1\n\nevent: chunk\ndata: chunk2\n\nevent: done\ndata: {\"plan_id\":\"p1\"}\n\n";
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse([sseText]));

    const events = await collectAll(streamSSE("/api/test", {}));

    expect(events).toHaveLength(3);
    expect(events[0].event).toBe("chunk");
    expect(events[0].data).toBe("chunk1");
    expect(events[1].event).toBe("chunk");
    expect(events[1].data).toBe("chunk2");
    expect(events[2].event).toBe("done");
    expect(events[2].data).toBe('{"plan_id":"p1"}');
  });

  it("跨 chunk 拼接不完整事件块", async () => {
    // 第一个 chunk 只包含半个事件块，第二个 chunk 补全
    const chunk1 = "event: chu";
    const chunk2 = "nk\ndata: hello\n\n";
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse([chunk1, chunk2]));

    const events = await collectAll(streamSSE("/api/test", {}));

    expect(events).toHaveLength(1);
    expect(events[0].event).toBe("chunk");
    expect(events[0].data).toBe("hello");
  });

  it("默认事件类型为 message（无 event 行）", async () => {
    const sseText = "data: hello\n\n";
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse([sseText]));

    const events = await collectAll(streamSSE("/api/test", {}));

    expect(events).toHaveLength(1);
    expect(events[0].event).toBe("message");
    expect(events[0].data).toBe("hello");
  });

  it("多行 data 用 \\n 拼接", async () => {
    const sseText = "data: line1\ndata: line2\ndata: line3\n\n";
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse([sseText]));

    const events = await collectAll(streamSSE("/api/test", {}));

    expect(events).toHaveLength(1);
    expect(events[0].data).toBe("line1\nline2\nline3");
  });

  it("跳过注释行（以 : 开头）", async () => {
    const sseText = ": this is a comment\nevent: chunk\ndata: hello\n\n";
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse([sseText]));

    const events = await collectAll(streamSSE("/api/test", {}));

    expect(events).toHaveLength(1);
    expect(events[0].event).toBe("chunk");
    expect(events[0].data).toBe("hello");
  });

  it("跳过空行", async () => {
    const sseText = "\n\nevent: chunk\ndata: hello\n\n\n";
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse([sseText]));

    const events = await collectAll(streamSSE("/api/test", {}));

    expect(events).toHaveLength(1);
    expect(events[0].data).toBe("hello");
  });

  it("冒号后单个空格被剥离（SSE 规范）", async () => {
    // SSE 规范：冒号后仅剥离一个可选空格
    const sseText = "event: spaced\ndata: value\n\n";
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse([sseText]));

    const events = await collectAll(streamSSE("/api/test", {}));

    expect(events[0].event).toBe("spaced");
    expect(events[0].data).toBe("value");
  });

  it("冒号后多空格仅剥离一个（SSE 规范）", async () => {
    // SSE 规范：仅剥离第一个空格，其余保留
    const sseText = "event:  spaced\ndata:  value\n\n";
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse([sseText]));

    const events = await collectAll(streamSSE("/api/test", {}));

    expect(events[0].event).toBe(" spaced");
    expect(events[0].data).toBe(" value");
  });

  it("处理尾部不完整事件块（无 \\n\\n 结尾）", async () => {
    // 尾部不完整的块（无 \n\n 结尾）应当被解析
    const sseText = "event: chunk\ndata: tail";
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse([sseText]));

    const events = await collectAll(streamSSE("/api/test", {}));

    expect(events).toHaveLength(1);
    expect(events[0].event).toBe("chunk");
    expect(events[0].data).toBe("tail");
  });

  it("空 body 不返回任何事件", async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse([""]));

    const events = await collectAll(streamSSE("/api/test", {}));

    expect(events).toEqual([]);
  });
});

// ============================================================
// 请求参数
// ============================================================

describe("streamSSE - 请求参数", () => {
  it("使用 POST 方法发送 JSON body", async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse([""]));

    const body = { source_id: "src_001" };
    await collectAll(streamSSE("/api/test", body));

    const [url, opts] = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("/api/test");
    expect(opts.method).toBe("POST");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(opts.body)).toEqual(body);
  });

  it("传递 AbortSignal", async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockOkResponse([""]));

    const controller = new AbortController();
    await collectAll(streamSSE("/api/test", {}, controller.signal));

    const opts = ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mock.calls[0][1];
    expect(opts.signal).toBe(controller.signal);
  });
});

// ============================================================
// 错误场景
// ============================================================

describe("streamSSE - 错误处理", () => {
  it("HTTP 4xx 透传后端结构化错误", async () => {
    const errorBody = {
      error: { code: "SOURCE_NOT_FOUND", message: "来源不存在" },
    };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(404, errorBody));

    await expect(collectAll(streamSSE("/api/test", {}))).rejects.toEqual(errorBody.error);
  });

  it("HTTP 5xx 透传后端结构化错误", async () => {
    const errorBody = {
      error: { code: "LLM_UNAVAILABLE", message: "LLM 服务不可用" },
    };
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce(mockErrorResponse(503, errorBody));

    await expect(collectAll(streamSSE("/api/test", {}))).rejects.toEqual(errorBody.error);
  });

  it("HTTP 错误无 JSON body 时返回默认错误", async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: () => Promise.reject(new Error("not json")),
    } as unknown as Response);

    await expect(collectAll(streamSSE("/api/test", {}))).rejects.toEqual({
      message: "请求失败 (500)",
    });
  });

  it("fetch reject 时透传异常", async () => {
    const networkErr = new Error("network down");
    (globalThis as any).fetch = vi.fn().mockRejectedValueOnce(networkErr);

    await expect(collectAll(streamSSE("/api/test", {}))).rejects.toBe(networkErr);
  });

  it("响应体为空时抛出错误", async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      body: null,
    } as unknown as Response);

    await expect(collectAll(streamSSE("/api/test", {}))).rejects.toEqual({
      message: "响应体为空",
    });
  });
});
