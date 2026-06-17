# 实验报告助手｜第二开发切片 SPEC：实验要求输入与结构化任务单

> 状态：已完成实现、复核验收并由项目负责人确认收口  
> 创建日期：2026-06-16  
> 依据：[project-charter.md](../project-charter.md)、[architecture.md](../architecture.md)、[implementation-plan.md](../implementation-plan.md)、[specs/0001-project-workspace-and-scaffold.md](0001-project-workspace-and-scaffold.md)  
> 阶段约束：本切片实现完成后必须暂停；项目负责人确认验收前，不进入下一切片。

## 1. 切片定位

第二开发切片只解决一个问题：**让已创建的实验项目能够保存老师的原始实验要求，并生成一份可审阅、可修改、可确认的结构化任务单。**

它承接 SPEC 0001 的项目工作区，不进入资料采集、数据集处理、Python 执行、Word/PPT 生成。

本切片建立以下能力：

- 保存原始实验要求来源；
- 区分老师原始要求、用户补充说明和模型建议；
- 生成结构化任务单候选；
- 给出 L0、L1、L2 或 L3 超范围判断；
- 允许用户修改并确认任务单；
- 更新项目状态为 `REQUIREMENT_PARSED` 或 `REQUIREMENT_CONFIRMED`；
- 保存最小变更记录，避免后续工作流丢失“谁改了什么”。

## 2. 本轮目标

第二开发切片完成后，开发者应能在本地完成以下路径：

```text
打开已创建项目
  -> 进入实验要求工作区
  -> 粘贴实验要求文本或上传简单 .docx 要求文件
  -> 后端保存原始要求来源
  -> 触发任务单候选生成
  -> 系统返回结构化任务单候选和 L0-L3 判断
  -> 前端展示必须任务、推荐任务、可选任务、未知项和超范围任务
  -> 用户编辑任务单
  -> 用户确认任务单
  -> 项目状态变为 REQUIREMENT_CONFIRMED
  -> 刷新页面后仍能读取已确认任务单
```

## 3. 明确不做

本切片不得实现以下内容：

- 不做公开 URL 采集。
- 不解析论文、网页或 PDF。
- 不生成证据卡片。
- 不上传或解析样例数据集。
- 不生成数据清洗方案。
- 不生成 Python 分析代码。
- 不执行 Python。
- 不生成 Word 或 PPT。
- 不做 L3 完整复现。
- 不把 L1/L2 写成完整论文复现。
- 不要求用户提供真实 DeepSeek API Key。
- 不把真实 DeepSeek 调用作为本切片验收的必要条件。
- 不绕过登录、验证码、付费墙或访问控制。
- 不提供医疗诊断或治疗建议。
- 不做复杂 Word 模板还原、批注、页眉页脚、图片 OCR 或扫描件 OCR。

## 4. 推荐实现范围

本切片覆盖 `implementation-plan.md` 中的：

- 任务 2 的最小子集：`RequirementPlan`、`ReplicationLevel`、最小 `ChangeRecord`；
- 任务 3 的最小子集：需求确认后推进项目阶段状态；
- 任务 4：实验要求输入与结构化任务单。

不覆盖任务 5 及之后的资料、证据、数据、执行和交付物流程。

## 5. 目标目录结构

实际代码阶段开始后，建议在现有结构上新增或修改：

```text
server/
  app/
    api/
      routers/
        requirements.py
    modules/
      requirements/
        __init__.py
        contracts.py
        models.py
        service.py
        status.py
      llm/
        __init__.py
        gateway.py
        requirement_parser.py
    infrastructure/
      documents/
        docx_reader.py
  tests/
    test_requirement_service.py
    test_requirement_api.py

apps/
  web/
    src/
      features/
        requirements/
      routes/
        RequirementWorkspaceView.tsx
```

如实际实现发现更符合现有结构的路径，应优先保持本项目已有模式，并在完成后回写本文档。

## 6. 后端核心合同

### 6.1 `RequirementSource`

用于保存老师原始要求和用户补充说明。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | 字符串 | 要求来源唯一标识 |
| `project_id` | 字符串 | 所属项目 |
| `source_type` | 枚举 | `PASTED_TEXT`、`DOCX_FILE`、`USER_NOTE` |
| `title` | 字符串 | 来源标题 |
| `original_text` | 文本 | 解析或粘贴得到的原始文字 |
| `original_file_path` | 字符串，可空 | `.docx` 原始文件在受控项目目录内的位置 |
| `content_hash` | 字符串 | 内容哈希，用于判断是否变化 |
| `created_at` | 时间 | 创建时间 |

约束：

