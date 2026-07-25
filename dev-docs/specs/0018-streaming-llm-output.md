# SPEC 0018：流式 LLM 输出（任务单生成）

> **状态：** 已实现并由项目负责人确认收口（2026-07-25）。后端 783 passed（新增 47 测试）+ 前端 468 passed（新增 34 测试）+ lint/build 通过 + alembic 无变化 + 浏览器验收 PASS。已打 tag v2.0.0。
> **日期：** 2026-07-25
> **前置：** V1.4.0 已发布并打 tag v1.4.0（SPEC 0017 单用户前端实时编辑反馈已收口）；当前活跃可记录债务 TD-009（非阻断）
> **目标版本：** v2.0.0
> **关键决策（已由项目负责人确认）：**
> 1. 流式范围：**仅任务单生成**（POST /plans/generate → SSE 流式）；大纲生成保持 Worker 模式不变，推迟到 V2.1
> 2. 大纲流式架构（V2.1 备选）：新增 SSE 端点绕过 Worker
> 3. 降级策略：首 chunk 前失败降级到 LocalRule provider 一次性返回；中途失败保留已生成 chunk + 推送 error 事件

---

## 一、目标与边界

### 1.1 目标

在不破坏现有 owner 边界、不引入新 npm 依赖、不修改数据库 schema 的前提下，将"任务单生成"这一 LLM 调用从同步阻塞改造为 SSE 流式输出，让用户在前端实时看到 LLM 逐 chunk 生成的任务单 JSON，消除"点击生成 → 等 5-15s → 一次性显示"的体验缺陷。

具体目标：

- 用户点击"生成任务单"后，前端立即建立 SSE 连接
- 后端逐 chunk 推送 LLM 输出的 token 到前端
- 前端实时展示生成进度（JSON 文本逐字累积）
- 生成完成后，前端解析完整 JSON + 刷新任务单 query
- 失败时按降级策略处理

### 1.2 范围内

| 改动点 | 当前行为 | 目标行为 | 影响层 |
| --- | --- | --- | --- |
| `DeepSeekClient` | 只有同步 `chat_completion()` | 新增 `stream_chat_completion()` 生成器方法 | 基础设施层 |
| `DeepSeekRequirementDraftProvider` | 只有同步 `draft()` | 新增 `stream_draft()` 生成器方法，复用降级逻辑 | provider 层 |
| `req_service.generate_plan` | 同步调用 provider + 保存 | 新增 `stream_generate_plan()` 生成器方法，分段持有 db 会话 | service 层 |
| `requirements.py` 路由 | 只有 `POST /plans/generate` | 新增 `POST /plans/stream-generate` SSE 端点 | API 层 |
| 前端 `useGeneratePlan` | 同步 mutation | 新增 `useStreamGeneratePlan` hook，管理流式状态 | 前端 hooks |
| 前端任务单 API | `generatePlan()` fetch | 新增 `streamGeneratePlan()` 返回 AsyncGenerator | 前端 API |
| 前端 SSE 解析工具 | 无 | 新建 `stream-sse.ts` 通用 SSE 解析器 | 前端 shared |
| `RequirementWorkspaceView` | 等待 mutation 完成 | 流式展示生成中文本 + 取消按钮 | 前端组件 |

### 1.3 范围外（不做清单）

| 不做项 | 原因 | 后续入口 |
| --- | --- | --- |
| 不改造大纲生成（Worker 模式） | 用户已确认 V2.0 仅做任务单 | V2.1 SPEC 0019 |
| 不改造证据卡片 / 分析方案 / 代码任务 | 同上 | V2.1+ |
| 不新增数据库表 / Alembic 迁移 | 流式 chunk 不持久化 | 永久不做 |
| 不引入 WebSocket / 长轮询基础设施 | SSE 单向推送足够，符合 SPEC 0017 不引入实时通信的方向 | 永久不做 |
| 不引入新 npm / pip 依赖 | httpx + fetch 原生支持 | 永久不做 |
| 不修改 LLM 缓存机制（SPEC 0014） | 流式与同步共享缓存，命中时一次性 yield | 永久不做 |
| 不修改原 `POST /plans/generate` 端点 | 保留同步端点兼容性，新增 SSE 端点 | 永久不做 |
| 不引入新的状态管理库 | TanStack Query + useState 足够 | 永久不做 |

### 1.4 与 SPEC 0017 的关系

SPEC 0017 §1.3 明确"不引入 WebSocket/SSE 实时通信基础设施"指的是"多用户协作的实时双向通信"。本切片引入的 SSE 是"LLM 流式输出的单向推送"，属于单用户场景，不违反 SPEC 0017 范围。

### 1.5 与产品边界的关系

- 仍是本地单用户 Web MVP
- 不引入多用户身份、权限、冲突解决
- LLM 调用仍通过统一 LLM Gateway，不绕过 owner 边界

### 1.6 与 V1.4.0 的关系

V1.4.0 已完成 SPEC 0017 单用户前端实时编辑反馈。本切片是 V1.4.0 之后的第一个功能增强切片，属于 v2.0.0 版本。按 AGENTS.md 阶段闸，进入 v2.0.0 实现前必须先确认本 SPEC。

---

## 二、架构设计

### 2.1 分层影响

