# 公开资料与证据工作流 SPEC

> 状态：已完成实现并经端到端验收，待项目负责人确认收口
> 切片编号：SPEC 0003  
> 里程碑：V0.2 公开资料与证据工作流  
> 依据：[project-charter.md](../../../dev-docs/project-charter.md)、[architecture.md](../../../dev-docs/architecture.md)、[tech-stack.md](../../../dev-docs/tech-stack.md)、[implementation-plan.md](../../../dev-docs/implementation-plan.md) 任务 5、[specs/0002-requirement-input-and-task-plan.md](../../../dev-docs/specs/0002-requirement-input-and-task-plan.md)  
> 阶段约束：本切片实现完成后必须暂停；项目负责人确认验收前，不进入下一切片。

## Why

SPEC 0002 已完成实验要求输入与结构化任务单，项目状态可推进到 `REQUIREMENT_CONFIRMED`。下一切片需要解决：让用户为已确认要求的实验项目登记公开 URL 和 PDF 辅助文件，通过独立 Worker 异步完成采集与解析，生成可审阅、可确认的证据卡片，并保存完整的来源位置和采集状态，建立"资料事实有来源"的核心追踪链入口。

本切片是 V0.2 里程碑，是后续数据分析和交付物可追溯性的前提。

## What Changes

### 新增能力

- **来源登记**：支持公开 URL（HTML 页面或 PDF 直链）登记和本地 PDF 文件上传。
- **后台任务**：引入最小后台任务表 `background_jobs` 和独立 Worker 进程，承担 URL 采集、文档解析和证据卡片生成。
- **来源采集**：Worker 通过 HTTP 下载公开 URL 内容，保存原始文件到项目受控工作区。
- **文档解析**：Worker 解析 HTML 网页（beautifulsoup4）和 PDF 文件（pypdf），提取正文和基础元数据。
- **证据卡片候选**：通过 LLM Gateway 本地规则提供者从已解析文档生成结构化证据卡片候选。
- **证据卡片确认**：用户可确认、编辑或拒绝证据卡片候选。
- **状态推进**：项目状态从 `REQUIREMENT_CONFIRMED` 推进到 `SOURCES_COLLECTED` 和 `EVIDENCE_CONFIRMED`。
- **STALE 传播**：来源重新采集或删除时，关联证据卡片变为 `STALE`。
- **结构化拒绝**：非公开 URL、受限资源（登录/验证码/付费墙）、动态网页和不支持格式返回结构化错误。

### 明确不做

- 不绕过登录、验证码、付费墙或访问控制。
- 不自动登录知网等受限平台。
- 不使用 Playwright 渲染动态网页（推迟到后续切片）。
- 不接入真实 DeepSeek API（继续使用本地规则提供者）。
- 不支持 Word、TXT、CSV、Excel 文件上传（仅 PDF）。
- 不上传或解析样例数据集（数据集工作区属于下一切片）。
- 不生成数据清洗方案或分析方案。
- 不执行 Python 代码。
- 不生成 Word 或 PPT 交付物。
- 不做 OCR 或扫描件解析。
- 不做 L3 完整论文复现。
- 不把 L1/L2 方法参考包装成完整论文复现。
- 不提供医疗诊断或治疗建议。

### **BREAKING** 变更

无。本切片只新增模块、表和路由，不修改已有合同。

## Impact

- **影响 SPEC**：SPEC 0002 实验要求输入与结构化任务单（无修改，但本切片依赖其 `REQUIREMENT_CONFIRMED` 状态）。
- **影响代码**：
  - 新增 `server/app/modules/sources/`（来源与证据核心 owner）：`contracts.py`、`models.py`、`service.py`、`status.py`
  - 新增 `server/app/modules/jobs/`（后台任务核心 owner）：`contracts.py`、`models.py`、`service.py`、`status.py`
  - 新增 `server/app/infrastructure/fetchers/http_fetcher.py`（HTTP 采集适配器）
  - 新增 `server/app/infrastructure/parsers/html_parser.py`、`pdf_parser.py`（文档解析适配器）
  - 新增 `server/app/modules/llm/evidence_card_provider.py`（证据卡片本地规则提供者）
  - 新增 `server/worker/`（独立 Worker 进程）：`__init__.py`、`main.py`、`handlers.py`
  - 修改 `server/app/main.py`（注册新路由、新错误码映射）
  - 修改 `server/app/core/config.py`（新增配置项）
  - 新增 `server/app/api/routers/sources.py`、`evidence.py`、`jobs.py`
  - 新增 Alembic 迁移：`sources`、`parsed_documents`、`evidence_cards`、`background_jobs` 表
  - 新增前端 `apps/web/src/features/sources/`、`evidence/`、`jobs/`
  - 新增前端 `apps/web/src/routes/SourcesWorkspaceView.tsx`、`EvidenceWorkspaceView.tsx`
