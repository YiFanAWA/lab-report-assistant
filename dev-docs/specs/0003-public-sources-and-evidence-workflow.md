# 实验报告助手｜第三开发切片 SPEC：公开资料与证据工作流

> 状态：已完成实现、复核验收，并于 2026-06-22 由项目负责人确认收口
> 创建日期：2026-06-17
> 依据：[project-charter.md](../project-charter.md)、[architecture.md](../architecture.md)、[implementation-plan.md](../implementation-plan.md)、[specs/0002-requirement-input-and-task-plan.md](0002-requirement-input-and-task-plan.md)
> 阶段约束：第一阶段已完成并收口；第二阶段 Skill、Orchestrator 与 feasibility 未获批准，后续能力必须重新经过 SPEC 与项目负责人确认。

## 1. 切片定位

第三开发切片只解决一个问题：**让已确认实验要求的项目能够登记公开资料和本地辅助资料，并从可解析文本中生成可审阅、可确认、可追溯的证据卡片。**

它承接 SPEC 0002 的已确认任务单，不进入数据集工作区、Python 执行、实验大纲、Word/PPT 生成。

本切片建立以下能力：

- 登记公开 URL 资料；
- 上传本地辅助资料文件；
- 识别公开可访问、受限、失败和暂不支持的来源状态；
- 保存原始资料或原始资料定位信息；
- 从普通网页、公开 PDF、Word、TXT 中提取可定位文本；
- 生成证据卡片候选；
- 允许用户编辑、确认或拒绝证据卡片；
- 让证据卡片保留来源、位置、摘录和用途；
- 更新项目状态为 `SOURCES_COLLECTED` 或 `EVIDENCE_CONFIRMED`。

## 2. 本轮目标

第三开发切片完成后，开发者应能在本地完成以下路径：

```text
打开已确认任务单的项目
  -> 进入公开资料与证据工作区
  -> 添加一个公开 URL 或上传一个本地辅助文件
  -> 系统保存来源记录和采集/解析状态
  -> 对可解析来源提取正文和位置
  -> 系统生成证据卡片候选
  -> 前端展示来源列表、解析状态、证据候选、来源摘录和位置
  -> 用户编辑、确认或拒绝证据卡片
  -> 项目状态变为 SOURCES_COLLECTED 或 EVIDENCE_CONFIRMED
  -> 刷新页面后仍能读取已确认的证据卡片
```

## 3. 明确不做

本切片不得实现以下内容：

- 不做任意网站爬虫。
- 不做搜索引擎检索。
- 不做递归抓取、站点地图抓取或批量下载。
- 不绕过登录、验证码、付费墙、访问控制、反爬限制或 robots 明确禁止的内容。
- 不自动登录知网、学校平台、数据库平台或任何受限制系统。
- 不渲染需要浏览器执行 JavaScript 后才能出现的正文。
- 不注入用户 Cookie、账号、Token、代理或浏览器会话。
- 不解析图片、扫描件 OCR、音视频或复杂表格。
- 不把 CSV/Excel 当作数据集进行字段分析；本切片最多把它们登记为“数据文件候选”，数据预览与质量检查进入后续数据集工作区。
- 不生成数据清洗方案。
- 不生成或执行 Python 代码。
- 不生成实验大纲。
- 不生成 Word 或 PPT。
- 不接入真实 DeepSeek 作为验收必要条件。
- 不把模型总结当成事实；证据必须绑定原文摘录和位置。
- 不提供医学诊断、治疗建议或临床结论。

## 4. 推荐实现范围

本切片覆盖 `implementation-plan.md` 中的：

- 任务 2 的最小子集：`SourceRecord`、`EvidenceCard`；
- 任务 3 的最小子集：来源与证据阶段的项目状态推进；
- 任务 5：来源与证据工作流。

不覆盖任务 6 及之后的数据集、分析、执行、大纲和交付物流程。

## 5. 目标目录结构

实际代码阶段开始后，建议在现有结构上新增或修改：