```text
SPEC 0018 改动层
  ↓
server/app/infrastructure/llm/deepseek_client.py
  → 新增 stream_chat_completion() 生成器方法
  → 复用缓存查询（命中时一次性 yield 完整字符串模拟流式）
  → 复用错误映射（DeepSeekError）
  ↓ 影响层
server/app/modules/llm/deepseek_requirement_provider.py
  → 新增 stream_draft() 生成器方法
  → 首 chunk 前失败降级到 LocalRule（一次性 yield fallback JSON）
  → 中途失败 yield 已生成 chunks 后抛 DeepSeekError
  ↓ 影响层
server/app/modules/requirements/service.py
  → 新增 stream_generate_plan() 生成器方法
  → 流式期间不持有 db，完成后重新打开保存 RequirementPlan
  → yield StreamEvent 对象（chunk / done / error）
  ↓ 影响层
server/app/api/routers/requirements.py
  → 新增 POST /plans/stream-generate 端点
  → 使用 fastapi.responses.StreamingResponse + media_type="text/event-stream"
  → 序列化 StreamEvent 为 SSE 文本
  ↓ 不影响层
server/worker/                       → Worker 不动
server/app/modules/outlines/         → 大纲模块不动
server/app/modules/sources/          → 证据卡片不动
server/app/infrastructure/database/  → 数据库不动
server/alembic/versions/             → 迁移不动
```

### 2.2 唯一 Owner 边界

| 层 | Owner 文件 | 职责 | 本轮改动 |
| --- | --- | --- | --- |
| 基础设施 | `server/app/infrastructure/llm/deepseek_client.py` | DeepSeek HTTP 调用、超时、重试、错误映射 | 新增 `stream_chat_completion()` 生成器 |
| Provider | `server/app/modules/llm/deepseek_requirement_provider.py` | Prompt 构造、JSON 校验、降级 | 新增 `stream_draft()` 生成器 |
| Service | `server/app/modules/requirements/service.py` | 任务单业务语义、状态推进、RequirementPlan 保存 | 新增 `stream_generate_plan()` 生成器，分段持有 db |
| API | `server/app/api/routers/requirements.py` | HTTP 协议映射 | 新增 SSE 端点，序列化 StreamEvent |
| 前端 Shared | `apps/web/src/shared/stream-sse.ts` | 通用 SSE 解析 | 新建 |
| 前端 API | `apps/web/src/features/requirements/api.ts` | HTTP 调用 | 新增 `streamGeneratePlan()` |
| 前端 Hooks | `apps/web/src/features/requirements/hooks.ts` | TanStack Query 状态管理 | 新增 `useStreamGeneratePlan` |
| 前端组件 | `apps/web/src/routes/RequirementWorkspaceView.tsx` | 编辑 UI | 流式展示 + 取消按钮 |
| 后端业务模块 | `server/app/modules/outlines/` 等 | 业务真相 owner | **不改动** |
| 后端 Worker | `server/worker/` | 后台任务执行 | **不改动** |
| 数据库 | `server/app/infrastructure/database/` | 业务表 | **不改动** |
| Alembic 迁移 | `server/alembic/versions/` | 迁移文件 | **不改动** |

### 2.3 关键决策 1：流式范围仅限任务单生成

**决策：** V2.0 仅改造任务单生成（`POST /plans/generate`）为 SSE 流式，大纲生成保持 Worker 模式不变。

**理由：**
- 任务单生成是同步 API 直连 LLM，改造为 SSE 最自然，无需触碰 Worker 架构
- 大纲生成走 Worker 异步模式，Worker 是独立进程，无法直接推送 SSE 到前端
- 改造大纲流式需要"新增 SSE 端点绕过 Worker"或"Worker 流式 + chunk 表 + 前端轮询"，架构风险高
- 任务单生成是用户首次接触 LLM 的入口（项目创建后第一步），体验提升最显著
- 范围最小化符合 AGENTS.md "抽象只在减少真实复杂度时引入"

**风险：**
- 大纲生成仍需等待 Worker 5-15s，体验未改善
- **缓解：** V2.1 SPEC 0019 解决，本次仅在文档中记录方向

### 2.4 关键决策 2：API SSE + Gateway 直调（不引入 WebSocket）

**决策：** 后端使用 `fastapi.responses.StreamingResponse` + `media_type="text/event-stream"` 推送 SSE 事件，前端使用 `fetch + ReadableStream` 解析。

**理由：**
- SSE 是 HTML5 标准，浏览器原生支持 EventSource API（但本切片用 fetch + ReadableStream 以支持 POST + body）
- 单向推送与 LLM 流式输出天然匹配
- 不引入 WebSocket 的双向通信、心跳、重连复杂性
- 与 SPEC 0014 LLM 缓存兼容（缓存命中时一次性 yield 完整字符串）
- httpx 已支持 `client.stream()`，无需新增 Python 依赖

**SSE 事件格式：**

```text
event: chunk
data: {"text": "实验"}

event: chunk
data: {"text": "目的"}

event: done
data: {"plan_id": "plan_xxx", "candidate_source": "DEEPSEEK", "fallback_used": false}

event: error
data: {"error_code": "DEEPSEEK_TIMEOUT", "message": "请求超时"}
```

### 2.5 关键决策 3：首 chunk 前降级，中途失败保留已生成

**决策：**
- 首 chunk 前失败（HTTP 错误、连接失败、首 chunk 超时）：降级到 `LocalRuleRequirementDraftProvider.draft()`，一次性 yield fallback JSON 字符串（拆分为多个 chunk 模拟流式），最终 `done` 事件标记 `fallback_used: true`
- 中途失败（已 yield 至少一个 chunk 后异常）：yield `error` 事件，前端保留已展示的文本 + 提示错误，用户可重试
- 流式中途失败不保存 RequirementPlan（业务真相未生成完整）
- 流式中途失败不写入 LLM 缓存

**理由：**
- 首 chunk 前降级与现有同步路径一致，用户体验连贯
- 中途失败保留已生成内容让用户看到部分进度，可决定是否重试
- 不保存中途失败的结果避免污染业务真相
- 不写入缓存避免下次拉取到不完整内容

