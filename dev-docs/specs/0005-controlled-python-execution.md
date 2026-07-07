# 受控 Python 执行 SPEC

> 切片编号：SPEC 0005  
> 里程碑：V0.3 数据分析与 Python 执行（第二部分）  
> 依据：[project-charter.md](../project-charter.md) §3.1.9 受控 Python 执行环境、§9.4 Python 执行验收标准、[architecture.md](../architecture.md) §5 执行核心 owner、§风险边界 执行安全风险、[implementation-plan.md](../implementation-plan.md) 任务 7、[dependency-review.md](../dependency-review.md) §6 数据分析与交付物依赖复核、[0004-dataset-workspace.md](0004-dataset-workspace.md) 后续切片入口  
> 阶段约束：本切片实现完成后必须暂停；项目负责人确认验收前，不进入下一切片。  
> 前置条件：SPEC 0004 已完成实现、端到端验收并由项目负责人确认收口（commit `fba27b5`）。

## Why

SPEC 0004 让用户可以确认分析方案（`AnalysisPlan.status=CONFIRMED`），但项目当前没有任何执行 Python 代码的能力。charter §3.1.9 要求"报告中的实验结果来自受控环境真实执行，而不是仅由大模型编写描述"；architecture §5 把 CodeTask、ExecutionRun、ExecutionArtifact 列为执行核心的唯一 owner，并要求"Python 执行器不直接读写任意项目文件；只能访问被授权的数据版本目录和输出目录"。

本切片要建立"数据 → 方案 → 执行 → 结果"追踪链的执行环节：

- 基于已确认 AnalysisPlan 生成可执行的 Python 代码任务（CodeTask）；
- 用户可审阅、编辑、确认或拒绝代码候选；
- 在应用托管的受控环境中执行代码（独立进程、限时、限内存、限目录、限 import、禁网络）；
- 保存代码版本、数据版本、stdout、stderr、退出状态、表格产物和图表产物；
- 失败状态不被覆盖为成功；
- 用户确认至少一个执行结果后推进项目状态到 `RESULT_CONFIRMED`。

本切片完成后 V0.3 闭环：上传数据 → 解析 → 确认方案 → 生成代码 → 受控执行 → 真实结果。后续切片（SPEC 0006 大纲与交付物）才能基于已确认执行结果生成统一大纲和 Word/PPT。

## What Changes

- 新增后端 owner 模块 `server/app/modules/execution/`：CodeTask、ExecutionRun、ExecutionArtifact 核心归属。
- 新增基础设施适配器 `server/app/infrastructure/sandbox/python_executor.py`：受控 Python 执行环境（subprocess + 临时脚本文件）。
- 新增 LLM 提供者 `server/app/modules/llm/code_task_provider.py`：基于 AnalysisPlan 生成 Python 代码候选。
- 新增 Alembic 迁移 `0005_create_execution_tables.py`：3 张表 + 索引。
- 新增 11 个 API 端点（code_tasks 6 个 + execution_runs 5 个）。
- 新增 2 个 Worker handler：`GENERATE_CODE_TASK`、`EXECUTE_CODE_TASK`。
- 新增前端 `features/execution/` 模块和 `CodeWorkspaceView`、`ExecutionWorkspaceView` 两个工作台。
- 项目状态推进：`ANALYSIS_CONFIRMED → EXECUTING → RESULT_CONFIRMED`（失败 `EXECUTION_FAILED`，可重试）。
- STALE 传播：AnalysisPlan 重新确认时关联 CodeTask 变 STALE；CodeTask 编辑后关联 ExecutionRun 变 STALE。
- 安装新运行时依赖：`scipy 1.17.1`、`scikit-learn 1.9.0`、`matplotlib 3.11.0`。
- **不引入**：真实 DeepSeek 调用（继续本地规则提供者）、Notebook 风格、交互式调试、GPU 加速、Monaco/CodeMirror 前端编辑器。

## Impact

- 受影响 specs：
  - [0004-dataset-workspace.md](0004-dataset-workspace.md) 状态机前置：本切片要求 `ANALYSIS_CONFIRMED` 之后才能生成代码任务
  - [project-charter.md](../project-charter.md) §3.1.9 受控 Python 执行环境、§9.4 Python 执行验收标准
- 受影响代码：
  - `server/app/modules/projects/status.py`：状态机已有 `EXECUTING`、`EXECUTION_FAILED`、`RESULT_CONFIRMED`，无需修改枚举
  - `server/app/modules/jobs/status.py`：新增 `JobType.GENERATE_CODE_TASK` 和 `JobType.EXECUTE_CODE_TASK`
  - `server/app/modules/analysis/service.py`：AnalysisPlan 重新确认时触发 CodeTask STALE 传播
  - `server/app/main.py`：注册新路由、扩展错误码映射
  - `server/alembic/env.py`：导入新 ORM 模型
  - `server/worker/handlers.py`：新增 2 个 handler
  - `server/app/core/config.py`：新增执行环境配置项
  - `apps/web/src/app/App.tsx`：注册新路由
  - `apps/web/src/routes/ProjectDetailView.tsx`：加入代码和执行工作台入口
  - `apps/web/src/features/jobs/types.ts`：扩展 JobType 联合类型

