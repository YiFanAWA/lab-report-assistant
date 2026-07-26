"""DeepSeekEvidenceCardProvider.stream_draft 流式调用单元测试。

SPEC 0020：证据卡片生成流式化。

mock DeepSeekClient.stream_chat_completion 测试：
- 流式成功（多 chunk yield，JSON 校验通过）
- 首 chunk 前失败（降级到 LocalRule，拆分多 chunk 模拟流式）
- 中途失败（已 yield chunks 保留，抛异常由上层处理）
- JSON 校验失败（yield 完所有 chunk 后抛 DeepSeekError）
- 缓存命中（一次性 yield 完整字符串）
- 空响应（无 chunk，抛异常）

测试原则：
- 不调用真实 DeepSeek API
- mock DeepSeekClient.stream_chat_completion 方法
"""

import json
from unittest.mock import MagicMock

import pytest

from app.infrastructure.llm.deepseek_client import DeepSeekClient, DeepSeekError
from app.modules.llm.deepseek_evidence_provider import (
    DeepSeekEvidenceCardProvider,
    DeepSeekEvidenceResponse,
)
from app.modules.llm.evidence_card_provider import (
    LocalRuleEvidenceCardProvider,
    EvidenceCardDraft,
)


def _make_valid_evidence_json() -> str:
    """构造有效的证据卡片 LLM JSON 响应（3 张卡片）。"""
    return json.dumps({
        "cards": [
            {
                "summary": "本研究采用回顾性分析方法。",
                "evidence_type": "METHOD",
                "locator": "第 2 段",
                "source_quote": "采用回顾性分析方法",
            },
            {
                "summary": "结果显示胃病发病率逐年上升。",
                "evidence_type": "RESULT",
                "locator": "第 3 段",
                "source_quote": "发病率逐年上升",
            },
            {
                "summary": "研究存在样本量不足的局限。",
                "evidence_type": "LIMITATION",
                "locator": "第 5 段",
                "source_quote": None,
            },
        ]
    }, ensure_ascii=False)


def _make_mock_client_streaming(
    chunks: list[str] | None = None,
    raises_before_first: Exception | None = None,
    raises_after_first: Exception | None = None,
) -> MagicMock:
    """构造 mock DeepSeekClient，配置 stream_chat_completion 行为。

    参数：
    - chunks: 要 yield 的 chunk 列表
    - raises_before_first: 首 chunk 前抛出（立即抛）
    - raises_after_first: yield 第一个 chunk 后抛
    """
    client = MagicMock(spec=DeepSeekClient)

    def _gen():
        if raises_before_first is not None:
            raise raises_before_first
        if chunks:
            yield chunks[0]
            if raises_after_first is not None:
                raise raises_after_first
            for c in chunks[1:]:
                yield c

    client.stream_chat_completion.side_effect = lambda **kwargs: _gen()
    return client


# ============================================================
# 流式成功场景
# ============================================================


class TestStreamDraftSuccess:
    """流式成功场景。"""

    def test_多chunk按序yield(self):
        """多 chunk 应按序 yield，拼接后为完整 JSON。"""
        full_json = _make_valid_evidence_json()
        chunks = [full_json[i:i + 50] for i in range(0, len(full_json), 50)]
        client = _make_mock_client_streaming(chunks=chunks)
        provider = DeepSeekEvidenceCardProvider(client=client)

        result = list(provider.stream_draft("文档文本"))

        assert result == chunks
        assert "".join(result) == full_json

    def test_单chunk也能流式(self):
        """单个 chunk（完整 JSON）也能正常 yield。"""
        full_json = _make_valid_evidence_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekEvidenceCardProvider(client=client)

        result = list(provider.stream_draft("文档文本"))

        assert result == [full_json]

    def test_source_label返回DEEPSEEK(self):
        """source_label 应返回 DEEPSEEK。"""
        client = _make_mock_client_streaming(chunks=[_make_valid_evidence_json()])
        provider = DeepSeekEvidenceCardProvider(client=client)
        assert provider.source_label() == "DEEPSEEK"


# ============================================================
# 首 chunk 前失败降级场景
# ============================================================