**风险：**
- 中途失败的 JSON 不完整，前端无法解析为 RequirementPlanPayload
- **缓解：** 前端展示原始文本 + 错误提示，用户重试时重新建立 SSE 连接

### 2.6 关键决策 4：流式与同步端点共存

**决策：** 保留原 `POST /plans/generate` 同步端点不变，新增 `POST /plans/stream-generate` SSE 端点。

**理由：**
- 不破坏现有 API 合同（SPEC 0002 锁定）
- 同步端点仍可用于非流式场景（如脚本调用、测试）
- 前端默认使用流式端点，但保留同步端点作为兜底
- 测试可分别覆盖同步和流式路径

### 2.7 关键决策 5：流式期间分段持有数据库会话

**决策：** `stream_generate_plan()` 采用分段持有 db session 策略：

1. 端点入口：打开 db → 查询 source + 校验 → 关闭 db
2. 流式生成：调用 provider.stream_draft()（不持有 db）
3. 完成后：重新打开 db → 保存 RequirementPlan + 推进 project.status → 关闭 db

**理由：**
- 流式期间 db session 大部分时间空闲（等待 LLM chunk）
- SQLite 单写者，长时间持有写锁会阻塞其他请求
- 流式期间不写库，只在生成完成后批量写库；流式中途失败时不写库
- 流式开始前查询 source 后立即关闭 session，流式完成后重新打开 session 写库，更安全

### 2.8 关键决策 6：缓存策略

**决策：**
- 流式调用同样查询缓存（`LLMCache.get(cache_key)`）
- 缓存命中时一次性 yield 完整字符串（前端快速完成，模拟"瞬时生成"）
- 流式完成后写入缓存（与同步路径共享 `LLMCache.set()`）
- 流式中途失败不写入缓存
- 缓存 key 计算复用 `LLMCache.compute_key()`（model + messages + response_format + temperature）

**理由：**
- 缓存命中时直接走完整字符串，避免重新调 LLM
- 流式与同步路径共享缓存，命中率高
- 失败不写入缓存避免污染

---

## 三、实现细节

### 3.1 `DeepSeekClient.stream_chat_completion()` 实现

**文件：** `server/app/infrastructure/llm/deepseek_client.py`

**新增方法：**

```python
def stream_chat_completion(
    self,
    messages: list[dict],
    response_format: dict | None = None,
    temperature: float = 0.3,
) -> Generator[str, None, None]:
    """流式调用 DeepSeek chat/completions，逐 chunk yield content。

    缓存命中时一次性 yield 完整字符串（模拟流式）。
    流式完成后写入缓存（与同步路径共享）。
    流式中途失败不写入缓存。

    异常：
    - DeepSeekError（code, message）—— 首 chunk 前失败由 provider 降级
    """
    # 缓存查询
    cache_key = None
    if self._cache is not None:
        cache_key = LLMCache.compute_key(
            self._model, messages, response_format, temperature
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info(f"LLM 缓存命中（流式），key={cache_key[:12]}...")
            yield cached
            return

    # HTTP 流式调用（不重试，流式重试语义复杂）
    url = f"{self._base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {self._api_key}",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "model": self._model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if response_format is not None:
        payload["response_format"] = response_format

    accumulated: list[str] = []
    try:
        with httpx.Client(timeout=self._timeout_seconds) as client:
            with client.stream("POST", url, json=payload, headers=headers) as resp:
                # HTTP 状态码处理（首 chunk 前）
                if resp.status_code == 401:
                    raise DeepSeekError(
                        code="DEEPSEEK_AUTH_ERROR",
                        message="API Key 鉴权失败",
                    )
                if resp.status_code == 429:
                    raise DeepSeekError(
                        code="DEEPSEEK_RATE_LIMITED",
                        message="请求被限流",
                    )
                if 400 <= resp.status_code < 500:
                    raise DeepSeekError(
                        code="DEEPSEEK_CLIENT_ERROR",
                        message=f"客户端错误（{resp.status_code}）",
                    )
                if resp.status_code >= 500:
                    raise DeepSeekError(
                        code="DEEPSEEK_SERVER_ERROR",
                        message=f"服务端错误（{resp.status_code}）",
                    )

                # 流式读取 SSE 行
                for line in resp.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data)
                        delta = (
                            chunk_data.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if delta:
                            accumulated.append(delta)
                            yield delta
                    except (json.JSONDecodeError, KeyError, IndexError) as e:
                        logger.warning(f"流式 chunk 解析失败: {e}")
                        continue
    except httpx.TimeoutException as e:
        raise DeepSeekError(
            code="DEEPSEEK_TIMEOUT",
            message=f"流式请求超时（{self._timeout_seconds}s）：{e}",
        ) from e
    except httpx.ConnectError as e:
        raise DeepSeekError(
            code="DEEPSEEK_CONNECTION_ERROR",
            message=f"流式连接失败：{e}",
        ) from e
    except httpx.HTTPError as e:
        raise DeepSeekError(
            code="DEEPSEEK_HTTP_ERROR",
            message=f"流式 HTTP 错误：{e}",
        ) from e

    # 流式完成后写入缓存（失败不阻断主流程）
    if cache_key is not None and self._cache is not None and accumulated:
        try:
            self._cache.set(
                cache_key, "".join(accumulated), model=self._model
            )
        except Exception as e:
            logger.warning(f"LLM 缓存写入失败（流式）：{e}")
```

**关键实现要点：**
- 流式不重试（重试语义复杂，且首 chunk 前失败由 provider 降级）
- 流式期间不持有 db session（client 与 db 解耦）
- 缓存命中时一次性 yield，前端快速完成
- 错误统一为 DeepSeekError，由 provider 决定降级策略

