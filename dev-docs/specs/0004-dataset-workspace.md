# 数据集工作区 SPEC

> 切片编号：SPEC 0004  
> 里程碑：V0.3 数据集工作区（数据分析与 Python 执行第一部分）  
> 依据：[project-charter.md](../project-charter.md) §3.1.8 数据工作区、[architecture.md](../architecture.md) §4 数据集与分析核心 owner、[implementation-plan.md](../implementation-plan.md) 任务 6、[0003-sources-and-evidence-workflow.md](0003-sources-and-evidence-workflow.md) 后续切片入口  
> 阶段约束：本切片实现完成后必须暂停；项目负责人确认验收前，不进入下一切片。  
> 前置条件：SPEC 0003 已完成实现、端到端验收并由项目负责人确认收口（commit `ba683db`）。

## Why

SPEC 0003 建立了"资料事实有来源"的追踪链入口，但实验报告的核心结论还必须来自真实数据。当前项目状态可以推进到 `EVIDENCE_CONFIRMED`，但下一切片必须让用户：

- 上传或登记 CSV/Excel 数据集；
- 看到字段、类型、样例、缺失值、重复值和基础质量问题；
- 让系统生成可审阅的清洗方案和分析方案候选；
- 确认或修改分析方案，建立"数据 → 方案 → 执行 → 结果"的追踪链入口。

本切片是 V0.3 里程碑第一部分，只覆盖数据集工作区，不引入 Python 执行（V0.3 第二部分，SPEC 0005 处理）。清洗和分析方案的"执行"推迟到下下切片，本切片只生成方案候选和用户确认状态。

## What Changes

- 新增后端 owner 模块 `server/app/modules/datasets/`：数据集、数据版本、字段概览、质量检查、清洗方案、分析方案。
- 新增后端 owner 模块 `server/app/modules/analysis/`：分析方案候选、用户确认状态、STALE 传播。
- 新增基础设施适配器 `server/app/infrastructure/parsers/dataset_parser.py`：CSV/Excel 解析、字段类型推断、质量检查。
- 新增 LLM 提供者 `server/app/modules/llm/analysis_plan_provider.py`：本地规则生成清洗和分析方案候选。
- 新增 Alembic 迁移 `0004_create_datasets_and_analysis_tables.py`：6 张表 + 索引。
- 新增 14 个 API 端点（datasets 8 个 + analysis 6 个）。
- 新增 Worker handler `PARSE_DATASET` 和 `GENERATE_ANALYSIS_PLAN`。
- 新增前端 `features/datasets/` 和 `features/analysis/` 模块。
- 新增前端 `DatasetWorkspaceView` 和 `AnalysisWorkspaceView` 工作台。
- 项目状态推进：`EVIDENCE_CONFIRMED → DATASET_READY → ANALYSIS_PLANNED → ANALYSIS_CONFIRMED`。
- 安装新依赖：`pandas`、`numpy`、`openpyxl`。
- **不引入**：`scipy`、`scikit-learn`、`matplotlib`（推迟到 SPEC 0005 Python 执行切片）；不接入真实 DeepSeek（继续本地规则提供者）。

## Impact

- 受影响 specs：
  - [0003-sources-and-evidence-workflow.md](0003-sources-and-evidence-workflow.md) 状态机前置：本切片要求 `EVIDENCE_CONFIRMED` 之后才能上传数据集
  - [project-charter.md](../project-charter.md) §3.1.8 数据工作区验收项
- 受影响代码：
  - `server/app/modules/projects/status.py`：状态机已有 `DATASET_READY`、`ANALYSIS_PLANNED`、`ANALYSIS_CONFIRMED`，无需修改枚举
  - `server/app/modules/jobs/status.py`：新增 `JobType.PARSE_DATASET` 和 `JobType.GENERATE_ANALYSIS_PLAN`
  - `server/app/main.py`：注册新路由
  - `server/alembic/env.py`：导入新模型
  - `server/worker/handlers.py`：新增 2 个 handler
  - `server/app/core/config.py`：新增配置项
  - `apps/web/src/app/App.tsx`：注册新路由
  - `apps/web/src/routes/ProjectDetailView.tsx`：加入数据集和分析工作台入口

## ADDED Requirements

### Requirement: Dataset Registration

系统 SHALL 允许用户在 `EVIDENCE_CONFIRMED` 或之后状态的项目中登记数据集，支持两种来源：

