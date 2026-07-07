# 决策 0016：启动 SPEC 0005 受控 Python 执行切片

## 状态

已接受。

## 日期

2026-07-06

## 决策人

项目负责人。

## 背景

SPEC 0004"数据集工作区"已完成实现、端到端验收并由项目负责人确认收口（commit `fba27b5`，47 文件，+11467/-18，已推送到远程），本项目必须按根目录 `AGENTS.md` 的阶段闸推进：在下一切片 SPEC 编写并确认前，不得进入下一切片实现。

依据 `dev-docs/implementation-plan.md` 任务 7"受控 Python 执行"和 `dev-docs/architecture.md` §5 执行核心 owner 边界，下一切片应解决：让用户为已确认 AnalysisPlan 的实验项目生成可执行 Python 代码候选，在应用托管的受控环境中执行代码，保存代码版本、数据版本、stdout、stderr、退出状态、表格产物和图表产物，并建立"数据 → 方案 → 执行 → 结果"追踪链的执行环节，最终推进项目状态到 `RESULT_CONFIRMED`。

本切片是 V0.3 里程碑第二部分，是后续 SPEC 0006 大纲与交付物切片的前提：大纲与 Word/PPT 必须基于已确认执行结果生成，不能直接从模型临时上下文拼装。

## 范围边界

本切片引入：

- 后端 owner 模块 `server/app/modules/execution/`：CodeTask、ExecutionRun、ExecutionArtifact 核心归属。
- 基础设施适配器 `server/app/infrastructure/sandbox/python_executor.py`：受控 Python 执行环境（subprocess + 临时脚本文件）。
- LLM 提供者 `server/app/modules/llm/code_task_provider.py`：基于 AnalysisPlan 生成 Python 代码候选。
- Alembic 迁移 `0005_create_execution_tables.py`：3 张表（code_tasks、execution_runs、execution_artifacts）+ 6 个索引。
- 11 个 API 端点（code_tasks 7 个 + execution_runs 4 个）。
- 2 个 Worker handler：`GENERATE_CODE_TASK`、`EXECUTE_CODE_TASK`。
- 前端 `features/execution/` 模块和 `CodeWorkspaceView`、`ExecutionWorkspaceView` 两个工作台。
- 项目状态推进：`ANALYSIS_CONFIRMED → EXECUTING → RESULT_CONFIRMED`（失败 `EXECUTION_FAILED`，可重试）。
- STALE 传播：AnalysisPlan 重新确认时关联 CodeTask 变 STALE；CodeTask 编辑后关联 ExecutionRun 变 STALE。
- 安装新运行时依赖：`scipy 1.17.1`、`scikit-learn 1.9.0`、`matplotlib 3.11.0`（计划版本，实际以验收时为准）。

本切片明确不做：

- 不接入真实 DeepSeek API（继续使用本地规则提供者 `LocalRuleCodeTaskProvider`）。
- 不支持 Notebook 风格代码单元。
- 不支持任意 import（白名单严格限制为 pandas、numpy、matplotlib、scipy.stats、sklearn、openpyxl）。
- 不支持交互式调试。
- 不支持 GPU 加速。
- 不做代码格式化或 lint。
- 不做代码补全。
- 不做语法高亮（前端用 textarea，不引入 Monaco/CodeMirror）。
- 不做 L3 完整论文复现。
- 不提供医疗诊断或治疗建议。
- 不做执行环境容器化（V1 用 subprocess，在线多用户版本再升级为容器隔离）。
- 不支持并行执行多个 CodeTask（V1 串行）。
- 不支持执行历史对比。
- 不支持执行环境自定义依赖安装。

## 关键技术决策

1. **执行方式：subprocess + 临时脚本文件**。通过 `subprocess.run([python, script_path], cwd=work_dir, capture_output=True, timeout=30)` 执行，**禁止** `shell=True`。子进程的 cwd 限制为 `projects/{project_id}/execution_runs/{run_id}/`，只能读写此目录。不使用 `exec()`、`eval()` 或 Notebook 内核，因为它们难以施加资源限制和 import 白名单。

2. **import 白名单：AST 解析校验**。执行前用 `ast.parse` 解析代码，遍历 AST 节点查找 `Import` 和 `ImportFrom`，校验模块名是否在白名单（pandas、numpy、matplotlib、scipy.stats、sklearn、openpyxl）。违规返回 `EXECUTION_IMPORT_FORBIDDEN` 错误（400），不创建 ExecutionRun。白名单严格禁止 `os`、`subprocess`、`socket`、`shutil`、`sys`、`ctypes`、`pickle`、`multiprocessing` 等危险模块。

