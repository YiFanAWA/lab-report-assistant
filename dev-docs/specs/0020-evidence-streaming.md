# SPEC 0020：证据卡片生成流式化

**版本：** 1.0
**日期：** 2026-07-26
**状态：** 已完成实现与验收，待项目负责人确认收口
**目标版本：** v2.2.0
**前置版本：** v2.1.0（SPEC 0019 大纲生成流式化）
**关联决策：** [决策 0026](../decisions/0026-start-spec-0020-evidence-streaming.md)

> **实现收口说明（2026-07-26）：** 本切片已完成实现与验收。后端 858 passed 新增 37 测试 + 前端 519 passed 新增 26 测试；tsc 通过；Vite 构建通过；Alembic 无变化；不引入新依赖；stream-sse.ts 零修改；浏览器验收 PASS（6 步全通过，截图保存至 `dev-docs/e2e-screenshots/e2e-spec0020-*.png`）。详见 [changelog-v2.2.0.md](../changelog-v2.2.0.md) 和 [e2e-acceptance-report-spec0020.md](../e2e-acceptance-report-spec0020.md)。

---

## 一、背景与目标

### 1.1 痛点

证据卡片生成是实验报告工作流中**第三个高等待**的 LLM 调用（5-15s）。当前实现（V2.1.0）通过 Worker 异步执行：

1. 前端调用 `POST /api/projects/{project_id}/sources/{source_id}/evidence/generate` → 创建 `JobType.GENERATE_EVIDENCE` 任务 → 返回 `job_id`
2. 前端 `useJob` 轮询 job 状态（默认 2s 间隔）
3. Worker 进程领取 Job → 从 `ParsedDocument` 取 `parsed_text` → 调用 `provider.draft(parsed_text)` 批量生成多张卡片 → `save_evidence_card_drafts()` 保存为 CANDIDATE
4. Job 完成后，前端轮询发现状态变化 → 刷新证据卡片列表

用户痛点：
- 5-15s 空白等待，无进度反馈
- 无法看到 LLM 提取证据卡片的过程
- 无法中途取消
- 多来源场景下逐个触发，每次都要等待
- Worker 异步与 SSE 同步推送语义不兼容（与 SPEC 0019 相同问题）

### 1.2 目标

将证据卡片生成改造为 SSE 流式输出，复用 SPEC 0018/0019 的流式架构：
- 新增 `POST /api/projects/{project_id}/sources/{source_id}/evidence/stream-generate` SSE 端点（绕过 Worker）
- 后端流式调用 LLM，逐 chunk 推送
- 前端实时显示生成内容，支持取消
- 保留原 `POST /evidence/generate`（Worker 异步）兼容

### 1.3 与 SPEC 0018/0019 的关系

SPEC 0020 是流式能力的**第三次复用**，架构已完全成熟：

| 维度 | SPEC 0018（任务单） | SPEC 0019（大纲） | SPEC 0020（证据卡片） |
| --- | --- | --- | --- |
| 流式架构 | SSE + Gateway 直调 | SSE + Gateway 直调（复用） | SSE + Gateway 直调（复用） |
| 端点 | `POST /plans/stream-generate` | `POST /outline/stream-generate` | `POST /evidence/stream-generate` |
| Provider | `DeepSeekRequirementDraftProvider` | `DeepSeekOutlineProvider` | `DeepSeekEvidenceCardProvider` |
| Provider 输入 | 单一 requirement_text | 跨模块聚合（5 模块） | **单文档 parsed_text（最简单）** |
| 产出 | 单个任务单 JSON | 单个大纲 JSON（6 章节） | **批量卡片（多张 list）** |
| 原同步路径 | `POST /plans/generate`（保留） | `POST /outline/generate`（Worker，保留） | `POST /evidence/generate`（Worker，保留） |
| 前端工具 | `stream-sse.ts`（新建） | `stream-sse.ts`（复用） | `stream-sse.ts`（复用） |
| 降级策略 | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule | 首 chunk 前降级 LocalRule（复用） |

**关键差异**：证据卡片的产出是**批量卡片列表**（不是单个 JSON 对象），但 LLM 仍返回单个 JSON `{"cards": [...]}`，所以流式 chunk 累积后仍是单个 JSON，与 SPEC 0019 处理方式一致。区别仅在 done 事件返回 `card_count` 而非 `outline_id`。