## ADDED Requirements

### Requirement: Code Task Generation

系统 SHALL 允许用户在 `ANALYSIS_CONFIRMED` 状态的项目中，针对已确认的 AnalysisPlan 触发生成 Python 代码候选（CodeTask）。

代码候选生成流程：
1. 校验 AnalysisPlan 状态为 `CONFIRMED`，否则返回 `ANALYSIS_PLAN_NOT_CONFIRMED`。
2. 调用 LLM Gateway 的 `code_task_provider` 生成代码候选。
3. 创建 CodeTask 记录，`status=CANDIDATE`，关联 `analysis_plan_id` 和 `dataset_version_id`。
4. 创建 `GENERATE_CODE_TASK` 后台任务并返回 `job_id`。
5. Worker 调用 `LocalRuleCodeTaskProvider` 按 AnalysisPlan 的 cleaning/analysis/chart plan 拼装可执行 Python 脚本。
6. 字段数超过 50 时截断到前 20 个字段，避免代码爆炸。

生成的代码必须：
- 头部声明数据集路径变量（`DATA_PATH`）和输出目录变量（`OUTPUT_DIR`），由执行环境注入；
- 使用 `pandas` 读取数据集；
- 按 cleaning_plan 执行数据清洗；
- 按 analysis_plan 执行统计分析，结果用 `df.to_csv()` 保存到 `OUTPUT_DIR`；
- 按 chart_plan 用 `matplotlib`（agg backend）生成图表，保存为 PNG 到 `OUTPUT_DIR`；
- 不包含 `import os`、`import subprocess`、`import socket` 等危险模块；
- 不包含网络访问代码。

#### Scenario: 生成代码候选

- **WHEN** 用户在 `ANALYSIS_CONFIRMED` 状态的项目中，对 `CONFIRMED` 状态的 AnalysisPlan 调用 `POST /code/generate`
- **THEN** 系统创建 CodeTask（`status=CANDIDATE`），关联 AnalysisPlan 和 DatasetVersion
- **AND** 创建 `GENERATE_CODE_TASK` 任务，返回 `job_id`
- **AND** Worker 完成后 CodeTask.code 包含可执行 Python 脚本

#### Scenario: 项目状态不足

- **WHEN** 项目状态为 `ANALYSIS_PLANNED`（未达 `ANALYSIS_CONFIRMED`）
- **THEN** 返回 `PROJECT_ANALYSIS_NOT_CONFIRMED` 错误（400）

#### Scenario: 分析方案未确认

- **WHEN** AnalysisPlan 状态为 `CANDIDATE` 或 `STALE`
- **THEN** 返回 `ANALYSIS_PLAN_NOT_CONFIRMED` 错误（400）

#### Scenario: 字段过多

- **WHEN** 数据集字段数超过 50
- **THEN** 生成的代码只对前 20 个字段执行详细分析，其余字段在代码注释中标记为"字段过多，需手动选择"

### Requirement: Code Task Editing

系统 SHALL 允许用户编辑 CodeTask 的 `code` 字段：

- **编辑**：用户可修改 `CANDIDATE` 或 `CONFIRMED` 状态的 CodeTask
- 编辑 `CONFIRMED` 后状态回到 `CANDIDATE`，需要重新确认
- 编辑后关联的 ExecutionRun 全部变 `STALE`（需重新执行）
- 记录 `code_version`（每次编辑递增）

#### Scenario: 编辑候选代码

- **WHEN** 用户对 `CANDIDATE` 状态的 CodeTask 调用 `PUT /code-tasks/{task_id}`
- **THEN** CodeTask.code 更新，`code_version` 递增，状态保持 `CANDIDATE`
- **AND** 关联的 ExecutionRun 全部变 `STALE`

#### Scenario: 编辑已确认代码

- **WHEN** 用户对 `CONFIRMED` 状态的 CodeTask 调用 `PUT /code-tasks/{task_id}`
- **THEN** CodeTask.code 更新，`code_version` 递增，状态回到 `CANDIDATE`
- **AND** 关联的 ExecutionRun 全部变 `STALE`

#### Scenario: 编辑 STALE 代码

- **WHEN** 用户对 `STALE` 状态的 CodeTask 调用 `PUT /code-tasks/{task_id}`
- **THEN** 返回 `CODE_TASK_NOT_EDITABLE` 错误（400）；STALE 代码必须先重新生成

### Requirement: Code Task Confirmation

系统 SHALL 允许用户确认或拒绝 CodeTask：

- **确认**：状态 `CANDIDATE → CONFIRMED`，记录 `confirmed_at`
- **拒绝**：状态 `CANDIDATE → REJECTED`，必须重新生成
- 只有 `CONFIRMED` 状态的 CodeTask 才能触发执行

#### Scenario: 用户确认代码

- **WHEN** 用户对 `CANDIDATE` 状态的 CodeTask 调用 `POST /code-tasks/{task_id}/confirm`
- **THEN** CodeTask.status = `CONFIRMED`，记录 `confirmed_at`
- **AND** 可以调用 `POST /code-tasks/{task_id}/execute` 触发执行

#### Scenario: 拒绝代码