### 3.2 `DeepSeekRequirementDraftProvider.stream_draft()` 实现

**文件：** `server/app/modules/llm/deepseek_requirement_provider.py`

**新增方法：**

```python
from typing import Generator

def stream_draft(
    self, requirement_text: str
) -> Generator[str, None, None]:
    """流式调用 DeepSeek 拆解实验要求，逐 chunk yield content。

    首 chunk 前失败：降级到 LocalRule，一次性 yield fallback JSON（拆分为多个 chunk）。
    中途失败：yield 已生成 chunks 后抛 DeepSeekError（由上层捕获并推送 error 事件）。

    yield 内容：
    - LLM 流式 chunk（首 chunk 后保证至少有一个 chunk）
    - 降级时一次性 yield fallback JSON 字符串
    """
    chunks: list[str] = []
    started = False
    try:
        for chunk in self._client.stream_chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(requirement_text)},
            ],
            response_format={"type": "json_object"},
            temperature=self._temperature,
        ):
            started = True
            chunks.append(chunk)
            yield chunk
    except Exception as e:
        if not started:
            # 首 chunk 前失败，降级到 LocalRule
            logger.warning(
                f"DeepSeek 流式任务单失败，降级到 LocalRule: {e}"
            )
            fallback_payload = self._fallback.draft(requirement_text)
            fallback_json = fallback_payload.model_dump_json()
            # 拆分为多个 chunk 模拟流式（按 50 字符拆分）
            for i in range(0, len(fallback_json), 50):
                yield fallback_json[i:i + 50]
            return
        # 中途失败，已 yield 的 chunks 保留，抛异常由上层处理
        raise

    # 流式完成，校验完整 JSON
    raw = "".join(chunks)
    try:
        self._parse_and_validate(raw)
    except Exception as e:
        # JSON 不完整或校验失败
        raise DeepSeekError(
            code="DEEPSEEK_JSON_PARSE_ERROR",
            message=f"流式生成的 JSON 校验失败: {e}",
        ) from e
```

**关键实现要点：**
- 首 chunk 前失败降级到 LocalRule，拆分为多个 chunk 模拟流式
- 中途失败抛异常，由 service 层捕获并推送 error 事件
- 流式完成后校验完整 JSON（与同步路径一致）

### 3.3 `req_service.stream_generate_plan()` 实现

**文件：** `server/app/modules/requirements/service.py`

**新增 StreamEvent 类型：**

```python
from dataclasses import dataclass
from typing import Generator, Any

@dataclass
class StreamChunkEvent:
    text: str

@dataclass
class StreamDoneEvent:
    plan_id: str
    candidate_source: str
    fallback_used: bool

@dataclass
class StreamErrorEvent:
    error_code: str
    message: str
    partial_text: str  # 已生成的部分文本

StreamEvent = StreamChunkEvent | StreamDoneEvent | StreamErrorEvent
```

**新增方法：**

```python
def stream_generate_plan(
    db: Session, project_id: str, req: GeneratePlanRequest, provider,
) -> Generator[StreamEvent, None, None]:
    """流式生成任务单。

    流程：
    1. 校验 project + source（持有 db）
    2. 关闭 db，进入流式生成（不持有 db）
    3. 流式期间收集 chunks
    4. 完成后重新打开 db，保存 RequirementPlan + 推进 project.status
    5. 中途失败：yield StreamErrorEvent（保留 partial_text）

    注意：本方法在生成器内部管理 db session，调用方不需传入 db。
    """
    from app.infrastructure.database.engine import SessionLocal
    from app.modules.requirements.status import PlanStatus, CandidateSource

    # Phase 1: 校验（持有 db）
    project = _ensure_project(db, project_id)
    source = get_source(db, req.source_id)
    if source.project_id != project_id:
        raise AppError(
            code="REQUIREMENT_SOURCE_NOT_FOUND",
            message="要求来源不属于该项目",
        )
    requirement_text = source.original_text
    db.close()  # 显式关闭，避免流式期间持有连接

    # Phase 2: 流式生成（不持有 db）
    chunks: list[str] = []
    fallback_used = False
    try:
        # 判断 provider 是否支持流式
        if hasattr(provider, "stream_draft"):
            for chunk in provider.stream_draft(requirement_text):
                chunks.append(chunk)
                yield StreamChunkEvent(text=chunk)
        else:
            # 兼容 LocalRule provider（不支持流式）
            payload = provider.draft(requirement_text)
            full_json = payload.model_dump_json()
            for i in range(0, len(full_json), 50):
                yield StreamChunkEvent(text=full_json[i:i + 50])
            chunks.append(full_json)
    except Exception as e:
        # 中途失败
        partial_text = "".join(chunks)
        yield StreamErrorEvent(
            error_code=getattr(e, "code", "STREAM_FAILED"),
            message=str(e),
            partial_text=partial_text,
        )
        return

    # Phase 3: 校验完整 JSON
    raw = "".join(chunks)
    try:
        from app.modules.llm.deepseek_requirement_provider import (
            DeepSeekRequirementResponse,
        )
        parsed = DeepSeekRequirementResponse.model_validate_json(raw)
        payload = _deepseek_response_to_payload(parsed)
    except Exception as e:
        yield StreamErrorEvent(
            error_code="DEEPSEEK_JSON_PARSE_ERROR",
            message=f"流式生成的 JSON 校验失败: {e}",
            partial_text=raw,
        )
        return

    # Phase 4: 保存（重新打开 db）
    db2 = SessionLocal()
    try:
        old = (
            db2.query(RequirementPlan)
            .filter(
                RequirementPlan.project_id == project_id,
                RequirementPlan.status == PlanStatus.CANDIDATE.value,
            )
            .all()
        )
        for p in old:
            p.status = PlanStatus.STALE.value

        plan = RequirementPlan(
            project_id=project_id,
            source_id=source.id,
            status=PlanStatus.CANDIDATE.value,
            payload_json=payload.model_dump_json(),
            candidate_source=provider.source_label(),
        )
        db2.add(plan)
        project2 = _ensure_project(db2, project_id)
        project2.status = ProjectStatus.REQUIREMENT_PARSED.value
        _add_change(
            db2, project_id,
            ChangeType.REQUIREMENT_PLAN_GENERATED.value,
            f"流式生成任务单候选（{provider.source_label()}）",
        )
        db2.commit()
        db2.refresh(plan)

        yield StreamDoneEvent(
            plan_id=plan.id,
            candidate_source=provider.source_label(),
            fallback_used=fallback_used,
        )
    except Exception as e:
        yield StreamErrorEvent(
            error_code="PLAN_SAVE_FAILED",
            message=f"任务单保存失败: {e}",
            partial_text=raw,
        )
    finally:
        db2.close()
```

