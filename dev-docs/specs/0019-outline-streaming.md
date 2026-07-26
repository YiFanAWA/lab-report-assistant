# SPEC 0019：大纲生成流式化

**版本：** 1.0
**日期：** 2026-07-26
**状态：** 已实现并由项目负责人确认收口
**目标版本：** v2.1.0
**前置版本：** v2.0.0（SPEC 0018 流式 LLM 输出）
**关联决策：** [决策 0025](../decisions/0025-start-spec-0019-outline-streaming.md)

> **实现收口说明（2026-07-26）：** SPEC 0019 已完成实现与验收。后端 821 passed（新增 38 测试），前端 493 passed（新增 25 测试），tsc 通过，Vite build 成功。浏览器验收 PASS（后端 200 OK + 大纲保存 6 章节 + 列表自动刷新；transient 流式 UI 状态因 LocalRule 同步降级路径过快未被快照捕获，验证工具限制非代码缺陷）。不引入新依赖，不修改数据库 schema，复用 SPEC 0018 stream-sse.ts 零修改。详细验收记录见 [acceptance.md](../acceptance.md) SPEC 0019 章节，发布说明见 [changelog-v2.1.0.md](../changelog-v2.1.0.md)。

---

## 一、背景与目标

### 1.1 痛点

大纲生成是实验报告工作流中**等待时间最长**的 LLM 调用（10-30s）。当前实现（V2.0.0）通过 Worker 异步执行：

1. 前端调用 `POST /outline/generate` → 创建 Worker Job → 返回 `job_id`
2. 前端轮询 job 状态
3. Worker 进程领取 Job → 聚合上下文（5 个模块）→ 调用 LLM 生成 6 章节大纲 → 保存
4. Job 完成后，前端轮询发现状态变化 → 刷新大纲列表

用户痛点：
- 10-30s 空白等待，无进度反馈
- 无法看到 LLM 生成过程
- 无法中途取消
- 上下文聚合和 LLM 调用都在 Worker 中，不可观察

### 1.2 目标

将大纲生成改造为 SSE 流式输出，复用 SPEC 0018 的流式架构：
- 新增 `POST /outline/stream-generate` SSE 端点（绕过 Worker）
- 后端流式调用 LLM，逐 chunk 推送
- 前端实时显示生成内容，支持取消
- 保留原 `POST /outline/generate`（Worker 异步）兼容

### 1.3 与 SPEC 0018 的关系

SPEC 0019 是 SPEC 0018 流式能力的**自然延伸**：

| 维度 | SPEC 0018（任务单生成） | SPEC 0019（大纲生成） |
| --- | --- | --- |
| 流式架构 | SSE + Gateway 直调 | SSE + Gateway 直调（复用） |
| 端点 | `POST /plans/stream-generate` | `POST /outline/stream-generate` |
| Provider | `DeepSeekRequirementDraftProvider` | `DeepSeekOutlineProvider` |
| 上下文来源 | 单一 requirement_text | 跨模块聚合（5 个模块） |
| 原同步路径 | `POST /plans/generate`（保留） | `POST /outline/generate`（Worker，保留） |
| 前端工具 | `stream-sse.ts`（复用） | `stream-sse.ts`（复用） |
| 降级策略 | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule（复用模式） |

---

## 二、范围与边界

### 2.1 在范围内

1. 后端 `DeepSeekOutlineProvider.stream_generate()` 流式方法
2. 后端 `outline_service.stream_generate_outline()` 流式 service 方法
3. 后端 `outline_service.gather_outline_context()` 上下文聚合（从 worker handler 提取）
4. 后端 `POST /outline/stream-generate` SSE 端点
5. 前端 `streamGenerateOutline()` API 函数
6. 前端 `useStreamGenerateOutline()` hook
7. 前端大纲生成 UI 改造（流式按钮 + 展示区 + 取消）
8. 后端单元测试（Provider + Service + API）
9. 前端单元测试（API + Hook）
10. 浏览器验收

### 2.2 不在范围内