```text
server/
  app/
    api/
      routers/
        sources.py
    modules/
      sources/
        __init__.py
        contracts.py
        models.py
        service.py
        status.py
      llm/
        evidence_gateway.py
        local_rule_evidence_provider.py
    infrastructure/
      documents/
        pdf_reader.py
        text_reader.py
        html_reader.py
      sources/
        http_fetcher.py
        url_policy.py
  tests/
    test_source_service.py
    test_source_api.py
    test_evidence_service.py

apps/
  web/
    src/
      features/
        sources/
      routes/
        SourceEvidenceWorkspaceView.tsx
```

如实际实现发现更符合现有结构的路径，应优先保持本项目已有模式，并在完成后回写本文档。

## 6. 后端核心合同

### 6.1 `SourceRecord`

用于保存公开 URL 或本地辅助文件来源。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | 字符串 | 来源唯一标识 |
| `project_id` | 字符串 | 所属项目 |
| `source_kind` | 枚举 | `PUBLIC_URL`、`LOCAL_FILE` |
| `source_type` | 枚举 | `WEB_PAGE`、`PDF`、`DOCX`、`TXT`、`CSV`、`EXCEL`、`UNKNOWN` |
| `title` | 字符串 | 来源标题，可来自用户输入或解析结果 |
| `url` | 字符串，可空 | 公开 URL 原文 |
| `original_file_path` | 字符串，可空 | 本地保存的原始文件路径，必须在项目受控工作区内 |
| `content_hash` | 字符串，可空 | 原始内容哈希 |
| `collection_status` | 枚举 | `REGISTERED`、`FETCHED`、`PARSED`、`BLOCKED`、`FAILED`、`UNSUPPORTED` |
| `access_reason` | 字符串，可空 | 受限、失败或不支持原因 |
| `content_type` | 字符串，可空 | HTTP 或上传文件内容类型 |
| `size_bytes` | 整数，可空 | 内容大小 |
| `created_at` | 时间 | 创建时间 |
| `updated_at` | 时间 | 更新时间 |

约束：

- URL 只允许 `http` 和 `https`。
- URL 不允许携带用户名、密码或认证信息。
- URL 不允许指向本机、内网、链路本地地址、保留地址或文件协议。
- 重定向后的最终 URL 仍必须通过同样的安全校验。
- 本地文件必须保存到项目受控工作区内。
- 文件名必须清洗，不允许路径穿越。
- 失败和受限来源必须保存结构化原因，不得伪装成成功。

### 6.2 `ParsedDocument`

用于保存来源解析后的文本和可定位信息。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | 字符串 | 解析文档唯一标识 |
| `project_id` | 字符串 | 所属项目 |
| `source_id` | 字符串 | 所属来源 |
| `parser_type` | 枚举 | `HTML_TEXT`、`PDF_TEXT`、`DOCX_TEXT`、`TXT_TEXT` |
| `title` | 字符串 | 解析得到或继承的标题 |
| `parsed_text` | 文本 | 提取后的正文 |
| `text_hash` | 字符串 | 解析文本哈希 |
| `location_map_json` | JSON 文本 | 段落、页码、标题或网页片段位置映射 |
| `parse_status` | 枚举 | `SUCCEEDED`、`FAILED`、`UNSUPPORTED` |
| `parse_error_code` | 字符串，可空 | 解析失败错误码 |
| `created_at` | 时间 | 创建时间 |

约束：

- `parsed_text` 为空时不得生成证据卡片。
- PDF 必须保留页码或等价位置。
- HTML 必须尽量保留标题、段落序号或片段定位。
- TXT 必须记录编码处理结果。
- CSV/Excel 在本切片不生成 `ParsedDocument`，只保存为来源记录并标记后续数据集工作区处理。

### 6.3 `EvidenceCard`

用于保存可被后续大纲、报告和 PPT 引用的证据候选或已确认证据。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | 字符串 | 证据卡片唯一标识 |
| `project_id` | 字符串 | 所属项目 |
| `source_id` | 字符串 | 证据所属来源 |
| `parsed_document_id` | 字符串 | 证据所属解析文档 |
| `status` | 枚举 | `CANDIDATE`、`CONFIRMED`、`REJECTED`、`STALE` |
| `evidence_type` | 枚举 | `BACKGROUND`、`METHOD`、`DATA_SOURCE`、`METRIC`、`RESULT`、`LIMITATION`、`DEFINITION`、`REFERENCE` |
| `summary` | 字符串 | 证据摘要 |
| `source_quote` | 字符串 | 原文短摘录 |
| `location_label` | 字符串 | 页码、章节、标题、段落或网页位置 |
| `relevance_to_requirement` | 字符串 | 与已确认任务单的关系 |
| `candidate_source` | 枚举 | `MODEL`、`LOCAL_RULE`、`MANUAL` |
| `created_at` | 时间 | 创建时间 |
| `confirmed_at` | 时间，可空 | 确认时间 |

