"""DeepSeek LLM 驱动的实验要求拆解提供者。

调用 DeepSeek API 将自然语言实验要求拆解为结构化任务单。
LLM 调用失败时降级到 LocalRuleRequirementDraftProvider。
"""

import json
import logging

from pydantic import BaseModel, ValidationError

from app.infrastructure.llm.deepseek_client import DeepSeekClient, DeepSeekError
from app.modules.llm.local_rule_provider import LocalRuleRequirementDraftProvider
from app.modules.requirements.contracts import (
    RequirementPlanPayload,
    RequirementTask,
    ReplicationLevel,
)


logger = logging.getLogger(__name__)


# --- Pydantic 结构化输出校验模型 ---


class DeepSeekTask(BaseModel):
    """LLM 返回的单个任务（用于校验）。"""

    title: str
    description: str
    task_type: str
    reason: str
    source_quote: str | None = None


class DeepSeekReplicationLevel(BaseModel):
    """LLM 返回的复刻层级（用于校验）。"""

    level: str
    label: str
    supported_in_v1: bool
    reason: str
    suggested_scope: str


class DeepSeekRequirementResponse(BaseModel):
    """LLM 返回的完整任务单（用于校验）。

    字段与 RequirementPlanPayload 对齐，校验失败时降级。
    """

    topic: str
    experiment_type: str
    research_subject: str
    required_tasks: list[DeepSeekTask]
    recommended_tasks: list[DeepSeekTask]
    optional_tasks: list[DeepSeekTask]
    out_of_scope_tasks: list[DeepSeekTask]
    unknown_items: list[DeepSeekTask]
    data_requirements: list[str]
    method_requirements: list[str]
    chart_requirements: list[str]
    report_requirements: list[str]
    presentation_requirements: list[str]
    acceptance_criteria: list[str]
    replication_level: DeepSeekReplicationLevel


# --- Prompt 构造 ---


_SYSTEM_PROMPT = """你是一个实验要求分析助手。你的任务是将自然语言实验要求拆解为结构化任务单。

输出要求：
1. 必须返回 JSON 格式
2. JSON 必须包含以下字段：
   - topic: 实验主题（简短）
   - experiment_type: 实验类型
   - research_subject: 研究对象
   - required_tasks: 必须完成的任务列表
   - recommended_tasks: 推荐完成的任务列表
   - optional_tasks: 可选任务列表
   - out_of_scope_tasks: 超出第一版范围的任务列表
   - unknown_items: 需要用户确认的未知项列表
   - data_requirements: 数据要求列表
   - method_requirements: 方法要求列表
   - chart_requirements: 图表要求列表
   - report_requirements: 报告要求列表
   - presentation_requirements: PPT 要求列表
   - acceptance_criteria: 验收条件列表
   - replication_level: 复刻层级对象

每个任务对象包含：title, description, task_type（REQUIRED/RECOMMENDED/OPTIONAL/OUT_OF_SCOPE/UNKNOWN）, reason, source_quote（可选）

replication_level 对象包含：level（L0/L1/L2/L3）, label, supported_in_v1（bool）, reason, suggested_scope

第一版不支持 L3 完整复现，识别为 L3 时标记 supported_in_v1=false 并建议降级到 L2。"""


def _build_user_prompt(requirement_text: str) -> str:
    """构造用户消息。"""
    return f"""请拆解以下实验要求：

---
{requirement_text}
---

请返回 JSON 格式的结构化任务单。"""


# --- DeepSeek Provider 实现 ---


class DeepSeekRequirementDraftProvider:
    """DeepSeek LLM 驱动的实验要求拆解提供者。

    LLM 调用失败时降级到 LocalRuleRequirementDraftProvider。
    """

    def __init__(
        self,
        client: DeepSeekClient,
        fallback: LocalRuleRequirementDraftProvider | None = None,
        temperature: float = 0.3,
    ):
        self._client = client
        self._fallback = fallback or LocalRuleRequirementDraftProvider()
        self._temperature = temperature

    def source_label(self) -> str:
        return "DEEPSEEK"

    def draft(self, requirement_text: str) -> RequirementPlanPayload:
        """调用 DeepSeek 拆解实验要求，失败时降级到 LocalRule。"""
        try:
            raw = self._client.chat_completion(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_prompt(requirement_text)},
                ],
                response_format={"type": "json_object"},
                temperature=self._temperature,
            )
            parsed = self._parse_and_validate(raw)
            return self._to_payload(parsed)
        except (DeepSeekError, ValidationError, ValueError, TypeError) as e:
            logger.warning(f"DeepSeek 实验要求拆解失败，降级到 LocalRule: {e}")
            payload = self._fallback.draft(requirement_text)
            return self._mark_fallback(payload)

    def _parse_and_validate(self, raw: str) -> DeepSeekRequirementResponse:
        """解析 JSON 并用 Pydantic 校验结构。"""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise DeepSeekError(
                code="DEEPSEEK_JSON_PARSE_ERROR",
                message=f"LLM 返回 JSON 解析失败: {e}",
            ) from e
        return DeepSeekRequirementResponse.model_validate(data)

    def _to_payload(self, resp: DeepSeekRequirementResponse) -> RequirementPlanPayload:
        """将校验后的 LLM 响应转为业务 Payload。"""
        return RequirementPlanPayload(
            topic=resp.topic,
            experiment_type=resp.experiment_type,
            research_subject=resp.research_subject,
            required_tasks=[self._to_task(t) for t in resp.required_tasks],
            recommended_tasks=[self._to_task(t) for t in resp.recommended_tasks],
            optional_tasks=[self._to_task(t) for t in resp.optional_tasks],
            out_of_scope_tasks=[self._to_task(t) for t in resp.out_of_scope_tasks],
            unknown_items=[self._to_task(t) for t in resp.unknown_items],
            data_requirements=resp.data_requirements,
            method_requirements=resp.method_requirements,
            chart_requirements=resp.chart_requirements,
            report_requirements=resp.report_requirements,
            presentation_requirements=resp.presentation_requirements,
            acceptance_criteria=resp.acceptance_criteria,
            replication_level=ReplicationLevel(
                level=resp.replication_level.level,
                label=resp.replication_level.label,
                supported_in_v1=resp.replication_level.supported_in_v1,
                reason=resp.replication_level.reason,
                suggested_scope=resp.replication_level.suggested_scope,
            ),
        )

    def _to_task(self, t: DeepSeekTask) -> RequirementTask:
        """将 LLM 任务转为业务任务。"""
        return RequirementTask(
            title=t.title,
            description=t.description,
            task_type=t.task_type,
            reason=t.reason,
            source_quote=t.source_quote,
        )

    def _mark_fallback(self, payload: RequirementPlanPayload) -> RequirementPlanPayload:
        """降级时标记 source_label（通过返回 payload，candidate_source 由 service 层设置）。

        降级时不修改 payload 内容，service 层通过 source_label() 返回值判断。
        """
        return payload
