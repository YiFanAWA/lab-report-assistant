# SPEC 0006：大纲与交付物

> 切片编号：SPEC 0006  
> 里程碑：V0.4 大纲与交付物  
> 依据：[project-charter.md](../project-charter.md) §3.1.10 实验大纲、§3.1.11 Word 与 PPT 生成、§7.6 Word 与 PPT 共用统一大纲、§8.5 V0.4 大纲与交付物、§9.5 大纲与交付物验收标准、[architecture.md](../architecture.md) §6 大纲与交付物核心、§核心合同 Outline/Deliverable、§追踪链、[implementation-plan.md](../implementation-plan.md) 任务 8 和任务 9、[dependency-review.md](../dependency-review.md) §6 python-docx/python-pptx 版本、[0005-controlled-python-execution.md](0005-controlled-python-execution.md) 后续切片入口  
> 阶段约束：本切片 SPEC 文档编写完成后，必须由项目负责人确认，才能进入实现。  
> 前置条件：SPEC 0005 已完成实现、端到端验收并由项目负责人确认收口（commit `f30d500`）。

## Why

实验报告助手的核心价值是"让实验要求、资料证据、数据处理、代码执行、图表结果和最终交付物保持一致并可追溯"。

到 SPEC 0005 为止，项目已经建立了从实验要求 → 资料证据 → 数据集 → 分析方案 → 受控执行 → 执行产物的完整链路。但用户最终需要的是可提交的 Word 实验报告和 PPT 汇报文件。

如果没有统一大纲作为中间锚点，Word 和 PPT 各自从模型临时上下文生成，就会出现以下问题（正是本项目要解决的痛点）：

- Word 报告和 PPT 内容容易不一致；
- 生成过程缺少检查点，错误会一直传递到最终交付物；
- 资料性结论无法追溯到来源；
- 实验性结论无法追溯到执行记录。

本切片引入**统一实验大纲**作为唯一中间锚点，所有 Word 和 PPT 必须从同一份已确认大纲生成。大纲每个章节标记来源类型（要求、证据、数据、执行结果），确保追踪链不断裂。

## What Changes

本切片新增"大纲与交付物核心"owner 层，拥有大纲生成、确认、失效传播和 Word/PPT 生成的业务语义。

新增核心实体：

- `Outline`：统一实验大纲，包含章节列表，每章节标记来源类型和关联 ID。
- `Deliverable`：交付物（Word 或 PPT），关联大纲版本。
- `DeliverableVersion`：交付物版本，记录文件路径、生成状态和追溯索引。

新增状态推进：

- `RESULT_CONFIRMED → OUTLINE_CONFIRMED`（用户确认大纲）
- `OUTLINE_CONFIRMED → GENERATING`（触发 Word/PPT 生成）
- `GENERATING → COMPLETED`（生成完成）

新增 STALE 传播：

- ExecutionRun 重新执行 → Outline STALE
- Outline 编辑 → Deliverable STALE
- Outline 重新确认 → 旧 Deliverable STALE

## Impact

- 受影响 specs：
  - [0005-controlled-python-execution.md](0005-controlled-python-execution.md) 状态机前置：本切片要求 `RESULT_CONFIRMED` 之后才能生成大纲
  - [project-charter.md](../project-charter.md) §3.1.10 实验大纲、§3.1.11 Word 与 PPT 生成、§7.6 Word 与 PPT 共用统一大纲
- 受影响代码：
  - `server/app/modules/projects/status.py`：状态机已有 `OUTLINE_CONFIRMED`、`GENERATING`、`COMPLETED`，无需修改枚举
  - `server/app/modules/execution/service.py`：`complete_execution` 推进到 `RESULT_CONFIRMED`，为本切片提供前置状态
  - `server/app/modules/llm/gateway.py`：新增 `get_outline_provider()` 工厂方法
  - `server/worker/handlers.py`：新增 `handle_generate_outline`、`handle_generate_word`、`handle_generate_ppt` 三个 handler
  - `server/app/main.py`：注册新路由，扩展错误码映射

## ADDED Requirements