---

## 二、范围与边界

### 2.1 在范围内

1. 后端 `DeepSeekEvidenceCardProvider.stream_draft()` 流式方法
2. 后端 `sources_service.stream_generate_evidence_cards()` 流式 service 方法（含分段 db session）
3. 后端 `POST /api/projects/{project_id}/sources/{source_id}/evidence/stream-generate` SSE 端点
4. 前端 `streamGenerateEvidence()` API 函数
5. 前端 `useStreamGenerateEvidence()` hook
6. 前端证据卡片生成 UI 改造（流式按钮 + 展示区 + 取消）
7. 后端单元测试（Provider + Service + API）
8. 前端单元测试（API + Hook + UI）
9. 浏览器验收

### 2.2 不在范围内

1. 不改造原 Worker 异步端点（`POST /evidence/generate` 保留不变）
2. 不流式化分析方案、代码任务生成（后续 SPEC 候选）
3. 不引入 WebSocket / 长轮询
4. 不修改数据库 schema
5. 不引入新依赖
6. 不修改 `stream-sse.ts`（复用 SPEC 0018）
7. 不修改 `DeepSeekClient.stream_chat_completion()`（复用 SPEC 0018）
8. 不修改 `handle_generate_evidence` Worker handler（保留兼容）
9. 不实现"多来源批量流式生成"（每个来源仍独立触发流式；批量场景留待后续）

---

## 三、架构设计

### 3.1 整体架构

```text
前端 useStreamGenerateEvidence
    │
    ▼ fetch + ReadableStream
POST /sources/{source_id}/evidence/stream-generate (SSE)
    │
    ▼ StreamingResponse
sources_service.stream_generate_evidence_cards()
    │
    ├──▶ Phase 1: 校验（持有 db）
    │       └──▶ _ensure_project + _ensure_project_ready_for_sources
    │       └──▶ 取 ParsedDocument.parsed_text
    │       └──▶ db.close()
    │
    ├──▶ Phase 2: 流式生成（不持有 db）
    │       └──▶ DeepSeekEvidenceCardProvider.stream_draft(parsed_text)
    │               └──▶ DeepSeekClient.stream_chat_completion()
    │                       └──▶ httpx.Client.stream() → SSE 行
    │
    └──▶ Phase 3: 保存（重新打开 db）
            └──▶ save_evidence_card_drafts()
```

### 3.2 SSE 事件合同（复用 SPEC 0018/0019 格式）

```text
event: chunk
data: {"text": "{\"cards\":["}

event: chunk
data: {"text": "{\"summary\":\"研究背景...\",\"evidence_type\":\"BACKGROUND\"}"}

event: chunk
data: {"text": "]}"}

event: done
data: {"card_count": 3, "candidate_source": "DEEPSEEK", "fallback_used": false}

event: error
data: {"error_code": "DEEPSEEK_TIMEOUT", "message": "流式请求超时", "partial_text": "{\"cards\":[..."}
```

**done 事件字段说明**：
- `card_count`：保存的卡片数量（替代 SPEC 0019 的 `outline_id`，因为证据卡片是批量产出）
- `candidate_source`：DEEPSEEK / LOCAL_RULE
- `fallback_used`：是否使用了降级路径

### 3.3 降级策略（复用 SPEC 0018/0019 模式）

| 失败时机 | 降级行为 | 用户可见 | 是否保存 | 是否写缓存 |
| --- | --- | --- | --- | --- |
| 首 chunk 前 | 降级到 LocalRule，拆分多 chunk 模拟流式 | 是 | 是（LocalRule 结果保存） | 是 |
| 中途失败 | 保留已生成 chunk + 推送 error 事件 | 是（部分内容 + 错误提示） | 否 | 否 |
| JSON 校验失败 | 推送 error 事件 + partial_text | 是（错误提示 + 已生成 JSON） | 否 | 否 |
| 网络异常 | 前端映射 `STREAM_NETWORK_ERROR` | 是（错误提示 + partial_text） | 否 | 否 |
| 用户取消 | AbortController.abort() | 是（流式停止） | 否 | 否 |

### 3.4 分段 db session（复用 SPEC 0018/0019 模式）

