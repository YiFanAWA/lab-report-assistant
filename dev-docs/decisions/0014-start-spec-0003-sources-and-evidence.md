# 决策 0014：启动 SPEC 0003 公开资料与证据工作流切片

## 状态

已接受。

## 日期

2026-07-06

## 决策人

项目负责人。

## 背景

SPEC 0002"实验要求输入与结构化任务单"已由项目负责人确认收口，本项目必须按根目录 `AGENTS.md` 的阶段闸推进：在下一切片 SPEC 编写并确认前，不得进入下一切片实现。

依据 `dev-docs/implementation-plan.md` 任务 5"来源与证据工作流"和 `dev-docs/architecture.md` 中预留的 owner 边界（来源与证据核心、后台任务核心），下一切片应解决：让用户为已确认要求的实验项目登记公开 URL 和 PDF 辅助文件，通过独立 Worker 异步完成采集与解析，生成可审阅、可确认的证据卡片，并保存完整的来源位置和采集状态，建立"资料事实有来源"的核心追踪链入口。

本切片是 V0.2 里程碑，是后续数据分析和交付物可追溯性的前提。

## 范围边界

本切片引入：

- 来源登记：公开 URL（HTML 页面或 PDF 直链）和本地 PDF 文件上传。
- 后台任务：最小 `background_jobs` 表和独立 Worker 进程，承担 URL 采集、文档解析和证据卡片生成。
- 来源采集：Worker 通过 HTTP 下载公开 URL 内容，保存原始文件到项目受控工作区。
- 文档解析：HTML（beautifulsoup4 + lxml）和 PDF（pypdf）解析，提取正文和基础元数据。
- 证据卡片候选：通过 LLM Gateway 本地规则提供者从已解析文档生成结构化候选。
- 证据卡片确认：用户可确认、编辑或拒绝候选。
- 状态推进：`REQUIREMENT_CONFIRMED` → `SOURCES_COLLECTED` → `EVIDENCE_CONFIRMED`。
- STALE 传播：来源重新采集或删除时关联证据卡片变为 `STALE`。
- 结构化拒绝：非公开 URL、受限资源、动态网页和不支持格式返回结构化错误。

本切片明确不做：

- 不绕过登录、验证码、付费墙或访问控制。
- 不自动登录知网等受限平台。
- 不使用 Playwright 渲染动态网页（推迟到后续切片）。
- 不接入真实 DeepSeek API（继续使用本地规则提供者）。
- 不支持 Word、TXT、CSV、Excel 文件上传（仅 PDF）。
- 不上传或解析样例数据集、不生成数据清洗或分析方案、不执行 Python 代码、不生成 Word/PPT。
- 不做 OCR 或扫描件解析。
- 不做 L3 完整论文复现，不把 L1/L2 方法参考包装为完整复现。
- 不提供医疗诊断或治疗建议。

## 关键技术决策

1. **Worker**：引入最小 Worker 进程，使用数据库任务表 + 轮询方式领取任务，不引入 Celery/RQ/Redis 等额外组件。
2. **LLM**：继续使用本地规则提供者（`LocalRuleEvidenceCardProvider` + `FakeEvidenceCardProvider`），通过 LLM Gateway 工厂方法接入；真实 DeepSeek 接入推迟到后续切片。
3. **文件格式**：仅支持 PDF 文件上传和 PDF/HTML URL 采集，不支持 Word/TXT/CSV/Excel（推迟到数据集工作流切片）。
4. **Playwright**：不引入。动态网页检测后返回 `SOURCE_UNSUPPORTED_DYNAMIC`，建议用户手动上传 PDF。

## 依赖影响

本切片实际安装以下运行时依赖：

- `httpx` `0.28.1`（已在 dependency-review.md 复核，本切片首次实际安装）
- `pypdf` `6.14.2`
- `beautifulsoup4` `4.15.0`
- `lxml` `6.1.1`（SPEC 0002 已作为 `python-docx` 传递依赖安装，本切片作为 beautifulsoup4 解析器显式使用）

`playwright` 不在本切片安装。

## 验收证据

完成本切片后必须满足：

- `server/.venv/Scripts/python.exe -m pytest` 全部通过（原 26 + 新增测试）。
- `server/.venv/Scripts/python.exe -m alembic upgrade head` 迁移到 `0003` 成功。
- `apps/web` 下 `npm.cmd run lint` 和 `npm.cmd run build` 通过。
- 端到端主链路：创建项目 → 保存要求 → 生成任务单 → 确认任务单 → 登记 URL → Worker 采集 → 解析 → 生成证据卡片 → 确认卡片 → 推进状态。
- 非公开 URL 返回 `SOURCE_URL_NOT_PUBLIC`。
- 受限 URL 返回 `SOURCE_ACCESS_RESTRICTED`。
- 来源删除后证据卡片变为 `STALE`。

## 决策

启动 SPEC 0003"公开资料与证据工作流"切片。本切片实现完成后必须暂停，由项目负责人确认验收前不进入下一切片。

## 约束

- 不把本切片的启动误解为 V1 完成。
- 不在未经确认的情况下扩展到 Word/TXT/CSV/Excel、Playwright 或真实 DeepSeek 调用。
- 不绕过阶段闸：进入下一切片前必须先编写并确认 SPEC 0004。
- Worker 只调用核心服务（sources/evidence）的方法并写回状态，不拥有业务语义。
- LLM Gateway 继续作为唯一接入点，业务模块不得直接调用 DeepSeek SDK 或写死模型名。
- 外部 skill 仓库仍作为本地辅助资料保留在 `skills/` 下，不纳入主仓提交。