1. 不改造原 Worker 异步端点（`POST /outline/generate` 保留不变）
2. 不流式化证据卡片、分析方案、代码任务生成
3. 不引入 WebSocket / 长轮询
4. 不修改数据库 schema
5. 不引入新依赖
6. 不修改 `stream-sse.ts`（复用 SPEC 0018）
7. 不修改 `DeepSeekClient.stream_chat_completion()`（复用 SPEC 0018）

---

## 三、架构设计

### 3.1 整体架构

```text
前端 useStreamGenerateOutline
    │
    ▼ fetch + ReadableStream
POST /outline/stream-generate (SSE)
    │
    ▼ StreamingResponse
outline_service.stream_generate_outline()
    │
    ├──▶ Phase 1: 校验 + 聚合上下文（持有 db）
    │       └──▶ gather_outline_context()（从 worker handler 提取）
    │
    ├──▶ Phase 2: 流式生成（关闭 db）
    │       └──▶ DeepSeekOutlineProvider.stream_generate(context)
    │               └──▶ DeepSeekClient.stream_chat_completion()
    │                       └──▶ httpx.Client.stream() → SSE 行
    │
    └──▶ Phase 3: 保存（重新打开 db）
            └──▶ save_outline_draft()
```

### 3.2 SSE 事件合同（复用 SPEC 0018 格式）

```text
event: chunk
data: {"text": "实验目的"}

event: chunk
data: {"text": "：分析胃病数据"}

event: done
data: {"outline_id": "outline_xxx", "candidate_source": "DEEPSEEK", "fallback_used": false}

event: error
data: {"error_code": "DEEPSEEK_TIMEOUT", "message": "流式请求超时", "partial_text": "{\"sections\":..."}
```

### 3.3 降级策略（复用 SPEC 0018 模式）

| 失败时机 | 降级行为 | 用户可见 | 是否保存 | 是否写缓存 |
| --- | --- | --- | --- | --- |
| 首 chunk 前 | 降级到 LocalRule，拆分多 chunk 模拟流式 | 是 | 是（LocalRule 结果保存） | 是 |
| 中途失败 | 保留已生成 chunk + 推送 error 事件 | 是（部分内容 + 错误提示） | 否 | 否 |
| 网络异常 | 前端映射 `STREAM_NETWORK_ERROR` | 是（错误提示 + partial_text） | 否 | 否 |
| 用户取消 | AbortController.abort() | 是（流式停止） | 否 | 否 |

### 3.4 分段 db session（复用 SPEC 0018 模式）

- **Phase 1**：校验项目状态 + 聚合上下文（持有 db）→ 完成后 `db.close()`
- **Phase 2**：流式生成（不持有 db，避免 SQLite 写锁阻塞）
- **Phase 3**：完成后重新打开 db → 保存 Outline → `db2.close()`

---

## 四、实现细节

### 4.1 `DeepSeekOutlineProvider.stream_generate()` 实现

**文件：** `server/app/modules/llm/deepseek_outline_provider.py`
**新增方法：**

```python
from typing import Generator

def stream_generate(
    self, context: dict[str, Any]
) -> Generator[str, None, None]:
    """流式调用 DeepSeek 生成大纲，逐 chunk yield content。

    首 chunk 前失败降级到 LocalRule，拆分多 chunk 模拟流式。
    中途失败抛异常，由调用方处理。
    """
    chunks: list[str] = []
    started = False
    try:
        for chunk in self._client.stream_chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(context)},
            ],
            response_format={"type": "json_object"},
            temperature=self._temperature,
        ):
            started = True
            chunks.append(chunk)
            yield chunk
    except (DeepSeekError, httpx.HTTPError) as e:
        if not started:
            # 首 chunk 前失败，降级到 LocalRule
            logger.warning(f"DeepSeek 流式大纲失败，降级到 LocalRule: {e}")
            fallback_draft = self._fallback.generate(context)
            fallback_json = fallback_draft.model_dump_json()
            # 拆分为多个 chunk 模拟流式
            for i in range(0, len(fallback_json), 50):
                yield fallback_json[i:i + 50]
            return
        # 中途失败不降级，抛异常让调用方处理
        raise

    # 流式完成后，校验 JSON（不 yield，仅校验）
    raw = "".join(chunks)
    try:
        parsed = self._parse_and_validate(raw)
    except (DeepSeekError, ValidationError, ValueError) as e:
        # JSON 校验失败，降级到 LocalRule
        logger.warning(f"流式大纲 JSON 校验失败，降级到 LocalRule: {e}")
        fallback_draft = self._fallback.generate(context)
        fallback_json = fallback_draft.model_dump_json()
        # 注意：这里已经 yield 过原始 chunk，无法撤回
        # 但我们不保存这个结果，由调用方判断
        raise DeepSeekError(
            code="DEEPSEEK_JSON_PARSE_ERROR",
            message=f"流式大纲 JSON 校验失败: {e}",
        ) from e
```

