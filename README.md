# 实验报告助手

本地单用户 Web MVP 工作台，用证据化工作流辅助学生完成数据分析类实验报告和 PPT。

## 快速启动

### 环境要求

- Python 3.10+
- Node.js 18+
- SQLite（Python 内置，无需单独安装）

### 1. 启动后端

```bash
cd server
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001
```

后端默认运行在 `http://localhost:8001`。

### 2. 启动前端

```bash
cd apps/web
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`，`/api` 请求自动代理到后端。

### 3. 启动 Worker 进程

```bash
cd server
.venv\Scripts\activate
python -m worker.main
```

Worker 轮询后台任务表，处理 URL 采集、文档解析、LLM 调用、Python 执行、Word/PPT 生成等异步任务。

## Docker 启动（推荐）

### 前置要求

- Docker Desktop（含 Docker Engine + Docker Compose）

### 一键启动

```bash
# 1. 复制环境变量模板（首次使用）
cp .env.example .env

# 2. 构建镜像并启动三服务（backend + worker + frontend）
docker compose build
docker compose up -d

# 3. 访问应用
# 前端：http://localhost
# 后端 API：http://localhost:8001
# 健康检查：http://localhost:8001/health
```

### 端口说明

| 服务 | 容器内端口 | 宿主机端口 | 说明 |
| --- | --- | --- | --- |
| frontend（nginx） | 80 | 80 | 前端入口，`/api` 请求反向代理到 backend |
| backend（uvicorn） | 8001 | 8001 | 与 `config.py` 默认值一致，704 测试基于此端口 |
| worker | — | — | 后台任务进程，不对外暴露端口 |

> 端口被占用时，修改 `docker-compose.yml` 中 `ports` 的左侧数字（宿主机端口），容器内端口保持不变。

### 验证 Worker 在容器内正常工作

```bash
# 运行 Worker 容器内验证脚本
powershell -ExecutionPolicy Bypass -File server/scripts/docker_worker_verify.ps1
```

脚本验证：worker 容器运行状态、worker 日志显示启动、`worker.main` 在容器内可导入、worker command 与 SPEC 0013 一致。

### 常用命令

```bash
# 查看日志
docker compose logs -f backend
docker compose logs -f worker

# 停止服务（保留数据）
docker compose down

# 停止并删除数据（慎用）
docker compose down -v

# 重新构建（代码变更后）
docker compose build && docker compose up -d
```

### 数据持久化

| 数据卷 | 容器内路径 | 说明 |
| --- | --- | --- |
| `db-data` | `/app/data/db` | SQLite 数据库文件 |
| `project-data` | `/app/data/projects` | 数据集、交付物、Word 模板等 |

> 容器重建后数据不丢失。`docker compose down` 保留数据，`docker compose down -v` 删除数据。

## 环境变量配置

所有环境变量均有默认值，无需配置即可使用 LocalRule 模式（本地规则提供者）。
接入真实 DeepSeek LLM 需要配置以下环境变量。

### 核心配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `local` | 运行环境标识 |
| `DATABASE_URL` | `sqlite:///server/data/db/app.db` | 数据库连接字符串 |
| `PROJECT_DATA_ROOT` | `server/data/projects` | 项目工作区根目录 |

### LLM 配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_PROVIDER` | `deepseek` | LLM 供应商 |
| `LLM_MODEL` | `deepseek-v4-pro` | 模型名称 |
| `DEEPSEEK_API_KEY` | `""` | DeepSeek API 密钥（接入真实 LLM 必填） |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API 基础 URL |
| `DEEPSEEK_TIMEOUT_SECONDS` | `30` | HTTP 请求超时秒数 |
| `DEEPSEEK_MAX_RETRIES` | `2` | 最大重试次数（仅对 5xx 和网络超时重试） |
| `DEEPSEEK_TEMPERATURE` | `0.3` | 采样温度（0-1，越低越稳定） |

