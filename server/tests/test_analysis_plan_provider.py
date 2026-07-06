"""分析方案候选提供者测试。

覆盖 LocalRuleAnalysisPlanProvider 和 FakeAnalysisPlanProvider 的行为，
包括字段截断、清洗方案 4+、分析方案 4+、图表方案 4+ 等核心要求。
"""

import pytest

from app.infrastructure.parsers.dataset_parser import (
    DatasetProfile,
    FieldProfile,
)
from app.modules.llm.analysis_plan_provider import (
    AnalysisPlanDraft,
    AnalysisPlanDraftProvider,
    LocalRuleAnalysisPlanProvider,
    FakeAnalysisPlanProvider,
)


def _make_numeric_field(name: str, null_count: int = 0,
                         non_null_count: int = 10) -> FieldProfile:
    """构造数值字段概览。"""
    return FieldProfile(
        name=name,
        inferred_type="int",
        non_null_count=non_null_count,
        null_count=null_count,
        null_rate=null_count / (null_count + non_null_count) if (null_count + non_null_count) > 0 else 0.0,
        unique_count=non_null_count,
        sample_values=["1", "2", "3", "4", "5"],
        min_value=1.0,
        max_value=10.0,
        mean_value=5.0,
        median_value=5.0,
        std_value=2.0,
        q1=3.0,
        q3=7.0,
    )


def _make_string_field(name: str, null_count: int = 0,
                        non_null_count: int = 10,
                        unique_count: int = 5) -> FieldProfile:
    """构造字符串字段概览。"""
    return FieldProfile(
        name=name,
        inferred_type="string",
        non_null_count=non_null_count,
        null_count=null_count,
        null_rate=null_count / (null_count + non_null_count) if (null_count + non_null_count) > 0 else 0.0,
        unique_count=unique_count,
        sample_values=["a", "b", "c"],
        top_values=[("a", 5), ("b", 3)],
    )


def _make_profile(fields: list[FieldProfile], row_count: int = 10,
                  duplicate_row_count: int = 0) -> DatasetProfile:
    """构造数据集概览。"""
    return DatasetProfile(
        row_count=row_count,
        column_count=len(fields),
        complete_row_count=row_count,
        incomplete_row_count=0,
        duplicate_row_count=duplicate_row_count,
        field_profiles=fields,
        quality_score=80.0,
    )


# --- LocalRuleAnalysisPlanProvider ---


