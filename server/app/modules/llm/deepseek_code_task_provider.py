"""DeepSeek LLM 驱动的代码任务生成提供者。

调用 DeepSeek API 基于已确认分析方案生成 Python 代码候选。
LLM 调用失败时降级到 LocalRuleCodeTaskProvider。

设计决策：
- AnalysisPlan 阶段为字段截断唯一截断点。
- CodeTask 生成时直接透传已截断字段内容，不做二次截断。
- 提供者只接收 AnalysisPlan 的 dict 形式（不含原始数据），不泄露用户数据。
"""

import json
import logging

from pydantic import BaseModel, ValidationError

from app.infrastructure.llm.deepseek_client import DeepSeekClient, DeepSeekError
from app.modules.llm.code_task_provider import (
    CodeTaskDraft,
    LocalRuleCodeTaskProvider,
)


logger = logging.getLogger(__name__)


# --- Pydantic 结构化输出校验模型 ---


class DeepSeekCodeTaskResponse(BaseModel):
    """LLM 返回的代码任务（用于校验）。"""

    code: str


# --- Prompt 构造 ---


_SYSTEM_PROMPT = """你是一个 Python 数据分析代码生成助手。你的任务是基于已确认的分析方案生成可执行的 Python 代码。

代码要求：
1. 代码必须是完整可执行的 Python 脚本
2. 执行环境会注入以下变量：
   - DATA_PATH: 数据集文件路径（CSV 或 Excel）
   - OUTPUT_DIR: 输出目录路径
3. 代码应包含：
   - 数据读取（使用 pandas）
   - 数据清洗（按 cleaning_plan）
   - 统计分析（按 analysis_plan）
   - 图表生成（按 chart_plan，使用 matplotlib，保存到 OUTPUT_DIR）
   - 表格导出（CSV 格式，保存到 OUTPUT_DIR）
4. 图表保存格式：{OUTPUT_DIR}/{图表名}.png
5. 表格保存格式：{OUTPUT_DIR}/{表格名}.csv
6. 不使用 shell=True，不访问网络，不读写 OUTPUT_DIR 之外的路径

输出要求：
- 必须返回 JSON 格式：{"code": "完整 Python 代码字符串"}
- 代码字符串中的换行使用 \\n 转义"""


def _build_user_prompt(analysis_plan: dict) -> str:
    """构造用户消息。"""
    return f"""已确认的分析方案：

{json.dumps(analysis_plan, ensure_ascii=False, indent=2)}

请生成可执行的 Python 代码（JSON 格式）。"""


# --- DeepSeek Provider 实现 ---


class DeepSeekCodeTaskProvider:
    """DeepSeek LLM 驱动的代码任务生成提供者。"""

    def __init__(
        self,
        client: DeepSeekClient,
        fallback: LocalRuleCodeTaskProvider | None = None,
        temperature: float = 0.3,
    ):
        self._client = client
        self._fallback = fallback or LocalRuleCodeTaskProvider()
        self._temperature = temperature

    def source_label(self) -> str:
        return "DEEPSEEK"

    def generate(
        self, analysis_plan: dict, dataset_profile: dict | None = None
    ) -> CodeTaskDraft:
        """调用 DeepSeek 生成 Python 代码，失败时降级。"""
        try:
            raw = self._client.chat_completion(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_prompt(analysis_plan)},
                ],
                response_format={"type": "json_object"},
                temperature=self._temperature,
            )
            parsed = self._parse_and_validate(raw)
            return CodeTaskDraft(code=parsed.code)
        except (DeepSeekError, ValidationError, ValueError, TypeError) as e:
            logger.warning(f"DeepSeek 代码任务生成失败，降级到 LocalRule: {e}")
            return self._fallback.generate(analysis_plan, dataset_profile)

    def _parse_and_validate(self, raw: str) -> DeepSeekCodeTaskResponse:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise DeepSeekError(
                code="DEEPSEEK_JSON_PARSE_ERROR",
                message=f"LLM 返回 JSON 解析失败: {e}",
            ) from e
        return DeepSeekCodeTaskResponse.model_validate(data)
