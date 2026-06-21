"""基于解析文档位置块生成可校验的本地证据候选。"""

from app.modules.sources.contracts import EvidenceDraftCandidate, EvidenceDraftDocument
from app.modules.sources.status import EvidenceType


def _classify(text: str) -> EvidenceType:
    lowered = text.lower()
    if any(word in lowered for word in ["方法", "步骤", "method", "procedure"]):
        return EvidenceType.METHOD
    if any(word in lowered for word in ["数据来源", "数据集", "样本", "dataset"]):
        return EvidenceType.DATA_SOURCE
    if any(word in lowered for word in ["结果", "发现", "result", "finding"]):
        return EvidenceType.RESULT
    if any(word in lowered for word in ["局限", "不足", "limitation"]):
        return EvidenceType.LIMITATION
    if any(word in lowered for word in ["定义", "概念", "definition"]):
        return EvidenceType.DEFINITION
    if any(word in lowered for word in ["参考", "文献", "reference"]):
        return EvidenceType.REFERENCE
    if any(word in lowered for word in ["指标", "metric", "准确率", "召回率"]):
        return EvidenceType.METRIC
    return EvidenceType.BACKGROUND


def _located_excerpts(document: EvidenceDraftDocument):
    blocks = document.location_map.get("blocks", [])
    if isinstance(blocks, list):
        for block in blocks:
            if not isinstance(block, dict):
                continue
            start = block.get("start")
            end = block.get("end")
            label = block.get("label")
            if not isinstance(start, int) or not isinstance(end, int) or not isinstance(label, str):
                continue
            excerpt = document.parsed_text[start:end].strip()
            if excerpt:
                yield label, excerpt


class LocalRuleEvidenceDraftProvider:
    def source_label(self) -> str:
        return "LOCAL_RULE"

    def draft(self, document: EvidenceDraftDocument) -> list[dict]:
        located = list(_located_excerpts(document))
        if not located and document.parsed_text.strip():
            located = [("全文", document.parsed_text.strip())]

        candidates: list[dict] = []
        for index, (label, excerpt) in enumerate(located):
            quote = excerpt[:300].strip()
            candidate = EvidenceDraftCandidate(
                summary=excerpt[:200].strip(),
                source_quote=quote,
                evidence_type=(EvidenceType.BACKGROUND if index < 2 else _classify(excerpt)),
                location_label=label,
                relevance_to_requirement="需人工确认与任务单的相关性",
            )
            candidates.append(candidate.model_dump(mode="json"))
        return candidates


class FakeEvidenceDraftProvider(LocalRuleEvidenceDraftProvider):
    def source_label(self) -> str:
        return "MANUAL"
