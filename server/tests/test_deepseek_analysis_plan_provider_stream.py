"""DeepSeekAnalysisPlanProvider.stream_generate 流式调用单元测试。

SPEC 0021：分析方案生成流式化。

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
from app.infrastructure.parsers.dataset_parser import DatasetProfile, FieldProfile
from app.modules.llm.deepseek_analysis_plan_provider import (
    DeepSeekAnalysisPlanProvider,
    DeepSeekAnalysisPlanResponse,
)
from app.modules.llm.analysis_plan_provider import (
    LocalRuleAnalysisPlanProvider,
    AnalysisPlanDraft,
)


def _make_profile() -> DatasetProfile:
    """构造有效的 DatasetProfile（含数值字段和字符串字段，让 LocalRule 生成非空方案）。"""
    return DatasetProfile(
        row_count=100,
        column_count=3,
        complete_row_count=85,
        incomplete_row_count=15,
        duplicate_row_count=2,
        field_profiles=[
            FieldProfile(
                name="age",
                inferred_type="int",
                non_null_count=95,
                null_count=5,
                null_rate=0.05,
                unique_count=63,
                sample_values=["25", "30", "45"],
                min_value=18.0,
                max_value=80.0,
                mean_value=45.0,
            ),
            FieldProfile(
                name="gender",
                inferred_type="string",
                non_null_count=98,
                null_count=2,
                null_rate=0.02,
                unique_count=2,
                sample_values=["男", "女"],
            ),
            FieldProfile(
                name="diagnosis",
                inferred_type="string",
                non_null_count=100,
                null_count=0,
                null_rate=0.0,
                unique_count=5,
                sample_values=["胃炎", "胃溃疡"],
            ),
        ],
        quality_score=85.0,
    )


def _make_valid_analysis_plan_json() -> str:
    """构造有效的分析方案 LLM JSON 响应（含 cleaning/analysis/chart 三个列表）。"""
    return json.dumps({
        "cleaning_plan": [
            {
                "field": "age",
                "issue_type": "MISSING_VALUE",
                "action": "用中位数填充缺失值",
                "reason": "数值字段，中位数对异常值稳健",
            },
            {
                "field": "gender",
                "issue_type": "MISSING_VALUE",
                "action": "用众数填充缺失值",
                "reason": "字符串字段，众数可保留信息",
            },
        ],
        "analysis_plan": [
            {
                "analysis_type": "DESCRIPTIVE_STATISTICS",
                "target_fields": "age",
                "method": "计算均值、中位数、标准差",
                "expected_output": "描述性统计表",
                "dependencies": ["age"],
            },
            {
                "analysis_type": "GROUP_STATISTICS",
                "target_fields": "gender 分组 vs age",
                "method": "按性别分组聚合",
                "expected_output": "分组统计表",
                "dependencies": ["gender", "age"],
            },
        ],
        "chart_plan": [
            {
                "chart_type": "HISTOGRAM",
                "title": "age 分布直方图",
                "data_fields": ["age"],
                "description": "展示年龄分布",
            },
            {
                "chart_type": "BAR",
                "title": "gender 频次柱状图",
                "data_fields": ["gender"],
                "description": "展示性别分布",
            },
        ],
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


class TestStreamGenerateSuccess:
    """流式成功场景。"""

    def test_多chunk按序yield(self):
        """多 chunk 应按序 yield，拼接后为完整 JSON。"""
        full_json = _make_valid_analysis_plan_json()
        chunks = [full_json[i:i + 50] for i in range(0, len(full_json), 50)]
        client = _make_mock_client_streaming(chunks=chunks)
        provider = DeepSeekAnalysisPlanProvider(client=client)

        result = list(provider.stream_generate(_make_profile()))

        assert result == chunks
        assert "".join(result) == full_json

    def test_单chunk也能流式(self):
        """单个 chunk（完整 JSON）也能正常 yield。"""
        full_json = _make_valid_analysis_plan_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekAnalysisPlanProvider(client=client)

        result = list(provider.stream_generate(_make_profile()))

        assert result == [full_json]

    def test_source_label返回DEEPSEEK(self):
        """source_label 应返回 DEEPSEEK。"""
        client = _make_mock_client_streaming(chunks=[_make_valid_analysis_plan_json()])
        provider = DeepSeekAnalysisPlanProvider(client=client)
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
        fallback = LocalRuleAnalysisPlanProvider()
        provider = DeepSeekAnalysisPlanProvider(client=client, fallback=fallback)

        result = list(provider.stream_generate(_make_profile()))

        # 应 yield 多个 chunk（fallback JSON 拆分）
        assert len(result) > 0
        full = "".join(result)
        # 拼接后应能解析为有效 JSON
        parsed = json.loads(full)
        assert "cleaning_plan" in parsed
        assert "analysis_plan" in parsed
        assert "chart_plan" in parsed

    def test_首chunk前超时也降级(self):
        """首 chunk 前超时也应降级到 LocalRule。"""
        client = _make_mock_client_streaming(
            raises_before_first=DeepSeekError(
                code="DEEPSEEK_TIMEOUT", message="超时"
            )
        )
        provider = DeepSeekAnalysisPlanProvider(client=client)

        result = list(provider.stream_generate(_make_profile()))

        assert len(result) > 0
        full = "".join(result)
        assert json.loads(full) is not None

    def test_降级后内容包含三个方案列表(self):
        """降级到 LocalRule 后，内容应包含 cleaning/analysis/chart 三个非空列表。"""
        client = _make_mock_client_streaming(
            raises_before_first=DeepSeekError(
                code="DEEPSEEK_AUTH_ERROR", message="鉴权失败"
            )
        )
        fallback = LocalRuleAnalysisPlanProvider()
        provider = DeepSeekAnalysisPlanProvider(client=client, fallback=fallback)

        result = list(provider.stream_generate(_make_profile()))
        full = "".join(result)
        parsed = json.loads(full)

        # LocalRule 应基于字段类型生成方案
        assert "cleaning_plan" in parsed
        assert "analysis_plan" in parsed
        assert "chart_plan" in parsed
        # age 是数值字段，应触发描述性统计和直方图
        assert len(parsed["analysis_plan"]) >= 1
        assert len(parsed["chart_plan"]) >= 1


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
        provider = DeepSeekAnalysisPlanProvider(client=client)

        gen = provider.stream_generate(_make_profile())
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
        provider = DeepSeekAnalysisPlanProvider(client=client)

        chunks = []
        with pytest.raises(DeepSeekError):
            for c in provider.stream_generate(_make_profile()):
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
        provider = DeepSeekAnalysisPlanProvider(client=client)

        gen = provider.stream_generate(_make_profile())
        # 第一个 chunk 应成功 yield
        first = next(gen)
        assert first == "{invalid json"
        # 流结束后应抛 DeepSeekError（JSON 校验失败）
        with pytest.raises(DeepSeekError):
            next(gen, None)

    def test_有效JSON不抛异常(self):
        """有效的分析方案 JSON 流式完成后不应抛异常。"""
        full_json = _make_valid_analysis_plan_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekAnalysisPlanProvider(client=client)

        result = list(provider.stream_generate(_make_profile()))

        # 不抛异常，正常结束
        assert len(result) == 1
        assert result[0] == full_json


# ============================================================
# 边界场景
# ============================================================


class TestStreamGenerateEdgeCases:
    """边界场景。"""

    def test_空chunk列表抛异常(self):
        """LLM 返回空 chunk 列表（无内容），应抛 DeepSeekError（JSON 校验失败）。"""
        client = _make_mock_client_streaming(chunks=[])
        provider = DeepSeekAnalysisPlanProvider(client=client)

        gen = provider.stream_generate(_make_profile())
        # 空 chunks 会引发 JSON 校验失败（空字符串不是有效 JSON）
        with pytest.raises(DeepSeekError):
            list(gen)

    def test_缓存命中一次性yield(self):
        """缓存命中时，stream_chat_completion 一次性 yield 完整字符串。"""
        full_json = _make_valid_analysis_plan_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekAnalysisPlanProvider(client=client)

        result = list(provider.stream_generate(_make_profile()))

        # 一次性 yield 完整 JSON
        assert len(result) == 1
        assert result[0] == full_json
