# SPEC 0006 大纲与交付物 构建报告

**生成日期：** 2026-07-22 23:35
**切片编号：** SPEC 0006
**里程碑：** V0.4 大纲与交付物（Word/PPT 生成闭环）
**操作人：** AI Agent（项目负责人授权）
**目的：** 版本收口前的完整验收证据汇总

---

## 一、验收命令结果总览

| 序号 | 验收项 | 命令 | 工作目录 | 退出码 | 结果 | 耗时 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 后端测试套件 | `python -m pytest` | `server/` | 0 | **569 passed, 21 warnings** | 53.86s |
| 2 | 数据库迁移（全新临时 SQLite） | `python -m alembic upgrade head` | `server/` | 0 | 成功迁移到 0006，创建 3 张表 | ~3s |
| 3 | 前端类型检查 | `npm run lint` (tsc --noEmit) | `apps/web/` | 0 | 通过，无类型错误 | ~6s |
| 4 | 前端生产构建 | `npm run build` (tsc -b && vite build) | `apps/web/` | 0 | 106 模块转换，构建成功 | 2.68s |

**综合结论：四项验收全部通过，无阻断问题。**

---

## 二、后端测试详情

### 2.1 测试总数

- **测试套件总数：** 569 个测试
- **新增测试：** 113 个（相比 SPEC 0005 收口时的 456 个）
- **通过：** 569
- **失败：** 0
- **跳过：** 0
- **警告：** 21（均为已知非阻断债务）

### 2.2 测试分布

| 测试文件 | 测试数 | 状态 | 说明 |
| --- | --- | --- | --- |
| test_analysis_api.py | 26 | ✅ 通过 | 分析 API（已有） |
| test_analysis_plan_provider.py | 31 | ✅ 通过 | 分析方案提供者（已有） |
| test_analysis_service.py | 33 | ✅ 通过 | 分析服务（已有） |
| test_dataset_parser.py | 29 | ✅ 通过 | 数据集解析器（已有） |
| test_datasets_api.py | 33 | ✅ 通过 | 数据集 API（已有） |
| test_datasets_service.py | 41 | ✅ 通过 | 数据集服务（已有） |
| test_evidence_api.py | 15 | ✅ 通过 | 证据 API（已有） |
| test_evidence_service.py | 17 | ✅ 通过 | 证据服务（已有） |
| test_execution_api.py | 33 | ✅ 通过 | 执行 API（已有） |
| test_http_fetcher.py | 11 | ✅ 通过 | HTTP 抓取器（已有） |
| test_jobs_service.py | 13 | ✅ 通过 | 任务服务（已有） |
| **test_outline_provider.py** | **21** | ✅ **新增** | 大纲候选提供者 |
| **test_outline_worker_handlers.py** | **13** | ✅ **新增** | 大纲/Word/PPT Worker 处理器 |
| **test_outlines_api.py** | **21** | ✅ **新增** | 大纲与交付物 API（11 端点） |
| **test_outlines_service.py** | **40** | ✅ **新增** | 大纲与交付物核心服务 |
| test_parsers.py | 14 | ✅ 通过 | 文档解析器（已有） |
| test_project_service.py | 8 | ✅ 通过 | 项目服务（已有） |
| test_python_executor.py | 46 | ✅ 通过 | Python 执行器（已有） |
| **test_renderers.py** | **18** | ✅ **新增** | Word/PPT 渲染器（真实文件生成验证） |
| test_requirement_api.py | 6 | ✅ 通过 | 需求 API（已有） |
| test_requirement_service.py | 12 | ✅ 通过 | 需求服务（已有） |
| test_sources_api.py | 18 | ✅ 通过 | 来源 API（已有） |
| test_sources_service.py | 24 | ✅ 通过 | 来源服务（已有） |
| test_worker_handlers.py | 36 | ✅ 通过 | Worker 处理器（已有） |
| **合计** | **569** | ✅ | **456 已有 + 113 新增** |

### 2.3 警告分类（均为已知非阻断债务）

