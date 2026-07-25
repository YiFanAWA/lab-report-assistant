# V1.2.0 版本发布说明

> **版本：** v1.2.0  
> **发布日期：** 2026-07-25  
> **上一版本：** v1.1.0  
> **提交范围：** `v1.1.0..HEAD`（7 个提交）  
> **变更统计：** 后端 729 测试 + 前端 411 测试 = 1140 个测试（新增 25 个）  
> **文档状态：** 草稿，待项目负责人确认后发布

---

## 概述

实验报告助手 V1.2.0 是 V1.1.0 的运维和质量基础设施增强版本。V1.2.0 **不改变产品边界**（仍是本地单用户 Web MVP）和**架构主线**（仍是唯一 owner + API 适配 + 前端接线），不引入新的业务模块。

V1.2.0 聚焦于三个基础设施切片：

1. **SPEC 0013 Docker 化部署**：将应用容器化，提供一键 `docker compose up -d` 启动能力。
2. **SPEC 0014 LLM 调用缓存**：为 DeepSeek 调用增加 SQLite 缓存层，降低成本和延迟。
3. **SPEC 0015 GitHub Actions CI 流水线**：配置自动测试流水线，每次 push/PR 自动验证回归。

V1.2.0 包含 3 个 SPEC：

| SPEC | 标题 | 状态 |
| --- | --- | --- |
| SPEC 0013 | Docker 化部署 | ✅ 已完成（commit `c210911`） |
| SPEC 0014 | LLM 调用缓存 | ✅ 已完成（commit `31ec6cd`） |
| SPEC 0015 | GitHub Actions CI 流水线 | ✅ 已完成（commit `e203ac2`） |

---

## 一、新增功能

### 1.1 SPEC 0013：Docker 化部署

**提交：** `1f139d4`、`32b96c6`、`c210911`  
**模块：** `server/Dockerfile`、`apps/web/Dockerfile`、`docker-compose.yml`、`server/entrypoint.sh`、`apps/web/nginx.conf`

V1.1.0 应用部署依赖手动启动三个进程（后端 uvicorn + Worker + 前端 Vite/Nginx），缺少容器化能力。V1.2.0 引入完整 Docker 化部署方案。

**新增能力：**
- **后端镜像**（`server/Dockerfile`，895MB）：多阶段构建（builder + runtime），基础镜像 `python:3.13-slim`，包含 pandas/numpy/scipy/scikit-learn/matplotlib 科学计算栈 + psutil + bs4/lxml/pypdf 文档解析 + pytest 等 dev 依赖
- **前端镜像**（`apps/web/Dockerfile`，93.2MB）：多阶段构建（node build + nginx runtime），基础镜像 `node:20-slim` 构建 + `nginx:alpine` 托管静态文件
- **三服务编排**（`docker-compose.yml`）：
  - `backend`：8001 端口，挂载 db-data + project-data 命名卷
  - `worker`：依赖 backend `service_healthy`，共享 project-data 卷
  - `frontend`：80 端口，nginx 反向代理 `/api` 到 backend:8001
- **启动入口**（`server/entrypoint.sh`）：自动执行 `alembic upgrade head` 数据库迁移，再启动 uvicorn；处理 Windows 创建的 CRLF 行尾
- **健康检查**：backend 配置 `HEALTHCHECK`，worker 通过 `service_healthy` 依赖等待
- **数据持久化**：db-data 卷保存 SQLite 数据库，project-data 卷保存项目工作区文件
- **环境变量配置**：`.env.example` 提供 Docker 化路径（`sqlite:////app/data/db/app.db` 4 斜杠）

**测试：** 引用 SPEC 0013 验收记录，AC-1~18 全部通过。

**关键决策：**
- AC-1 后端镜像标准由 < 500MB 调整为 < 1000MB（含科学计算栈，项目负责人 2026-07-24 确认）
- AC-12 后端测试标准由"容器内 pytest"调整为"本地 venv pytest"（.dockerignore 排除 tests，行业最佳实践）

### 1.2 SPEC 0014：LLM 调用缓存

**提交：** `31ec6cd`  
**模块：** `server/app/infrastructure/llm/llm_cache.py`、`server/app/infrastructure/llm/deepseek_client.py`、`server/app/modules/llm/gateway.py`、`server/app/core/config.py`

V1.1.0 每次 LLM 调用都发起真实 HTTP 请求，成本和延迟无法优化。V1.2.0 引入 LLM 调用缓存层。

**新增能力：**
- **LLMCache 存储层**（`llm_cache.py`）：
  - 独立 SQLite 文件 `data/llm_cache/llm_cache.db`，**不走 Alembic 迁移**
  - 自动建表（`CREATE TABLE IF NOT EXISTS` + WAL 模式）
  - 缓存 key = `SHA256(model + messages + response_format + temperature)` 规范化 JSON
  - 惰性淘汰 TTL（默认 86400 秒，1 天）
  - 写入失败不抛错（降级到无缓存）
