/**
 * useStreamGenerateEvidence hook 单元测试（SPEC 0020 证据卡片生成流式化）。
 *
 * 测试覆盖：
 * - start() 成功：chunk 累积 + done 事件触发 result + invalidate
 * - start() 错误事件：error 状态 + 保留 partial_text
 * - start() 网络异常：STREAM_NETWORK_ERROR
 * - start() 用户取消（AbortError）：streaming 变 false，无 error
 * - cancel()：调用 AbortController.abort()
 * - reset()：状态重置为初始值
 *
 * 通过 mock api.streamGenerateEvidence 返回异步迭代器模拟 SSE 事件流。
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import * as api from "../api";
import { useStreamGenerateEvidence } from "../hooks";
import type { SSEEvent } from "../../../shared/stream-sse";

// --- 测试辅助 ---

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  }
  return { queryClient, Wrapper };
}

const PROJECT_ID = "proj_001";
const SOURCE_ID = "src_001";

/** 构造一个 mock SSE 异步迭代器。 */
function makeMockStream(events: SSEEvent[]): AsyncGenerator<SSEEvent, void, unknown> {
  return (async function* () {
    for (const evt of events) {
      yield evt;
    }
  })();
}

/** 构造一个抛出异常的 mock 异步迭代器。 */
function makeMockThrowingStream(error: Error): AsyncGenerator<SSEEvent, void, unknown> {
  return (async function* () {
    throw error;
  })();
}

function chunkEvent(text: string): SSEEvent {
  return { event: "chunk", data: JSON.stringify({ text }) };
}

function doneEvent(
  cardCount: number,
  candidateSource: string,
  fallbackUsed: boolean
): SSEEvent {
  return {
    event: "done",
    data: JSON.stringify({
      card_count: cardCount,
      candidate_source: candidateSource,
      fallback_used: fallbackUsed,
    }),
  };
}