约束：

- `source_quote` 必须来自 `parsed_text` 或可定位原文，不得由模型凭空生成。
- `summary` 可以由模型或本地规则改写，但必须保留 `source_quote`。
- 未确认卡片不得作为最终大纲或交付物的事实来源。
- 来源内容变化后，相关证据必须标记为 `STALE` 或保留为历史版本，不得静默覆盖。

## 7. 来源访问边界

### 7.1 公开 URL 策略

本切片只允许一次性获取用户显式提交的单个公开 URL。

允许：

- `http://` 或 `https://` 的公开 URL；
- 普通公开 HTML 页面；
- 可直接下载的公开 PDF；
- 可直接访问的纯文本文件；
- 可直接访问的 CSV/Excel 文件登记。

禁止：

- `file://`、`ftp://`、`data:`、`javascript:` 等非 HTTP 协议；
- `localhost`、`127.0.0.0/8`、`0.0.0.0`、`10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`、链路本地地址、IPv6 本地地址和保留地址；
- 带用户名或密码的 URL；
- 需要登录、验证码、付费或授权的页面；
- 依赖用户 Cookie、浏览器会话或 Token 的页面；
- 自动追踪页面内链接；
- 使用浏览器自动化绕过访问限制。

建议限制：

- 单次请求超时不超过 15 秒；
- 单个远程内容大小不超过 20 MB；
- 重定向次数不超过 3 次；
- 只保留必要正文、元数据和本地副本，不把全文当作公共分发内容。

### 7.2 本地文件策略

本切片支持上传以下本地辅助文件：

- `.pdf`；
- `.docx`；
- `.txt`；
- `.csv`；
- `.xlsx`。

处理规则：

- `.pdf`、`.docx`、`.txt` 可进入文本解析流程；
- `.csv`、`.xlsx` 只登记为数据文件候选，不做字段识别、数据预览和质量检查；
- 不支持 `.doc`、压缩包、图片、音视频、可执行文件和宏文件；
- 单个文件大小建议不超过 20 MB；
- 文件保存路径必须在项目受控工作区内。

## 8. 解析规则

### 8.1 HTML 解析

普通网页解析只提取标题、正文文本、标题层级和段落位置。

约束：

- 不执行 JavaScript。
- 不点击页面。
- 不滚动加载。
- 不模拟登录。
- 无法提取正文时返回结构化错误 `SOURCE_HTML_TEXT_EMPTY`。

### 8.2 PDF 解析

PDF 解析只提取可复制文本和页码。

约束：

- 不做 OCR。
- 不解析图片中的文字。
- 不还原复杂表格。
- 无文本 PDF 返回结构化错误 `SOURCE_PDF_TEXT_EMPTY`。

### 8.3 Word 和 TXT 解析

Word 复用或扩展现有 `.docx` 文本解析能力。TXT 按 UTF-8 优先解析，失败时尝试常见中文编码并记录编码结果。

约束：

- 不解析 `.doc`。
- 不执行宏。
- 解析后文本为空返回结构化错误。

## 9. 大模型网关边界

本切片必须经过统一证据候选提供者生成证据卡片候选，业务模块不得直接调用 DeepSeek SDK、HTTP 接口或写死模型名。

为了保证本地测试和无密钥环境可验收，本切片允许实现确定性的本地规则适配器：

```text
EvidenceDraftProvider
  -> DeepSeekEvidenceDraftProvider
  -> LocalRuleEvidenceDraftProvider
  -> FakeEvidenceDraftProvider
```

约束：