- **影响依赖**：新增 `pypdf`、`beautifulsoup4`、`lxml`（beautifulsoup4 解析器）作为运行时依赖；`httpx` 已在依赖复核中但未实际安装，本切片安装。
- **影响文档**：完成后回写 `dev-docs/README.md`、`dev-docs/acceptance.md`、`dev-docs/implementation-plan.md`、`dev-docs/dependency-review.md` 和本 SPEC。

## ADDED Requirements

### Requirement: 来源登记

系统 SHALL 支持为处于 `REQUIREMENT_CONFIRMED` 或之后状态的实验项目登记公开 URL 和本地 PDF 文件。

#### Scenario: 登记公开 URL
- **WHEN** 用户提交一个公开 URL（如 `https://example.com/article.html` 或 `https://example.com/paper.pdf`）
- **AND** 项目状态为 `REQUIREMENT_CONFIRMED` 或之后
- **THEN** 系统创建一条 `Source` 记录，`source_kind` 为 `URL`，`status` 为 `PENDING`
- **AND** 创建一个 `BackgroundJob`，`job_type` 为 `FETCH_URL`，`status` 为 `PENDING`
- **AND** 返回来源 ID 和任务 ID，前端可轮询任务状态

#### Scenario: 上传本地 PDF 文件
- **WHEN** 用户上传一个 PDF 文件（Content-Type 为 `application/pdf` 或扩展名为 `.pdf`）
- **THEN** 系统将文件保存到项目受控工作区 `sources/{source_id}/raw.pdf`
- **AND** 创建一条 `Source` 记录，`source_kind` 为 `FILE`，`status` 为 `PENDING`
- **AND** 创建一个 `BackgroundJob`，`job_type` 为 `PARSE_DOCUMENT`

#### Scenario: 拒绝非公开 URL
- **WHEN** 用户提交非公开 URL（如 `localhost`、`127.0.0.1`、`192.168.*`、`10.*`、`172.16-31.*`、`file://`、`ftp://`）
- **THEN** 系统返回 `SOURCE_URL_NOT_PUBLIC` 结构化错误，不创建来源

#### Scenario: 拒绝不支持协议
- **WHEN** 用户提交非 `http` 或 `https` 协议的 URL
- **THEN** 系统返回 `SOURCE_URL_SCHEME_UNSUPPORTED` 结构化错误

#### Scenario: 拒绝过大文件
- **WHEN** 用户上传的 PDF 文件超过 10 MB
- **THEN** 系统返回 `SOURCE_FILE_TOO_LARGE` 结构化错误，HTTP 状态码 413

#### Scenario: 项目状态不足
- **WHEN** 项目状态不是 `REQUIREMENT_CONFIRMED` 或之后状态
- **THEN** 系统返回 `PROJECT_REQUIREMENT_NOT_CONFIRMED` 结构化错误

### Requirement: 后台任务

系统 SHALL 提供最小后台任务表和独立 Worker 进程，承担 URL 采集、文档解析和证据卡片生成。

#### Scenario: 创建后台任务
- **WHEN** 用户登记 URL 或上传文件或触发生成证据卡片
- **THEN** 系统创建 `BackgroundJob` 记录，`status` 为 `PENDING`，`retry_count` 为 0

#### Scenario: Worker 领取任务
- **WHEN** Worker 进程轮询发现有 `PENDING` 任务
- **THEN** Worker 原子性地将任务状态改为 `RUNNING`，记录 `started_at`
- **AND** 根据 `job_type` 调用对应处理器
- **AND** 成功时更新为 `SUCCEEDED`，记录 `finished_at` 和 `output_json`
- **AND** 失败时更新为 `FAILED`，记录 `error_code`、`error_message` 和 `finished_at`

#### Scenario: 任务失败重试
- **WHEN** 任务失败且 `retry_count < max_retries`（默认 2）
- **THEN** 任务状态变为 `PENDING`，`retry_count` 递增，`next_retry_at` 设为当前时间加退避间隔

#### Scenario: 任务达到最大重试
- **WHEN** 任务失败且 `retry_count >= max_retries`
- **THEN** 任务状态变为 `FAILED`，不再重试

#### Scenario: Worker 不拥有业务语义
- **WHEN** Worker 执行任务
- **THEN** Worker 只调用核心服务（sources/evidence）的方法并写回状态
- **AND** Worker 不直接判断 L0-L3、不判断实验结果真实性、不修改项目状态机（项目状态由核心服务在用户确认时推进）

### Requirement: 来源采集

系统 SHALL 通过 HTTP 下载公开 URL 内容，并保存原始文件到项目受控工作区。

#### Scenario: 成功采集 HTML 页面
- **WHEN** Worker 领取 `FETCH_URL` 任务
- **AND** URL 返回 200 且 Content-Type 为 `text/html`
- **THEN** Worker 保存原始 HTML 到 `sources/{source_id}/raw.html`
- **AND** 更新 `Source.status` 为 `FETCHED`，记录 `content_type`、`content_hash`、`fetched_at`
- **AND** 自动创建 `PARSE_DOCUMENT` 任务

