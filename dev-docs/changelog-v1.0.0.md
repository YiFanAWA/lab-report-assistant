# V1.0.0 详细变更日志

> **版本：** v1.0.0  
> **发布日期：** 2026-07-23  
> **上一版本：** 无（首次正式版本）  
> **提交范围：** `14450a6..a7d78a3`（11 个提交）  
> **变更统计：** 后端 60+ API 端点、前端 8 个工作区视图、606 个测试

---

## 概述

实验报告助手 V1.0.0 是首个正式版本，实现本地单用户 Web MVP 工作台，用证据化工作流辅助学生完成数据分析类实验报告和 PPT。核心价值是让实验要求、资料证据、数据处理、代码执行、图表结果和最终交付物保持一致并可追溯。

V1.0 覆盖了从创建项目到下载 Word/PPT 的完整闭环，包含 6 个开发切片（SPEC 0001-0006）和 V1.0 端到端验收阶段。

---

## 一、新增功能

### 1.1 SPEC 0001：项目工作区与脚手架

**提交：** 初始设置  
**模块：** `server/app/modules/projects/`、`apps/web/`

- 后端 FastAPI + SQLAlchemy + Alembic + SQLite 脚手架
- 前端 React + TypeScript + Vite + React Router + TanStack Query 脚手架
- 项目 CRUD API（创建、列表、详情、状态查询）
- 项目状态机：`DRAFT → REQUIREMENT_PARSED → ... → COMPLETED`
- 前端项目列表页和项目详情页
- Vite 代理配置（`/api` → `http://localhost:8001`）
- 数据库迁移基础（Alembic 0001）

### 1.2 SPEC 0002：实验要求输入与结构化任务单

**提交：** `14450a6`  
**模块：** `server/app/modules/requirements/`

- 实验要求来源：文本输入和 `.docx` 文件上传
- 结构化任务单自动生成（L0-L3 分级）
- L0 基础任务、L1 方法参考、L2 数据分析、L3 完整复现
- 未知项和超范围项识别
- 最小变更记录
- 任务单确认状态推进：`REQUIREMENT_PARSED → REQUIREMENT_CONFIRMED`
- `.docx` 文件解析基础设施（`server/app/infrastructure/documents/`）
- 前端实验要求工作区视图

### 1.3 SPEC 0003：公开资料与证据工作流

**提交：** `ba683db`  
**模块：** `server/app/modules/sources/`、`server/app/modules/evidence/`

- 公开 URL 采集（不绕过登录/验证码/付费墙）
- URL 来源登记和解析状态跟踪
- HTML/PDF 文档解析基础设施
- 证据卡片候选生成（从来源文本提取关键证据）
- 证据卡片确认/拒绝
- 后台任务系统：`FETCH_URL`、`PARSE_DOCUMENT`、`GENERATE_EVIDENCE` 三种任务类型
- Worker 进程独立轮询机制（`python -m worker`）
- 状态推进：`REQUIREMENT_CONFIRMED → SOURCES_COLLECTED → EVIDENCE_CONFIRMED`
- 前端来源工作区和证据工作区视图
- 任务状态轮询（TanStack Query `refetchInterval`）

### 1.4 SPEC 0004：数据集工作区

**提交：** `fba27b5`  
**模块：** `server/app/modules/datasets/`、`server/app/modules/analysis/`

- 数据集上传（CSV/XLSX，支持 pandas 解析）
- 字段类型推断（int/float/string/datetime/bool）
- 字段概览：缺失率、唯一值、样例值、数值统计（min/max/mean/median/std/q1/q3）、字符串高频值
- 数据集质量评分（基于缺失率和重复率）
- 数据集版本管理
- 分析方案候选生成：清洗方案 + 分析方案 + 图表方案
- 分析方案确认/拒绝
- AnalysisPlan 作为字段截断唯一截断点
- 状态推进：`EVIDENCE_CONFIRMED → DATASET_READY → ANALYSIS_PLANNED → ANALYSIS_CONFIRMED`
- 后台任务：`PARSE_DATASET`、`GENERATE_ANALYSIS_PLAN`
- 前端数据集工作区和分析方案工作区视图

### 1.5 SPEC 0005：受控 Python 执行

**提交：** `f30d500`  
**模块：** `server/app/modules/execution/`、`server/app/infrastructure/sandbox/`

- CodeTask 代码任务：从已确认分析方案生成 Python 代码候选
- 代码编辑（CANDIDATE/STALE 可编辑）
- 代码确认/拒绝
- 受控 Python 执行环境：
  - AST 导入验证黑名单：`socket`、`ssl`、`http.client`、`urllib`、`requests`、`__import__()`
  - 工作目录限制（项目受控工作区）
  - 运行时间限制（`EXECUTION_TIMEOUT_SECONDS`）
  - 内存限制（psutil 轮询 0.5s-1s 间隔，`EXECUTION_MEMORY_LIMIT_MB`）
  - 输出大小限制（`EXECUTION_OUTPUT_MAX_BYTES`）
  - 禁止 `shell=True` 和任意宿主机目录访问