1. **CSV/Excel 文件上传**：用户上传本地 CSV 或 Excel（.xlsx）文件，系统保存原始文件到受控工作区 `projects/{project_id}/datasets/{dataset_id}/raw.{ext}`。
2. **公开 URL 登记**：用户登记公开可访问的 CSV/Excel URL，系统通过 HTTP 下载并保存（复用 SPEC 0003 的 HTTP 采集器，但限制 content-type 为 CSV/Excel）。

每次登记创建一个 `Dataset` 记录和首个 `DatasetVersion`（version=1, status=PENDING），并创建 `PARSE_DATASET` 后台任务。

#### Scenario: 用户上传 CSV 文件

- **WHEN** 用户在 `EVIDENCE_CONFIRMED` 状态的项目中上传 CSV 文件
- **THEN** 系统保存文件到受控工作区，创建 Dataset + DatasetVersion(v1, PENDING)，创建 PARSE_DATASET 任务
- **AND** 返回 dataset_id 和 job_id

#### Scenario: 用户上传 Excel 文件

- **WHEN** 用户上传 .xlsx 文件
- **THEN** 系统保存文件并创建解析任务，Excel 文件默认解析第一个工作表

#### Scenario: 项目状态不足

- **WHEN** 项目状态为 `SOURCES_COLLECTED`（未达 `EVIDENCE_CONFIRMED`）
- **THEN** 返回 `PROJECT_EVIDENCE_NOT_CONFIRMED` 错误（400）

#### Scenario: 文件格式不支持

- **WHEN** 用户上传 .txt、.pdf、.docx 文件
- **THEN** 返回 `DATASET_FILE_UNSUPPORTED` 错误（400），仅支持 CSV 和 XLSX

#### Scenario: 文件过大

- **WHEN** 文件大小超过 50 MB
- **THEN** 返回 `DATASET_FILE_TOO_LARGE` 错误（413）

### Requirement: Dataset Parsing and Profiling

系统 SHALL 通过 Worker 异步解析数据集，生成字段概览和质量检查结果。

解析流程：
1. 读取 CSV/Excel 文件（用 pandas + openpyxl）
2. 推断每列的数据类型（整数、浮点、字符串、日期、布尔）
3. 对每列生成字段概览：名称、推断类型、非空数、缺失数、缺失率、唯一值数、样例值（前 5 个）
4. 对数值列生成统计概览：最小值、最大值、均值、中位数、标准差、四分位数
5. 对字符串列生成频次概览：前 10 个高频值和频次
6. 生成数据质量概览：总行数、总列数、完整行数、缺失行数、重复行数、字段质量评分
7. 保存解析结果到 `DatasetVersion.profile_json`
8. 状态推进：DatasetVersion.status = PARSED, Dataset.status = READY

#### Scenario: CSV 解析成功

- **WHEN** Worker 处理 PARSE_DATASET 任务，CSV 文件可正常读取
- **THEN** DatasetVersion.status = PARSED，profile_json 包含字段概览和质量概览
- **AND** 自动创建 GENERATE_ANALYSIS_PLAN 任务（基于已解析数据生成清洗和分析方案候选）

#### Scenario: Excel 解析成功

- **WHEN** Worker 处理 Excel 文件
- **THEN** 默认解析第一个工作表，生成与 CSV 相同结构的 profile

#### Scenario: 数据集为空

- **WHEN** 文件存在但无数据行
- **THEN** DatasetVersion.status = FAILED，error_code = DATASET_EMPTY

#### Scenario: 文件损坏

- **WHEN** CSV/Excel 文件格式损坏无法解析
- **THEN** DatasetVersion.status = FAILED，error_code = DATASET_PARSE_FAILED

### Requirement: Dataset Version Management

系统 SHALL 支持数据集版本管理：

- 每次重新上传或重新采集同一 Dataset，创建新的 DatasetVersion（version 递增）
- 旧版本状态变为 SUPERSEDED
- 新版本状态为 PENDING → PARSED
- 关联的分析方案变为 STALE（需重新生成）
- 原始文件保留在 `datasets/{dataset_id}/v{N}/raw.{ext}`

#### Scenario: 重新上传数据集

- **WHEN** 用户对已存在 Dataset 上传新文件
- **THEN** 创建新 DatasetVersion(v2, PENDING)，旧版本 v1 变为 SUPERSEDED
- **AND** 关联的 AnalysisPlan 变为 STALE

### Requirement: Analysis Plan Generation

系统 SHALL 通过 LLM Gateway 本地规则提供者生成分析方案候选，包含：

