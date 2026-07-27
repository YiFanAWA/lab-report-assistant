"""LocalRuleCodeTaskProvider 输出格式校验测试。

SPEC 0022：代码任务生成流式化。
参考 SPEC 0021 收口经验：LocalRule 输出格式不正确会导致前端 TypeError 阻断。

测试：
- LocalRule 输出 CodeTaskDraft.code 为字符串
- code 内容可编译为合法 Python（compile() 不报错）
- target_fields 类型容错（字符串/数组/null/缺失）
- 不因 AnalysisPlan 字段类型异常崩溃
- 空方案不崩溃
- 含清洗/分析/图表步骤时生成对应代码
- stream_generate() 方法存在并返回迭代器（红色阶段：尚未实现）

红色阶段说明：
- stream_generate() 方法尚未实现，相关测试应失败
- generate() 方法已存在，相关测试应通过
"""

import ast
import json

import pytest

from app.modules.llm.code_task_provider import (
    CodeTaskDraft,
    LocalRuleCodeTaskProvider,
)


# --- 测试用 AnalysisPlan 构造 ---


def _make_full_plan() -> dict:
    """构造完整的 AnalysisPlan（含清洗/分析/图表三个列表）。"""
    return {
        "cleaning_plan": [
            {
                "field": "age",
                "issue_type": "MISSING_VALUE",
                "action": "用中位数填充缺失值",
                "reason": "数值字段",
            },
            {
                "field": "gender",
                "issue_type": "MISSING_VALUE",
                "action": "用众数填充缺失值",
                "reason": "字符串字段",
            },
        ],
        "analysis_plan": [
            {
                "analysis_type": "DESCRIPTIVE_STATISTICS",
                "target_fields": ["age"],
                "method": "计算均值",
                "expected_output": "统计表",
            },
        ],
        "chart_plan": [
            {
                "chart_type": "HISTOGRAM",
                "title": "age 分布",
                "data_fields": ["age"],
                "description": "展示分布",
            },
        ],
    }


def _make_minimal_plan() -> dict:
    """构造最小的 AnalysisPlan（空列表）。"""
    return {
        "cleaning_plan": [],
        "analysis_plan": [],
        "chart_plan": [],
    }


# --- 基础格式校验 ---


class TestLocalRuleCodeTaskProviderBasicFormat:
    """LocalRule 输出基础格式校验。"""

    def test_输出为CodeTaskDraft类型(self):
        """generate() 应返回 CodeTaskDraft 实例。"""
        provider = LocalRuleCodeTaskProvider()
        result = provider.generate(_make_full_plan())
        assert isinstance(result, CodeTaskDraft)

    def test_code字段为字符串类型(self):
        """CodeTaskDraft.code 必须是字符串（避免前端 join 报错，参考 SPEC 0021 收口经验）。"""
        provider = LocalRuleCodeTaskProvider()
        result = provider.generate(_make_full_plan())
        assert isinstance(result.code, str)
        assert result.code  # 非空

    def test_code字段非None(self):
        """code 字段不能为 None（前端会调用字符串方法）。"""
        provider = LocalRuleCodeTaskProvider()
        result = provider.generate(_make_full_plan())
        assert result.code is not None

    def test_code可编译为合法Python(self):
        """code 内容必须能通过 Python ast.parse 校验（语法合法）。

        参考 SPEC 0022 §1.3：LocalRule 拼装的代码必须可执行。
        """
        provider = LocalRuleCodeTaskProvider()
        result = provider.generate(_make_full_plan())
        # ast.parse 会抛 SyntaxError 如果代码不合法
        # 注意：LocalRule 生成的代码引用了 DATA_PATH 和 OUTPUT_DIR 变量
        # 但 ast.parse 只做语法检查，不检查变量是否存在
        ast.parse(result.code)

    def test_source_label返回LOCAL_RULE(self):
        """source_label() 应返回 'LOCAL_RULE'。"""
        provider = LocalRuleCodeTaskProvider()
        assert provider.source_label() == "LOCAL_RULE"


# --- target_fields 类型容错测试（参考 SPEC 0021 收口经验） ---


