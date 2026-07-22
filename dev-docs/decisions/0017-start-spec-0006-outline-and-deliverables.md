# 决策 0017：启动 SPEC 0006 大纲与交付物切片

## 状态

已接受。

## 日期

2026-07-07

## 决策人

项目负责人。

## 背景

SPEC 0005"受控 Python 执行"已完成实现、端到端验收并由项目负责人确认收口（commit `f30d500`，26 文件，+4172 行，已推送到远程），本项目必须按根目录 `AGENTS.md` 的阶段闸推进：在下一切片 SPEC 编写并确认前，不得进入下一切片实现。

依据 `dev-docs/implementation-plan.md` 任务 8"大纲核心"和任务 9"Word 与 PPT 交付物"，以及 `dev-docs/architecture.md` §6 大纲与交付物核心 owner 边界，下一切片应解决：为已完成执行的项目生成统一实验大纲，用户确认后从同一份大纲分别生成 Word 实验报告和 PPT 汇报文件，建立"要求 → 证据 → 数据 → 执行 → 大纲 → 交付物"的完整追踪链，最终推进项目状态到 `COMPLETED`。

本切片是 V0.4 里程碑（大纲与交付物），也是 V1.0 完整闭环验收前的最后一个功能切片。完成后，项目将具备从创建项目到 Word/PPT 下载的完整闭环能力。

## 范围边界

本切片引入：

- 后端 owner 模块 `server/app/modules/outlines/`：Outline、Deliverable、DeliverableVersion 核心归属。
- 基础设施适配器 `server/app/infrastructure/renderers/word_renderer.py` 和 `ppt_renderer.py`：Word/PPT 渲染器。
- LLM 提供者 `server/app/modules/llm/outline_provider.py`：基于已确认内容生成大纲候选。
- Alembic 迁移 `0006_create_outline_and_deliverable_tables.py`：3 张表（outlines、deliverables、deliverable_versions）+ 5 个索引。
- 12 个 API 端点（大纲 7 个 + 交付物 4 个 + 完成 1 个）。
- 3 个 Worker handler：`GENERATE_OUTLINE`、`GENERATE_WORD`、`GENERATE_PPT`。
- 前端大纲工作区和交付物工作区。
- 项目状态推进：`RESULT_CONFIRMED → OUTLINE_CONFIRMED → GENERATING → COMPLETED`。
- STALE 传播：ExecutionRun 重新执行 → Outline STALE；Outline 编辑 → Deliverable STALE；Outline 重新确认 → 旧 Deliverable STALE。
- 安装新运行时依赖：`python-docx 1.2.0`、`python-pptx 1.0.2`（计划版本，实际以验收时为准）。

本切片明确不做：

- 不接入真实 DeepSeek API（继续使用本地规则提供者 `LocalRuleOutlineProvider`）。
- 不做 Word 模板完全兼容（V1 只支持默认模板或简单模板）。
- 不做 PPT 动画和复杂排版。
- 不做交付物内容自动润色。
- 不做交付物版本对比工具。
- 不做论文投稿级排版。
- 不做在线多用户协作。
- 不让 Word 和 PPT 各自从模型临时上下文生成。
- 不在未确认大纲的情况下生成 Word 或 PPT。
- 不提供医疗诊断或治疗建议。
- 不把医学教学数据分析结论包装为临床结论。

## 关键技术决策

1. **统一大纲作为唯一中间锚点**。Word 和 PPT 必须从同一份已确认大纲生成，禁止各自从模型临时上下文生成。大纲包含 6 个章节（目的、背景、数据、方案、结果、结论），每章节标记来源类型和关联 ID，确保追踪链不断裂。

2. **大纲章节来源标记**。每个章节标记 `source_type`（REQUIREMENT/EVIDENCE/DATASET/ANALYSIS/EXECUTION/SUMMARY）和 `source_ids`（对应实体 ID 列表），实现资料性结论追溯到来源、实验性结论追溯到执行记录的追踪链。

3. **Word 渲染：python-docx 模板驱动**。使用 `python-docx` 库生成 `.docx` 文件，从大纲章节渲染 Word 段落，嵌入执行产物中的表格（CSV）和图表（PNG）。不引入外部模板引擎，用 python-docx 原生 API 构建。

