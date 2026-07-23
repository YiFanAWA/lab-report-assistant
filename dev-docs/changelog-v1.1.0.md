# V1.1.0 版本发布说明（草稿）

> **版本：** v1.1.0  
> **发布日期：** 2026-07-23  
> **上一版本：** v1.0.0  
> **提交范围：** `v1.0.0..HEAD`（15 个提交）  
> **变更统计：** 后端 704 测试 + 前端 411 测试 = 1115 个测试（新增 509 个）  
> **文档状态：** 草稿，待项目负责人确认后发布

---

## 概述

实验报告助手 V1.1.0 是 V1.0 的增量改进版本，聚焦于填补 V1.0 的功能缺口和提升候选质量。V1.1.0 **不改变产品边界**（仍是本地单用户 Web MVP）和**架构主线**（仍是唯一 owner + API 适配 + 前端接线），不引入新的业务模块。

V1.1.0 包含 6 个 SPEC：

| SPEC | 标题 | 状态 |
| --- | --- | --- |
| SPEC 0007 | 真实 DeepSeek LLM 接入 | ✅ 已完成 |
| SPEC 0008 | 部署文档与运维指南 | ✅ 已完成 |
| SPEC 0009 | 前端测试覆盖补全 | ✅ 已完成 |
| SPEC 0010 | Word 模板支持 | ✅ 已完成 |
| SPEC 0011 | PPT 配置选项 | ✅ 已完成 |
| SPEC 0012 | 数据保留周期配置 | ✅ 已完成 |

---

## 一、新增功能

### 1.1 SPEC 0007：真实 DeepSeek LLM 接入

**提交：** `36e39f9`  
**模块：** `server/app/infrastructure/llm/`、`server/app/modules/llm/`

V1.0 最大的功能缺口是候选生成全部依赖 LocalRule 本地规则，候选质量受限。V1.1.0 接入真实 DeepSeek LLM，5 个业务模块全部支持 LLM 优先 + LocalRule 降级。

**新增能力：**
- DeepSeek 客户端（`deepseek_client.py`）：基于 httpx2 调用 DeepSeek Chat API，支持超时、重试、温度配置
- 5 个 LLM Provider 替换 LocalRule：
  - `RequirementDraftProvider`：实验要求拆解
  - `EvidenceCardProvider`：证据卡片提取
  - `AnalysisPlanProvider`：分析方案候选
  - `CodeTaskProvider`：Python 代码生成
  - `OutlineProvider`：实验大纲生成
- 每个 Provider 采用 LLM 优先策略：LLM 可用时返回 LLM 候选，LLM 不可用时自动降级到 LocalRule
- Pydantic 严格结构化输出校验：LLM 返回的 JSON 必须通过 Pydantic 模型校验，防止幻觉导致的非法输出
- 新增环境变量：`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_TIMEOUT_SECONDS`、`DEEPSEEK_MAX_RETRIES`、`DEEPSEEK_TEMPERATURE`
- 每个 Provider 可独立切换 `local_rule` / `deepseek`

**不做：**
- 不接入其他 LLM 供应商（V1.1.0 只接 DeepSeek）
- 不做流式输出（保持异步任务模式）
- 不做 LLM 调用缓存优化

**测试：** 新增 36 个后端测试（deepseek_client 11 + deepseek_providers 25）。

### 1.2 SPEC 0008：部署文档与运维指南

**提交：** `4da4a1b`  
**文件：** 根目录 `README.md`

V1.0 遗留的部署文档缺失问题。新增面向首次使用者的完整部署文档。

**新增内容：**
- 环境要求（Python 3.10+、Node 18+、SQLite）
- 后端启动步骤（venv 创建、pip install、alembic upgrade、uvicorn 启动）
- 前端启动步骤（npm install、npm run dev）
- Worker 启动步骤（python -m worker）
- 完整环境变量清单（核心配置、LLM 配置、Provider 切换、Worker、采集、沙箱、数据集、保留周期）
- 5 个配置示例（LocalRule 模式、全量 LLM、部分 LLM、自定义路径、.env 文件）
- 常见排障（端口冲突、SQLite 锁定、Worker 不领取、DeepSeek 失败、数据集上传失败）
- 数据保留与清理章节（SPEC 0012）

### 1.3 SPEC 0009：前端测试覆盖补全

**提交：** `c8bbdf9`、`32646d5`、`5782499`、`1e5e5c5`、`323b723`、`2a87626`、`e70bb51`  
**模块：** `apps/web/src/`（8 个 API 模块 + 11 个 Workspace 组件）

V1.0 前端测试仅覆盖 execution 模块（37 个测试），其余 7 个工作区无前端测试。V1.1.0 补全全部前端测试。