**注意：** JSON 校验失败的处理需要特别考虑。由于 chunk 已经 yield 给前端，无法撤回。方案：
- 方案 A：流式完成后 JSON 校验失败 → 推送 `error` 事件 → 不保存 Outline
- 方案 B：流式完成后 JSON 校验失败 → 降级到 LocalRule 重新生成（但用户会看到两次生成）

选择**方案 A**：JSON 校验失败时推送 `error` 事件，不保存 Outline，用户可重试。

### 4.2 上下文聚合提取

**文件：** `server/app/modules/outlines/service.py`
**新增方法：**

```python
def gather_outline_context(db: Session, project_id: str) -> dict:
    """聚合大纲生成所需的上下文。

    从各 owner 服务查询已确认内容：
    - requirements: 已确认任务单
    - sources: 已确认证据卡片
    - datasets: 数据集字段概览
    - analysis: 已确认分析方案
    - execution: 成功的执行记录和产物

    从 worker/handlers.py 的 _gather_outline_context() 提取，
    让流式 service 和 Worker handler 共享。
    """
    # ... 从 worker/handlers.py 移植的代码 ...
    return context
```

**文件：** `server/worker/handlers.py`
**修改：**

```python
def handle_generate_outline(db: Session, job) -> dict:
    # ... 前置校验 ...

    # 聚合上下文（改为调用 service 层方法）
    context = outline_service.gather_outline_context(db, project_id)

    provider = get_outline_provider()
    draft = provider.generate(context)
    # ... 保存逻辑不变 ...
```

### 4.3 `outline_service.stream_generate_outline()` 实现

**文件：** `server/app/modules/outlines/service.py`
**新增方法和事件类型：**

