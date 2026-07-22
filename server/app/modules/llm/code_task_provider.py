"""代码任务候选提供者。

不依赖任何外部模型、不调用 DeepSeek。
基于已确认 AnalysisPlan 的 cleaning/analysis/chart plan 拼装可执行 Python 代码。

设计决策（用户确认）：
- AnalysisPlan 阶段完成的字段截断为唯一截断点。
- CodeTask 生成时直接透传已截断的字段内容，不再做任何二次截断处理。
- 字段过多时由 AnalysisPlanProvider 处理，CodeTask 只消费已截断后的方案。

提供者只接收 AnalysisPlan 的 dict 形式（不含原始数据），不泄露用户数据。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import json


@dataclass
class CodeTaskDraft:
    """代码任务候选（提供者产出，非业务实体）。

    code 是完整可执行 Python 脚本，包含数据读取、清洗、分析、可视化逻辑。
    执行环境会注入 DATA_PATH 和 OUTPUT_DIR 变量。
    """

    code: str


class CodeTaskDraftProvider(ABC):
    """代码任务候选提供者抽象基类。"""

    @abstractmethod
    def generate(self, analysis_plan: dict, dataset_profile: dict | None = None) -> CodeTaskDraft:
        """从已确认分析方案生成 Python 代码候选。

        参数：
        - analysis_plan: dict，包含 cleaning_plan, analysis_plan, chart_plan 三个 list[dict]
        - dataset_profile: dict，可选，包含字段信息用于代码生成

        返回：CodeTaskDraft(code=完整可执行 Python 脚本)
        """

    @abstractmethod
    def source_label(self) -> str:
        """返回候选来源标签（用于写入 candidate_source）。"""


# --- 本地规则实现 ---


_HEADER = '''"""由实验报告助手受控执行环境生成的 Python 代码。

来源：LocalRuleCodeTaskProvider
说明：基于已确认 AnalysisPlan 的清洗/分析/图表方案拼装。

环境变量（由执行环境注入）：
- DATA_PATH: 数据集文件绝对路径
- OUTPUT_DIR: 产物输出目录绝对路径
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

# 数据读取（根据扩展名自动选择 read_csv 或 read_excel）
_data_path = DATA_PATH
if _data_path.lower().endswith((".xlsx", ".xls")):
    df = pd.read_excel(_data_path)
else:
    df = pd.read_csv(_data_path)

