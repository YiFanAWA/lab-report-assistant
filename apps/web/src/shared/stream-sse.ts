/**
 * 通用 SSE 解析工具。
 *
 * SPEC 0018 流式 LLM 输出。
 *
 * 使用 fetch + ReadableStream 而非 EventSource，以支持 POST + body。
 * 处理 event: xxx / data: yyy 格式的 SSE 文本块。
 *
 * SSE 规范要点：
 * - 事件块以 \n\n 分隔
 * - 每块包含若干行，每行格式为 "field: value"
 * - event: 行指定事件类型（默认 "message"）
 * - data: 行指定数据（多行 data 用 \n 拼接）
 * - 以 ":" 开头的行是注释，跳过
 */

export interface SSEEvent {
  /** 事件类型，如 "chunk" / "done" / "error" / "message" */
  event: string;
  /** 数据字符串（JSON 字符串，由调用方解析） */
  data: string;
}

/**
 * 发起 SSE 请求并返回异步迭代器。
 *
 * @param url 请求 URL
 * @param body 请求体（POST JSON）
 * @param signal 可选的 AbortSignal，用于取消
 * @yields SSEEvent 对象
 * @throws 当 HTTP 状态码非 2xx 时抛出后端结构化错误
 */
export async function* streamSSE(
  url: string,
  body: unknown,
  signal?: AbortSignal
): AsyncGenerator<SSEEvent, void, unknown> {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!resp.ok) {
    let detail: unknown = null;
    try {
      detail = await resp.json();
    } catch {
      detail = { message: `请求失败 (${resp.status})` };
    }
    // 透传后端结构化错误（与 handle() 一致的错误格式）
    const err = detail as { error?: unknown } | null;
    throw err?.error ?? err ?? { message: resp.statusText };
  }

  if (!resp.body) {
    throw { message: "响应体为空" };
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // 按 \n\n 分隔事件块
      const events = buffer.split("\n\n");
      // 最后一段可能不完整，保留在 buffer
      buffer = events.pop() || "";

      for (const evtText of events) {
        const parsed = parseSSEBlock(evtText);
        if (parsed) {
          yield parsed;
        }
      }
    }

    // 处理 buffer 中剩余的最后一个事件块（如果以 \n\n 结尾则已处理，否则丢弃不完整块）
    if (buffer.trim()) {
      const parsed = parseSSEBlock(buffer);
      if (parsed) {
        yield parsed;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * 解析单个 SSE 事件块。
 *
 * @param block 事件块文本（不含尾部的 \n\n）
 * @returns SSEEvent 或 null（空块或纯注释）
 */
function parseSSEBlock(block: string): SSEEvent | null {
  const lines = block.split("\n");
  let event = "message";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (!line || line.startsWith(":")) {
      // 空行或注释行，跳过
      continue;
    }
    const colonIndex = line.indexOf(":");
    if (colonIndex === -1) {
      // 无冒号的行，视为字段名，值为空
      continue;
    }
    const field = line.slice(0, colonIndex);
    // 冒号后可能有一个空格，按 SSE 规范跳过
    let value = line.slice(colonIndex + 1);
    if (value.startsWith(" ")) {
      value = value.slice(1);
    }

    if (field === "event") {
      event = value;
    } else if (field === "data") {
      dataLines.push(value);
    }
  }

  const data = dataLines.join("\n");
  if (!data) {
    return null;
  }

  return { event, data };
}
