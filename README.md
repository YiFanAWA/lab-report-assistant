# 实验报告助手

实验报告助手是一个本地单用户 Web 工作台，帮助学生把实验要求、公开资料、数据分析、代码执行、图表结果和最终交付物串成一条可追溯的证据链。

它解决的不是“让模型直接代写一份报告”，而是把实验报告拆成可检查、可确认、可复用的中间产物：结构化任务单、来源与证据卡片、数据集版本、分析方案、受控执行记录、图表索引、统一大纲，以及由同一份事实链生成的 Word/PDF/PPT。

> 当前仓库处于代码阶段，包含多个已实现但尚未统一发布为新版本标签的开发切片。项目内部阶段、验收和决策以 [dev-docs/README.md](dev-docs/README.md) 为准。

## 项目适合什么场景

当前主线面向数据分析类实验，首个标准演示课题是“胃病数据分析”。典型使用者可以：

- 将实验要求、教师说明或本地 .docx 资料整理为结构化任务单；
- 添加公开可访问 URL、PDF 或本地辅助资料，并生成带来源位置的证据卡片；
- 上传 CSV/XLSX 数据集，查看字段概览、数据质量和分析方案候选；
- 通过本地规则或统一 LLM Gateway 生成分析代码任务，再在应用托管的受控 Python 环境中执行；
- 检查表格输出、图表输出和执行日志，确认结果后生成统一实验大纲；
- 从同一份已确认大纲、证据卡片、执行记录和图表索引生成 Word、PDF 与 PPT；
- 在交付物审阅台中查看版本、追溯关系和最终文件。

## 核心工作流

    创建项目
      -> 输入实验要求并整理任务单
      -> 添加公开资料与证据卡片
      -> 上传数据集并查看字段/质量概览
      -> 确认分析方案
      -> 生成并确认代码任务
      -> 受控 Python 执行
      -> 检查表格、图表和执行记录
      -> 生成并确认统一实验大纲
      -> 生成 Word / PDF / PPT
      -> 交付物审阅、版本下载和追溯

每个需要用户确认的阶段都保留状态、候选来源、错误原因和关联记录。模型只负责产生可校验候选，不能直接替代业务状态或用户确认。

## 已覆盖的能力

- 实验要求结构化、任务单和 L0-L3 范围判断；
- 文本、.docx、公开 URL/PDF 来源与证据卡片；
- CSV/XLSX 数据集版本、字段概览、质量检查和分析方案；
- local_rule/deepseek Provider、LLM Gateway 和 SSE 流式候选生成；
- Worker 后台任务、受控 Python 执行、日志和执行产物；
- 统一实验大纲，以及 Word、PDF、PPT 交付物版本；
- PPT 主题、版式、图表布局、语义选图和科学示意图组件；
- 交付物审阅台、Docker Compose 和 Windows x64 portable bundle。

## 产品边界

- 只做本地单用户 Web MVP，不做注册登录、在线多用户账号体系和多人协作；
- 只面向公开可访问 URL 和用户提供的本地辅助文件，不绕过登录、验证码、付费墙或访问控制；
- 不把 L1/L2 方法参考包装成 L3 完整论文复现；
- 医学内容只用于教学性数据分析，不提供诊断或治疗建议；
- Word、PDF、PPT 必须来自同一份已确认大纲、证据卡片、执行记录和图表索引；
- 应用产生可审阅、可追溯的候选和交付物，不替用户承担学术判断或数据真实性责任。

## 技术架构

    apps/web/                  React + TypeScript + Vite 工作台
            │ REST API / SSE
            ▼
    server/app/api/            FastAPI 协议适配层
            │
            ▼
    server/app/modules/        项目、要求、来源、数据、执行、大纲、交付物等业务 Owner
            │
            ├─ modules/llm/              统一 LLM Gateway 与 Provider
            ├─ infrastructure/database/ SQLAlchemy + Alembic + SQLite
            ├─ infrastructure/documents/ 文档解析适配器
            ├─ infrastructure/renderers/ Word/PDF/PPT/科研示意图渲染器
            └─ infrastructure/sandbox/   受控 Python 执行器
            │
            ▼
    server/worker/             独立 Worker，领取数据库后台任务

API、UI、Worker 和 Prompt 只做协议映射、展示或候选生成，不私造任务状态、权限结论、实验结论或交付物事实。

