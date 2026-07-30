# 决策 0031：SPEC 0022 代码任务执行链路关键修复

> **日期：** 2026-07-30
> **状态：** 已实现并验证（commit 93f1f13），待项目负责人确认收口
> **决策人：** 项目负责人
> **类型：** 已确认切片收口后阻断问题修复（SPEC 0022 代码任务执行链路）

## 背景

SPEC 0022（代码任务生成流式化，V2.4.0）已由项目负责人确认收口（见 [决策 0030](0030-confirm-spec-0022-acceptance.md)）。收口后启动 Worker 进程进行端到端完整链路验证（代码任务生成 → 执行 → 大纲 → Word/PPT 交付物），发现 3 项阻断问题导致代码任务执行失败。

这 3 项问题分属两类：
- **代码层修复（2 项）**：`_SYSTEM_PROMPT` 指令缺陷 + `python_executor` 路径解析缺陷，需改源码并补回归测试。
- **验证环境注意事项（1 项）**：`httpx` 客户端默认读取 Windows 系统代理导致 502，属验证脚本配置问题，不改业务代码，但需记录避免后续踩坑。

本决策整理这 3 项关键修复逻辑，作为 SPEC 0022 收口后的补充验收记录。

## 根因与修复

### 修复 1：prompt 换行双重转义（代码层，P0 阻断）

**现象**：Worker 执行代码任务时抛 `EXECUTION_IMPORT_FORBIDDEN: 代码语法错误: unexpected character after line continuation character`，AST 解析阶段就失败，未进入 subprocess。

**根因**：`deepseek_code_task_provider.py` 的 `_SYSTEM_PROMPT` 中存在指令"代码字符串中的换行使用 \\n 转义"。DeepSeek 遵循该指令，将代码中的真实换行符 `\n` 再转义一次为字面量 `\\n`，导致：
- LLM 返回的 JSON 中 `code` 字段值包含字面量 `\\n`（反斜杠 + n）
- 反序列化后 Python 字符串中是 `\n` 字面量（反斜杠 + n），而非真实换行
- AST 解析时把 `\` 当作行延续符，紧跟 `n` 报"unexpected character after line continuation character"

**修复**：删除"换行使用 \\n 转义"指令，新增"代码必须是合法 JSON（换行符由 JSON 标准自动转义，无需手动处理）"。

```python
# 修复前（deepseek_code_task_provider.py:66）
- 代码字符串中的换行使用 \n 转义

# 修复后
- 代码必须是合法 JSON（换行符由 JSON 标准自动转义，无需手动处理）
```

**关键认知**：JSON 标准本身会对字符串中的换行符自动转义为 `\n`（两字符序列），反序列化时还原为真实换行。任何"手动转义"指令都会导致双重转义。Prompt 不应指导 LLM 处理 JSON 序列化层的事。

### 修复 2：import 白名单缺失（代码层，P0 阻断）

**现象**：代码执行抛 `EXECUTION_IMPORT_FORBIDDEN: 禁止 import 模块: os`。

**根因**：`_SYSTEM_PROMPT` 未明确告知 LLM 允许的 import 模块范围。DeepSeek 在生成数据分析代码时，习惯性加入 `import os`（用于路径处理），但 `python_executor.FORBIDDEN_MODULES` 黑名单包含 `os`，AST 校验直接拒绝。

**修复**：在 `_SYSTEM_PROMPT` 中新增白名单和禁止模块列表：

```python
# 新增指令
允许 import 的模块白名单：pandas、numpy、matplotlib、scipy、sklearn、openpyxl
禁止 import 的模块：os、sys、subprocess、socket、ssl、requests、urllib 等
路径变量已由执行环境注入（DATA_PATH、OUTPUT_DIR），无需 import os
```

**关键认知**：`python_executor` 通过 AST 校验施加 import 白名单（详见 `python_executor.py:155 validate_code`），是 SPEC 0005 决策 0016 确认的安全边界。Prompt 必须与该白名单对齐，否则 LLM 生成的代码会100%被拒。路径处理应使用注入的 `DATA_PATH` / `OUTPUT_DIR` 字面量，而非 `import os`。

### 修复 3：python_executor 路径解析（代码层，P0 阻断）

**现象**：代码执行抛 `FileNotFoundError: [Errno 2] No such file or directory: 'D:\\...\\test.csv'`，但文件实际存在于该路径。

**根因**：`python_executor.execute_code_safe` 中 `work_path` 和 `data_path` 未 resolve 为绝对路径。当 `settings.project_data_root` 是相对路径时：
- `work_dir` 传入是相对路径，`subprocess.Popen` 的 `cwd` 设为相对路径
- 脚本文件 `script_path = work_path / "_run.py"` 也是相对路径
- subprocess 在相对 `cwd` 下执行相对 `script_path`，导致路径重复拼接（cwd + 相对 script_path）
- 同理 `data_path` 相对路径在子进程 cwd 下解析失败

**修复**：在 `execute_code_safe` 入口处将 `work_path` 和 `data_path` 都 resolve 为绝对路径：

```python
# python_executor.py:355-364（修复后）
work_path = Path(work_dir).resolve()
work_path.mkdir(parents=True, exist_ok=True)

