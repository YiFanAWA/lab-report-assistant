# SPEC 0010：Word 模板支持

> **状态：** 待项目负责人确认  
> **版本：** V1.1.0  
> **日期：** 2026-07-23  
> **前置依赖：** SPEC 0006（大纲与交付物）已完成并收口  
> **解决限制：** L2（不做 Word 模板完全兼容）、P1（Word 模板兼容的复杂程度）

---

## 1. 目标

允许用户为每个项目上传 `.docx` 模板文件，在生成 Word 交付物时使用该模板替代默认空白文档。模板使用 Jinja2 风格占位符，支持封面变量替换和章节循环渲染。

### 核心价值

- 学生可以匹配老师要求的特定 Word 格式（封面、页眉页脚、字体、表格样式）
- 不同项目可使用不同模板（项目级绑定，非全局）
- 无模板时保持现有默认渲染行为，向后兼容

### 不做

- 不支持复杂样式继承（如分栏、嵌套表格、SmartArt）
- 不支持 VBA 宏
- 不支持老师特定模板的自动识别
- 不支持模板在线预览
- 不支持模板的图形化编辑器
- 不引入 Jinja2 依赖（使用 python-docx 原生遍历 + 字符串替换模拟 Jinja2 语法）

---

## 2. 范围

### 2.1 功能点清单

| # | 功能点 | 优先级 |
| --- | --- | --- |
 | F1 | 项目级模板上传（.docx 文件） | 必须 |
| F2 | 模板存储到项目工作区受控目录 | 必须 |
| F3 | 模板占位符解析（`{{var}}` 语法） | 必须 |
| F4 | 封面变量替换（课题、项目名、日期等） | 必须 |
| F5 | 章节循环渲染（`{{#sections}}...{{/sections}}`） | 必须 |
| F6 | 无模板时降级到默认渲染 | 必须 |
| F7 | 模板解析失败时降级到默认渲染 + 错误日志 | 必须 |
| F8 | 模板文件大小和类型校验 | 必须 |
| F9 | 删除/替换模板 | 必须 |
| F10 | 生成 Word 时记录是否使用模板 | 必须 |
| F11 | 模板中执行产物嵌入（`{{#artifacts}}`） | 可选 |
| F12 | 模板下载（用户获取自己上传的模板） | 可选 |

### 2.2 占位符规范

#### 封面变量（单值替换）

| 占位符 | 含义 | 数据来源 |
| --- | --- | --- |
| `{{project_name}}` | 项目名称 | Project.name |
| `{{project_topic}}` | 项目课题 | Project.topic |
| `{{generated_date}}` | 生成日期（YYYY-MM-DD） | 渲染时 datetime.now() |
| `{{student_name}}` | 学生姓名（可选） | 预留，V1.1.0 留空 |
| `{{course_name}}` | 课程名称（可选） | 预留，V1.1.0 留空 |

#### 章节循环变量（在 `{{#sections}}...{{/sections}}` 块内）

| 占位符 | 含义 | 数据来源 |
| --- | --- | --- |
| `{{section_title}}` | 章节标题 | OutlineSection.title |
| `{{section_content}}` | 章节正文内容 | OutlineSection.content |
| `{{section_source_type}}` | 章节来源类型 | OutlineSection.source_type |
| `{{section_source_ids}}` | 来源 ID 列表（逗号分隔） | OutlineSection.source_ids |

#### 章节循环语法

模板中使用以下标记表示章节循环区域：

```
{{#sections}}
章节标题：{{section_title}}

{{section_content}}

来源类型：{{section_source_type}}
{{/sections}}
```

- `{{#sections}}` 和 `{{/sections}}` 之间的段落和表格会按大纲的每个 section 重复渲染
- 循环块内的占位符在每次迭代中替换为当前 section 的值
- 循环块外的占位符按封面变量替换

#### 产物占位符（可选，V1.1.0 可不实现）

```
{{#artifacts}}
产物名称：{{artifact_name}}
类型：{{artifact_type}}
{{/artifacts}}
```