**关键实现要点：**
- 流式期间不持有 db（关闭后调用 provider）
- 完成后重新打开 db 保存
- 中途失败 yield StreamErrorEvent（保留 partial_text 供前端展示）
- 兼容不支持流式的 provider（LocalRule）

### 3.4 API SSE 端点实现

**文件：** `server/app/api/routers/requirements.py`

**新增端点：**

```python
from fastapi.responses import StreamingResponse
from app.modules.requirements.service import (
    stream_generate_plan, StreamChunkEvent, StreamDoneEvent, StreamErrorEvent,
)

@router.post("/plans/stream-generate")
def stream_generate_plan_endpoint(project_id: str, body: dict):
    """SSE 流式生成任务单。

    返回 text/event-stream，事件格式：
    - event: chunk / data: {"text": "..."}
    - event: done / data: {"plan_id": "...", "candidate_source": "...", "fallback_used": false}
    - event: error / data: {"error_code": "...", "message": "...", "partial_text": "..."}
    """
    try:
        req = GeneratePlanRequest(**body)
    except ValidationError as exc:
        raise AppError(
            code="REQUEST_VALIDATION_ERROR",
            message="请求参数不符合要求",
            field=_field_from_validation(exc),
        )

    provider = get_provider()

    def event_stream():
        db = SessionLocal()
        try:
            for event in stream_generate_plan(db, project_id, req, provider):
                yield _serialize_sse_event(event)
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
            "X-Accel-Buffering": "no",  # nginx 禁用缓冲
        },
    )


def _serialize_sse_event(event) -> str:
    """序列化 StreamEvent 为 SSE 文本块。"""
    import json
    if isinstance(event, StreamChunkEvent):
        return f"event: chunk\ndata: {json.dumps({'text': event.text}, ensure_ascii=False)}\n\n"
    elif isinstance(event, StreamDoneEvent):
        return f"event: done\ndata: {json.dumps({'plan_id': event.plan_id, 'candidate_source': event.candidate_source, 'fallback_used': event.fallback_used}, ensure_ascii=False)}\n\n"
    elif isinstance(event, StreamErrorEvent):
        return f"event: error\ndata: {json.dumps({'error_code': event.error_code, 'message': event.message, 'partial_text': event.partial_text}, ensure_ascii=False)}\n\n"
    return ""
```

### 3.5 前端 SSE 解析工具

**文件：** `apps/web/src/shared/stream-sse.ts`（新建）

```typescript
/**
 * 通用 SSE 解析工具。
 *
 * 使用 fetch + ReadableStream 而非 EventSource，以支持 POST + body。
 * 处理 event: xxx / data: yyy 格式的 SSE 文本块。
 */

export interface SSEEvent {
  event: string;
  data: string;
}

/**
 * 发起 SSE 请求并返回异步迭代器。
 *
 * @param url 请求 URL
 * @param body 请求体（POST JSON）
 * @param signal 可选的 AbortSignal，用于取消
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
    let detail: any = null;
    try {
      detail = await resp.json();
    } catch {
      detail = { message: `请求失败 (${resp.status})` };
    }
    throw detail?.error ?? detail ?? { message: resp.statusText };
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
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      for (const evtText of events) {
        const lines = evtText.split("\n");
        let event = "message";
        let data = "";
        for (const line of lines) {
          if (line.startsWith("event:")) {
            event = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            data = line.slice(5).trim();
          }
        }
        if (data) {
          yield { event, data };
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
```

### 3.6 前端流式 API 调用

**文件：** `apps/web/src/features/requirements/api.ts`（修改）

```typescript
import { streamSSE, type SSEEvent } from "../../shared/stream-sse";

const BASE = "/api";

/**
 * 流式生成任务单。
 *
 * 返回异步迭代器，逐个 yield SSE 事件。
 * 调用方负责处理 chunk / done / error 事件。
 */
export async function* streamGeneratePlan(
  projectId: string,
  sourceId: string,
  signal?: AbortSignal
): AsyncGenerator<SSEEvent, void, unknown> {
  const url = `${BASE}/projects/${encodeURIComponent(projectId)}/requirements/plans/stream-generate`;
  yield* streamSSE(url, { source_id: sourceId }, signal);
}
```

### 3.7 前端流式 Hook

**文件：** `apps/web/src/features/requirements/hooks.ts`（修改）