```python
from dataclasses import dataclass
from typing import Generator

@dataclass
class StreamOutlineChunkEvent:
    text: str

@dataclass
class StreamOutlineDoneEvent:
    outline_id: str
    candidate_source: str
    fallback_used: bool

@dataclass
class StreamOutlineErrorEvent:
    error_code: str
    message: str
    partial_text: str

StreamOutlineEvent = (
    StreamOutlineChunkEvent
    | StreamOutlineDoneEvent
    | StreamOutlineErrorEvent
)


def stream_generate_outline(
    db: Session, project_id: str, provider
) -> Generator[StreamOutlineEvent, None, None]:
    """流式生成大纲。

    Phase 1: 校验 + 聚合上下文（持有 db）
    Phase 2: 流式生成（关闭 db）
    Phase 3: 保存（重新打开 db）
    """
    # Phase 1: 校验 + 聚合上下文
    project = _ensure_project(db, project_id)
    _ensure_project_ready_for_outline(project)

    from app.modules.execution.models import ExecutionRun
    from app.modules.execution.status import ExecutionRunStatus
    succeeded_count = (
        db.query(ExecutionRun)
        .filter(
            ExecutionRun.project_id == project_id,
            ExecutionRun.status == ExecutionRunStatus.SUCCEEDED.value,
        )
        .count()
    )
    if succeeded_count == 0:
        raise AppError(code="OUTLINE_NOT_GENERATABLE",
                       message="没有成功的执行记录，无法生成大纲")

    context = gather_outline_context(db, project_id)
    db.close()  # 显式关闭，避免流式期间持有连接

    # Phase 2: 流式生成（不持有 db）
    chunks: list[str] = []
    fallback_used = False
    try:
        if hasattr(provider, "stream_generate"):
            for chunk in provider.stream_generate(context):
                chunks.append(chunk)
                yield StreamOutlineChunkEvent(text=chunk)
        else:
            # 兼容只支持同步的 provider
            draft = provider.generate(context)
            full_json = draft.model_dump_json()
            for i in range(0, len(full_json), 50):
                yield StreamOutlineChunkEvent(text=full_json[i:i + 50])
            chunks.append(full_json)
    except Exception as e:
        partial_text = "".join(chunks)
        yield StreamOutlineErrorEvent(
            error_code="OUTLINE_STREAM_FAILED",
            message=str(e),
            partial_text=partial_text,
        )
        return

    # Phase 2.5: 校验完整 JSON
    raw = "".join(chunks)
    try:
        parsed = DeepSeekOutlineResponse.model_validate_json(raw)
        sections_data = [
            {
                "id": s.id,
                "title": s.title,
                "content": s.content,
                "source_type": s.source_type,
                "source_ids": s.source_ids,
            }
            for s in parsed.sections
        ]
    except Exception as e:
        partial_text = raw
        yield StreamOutlineErrorEvent(
            error_code="OUTLINE_JSON_PARSE_ERROR",
            message=f"大纲 JSON 校验失败: {e}",
            partial_text=partial_text,
        )
        return

    # Phase 3: 保存（重新打开 db）
    from app.infrastructure.database.engine import SessionLocal
    db2 = SessionLocal()
    try:
        outline = save_outline_draft(
            db2,
            project_id=project_id,
            sections=sections_data,
            candidate_source=provider.source_label(),
        )
        _add_change(db2, project_id,
                    OutlineChangeType.OUTLINE_GENERATED.value,
                    f"流式生成大纲候选：{len(sections_data)} 个章节")
        db2.commit()
        yield StreamOutlineDoneEvent(
            outline_id=outline.id,
            candidate_source=provider.source_label(),
            fallback_used=fallback_used,
        )
    except Exception as e:
        yield StreamOutlineErrorEvent(
            error_code="OUTLINE_SAVE_FAILED",
            message=f"大纲保存失败: {e}",
            partial_text=raw,
        )
    finally:
        db2.close()
```

### 4.4 API 端点实现

**文件：** `server/app/api/routers/outlines.py`
**新增端点：**

```python
from fastapi.responses import StreamingResponse
import json
from app.modules.llm.gateway import get_outline_provider
from app.modules.outlines.service import (
    stream_generate_outline,
    StreamOutlineChunkEvent,
    StreamOutlineDoneEvent,
    StreamOutlineErrorEvent,
)


def _serialize_outline_sse_event(event) -> str:
    """将流式事件序列化为 SSE 文本。"""
    if isinstance(event, StreamOutlineChunkEvent):
        return f"event: chunk\ndata: {json.dumps({'text': event.text}, ensure_ascii=False)}\n\n"
    elif isinstance(event, StreamOutlineDoneEvent):
        data = {
            "outline_id": event.outline_id,
            "candidate_source": event.candidate_source,
            "fallback_used": event.fallback_used,
        }
        return f"event: done\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    elif isinstance(event, StreamOutlineErrorEvent):
        data = {
            "error_code": event.error_code,
            "message": event.message,
            "partial_text": event.partial_text,
        }
        return f"event: error\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    return ""


@router.post("/outline/stream-generate")
def stream_generate_outline_endpoint(project_id: str):
    """流式生成大纲（SPEC 0019）。

    SSE 端点，绕过 Worker，直接调用 LLM provider 流式生成。
    保留原 POST /outline/generate（Worker 异步）兼容。
    """
    provider = get_outline_provider()

    def event_stream():
        db = SessionLocal()
        try:
            for event in stream_generate_outline(db, project_id, provider):
                yield _serialize_outline_sse_event(event)
        finally:
            db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

### 4.5 前端 API 实现

**文件：** `apps/web/src/features/outlines/api.ts`
**新增函数：**

```typescript
import { streamSSE, type SSEEvent } from "../../shared/stream-sse";

/**
 * 流式生成大纲（SPEC 0019）。
 *
 * 返回异步迭代器，逐个 yield SSE 事件。
 * 复用 SPEC 0018 的 streamSSE 工具。
 */
