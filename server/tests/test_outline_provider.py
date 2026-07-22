"""大纲候选提供者测试。

覆盖 LocalRuleOutlineProvider 和 FakeOutlineProvider 的章节生成逻辑：
- 基于 context dict 生成 6 个章节
- 章节来源标记正确（REQUIREMENT/EVIDENCE/DATASET/ANALYSIS/EXECUTION/SUMMARY）
- 空上下文回退到待补充占位
- source_ids 正确关联
- _truncate 截断行为
"""

from app.modules.llm.outline_provider import (
    LocalRuleOutlineProvider,
    FakeOutlineProvider,
    OutlineDraftProvider,
    _truncate,
)


class TestLocalRuleOutlineProvider:
    """本地规则提供者测试。"""

    def test_implements_abstract(self):
        """LocalRuleOutlineProvider 是 OutlineDraftProvider 的具体实现。"""
        provider = LocalRuleOutlineProvider()
        assert isinstance(provider, OutlineDraftProvider)

    def test_source_label(self):
        """source_label 返回 local_rule。"""
        assert LocalRuleOutlineProvider().source_label() == "local_rule"

    def test_generates_six_sections_with_empty_context(self):
        """空上下文也返回 6 个章节（带待补充占位）。"""
        provider = LocalRuleOutlineProvider()
        draft = provider.generate(context={})

        assert len(draft.sections) == 6
        ids = [s.id for s in draft.sections]
        assert ids == ["sec_001", "sec_002", "sec_003",
                       "sec_004", "sec_005", "sec_006"]

    def test_section_source_types(self):
        """6 个章节的 source_type 严格对应。"""
        provider = LocalRuleOutlineProvider()
        draft = provider.generate(context={})

        source_types = [s.source_type for s in draft.sections]
        assert source_types == [
            "REQUIREMENT", "EVIDENCE", "DATASET",
            "ANALYSIS", "EXECUTION", "SUMMARY",
        ]

    def test_objective_from_requirement_payload(self):
        """实验目的优先取 payload.objective。"""
        provider = LocalRuleOutlineProvider()
        draft = provider.generate(context={
            "requirements": {
                "plan_id": "plan_001",
                "payload": {"objective": "分析胃病数据分布"},
            },
        })

        sec1 = draft.sections[0]
        assert sec1.title == "实验目的"
        assert "分析胃病数据分布" in sec1.content
        assert sec1.source_ids == ["plan_001"]

    def test_objective_falls_back_to_description(self):
        """payload.objective 缺失时回退到 description。"""
        provider = LocalRuleOutlineProvider()
        draft = provider.generate(context={
            "requirements": {
                "plan_id": "plan_002",
                "payload": {"description": "通过描述补充目的"},
            },
        })

        assert "通过描述补充目的" in draft.sections[0].content

    def test_objective_falls_back_to_source_text(self):
        """payload 完全缺失时回退到 source_text。"""
        provider = LocalRuleOutlineProvider()
        draft = provider.generate(context={
            "requirements": {
                "plan_id": "plan_003",
                "source_text": "原始任务单文本",
            },
        })

        assert "原始任务单文本" in draft.sections[0].content

    def test_evidence_cards_aggregated(self):
        """证据卡片聚合为列表项，id 写入 source_ids。"""
        provider = LocalRuleOutlineProvider()
        draft = provider.generate(context={
            "evidence_cards": [
                {"id": "card_001", "claim": "胃病发病率上升"},
                {"id": "card_002", "summary": "地区差异显著"},
                {"id": "card_003"},  # 无 claim 和 summary，跳过
            ],
        })

        sec2 = draft.sections[1]
        assert sec2.title == "实验背景"
        assert "胃病发病率上升" in sec2.content
        assert "地区差异显著" in sec2.content
        assert sec2.source_ids == ["card_001", "card_002"]

    def test_evidence_empty_returns_placeholder(self):
        """无证据卡片时返回占位文本。"""
        provider = LocalRuleOutlineProvider()
        draft = provider.generate(context={"evidence_cards": []})

        assert "暂无已确认证据" in draft.sections[1].content

    def test_dataset_profile_fields(self):
        """数据集字段概览渲染为字段列表，ftype 正确显示。"""
        provider = LocalRuleOutlineProvider()
        draft = provider.generate(context={
            "dataset": {
                "version_id": "ver_001",
                "row_count": 100,
                "column_count": 3,
                "profile": {
                    "fields": [
                        {"name": "age", "type": "int64", "sample": "45"},
                        {"name": "gender", "type": "object", "sample": "男"},
                    ],
                },
            },
        })

        sec3 = draft.sections[2]
        assert sec3.title == "数据描述"
        assert "100 行 × 3 列" in sec3.content
        assert "age" in sec3.content
        assert "int64" in sec3.content  # ftype 而非内置 type
        assert "gender" in sec3.content
        assert sec3.source_ids == ["ver_001"]

    def test_analysis_plan_rendered(self):
        """分析方案的 cleaning/analysis/chart 三部分渲染。"""
        provider = LocalRuleOutlineProvider()
        draft = provider.generate(context={
            "analysis_plan": {
                "plan_id": "plan_a",
                "cleaning_plan": [{"description": "去除缺失值"}],
                "analysis_plan": [{"description": "描述性统计"}],
                "chart_plan": [{"description": "柱状图"}],
            },
        })

        sec4 = draft.sections[3]
        assert sec4.title == "分析方案"
        assert "去除缺失值" in sec4.content
        assert "描述性统计" in sec4.content
        assert "柱状图" in sec4.content
        assert sec4.source_ids == ["plan_a"]

    def test_execution_runs_with_artifacts(self):
        """执行结果含 stdout 和产物列表，run_id 写入 source_ids。"""
        provider = LocalRuleOutlineProvider()
        draft = provider.generate(context={
            "executions": [
                {
                    "run_id": "run_001",
                    "stdout": "执行输出结果",
                    "artifacts": [
                        {"name": "chart.png"},
                        {"name": "result.csv"},
                    ],
                },
            ],
        })

        sec5 = draft.sections[4]
        assert sec5.title == "实验结果"
        assert "执行输出结果" in sec5.content
        assert "chart.png" in sec5.content
        assert "result.csv" in sec5.content
        assert sec5.source_ids == ["run_001"]

    def test_execution_empty_returns_placeholder(self):
        """无执行结果时返回占位。"""
        provider = LocalRuleOutlineProvider()
        draft = provider.generate(context={"executions": []})

        assert "暂无成功执行结果" in draft.sections[4].content

    def test_summary_section_content(self):
        """结论与讨论基于执行结果和图表方案生成。"""
        provider = LocalRuleOutlineProvider()
        draft = provider.generate(context={
            "executions": [{"run_id": "r1", "stdout": "ok"}],
            "analysis_plan": {
                "chart_plan": [{"description": "图1"}, {"description": "图2"}],
            },
        })

        sec6 = draft.sections[5]
        assert sec6.title == "结论与讨论"
        assert "完成" in sec6.content
        assert "2 个图表方案" in sec6.content