### 1. 大纲核心 owner

新增 `server/app/modules/outlines/` 模块作为大纲与交付物核心 owner。

唯一归属：

- 统一实验大纲生成、用户确认、编辑、失效传播
- Word/PPT 生成请求、生成状态、交付物版本
- 交付物与证据/执行记录之间的追溯关系

API、Worker、提示词只能调用本服务，不能直接修改大纲状态或绕过 STALE 传播。

### 2. Outline 实体

```python
class Outline(Base):
    """统一实验大纲实体。

    基于已确认的实验要求、证据卡片、数据概览、分析方案和执行结果生成。
    用户确认后才能进入 Word/PPT 生成阶段。
    """

    __tablename__ = "outlines"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # 大纲内容 JSON：章节列表，每章节含 title、content、source_type、source_ids
    sections_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_source: Mapped[str] = mapped_column(String(32), nullable=False)
    code_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

大纲状态机：

```text
CANDIDATE → CONFIRMED / REJECTED
CONFIRMED 编辑 → CANDIDATE（version 递增）
ExecutionRun 重新执行 → STALE
```

### 3. 大纲章节结构

大纲 `sections_json` 是一个 JSON 数组，每个章节包含：

```json
{
  "id": "sec_001",
  "title": "实验目的",
  "content": "本实验旨在分析胃病数据...",
  "source_type": "REQUIREMENT",
  "source_ids": ["req_plan_001"]
}
```

`source_type` 取值：

- `REQUIREMENT`：来自实验要求和任务单
- `EVIDENCE`：来自证据卡片
- `DATASET`：来自数据集字段概览
- `ANALYSIS`：来自分析方案
- `EXECUTION`：来自执行结果（stdout、表格、图表）
- `SUMMARY`：综合总结（由大纲生成器归纳）

`source_ids` 是对应实体的 ID 列表，用于追溯。

### 4. 大纲章节模板

本地规则提供者 `LocalRuleOutlineProvider` 按以下模板生成章节：

1. **实验目的**（source_type=REQUIREMENT）：从已确认任务单提取
2. **实验背景**（source_type=EVIDENCE）：从已确认证据卡片提取
3. **数据描述**（source_type=DATASET）：从数据集字段概览提取
4. **分析方案**（source_type=ANALYSIS）：从已确认分析方案提取
5. **实验结果**（source_type=EXECUTION）：从执行结果（stdout、表格、图表）提取
6. **结论与讨论**（source_type=SUMMARY）：由生成器归纳

PPT 章节模板（从大纲提炼）：

1. 课题与问题
2. 方法与数据
3. 关键图表（引用执行产物）
4. 主要发现
5. 总结

### 5. Deliverable 实体

```python
class Deliverable(Base):
    """交付物实体（Word 或 PPT）。

    从同一份已确认大纲生成，不直接从模型临时上下文生成。
    """

    __tablename__ = "deliverables"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    outline_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    deliverable_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # WORD 或 PPT
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
```

交付物状态机：

```text
PENDING → RUNNING → SUCCEEDED / FAILED
Outline 编辑 → STALE
Outline 重新确认 → 旧 Deliverable STALE
```

### 6. DeliverableVersion 实体

```python
class DeliverableVersion(Base):
    """交付物版本实体。

    每次生成创建一个新版本，旧版本保留不删除。
    记录文件路径、生成状态和追溯索引。
    """

    __tablename__ = "deliverable_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    deliverable_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
```

### 7. 大纲生成触发

```python
def generate_outline(db: Session, project_id: str) -> str:
    """触发生成大纲候选，返回 job_id。

    前置条件：
    - project.status == RESULT_CONFIRMED
    - 至少一个 ExecutionRun.status == SUCCEEDED
    """
```

- API `POST /api/projects/{project_id}/outline/generate` 触发
- Worker `handle_generate_outline` 调用 `LocalRuleOutlineProvider` 生成
- 生成后 status=CANDIDATE，推进 project.status 到 `OUTLINE_PLANNED`（新增中间状态？不，保持 RESULT_CONFIRMED 直到确认）

### 8. 大纲确认

```python
def confirm_outline(db: Session, project_id: str,
                     outline_id: str) -> Outline:
    """确认候选大纲，状态变为 CONFIRMED。

    推进 project.status 到 OUTLINE_CONFIRMED。
    重新确认时，旧 Deliverable 全部变 STALE。
    """
