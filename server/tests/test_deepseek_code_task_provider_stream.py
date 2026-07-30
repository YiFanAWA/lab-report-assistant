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


# ============================================================
# SPEC 0022 回归测试：prompt 换行转义 bug
# ============================================================


class TestPromptNoDoubleEscapeInstruction:
    """SPEC 0022 回归测试：prompt 不应包含导致换行符双重转义的指令。

    bug 根因：
    _SYSTEM_PROMPT 曾包含 "代码字符串中的换行使用 \\n 转义" 指令，导致
    DeepSeek 返回的 JSON 中 code 字段换行被双重转义为字面量 \\n（反斜杠+n），
    json.loads 解析后仍为字面量 \\n 而非真正换行符，执行时被 Python 解释器
    当作行延续符引发语法错误：
        EXECUTION_IMPORT_FORBIDDEN: 代码语法错误:
        unexpected character after line continuation character

    修复：
    删除该错误指令，新增 "代码必须是合法 JSON（换行符由 JSON 标准自动转义，
    无需手动处理）"，让 LLM 依赖 JSON 标准自动处理换行转义。
    """

    def test_prompt不包含换行手动转义指令(self):
        """_SYSTEM_PROMPT 不应包含 '换行使用 \\n 转义' 这类错误指令。"""
        from app.modules.llm.deepseek_code_task_provider import _SYSTEM_PROMPT
        # 字面量反斜杠+n 不应出现在 prompt 的换行转义指令中
        assert "换行使用 \\n 转义" not in _SYSTEM_PROMPT, (
            "_SYSTEM_PROMPT 不应包含 '换行使用 \\n 转义' 指令，"
            "该指令会导致 LLM 双重转义换行符，引发代码执行语法错误"
        )

    def test_prompt包含合法JSON说明(self):
        """_SYSTEM_PROMPT 应包含 '合法 JSON' 说明，引导 LLM 正确处理换行。"""
        from app.modules.llm.deepseek_code_task_provider import _SYSTEM_PROMPT
        assert "合法 JSON" in _SYSTEM_PROMPT, (
            "_SYSTEM_PROMPT 应包含 '合法 JSON' 说明，"
            "引导 LLM 依赖 JSON 标准自动转义换行符"
        )

    def test_流式生成code含真正换行符(self):
        """流式生成的 code 通过 json.loads 解析后应包含真正换行符。

        回归 bug：双重转义会导致 code 字段值包含字面量 '\\n'（反斜杠+n
        两个字符），而非真正换行符，执行时引发 Python 行延续符语法错误。
        """
        full_json = _make_valid_code_task_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekCodeTaskProvider(client=client)

        result = list(provider.stream_generate(_make_analysis_plan()))
        full = "".join(result)
        parsed = json.loads(full)

        assert "code" in parsed
        code = parsed["code"]
        # code 应包含真正换行符（\n），而非字面量转义字符
        assert "\n" in code, (
            "code 应包含真正换行符（\\n），而非字面量转义字符，"
            "否则执行时会引发 Python 行延续符语法错误"
        )
        # code 不应包含字面量反斜杠+n（双重转义的标志）
        assert "\\n" not in code, (
            "code 不应包含字面量 '\\n'（反斜杠+n 两个字符），"
            "这是 prompt 双重转义指令导致的回归 bug 标志"
        )

    def test_流式生成code可被compile为合法Python(self):
        """流式生成的 code 应能被 compile() 解析为合法 Python 语法。

        这是对 bug 的端到端回归保护：双重转义的 code 会导致
        compile() 抛出 SyntaxError。
        """
        full_json = _make_valid_code_task_json()
        client = _make_mock_client_streaming(chunks=[full_json])
        provider = DeepSeekCodeTaskProvider(client=client)

        result = list(provider.stream_generate(_make_analysis_plan()))
        full = "".join(result)
        parsed = json.loads(full)
        code = parsed["code"]

        # compile() 不抛 SyntaxError 即证明 code 是合法 Python 语法
        # 这是 bug 修复的直接验证：双重转义的 code 会在此抛出
        # "unexpected character after line continuation character"
        compile(code, "<code_task>", "exec")


# ============================================================
# SPEC 0022 回归测试：prompt import 白名单约束
# ============================================================


class TestPromptImportWhitelist:
    """SPEC 0022 回归测试：prompt 必须明确 import 白名单和禁止模块。

    bug 根因：
    _SYSTEM_PROMPT 曾未明确列出 import 白名单和禁止模块，导致 DeepSeek
    生成的代码包含 import os 等被 AST 校验拒绝的模块，执行时返回
    EXECUTION_IMPORT_FORBIDDEN，代码任务执行失败。

    修复：
    在 _SYSTEM_PROMPT 中添加明确的 import 白名单（pandas/numpy/matplotlib/
    scipy/sklearn/openpyxl）和禁止模块列表（os/sys/pathlib/socket 等），
    并禁止使用 os.path 或 pathlib 进行路径操作。
    """

    def test_prompt包含import白名单说明(self):
        """_SYSTEM_PROMPT 应包含 'import 白名单' 说明。"""
        from app.modules.llm.deepseek_code_task_provider import _SYSTEM_PROMPT
        assert "import 白名单" in _SYSTEM_PROMPT, (
            "_SYSTEM_PROMPT 应包含 'import 白名单' 说明，"
            "明确告知 LLM 只允许使用哪些模块"
        )

    def test_prompt包含白名单模块列表(self):
        """_SYSTEM_PROMPT 应列出允许的模块：pandas/numpy/matplotlib/scipy/sklearn/openpyxl。"""
        from app.modules.llm.deepseek_code_task_provider import _SYSTEM_PROMPT
        for module in ["pandas", "numpy", "matplotlib", "scipy", "sklearn", "openpyxl"]:
            assert module in _SYSTEM_PROMPT, (
                f"_SYSTEM_PROMPT 应在白名单中列出允许的模块: {module}"
            )

    def test_prompt明确禁止os模块(self):
        """_SYSTEM_PROMPT 应明确禁止 import os（最常见的违规模块）。"""
        from app.modules.llm.deepseek_code_task_provider import _SYSTEM_PROMPT
        # prompt 的禁止模块列表中应包含 os
        assert "严禁 import" in _SYSTEM_PROMPT or "禁止" in _SYSTEM_PROMPT, (
            "_SYSTEM_PROMPT 应包含明确的禁止 import 指令"
        )
        # os 应在禁止列表中
        forbidden_section = _SYSTEM_PROMPT[_SYSTEM_PROMPT.index("严禁"):]
        assert "os" in forbidden_section, (
            "_SYSTEM_PROMPT 的禁止模块列表应包含 os"
        )

    def test_prompt禁止pathlib路径操作(self):
        """_SYSTEM_PROMPT 应禁止使用 os.path 或 pathlib 进行路径操作。"""
        from app.modules.llm.deepseek_code_task_provider import _SYSTEM_PROMPT
        assert "os.path" in _SYSTEM_PROMPT, (
            "_SYSTEM_PROMPT 应提及 os.path 并禁止使用"
        )
        assert "pathlib" in _SYSTEM_PROMPT, (
            "_SYSTEM_PROMPT 应提及 pathlib 并禁止使用"
        )
        assert "f-string" in _SYSTEM_PROMPT or "f\"" in _SYSTEM_PROMPT, (
            "_SYSTEM_PROMPT 应引导使用 f-string 拼接路径"
        )