**新增测试覆盖：**
- API 层测试（8 个模块）：
  - `features/projects/api.ts`（10 测试）
  - `features/requirements/api.ts`（19 测试）
  - `features/sources/api.ts`（16 测试）
  - `features/evidence/api.ts`（17 测试）
  - `features/datasets/api.ts`（22 测试）
  - `features/analysis/api.ts`（19 测试）
  - `features/outlines/api.ts`（33 测试）
  - `features/jobs/api.ts`（9 测试）
- 组件测试（11 个 Workspace 视图）：
  - `ProjectListView`（11 测试）
  - `ProjectDetailView`（39 测试，覆盖 14 种状态中文标签 + 8 个入口门控）
  - `RequirementWorkspaceView`（35 测试）
  - `SourcesWorkspaceView`（24 测试）
  - `EvidenceWorkspaceView`（22 测试）
  - `DatasetWorkspaceView`（25 测试）
  - `AnalysisWorkspaceView`（21 测试）
  - `OutlineWorkspaceView`（24 测试）
  - `DeliverableWorkspaceView`（20 测试）

**测试统计：** 前端测试从 37 个增加到 411 个（新增 374 个）。

### 1.4 SPEC 0010：Word 模板支持

**提交：** `fa35b79`  
**模块：** `server/app/modules/outlines/`、`server/app/infrastructure/renderers/word_renderer.py`

V1.0 只支持默认 Word 模板，无法匹配老师特定模板。V1.1.0 支持项目级上传 `.docx` 模板。

**新增能力：**
- 项目级 Word 模板上传（每个项目可绑定不同模板，覆盖式存储，SHA-256 哈希校验）
- Jinja2 风格占位符支持：
  - 封面变量：`{{project_name}}`、`{{project_topic}}`、`{{generated_date}}`
  - 章节循环：`{{#sections}}...{{/sections}}`（文本重建方式渲染循环块）
- `WordTemplate` ORM 实体 + Alembic 迁移 0007（唯一约束 `uq_word_templates_project_id`）
- 4 个 API 端点：上传、获取、删除、下载模板
- `render_with_template` 渲染方法：有模板用模板，无模板用默认
- 模板渲染失败降级链：
  - 文件缺失 → `WORD_TEMPLATE_FILE_MISSING` → 降级默认渲染
  - 解析失败 → `WORD_TEMPLATE_PARSE_FAILED` → 降级默认渲染
  - 循环块无效 → `WORD_TEMPLATE_SECTION_BLOCK_INVALID` → 降级默认渲染
- Worker handler 降级策略：模板渲染失败时降级 + warning 日志
- 前端 `OutlineWorkspaceView` 新增 `WordTemplateSection` 组件（上传/下载/删除 UI + 占位符说明）
- 新增环境变量：`WORD_TEMPLATE_MAX_SIZE_BYTES`（默认 5MB）

**测试：** 新增 18 个后端测试（渲染器 6 + API 12）+ 8 个前端 API 测试。

### 1.5 SPEC 0011：PPT 配置选项

**提交：** `8b34b69`  
**模块：** `server/app/modules/outlines/`、`server/app/infrastructure/renderers/ppt_renderer.py`

V1.0 PPT 只支持基础版式，无法配置页数和样式。V1.1.0 新增 PPT 配置选项。

**新增能力：**
- PPT 生成时支持配置：
  - 目标页数（5-20 页，Pydantic ge/le 校验）
  - 主题色（6 个预设色板，非预设色降级到默认色）
  - 全局图表开关（`include_charts`，默认 True）
- 页数控制：`available_slots = max(0, target - 2)`（减去标题页和总结页），内容页超过槽位时合并章节，不足时保持实际页数
- 主题色应用：`_apply_theme_color` 应用到标题 run 的 `font.color.rgb`
- 配置不持久化：每次生成时传参，写入 job `input_data`，不落库 `DeliverableVersion`
- API 向后兼容：无 body 时使用默认配置
- Worker handler 降级：config 渲染失败时降级到默认渲染 + warning 日志
- 前端 `OutlineWorkspaceView` 新增 PPT 配置表单（页数输入/色板选择/图表开关）

**预设色板：** 6 个主题色（`PPT_THEME_COLORS` 常量集合）。

**测试：** 新增 23 个后端测试（渲染器 15 + API 8）。

### 1.6 SPEC 0012：数据保留周期配置

**提交：** `efac98b`  
**模块：** `server/app/core/config.py`、`server/app/modules/jobs/service.py`、`server/scripts/`

V1.0 数据永久保留，无清理机制。V1.1.0 新增数据保留周期配置和清理脚本。