- `original_text` 不能为空。
- `.docx` 文件必须保存到项目受控工作区内。
- 不允许用户指定任意宿主机路径。
- 不支持的文件格式返回结构化错误。

### 6.2 `RequirementPlan`

结构化任务单候选或已确认任务单。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | 字符串 | 任务单唯一标识 |
| `project_id` | 字符串 | 所属项目 |
| `source_id` | 字符串 | 主要要求来源 |
| `status` | 枚举 | `CANDIDATE`、`CONFIRMED`、`STALE` |
| `topic` | 字符串 | 课题 |
| `experiment_type` | 字符串 | 实验类型 |
| `research_subject` | 字符串 | 研究对象 |
| `required_tasks` | 列表 | 必须完成任务 |
| `recommended_tasks` | 列表 | 推荐任务 |
| `optional_tasks` | 列表 | 可选任务 |
| `out_of_scope_tasks` | 列表 | 超出第一版范围的任务 |
| `unknown_items` | 列表 | 未明确项和需确认问题 |
| `data_requirements` | 列表 | 数据要求 |
| `method_requirements` | 列表 | 方法要求 |
| `chart_requirements` | 列表 | 图表要求 |
| `report_requirements` | 列表 | Word 报告要求 |
| `presentation_requirements` | 列表 | PPT 要求 |
| `acceptance_criteria` | 列表 | 可检查验收条件 |
| `replication_level` | 对象 | L0-L3 判断 |
| `candidate_source` | 枚举 | `MODEL`、`LOCAL_RULE`、`MANUAL` |
| `created_at` | 时间 | 创建时间 |
| `confirmed_at` | 时间，可空 | 确认时间 |

约束：

- 模型建议必须通过结构化合同校验后才能保存。
- 未明确内容进入 `unknown_items`，不得擅自写成老师要求。
- 超出第一版范围的任务进入 `out_of_scope_tasks`，不得悄悄丢弃。
- 用户确认后状态变为 `CONFIRMED`。
- 原始要求变化后，旧任务单必须变为 `STALE` 或保留为历史版本，不得静默覆盖。

### 6.3 `RequirementTask`

任务单中的单条任务。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `title` | 字符串 | 任务标题 |
| `description` | 字符串 | 任务说明 |
| `task_type` | 枚举 | `REQUIRED`、`RECOMMENDED`、`OPTIONAL`、`OUT_OF_SCOPE`、`UNKNOWN` |
| `reason` | 字符串 | 为什么这样归类 |
| `source_quote` | 字符串，可空 | 来自原始要求的短摘录或定位说明 |

### 6.4 `ReplicationLevel`

论文复刻层级判断。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `level` | 枚举 | `L0`、`L1`、`L2`、`L3` |
| `label` | 字符串 | 中文标签 |
| `supported_in_v1` | 布尔 | 第一版是否支持 |
| `reason` | 字符串 | 判断原因 |
| `suggested_scope` | 字符串 | 建议用户采用的复刻范围 |

规则：

- `L0` 表示只作为背景和参考文献。
- `L1` 表示方法参考。
- `L2` 表示局部复现。
- `L3` 表示完整复现，第一版必须标记为不支持。

### 6.5 `ChangeRecord`

本切片只实现最小变更记录。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | 字符串 | 变更记录唯一标识 |
| `project_id` | 字符串 | 所属项目 |
| `change_type` | 枚举 | `REQUIREMENT_SOURCE_CREATED`、`REQUIREMENT_PLAN_GENERATED`、`REQUIREMENT_PLAN_UPDATED`、`REQUIREMENT_PLAN_CONFIRMED` |
| `summary` | 字符串 | 变更摘要 |
| `created_at` | 时间 | 创建时间 |

## 7. 大模型网关边界

本切片必须经过统一 `LLMGateway` 或等价适配层生成结构化候选，业务模块不得直接调用 DeepSeek SDK、HTTP 接口或写死模型名。

为了保证本地测试和无密钥环境可验收，本切片允许实现一个确定性的本地测试适配器：

```text
RequirementDraftProvider
  -> DeepSeekRequirementDraftProvider
  -> LocalRuleRequirementDraftProvider
  -> FakeRequirementDraftProvider
```

约束：

- 没有 `DEEPSEEK_API_KEY` 时，不得伪装成真实模型输出。
- 本地适配器生成的候选必须标记 `candidate_source=LOCAL_RULE` 或 `MANUAL`。
- 单元测试和 API 测试使用 Fake 或 LocalRule 适配器，不依赖外网。
- 真实 DeepSeek 调用是否在本切片实现，由实施计划和依赖复核决定；但验收不得依赖真实外网调用。