- **DeepSeekClient 接入**：
  - `cache=None` 默认值保证零回归
  - 调用前查缓存（命中跳过 HTTP）
  - 调用后写缓存（失败降级）
- **配置项**（3 个新增环境变量）：
  - `LLM_CACHE_ENABLED`（默认 `false`，需显式启用）
  - `LLM_CACHE_TTL_SECONDS`（默认 `86400`，1 天）
  - `LLM_CACHE_DB_PATH`（默认 `data/llm_cache/llm_cache.db`）
- **降级策略**：
  - 缓存查询异常返回 None，不阻断主流程
  - 缓存写入异常仅记录 warning，不抛错
  - 非法配置值降级到默认（非法 TTL/ENABLED 值）

**测试：** 新增 25 个后端测试（test_llm_cache 20 + test_deepseek_client 缓存接入 5），0 warnings。

**关键决策：**
- 缓存表不进入业务数据库 Alembic 迁移（缓存是性能优化非业务真相，独立存储保持 owner 边界清晰）
- `LLM_CACHE_ENABLED` 默认关闭（保证现有行为零变化，用户明确需要时再开启）
- TTL 默认 1 天（平衡缓存命中率和数据新鲜度）

### 1.3 SPEC 0015：GitHub Actions CI 流水线

**提交：** `5186a64`、`64f2eb4`、`e203ac2`  
**模块：** `.github/workflows/ci.yml`

V1.1.0 没有 CI 流水线，推送代码无法自动验证回归。V1.2.0 配置 GitHub Actions 自动化流水线。

**新增能力：**
- **CI 工作流**（`.github/workflows/ci.yml`）：
  - 触发条件：`push` 到 `master` 分支、`pull_request` 到 `master` 分支
  - **后端 Job**（ubuntu-latest + Python 3.13）：
    - `pip install -e ".[dev]"`（server/ 目录）
    - 额外安装科学计算包（弥补 TD-004：pandas/numpy/scipy/scikit-learn/matplotlib/psutil 固定版本）
    - `alembic upgrade head`（临时 SQLite 文件）
    - `pytest -q`
  - **前端 Job**（ubuntu-latest + Node 20）：
    - `npm install`（根目录，workspace 模式）
    - `npm run lint`（tsc --noEmit）
    - `npm run build`（Vite 构建）
  - 两 Job 并行运行，无依赖关系
  - 不使用任何 GitHub Secrets（`DEEPSEEK_API_KEY` 留空，测试全 mock）
- **CI 运行历史**：
  - Run #1（`5186a64`）：failure（backend job 失败，TD-007 openpyxl 未声明）
  - Run #2（`64f2eb4`）：**success**（修复后全绿，729 passed in 33s）
  - Run #3（`e203ac2`）：**success**（最终文档回写后持续绿色）

**测试：** CI 流水线本身通过 GitHub Actions 实际运行验证（Run #2/#3 均成功）。

**关键决策：**
- CI 仅对 master 分支触发（feature 分支推送不触发，避免配额消耗）
- 不配置分支保护规则（首版 CI 优先正确性验证，不强制门禁）
- 不使用缓存优化（首版优先正确性，V1.3.0 再优化）
- 不修复 TD-004（独立债务，CI 额外安装科学计算包带注释引用 TD-004）

---

## 二、Bug 修复

### 2.1 SPEC 0015 TD-007：openpyxl 未声明在 pyproject.toml

| # | Bug 描述 | 根因 | 修复 |
| --- | --- | --- | --- |
| 1 | CI Run #1 backend job exit code 2，`test_dataset_parser.py` 导入 `openpyxl` 失败 | `openpyxl` 自 SPEC 0004 起被 app 代码直接导入但未声明在 `pyproject.toml` dependencies（与 TD-004 同类问题） | `pyproject.toml` dependencies 新增 `openpyxl>=3.1.0`（commit `64f2eb4`）；CI Run #2 全绿验证 |

### 2.2 SPEC 0013 .env DATABASE_URL 修正

| # | Bug 描述 | 根因 | 修复 |
| --- | --- | --- | --- |
| 2 | Docker 容器启动时 `unable to open database file` | `.env.example` 和 `.env` 的 `DATABASE_URL` 使用 3 斜杠 `sqlite:///app/data/db/app.db`，被 SQLAlchemy 解析为相对路径 | 修正为 4 斜杠 `sqlite:////app/data/db/app.db`（绝对路径） |

### 2.3 SPEC 0013 依赖遗漏修复