```typescript
import { useState, useRef, useCallback } from "react";
import { streamGeneratePlan } from "./api";

export interface StreamPlanState {
  streaming: boolean;
  chunks: string;          // 已生成的完整文本
  result: { plan_id: string; candidate_source: string; fallback_used: boolean } | null;
  error: { error_code: string; message: string; partial_text: string } | null;
}

const INITIAL_STATE: StreamPlanState = {
  streaming: false,
  chunks: "",
  result: null,
  error: null,
};

/**
 * 流式生成任务单 hook。
 */
export function useStreamGeneratePlan(projectId: string) {
  const qc = useQueryClient();
  const [state, setState] = useState<StreamPlanState>(INITIAL_STATE);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(async (sourceId: string) => {
    setState({ ...INITIAL_STATE, streaming: true });
    abortRef.current = new AbortController();
    try {
      for await (const evt of streamGeneratePlan(projectId, sourceId, abortRef.current.signal)) {
        if (evt.event === "chunk") {
          const { text } = JSON.parse(evt.data);
          setState((s) => ({ ...s, chunks: s.chunks + text }));
        } else if (evt.event === "done") {
          const data = JSON.parse(evt.data);
          setState((s) => ({ ...s, result: data, streaming: false }));
          qc.invalidateQueries({ queryKey: [...projectKey(projectId), "plan"] });
        } else if (evt.event === "error") {
          const data = JSON.parse(evt.data);
          setState((s) => ({
            ...s,
            error: data,
            streaming: false,
          }));
        }
      }
    } catch (e: any) {
      if (e?.name === "AbortError") {
        setState((s) => ({ ...s, streaming: false }));
      } else {
        setState((s) => ({
          ...s,
          error: {
            error_code: "STREAM_NETWORK_ERROR",
            message: e?.message ?? "流式连接失败",
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
    setState(INITIAL_STATE);
  }, []);

  return { ...state, start, cancel, reset };
}
```

### 3.8 前端 UI 改造

**文件：** `apps/web/src/routes/RequirementWorkspaceView.tsx`（修改）

**关键改动：**
- 在原有"生成任务单"按钮旁新增"流式生成"按钮（或替换原按钮）
- 流式期间展示文本框，逐字累积显示生成内容
- 提供"取消"按钮
- 完成后自动切换到任务单详情视图
- 失败时展示错误提示 + 保留已生成内容

**UI 规范：**
- 流式文本框使用 `<pre>` 或 `<textarea readonly>` 展示，等宽字体
- 流式期间按钮 disabled，文案"生成中…"
- 完成后 1.5s 自动清空流式文本框（避免遮挡）
- 错误展示使用红色文案，文案来自 `error.message`
- 不引入 Toast 库，用内联状态展示

---

## 四、API 合同

### 4.1 新增端点

**`POST /api/projects/{project_id}/requirements/plans/stream-generate`**

请求体（与同步端点一致）：
```json
{
  "source_id": "src_xxx"
}
```

响应：`text/event-stream`

事件流示例：
```text
event: chunk
data: {"text": "实验"}

event: chunk
data: {"text": "目的"}

event: done
data: {"plan_id": "plan_xxx", "candidate_source": "DEEPSEEK", "fallback_used": false}
```

或失败时：
```text
event: error
data: {"error_code": "DEEPSEEK_TIMEOUT", "message": "流式请求超时", "partial_text": "实验目的..."}
```

### 4.2 不修改原端点

`POST /plans/generate` 同步端点保留不变，合同与 SPEC 0002 一致。

---

## 五、测试策略

### 5.1 新增后端单元测试

**文件：**
- `server/tests/unit/infrastructure/test_deepseek_client_stream.py`（新增）
- `server/tests/unit/modules/test_deepseek_requirement_provider_stream.py`（新增）
- `server/tests/unit/modules/test_requirements_service_stream.py`（新增）
- `server/tests/unit/api/test_requirements_stream.py`（新增）

**测试覆盖矩阵：**

| 测试场景 | 覆盖点 | 预期 |
| --- | --- | --- |
| 流式成功 | mock DeepSeek API 返回多个 chunk，验证 yield 顺序 | 通过 |
| 缓存命中 | mock 缓存命中，验证一次性 yield 完整字符串 | 通过 |
| 缓存写入 | 流式完成后验证 cache.set 被调用 | 通过 |
| 首 chunk 前失败 | mock HTTP 401，验证抛 DeepSeekError | 通过 |
| 中途失败 | mock 第一个 chunk 后断连，验证已 yield 一个 chunk | 通过 |
| Provider 降级 | 首 chunk 前失败，验证降级到 LocalRule | 通过 |
| Provider 中途失败 | 第一个 chunk 后失败，验证抛异常 | 通过 |
| Service 流式成功 | 完整流程，验证 RequirementPlan 保存 + StreamDoneEvent | 通过 |
| Service 中途失败 | mock provider 失败，验证 StreamErrorEvent + 不保存 | 通过 |
| Service 兼容 LocalRule | provider 不支持 stream_draft，验证一次性 yield | 通过 |
| API SSE 端点 | TestClient 请求，验证 SSE 文本格式 | 通过 |
| API 错误响应 | source_id 无效，验证 AppError 返回 | 通过 |

**预计新增测试：** ~20 个

### 5.2 新增前端单元测试

**文件：**
- `apps/web/src/shared/stream-sse.test.ts`（新增）
- `apps/web/src/features/requirements/hooks.test.tsx`（扩展）

**测试覆盖矩阵：**

