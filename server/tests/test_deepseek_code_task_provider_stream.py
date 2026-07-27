"""DeepSeekCodeTaskProvider.stream_generate 流式调用单元测试。

SPEC 0022：代码任务生成流式化。

mock DeepSeekClient.stream_chat_completion 测试：
- 流式成功（多 chunk yield，JSON 校验通过）
- 首 chunk 前失败（降级到 LocalRule，拆分多 chunk 模拟流式）
- 中途失败（已 yield chunks 保留，抛异常由上层处理）
- JSON 校验失败（yield 完所有 chunk 后抛 DeepSeekError）
- source_label 正确
- dataset_profile 可选参数
- LocalRule provider stream_generate 接口一致

测试原则：
- 不调用真实 DeepSeek API
- mock DeepSeekClient.stream_chat_completion 方法
"""

import json
from unittest.mock import MagicMock

import pytest

from app.infrastructure.llm.deepseek_client import DeepSeekClient, DeepSeekError
from app.modules.llm.deepseek_code_task_provider import (
    DeepSeekCodeTaskProvider,
    DeepSeekCodeTaskResponse,
)
from app.modules.llm.code_task_provider import (
    CodeTaskDraft,
    LocalRuleCodeTaskProvider,
    CodeTaskDraftProvider,
)


def _make_analysis_plan() -> dict:
    """构造有效的已确认 AnalysisPlan dict（含 cleaning/analysis/chart 三个列表）。"""
    return {
        "cleaning_plan": [
            {
                "field": "age",
                "issue_type": "MISSING_VALUE",
                "action": "用中位数填充缺失值",
                "reason": "数值字段，中位数对异常值稳健",
            },
        ],
        "analysis_plan": [
            {
                "analysis_type": "DESCRIPTIVE_STATISTICS",
                "target_fields": ["age"],
                "method": "计算均值、中位数、标准差",
                "expected_output": "描述性统计表",
            },
        ],
        "chart_plan": [
            {
                "chart_type": "HISTOGRAM",
                "title": "age 分布直方图",
                "data_fields": ["age"],
                "description": "展示年龄分布",
            },
        ],
    }


