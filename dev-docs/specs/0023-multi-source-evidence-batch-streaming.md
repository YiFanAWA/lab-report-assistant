# SPEC 0023：多来源批量证据卡片流式生成

**版本：** 0.2（草案）
**日期：** 2026-07-26（初稿）/ 2026-07-28（草案 0.2 同步 V2.4.0 发布状态与 SPEC 0022 评审反馈）
**状态：** 草案，待项目负责人批准
**目标版本：** v2.5.0（V2.4.0 SPEC 0022 已独立收口为 v2.4.0，本切片为独立新切片）
**前置版本：** v2.4.0（SPEC 0022 代码任务生成流式化，已完成并打 tag v2.4.0，commit `c4b5fdf`）
**关联决策：** 待创建（决策 0029）

---

## 草案 0.2 更新说明（2026-07-28）

V2.4.0 发布后，对草案 0.1 进行以下同步更新：

1. **版本号同步**：目标版本从 `v2.3.0` 更新为 `v2.5.0`（v2.3.0/v2.4.0 已分别被 SPEC 0021/0022 占用）。
2. **前置版本同步**：前置版本从 `v2.2.0` 更新为 `v2.4.0`（最新已发布版本）。
3. **第八节重写**：原"与 V2.3.0 其他 SPEC 的关系"章节已过时（SPEC 0021/0022 均已完成），重写为"与已完成流式切片的关系"。
4. **纳入 SPEC 0022 评审反馈**（适用部分）：
   - **并发保护**：批量端点应引入 `active_streams` 字典保护同一项目的批量流式请求冲突
   - **服务端取消语义**：`Request.is_disconnected()` 检测客户端断开后立即停止后续来源处理
   - **错误分层**：流前错误（项目不存在）用 HTTP 404；流后错误（单个来源失败）用 `source_error` 事件
   - **可观测性**：每个来源记录 `source_index` / `first_chunk_latency_ms` / `fallback_used` / `cancel_reason` 等指标
5. **新增风险项**：批量请求总耗时可能较长（5 来源 × 5-15s = 25-75s），需考虑取消与进度展示设计。

---

## 一、背景与目标

### 1.1 痛点

SPEC 0020（V2.2.0）已实现单来源证据卡片流式生成，但在**多来源场景**下存在体验短板：

1. 用户需要**逐个点击**每个来源的"流式生成证据卡片"按钮
2. 无法看到**总体进度**（"已生成 2/5 个来源"）
3. 每个来源独立等待，无法**一次性批量处理**
4. 缺少**部分失败容错**（某个来源失败后无法继续处理剩余来源）

典型场景：用户登记了 5 个公开 URL 资料，每个都已解析完成，需要为每个来源生成证据卡片。当前需要点击 5 次，每次等待流式完成。

### 1.2 目标

新增**批量流式生成**端点，一次性为项目下所有已解析来源批量生成证据卡片：
- 新增 `POST /api/projects/{project_id}/evidence/stream-generate-all` SSE 端点
- 后端遍历所有已解析来源，**逐个流式生成**（不是并发）
- SSE 事件区分**来源边界**和**总体进度**
- 前端显示当前来源 + 总进度 + 每个来源的完成状态
- 部分失败容错：某个来源失败后继续处理剩余来源

### 1.3 与 SPEC 0020 的关系

SPEC 0023 是 SPEC 0020 的**扩展**，不是替代：
- 保留 SPEC 0020 的单来源端点 `POST /sources/{source_id}/evidence/stream-generate`
- 新增批量端点 `POST /projects/{project_id}/evidence/stream-generate-all`
- 批量端点内部**复用**单来源的 service 方法 `stream_generate_evidence_cards()`
- 前端可同时支持单来源和批量两种触发方式

---

## 二、范围与边界

### 2.1 在范围内

1. 后端 `sources_service.stream_generate_all_evidence_cards()` 批量流式 service 方法
2. 后端 `POST /api/projects/{project_id}/evidence/stream-generate-all` SSE 端点
3. 前端 `streamGenerateAllEvidence()` API 函数
4. 前端 `useStreamGenerateAllEvidence()` hook（含总体进度状态）
5. 前端证据工作区 UI 改造（新增"批量流式生成"按钮 + 进度展示）
6. 后端单元测试（Service + API）
7. 前端单元测试（API + Hook + UI）
8. 浏览器验收