4. **PPT 渲染：python-pptx 母版驱动**。使用 `python-pptx` 库生成 `.pptx` 文件，从同一份大纲提炼关键内容（5-8 页），引用执行产物中的 PNG 图表。PPT 不包含全部细节，只包含问题、方法、关键图表、主要发现和总结。

5. **交付物版本管理**。每次生成创建新 `DeliverableVersion`，旧版本保留不删除。生成失败不覆盖已有成功版本。用户可重新生成任意类型的交付物。

6. **状态机推进**：生成大纲候选时保持 `RESULT_CONFIRMED`；确认大纲时推进到 `OUTLINE_CONFIRMED`；触发 Word/PPT 生成时推进到 `GENERATING`；用户主动确认完成且至少一个 Word 和一个 PPT 版本成功时推进到 `COMPLETED`。

7. **STALE 传播链**：ExecutionRun 重新执行 → 关联 Outline 变 STALE；Outline 编辑 → 关联 Deliverable 变 STALE；Outline 重新确认 → 旧 Deliverable 变 STALE。STALE 传播幂等，不重复标记。

8. **项目级不新增 DELIVERABLE_FAILED 状态**。Word 和 PPT 独立生成，一个失败不影响另一个。单个 `DeliverableVersion.status=FAILED` 已足够记录失败，用户可重新触发该类型生成。项目状态保持 `GENERATING`，在用户主动确认完成后推进到 `COMPLETED`。

9. **字段截断唯一截断点**。AnalysisPlan 阶段为字段截断唯一截断点，Outline 生成时直接透传已截断字段内容，提供者不做二次截断。与 SPEC 0005 CodeTask 保持一致。

## 依赖影响

本切片计划安装以下运行时依赖（计划版本，实际安装版本以 SPEC 0006 验收时记录为准）：

- `python-docx` `1.2.0`（dependency-review.md §6 复核版本）
- `python-pptx` `1.0.2`（复核版本）

真实 DeepSeek 调用继续推迟到后续切片。

## 验收证据要求

完成本切片后必须满足：

- `server/.venv/Scripts/python.exe -m pytest` 全部通过（原 456 + 新增测试）。
- `server/.venv/Scripts/python.exe -m alembic upgrade head` 迁移到 `0006` 成功。
- `apps/web` 下 `npm.cmd run lint` 和 `npm.cmd run build` 通过。
- 端到端主链路：SPEC 0005 完成状态 → 生成大纲 → 编辑确认 → 生成 Word → 生成 PPT → 下载 → `COMPLETED`。
- 错误分支：项目状态不足、大纲未确认、大纲不可编辑、交付物不可生成、无成功交付物等返回结构化错误。
- STALE 传播：ExecutionRun 重新执行时 Outline 变 STALE；Outline 编辑后 Deliverable 变 STALE。
- Word 和 PPT 来自同一份已确认大纲。
- Word 包含表格和图表产物。
- PPT 包含关键图表产物。
- 旧版本保留不删除。
- 生成失败不覆盖已有成功版本。
- 无真实 DeepSeek API Key 时本地验收通过。

## 决策

启动 SPEC 0006"大纲与交付物"切片。本切片实现完成后必须暂停，由项目负责人确认验收前不进入下一切片。

## 约束

- 不把本切片的启动误解为 V1 完成。
- 不绕过阶段闸：进入下一切片前必须先编写并确认 SPEC 0007（如需要）。
- 不在未经确认的情况下扩展到真实 DeepSeek 调用、Word 模板完全兼容、PPT 动画、交付物自动润色或版本对比工具。
- Worker 只调用核心服务（outlines）的方法并写回状态，不拥有业务语义。
- LLM Gateway 继续作为唯一接入点，业务模块不得直接调用 DeepSeek SDK 或写死模型名。
- Word 和 PPT 必须从同一份已确认大纲生成，禁止各自从模型临时上下文生成。
- 失败状态必须如实保存，不得为通过验收而覆盖为成功。
- 交付物文件路径必须校验不越界，防止路径穿越攻击。
- 外部 skill 仓库仍作为本地辅助资料保留在 `skills/` 下，不纳入主仓提交。