1. **清洗方案**（cleaning_plan）：
   - 缺失值处理建议（删除/填充/保留）
   - 重复值处理建议
   - 异常值处理建议（基于 IQR 或 Z-score）
   - 类型转换建议
   - 每条建议包含：字段名、问题类型、建议动作、理由

2. **分析方案**（analysis_plan）：
   - 描述性统计：均值、中位数、标准差、分位数
   - 分组统计：按类别字段分组聚合
   - 相关性分析：数值字段间相关系数
   - 基础统计检验：t 检验、卡方检验（如适用）
   - 可视化建议：直方图、箱线图、散点图、柱状图
   - 每条建议包含：分析类型、目标字段、方法、预期输出、依赖字段

3. **图表方案**（chart_plan）：
   - 推荐图表列表，每项包含：图表类型、标题、数据字段、说明

方案状态：CANDIDATE → CONFIRMED 或 REJECTED。

#### Scenario: 生成分析方案候选

- **WHEN** DatasetVersion 解析成功后，Worker 自动生成分析方案候选
- **THEN** 创建 AnalysisPlan 记录，status=CANDIDATE，包含 cleaning_plan、analysis_plan、chart_plan
- **AND** project.status 推进到 ANALYSIS_PLANNED

#### Scenario: 本地规则提供者

- **WHEN** `ANALYSIS_PLAN_PROVIDER=local_rule`
- **THEN** 使用 `LocalRuleAnalysisPlanProvider`，基于字段类型和缺失率生成确定性方案

#### Scenario: 字段过多

- **WHEN** 数据集字段数超过 50
- **THEN** 只对前 20 个字段生成详细方案，其余标记为"字段过多，需手动选择"

### Requirement: Analysis Plan Confirmation

系统 SHALL 允许用户确认或拒绝分析方案，并支持编辑：

- **编辑**：用户可修改 cleaning_plan、analysis_plan、chart_plan 的具体条目
- **确认**：状态 CANDIDATE → CONFIRMED，记录 confirmed_at
- **拒绝**：状态 CANDIDATE → REJECTED，必须重新生成
- **完成确认**：至少一个 AnalysisPlan 状态为 CONFIRMED 时，可推进 project.status 到 ANALYSIS_CONFIRMED

#### Scenario: 用户确认分析方案

- **WHEN** 用户对 CANDIDATE 状态的 AnalysisPlan 调用 confirm
- **THEN** AnalysisPlan.status = CONFIRMED，记录 confirmed_at
- **AND** 可以调用 complete 推进 project.status 到 ANALYSIS_CONFIRMED

#### Scenario: 编辑已确认方案

- **WHEN** 用户编辑 CONFIRMED 状态的 AnalysisPlan
- **THEN** 状态回到 CANDIDATE，需要重新确认
- **AND** project.status 不自动回退（但下游大纲会标记为 STALE）

#### Scenario: 完成分析方案确认

- **WHEN** 用户调用 complete 且至少一个 AnalysisPlan 为 CONFIRMED
- **THEN** project.status = ANALYSIS_CONFIRMED

#### Scenario: 无已确认方案

- **WHEN** 用户调用 complete 但无 CONFIRMED 状态方案
- **THEN** 返回 `PROJECT_NO_CONFIRMED_ANALYSIS_PLAN` 错误（400）

### Requirement: STALE Propagation

系统 SHALL 在以下情况下将关联产物标记为 STALE：

- Dataset 重新上传新版本时，关联 AnalysisPlan 变为 STALE
- DatasetVersion 被删除时，关联 AnalysisPlan 变为 STALE
- AnalysisPlan 被编辑后回到 CANDIDATE，下游（将来的大纲）变 STALE

#### Scenario: 数据集版本变化导致方案过期

- **WHEN** Dataset 有新版本上传
- **THEN** 关联的 CANDIDATE/CONFIRMED/REJECTED AnalysisPlan 全部变为 STALE
- **AND** 用户需重新生成或确认方案

## MODIFIED Requirements

### Requirement: Project Status Machine

原状态机（SPEC 0003 之后）：

```text
DRAFT → ... → EVIDENCE_CONFIRMED → [停止]
```

修改后：

```text
DRAFT → ... → EVIDENCE_CONFIRMED → DATASET_READY → ANALYSIS_PLANNED → ANALYSIS_CONFIRMED → [后续切片]
```