- **WHEN** 用户对 `CANDIDATE` 状态的 CodeTask 调用 `POST /code-tasks/{task_id}/reject`
- **THEN** CodeTask.status = `REJECTED`，必须重新生成

### Requirement: Controlled Execution Environment

系统 SHALL 通过独立进程执行已确认的 CodeTask，并施加以下资源限制：

| 限制项 | 默认值 | 说明 |
| --- | --- | --- |
| 执行超时 | 30 秒 | 超过则终止进程，状态 `FAILED`，错误码 `EXECUTION_TIMEOUT` |
| 内存上限 | 1024 MB | 通过 `subprocess` 资源限制（POSIX `RLIMIT_AS`，Windows 用 `Job Object` 等价机制） |
| 输出大小上限 | 10 MB | stdout/stderr 合计超过则截断，状态 `FAILED`，错误码 `EXECUTION_OUTPUT_TOO_LARGE` |
| 工作目录 | `projects/{project_id}/execution_runs/{run_id}/` | 子进程的 cwd，只能读写此目录 |
| 网络访问 | 完全禁用 | 子进程不允许任何网络 socket 操作 |
| import 白名单 | pandas、numpy、matplotlib、scipy.stats、sklearn、openpyxl | 通过 AST 解析校验，禁止其他 import |
| `shell` 参数 | 禁止 `shell=True` | 通过 `subprocess.run([python, script_path], ...)` 执行 |

执行流程：
1. 创建 `ExecutionRun` 记录，`status=PENDING`，关联 `code_task_id`、`code_version`、`dataset_version_id`
2. 创建受控工作目录 `projects/{project_id}/execution_runs/{run_id}/`
3. 写入临时脚本文件 `run.py`，内容为 CodeTask.code 加上环境注入头部
4. 通过 `subprocess.run` 执行 `python run.py`，cwd 设为受控工作目录
5. 捕获 stdout、stderr、exit_code、执行时长
6. 扫描受控工作目录，收集所有 `.csv` 和 `.png` 文件作为 ExecutionArtifact
7. 根据退出码设置 ExecutionRun.status：`SUCCEEDED`（exit_code=0）或 `FAILED`（exit_code≠0）
8. 失败时不覆盖为成功；stdout/stderr 完整保存（即使失败）

#### Scenario: 成功执行

- **WHEN** 用户对 `CONFIRMED` 状态的 CodeTask 调用 `POST /code-tasks/{task_id}/execute`
- **THEN** 创建 `EXECUTE_CODE_TASK` 任务，Worker 执行脚本
- **AND** exit_code=0 时 ExecutionRun.status = `SUCCEEDED`，artifacts 收集完成
- **AND** project.status 推进到 `EXECUTING`

#### Scenario: 执行超时

- **WHEN** 脚本执行超过 30 秒
- **THEN** 进程被终止，ExecutionRun.status = `FAILED`，error_code = `EXECUTION_TIMEOUT`

#### Scenario: 禁止 import

- **WHEN** 代码包含 `import os` 或 `import subprocess` 等非白名单模块
- **THEN** 执行前 AST 校验失败，返回 `EXECUTION_IMPORT_FORBIDDEN` 错误（400）
- **AND** ExecutionRun 不创建（在 API 层拦截）

#### Scenario: 执行失败

- **WHEN** 脚本抛出异常，exit_code ≠ 0
- **THEN** ExecutionRun.status = `FAILED`，error_code = `EXECUTION_FAILED`，stderr 保存完整堆栈
- **AND** project.status 推进到 `EXECUTION_FAILED`

#### Scenario: 输出过大

- **WHEN** stdout + stderr 超过 10 MB
- **THEN** 输出被截断，ExecutionRun.status = `FAILED`，error_code = `EXECUTION_OUTPUT_TOO_LARGE`

### Requirement: Execution Run and Artifacts

系统 SHALL 保存完整的执行记录和产物：

ExecutionRun 字段：
- `id`、`project_id`、`code_task_id`、`dataset_version_id`
- `code_version`（执行时的 CodeTask.code_version 快照）
- `status`（PENDING、RUNNING、SUCCEEDED、FAILED、STALE）
- `stdout`、`stderr`（完整输出，截断后标记）
- `exit_code`（int 或 None）
- `started_at`、`finished_at`、`duration_seconds`
- `error_code`、`error_message`
- `created_at`

ExecutionArtifact 字段：
- `id`、`execution_run_id`、`project_id`
- `artifact_type`（TABLE_CSV、CHART_PNG）
- `file_path`（受控工作区相对路径）
- `file_size_bytes`
- `name`（用户可见名称，如"年龄分布直方图.png"）
- `created_at`

#### Scenario: 收集产物

- **WHEN** ExecutionRun 执行完成（无论成功或失败）
- **THEN** 扫描受控工作目录，所有 `.csv` 文件登记为 `TABLE_CSV` 类型 artifact
- **AND** 所有 `.png` 文件登记为 `CHART_PNG` 类型 artifact
- **AND** 每个产物记录 file_path、file_size_bytes、name

#### Scenario: 失败时仍保存产物