#### Scenario: 成功采集 PDF 文件
- **WHEN** URL 返回 200 且 Content-Type 为 `application/pdf`
- **THEN** Worker 保存原始 PDF 到 `sources/{source_id}/raw.pdf`
- **AND** 更新 `Source.status` 为 `FETCHED`
- **AND** 自动创建 `PARSE_DOCUMENT` 任务

#### Scenario: 检测到登录或付费限制
- **WHEN** URL 返回 401、403 或页面内容包含登录表单特征
- **THEN** 任务状态变为 `FAILED`，`error_code` 为 `SOURCE_ACCESS_RESTRICTED`
- **AND** `Source.status` 变为 `FAILED`，`error_code` 为 `SOURCE_ACCESS_RESTRICTED`

#### Scenario: 采集超时
- **WHEN** URL 采集超过 30 秒
- **THEN** 任务状态变为 `FAILED`，`error_code` 为 `FETCH_TIMEOUT`
- **AND** `Source.status` 变为 `FAILED`

#### Scenario: 采集过大文件
- **WHEN** URL 返回内容超过 10 MB
- **THEN** 任务状态变为 `FAILED`，`error_code` 为 `FETCH_TOO_LARGE`
- **AND** `Source.status` 变为 `FAILED`

#### Scenario: 检测到动态网页
- **WHEN** HTML 解析后正文为空且页面包含大量 `<script>` 标签
- **THEN** 任务状态变为 `FAILED`，`error_code` 为 `SOURCE_UNSUPPORTED_DYNAMIC`
- **AND** `Source.status` 变为 `FAILED`，提示用户手动上传 PDF

### Requirement: 文档解析

系统 SHALL 解析已采集的来源文件，提取正文和基础元数据。

#### Scenario: 解析 HTML 页面
- **WHEN** Worker 对 HTML 文件执行解析
- **THEN** 提取页面标题（`<title>`）、正文文本和基础元数据（`<meta name="description">`）
- **AND** 移除 `<script>`、`<style>`、`<nav>`、`<footer>` 等非正文标签
- **AND** 创建 `ParsedDocument` 记录，`parsed_text` 不为空，`title` 为页面标题
- **AND** 更新 `Source.status` 为 `PARSED`

#### Scenario: 解析 PDF 文件
- **WHEN** Worker 对 PDF 文件执行解析
- **THEN** 提取 PDF 文本内容
- **AND** 创建 `ParsedDocument` 记录，`parsed_text` 不为空
- **AND** 更新 `Source.status` 为 `PARSED`

#### Scenario: 解析为空
- **WHEN** 解析后文本内容为空或过短（少于 50 字符）
- **THEN** 任务状态变为 `FAILED`，`error_code` 为 `PARSE_TEXT_EMPTY`
- **AND** `Source.status` 变为 `FAILED`

### Requirement: 证据卡片候选生成

系统 SHALL 通过 LLM Gateway 从已解析文档生成结构化证据卡片候选。

#### Scenario: 生成本地规则证据卡片
- **WHEN** 用户对已解析来源触发证据卡片生成
- **THEN** 系统创建 `GENERATE_EVIDENCE` 后台任务
- **AND** Worker 通过本地规则提供者从 `ParsedDocument.parsed_text` 提取关键句子作为候选
- **AND** 每张候选卡片包含 `summary`、`evidence_type`、`source_id`、`locator`、`status=CANDIDATE`
- **AND** `candidate_source` 为 `LOCAL_RULE`

#### Scenario: 无可用解析文档
- **WHEN** 触发生成但来源未解析（`Source.status` 不是 `PARSED`）
- **THEN** 返回 `EVIDENCE_SOURCE_NOT_PARSED` 结构化错误

#### Scenario: 证据类型分类
- **WHEN** 本地规则提供者提取证据
- **THEN** 每张卡片 `evidence_type` 为以下之一：`BACKGROUND`（背景）、`METHOD`（方法）、`RESULT`（结果）、`CONCLUSION`（结论）、`LIMITATION`（局限性）、`REFERENCE`（参考）

### Requirement: 证据卡片确认

系统 SHALL 允许用户确认、编辑或拒绝证据卡片候选。

#### Scenario: 确认证据卡片
- **WHEN** 用户确认一张候选卡片
- **THEN** 卡片 `status` 变为 `CONFIRMED`
- **AND** 写入变更记录，`change_type` 为 `EVIDENCE_CARD_CONFIRMED`

#### Scenario: 编辑证据卡片
- **WHEN** 用户修改候选卡片的 `summary` 或 `evidence_type`
- **THEN** 卡片更新并保持 `CANDIDATE` 状态
- **AND** 写入变更记录，`change_type` 为 `EVIDENCE_CARD_UPDATED`

#### Scenario: 拒绝证据卡片
- **WHEN** 用户拒绝一张候选卡片
- **THEN** 卡片 `status` 变为 `REJECTED`
- **AND** 写入变更记录，`change_type` 为 `EVIDENCE_CARD_REJECTED`

### Requirement: 状态推进