新增状态推进规则：
- `EVIDENCE_CONFIRMED → DATASET_READY`：至少一个 Dataset 状态为 READY（即有 PARSED 版本）
- `DATASET_READY → ANALYSIS_PLANNED`：自动，当 AnalysisPlan 生成成功
- `ANALYSIS_PLANNED → ANALYSIS_CONFIRMED`：用户确认至少一个 AnalysisPlan

### Requirement: JobType Enum

`server/app/modules/jobs/status.py` 新增：

- `PARSE_DATASET`：解析数据集，生成字段概览和质量检查
- `GENERATE_ANALYSIS_PLAN`：基于已解析数据生成清洗和分析方案候选

## REMOVED Requirements

无。本切片只新增，不删除现有功能。

## 后端核心合同

### Dataset 模块（`server/app/modules/datasets/`）

#### status.py

```python
class DatasetKind(str, Enum):
    FILE = "FILE"          # 本地上传
    URL = "URL"            # 公开 URL 下载

class DatasetStatus(str, Enum):
    PENDING = "PENDING"    # 等待解析
    READY = "READY"        # 至少一个版本 PARSED
    FAILED = "FAILED"      # 所有版本都失败
    DELETED = "DELETED"    # 软删除

class DatasetVersionStatus(str, Enum):
    PENDING = "PENDING"
    PARSING = "PARSING"
    PARSED = "PARSED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"  # 被新版本取代

class DatasetChangeType(str, Enum):
    DATASET_CREATED = "DATASET_CREATED"
    DATASET_PARSED = "DATASET_PARSED"
    DATASET_REUPLOADED = "DATASET_REUPLOADED"
    DATASET_DELETED = "DATASET_DELETED"
    DATASETS_COMPLETED = "DATASETS_COMPLETED"
```

#### contracts.py

```python
class DatasetUploadRequest(BaseModel):
    title: str | None = None
    description: str | None = None

class DatasetUrlRequest(BaseModel):
    url: str
    title: str | None = None
    description: str | None = None

class DatasetResponse(BaseModel):
    id: str
    project_id: str
    dataset_kind: str
    title: str
    description: str | None
    status: str
    error_code: str | None
    error_message: str | None
    created_at: str
    updated_at: str | None
    job_id: str | None = None  # 关联的最新任务

class DatasetListResponse(BaseModel):
    items: list[DatasetResponse]

class DatasetVersionResponse(BaseModel):
    id: str
    dataset_id: str
    project_id: str
    version: int
    status: str
    file_path: str
    file_size_bytes: int
    row_count: int | None
    column_count: int | None
    profile_json: str | None     # JSON 字符串
    error_code: str | None
    error_message: str | None
    created_at: str
    parsed_at: str | None

class DatasetVersionListResponse(BaseModel):
    items: list[DatasetVersionResponse]

class CompleteDatasetsResponse(BaseModel):
    status: str
```

#### models.py

```python
class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    dataset_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=True)
    column_count: Mapped[int] = mapped_column(Integer, nullable=True)
    profile_json: Mapped[str] = mapped_column(Text, nullable=True)  # 长文本
    error_code: Mapped[str] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime]
    parsed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
```

#### service.py 关键方法

```python
def create_file_dataset(db, project_id, title, description, file_content, original_filename) -> tuple[Dataset, str]:
    """上传 CSV/Excel 文件，保存到受控工作区，创建 PARSE_DATASET 任务。"""

def create_url_dataset(db, project_id, req) -> tuple[Dataset, str]:
    """登记公开 CSV/Excel URL，创建 PARSE_DATASET 任务（含下载步骤）。"""

def list_datasets(db, project_id) -> list[Dataset]:
    """列数据集。"""

def get_dataset(db, dataset_id) -> Dataset:
    """查单个。"""

def get_dataset_by_id_and_project(db, project_id, dataset_id) -> Dataset:
    """按项目归属查。"""

def list_dataset_versions(db, dataset_id) -> list[DatasetVersion]:
    """列版本。"""

def get_latest_version(db, dataset_id) -> DatasetVersion:
    """取最新版本。"""

def delete_dataset(db, project_id, dataset_id) -> Dataset:
    """软删除：status=DELETED，关联 AnalysisPlan 变 STALE。"""

def complete_datasets(db, project_id):
    """推进 project.status 到 DATASET_READY。前置：至少一个 Dataset.status=READY。"""

# Worker 调用方法
def mark_dataset_parsing(db, version_id): ...
def mark_dataset_parsed(db, version_id, profile_data, row_count, column_count): ...
def mark_dataset_failed(db, version_id, error_code, error_message): ...
def trigger_analysis_plan_generation(db, dataset_id, version_id) -> str:
    """自动触发生成分析方案候选，返回 job_id。"""
```