- 没有 `DEEPSEEK_API_KEY` 时，不得伪装成真实模型输出。
- 本地规则生成的候选必须标记 `candidate_source=LOCAL_RULE` 或 `MANUAL`。
- 单元测试和 API 测试使用 Fake 或 LocalRule 适配器，不依赖外网。
- 模型只能生成候选，不拥有最终事实判断。
- 证据候选必须带原文摘录和位置；拿不到位置时不得生成可确认卡片。

## 10. 后端 API 合同

### 10.1 新增公开 URL 来源

```text
POST /api/projects/{project_id}/sources/urls
```

请求体：

```json
{
  "url": "https://example.com/public-page",
  "title": "公开资料标题"
}
```

成功响应返回 `SourceRecord`。

错误规则：

- URL 为空返回 `SOURCE_URL_REQUIRED`。
- URL 协议不支持返回 `SOURCE_URL_UNSUPPORTED_SCHEME`。
- URL 指向本机或内网返回 `SOURCE_URL_BLOCKED_PRIVATE_NETWORK`。
- 项目不存在返回 `PROJECT_NOT_FOUND`。
- 项目尚未确认任务单返回 `REQUIREMENT_PLAN_NOT_CONFIRMED`。

### 10.2 上传本地辅助资料

```text
POST /api/projects/{project_id}/sources/files
```

请求为 `multipart/form-data`，字段：

- `file`：本地文件；
- `title`：来源标题，可选。

成功响应返回 `SourceRecord`。

错误规则：

- 不支持格式返回 `SOURCE_FILE_UNSUPPORTED`。
- 文件为空返回 `SOURCE_FILE_EMPTY`。
- 文件过大返回 `SOURCE_FILE_TOO_LARGE`。

### 10.3 获取来源列表

```text
GET /api/projects/{project_id}/sources
```

成功响应：

```json
{
  "items": []
}
```

### 10.4 解析来源

```text
POST /api/projects/{project_id}/sources/{source_id}/parse
```

成功响应返回 `ParsedDocument`。

说明：

- 对可解析来源执行文本解析；
- 对 CSV/Excel 返回 `SOURCE_PARSE_UNSUPPORTED_FOR_DATASET_FILE`，提示进入后续数据集工作区；
- 解析失败必须返回结构化错误并保留来源记录。

### 10.5 获取解析文本

```text
GET /api/projects/{project_id}/sources/{source_id}/parsed-document
```

成功响应返回 `ParsedDocument`。

### 10.6 生成证据卡片候选

```text
POST /api/projects/{project_id}/sources/{source_id}/evidence/generate
```

成功响应：

```json
{
  "items": []
}
```

说明：

- 来源必须已有成功解析文本；
- 候选卡片状态为 `CANDIDATE`；
- 候选来源在无真实模型时必须为 `LOCAL_RULE` 或 `MANUAL`。

### 10.7 获取证据卡片列表

```text
GET /api/projects/{project_id}/evidence
```

支持按 `source_id`、`status`、`evidence_type` 过滤。

### 10.8 更新证据卡片

```text
PUT /api/projects/{project_id}/evidence/{evidence_id}
```

用于用户修改候选卡片摘要、证据类型或相关性说明。不得修改 `source_quote` 到原文不存在的内容。

### 10.9 确认证据卡片

```text
POST /api/projects/{project_id}/evidence/{evidence_id}/confirm
```

成功后：

- 证据卡片状态变为 `CONFIRMED`；
- 若项目已有至少一张确认卡片，项目状态可变为 `EVIDENCE_CONFIRMED`；
- 保留确认时间。

### 10.10 拒绝证据卡片

```text
POST /api/projects/{project_id}/evidence/{evidence_id}/reject
```

成功后证据卡片状态变为 `REJECTED`。

## 11. 前端工作台范围

本切片前端至少提供一个“公开资料与证据工作区”。

展示：

- 当前项目名称和状态；
- 已确认任务单摘要；
- 公开 URL 输入入口；
- 本地辅助文件上传入口；
- 来源列表；
- 来源采集状态、解析状态和结构化错误；
- 解析文本摘要；
- 证据卡片候选；
- 证据类型、原文摘录、来源位置、相关性说明；
- 确认、拒绝和编辑入口。

行为：