- **Phase 1**：校验项目状态 + 取 ParsedDocument（持有 db）→ 完成后 `db.close()`
- **Phase 2**：流式生成（不持有 db，避免 SQLite 写锁阻塞）
- **Phase 3**：完成后重新打开 db → `save_evidence_card_drafts()` → `db2.close()`

### 3.5 与大纲流式（SPEC 0019）的关键差异

1. **无需提取上下文聚合**：大纲需要从 5 个模块聚合上下文（`gather_outline_context`），证据卡片只需取 `ParsedDocument.parsed_text`，Worker handler 已极简，无需提取共享方法
2. **批量产出**：一次生成多张卡片，但 LLM 仍返回单个 JSON `{"cards": [...]}`，流式处理与 SPEC 0019 一致
3. **done 事件返回 card_count**：而非 `outline_id`，因为卡片是批量产出无单一 ID
4. **按来源触发**：每个来源独立触发流式，不跨来源聚合

---

## 四、实现细节

### 4.1 `DeepSeekEvidenceCardProvider.stream_draft()` 实现

**文件：** `server/app/modules/llm/deepseek_evidence_provider.py`
**新增方法：**

```python
from typing import Generator

def stream_draft(
    self, text: str
) -> Generator[str, None, None]:
    """流式调用 DeepSeek 提取证据卡片，逐 chunk yield content。

    首 chunk 前失败降级到 LocalRule，拆分多 chunk 模拟流式。
    中途失败抛异常，由调用方处理。
    """
    chunks: list[str] = []
    started = False
    try:
        for chunk in self._client.stream_chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(text)},
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
            logger.warning(f"DeepSeek 流式证据卡片失败，降级到 LocalRule: {e}")
            fallback_drafts = self._fallback.draft(text)
            # 序列化为 JSON（EvidenceCardDraft 是 dataclass，不是 Pydantic 模型）
            full_json = json.dumps({
                "cards": [
                    {
                        "summary": d.summary,
                        "evidence_type": d.evidence_type,
                        "locator": d.locator,
                        "source_quote": d.source_quote,
                    }
                    for d in fallback_drafts
                ]
            }, ensure_ascii=False)
            # 拆分为多个 chunk 模拟流式
            for i in range(0, len(full_json), 50):
                piece = full_json[i:i + 50]
                chunks.append(piece)
                yield piece
            return
        # 中途失败不降级，抛异常让调用方处理
        raise
```

**注意**：与 SPEC 0019 相同，`EvidenceCardDraft` 是 dataclass，需要手动序列化为 JSON（不能用 `model_dump_json()`）。

### 4.2 `sources_service.stream_generate_evidence_cards()` 实现

**文件：** `server/app/modules/sources/service.py`
**新增方法和事件类型：**