- **WHEN** 脚本执行失败但已生成部分产物
- **THEN** 产物仍被收集（用户可查看已生成的部分结果）
- **AND** ExecutionRun.status = `FAILED`，但 artifacts 列表非空

### Requirement: Result Confirmation

系统 SHALL 允许用户确认执行结果，推进项目状态到 `RESULT_CONFIRMED`：

- **完成结果确认**：至少一个 ExecutionRun 状态为 `SUCCEEDED` 时，可推进 project.status 到 `RESULT_CONFIRMED`
- **STALE 传播**：CodeTask 编辑后关联 ExecutionRun 全部变 `STALE`
- **重试**：`EXECUTION_FAILED` 状态下，用户编辑 CodeTask 后重新执行，状态自动推进回 `EXECUTING`
- **重置**：用户可通过显式操作回到 `ANALYSIS_CONFIRMED`（不在本切片实现，推迟到后续切片）

#### Scenario: 完成结果确认

- **WHEN** 用户调用 `POST /execution-runs/complete` 且至少一个 ExecutionRun 为 `SUCCEEDED`
- **THEN** project.status = `RESULT_CONFIRMED`

#### Scenario: 无成功执行

- **WHEN** 用户调用 `POST /execution-runs/complete` 但无 `SUCCEEDED` 状态的 ExecutionRun
- **THEN** 返回 `PROJECT_NO_SUCCESSFUL_EXECUTION_RUN` 错误（400）

#### Scenario: 编辑代码后执行记录过期

- **WHEN** 用户编辑 CodeTask 后，关联的 ExecutionRun 全部变 `STALE`
- **AND** 用户必须重新执行才能获得新的 `SUCCEEDED` 记录

### Requirement: STALE Propagation

系统 SHALL 在以下情况下将关联产物标记为 STALE：

- AnalysisPlan 重新确认（CONFIRMED → 编辑回到 CANDIDATE → 重新 CONFIRMED）时，关联的 CodeTask 全部变 STALE
- CodeTask 编辑（任意状态）后，关联的 ExecutionRun 全部变 STALE
- STALE 传播幂等：已是 STALE 的记录保持 STALE，不重复标记
- 项目状态不自动回退（用户需显式操作）

## MODIFIED Requirements

### Requirement: Project Status Machine

原状态机（SPEC 0004 之后）：

```text
DRAFT → ... → ANALYSIS_CONFIRMED → [停止]
```

修改后：

```text
DRAFT → ... → ANALYSIS_CONFIRMED → EXECUTING → RESULT_CONFIRMED → [后续切片：大纲]
                                    ↓
                              EXECUTION_FAILED（可重试）
```

新增状态推进规则：
- `ANALYSIS_CONFIRMED → EXECUTING`：触发 `EXECUTE_CODE_TASK` 时自动推进
- `EXECUTING → RESULT_CONFIRMED`：用户调用 `complete` 且至少一个 `SUCCEEDED`
- `EXECUTING → EXECUTION_FAILED`：执行失败时自动推进
- `EXECUTION_FAILED → EXECUTING`：用户编辑 CodeTask 后重新执行，自动推进回
- `EXECUTION_FAILED → ANALYSIS_CONFIRMED`：显式"重置执行"（推迟到后续切片）

### Requirement: JobType Enum

`server/app/modules/jobs/status.py` 新增：

- `GENERATE_CODE_TASK`：基于 AnalysisPlan 生成 Python 代码候选
- `EXECUTE_CODE_TASK`：在受控环境中执行 CodeTask

### Requirement: AnalysisPlan STALE 传播

`server/app/modules/analysis/service.py` 修改：
- `confirm_analysis_plan`：确认时不变更 CodeTask 状态（首次确认才生成 CodeTask）
- AnalysisPlan 从 `CONFIRMED` 编辑回到 `CANDIDATE` 时，关联的 CodeTask 全部变 `STALE`
- AnalysisPlan 重新 `CONFIRMED` 后，旧 CodeTask 保持 STALE，需用户重新生成

## REMOVED Requirements

无。本切片只新增，不删除现有功能。

## 后端核心合同

### Execution 模块（`server/app/modules/execution/`）

#### status.py

```python
class CodeTaskStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    STALE = "STALE"

class ExecutionRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    STALE = "STALE"

class ExecutionArtifactType(str, Enum):
    TABLE_CSV = "TABLE_CSV"
    CHART_PNG = "CHART_PNG"

class CodeChangeType(str, Enum):
    CODE_TASK_GENERATED = "CODE_TASK_GENERATED"
    CODE_TASK_UPDATED = "CODE_TASK_UPDATED"
    CODE_TASK_CONFIRMED = "CODE_TASK_CONFIRMED"
    CODE_TASK_REJECTED = "CODE_TASK_REJECTED"
    CODE_TASK_EXECUTED = "CODE_TASK_EXECUTED"

class ExecutionChangeType(str, Enum):
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_SUCCEEDED = "EXECUTION_SUCCEEDED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXECUTIONS_COMPLETED = "EXECUTIONS_COMPLETED"
```

#### contracts.py