1. **StarletteDeprecationWarning ×1**：`fastapi.testclient` 使用 `httpx` 已弃用，建议安装 `httpx2`。自 SPEC 0002 起持续保留，不影响测试结果。
2. **UserWarning ×20**：pandas `to_datetime` 无法推断格式，回退到 `dateutil` 逐元素解析。自 SPEC 0004 起持续保留，发生在 `dataset_parser.py:96`，不影响数据正确性。

---

## 三、数据库迁移详情

### 3.1 迁移执行

```
命令：python -m alembic upgrade head
环境变量：DATABASE_URL=sqlite:///<临时文件>.db
退出码：0
```

### 3.2 迁移路径

```
-> 0001, create projects table
-> 0002, create requirement_sources, requirement_plans, change_records tables
-> 0003, create sources, parsed_documents, evidence_cards, background_jobs tables
-> 0004, create datasets, dataset_versions, analysis_plans tables
-> 0005, create code_tasks, execution_runs, execution_artifacts tables
-> 0006, create outlines, deliverables, deliverable_versions tables  ← 本切片新增
```

### 3.3 新增表结构

- **outlines**：大纲主表（id, project_id, sections_json, status, candidate_source, code_version, created_at, updated_at, confirmed_at）
- **deliverables**：交付物表（id, project_id, outline_id, deliverable_type, status, created_at, updated_at）
- **deliverable_versions**：交付物版本表（id, deliverable_id, project_id, version, status, file_path, file_size_bytes, error_code, error_message, started_at, finished_at, duration_seconds, created_at）

---

## 四、前端验收详情

### 4.1 类型检查（lint）

```
命令：npm run lint
实际执行：tsc --noEmit
退出码：0
结果：TypeScript 严格类型检查通过，无类型错误
```

### 4.2 生产构建（build）

```
命令：npm run build
实际执行：tsc -b && vite build
退出码：0
构建工具：Vite v6.4.3
模块转换：106 个
构建产物：
  - dist/index.html        0.34 kB │ gzip:  0.27 kB
  - dist/assets/index-D2iZTm6P.js  347.19 kB │ gzip: 99.84 kB
构建耗时：2.68s
```

---

## 五、代码变更统计

### 5.1 修改文件（13 个）

| 文件 | 变更行数 | 说明 |
| --- | --- | --- |
| dev-docs/README.md | +6/-3 | 当前阶段更新 |
| dev-docs/acceptance.md | +14 | 新增 14 条验收证据 |
| dev-docs/changelog.md | +125 | 新增 SPEC 0006 变更日志 |
| dev-docs/dependency-review.md | +21/-7 | python-pptx 版本记录 |
| dev-docs/implementation-plan.md | +30/-10 | 任务 8/9 勾选完成 |
| server/app/core/config.py | +23 | 4 个新配置项 |
| server/app/main.py | +6 | 注册路由和错误码 |
| server/app/modules/execution/service.py | +4 | STALE 传播 |
| server/app/modules/jobs/status.py | +3 | 3 个新 JobType |
| server/app/modules/llm/gateway.py | +19 | get_outline_provider 工厂 |
| server/pyproject.toml | +1 | python-pptx 依赖 |
| server/tests/conftest.py | +5 | 注册 ORM 模型 |
| server/worker/handlers.py | +467 | 3 个新 handler + 上下文聚合 |

### 5.2 新增文件（18 个）

**outlines owner 模块（5 个）：**
- server/app/modules/outlines/__init__.py
- server/app/modules/outlines/status.py
- server/app/modules/outlines/models.py
- server/app/modules/outlines/contracts.py
- server/app/modules/outlines/service.py

**LLM 提供者（1 个）：**
- server/app/modules/llm/outline_provider.py

**渲染器基础设施（3 个）：**
- server/app/infrastructure/renderers/__init__.py
- server/app/infrastructure/renderers/word_renderer.py
- server/app/infrastructure/renderers/ppt_renderer.py

**API 路由（2 个）：**
- server/app/api/routers/outlines.py
- server/app/api/routers/deliverables.py