```

### 9. Word 生成

```python
def generate_word(db: Session, project_id: str,
                   outline_id: str) -> str:
    """触发 Word 生成，返回 job_id。

    前置条件：outline.status == CONFIRMED。
    """
```

- API `POST /api/projects/{project_id}/outline/{outline_id}/word/generate` 触发
- Worker `handle_generate_word` 调用 `WordRenderer` 生成 `.docx` 文件
- 文件保存到 `project_data_root / project_id / "deliverables" / deliverable_id / "word_v{version}.docx"`
- 生成后推进 project.status 到 `GENERATING`，完成后推进到 `COMPLETED`

### 10. PPT 生成

```python
def generate_ppt(db: Session, project_id: str,
                  outline_id: str) -> str:
    """触发 PPT 生成，返回 job_id。

    前置条件：outline.status == CONFIRMED。
    """
```

- API `POST /api/projects/{project_id}/outline/{outline_id}/ppt/generate` 触发
- Worker `handle_generate_ppt` 调用 `PptRenderer` 生成 `.pptx` 文件
- 文件保存到 `project_data_root / project_id / "deliverables" / deliverable_id / "ppt_v{version}.pptx"`

### 11. Word 渲染器

新增 `server/app/infrastructure/renderers/word_renderer.py`：

```python
class WordRenderer:
    """Word 文档渲染器。

    从已确认大纲生成 .docx 文件。
    使用 python-docx 库，模板驱动。
    """

    def render(self, outline: dict, output_path: str,
               execution_artifacts: list[dict]) -> str:
        """渲染 Word 文档。

        参数：
        - outline: 已确认大纲的 sections 列表
        - output_path: 输出文件路径
        - execution_artifacts: 执行产物列表（CSV 表格和 PNG 图表）

        返回：生成的文件路径
        """
```

Word 文档结构：

- 封面（标题、课题、日期）
- 实验目的
- 实验背景
- 数据描述（含表格）
- 分析方案
- 实验结果（含图表和表格）
- 结论与讨论
- 附录（代码、原始数据引用）

### 12. PPT 渲染器

新增 `server/app/infrastructure/renderers/ppt_renderer.py`：

```python
class PptRenderer:
    """PPT 文档渲染器。

    从同一份已确认大纲提炼生成 .pptx 文件。
    使用 python-pptx 库，母版驱动。
    """

    def render(self, outline: dict, output_path: str,
               execution_artifacts: list[dict]) -> str:
        """渲染 PPT 文档。

        PPT 从大纲提炼关键内容，不包含全部细节。
        """
```

PPT 结构（5-8 页）：

1. 标题页（课题、学生信息）
2. 课题与问题
3. 方法与数据
4. 关键图表（引用执行产物中的 PNG）
5. 主要发现
6. 总结

### 13. 交付物下载

```python
def get_deliverable_file_path(db: Session, project_id: str,
                                deliverable_id: str,
                                version_id: str) -> tuple[Path, str, str]:
    """返回交付物下载信息：(绝对路径, 文件名, media_type)。

    校验归属和路径不越界。
    """
```

- API `GET /api/projects/{project_id}/deliverables/{deliverable_id}/versions/{version_id}/download`
- 返回 FileResponse，media_type 为 `application/vnd.openxmlformats-officedocument.wordprocessingml.document`（Word）或 `application/vnd.openxmlformats-officedocument.presentationml.presentation`（PPT）

### 14. STALE 传播

#### 14.1 ExecutionRun 重新执行 → Outline STALE

在 `execution_service.execute_code_task` 中新增传播：

```python
# STALE 传播：重新执行 → 关联 Outline 变 STALE
from app.modules.outlines import service as outline_service
outline_service.mark_outlines_stale(db, project_id)
```

#### 14.2 Outline 编辑 → Deliverable STALE

```python
def update_outline(db: Session, project_id: str,
                    outline_id: str, req: UpdateOutlineRequest) -> Outline:
    """编辑大纲。

    - CANDIDATE 或 CONFIRMED 可编辑
    - CONFIRMED 编辑后回到 CANDIDATE，version 递增
    - 编辑后关联 Deliverable 全部变 STALE
    """