```python
class UpdateCodeTaskRequest(BaseModel):
    code: str

class CodeTaskResponse(BaseModel):
    id: str
    project_id: str
    analysis_plan_id: str
    dataset_id: str
    dataset_version_id: str
    code: str
    code_version: int
    status: str
    candidate_source: str
    created_at: str
    updated_at: str | None
    confirmed_at: str | None

class CodeTaskListResponse(BaseModel):
    items: list[CodeTaskResponse]

class ExecutionRunResponse(BaseModel):
    id: str
    project_id: str
    code_task_id: str
    dataset_version_id: str
    code_version: int
    status: str
    stdout: str
    stderr: str
    exit_code: int | None
    started_at: str | None
    finished_at: str | None
    duration_seconds: float | None
    error_code: str | None
    error_message: str | None
    created_at: str
    artifacts: list[ExecutionArtifactResponse]

class ExecutionArtifactResponse(BaseModel):
    id: str
    execution_run_id: str
    artifact_type: str
    file_path: str
    file_size_bytes: int
    name: str
    created_at: str

class ExecutionRunListResponse(BaseModel):
    items: list[ExecutionRunResponse]

class CompleteExecutionResponse(BaseModel):
    status: str
```

#### models.py

```python
class CodeTask(Base):
    __tablename__ = "code_tasks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    analysis_plan_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    dataset_id: Mapped[str] = mapped_column(String(32), nullable=False)
    dataset_version_id: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    code_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

class ExecutionRun(Base):
    __tablename__ = "execution_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    code_task_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    dataset_version_id: Mapped[str] = mapped_column(String(32), nullable=False)
    code_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    stdout: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stderr: Mapped[str] = mapped_column(Text, nullable=False, default="")
    exit_code: Mapped[int] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    error_code: Mapped[str] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime]

class ExecutionArtifact(Base):
    __tablename__ = "execution_artifacts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    execution_run_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime]
```

#### service.py 关键方法

```python
def generate_code_task(db, project_id, analysis_plan_id) -> str:
    """触发生成代码候选，返回 job_id。前置：project.status=ANALYSIS_CONFIRMED 且 plan.status=CONFIRMED。"""

def list_code_tasks(db, project_id, status=None) -> list[CodeTask]: ...

def get_code_task(db, task_id) -> CodeTask: ...

def update_code_task(db, task_id, code) -> CodeTask:
    """编辑 CANDIDATE 或 CONFIRMED；CONFIRMED 回到 CANDIDATE；关联 ExecutionRun 变 STALE。"""

def confirm_code_task(db, task_id) -> CodeTask: ...

def reject_code_task(db, task_id) -> CodeTask: ...

def execute_code_task(db, task_id) -> str:
    """触发执行，返回 job_id。前置：task.status=CONFIRMED。"""

def list_execution_runs(db, project_id, status=None) -> list[ExecutionRun]: ...

def get_execution_run(db, run_id) -> ExecutionRun: ...

def get_artifact_file_path(db, run_id, artifact_id) -> tuple[str, str]:
    """返回 (绝对路径, 文件名) 用于下载。"""

def complete_execution(db, project_id):
    """推进 project.status 到 RESULT_CONFIRMED。前置：至少一个 SUCCEEDED。"""

# Worker 调用方法
def save_code_task_draft(db, analysis_plan_id, dataset_version_id, code) -> CodeTask: ...

def mark_execution_running(db, run_id): ...
def mark_execution_succeeded(db, run_id, stdout, stderr, exit_code, started_at, finished_at): ...
def mark_execution_failed(db, run_id, stdout, stderr, exit_code, error_code, error_message, started_at, finished_at): ...
def save_execution_artifacts(db, run_id, artifacts) -> list[ExecutionArtifact]: ...

def _mark_code_tasks_stale(db, analysis_plan_id) -> int:
    """关联代码任务变 STALE。"""

def _mark_execution_runs_stale(db, code_task_id) -> int:
    """关联执行记录变 STALE。"""
```

### 基础设施：受控 Python 执行器

`server/app/infrastructure/sandbox/python_executor.py`：

```python
@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    artifacts: list[ArtifactInfo]  # 收集到的产物

@dataclass
class ArtifactInfo:
    file_path: str       # 相对路径
    file_size_bytes: int
    name: str
    artifact_type: str   # TABLE_CSV 或 CHART_PNG

class SandboxError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message

def validate_code(code: str, allowed_imports: list[str]) -> None:
    """AST 解析校验 import 白名单。违规抛 SandboxError(code=EXECUTION_IMPORT_FORBIDDEN)。"""

def execute_code(
    code: str,
    work_dir: str,                       # 受控工作目录绝对路径
    data_path: str,                      # 数据集文件绝对路径
    timeout_seconds: int = 30,
    memory_limit_mb: int = 1024,
    output_max_bytes: int = 10 * 1024 * 1024,
    allowed_imports: list[str] | None = None,
) -> ExecutionResult:
    """在受控环境中执行 Python 代码。
    
    流程：
    1. validate_code 校验 import
    2. 写入 run.py（头部注入 DATA_PATH、OUTPUT_DIR 环境变量）
    3. subprocess.run([python, run.py], cwd=work_dir, capture_output=True, timeout=timeout)
    4. 截断 stdout/stderr 超过 output_max_bytes
    5. 扫描 work_dir 收集 .csv 和 .png 文件
    6. 返回 ExecutionResult
    
    异常：
    - SandboxError(code=EXECUTION_IMPORT_FORBIDDEN)
    - SandboxError(code=EXECUTION_TIMEOUT)（subprocess.TimeoutExpired 转）
    - SandboxError(code=EXECUTION_OUTPUT_TOO_LARGE)
    - SandboxError(code=EXECUTION_FAILED)
    """
```

