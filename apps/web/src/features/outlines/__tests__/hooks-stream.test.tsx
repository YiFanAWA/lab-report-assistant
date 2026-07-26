/**
 * useStreamGenerateOutline hook 单元测试（SPEC 0019 大纲生成流式化）。
 *
 * 测试覆盖：
 * - start() 成功：chunk 累积 + done 事件触发 result + invalidate
 * - start() 错误事件：error 状态 + 保留 partial_text
 * - start() 网络异常：STREAM_NETWORK_ERROR
 * - start() 用户取消（AbortError）：streaming 变 false，无 error
 * - cancel()：调用 AbortController.abort()
 * - reset()：状态重置为初始值
 *
 * 通过 mock api.streamGenerateOutline 返回异步迭代器模拟 SSE 事件流。
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import * as api from "../api";
import { useStreamGenerateOutline } from "../hooks";
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
  outlineId: string,
  candidateSource: string,
  fallbackUsed: boolean
): SSEEvent {
  return {
    event: "done",
    data: JSON.stringify({
      outline_id: outlineId,
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

describe("useStreamGenerateOutline - 成功路径", () => {
  it("chunk 事件累积到 chunks（done 前可见）", async () => {
    const { Wrapper } = createWrapper();
    const streamSpy = vi
      .spyOn(api, "streamGenerateOutline")
      .mockReturnValue(
        makeMockStream([chunkEvent("hello"), chunkEvent(" world")])
      );

    const { result } = renderHook(() => useStreamGenerateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

    expect(result.current.streaming).toBe(false);
    expect(result.current.chunks).toBe("");

    // 完整等待 start 完成
    // 注意：此处 mock 流只产生 chunk 事件，无 done 事件，streaming 最终仍为 true
    await act(async () => {
      await result.current.start();
    });

    // chunks 应累积为 "hello world"
    expect(result.current.chunks).toBe("hello world");
    // 无 done 事件，streaming 仍为 true
    expect(result.current.streaming).toBe(true);

    expect(streamSpy).toHaveBeenCalledWith(PROJECT_ID, expect.any(AbortSignal));
  });

  it("done 事件设置 result 并清空 chunks", async () => {
    const { Wrapper } = createWrapper();
    vi.spyOn(api, "streamGenerateOutline").mockReturnValue(
      makeMockStream([
        chunkEvent('{"sections":['),
        chunkEvent('{"id":"s1"}]}'),
        doneEvent("ol_001", "DEEPSEEK", false),
      ])
    );

    const { result } = renderHook(() => useStreamGenerateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

    await act(async () => {
      await result.current.start();
    });

    expect(result.current.streaming).toBe(false);
    expect(result.current.chunks).toBe("");
    expect(result.current.result).toEqual({
      outline_id: "ol_001",
      candidate_source: "DEEPSEEK",
      fallback_used: false,
    });
    expect(result.current.error).toBeNull();
  });

  it("done 事件触发 invalidate outline list query", async () => {
    const { queryClient, Wrapper } = createWrapper();
    vi.spyOn(api, "streamGenerateOutline").mockReturnValue(
      makeMockStream([doneEvent("ol_001", "DEEPSEEK", false)])
    );

    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useStreamGenerateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

    await act(async () => {
      await result.current.start();
    });

    // 应触发大纲列表 query 的 invalidate（与 SPEC 0019 hook 实现一致）
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["outlines", PROJECT_ID, "list"],
    });
  });

  it("start 时重置旧状态", async () => {
    const { Wrapper } = createWrapper();
    // 第一次流式：返回 error
    vi.spyOn(api, "streamGenerateOutline")
      .mockReturnValueOnce(makeMockStream([errorEvent("LLM_ERROR", "失败", "部分")]))
      .mockReturnValueOnce(makeMockStream([doneEvent("ol_002", "LOCAL_RULE", true)]));

    const { result } = renderHook(() => useStreamGenerateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

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
      outline_id: "ol_002",
      candidate_source: "LOCAL_RULE",
      fallback_used: true,
    });
  });

  it("done 事件包含 fallback_used 标记", async () => {
    const { Wrapper } = createWrapper();
    vi.spyOn(api, "streamGenerateOutline").mockReturnValue(
      makeMockStream([doneEvent("ol_003", "LOCAL_RULE", true)])
    );

    const { result } = renderHook(() => useStreamGenerateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

    await act(async () => {
      await result.current.start();
    });

    expect(result.current.result?.fallback_used).toBe(true);
    expect(result.current.result?.candidate_source).toBe("LOCAL_RULE");
  });

  it("流式期间 streaming 为 true", async () => {
    const { Wrapper } = createWrapper();
    // 构造一个不结束的流（不 yield done/error）
    vi.spyOn(api, "streamGenerateOutline").mockReturnValue(
      makeMockStream([chunkEvent("部分内容")])
    );

    const { result } = renderHook(() => useStreamGenerateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

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

describe("useStreamGenerateOutline - error 事件", () => {
  it("error 事件设置错误信息并保留 partial_text", async () => {
    const { Wrapper } = createWrapper();
    vi.spyOn(api, "streamGenerateOutline").mockReturnValue(
      makeMockStream([
        chunkEvent('{"sections":['),
        chunkEvent('"部分内容"}'),
        errorEvent("OUTLINE_JSON_PARSE_ERROR", "JSON 校验失败", '{"sections":["部分内容"}'),
      ])
    );

    const { result } = renderHook(() => useStreamGenerateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

    await act(async () => {
      await result.current.start();
    });

    expect(result.current.streaming).toBe(false);
    expect(result.current.error).toEqual({
      error_code: "OUTLINE_JSON_PARSE_ERROR",
      message: "JSON 校验失败",
      partial_text: '{"sections":["部分内容"}',
    });
    expect(result.current.result).toBeNull();
  });
});

// ============================================================
// start() - 网络异常
// ============================================================

describe("useStreamGenerateOutline - 网络异常", () => {
  it("非 AbortError 异常被映射为 STREAM_NETWORK_ERROR", async () => {
    const { Wrapper } = createWrapper();
    vi.spyOn(api, "streamGenerateOutline").mockReturnValue(
      makeMockThrowingStream(new Error("network down"))
    );

    const { result } = renderHook(() => useStreamGenerateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

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
    vi.spyOn(api, "streamGenerateOutline").mockReturnValue(makeMockThrowingStream(abortErr));

    const { result } = renderHook(() => useStreamGenerateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

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

describe("useStreamGenerateOutline - cancel/reset", () => {
  it("cancel() 通过 AbortSignal 中断流式", async () => {
    const { Wrapper } = createWrapper();
    // 捕获传递给 streamGenerateOutline 的 signal
    let capturedSignal: AbortSignal | undefined;
    vi.spyOn(api, "streamGenerateOutline").mockImplementation(
      (pid: string, signal?: AbortSignal) => {
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

    const { result } = renderHook(() => useStreamGenerateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

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
    vi.spyOn(api, "streamGenerateOutline").mockReturnValue(
      makeMockStream([errorEvent("LLM_ERROR", "失败", "部分")])
    );

    const { result } = renderHook(() => useStreamGenerateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

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
    vi.spyOn(api, "streamGenerateOutline").mockReturnValue(makeMockStream([]));

    const { result } = renderHook(() => useStreamGenerateOutline(PROJECT_ID), {
      wrapper: Wrapper,
    });

    expect(result.current.streaming).toBe(false);
    expect(result.current.chunks).toBe("");
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
    expect(typeof result.current.start).toBe("function");
    expect(typeof result.current.cancel).toBe("function");
    expect(typeof result.current.reset).toBe("function");
  });
});