3. **网络策略：完全禁用**。子进程不允许任何网络 socket 操作。V1 不实现网络代理或域名白名单，统一拒绝。后续若需联网数据集（如公开 API），需通过 Worker 在执行前下载到工作区，执行环境仍保持离线。

4. **资源限制：限时 30s、限内存 1024MB、限输出 10MB**。超时通过 `subprocess.run(timeout=30)` 实现；内存限制在 POSIX 用 `RLIMIT_AS`，Windows 用 `Job Object` 等价机制；输出大小在捕获后截断，截断时标记 `error_code=EXECUTION_OUTPUT_TOO_LARGE`。

5. **前端编辑器：textarea**。不引入 Monaco、CodeMirror 或其他代码编辑器依赖。前端用 `<textarea style={{fontFamily: 'monospace'}}>` 元素，支持基本编辑、复制、粘贴。语法高亮、自动补全、格式化推迟到后续切片。

6. **状态机推进**：触发 `EXECUTE_CODE_TASK` 时自动推进 `ANALYSIS_CONFIRMED → EXECUTING`；执行失败时自动推进 `EXECUTING → EXECUTION_FAILED`；用户编辑 CodeTask 后重新执行，自动推进 `EXECUTION_FAILED → EXECUTING`；用户调用 `/execution-runs/complete` 且至少一个 `SUCCEEDED` 时推进到 `RESULT_CONFIRMED`。

7. **STALE 传播链**：AnalysisPlan 重新确认（CONFIRMED → 编辑回到 CANDIDATE → 重新 CONFIRMED）时关联 CodeTask 全部变 STALE；CodeTask 编辑（任意状态）后关联 ExecutionRun 全部变 STALE。STALE 传播幂等，不重复标记。

8. **失败状态不被覆盖为成功**：ExecutionRun.status 一旦为 `FAILED`，不会被后续操作覆盖为 `SUCCEEDED`；用户必须重新执行才能获得新的 ExecutionRun 记录。

## 依赖影响

本切片计划安装以下运行时依赖（计划版本，实际安装版本以 SPEC 0005 验收时记录为准）：

- `scipy` `1.17.1`（dependency-review.md §6 复核版本）
- `scikit-learn` `1.9.0`（复核版本）
- `matplotlib` `3.11.0`（复核版本，使用 agg backend）

`playwright` 不在本切片安装。真实 DeepSeek 调用继续推迟到后续切片。

## 验收证据要求

完成本切片后必须满足：

- `server/.venv/Scripts/python.exe -m pytest` 全部通过（原 375 + 新增测试）。
- `server/.venv/Scripts/python.exe -m alembic upgrade head` 迁移到 `0005` 成功。
- `apps/web` 下 `npm.cmd run lint` 和 `npm.cmd run build` 通过。
- 端到端主链路：SPEC 0004 完成状态 → 生成代码 → 编辑确认 → 触发执行 → 查看 stdout/stderr/artifacts → 推进到 `RESULT_CONFIRMED`。
- 错误分支：项目状态不足、方案未确认、代码不可编辑、代码不可执行、超时、禁止 import、输出过大、无成功执行等返回结构化错误。
- STALE 传播：AnalysisPlan 重新确认时 CodeTask 变 STALE；CodeTask 编辑后 ExecutionRun 变 STALE。
- 受控环境限制生效：限时 30s、限内存 1024MB、限输出 10MB、import 白名单、网络禁用、`shell=True` 被禁止。
- 失败状态不被覆盖为成功。
- 无真实 DeepSeek API Key 时本地验收通过。

## 决策

启动 SPEC 0005"受控 Python 执行"切片。本切片实现完成后必须暂停，由项目负责人确认验收前不进入下一切片。

## 约束

- 不把本切片的启动误解为 V1 完成。
- 不绕过阶段闸：进入下一切片前必须先编写并确认 SPEC 0006（大纲与交付物）。
- 不在未经确认的情况下扩展到真实 DeepSeek 调用、Notebook 风格、交互式调试、GPU 加速、Monaco/CodeMirror 前端编辑器或容器化执行。
- Worker 只调用核心服务（execution）的方法并写回状态，不拥有业务语义。
- LLM Gateway 继续作为唯一接入点，业务模块不得直接调用 DeepSeek SDK 或写死模型名。
- 受控执行环境必须严格施加资源限制和 import 白名单，不得为方便调试而放宽。
- 失败状态必须如实保存，不得为通过验收而覆盖为成功。
- 外部 skill 仓库仍作为本地辅助资料保留在 `skills/` 下，不纳入主仓提交。
- 真实密钥不写入仓库，只能通过环境变量或本地未提交配置读取。
