"""DeepSeek LLM 驱动的证据卡片提取提供者。

调用 DeepSeek API 从已解析文档文本中提取结构化证据卡片候选。
LLM 调用失败时降级到 LocalRuleEvidenceCardProvider。
"""

import json
import logging

from pydantic import BaseModel, ValidationError

from app.infrastructure.llm.deepseek_client import DeepSeekClient, DeepSeekError
from app.modules.llm.evidence_card_provider import (
    EvidenceCardDraft,
    LocalRuleEvidenceCardProvider,
)


logger = logging.getLogger(__name__)


# --- Pydantic 结构化输出校验模型 ---


class DeepSeekEvidenceCard(BaseModel):
    """LLM 返回的单个证据卡片（用于校验）。"""

    summary: str
    evidence_type: str
    locator: str
    source_quote: str | None = None


class DeepSeekEvidenceResponse(BaseModel):
    """LLM 返回的证据卡片列表（用于校验）。"""

    cards: list[DeepSeekEvidenceCard]


# --- Prompt 构造 ---


_SYSTEM_PROMPT = """你是一个资料分析助手。你的任务是从已解析的文档文本中提取关键证据卡片。

输出要求：
1. 必须返回 JSON 格式：{"cards": [...]}
2. 每个证据卡片包含：
   - summary: 内容摘要（简短，1-2 句）
   - evidence_type: 证据类型（BACKGROUND/METHOD/RESULT/CONCLUSION/LIMITATION/REFERENCE）
   - locator: 来源定位（章节、段落或位置描述）
   - source_quote: 原文引用（可选，精确引用原文片段）

提取原则：
- 只提取有价值的证据，避免冗余
- 每个卡片应独立可引用
- 来源定位要准确
- 不编造原文中不存在的内容"""


def _build_user_prompt(text: str) -> str:
    """构造用户消息。"""
    # 截断过长文本，避免超出 token 限制
    truncated = text[:8000] if len(text) > 8000 else text
    return f"""请从以下文档文本中提取证据卡片：

---
{truncated}
---

请返回 JSON 格式的证据卡片列表。"""


# --- DeepSeek Provider 实现 ---


class DeepSeekEvidenceCardProvider:
    """DeepSeek LLM 驱动的证据卡片提取提供者。"""

    def __init__(
        self,
        client: DeepSeekClient,
        fallback: LocalRuleEvidenceCardProvider | None = None,
        temperature: float = 0.3,
    ):
        self._client = client
        self._fallback = fallback or LocalRuleEvidenceCardProvider()
        self._temperature = temperature

    def source_label(self) -> str:
        return "DEEPSEEK"

    def draft(self, text: str) -> list[EvidenceCardDraft]:
        """调用 DeepSeek 提取证据卡片，失败时降级。"""
        try:
            raw = self._client.chat_completion(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_prompt(text)},
                ],
                response_format={"type": "json_object"},
                temperature=self._temperature,
            )
            parsed = self._parse_and_validate(raw)
            return [self._to_draft(c) for c in parsed.cards]
        except (DeepSeekError, ValidationError, ValueError, TypeError) as e:
            logger.warning(f"DeepSeek 证据卡片提取失败，降级到 LocalRule: {e}")
            return self._fallback.draft(text)

    def _parse_and_validate(self, raw: str) -> DeepSeekEvidenceResponse:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise DeepSeekError(
                code="DEEPSEEK_JSON_PARSE_ERROR",
                message=f"LLM 返回 JSON 解析失败: {e}",
            ) from e
        return DeepSeekEvidenceResponse.model_validate(data)

    def _to_draft(self, card: DeepSeekEvidenceCard) -> EvidenceCardDraft:
        return EvidenceCardDraft(
            summary=card.summary,
            evidence_type=card.evidence_type,
            locator=card.locator,
            source_quote=card.source_quote,
        )
