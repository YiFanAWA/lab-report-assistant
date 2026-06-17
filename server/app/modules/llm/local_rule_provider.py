"""本地规则驱动的任务单草案提供者。

不依赖任何外部模型、不调用 DeepSeek。
基于对实验要求的简单规则匹配，生成结构化候选任务单。
"""

from app.modules.requirements.contracts import (
    RequirementPlanPayload,
    RequirementTask,
    ReplicationLevel,
)


def _make_task(title: str, description: str, task_type: str, reason: str,
               source_quote: str | None = None) -> RequirementTask:
    return RequirementTask(
        title=title,
        description=description,
        task_type=task_type,
        reason=reason,
        source_quote=source_quote,
    )


def _keyword_match(text: str) -> dict:
    """从实验要求文本中提取关键词。"""
    lowered = text.lower()
    has_replication = any(w in lowered for w in ["复现", "复刻", "论文", "文献"])
    return {
        "数据分析": any(w in lowered for w in ["数据", "分析", "统计", "可视化", "图表"]),
        "清洗": any(w in lowered for w in ["清洗", "预处理", "缺失", "异常"]),
        "报告": any(w in lowered for w in ["报告", "word", "文档"]),
        "PPT": any(w in lowered for w in ["ppt", "演示", "汇报", "幻灯片"]),
        "复现": has_replication,
        "完整复现": has_replication and any(w in lowered for w in ["完整", "全部", "全量", "完全", "所有"]),
        "机器学习": any(w in lowered for w in ["机器学习", "预测", "分类", "回归", "聚类"]),
    }


class LocalRuleRequirementDraftProvider:
    """基于关键词匹配生成任务单候选。"""

    def source_label(self) -> str:
        return "LOCAL_RULE"

    def draft(self, requirement_text: str) -> RequirementPlanPayload:
        kw = _keyword_match(requirement_text)

        topic = "数据分析实验"
        experiment_type = "数据分析与可视化"

        # --- 必须任务 ---
        required = [
            _make_task(
                "数据加载与理解",
                "加载原始数据，理解每个字段的含义和数据类型。",
                "REQUIRED",
                "所有数据分析实验的必要起点",
            ),
            _make_task(
                "数据预处理",
                "检查并处理缺失值、重复值和异常值。",
                "REQUIRED",
                "数据质量直接影响分析结论",
            ),
        ]
        if kw["清洗"]:
            required.append(_make_task(
                "数据清洗方案记录",
                "用表格记录每条清洗操作的原因、方法和影响行数。",
                "REQUIRED",
                "原始要求提到了数据清洗",
            ))

        if kw["数据分析"]:
            required.append(_make_task(
                "描述性统计",
                "计算各字段的均值、中位数、标准差、最小/最大值等基础统计量。",
                "REQUIRED",
                "原始要求包含数据分析",
            ))
            required.append(_make_task(
                "数据可视化",
                "生成关键字段的直方图、箱线图、相关性热力图等。",
                "REQUIRED",
                "原始要求包含可视化或图表",
            ))

        if kw["机器学习"]:
            required.append(_make_task(
                "构建预测或分类模型",
                "根据数据特点选择合适的模型进行训练和评估。",
                "REQUIRED",
                "原始要求包含机器学习或预测任务",
            ))

        if kw["报告"]:
            required.append(_make_task(
                "撰写实验报告",
                "按照实验要求的结构完成 Word 实验报告。",
                "REQUIRED",
                "原始要求包含报告或文档交付",
            ))

        if kw["PPT"]:
            required.append(_make_task(
                "制作汇报 PPT",
                "从实验报告中提炼关键发现制作演示文稿。",
                "REQUIRED",
                "原始要求包含 PPT 或汇报",
            ))

        # --- 推荐任务 ---
        recommended = [
            _make_task(
                "字段相关性分析",
                "分析关键字段之间的 Pearson 或 Spearman 相关系数。",
                "RECOMMENDED",
                "有助于理解数据内在结构",
            ),
            _make_task(
                "分组对比分析",
                "按关键分组变量（如性别、年龄组）进行分组统计检验。",
                "RECOMMENDED",
                "能发现群体间差异",
            ),
        ]

        # --- 可选任务 ---
        optional = [
            _make_task(
                "高级可视化",
                "使用 Seaborn 或 Plotly 创建交互式或更美观的图表。",
                "OPTIONAL",
                "提升报告视觉效果",
            ),
        ]

        # --- 超范围任务 ---
        out_of_scope: list[RequirementTask] = []
        if kw["完整复现"]:
            out_of_scope.append(_make_task(
                "完整论文复现",
                "完整复现参考文献中论文的全部实验步骤和结果。",
                "OUT_OF_SCOPE",
                "第一版不支持 L3 完整复现",
            ))

        # --- 未知项 ---
        unknown = [
            _make_task(
                "明确数据来源和版本",
                "请确认数据的具体来源、采集时间和版本信息。",
                "UNKNOWN",
                "需要用户补充",
            ),
        ]

        # --- L0-L3 判断 ---
        if kw["完整复现"]:
            replication = ReplicationLevel(
                level="L3",
                label="完整复现",
                supported_in_v1=False,
                reason="原始要求包含完整、全部等完整复现信号，第一版不支持 L3 完整复现",
                suggested_scope="降级为 L2 局部复现：仅参考论文方法，用当前数据完成可追溯的数据分析",
            )
        elif kw["复现"]:
            replication = ReplicationLevel(
                level="L2",
                label="局部复现",
                supported_in_v1=True,
                reason="原始要求包含复刻或论文相关要求，第一版支持局部复现（L2）",
                suggested_scope="仅参考论文的数据处理方法和分析思路，使用自己的数据重新完成分析",
            )
        else:
            replication = ReplicationLevel(
                level="L0",
                label="不复刻",
                supported_in_v1=True,
                reason="原始要求未明确要求复刻论文，作为独立数据分析实验处理",
                suggested_scope="仅使用公开数据和用户数据完成独立分析",
            )

        return RequirementPlanPayload(
            topic=topic,
            experiment_type=experiment_type,
            research_subject=requirement_text[:100].strip() or "待确认",
            required_tasks=required,
            recommended_tasks=recommended,
            optional_tasks=optional,
            out_of_scope_tasks=out_of_scope,
            unknown_items=unknown,
            data_requirements=["CSV 或 Excel 格式的结构化数据集"],
            method_requirements=["描述性统计", "数据可视化"] + (
                ["机器学习模型训练与评估"] if kw["机器学习"] else []
            ),
            chart_requirements=["直方图", "箱线图", "相关性热力图"] if kw["数据分析"] else [],
            report_requirements=["包含方法、结果、讨论和结论的标准实验报告"] if kw["报告"] else [],
            presentation_requirements=["10-15 页 PPT，突出问题和主要发现"] if kw["PPT"] else [],
            acceptance_criteria=["所有分析步骤有可追溯的代码和执行记录",
                               "图表来源于真实数据而非大模型生成"],
            replication_level=replication,
        )


class FakeRequirementDraftProvider(LocalRuleRequirementDraftProvider):
    """测试替身 —— 行为与 LocalRule 相同，但返回固定标签。"""

    def source_label(self) -> str:
        return "MANUAL"
