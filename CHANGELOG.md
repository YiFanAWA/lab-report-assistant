# 变更日志（CHANGELOG）

本项目所有显著变更均记录在此文件中。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 修复

- **代码任务执行 prompt 换行双重转义**（commit `93f1f13`，P0 阻断）：`deepseek_code_task_provider` 的 `_SYSTEM_PROMPT` 中"换行使用 `\n` 转义"指令导致 DeepSeek 返回的代码换行被双重转义为字面量 `\\n`，AST 解析时被当作行延续符引发 `unexpected character after line continuation character` 语法错误。修复为"代码必须是合法 JSON（换行符由 JSON 标准自动转义，无需手动处理）"。
- **代码任务 import 白名单缺失**（commit `93f1f13`，P0 阻断）：`_SYSTEM_PROMPT` 未明确允许的 import 模块范围，DeepSeek 生成 `import os` 被 `python_executor` 的 AST 黑名单校验拒绝。新增白名单（pandas/numpy/matplotlib/scipy/sklearn/openpyxl）和禁止模块列表，并告知 LLM 路径变量已由执行环境注入（`DATA_PATH`、`OUTPUT_DIR`），无需 `import os`。
- **Python 执行器路径解析**（commit `93f1f13`，P0 阻断）：`python_executor.execute_code_safe` 中 `work_path` 和 `data_path` 未 resolve 为绝对路径，当 `settings.project_data_root` 为相对路径时，subprocess `cwd` + 相对 `script_path` 导致路径重复拼接，引发 `FileNotFoundError`。修复为入口处 `Path(work_dir).resolve()` + `data_path` resolve。

### 新增

- **Worker 执行与文档生成模块单元测试补全**：新增 44 个单元测试（`test_execution_worker_handlers.py` 22 个 + `test_outline_worker_handlers.py` 新增 9 个），覆盖 Worker handler 的成功路径、脚本错误、沙箱限制（import 禁止/内存超限）、前置校验、资源不存在（plan/code_task/version/outline/deliverable）、产物收集、版本管理（失败生成不覆盖成功版本）、降级链（Word 模板降级 + PPT 配置降级）等场景。详见 [决策 0031](dev-docs/decisions/0031-code-task-execution-link-fixes.md)。

### 文档

- 新增决策记录 [决策 0031](dev-docs/decisions/0031-code-task-execution-link-fixes.md)：SPEC 0022 代码任务执行链路关键修复，详细记录三项代码层修复（prompt 换行转义、import 白名单、路径解析）的根因/方案/代码变更，以及三项链路验证环境注意事项（httpx 代理、CSV 列匹配、Worker 进程独立启动）。

### 链路验证环境注意事项

> 以下三项不属代码修复，但属端到端链路验证必须遵守的环境配置：

1. **httpx 客户端需禁用系统代理**：Windows 系统配置了 HTTP 代理时，`httpx` 默认读取 `HTTP_PROXY`/`HTTPS_PROXY` 环境变量导致本地请求 502。验证脚本应使用 `httpx.Client(trust_env=False)`。
2. **AnalysisPlan 字段名必须与 CSV 列名匹配**：AnalysisPlan 的 `analysis_plan[].target_fields` 是数据集字段引用，必须与 CSV 实际列名严格匹配，否则执行时抛 `KeyError`。
3. **Worker 进程需单独启动**：Worker 是独立进程（`python -m worker.main`），不随 uvicorn 自动启动。链路验证时需单独启动 Worker 进程领取后台任务。

## [v2.4.0] - 2026-07-30

- SPEC 0022 代码任务生成流式化（SSE 端点绕过 Worker，Provider 输入为 AnalysisPlan，复用 SPEC 0018/0019/0020/0021 流式架构，新增并发保护与服务端取消）。详见 [决策 0028](dev-docs/decisions/0028-start-spec-0022-code-task-streaming.md) 与 [决策 0030](dev-docs/decisions/0030-confirm-spec-0022-acceptance.md)。

## [v2.3.0] - 2026-07-29

- SPEC 0021 分析方案生成流式化。详见 [决策 0027](dev-docs/decisions/0027-start-spec-0021-analysis-plan-streaming.md)。

## [v2.2.0] - 2026-07-28

- SPEC 0020 证据卡片生成流式化。详见 [决策 0026](dev-docs/decisions/0026-start-spec-0020-evidence-streaming.md)。

## [v2.1.0] - 2026-07-27

- SPEC 0019 大纲生成流式化。详见 [决策 0025](dev-docs/decisions/0025-start-spec-0019-outline-streaming.md)。

## [v2.0.0] - 2026-07-26

- SPEC 0018 流式 LLM 输出（任务单生成 SSE 流式化）。详见 [决策 0024](dev-docs/decisions/0024-start-spec-0018-streaming-llm-output.md)。

## [v1.4.0] - 2026-07-25

- SPEC 0017 单用户前端实时编辑反馈。详见 [决策 0023](dev-docs/decisions/0023-start-spec-0017-frontend-realtime-edit-feedback.md)。

## [v1.3.0] - 2026-07-24

- SPEC 0016 技术债务清理（TD-004/005/006/008）。详见 [决策 0022](dev-docs/decisions/0022-start-spec-0016-tech-debt-cleanup.md)。

## [v1.2.0] - 2026-07-23

- SPEC 0013 Docker 化部署、SPEC 0014 LLM 调用缓存、SPEC 0015 GitHub Actions CI 流水线。详见 [决策 0020](dev-docs/decisions/0020-start-spec-0014-llm-cache.md) 与 [决策 0021](dev-docs/decisions/0021-start-spec-0015-github-actions-ci.md)。

## [v1.1.0] - 2026-07-22

- SPEC 0007 真实 DeepSeek LLM 接入、SPEC 0009 前端测试覆盖补全、SPEC 0010 Word 模板支持、SPEC 0011 PPT 配置选项、SPEC 0012 数据保留周期配置。详见 [决策 0019](dev-docs/decisions/0019-deepseek-llm-integration.md)。

## [v1.0.0] - 2026-07-22

- 首个完整闭环版本：从创建项目到 Word/PPT 下载完整跑通。SPEC 0001-0006 全部完成。端到端验收报告见 [e2e-acceptance-report-v1.0.md](dev-docs/e2e-acceptance-report-v1.0.md)。