class TestTargetFieldsTypeTolerance:
    """target_fields 类型容错测试。

    SPEC 0021 收口经验：LocalRule 输出 target_fields 为字符串导致前端 PlanCard 报错。
    本测试校验 LocalRuleCodeTaskProvider 能处理各种 target_fields 类型输入。
    """

    def test_target_fields为字符串不崩溃(self):
        """target_fields 为字符串时 LocalRule 不应崩溃。"""
        provider = LocalRuleCodeTaskProvider()
        plan = _make_full_plan()
        plan["analysis_plan"][0]["target_fields"] = "age"
        # 不应抛异常
        result = provider.generate(plan)
        assert isinstance(result.code, str)

    def test_target_fields为数组不崩溃(self):
        """target_fields 为数组时 LocalRule 不应崩溃。"""
        provider = LocalRuleCodeTaskProvider()
        plan = _make_full_plan()
        plan["analysis_plan"][0]["target_fields"] = ["age", "gender"]
        result = provider.generate(plan)
        assert isinstance(result.code, str)

    def test_target_fields为null不崩溃(self):
        """target_fields 为 None 时 LocalRule 不应崩溃。"""
        provider = LocalRuleCodeTaskProvider()
        plan = _make_full_plan()
        plan["analysis_plan"][0]["target_fields"] = None
        result = provider.generate(plan)
        assert isinstance(result.code, str)

    def test_target_fields缺失不崩溃(self):
        """target_fields 字段缺失时 LocalRule 不应崩溃。"""
        provider = LocalRuleCodeTaskProvider()
        plan = _make_full_plan()
        del plan["analysis_plan"][0]["target_fields"]
        result = provider.generate(plan)
        assert isinstance(result.code, str)

    def test_target_fields为空字符串不崩溃(self):
        """target_fields 为空字符串时 LocalRule 不应崩溃。"""
        provider = LocalRuleCodeTaskProvider()
        plan = _make_full_plan()
        plan["analysis_plan"][0]["target_fields"] = ""
        result = provider.generate(plan)
        assert isinstance(result.code, str)

    def test_FREQUENCY类型target_fields为数组不崩溃(self):
        """FREQUENCY 分析类型 + target_fields 为数组时不应崩溃。

        回归测试：SPEC 0022 浏览器验收发现 bug，
        _build_analysis_code 中 target_fields.split() 在 list 上调用会报错
        "'list' object has no attribute 'split'"。
        修复后使用 _first_field_name() 兼容 list 和 string。
        """
        provider = LocalRuleCodeTaskProvider()
        plan = _make_full_plan()
        plan["analysis_plan"][0]["analysis_type"] = "FREQUENCY"
        plan["analysis_plan"][0]["target_fields"] = ["diagnosis", "gender"]
        # 不应抛 'list' object has no attribute 'split'
        result = provider.generate(plan)
        assert isinstance(result.code, str)
        # 代码应包含 value_counts 调用（FREQUENCY 类型的输出）
        assert "value_counts" in result.code

    def test_FREQUENCY类型target_fields为字符串不崩溃(self):
        """FREQUENCY 分析类型 + target_fields 为字符串时不应崩溃（兼容旧格式）。"""
        provider = LocalRuleCodeTaskProvider()
        plan = _make_full_plan()
        plan["analysis_plan"][0]["analysis_type"] = "FREQUENCY"
        plan["analysis_plan"][0]["target_fields"] = "diagnosis"
        result = provider.generate(plan)
        assert isinstance(result.code, str)
        assert "value_counts" in result.code


# --- AnalysisPlan 字段类型异常容错 ---


class TestAnalysisPlanFieldTypeTolerance:
    """AnalysisPlan 字段类型异常容错测试。"""

    def test_cleaning_plan为JSON字符串不崩溃(self):
        """cleaning_plan 为 JSON 字符串时 LocalRule 应能解析。"""
        provider = LocalRuleCodeTaskProvider()
        plan = _make_full_plan()
        plan["cleaning_plan"] = json.dumps(plan["cleaning_plan"])
        result = provider.generate(plan)
        assert isinstance(result.code, str)

    def test_analysis_plan为JSON字符串不崩溃(self):
        """analysis_plan 为 JSON 字符串时 LocalRule 应能解析。"""
        provider = LocalRuleCodeTaskProvider()
        plan = _make_full_plan()
        plan["analysis_plan"] = json.dumps(plan["analysis_plan"])
        result = provider.generate(plan)
        assert isinstance(result.code, str)

    def test_chart_plan为JSON字符串不崩溃(self):
        """chart_plan 为 JSON 字符串时 LocalRule 应能解析。"""
        provider = LocalRuleCodeTaskProvider()
        plan = _make_full_plan()
        plan["chart_plan"] = json.dumps(plan["chart_plan"])
        result = provider.generate(plan)
        assert isinstance(result.code, str)

    def test_空方案不崩溃(self):
        """空方案（三个列表都为空）时 LocalRule 不应崩溃。"""
        provider = LocalRuleCodeTaskProvider()
        result = provider.generate(_make_minimal_plan())
        assert isinstance(result.code, str)
        assert result.code  # 非空（至少有 header）

    def test_缺失cleaning_plan字段不崩溃(self):
        """缺失 cleaning_plan 字段时不应崩溃。"""
        provider = LocalRuleCodeTaskProvider()
        plan = _make_full_plan()
        del plan["cleaning_plan"]
        result = provider.generate(plan)
        assert isinstance(result.code, str)

    def test_缺失analysis_plan字段不崩溃(self):
        """缺失 analysis_plan 字段时不应崩溃。"""
        provider = LocalRuleCodeTaskProvider()
        plan = _make_full_plan()
        del plan["analysis_plan"]
        result = provider.generate(plan)
        assert isinstance(result.code, str)

    def test_缺失chart_plan字段不崩溃(self):
        """缺失 chart_plan 字段时不应崩溃。"""
        provider = LocalRuleCodeTaskProvider()
        plan = _make_full_plan()
        del plan["chart_plan"]
        result = provider.generate(plan)
        assert isinstance(result.code, str)


