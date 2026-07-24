# SPEC 0015：GitHub Actions CI 流水线

> **状态：** 草案，待项目负责人确认  
> **日期：** 2026-07-24  
> **前置：** SPEC 0013 Docker 化部署已收口（commit `c210911`），项目远程仓库为 GitHub `YiFanAWA/lab-report-assistant`（决策 0012）  
> **目标版本：** v1.2.0

---

## 一、目标与边界

### 1.1 目标

为项目配置 GitHub Actions 持续集成流水线，在每次推送到 `master` 和 Pull Request 时自动运行后端测试、数据库迁移、前端类型检查和前端构建，确保代码变更不引入回归。

### 1.2 范围内

- 新增 `.github/workflows/ci.yml` 工作流文件
- 触发条件：`push` 到 `master` 分支、`pull_request` 到 `master` 分支
- 后端 Job：Python 3.13 环境安装依赖、运行 Alembic 迁移、运行 pytest
- 前端 Job：Node 20 环境安装依赖、运行 `npm run lint`（tsc 类型检查）、运行 `npm run build`（Vite 构建）
- 科学计算包额外安装（弥补 TD-004：`pyproject.toml` 未声明 pandas/numpy/scipy 等）
- CI 失败时通过 GitHub 通知（Status Check）

### 1.3 范围外（不做清单）

| 不做项 | 原因 | 后续入口 |
| --- | --- | --- |
| 不做 CD（持续部署） | V1 本地单用户，无在线部署目标 | V2.0 多用户时评估 |
| 不做 Docker 镜像构建推送 | SPEC 0013 已提供本地 Docker 构建；CI 构建镜像推送需镜像仓库 | V2.0 |
| 不做多 OS 矩阵 | V1 仅需 Ubuntu 验证（生产 Docker 基于 linux）；Windows/macOS 矩阵增加耗时且无增量价值 | V2.0 |
| 不做 code coverage 上传 | 覆盖率非本轮目标；本地 pytest 已足够 | V2.0 |
| 不做 lint 工具集成（ruff/flake8） | 项目后端无 lint 配置；前端 lint 实际是 tsc 类型检查 | V2.0 评估引入 ruff |
| 不做安全扫描（dependabot/trivy） | 依赖安全扫描非本轮目标 | V2.0 |
| 不做缓存优化（pip cache / npm cache） | 首版优先正确性，缓存优化后续迭代 | V1.3.0 |
| 不做并发控制（cancel in-progress） | 首版简单，不引入 concurrency 配置 | V1.3.0 |
| 不做分支保护规则配置 | 分支保护是仓库设置，非代码配置，需项目负责人在 GitHub 侧操作 | 项目负责人手动配置 |
| 不修改任何业务代码 | CI 是基础设施配置，不触碰 server/ 或 apps/web/ 代码 | 永久不做 |

### 1.4 与现有规划的关系

V1.1.0-planning.md 曾明确"CI/CD：本地 MVP 不需要，推迟 V2.0"。本切片将该项提前到 V1.2.0，理由：
- 项目已推送至 GitHub 公开仓库，无 CI 时无法在推送时自动验证回归
- V1.1.0 已有 1115 个测试（704 后端 + 411 前端），CI 可自动运行，降低人工验收成本
- SPEC 0013 Docker 化已收口，CI 可作为 Docker 化之外的另一道质量门禁

---

## 二、架构设计

### 2.1 工作流结构

```
.github/workflows/ci.yml
  ├─ 触发器：push(master) + pull_request(master)
  ├─ Job: backend（ubuntu-latest, Python 3.13）
  │   ├─ checkout 代码
  │   ├─ setup Python 3.13
  │   ├─ pip install -e ".[dev]"（server/ 目录）
  │   ├─ pip install pandas numpy scipy scikit-learn matplotlib psutil（弥补 TD-004）
  │   ├─ alembic upgrade head（临时 SQLite 文件）
  │   └─ pytest
  └─ Job: frontend（ubuntu-latest, Node 20）
      ├─ checkout 代码
      ├─ setup Node 20
      ├─ npm install（根目录，workspace 模式）
      └─ npm run lint && npm run build（apps/web）
```

### 2.2 唯一 Owner 边界

| 层 | Owner 文件 | 职责 | 本轮改动 |
| --- | --- | --- | --- |
| CI 配置 | `.github/workflows/ci.yml`（新建） | 工作流定义、Job 编排、触发条件 | 新建 |
| 后端代码 | `server/` | 业务实现 | 不改动 |
| 前端代码 | `apps/web/` | 业务实现 | 不改动 |
| 依赖清单 | `server/pyproject.toml`、`package.json` | 依赖声明 | 不改动（TD-004 另行处理） |