### 2.3 模板文件约束

| 约束项 | 限制 |
| --- | --- |
| 文件格式 | `.docx`（application/vnd.openxmlformats-officedocument.wordprocessingml.document） |
| 文件大小 | ≤ 5 MB（`WORD_TEMPLATE_MAX_SIZE_BYTES` 环境变量，默认 5MB） |
| 模板文件内容 | 必须可被 python-docx 成功打开 |
| 占位符语法 | 不合法的占位符保持原样输出（不报错） |
| 章节循环标记 | 若模板含 `{{#sections}}` 但无对应 `{{/sections}}`，降级到默认渲染并记录错误日志 |

---

## 3. 架构设计

### 3.1 Owner 边界

| 层 | Owner | 职责 |
| --- | --- | --- |
| 模板存储 | `server/app/modules/outlines/` | 模板的持久化、查询、删除（模板与大纲/交付物同属 outlines 模块） |
| 模板解析 | `server/app/infrastructure/renderers/word_renderer.py` | 解析 .docx 模板、替换占位符、生成最终文档 |
| API 适配 | `server/app/api/routers/outlines.py` | HTTP 协议映射（上传/下载/删除模板） |
| 配置 | `server/app/core/config.py` | 模板大小限制等环境变量 |
| 前端 | `apps/web/src/routes/OutlineWorkspaceView.tsx` | 上传/删除模板 UI + 生成 Word 时显示模板状态 |

**禁止：**
- 前端不解析模板
- API 层不做模板渲染
- 不在路由中散落模板文件操作

### 3.2 数据模型

在 `outlines` 模块新增 `WordTemplate` 模型：

```python
class WordTemplate(Base):
    """项目级 Word 模板。"""
    __tablename__ = "word_templates"

    id = Column(String, primary_key=True, default=lambda: f"wt_{uuid4().hex[:12]}")
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    file_path = Column(String, nullable=False)  # 相对 PROJECT_DATA_ROOT 的路径
    original_filename = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)  # SHA-256，用于去重和变更检测
    file_size_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=True)

    # 每个项目最多一个模板（唯一约束）
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_word_templates_project_id"),
    )
```

**设计要点：**
- 每个项目最多一个 Word 模板（唯一约束）
- 重新上传时覆盖旧模板（先删旧记录+旧文件，再写新记录+新文件）
- `file_path` 相对 `PROJECT_DATA_ROOT`，绝对路径由 service 层拼接
- `content_hash` 用于检测模板是否变更

### 3.3 模板解析流程

```
用户触发生成 Word
  ↓
outlines_service 判断项目是否有 WordTemplate
  ↓ 有模板                          ↓ 无模板
WordRenderer.render_with_template()   WordRenderer.render()（现有默认逻辑）
  ↓
  打开模板 .docx
  ↓
  遍历段落和表格，识别 {{#sections}}...{{/sections}} 块
  ↓
  循环块外：替换封面变量（{{project_name}} 等）
  ↓
  循环块内：按每个 outline section 重复段落，替换章节变量
  ↓
  保存到输出路径
  ↓
  返回文件路径
```

**降级策略：**
- 模板文件不存在 → 降级到默认渲染 + 日志 `WORD_TEMPLATE_FILE_MISSING`
- 模板无法被 python-docx 打开 → 降级到默认渲染 + 日志 `WORD_TEMPLATE_PARSE_FAILED`
- 章节循环标记不匹配（有开始无结束） → 降级到默认渲染 + 日志 `WORD_TEMPLATE_SECTION_BLOCK_INVALID`

### 3.4 模板文件存储

```
{PROJECT_DATA_ROOT}/{project_id}/word_template/
  └── template.docx  # 固定文件名，覆盖式存储
```

- 上传时先校验大小和类型
- 保存到受控工作区目录
- 路径拼接由 outlines service 负责，禁止用户指定任意宿主机路径

### 3.5 API 合同

新增 3 个端点，挂载在 `server/app/api/routers/outlines.py`：

#### 上传模板