class TestTruncate:
    """_truncate 截断函数测试。"""

    def test_short_text_unchanged(self):
        """短于上限的文本原样返回。"""
        assert _truncate("短文本") == "短文本"

    def test_empty_text_returns_empty(self):
        """空文本返回空字符串。"""
        assert _truncate("") == ""
        assert _truncate(None) == ""

    def test_long_text_truncated_with_marker(self):
        """超长文本截断并附加标记。"""
        long_text = "x" * 2000
        result = _truncate(long_text, max_chars=100)
        assert len(result) == len("x" * 100) + len("…（已截断）")
        assert result.endswith("…（已截断）")

    def test_exact_boundary_not_truncated(self):
        """恰好等于上限不截断。"""
        text = "y" * 100
        assert _truncate(text, max_chars=100) == text


class TestFakeOutlineProvider:
    """确定性测试用提供者测试。"""

    def test_source_label(self):
        assert FakeOutlineProvider().source_label() == "fake"

    def test_generates_six_sections(self):
        """始终返回 6 个带（Fake）前缀的章节。"""
        draft = FakeOutlineProvider().generate(context={})

        assert len(draft.sections) == 6
        for s in draft.sections:
            assert "（Fake）" in s.content

    def test_is_deterministic(self):
        """相同调用产生相同结果。"""
        p = FakeOutlineProvider()
        d1 = p.generate(context={})
        d2 = p.generate(context={"any": "thing"})
        assert [s.content for s in d1.sections] == [s.content for s in d2.sections]
