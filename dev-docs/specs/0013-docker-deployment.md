# SPEC 0013：Docker 化部署

> **版本：** V1.2.0  
> **状态：** 已由项目负责人确认（2026-07-24），待批准进入实现  
> **所属版本规划：** V1.2.0（v1.1.0-planning.md 明确推迟到 V1.2.0 的项）  
> **不改变：** 产品边界（仍为本地单用户 Web MVP）、唯一 owner 层架构、数据库/文件存储方式、业务代码

---

## 一、目标与范围

### 1.1 解决的问题

V1.0/V1.1.0 部署依赖手动配置环境（Python venv + Node.js + SQLite + 环境变量 + 3 个进程手动启动），存在以下痛点：

- 环境不一致：不同机器 Python 版本、依赖版本、Node 版本差异导致行为不一致
- 启动繁琐：需手动启动后端（uvicorn）、前端（vite dev）、Worker 三个进程
- 前端生产构建缺失：当前前端用 vite dev 模式，未做生产构建 + 静态托管
- 新用户上手成本高：需理解 venv、pip install、alembic、npm install 等概念

### 1.2 目标

通过 Docker 化提供**一键启动**能力，新用户只需 `docker compose up` 即可运行完整应用：

1. **环境一致性**：所有依赖锁定在镜像内，消除"在我机器上能跑"问题
2. **一键启动**：`docker compose up` 启动后端 + Worker + 前端，无需手动管理 3 个进程
3. **数据持久化**：SQLite 数据库 + 项目数据目录通过 volume 挂载，容器重建不丢数据
4. **生产构建**：前端 Vite 构建产物由 nginx 托管，API 请求反向代理到后端
5. **配置外置**：环境变量通过 `.env` 文件和 `docker-compose.yml` 传入，不写入镜像

### 1.3 范围

| 项 | 是否在本 SPEC | 说明 |
| --- | --- | --- |
| 后端 Dockerfile | ✅ | Python 3.13-slim 基础镜像，安装依赖，不含业务代码改动 |
| 前端生产构建 + nginx | ✅ | Vite build → nginx 托管 dist/ + 反向代理 /api |
| docker-compose.yml | ✅ | 编排 backend + worker + nginx 三服务 |
| 数据 volume 挂载 | ✅ | SQLite + 项目数据目录持久化 |
| 环境变量传递 | ✅ | 通过 .env 文件注入，不写入镜像 |
| 健康检查 | ✅ | backend 的 /health 端点 + compose healthcheck |
| 部署文档更新 | ✅ | 根 README.md 新增 Docker 启动章节 |

---

## 二、不做清单

以下明确不在本 SPEC 范围内（推迟到后续版本或永久不做）：

| 不做项 | 原因 | 推迟到 |
| --- | --- | --- |
| Kubernetes 编排 | 本地单用户 MVP 不需要编排平台 | 永久不做（产品边界） |
| CI/CD 流水线 | 本地 MVP 不需要持续集成 | V2.0+ |
| 多节点/集群部署 | 本地单用户，不做多节点 | 永久不做（产品边界） |
| Docker-in-Docker 沙箱 | Python 执行沙箱保持 AST + psutil 方案，不引入 DinD | V2.0+（如需更强隔离） |
| 镜像签名/镜像扫描 | V1.2.0 不引入安全供应链工具 | V2.0+ |
| 镜像仓库推送 | 本地构建本地使用，不推送到远程仓库 | V2.0+（如需分发） |
| 多架构镜像（arm64/amd64） | V1.2.0 聚焦 amd64，多架构推迟 | V2.0+ |
| Hot reload 开发模式容器 | 开发仍用本地 venv + vite dev，容器只用于生产部署 | 不做 |
| 修改现有业务代码 | Docker 化只做打包 + 编排，不改 owner 边界 | — |
| 修改数据库 schema | 无 schema 变更，仅挂载 volume | — |
| 新增业务模块 | 不引入新 owner | — |
| LLM 调用缓存合并 | owner 不同（LLM Gateway 业务层 vs 基础设施层），关注点正交，风险隔离需要独立验收。v1.1.0-planning.md 第 250/259 行将 Docker 化和 LLM 缓存列为并列独立推迟项。本 SPEC 不包含 LLM 缓存，独立为 SPEC 0014 | V1.2.0 独立 SPEC |