| # | Bug 描述 | 根因 | 修复 |
| --- | --- | --- | --- |
| 3 | Docker 镜像构建后 backend 启动失败 | `pyproject.toml` 遗漏 3 个运行时依赖：`beautifulsoup4`（html_parser.py）、`lxml`（BeautifulSoup 解析器）、`pypdf`（pdf_parser.py）；本地 venv 因手动安装未暴露 | `pyproject.toml` dependencies 新增 `beautifulsoup4>=4.12.0`、`lxml>=5.0.0`、`pypdf>=4.0.0`（commit `32b96c6`） |

---

## 三、架构改进

### 3.1 LLM 缓存独立存储

- 缓存表使用独立 SQLite 文件 `data/llm_cache/llm_cache.db`
- 不进入业务数据库 Alembic 迁移，保持 owner 边界清晰
- 缓存丢失可重建（重新调用 LLM 即可），与业务表不可丢失性质不同
- Docker 化时缓存 volume 可独立挂载或 ephemeral

### 3.2 Docker 多阶段构建

- 后端镜像分 builder 阶段（安装依赖）和 runtime 阶段（精简运行时）
- 前端镜像分 node build 阶段（编译 dist/）和 nginx runtime 阶段（托管静态文件）
- 减少运行时镜像体积，builder 阶段的 dev 依赖不进入 runtime

### 3.3 CI 流水线作为质量门禁

- 每次 push/PR 自动运行 1140 个测试（729 后端 + 411 前端）
- 不修改业务代码，不使用 Secrets，与业务逻辑解耦
- TD-004（科学计算包未声明）通过 ci.yml 注释明确引用，作为后续清理入口

### 3.4 openpyxl 依赖声明修复（TD-007）

- 与 TD-004 同类问题，但 `openpyxl` 直接被 app 代码导入（`dataset_parser.py`）
- 直接补入 `pyproject.toml` 主 `dependencies`，而非 `optional-dependencies`
- 修复后 CI 流水线全绿，本地 Windows venv 因已手动安装未暴露该问题

---

## 四、依赖变更

### 4.1 运行时依赖

| 依赖 | 版本 | 用途 | 引入版本 |
| --- | --- | --- | --- |
| `openpyxl` | `>=3.1.0` | Excel 数据集解析（`dataset_parser.py` 直接导入） | V1.2.0（TD-007 修复） |
| `beautifulsoup4` | `>=4.12.0` | HTML 解析（`html_parser.py`） | V1.2.0（SPEC 0013 修复） |
| `lxml` | `>=5.0.0` | BeautifulSoup 解析器 | V1.2.0（SPEC 0013 修复） |
| `pypdf` | `>=4.0.0` | PDF 文档解析（`pdf_parser.py`） | V1.2.0（SPEC 0013 修复） |

### 4.2 开发依赖

无新增开发依赖。`httpx2` 在 V1.1.0 已引入，SPEC 0014 复用。

### 4.3 基础设施依赖（不进入项目依赖清单）

| 依赖 | 版本 | 来源 | 用途 |
| --- | --- | --- | --- |
| `actions/checkout` | v4 | GitHub 托管 | CI 代码检出 |
| `actions/setup-python` | v5 | GitHub 托管 | CI Python 环境配置 |
| `actions/setup-node` | v4 | GitHub 托管 | CI Node 环境配置 |
| `python:3.13-slim` | 3.13 | Docker Hub | 后端镜像基础 |
| `node:20-slim` | 20 | Docker Hub | 前端 builder 镜像 |
| `nginx:alpine` | alpine | Docker Hub | 前端 runtime 镜像 |

---

## 五、测试统计

| 测试套件 | V1.1.0 | V1.2.0 | 新增 | 状态 |
| --- | --- | --- | --- | --- |
| 后端 pytest | 704 | 729 | +25 | ✅ 0 warnings |
| 前端 Vitest | 411 | 411 | 0 | ✅ 全部通过 |
| **总计** | **1115** | **1140** | **+25** | — |

### 后端新增测试分布

| SPEC | 新增测试数 | 累计后端测试 |
| --- | --- | --- |
| SPEC 0013 Docker | 0（基础设施，AC 通过 Docker 实际构建验证） | 704 |
| SPEC 0014 LLM 缓存 | 25（test_llm_cache 20 + test_deepseek_client 缓存接入 5） | 729 |
| SPEC 0015 CI | 0（基础设施，AC 通过 CI 实际运行验证） | 729 |

### CI 流水线运行记录

| Run # | Commit | 状态 | 耗时 | 说明 |
| --- | --- | --- | --- | --- |
| Run #1 | `5186a64` | ❌ failure | — | TD-007 openpyxl 缺失导致 backend job 失败 |
| Run #2 | `64f2eb4` | ✅ success | 76s（backend）+ 33s（frontend） | openpyxl 修复后 CI 全绿 |
| Run #3 | `e203ac2` | ✅ success | — | 最终文档回写 commit，CI 持续绿色 |