## 8. 后端 API 合同

### 8.1 新增文本要求来源

```text
POST /api/projects/{project_id}/requirements/sources/text
```

请求体：

```json
{
  "title": "老师实验要求",
  "text": "请围绕胃病数据完成数据清洗、统计分析和可视化，并形成实验报告。"
}
```

成功响应返回 `RequirementSource`。

错误规则：

- 文本为空返回 `REQUIREMENT_TEXT_REQUIRED`。
- 项目不存在返回 `PROJECT_NOT_FOUND`。

### 8.2 上传 Word 要求文件

```text
POST /api/projects/{project_id}/requirements/sources/docx
```

请求为 `multipart/form-data`，字段：

- `file`：`.docx` 文件；
- `title`：来源标题，可选。

成功响应返回解析后的 `RequirementSource`。

错误规则：

- 非 `.docx` 返回 `REQUIREMENT_FILE_UNSUPPORTED`。
- 文件为空返回 `REQUIREMENT_FILE_EMPTY`。
- 解析后文本为空返回 `REQUIREMENT_DOCX_TEXT_EMPTY`。

### 8.3 获取要求来源列表

```text
GET /api/projects/{project_id}/requirements/sources
```

成功响应：

```json
{
  "items": []
}
```

### 8.4 生成任务单候选

```text
POST /api/projects/{project_id}/requirements/plans/generate
```

请求体：

```json
{
  "source_id": "要求来源标识"
}
```

成功响应返回 `RequirementPlan`，状态为 `CANDIDATE`。

### 8.5 获取当前任务单

```text
GET /api/projects/{project_id}/requirements/plan
```

返回当前最新任务单。不存在时返回结构化 `404` 错误。

### 8.6 更新任务单候选

```text
PUT /api/projects/{project_id}/requirements/plans/{plan_id}
```

用于用户修改候选任务单。只能修改 `CANDIDATE` 或 `STALE` 状态的任务单。

### 8.7 确认任务单

```text
POST /api/projects/{project_id}/requirements/plans/{plan_id}/confirm
```

成功后：

- 任务单状态变为 `CONFIRMED`；
- 项目状态变为 `REQUIREMENT_CONFIRMED`；
- 写入变更记录。

## 9. 前端工作台范围

本切片前端至少提供一个“实验要求工作区”。

展示：

- 当前项目名称和状态；
- 原始要求来源列表；
- 粘贴实验要求文本入口；
- `.docx` 上传入口；
- 生成任务单按钮；
- 任务单候选展示；
- L0-L3 复刻层级判断；
- 未明确项；
- 超范围任务；
- 编辑和确认入口。

行为：

- 未保存原始要求时，不能生成任务单。
- 生成失败时展示后端结构化错误。
- 任务单确认前明确提示“仍可修改”。
- 任务单确认后明确展示 `REQUIREMENT_CONFIRMED`。
- 前端不得自行判断 L0-L3，不得自行把任务归类为必须、推荐或超范围。

## 10. 数据库与迁移

本切片建议新增表：

```text
requirement_sources
  id
  project_id
  source_type
  title
  original_text
  original_file_path
  content_hash
  created_at

requirement_plans
  id
  project_id
  source_id
  status
  payload_json
  candidate_source
  created_at
  updated_at
  confirmed_at

change_records
  id
  project_id
  change_type
  summary
  created_at
```

说明：

- 第一版可将任务单复杂结构保存在 `payload_json`，但必须由 Pydantic 合同校验后写入。
- 后续如果需要复杂查询，再拆分任务表和未知项表。
- 迁移必须通过 Alembic 管理。

## 11. 本地配置

本切片不得要求真实密钥。

建议新增或复用配置：

```text
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-v4-pro
DEEPSEEK_API_KEY=
REQUIREMENT_DRAFT_PROVIDER=local_rule
```

规则：

- 默认本地开发使用 `local_rule` 或测试替身。
- `deepseek` 适配器不得绕过统一网关。
- 如果本切片实现真实 DeepSeek 适配器，必须保证无密钥时返回结构化不可用原因，而不是崩溃。

## 12. 测试与验收

第一轮实现完成后必须提供当前实际运行过的命令和结果。

最低验收命令建议：

```text
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
```

本切片验收项：

