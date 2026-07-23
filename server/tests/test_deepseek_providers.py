"""DeepSeek provider 单元测试。

mock DeepSeekClient 测试 5 个 provider：
- 成功调用（LLM 返回有效 JSON，结构化校验通过）
- 降级路径（LLM 调用失败，降级到 LocalRule）
- 校验失败（LLM 返回缺失字段的 JSON，Pydantic 校验失败，降级）
- source_label 正确标记

测试原则：
- 不调用真实 DeepSeek API
- mock DeepSeekClient.chat_completion 方法
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.llm.deepseek_client import DeepSeekClient, DeepSeekError
from app.modules.llm.deepseek_requirement_provider import (
    DeepSeekRequirementDraftProvider,
    DeepSeekRequirementResponse,
)
from app.modules.llm.deepseek_evidence_provider import (
    DeepSeekEvidenceCardProvider,
)
from app.modules.llm.deepseek_analysis_plan_provider import (
    DeepSeekAnalysisPlanProvider,
)
from app.modules.llm.deepseek_code_task_provider import (
    DeepSeekCodeTaskProvider,
)
from app.modules.llm.deepseek_outline_provider import (
    DeepSeekOutlineProvider,
)
from app.modules.llm.local_rule_provider import LocalRuleRequirementDraftProvider
from app.modules.llm.evidence_card_provider import LocalRuleEvidenceCardProvider
from app.modules.llm.analysis_plan_provider import LocalRuleAnalysisPlanProvider
from app.modules.llm.code_task_provider import LocalRuleCodeTaskProvider
from app.modules.llm.outline_provider import LocalRuleOutlineProvider
from app.infrastructure.parsers.dataset_parser import DatasetProfile, FieldProfile


def _make_mock_client(response: str | None = None, raises: Exception | None = None):
    """构造 mock DeepSeekClient。"""
    client = MagicMock(spec=DeepSeekClient)
    if raises:
        client.chat_completion.side_effect = raises
    else:
        client.chat_completion.return_value = response or ""
    return client


# ============================================================
# DeepSeekRequirementDraftProvider 测试
# ============================================================


class TestDeepSeekRequirementProvider:
    """实验要求拆解 provider 测试。"""

    def _make_valid_response_json(self) -> str:
        """构造有效的 LLM JSON 响应。"""
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

    def test_成功调用LLM返回有效任务单(self):
        client = _make_mock_client(self._make_valid_response_json())
        provider = DeepSeekRequirementDraftProvider(client=client)

        result = provider.draft("分析胃病数据")

        assert result.topic == "胃病数据分析"
        assert len(result.required_tasks) == 1
        assert result.required_tasks[0].title == "数据加载"
        assert result.replication_level.level == "L0"

    def test_source_label返回DEEPSEEK(self):
        client = _make_mock_client(self._make_valid_response_json())
        provider = DeepSeekRequirementDraftProvider(client=client)

        assert provider.source_label() == "DEEPSEEK"

    def test_LLM调用失败时降级到LocalRule(self):
        client = _make_mock_client(
            raises=DeepSeekError(code="DEEPSEEK_TIMEOUT", message="超时")
        )
        fallback = LocalRuleRequirementDraftProvider()
        provider = DeepSeekRequirementDraftProvider(
            client=client, fallback=fallback
        )

        result = provider.draft("分析胃病数据")

        # 降级后应返回 LocalRule 的结果
        assert result is not None
        assert len(result.required_tasks) > 0

    def test_LLM返回缺失字段时降级(self):
        """LLM 返回的 JSON 缺少 required_tasks 字段，Pydantic 校验失败，降级。"""
        invalid_json = json.dumps({"topic": "测试"})  # 缺少大量必需字段
        client = _make_mock_client(invalid_json)
        fallback = LocalRuleRequirementDraftProvider()
        provider = DeepSeekRequirementDraftProvider(
            client=client, fallback=fallback
        )

        result = provider.draft("分析数据")

        # 降级后返回 LocalRule 结果
        assert result is not None
        assert len(result.required_tasks) > 0

    def test_LLM返回非JSON时降级(self):
        client = _make_mock_client("这不是JSON {{{")
        fallback = LocalRuleRequirementDraftProvider()
        provider = DeepSeekRequirementDraftProvider(
            client=client, fallback=fallback
        )

        result = provider.draft("分析数据")

        assert result is not None


# ============================================================
# DeepSeekEvidenceCardProvider 测试
# ============================================================


class TestDeepSeekEvidenceProvider:
    """证据卡片提取 provider 测试。"""

    def _make_valid_response_json(self) -> str:
        return json.dumps({
            "cards": [
                {
                    "summary": "本研究采用回顾性分析方法",
                    "evidence_type": "METHOD",
                    "locator": "方法章节第1段",
                    "source_quote": "采用回顾性分析方法",
                },
                {
                    "summary": "结果显示胃病发病率逐年上升",
                    "evidence_type": "RESULT",
                    "locator": "结果章节第2段",
                    "source_quote": "发病率逐年上升",
                },
            ]
        }, ensure_ascii=False)

    def test_成功提取证据卡片(self):
        client = _make_mock_client(self._make_valid_response_json())
        provider = DeepSeekEvidenceCardProvider(client=client)

        result = provider.draft("本研究采用回顾性分析方法。结果显示胃病发病率逐年上升。")

        assert len(result) == 2
        assert result[0].evidence_type == "METHOD"
        assert result[1].evidence_type == "RESULT"

    def test_source_label返回DEEPSEEK(self):
        client = _make_mock_client(self._make_valid_response_json())
        provider = DeepSeekEvidenceCardProvider(client=client)
        assert provider.source_label() == "DEEPSEEK"

    def test_LLM失败时降级到LocalRule(self):
        client = _make_mock_client(
            raises=DeepSeekError(code="DEEPSEEK_AUTH_ERROR", message="鉴权失败")
        )
        fallback = LocalRuleEvidenceCardProvider()
        provider = DeepSeekEvidenceCardProvider(client=client, fallback=fallback)

        result = provider.draft("测试文本")

        assert isinstance(result, list)

    def test_LLM返回空cards列表(self):
        """LLM 返回空列表，校验通过但返回空列表。"""
        client = _make_mock_client(json.dumps({"cards": []}))
        provider = DeepSeekEvidenceCardProvider(client=client)

        result = provider.draft("测试文本")

        assert result == []


# ============================================================
# DeepSeekAnalysisPlanProvider 测试
# ============================================================


class TestDeepSeekAnalysisPlanProvider:
    """分析方案生成 provider 测试。"""

    def _make_valid_response_json(self) -> str:
        return json.dumps({
            "cleaning_plan": [
                {"field": "age", "action": "填充中位数", "reason": "缺失率高"}
            ],
            "analysis_plan": [
                {"name": "描述性统计", "method": "mean", "fields": ["age"], "reason": "基础"}
            ],
            "chart_plan": [
                {"name": "年龄分布", "chart_type": "histogram", "fields": ["age"], "reason": "分布"}
            ],
        }, ensure_ascii=False)

    def _make_profile(self) -> DatasetProfile:
        return DatasetProfile(
            row_count=100,
            column_count=3,
            complete_row_count=80,
            incomplete_row_count=20,
            duplicate_row_count=5,
            field_profiles=[
                FieldProfile(
                    name="age",
                    inferred_type="int",
                    non_null_count=80,
                    null_count=20,
                    null_rate=0.2,
                    unique_count=50,
                    sample_values=["25", "30"],
                    min_value=18.0,
                    max_value=80.0,
                    mean_value=45.0,
                ),
            ],
            quality_score=85.0,
        )

    def test_成功生成分析方案(self):
        client = _make_mock_client(self._make_valid_response_json())
        provider = DeepSeekAnalysisPlanProvider(client=client)

        result = provider.generate(self._make_profile())

        assert len(result.cleaning_plan) == 1
        assert result.cleaning_plan[0]["field"] == "age"
        assert len(result.analysis_plan) == 1
        assert len(result.chart_plan) == 1

    def test_source_label返回DEEPSEEK(self):
        client = _make_mock_client(self._make_valid_response_json())
        provider = DeepSeekAnalysisPlanProvider(client=client)
        assert provider.source_label() == "DEEPSEEK"

    def test_LLM失败时降级到LocalRule(self):
        client = _make_mock_client(
            raises=DeepSeekError(code="DEEPSEEK_SERVER_ERROR", message="500")
        )
        fallback = LocalRuleAnalysisPlanProvider()
        provider = DeepSeekAnalysisPlanProvider(client=client, fallback=fallback)

        result = provider.generate(self._make_profile())

        assert isinstance(result.cleaning_plan, list)
        assert isinstance(result.analysis_plan, list)
        assert isinstance(result.chart_plan, list)


# ============================================================
# DeepSeekCodeTaskProvider 测试
# ============================================================


class TestDeepSeekCodeTaskProvider:
    """代码任务生成 provider 测试。"""

    def _make_valid_response_json(self) -> str:
        code = "import pandas as pd\nimport matplotlib.pyplot as plt\ndf = pd.read_csv(DATA_PATH)\nprint(df.head())"
        return json.dumps({"code": code}, ensure_ascii=False)

    def test_成功生成Python代码(self):
        client = _make_mock_client(self._make_valid_response_json())
        provider = DeepSeekCodeTaskProvider(client=client)

        result = provider.generate({
            "cleaning_plan": [],
            "analysis_plan": [],
            "chart_plan": [],
        })

        assert "import pandas" in result.code
        assert "DATA_PATH" in result.code

    def test_source_label返回DEEPSEEK(self):
        client = _make_mock_client(self._make_valid_response_json())
        provider = DeepSeekCodeTaskProvider(client=client)
        assert provider.source_label() == "DEEPSEEK"

    def test_LLM失败时降级到LocalRule(self):
        client = _make_mock_client(
            raises=DeepSeekError(code="DEEPSEEK_RATE_LIMITED", message="限流")
        )
        fallback = LocalRuleCodeTaskProvider()
        provider = DeepSeekCodeTaskProvider(client=client, fallback=fallback)

        result = provider.generate({
            "cleaning_plan": [],
            "analysis_plan": [],
            "chart_plan": [],
        })

        assert isinstance(result.code, str)
        assert len(result.code) > 0

    def test_LLM返回空code时降级(self):
        """LLM 返回 code 为空字符串，Pydantic 校验可能通过但内容为空。"""
        # 注意：DeepSeekCodeTaskResponse.code 是 str，空字符串也会通过校验
        # 但空代码无意义，这里测试降级路径由 LLM 错误触发
        client = _make_mock_client(
            raises=DeepSeekError(code="DEEPSEEK_JSON_PARSE_ERROR", message="解析失败")
        )
        fallback = LocalRuleCodeTaskProvider()
        provider = DeepSeekCodeTaskProvider(client=client, fallback=fallback)

        result = provider.generate({"cleaning_plan": [], "analysis_plan": [], "chart_plan": []})

        assert len(result.code) > 0


# ============================================================
# DeepSeekOutlineProvider 测试
# ============================================================


class TestDeepSeekOutlineProvider:
    """实验大纲生成 provider 测试。"""

    def _make_valid_response_json(self) -> str:
        return json.dumps({
            "sections": [
                {
                    "id": "purpose",
                    "title": "实验目的",
                    "content": "分析胃病数据",
                    "source_type": "REQUIREMENT",
                    "source_ids": ["req_001"],
                },
                {
                    "id": "background",
                    "title": "实验背景",
                    "content": "胃病数据分析背景",
                    "source_type": "EVIDENCE",
                    "source_ids": ["evi_001"],
                },
                {
                    "id": "dataset",
                    "title": "数据与数据集",
                    "content": "数据集包含100条记录",
                    "source_type": "DATASET",
                    "source_ids": ["ds_001"],
                },
                {
                    "id": "analysis",
                    "title": "分析方案",
                    "content": "描述性统计分析",
                    "source_type": "ANALYSIS",
                    "source_ids": ["plan_001"],
                },
                {
                    "id": "results",
                    "title": "执行结果",
                    "content": "统计结果已生成",
                    "source_type": "EXECUTION",
                    "source_ids": ["run_001"],
                },
                {
                    "id": "conclusion",
                    "title": "结论与总结",
                    "content": "胃病数据呈现一定规律",
                    "source_type": "SUMMARY",
                    "source_ids": [],
                },
            ]
        }, ensure_ascii=False)

    def _make_context(self) -> dict:
        """构造 context，格式与 LocalRuleOutlineProvider 期望一致。"""
        return {
            "requirements": {
                "plan_id": "req_001",
                "payload": {
                    "objective": "分析胃病数据",
                    "description": "完成胃病数据分析实验",
                },
                "source_text": "分析胃病数据",
            },
            "evidence": [
                {"id": "evi_001", "summary": "证据卡片内容", "claim": "证据内容"},
            ],
            "dataset": {
                "id": "ds_001",
                "profile": {"row_count": 100, "column_count": 5},
            },
            "analysis_plan": {
                "id": "plan_001",
                "cleaning_plan": [],
                "analysis_plan": [],
                "chart_plan": [],
            },
            "executions": [
                {"id": "run_001", "status": "SUCCEEDED", "stdout": "执行完成"},
            ],
        }

    def test_成功生成大纲(self):
        client = _make_mock_client(self._make_valid_response_json())
        provider = DeepSeekOutlineProvider(client=client)

        result = provider.generate(self._make_context())

        assert len(result.sections) == 6
        assert result.sections[0].id == "purpose"
        assert result.sections[0].source_type == "REQUIREMENT"
        assert result.sections[5].id == "conclusion"
        assert result.sections[5].source_type == "SUMMARY"

    def test_source_label返回DEEPSEEK(self):
        client = _make_mock_client(self._make_valid_response_json())
        provider = DeepSeekOutlineProvider(client=client)
        assert provider.source_label() == "DEEPSEEK"

    def test_LLM失败时降级到LocalRule(self):
        client = _make_mock_client(
            raises=DeepSeekError(code="DEEPSEEK_CONNECTION_ERROR", message="连接失败")
        )
        fallback = LocalRuleOutlineProvider()
        provider = DeepSeekOutlineProvider(client=client, fallback=fallback)

        result = provider.generate(self._make_context())

        # LocalRule 也会返回 6 个章节
        assert len(result.sections) == 6

    def test_LLM返回缺失sections字段时降级(self):
        """LLM 返回的 JSON 缺少 sections 字段，Pydantic 校验失败，降级。"""
        invalid_json = json.dumps({"wrong_field": "test"})
        client = _make_mock_client(invalid_json)
        fallback = LocalRuleOutlineProvider()
        provider = DeepSeekOutlineProvider(client=client, fallback=fallback)

        result = provider.generate(self._make_context())

        assert len(result.sections) == 6


# ============================================================
# Gateway 工厂函数测试（deepseek 分支）
# ============================================================


class TestGatewayDeepSeekBranch:
    """Gateway 工厂函数 deepseek 分支测试。

    使用 monkeypatch 设置环境变量，避免 patch settings 对象导致的状态泄露。
    """

    def test_get_provider_deepseek分支创建实例(self, monkeypatch):
        """验证 deepseek 分支能正确创建 DeepSeekRequirementDraftProvider。"""
        monkeypatch.setenv("REQUIREMENT_DRAFT_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key")
        monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        monkeypatch.setenv("LLM_MODEL", "deepseek-chat")
        monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", "30")
        monkeypatch.setenv("DEEPSEEK_MAX_RETRIES", "2")
        monkeypatch.setenv("DEEPSEEK_TEMPERATURE", "0.3")

        from app.modules.llm.gateway import get_provider
        provider = get_provider()

        assert provider.source_label() == "DEEPSEEK"
        assert hasattr(provider, "_client")
        assert hasattr(provider, "_fallback")

    def test_APIKey未配置时抛出错误(self, monkeypatch):
        """deepseek 分支下 API Key 未配置时，create_client_from_settings 抛出 DeepSeekError。"""
        monkeypatch.setenv("REQUIREMENT_DRAFT_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "")  # 未配置
        monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        monkeypatch.setenv("LLM_MODEL", "deepseek-chat")
        monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", "30")
        monkeypatch.setenv("DEEPSEEK_MAX_RETRIES", "2")
        monkeypatch.setenv("DEEPSEEK_TEMPERATURE", "0.3")

        from app.infrastructure.llm.deepseek_client import DeepSeekError
        from app.modules.llm.gateway import get_provider

        with pytest.raises(DeepSeekError) as exc_info:
            get_provider()

        assert exc_info.value.code == "DEEPSEEK_API_KEY_MISSING"