```
POST /api/projects/{project_id}/word-template
Content-Type: multipart/form-data

Body:
  file: .docx 文件
```

**响应：**
- 200 OK：`{ "id": "wt_xxx", "project_id": "...", "original_filename": "template.docx", "file_size_bytes": 12345, "created_at": "..." }`
- 400：`WORD_TEMPLATE_FILE_UNSUPPORTED`（非 .docx）
- 400：`WORD_TEMPLATE_TOO_LARGE`（超过 5MB）
- 409：`PROJECT_OUTLINE_NOT_CONFIRMED`（大纲未确认时不可上传）
- 409：`PROJECT_NOT_FOUND`

#### 获取模板信息

```
GET /api/projects/{project_id}/word-template
```

**响应：**
- 200 OK：`{ "id": "wt_xxx", ... }` 或 `null`（无模板）

#### 删除模板

```
DELETE /api/projects/{project_id}/word-template
```

**响应：**
- 204 No Content
- 404：`WORD_TEMPLATE_NOT_FOUND`

#### 修改现有端点

`POST /api/projects/{project_id}/outline/{outline_id}/word/generate` 的响应中新增字段：

```json
{
  "job_id": "job_xxx",
  "deliverable_id": "del_xxx",
  "template_used": true  // 新增：是否使用了模板
}
```

### 3.6 前端接线

在 `OutlineWorkspaceView.tsx` 新增模板管理区域：

```
大纲已确认区域
  ├── [生成 Word] [生成 PPT]
  └── Word 模板管理
       ├── [上传模板] (文件选择 + 上传按钮)
       ├── [当前模板：template.docx (12.3 KB)] [删除]
       └── [无模板时显示：使用默认格式生成]
```

- 上传成功后显示模板文件名和大小
- 生成 Word 后显示是否使用了模板（`template_used` 字段）

---

## 4. 实现计划

### 4.1 实现顺序（遵循 AGENTS.md 阶段闸）

```
1. 数据模型 + 迁移（server/app/modules/outlines/models.py + alembic）
2. 核心服务层（server/app/modules/outlines/service.py 新增模板 CRUD）
3. 渲染器扩展（server/app/infrastructure/renderers/word_renderer.py 新增 render_with_template）
4. API 适配层（server/app/api/routers/outlines.py 新增 3 端点）
5. Worker handler 接线（GENERATE_WORD handler 读取项目模板并传递给渲染器）
6. 前端接线（OutlineWorkspaceView.tsx + types.ts + api.ts + hooks.ts）
7. 测试（后端 service + renderer + API 测试 + 前端组件测试补充）
```

### 4.2 依赖

| 依赖 | 版本 | 用途 | 是否新增 |
| --- | --- | --- | --- |
| python-docx | 1.2.0 | 模板解析和渲染 | 否（SPEC 0002 已安装） |
| jinja2 | — | — | **不引入**（使用原生遍历替换） |

**不引入新依赖。** 模板占位符替换通过 python-docx 原生段落遍历 + 字符串替换实现。

### 4.3 环境变量

新增 1 个环境变量：

| 变量名 | 默认值 | 说明 |
| --- | --- | --- |
| `WORD_TEMPLATE_MAX_SIZE_BYTES` | `5242880`（5MB） | Word 模板文件大小上限 |

`WORD_TEMPLATE_PATH` 环境变量保留但不使用（全局模板功能推迟到 V2.0）。

### 4.4 预计工作量

| 阶段 | 预计耗时 |
| --- | --- |
| 数据模型 + 迁移 | 0.5 天 |
| 核心服务层 | 0.5 天 |
| 渲染器扩展 | 1 天 |
| API 适配层 | 0.5 天 |
| Worker 接线 | 0.25 天 |
| 前端接线 | 0.5 天 |
| 测试 | 1 天 |
| **合计** | **4.25 天** |

---

## 5. 验收标准

### 5.1 功能验收