**新增能力：**
- `DATA_RETENTION_DAYS` 环境变量：
  - `0`（默认）：永久保留，不清理
  - `>0`：保留 N 天，超过 N 天未更新的项目进入清理列表
  - 负值/非数字/浮点数：降级到 0（永久保留）
- 清理脚本 `server/scripts/cleanup_expired_data.py`：
  - 双模式：`--dry-run`（默认，只输出报告）和 `--execute`（实际删除）
  - 同时指定 `--dry-run --execute` 时采用 dry-run（安全优先）
  - 基于 `Project.updated_at` 判断过期（活跃项目自动重置计时器）
  - RUNNING job 保护：有 PENDING/RUNNING 后台任务的项目跳过清理
  - 18 张表级联删除（按外键依赖顺序从叶子到根删除）
  - 文件系统目录清理（`shutil.rmtree(ignore_errors=True)` + 残留检查）
  - `run_cleanup` 支持可选 `db` 参数注入（CLI 用 `settings.database_url`，测试用内存 SQLite）
- `has_active_jobs` 查询方法（jobs service 新增）：检查项目活跃任务

**测试：** 新增 58 个后端测试。

**测试覆盖：**
| 测试文件 | 测试数 | 覆盖范围 |
| --- | --- | --- |
| `test_data_retention_config.py` | 10 | 配置降级（默认/正整数/负值/非数字/浮点/空字符串） |
| `test_cleanup_safety.py` | 18 | has_active_jobs 基础/混合/边界 + cleanup_project 保护接线 |
| `test_cleanup_expired_data.py` | 14 | 过期判断 + 级联删除 + 文件系统清理 |
| `test_cleanup_script.py` | 10 | 参数解析 + run_cleanup 输出 |
| `test_cleanup_integration.py` | 6 | 端到端清理/dry-run/混合场景/完整性/活跃重置/RUNNING 保护 |

---

## 二、Bug 修复

### 2.1 SPEC 0010 前端 lint 修复

| # | Bug 描述 | 根因 | 修复 |
| --- | --- | --- | --- |
| 1 | 8 个前端测试文件共 215 处 `global.fetch` 类型告警 | TypeScript 严格模式下 `global` 未定义 | 批量替换为 `(globalThis as any).fetch` |
| 2 | `analysis/api.test.ts` 类型错误 | `UpdateAnalysisPlanRequest` 字段 `string \| null` 与 `AnalysisPlan` 字段 `string` 不兼容 | 用非空断言修复 |

### 2.2 SPEC 0012 测试代码修复

| # | Bug 描述 | 根因 | 修复 |
| --- | --- | --- | --- |
| 3 | `ExecutionArtifact` 插入失败 | 测试 fixture 缺少 `file_size_bytes` 和 `name`（NOT NULL） | 补充必填字段 |
| 4 | `EvidenceCard` 插入失败 | 测试 fixture 缺少 `status` 和 `candidate_source`（NOT NULL） | 补充必填字段 |
| 5 | 集成测试 `run_cleanup` 看不到测试数据 | `run_cleanup` 自建数据库引擎，与测试内存 SQLite 隔离 | 重构为接受可选 `db` 参数注入 |

> 注：Bug 3-5 均为测试代码问题，不影响生产功能。

---

## 三、架构改进

### 3.1 LLM Gateway 统一接入

- 5 个 Provider 统一通过 LLM Gateway 接入，不直接调用 DeepSeek SDK 或写死模型名
- LLM 优先 + LocalRule 降级策略统一，不阻断业务流程
- Pydantic 结构化输出校验作为 LLM 幻觉防线

### 3.2 Word 模板降级链

- 模板缺失/解析失败/循环块无效三种失败场景均有降级路径
- Worker handler 降级时记录 warning 日志，`template_used` 字段反映实际使用的模板

### 3.3 PPT 配置不持久化

- PPT 配置（页数/主题色/图表开关）不落库，每次生成时传参
- 避免 DeliverableVersion 表膨胀，配置与版本解耦

### 3.4 清理脚本可测试性

- `run_cleanup` 支持可选 `db` 参数注入，CLI 与测试共用同一套清理逻辑
- 符合现有服务的 `db` 注入模式，不私造数据库会话

---

## 四、依赖变更

### 4.1 运行时依赖

**V1.1.0 无新增运行时依赖。** 全部复用 V1.0 已有依赖：

| 依赖 | 版本 | 用途 | 引入版本 |
| --- | --- | --- | --- |
| `httpx2` | 2.7.0 | DeepSeek HTTP 客户端（SPEC 0007 复用） | V1.0 |
| `python-docx` | 1.2.0 | Word 模板渲染（SPEC 0010 复用） | V1.0 |
| `python-pptx` | 1.0.2 | PPT 配置渲染（SPEC 0011 复用） | V1.0 |

