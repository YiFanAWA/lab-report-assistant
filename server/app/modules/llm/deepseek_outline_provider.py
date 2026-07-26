"""DeepSeek LLM 驱动的实验大纲生成提供者。

调用 DeepSeek API 基于已确认的任务单、证据卡片、数据概览、分析方案和执行结果
生成统一实验大纲候选。LLM 调用失败时降级到 LocalRuleOutlineProvider。

设计决策：
- AnalysisPlan 阶段为字段截断唯一截断点。
- Outline 生成时直接透传已截断字段内容，不做二次截断。
- 提供者只接收 context dict（含摘要），不泄露完整用户数据。
"""

import json
import logging
from typing import Any, Generator

from pydantic import BaseModel, ValidationError

from app.infrastructure.llm.deepseek_client import DeepSeekClient, DeepSeekError
from app.modules.llm.outline_provider import (
    LocalRuleOutlineProvider,
    OutlineDraft,
    OutlineDraftSection,
)


logger = logging.getLogger(__name__)


# --- Pydantic 结构化输出校验模型 ---


class DeepSeekOutlineSection(BaseModel):
    """LLM 返回的大纲章节（用于校验）。"""

    id: str
    title: str
    content: str
    source_type: str
    source_ids: list[str] = []


class DeepSeekOutlineResponse(BaseModel):
    """LLM 返回的大纲（用于校验）。"""

    sections: list[DeepSeekOutlineSection]


# --- Prompt 构造 ---


_SYSTEM_PROMPT = """你是一个实验报告大纲生成助手。你的任务是基于已确认的内容生成统一实验大纲。

大纲必须包含 6 个章节：
1. 实验目的（id="purpose", source_type="REQUIREMENT"）
2. 实验背景（id="background", source_type="EVIDENCE"）
3. 数据与数据集（id="dataset", source_type="DATASET"）
4. 分析方案（id="analysis", source_type="ANALYSIS"）
5. 执行结果（id="results", source_type="EXECUTION"）
6. 结论与总结（id="conclusion", source_type="SUMMARY"）

输出要求：
1. 必须返回 JSON 格式：{"sections": [...]}
2. 每个章节包含：
   - id: 章节标识（固定 6 个）
   - title: 章节标题
   - content: 章节内容（综合上下文生成）
   - source_type: 来源类型（REQUIREMENT/EVIDENCE/DATASET/ANALYSIS/EXECUTION/SUMMARY）
   - source_ids: 来源 ID 列表

生成原则：
- 内容必须基于提供的上下文，不编造
- 实验结果必须来自真实执行记录
- 资料性结论必须关联来源
- 模型建议必须标记为建议"""


def _build_user_prompt(context: dict[str, Any]) -> str:
    """构造用户消息，包含上下文摘要。"""
    # 安全提取各部分摘要，截断过长内容
    requirements = str(context.get("requirements", ""))[:2000]
    evidence = str(context.get("evidence", ""))[:2000]
    dataset = str(context.get("dataset", ""))[:1000]
    analysis = str(context.get("analysis", ""))[:2000]
    execution = str(context.get("execution", ""))[:2000]

    return f"""上下文信息：

【实验要求】
{requirements}

【证据卡片】
{evidence}

【数据集概览】
{dataset}

【分析方案】
{analysis}

【执行结果】
{execution}

请生成 6 章节的实验大纲（JSON 格式）。"""


# --- DeepSeek Provider 实现 ---


class DeepSeekOutlineProvider:
    """DeepSeek LLM 驱动的实验大纲生成提供者。"""

    def __init__(
        self,
        client: DeepSeekClient,
        fallback: LocalRuleOutlineProvider | None = None,
        temperature: float = 0.3,
    ):
        self._client = client
        self._fallback = fallback or LocalRuleOutlineProvider()
        self._temperature = temperature

    def source_label(self) -> str:
        return "DEEPSEEK"

    def generate(self, context: dict[str, Any]) -> OutlineDraft:
        """调用 DeepSeek 生成大纲，失败时降级。"""
        try:
            raw = self._client.chat_completion(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_prompt(context)},
                ],
                response_format={"type": "json_object"},
                temperature=self._temperature,
            )
            parsed = self._parse_and_validate(raw)
            sections = [
                OutlineDraftSection(
                    id=s.id,
                    title=s.title,
                    content=s.content,
                    source_type=s.source_type,
                    source_ids=s.source_ids,
                )
                for s in parsed.sections
            ]
            return OutlineDraft(sections=sections)
        except (DeepSeekError, ValidationError, ValueError, TypeError) as e:
            logger.warning(f"DeepSeek 大纲生成失败，降级到 LocalRule: {e}")
            return self._fallback.generate(context)

    def stream_generate(
        self, context: dict[str, Any]
    ) -> Generator[str, None, None]:
        """流式调用 DeepSeek 生成大纲，逐 chunk yield content。

        SPEC 0019 大纲生成流式化。

        降级策略（复用 SPEC 0018 模式）：
        - 首 chunk 前失败：降级到 LocalRule，一次性 yield fallback JSON（拆分多 chunk 模拟流式）
        - 中途失败：已 yield 的 chunks 保留，抛 DeepSeekError 由上层 service 转 StreamErrorEvent
        - JSON 校验失败：流式完成后校验失败，抛 DeepSeekError（由 service 层转 error 事件，不保存 Outline）

        yield 内容：LLM 流式 chunk（首 chunk 后保证至少有一个 chunk）
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
        except Exception as e:
            if not started:
                # 首 chunk 前失败，降级到 LocalRule
                logger.warning(
                    f"DeepSeek 流式大纲失败，降级到 LocalRule: {e}"
                )
                fallback_draft = self._fallback.generate(context)
                # 手动序列化为 JSON（OutlineDraft 是 dataclass，不是 Pydantic 模型）
                fallback_json = json.dumps({
                    "sections": [
                        {
                            "id": s.id,
                            "title": s.title,
                            "content": s.content,
                            "source_type": s.source_type,
                            "source_ids": s.source_ids,
                        }
                        for s in fallback_draft.sections
                    ]
                }, ensure_ascii=False)
                # 拆分为多个 chunk 模拟流式（按 50 字符拆分）
                for i in range(0, len(fallback_json), 50):
                    yield fallback_json[i:i + 50]
                return
            # 中途失败，已 yield 的 chunks 保留，抛异常由上层 service 转 StreamErrorEvent
            raise

        # 流式完成，校验完整 JSON
        raw = "".join(chunks)
        try:
            self._parse_and_validate(raw)
        except DeepSeekError:
            raise
        except Exception as e:
            raise DeepSeekError(
                code="DEEPSEEK_JSON_PARSE_ERROR",
                message=f"流式生成的 JSON 校验失败: {e}",
            ) from e

    def _parse_and_validate(self, raw: str) -> DeepSeekOutlineResponse:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise DeepSeekError(
                code="DEEPSEEK_JSON_PARSE_ERROR",
                message=f"LLM 返回 JSON 解析失败: {e}",
            ) from e
        return DeepSeekOutlineResponse.model_validate(data)