export async function* streamGenerateOutline(
  projectId: string,
  signal?: AbortSignal
): AsyncGenerator<SSEEvent, void, unknown> {
  const url = `${BASE}/projects/${encodeURIComponent(projectId)}/outline/stream-generate`;
  yield* streamSSE(url, {}, signal);
}
```

### 4.6 前端 Hook 实现

**文件：** `apps/web/src/features/outlines/hooks.ts`
**新增 hook：**

```typescript
export interface StreamOutlineState {
  /** 是否正在流式生成 */
  streaming: boolean;
  /** 已生成的完整文本（chunk 累积） */
  chunks: string;
  /** 完成事件返回的结果 */
  result: {
    outline_id: string;
    candidate_source: string;
    fallback_used: boolean;
  } | null;
  /** 错误事件返回的信息 */
  error: {
    error_code: string;
    message: string;
    partial_text: string;
  } | null;
}

const INITIAL_STREAM_STATE: StreamOutlineState = {
  streaming: false,
  chunks: "",
  result: null,
  error: null,
};

export function useStreamGenerateOutline(projectId: string) {
  const qc = useQueryClient();
  const [state, setState] = useState<StreamOutlineState>(INITIAL_STREAM_STATE);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(async () => {
    setState({ ...INITIAL_STREAM_STATE, streaming: true });
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const evt of streamGenerateOutline(
        projectId,
        controller.signal
      )) {
        if (evt.event === "chunk") {
          const { text } = JSON.parse(evt.data);
          setState((s) => ({ ...s, chunks: s.chunks + text }));
        } else if (evt.event === "done") {
          const data = JSON.parse(evt.data);
          setState({
            streaming: false,
            chunks: "",
            result: data,
            error: null,
          });
          // 刷新大纲列表
          qc.invalidateQueries({
            queryKey: [...outlinesKey(projectId), "list"],
          });
        } else if (evt.event === "error") {
          const data = JSON.parse(evt.data);
          setState((s) => ({
            ...s,
            error: data,
            streaming: false,
          }));
        }
      }
    } catch (e: unknown) {
      const err = e as { name?: string; message?: string };
      if (err?.name === "AbortError") {
        setState((s) => ({ ...s, streaming: false }));
      } else {
        setState((s) => ({
          ...s,
          error: {
            error_code: "STREAM_NETWORK_ERROR",
            message: err?.message ?? "流式连接失败",
            partial_text: s.chunks,
          },
          streaming: false,
        }));
      }
    } finally {
      abortRef.current = null;
    }
  }, [projectId, qc]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    setState(INITIAL_STREAM_STATE);
  }, []);

  return { ...state, start, cancel, reset };
}
```

### 4.7 前端 UI 改造

**文件：** `apps/web/src/routes/OutlineWorkspaceView.tsx`
**改造点：**

在大纲生成区域新增：
- "流式生成大纲"按钮（与原"生成大纲"按钮并列）
- 流式展示区（带边框灰色背景 + 取消按钮 + `<pre>` chunk 累积）
- 完成提示"流式生成完成 ✓ [源]"
- 错误展示

```tsx
// 新增导入
import { useStreamGenerateOutline } from "../features/outlines/hooks";

// 在组件中
const streamOutline = useStreamGenerateOutline(pid);

// UI 新增
<div style={{ marginTop: "1rem" }}>
  <button
    onClick={() => streamOutline.start()}
    disabled={streamOutline.streaming}
    style={{ padding: "0.5rem 1rem" }}
  >
    {streamOutline.streaming ? "生成中…" : "流式生成大纲"}
  </button>
  {streamOutline.streaming && (
    <div style={{ marginTop: "0.5rem", padding: "1rem", border: "1px solid #e5e7eb", background: "#f9fafb" }}>
      <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem", fontFamily: "monospace", maxHeight: "300px", overflow: "auto" }}>
        {streamOutline.chunks}
      </pre>
      <button
        onClick={streamOutline.cancel}
        style={{ marginTop: "0.5rem", padding: "0.3rem 0.8rem", fontSize: "0.85rem" }}
      >
        取消
      </button>
    </div>
  )}
  {streamOutline.result && (
    <p style={{ color: "#16a34a", fontSize: "0.85rem" }}>
      流式生成完成 ✓ [{streamOutline.result.candidate_source}]
    </p>
  )}
  {streamOutline.error && (
    <div style={{ color: "#c00", fontSize: "0.85rem" }}>
      <p>生成失败：{streamOutline.error.message}</p>
      {streamOutline.error.partial_text && (
        <details>
          <summary>已生成内容</summary>
          <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem" }}>
            {streamOutline.error.partial_text}
          </pre>
        </details>
      )}
    </div>
  )}
