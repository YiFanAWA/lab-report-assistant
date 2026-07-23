"""DeepSeek LLM 驱动的分析方案生成提供者。

调用 DeepSeek API 基于数据集字段概览生成清洗/分析/图表方案候选。
LLM 调用失败时降级到 LocalRuleAnalysisPlanProvider。

设计决策：
- AnalysisPlan 阶段为字段截断唯一截断点。
- 提供者只接收 DatasetProfile（不含原始数据），不泄露用户数据。
"""

import json
import logging

from pydantic import BaseModel, ValidationError

from app.infrastructure.llm.deepseek_client import DeepSeekClient, DeepSeekError
from app.infrastructure.parsers.dataset_parser import DatasetProfile
from app.modules.llm.analysis_plan_provider import (
    AnalysisPlanDraft,
    LocalRuleAnalysisPlanProvider,
)


logger = logging.getLogger(__name__)


# --- Pydantic 结构化输出校验模型 ---


class DeepSeekAnalysisPlanResponse(BaseModel):
    """LLM 返回的分析方案（用于校验）。"""

    cleaning_plan: list[dict]
    analysis_plan: list[dict]
    chart_plan: list[dict]


# --- Prompt 构造 ---


_SYSTEM_PROMPT = """你是一个数据分析方案生成助手。你的任务是基于数据集字段概览生成清洗、分析和图表方案。

输出要求：
1. 必须返回 JSON 格式：
   {
     "cleaning_plan": [...],
     "analysis_plan": [...],
     "chart_plan": [...]
   }
2. cleaning_plan: 每项包含 field（字段名）, action（清洗动作）, reason（原因）
3. analysis_plan: 每项包含 name（分析名称）, method（方法）, fields（涉及字段）, reason（原因）
4. chart_plan: 每项包含 name（图表名称）, chart_type（类型：histogram/boxplot/heatmap/bar/scatter/pie）, fields（涉及字段）, reason（原因）

生成原则：
- 基于字段类型和缺失率给出合理建议
- 缺失率高的字段优先建议清洗
- 数值字段建议统计分析和可视化
- 分类字段建议分组对比
- 不编造字段不存在的统计方法"""


def _build_user_prompt(profile: DatasetProfile) -> str:
    """构造用户消息，包含字段概览信息。"""
    fields_info = []
    for fp in profile.field_profiles[:20]:  # 限制前 20 个字段
        info = f"- {fp.name}: 类型={fp.inferred_type}, 非空={fp.non_null_count}, 缺失率={fp.null_rate:.2%}"
        if fp.inferred_type in ("int", "float") and fp.min_value is not None:
            info += f", min={fp.min_value}, max={fp.max_value}, mean={fp.mean_value:.2f}"
        fields_info.append(info)

    return f"""数据集概览：
- 总行数: {profile.row_count}
- 总列数: {profile.column_count}
- 完整行数: {profile.complete_row_count}
- 重复行数: {profile.duplicate_row_count}
- 质量评分: {profile.quality_score}

字段概览：
{chr(10).join(fields_info)}

请生成清洗、分析和图表方案（JSON 格式）。"""


# --- DeepSeek Provider 实现 ---


class DeepSeekAnalysisPlanProvider:
    """DeepSeek LLM 驱动的分析方案生成提供者。"""

    def __init__(
        self,
        client: DeepSeekClient,
        fallback: LocalRuleAnalysisPlanProvider | None = None,
        temperature: float = 0.3,
    ):
        self._client = client
        self._fallback = fallback or LocalRuleAnalysisPlanProvider()
        self._temperature = temperature

    def source_label(self) -> str:
        return "DEEPSEEK"

    def generate(self, profile: DatasetProfile) -> AnalysisPlanDraft:
        """调用 DeepSeek 生成分析方案，失败时降级。"""
        try:
            raw = self._client.chat_completion(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_prompt(profile)},
                ],
                response_format={"type": "json_object"},
                temperature=self._temperature,
            )
            parsed = self._parse_and_validate(raw)
            return AnalysisPlanDraft(
                cleaning_plan=parsed.cleaning_plan,
                analysis_plan=parsed.analysis_plan,
                chart_plan=parsed.chart_plan,
            )
        except (DeepSeekError, ValidationError, ValueError, TypeError) as e:
            logger.warning(f"DeepSeek 分析方案生成失败，降级到 LocalRule: {e}")
            return self._fallback.generate(profile)

    def _parse_and_validate(self, raw: str) -> DeepSeekAnalysisPlanResponse:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise DeepSeekError(
                code="DEEPSEEK_JSON_PARSE_ERROR",
                message=f"LLM 返回 JSON 解析失败: {e}",
            ) from e
        return DeepSeekAnalysisPlanResponse.model_validate(data)