# --- 代码内容校验 ---


class TestGeneratedCodeContent:
    """LocalRule 生成的代码内容校验。"""

    def test_代码包含pandas导入(self):
        """生成的代码应包含 pandas 导入（LocalRule header 固定包含）。"""
        provider = LocalRuleCodeTaskProvider()
        result = provider.generate(_make_full_plan())
        assert "import pandas" in result.code

    def test_代码包含DATA_PATH引用(self):
        """生成的代码应引用 DATA_PATH 变量（由执行环境注入）。"""
        provider = LocalRuleCodeTaskProvider()
        result = provider.generate(_make_full_plan())
        assert "DATA_PATH" in result.code

    def test_代码包含OUTPUT_DIR引用(self):
        """生成的代码应引用 OUTPUT_DIR 变量（由执行环境注入）。"""
        provider = LocalRuleCodeTaskProvider()
        result = provider.generate(_make_full_plan())
        assert "OUTPUT_DIR" in result.code

    def test_含清洗步骤时生成对应代码(self):
        """含 MISSING_VALUE 清洗步骤时应生成 fillna 代码。"""
        provider = LocalRuleCodeTaskProvider()
        result = provider.generate(_make_full_plan())
        # LocalRule 对 MISSING_VALUE 类型生成 fillna
        assert "fillna" in result.code

    def test_含分析步骤时生成对应代码(self):
        """含 DESCRIPTIVE_STATISTICS 分析步骤时应生成 describe 代码。"""
        provider = LocalRuleCodeTaskProvider()
        result = provider.generate(_make_full_plan())
        # LocalRule 对 DESCRIPTIVE_STATISTICS 生成 describe
        assert "describe" in result.code

    def test_含图表步骤时生成对应代码(self):
        """含 HISTOGRAM 图表步骤时应生成 hist 代码。"""
        provider = LocalRuleCodeTaskProvider()
        result = provider.generate(_make_full_plan())
        # LocalRule 对 HISTOGRAM 生成 hist
        assert "hist" in result.code or "plt" in result.code

    def test_代码可通过ast语法检查(self):
        """完整方案生成的代码应通过 ast.parse 语法检查。"""
        provider = LocalRuleCodeTaskProvider()
        result = provider.generate(_make_full_plan())
        # 不应抛 SyntaxError
        ast.parse(result.code)


# --- dataset_profile 参数容错 ---


class TestDatasetProfileParameter:
    """dataset_profile 参数容错测试。"""

    def test_dataset_profile为None不崩溃(self):
        """dataset_profile 为 None 时不应崩溃（默认调用方式）。"""
        provider = LocalRuleCodeTaskProvider()
        result = provider.generate(_make_full_plan(), dataset_profile=None)
        assert isinstance(result.code, str)

    def test_dataset_profile为空dict不崩溃(self):
        """dataset_profile 为空 dict 时不应崩溃。"""
        provider = LocalRuleCodeTaskProvider()
        result = provider.generate(_make_full_plan(), dataset_profile={})
        assert isinstance(result.code, str)

    def test_dataset_profile包含字段信息不崩溃(self):
        """dataset_profile 包含字段信息时不应崩溃。"""
        provider = LocalRuleCodeTaskProvider()
        profile = {
            "row_count": 100,
            "column_count": 3,
            "field_profiles": [
                {"name": "age", "inferred_type": "int"},
            ],
        }
        result = provider.generate(_make_full_plan(), dataset_profile=profile)
        assert isinstance(result.code, str)


# --- stream_generate() 方法存在性校验（红色阶段） ---