### Analysis 模块（`server/app/modules/analysis/`）

#### status.py

```python
class AnalysisPlanStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    STALE = "STALE"

class AnalysisChangeType(str, Enum):
    ANALYSIS_PLAN_GENERATED = "ANALYSIS_PLAN_GENERATED"
    ANALYSIS_PLAN_UPDATED = "ANALYSIS_PLAN_UPDATED"
    ANALYSIS_PLAN_CONFIRMED = "ANALYSIS_PLAN_CONFIRMED"
    ANALYSIS_PLAN_REJECTED = "ANALYSIS_PLAN_REJECTED"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
```

#### contracts.py

```python
class UpdateAnalysisPlanRequest(BaseModel):
    cleaning_plan: str | None = None     # JSON 字符串
    analysis_plan: str | None = None     # JSON 字符串
    chart_plan: str | None = None        # JSON 字符串

class AnalysisPlanResponse(BaseModel):
    id: str
    project_id: str
    dataset_id: str
    dataset_version_id: str
    cleaning_plan: str        # JSON 字符串
    analysis_plan: str        # JSON 字符串
    chart_plan: str           # JSON 字符串
    status: str
    candidate_source: str
    created_at: str
    updated_at: str | None
    confirmed_at: str | None

class AnalysisPlanListResponse(BaseModel):
    items: list[AnalysisPlanResponse]

class CompleteAnalysisResponse(BaseModel):
    status: str
```

#### models.py

```python
class AnalysisPlan(Base):
    __tablename__ = "analysis_plans"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    dataset_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    dataset_version_id: Mapped[str] = mapped_column(String(32), nullable=False)
    cleaning_plan: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_plan: Mapped[str] = mapped_column(Text, nullable=False)
    chart_plan: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
```

#### service.py 关键方法

```python
def generate_analysis_plan(db, project_id, dataset_id) -> str:
    """触发生成分析方案候选，返回 job_id。前置：dataset.status=READY。"""

def list_analysis_plans(db, project_id, dataset_id=None, status=None) -> list[AnalysisPlan]:
    """列方案。"""

def get_analysis_plan(db, plan_id) -> AnalysisPlan: ...

def update_analysis_plan(db, plan_id, req) -> AnalysisPlan:
    """编辑 CANDIDATE 或 STALE 状态方案；CONFIRMED 编辑后回到 CANDIDATE。"""

def confirm_analysis_plan(db, plan_id) -> AnalysisPlan: ...

def reject_analysis_plan(db, plan_id) -> AnalysisPlan: ...

def complete_analysis(db, project_id):
    """推进 project.status 到 ANALYSIS_CONFIRMED。前置：至少一个 CONFIRMED。"""

# Worker 调用方法
def save_analysis_plan_draft(db, dataset_id, dataset_version_id, drafts) -> AnalysisPlan: ...

def _mark_analysis_stale(db, dataset_id) -> int:
    """关联方案变 STALE。"""
```

### 基础设施：数据集解析器

`server/app/infrastructure/parsers/dataset_parser.py`：

```python
@dataclass
class FieldProfile:
    name: str
    inferred_type: str        # int, float, string, datetime, bool
    non_null_count: int
    null_count: int
    null_rate: float
    unique_count: int
    sample_values: list[str]  # 前 5 个
    # 数值字段额外
    min_value: float | None
    max_value: float | None
    mean_value: float | None
    median_value: float | None
    std_value: float | None
    q1: float | None
    q3: float | None
    # 字符串字段额外
    top_values: list[tuple[str, int]]  # 前 10 高频值

@dataclass
class DatasetProfile:
    row_count: int
    column_count: int
    complete_row_count: int       # 无缺失的行数
    incomplete_row_count: int
    duplicate_row_count: int
    field_profiles: list[FieldProfile]
    quality_score: float          # 0-100

@dataclass
class DatasetParseResult:
    profile: DatasetProfile
    raw_dataframe: Any            # pandas DataFrame，用于后续生成方案

def parse_dataset(file_path: str, file_extension: str) -> DatasetParseResult:
    """解析 CSV/Excel，返回 profile 和 DataFrame。
    
    异常：
    - DatasetParseError(code=DATASET_EMPTY)
    - DatasetParseError(code=DATASET_PARSE_FAILED)
    - DatasetParseError(code=DATASET_TOO_LARGE)
    """
```