- 未确认任务单时，不能进入证据工作流。
- 公开 URL 输入区必须提示“仅支持公开可访问资料”。
- 生成失败时展示后端结构化错误。
- 证据确认前明确提示“候选证据需要人工核对”。
- 证据确认后展示确认状态。
- 前端不得自行判断网页是否受限、证据是否真实或医学结论是否成立。

## 12. 数据库与迁移

本切片建议新增表：

```text
source_records
  id
  project_id
  source_kind
  source_type
  title
  url
  original_file_path
  content_hash
  collection_status
  access_reason
  content_type
  size_bytes
  created_at
  updated_at

parsed_documents
  id
  project_id
  source_id
  parser_type
  title
  parsed_text
  text_hash
  location_map_json
  parse_status
  parse_error_code
  created_at

evidence_cards
  id
  project_id
  source_id
  parsed_document_id
  status
  evidence_type
  summary
  source_quote
  location_label
  relevance_to_requirement
  candidate_source
  created_at
  confirmed_at
```

说明：

- 第一版可将 `location_map_json` 保存为 JSON 文本。
- 后续如果需要复杂检索，再拆分位置表或全文索引。
- 迁移必须通过 Alembic 管理。

## 13. 本地配置

本切片不得要求真实密钥。

建议新增或复用配置：

```text
EVIDENCE_DRAFT_PROVIDER=local_rule
SOURCE_FETCH_TIMEOUT_SECONDS=15
SOURCE_FETCH_MAX_BYTES=20971520
SOURCE_UPLOAD_MAX_BYTES=20971520
```

规则：

- 默认本地开发使用 `local_rule` 或测试替身。
- 真实 DeepSeek 适配器不得绕过统一网关。
- 网络请求失败、无权限、超时或内容过大必须返回结构化不可用原因。

## 14. 测试与验收

第一轮实现完成后必须提供当前实际运行过的命令和结果。

最低验收命令建议：

```text
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
```

本切片验收项：

- 未确认任务单的项目不能进入证据工作流。
- 能登记一个公开 URL 来源。
- 能拒绝非 HTTP/HTTPS URL。
- 能拒绝本机、内网和保留地址 URL。
- 能上传 PDF、DOCX、TXT 辅助资料。
- 能把 CSV/Excel 登记为数据文件候选，但不做数据字段分析。
- 能解析一个普通 HTML fixture 并保留标题和段落位置。
- 能解析一个可复制文本 PDF fixture 并保留页码。
- 能解析一个 TXT fixture。
- 能生成证据卡片候选。
- 候选卡片包含证据类型、摘要、原文摘录、来源位置和相关性说明。
- 用户能编辑候选卡片摘要和证据类型。
- 用户能确认或拒绝证据卡片。
- 确认后刷新页面仍能读取证据卡片。
- 至少一张证据确认后，项目状态推进到 `EVIDENCE_CONFIRMED`。
- 受限、失败或不可解析来源有结构化错误。
- 无真实 DeepSeek API Key 时，本地验收仍可通过，但候选来源不得伪装为 `MODEL`。
- 前端构建通过。
- 后端测试通过。

## 15. 错误处理

沿用统一错误形状：

```json
{
  "error": {
    "code": "SOURCE_URL_REQUIRED",
    "message": "公开资料 URL 不能为空",
    "field": "url"
  }
}
```

建议错误码：

- `REQUIREMENT_PLAN_NOT_CONFIRMED`
- `SOURCE_URL_REQUIRED`
- `SOURCE_URL_UNSUPPORTED_SCHEME`
- `SOURCE_URL_BLOCKED_PRIVATE_NETWORK`
- `SOURCE_URL_FETCH_TIMEOUT`
- `SOURCE_URL_FETCH_FAILED`
- `SOURCE_URL_ACCESS_BLOCKED`
- `SOURCE_CONTENT_TOO_LARGE`
- `SOURCE_CONTENT_TYPE_UNSUPPORTED`
- `SOURCE_FILE_UNSUPPORTED`
- `SOURCE_FILE_EMPTY`
- `SOURCE_FILE_TOO_LARGE`
- `SOURCE_HTML_TEXT_EMPTY`
- `SOURCE_PDF_TEXT_EMPTY`
- `SOURCE_TEXT_EMPTY`
- `SOURCE_PARSE_UNSUPPORTED_FOR_DATASET_FILE`
- `SOURCE_RECORD_NOT_FOUND`
- `PARSED_DOCUMENT_NOT_FOUND`
- `EVIDENCE_CARD_NOT_FOUND`
- `EVIDENCE_CARD_INVALID_QUOTE`
- `EVIDENCE_DRAFT_PROVIDER_UNAVAILABLE`