### 2.2 不在范围内

1. 不修改 SPEC 0020 的单来源端点（保留兼容）
2. 不实现**并发**流式生成（串行逐个处理，避免 LLM 并发限流）
3. 不引入 WebSocket / 长轮询
4. 不修改数据库 schema
5. 不引入新依赖
6. 不修改 `stream-sse.ts`（复用 SPEC 0018）
7. 不修改 `DeepSeekEvidenceCardProvider.stream_draft()`（复用 SPEC 0020）
8. 不实现"批量生成大纲/分析方案/代码任务"（仅限证据卡片）

---

## 三、架构设计

### 3.1 整体架构

```text
前端 useStreamGenerateAllEvidence
    │
    ▼ fetch + ReadableStream
POST /projects/{project_id}/evidence/stream-generate-all (SSE)
    │
    ▼ StreamingResponse
sources_service.stream_generate_all_evidence_cards()
    │
    ├──▶ Phase 1: 查询所有已解析来源（持有 db）
    │       └──▶ SELECT sources WHERE project_id=? AND status=PARSED
    │       └──▶ db.close()
    │
    ├──▶ Phase 2: 逐个流式生成（不持有 db）
    │       └──▶ FOR each source:
    │              └──▶ yield source_start 事件（含 source_id, source_label, index, total）
    │              └──▶ FOR chunk in stream_generate_evidence_cards(source):
    │                     └──▶ yield chunk 事件（含 source_id 前缀）
    │              └──▶ yield source_done 事件（含 source_id, card_count）
    │              └──▶ ON ERROR: yield source_error 事件，继续下一个
    │
    └──▶ Phase 3: 全部完成
            └──▶ yield all_done 事件（含 total_sources, success_count, failure_count, total_cards）
```

### 3.2 SSE 事件合同（扩展 SPEC 0020 格式）

```text
event: source_start
data: {"source_id": "...", "source_label": "研究背景文献", "index": 1, "total": 5}

event: chunk
data: {"source_id": "...", "text": "{\"cards\":["}

event: chunk
data: {"source_id": "...", "text": "{\"summary\":\"...\"}"}

event: source_done
data: {"source_id": "...", "card_count": 3, "candidate_source": "DEEPSEEK"}

event: source_start
data: {"source_id": "...", "source_label": "数据集说明", "index": 2, "total": 5}

...

event: source_error
data: {"source_id": "...", "error_code": "DEEPSEEK_TIMEOUT", "message": "流式请求超时"}

event: all_done
data: {"total_sources": 5, "success_count": 4, "failure_count": 1, "total_cards": 12}
```

**新增事件类型**：
- `source_start`：开始处理某个来源（含 index/total 用于进度展示）
- `source_done`：某个来源完成（含 card_count）
- `source_error`：某个来源失败（不中断整体流程）
- `all_done`：全部完成（含汇总统计）
- `chunk`：扩展字段，新增 `source_id` 标识来源

### 3.3 串行处理策略

**为什么不并发？**
1. **DeepSeek API 限流**：并发多个 LLM 请求可能触发速率限制
2. **用户体验**：串行处理可以让用户清晰地看到每个来源的生成过程
3. **资源占用**：并发会同时占用多个 HTTP 连接和内存
4. **实现简单**：串行处理无需处理并发同步问题

### 3.4 部分失败容错

| 场景 | 处理方式 | 用户感知 |
| --- | --- | --- |
| 某个来源 LLM 失败 | 推送 `source_error` 事件，继续下一个 | 看到该来源失败提示，其余继续 |
| 某个来源 JSON 校验失败 | 推送 `source_error` 事件，继续下一个 | 看到该来源失败提示，其余继续 |
| 某个来源 LocalRule 降级 | 正常推送 `source_done`（fallback_used） | 看到降级标记 |
| 用户取消 | AbortController.abort()，停止后续来源 | 已完成的保留，未处理的不生成 |

### 3.5 前端进度展示设计