class TestStreamDraftFirstChunkFallback:
    """首 chunk 前失败降级场景。"""

    def test_首chunk前失败降级到LocalRule(self):
        """LLM 调用立即抛 DeepSeekError，应降级到 LocalRule 拆分多 chunk。"""
        client = _make_mock_client_streaming(
            raises_before_first=DeepSeekError(
                code="DEEPSEEK_AUTH_ERROR", message="鉴权失败"
            )
        )
        fallback = LocalRuleEvidenceCardProvider()
        provider = DeepSeekEvidenceCardProvider(client=client, fallback=fallback)

        result = list(provider.stream_draft("胃病数据研究背景..."))

        # 应 yield 多个 chunk（fallback JSON 拆分）
        assert len(result) > 0
        full = "".join(result)
        # 拼接后应能解析为有效 JSON（LocalRule EvidenceCardDraft 的 JSON）
        parsed = json.loads(full)
        assert "cards" in parsed

    def test_首chunk前超时也降级(self):
        """首 chunk 前超时也应降级到 LocalRule。"""
        client = _make_mock_client_streaming(
            raises_before_first=DeepSeekError(
                code="DEEPSEEK_TIMEOUT", message="超时"
            )
        )
        provider = DeepSeekEvidenceCardProvider(client=client)

        result = list(provider.stream_draft("文档内容"))

        assert len(result) > 0
        full = "".join(result)
        assert json.loads(full) is not None

    def test_降级后内容包含多张卡片(self):
        """降级到 LocalRule 后，内容应包含多张卡片（list 非空）。"""
        client = _make_mock_client_streaming(
            raises_before_first=DeepSeekError(
                code="DEEPSEEK_AUTH_ERROR", message="鉴权失败"
            )
        )
        fallback = LocalRuleEvidenceCardProvider()
        provider = DeepSeekEvidenceCardProvider(client=client, fallback=fallback)

        # 多段落文本（每段 >= 30 字符），LocalRule 会按段落生成多张卡片
        text = (
            "背景：本节介绍胃病数据的研究背景与意义，包含流行病学统计和疾病分类说明。\n"
            "方法：采用描述性统计方法和可视化技术分析数据，包括均值、标准差和分布检验。\n"
            "结果：分析显示关键变量之间存在显著相关，胃病发病率呈现上升趋势。"
        )
        result = list(provider.stream_draft(text))
        full = "".join(result)
        parsed = json.loads(full)

        # LocalRule 应至少生成 1 张卡片
        assert "cards" in parsed
        assert len(parsed["cards"]) >= 1
        # 每张卡片应包含必要字段
        for card in parsed["cards"]:
            assert "summary" in card
            assert "evidence_type" in card
            assert "locator" in card


# ============================================================
# 中途失败场景
# ============================================================


class TestStreamDraftMidStreamFailure:
    """中途失败场景。"""

    def test_中途失败抛异常且已yield保留(self):
        """第一个 chunk yield 成功后抛 DeepSeekError，应抛异常由上层处理。"""
        client = _make_mock_client_streaming(
            chunks=["部分内容"],
            raises_after_first=DeepSeekError(
                code="DEEPSEEK_HTTP_ERROR", message="中断"
            ),
        )
        provider = DeepSeekEvidenceCardProvider(client=client)

        gen = provider.stream_draft("文档")
        first = next(gen)
        assert first == "部分内容"
        # 之后应抛异常
        with pytest.raises(DeepSeekError):
            next(gen)

    def test_中途失败不降级到LocalRule(self):
        """中途失败不应降级到 LocalRule（只首 chunk 前降级）。"""
        client = _make_mock_client_streaming(
            chunks=["部分"],
            raises_after_first=DeepSeekError(
                code="DEEPSEEK_HTTP_ERROR", message="中断"
            ),
        )
        provider = DeepSeekEvidenceCardProvider(client=client)

        chunks = []
        with pytest.raises(DeepSeekError):
            for c in provider.stream_draft("文档"):
                chunks.append(c)

        # 只 yield 了第一个 chunk，没有 LocalRule fallback 内容
        assert chunks == ["部分"]


# ============================================================
# JSON 校验场景
# ============================================================


class TestStreamDraftJSONValidation:
    """JSON 校验场景。"""

    def test_流式完成后JSON校验失败抛异常(self):
        """LLM 返回不完整 JSON，流式完成后校验失败应抛 DeepSeekError。"""
        client = _make_mock_client_streaming(chunks=["{invalid json"])
        provider = DeepSeekEvidenceCardProvider(client=client)

        gen = provider.stream_draft("文档")
        # 第一个 chunk 应成功 yield
        first = next(gen)
        assert first == "{invalid json"
        # 流结束后应抛 DeepSeekError（JSON 校验失败）
        with pytest.raises(DeepSeekError):
            next(gen, None)

    def test_有效JSON不抛异常(self):
        """有效的证据卡片 JSON 流式完成后不应抛异常。"""
        full_json = _make_valid_evidence_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekEvidenceCardProvider(client=client)

        result = list(provider.stream_draft("文档"))

        # 不抛异常，正常结束
        assert len(result) == 1
        assert result[0] == full_json


# ============================================================
# 边界场景
# ============================================================


class TestStreamDraftEdgeCases:
    """边界场景。"""

    def test_空chunk列表抛异常(self):
        """LLM 返回空 chunk 列表（无内容），应抛 DeepSeekError（JSON 校验失败）。"""
        client = _make_mock_client_streaming(chunks=[])
        provider = DeepSeekEvidenceCardProvider(client=client)

        gen = provider.stream_draft("文档")
        # 空 chunks 会引发 JSON 校验失败（空字符串不是有效 JSON）
        with pytest.raises(DeepSeekError):
            list(gen)

    def test_缓存命中一次性yield(self):
        """缓存命中时，stream_chat_completion 一次性 yield 完整字符串。"""
        full_json = _make_valid_evidence_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekEvidenceCardProvider(client=client)

        result = list(provider.stream_draft("文档"))

        # 一次性 yield 完整 JSON
        assert len(result) == 1
        assert result[0] == full_json

    def test_空text也能调用(self):
        """空 text 也能调用 stream_draft（由 LLM 处理）。"""
        full_json = _make_valid_evidence_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekEvidenceCardProvider(client=client)

        result = list(provider.stream_draft(""))

        assert len(result) == 1
        assert result[0] == full_json