```python
from dataclasses import dataclass
from typing import Generator

@dataclass
class StreamEvidenceChunkEvent:
    text: str

@dataclass
class StreamEvidenceDoneEvent:
    card_count: int
    candidate_source: str
    fallback_used: bool

@dataclass
class StreamEvidenceErrorEvent:
    error_code: str
    message: str
    partial_text: str

StreamEvidenceEvent = (
    StreamEvidenceChunkEvent
    | StreamEvidenceDoneEvent
    | StreamEvidenceErrorEvent
)


def stream_generate_evidence_cards(
    db: Session, project_id: str, source_id: str, provider
) -> Generator[StreamEvidenceEvent, None, None]:
    """流式生成证据卡片。

    Phase 1: 校验 + 取 ParsedDocument（持有 db）
    Phase 2: 流式生成（关闭 db）
    Phase 3: 保存（重新打开 db）
    """
    # Phase 1: 校验
    project = _ensure_project(db, project_id)
    _ensure_project_ready_for_sources(project)

    source = get_source_by_id_and_project(db, project_id, source_id)
    if source.status != SourceStatus.PARSED.value:
        raise AppError(
            code="EVIDENCE_SOURCE_NOT_PARSED",
            message="来源未解析，无法生成证据卡片",
            field="source_id",
        )

    pd = (
        db.query(ParsedDocument)
        .filter(ParsedDocument.source_id == source_id)
        .first()
    )
    if not pd:
        raise AppError(
            code="EVIDENCE_SOURCE_NOT_PARSED",
            message="来源未解析，无法生成证据卡片",
            field="source_id",
        )

    parsed_text = pd.parsed_text
    pd_id = pd.id
    db.close()  # 显式关闭，避免流式期间持有连接

    # Phase 2: 流式生成（不持有 db）
    chunks: list[str] = []
    fallback_used = False
    try:
        if hasattr(provider, "stream_draft"):
            for chunk in provider.stream_draft(parsed_text):
                chunks.append(chunk)
                yield StreamEvidenceChunkEvent(text=chunk)
        else:
            # 兼容只支持同步的 provider（LocalRule/Fake）
            drafts = provider.draft(parsed_text)
            full_json = json.dumps({
                "cards": [
                    {
                        "summary": d.summary,
                        "evidence_type": d.evidence_type,
                        "locator": d.locator,
                        "source_quote": d.source_quote,
                    }
                    for d in drafts
                ]
            }, ensure_ascii=False)
            for i in range(0, len(full_json), 50):
                piece = full_json[i:i + 50]
                chunks.append(piece)
                yield StreamEvidenceChunkEvent(text=piece)
    except Exception as e:
        partial_text = "".join(chunks)
        yield StreamEvidenceErrorEvent(
            error_code=getattr(e, "code", "EVIDENCE_STREAM_FAILED"),
            message=str(e) or e.__class__.__name__,
            partial_text=partial_text,
        )
        return

    # Phase 2.5: 校验完整 JSON
    raw = "".join(chunks)
    try:
        from app.modules.llm.deepseek_evidence_provider import (
            DeepSeekEvidenceResponse,
        )
        parsed = DeepSeekEvidenceResponse.model_validate_json(raw)
        drafts_data = [
            {
                "summary": c.summary,
                "evidence_type": c.evidence_type,
                "locator": c.locator,
                "source_quote": c.source_quote,
            }
            for c in parsed.cards
        ]
    except Exception as e:
        yield StreamEvidenceErrorEvent(
            error_code="EVIDENCE_JSON_PARSE_ERROR",
            message=f"证据卡片 JSON 校验失败: {e}",
            partial_text=raw,
        )
        return

    # Phase 3: 保存（重新打开 db）
    from app.infrastructure.database.engine import SessionLocal
    from app.modules.llm.evidence_card_provider import EvidenceCardDraft
    db2 = SessionLocal()
    try:
        drafts = [
            EvidenceCardDraft(
                summary=d["summary"],
                evidence_type=d["evidence_type"],
                locator=d["locator"],
                source_quote=d["source_quote"],
            )
            for d in drafts_data
        ]
        cards = save_evidence_card_drafts(
            db2,
            project_id=project_id,
            source_id=source_id,
            parsed_document_id=pd_id,
            drafts=drafts,
            candidate_source=provider.source_label(),
        )
        _add_change(db2, project_id,
                    SourceChangeType.EVIDENCE_CARD_GENERATED.value,
                    f"流式生成证据卡片候选 {len(cards)} 张")
        db2.commit()

        yield StreamEvidenceDoneEvent(
            card_count=len(cards),
            candidate_source=provider.source_label(),
            fallback_used=fallback_used,
        )
    except Exception as e:
        yield StreamEvidenceErrorEvent(
            error_code="EVIDENCE_SAVE_FAILED",
            message=f"证据卡片保存失败: {e}",
            partial_text=raw,
        )
    finally:
        db2.close()
```

### 4.3 API 端点实现

**文件：** `server/app/api/routers/evidence.py`
**新增端点：**