class TestLocalRuleProvider:
    """本地规则提供者测试。"""

    def test_source_label_is_local_rule(self):
        """source_label 返回 LOCAL_RULE。"""
        provider = LocalRuleAnalysisPlanProvider()
        assert provider.source_label() == "LOCAL_RULE"

    def test_generates_cleaning_plan_with_missing_value_action(self):
        """缺失值字段会生成对应的清洗建议。"""
        fields = [
            _make_numeric_field("age", null_count=2, non_null_count=8),
            _make_string_field("name", null_count=0, non_null_count=10),
        ]
        profile = _make_profile(fields)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        assert isinstance(draft, AnalysisPlanDraft)
        # 缺失字段应触发 MISSING_VALUE 清洗建议
        missing_actions = [
            a for a in draft.cleaning_plan
            if a.get("issue_type") == "MISSING_VALUE"
        ]
        assert len(missing_actions) >= 1
        assert any(a["field"] == "age" for a in missing_actions)

    def test_cleaning_plan_includes_type_conversion_for_string(self):
        """字符串字段触发 TYPE_CONVERSION 建议。"""
        fields = [
            _make_string_field("category"),
            _make_numeric_field("age"),
        ]
        profile = _make_profile(fields)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        type_conv = [
            a for a in draft.cleaning_plan
            if a.get("issue_type") == "TYPE_CONVERSION"
        ]
        assert len(type_conv) >= 1
        assert any(a["field"] == "category" for a in type_conv)

    def test_cleaning_plan_includes_duplicate_row_when_duplicates_exist(self):
        """存在重复行时 cleaning_plan 包含 DUPLICATE_ROW 建议。"""
        fields = [
            _make_numeric_field("age"),
        ]
        profile = _make_profile(fields, duplicate_row_count=3)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        dup_actions = [
            a for a in draft.cleaning_plan
            if a.get("issue_type") == "DUPLICATE_ROW"
        ]
        assert len(dup_actions) == 1
        # 应包含重复行数
        assert "3" in dup_actions[0]["action"]

    def test_cleaning_plan_includes_constant_value_warning(self):
        """唯一值为 1 的字段触发 CONSTANT_VALUE 建议。"""
        fields = [
            _make_string_field("status", unique_count=1, non_null_count=10),
        ]
        profile = _make_profile(fields)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        constant = [
            a for a in draft.cleaning_plan
            if a.get("issue_type") == "CONSTANT_VALUE"
        ]
        assert len(constant) >= 1

    def test_analysis_plan_includes_descriptive_statistics_for_numeric(self):
        """存在数值字段时生成 DESCRIPTIVE_STATISTICS 建议。"""
        fields = [
            _make_numeric_field("age"),
            _make_numeric_field("score"),
        ]
        profile = _make_profile(fields)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        desc = [
            a for a in draft.analysis_plan
            if a.get("analysis_type") == "DESCRIPTIVE_STATISTICS"
        ]
        assert len(desc) >= 1

    def test_analysis_plan_includes_group_statistics(self):
        """存在数值和分类字段时生成 GROUP_STATISTICS 建议。"""
        fields = [
            _make_numeric_field("age"),
            _make_string_field("category"),
        ]
        profile = _make_profile(fields)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        group = [
            a for a in draft.analysis_plan
            if a.get("analysis_type") == "GROUP_STATISTICS"
        ]
        assert len(group) >= 1

    def test_analysis_plan_includes_correlation_when_2_or_more_numeric(self):
        """2+ 数值字段时生成 CORRELATION 建议。"""
        fields = [
            _make_numeric_field("age"),
            _make_numeric_field("score"),
        ]
        profile = _make_profile(fields)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        corr = [
            a for a in draft.analysis_plan
            if a.get("analysis_type") == "CORRELATION"
        ]
        assert len(corr) >= 1

    def test_analysis_plan_includes_frequency_for_categorical(self):
        """存在分类字段时生成 FREQUENCY 建议。"""
        fields = [
            _make_string_field("category"),
        ]
        profile = _make_profile(fields)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        freq = [
            a for a in draft.analysis_plan
            if a.get("analysis_type") == "FREQUENCY"
        ]
        assert len(freq) >= 1

    def test_chart_plan_includes_histogram_for_numeric(self):
        """数值字段生成 HISTOGRAM 图表方案。"""
        fields = [
            _make_numeric_field("age"),
            _make_numeric_field("score"),
            _make_numeric_field("value"),
        ]
        profile = _make_profile(fields)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        histograms = [c for c in draft.chart_plan if c.get("chart_type") == "HISTOGRAM"]
        assert len(histograms) >= 1

    def test_chart_plan_includes_boxplot(self):
        """存在数值字段时生成 BOXPLOT 图表方案。"""
        fields = [_make_numeric_field("age")]
        profile = _make_profile(fields)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        boxplots = [c for c in draft.chart_plan if c.get("chart_type") == "BOXPLOT"]
        assert len(boxplots) >= 1

    def test_chart_plan_includes_bar_for_categorical(self):
        """分类字段生成 BAR 柱状图。"""
        fields = [
            _make_string_field("category"),
            _make_string_field("status"),
        ]
        profile = _make_profile(fields)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        bars = [c for c in draft.chart_plan if c.get("chart_type") == "BAR"]
        assert len(bars) >= 1

    def test_chart_plan_includes_scatter_for_2_numeric(self):
        """2+ 数值字段生成 SCATTER 散点图。"""
        fields = [
            _make_numeric_field("age"),
            _make_numeric_field("score"),
        ]
        profile = _make_profile(fields)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        scatters = [c for c in draft.chart_plan if c.get("chart_type") == "SCATTER"]
        assert len(scatters) >= 1

    def test_truncates_when_more_than_50_fields(self):
        """字段数超过 50 时只对前 20 个生成详细方案，并添加 TOO_MANY_FIELDS 提示。"""
        fields = [
            _make_numeric_field(f"col_{i}") for i in range(60)
        ]
        profile = _make_profile(fields)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        # 应包含 TOO_MANY_FIELDS 提示
        too_many = [
            a for a in draft.cleaning_plan
            if a.get("issue_type") == "TOO_MANY_FIELDS"
        ]
        assert len(too_many) == 1
        assert "60" in too_many[0]["action"]

    def test_cleaning_plan_at_least_4_when_full_dataset(self):
        """完整数据集（数值 + 字符串 + 缺失 + 重复）至少生成 4 条清洗建议。"""
        fields = [
            _make_numeric_field("age", null_count=2, non_null_count=8),
            _make_string_field("category", null_count=1, non_null_count=9),
            _make_string_field("status", unique_count=1, non_null_count=10),
            _make_numeric_field("score"),
        ]
        profile = _make_profile(fields, duplicate_row_count=2)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        # 应至少 4 条（age 缺失 + category 缺失 + category TYPE_CONVERSION +
        # status CONSTANT + status TYPE_CONVERSION + 重复行 + score TYPE_CONVERSION）
        assert len(draft.cleaning_plan) >= 4

    def test_analysis_plan_at_least_4_when_full_dataset(self):
        """完整数据集至少生成 4 条分析建议。"""
        fields = [
            _make_numeric_field("age", null_count=2, non_null_count=8),
            _make_string_field("category"),
            _make_numeric_field("score"),
            _make_numeric_field("value"),
        ]
        profile = _make_profile(fields)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        # DESCRIPTIVE_STATISTICS + GROUP_STATISTICS + CORRELATION + FREQUENCY = 4
        assert len(draft.analysis_plan) >= 4

    def test_chart_plan_at_least_4_when_full_dataset(self):
        """完整数据集至少生成 4 条图表建议。"""
        fields = [
            _make_numeric_field("age"),
            _make_numeric_field("score"),
            _make_numeric_field("value"),
            _make_string_field("category"),
        ]
        profile = _make_profile(fields)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        # 3 HISTOGRAM + 1 BOXPLOT + 1 BAR + 1 SCATTER = 6 ≥ 4
        assert len(draft.chart_plan) >= 4

    def test_truncates_to_first_20_fields_for_detailed_plan(self):
        """字段数超过 20 时只对前 20 个生成详细方案（HISTOGRAM 最多 3 个）。"""
        # 60 个数值字段
        fields = [_make_numeric_field(f"col_{i}") for i in range(60)]
        profile = _make_profile(fields)

        provider = LocalRuleAnalysisPlanProvider()
        draft = provider.generate(profile)

        # HISTOGRAM 最多 3 个（_DETAILED_FIELD_LIMIT 内的前 3 个数值字段）
        histograms = [c for c in draft.chart_plan if c.get("chart_type") == "HISTOGRAM"]
        assert len(histograms) <= 3

        # DESCRIPTIVE_STATISTICS 仅 1 条（target_fields 是前 5 个数值字段）
        desc = [
            a for a in draft.analysis_plan
            if a.get("analysis_type") == "DESCRIPTIVE_STATISTICS"
        ]
        assert len(desc) <= 1