### LLM 提供者：分析方案

`server/app/modules/llm/analysis_plan_provider.py`：

```python
@dataclass
class AnalysisPlanDraft:
    cleaning_plan: list[dict]     # 每条 {field, issue_type, action, reason}
    analysis_plan: list[dict]    # 每条 {analysis_type, target_fields, method, expected_output}
    chart_plan: list[dict]        # 每条 {chart_type, title, data_fields, description}

class AnalysisPlanDraftProvider(ABC):
    @abstractmethod
    def generate(self, profile: DatasetProfile) -> AnalysisPlanDraft: ...

class LocalRuleAnalysisPlanProvider(AnalysisPlanDraftProvider):
    """基于字段类型和缺失率的本地规则。"""

class FakeAnalysisPlanProvider(AnalysisPlanDraftProvider):
    """确定性测试用提供者。"""
```

`server/app/modules/llm/gateway.py` 新增：

```python
def get_analysis_plan_provider() -> AnalysisPlanDraftProvider: ...
```

## API 合同

### Datasets API（`server/app/api/routers/datasets.py`）

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/api/projects/{project_id}/datasets/upload` | POST | 上传 CSV/Excel 文件（multipart/form-data） |
| `/api/projects/{project_id}/datasets/url` | POST | 登记 CSV/Excel 公开 URL |
| `/api/projects/{project_id}/datasets` | GET | 数据集列表 |
| `/api/projects/{project_id}/datasets/{dataset_id}` | GET | 数据集详情 |
| `/api/projects/{project_id}/datasets/{dataset_id}/versions` | GET | 版本列表 |
| `/api/projects/{project_id}/datasets/{dataset_id}` | DELETE | 软删除数据集 |
| `/api/projects/{project_id}/datasets/{dataset_id}/reupload` | POST | 重新上传（创建新版本） |
| `/api/projects/{project_id}/datasets/complete` | POST | 完成数据集收集 |

### Analysis API（`server/app/api/routers/analysis.py`）

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/api/projects/{project_id}/datasets/{dataset_id}/analysis/generate` | POST | 触发生成分析方案 |
| `/api/projects/{project_id}/analysis` | GET | 方案列表（支持 dataset_id 和 status 过滤） |
| `/api/projects/{project_id}/analysis/{plan_id}` | GET | 方案详情 |
| `/api/projects/{project_id}/analysis/{plan_id}` | PUT | 编辑方案 |
| `/api/projects/{project_id}/analysis/{plan_id}/confirm` | POST | 确认方案 |
| `/api/projects/{project_id}/analysis/{plan_id}/reject` | POST | 拒绝方案 |
| `/api/projects/{project_id}/analysis/complete` | POST | 完成方案确认 |

## 数据库迁移

`server/alembic/versions/0004_create_datasets_and_analysis_tables.py`（revision=`0004`, down_revision=`0003`）：

```text
datasets:
  id (String 32, PK)
  project_id (String 32, not null, index)
  dataset_kind (String 16, not null)
  title (String 500, not null)
  description (Text, null)
  status (String 32, not null)
  error_code (String 64, null)
  error_message (Text, null)
  created_at (DateTime, not null)
  updated_at (DateTime, not null)

dataset_versions:
  id (String 32, PK)
  dataset_id (String 32, not null, index)
  project_id (String 32, not null, index)
  version (Integer, not null)
  status (String 32, not null)
  file_path (String 1000, not null)
  file_size_bytes (Integer, not null)
  row_count (Integer, null)
  column_count (Integer, null)
  profile_json (Text, null)
  error_code (String 64, null)
  error_message (Text, null)
  created_at (DateTime, not null)
  parsed_at (DateTime, null)

analysis_plans:
  id (String 32, PK)
  project_id (String 32, not null, index)
  dataset_id (String 32, not null, index)
  dataset_version_id (String 32, not null)
  cleaning_plan (Text, not null)
  analysis_plan (Text, not null)
  chart_plan (Text, not null)
  status (String 32, not null)
  candidate_source (String 32, not null)
  created_at (DateTime, not null)
  updated_at (DateTime, not null)
  confirmed_at (DateTime, null)

索引：
  ix_datasets_project_id
  ix_dataset_versions_dataset_id
  ix_dataset_versions_project_id
  ix_analysis_plans_project_id
  ix_analysis_plans_dataset_id
```

## LLM 网关边界