```python
from fastapi.responses import StreamingResponse
import json
from app.modules.llm.gateway import get_evidence_card_provider
from app.modules.sources import service as sources_service


def _serialize_evidence_sse_event(event) -> str:
    """将流式事件序列化为 SSE 文本。"""
    if isinstance(event, sources_service.StreamEvidenceChunkEvent):
        data = json.dumps({"text": event.text}, ensure_ascii=False)
        return f"event: chunk\ndata: {data}\n\n"
    elif isinstance(event, sources_service.StreamEvidenceDoneEvent):
        data = json.dumps({
            "card_count": event.card_count,
            "candidate_source": event.candidate_source,
            "fallback_used": event.fallback_used,
        }, ensure_ascii=False)
        return f"event: done\ndata: {data}\n\n"
    elif isinstance(event, sources_service.StreamEvidenceErrorEvent):
        data = json.dumps({
            "error_code": event.error_code,
            "message": event.message,
            "partial_text": event.partial_text,
        }, ensure_ascii=False)
        return f"event: error\ndata: {data}\n\n"
    return ""


@router.post("/sources/{source_id}/evidence/stream-generate")
def stream_generate_evidence_cards_endpoint(project_id: str, source_id: str):
    """SSE 流式生成证据卡片（SPEC 0020）。

    绕过 Worker，直接调用 LLM provider 流式生成。
    保留原 POST /sources/{source_id}/evidence/generate（Worker 异步）兼容。
    """
    provider = get_evidence_card_provider()

    # 预校验：项目和来源存在（确保 404 而非 SSE 错误流）
    db = SessionLocal()
    try:
        from app.modules.projects import service as project_service
        project_service.get_project(db, project_id)
        sources_service.get_source_by_id_and_project(db, project_id, source_id)
    finally:
        db.close()

    def event_stream():
        db = SessionLocal()
        try:
            for event in sources_service.stream_generate_evidence_cards(
                db, project_id, source_id, provider
            ):
                yield _serialize_evidence_sse_event(event)
        except AppError as e:
            yield _serialize_evidence_sse_event(
                sources_service.StreamEvidenceErrorEvent(
                    error_code=e.code,
                    message=e.message,
                    partial_text="",
                )
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

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

### 4.4 前端 API 实现

**文件：** `apps/web/src/features/evidence/api.ts`
**新增函数：**

```typescript
import { streamSSE, type SSEEvent } from "../../shared/stream-sse";

/**
 * 流式生成证据卡片（SPEC 0020）。
 *
 * 返回异步迭代器，逐个 yield SSE 事件。
 * 复用 SPEC 0018 的 streamSSE 工具。
 */