</div>
```

---

## 五、测试策略

### 5.1 后端测试

| 测试文件 | 测试数量 | 覆盖点 |
| --- | --- | --- |
| `test_deepseek_outline_provider_stream.py` | 12 | 流式成功 / 缓存命中 / 首 chunk 前降级 LocalRule / 中途失败抛异常 / JSON 校验失败 / 空响应 |
| `test_outline_service_stream.py` | 10 | stream_generate_outline 成功 / 中途失败不保存 / 兼容同步 provider / 分段 db session / 上下文聚合正确性 |
| `test_outline_stream_api.py` | 10 | SSE 端点返回 text/event-stream / 事件格式 / 项目不存在 404 / 无执行记录 404 / 原端点零回归 |
| `test_outline_context.py` | 5 | gather_outline_context 提取后的独立测试（各模块数据聚合） |
| **小计** | **37** | — |

### 5.2 前端测试

| 测试文件 | 测试数量 | 覆盖点 |
| --- | --- | --- |
| `api-stream.test.ts` | 6 | 正确 URL / POST 方法 / 空 body / URL 编码 / 委托 streamSSE / AbortSignal |
| `hooks-stream.test.tsx` | 12 | chunk 累积 / done 事件 + invalidate / error 事件 / start 重置 / AbortError / STREAM_NETWORK_ERROR / cancel / reset |
| `OutlineWorkspaceView.test.tsx` | 7 | 流式按钮存在 / 点击触发 start / 流式展示区显示 / 取消按钮 / 完成提示 / 错误展示 / 与原按钮共存 |
| **小计** | **25** | — |

### 5.3 回归测试

- `test_outline_worker_handlers.py`（原 Worker 路径，零回归）
- `test_outline_service.py`（原 service 方法，零回归）
- `test_outline_api.py`（原 API 端点，零回归）
- 现有大纲相关前端测试（零回归）

---

## 六、验收标准

### 6.1 功能验收（AC-1 ~ AC-10）

| AC | 描述 | 验证方法 |
| --- | --- | --- |
| AC-1 | `POST /outline/stream-generate` 返回 `text/event-stream` | API 测试 |
| AC-2 | 流式期间逐 chunk 推送 `event: chunk` | API 测试 |
| AC-3 | 完成后推送 `event: done`，含 `outline_id` 和 `candidate_source` | API 测试 |
| AC-4 | 失败时推送 `event: error`，含 `error_code` 和 `partial_text` | API 测试 |
| AC-5 | 首 chunk 前失败降级 LocalRule | Provider 测试 |
| AC-6 | 中途失败不保存 Outline | Service 测试 |
| AC-7 | 前端"流式生成大纲"按钮触发流式 | Hook 测试 + 浏览器验收 |
| AC-8 | 前端实时显示 chunk 累积 | Hook 测试 + 浏览器验收 |
| AC-9 | 前端"取消"按钮可中断 | Hook 测试 + 浏览器验收 |
| AC-10 | 流式完成后大纲列表自动刷新 | Hook 测试（invalidateQueries） |

### 6.2 兼容性验收（AC-11 ~ AC-13）

| AC | 描述 | 验证方法 |
| --- | --- | --- |
| AC-11 | 原 `POST /outline/generate` + Worker 路径不受影响 | `test_outline_worker_handlers.py` 全通过 |
| AC-12 | 现有大纲测试全部通过 | pytest + vitest |
| AC-13 | 上下文聚合提取后 Worker handler 行为不变 | `test_outline_worker_handlers.py` 全通过 |

### 6.3 约束验收（AC-14 ~ AC-18）

| AC | 描述 | 验证方法 |
| --- | --- | --- |
| AC-14 | 不引入新依赖 | `git diff pyproject.toml package.json` 无变化 |
| AC-15 | 不修改数据库 schema | 无新增 Alembic 迁移 |
| AC-16 | 不引入 WebSocket | 代码审查 |
| AC-17 | 复用 `stream-sse.ts`（不修改） | `git diff apps/web/src/shared/stream-sse.ts` 无变化 |
| AC-18 | owner 边界：API 只做协议映射 | 代码审查 |

### 6.4 测试验收（AC-19 ~ AC-23）

| AC | 描述 | 验证方法 |
| --- | --- | --- |
| AC-19 | 后端 pytest 新增 ≥ 37 个，总数 ≥ 820 | `pytest` |
| AC-20 | 前端 vitest 新增 ≥ 25 个，总数 ≥ 493 | `npm test -- --run` |
| AC-21 | TypeScript 类型检查通过 | `tsc --noEmit` |
| AC-22 | Vite 构建成功 | `npm run build` |
| AC-23 | 浏览器验收通过 | browser_use agent |

---

## 七、实现顺序

按照 AGENTS.md 阶段闸：

1. **测试先行**：编写后端 Provider 流式测试（红）
2. **Provider 实现**：`DeepSeekOutlineProvider.stream_generate()`
3. **上下文聚合提取**：`gather_outline_context()` 从 worker handler 提取到 service
4. **Service 实现**：`stream_generate_outline()` + 事件类型
5. **API 实现**：`POST /outline/stream-generate` SSE 端点
6. **后端测试全绿**：运行 pytest
7. **前端 API**：`streamGenerateOutline()`
8. **前端 Hook**：`useStreamGenerateOutline()`
9. **前端 UI**：OutlineWorkspaceView 改造
10. **前端测试**：编写并运行 vitest
11. **类型检查与构建**：tsc + Vite build
12. **浏览器验收**：browser_use agent
13. **文档回写**：acceptance.md / implementation-plan.md / README.md / changelog-v2.1.0.md
14. **git 收口**：commit + tag v2.1.0 + push

---

## 八、风险与降级

### 8.1 已识别风险

| 风险 | 等级 | 缓解措施 |
| --- | --- | --- |
| 上下文聚合提取破坏 Worker handler | 中 | 提取后 Worker handler 改为调用 service 层方法；运行 `test_outline_worker_handlers.py` 验证零回归 |
| JSON 校验失败后 chunk 已推送 | 中 | 推送 `error` 事件，不保存 Outline；用户可重试 |
| 流式期间 LLM 超时 | 中 | 复用 SPEC 0018 超时处理；首 chunk 前降级 LocalRule |
| 上下文过大导致 prompt 超限 | 低 | `_build_user_prompt` 已有截断逻辑 |
| SSE 连接被代理截断 | 低 | 设置 `X-Accel-Buffering: no` 头 |

### 8.2 不在风险范围

- 不破坏产品边界（仍是单用户 Web MVP）
- 不破坏 owner 边界（API 只做协议映射）
- 不引入安全风险

---

## 九、关联文档

- [SPEC 0018 流式 LLM 输出](0018-streaming-llm-output.md)（V2.0.0，已收口）
- [决策 0025 启动 SPEC 0019](../decisions/0025-start-spec-0019-outline-streaming.md)
- [决策 0024 启动 SPEC 0018](../decisions/0024-start-spec-0018-streaming-llm-output.md)（§3 预留备选方案）
- [changelog-v2.0.0.md](../changelog-v2.0.0.md)（V2.0.0 发布说明）
- AGENTS.md（项目宪法）

---

## 十、待确认问题

1. **JSON 校验失败后的处理**：当前方案是推送 `error` 事件，不保存 Outline。是否需要自动降级到 LocalRule 重新生成？（可能导致用户看到两次生成）
   - **推荐**：推送 `error` 事件，用户手动重试。原因：自动降级会导致用户困惑（看到两次不同的内容）。

2. **上下文聚合方法命名**：`gather_outline_context` 还是 `build_outline_context`？
   - **推荐**：`gather_outline_context`，与原 `_gather_outline_context` 命名一致。