- 配置项：`ANALYSIS_PLAN_PROVIDER`，默认 `local_rule`。
- `LocalRuleAnalysisPlanProvider`：基于字段类型和缺失率生成确定性方案，不调用外部 API。
- `FakeAnalysisPlanProvider`：测试用确定性提供者。
- 真实 DeepSeek 适配器**不**在本切片接入业务模块。
- 业务模块只通过 `get_analysis_plan_provider()` 工厂方法获取提供者，不直接实例化。

## 配置

`server/app/core/config.py` 新增：

```python
@property
def dataset_max_size_bytes(self) -> int:
    return int(os.getenv("DATASET_MAX_SIZE_BYTES", str(50 * 1024 * 1024)))

@property
def analysis_plan_provider(self) -> str:
    return os.getenv("ANALYSIS_PLAN_PROVIDER", "local_rule")
```

## 前端工作台范围

### 数据集工作区（`DatasetWorkspaceView`）

展示：
- 项目名称和状态
- 数据集列表（含状态、类型、标题、字段数、行数、错误信息）
- CSV/Excel 文件上传入口
- 公开 URL 登记入口
- 数据集详情（版本列表、字段概览、质量概览、样例数据预览）
- 后台任务状态轮询
- 删除数据集按钮
- 重新上传按钮
- 完成数据集收集按钮

行为：
- 项目状态未达 `EVIDENCE_CONFIRMED` 时禁用登记入口
- 上传后立即创建任务并轮询
- 解析失败展示后端结构化错误
- 字段概览用表格展示（字段名、类型、缺失率、唯一值数、样例）
- 质量概览用指标卡片展示（总行数、缺失行数、重复行数、质量评分）

### 分析方案工作区（`AnalysisWorkspaceView`）

展示：
- 数据集选择下拉
- 分析方案列表（含状态、来源、确认时间）
- 方案详情：清洗方案、分析方案、图表方案三栏
- 编辑、确认、拒绝按钮
- STALE 标记
- 完成分析确认按钮

行为：
- 只能编辑 `CANDIDATE` 或 `STALE` 状态方案
- 只能确认 `CANDIDATE` 状态方案
- 编辑 `CONFIRMED` 方案后状态回到 `CANDIDATE`，显示提示
- 前端不判断分析方案正确性，只展示后端返回的内容

### 通用行为

- 复用 SPEC 0003 的任务轮询模式（`useJob` hook，PENDING/RUNNING 时 2 秒轮询）
- 错误消息复用 `errorMessage(e, fallback)` 函数
- 中文界面，inline styles 与现有视图风格一致

## 错误码

新增错误码：

- `PROJECT_EVIDENCE_NOT_CONFIRMED`：项目证据未确认，无法登记数据集（400）
- `DATASET_URL_REQUIRED`：URL 不能为空（400）
- `DATASET_URL_INVALID`：URL 格式不正确（400）
- `DATASET_URL_SCHEME_UNSUPPORTED`：仅支持 http/https（400）
- `DATASET_URL_NOT_PUBLIC`：URL 指向非公开地址（400）
- `DATASET_FILE_UNSUPPORTED`：仅支持 CSV 和 XLSX（400）
- `DATASET_FILE_EMPTY`：文件不能为空（400）
- `DATASET_FILE_TOO_LARGE`：文件超过 50 MB（413）
- `DATASET_NOT_FOUND`：未找到数据集（404）
- `DATASET_VERSION_NOT_FOUND`：未找到数据集版本（404）
- `DATASET_EMPTY`：数据集无数据行（400）
- `DATASET_PARSE_FAILED`：数据集解析失败（400）
- `DATASET_TOO_LARGE`：数据集超过解析上限（400）
- `DATASET_ACCESS_RESTRICTED`：URL 需要登录或付费（403）
- `DATASET_NOT_PARSED`：数据集未解析，无法生成分析方案（400）
- `ANALYSIS_PLAN_NOT_FOUND`：未找到分析方案（404）
- `ANALYSIS_PLAN_NOT_EDITABLE`：只能修改候选或过期方案（400）
- `ANALYSIS_PLAN_NOT_CONFIRMABLE`：只能确认候选方案（400）
- `PROJECT_NO_READY_DATASET`：没有已就绪的数据集（400）
- `PROJECT_NO_CONFIRMED_ANALYSIS_PLAN`：没有已确认的分析方案（400）

## 安全与边界