### Provider 切换

每个业务模块可独立切换 `local_rule`（本地规则）或 `deepseek`（真实 LLM）。
LLM 调用失败时自动降级到 LocalRule，不阻断流程。

| 环境变量 | 默认值 | 可选值 | 说明 |
| --- | --- | --- | --- |
| `REQUIREMENT_DRAFT_PROVIDER` | `local_rule` | `local_rule` / `deepseek` | 实验要求拆解 |
| `EVIDENCE_CARD_PROVIDER` | `local_rule` | `local_rule` / `deepseek` | 证据卡片提取 |
| `ANALYSIS_PLAN_PROVIDER` | `local_rule` | `local_rule` / `deepseek` | 分析方案生成 |
| `CODE_TASK_PROVIDER` | `local_rule` | `local_rule` / `deepseek` | 代码任务生成 |
| `OUTLINE_PROVIDER` | `local_rule` | `local_rule` / `deepseek` | 实验大纲生成 |

### Worker 配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WORKER_POLL_INTERVAL_SECONDS` | `1` | Worker 轮询间隔秒数 |
| `JOB_MAX_RETRIES` | `2` | 后台任务最大重试次数 |
| `JOB_RETRY_BACKOFF_SECONDS` | `5` | 后台任务重试间隔秒数 |

### 公开资料采集配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SOURCE_FETCH_TIMEOUT_SECONDS` | `30` | URL 采集超时秒数 |
| `SOURCE_FETCH_MAX_SIZE_BYTES` | `10485760`（10MB） | 单次采集内容大小上限 |

### Python 执行沙箱配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `EXECUTION_TIMEOUT_SECONDS` | `30` | 用户代码执行超时秒数 |
| `EXECUTION_MEMORY_LIMIT_MB` | `1024` | 用户代码执行内存上限（MB） |
| `EXECUTION_OUTPUT_MAX_BYTES` | `10485760`（10MB） | 执行输出大小上限 |

### 数据集与交付物配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATASET_MAX_SIZE_BYTES` | `52428800`（50MB） | 数据集上传大小上限 |
| `DELIVERABLE_MAX_SIZE_BYTES` | `52428800`（50MB） | 交付物文件大小上限 |
| `WORD_TEMPLATE_PATH` | `""` | Word 模板路径（留空使用默认模板） |
| `PPT_TEMPLATE_PATH` | `""` | PPT 母版路径（留空使用默认母版） |

### 数据保留与清理配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATA_RETENTION_DAYS` | `0` | 数据保留天数（0=永久保留，>0=保留 N 天后可清理） |

## 配置示例

### 示例 1：LocalRule 模式（默认，无需 API Key）

适用于无网络或无 DeepSeek API Key 的场景，使用本地规则生成候选。

```bash
# 无需任何环境变量，直接启动即可
```

### 示例 2：全量接入 DeepSeek LLM

适用于需要高质量候选的场景。

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
$env:REQUIREMENT_DRAFT_PROVIDER = "deepseek"
$env:EVIDENCE_CARD_PROVIDER = "deepseek"
$env:ANALYSIS_PLAN_PROVIDER = "deepseek"
$env:CODE_TASK_PROVIDER = "deepseek"
$env:OUTLINE_PROVIDER = "deepseek"
```

```bash
# Linux/macOS
export DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
export REQUIREMENT_DRAFT_PROVIDER="deepseek"
export EVIDENCE_CARD_PROVIDER="deepseek"
export ANALYSIS_PLAN_PROVIDER="deepseek"
export CODE_TASK_PROVIDER="deepseek"
export OUTLINE_PROVIDER="deepseek"
```

### 示例 3：部分模块接入 LLM

适用于渐进式迁移，只对大纲生成启用 LLM。

```bash
$env:DEEPSEEK_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
$env:OUTLINE_PROVIDER = "deepseek"
```

### 示例 4：自定义数据库路径

```bash
$env:DATABASE_URL = "sqlite:///D:/data/lab-report.db"
$env:PROJECT_DATA_ROOT = "D:/data/lab-projects"
```

### 示例 5：使用 .env 文件

在 `server/` 目录下创建 `.env` 文件（不提交到 git）：

```ini
APP_ENV=local
DATABASE_URL=sqlite:///data/db/app.db
PROJECT_DATA_ROOT=data/projects