```

#### 14.3 Outline 重新确认 → 旧 Deliverable STALE

在 `confirm_outline` 中：重新确认时，旧 Deliverable 全部变 STALE（首次确认时无 Deliverable，传播为空操作）。

### 15. 项目状态推进

```text
RESULT_CONFIRMED
  → 生成大纲候选（保持 RESULT_CONFIRMED）
  → 确认大纲 → OUTLINE_CONFIRMED
  → 触发 Word/PPT 生成 → GENERATING
  → 生成完成 → COMPLETED
```

失败可重试：

```text
GENERATING → DELIVERABLE_FAILED（新增中间状态？不，保持 GENERATING，单个 DeliverableVersion 标记 FAILED）
```

设计决策：项目级状态不新增 `DELIVERABLE_FAILED`，因为 Word 和 PPT 是独立生成的，一个失败不影响另一个。单个 `DeliverableVersion.status=FAILED` 已足够记录失败，用户可重新触发该类型生成。项目状态在至少一个 DeliverableVersion SUCCEEDED 后保持 `GENERATING`，在用户主动确认完成后推进到 `COMPLETED`。

### 16. 大纲提供者

新增 `server/app/modules/llm/outline_provider.py`：

```python
class OutlineDraftProvider(ABC):
    """大纲候选提供者抽象基类。"""

    @abstractmethod
    def generate(self, context: dict) -> OutlineDraft:
        """基于上下文生成大纲候选。"""
        ...

    @abstractmethod
    def source_label(self) -> str:
        ...


class LocalRuleOutlineProvider(OutlineDraftProvider):
    """本地规则提供者。

    基于已确认的任务单、证据卡片、数据概览、分析方案和执行结果
    拼装大纲章节，不调用外部 API。

    设计决策（用户确认）：AnalysisPlan 阶段为字段截断唯一截断点，
    Outline 生成时直接透传已截断字段内容，提供者不做二次截断。
    """


class FakeOutlineProvider(OutlineDraftProvider):
    """确定性测试用提供者，返回固定大纲。"""
```

### 17. 上下文聚合

大纲生成需要从多个 owner 聚合上下文：

```python
def _gather_outline_context(db: Session, project_id: str) -> dict:
    """聚合大纲生成所需的上下文。

    从各 owner 服务查询已确认内容：
    - requirements: 已确认任务单
    - sources: 已确认证据卡片
    - datasets: 数据集字段概览
    - analysis: 已确认分析方案
    - execution: 成功的执行记录和产物
    """
```

### 18. 完成交付

```python
def complete_project(db: Session, project_id: str):
    """推进 project.status 到 COMPLETED。

    前置条件：至少一个 Word DeliverableVersion 和一个 PPT DeliverableVersion 为 SUCCEEDED。
    """
```

- API `POST /api/projects/{project_id}/complete`

## MODIFIED Requirements

### 1. execution 模块 STALE 传播扩展

`execution_service.execute_code_task` 新增大纲 STALE 传播：触发执行时，关联 Outline 全部变 STALE。

### 2. gateway 新增工厂方法

```python
def get_outline_provider():
    """返回当前激活的大纲候选提供者。"""
    provider_name = getattr(settings, "outline_provider", "local_rule")
    if provider_name == "local_rule" or provider_name is None:
        from app.modules.llm.outline_provider import LocalRuleOutlineProvider
        return LocalRuleOutlineProvider()
    if provider_name == "fake":
        from app.modules.llm.outline_provider import FakeOutlineProvider
        return FakeOutlineProvider()
    raise AppError(
        code="OUTLINE_PROVIDER_UNAVAILABLE",
        message=f"未知的纲要提供者：{provider_name}",
    )