class TestStreamGenerateMethod:
    """stream_generate() 方法存在性校验。

    红色阶段说明：
    - stream_generate() 方法尚未实现，相关测试应失败
    - 实现完成后应验证：方法存在、返回迭代器、yield 字符串
    """

    def test_stream_generate方法存在(self):
        """LocalRuleCodeTaskProvider 应实现 stream_generate() 方法。

        红色阶段：方法尚未实现，hasattr 应返回 False。
        """
        provider = LocalRuleCodeTaskProvider()
        # 红色阶段预期：方法不存在
        # 实现完成后：方法存在
        assert hasattr(provider, "stream_generate"), \
            "LocalRuleCodeTaskProvider 应实现 stream_generate() 方法（SPEC 0022 要求）"

    def test_stream_generate返回迭代器(self):
        """stream_generate() 应返回迭代器，逐 chunk yield 字符串。

        红色阶段：方法尚未实现，跳过。
        """
        provider = LocalRuleCodeTaskProvider()
        if not hasattr(provider, "stream_generate"):
            pytest.skip("stream_generate() 尚未实现（红色阶段）")

        chunks = list(provider.stream_generate(_make_full_plan()))
        assert len(chunks) >= 1
        # 每个 chunk 应为字符串
        for chunk in chunks:
            assert isinstance(chunk, str)

    def test_stream_generate拼接为有效JSON含code字段(self):
        """stream_generate() 拼接所有 chunk 后应为有效 JSON，含 code 字段。

        红色阶段：方法尚未实现，跳过。
        """
        provider = LocalRuleCodeTaskProvider()
        if not hasattr(provider, "stream_generate"):
            pytest.skip("stream_generate() 尚未实现（红色阶段）")

        chunks = list(provider.stream_generate(_make_full_plan()))
        full_text = "".join(chunks)
        parsed = json.loads(full_text)
        assert "code" in parsed
        assert isinstance(parsed["code"], str)

    def test_stream_generate拼接代码可编译为合法Python(self):
        """stream_generate() 拼接所有 chunk 后的 code 字段应可编译为合法 Python。

        红色阶段：方法尚未实现，跳过。
        """
        provider = LocalRuleCodeTaskProvider()
        if not hasattr(provider, "stream_generate"):
            pytest.skip("stream_generate() 尚未实现（红色阶段）")

        chunks = list(provider.stream_generate(_make_full_plan()))
        full_text = "".join(chunks)
        parsed = json.loads(full_text)
        # code 字段应通过 ast 语法检查
        ast.parse(parsed["code"])

    def test_stream_generate兼容同步generate输出(self):
        """stream_generate() 拼接后的 code 字段应与 generate() 输出的 code 一致。

        红色阶段：方法尚未实现，跳过。
        """
        provider = LocalRuleCodeTaskProvider()
        if not hasattr(provider, "stream_generate"):
            pytest.skip("stream_generate() 尚未实现（红色阶段）")

        # 同步生成
        sync_result = provider.generate(_make_full_plan())
        # 流式生成
        chunks = list(provider.stream_generate(_make_full_plan()))
        full_text = "".join(chunks)
        parsed = json.loads(full_text)
        # 两者的 code 字段应一致
        assert parsed["code"] == sync_result.code


# --- FakeCodeTaskProvider 格式校验（参考 LocalRule） ---


class TestFakeCodeTaskProviderFormat:
    """FakeCodeTaskProvider 输出格式校验（测试用确定性 provider）。

    参考 SPEC 0021 收口经验：Fake provider 也应保证输出格式正确。
    """

    def test_输出为CodeTaskDraft类型(self):
        """generate() 应返回 CodeTaskDraft 实例。"""
        from app.modules.llm.code_task_provider import FakeCodeTaskProvider
        provider = FakeCodeTaskProvider()
        result = provider.generate(_make_full_plan())
        assert isinstance(result, CodeTaskDraft)

    def test_code字段为字符串类型(self):
        """CodeTaskDraft.code 必须是字符串。"""
        from app.modules.llm.code_task_provider import FakeCodeTaskProvider
        provider = FakeCodeTaskProvider()
        result = provider.generate(_make_full_plan())
        assert isinstance(result.code, str)
        assert result.code

    def test_code可编译为合法Python(self):
        """code 内容必须能通过 ast.parse 校验。"""
        from app.modules.llm.code_task_provider import FakeCodeTaskProvider
        provider = FakeCodeTaskProvider()
        result = provider.generate(_make_full_plan())
        ast.parse(result.code)

    def test_source_label返回LOCAL_RULE(self):
        """FakeCodeTaskProvider 的 source_label 应返回 'LOCAL_RULE'（与 LocalRule 一致）。"""
        from app.modules.llm.code_task_provider import FakeCodeTaskProvider
        provider = FakeCodeTaskProvider()
        assert provider.source_label() == "LOCAL_RULE"