系统 SHALL 在来源收集和证据确认后推进项目状态。

#### Scenario: 推进到 SOURCES_COLLECTED
- **WHEN** 项目至少有一个来源状态为 `PARSED`
- **AND** 用户触发"完成来源收集"
- **THEN** 项目状态变为 `SOURCES_COLLECTED`
- **AND** 写入变更记录

#### Scenario: 推进到 EVIDENCE_CONFIRMED
- **WHEN** 项目至少有一张证据卡片状态为 `CONFIRMED`
- **AND** 用户触发"完成证据确认"
- **THEN** 项目状态变为 `EVIDENCE_CONFIRMED`
- **AND** 写入变更记录

#### Scenario: 状态不足时拒绝推进
- **WHEN** 项目状态不足（如 `DRAFT` 或 `REQUIREMENT_PARSED`）
- **THEN** 拒绝推进并返回 `PROJECT_REQUIREMENT_NOT_CONFIRMED` 结构化错误

### Requirement: STALE 传播

系统 SHALL 在来源变化时标记关联证据卡片为过期。

#### Scenario: 来源重新采集导致证据卡片过期
- **WHEN** 来源重新采集后 `content_hash` 变化
- **AND** 该来源已有关联证据卡片
- **THEN** 关联证据卡片 `status` 变为 `STALE`

#### Scenario: 来源删除导致证据卡片过期
- **WHEN** 用户删除一个已有关联证据卡片的来源
- **THEN** 关联证据卡片 `status` 变为 `STALE`
- **AND** 来源记录标记为 `DELETED`（软删除，不物理删除）

## MODIFIED Requirements

无。本切片不修改 SPEC 0001 或 SPEC 0002 的已有合同。

## REMOVED Requirements

无。

---

## 后端核心合同

### Source

用于保存公开 URL 或本地 PDF 文件来源。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | 字符串 | 来源唯一标识 |
| `project_id` | 字符串 | 所属项目 |
| `source_kind` | 枚举 | `URL`、`FILE` |
| `title` | 字符串 | 来源标题（URL 时为页面标题或 URL，文件时为文件名） |
| `url` | 字符串，可空 | URL 来源的原始地址 |
| `file_path` | 字符串，可空 | 本地文件在受控工作区内的位置 |
| `content_type` | 字符串，可空 | 采集到的 Content-Type |
| `content_hash` | 字符串，可空 | 内容哈希，用于判断变化 |
| `status` | 枚举 | `PENDING`、`FETCHED`、`PARSED`、`FAILED`、`DELETED` |
| `error_code` | 字符串，可空 | 失败原因码 |
| `error_message` | 字符串，可空 | 失败原因中文说明 |
| `created_at` | 时间 | 创建时间 |
| `fetched_at` | 时间，可空 | 采集完成时间 |
| `parsed_at` | 时间，可空 | 解析完成时间 |

约束：
- `source_kind=URL` 时 `url` 必须非空；`source_kind=FILE` 时 `file_path` 必须非空。
- 文件必须保存到项目受控工作区 `sources/{source_id}/` 目录内。
- 不允许用户指定任意宿主机路径。
- `content_hash` 变化时触发 STALE 传播。

### ParsedDocument

用于保存解析后的文档内容。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | 字符串 | 解析文档唯一标识 |
| `source_id` | 字符串 | 所属来源 |
| `project_id` | 字符串 | 所属项目 |
| `title` | 字符串，可空 | 文档标题 |
| `parsed_text` | 文本 | 解析后的正文 |
| `metadata_json` | 字符串，可空 | 基础元数据（如 meta description、页数） |
| `parsed_at` | 时间 | 解析时间 |

约束：
- `parsed_text` 不能为空。
- 一个来源只能有一个 `ParsedDocument`（重新解析时覆盖并触发 STALE）。

### EvidenceCard

用于保存证据卡片候选或已确认卡片。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | 字符串 | 证据卡片唯一标识 |
| `project_id` | 字符串 | 所属项目 |
| `source_id` | 字符串 | 来源 |
| `parsed_document_id` | 字符串 | 解析文档 |
| `summary` | 文本 | 证据摘要 |
| `evidence_type` | 枚举 | `BACKGROUND`、`METHOD`、`RESULT`、`CONCLUSION`、`LIMITATION`、`REFERENCE` |
| `locator` | 字符串 | 来源位置（如"第3段"或"页面顶部"） |
| `source_quote` | 字符串，可空 | 原文短摘录 |
| `status` | 枚举 | `CANDIDATE`、`CONFIRMED`、`REJECTED`、`STALE` |
| `candidate_source` | 枚举 | `MODEL`、`LOCAL_RULE`、`MANUAL` |
| `created_at` | 时间 | 创建时间 |
| `updated_at` | 时间 | 更新时间 |
| `confirmed_at` | 时间，可空 | 确认时间 |

约束：
- 模型建议必须通过结构化合同校验后才能保存。
- 用户确认后状态变为 `CONFIRMED`。
- 来源变化后关联卡片变为 `STALE`，不得静默覆盖。