```text
┌─────────────────────────────────────────────┐
│ 批量流式生成证据卡片            [取消]       │
│                                             │
│ 总进度: 2/5 来源完成                        │
│ ████████░░░░░░░░░░░░░░░░░░░░░░             │
│                                             │
│ ✅ 来源 1: 研究背景文献 (3 张卡片)           │
│ ✅ 来源 2: 数据集说明 (2 张卡片, 降级)       │
│ ⏳ 来源 3: 实验方法 (正在生成...)            │
│    └─ {"cards":[{"summary":"...             │
│ ⏸ 来源 4: 待处理                           │
│ ⏸ 来源 5: 待处理                           │
│                                             │
│ 当前 chunk: {"summary":"实验采用...          │
└─────────────────────────────────────────────┘
```

---

## 四、关键设计点

### 4.1 service 层实现

```python
def stream_generate_all_evidence_cards(
    db: Session, project_id: str, provider
) -> Generator[StreamEvidenceBatchEvent, None, None]:
    """批量流式生成所有已解析来源的证据卡片。

    串行处理每个来源，复用 stream_generate_evidence_cards()。
    """
    # Phase 1: 查询所有已解析来源
    sources = get_sources_by_project(db, project_id, status=SourceStatus.PARSED)
    total = len(sources)
    if total == 0:
        yield StreamEvidenceAllDoneEvent(
            total_sources=0, success_count=0, failure_count=0, total_cards=0
        )
        return
    db.close()

    # Phase 2: 逐个流式生成
    success_count = 0
    failure_count = 0
    total_cards = 0

    for index, source in enumerate(sources, 1):
        yield StreamEvidenceSourceStartEvent(
            source_id=source.id,
            source_label=source.label,
            index=index,
            total=total,
        )

        # 重新打开 db 给 stream_generate_evidence_cards 使用
        db2 = SessionLocal()
        try:
            card_count = 0
            for event in stream_generate_evidence_cards(
                db2, project_id, source.id, provider
            ):
                if isinstance(event, StreamEvidenceChunkEvent):
                    # 在 chunk 事件中附加 source_id
                    yield StreamEvidenceChunkEvent(
                        text=event.text, source_id=source.id
                    )
                elif isinstance(event, StreamEvidenceDoneEvent):
                    card_count = event.card_count
                    yield StreamEvidenceSourceDoneEvent(
                        source_id=source.id,
                        card_count=card_count,
                        candidate_source=event.candidate_source,
                        fallback_used=event.fallback_used,
                    )
                elif isinstance(event, StreamEvidenceErrorEvent):
                    yield StreamEvidenceSourceErrorEvent(
                        source_id=source.id,
                        error_code=event.error_code,
                        message=event.message,
                    )
                    failure_count += 1
                    break
            else:
                # for-else: 没有 break，表示成功完成
                success_count += 1
                total_cards += card_count
        finally:
            db2.close()

    # Phase 3: 全部完成
    yield StreamEvidenceAllDoneEvent(
        total_sources=total,
        success_count=success_count,
        failure_count=failure_count,
        total_cards=total_cards,
    )
```

### 4.2 事件类型定义

```python
@dataclass
class StreamEvidenceSourceStartEvent:
    source_id: str
    source_label: str
    index: int
    total: int

@dataclass
class StreamEvidenceChunkEvent:  # 扩展 SPEC 0020 的 ChunkEvent
    text: str
    source_id: str  # 新增字段

@dataclass
class StreamEvidenceSourceDoneEvent:
    source_id: str
    card_count: int
    candidate_source: str
    fallback_used: bool

@dataclass
class StreamEvidenceSourceErrorEvent:
    source_id: str
    error_code: str
    message: str

@dataclass
class StreamEvidenceAllDoneEvent:
    total_sources: int
    success_count: int
    failure_count: int
    total_cards: int
```

---

## 五、测试策略

### 5.1 后端测试（预期 ~20 测试）

| 测试文件 | 预期数量 | 覆盖点 |
| --- | --- | --- |
| `test_evidence_batch_service_stream.py` | ~12 | 批量成功 / 单个失败继续 / 全部失败 / 无已解析来源 / source_start 事件 / source_done 事件 / all_done 汇总 / 串行顺序 |
| `test_evidence_batch_stream_api.py` | ~8 | SSE 端点 / 事件格式 / all_done 汇总 / 404 / 原单来源端点零回归 |

### 5.2 前端测试（预期 ~20 测试）