| 测试场景 | 覆盖点 | 预期 |
| --- | --- | --- |
| SSE 解析正确 | mock fetch 返回多 chunk，验证 yield 顺序 | 通过 |
| SSE 取消 | AbortController.abort()，验证 reader.releaseLock | 通过 |
| SSE 错误响应 | mock fetch 返回 4xx，验证抛错 | 通过 |
| useStreamGeneratePlan 成功 | mock streamGeneratePlan，验证状态变化 | 通过 |
| useStreamGeneratePlan 取消 | 调用 cancel()，验证 streaming: false | 通过 |
| useStreamGeneratePlan 错误 | mock error 事件，验证 error 状态 | 通过 |
| useStreamGeneratePlan 完成后 invalidate | done 事件后验证 invalidateQueries | 通过 |

**预计新增测试：** ~10 个

### 5.3 现有测试零回归

**要求：**
- 后端 736 passed → 736 + ~20 = ~756 passed
- 前端 434 passed → 434 + ~10 = ~444 passed
- TypeScript 类型检查通过
- Vite 构建通过
- Alembic 迁移无变化（无 schema 变更）

### 5.4 浏览器验收

按 AGENTS.md "UI 行为变化应做浏览器点击或截图验收"：
- 启动后端 + 前端
- 在 RequirementWorkspaceView 点击"流式生成"
- 截图生成过程中的文本累积
- 截图完成后的任务单详情
- 模拟失败（断开后端），截图错误提示

**证据保存路径：** `dev-docs/e2e-screenshots/spec-0018/`

### 5.5 验收命令

按 AGENTS.md 基础验收命令：

```text
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
```

**预期：**
- pytest: ~756 passed, 0 warnings
- alembic: 迁移无变化
- lint: TypeScript 通过
- build: Vite 构建通过

---

## 六、依赖

### 6.1 不新增依赖

| 依赖 | 当前版本 | 本轮改动 |
| --- | --- | --- |
| `httpx`（Python） | 已使用 | 不升级，stream() 已支持 |
| `@tanstack/react-query` | 5.101.0 | 不升级 |
| `react` | 19.2.7 | 不升级 |
| `typescript` | 6.0.3 | 不升级 |
| `vitest` | 4.1.10 | 不升级 |

---

## 七、验收标准

| AC # | 验收项 | 通过标准 |
| --- | --- | --- |
| AC-1 | DeepSeekClient.stream_chat_completion 成功 | mock API 返回多 chunk，yield 顺序正确 |
| AC-2 | 流式缓存命中 | 缓存命中时一次性 yield 完整字符串 |
| AC-3 | 流式缓存写入 | 完成后 cache.set 被调用 |
| AC-4 | 流式首 chunk 前失败 | 抛 DeepSeekError，不写缓存 |
| AC-5 | 流式中途失败 | 已 yield chunk，不写缓存 |
| AC-6 | Provider.stream_draft 成功 | yield 顺序正确，JSON 校验通过 |
| AC-7 | Provider 首 chunk 前降级 | 降级到 LocalRule，yield fallback JSON |
| AC-8 | Provider 中途失败 | 抛异常，已 yield chunks 保留 |
| AC-9 | Service.stream_generate_plan 成功 | RequirementPlan 保存，StreamDoneEvent |
| AC-10 | Service 中途失败 | StreamErrorEvent，不保存 RequirementPlan |
| AC-11 | Service 兼容 LocalRule | provider 不支持 stream_draft 时降级为一次性 yield |
| AC-12 | API SSE 端点 | 返回 text/event-stream，事件格式正确 |
| AC-13 | API 错误响应 | source_id 无效时返回 AppError |
| AC-14 | 前端 streamSSE 解析 | 正确解析 chunk/done/error 事件 |
| AC-15 | 前端 useStreamGeneratePlan | 状态变化正确，支持取消 |
| AC-16 | 前端 UI 流式展示 | 逐字累积，取消按钮可用 |
| AC-17 | 原同步端点零回归 | POST /plans/generate 行为不变 |
| AC-18 | 后端测试通过 | 736 + ~20 = ~756 passed |
| AC-19 | 前端测试通过 | 434 + ~10 = ~444 passed |
| AC-20 | TypeScript 类型检查 | npm run lint 通过 |
| AC-21 | Vite 构建 | npm run build 通过 |
| AC-22 | Alembic 无变化 | 无新增迁移文件 |
| AC-23 | 数据库零改动 | git diff server/alembic/ 无变化 |
| AC-24 | 不引入新依赖 | package.json 和 pyproject.toml 无新增依赖 |
| AC-25 | 浏览器验收 | 截图保存到 dev-docs/e2e-screenshots/spec-0018/ |
| AC-26 | 不破坏 owner 边界 | API 只做协议映射，业务在 service 层 |
| AC-27 | 文档回写 | acceptance.md、implementation-plan.md、README.md、decisions/0024、changelog-v2.0.0.md |
| AC-28 | 版本收口 | 完成 commit "完成 SPEC 0018 流式 LLM 输出"，push 到 origin/master，打 tag v2.0.0 |

---

## 八、实施顺序

按 AGENTS.md 阶段闸：

1. **SPEC 0018 文档确认**（本文件，待项目负责人批准）
2. **新增决策记录** `dev-docs/decisions/0024-start-spec-0018-streaming-llm-output.md`
3. **测试先行**：编写后端 DeepSeekClient.stream_chat_completion 测试（先红）
4. **基础设施层实现**：`DeepSeekClient.stream_chat_completion()`
5. **Provider 层实现**：`DeepSeekRequirementDraftProvider.stream_draft()`
6. **Service 层实现**：`req_service.stream_generate_plan()` + StreamEvent 类型
7. **API 层实现**：新增 `/plans/stream-generate` SSE 端点
8. **后端测试**：`pytest` 全部通过
9. **前端 SSE 工具**：`stream-sse.ts` + 测试
10. **前端 API**：`streamGeneratePlan()`
11. **前端 Hook**：`useStreamGeneratePlan`
12. **前端组件**：RequirementWorkspaceView UI 改造
13. **前端测试**：`npm run test` 全部通过
14. **类型检查与构建**：`npm run lint` + `npm run build`
15. **浏览器验收**：截图保存到 `dev-docs/e2e-screenshots/spec-0018/`
16. **后端回归验证**：`pytest` + `alembic upgrade head`（确认无后端改动）
17. **文档回写**：`acceptance.md`、`implementation-plan.md`、`README.md`、`changelog-v2.0.0.md`、`decisions/0024`
18. **git 边界复核 → 精确 stage → commit → push → git tag v2.0.0 → push --tags**