```

### 3. config 新增配置项

```python
@property
def outline_provider(self) -> str:
    return os.getenv("OUTLINE_PROVIDER", "local_rule")

@property
def word_template_path(self) -> str:
    """Word 模板路径（可选，留空使用默认模板）。"""
    return os.getenv("WORD_TEMPLATE_PATH", "")

@property
def ppt_template_path(self) -> str:
    """PPT 母版路径（可选，留空使用默认母版）。"""
    return os.getenv("PPT_TEMPLATE_PATH", "")

@property
def deliverable_max_size_bytes(self) -> int:
    """交付物文件大小上限（默认 50MB）。"""
    raw = os.getenv("DELIVERABLE_MAX_SIZE_BYTES", str(50 * 1024 * 1024))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 50 * 1024 * 1024
```

### 4. jobs/status.py 新增 JobType

```python
class JobType(str, Enum):
    # ... 已有 ...
    GENERATE_OUTLINE = "GENERATE_OUTLINE"
    GENERATE_WORD = "GENERATE_WORD"
    GENERATE_PPT = "GENERATE_PPT"
```

## REMOVED Requirements

无。本切片纯新增，不删除已有功能。

## 后端核心合同

### Pydantic 合同

```python
# contracts.py

class OutlineSection(BaseModel):
    """大纲章节。"""
    id: str
    title: str
    content: str
    source_type: str  # REQUIREMENT / EVIDENCE / DATASET / ANALYSIS / EXECUTION / SUMMARY
    source_ids: list[str] = []


class UpdateOutlineRequest(BaseModel):
    """编辑大纲请求。"""
    sections: list[OutlineSection]


class OutlineResponse(BaseModel):
    """大纲响应。"""
    id: str
    project_id: str
    sections: list[OutlineSection]
    status: str
    candidate_source: str
    version: int
    created_at: str
    updated_at: str | None = None
    confirmed_at: str | None = None


class OutlineListResponse(BaseModel):
    items: list[OutlineResponse]


class DeliverableResponse(BaseModel):
    """交付物响应。"""
    id: str
    project_id: str
    outline_id: str
    deliverable_type: str  # WORD / PPT
    status: str
    created_at: str
    updated_at: str | None = None


class DeliverableListResponse(BaseModel):
    items: list[DeliverableResponse]


class DeliverableVersionResponse(BaseModel):
    """交付物版本响应。"""
    id: str
    deliverable_id: str
    version: int
    status: str
    file_path: str | None = None
    file_size_bytes: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    created_at: str


class DeliverableVersionListResponse(BaseModel):
    items: list[DeliverableVersionResponse]


class GenerateOutlineResponse(BaseModel):
    job_id: str


class GenerateDeliverableResponse(BaseModel):
    job_id: str
    deliverable_id: str


class CompleteProjectResponse(BaseModel):
    status: str
```

### 枚举

```python
# status.py

class OutlineStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    STALE = "STALE"


class DeliverableStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    STALE = "STALE"


class DeliverableType(str, Enum):
    WORD = "WORD"
    PPT = "PPT"


class DeliverableVersionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class OutlineChangeType(str, Enum):
    OUTLINE_GENERATED = "OUTLINE_GENERATED"
    OUTLINE_UPDATED = "OUTLINE_UPDATED"
    OUTLINE_CONFIRMED = "OUTLINE_CONFIRMED"
    OUTLINE_REJECTED = "OUTLINE_REJECTED"


class DeliverableChangeType(str, Enum):
    WORD_GENERATED = "WORD_GENERATED"
    PPT_GENERATED = "PPT_GENERATED"
    DELIVERABLE_SUCCEEDED = "DELIVERABLE_SUCCEEDED"
    DELIVERABLE_FAILED = "DELIVERABLE_FAILED"
    PROJECT_COMPLETED = "PROJECT_COMPLETED"