data_path_resolved = (
    str(Path(data_path).resolve())
    if not Path(data_path).is_absolute()
    else str(data_path)
)
```

**关键认知**：subprocess 的 `cwd` 参数和脚本路径、注入的数据路径都必须是绝对路径，否则会在子进程的工作目录下重新解析，导致路径重复或找不到文件。`Path.resolve()` 会同时处理相对路径和符号链接，是最稳妥的做法。

## 链路验证环境注意事项

以下 3 项不属代码修复，但属链路验证必须遵守的环境配置，记录避免后续踩坑：

### 注意事项 1：httpx 客户端需禁用系统代理（验证脚本层）

**现象**：用 `httpx` 调用后端 API 验证链路时，返回 502 Bad Gateway。

**根因**：Windows 系统配置了 HTTP 代理（如公司代理或 VPN 残留），`httpx` 默认读取 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量，把请求经代理转发到 `localhost:8001`，代理无法处理本地请求返回 502。

**处理**：验证脚本中显式构造 `httpx.Client(trust_env=False)`，禁用环境变量代理读取。后端 uvicorn 服务本身不受影响（它监听端口，不主动走代理）。

```python
# 验证脚本正确姿势
import httpx
client = httpx.Client(trust_env=False)  # 不读取系统代理环境变量
```

**关键认知**：`httpx` 默认 `trust_env=True` 会读取 `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` 等环境变量。本地链路验证应使用 `trust_env=False`。前端 Vite 代理不受此影响（Vite 代理是 Node 层转发，不读 httpx 环境变量）。

### 注意事项 2：AnalysisPlan 字段名必须与 CSV 列名匹配（数据准备层）

**现象**：代码执行抛 `KeyError: 'diagnosis'`，脚本尝试访问 `diagnosis` 列但数据集中不存在。

**根因**：AnalysisPlan 的 `analysis_plan[].target_fields` 引用了 `diagnosis` 字段，但验证用的 CSV 数据集只有 `pathology_result` 列。`LocalRuleCodeTaskProvider` 根据 AnalysisPlan 生成代码，代码按 plan 访问 `diagnosis` 列，数据集没有该列就抛 KeyError。

**处理**：验证用 CSV 的列名必须与 AnalysisPlan 引用的字段名一致。若复用其他项目的 AnalysisPlan，需同步调整 CSV 列名（如把 `pathology_result` 改名为 `diagnosis`，或新增 `diagnosis` 列）。

**关键认知**：AnalysisPlan 是代码生成的输入契约，`target_fields` 是数据集字段引用，必须与数据集实际列名严格匹配。这是业务语义层的强约束，不是容错层能吸收的。

### 注意事项 3：Worker 进程需单独启动（运维层）

**现象**：API 能创建 job，但 job 一直 PENDING 不被处理。

**根因**：Worker 是独立进程（`python -m worker.main`），不随 uvicorn 自动启动。SPEC 0003 起就确立了 Worker 独立进程边界。

**处理**：链路验证时需单独启动 Worker 进程：

```bash
cd server
.venv\Scripts\python.exe -m worker.main
```

**关键认知**：后端 uvicorn 只承载 API + SSE 流式端点；后台任务（FETCH_URL、PARSE_DOCUMENT、GENERATE_EVIDENCE、PARSE_DATASET、GENERATE_ANALYSIS_PLAN、GENERATE_CODE_TASK、EXECUTE_CODE_TASK、GENERATE_OUTLINE、GENERATE_WORD、GENERATE_PPT）由 Worker 进程领取执行。这是 SPEC 0003 确立的架构边界。

## 影响范围

### 范围内（改动文件）

- `server/app/modules/llm/deepseek_code_task_provider.py`：删除换行转义错误指令，新增 JSON 标准转义说明 + import 白名单 + 禁止模块列表。
- `server/app/infrastructure/sandbox/python_executor.py`：`execute_code_safe` 入口 `work_path` 和 `data_path` resolve 为绝对路径。
- `server/tests/test_deepseek_code_task_provider_stream.py`：新增 8 个回归测试（4 换行转义 + 4 import 白名单）。
- `server/tests/test_python_executor.py`：新增 1 个路径解析回归测试。
- `server/tests/test_execution_worker_handlers.py`：新增 17 个 Worker 执行 handler 单元测试（覆盖成功/失败/沙箱限制/前置校验/产物收集/参数传递）。
- `dev-docs/acceptance.md`：新增 SPEC 0022 代码任务执行链路修复记录。

### 范围外（不改动）

- 其他 provider（任务单、证据卡片、分析方案、大纲）：不动。
- 数据库 schema / Alembic 迁移：不动。
- 前端：不动。
- `python_executor` 的 AST 校验逻辑、psutil 内存监控逻辑：不动（仅改路径解析）。

## 验收证据（2026-07-30）

### 单元测试

- `test_deepseek_code_task_provider_stream.py`：8 个回归测试全过（4 换行转义 + 4 import 白名单）。
- `test_python_executor.py`：48 个测试全过（含新增路径解析回归测试）。
- `test_execution_worker_handlers.py`：22 个测试全过（含 9 个异常分支补充：plan 不存在/JSON 解析失败/code_task 不存在/version 不存在/stderr 为空边界）。
- `test_outline_worker_handlers.py`：22 个测试全过（含 9 个新增失败路径/版本管理/降级链测试：Word/PPT 渲染失败、失败不覆盖成功、资源不存在、Word 模板降级、PPT 配置降级）。
- 两个 Worker handler 测试文件合并运行：44 passed in 3.94s。

### 完整链路验证

启动 uvicorn + Worker + Vite 三进程，用真实 DeepSeek API 端到端验证：

| 步骤 | 结果 |
| --- | --- |
| 流式生成代码任务（DEEPSEEK） | PASS，CANDIDATE |
| 确认代码任务 | PASS，CONFIRMED |
| Worker 执行代码任务 | PASS，exit_code=0，12 产物，3.65s |
| 确认执行结果 | PASS，RESULT_CONFIRMED |
| 流式生成大纲 | PASS，OUTLINE_CONFIRMED |
| 生成 Word | PASS，132,942 bytes |
| 生成 PPT | PASS，63,821 bytes |
| 项目状态 | COMPLETED |

### commit

`93f1f13`：修复 SPEC 0022 代码任务执行 prompt 换行转义、import 白名单、路径解析三项阻断问题

## 后续方向

- 三个修复均针对 SPEC 0022 代码任务执行链路，不扩大到其他 provider。
- `test_execution_worker_handlers.py` 的测试模式（mock provider + mock execute_code_safe + 内存 SQLite）可复用到其他 Worker handler 测试。
- 链路验证环境注意事项已回写 `dev-docs/acceptance.md`，后续验证脚本编写时应优先参考。
