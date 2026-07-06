"""证据卡片候选提供者。

不依赖任何外部模型、不调用 DeepSeek。
基于已解析文档的段落和关键词规则生成证据卡片候选。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EvidenceCardDraft:
    """证据卡片候选（提供者产出，非业务实体）。"""

    summary: str
    evidence_type: str
    locator: str
    source_quote: str | None


class EvidenceCardDraftProvider(ABC):
    """证据卡片候选提供者抽象基类。"""

    @abstractmethod
    def draft(self, text: str) -> list[EvidenceCardDraft]:
        """从已解析文本生成证据卡片候选。"""

    @abstractmethod
    def source_label(self) -> str:
        """返回候选来源标签（用于写入 candidate_source）。"""


# --- 关键词分类规则 ---

# 关键词列表顺序决定优先级：先匹配者先归类。
_EVIDENCE_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("BACKGROUND", ["背景", "介绍", "概述", "background", "introduction"]),
    ("METHOD", ["方法", "methodology", "method", "步骤", "采用"]),
    ("RESULT", ["结果", "result", "发现", "表明", "显示"]),
    ("CONCLUSION", ["结论", "conclusion", "综上", "总结"]),
    ("LIMITATION", ["局限", "limitation", "不足", "缺陷"]),
    ("REFERENCE", ["参考", "reference", "引用", "文献"]),
]


def _classify_evidence_type(paragraph: str) -> str:
    """根据关键词匹配分类证据类型。"""
    lowered = paragraph.lower()
    for evidence_type, keywords in _EVIDENCE_TYPE_RULES:
        for keyword in keywords:
            if keyword in lowered:
                return evidence_type
    return "BACKGROUND"


def _split_paragraphs(text: str) -> list[str]:
    """将文本按段落分割（双换行优先，否则按单换行）。"""
    if not text:
        return []
    # 优先按双换行分段
    if "\n\n" in text:
        paragraphs = text.split("\n\n")
    else:
        paragraphs = text.split("\n")
    return [p.strip() for p in paragraphs if p.strip()]


class LocalRuleEvidenceCardProvider(EvidenceCardDraftProvider):
    """基于段落和关键词规则生成证据卡片候选。"""

    def source_label(self) -> str:
        return "LOCAL_RULE"

    def draft(self, text: str) -> list[EvidenceCardDraft]:
        paragraphs = _split_paragraphs(text)
        drafts: list[EvidenceCardDraft] = []
        for index, paragraph in enumerate(paragraphs, start=1):
            if len(paragraph) < 30:
                continue
            evidence_type = _classify_evidence_type(paragraph)
            locator = f"第{index}段"
            source_quote = paragraph[:100]
            drafts.append(
                EvidenceCardDraft(
                    summary=paragraph,
                    evidence_type=evidence_type,
                    locator=locator,
                    source_quote=source_quote,
                )
            )
            if len(drafts) >= 10:
                break
        return drafts


class FakeEvidenceCardProvider(EvidenceCardDraftProvider):
    """测试替身 —— 返回固定 3 张确定性候选。"""

    def source_label(self) -> str:
        return "LOCAL_RULE"

    def draft(self, text: str) -> list[EvidenceCardDraft]:
        return [
            EvidenceCardDraft(
                summary="背景：本节介绍实验背景与研究意义。",
                evidence_type="BACKGROUND",
                locator="第1段",
                source_quote="背景：本节介绍实验背景与研究意义。",
            ),
            EvidenceCardDraft(
                summary="方法：采用描述性统计和可视化方法分析数据。",
                evidence_type="METHOD",
                locator="第2段",
                source_quote="方法：采用描述性统计和可视化方法分析数据。",
            ),
            EvidenceCardDraft(
                summary="结果：分析显示关键变量之间存在显著相关。",
                evidence_type="RESULT",
                locator="第3段",
                source_quote="结果：分析显示关键变量之间存在显著相关。",
            ),
        ]