export async function* streamGenerateEvidence(
  projectId: string,
  sourceId: string,
  signal?: AbortSignal
): AsyncGenerator<SSEEvent, void, unknown> {
  const url = `${BASE}/projects/${encodeURIComponent(projectId)}/sources/${encodeURIComponent(sourceId)}/evidence/stream-generate`;
  yield* streamSSE(url, {}, signal);
}
```

### 4.5 前端 Hook 实现

**文件：** `apps/web/src/features/evidence/hooks.ts`
**新增 hook：**

```typescript
export interface StreamEvidenceState {
  /** 是否正在流式生成 */
  streaming: boolean;
  /** 已生成的完整文本（chunk 累积） */
  chunks: string;
  /** 完成事件返回的结果 */
  result: {
    card_count: number;
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

const INITIAL_STREAM_EVIDENCE_STATE: StreamEvidenceState = {
  streaming: false,
  chunks: "",
  result: null,
  error: null,
};

/**
 * 流式生成证据卡片 hook（SPEC 0020）。
 *
 * 管理 SSE 连接的生命周期：
 * - start(): 建立连接，逐 chunk 累积文本
 * - cancel(): 中断连接（AbortController.abort()）
 * - reset(): 重置状态
 *
 * 完成后自动 invalidate 证据卡片列表 query，触发 GET 刷新最终结果。
 */
export function useStreamGenerateEvidence(
  projectId: string,
  sourceId: string
) {
  const qc = useQueryClient();
  const [state, setState] = useState<StreamEvidenceState>(
    INITIAL_STREAM_EVIDENCE_STATE
  );
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(async () => {
    setState({ ...INITIAL_STREAM_EVIDENCE_STATE, streaming: true });
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const evt of streamGenerateEvidence(
        projectId,
        sourceId,
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
          // 刷新证据卡片列表 query，获取后端保存的最终结果
          qc.invalidateQueries({
            queryKey: [...evidenceKey(projectId), "list"],
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
  }, [projectId, sourceId, qc]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    setState(INITIAL_STREAM_EVIDENCE_STATE);
  }, []);

  return { ...state, start, cancel, reset };
}
```

### 4.6 前端 UI 改造

**文件：** `apps/web/src/routes/EvidenceWorkspaceView.tsx`
**改造点：**

1. 在 `GenerateEvidenceRow` 组件中新增"流式生成"按钮（与原"生成候选"按钮并列）
2. 流式按钮点击后调用 `useStreamGenerateEvidence(pid, source.id).start()`
3. 流式期间显示 chunk 累积展示区（带边框灰色背景 + `<pre>` 标签）
4. 流式期间显示"取消"按钮
5. 完成后显示"流式生成完成 ✓ [源]（降级）"提示（与 SPEC 0019 一致）
6. 错误时显示错误信息 + "查看已生成内容"详情折叠（含 partial_text）

**UI 状态参考 SPEC 0019：**
- 流式按钮：紫色 #6366f1
- 流式展示区：带边框灰色背景 #f3f4f6
- 取消按钮：红色 #dc2626
- 完成提示：绿色 #16a34a
- 错误提示：红色 #dc2626

---

## 五、数据库变更

**无数据库变更。**

- 不新增表、字段、索引
- 不新增 Alembic 迁移
- 流式 chunk 不持久化（仅通过 SSE 推送）
- 最终保存仍复用 `save_evidence_card_drafts()`，与 Worker 路径完全一致

---

## 六、测试策略

### 6.1 后端单元测试

**新增测试文件：**

1. `server/tests/test_deepseek_evidence_provider_stream.py`
   - 流式成功：多 chunk 按序 yield
   - 单 chunk 也能流式
   - source_label 返回 DEEPSEEK
   - 首 chunk 前失败降级 LocalRule
   - 首 chunk 前超时也降级
   - 降级后内容包含多张卡片 JSON
   - 中途失败抛异常且已 yield 保留
   - 中途失败不降级
   - JSON 校验失败抛异常
   - 有效 JSON 不抛异常
   - 空 chunk 列表不抛异常
   - 缓存命中一次性 yield
   - 空 text 也能调用

2. `server/tests/test_evidence_service_stream.py`
   - 流式成功 yield chunks + done
   - 流式成功后保存 EvidenceCard（CANDIDATE 状态）
   - 流式成功后写变更记录
   - 中途失败 yield ErrorEvent
   - 中途失败不保存 EvidenceCard
   - JSON 校验失败 yield ErrorEvent
   - JSON 校验失败不保存 EvidenceCard
   - 同步 provider 一次性 yield
   - 同步 provider 保存 EvidenceCard
   - 项目不存在抛 AppError
   - 项目状态不满足抛 AppError
   - 来源不存在抛 AppError
   - 来源未解析抛 AppError（EVIDENCE_SOURCE_NOT_PARSED）
   - ParsedDocument 不存在抛 AppError

3. `server/tests/test_evidence_stream_api.py`
   - 返回 text/event-stream content-type
   - 完整流程：多 chunk + done 事件
   - chunk 拼接为有效 JSON
   - done 事件包含 card_count 字段
   - 项目不存在返回 404
   - 来源不存在返回 404
   - 来源未解析返回 error 事件
   - 项目状态未满足返回 error 事件
   - 原同步端点零回归（POST /evidence/generate 仍返回 job_id）

### 6.2 前端单元测试

**新增测试文件：**

1. `apps/web/src/features/evidence/__tests__/api-stream.test.ts`
   - 正确 URL + POST 方法
   - 请求体为空对象（无 source_id 在 body）
   - 项目 ID 和来源 ID 都 URL 编码
   - 委托 streamSSE 解析
   - 传递 AbortSignal
   - HTTP 错误透传

2. `apps/web/src/features/evidence/__tests__/hooks-stream.test.tsx`
   - chunk 累积
   - done 设置 result 并清空 chunks
   - done 触发 invalidate evidence list query
   - start 重置旧状态
   - done 包含 fallback_used 标记
   - 流式期间 streaming 为 true
   - error 事件保留 partial_text
   - 非 AbortError 映射 STREAM_NETWORK_ERROR
   - AbortError 不设 error
   - cancel 通过 AbortSignal 中断
   - reset 重置
   - 初始状态正确

3. `apps/web/src/routes/__tests__/EvidenceWorkspaceView.test.tsx`（扩展）
   - 流式按钮与原按钮共存
   - 点击触发 start
   - 流式期间显示 chunk 累积展示区
   - 取消按钮触发 cancel
   - 完成提示显示 candidate_source
   - 错误展示含 partial_text 详情
   - 无 partial_text 时不显示详情

### 6.3 回归测试

- 原 Worker 路径 `POST /evidence/generate` + `handle_generate_evidence` 不受影响
- `test_evidence_service.py` 全部通过
- `test_evidence_api.py` 全部通过
- `test_worker_handlers.py::TestHandleGenerateEvidence` 全部通过

### 6.4 浏览器验收

- 启动后端 + 前端 dev server
- 创建已确认项目 + PARSED 来源
- 进入证据卡片工作区
- 确认"生成候选"和"流式生成"两个按钮并列存在
- 点击"流式生成"
- 后端日志确认 `POST /evidence/stream-generate` 返回 200 OK
- 后端 API 验证证据卡片已保存（CANDIDATE 状态）
- 前端证据卡片列表自动刷新显示新 CANDIDATE 卡片
- 截图归档：按 TD-009 现状处理（可选）

---

## 七、验收标准

### 7.1 功能验收

| AC # | 验收项 | 验证方式 |
| --- | --- | --- |
| AC-1 | `DeepSeekEvidenceCardProvider.stream_draft()` 流式方法存在且按序 yield chunk | 单元测试 |
| AC-2 | 首 chunk 前失败降级 LocalRule，拆分多 chunk 模拟流式 | 单元测试 |
| AC-3 | 中途失败抛异常，已 yield chunk 保留 | 单元测试 |
| AC-4 | `source_label()` 返回 DEEPSEEK | 单元测试 |
| AC-5 | `sources_service.stream_generate_evidence_cards()` 流式方法存在 | 单元测试 |
| AC-6 | 流式成功 yield 多个 chunk + done 事件 | 单元测试 |
| AC-7 | 流式成功后保存 EvidenceCard（CANDIDATE 状态） | 单元测试 |
| AC-8 | 流式成功后写变更记录（EVIDENCE_CARD_GENERATED） | 单元测试 |
| AC-9 | 中途失败 yield ErrorEvent，不保存 EvidenceCard | 单元测试 |
| AC-10 | JSON 校验失败 yield ErrorEvent，不保存 EvidenceCard | 单元测试 |
| AC-11 | 同步 provider（LocalRule/Fake）兼容路径正常工作 | 单元测试 |
| AC-12 | 项目不存在抛 AppError | 单元测试 |
| AC-13 | 来源不存在抛 AppError | 单元测试 |
| AC-14 | 来源未解析抛 AppError（EVIDENCE_SOURCE_NOT_PARSED） | 单元测试 |
| AC-15 | `POST /evidence/stream-generate` 返回 text/event-stream | API 测试 |
| AC-16 | SSE 事件格式正确（chunk/done/error） | API 测试 |
| AC-17 | done 事件包含 card_count 字段 | API 测试 |
| AC-18 | 项目不存在返回 404（非 SSE 错误流） | API 测试 |
| AC-19 | 来源不存在返回 404 | API 测试 |
| AC-20 | 原同步端点 `POST /evidence/generate` 零回归 | API 测试 |
| AC-21 | Worker handler `handle_generate_evidence` 零回归 | 单元测试 |

### 7.2 前端验收

| AC # | 验收项 | 验证方式 |
| --- | --- | --- |
| AC-22 | `streamGenerateEvidence()` API 函数正确调用 SSE 端点 | 单元测试 |
| AC-23 | `useStreamGenerateEvidence()` hook 管理 streaming/chunks/result/error 状态 | 单元测试 |
| AC-24 | done 事件触发 invalidate evidence list query | 单元测试 |
| AC-25 | cancel 通过 AbortSignal 中断 | 单元测试 |
| AC-26 | 非 AbortError 映射 STREAM_NETWORK_ERROR | 单元测试 |
| AC-27 | UI 显示流式按钮 + chunk 累积展示区 + 取消按钮 | 单元测试 |
| AC-28 | 完成提示显示 candidate_source 和 fallback_used | 单元测试 |
| AC-29 | 错误展示含 partial_text 详情折叠 | 单元测试 |

### 7.3 质量验收

| AC # | 验收项 | 验证方式 |
| --- | --- | --- |
| AC-30 | 后端测试全部通过（预期 ~860 passed，新增 ~39 测试） | pytest |
| AC-31 | 前端测试全部通过（预期 ~525 passed，新增 ~32 测试） | vitest |
| AC-32 | TypeScript 类型检查通过（tsc --noEmit） | npm run lint |
| AC-33 | Vite 构建通过 | npm run build |
| AC-34 | Alembic 无变化（不修改数据库 schema） | git diff server/alembic/ |
| AC-35 | 不引入新依赖（pyproject.toml / package.json 无变化） | git diff |
| AC-36 | 复用 stream-sse.ts（零修改） | git diff apps/web/src/shared/stream-sse.ts |
| AC-37 | 不引入 WebSocket 或长轮询 | 代码审查 |
| AC-38 | owner 边界：API 仅做 SSE 协议映射，业务真相在 service 层 | 代码审查 |

### 7.4 文档与版本验收

| AC # | 验收项 | 验证方式 |
| --- | --- | --- |
| AC-39 | 浏览器验收 PASS（200 OK + 卡片持久化 + 列表自动刷新） | browser_use agent |
| AC-40 | 文档回写：README.md / acceptance.md / implementation-plan.md / 决策 0026 / changelog-v2.2.0.md | git diff |
| AC-41 | 版本收口：commit 中文 + tag v2.2.0 + push origin master --tags | git log |

---

## 八、风险与缓解

| 风险 | 级别 | 缓解措施 |
| --- | --- | --- |
| SSE 流式期间 SQLite 写锁阻塞 | 中 | 分段持有 db session（Phase 1/3 持有，Phase 2 关闭） |
| LLM 返回 JSON 不完整导致校验失败 | 中 | 推送 error 事件 + partial_text，不保存卡片，用户可重试 |
| LocalRule 降级路径过快，UI 状态不可见 | 低 | 已在 SPEC 0019 验证为工具限制非代码缺陷，后端 200 OK + 持久化为关键证据 |
| 多来源场景下逐个触发流式体验差 | 低 | 本切片不解决，留待后续 SPEC（可考虑批量流式） |
| 截图未持久化（TD-009 延续） | 低 | 按 TD-009 评估结论处理（建议方案 A：文档化） |

---

## 九、不在范围内的事项

1. **多来源批量流式生成**：当前每个来源独立触发流式，不跨来源聚合。后续可考虑"一键流式生成所有未生成来源"功能。
2. **流式期间进度百分比**：本切片只展示 chunk 累积文本，不计算"已生成 X 张卡片"的实时统计（因 LLM 返回是单个 JSON，无法在解析前知道卡片数）。
3. **流式重试机制**：失败后用户需手动点击重试，不自动重试。
4. **TD-009 修复**：本切片不修复 TD-009，按 TD-009 评估结论单独处理。

---

## 十、后续方向

SPEC 0020 完成后，V2.2 后续 SPEC 待项目负责人规划。可能候选方向：

- **V2.3 SPEC 0022**：分析方案流式化（同步直连 LLM，复用 SPEC 0018 模式）
- **V2.3 SPEC 0023**：代码任务流式化（同步直连 LLM，复用 SPEC 0018 模式）
- **TD-009 修复**：按评估结论处理（建议方案 A 文档化，或方案 B 引入 Playwright）
- **多来源批量流式**：扩展 SPEC 0020 支持跨来源批量流式生成

上述方向均需先编写并确认对应 SPEC，不得直接进入实现。

---

## 附录 A：与 SPEC 0019 的对照表

| 维度 | SPEC 0019（大纲） | SPEC 0020（证据卡片） | 差异说明 |
| --- | --- | --- | --- |
| Provider 方法 | `stream_generate(context)` | `stream_draft(text)` | 输入不同（上下文 vs 纯文本） |
| 上下文聚合 | `gather_outline_context()` 从 5 模块提取 | 无（直接取 `ParsedDocument.parsed_text`） | 证据卡片更简单 |
| 产出 | 单个 Outline（6 章节） | 批量 EvidenceCard（多张） | done 事件返回 card_count 而非 outline_id |
| Worker handler 改造 | 提取 `gather_outline_context` 共享 | 不改造（Worker handler 已极简） | 无共享方法需提取 |
| SSE 端点路径 | `/outline/stream-generate` | `/sources/{source_id}/evidence/stream-generate` | 路径参数不同 |
| 触发方式 | 项目级（一个项目一个大纲） | 来源级（每个来源独立触发） | 证据卡片粒度更细 |

---

**草案结束。待项目负责人批准后，创建决策 0026 并进入实现阶段。**