### 2.3 关键决策：不修复 TD-004，CI 额外安装科学计算包

**决策：** CI 工作流在 `pip install -e ".[dev]"` 后，额外 `pip install pandas numpy scipy scikit-learn matplotlib psutil`。

**理由：**
- TD-004 是独立的依赖声明债务，按 AGENTS.md "无关优化不进入本轮范围"，不在 SPEC 0015 修复 TD-004。
- CI 必须能跑通后端 704 个测试，测试依赖 pandas/numpy/scipy/matplotlib/psutil，必须安装。
- 额外安装步骤显式记录在 ci.yml 注释中，引用 TD-004 作为后续清理入口。
- 当 TD-004 清理后（pyproject.toml 新增 `[project.optional-dependencies] analysis`），CI 改为 `pip install -e ".[dev,analysis]"` 即可。

---

## 三、工作流详细设计

### 3.1 触发条件

```yaml
on:
  push:
    branches: [master]
  pull_request:
    branches: [master]
```

**设计说明：**
- 只对 `master` 分支触发，避免 feature 分支推送产生大量 CI 运行。
- `pull_request` 触发确保 PR 合并前自动验证。
- 不触发 `workflow_dispatch`（手动触发），首版保持简单。

### 3.2 后端 Job

```yaml
jobs:
  backend:
    name: 后端测试（Python 3.13）
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: server

    steps:
      - name: 检出代码
        uses: actions/checkout@v4

      - name: 设置 Python 3.13
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: 安装后端依赖
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
          # TD-004：科学计算包未声明在 pyproject.toml dependencies
          # CI 额外安装以跑通测试，TD-004 清理后改为 pip install -e ".[dev,analysis]"
          pip install pandas==3.0.3 numpy==2.5.1 scipy==1.18.0 \
                      scikit-learn==1.9.0 matplotlib==3.11.0 psutil==7.2.2

      - name: 运行数据库迁移
        env:
          DATABASE_URL: sqlite:///./ci_test.db
        run: python -m alembic upgrade head

      - name: 运行后端测试
        env:
          DATABASE_URL: sqlite:///./ci_test.db
          DEEPSEEK_API_KEY: ""  # CI 不调用真实 LLM，测试全 mock
        run: python -m pytest -q
```

**设计说明：**
- `working-directory: server`：所有命令在 server/ 目录执行，与本地开发一致。
- Python 版本固定 `3.13`，与 Docker 镜像 `python:3.13-slim` 一致（SPEC 0013 决策）。
- 科学计算包版本固定，与 [dependency-review.md](../dev-docs/dependency-review.md) §9.2 记录的 Docker 镜像版本一致。
- `DATABASE_URL` 使用 CI 临时文件 `ci_test.db`，Job 结束自动清理。
- `DEEPSEEK_API_KEY` 留空：SPEC 0007 测试全部 mock HTTP，不调用真实 API。
- pytest 加 `-q` 减少日志输出。

### 3.3 前端 Job

```yaml
  frontend:
    name: 前端类型检查与构建（Node 20）
    runs-on: ubuntu-latest

    steps:
      - name: 检出代码
        uses: actions/checkout@v4

      - name: 设置 Node 20
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: 安装前端依赖
        run: npm install

      - name: 类型检查（lint）
        run: npm run lint

      - name: 生产构建
        run: npm run build
```

**设计说明：**
- Node 版本固定 `20`，与 Docker 镜像 `node:20-slim` 一致（SPEC 0013 决策）。
- `npm install` 在根目录执行（workspace 模式），与本地开发一致。
- `npm run lint` 实际是 `tsc --noEmit`（前端类型检查），定义在根 `package.json`。
- `npm run build` 触发 Vite 构建。
- 两个 Job 并行运行（无依赖关系），缩短 CI 总耗时。

### 3.4 完整工作流文件