### LLM 提供者：代码任务

`server/app/modules/llm/code_task_provider.py`：

```python
@dataclass
class CodeTaskDraft:
    code: str  # 完整可执行 Python 脚本

class CodeTaskDraftProvider(ABC):
    @abstractmethod
    def generate(self, analysis_plan: dict, dataset_profile: dict) -> CodeTaskDraft: ...

class LocalRuleCodeTaskProvider(CodeTaskDraftProvider):
    """基于 AnalysisPlan 的 cleaning/analysis/chart plan 拼装 Python 代码。
    
    生成规则：
    - 头部注释说明生成来源
    - DATA_PATH 和 OUTPUT_DIR 由执行环境注入（代码中只引用变量名）
    - 数据读取：pd.read_csv(DATA_PATH) 或 pd.read_excel(DATA_PATH)
    - 清洗：按 cleaning_plan 逐条生成代码（缺失值填充、类型转换、重复行删除）
    - 分析：按 analysis_plan 生成描述性统计、分组统计、相关性、统计检验
    - 可视化：按 chart_plan 生成 matplotlib 图表，plt.savefig(OUTPUT_DIR + "/xxx.png")
    - 字段数 > 50 时截断到前 20
    """

class FakeCodeTaskProvider(CodeTaskDraftProvider):
    """确定性测试用提供者，返回固定代码。"""
```

`server/app/modules/llm/gateway.py` 新增：

```python
def get_code_task_provider() -> CodeTaskDraftProvider: ...
```

## API 合同

### Code Tasks API（`server/app/api/routers/code_tasks.py`）

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/api/projects/{project_id}/analysis/{plan_id}/code/generate` | POST | 触发生成代码候选 |
| `/api/projects/{project_id}/code-tasks` | GET | 代码任务列表（支持 status 过滤） |
| `/api/projects/{project_id}/code-tasks/{task_id}` | GET | 代码任务详情 |
| `/api/projects/{project_id}/code-tasks/{task_id}` | PUT | 编辑代码（code 字段） |
| `/api/projects/{project_id}/code-tasks/{task_id}/confirm` | POST | 确认代码 |
| `/api/projects/{project_id}/code-tasks/{task_id}/reject` | POST | 拒绝代码 |
| `/api/projects/{project_id}/code-tasks/{task_id}/execute` | POST | 触发执行（前置：CONFIRMED） |

### Execution Runs API（`server/app/api/routers/execution_runs.py`）

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/api/projects/{project_id}/execution-runs` | GET | 执行记录列表（含 artifacts，支持 status 过滤） |
| `/api/projects/{project_id}/execution-runs/{run_id}` | GET | 执行详情（含 stdout/stderr/artifacts） |
| `/api/projects/{project_id}/execution-runs/{run_id}/artifacts/{artifact_id}` | GET | 下载产物（返回文件流） |
| `/api/projects/{project_id}/execution-runs/complete` | POST | 完成结果确认 |

## 数据库迁移

`server/alembic/versions/0005_create_execution_tables.py`（revision=`0005`, down_revision=`0004`）：

```text
code_tasks:
  id (String 32, PK)
  project_id (String 32, not null, index)
  analysis_plan_id (String 32, not null, index)
  dataset_id (String 32, not null)
  dataset_version_id (String 32, not null)
  code (Text, not null)
  code_version (Integer, not null, default=1)
  status (String 32, not null)
  candidate_source (String 32, not null)
  created_at (DateTime, not null)
  updated_at (DateTime, not null)
  confirmed_at (DateTime, null)

execution_runs:
  id (String 32, PK)
  project_id (String 32, not null, index)
  code_task_id (String 32, not null, index)
  dataset_version_id (String 32, not null)
  code_version (Integer, not null)
  status (String 32, not null)
  stdout (Text, not null, default="")
  stderr (Text, not null, default="")
  exit_code (Integer, null)
  started_at (DateTime, null)
  finished_at (DateTime, null)
  duration_seconds (Float, null)
  error_code (String 64, null)
  error_message (Text, null)
  created_at (DateTime, not null)

execution_artifacts:
  id (String 32, PK)
  execution_run_id (String 32, not null, index)
  project_id (String 32, not null, index)
  artifact_type (String 32, not null)
  file_path (String 1000, not null)
  file_size_bytes (Integer, not null)
  name (String 500, not null)
  created_at (DateTime, not null)

索引：
  ix_code_tasks_project_id
  ix_code_tasks_analysis_plan_id
  ix_execution_runs_project_id
  ix_execution_runs_code_task_id
  ix_execution_artifacts_execution_run_id
  ix_execution_artifacts_project_id
```

## LLM 网关边界