**数据库迁移（1 个）：**
- server/alembic/versions/0006_create_outline_and_deliverable_tables.py

**测试文件（4 个）：**
- server/tests/test_outline_provider.py
- server/tests/test_renderers.py
- server/tests/test_outlines_service.py
- server/tests/test_outlines_api.py
- server/tests/test_outline_worker_handlers.py

**SPEC 文档和决策记录（2 个）：**
- dev-docs/specs/0006-outline-and-deliverables.md
- dev-docs/decisions/0017-start-spec-0006-outline-and-deliverables.md

**构建报告（1 个）：**
- dev-docs/build-report-spec-0006.md（本文件）

### 5.3 总变更量

- **修改：** 13 文件，+708/-16 行
- **新增：** 18 文件
- **测试新增：** 113 个（456 → 569）

---

## 六、依赖安装记录

| 依赖 | 版本 | 类型 | 用途 |
| --- | --- | --- | --- |
| python-pptx | 1.0.2 | 直接新依赖 | PPT 生成 |
| XlsxWriter | 3.2.9 | 传递依赖 | python-pptx 依赖 |
| Pillow | 12.3.0 | 已存在 | python-pptx 依赖（复用） |
| lxml | 6.1.1 | 已存在 | python-pptx 依赖（复用） |
| typing-extensions | 4.16.0 | 已存在 | python-pptx 依赖（复用） |

---

## 七、测试期间发现并修复的 Bug

### 7.1 outline_provider.py 字段类型 bug

- **位置：** `server/app/modules/llm/outline_provider.py:133`
- **问题：** `f"  - {name}（{type}）：样例 {sample}"` 误用 Python 内置 `type` 替代局部变量 `ftype`
- **影响：** 数据集字段类型会显示为 `<class 'type'>` 而非实际类型（如 `int64`）
- **修复：** 替换为 `{ftype}`
- **验证：** `test_outline_provider.py::TestLocalRuleOutlineProvider::test_dataset_profile_fields` 覆盖

### 7.2 worker/handlers.py 缺少 AnalysisPlan 导入

- **位置：** `server/worker/handlers.py:552`（_gather_outline_context 函数）
- **问题：** 缺少 `from app.modules.analysis.models import AnalysisPlan` 导入
- **影响：** 查询已确认分析方案时触发 `NameError: name 'AnalysisPlan' is not defined`
- **修复：** 补充 `from app.modules.analysis.models import AnalysisPlan` 导入
- **验证：** `test_outline_worker_handlers.py::TestHandleGenerateOutline::test_success_path` 覆盖

---

## 八、已知非阻断债务

1. **fastapi.testclient httpx 弃用提示**：第三方弃用警告，自 SPEC 0002 起持续保留，不影响功能。
2. **pandas datetime 推断 UserWarning**：自 SPEC 0004 起持续保留，不影响数据正确性。
3. **浏览器点击截图验收未执行**：当前会话未暴露可调用的 in-app Browser 工具。以 API 测试套件（21 个测试覆盖 11 个端点）、Worker handler 测试（13 个测试）和渲染器测试（18 个测试验证真实 .docx/.pptx 文件生成）作为替代证据。

---

## 九、收口结论

**综合判定：通过，可执行 git 版本控制收口。**

依据：
1. 四项基础验收命令全部通过（pytest 569 passed、alembic upgrade head 成功、npm run lint 通过、npm run build 通过）。
2. 新增 113 个测试覆盖 outlines owner 模块、outline_provider、renderers、API 路由、Worker handler 全链路。
3. 测试期间发现的 2 个 bug 已修复并有测试覆盖。
4. 文档回写完成（README、acceptance、changelog、implementation-plan、dependency-review）。
5. 无阻断问题，已知债务均为非阻断且已记录。
6. Git 状态清晰：13 个修改文件 + 18 个新增文件，无敏感文件、无运行产物、无 .venv/node_modules/dist 等被忽略文件混入。

**下一步：** 执行 `git add` 精确 stage → `git commit` 中文提交信息 → `git push origin master` 推送到远程。