---

## 三、现状分析

### 3.1 现有部署架构

| 组件 | 当前方式 | 端口 |
| --- | --- | --- |
| 后端 API | `uvicorn app.main:app` | 8001 |
| 前端 | `vite dev`（开发模式，HMR） | 5173 |
| Worker | `python -m worker` | — |
| 数据库 | SQLite，默认 `server/data/db/app.db` | — |
| 项目数据 | 文件系统，默认 `server/data/projects/` | — |

### 3.2 现有依赖

**后端**（`server/pyproject.toml`）：
- fastapi, pydantic, sqlalchemy, alembic, uvicorn, python-docx, python-pptx, python-multipart, httpx
- dev: pytest, httpx2

**前端**（`apps/web/package.json`）：
- @tanstack/react-query, react 19, react-dom, react-router
- devDependencies: testing-library, typescript, vite 6, vitest

### 3.3 现有配置入口

- `server/app/core/config.py`：Settings 类，全部从环境变量读取
- `apps/web/vite.config.ts`：开发模式 `/api` 代理到 `http://localhost:8001`
- 根 `README.md`：SPEC 0008 部署文档

### 3.4 Python 执行沙箱现状

- 用户代码通过 `subprocess` 在宿主机 Python 进程中执行
- 安全限制：AST import 白名单（禁止 socket/ssl/http.client/urllib/requests/__import__）
- 资源限制：psutil 内存轮询 + 超时 + 输出大小上限
- **容器化后**：用户代码在容器内 subprocess 执行，隔离层从"宿主机进程"变为"容器进程"，安全性**增强**（容器本身提供文件系统/网络隔离），AST + psutil 限制保持不变

---

## 四、技术方案

### 4.1 镜像构建策略

采用**多阶段构建**，2 个 Dockerfile：

#### 4.1.1 后端镜像 `server/Dockerfile`

```dockerfile
# 阶段 1：依赖安装（builder）
FROM python:3.13-slim AS builder
WORKDIR /app
# editable install 需要包源码，先复制依赖描述和源码目录
COPY pyproject.toml ./
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY worker/ worker/
COPY scripts/ scripts/
# 创建 venv 并安装依赖（Linux 容器 venv 路径为 .venv/bin/）
RUN python -m venv .venv && \
    .venv/bin/pip install --no-cache-dir --upgrade pip && \
    .venv/bin/pip install --no-cache-dir -e ".[dev]"

# 阶段 2：运行时（runtime）
FROM python:3.13-slim AS runtime
WORKDIR /app
# 从 builder 复制 venv 和源码（不复制 tests/data/.venv 减小体积）
COPY --from=builder /app/.venv /app/.venv
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY worker/ worker/
COPY scripts/ scripts/
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh
EXPOSE 8001
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
  CMD .venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1
CMD ["./entrypoint.sh"]
```

**关键决策：**
- 基础镜像 `python:3.13-slim`（与当前开发环境 3.13.5 一致）
- 多阶段构建：builder 阶段创建 venv 并安装依赖，runtime 阶段只复制 .venv 和源码，减小镜像体积
- **venv 路径**：Linux 容器为 `.venv/bin/python`（非 Windows 的 `.venv/Scripts/python.exe`）
- **editable install**：`pip install -e ".[dev]"` 需要包源码，因此 builder 阶段先 `COPY app/ app/` 等源码目录
- 暴露 8001 端口
- 启动命令在 entrypoint 中先执行 `alembic upgrade head` 再启动 uvicorn
- HEALTHCHECK 直接用 venv 内的 Python 调用 urllib，无需额外安装 curl

#### 4.1.2 前端 + nginx 镜像 `apps/web/Dockerfile`