| 测试文件 | 预期数量 | 覆盖点 |
| --- | --- | --- |
| `api-batch-stream.test.ts` | ~5 | URL / POST / streamSSE / AbortSignal / HTTP 错误 |
| `hooks-batch-stream.test.tsx` | ~10 | 总进度状态 / 单来源完成 / 单来源失败 / all_done / 取消 |
| `EvidenceWorkspaceView.test.tsx`（扩展） | ~5 | 批量按钮 / 进度展示 / 来源列表 / 取消 |

### 5.3 回归测试

- SPEC 0020 单来源端点零回归（`test_evidence_stream_api.py` 全部通过）
- Worker handler 零改动

---

## 六、验收标准（预期 ~25 项）

| AC 范围 | 内容 |
| --- | --- |
| AC-1~8 | Service 批量流式调用（批量成功 / 单个失败继续 / 无来源 / source_start/done/error 事件 / all_done 汇总） |
| AC-9~15 | API SSE 端点（事件格式 / all_done / 404 / 原单来源端点零回归） |
| AC-16~22 | 前端（API / Hook 总进度 / UI 进度展示 / 取消） |
| AC-23~25 | 测试通过 + 不引入新依赖 + 浏览器验收 |

---

## 七、风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| 复用 SPEC 0020 service 方法时 db session 管理 | 中 | 中 | 批量 service 为每个来源重新打开 db2，确保不跨来源共享 session |
| SSE 事件类型扩展影响 SPEC 0020 | 低 | 低 | 新增事件类型独立定义，不修改 SPEC 0020 的事件类型 |
| 前端进度展示复杂度 | 中 | 低 | 参考 SPEC 0020 的流式展示区设计，增加来源列表和进度条 |
| 串行处理总耗时过长 | 中 | 中 | 5 个来源 × 5-15s = 25-75s，用户可取消；未来可考虑并发优化 |
| LLM 限流导致连续失败 | 低 | 中 | 串行处理本身降低并发风险；如遇限流，source_error 事件会提示用户 |

---

## 八、与已完成流式切片的关系

V2.4.0 发布后，实验报告工作流五个 LLM 生成环节均已流式化：

| SPEC | 模块 | 版本 | 状态 |
| --- | --- | --- | --- |
| SPEC 0018 | 任务单生成 | v2.0.0 | ✅ 已完成 |
| SPEC 0019 | 大纲生成 | v2.1.0 | ✅ 已完成 |
| SPEC 0020 | 证据卡片生成（单来源） | v2.2.0 | ✅ 已完成 |
| SPEC 0021 | 分析方案生成 | v2.3.0 | ✅ 已完成 |
| SPEC 0022 | 代码任务生成 | v2.4.0 | ✅ 已完成 |
| **SPEC 0023** | **证据卡片批量生成（多来源）** | **v2.5.0（草案）** | **⏳ 草案 0.2** |

**SPEC 0023 与已完成切片的关系：**

- **强依赖 SPEC 0020**：复用 `stream_generate_evidence_cards()` 单来源 service 方法，扩展为批量调用。SPEC 0020 的端点、Provider、前端 hook 均保持零改动。
- **借鉴 SPEC 0022 评审反馈**（适用部分）：
  - 并发保护 `active_streams` 字典（按 project_id 维度，避免同一项目重复发起批量流式请求）
  - 服务端取消语义 `Request.is_disconnected()`（客户端断开后立即停止后续来源处理）
  - 错误分层（流前 404 / 流后 source_error 事件）
  - 可观测性结构化日志（每来源记录 source_index / latency / fallback_used / cancel_reason）
- **独立于 SPEC 0021/0022**：只涉及 `sources` 模块，不修改 `analysis` / `execution` 模块。

**与 V2.4.0 已完成流式切片的对比：**

| 维度 | SPEC 0022（代码任务） | SPEC 0023（多来源批量证据） |
| --- | --- | --- |
| 产出数量 | 单个 CodeTaskDraft | 多个来源 × 多张 EvidenceCard |
| 流式范围 | 单次 LLM 调用 | 多次 LLM 调用（串行） |
| 进度展示 | 单次流式累积 | 总进度 + 每来源进度 |
| 失败容错 | 整体失败或成功 | 单来源失败继续后续 |
| 取消语义 | 立即停止 | 立即停止后续来源（已完成来源保留） |
| 耗时 | 3-10s | 5 来源 × 5-15s = 25-75s |

本切片完成后，**实验报告工作流的流式化改造将进入"优化阶段"**（批量、并发、状态持久化等），不再是首次流式化。
