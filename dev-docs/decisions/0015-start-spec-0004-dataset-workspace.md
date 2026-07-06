# 决策 0015：启动 SPEC 0004 数据集工作区切片

## 状态

已接受。

## 日期

2026-07-06

## 决策人

项目负责人。

## 背景

SPEC 0003"公开资料与证据工作流"已完成实现、端到端验收并由项目负责人确认收口（commit `ba683db`），本项目必须按根目录 `AGENTS.md` 的阶段闸推进：在下一切片 SPEC 编写并确认前，不得进入下一切片实现。

依据 `dev-docs/implementation-plan.md` 任务 6"数据集工作区"和 `dev-docs/architecture.md` §4 数据集与分析核心 owner 边界，下一切片应解决：让用户为已确认证据的实验项目上传 CSV/Excel 数据集，由 Worker 异步解析生成字段概览与质量评分，通过 LLM Gateway 本地规则提供者生成清洗和分析方案候选，用户确认方案后建立"数据 → 方案 → 执行 → 结果"的追踪链入口。

本切片是 V0.3 里程碑第一部分，是后续 Python 执行（SPEC 0005）的前提。

## 范围边界

本切片引入：

- 数据集登记：CSV/Excel 文件上传和公开 URL 登记（仅 CSV/Excel 直链）。
- 数据集版本：每次重新上传创建新版本，旧版本 `SUPERSEDED`，关联 `AnalysisPlan` 变 `STALE`。
- 字段概览：通过 pandas 解析推断字段类型（string/float/int/datetime/bool），统计缺失值、唯一值、重复行、top_values，计算 `quality_score`。
- 分析方案候选：通过 LLM Gateway 本地规则提供者（`LocalRuleAnalysisPlanProvider`）生成清洗、分析、可视化三类方案候选。
- 用户确认：用户可确认、编辑（CONFIRMED 回到 CANDIDATE）、拒绝方案。
- 状态推进：`EVIDENCE_CONFIRMED` → `DATASET_READY` → `ANALYSIS_PLANNED` → `ANALYSIS_CONFIRMED`。
- STALE 传播：数据集重新上传时关联 `AnalysisPlan` 变 `STALE`；同版本重新生成方案时旧 `CANDIDATE` 变 `STALE`。
- 结构化拒绝：文件过大、类型不支持、URL 非公开、状态不允许等返回结构化错误。

本切片明确不做：

- 不引入 `scipy`、`scikit-learn`、`matplotlib`（推迟到 SPEC 0005 Python 执行切片）。
- 不接入真实 DeepSeek API（继续使用本地规则提供者）。
- 不执行 Python 代码（只生成方案候选，不产生执行结果）。
- 不生成图表（只生成图表方案描述）。
- 不支持工作表选择（默认解析第一个工作表）。
- 不做数据预览或行级编辑（推迟到后续切片）。
- 不做 L3 完整论文复现。
- 不提供医疗诊断或治疗建议。

## 关键技术决策

1. **数据集 URL 同步下载**：`create_url_dataset` 在 API 层同步下载文件（复用 SPEC 0003 `fetch_url`），保存到受控工作区后再创建 `PARSE_DATASET` 任务。URL 错误（不公开、需登录、过大）直接以 400/403/413 返回，与 sources 模块 PDF 上传模式一致。
2. **Worker 解析与方案生成分离**：`PARSE_DATASET` handler 解析成功后自动触发 `GENERATE_ANALYSIS_PLAN` 任务，但 `advance_project_to_planned` 只在 `DATASET_READY` 状态推进，避免在 `EVIDENCE_CONFIRMED` 状态下错误推进。用户调用 `/datasets/complete` 后再调用 `/analysis/generate` 显式触发，旧 CANDIDATE 变 STALE。
3. **LLM Provider**：`LocalRuleAnalysisPlanProvider` 按字段类型生成方案候选；字段数 > 50 时截断到前 20 字段。`FakeAnalysisPlanProvider` 用于测试。
4. **STALE 传播**：reupload 创建新版本时，旧版本关联的 `AnalysisPlan`（任意状态）变 `STALE`；同版本重新 `generate` 时，旧 `CANDIDATE` 变 `STALE`。
5. **不引入新执行依赖**：本切片只安装 `pandas`、`numpy`、`openpyxl`，不安装 `scipy`/`scikit-learn`/`matplotlib`。

## 依赖影响

本切片实际安装以下运行时依赖：

- `pandas` `3.0.3`（dependency-review.md §6 复核版本，实际安装版本一致）
- `numpy` `2.5.1`（复核版本 `2.4.6`，实际安装版本 `2.5.1`，pandas 3.0.3 依赖升级，无破坏性变更）
- `openpyxl` `3.1.5`（复核版本一致）

`scipy`、`scikit-learn`、`matplotlib`、`playwright` 不在本切片安装。

## 验收证据

完成本切片后必须满足：

- `server/.venv/Scripts/python.exe -m pytest` 全部通过（原 153 + 新增 222 = 375 测试）。
- `server/.venv/Scripts/python.exe -m alembic upgrade head` 迁移到 `0004` 成功。
- `apps/web` 下 `npm.cmd run lint` 和 `npm.cmd run build` 通过。
- 端到端主链路：创建项目 → 确认证据 → 上传 xlsx → Worker 解析 → 完成数据集收集 → 触发生成方案 → Worker 生成 → 确认方案 → 推进到 `ANALYSIS_CONFIRMED`。
- 错误分支：状态不允许、文件过大、类型不支持、方案不存在、状态不可确认等返回结构化错误。
- STALE 传播：reupload 后旧方案变 STALE。

## 决策

启动 SPEC 0004"数据集工作区"切片。本切片实现完成后必须暂停，由项目负责人确认验收前不进入下一切片。

## 约束

- 不把本切片的启动误解为 V1 完成。
- 不在未经确认的情况下扩展到 Python 执行、scipy/scikit-learn/matplotlib 或真实 DeepSeek 调用。
- 不绕过阶段闸：进入下一切片前必须先编写并确认 SPEC 0005。
- Worker 只调用核心服务（datasets/analysis）的方法并写回状态，不拥有业务语义。
- LLM Gateway 继续作为唯一接入点，业务模块不得直接调用 DeepSeek SDK 或写死模型名。
- 外部 skill 仓库仍作为本地辅助资料保留在 `skills/` 下，不纳入主仓提交。
