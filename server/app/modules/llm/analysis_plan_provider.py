"""分析方案候选提供者。

不依赖任何外部模型、不调用 DeepSeek。
基于已解析数据集的字段概览和缺失率生成清洗和分析方案候选。
提供者只接收 DatasetProfile（不含原始数据），不泄露用户数据。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.infrastructure.parsers.dataset_parser import DatasetProfile, FieldProfile


@dataclass
class AnalysisPlanDraft:
    """分析方案候选（提供者产出，非业务实体）。

    cleaning_plan / analysis_plan / chart_plan 均为 list[dict]，
    序列化为 JSON 字符串后写入 AnalysisPlan。
    """

    cleaning_plan: list[dict] = field(default_factory=list)
    analysis_plan: list[dict] = field(default_factory=list)
    chart_plan: list[dict] = field(default_factory=list)


class AnalysisPlanDraftProvider(ABC):
    """分析方案候选提供者抽象基类。"""

    @abstractmethod
    def generate(self, profile: DatasetProfile) -> AnalysisPlanDraft:
        """从数据集概览生成分析方案候选。"""

    @abstractmethod
    def source_label(self) -> str:
        """返回候选来源标签（用于写入 candidate_source）。"""


# --- 本地规则实现 ---


# 字段过多时的截断阈值（SPEC：超过 50 字段只对前 20 个生成详细方案）
_DETAILED_FIELD_LIMIT = 20
_FIELD_COUNT_THRESHOLD = 50


def _build_cleaning_plan(profile: DatasetProfile) -> list[dict]:
    """基于字段类型和缺失率生成清洗方案。"""
    items: list[dict] = []
    for field_profile in profile.field_profiles[:_DETAILED_FIELD_LIMIT]:
        # 缺失值处理
        if field_profile.null_count > 0:
            if field_profile.null_rate > 0.5:
                action = "考虑删除该字段或记录缺失标记"
                reason = f"缺失率 {field_profile.null_rate:.1%}，超过 50%"
            elif field_profile.inferred_type in ("int", "float"):
                action = "用中位数填充缺失值"
                reason = "数值字段，中位数对异常值稳健"
            elif field_profile.inferred_type == "string":
                action = "用众数或常量 '未知' 填充缺失值"
                reason = "字符串字段，众数或常量可保留信息"
            elif field_profile.inferred_type == "datetime":
                action = "保留缺失或用前向填充"
                reason = "时间字段，前向填充可保持时序"
            else:
                action = "保留缺失值，标记为未知"
                reason = "布尔或其他类型，保留以备分析"
            items.append({
                "field": field_profile.name,
                "issue_type": "MISSING_VALUE",
                "action": action,
                "reason": reason,
            })

        # 类型转换建议
        if field_profile.inferred_type == "string":
            items.append({
                "field": field_profile.name,
                "issue_type": "TYPE_CONVERSION",
                "action": "尝试转换为数值或日期类型",
                "reason": "字符串可能隐含数值或日期信息",
            })

        # 重复值处理（仅对唯一值少的字符串字段建议）
        if (field_profile.inferred_type in ("string", "bool")
                and profile.row_count > 0
                and field_profile.unique_count == 1):
            items.append({
                "field": field_profile.name,
                "issue_type": "CONSTANT_VALUE",
                "action": "考虑删除该字段",
                "reason": "唯一值为 1，无区分度",
            })

    # 全局重复行建议
    if profile.duplicate_row_count > 0:
        items.append({
            "field": "*",
            "issue_type": "DUPLICATE_ROW",
            "action": f"删除 {profile.duplicate_row_count} 个重复行",
            "reason": "重复行可能影响统计结果",
        })

    # 字段过多提示
    if profile.column_count > _FIELD_COUNT_THRESHOLD:
        items.append({
            "field": "*",
            "issue_type": "TOO_MANY_FIELDS",
            "action": f"字段数 {profile.column_count} 超过 {_FIELD_COUNT_THRESHOLD}，需手动选择关键字段",
            "reason": "字段过多，建议聚焦关键分析字段",
        })

    return items


def _build_analysis_plan_items(profile: DatasetProfile) -> list[dict]:
    """基于字段类型生成分析方案条目。"""
    items: list[dict] = []
    numeric_fields = [
        f for f in profile.field_profiles[:_DETAILED_FIELD_LIMIT]
        if f.inferred_type in ("int", "float")
    ]
    categorical_fields = [
        f for f in profile.field_profiles[:_DETAILED_FIELD_LIMIT]
        if f.inferred_type in ("string", "bool")
    ]

    # 描述性统计
    if numeric_fields:
        target = ", ".join(f.name for f in numeric_fields[:5])
        items.append({
            "analysis_type": "DESCRIPTIVE_STATISTICS",
            "target_fields": target,
            "method": "计算均值、中位数、标准差、分位数",
            "expected_output": "数值字段的描述性统计表",
            "dependencies": [],
        })

    # 分组统计
    if categorical_fields and numeric_fields:
        items.append({
            "analysis_type": "GROUP_STATISTICS",
            "target_fields": f"{categorical_fields[0].name} 分组 vs {numeric_fields[0].name}",
            "method": "按类别字段分组聚合，计算均值/计数",
            "expected_output": "分组统计表",
            "dependencies": [categorical_fields[0].name, numeric_fields[0].name],
        })

    # 相关性分析
    if len(numeric_fields) >= 2:
        items.append({
            "analysis_type": "CORRELATION",
            "target_fields": ", ".join(f.name for f in numeric_fields[:5]),
            "method": "计算 Pearson 相关系数矩阵",
            "expected_output": "相关系数矩阵热图数据",
            "dependencies": [f.name for f in numeric_fields[:5]],
        })

    # 频次分析
    if categorical_fields:
        target = categorical_fields[0].name
        items.append({
            "analysis_type": "FREQUENCY",
            "target_fields": target,
            "method": "统计各类别频次和占比",
            "expected_output": "频次分布表",
            "dependencies": [target],
        })

    # 缺失值分析
    fields_with_missing = [f for f in profile.field_profiles if f.null_count > 0]
    if fields_with_missing:
        items.append({
            "analysis_type": "MISSING_PATTERN",
            "target_fields": ", ".join(f.name for f in fields_with_missing[:5]),
            "method": "分析缺失值的分布模式",
            "expected_output": "缺失值模式报告",
            "dependencies": [f.name for f in fields_with_missing[:5]],
        })

    return items


def _build_chart_plan(profile: DatasetProfile) -> list[dict]:
    """基于字段类型生成图表方案条目。"""
    charts: list[dict] = []
    numeric_fields = [
        f for f in profile.field_profiles[:_DETAILED_FIELD_LIMIT]
        if f.inferred_type in ("int", "float")
    ]
    categorical_fields = [
        f for f in profile.field_profiles[:_DETAILED_FIELD_LIMIT]
        if f.inferred_type in ("string", "bool")
    ]

    # 直方图
    for f in numeric_fields[:3]:
        charts.append({
            "chart_type": "HISTOGRAM",
            "title": f"{f.name} 分布直方图",
            "data_fields": [f.name],
            "description": "展示数值字段的分布形态",
        })

    # 箱线图
    if numeric_fields:
        charts.append({
            "chart_type": "BOXPLOT",
            "title": "数值字段箱线图",
            "data_fields": [f.name for f in numeric_fields[:5]],
            "description": "展示数值字段的分布和异常值",
        })

    # 柱状图
    for f in categorical_fields[:3]:
        charts.append({
            "chart_type": "BAR",
            "title": f"{f.name} 频次柱状图",
            "data_fields": [f.name],
            "description": "展示各类别的频次分布",
        })

    # 散点图
    if len(numeric_fields) >= 2:
        charts.append({
            "chart_type": "SCATTER",
            "title": f"{numeric_fields[0].name} vs {numeric_fields[1].name} 散点图",
            "data_fields": [numeric_fields[0].name, numeric_fields[1].name],
            "description": "展示两个数值字段间的关系",
        })

    return charts


class LocalRuleAnalysisPlanProvider(AnalysisPlanDraftProvider):
    """基于字段类型和缺失率的本地规则生成分析方案候选。"""

    def source_label(self) -> str:
        return "LOCAL_RULE"

    def generate(self, profile: DatasetProfile) -> AnalysisPlanDraft:
        return AnalysisPlanDraft(
            cleaning_plan=_build_cleaning_plan(profile),
            analysis_plan=_build_analysis_plan_items(profile),
            chart_plan=_build_chart_plan(profile),
        )


class FakeAnalysisPlanProvider(AnalysisPlanDraftProvider):
    """测试用确定性提供者 —— 返回固定结构方案。"""

    def source_label(self) -> str:
        return "LOCAL_RULE"

    def generate(self, profile: DatasetProfile) -> AnalysisPlanDraft:
        return AnalysisPlanDraft(
            cleaning_plan=[
                {
                    "field": "*",
                    "issue_type": "DUPLICATE_ROW",
                    "action": "删除重复行",
                    "reason": "测试用确定性方案",
                },
            ],
            analysis_plan=[
                {
                    "analysis_type": "DESCRIPTIVE_STATISTICS",
                    "target_fields": "*",
                    "method": "计算描述性统计",
                    "expected_output": "统计表",
                    "dependencies": [],
                },
            ],
            chart_plan=[
                {
                    "chart_type": "HISTOGRAM",
                    "title": "字段分布直方图",
                    "data_fields": [],
                    "description": "测试用确定性图表方案",
                },
            ],
        )