```yaml
# GitHub Actions CI 流水线（SPEC 0015）
# 触发：push 到 master 或 pull_request 到 master
# 作用：自动运行后端测试 + 数据库迁移 + 前端类型检查 + 前端构建
# 不做：CD、Docker 镜像构建、多 OS、coverage 上传（详见 SPEC 0015 §1.3）
name: CI

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

jobs:
  backend:
    name: 后端测试（Python 3.13）
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: server

    steps:
      - name: 检出代码
        uses: actions/checkout@v4

      - name: 设置 Python 3.13
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: 安装后端依赖
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
          # TD-004：科学计算包未声明在 pyproject.toml dependencies
          # CI 额外安装以跑通测试，TD-004 清理后改为 pip install -e ".[dev,analysis]"
          pip install pandas==3.0.3 numpy==2.5.1 scipy==1.18.0 \
                      scikit-learn==1.9.0 matplotlib==3.11.0 psutil==7.2.2

      - name: 运行数据库迁移
        env:
          DATABASE_URL: sqlite:///./ci_test.db
        run: python -m alembic upgrade head

      - name: 运行后端测试
        env:
          DATABASE_URL: sqlite:///./ci_test.db
          DEEPSEEK_API_KEY: ""
        run: python -m pytest -q

  frontend:
    name: 前端类型检查与构建（Node 20）
    runs-on: ubuntu-latest

    steps:
      - name: 检出代码
        uses: actions/checkout@v4

      - name: 设置 Node 20
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: 安装前端依赖
        run: npm install

      - name: 类型检查（lint）
        run: npm run lint

      - name: 生产构建
        run: npm run build
```

---

## 四、配置项

### 4.1 不新增环境变量

CI 工作流不引入新的应用配置项。`DATABASE_URL` 和 `DEEPSEEK_API_KEY` 是 SPEC 0001/0007 已有的环境变量，CI 中设置临时值。

### 4.2 Secrets 管理

本轮**不使用任何 GitHub Secrets**：
- `DEEPSEEK_API_KEY` 留空（测试全 mock，不需要真实密钥）
- 无第三方服务凭证
- 无镜像仓库凭证（不做 Docker 镜像推送）

后续若 CI 需要真实 LLM 调用测试，再通过 GitHub Secrets 注入 `DEEPSEEK_API_KEY`，届时需更新本 SPEC。

---

## 五、测试策略

### 5.1 CI 本身的验证

CI 工作流无法用单元测试覆盖，通过以下方式验证：

| 验证项 | 方法 |
| --- | --- |
| 工作流语法正确 | 推送后观察 GitHub Actions 是否能解析工作流 |
| 后端 Job 通过 | 推送后观察 backend job 绿色（704 passed） |
| 前端 Job 通过 | 推送后观察 frontend job 绿色（lint + build 通过） |
| 触发条件正确 | 推送 master 触发；创建 PR 触发 |

### 5.2 本地预演

在推送 ci.yml 前，可在本地模拟 CI 环境：

```text
# 后端模拟（ubuntu 等价环境）
cd server
python -m pip install -e ".[dev]"
pip install pandas==3.0.3 numpy==2.5.1 scipy==1.18.0 scikit-learn==1.9.0 matplotlib==3.11.0 psutil==7.2.2
DATABASE_URL=sqlite:///./ci_test.db python -m alembic upgrade head
DATABASE_URL=sqlite:///./ci_test.db DEEPSEEK_API_KEY="" python -m pytest -q

# 前端模拟
npm install
npm run lint
npm run build
```

### 5.3 验收命令

CI 推送后，通过 GitHub API 或网页确认：

```text
gh run list --limit 5
gh run view <run-id>
```

---

## 六、依赖

### 6.1 不新增项目依赖

CI 工作流使用 GitHub 官方 Actions：
- `actions/checkout@v4`
- `actions/setup-python@v5`
- `actions/setup-node@v4`

这些是 GitHub 托管的 Actions，不进入项目 `package.json` 或 `pyproject.toml`。

### 6.2 运行时依赖

| 依赖 | 版本 | 来源 |
| --- | --- | --- |
| Python | 3.13 | `actions/setup-python@v5` |
| Node.js | 20 | `actions/setup-node@v4` |
| SQLite | 系统自带 | ubuntu-latest 预装 |
| 后端 Python 包 | 见 `pyproject.toml` + 科学计算包固定版本 | PyPI |
| 前端 npm 包 | 见 `package.json` | npm registry |

---

## 七、验收标准

| AC # | 验收项 | 通过标准 |
| --- | --- | --- |
| AC-1 | 工作流文件创建 | `.github/workflows/ci.yml` 存在且语法正确 |
| AC-2 | 触发条件 | push 到 master 触发 CI；PR 到 master 触发 CI |
| AC-3 | 后端 Job 通过 | backend job 绿色，704 passed, 0 warnings |
| AC-4 | 数据库迁移通过 | `alembic upgrade head` 在临时 SQLite 成功 |
| AC-5 | 前端 Job 通过 | frontend job 绿色，tsc --noEmit 通过 |
| AC-6 | 前端构建通过 | `npm run build` Vite 构建成功 |
| AC-7 | 不修改业务代码 | `git diff` 确认 server/ 和 apps/web/ 无改动 |
| AC-8 | 不使用 Secrets | 工作流无 secrets 引用 |
| AC-9 | 文档回写 | acceptance.md、README.md 更新 CI 说明 |
| AC-10 | 分支状态可见 | GitHub master 分支显示最新 CI 状态 |