- 配置项：`CODE_TASK_PROVIDER`，默认 `local_rule`。
- `LocalRuleCodeTaskProvider`：基于 AnalysisPlan 拼装 Python 代码，不调用外部 API。
- `FakeCodeTaskProvider`：测试用确定性提供者。
- 真实 DeepSeek 适配器**不**在本切片接入业务模块。
- 业务模块只通过 `get_code_task_provider()` 工厂方法获取提供者，不直接实例化。

## 配置

`server/app/core/config.py` 新增：

```python
@property
def code_execution_enabled(self) -> bool:
    return os.getenv("CODE_EXECUTION_ENABLED", "true").lower() == "true"

@property
def code_execution_timeout_seconds(self) -> int:
    return int(os.getenv("CODE_EXECUTION_TIMEOUT_SECONDS", "30"))

@property
def code_execution_memory_limit_mb(self) -> int:
    return int(os.getenv("CODE_EXECUTION_MEMORY_LIMIT_MB", "1024"))

@property
def code_execution_output_max_bytes(self) -> int:
    return int(os.getenv("CODE_EXECUTION_OUTPUT_MAX_BYTES", str(10 * 1024 * 1024)))

@property
def code_execution_allowed_imports(self) -> list[str]:
    return ["pandas", "numpy", "matplotlib", "scipy", "sklearn", "openpyxl"]

@property
def code_task_provider(self) -> str:
    return os.getenv("CODE_TASK_PROVIDER", "local_rule")
```

## 前端工作台范围

### 代码工作区（`CodeWorkspaceView`）

展示：
- 项目名称和状态
- 数据集和分析方案概览（只读）
- 代码任务列表（含状态、来源、确认时间、code_version）
- 生成代码按钮（针对已确认 AnalysisPlan）
- 代码编辑器（textarea，monospace 字体，可调整高度）
- 保存、确认、拒绝按钮
- 执行按钮（仅 CONFIRMED 状态可用）
- STALE 标记
- 后台任务状态轮询

行为：
- 项目状态未达 `ANALYSIS_CONFIRMED` 时禁用生成入口
- 生成后立即创建任务并轮询
- 编辑后 code_version 递增，状态回到 CANDIDATE
- 执行后跳转到执行工作区查看结果

### 执行工作区（`ExecutionWorkspaceView`）

展示：
- 执行记录列表（含状态、exit_code、duration、artifacts 数量）
- 执行详情：stdout、stderr（可滚动、可复制）
- 产物列表：表格（CSV 预览前 10 行）、图表（PNG 内联展示）
- 下载按钮（单个产物）
- 完成结果确认按钮
- STALE 标记
- 错误展示（结构化错误码和消息）

行为：
- 执行中状态轮询（PENDING/RUNNING 时 2 秒轮询）
- 失败时展示完整 stderr 和错误码
- 完成确认按钮仅在存在 SUCCEEDED 记录时可用
- 复用现有 `useJob` 轮询模式和 `errorMessage` 函数

### 通用行为

- 复用 SPEC 0003 的任务轮询模式（`useJob` hook，PENDING/RUNNING 时 2 秒轮询）
- 错误消息复用 `errorMessage(e, fallback)` 函数
- 中文界面，inline styles 与现有视图风格一致
- 代码编辑器用 `<textarea>` 元素，`font-family: monospace`，不引入新依赖

## 错误码

新增错误码：

| 错误码 | HTTP 状态码 | 触发条件 |
| --- | --- | --- |
| `PROJECT_ANALYSIS_NOT_CONFIRMED` | 400 | 项目状态未达 ANALYSIS_CONFIRMED |
| `ANALYSIS_PLAN_NOT_CONFIRMED` | 400 | AnalysisPlan 状态不是 CONFIRMED |
| `CODE_TASK_NOT_FOUND` | 404 | 代码任务不存在或不属于该项目 |
| `CODE_TASK_NOT_EDITABLE` | 400 | 只能修改候选或已确认代码（STALE/REJECTED 不可编辑） |
| `CODE_TASK_NOT_CONFIRMABLE` | 400 | 只能确认候选代码 |
| `CODE_TASK_NOT_EXECUTABLE` | 400 | 只能执行已确认代码 |
| `EXECUTION_RUN_NOT_FOUND` | 404 | 执行记录不存在 |
| `EXECUTION_ARTIFACT_NOT_FOUND` | 404 | 产物不存在 |
| `EXECUTION_TIMEOUT` | 400 | 执行超过 30 秒 |
| `EXECUTION_MEMORY_LIMIT` | 400 | 执行内存超过 1024 MB |
| `EXECUTION_OUTPUT_TOO_LARGE` | 400 | stdout/stderr 超过 10 MB |
| `EXECUTION_IMPORT_FORBIDDEN` | 400 | 代码包含非白名单 import |
| `EXECUTION_FAILED` | 400 | 脚本执行失败（exit_code ≠ 0） |
| `PROJECT_NO_CONFIRMED_CODE_TASK` | 400 | 没有已确认代码任务 |
| `PROJECT_NO_SUCCESSFUL_EXECUTION_RUN` | 400 | 没有成功的执行记录 |
| `CODE_EXECUTION_DISABLED` | 403 | 执行环境被配置禁用 |

## 安全与边界