# LLM 配置
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
REQUIREMENT_DRAFT_PROVIDER=deepseek
EVIDENCE_CARD_PROVIDER=deepseek
ANALYSIS_PLAN_PROVIDER=deepseek
CODE_TASK_PROVIDER=deepseek
OUTLINE_PROVIDER=deepseek
```

> **注意：** `.env` 文件包含敏感信息，请确保已在 `.gitignore` 中排除。

## 常见排障

### 端口冲突

后端默认端口 8001，前端默认端口 5173。如端口被占用：

```bash
# 后端
python -m uvicorn app.main:app --port 8002

# 前端（修改 apps/web/vite.config.ts 中的 port）
```

### SQLite 数据库锁定

SQLite 在高并发写入时可能锁定。如遇 `database is locked` 错误：

1. 确认只有一个后端进程在运行
2. 确认只有一个 Worker 进程在运行
3. 重启后端和 Worker 进程

### Worker 不领取任务

1. 确认 Worker 进程正在运行：`python -m worker.main`
2. 检查数据库连接是否正确
3. 查看 Worker 控制台输出的 `[Worker]` 日志

### DeepSeek API 调用失败

1. 确认 `DEEPSEEK_API_KEY` 已正确设置
2. 确认网络可访问 `https://api.deepseek.com`
3. 查看 Worker 日志中的 `DeepSeek ... 失败，降级到 LocalRule` 警告
4. 系统会自动降级到 LocalRule，不会阻断流程

### 数据集上传失败

1. 检查文件大小是否超过 `DATASET_MAX_SIZE_BYTES`（默认 50MB）
2. 检查文件格式是否为 CSV 或 XLSX
3. 检查 `PROJECT_DATA_ROOT` 路径是否有写入权限

## 数据保留与清理

默认情况下，所有项目数据永久保留（`DATA_RETENTION_DAYS=0`）。如需定期清理过期项目数据，可配置保留天数并手动执行清理脚本。

### 配置保留天数

```bash
# 设置保留 30 天（超过 30 天未更新的项目可被清理）
$env:DATA_RETENTION_DAYS = "30"
```

### 执行清理脚本

清理脚本支持两种模式：dry-run（默认，只输出报告不删除）和 execute（实际删除）。

```bash
cd server
.venv\Scripts\activate

# 默认 dry-run：只输出清理报告，不实际删除
python -m scripts.cleanup_expired_data

# 显式 dry-run
python -m scripts.cleanup_expired_data --dry-run

# 实际执行清理（删除过期项目数据）
python -m scripts.cleanup_expired_data --execute
```

### 清理行为说明

- 基于 `Project.updated_at` 判断过期：超过 `DATA_RETENTION_DAYS` 天未更新的项目进入清理列表。
- 活跃项目自动重置计时器：项目有任何更新（如状态推进、数据上传）时 `updated_at` 自动刷新。
- RUNNING job 保护：有 PENDING/RUNNING 后台任务的项目跳过清理，避免清理正在执行任务的项目。
- 级联删除：清理项目时按外键依赖顺序删除全部 18 张关联表记录和项目文件系统目录。
- `--dry-run` 和 `--execute` 同时指定时采用 dry-run（安全优先）。

## 开发文档

内部架构、验收、实施计划、决策记录等文档位于 `dev-docs/` 目录。

## 版本

当前版本：v1.1.0

详细变更日志见 [dev-docs/changelog-v1.1.0.md](dev-docs/changelog-v1.1.0.md)。