### 4.2 开发依赖

无新增开发依赖。Vitest + React Testing Library 在 V1.0 验收阶段已引入，SPEC 0009 复用。

---

## 五、测试统计

| 测试套件 | V1.0.0 | V1.1.0 | 新增 | 状态 |
| --- | --- | --- | --- | --- |
| 后端 pytest | 569 | 704 | +135 | ✅ 0 warnings |
| 前端 Vitest | 37 | 411 | +374 | ✅ 全部通过 |
| **总计** | **606** | **1115** | **+509** | — |

### 后端新增测试分布

| SPEC | 新增测试数 | 累计后端测试 |
| --- | --- | --- |
| SPEC 0007 | 36 | 605 |
| SPEC 0009 | 0（前端测试） | 605 |
| SPEC 0010 | 18 | 623 |
| SPEC 0011 | 23 | 646 |
| SPEC 0012 | 58 | 704 |

---

## 六、已知限制（V1.1.0 边界）

1. **不做自动清理定时任务**：SPEC 0012 数据保留为手动执行清理脚本，不自动定时清理
2. **不做项目级保留策略**：DATA_RETENTION_DAYS 为全局配置，不支持项目级差异化
3. **不做 LLM 调用缓存**：每次调用 DeepSeek 均发起真实请求
4. **不做流式 LLM 输出**：保持异步任务模式，LLM 调用通过 Worker 异步处理
5. **不做 Word 模板预览**：模板预览推迟到 V2.0
6. **不做 PPT 动画和复杂排版**：保持基础版式
7. **不做任意 hex 色值输入**：PPT 主题色使用 6 个预设色板
8. **不做每张图表单独配置**：PPT 图表使用全局开关
9. **真实 DeepSeek 调用需要有效 API Key**：无 Key 时走 LocalRule 降级

---

## 七、升级指南

### 7.1 从 V1.0.0 升级

V1.1.0 无破坏性变更，升级步骤简单：

```bash
# 1. 拉取最新代码
git pull origin master

# 2. 更新后端依赖（无新增依赖，确认即可）
cd server
.venv\Scripts\activate
pip install -e ".[dev]"

# 3. 执行数据库迁移（新增 0007 word_templates 表）
.venv\Scripts\python.exe -m alembic upgrade head

# 4. 更新前端依赖（无新增依赖）
cd ../apps/web
npm install

# 5. 重启服务
# 后端 + Worker + 前端
```

### 7.2 启用真实 DeepSeek LLM（可选）

```bash
# 配置 API Key
$env:DEEPSEEK_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"

# 启用各模块 LLM（可选启用部分模块）
$env:REQUIREMENT_DRAFT_PROVIDER = "deepseek"
$env:EVIDENCE_CARD_PROVIDER = "deepseek"
$env:ANALYSIS_PLAN_PROVIDER = "deepseek"
$env:CODE_TASK_PROVIDER = "deepseek"
$env:OUTLINE_PROVIDER = "deepseek"
```

### 7.3 配置数据保留周期（可选）

```bash
# 设置保留 30 天（超过 30 天未更新的项目可被清理）
$env:DATA_RETENTION_DAYS = "30"

# 手动执行清理（先 dry-run 确认）
cd server
python -m scripts.cleanup_expired_data --dry-run
python -m scripts.cleanup_expired_data --execute
```

### 7.4 使用 Word 模板（可选）

在项目大纲工作区上传 `.docx` 模板文件，模板支持 Jinja2 风格占位符：
- 封面变量：`{{project_name}}`、`{{project_topic}}`、`{{generated_date}}`
- 章节循环：`{{#sections}}...{{/sections}}`

### 7.5 配置 PPT 生成选项（可选）

在大纲工作区生成 PPT 时，可配置：
- 目标页数（5-20 页）
- 主题色（6 个预设色板）
- 是否包含图表（全局开关）

---

## 八、回归测试

V1.1.0 发布前需执行完整回归测试，详见 [v1.1.0-regression-test-plan.md](v1.1.0-regression-test-plan.md)。

**关键回归点：**
- 后端 704 测试全部通过，0 warnings
- 前端 411 测试全部通过
- V1.0 端到端主链路（创建项目 → 下载 Word/PPT）完整跑通
- 6 个 SPEC 专项回归全部通过

---

## 九、致谢

感谢项目负责人的严格阶段闸管理和验收标准。V1.1.0 的 6 个 SPEC 均遵循"先编写并确认 SPEC → 项目负责人批准 → 测试先行 → 实现 → 验收 → 文档回写 → git 收口"的阶段闸流程。

---

**版本标签：** `v1.1.0`（待创建）  
**发布状态：** 草稿，待项目负责人确认