约束：

- 不向前端返回裸异常堆栈。
- 不把模型原始失败文本直接暴露给用户。
- 不把访问受限或解析失败伪装成成功。
- 不把无来源位置的模型总结保存为可确认事实。

## 16. 安全、版权与边界

- 公开 URL 获取必须有超时、大小上限和重定向上限。
- URL 校验必须阻止 SSRF 风险。
- 文件保存必须限制在项目受控工作区。
- 不执行远程页面脚本。
- 不执行文档宏。
- 不访问外部登录态。
- 不把受版权保护的全文作为产品对外分发内容。
- 证据卡片只保存必要摘录和定位说明。
- 医学相关内容只能作为教学数据分析背景资料，不生成诊断或治疗建议。

## 17. 文档回写要求

本切片代码真正完成后，必须回写：

- `dev-docs/README.md`：更新当前切片状态。
- `dev-docs/acceptance.md`：记录实际验收命令和结果。
- `dev-docs/implementation-plan.md`：勾选任务 2、任务 3、任务 5 中已完成子项。
- 本 SPEC：若实现范围与本文档不同，必须更新差异和原因。
- 如新增 HTTP、HTML、PDF 或编码解析依赖，必须更新 `dev-docs/dependency-review.md` 或新增依赖决策记录。

## 18. 停止条件

第三切片完成的停止条件：

- 公开 URL 和本地辅助文件可登记、读取和追踪。
- 可解析来源能生成 `ParsedDocument`。
- 证据卡片候选可生成、编辑、确认和拒绝。
- 证据卡片能追溯到来源摘录和位置。
- 受限、失败和不可解析来源不会被包装为成功。
- 项目状态可推进到 `SOURCES_COLLECTED` 或 `EVIDENCE_CONFIRMED`。
- 没有引入本 SPEC 明确排除的功能。
- 基础测试和构建命令有当前证据。
- 文档回写完成。

完成第三切片后必须暂停，由项目负责人确认后再进入数据集工作区切片。

## 19. 后续切片入口

第三切片之后，下一切片建议进入：

```text
数据集工作区 SPEC
```

该下一切片才开始处理：

- CSV 或 Excel 数据上传；
- 字段、类型、样例和质量概览；
- 缺失值、重复值和异常值提示；
- 数据清洗建议；
- 分析方案候选；
- 数据版本和方案版本关联。

## 20. 待确认事项

以下事项不阻塞本 SPEC 草案，但项目负责人确认前应了解取舍：

- 本切片默认不做搜索，只处理用户手动提交的单个公开 URL。
- 本切片默认不做 JavaScript 渲染网页。
- 本切片默认不把 CSV/Excel 作为数据集解析，只登记为后续数据工作区输入。
- 本切片默认使用本地规则生成证据候选，真实 DeepSeek 不作为验收必要条件。

## 21. 已确认的两阶段修复设计

项目负责人于 2026-06-18 确认采用“先修复，再扩展”的两阶段主线。当前只批准第一阶段进入实施计划；第二阶段必须等待第一阶段验收和收口确认，不得混入本切片。

### 21.1 第一阶段：闭合 SPEC 0003

本阶段只修复并完成公开资料与证据工作流，唯一业务 owner 仍为 `server/app/modules/sources/`。API、前端、文档解析器、URL 获取器和候选生成 Provider 只做适配或候选生成，不拥有来源状态、证据状态和项目阶段推进语义。

修复范围：