### BackgroundJob

用于保存后台任务记录。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | 字符串 | 任务唯一标识 |
| `project_id` | 字符串 | 所属项目 |
| `job_type` | 枚举 | `FETCH_URL`、`PARSE_DOCUMENT`、`GENERATE_EVIDENCE` |
| `status` | 枚举 | `PENDING`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED` |
| `input_json` | 字符串 | 任务输入参数（如 `source_id`、`url`） |
| `output_json` | 字符串，可空 | 任务输出（如 `parsed_document_id`） |
| `error_code` | 字符串，可空 | 失败原因码 |
| `error_message` | 字符串，可空 | 失败原因中文说明 |
| `retry_count` | 整数 | 已重试次数 |
| `max_retries` | 整数 | 最大重试次数，默认 2 |
| `created_at` | 时间 | 创建时间 |
| `started_at` | 时间，可空 | 开始执行时间 |
| `finished_at` | 时间，可空 | 完成或失败时间 |
| `next_retry_at` | 时间，可空 | 下次重试时间 |

约束：
- Worker 领取任务必须原子性（使用数据库行锁或状态条件更新）。
- 任务失败时根据 `retry_count` 和 `max_retries` 决定是否重试。
- Worker 不拥有业务语义，只调用核心服务并写回状态。

---

## 后端 API 合同

### 来源

#### 登记公开 URL

```text
POST /api/projects/{project_id}/sources/url
```

请求体：
```json
{ "url": "https://example.com/article.html", "title": "可选标题" }
```

成功响应（201）返回 `SourceResponse`，包含 `id` 和 `job_id`。

#### 上传 PDF 文件

```text
POST /api/projects/{project_id}/sources/pdf
```

请求为 `multipart/form-data`，字段 `file`（PDF 文件）和可选 `title`。

成功响应（201）返回 `SourceResponse`，包含 `id` 和 `job_id`。

#### 获取来源列表

```text
GET /api/projects/{project_id}/sources
```

返回 `{ "items": [SourceResponse] }`。

#### 获取来源详情

```text
GET /api/projects/{project_id}/sources/{source_id}
```

返回 `SourceResponse`。

#### 删除来源

```text
DELETE /api/projects/{project_id}/sources/{source_id}
```

软删除：来源标记为 `DELETED`，关联证据卡片变为 `STALE`。

#### 完成来源收集

```text
POST /api/projects/{project_id}/sources/complete
```

推进项目状态到 `SOURCES_COLLECTED`。前置条件：至少一个来源 `status=PARSED`。

### 证据卡片

#### 生成证据卡片候选

```text
POST /api/projects/{project_id}/sources/{source_id}/evidence/generate
```

创建 `GENERATE_EVIDENCE` 后台任务。前置条件：来源 `status=PARSED`。

返回（201）`{ "job_id": "..." }`。

#### 获取证据卡片列表

```text
GET /api/projects/{project_id}/evidence
```

可选查询参数 `source_id` 和 `status`。

返回 `{ "items": [EvidenceCardResponse] }`。

#### 更新证据卡片

```text
PUT /api/projects/{project_id}/evidence/{card_id}
```

请求体：`{ "summary": "...", "evidence_type": "METHOD", "locator": "..." }`

只能修改 `CANDIDATE` 或 `STALE` 状态的卡片。

#### 确认证据卡片

```text
POST /api/projects/{project_id}/evidence/{card_id}/confirm
```

只能确认 `CANDIDATE` 状态的卡片。

#### 拒绝证据卡片

```text
POST /api/projects/{project_id}/evidence/{card_id}/reject
```

只能拒绝 `CANDIDATE` 状态的卡片。

#### 完成证据确认

```text
POST /api/projects/{project_id}/evidence/complete
```

推进项目状态到 `EVIDENCE_CONFIRMED`。前置条件：至少一张卡片 `status=CONFIRMED`。

### 后台任务

#### 获取任务状态

```text
GET /api/projects/{project_id}/jobs/{job_id}
```

返回 `JobResponse`，前端用于轮询。

#### 获取任务列表

```text
GET /api/projects/{project_id}/jobs
```

可选查询参数 `status` 和 `job_type`。

返回 `{ "items": [JobResponse] }`。

---

## 数据库与迁移

新增表：

```text
sources
  id (PK, String 32)
  project_id (String 32, indexed)
  source_kind (String 16)
  title (String 500)
  url (String 2000, nullable)
  file_path (String 1000, nullable)
  content_type (String 100, nullable)
  content_hash (String 64, nullable)
  status (String 16)
  error_code (String 64, nullable)
  error_message (String 500, nullable)
  created_at (DateTime)
  fetched_at (DateTime, nullable)
  parsed_at (DateTime, nullable)

parsed_documents
  id (PK, String 32)
  source_id (String 32, indexed)
  project_id (String 32, indexed)
  title (String 500, nullable)
  parsed_text (Text)
  metadata_json (Text, nullable)
  parsed_at (DateTime)

