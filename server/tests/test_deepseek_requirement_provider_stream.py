"""DeepSeekRequirementDraftProvider.stream_draft 流式调用单元测试。

mock DeepSeekClient.stream_chat_completion 测试：
- 流式成功（多 chunk yield，JSON 校验通过）
- 首 chunk 前失败（降级到 LocalRule，一次性 yield fallback JSON 拆分多 chunk）
- 中途失败（已 yield chunks 保留，抛异常由上层处理）
- JSON 校验失败（yield 完所有 chunk 后抛 DeepSeekError）
- LocalRule provider 不支持流式（has stream_draft 判断）

测试原则：
- 不调用真实 DeepSeek API
- mock DeepSeekClient.stream_chat_completion 方法
"""

import json
from unittest.mock import MagicMock

import pytest

from app.infrastructure.llm.deepseek_client import DeepSeekClient, DeepSeekError
from app.modules.llm.deepseek_requirement_provider import (
    DeepSeekRequirementDraftProvider,
    DeepSeekRequirementResponse,
)
from app.modules.llm.local_rule_provider import LocalRuleRequirementDraftProvider


def _make_valid_response_json() -> str:
    """构造有效的任务单 LLM JSON 响应。"""
    return json.dumps({
        "topic": "胃病数据分析",
        "experiment_type": "数据分析与可视化",
        "research_subject": "胃病数据",
        "required_tasks": [
            {
                "title": "数据加载",
                "description": "加载数据集",
                "task_type": "REQUIRED",
                "reason": "必要步骤",
                "source_quote": None,
            }
        ],
        "recommended_tasks": [],
        "optional_tasks": [],
        "out_of_scope_tasks": [],
        "unknown_items": [],
        "data_requirements": ["CSV"],
        "method_requirements": ["描述性统计"],
        "chart_requirements": ["直方图"],
        "report_requirements": ["实验报告"],
        "presentation_requirements": ["PPT"],
        "acceptance_criteria": ["可追溯"],
        "replication_level": {
            "level": "L0",
            "label": "不复刻",
            "supported_in_v1": True,
            "reason": "无复刻要求",
            "suggested_scope": "独立分析",
        },
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


class TestStreamDraftSuccess:
    """流式成功场景。"""

    def test_多chunk按序yield且JSON校验通过(self):
        full_json = _make_valid_response_json()
        # 拆分为多个 chunk
        chunks = [full_json[i:i + 30] for i in range(0, len(full_json), 30)]
        client = _make_mock_client_streaming(chunks=chunks)
        provider = DeepSeekRequirementDraftProvider(client=client)

        result = list(provider.stream_draft("分析胃病数据"))

        # yield 顺序与 chunk 一致
        assert result == chunks
        # 拼接后应能通过校验
        assert "".join(result) == full_json

    def test_source_label返回DEEPSEEK(self):
        client = _make_mock_client_streaming(chunks=[_make_valid_response_json()])
        provider = DeepSeekRequirementDraftProvider(client=client)
        assert provider.source_label() == "DEEPSEEK"


class TestStreamDraftFirstChunkFallback:
    """首 chunk 前失败降级场景。"""

    def test_首chunk前失败降级到LocalRule(self):
        """LLM 调用立即抛 DeepSeekError，应降级到 LocalRule 一次性 yield fallback JSON。"""
        client = _make_mock_client_streaming(
            raises_before_first=DeepSeekError(
                code="DEEPSEEK_AUTH_ERROR", message="鉴权失败"
            )
        )
        fallback = LocalRuleRequirementDraftProvider()
        provider = DeepSeekRequirementDraftProvider(
            client=client, fallback=fallback
        )

        result = list(provider.stream_draft("分析胃病数据"))

        # 应 yield 多个 chunk（fallback JSON 拆分）
        assert len(result) > 0
        full = "".join(result)
        # 拼接后应能解析为有效 JSON（LocalRule payload 的 JSON）
        parsed = json.loads(full)
        assert "topic" in parsed
        assert "required_tasks" in parsed

    def test_首chunk前超时也降级(self):
        client = _make_mock_client_streaming(
            raises_before_first=DeepSeekError(
                code="DEEPSEEK_TIMEOUT", message="超时"
            )
        )
        provider = DeepSeekRequirementDraftProvider(client=client)

        result = list(provider.stream_draft("分析胃病数据"))

        assert len(result) > 0
        # fallback JSON 拆分多 chunk
        full = "".join(result)
        assert json.loads(full) is not None


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
        provider = DeepSeekRequirementDraftProvider(client=client)

        gen = provider.stream_draft("分析胃病数据")
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
        provider = DeepSeekRequirementDraftProvider(client=client)

        chunks = []
        with pytest.raises(DeepSeekError):
            for c in provider.stream_draft("分析数据"):
                chunks.append(c)

        # 只 yield 了第一个 chunk，没有 LocalRule fallback 内容
        assert chunks == ["部分"]


class TestStreamDraftJSONValidation:
    """JSON 校验场景。"""

    def test_流式完成后JSON校验失败抛异常(self):
        """LLM 返回不完整 JSON，流式完成后校验失败应抛 DeepSeekError。"""
        client = _make_mock_client_streaming(chunks=["{invalid json"])
        provider = DeepSeekRequirementDraftProvider(client=client)

        gen = provider.stream_draft("分析数据")
        # 第一个 chunk 应成功 yield
        first = next(gen)
        assert first == "{invalid json"
        # 流结束后应抛 DeepSeekError（JSON 校验失败）
        with pytest.raises(DeepSeekError):
            next(gen, None)  # StopIteration 或抛异常


def _make_valid_response_dict() -> dict:
    """构造有效的任务单 LLM 响应 dict（便于修改单个字段测试容错）。"""
    return json.loads(_make_valid_response_json())


class TestDeepSeekResponseTolerance:
    """LLM 输出不稳定时的容错场景。

    真实 DeepSeek（temperature=0.3）5 次调用有 3 次失败，两类根因：
    - *_requirements 字段返回 [{"description": "..."}] 而非 ["..."]
    - replication_level.suggested_scope 返回 null 而非 str

    模型容错层（field_validator mode=before）应吸收这些不稳定输出。
    """

    def test_data_requirements返回对象数组时容错为字符串数组(self):
        data = _make_valid_response_dict()
        data["data_requirements"] = [{"description": "CSV 数据集"}]
        resp = DeepSeekRequirementResponse.model_validate(data)
        assert resp.data_requirements == ["CSV 数据集"]

    def test_method_requirements返回对象数组时容错(self):
        data = _make_valid_response_dict()
        data["method_requirements"] = [
            {"description": "描述性统计"},
            {"description": "可视化"},
        ]
        resp = DeepSeekRequirementResponse.model_validate(data)
        assert resp.method_requirements == ["描述性统计", "可视化"]

    def test_chart_requirements返回对象数组时容错(self):
        data = _make_valid_response_dict()
        data["chart_requirements"] = [{"description": "年龄分布直方图"}]
        resp = DeepSeekRequirementResponse.model_validate(data)
        assert resp.chart_requirements == ["年龄分布直方图"]

    def test_report_requirements返回对象数组时容错(self):
        data = _make_valid_response_dict()
        data["report_requirements"] = [{"description": "实验报告"}]
        resp = DeepSeekRequirementResponse.model_validate(data)
        assert resp.report_requirements == ["实验报告"]

    def test_suggested_scope为null时容错为空串(self):
        data = _make_valid_response_dict()
        data["replication_level"]["suggested_scope"] = None
        resp = DeepSeekRequirementResponse.model_validate(data)
        assert resp.replication_level.suggested_scope == ""

    def test_混合元素数组容错_字符串与对象共存(self):
        data = _make_valid_response_dict()
        data["chart_requirements"] = [
            "年龄分布直方图",
            {"description": "病情分布图"},
        ]
        resp = DeepSeekRequirementResponse.model_validate(data)
        assert resp.chart_requirements == ["年龄分布直方图", "病情分布图"]

    def test_对象无description字段取首个字符串值(self):
        data = _make_valid_response_dict()
        data["data_requirements"] = [{"reason": "无 desc 字段"}]
        resp = DeepSeekRequirementResponse.model_validate(data)
        assert resp.data_requirements == ["无 desc 字段"]

    def test_正常字符串数组不受容错影响(self):
        data = _make_valid_response_dict()
        data["acceptance_criteria"] = ["可追溯", "图表正确"]
        resp = DeepSeekRequirementResponse.model_validate(data)
        assert resp.acceptance_criteria == ["可追溯", "图表正确"]

    def test_整份LLM不稳定输出容错后通过校验(self):
        """复现真实失败场景：多个 *_requirements 同时返回对象数组 + suggested_scope 为 null。"""
        data = _make_valid_response_dict()
        data["data_requirements"] = [{"description": "胃病诊疗数据集"}]
        data["method_requirements"] = [{"description": "Python"}, {"description": "统计"}]
        data["chart_requirements"] = [{"description": "直方图"}]
        data["report_requirements"] = [{"description": "实验报告"}]
        data["replication_level"]["suggested_scope"] = None
        # 容错后应通过校验
        resp = DeepSeekRequirementResponse.model_validate(data)
        assert resp.data_requirements == ["胃病诊疗数据集"]
        assert resp.method_requirements == ["Python", "统计"]
        assert resp.chart_requirements == ["直方图"]
        assert resp.report_requirements == ["实验报告"]
        assert resp.replication_level.suggested_scope == ""