def _make_valid_code_task_json() -> str:
    """构造有效的代码任务 LLM JSON 响应（含 code 字段）。"""
    return json.dumps({
        "code": "import pandas as pd\nimport matplotlib.pyplot as plt\n\ndf = pd.read_csv(DATA_PATH)\nprint(df.describe())\ndf.hist(column='age')\nplt.savefig(OUTPUT_DIR + '/age_hist.png')\n",
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
        full_json = _make_valid_code_task_json()
        chunks = [full_json[i:i + 50] for i in range(0, len(full_json), 50)]
        client = _make_mock_client_streaming(chunks=chunks)
        provider = DeepSeekCodeTaskProvider(client=client)

        result = list(provider.stream_generate(_make_analysis_plan()))

        assert result == chunks
        assert "".join(result) == full_json

    def test_单chunk也能流式(self):
        """单个 chunk（完整 JSON）也能正常 yield。"""
        full_json = _make_valid_code_task_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekCodeTaskProvider(client=client)

        result = list(provider.stream_generate(_make_analysis_plan()))

        assert result == [full_json]

    def test_source_label返回DEEPSEEK(self):
        """source_label 应返回 DEEPSEEK。"""
        client = _make_mock_client_streaming(chunks=[_make_valid_code_task_json()])
        provider = DeepSeekCodeTaskProvider(client=client)
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
        fallback = LocalRuleCodeTaskProvider()
        provider = DeepSeekCodeTaskProvider(client=client, fallback=fallback)

        result = list(provider.stream_generate(_make_analysis_plan()))

        # 应 yield 多个 chunk（fallback JSON 拆分）
        assert len(result) > 0
        full = "".join(result)
        # 拼接后应能解析为有效 JSON（含 code 字段）
        parsed = json.loads(full)
        assert "code" in parsed
        assert isinstance(parsed["code"], str)
        assert len(parsed["code"]) > 0

    def test_首chunk前超时也降级(self):
        """首 chunk 前超时也应降级到 LocalRule。"""
        client = _make_mock_client_streaming(
            raises_before_first=DeepSeekError(
                code="DEEPSEEK_TIMEOUT", message="超时"
            )
        )
        provider = DeepSeekCodeTaskProvider(client=client)

        result = list(provider.stream_generate(_make_analysis_plan()))

        assert len(result) > 0
        full = "".join(result)
        assert json.loads(full) is not None

    def test_降级后内容包含可执行代码(self):
        """降级到 LocalRule 后，内容应包含可执行 Python 代码。"""
        client = _make_mock_client_streaming(
            raises_before_first=DeepSeekError(
                code="DEEPSEEK_AUTH_ERROR", message="鉴权失败"
            )
        )
        fallback = LocalRuleCodeTaskProvider()
        provider = DeepSeekCodeTaskProvider(client=client, fallback=fallback)

        result = list(provider.stream_generate(_make_analysis_plan()))
        full = "".join(result)
        parsed = json.loads(full)

        # LocalRule 应生成包含 pandas 导入和数据处理逻辑的代码
        assert "code" in parsed
        code = parsed["code"]
        assert "import pandas" in code or "pd.read_csv" in code


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
        provider = DeepSeekCodeTaskProvider(client=client)

        gen = provider.stream_generate(_make_analysis_plan())
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
        provider = DeepSeekCodeTaskProvider(client=client)

        chunks = []
        with pytest.raises(DeepSeekError):
            for c in provider.stream_generate(_make_analysis_plan()):
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
        provider = DeepSeekCodeTaskProvider(client=client)

        gen = provider.stream_generate(_make_analysis_plan())
        # 第一个 chunk 应成功 yield
        first = next(gen)
        assert first == "{invalid json"
        # 流结束后应抛 DeepSeekError（JSON 校验失败）
        with pytest.raises(DeepSeekError):
            next(gen, None)

    def test_有效JSON不抛异常(self):
        """有效的代码任务 JSON 流式完成后不应抛异常。"""
        full_json = _make_valid_code_task_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekCodeTaskProvider(client=client)

        result = list(provider.stream_generate(_make_analysis_plan()))

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
        provider = DeepSeekCodeTaskProvider(client=client)

        gen = provider.stream_generate(_make_analysis_plan())
        # 空 chunks 会引发 JSON 校验失败（空字符串不是有效 JSON）
        with pytest.raises(DeepSeekError):
            list(gen)

    def test_dataset_profile可选参数(self):
        """dataset_profile 为可选参数，不传也应正常工作。"""
        full_json = _make_valid_code_task_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekCodeTaskProvider(client=client)

        # 不传 dataset_profile
        result_no_profile = list(provider.stream_generate(_make_analysis_plan()))
        assert len(result_no_profile) == 1

        # 传 dataset_profile
        result_with_profile = list(
            provider.stream_generate(
                _make_analysis_plan(),
                dataset_profile={"row_count": 100, "column_count": 3},
            )
        )
        assert len(result_with_profile) == 1


# ============================================================
# LocalRule provider stream_generate 接口一致性
# ============================================================


class TestLocalRuleStreamGenerateInterface:
    """LocalRuleCodeTaskProvider 的 stream_generate 接口一致性。"""

    def test_LocalRule_stream_generate存在(self):
        """LocalRuleCodeTaskProvider 应实现 stream_generate 方法。"""
        provider = LocalRuleCodeTaskProvider()
        assert hasattr(provider, "stream_generate"), (
            "LocalRuleCodeTaskProvider 必须实现 stream_generate 方法，"
            "与 DeepSeekCodeTaskProvider 接口一致"
        )

    def test_LocalRule_stream_generate_yield字符串(self):
        """LocalRuleCodeTaskProvider.stream_generate 应 yield 字符串 chunk。"""
        provider = LocalRuleCodeTaskProvider()
        result = list(provider.stream_generate(_make_analysis_plan()))

        assert len(result) > 0
        for chunk in result:
            assert isinstance(chunk, str)

        # 拼接后应能解析为有效 JSON（含 code 字段）
        full = "".join(result)
        parsed = json.loads(full)
        assert "code" in parsed
        assert isinstance(parsed["code"], str)

    def test_LocalRule_stream_generate拆分多chunk(self):
        """LocalRuleCodeTaskProvider.stream_generate 应拆分多 chunk 模拟流式。"""
        provider = LocalRuleCodeTaskProvider()
        result = list(provider.stream_generate(_make_analysis_plan()))

        # 应拆分为多个 chunk（不是单个完整 JSON）
        assert len(result) > 1, "LocalRule stream_generate 应拆分多 chunk 模拟流式"

    def test_抽象基类定义stream_generate(self):
        """CodeTaskDraftProvider 抽象基类应定义 stream_generate 抽象方法。"""
        assert hasattr(CodeTaskDraftProvider, "stream_generate"), (
            "CodeTaskDraftProvider 抽象基类必须定义 stream_generate 抽象方法，"
            "确保所有 Provider 实现流式接口"
        )