---

## 九、风险与回退

### 9.1 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| 流式期间 db session 处理不当导致 SQLite 锁 | 中 | 其他请求阻塞 | 流式期间不持有 db，完成后重新打开 |
| 缓存命中时一次性返回大量数据 | 低 | 前端渲染卡顿 | 缓存命中时也按 chunk 拆分 yield |
| DeepSeek SSE 格式与预期不符 | 低 | chunk 解析失败 | 测试覆盖 + 容错解析（解析失败跳过 chunk） |
| 前端 AbortController 兼容性 | 低 | 取消功能不可用 | 现代浏览器原生支持，无需 polyfill |
| 原 sync 端点回归 | 低 | 同步调用失败 | 不修改原端点，测试覆盖 |
| 浏览器 SSE 连接超时 | 中 | 流式中断 | 前端检测连接关闭后展示错误 + 重试按钮 |
| 大型任务单 JSON 渲染性能 | 低 | UI 卡顿 | 流式文本框用 `<pre>` 等宽字体，避免复杂渲染 |
| Worker 大纲生成未改造仍慢 | 中 | 用户期望落差 | 文档明确说明 V2.0 范围，V2.1 解决 |

### 9.2 回退方案

如本切片引入阻断问题，可通过以下方式回退：

1. **后端回退：** 删除 `stream_chat_completion` / `stream_draft` / `stream_generate_plan` / `/plans/stream-generate` 端点
2. **前端回退：** 还原 `useStreamGeneratePlan` 调用为 `useGeneratePlan`，移除流式 UI
3. **保留兼容：** 原 `POST /plans/generate` 同步端点从未修改，回退后用户使用同步路径

回退后用户体验回到 V1.4.0 状态（任务单生成等待 5-15s 一次性显示），不阻断核心功能。

### 9.3 最大回归风险

**最大风险：** 流式期间 db session 管理不当导致 SQLite 写锁阻塞其他请求。

**阻断证据：**
- AC-9 / AC-10 通过 service 层测试覆盖 db session 管理
- AC-22 / AC-23 确认无数据库 schema 变更
- 浏览器验收 AC-25 验证完整流程无阻塞

---

## 十、确认事项（项目负责人已确认）

### 10.1 流式范围仅限任务单生成

**决策：** 见 §2.3。V2.0 仅做任务单流式，大纲流式推迟到 V2.1。

### 10.2 API SSE + Gateway 直调

**决策：** 见 §2.4。不引入 WebSocket。

### 10.3 首 chunk 前降级，中途失败保留已生成

**决策：** 见 §2.5。

### 10.4 流式与同步端点共存

**决策：** 见 §2.6。保留原 `POST /plans/generate` 不变。

### 10.5 流式期间分段持有 db

**决策：** 见 §2.7。流式期间不持有 db，完成后重新打开。

### 10.6 v2.0.0 版本号

**决策：** 本切片发布为 v2.0.0。

**理由：** 引入流式 LLM 输出是用户体验的重大升级，从 V1.x 升级到 V2.0 符合语义化版本。如项目负责人认为不应升级大版本，可改为 v1.5.0。

---

## 十一、与 V2.0 整体规划的关系

本切片是 V2.0 的第一个 SPEC。按 AGENTS.md "多 SPEC 版本规划时需保证各 SPEC 关注点正交、风险隔离、独立验收"：

| SPEC | 关注点 | owner 层 | 风险隔离 |
| --- | --- | --- | --- |
| SPEC 0018 | 任务单生成流式 LLM 输出 | DeepSeekClient + 任务单 provider/service/api/前端 | 不触碰 Worker、大纲模块、数据库 |
| SPEC 0019（V2.1 备选） | 大纲生成流式化 | Worker 改造或 SSE 绕过 Worker | 待 SPEC 0018 收口后规划 |

本切片不依赖 V2.0 后续 SPEC，可独立验收。V2.0 后续 SPEC 待项目负责人规划。

---

## 十二、停止条件

本切片完成的停止条件：

1. AC-1~AC-28 全部通过
2. 后端测试 ~756 passed（736 + ~20）
3. 前端测试 ~444 passed（434 + ~10）
4. TypeScript 类型检查通过
5. Vite 构建通过
6. Alembic 迁移无变化
7. 浏览器验收截图保存到 `dev-docs/e2e-screenshots/spec-0018/`
8. 项目负责人确认收口
9. 完成 git commit + push + tag v2.0.0

---

## 十三、未在本切片处理的已知问题

| 问题 | 不处理原因 | 后续入口 |
| --- | --- | --- |
| 大纲生成流式化 | 用户已确认 V2.0 仅做任务单 | V2.1 SPEC 0019 |
| 证据卡片 / 分析方案 / 代码任务流式化 | 同上 | V2.1+ |
| 流式 chunk 持久化（断点续传） | 流式是即时体验，无需持久化 | 永久不做 |
| 流式生成取消后恢复 | 取消后重新开始即可 | V2.1+ 评估 |
| TD-009 浏览器验收截图未持久化 | 非本切片范围 | 后续工具升级 |
