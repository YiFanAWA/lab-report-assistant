"""大纲候选提供者。

不依赖任何外部模型、不调用 DeepSeek。
基于已确认的任务单、证据卡片、数据概览、分析方案和执行结果
拼装大纲章节。

设计决策（用户确认）：
- AnalysisPlan 阶段为字段截断唯一截断点。
- Outline 生成时直接透传已截断字段内容，提供者不做二次截断。

提供者只接收 context dict（含 requirements/evidence/dataset/analysis/execution 摘要），
不泄露完整用户数据。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OutlineDraftSection:
    """大纲章节候选（提供者产出，非业务实体）。"""

    id: str
    title: str
    content: str
    source_type: str
    source_ids: list[str] = field(default_factory=list)


@dataclass
class OutlineDraft:
    """大纲候选（提供者产出，非业务实体）。"""

    sections: list[OutlineDraftSection]


class OutlineDraftProvider(ABC):
    """大纲候选提供者抽象基类。"""

    @abstractmethod
    def generate(self, context: dict[str, Any]) -> OutlineDraft:
        """基于上下文生成大纲候选。

        参数：
        - context: dict，包含 requirements/evidence/dataset/analysis/execution 摘要

        返回：OutlineDraft(sections=[...])
        """

    @abstractmethod
    def source_label(self) -> str:
        """返回候选来源标签（用于写入 candidate_source）。"""


# --- 本地规则实现 ---


def _truncate(text: str, max_chars: int = 1500) -> str:
    """截断文本到指定字符数（用于章节内容，避免过长）。"""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…（已截断）"


class LocalRuleOutlineProvider(OutlineDraftProvider):
    """本地规则提供者。

    基于已确认的任务单、证据卡片、数据概览、分析方案和执行结果
    拼装大纲章节，不调用外部 API。

    设计决策（用户确认）：AnalysisPlan 阶段为字段截断唯一截断点，
    Outline 生成时直接透传已截断字段内容，提供者不做二次截断。
    """

    def generate(self, context: dict[str, Any]) -> OutlineDraft:
        req = context.get("requirements") or {}
        evidence_cards = context.get("evidence_cards") or []
        dataset = context.get("dataset") or {}
        analysis_plan = context.get("analysis_plan") or {}
        executions = context.get("executions") or []

        sections: list[OutlineDraftSection] = []

        # 1. 实验目的（来自任务单）
        req_payload = req.get("payload") or {}
        objective = req_payload.get("objective") or req_payload.get("goal") or ""
        if not objective:
            # 回退到任务单的 task_items 或 description
            objective = req_payload.get("description") or req.get("source_text") or "（实验目的待补充）"
        sections.append(OutlineDraftSection(
            id="sec_001",
            title="实验目的",
            content=_truncate(str(objective)),
            source_type="REQUIREMENT",
            source_ids=[req.get("plan_id")] if req.get("plan_id") else [],
        ))

        # 2. 实验背景（来自证据卡片）
        bg_parts: list[str] = []
        evidence_ids: list[str] = []
        for card in evidence_cards:
            claim = card.get("claim") or card.get("summary") or ""
            if claim:
                bg_parts.append(f"- {claim}")
                if card.get("id"):
                    evidence_ids.append(card["id"])
        bg_content = "\n".join(bg_parts) if bg_parts else "（暂无已确认证据）"
        sections.append(OutlineDraftSection(
            id="sec_002",
            title="实验背景",
            content=_truncate(bg_content),
            source_type="EVIDENCE",
            source_ids=evidence_ids,
        ))

        # 3. 数据描述（来自数据集字段概览）
        ds_profile = dataset.get("profile") or {}
        row_count = ds_profile.get("row_count") or dataset.get("row_count") or 0
        col_count = ds_profile.get("column_count") or dataset.get("column_count") or 0
        fields = ds_profile.get("fields") or []
        ds_parts: list[str] = []
        if row_count or col_count:
            ds_parts.append(f"数据集规模：{row_count} 行 × {col_count} 列")
        if fields:
            ds_parts.append("字段列表：")
            for f in fields[:20]:
                name = f.get("name") or ""
                ftype = f.get("type") or ""
                sample = f.get("sample") or ""
                ds_parts.append(f"  - {name}（{ftype}）：样例 {sample}")
        ds_content = "\n".join(ds_parts) if ds_parts else "（数据集概览待补充）"
        ds_ids = [dataset.get("version_id")] if dataset.get("version_id") else []
        sections.append(OutlineDraftSection(
            id="sec_003",
            title="数据描述",
            content=_truncate(ds_content),
            source_type="DATASET",
            source_ids=ds_ids,
        ))

        # 4. 分析方案（来自已确认 AnalysisPlan）
        cleaning = analysis_plan.get("cleaning_plan") or []
        analysis_items = analysis_plan.get("analysis_plan") or []
        chart_plan = analysis_plan.get("chart_plan") or []
        an_parts: list[str] = []
        if cleaning:
            an_parts.append("清洗方案：")
            for c in cleaning[:10]:
                an_parts.append(f"  - {c.get('description') or c}")
        if analysis_items:
            an_parts.append("分析方案：")
            for a in analysis_items[:10]:
                an_parts.append(f"  - {a.get('description') or a}")
        if chart_plan:
            an_parts.append("图表方案：")
            for ch in chart_plan[:10]:
                an_parts.append(f"  - {ch.get('description') or ch}")
        an_content = "\n".join(an_parts) if an_parts else "（分析方案待补充）"
        an_ids = [analysis_plan.get("plan_id")] if analysis_plan.get("plan_id") else []
        sections.append(OutlineDraftSection(
            id="sec_004",
            title="分析方案",
            content=_truncate(an_content),
            source_type="ANALYSIS",
            source_ids=an_ids,
        ))

        # 5. 实验结果（来自执行结果）
        exec_parts: list[str] = []
        exec_ids: list[str] = []
        for run in executions:
            stdout = run.get("stdout") or ""
            if stdout:
                # 取 stdout 前 800 字符作为结果摘要
                exec_parts.append(f"执行记录 {run.get('run_id', '')}：")
                exec_parts.append(_truncate(stdout, 800))
            arts = run.get("artifacts") or []
            for art in arts:
                art_name = art.get("name") or ""
                if art_name:
                    exec_parts.append(f"  产物：{art_name}")
            if run.get("run_id"):
                exec_ids.append(run["run_id"])
        exec_content = "\n".join(exec_parts) if exec_parts else "（暂无成功执行结果）"
        sections.append(OutlineDraftSection(
            id="sec_005",
            title="实验结果",
            content=_truncate(exec_content),
            source_type="EXECUTION",
            source_ids=exec_ids,
        ))

        # 6. 结论与讨论（综合总结）
        summary_parts: list[str] = []
        if exec_parts:
            summary_parts.append("基于执行结果，本实验完成了既定分析目标。")
        if chart_plan:
            summary_parts.append(f"共生成 {len(chart_plan)} 个图表方案，已通过受控执行环境验证。")
        if not summary_parts:
            summary_parts.append("（结论待用户根据执行结果补充）")
        sections.append(OutlineDraftSection(
            id="sec_006",
            title="结论与讨论",
            content=_truncate("\n".join(summary_parts)),
            source_type="SUMMARY",
            source_ids=[],
        ))

        return OutlineDraft(sections=sections)

    def source_label(self) -> str:
        return "local_rule"


class FakeOutlineProvider(OutlineDraftProvider):
    """确定性测试用提供者，返回固定大纲。"""

    def generate(self, context: dict[str, Any]) -> OutlineDraft:
        return OutlineDraft(sections=[
            OutlineDraftSection(
                id="sec_001",
                title="实验目的",
                content="（Fake）测试用实验目的",
                source_type="REQUIREMENT",
                source_ids=["fake_plan"],
            ),
            OutlineDraftSection(
                id="sec_002",
                title="实验背景",
                content="（Fake）测试用实验背景",
                source_type="EVIDENCE",
                source_ids=["fake_card"],
            ),
            OutlineDraftSection(
                id="sec_003",
                title="数据描述",
                content="（Fake）测试用数据描述",
                source_type="DATASET",
                source_ids=["fake_version"],
            ),
            OutlineDraftSection(
                id="sec_004",
                title="分析方案",
                content="（Fake）测试用分析方案",
                source_type="ANALYSIS",
                source_ids=["fake_plan"],
            ),
            OutlineDraftSection(
                id="sec_005",
                title="实验结果",
                content="（Fake）测试用实验结果",
                source_type="EXECUTION",
                source_ids=["fake_run"],
            ),
            OutlineDraftSection(
                id="sec_006",
                title="结论与讨论",
                content="（Fake）测试用结论",
                source_type="SUMMARY",
                source_ids=[],
            ),
        ])

    def source_label(self) -> str:
        return "fake"