function errorEvent(errorCode: string, message: string, partialText: string): SSEEvent {
  return {
    event: "error",
    data: JSON.stringify({
      error_code: errorCode,
      message,
      partial_text: partialText,
    }),
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

// ============================================================
// start() - 成功路径
// ============================================================

describe("useStreamGenerateEvidence - 成功路径", () => {
  it("chunk 事件累积到 chunks（done 前可见）", async () => {
    const { Wrapper } = createWrapper();
    const streamSpy = vi
      .spyOn(api, "streamGenerateEvidence")
      .mockReturnValue(
        makeMockStream([chunkEvent("hello"), chunkEvent(" world")])
      );

    const { result } = renderHook(
      () => useStreamGenerateEvidence(PROJECT_ID, SOURCE_ID),
      { wrapper: Wrapper }
    );

    expect(result.current.streaming).toBe(false);
    expect(result.current.chunks).toBe("");

    await act(async () => {
      await result.current.start();
    });

    // chunks 应累积为 "hello world"
    expect(result.current.chunks).toBe("hello world");
    // 无 done 事件，streaming 仍为 true
    expect(result.current.streaming).toBe(true);

    expect(streamSpy).toHaveBeenCalledWith(
      PROJECT_ID,
      SOURCE_ID,
      expect.any(AbortSignal)
    );
  });

  it("done 事件设置 result 并清空 chunks", async () => {
    const { Wrapper } = createWrapper();
    vi.spyOn(api, "streamGenerateEvidence").mockReturnValue(
      makeMockStream([
        chunkEvent('{"cards":['),
        chunkEvent('{"summary":"背景"}]}'),
        doneEvent(1, "DEEPSEEK", false),
      ])
    );

    const { result } = renderHook(
      () => useStreamGenerateEvidence(PROJECT_ID, SOURCE_ID),
      { wrapper: Wrapper }
    );

    await act(async () => {
      await result.current.start();
    });

    expect(result.current.streaming).toBe(false);
    expect(result.current.chunks).toBe("");
    expect(result.current.result).toEqual({
      card_count: 1,
      candidate_source: "DEEPSEEK",
      fallback_used: false,
    });
    expect(result.current.error).toBeNull();
  });

  it("done 事件触发 invalidate evidence list query", async () => {
    const { queryClient, Wrapper } = createWrapper();
    vi.spyOn(api, "streamGenerateEvidence").mockReturnValue(
      makeMockStream([doneEvent(3, "DEEPSEEK", false)])
    );

    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(
      () => useStreamGenerateEvidence(PROJECT_ID, SOURCE_ID),
      { wrapper: Wrapper }
    );

    await act(async () => {
      await result.current.start();
    });

    // 应触发证据卡片列表 query 的 invalidate
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["evidence", PROJECT_ID, "list"],
    });
  });

  it("start 时重置旧状态", async () => {
    const { Wrapper } = createWrapper();
    // 第一次流式：返回 error
    vi.spyOn(api, "streamGenerateEvidence")
      .mockReturnValueOnce(makeMockStream([errorEvent("LLM_ERROR", "失败", "部分")]))
      .mockReturnValueOnce(makeMockStream([doneEvent(2, "LOCAL_RULE", true)]));

    const { result } = renderHook(
      () => useStreamGenerateEvidence(PROJECT_ID, SOURCE_ID),
      { wrapper: Wrapper }
    );

    // 第一次：error
    await act(async () => {
      await result.current.start();
    });
    expect(result.current.error).not.toBeNull();
    expect(result.current.error?.error_code).toBe("LLM_ERROR");

    // 第二次：成功，应清空旧 error
    await act(async () => {
      await result.current.start();
    });
    expect(result.current.error).toBeNull();
    expect(result.current.result).toEqual({
      card_count: 2,
      candidate_source: "LOCAL_RULE",
      fallback_used: true,
    });
  });

  it("done 事件包含 fallback_used 标记", async () => {
    const { Wrapper } = createWrapper();
    vi.spyOn(api, "streamGenerateEvidence").mockReturnValue(
      makeMockStream([doneEvent(3, "LOCAL_RULE", true)])
    );

    const { result } = renderHook(
      () => useStreamGenerateEvidence(PROJECT_ID, SOURCE_ID),
      { wrapper: Wrapper }
    );

    await act(async () => {
      await result.current.start();
    });

    expect(result.current.result?.fallback_used).toBe(true);
    expect(result.current.result?.candidate_source).toBe("LOCAL_RULE");
    expect(result.current.result?.card_count).toBe(3);
  });

  it("流式期间 streaming 为 true", async () => {
    const { Wrapper } = createWrapper();
    // 构造一个不结束的流（不 yield done/error）
    vi.spyOn(api, "streamGenerateEvidence").mockReturnValue(
      makeMockStream([chunkEvent("部分内容")])
    );

    const { result } = renderHook(
      () => useStreamGenerateEvidence(PROJECT_ID, SOURCE_ID),
      { wrapper: Wrapper }
    );

    await act(async () => {
      await result.current.start();
    });

    // 流未结束，streaming 仍为 true
    expect(result.current.streaming).toBe(true);
    expect(result.current.chunks).toBe("部分内容");
  });
});

// ============================================================
// start() - 错误事件
// ============================================================

describe("useStreamGenerateEvidence - error 事件", () => {
  it("error 事件设置错误信息并保留 partial_text", async () => {
    const { Wrapper } = createWrapper();
    vi.spyOn(api, "streamGenerateEvidence").mockReturnValue(
      makeMockStream([
        chunkEvent('{"cards":['),
        chunkEvent('"部分内容"}'),
        errorEvent(
          "EVIDENCE_JSON_PARSE_ERROR",
          "JSON 校验失败",
          '{"cards":["部分内容"}'
        ),
      ])
    );

    const { result } = renderHook(
      () => useStreamGenerateEvidence(PROJECT_ID, SOURCE_ID),
      { wrapper: Wrapper }
    );

    await act(async () => {
      await result.current.start();
    });

    expect(result.current.streaming).toBe(false);
    expect(result.current.error).toEqual({
      error_code: "EVIDENCE_JSON_PARSE_ERROR",
      message: "JSON 校验失败",
      partial_text: '{"cards":["部分内容"}',
    });
    expect(result.current.result).toBeNull();
  });
});

// ============================================================
// start() - 网络异常
// ============================================================