# --- FakeAnalysisPlanProvider ---


class TestFakeAnalysisPlanProvider:
    """测试用确定性提供者测试。"""

    def test_source_label_is_local_rule(self):
        """FakeAnalysisPlanProvider 也用 LOCAL_RULE 标签。"""
        provider = FakeAnalysisPlanProvider()
        assert provider.source_label() == "LOCAL_RULE"

    def test_returns_fixed_cleaning_plan(self):
        """返回固定的清洗方案结构。"""
        provider = FakeAnalysisPlanProvider()
        profile = _make_profile([_make_numeric_field("x")])
        draft = provider.generate(profile)

        assert isinstance(draft, AnalysisPlanDraft)
        assert len(draft.cleaning_plan) == 1
        assert draft.cleaning_plan[0]["issue_type"] == "DUPLICATE_ROW"

    def test_returns_fixed_analysis_plan(self):
        """返回固定的分析方案结构。"""
        provider = FakeAnalysisPlanProvider()
        profile = _make_profile([_make_numeric_field("x")])
        draft = provider.generate(profile)

        assert len(draft.analysis_plan) == 1
        assert draft.analysis_plan[0]["analysis_type"] == "DESCRIPTIVE_STATISTICS"

    def test_returns_fixed_chart_plan(self):
        """返回固定的图表方案结构。"""
        provider = FakeAnalysisPlanProvider()
        profile = _make_profile([_make_numeric_field("x")])
        draft = provider.generate(profile)

        assert len(draft.chart_plan) == 1
        assert draft.chart_plan[0]["chart_type"] == "HISTOGRAM"

    def test_returns_consistent_regardless_of_profile(self):
        """无论 profile 如何，Fake 始终返回相同结构。"""
        provider = FakeAnalysisPlanProvider()
        profile1 = _make_profile([_make_numeric_field("x")])
        profile2 = _make_profile([_make_string_field("y") for _ in range(5)])

        draft1 = provider.generate(profile1)
        draft2 = provider.generate(profile2)

        assert len(draft1.cleaning_plan) == len(draft2.cleaning_plan)
        assert len(draft1.analysis_plan) == len(draft2.analysis_plan)
        assert len(draft1.chart_plan) == len(draft2.chart_plan)