---

## 八、实施顺序

按 AGENTS.md 阶段闸：

1. **SPEC 0015 文档确认**（本文件，待项目负责人批准）
2. **创建 `.github/workflows/ci.yml`**
3. **本地预演**（按 §5.2 在本地模拟 CI 命令）
4. **推送 ci.yml 到 master**
5. **观察 GitHub Actions 运行结果**（`gh run list`）
6. **修复 CI 失败项**（如有，常见：路径问题、依赖版本、权限）
7. **确认两个 Job 全绿**
8. **文档回写**（acceptance.md、README.md）
9. **git 提交推送**（含 ci.yml + 文档回写）

---

## 九、风险与回退

### 9.1 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| CI 环境科学计算包安装失败 | 低 | backend job 失败 | 固定版本 + 与 Docker 镜像版本一致 |
| 数据库迁移在 CI 环境失败 | 低 | backend job 失败 | 使用临时 SQLite 文件，与本地 alembic 命令一致 |
| 前端 npm install 失败 | 低 | frontend job 失败 | ubuntu-latest 预装 npm；固定 Node 20 |
| 工作流语法错误 | 低 | 工作流不触发 | 本地预演 + GitHub 网页语法检查 |
| CI 耗时过长 | 中 | 开发体验下降 | 两个 Job 并行；首版不优化缓存，后续迭代 |
| 误触发大量 CI 运行 | 低 | Actions 配额消耗 | 只对 master 触发；不做 feature 分支推送触发 |

### 9.2 回退方案

如 CI 引入问题，可通过以下方式回退：

1. **临时禁用：** 删除 `.github/workflows/ci.yml` 或重命名为 `.github/workflows/ci.yml.disabled`
2. **保留历史：** Git 历史保留 ci.yml，可随时恢复
3. **不影响业务：** CI 是独立工作流，失败不影响应用运行

### 9.3 最大回归风险

**最大风险：** CI 配置不当导致推送被阻断（分支保护规则强制 CI 通过才能合并）。

**阻断证据：**
- 本轮**不配置分支保护规则**（§1.3 明确不做），CI 失败不阻断推送
- CI 仅作为通知手段，首版不强制
- 分支保护需项目负责人在 GitHub 仓库设置中手动开启，本 SPEC 不覆盖

---

## 十、确认事项（待项目负责人确认）

> 本章节的技术决策需项目负责人确认后方可进入实现。

### 10.1 触发分支：仅 master

**决策：** CI 仅对 `master` 分支的 push 和 pull_request 触发，不对 feature 分支触发。

**理由：** 首版优先简单。feature 分支推送触发 CI 会增加 Actions 配额消耗，且 V1 单人开发场景下 master 即主开发分支。

### 10.2 不配置分支保护

**决策：** 本轮不配置 GitHub 分支保护规则，CI 失败不阻断推送。

**理由：** 首版 CI 优先正确性验证，不强制门禁。分支保护需项目负责人在 GitHub 设置中手动开启，确认 CI 稳定后再启用。

### 10.3 不使用缓存

**决策：** 首版不配置 pip cache 和 npm cache。

**理由：** 优先正确性。缓存配置增加复杂度，首版接受较慢的 CI（预计 5-8 分钟）。V1.3.0 再优化。

### 10.4 科学计算包额外安装

**决策：** CI 额外 `pip install` 科学计算包，不修复 TD-004。

**理由：** TD-004 是独立债务，不在本切片范围。CI 额外安装步骤带注释引用 TD-004 作为后续清理入口。

---

## 十一、与 V1.2.0 整体规划的关系

本切片是 V1.2.0 的第三个 SPEC：

| SPEC | 关注点 | owner 层 | 风险隔离 |
| --- | --- | --- | --- |
| SPEC 0013 | Docker 化部署 | 基础设施（Dockerfile/compose） | 不触碰业务代码 |
| SPEC 0014 | LLM 调用缓存 | 基础设施（llm_cache.py） + LLM 模块 | 不触碰业务数据库 |
| SPEC 0015 | CI 流水线 | 基础设施（.github/workflows/） | 不触碰业务代码 |

三切片正交，可独立验收。SPEC 0015 不依赖 SPEC 0013/0014，但建议在 SPEC 0013/0014 收口后再启用 CI，避免 CI 频繁失败。

**建议实施顺序：** SPEC 0013（已收口）→ SPEC 0014（缓存）→ SPEC 0015（CI）。SPEC 0015 最后实施，确保 CI 启用时代码已稳定，CI 能持续绿色。