- 先纠正真源索引、实施计划和验收记录中的超前完成声明；
- 将公开 URL 原始内容保存到项目受控工作区，使“登记 -> 落盘 -> 解析”形成真实闭环；
- 在首次请求、DNS 解析结果和每次重定向后统一执行 URL 安全策略，并限制重定向次数、响应大小和超时；
- 来源与证据 Service 校验项目归属，API 只映射 Pydantic 合同和统一 `AppError`；
- 保存解析失败状态和结构化原因，不把失败、受限或不支持来源包装为成功；
- 证据候选生成必须消费解析文本及位置映射，保存前校验 `source_quote` 真实存在并具有可定位位置；
- 由来源与证据核心推进 `SOURCES_COLLECTED`、`EVIDENCE_CONFIRMED`，前端和 Skill 不得自行推进；
- 补齐普通 HTML、可复制文本 PDF、DOCX、TXT、CSV/Excel 登记所需依赖与确定性 fixture；
- 补齐来源 API、结构化错误、跨项目隔离、SSRF、状态推进、刷新读取和证据真实性测试；
- 补齐前端公开资料与证据工作台，并通过真实 API 合同展示来源、错误、解析文本和证据确认状态。

第一阶段明确不做：

- 不修复或扩展 `ExperimentFeasibilityCheckSkill`；
- 不新增数据集字段检查、分析方案、Python 执行、大纲或 Word/PPT；
- 不把 `SkillRegistry`、`WorkflowOrchestrator` 或 `skill_runs` 计入 SPEC 0003 完成条件；
- 不以旧测试输出、语法检查或前端构建代替当前后端测试、迁移、API 和浏览器证据。

第一阶段数据流：

```text
已确认任务单
  -> 来源与证据 API
  -> SourceService 校验项目与来源边界
  -> URL/File Adapter 获取并落盘原始内容
  -> Document Adapter 生成 ParsedDocument 与位置映射
  -> EvidenceDraftProvider 生成候选
  -> SourceService 校验摘录、位置和状态
  -> 用户编辑、确认或拒绝
  -> SourceService 推进项目状态
  -> 前端刷新后读取持久化结果
```

第一阶段实施纪律：每个阻断问题先增加能够稳定复现的失败测试，确认失败原因后再做最小修复；核心 Service 通过后，才接 API 和 UI。不得为了让测试变绿而绕过真实落盘、真实位置、结构化错误或项目归属校验。

第一阶段停止条件：

- 本 SPEC 第 14 节验收项全部有当前实际证据；
- URL 与本地文件均可从登记走到确认证据，并能在刷新后读取；
- SSRF、跨项目读取、无原文摘录、无位置证据和错误状态伪装均有回归测试；
- 后端测试、全新 SQLite 迁移、前端 lint/build 和浏览器主链路通过；
- `dev-docs/README.md`、`acceptance.md`、`implementation-plan.md` 与当前源码一致；
- 项目负责人确认 SPEC 0003 收口。

### 21.2 第二阶段：扩展轻量 Skill 层

第二阶段只能在第一阶段收口后启动，并需项目负责人单独确认 Skill 方案。该阶段才处理：

- Skill 正式注册和统一执行入口；
- Runner 与业务 Service 共用明确的事务/会话边界；
- `SUCCEEDED`、`FAILED`、`BLOCKED` 全部写入可靠审计；
- 审计失败不得静默吞掉，业务写入与审计一致性必须有明确策略；
- Orchestrator 成为实际前置条件和允许命令的执行闸，而不只是列表展示；
- Requirement/Evidence Skill 只包装现有 Service，不复制业务规则；
- feasibility 能力等待数据集与分析合同确认后再实现，不以字符串包含匹配代替任务—证据—字段关系。

第二阶段不修改第一阶段已经确认的来源、证据和项目状态业务语义；如确需改变核心合同，必须新建或更新对应 SPEC 后再实施。

### 21.3 第一阶段 Agent 任务分派入口

第一阶段详细步骤、失败测试、最小实现、验收命令和停止条件统一见：

- [SPEC 0003 第一阶段修复实施计划](../plans/2026-06-18-spec-0003-repair-plan.md)

其他 Agent 必须按以下顺序领取任务，不得跳过依赖或把第二阶段 Skill 扩展混入第一阶段：