print(f"数据加载完成: {len(df)} 行, {len(df.columns)} 列")
'''


def _parse_plan_items(plan_json: str | list) -> list[dict]:
    """将 AnalysisPlan 的 JSON 字符串或已解析的 list 转为 list[dict]。"""
    if isinstance(plan_json, str):
        try:
            parsed = json.loads(plan_json)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    if isinstance(plan_json, list):
        return plan_json
    return []


def _build_cleaning_code(cleaning_plan: list[dict]) -> str:
    """基于清洗方案生成清洗代码。

    注意：字段截断由 AnalysisPlan 阶段完成，这里直接透传，不二次截断。
    """
    if not cleaning_plan:
        return "# 无清洗步骤\n"

    lines: list[str] = ["# === 数据清洗 ==="]
    for i, item in enumerate(cleaning_plan, 1):
        issue_type = item.get("issue_type", "")
        field = item.get("field", "")
        action = item.get("action", "")
        reason = item.get("reason", "")

        lines.append(f"# 步骤 {i}: {action}（{reason}）")

        if issue_type == "MISSING_VALUE":
            if field == "*":
                lines.append("df = df.dropna()  # 删除含缺失值的行")
            else:
                # 按字段类型填充（运行时根据 dtype 判断）
                lines.append(f"if df['{field}'].dtype in ('int64', 'float64'):")
                lines.append(f"    df['{field}'] = df['{field}'].fillna(df['{field}'].median())")
                lines.append("else:")
                lines.append(f"    df['{field}'] = df['{field}'].fillna(df['{field}'].mode().iloc[0] if len(df['{field}'].mode()) > 0 else '未知')")
        elif issue_type == "TYPE_CONVERSION":
            if field != "*":
                lines.append(f"# 尝试转换 {field} 类型")
                lines.append(f"df['{field}'] = pd.to_numeric(df['{field}'], errors='ignore')")
        elif issue_type == "DUPLICATE_ROW":
            lines.append("df = df.drop_duplicates()")
        elif issue_type == "CONSTANT_VALUE":
            if field != "*":
                lines.append(f"df = df.drop(columns=['{field}'], errors='ignore')")
        elif issue_type == "TOO_MANY_FIELDS":
            lines.append(f"# 提示：{action}")

    lines.append("print('清洗完成')")
    return "\n".join(lines) + "\n"


def _build_analysis_code(analysis_plan: list[dict]) -> str:
    """基于分析方案生成分析代码，结果保存到 OUTPUT_DIR。"""
    if not analysis_plan:
        return "# 无分析步骤\n"

    lines: list[str] = ["# === 数据分析 ==="]
    for i, item in enumerate(analysis_plan, 1):
        analysis_type = item.get("analysis_type", "")
        target_fields = item.get("target_fields", "")
        method = item.get("method", "")
        expected_output = item.get("expected_output", "")

        lines.append(f"# 步骤 {i}: {method}")
        lines.append(f"# 预期输出: {expected_output}")

        if analysis_type == "DESCRIPTIVE_STATISTICS":
            lines.append("desc = df.describe()")
            lines.append("desc.to_csv(OUTPUT_DIR + '/descriptive_stats.csv')")
            lines.append("print('描述性统计完成')")
        elif analysis_type == "GROUP_STATISTICS":
            # target_fields 形如 "sex 分组 vs age"
            lines.append(f"# 分组字段: {target_fields}")
            lines.append("numeric_cols = df.select_dtypes(include=[np.number]).columns")
            lines.append("if len(numeric_cols) > 0:")
            lines.append("    group_result = df.groupby(df.select_dtypes(include=['object', 'bool']).columns[0] if len(df.select_dtypes(include=['object', 'bool']).columns) > 0 else df.columns[0])[numeric_cols].mean()")
            lines.append("    group_result.to_csv(OUTPUT_DIR + '/group_stats.csv')")
            lines.append("    print('分组统计完成')")
        elif analysis_type == "CORRELATION":
            lines.append("numeric_df = df.select_dtypes(include=[np.number])")
            lines.append("if len(numeric_df.columns) >= 2:")
            lines.append("    corr = numeric_df.corr()")
            lines.append("    corr.to_csv(OUTPUT_DIR + '/correlation.csv')")
            lines.append("    print('相关性分析完成')")
        elif analysis_type == "FREQUENCY":
            if target_fields and target_fields != "*":
                lines.append(f"freq = df['{target_fields.split()[0]}'].value_counts()")
                lines.append("freq.to_csv(OUTPUT_DIR + '/frequency.csv')")
                lines.append("print('频次分析完成')")
        elif analysis_type == "MISSING_PATTERN":
            lines.append("missing = df.isnull().sum()")
            lines.append("missing.to_csv(OUTPUT_DIR + '/missing_pattern.csv')")
            lines.append("print('缺失值分析完成')")
        else:
            lines.append(f"print('未知分析类型: {analysis_type}')")

    return "\n".join(lines) + "\n"


def _build_chart_code(chart_plan: list[dict]) -> str:
    """基于图表方案生成可视化代码，图表保存到 OUTPUT_DIR。"""
    if not chart_plan:
        return "# 无图表步骤\n"

    lines: list[str] = ["# === 数据可视化 ==="]
    for i, item in enumerate(chart_plan, 1):
        chart_type = item.get("chart_type", "")
        title = item.get("title", f"chart_{i}")
        data_fields = item.get("data_fields", [])
        description = item.get("description", "")

        # 生成安全的文件名
        safe_name = title.replace(" ", "_").replace("/", "_")[:50]
        lines.append(f"# 图表 {i}: {title}（{description}）")

        if chart_type == "HISTOGRAM":
            if data_fields:
                for field in data_fields:
                    lines.append(f"plt.figure(figsize=(8, 5))")
                    lines.append(f"if '{field}' in df.columns:")
                    lines.append(f"    df['{field}'].hist(bins=30)")
                    lines.append(f"    plt.title('{title}')")
                    lines.append(f"    plt.xlabel('{field}')")
                    lines.append(f"    plt.ylabel('频次')")
                    lines.append(f"    plt.savefig(OUTPUT_DIR + '/{safe_name}.png', dpi=100, bbox_inches='tight')")
                    lines.append(f"    plt.close()")
            else:
                lines.append("numeric_cols = df.select_dtypes(include=[np.number]).columns")
                lines.append("if len(numeric_cols) > 0:")
                lines.append("    plt.figure(figsize=(8, 5))")
                lines.append("    df[numeric_cols[0]].hist(bins=30)")
                lines.append(f"    plt.title('{title}')")
                lines.append("    plt.savefig(OUTPUT_DIR + '/{safe_name}.png', dpi=100, bbox_inches='tight')")
                lines.append("    plt.close()")
        elif chart_type == "BOXPLOT":
            lines.append("numeric_df = df.select_dtypes(include=[np.number])")
            lines.append("if len(numeric_df.columns) > 0:")
            lines.append("    plt.figure(figsize=(10, 6))")
            lines.append("    numeric_df.boxplot()")
            lines.append(f"    plt.title('{title}')")
            lines.append("    plt.savefig(OUTPUT_DIR + '/{safe_name}.png', dpi=100, bbox_inches='tight')")
            lines.append("    plt.close()")
        elif chart_type == "BAR":
            if data_fields:
                field = data_fields[0]
                lines.append(f"plt.figure(figsize=(8, 5))")
                lines.append(f"if '{field}' in df.columns:")
                lines.append(f"    df['{field}'].value_counts().plot(kind='bar')")
                lines.append(f"    plt.title('{title}')")
                lines.append(f"    plt.ylabel('频次')")
                lines.append(f"    plt.savefig(OUTPUT_DIR + '/{safe_name}.png', dpi=100, bbox_inches='tight')")
                lines.append(f"    plt.close()")
        elif chart_type == "SCATTER":
            if len(data_fields) >= 2:
                f1, f2 = data_fields[0], data_fields[1]
                lines.append(f"plt.figure(figsize=(8, 5))")
                lines.append(f"if '{f1}' in df.columns and '{f2}' in df.columns:")
                lines.append(f"    plt.scatter(df['{f1}'], df['{f2}'])")
                lines.append(f"    plt.title('{title}')")
                lines.append(f"    plt.xlabel('{f1}')")
                lines.append(f"    plt.ylabel('{f2}')")
                lines.append(f"    plt.savefig(OUTPUT_DIR + '/{safe_name}.png', dpi=100, bbox_inches='tight')")
                lines.append(f"    plt.close()")
        else:
            lines.append(f"print('未知图表类型: {chart_type}')")

    lines.append("print('可视化完成')")
    return "\n".join(lines) + "\n"


class LocalRuleCodeTaskProvider(CodeTaskDraftProvider):
    """基于 AnalysisPlan 拼装 Python 代码的本地规则提供者。

    设计决策：AnalysisPlan 阶段完成的字段截断为唯一截断点。
    本提供者直接透传已截断的字段内容，不再做任何二次截断处理。
    """

    def source_label(self) -> str:
        return "LOCAL_RULE"

    def generate(self, analysis_plan: dict, dataset_profile: dict | None = None) -> CodeTaskDraft:
        cleaning_plan = _parse_plan_items(analysis_plan.get("cleaning_plan", []))
        analysis_plan_items = _parse_plan_items(analysis_plan.get("analysis_plan", []))
        chart_plan = _parse_plan_items(analysis_plan.get("chart_plan", []))

        # 拼装完整代码
        parts = [
            _HEADER,
            _build_cleaning_code(cleaning_plan),
            _build_analysis_code(analysis_plan_items),
            _build_chart_code(chart_plan),
            'print("全部步骤完成")\n',
        ]

        return CodeTaskDraft(code="\n".join(parts))


class FakeCodeTaskProvider(CodeTaskDraftProvider):
    """测试用确定性提供者 —— 返回固定最小代码。"""

    def source_label(self) -> str:
        return "LOCAL_RULE"

    def generate(self, analysis_plan: dict, dataset_profile: dict | None = None) -> CodeTaskDraft:
        code = (
            "# 测试用确定性代码\n"
            "import pandas as pd\n"
            "df = pd.read_csv(DATA_PATH)\n"
            "print(f'rows={len(df)}')\n"
            "df.describe().to_csv(OUTPUT_DIR + '/stats.csv')\n"
        )
        return CodeTaskDraft(code=code)