## 目录结构

    .
    ├─ apps/web/                  前端 React/Vite 应用
    ├─ server/app/api/            FastAPI 路由与结构化错误映射
    ├─ server/app/modules/        业务模块与领域合同
    ├─ server/app/infrastructure/ 数据库、解析、渲染、沙箱
    ├─ server/worker/             后台任务 Worker
    ├─ server/tests/              后端服务/API/渲染/安全边界测试
    ├─ packaging/windows/         Windows portable bundle 构建入口
    ├─ dev-docs/                  内部架构、SPEC、验收和决策真源
    ├─ docker-compose.yml         Docker Compose 编排
    └─ .env.example               Docker 环境变量模板

## 本地开发启动

环境要求：Python 3.10+、Node.js 22+、npm 10+、SQLite；Docker 运行方式需要 Docker Desktop。

安装后端：

    cd server
    python -m venv .venv
    .venv/Scripts/python.exe -m pip install --upgrade pip setuptools wheel
    .venv/Scripts/python.exe -m pip install -e ".[dev]"

如需执行 pandas、NumPy、SciPy、scikit-learn、Matplotlib、Seaborn 分析代码：

    .venv/Scripts/python.exe -m pip install -e ".[dev,analysis]"

启动 API：

    cd server
    .venv/Scripts/python.exe -m alembic upgrade head
    .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001

后端地址为 http://127.0.0.1:8001，健康检查为 http://127.0.0.1:8001/health，FastAPI 文档为 http://127.0.0.1:8001/docs。

启动前端：

    cd apps/web
    npm install
    npm run dev

前端默认地址为 http://localhost:5173，/api 请求代理到后端。

启动 Worker：

    cd server
    .venv/Scripts/python.exe -m worker.main

开发时建议同时运行 API、前端和 Worker。

## Docker 启动

    Copy-Item .env.example .env
    docker compose build
    docker compose up -d

| 服务 | 地址 | 用途 |
| --- | --- | --- |
| 前端 | http://localhost | 用户工作台 |
| 后端 | http://localhost:8001 | API 与健康检查 |
| 健康检查 | http://localhost:8001/health | 容器存活检查 |

Compose 启动 backend、worker、frontend 三个服务。SQLite 数据库与项目数据分别使用 db-data、project-data 卷；docker compose down 保留数据，docker compose down -v 会删除卷内数据。

    docker compose logs -f backend
    docker compose logs -f worker
    docker compose down

## Windows 一键运行包

Windows x64 portable bundle 让用户无需安装 Python、Node.js 或 Docker，即可启动本地后端、Worker 并打开浏览器工作台。

构建说明见 [packaging/windows/README.md](packaging/windows/README.md)：

    server/.venv/Scripts/python.exe -m pip install -r packaging/windows/requirements-build.txt
    server/.venv/Scripts/python.exe packaging/windows/build_windows_bundle.py

构建前需要准备官方 Windows x64 LibreOffice headless runtime，用于 DOCX 到 PDF 的派生。构建结果 server/.tmp/windows-package/ 属于本地产物，不应提交。

## 环境变量

完整模板见 [.env.example](.env.example)，命令索引见 [dev-docs/commands.md](dev-docs/commands.md)。

| 变量 | 默认/示例 | 说明 |
| --- | --- | --- |
| APP_ENV | local / docker | 运行环境标识 |
| DATABASE_URL | SQLite | 数据库连接字符串 |
| PROJECT_DATA_ROOT | server/data/projects | 受控项目工作区根目录 |
| DEEPSEEK_API_KEY | 空 | 使用真实 DeepSeek 时配置；不要提交 |
| DEEPSEEK_BASE_URL | https://api.deepseek.com | LLM 服务地址 |
| *_PROVIDER | local_rule | 各模块选择 local_rule 或 deepseek |
| LLM_CACHE_ENABLED | false | 是否启用 LLM 调用缓存 |
| WORKER_POLL_INTERVAL_SECONDS | 1 | Worker 轮询间隔 |
| JOB_MAX_RETRIES | 2 | 后台任务最大重试次数 |
| SOURCE_FETCH_MAX_SIZE_BYTES | 10485760 | 单次来源采集大小上限 |
| EXECUTION_TIMEOUT_SECONDS | 30 | Python 执行超时 |
| EXECUTION_MEMORY_LIMIT_MB | 1024 | Python 执行内存上限 |
| EXECUTION_OUTPUT_MAX_BYTES | 10485760 | 执行输出大小上限 |
| DATASET_MAX_SIZE_BYTES | 52428800 | 数据集上传大小上限 |
| DELIVERABLE_MAX_SIZE_BYTES | 52428800 | 交付物大小上限 |
| DATA_RETENTION_DAYS | 0 | 0 表示默认永久保留 |