| 任务 | 目标 | 主要写入边界 | 前置任务 | 必须提交的证据 |
| --- | --- | --- | --- | --- |
| Task 0 | 恢复可复核 Python 环境并记录基线 | server/.venv/、server/pyproject.toml | 无 | 解释器、依赖安装和 pytest 基线输出 |
| Task 1 | 纠正阶段真源和虚假完成声明 | AGENTS.md、dev-docs/ | Task 0 | 漂移扫描、diff --check |
| Task 2 | URL/文件真实落盘、项目归属、SOURCES_COLLECTED | modules/sources/、infrastructure/sources/storage.py、服务测试 | Task 0–1 | 对应 RED/GREEN 测试输出 |
| Task 3 | DNS、重定向、超时、大小与协议安全 | infrastructure/sources/url_policy.py、http_fetcher.py、安全测试 | Task 2 合同稳定 | SSRF 与上界 RED/GREEN 输出 |
| Task 4 | HTML/PDF/TXT 真实位置和失败持久化 | infrastructure/documents/、解析测试 | Task 0、Task 2 | fixture 解析、页码/段落和失败记录测试 |
| Task 5 | 证据摘录、位置、原子保存和状态转换 | modules/sources/、Evidence Provider、证据测试 | Task 2、Task 4 | 伪造摘录拒绝、位置、STALE、确认/拒绝测试 |
| Task 6 | 薄 API、统一错误和跨项目隔离 | api/routers/sources.py、main.py、API 测试 | Task 2–5 | API 成功/错误/隔离合同测试 |
| Task 7 | 前端公开资料与证据工作台 | apps/web/src/features/sources/、页面与路由 | Task 6 | npm.cmd run lint、npm.cmd run build |
| Task 8 | 全新迁移、完整回归和浏览器主链路 | 只允许必要迁移；临时验收产物留在忽略目录 | Task 0–7 | pytest、Alembic、lint/build、浏览器或明确未执行项 |
| Task 9 | 文档回写、漂移锁和 git 边界复核 | dev-docs/，不自动 stage | Task 8 | 实际验收记录、status、diff/staged 列表 |

多 Agent 协作规则：

- 实现任务按表中依赖串行推进；共享文件任务不得并行写入。
- 每个实现 Agent 只拥有任务表指定的写入边界，开始前必须读取 AGENTS.md、dev-docs/README.md、本 SPEC 和详细实施计划。
- 每个生产代码任务必须先产生预期失败的测试证据，再写最小实现并产生通过证据。
- 每个任务完成后先做 SPEC 符合性复核，再做代码质量复核；阻断和重要问题未清零前不得领取下一任务。
- Agent 不得提交、推送、删除或移动 Skill/Orchestrator/0004 及用户其他未提交改动。
- Task 9 完成后必须停止，等待项目负责人确认 SPEC 0003 收口；不得自动进入第二阶段。

### 21.4 第一阶段最终收口状态

最终证据：

- 干净收口分支只包含来源与证据业务、API、前端、迁移 0003 和对应测试，排除 Skill、Orchestrator、feasibility、迁移 0004 与相关浅层测试。
- 全量业务回归为 `54 passed, 1 warning`；warning 为已登记的第三方 TestClient 弃用提示。
- 全新 SQLite 数据库依次迁移到 `0003 (head)`。
- 前端 `npm.cmd run lint` 与 `npm.cmd run build` 均退出码 0，Vite 转换 95 modules。
- Vite `/api` 代理跑通任务单确认、TXT 上传、解析、候选生成、证据确认和刷新读取，最终项目状态为 `EVIDENCE_CONFIRMED`；私网 URL 返回 `SOURCE_URL_BLOCKED_PRIVATE_NETWORK`。
- in-app Browser 已验证私网 URL 错误展示、解析、候选生成、证据编辑保存、刷新保持、证据确认、项目状态推进、项目详情入口和工作台导航，页面控制台无 error/warn。
- Browser 自动化不提供本地文件选择注入，项目负责人明确接受“API 文件上传合同 + Browser 下游真实交互”的分段证据。

### 21.5 收口决策

项目负责人于 2026-06-22 明确确认 SPEC 0003 收口。第二阶段 Skill 扩展不会自动启动；任何后续能力必须重新编写并确认对应 SPEC。