```

## API 合同

| 路由 | 方法 | 用途 |
| --- | --- | --- |
| `/api/projects/{project_id}/outline/generate` | POST | 触发生成大纲候选 |
| `/api/projects/{project_id}/outline` | GET | 大纲列表（支持 status 过滤） |
| `/api/projects/{project_id}/outline/{outline_id}` | GET | 大纲详情 |
| `/api/projects/{project_id}/outline/{outline_id}` | PUT | 编辑大纲（sections 字段） |
| `/api/projects/{project_id}/outline/{outline_id}/confirm` | POST | 确认大纲 |
| `/api/projects/{project_id}/outline/{outline_id}/reject` | POST | 拒绝大纲 |
| `/api/projects/{project_id}/outline/{outline_id}/word/generate` | POST | 触发 Word 生成 |
| `/api/projects/{project_id}/outline/{outline_id}/ppt/generate` | POST | 触发 PPT 生成 |
| `/api/projects/{project_id}/deliverables` | GET | 交付物列表（含版本） |
| `/api/projects/{project_id}/deliverables/{deliverable_id}/versions` | GET | 交付物版本列表 |
| `/api/projects/{project_id}/deliverables/{deliverable_id}/versions/{version_id}/download` | GET | 下载交付物文件 |
| `/api/projects/{project_id}/complete` | POST | 完成项目 |

## 数据库迁移

新增 Alembic 迁移 `0006_create_outline_and_deliverable_tables.py`，创建 3 张表：

- `outlines`：大纲表
- `deliverables`：交付物表
- `deliverable_versions`：交付物版本表

索引：

- `ix_outlines_project_id`
- `ix_deliverables_project_id`
- `ix_deliverables_outline_id`
- `ix_deliverable_versions_deliverable_id`
- `ix_deliverable_versions_project_id`

Revision ID: 0006, Revises: 0005。

## LLM 网关边界

- 配置项：`OUTLINE_PROVIDER`，默认 `local_rule`。
- `LocalRuleOutlineProvider`：基于已确认的任务单、证据卡片、数据概览、分析方案和执行结果拼装大纲章节，不调用外部 API。
- `FakeOutlineProvider`：测试用确定性提供者。
- 真实 DeepSeek 适配器**不**在本切片接入业务模块。
- 业务模块只通过 `get_outline_provider()` 工厂方法获取提供者，不直接实例化。

## 配置

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `OUTLINE_PROVIDER` | `local_rule` | 大纲提供者 |
| `WORD_TEMPLATE_PATH` | `""` | Word 模板路径（空使用默认） |
| `PPT_TEMPLATE_PATH` | `""` | PPT 母版路径（空使用默认） |
| `DELIVERABLE_MAX_SIZE_BYTES` | `52428800`（50MB） | 交付物文件大小上限 |

## 前端工作台范围

新增页面（`apps/web/src/`）：

1. **大纲工作区**（`OutlineWorkspace.tsx`）
   - 展示候选大纲章节列表
   - 编辑章节内容（textarea）
   - 确认/拒绝按钮
   - 触发生成按钮

2. **交付物工作区**（`DeliverableWorkspace.tsx`）
   - 展示 Word 和 PPT 交付物卡片
   - 每个卡片显示版本列表和状态
   - 触发生成按钮（Word 和 PPT 独立）
   - 下载按钮
   - 完成项目按钮

前端约束：

- 前端不得判断大纲质量、内容真实性或交付物完整性
- 前端只展示状态、收集输入、触发命令、展示结果
- 交付物状态轮询使用 TanStack Query

## 错误码

新增错误码：

| 错误码 | HTTP 状态 | 说明 |
| --- | --- | --- |
| `OUTLINE_NOT_FOUND` | 404 | 大纲不存在 |
| `OUTLINE_NOT_CONFIRMABLE` | 400 | 非 CANDIDATE 状态无法确认 |
| `OUTLINE_NOT_EDITABLE` | 400 | STALE/REJECTED 状态无法编辑 |
| `OUTLINE_NOT_GENERATABLE` | 400 | 项目状态未达 RESULT_CONFIRMED |
| `DELIVERABLE_NOT_FOUND` | 404 | 交付物不存在 |
| `DELIVERABLE_VERSION_NOT_FOUND` | 404 | 交付物版本不存在 |
| `DELIVERABLE_NOT_GENERATABLE` | 400 | 大纲未确认 |
| `PROJECT_NO_SUCCESSFUL_DELIVERABLE` | 400 | 无成功的 Word 和 PPT 交付物 |
| `OUTLINE_PROVIDER_UNAVAILABLE` | 400 | 未知的大纲提供者 |

## 安全与边界

- 交付物文件路径必须校验不越界（防穿越）
- 交付物文件大小有上界（50MB）
- Word/PPT 生成是长任务，必须通过 Worker 异步执行
- 生成失败不覆盖已有成功版本
- 旧版本保留不删除，可追溯

## 测试与验收

最低验收命令：

```text
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
```

本切片验收项：

- 能为 `RESULT_CONFIRMED` 状态项目生成大纲候选
- 大纲包含 6 个章节（目的、背景、数据、方案、结果、结论）
- 每个章节标记来源类型和关联 ID
- 能编辑候选大纲
- 能确认候选大纲
- 能拒绝候选大纲
- 编辑 CONFIRMED 大纲后状态回到 CANDIDATE
- 编辑后关联 Deliverable 变 STALE
- 能触发 Word 生成
- 能触发 PPT 生成
- Word 生成成功后可下载 `.docx` 文件
- PPT 生成成功后可下载 `.pptx` 文件
- Word 和 PPT 来自同一份已确认大纲
- 无已确认大纲时生成返回 `DELIVERABLE_NOT_GENERATABLE`
- 无成功交付物时完成返回 `PROJECT_NO_SUCCESSFUL_DELIVERABLE`
- ExecutionRun 重新执行时关联 Outline 变 STALE
- 后台任务有重试机制
- 无真实 DeepSeek API Key 时本地验收通过
- 前端构建通过
- 后端测试通过
- 数据库迁移通过
- 端到端：SPEC 0005 完成状态 → 生成大纲 → 编辑确认 → 生成 Word → 生成 PPT → 下载 → `COMPLETED`

## 文档回写要求

本切片代码完成后必须回写：

- `dev-docs/README.md`：更新当前切片状态
- `dev-docs/acceptance.md`：记录实际验收命令和结果
- `dev-docs/implementation-plan.md`：勾选任务 8 和任务 9 已完成子项
- 本 SPEC：若实现与文档不同，更新差异和原因
- `dev-docs/dependency-review.md`：记录实际安装的 `python-docx`、`python-pptx` 版本
- `dev-docs/changelog.md`：追加 SPEC 0006 变更日志
- 新增决策记录 `0017-start-spec-0006-outline-and-deliverables.md`

## 停止条件

本切片完成后：

- 项目从创建到 Word/PPT 下载的完整闭环跑通
- 关键步骤都有状态、错误提示和重新运行能力
- 来源、数据、代码、图表和结论能够关联
- Word 和 PPT 来自同一份已确认大纲
- 资料性结论可追溯到来源
- 实验性结论可追溯到执行记录
- 受限资源被结构化拒绝
- 基础测试和构建命令有当前证据
- 没有引入本 SPEC 明确排除的功能
- 文档回写完成

满足以上条件后，项目负责人确认收口，项目进入 V1.0 完整闭环验收阶段。

## 后续切片入口

本切片完成后，V0.4 里程碑结束。后续 V1.0 验收切片可能包括：

- 端到端"胃病数据分析"完整闭环验收
- 真实 DeepSeek API 接入（替换本地规则提供者）
- 前端交互打磨和可视化点击验收
- 部署文档和用户文档

## 明确不做

- 不做在线多用户协作
- 不做论文投稿级排版
- 不做 Word 模板完全兼容（V1 只支持默认模板或简单模板）
- 不做 PPT 动画和复杂排版
- 不做交付物内容自动润色（用户审阅后自行修改）
- 不做交付物版本对比工具
- 不把医学教学数据分析结论包装为临床结论
- 不在未确认大纲的情况下生成 Word 或 PPT
- 不让 Word 和 PPT 各自从模型临时上下文生成