evidence_cards
  id (PK, String 32)
  project_id (String 32, indexed)
  source_id (String 32, indexed)
  parsed_document_id (String 32)
  summary (Text)
  evidence_type (String 32)
  locator (String 200)
  source_quote (Text, nullable)
  status (String 16)
  candidate_source (String 32)
  created_at (DateTime)
  updated_at (DateTime)
  confirmed_at (DateTime, nullable)

background_jobs
  id (PK, String 32)
  project_id (String 32, indexed)
  job_type (String 32)
  status (String 16)
  input_json (Text)
  output_json (Text, nullable)
  error_code (String 64, nullable)
  error_message (String 500, nullable)
  retry_count (Integer, default 0)
  max_retries (Integer, default 2)
  created_at (DateTime)
  started_at (DateTime, nullable)
  finished_at (DateTime, nullable)
  next_retry_at (DateTime, nullable)
```

迁移必须通过 Alembic 管理。

---

## 大模型网关边界

本切片继续使用本地规则提供者，不接入真实 DeepSeek。

```text
EvidenceCardDraftProvider
  -> LocalRuleEvidenceCardProvider（按段落和关键词提取候选）
  -> FakeEvidenceCardProvider（测试用）
```

约束：
- 没有 `DEEPSEEK_API_KEY` 时，不得伪装成真实模型输出。
- 本地适配器生成的候选必须标记 `candidate_source=LOCAL_RULE`。
- 单元测试和 API 测试使用 Fake 或 LocalRule 适配器，不依赖外网。
- 真实 DeepSeek 调用是否在后续切片实现，由后续决策记录决定。

---

## 本地配置

新增配置：

```text
SOURCE_FETCH_TIMEOUT_SECONDS=30
SOURCE_FETCH_MAX_SIZE_BYTES=10485760
JOB_MAX_RETRIES=2
JOB_RETRY_BACKOFF_SECONDS=5
WORKER_POLL_INTERVAL_SECONDS=1
```

规则：
- 默认本地开发使用 `local_rule` 证据卡片提供者。
- 真实 DeepSeek 适配器不得在本切片接入业务模块。

---

## 前端工作台范围

本切片前端至少提供两个工作区："资料来源工作区"和"证据卡片工作区"。

### 资料来源工作区

展示：
- 当前项目名称和状态；
- 来源列表（含状态、类型、标题、错误信息）；
- URL 登记入口；
- PDF 文件上传入口；
- 来源详情（含采集状态、解析状态、错误原因）；
- 后台任务状态轮询（使用 TanStack Query）；
- 删除来源按钮；
- "完成来源收集"按钮。

行为：
- 项目状态不足时，禁用来源登记入口。
- URL 登记后立即创建任务并开始轮询。
- 采集失败时展示后端结构化错误。
- 来源未解析时，禁用"生成证据卡片"按钮。

### 证据卡片工作区

展示：
- 证据卡片列表（含状态、类型、摘要、来源位置）；
- 按状态筛选；
- 编辑、确认、拒绝按钮；
- STALE 卡片标记；
- "完成证据确认"按钮。

行为：
- 只能编辑 `CANDIDATE` 或 `STALE` 状态的卡片。
- 只能确认 `CANDIDATE` 状态的卡片。
- 前端不得自行判断证据类型或来源位置。

### 通用行为

- 前端只消费后端状态和结构化错误，不私造业务状态机。
- 任务状态轮询使用 TanStack Query 的 `refetchInterval`。
- 前端不得自行判断来源是否可访问或证据是否真实。

---

## 错误码

新增错误码：

- `SOURCE_URL_REQUIRED`：URL 不能为空
- `SOURCE_URL_INVALID`：URL 格式不正确
- `SOURCE_URL_SCHEME_UNSUPPORTED`：仅支持 http 和 https
- `SOURCE_URL_NOT_PUBLIC`：URL 指向非公开地址
- `SOURCE_FILE_UNSUPPORTED`：仅支持 PDF 文件
- `SOURCE_FILE_EMPTY`：文件不能为空
- `SOURCE_FILE_TOO_LARGE`：文件大小超过 10 MB
- `SOURCE_NOT_FOUND`：未找到来源
- `SOURCE_NOT_PARSED`：来源未解析
- `SOURCE_ACCESS_RESTRICTED`：来源需要登录或付费
- `FETCH_TIMEOUT`：采集超时
- `FETCH_TOO_LARGE`：采集内容过大
- `PARSE_TEXT_EMPTY`：解析后文本为空
- `SOURCE_UNSUPPORTED_DYNAMIC`：动态网页不支持
- `EVIDENCE_SOURCE_NOT_PARSED`：来源未解析，无法生成证据
- `EVIDENCE_CARD_NOT_FOUND`：未找到证据卡片
- `EVIDENCE_CARD_NOT_EDITABLE`：只能修改候选或过期卡片
- `EVIDENCE_CARD_NOT_CONFIRMABLE`：只能确认候选卡片
- `JOB_NOT_FOUND`：未找到任务
- `PROJECT_REQUIREMENT_NOT_CONFIRMED`：项目需求未确认
- `PROJECT_SOURCES_NOT_COLLECTED`：来源未收集完成
- `PROJECT_NO_PARSED_SOURCE`：没有已解析的来源
- `PROJECT_NO_CONFIRMED_EVIDENCE`：没有已确认的证据卡片

错误响应格式沿用 SPEC 0001/0002 的统一形状：

```json
{ "error": { "code": "SOURCE_URL_NOT_PUBLIC", "message": "URL 指向非公开地址", "field": "url" } }
```

---

## 安全与边界

- URL 必须是 `http` 或 `https` 协议。
- URL 不得指向私有 IP 段（`127.0.0.0/8`、`10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`）、`localhost`、`file://` 或 `ftp://`。
- URL 采集必须设置 30 秒超时和 10 MB 大小上限。
- PDF 文件上传必须保存到项目受控工作区 `sources/{source_id}/` 目录。
- 文件名必须清洗后再写入受控工作区（沿用 SPEC 0002 的 `_safe_upload_filename` 模式）。
- 不解析宏，不执行文档内任何内容。
- 不绕过登录、验证码、付费墙或访问控制。
- 检测到 401/403 或登录表单特征时，返回 `SOURCE_ACCESS_RESTRICTED`，不重试。
- Worker 进程不得访问项目工作区外的目录。
- Worker 不得执行用户提供代码。
- 模型建议不得覆盖来源原始内容。
- 医学相关内容只作为教学数据分析，不提供诊断或治疗建议。