- ExecutionRun 执行记录：stdout/stderr/exit_code/duration
- ExecutionArtifact 执行产物：TABLE_CSV（表格）、CHART_PNG（图表）
- 产物文件下载
- 结果确认推进到 `RESULT_CONFIRMED`
- 后台任务：`GENERATE_CODE_TASK`、`EXECUTE_CODE_TASK`
- Worker handler 实际执行（非 mock）
- 前端执行工作区视图（SPEC 0005 前端接线，提交 `b70547f`）：
  - 代码编辑器（深色主题 monospace）
  - 生成/编辑/确认/拒绝/触发执行按钮
  - stdout/stderr 可折叠展示
  - 产物下载链接
  - 3s 轮询执行状态
  - 完成结果确认

### 1.6 SPEC 0006：大纲与交付物

**提交：** `8e098ab`  
**模块：** `server/app/modules/outlines/`

- 统一实验大纲：6 章节（目的、背景、数据、方案、结果、结论）
- 章节来源标记：`source_type`（REQUIREMENT/EVIDENCE/DATASET/ANALYSIS/EXECUTION/SUMMARY）+ `source_ids`
- 大纲候选生成、编辑、确认/拒绝
- Word 交付物生成（python-docx 1.2.0）
- PPT 交付物生成（python-pptx 1.0.2）
- Word 和 PPT 来自同一份已确认大纲（禁止各自从模型临时上下文生成）
- 交付物版本管理：新版本创建保留旧版本，失败不覆盖成功
- STALE 传播链：
  - ExecutionRun 重新执行 → Outline STALE
  - Outline 编辑/重新确认 → Deliverable STALE
- 状态推进：`RESULT_CONFIRMED → OUTLINE_CONFIRMED → GENERATING → COMPLETED`
- 后台任务：`GENERATE_OUTLINE`、`GENERATE_WORD`、`GENERATE_PPT`
- 数据库迁移 0006：outlines、deliverables、deliverable_versions 三表 + 5 索引
- 前端大纲工作区视图（大纲生成/编辑/确认/Word+PPT 生成）
- 前端交付物工作区视图（列表/版本/下载/完成项目）

### 1.7 V1.0 端到端验收

**提交：** `bef1695`、`989b31f`  
**文档：** `dev-docs/e2e-acceptance-report-v1.0.md`

- 浏览器截图验收（browser_use agent 驱动 Chromium）
- Worker 端到端验证脚本（`server/worker_e2e_verify.py`）
- 完整状态机流转验证：`RESULT_CONFIRMED → COMPLETED`
- 真实 Word（37032 bytes）和 PPT（32231 bytes）文件生成验证
- V1.0 端到端验收报告（16 项检查全部通过）

### 1.8 前端测试框架引入

**提交：** `174a92c`  
**决策记录：** [0018-frontend-test-framework.md](decisions/0018-frontend-test-framework.md)

- Vitest 4.1.10 + React Testing Library 测试框架
- jsdom 浏览器环境模拟
- jest-dom matchers（toBeInTheDocument 等）
- 37 个前端单元测试：
  - API 层测试（20 个）：11 个 API 函数的 URL/method/body/响应解析/错误处理
  - 组件测试（17 个）：渲染/生成区域/代码任务卡片/执行记录卡片/完成确认按钮

---

## 二、Bug 修复

### 2.1 SPEC 0006 实现期间修复的 Bug

| # | Bug 描述 | 根因 | 修复 | 提交 |
| --- | --- | --- | --- | --- |
| 1 | outline_provider.py 变量名拼写错误 | 变量名 typo | 修正变量名 | `8e098ab` |
| 2 | worker/handlers.py 缺失导入 | missing import | 补充导入语句 | `8e098ab` |

### 2.2 V1.0 验收阶段修复的 Bug

| # | Bug 描述 | 根因 | 修复 | 提交 |
| --- | --- | --- | --- | --- |
| 3 | ProjectDetailView 缺失 5 个项目状态中文映射 | EXECUTING/EXECUTION_FAILED/RESULT_CONFIRMED/OUTLINE_CONFIRMED/GENERATING 未映射 | 补充中文映射和 ORDERED_STATUSES 索引 | `989b31f` |
| 4 | 前端缺少大纲和交付物入口链接 | ProjectDetailView 未添加入口 | 新增 accentLinkStyle 入口 + isAtOrAfter 门控 | `989b31f` |

### 2.3 SPEC 0005 前端接线期间修复的 Bug

| # | Bug 描述 | 根因 | 修复 | 提交 |
| --- | --- | --- | --- | --- |
| 5 | 前端缺少执行工作区入口 | ProjectDetailView 未添加执行入口 | 新增 showExecutionEntry 入口 | `b70547f` |

### 2.4 前端测试编写期间修复的 Bug

| # | Bug 描述 | 根因 | 修复 | 提交 |
| --- | --- | --- | --- | --- |
| 6 | vi.mock 模块路径与组件 import 路径不一致 | 测试文件在 `__tests__/` 子目录，mock 路径相对路径错误 | 修正 mock 路径与组件实际 import 路径一致 | `174a92c` |
| 7 | getByText 匹配到多个元素 | 项目状态中文映射导致"候选"/"已成功"/"失败"等文本重复 | 改用 `getAllByText` 或更精确的按钮查询 | `174a92c` |