- URL 公开性校验复用 SPEC 0003 的 `_validate_public_url`
- CSV/Excel 文件大小上限 50 MB
- 解析时只读取受控工作区内的文件
- Worker 不执行用户提供的代码（只调用 pandas API）
- 文件名清洗复用 SPEC 0002 的 `_safe_upload_filename`
- 不解析宏，不执行 Excel 公式
- 不上传到云端，不外部发送数据内容
- LLM 提供者只接收字段概览（不含原始数据），不泄露用户数据
- 医学相关字段只做教学分析建议，不提供诊断结论

## 测试与验收

最低验收命令：

```text
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
```

本切片验收项：

- 能为 `EVIDENCE_CONFIRMED` 状态项目上传 CSV 文件
- 能为 `EVIDENCE_CONFIRMED` 状态项目上传 Excel 文件
- 能登记公开 CSV/Excel URL
- Worker 能领取 `PARSE_DATASET` 任务并解析 CSV
- Worker 能解析 Excel（默认第一工作表）
- 解析结果包含字段概览和质量概览
- 字段概览包含名称、类型、缺失率、唯一值数、样例值
- 数值字段包含 min/max/mean/median/std/q1/q3
- 字符串字段包含 top_values 高频值
- 空数据集返回 `DATASET_EMPTY`
- 损坏文件返回 `DATASET_PARSE_FAILED`
- 能生成分析方案候选（本地规则）
- 候选方案包含 cleaning_plan、analysis_plan、chart_plan
- 能编辑候选方案
- 能确认候选方案
- 能拒绝候选方案
- 数据集重新上传后关联方案变 `STALE`
- 数据集删除后关联方案变 `STALE`
- 能推进项目状态到 `DATASET_READY`
- 能推进项目状态到 `ANALYSIS_PLANNED`
- 能推进项目状态到 `ANALYSIS_CONFIRMED`
- 后台任务有重试机制
- 无真实 DeepSeek API Key 时本地验收通过
- 前端构建通过
- 后端测试通过
- 数据库迁移通过
- 端到端：SPEC 0003 完成状态 → 上传样例 `胃病数据集_教学实验版.xlsx` → 解析 → 生成方案 → 确认 → `ANALYSIS_CONFIRMED`

## 文档回写要求

本切片代码完成后必须回写：

- `dev-docs/README.md`：更新当前切片状态
- `dev-docs/acceptance.md`：记录实际验收命令和结果
- `dev-docs/implementation-plan.md`：勾选任务 6 已完成子项
- 本 SPEC：若实现与文档不同，更新差异和原因
- `dev-docs/dependency-review.md`：记录实际安装的 `pandas`、`numpy`、`openpyxl` 版本
- `dev-docs/changelog.md`：追加 SPEC 0004 变更日志
- 新增决策记录 `0015-start-spec-0004-dataset-workspace.md`

## 停止条件

第四切片完成的停止条件：

- CSV/Excel 可上传、保存和解析
- 公开 CSV/Excel URL 可登记和下载
- 字段概览和质量概览可生成
- 分析方案候选可生成、编辑和确认
- 数据集版本变化时关联方案变 `STALE`
- 项目状态可从 `EVIDENCE_CONFIRMED` 推进到 `DATASET_READY`、`ANALYSIS_PLANNED`、`ANALYSIS_CONFIRMED`
- 受限资源被结构化拒绝
- 基础测试和构建命令有当前证据
- 没有引入本 SPEC 明确排除的功能
- 文档回写完成

完成第四切片后必须暂停，由项目负责人确认后再进入下一切片。

## 后续切片入口

第四切片之后，下一切片建议进入：

```text
受控 Python 执行 SPEC（V0.3 第二部分，SPEC 0005）
```

该下一切片才开始处理：

- Python 代码任务生成（基于已确认分析方案）
- 受控执行环境（独立进程、限时、限目录、固定依赖）
- 执行日志、stdout/stderr、退出状态保存
- 表格和图表产物保存
- 执行失败状态不覆盖为成功
- 每个结果关联代码版本和数据版本

## 明确不做

- 不引入 `scipy`、`scikit-learn`、`matplotlib`（推迟到 SPEC 0005）
- 不接入真实 DeepSeek（继续本地规则提供者）
- 不执行 Python 代码（只生成方案候选）
- 不生成图表（只生成图表方案）
- 不生成 Word/PPT 大纲
- 不做数据脱敏或匿名化（医学数据敏感性由后续切片处理）
- 不支持数据库直连导入（只支持 CSV/Excel 文件和 URL）
- 不做数据版本对比（diff）
- 不做自动化数据清洗（只生成建议，由用户确认后下一切片执行）
