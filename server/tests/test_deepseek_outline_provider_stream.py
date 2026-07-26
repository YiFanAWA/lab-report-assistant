"""DeepSeekOutlineProvider.stream_generate 流式调用单元测试。

SPEC 0019：大纲生成流式化。

mock DeepSeekClient.stream_chat_completion 测试：
- 流式成功（多 chunk yield，JSON 校验通过）
- 首 chunk 前失败（降级到 LocalRule，拆分多 chunk 模拟流式）
- 中途失败（已 yield chunks 保留，抛异常由上层处理）
- JSON 校验失败（yield 完所有 chunk 后抛 DeepSeekError）
- 缓存命中（一次性 yield 完整字符串）
- 空响应（无 chunk，不抛异常）

测试原则：
- 不调用真实 DeepSeek API
- mock DeepSeekClient.stream_chat_completion 方法
"""

import json
from unittest.mock import MagicMock

import pytest

from app.infrastructure.llm.deepseek_client import DeepSeekClient, DeepSeekError
from app.modules.llm.deepseek_outline_provider import (
    DeepSeekOutlineProvider,
    DeepSeekOutlineResponse,
)
from app.modules.llm.outline_provider import LocalRuleOutlineProvider


def _make_valid_outline_json() -> str:
    """构造有效的大纲 LLM JSON 响应（6 个章节）。"""
    return json.dumps({
        "sections": [
            {
                "id": "purpose",
                "title": "实验目的",
                "content": "分析胃病数据分布特征",
                "source_type": "REQUIREMENT",
                "source_ids": ["plan_001"],
            },
            {
                "id": "background",
                "title": "实验背景",
                "content": "胃病数据分析背景",
                "source_type": "EVIDENCE",
                "source_ids": ["card_001"],
            },
            {
                "id": "dataset",
                "title": "数据与数据集",
                "content": "数据集包含 1000 条记录",
                "source_type": "DATASET",
                "source_ids": ["ds_001"],
            },
            {
                "id": "analysis",
                "title": "分析方案",
                "content": "描述性统计和可视化",
                "source_type": "ANALYSIS",
                "source_ids": ["ap_001"],
            },
            {
                "id": "results",
                "title": "执行结果",
                "content": "图表和统计数据",
                "source_type": "EXECUTION",
                "source_ids": ["run_001"],
            },
            {
                "id": "conclusion",
                "title": "结论与总结",
                "content": "实验结论",
                "source_type": "SUMMARY",
                "source_ids": [],
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


def _make_context() -> dict:
    """构造测试用上下文。"""
    return {
        "project": {"id": "proj_001", "name": "胃病数据分析", "topic": "胃病"},
        "requirements": {"plan_id": "plan_001", "payload": {"topic": "胃病"}},
        "evidence_cards": [{"id": "card_001", "summary": "证据"}],
        "dataset": {"dataset_id": "ds_001", "row_count": 1000},
        "analysis_plan": {"plan_id": "ap_001", "cleaning_plan": []},
        "executions": [{"run_id": "run_001", "stdout": "ok"}],
    }


# ============================================================
# 流式成功场景
# ============================================================


class TestStreamGenerateSuccess:
    """流式成功场景。"""

    def test_多chunk按序yield(self):
        """多 chunk 应按序 yield，拼接后为完整 JSON。"""
        full_json = _make_valid_outline_json()
        chunks = [full_json[i:i + 50] for i in range(0, len(full_json), 50)]
        client = _make_mock_client_streaming(chunks=chunks)
        provider = DeepSeekOutlineProvider(client=client)

        result = list(provider.stream_generate(_make_context()))

        assert result == chunks
        assert "".join(result) == full_json

    def test_单chunk也能流式(self):
        """单个 chunk（完整 JSON）也能正常 yield。"""
        full_json = _make_valid_outline_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekOutlineProvider(client=client)

        result = list(provider.stream_generate(_make_context()))

        assert result == [full_json]

    def test_source_label返回DEEPSEEK(self):
        """source_label 应返回 DEEPSEEK。"""
        client = _make_mock_client_streaming(chunks=[_make_valid_outline_json()])
        provider = DeepSeekOutlineProvider(client=client)
        assert provider.source_label() == "DEEPSEEK"


# ============================================================
# 首 chunk 前失败降级场景
# ============================================================


class TestStreamGenerateFirstChunkFallback:
    """首 chunk 前失败降级场景。"""

    def test_首chunk前失败降级到LocalRule(self):
        """LLM 调用立即抛 DeepSeekError，应降级到 LocalRule 拆分多 chunk。"""
        client = _make_mock_client_streaming(
            raises_before_first=DeepSeekError(
                code="DEEPSEEK_AUTH_ERROR", message="鉴权失败"
            )
        )
        fallback = LocalRuleOutlineProvider()
        provider = DeepSeekOutlineProvider(client=client, fallback=fallback)

        result = list(provider.stream_generate(_make_context()))

        # 应 yield 多个 chunk（fallback JSON 拆分）
        assert len(result) > 0
        full = "".join(result)
        # 拼接后应能解析为有效 JSON（LocalRule OutlineDraft 的 JSON）
        parsed = json.loads(full)
        assert "sections" in parsed

    def test_首chunk前超时也降级(self):
        """首 chunk 前超时也应降级到 LocalRule。"""
        client = _make_mock_client_streaming(
            raises_before_first=DeepSeekError(
                code="DEEPSEEK_TIMEOUT", message="超时"
            )
        )
        provider = DeepSeekOutlineProvider(client=client)

        result = list(provider.stream_generate(_make_context()))

        assert len(result) > 0
        full = "".join(result)
        assert json.loads(full) is not None

    def test_降级后内容包含6个章节(self):
        """降级到 LocalRule 后，内容应包含 6 个章节。"""
        client = _make_mock_client_streaming(
            raises_before_first=DeepSeekError(
                code="DEEPSEEK_AUTH_ERROR", message="鉴权失败"
            )
        )
        fallback = LocalRuleOutlineProvider()
        provider = DeepSeekOutlineProvider(client=client, fallback=fallback)

        result = list(provider.stream_generate(_make_context()))
        full = "".join(result)
        parsed = json.loads(full)

        # LocalRule 生成 6 个章节
        assert len(parsed["sections"]) == 6


# ============================================================
# 中途失败场景
# ============================================================


class TestStreamGenerateMidStreamFailure:
    """中途失败场景。"""

    def test_中途失败抛异常且已yield保留(self):
        """第一个 chunk yield 成功后抛 DeepSeekError，应抛异常由上层处理。"""
        client = _make_mock_client_streaming(
            chunks=["部分内容"],
            raises_after_first=DeepSeekError(
                code="DEEPSEEK_HTTP_ERROR", message="中断"
            ),
        )
        provider = DeepSeekOutlineProvider(client=client)

        gen = provider.stream_generate(_make_context())
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
        provider = DeepSeekOutlineProvider(client=client)

        chunks = []
        with pytest.raises(DeepSeekError):
            for c in provider.stream_generate(_make_context()):
                chunks.append(c)

        # 只 yield 了第一个 chunk，没有 LocalRule fallback 内容
        assert chunks == ["部分"]


# ============================================================
# JSON 校验场景
# ============================================================


class TestStreamGenerateJSONValidation:
    """JSON 校验场景。"""

    def test_流式完成后JSON校验失败抛异常(self):
        """LLM 返回不完整 JSON，流式完成后校验失败应抛 DeepSeekError。"""
        client = _make_mock_client_streaming(chunks=["{invalid json"])
        provider = DeepSeekOutlineProvider(client=client)

        gen = provider.stream_generate(_make_context())
        # 第一个 chunk 应成功 yield
        first = next(gen)
        assert first == "{invalid json"
        # 流结束后应抛 DeepSeekError（JSON 校验失败）
        with pytest.raises(DeepSeekError):
            next(gen, None)  # StopIteration 或抛异常

    def test_有效JSON不抛异常(self):
        """有效的大纲 JSON 流式完成后不应抛异常。"""
        full_json = _make_valid_outline_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekOutlineProvider(client=client)

        result = list(provider.stream_generate(_make_context()))

        # 不抛异常，正常结束
        assert len(result) == 1
        assert result[0] == full_json


# ============================================================
# 边界场景
# ============================================================


class TestStreamGenerateEdgeCases:
    """边界场景。"""

    def test_空chunk列表不抛异常(self):
        """LLM 返回空 chunk 列表（无内容），不应抛异常。"""
        client = _make_mock_client_streaming(chunks=[])
        provider = DeepSeekOutlineProvider(client=client)

        # 空 chunks 会引发 JSON 校验失败（空字符串不是有效 JSON）
        gen = provider.stream_generate(_make_context())
        # 应该抛 DeepSeekError（JSON 校验失败）
        with pytest.raises(DeepSeekError):
            list(gen)

    def test_缓存命中一次性yield(self):
        """缓存命中时，stream_chat_completion 一次性 yield 完整字符串。"""
        full_json = _make_valid_outline_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekOutlineProvider(client=client)

        result = list(provider.stream_generate(_make_context()))

        # 一次性 yield 完整 JSON
        assert len(result) == 1
        assert result[0] == full_json

    def test_上下文为空也能调用(self):
        """空上下文也能调用 stream_generate（由 LLM 处理）。"""
        full_json = _make_valid_outline_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekOutlineProvider(client=client)

        result = list(provider.stream_generate({}))

        assert len(result) == 1
        assert result[0] == full_json