- subprocess + 临时脚本文件，**禁止** `shell=True`
- 限时 30 秒、限内存 1024 MB、限输出 10 MB
- 工作目录限制：`projects/{project_id}/execution_runs/{run_id}/`，子进程只能读写此目录
- 网络完全禁用：子进程不允许任何网络 socket 操作
- import 白名单：`pandas`、`numpy`、`matplotlib`（agg backend）、`scipy.stats`、`sklearn`、`openpyxl`
- 通过 AST 解析校验 import 语句，禁止 `os`、`subprocess`、`socket`、`shutil`、`sys`、`ctypes` 等
- 不执行非 Python 代码
- 不支持 GPU 加速
- 失败状态不被覆盖为成功
- stdout/stderr 完整保存（即使失败），截断时标记
- 产物只从受控工作目录收集，不访问其他路径
- 医学相关字段只做教学分析，不提供诊断结论
- 真实密钥不写入仓库

## 测试与验收

最低验收命令：

```text
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
```

本切片验收项：

- 能为 `ANALYSIS_CONFIRMED` 状态项目生成代码候选
- 生成代码包含数据读取、清洗、分析、可视化逻辑
- 能编辑候选代码
- 能确认候选代码
- 能拒绝候选代码
- 编辑 CONFIRMED 后状态回到 CANDIDATE
- 编辑后关联 ExecutionRun 变 STALE
- 能触发执行已确认代码
- 执行成功保存 stdout、stderr、exit_code、artifacts
- 执行失败状态为 FAILED，不覆盖为成功
- 超时返回 `EXECUTION_TIMEOUT`
- 禁止 import 返回 `EXECUTION_IMPORT_FORBIDDEN`
- 输出过大返回 `EXECUTION_OUTPUT_TOO_LARGE`
- 能下载产物（CSV 和 PNG）
- 能推进项目状态到 `RESULT_CONFIRMED`
- 无已确认代码时执行返回 `CODE_TASK_NOT_EXECUTABLE`
- 无成功执行时完成返回 `PROJECT_NO_SUCCESSFUL_EXECUTION_RUN`
- AnalysisPlan 重新确认时关联 CodeTask 变 STALE
- 后台任务有重试机制
- 无真实 DeepSeek API Key 时本地验收通过
- 前端构建通过
- 后端测试通过
- 数据库迁移通过
- 端到端：SPEC 0004 完成状态 → 生成代码 → 编辑确认 → 执行 → 查看产物 → `RESULT_CONFIRMED`

## 文档回写要求

本切片代码完成后必须回写：

- `dev-docs/README.md`：更新当前切片状态
- `dev-docs/acceptance.md`：记录实际验收命令和结果
- `dev-docs/implementation-plan.md`：勾选任务 7 已完成子项
- 本 SPEC：若实现与文档不同，更新差异和原因
- `dev-docs/dependency-review.md`：记录实际安装的 `scipy`、`scikit-learn`、`matplotlib` 版本
- `dev-docs/changelog.md`：追加 SPEC 0005 变更日志
- 新增决策记录 `0016-start-spec-0005-controlled-python-execution.md`

## 停止条件

第五切片完成的停止条件：

- 代码候选可生成、编辑、确认、拒绝
- 已确认代码可在受控环境中执行
- 受控环境限制生效（时间、内存、输出、import 白名单、网络禁用）
- 执行产物（CSV、PNG）可保存和下载
- 失败状态不被覆盖为成功
- STALE 传播正确（AnalysisPlan → CodeTask → ExecutionRun）
- 项目状态可从 `ANALYSIS_CONFIRMED` 推进到 `EXECUTING`、`RESULT_CONFIRMED`
- 执行失败可重试（`EXECUTION_FAILED → EXECUTING`）
- 受限资源被结构化拒绝
- 基础测试和构建命令有当前证据
- 没有引入本 SPEC 明确排除的功能
- 文档回写完成

完成第五切片后必须暂停，由项目负责人确认后再进入下一切片。

## 后续切片入口

第五切片之后，下一切片建议进入：

```text
大纲与交付物 SPEC（V0.4，SPEC 0006）
```

该下一切片才开始处理：

- 基于已确认执行结果、证据卡片、数据概览生成统一实验大纲
- 大纲每个段落标记来源类型（资料性/实验性）
- 用户确认大纲后才能生成 Word 和 PPT
- Word 和 PPT 从同一份已确认大纲生成
- 资料性结论可追溯到 EvidenceCard
- 实验性结论可追溯到 ExecutionRun
- 交付物版本和追溯索引

## 明确不做

- 不接入真实 DeepSeek API（继续本地规则提供者）
- 不支持 Notebook 风格代码单元
- 不支持任意 import（白名单严格限制）
- 不支持交互式调试
- 不支持 GPU 加速
- 不做代码格式化或 lint
- 不做代码补全
- 不做语法高亮（textarea 即可）
- 不做 L3 完整论文复现
- 不提供医疗诊断或治疗建议
- 不做执行环境容器化（V1 用 subprocess，在线多用户版本再升级为容器隔离）
- 不支持并行执行多个 CodeTask（V1 串行）
- 不支持执行历史对比
- 不支持执行环境自定义依赖安装