---

## 测试与验收

最低验收命令：

```text
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
```

本切片验收项：

- 能为 `REQUIREMENT_CONFIRMED` 状态的项目登记公开 URL。
- 能上传 PDF 文件并保存到受控工作区。
- Worker 能领取 `FETCH_URL` 任务并采集 HTML 页面。
- Worker 能采集 PDF 直链。
- 非公开 URL 返回 `SOURCE_URL_NOT_PUBLIC`。
- 受限 URL 返回 `SOURCE_ACCESS_RESTRICTED`。
- 采集超时返回 `FETCH_TIMEOUT`。
- Worker 能解析 HTML 和 PDF。
- 解析为空返回 `PARSE_TEXT_EMPTY`。
- 动态网页返回 `SOURCE_UNSUPPORTED_DYNAMIC`。
- 能生成证据卡片候选（本地规则）。
- 候选卡片包含 `summary`、`evidence_type`、`locator` 和 `source_id`。
- 能编辑候选卡片。
- 能确认候选卡片。
- 能拒绝候选卡片。
- 来源重新采集后关联卡片变为 `STALE`。
- 来源删除后关联卡片变为 `STALE`。
- 能推进项目状态到 `SOURCES_COLLECTED`。
- 能推进项目状态到 `EVIDENCE_CONFIRMED`。
- 后台任务有重试机制。
- 无真实 DeepSeek API Key 时，本地验收仍可通过。
- 前端构建通过。
- 后端测试通过。
- 数据库迁移通过。

---

## 文档回写要求

本切片代码真正完成后，必须回写：

- `dev-docs/README.md`：更新当前切片状态。
- `dev-docs/acceptance.md`：记录实际验收命令和结果。
- `dev-docs/implementation-plan.md`：勾选任务 5 中已完成子项。
- 本 SPEC：若实现范围与本文档不同，必须更新差异和原因。
- `dev-docs/dependency-review.md`：更新实际安装的 `pypdf`、`beautifulsoup4`、`lxml`、`httpx` 版本。

---

## 停止条件

第三切片完成的停止条件：

- 公开 URL 可登记、采集和解析。
- PDF 文件可上传、保存和解析。
- 后台任务表和 Worker 进程可运行。
- 证据卡片候选可生成、编辑和确认。
- 来源变化时关联证据卡片变为 `STALE`。
- 项目状态可从 `REQUIREMENT_CONFIRMED` 推进到 `SOURCES_COLLECTED` 和 `EVIDENCE_CONFIRMED`。
- 受限资源被结构化拒绝，不绕过限制。
- 基础测试和构建命令有当前证据。
- 没有引入本 SPEC 明确排除的功能。
- 文档回写完成。

完成第三切片后必须暂停，由项目负责人确认后再进入下一切片。

---

## 后续切片入口

第三切片之后，下一切片建议进入：

```text
数据集工作区 SPEC（V0.3 第一部分）
```

该下一切片才开始处理：

- CSV/Excel 数据集上传；
- 数据版本管理；
- 字段概览与质量检查；
- 清洗方案和分析方案候选；
- 用户确认分析方案。

---

## 实施差异记录（2026-07-06）

本切片已完成实现并经端到端验收，实际实现与 SPEC 文档一致，仅以下细节存在差异或补充说明：

### 实际安装依赖版本