可独立切换的 Provider：REQUIREMENT_DRAFT_PROVIDER、EVIDENCE_CARD_PROVIDER、ANALYSIS_PLAN_PROVIDER、CODE_TASK_PROVIDER、OUTLINE_PROVIDER。真实密钥只能通过本地 .env 或宿主机环境变量传入。

## API 与前端请求

后端 REST API 使用 /api 前缀并按项目聚合资源：

| 领域 | 入口示例 |
| --- | --- |
| 项目 | /api/projects |
| 实验要求 | /api/projects/{project_id}/requirements |
| 公开来源 | /api/projects/{project_id}/sources |
| 证据 | /api/projects/{project_id}/evidence |
| 数据集 | /api/projects/{project_id}/datasets |
| 分析方案 | /api/projects/{project_id}/analysis |
| 代码任务 | /api/projects/{project_id}/code-tasks |
| 执行记录 | /api/projects/{project_id}/execution-runs |
| 大纲与交付物 | /api/projects/{project_id}/outline、/api/projects/{project_id}/deliverables |
| 后台任务 | /api/projects/{project_id}/jobs |

任务单、证据卡片、分析方案、代码任务和大纲提供 stream-generate SSE 入口。前端通过 TanStack Query 管理请求、缓存、刷新和状态轮询。

## 测试与验收

后端命令在 server/ 目录执行：

    cd server
    .venv/Scripts/python.exe -m alembic upgrade head
    .venv/Scripts/python.exe -m pytest

前端命令在 apps/web/ 目录执行：

    cd apps/web
    npm run test
    npm run lint
    npm run build

当前代码快照已验证：后端 1269 passed，前端 lint 和 build 通过。UI 变化还应进行真实浏览器点击或截图验收；截图、渲染交付物和日志属于验收证据，不自动纳入源代码提交。

更多门禁和停止条件见 [dev-docs/acceptance.md](dev-docs/acceptance.md)。

## 内部文档入口

| 文档 | 内容 |
| --- | --- |
| [dev-docs/README.md](dev-docs/README.md) | 当前阶段、真源索引和工程入口 |
| [dev-docs/project-charter.md](dev-docs/project-charter.md) | 产品定位、目标与边界 |
| [dev-docs/architecture.md](dev-docs/architecture.md) | 架构主线、Owner 和禁止路径 |
| [dev-docs/commands.md](dev-docs/commands.md) | 安装、启动、测试和版本收口命令 |
| [dev-docs/acceptance.md](dev-docs/acceptance.md) | 验收证据、停止条件和已知债务 |
| [dev-docs/specs/](dev-docs/specs/) | 开发切片的需求、合同和验收标准 |
| [dev-docs/decisions/](dev-docs/decisions/) | 产品、架构和切片启动决策 |
| [packaging/windows/README.md](packaging/windows/README.md) | Windows portable bundle 构建边界 |
| [server/app/assets/scientific/README.md](server/app/assets/scientific/README.md) | 科研图形资产许可和归属 |

## 当前状态与后续工作

项目已完成从要求输入到证据、数据、执行、大纲和交付物的主链路建设，并持续增强论文复核、学术排版、图表语义选择、科研示意图、统一工作台和 Windows 便携运行能力。

当前仍需按内部 SPEC 逐项完成负责人确认、真实环境视觉验收和版本标签收口。论文复核类案例必须保持“教学性论文复核报告（非独立研究论文）”定位，不能将局部数据复核描述成原论文完整复现或临床结论。

## 贡献与协作约定

开始修改前请先阅读 [AGENTS.md](AGENTS.md) 和 [dev-docs/README.md](dev-docs/README.md)。

- 先确认当前真源、Owner、合同和验收边界，再进入实现；
- API、UI、Worker 和 Prompt 不得私造业务真相；
- 生成目录、运行产物、本地数据库、密钥和虚拟环境不得提交；
- 提交前只 stage 当前任务相关的明确路径，不使用 git add .；
- 声称通过、完成或可发布时，必须给出本轮实际运行过的命令和证据。