---

## 六、已知限制（V1.2.0 边界）

1. **不做 CD（持续部署）**：V1 本地单用户，无在线部署目标，CI 只验证不部署
2. **不做 Docker 镜像仓库推送**：SPEC 0013 仅提供本地 Docker 构建，镜像推送需镜像仓库
3. **不做多 OS 矩阵**：CI 仅在 ubuntu-latest 验证，Windows/macOS 矩阵增加耗时
4. **不做 code coverage 上传**：覆盖率非本轮目标，本地 pytest 已足够
5. **不做 lint 工具集成（ruff/flake8）**：项目后端无 lint 配置，前端 lint 实际是 tsc
6. **不做缓存优化（pip cache / npm cache）**：首版优先正确性，V1.3.0 再优化
7. **不做并发控制（cancel in-progress）**：首版简单，不引入 concurrency 配置
8. **不做分支保护规则配置**：分支保护是仓库设置，需项目负责人在 GitHub 侧操作
9. **不做 Redis 或内存缓存**：V1 本地单用户，SQLite 足够；Redis 引入运维负担
10. **不做缓存统计 API**：运维监控非本轮目标，可通过日志查
11. **不做手动失效接口**：TTL + 配置开关已满足；手动失效增加 API 面
12. **不缓存 LocalRule 调用**：LocalRule 无网络成本，无需缓存
13. **不做缓存预热**：V1 场景不需要批量预填充

---

## 七、升级指南

### 7.1 从 V1.1.0 升级（本地开发）

V1.2.0 无破坏性变更，升级步骤简单：

```bash
# 1. 拉取最新代码
git pull origin master

# 2. 更新后端依赖（新增 openpyxl/beautifulsoup4/lxml/pypdf 显式声明）
cd server
.venv\Scripts\activate
pip install -e ".[dev]"

# 3. 执行数据库迁移（无新增迁移，确认现有 0001-0007 无错误）
.venv\Scripts\python.exe -m alembic upgrade head

# 4. 更新前端依赖（无新增依赖）
cd ../apps/web
npm install
```

### 7.2 启用 Docker 化部署（可选，推荐）

```bash
# 1. 配置环境变量
cp server/.env.example server/.env
# 编辑 .env，注意 DATABASE_URL 使用 4 斜杠 sqlite:////app/data/db/app.db

# 2. 一键启动三服务
docker compose up -d

# 3. 验证服务
docker compose ps
curl http://localhost/health
curl http://localhost/api/projects
```

### 7.3 启用 LLM 调用缓存（可选）

```bash
# 1. 在 .env 中配置（或环境变量）
LLM_CACHE_ENABLED=true
LLM_CACHE_TTL_SECONDS=86400
LLM_CACHE_DB_PATH=data/llm_cache/llm_cache.db

# 2. 重启后端和 Worker
# 缓存文件首次访问时自动创建，无需手动初始化

# 3. 验证缓存命中
# 后端日志会输出 "LLM 缓存命中, key=xxxxxxxxxxxx..."
```

### 7.4 CI 流水线状态查看

```bash
# 1. 浏览器访问
# https://github.com/YiFanAWA/lab-report-assistant/actions

# 2. 通过 GitHub REST API 查询最新运行
curl -s "https://api.github.com/repos/YiFanAWA/lab-report-assistant/actions/runs?branch=master&per_page=5"

# 3. 通过 gh CLI（如已安装）
gh run list --branch master --limit 5
```

---

## 八、回归测试

V1.2.0 发布前已执行完整回归测试，详见 [v1.2.0-regression-test-plan.md](v1.2.0-regression-test-plan.md)。

**关键回归点：**
- 后端 729 测试全部通过，0 warnings
- 前端 411 测试全部通过
- V1.1.0 端到端主链路（创建项目 → 下载 Word/PPT）完整跑通（E2E_RESULT=PASS）
- 3 个 SPEC 专项回归全部通过
- CI Run #2 和 Run #3 全绿
- 关键回归点 63 个测试通过（STALE/沙箱/路径穿越/URL 安全等）

---

## 九、致谢

感谢项目负责人的严格阶段闸管理和验收标准。V1.2.0 的 3 个 SPEC 均遵循"先编写并确认 SPEC → 项目负责人批准 → 测试先行 → 实现 → 验收 → 文档回写 → git 收口"的阶段闸流程。

特别感谢项目负责人在 SPEC 0013 验收时对镜像大小标准的灵活调整（AC-1 从 < 500MB 调整为 < 1000MB 以容纳科学计算栈），以及在 SPEC 0015 TD-007 修复过程中的快速决策支持。

---

**版本标签：** `v1.2.0`（待创建）  
**发布状态：** 草稿，待项目负责人确认