| 依赖 | SPEC 复核版本 | 实际安装版本 | 说明 |
| --- | --- | --- | --- |
| `httpx` | `0.28.1` | `0.28.1` | 与 SPEC 一致 |
| `pypdf` | `6.13.2` | `6.14.2` | 复核后的小版本升级，无破坏性变更 |
| `beautifulsoup4` | `4.15.0` | `4.15.0` | 与 SPEC 一致 |
| `lxml` | `6.1.1` | `6.1.1` | 与 SPEC 一致 |

`playwright` 未在本切片安装，符合 SPEC 边界。

### 实际实现的 14 个 API 端点

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/api/projects/{project_id}/sources/url` | POST | 登记 URL 来源 |
| `/api/projects/{project_id}/sources/pdf` | POST | 上传 PDF 文件 |
| `/api/projects/{project_id}/sources` | GET | 来源列表 |
| `/api/projects/{project_id}/sources/{source_id}` | GET | 来源详情 |
| `/api/projects/{project_id}/sources/{source_id}` | DELETE | 软删除来源 |
| `/api/projects/{project_id}/sources/complete` | POST | 完成来源收集 |
| `/api/projects/{project_id}/sources/{source_id}/evidence/generate` | POST | 触发证据卡片生成 |
| `/api/projects/{project_id}/evidence` | GET | 证据卡片列表（支持 `source_id` 和 `status` 过滤） |
| `/api/projects/{project_id}/evidence/{card_id}` | PUT | 更新证据卡片 |
| `/api/projects/{project_id}/evidence/{card_id}/confirm` | POST | 确认证据卡片 |
| `/api/projects/{project_id}/evidence/{card_id}/reject` | POST | 拒绝证据卡片 |
| `/api/projects/{project_id}/evidence/complete` | POST | 完成证据确认 |
| `/api/projects/{project_id}/jobs/{job_id}` | GET | 任务详情 |
| `/api/projects/{project_id}/jobs` | GET | 任务列表 |

### 数据库迁移

迁移文件 `server/alembic/versions/0003_create_sources_and_jobs_tables.py`，revision=`0003`，down_revision=`0002`，创建 4 张表（sources、parsed_documents、evidence_cards、background_jobs）和 6 个索引。

### 测试覆盖

实际编写 8 个测试文件，共新增 127 个测试用例：

| 测试文件 | 测试数 |
| --- | --- |
| test_sources_service.py | 24 |
| test_sources_api.py | 18 |
| test_evidence_service.py | 17 |
| test_evidence_api.py | 15 |
| test_jobs_service.py | 13 |
| test_worker_handlers.py | 15 |
| test_http_fetcher.py | 11 |
| test_parsers.py | 14 |

加上原 SPEC 0001/0002 的 26 个测试，总计 153 个测试全部通过。

### 端到端验收结果

主链路完整跑通：

```text
创建项目 → 添加文本要求 → 生成任务单 → 确认任务单（状态 REQUIREMENT_CONFIRMED）
  → 登记 URL https://example.com/ → Worker FETCH_URL → FETCHED → PARSE_DOCUMENT → PARSED
  → 触发生成证据卡片 → Worker GENERATE_EVIDENCE → 1 张 CANDIDATE 卡片
  → 确认卡片（CONFIRMED）→ 完成证据确认 → 状态 EVIDENCE_CONFIRMED
```

错误分支验收：
- 非公开 URL（localhost、127.0.0.1、192.168.x.x）返回 `SOURCE_URL_NOT_PUBLIC`
- 不支持协议（file://、ftp://）返回 `SOURCE_URL_SCHEME_UNSUPPORTED`
- 受限 URL（http://jigsaw.w3.org/HTTP/Basic/，返回 401）最终 `SOURCE_ACCESS_RESTRICTED`
- 来源删除后 10 张 CANDIDATE 卡片全部变为 `STALE`

### 非阻断债务

- 第三方 `fastapi.testclient` 对 `httpx` 的弃用提示继续保留，是 SPEC 0002 已记录的非阻断债务。
- 真实浏览器点击截图验收未执行（当前会话未暴露可调用的 in-app Browser 工具），用 Vite 页面可访问、`/api` 代理主链路联通、`curl` 端到端验证作为替代证据。
- `https://httpbin.org/status/403` 在 `curl` 中返回 403，但 `httpx` 实际收到 503（httpbin 前置代理对 Python User-Agent 差异化响应）。这是外部服务行为，与本项目代码无关，已用 `jigsaw.w3.org/HTTP/Basic/` 验证 `SOURCE_ACCESS_RESTRICTED` 路径。

### 实施过程的范围决策

通过 AskUserQuestion 在 spec 编写阶段确认了 4 个关键范围决策：

1. Worker：引入最小 Worker 进程（数据库任务表 + 轮询），不引入 Celery/RQ/Redis。
2. LLM：继续使用本地规则提供者，不接入真实 DeepSeek。
3. 文件格式：仅支持 PDF + HTML URL，不支持 Word/TXT/CSV/Excel。
4. Playwright：不引入，动态网页检测后建议用户手动上传 PDF。

这些决策已在决策记录 0014 中固化。