describe("useStreamGenerateEvidence - 网络异常", () => {
  it("非 AbortError 异常被映射为 STREAM_NETWORK_ERROR", async () => {
    const { Wrapper } = createWrapper();
    vi.spyOn(api, "streamGenerateEvidence").mockReturnValue(
      makeMockThrowingStream(new Error("network down"))
    );

    const { result } = renderHook(
      () => useStreamGenerateEvidence(PROJECT_ID, SOURCE_ID),
      { wrapper: Wrapper }
    );

    await act(async () => {
      await result.current.start();
    });

    expect(result.current.streaming).toBe(false);
    expect(result.current.error).toEqual({
      error_code: "STREAM_NETWORK_ERROR",
      message: "network down",
      partial_text: "",
    });
  });

  it("AbortError 不视为错误，仅结束 streaming", async () => {
    const { Wrapper } = createWrapper();
    const abortErr = new Error("aborted");
    abortErr.name = "AbortError";
    vi.spyOn(api, "streamGenerateEvidence").mockReturnValue(
      makeMockThrowingStream(abortErr)
    );

    const { result } = renderHook(
      () => useStreamGenerateEvidence(PROJECT_ID, SOURCE_ID),
      { wrapper: Wrapper }
    );

    await act(async () => {
      await result.current.start();
    });

    expect(result.current.streaming).toBe(false);
    expect(result.current.error).toBeNull();
  });
});

// ============================================================
// cancel() 和 reset()
// ============================================================

describe("useStreamGenerateEvidence - cancel/reset", () => {
  it("cancel() 通过 AbortSignal 中断流式", async () => {
    const { Wrapper } = createWrapper();
    // 捕获传递给 streamGenerateEvidence 的 signal
    let capturedSignal: AbortSignal | undefined;
    vi.spyOn(api, "streamGenerateEvidence").mockImplementation(
      (pid: string, sid: string, signal?: AbortSignal) => {
        capturedSignal = signal;
        // 返回一个在 signal abort 时抛 AbortError 的流
        return (async function* () {
          if (signal?.aborted) {
            const err = new Error("aborted");
            err.name = "AbortError";
            throw err;
          }
          await new Promise((resolve) => setTimeout(resolve, 50));
          if (signal?.aborted) {
            const err = new Error("aborted");
            err.name = "AbortError";
            throw err;
          }
        })();
      }
    );

    const { result } = renderHook(
      () => useStreamGenerateEvidence(PROJECT_ID, SOURCE_ID),
      { wrapper: Wrapper }
    );

    // 启动流式
    let startPromise: Promise<void>;
    act(() => {
      startPromise = result.current.start();
    });

    await waitFor(() => {
      expect(result.current.streaming).toBe(true);
    });

    expect(capturedSignal).toBeDefined();
    expect(capturedSignal?.aborted).toBe(false);

    // 取消
    act(() => {
      result.current.cancel();
    });

    expect(capturedSignal?.aborted).toBe(true);

    await act(async () => {
      await startPromise!;
    });

    expect(result.current.streaming).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("reset() 重置状态到初始值", async () => {
    const { Wrapper } = createWrapper();
    vi.spyOn(api, "streamGenerateEvidence").mockReturnValue(
      makeMockStream([errorEvent("LLM_ERROR", "失败", "部分")])
    );

    const { result } = renderHook(
      () => useStreamGenerateEvidence(PROJECT_ID, SOURCE_ID),
      { wrapper: Wrapper }
    );

    await act(async () => {
      await result.current.start();
    });
    expect(result.current.error).not.toBeNull();

    // 重置
    act(() => {
      result.current.reset();
    });

    expect(result.current.streaming).toBe(false);
    expect(result.current.chunks).toBe("");
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("初始状态正确", () => {
    const { Wrapper } = createWrapper();
    vi.spyOn(api, "streamGenerateEvidence").mockReturnValue(makeMockStream([]));

    const { result } = renderHook(
      () => useStreamGenerateEvidence(PROJECT_ID, SOURCE_ID),
      { wrapper: Wrapper }
    );

    expect(result.current.streaming).toBe(false);
    expect(result.current.chunks).toBe("");
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
    expect(typeof result.current.start).toBe("function");
    expect(typeof result.current.cancel).toBe("function");
    expect(typeof result.current.reset).toBe("function");
  });
});