# --- AnalysisPlanDraft 数据结构 ---


class TestAnalysisPlanDraft:
    """AnalysisPlanDraft 数据结构测试。"""

    def test_default_factory_creates_empty_lists(self):
        """AnalysisPlanDraft 默认创建空列表。"""
        draft = AnalysisPlanDraft()
        assert draft.cleaning_plan == []
        assert draft.analysis_plan == []
        assert draft.chart_plan == []

    def test_provider_returns_proper_dataclass(self):
        """LocalRuleAnalysisPlanProvider 返回 AnalysisPlanDraft 实例。"""
        provider = LocalRuleAnalysisPlanProvider()
        profile = _make_profile([_make_numeric_field("age")])

        draft = provider.generate(profile)

        assert isinstance(draft, AnalysisPlanDraft)
        assert isinstance(draft.cleaning_plan, list)
        assert isinstance(draft.analysis_plan, list)
        assert isinstance(draft.chart_plan, list)

    def test_cleaning_plan_item_has_required_fields(self):
        """清洗方案条目包含 field/issue_type/action/reason。"""
        provider = LocalRuleAnalysisPlanProvider()
        fields = [_make_numeric_field("age", null_count=2, non_null_count=8)]
        profile = _make_profile(fields)
        draft = provider.generate(profile)

        for item in draft.cleaning_plan:
            assert "field" in item
            assert "issue_type" in item
            assert "action" in item
            assert "reason" in item

    def test_analysis_plan_item_has_required_fields(self):
        """分析方案条目包含 analysis_type/target_fields/method/expected_output。"""
        provider = LocalRuleAnalysisPlanProvider()
        fields = [_make_numeric_field("age"), _make_string_field("cat")]
        profile = _make_profile(fields)
        draft = provider.generate(profile)

        for item in draft.analysis_plan:
            assert "analysis_type" in item
            assert "target_fields" in item
            assert "method" in item
            assert "expected_output" in item

    def test_chart_plan_item_has_required_fields(self):
        """图表方案条目包含 chart_type/title/data_fields/description。"""
        provider = LocalRuleAnalysisPlanProvider()
        fields = [_make_numeric_field("age")]
        profile = _make_profile(fields)
        draft = provider.generate(profile)

        for item in draft.chart_plan:
            assert "chart_type" in item
            assert "title" in item
            assert "data_fields" in item
            assert "description" in item


# --- 抽象基类 ---


class TestAnalysisPlanDraftProviderAbc:
    """AnalysisPlanDraftProvider 抽象基类测试。"""

    def test_cannot_instantiate_abc_directly(self):
        """抽象基类不能直接实例化。"""
        with pytest.raises(TypeError):
            AnalysisPlanDraftProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_methods(self):
        """子类必须实现 generate 和 source_label。"""
        class Incomplete(AnalysisPlanDraftProvider):
            pass

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_concrete_subclass_works(self):
        """实现两个抽象方法的子类可以实例化。"""
        class Complete(AnalysisPlanDraftProvider):
            def generate(self, profile):
                return AnalysisPlanDraft()

            def source_label(self):
                return "TEST_LABEL"

        provider = Complete()
        assert provider.source_label() == "TEST_LABEL"