```dockerfile
# 阶段 1：构建
FROM node:20-slim AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

# 阶段 2：nginx 托管
FROM nginx:alpine AS runtime
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

**nginx.conf 关键配置：**
- 静态文件托管 `/usr/share/nginx/html`
- API 反向代理 `location /api { proxy_pass http://backend:8001; }`
- 健康检查代理 `location /health { proxy_pass http://backend:8001; }`

### 4.2 docker-compose 编排

```yaml
version: "3.9"
services:
  backend:
    build: ./server
    env_file: .env
    volumes:
      - db-data:/app/data/db
      - project-data:/app/data/projects
    ports:
      - "8001:8001"
    healthcheck:
      test: ["CMD", ".venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  worker:
    build: ./server
    env_file: .env
    volumes:
      - db-data:/app/data/db
      - project-data:/app/data/projects
    command: [".venv/bin/python", "-m", "worker.main"]
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

  frontend:
    build: ./apps/web
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  db-data:
  project-data:
```

**关键决策：**
- **backend 和 worker 共享同一镜像**（都构建自 `server/Dockerfile`），worker 用不同 command 覆盖
- **共享 volume**：db-data 和 project-data 同时挂载到 backend 和 worker，保证两者访问同一数据库和数据
- **启动顺序**：worker `depends_on backend (service_healthy)`，确保后端健康后才启动 worker
- **前端端口 80**：nginx 托管，用户访问 `http://localhost`
- **restart: unless-stopped**：异常退出自动重启，但不自动重启用户手动停止的容器

### 4.3 数据持久化

| 数据类型 | 容器内路径 | volume | 说明 |
| --- | --- | --- | --- |
| SQLite 数据库 | `/app/data/db/app.db` | `db-data` | 后端 + Worker 共享 |
| 项目数据 | `/app/data/projects/` | `project-data` | 后端 + Worker 共享，含数据集/交付物/Word模板 |

**关键：** 容器内路径与 `config.py` 默认值一致（`PROJECT_ROOT / "data" / "db"` 和 `PROJECT_ROOT / "data" / "projects"`），通过 `DATABASE_URL` 和 `PROJECT_DATA_ROOT` 环境变量显式指定，避免路径漂移。

### 4.4 环境变量传递

创建 `.env.example` 作为模板（提交到 git），用户复制为 `.env`（不提交）：

```env
# 核心配置
APP_ENV=docker
DATABASE_URL=sqlite:///app/data/db/app.db
PROJECT_DATA_ROOT=/app/data/projects

# LLM 配置（默认 LocalRule，无需 API Key）
DEEPSEEK_API_KEY=
REQUIREMENT_DRAFT_PROVIDER=local_rule
EVIDENCE_CARD_PROVIDER=local_rule
ANALYSIS_PLAN_PROVIDER=local_rule
CODE_TASK_PROVIDER=local_rule
OUTLINE_PROVIDER=local_rule

# Worker 配置
WORKER_POLL_INTERVAL_SECONDS=1

# Python 执行沙箱（容器内）
EXECUTION_TIMEOUT_SECONDS=30
EXECUTION_MEMORY_LIMIT_MB=1024
EXECUTION_OUTPUT_MAX_BYTES=10485760

# 数据保留
DATA_RETENTION_DAYS=0
```

**关键：**
- `DATABASE_URL` 和 `PROJECT_DATA_ROOT` 必须指向 volume 挂载路径，保证持久化
- `DEEPSEEK_API_KEY` 留空时走 LocalRule 降级，与 V1.1.0 行为一致
- `.env` 文件不提交到 git（已在 .gitignore 排除）

### 4.5 Python 执行沙箱在容器内的考量

| 考量点 | 方案 | 风险 |
| --- | --- | --- |
| 用户代码执行 | 仍在容器内 subprocess 执行（`subprocess.run`） | 低：容器本身提供文件系统隔离 |
| AST import 白名单 | 保持现有实现，不改动 | 无 |
| psutil 内存监控 | 保持现有实现，监控容器内进程 | 低：容器内 psutil 可读取进程信息 |
| 网络访问 | 用户代码被 AST 禁止 socket/ssl/http.client/urllib/requests，无法联网 | 无：AST 拦截在代码层，容器只是额外隔离层 |
| 文件系统访问 | 用户代码只能访问 `/app/data/projects/{project_id}/`，容器内其余路径无业务数据 | 低 |
| 资源上限 | 容器可加 `mem_limit` 和 `cpus` 限制，作为 psutil 之外的额外防线 | 可选，V1.2.0 默认不加容器资源限制（保持与 V1.1.0 一致） |

**结论：** Docker 化不改变 Python 执行沙箱的 owner（仍在 `server/app/modules/execution/`），只是执行环境从宿主机变为容器，安全性增强。

### 4.6 前端生产构建

| 项 | V1.1.0 | V1.2.0 Docker 化 |
| --- | --- | --- |
| 构建方式 | `vite dev`（开发模式） | `npm run build` → `dist/` |
| 托管方式 | vite dev 服务器（5173） | nginx 静态托管（80） |
| API 代理 | vite.config.ts proxy | nginx `proxy_pass` |
| HMR | 有 | 无（生产模式不需要） |

**关键：** `apps/web/vite.config.ts` 中的 `/api` 代理配置仅在开发模式生效。生产模式由 nginx 接管 API 代理，前端代码无需改动（仍用相对路径 `/api/...`）。

### 4.7 entrypoint 脚本

后端镜像使用 entrypoint 脚本确保迁移先于启动：

```bash
#!/bin/sh
# server/entrypoint.sh
set -e

# 等待数据库 volume 就绪
sleep 1

# 执行数据库迁移
.venv/bin/python -m alembic upgrade head

# 启动后端
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

**说明：** Docker 镜像基于 Linux，venv 路径统一为 `.venv/bin/python`（非 Windows 的 `.venv/Scripts/python.exe`）。entrypoint 先执行 `alembic upgrade head` 确保数据库 schema 最新，再启动 uvicorn。

---

## 五、文件清单

### 5.1 新增文件

| 文件 | 作用 |
| --- | --- |
| `server/Dockerfile` | 后端镜像构建（多阶段） |
| `server/entrypoint.sh` | 后端启动脚本（迁移 + uvicorn） |
| `server/.dockerignore` | 排除 .venv、data、tests 等 |
| `apps/web/Dockerfile` | 前端镜像构建（多阶段：node build + nginx） |
| `apps/web/nginx.conf` | nginx 配置（静态托管 + API 反向代理） |
| `apps/web/.dockerignore` | 排除 node_modules、dist 等 |
| `docker-compose.yml` | 编排 backend + worker + frontend |
| `.env.example` | 环境变量模板（提交到 git） |

### 5.2 修改文件

| 文件 | 改动 | 是否改业务代码 |
| --- | --- | --- |
| `README.md` | 新增"Docker 启动"章节 | 否（文档） |
| `dev-docs/dependency-review.md` | 记录 Docker 化依赖决策 | 否（文档） |
| `.gitignore` | 确认 .env 已排除 | 否（配置） |

### 5.3 不改动文件

| 文件 | 原因 |
| --- | --- |
| `server/app/**/*.py` | Docker 化不改业务代码，保持 owner 边界 |
| `server/app/core/config.py` | 环境变量读取逻辑不变，Docker 通过环境变量注入 |
| `server/alembic/**` | 迁移逻辑不变，entrypoint 调用 `alembic upgrade head` |
| `apps/web/src/**` | 前端代码不变，只改构建和托管方式 |
| `apps/web/vite.config.ts` | 开发模式代理保留，生产模式用 nginx |

---

## 六、验收标准

### 6.1 镜像构建验收

| # | 检查项 | 通过标准 |
| --- | --- | --- |
| AC-1 | 后端镜像构建 | `docker build -t lab-report-backend ./server` 成功，镜像大小 < 500MB |
| AC-2 | 前端镜像构建 | `docker build -t lab-report-frontend ./apps/web` 成功，镜像大小 < 100MB |
| AC-3 | 镜像不含源码泄露 | `.dockerignore` 排除 .venv、node_modules、data、tests、.git |

### 6.2 容器编排验收

| # | 检查项 | 通过标准 |
| --- | --- | --- |
| AC-4 | 一键启动 | `docker compose up -d` 启动 backend + worker + frontend 三服务 |
| AC-5 | 启动顺序 | worker 在 backend 健康检查通过后才启动 |
| AC-6 | 健康检查 | backend healthcheck 通过，`/health` 返回 `{"status":"ok"}` |
| AC-7 | 前端可访问 | 浏览器访问 `http://localhost` 正常渲染首页 |
| AC-8 | API 代理 | 前端 `/api/projects` 请求经 nginx 反向代理到 backend，返回项目列表 |

### 6.3 数据持久化验收

| # | 检查项 | 通过标准 |
| --- | --- | --- |
| AC-9 | 数据库持久化 | `docker compose down` 后 `docker compose up`，原项目数据仍在 |
| AC-10 | 项目数据持久化 | 上传的数据集和生成的 Word/PPT 在容器重建后仍可访问 |
| AC-11 | volume 隔离 | `docker compose down -v` 删除 volume 后数据清空（符合预期） |

### 6.4 功能回归验收

| # | 检查项 | 通过标准 |
| --- | --- | --- |
| AC-12 | 后端测试 | 容器内 `pytest -q` 通过 704 个测试（与 V1.1.0 一致） |
| AC-13 | 迁移自动执行 | entrypoint 自动执行 `alembic upgrade head`，迁移到 0007 |
| AC-14 | LocalRule 降级 | 不配置 DEEPSEEK_API_KEY 时，5 Provider 走 local_rule |
| AC-15 | Worker 领取任务 | Worker 进程正常轮询，能处理后台任务 |

### 6.5 Python 沙箱验收

| # | 检查项 | 通过标准 |
| --- | --- | --- |
| AC-16 | AST 拦截 | 容器内执行含 `import socket` 的代码被 AST 拦截 |
| AC-17 | 内存监控 | 容器内 psutil 内存监控正常工作 |
| AC-18 | 超时限制 | 容器内用户代码超时被终止 |

---

## 七、依赖与风险

### 7.1 新增依赖

| 依赖 | 类型 | 用途 | 是否需决策记录 |
| --- | --- | --- | --- |
| Docker | 运行时 | 容器运行时 | 否（基础设施，非业务依赖） |
| docker-compose | 运行时 | 容器编排 | 否 |
| nginx:alpine | 镜像 | 前端静态托管 + 反向代理 | 是（新增基础设施镜像） |
| node:20-slim | 镜像 | 前端构建阶段 | 是（构建阶段镜像） |
| python:3.13-slim | 镜像 | 后端基础镜像 | 是（运行时镜像） |

**关键：** 不新增 Python/Node.js 业务依赖，只引入基础设施镜像。需更新 `dev-docs/dependency-review.md`。

### 7.2 风险评估

| 风险 | 影响 | 缓解措施 |
| --- | --- | --- |
| Linux/Windows venv 路径差异 | entrypoint 脚本中 `.venv/Scripts/python.exe`（Windows）vs `.venv/bin/python`（Linux） | Dockerfile 基于 Linux，统一用 `.venv/bin/python`；entrypoint 脚本做路径检测 |
| SQLite 文件锁在 volume 上 | Docker volume 上 SQLite 可能有文件锁问题 | 单后端 + 单 Worker 访问同一 SQLite，与 V1.1.0 一致；如遇锁定，加 `?timeout=30` 连接参数 |
| 容器内时区 | 默认 UTC，与开发环境可能不一致 | 设置 `TZ=Asia/Shanghai` 环境变量 |
| 镜像体积过大 | 影响分发 | 多阶段构建 + slim 基础镜像 + .dockerignore 排除测试/数据 |
| 前端构建在容器内失败 | Vite 构建环境差异 | 构建阶段用 node:20-slim，与本地 Node 18+ 一致；CI 验证 |
| 用户代码 subprocess 路径 | 容器内 Python 路径与宿主机不同 | `python_executor.py` 使用 `sys.executable` 而非硬编码路径，已兼容 |

### 7.3 已知限制（非阻断）

| # | 限制 | 影响 | 后续入口 |
| --- | --- | --- | --- |
| L-1 | 不支持多架构镜像 | arm64 机器（如 Apple Silicon）需加 --platform=linux/amd64 模拟运行 | V2.0 多架构构建 |
| L-2 | 不推送镜像仓库 | 用户需本地构建 | V2.0 GitHub Container Registry |
| L-3 | 不做容器资源限制 | 用户代码可能消耗较多资源 | V2.0 mem_limit/cpus |
| L-4 | 开发模式不容器化 | 开发仍用本地 venv + vite dev | 不做（开发体验优先） |

---

## 八、实施顺序

按 AGENTS.md 阶段闸，确认本 SPEC 后按以下顺序实施：

```
1. 创建 .dockerignore（server/ 和 apps/web/）
2. 编写 server/Dockerfile（多阶段构建）
3. 编写 server/entrypoint.sh（迁移 + 启动）
4. 编写 apps/web/Dockerfile（node build + nginx）
5. 编写 apps/web/nginx.conf（静态托管 + API 代理）
6. 编写 docker-compose.yml（三服务编排）
7. 创建 .env.example（环境变量模板）
8. 更新 .gitignore（确认 .env 排除）
9. 本地构建测试：docker compose build && docker compose up
10. 执行验收（AC-1 ~ AC-18）
11. 更新 README.md（新增 Docker 启动章节）
12. 更新 dev-docs/dependency-review.md（记录镜像依赖）
13. 更新 dev-docs/acceptance.md（记录验收证据）
14. git 边界复核 + commit + push
```

---

## 九、确认事项（已由项目负责人确认）

> **确认时间：** 2026-07-24  
> **确认方式：** 项目负责人对 4 个技术决策给出方向，AI 基于证据研究给出推荐组合，项目负责人认可。

### 9.1 镜像基础：slim（debian-based），不用 alpine

**决策：** 采用 `python:3.13-slim`（debian glibc），不用 alpine（musl libc）。

**证据：**
- 项目预装科学计算包：pandas 3.0.3 / numpy 2.5.1 / scipy 1.18.0 / scikit-learn 1.9.0 / matplotlib 3.11.0
- alpine 使用 musl libc，这些包无预编译 wheel，需源码编译（构建时间 30min+，可能因 musl 兼容性失败）
- slim 基于 debian glibc，有预编译 wheel，构建快且稳定
- 镜像体积差异（slim ~120MB vs alpine ~50MB）可接受，换取构建稳定性和科学计算生态兼容性

### 9.2 端口：保持 8001（backend）+ 80（frontend nginx），不固定 8000

**决策：** 容器内保持 8001（与 config.py 默认值一致），nginx 前端用 80。

**证据：**
- `server/app/core/config.py` 默认端口 8001
- 704 个测试基于 8001 端口
- 改为 8000 需同步改 config.py 默认值或全量环境变量覆盖，有漂移风险
- Docker 宿主机映射可灵活配置（`"8001:8001"` 或用户自定义 `"8000:8001"`），容器内保持 8001 与代码一致

### 9.3 Python 版本：保持 3.13-slim，不用 3.11-slim

**决策：** 采用 `python:3.13-slim`，与开发环境一致。

**证据：**
- 当前开发环境 Python 3.13.5
- 704 个后端测试 + 411 个前端测试在此版本通过
- pandas 3.0.3 / numpy 2.5.1 是较新版本，在 3.11 上未验证
- 改用 3.11-slim 需重新跑全部 704 测试验证，有回归风险
- 3.13 是当前稳定版本，与开发环境一致消除"在我机器上能跑"问题

### 9.4 不做清单：全部认可

**决策：** 第二章不做清单全部认可，无需调整。

### 9.5 已决策项（技术判断，非产品决策）

- **LLM 调用缓存不合并**：v1.1.0-planning.md 第 250 行（Docker 化）和第 259 行（LLM 缓存）是并列独立推迟项。按 AGENTS.md "唯一 owner"原则，Docker 化属基础设施层，LLM 缓存属 `server/app/modules/llm/` 业务层，owner 边界不同、关注点正交、风险面需独立隔离。本 SPEC 不包含 LLM 缓存。如 V1.2.0 要做 LLM 缓存，独立起草 SPEC 0014。

---

**本 SPEC 已由项目负责人确认（2026-07-24，见第九章）。按 AGENTS.md 阶段闸，进入实现需项目负责人明确批准。**