---

## 三、技术债务清理

### 3.1 TD-001：httpx 弃用提示

| 项 | 内容 |
| --- | --- |
| **描述** | StarletteDeprecationWarning：`fastapi.testclient` 使用 `httpx` 已弃用 |
| **影响** | pytest 产生 21 条 warnings |
| **清理方案** | 安装 `httpx2 2.7.0`，dev 依赖新增 `httpx2>=2.0.0` |
| **验证** | pytest warnings 从 21 降至 0 |
| **提交** | `989b31f` |
| **状态** | ✅ 已清理 |

### 3.2 TD-002：pandas datetime 推断 UserWarning

| 项 | 内容 |
| --- | --- |
| **描述** | pandas `to_datetime` 无法推断格式时产生 UserWarning |
| **影响** | pytest 产生 warnings |
| **清理方案** | `dataset_parser.py` 添加 `format="mixed"` 参数 |
| **验证** | pytest warnings 归零 |
| **提交** | `989b31f` |
| **状态** | ✅ 已清理 |

### 3.3 TD-003：浏览器截图验收缺失

| 项 | 内容 |
| --- | --- |
| **描述** | 之前各 SPEC 未完成真实浏览器点击截图验收 |
| **影响** | 验收证据不完整 |
| **清理方案** | 使用 browser_use agent 驱动 Chromium 访问前端 |
| **验证** | 截图保存至 `dev-docs/e2e-screenshots/`，控制台无错误 |
| **提交** | `bef1695` |
| **状态** | ✅ 已清理 |

---

## 四、架构改进

### 4.1 唯一 Owner 边界

- 每个业务语义进入唯一 owner 层（`server/app/modules/xxx/`）
- API 路由只做 HTTP 协议映射
- 前端只展示状态、收集输入、触发命令
- LLM Gateway 统一接入，不写死模型名

### 4.2 STALE 传播链

- ExecutionRun 重新执行 → Outline STALE → Deliverable STALE
- 幂等传播，不重复标记
- 前端展示失效提示

### 4.3 字段截断唯一截断点

- AnalysisPlan 阶段为字段截断唯一截断点
- CodeTask 和 Outline 透传已截断内容，不做二次截断

### 4.4 交付物版本管理

- 每次生成创建新版本，旧版本保留
- 失败不覆盖成功
- 用户可重新生成任意类型交付物

---

## 五、依赖变更

### 5.1 后端新增依赖

| 依赖 | 版本 | 用途 | 引入切片 |
| --- | --- | --- | --- |
| `python-docx` | 1.2.0 | Word 生成 | SPEC 0006 |
| `python-pptx` | 1.0.2 | PPT 生成 | SPEC 0006 |
| `httpx2` | 2.7.0 | 消除弃用警告 | V1.0 验收 |

### 5.2 前端新增依赖

| 依赖 | 版本 | 用途 | 引入阶段 |
| --- | --- | --- | --- |
| `vitest` | 4.1.10 | 测试框架 | V1.0 验收 |
| `@testing-library/react` | ^16.0.0 | 组件测试 | V1.0 验收 |
| `@testing-library/jest-dom` | ^6.0.0 | DOM matchers | V1.0 验收 |
| `@testing-library/user-event` | ^14.0.0 | 交互模拟 | V1.0 验收 |
| `jsdom` | ^25.0.0 | 浏览器环境 | V1.0 验收 |

---

## 六、文件统计

| 类别 | 文件数 | 说明 |
| --- | --- | --- |
| 后端 Python | ~120 | 模块、基础设施、API、迁移、测试 |
| 前端 TypeScript/TSX | ~40 | features、routes、app、shared |
| 文档 | ~35 | dev-docs、SPEC、决策记录 |
| 配置 | ~10 | pyproject.toml、package.json、tsconfig、vite.config 等 |
| **总计** | **~205** | — |

---

## 七、测试统计

| 测试套件 | 测试数 | 状态 |
| --- | --- | --- |
| 后端 pytest | 569 | ✅ 0 warnings |
| 前端 Vitest | 37 | ✅ 全部通过 |
| **总计** | **606** | — |

---

## 八、已知限制（V1.0 边界）

1. **不做真实 DeepSeek 调用**：V1 使用本地规则提供者（LocalRule），真实 LLM 接入推迟到后续版本
2. **不做注册登录**：V1 为本地单用户
3. **不支持 L3 完整复现**：识别为超范围或建议降级
4. **不做 Word 模板完全兼容**：V1 只支持默认模板或简单模板
5. **不做 PPT 动画和复杂排版**
6. **不做在线多用户协作**
7. **医学内容只作教学数据分析**：不提供诊断或治疗建议
8. **公开资料只面向公开 URL**：不绕过访问控制

---

## 九、致谢

感谢项目负责人的严格阶段闸管理和验收标准，确保了 V1.0 的架构清晰、边界明确、测试充分。

---

**版本标签：** `v1.0.0`  
**发布状态：** 待确认