| # | 验收项 | 验证方法 |
| --- | --- | --- |
| A1 | 上传 .docx 模板成功，返回模板信息 | API 测试 |
| A2 | 上传非 .docx 文件返回 WORD_TEMPLATE_FILE_UNSUPPORTED | API 测试 |
| A3 | 上传超过 5MB 文件返回 WORD_TEMPLATE_TOO_LARGE | API 测试 |
| A4 | 获取已上传模板返回模板信息 | API 测试 |
| A5 | 获取无模板项目返回 null | API 测试 |
| A6 | 删除模板返回 204 | API 测试 |
| A7 | 重新上传模板覆盖旧模板 | API 测试 |
| A8 | 有模板时生成 Word 使用模板渲染 | 渲染器测试 |
| A9 | 无模板时生成 Word 使用默认渲染 | 渲染器测试（现有测试） |
| A10 | 模板含 `{{project_name}}` 被替换为项目名 | 渲染器测试 |
| A11 | 模板含 `{{#sections}}...{{/sections}}` 循环渲染章节 | 渲染器测试 |
| A12 | 模板文件损坏时降级到默认渲染 + 错误日志 | 渲染器测试 |
| A13 | 模板循环标记不匹配时降级到默认渲染 | 渲染器测试 |
| A14 | 生成 Word 的响应含 `template_used` 字段 | API 测试 |
| A15 | 前端显示模板上传/删除/状态 | 组件测试 |

### 5.2 回归验收

| # | 验收项 | 验证方法 |
| --- | --- | --- |
| R1 | 后端测试全部通过，0 warnings | `python -m pytest` |
| R2 | 前端测试全部通过 | `npx vitest run` |
| A3 | 前端 lint + build 通过 | `npm run lint && npm run build` |
| R4 | 数据库迁移成功 | `alembic upgrade head` |
| R5 | V1.0 完整端到端流程仍可跑通 | Worker e2e 验证脚本 |

### 5.3 边界验收

| # | 验收项 | 验证方法 |
| --- | --- | --- |
| B1 | 路径穿越防护（模板文件路径不可逃逸项目工作区） | 安全测试 |
| B2 | 模板文件大小有上界 | API 测试 A3 |
| B3 | 无模板时行为与 V1.0 完全一致 | 回归测试 R5 |

---

## 6. 风险与降级

| 风险 | 影响 | 缓解措施 |
| --- | --- | --- |
| 模板 .docx 结构复杂导致解析异常 | 渲染失败 | 降级到默认渲染 + 错误日志 |
| python-docx 无法处理某些 Word 高级特性 | 模板样式丢失 | 限制模板复杂度，文档说明支持的特性 |
| 章节循环段落格式错乱 | 排版异常 | 循环块内只支持纯文本和简单表格，不支持嵌套图片 |
| 模板文件过大 | 存储和解析慢 | 5MB 大小限制 |

---

## 7. 文档回写

实现完成后需同步更新：

- [ ] `dev-docs/acceptance.md` — 验收证据
- [ ] `dev-docs/implementation-plan.md` — 实施进度
- [ ] `dev-docs/v1.1.0-planning.md` — SPEC 0010 完成状态
- [ ] `dev-docs/dependency-review.md` — 无新依赖（确认）
- [ ] `dev-docs/decisions/` — 新增决策记录：项目级 Word 模板设计决策

---

## 8. 与现有架构的兼容性

### 8.1 不破坏的合同

- Outline 和 OutlineSection 的结构不变
- Deliverable 和 DeliverableVersion 的结构不变
- 现有 `WordRenderer.render()` 方法签名保留，新增 `render_with_template()` 方法
- 现有 Word 生成 API 响应新增 `template_used` 字段，向后兼容

### 8.2 新增的合同

- `WordTemplate` 数据模型
- 3 个新 API 端点（上传/获取/删除模板）
- `GenerateDeliverableResponse` 新增 `template_used: bool` 字段

### 8.3 不改变的边界

- 仍然是本地单用户 Web MVP
- 仍然从同一份已确认大纲生成
- 生成物仍然可追溯到来源
- 仍然是受控工作区目录