- 能在已有项目下保存粘贴实验要求。
- 能上传一个简单 `.docx` 并提取正文。
- 原始要求刷新后仍可读取。
- 能生成结构化任务单候选。
- 候选任务单包含必须任务、推荐任务、可选任务、未知项、超范围任务和验收条件。
- 能给出 L0-L3 复刻层级判断。
- L3 必须标记为第一版不支持。
- 用户能修改候选任务单。
- 用户能确认任务单。
- 确认后项目状态变为 `REQUIREMENT_CONFIRMED`。
- 原始要求变化后，旧任务单不会被静默覆盖。
- 生成、修改、确认均写入最小变更记录。
- 无真实 DeepSeek API Key 时，本地验收仍可通过，但候选来源不得伪装为 `MODEL`。
- 前端构建通过。
- 后端测试通过。

## 13. 错误处理

沿用统一错误形状：

```json
{
  "error": {
    "code": "REQUIREMENT_TEXT_REQUIRED",
    "message": "实验要求不能为空",
    "field": "text"
  }
}
```

建议错误码：

- `REQUIREMENT_TEXT_REQUIRED`
- `REQUIREMENT_FILE_UNSUPPORTED`
- `REQUIREMENT_FILE_EMPTY`
- `REQUIREMENT_DOCX_TEXT_EMPTY`
- `REQUIREMENT_SOURCE_NOT_FOUND`
- `REQUIREMENT_PLAN_NOT_FOUND`
- `REQUIREMENT_PLAN_NOT_EDITABLE`
- `REQUIREMENT_DRAFT_PROVIDER_UNAVAILABLE`
- `REQUIREMENT_PLAN_INVALID`

约束：

- 不向前端返回裸异常堆栈。
- 不把模型原始失败文本直接暴露给用户。
- 不把无密钥或模型不可用伪装成成功。

## 14. 安全与边界

- `.docx` 文件只能保存到项目受控工作区。
- 文件大小上限为 10 MB。
- 不解析宏，不执行文档内任何内容。
- 不访问外部 URL。
- 不读取样例数据。
- 不执行用户提供代码。
- 医学相关内容只能作为教学数据分析要求处理。
- 模型建议不得覆盖老师原始要求。

## 15. 文档回写要求

本切片代码真正完成后，必须回写：

- `dev-docs/README.md`：更新当前切片状态。
- `dev-docs/acceptance.md`：记录实际验收命令和结果。
- `dev-docs/implementation-plan.md`：勾选任务 2、任务 3、任务 4 中已完成子项。
- 本 SPEC：若实现范围与本文档不同，必须更新差异和原因。
- 如新增依赖，例如 `.docx` 解析库，必须更新 `dev-docs/dependency-review.md` 或新增依赖决策记录。

## 16. 停止条件

第二切片完成的停止条件：

- 原始实验要求可保存、读取和追踪。
- 结构化任务单候选可生成、编辑和确认。
- L0-L3 判断进入后端合同。
- 项目状态可从 `DRAFT` 或 `REQUIREMENT_PARSED` 推进到 `REQUIREMENT_CONFIRMED`。
- 旧任务单不会被新要求静默覆盖。
- 基础测试和构建命令有当前证据。
- 没有引入本 SPEC 明确排除的功能。
- 文档回写完成。

完成第二切片后必须暂停，由项目负责人确认后再进入资料来源与证据工作流切片。

## 17. 后续切片入口

第二切片之后，下一切片建议进入：

```text
公开资料与证据工作流 SPEC
```

该下一切片才开始处理：

- 公开 URL 登记；
- 本地辅助资料登记；
- 网页、PDF 和文本资料解析；
- 证据卡片候选；
- 来源位置和确认状态。

## 18. 实施差异与当前验收记录

实际实现遵循现有目录风格，主要落点如下：

- 后端需求 owner：`server/app/modules/requirements/`。
- API 接线：`server/app/api/routers/requirements.py`。
- 本地任务单草案提供者：`server/app/modules/llm/local_rule_provider.py`，未接入真实 DeepSeek。
- `.docx` 简单正文提取：`server/app/infrastructure/documents/docx_reader.py`。
- 前端工作区：`apps/web/src/routes/RequirementWorkspaceView.tsx`。
- API 与服务测试：`server/tests/test_requirement_service.py`、`server/tests/test_requirement_api.py`。

与草案的差异：

- 草案中的 `llm/requirement_parser.py` 未单独创建；本切片将本地规则草案提供者放在 `local_rule_provider.py`，仍通过统一 `get_provider()` 网关取得。
- `RequirementTask.task_type` 实际补充 `UNKNOWN`，用于展示未明确项，避免把待确认问题伪装成必须、推荐或超范围任务。
- `.docx` 上传文件名会先清洗再写入项目受控工作区，避免用户文件名携带路径片段。

当前实际验收命令和结果已写入 [acceptance.md](../acceptance.md)。本切片已确认收口，后续只能先编写并确认“公开资料与证据工作流”SPEC，不得直接进入下一切片实现。
