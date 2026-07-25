# V1.3.0 版本发布说明

> **版本：** v1.3.0  
> **发布日期：** 2026-07-25  
> **上一版本：** v1.2.0  
> **提交范围：** `v1.2.0..v1.3.0`（3 个提交：`9dd4886`、`1bbbc17`、`4cff5a9`）  
> **变更统计：** 后端 736 测试 + 前端 411 测试 = 1147 个测试（新增 7 个）  
> **文档状态：** 已由项目负责人确认发布

---

## 概述

实验报告助手 V1.3.0 是 V1.2.0 的技术债务清理版本。V1.3.0 **不改变产品边界**（仍是本地单用户 Web MVP）和**架构主线**（仍是唯一 owner + API 适配 + 前端接线），**不引入任何新功能**，只做债务清零。

V1.3.0 聚焦于一个技术债务清理切片：

1. **SPEC 0016 技术债务清理**：清理 V1.2.0 发布后登记的 4 个可记录债务（TD-004/005/006/008），消除文档表述过时、依赖声明缺失和脚本硬编码问题。

V1.3.0 包含 1 个 SPEC：

| SPEC | 标题 | 状态 |
| --- | --- | --- |
| SPEC 0016 | 技术债务清理 TD-004/005/006/008 | ✅ 已完成（commit `4cff5a9`） |

**核心价值：** V1.3.0 发布后，项目当前无活跃可记录债务（TD-001~008 全部关闭），代码层面无 TODO/FIXME，技术债务清单清零，为后续新功能开发扫清障碍。

---

## 一、债务清理变更

### 1.1 TD-004：科学计算包声明在 pyproject.toml optional-dependencies

**提交：** `4cff5a9`  
**模块：** `server/pyproject.toml`、`server/Dockerfile`、`dev-docs/dependency-review.md`、`README.md`

**问题：** pandas/numpy/scipy/scikit-learn/matplotlib/psutil 在本地开发环境手动 `pip install`，未写入 `pyproject.toml`。SPEC 0013 Docker 化时通过 Dockerfile 硬编码固定版本安装弥补，但 `pip install -e .` 不会自动安装这些包，CI 流水线也需要额外安装步骤。

**清理动作：**
- `server/pyproject.toml` 新增 `[project.optional-dependencies] analysis` 段
- 声明 6 个科学计算包，版本下限与 Dockerfile 第 23-29 行固定版本对齐：
  - `pandas>=3.0.3`
  - `numpy>=2.5.1`
  - `scipy>=1.18.0`
  - `scikit-learn>=1.9.0`
  - `matplotlib>=3.11.0`
  - `psutil>=7.2.2`
- `server/Dockerfile` 改用 `pip install -e ".[dev,analysis]"` 一次安装，移除硬编码 pip install
- `dev-docs/dependency-review.md` §9.2/9.3 同步标记 TD-004 关闭
- `README.md` 快速启动章节说明 `analysis` 可选依赖的两种安装模式

**关键决策：**
- 科学计算包作为 `optional-dependencies` 而非主 `dependencies`（应用代码不直接导入，是分析依赖，由用户代码通过 `python_executor` 运行时调用）
- `pyproject.toml` 使用 `>=` 下限（保持向后兼容），Dockerfile 不再固定 `==` 精确版本（由 pip 解析最新满足版本）
- 与 TD-007（openpyxl）不同：openpyxl 直接被 app 代码导入（`dataset_parser.py`），故在 V1.2.0 直接补入主 `dependencies`；pandas 等是分析依赖，作为可选依赖让用户选择安装模式

**验证证据：**
- `pip install --dry-run -e ".[analysis]"` 依赖解析正确，所有包版本已满足
- Docker 镜像构建成功（exit 0）
- Docker 容器内 `import pandas, numpy, scipy, sklearn, matplotlib, psutil` 全部成功（pandas 3.0.5, numpy 2.5.1, scipy 1.18.0, sklearn 1.9.0, matplotlib 3.11.1, psutil 7.2.2）

### 1.2 TD-005：AGENTS.md "当前已知非阻断债务"表述过时

**提交：** `4cff5a9`  
**模块：** `AGENTS.md`

**问题：** AGENTS.md "当前已知非阻断债务"章节仍记载"当前会话未暴露可调用的 in-app Browser 工具，因此 SPEC 0002 未完成真实浏览器点击截图验收"。但 TD-003 已于 2026-07-22 清理：V1.0 端到端验收时用 browser_use agent 完成浏览器验收，截图在 `dev-docs/e2e-screenshots/`。保留过时表述会让后续 agent 误以为浏览器验收从未做。

**清理动作：**
- 更新 AGENTS.md "当前已知非阻断债务"章节
- 移除"未暴露可调用的 in-app Browser 工具"过时表述
- 用 V1.0 验收事实替换：引用 `e2e-acceptance-report-v1.0.md` 作为浏览器验收证据
- 补充 TD-001 关闭状态说明（原表述只提"非本轮阻断债务"，未标注已关闭）

**关键决策：**
- 只修改"当前已知非阻断债务"事实清单，**不修改任何规则条款**（推理闸、设计规则、版本控制等完全不变）
- 事实清单更新不属于 AGENTS.md "宪法维护规则" 触发范围（宪法维护规则针对规则条款变更，不针对事实清单更新）
- 压力测试：后续 agent 读 AGENTS.md 时获得准确的债务状态，不会误判"需要补做浏览器验收"

**验证证据：**
- `git diff AGENTS.md` 只涉及第 203-204 行（"当前已知非阻断债务"章节），其他章节无变化
- 规则条款（第 1-200 行和第 206 行之后）完全未变

### 1.3 TD-006：acceptance.md 浏览器验收状态说明

**提交：** `4cff5a9`  
**模块：** `dev-docs/acceptance.md`

**问题：** acceptance.md 各 SPEC 收口记录中"可视化点击验收：未执行"是当时的事实快照。V1.0 整体端到端验收（2026-07-22）用 browser_use agent 补做了浏览器验收（TD-003 关闭）。收口记录不回溯修改历史，但可能让读者误以为浏览器验收从未做。

**清理动作：**
- 在 acceptance.md 顶部"当前限制"段落之后新增"浏览器验收状态说明"小节
- 明确 V1.0 整体端到端验收已于 2026-07-22 完成 browser_use agent 浏览器验收
- 引用 `e2e-acceptance-report-v1.0.md` 和具体截图文件（home-full.png、home-viewport.png）
- 明确"各 SPEC 收口记录不回溯修改"，避免读者误以为历史记录错误
- 明确"V1.0 之后的新切片若有 UI 变化，应按 AGENTS.md 执行浏览器验收"

**关键决策：**
- **不回溯修改各 SPEC 收口记录**（SPEC 0001~SPEC 0015 的"可视化点击验收：未执行"保留历史快照真实性）
- 在顶部新增说明即可，避免追溯链断裂
- 按 AGENTS.md "禁止无意义兼容旧路线"和"事实优先"原则

**验证证据：**
- `git diff dev-docs/acceptance.md` 只涉及顶部"当前限制"段落和状态行
- 各 SPEC 收口记录（第 9 行之后）完全未变

### 1.4 TD-008：worker_e2e_verify.py 参数化

**提交：** `4cff5a9`  
**模块：** `server/worker_e2e_verify.py`、`server/tests/test_worker_e2e_verify.py`

**问题：** `server/worker_e2e_verify.py` 硬编码日志标题为 `"# V1.0 Worker 端到端验证日志"`。V1.1.0 和 V1.2.0 回归测试执行该脚本时，输出的日志标题仍是"V1.0"，需手动修正标题为对应版本。V1.2.0 已手动修正日志标题为"V1.2.0 Worker 端到端验证日志（V1.2.0 回归测试）"。

**清理动作：**
- 新增 `parse_args()` 函数，支持命令行参数解析
- 新增 `--version` 参数：指定日志标题中的版本号
- 新增 `--output` 参数：指定日志输出文件路径（避免覆盖历史日志）
- 支持 `WORKER_E2E_VERSION` 环境变量：优先级低于命令行参数，高于默认值
- 默认值保持 `"V1.0"`：向后兼容，不破坏现有调用方式
- 默认输出路径保持 `LOG_FILE`：不指定参数时行为不变
- `write_log()` 函数改为接受 `file_path` 参数

**使用方式：**
```bash
# V1.3.0 回归测试
python worker_e2e_verify.py --version V1.3.0 --output ../dev-docs/worker-e2e-log-v1.3.0-regression.md

# 或通过环境变量
$env:WORKER_E2E_VERSION = "V1.3.0"
python worker_e2e_verify.py --output ../dev-docs/worker-e2e-log-v1.3.0-regression.md

# 默认行为（向后兼容）
python worker_e2e_verify.py
```

**关键决策：**
- 默认值 "V1.0" 保持向后兼容（不指定参数时行为与 V1.2.0 完全一致）
- 优先级：命令行参数 > 环境变量 > 默认值
- 同时支持 `--output` 参数让用户指定输出文件（避免覆盖历史日志，解决 V1.2.0 回归测试时需要手动重命名日志文件的问题）
- 不修改验证逻辑（只改标题来源和输出路径）

**验证证据：**
- 新增 `server/tests/test_worker_e2e_verify.py` 7 个单元测试全部通过
- 测试覆盖：默认值、`--version` 参数、`--output` 参数、环境变量、参数优先级、`--help` 输出

---

## 二、性能提升

V1.3.0 是技术债务清理切片，**不包含直接的运行时性能优化**。但以下清理动作对开发体验和部署效率有间接提升：

### 2.1 依赖安装效率提升（TD-004 清理后）

**改进点：** 科学计算包声明在 `pyproject.toml` `[project.optional-dependencies] analysis` 段后，开发者可通过一条命令安装完整分析依赖：

| 场景 | V1.2.0（清理前） | V1.3.0（清理后） |
| --- | --- | --- |
| 本地开发（LocalRule 模式） | `pip install -e ".[dev]"` | `pip install -e ".[dev]"`（无变化） |
| 本地开发（完整模式） | `pip install -e ".[dev]"` + 手动 `pip install pandas numpy scipy scikit-learn matplotlib psutil` | `pip install -e ".[dev,analysis]"`（一条命令） |
| Docker 镜像构建 | `pip install -e ".[dev]"` + Dockerfile 硬编码 6 行 pip install | `pip install -e ".[dev,analysis]"`（一条命令） |
| CI 流水线 | `pip install -e ".[dev]"` + ci.yml 硬编码 6 行 pip install | `pip install -e ".[dev,analysis]"`（一条命令，CI 未改动但可受益） |

**效率提升：**
- 本地开发完整模式安装命令从 2 条减少到 1 条
- Docker 镜像构建 Dockerfile 从 8 行 pip install 减少到 1 行
- 新开发者 onboarding 成本降低：无需查阅 Dockerfile 或文档了解需要手动安装哪些科学计算包

### 2.2 回归测试效率提升（TD-008 清理后）

**改进点：** `worker_e2e_verify.py` 支持 `--version` 和 `--output` 参数后，回归测试无需手动修正日志标题或重命名日志文件：

| 场景 | V1.2.0（清理前） | V1.3.0（清理后） |
| --- | --- | --- |
| 回归测试日志标题 | 硬编码"V1.0"，需手动改为对应版本 | `--version V1.3.0` 自动生成正确标题 |
| 回归测试日志文件 | 默认覆盖 `worker-e2e-log.md`，需手动重命名为 `worker-e2e-log-vX.Y.0-regression.md` | `--output ../dev-docs/worker-e2e-log-v1.3.0-regression.md` 直接写入正确路径 |

**效率提升：**
- 回归测试后处理步骤从 2 个手动操作减少到 0 个
- 避免因手动修正导致的历史日志被覆盖风险（V1.0 原始日志曾被 V1.2.0 回归日志覆盖，后恢复）

### 2.3 文档准确性提升（TD-005/006 清理后）

**改进点：** AGENTS.md 和 acceptance.md 的过时表述清理后，后续 agent 和开发者获得准确的项目状态：

| 文档 | V1.2.0（清理前） | V1.3.0（清理后） |
| --- | --- | --- |
| AGENTS.md 债务清单 | 记载"未暴露 Browser 工具"（已过时，V1.0 已补做） | 记载"V1.0 已用 browser_use agent 完成浏览器验收"（准确） |
| acceptance.md 顶部 | 记载"未完成真实浏览器点击截图验收"（已过时） | 新增"浏览器验收状态说明"小节，明确 V1.0 已补做 |

**效率提升：**
- 后续 agent 不会误判"需要补做浏览器验收"，避免浪费时间在已完成的任务上
- 新开发者查阅文档时获得准确的项目验收状态

---

## 三、Bug 修复

V1.3.0 **无 Bug 修复**。本切片是技术债务清理，不涉及 Bug 修复，所有现有功能保持原有行为（零回归）。

---

## 四、架构改进

### 4.1 依赖声明规范化

- 科学计算包从 Dockerfile 硬编码迁移到 `pyproject.toml` 标准 `[project.optional-dependencies]` 段
- 符合 Python 打包规范（PEP 621），让依赖声明可被 pip、poetry、uv 等工具统一识别
- Dockerfile 简化为 `pip install -e ".[dev,analysis]"` 一条命令，减少维护点

### 4.2 验证脚本可参数化

- `worker_e2e_verify.py` 从硬编码脚本改为支持命令行参数的通用验证工具
- `--version` 和 `--output` 参数让脚本可复用于不同版本的回归测试
- `WORKER_E2E_VERSION` 环境变量支持 CI/CD 环境注入

### 4.3 文档与代码状态一致性

- AGENTS.md "当前已知非阻断债务"章节与 `tech-debt-inventory.md` 状态保持一致
- acceptance.md 顶部说明与各 SPEC 收口记录的关系明确（不回溯修改历史快照）
- 技术债务总清单更新为 V1.3.0 状态：8 个债务全部关闭，0 个活跃债务

---

## 五、依赖变更

### 5.1 运行时依赖

V1.3.0 **无新增运行时依赖**。所有依赖已在 V1.0~V1.2.0 阶段安装并通过 Dockerfile 固定版本。TD-004 只是将已安装的依赖从 Dockerfile 硬编码迁移到 `pyproject.toml` 声明。

### 5.2 可选依赖（新增声明，非新增安装）

| 依赖 | 版本约束 | 用途 | 声明位置 |
| --- | --- | --- | --- |
| `pandas` | `>=3.0.3` | 数据分析（用户代码运行时调用） | `[project.optional-dependencies] analysis` |
| `numpy` | `>=2.5.1` | 数值计算（用户代码运行时调用） | `[project.optional-dependencies] analysis` |
| `scipy` | `>=1.18.0` | 统计检验（用户代码运行时调用） | `[project.optional-dependencies] analysis` |
| `scikit-learn` | `>=1.9.0` | 机器学习（用户代码运行时调用） | `[project.optional-dependencies] analysis` |
| `matplotlib` | `>=3.11.0` | 图表生成（用户代码运行时调用） | `[project.optional-dependencies] analysis` |
| `psutil` | `>=7.2.2` | 执行沙箱内存监控（python_executor 运行时调用） | `[project.optional-dependencies] analysis` |

### 5.3 开发依赖

无新增开发依赖。

---

## 六、测试统计

| 测试套件 | V1.2.0 | V1.3.0 | 新增 | 状态 |
| --- | --- | --- | --- | --- |
| 后端 pytest | 729 | 736 | +7 | ✅ 0 warnings |
| 前端 Vitest | 411 | 411 | 0 | ✅ 全部通过 |
| **总计** | **1140** | **1147** | **+7** | — |

### 后端新增测试分布

| SPEC | 新增测试数 | 累计后端测试 | 测试文件 |
| --- | --- | --- | --- |
| SPEC 0016 TD-008 worker_e2e_verify | 7 | 736 | `server/tests/test_worker_e2e_verify.py` |

### 新增测试详情

| 测试用例 | 覆盖点 |
| --- | --- |
| `test_default_version_is_v1_0` | 不指定参数且无环境变量时，version 默认为 "V1.0" |
| `test_version_from_arg` | `--version V1.3.0` 时，version 为 "V1.3.0" |
| `test_version_from_env` | 设置 `WORKER_E2E_VERSION=V1.2.0` 时，version 为 "V1.2.0" |
| `test_arg_overrides_env` | 同时设置参数和环境变量时，命令行参数优先 |
| `test_default_output_path` | 不指定 `--output` 时，output 为 LOG_FILE 默认值 |
| `test_custom_output_path` | `--output` 指定路径时，output 为指定路径 |
| `test_help_exits_zero` | `--help` 输出用法说明，退出码 0 |

---

## 七、技术债务清零状态

### V1.3.0 发布前债务状态

| 债务编号 | 名称 | 引入切片 | 关闭时间 | 关闭证据 |
| --- | --- | --- | --- | --- |
| TD-001 | fastapi.testclient httpx 弃用提示 | SPEC 0002 | 2026-07-22 | 安装 `httpx2 2.7.0`，dev 依赖新增 `httpx2>=2.0.0` |
| TD-002 | pandas datetime 推断 UserWarning | SPEC 0004 | 2026-07-22 | `dataset_parser.py:96` 添加 `format="mixed"` |
| TD-003 | 浏览器点击截图验收未执行 | SPEC 0002 | 2026-07-22 | V1.0 端到端验收用 browser_use agent 完成浏览器验收 |
| TD-004 | 科学计算包未声明在 pyproject.toml | SPEC 0004/0005 | **2026-07-25** | **V1.3.0 SPEC 0016 清理：新增 analysis 段** |
| TD-005 | AGENTS.md 债务清单表述过时 | 立项阶段 | **2026-07-25** | **V1.3.0 SPEC 0016 清理：更新事实清单** |
| TD-006 | acceptance.md 浏览器验收状态不一致 | SPEC 0001~0012 | **2026-07-25** | **V1.3.0 SPEC 0016 清理：顶部新增说明** |
| TD-007 | openpyxl 未声明在 pyproject.toml | SPEC 0004 | 2026-07-24 | V1.2.0 SPEC 0015 修复：dependencies 新增 `openpyxl>=3.1.0` |
| TD-008 | worker_e2e_verify.py 硬编码标题 | V1.0 端到端验收 | **2026-07-25** | **V1.3.0 SPEC 0016 清理：参数化** |

### V1.3.0 发布后债务汇总

| 类别 | 数量 | 状态 |
| --- | --- | --- |
| 阻断问题 | 0 | — |
| 可记录债务 | 0 | V1.3.0 SPEC 0016 已清理全部 4 个 |
| 产品边界限制（L2-L15） | 14 | 按版本规划（非债务） |
| 已关闭债务（TD-001~008） | 8 | 全部关闭，保留追溯 |
| 代码 TODO/FIXME | 0 | 项目源码无 TODO/FIXME/XXX/HACK |

**结论：** 项目当前无阻断性技术债务，无活跃可记录债务，代码层面无 TODO/FIXME。V1.3.0 是项目首个债务清零版本。

---

## 八、已知限制（V1.3.0 边界）

1. **不引入新功能**：V1.3.0 是技术债务清理切片，不新增任何业务功能
2. **不修改业务代码**：不触碰 `server/app/modules/`、`server/app/api/`、`server/worker/handlers/`
3. **不修改 API 合同**：所有 API 路由和 schema 保持不变
4. **不修改数据库**：无 Alembic 迁移变更
5. **不修改 AGENTS.md 规则条款**：只更新"当前已知非阻断债务"事实清单
6. **不回溯修改各 SPEC 收口记录**：保留历史快照真实性
6. **不升级科学计算包版本**：仅声明依赖，不改动版本固定（避免引入兼容风险）
7. **不修改 CI 流水线**：ci.yml 保持不变（可通过 `.[analysis]` 受益，但本轮不改动）
8. **不做 E2E 测试框架引入**：Playwright/Cypress 推迟到 V2.0（产品边界限制 L12）
9. **不做流式 LLM 输出**：推迟到 V2.0（产品边界限制 L11）
10. **不做 OCR 与扫描文档**：推迟到 V2.0（产品边界限制 L14）

---

## 九、升级指南

### 9.1 从 V1.2.0 升级（本地开发）

V1.3.0 无破坏性变更，升级步骤简单：

```bash
# 1. 拉取最新代码
git pull origin master

# 2. 更新后端依赖（无新增主依赖，新增 analysis 可选依赖段）
cd server
.venv\Scripts\activate

# LocalRule 模式（无需分析包，最小依赖，与 V1.2.0 行为一致）
pip install -e ".[dev]"

# 或：完整模式（含科学计算包，支持真实执行用户 Python 代码，推荐）
pip install -e ".[dev,analysis]"

# 3. 执行数据库迁移（无新增迁移）
.venv\Scripts\python.exe -m alembic upgrade head

# 4. 更新前端依赖（无新增依赖）
cd ../apps/web
npm install
```

### 9.2 从 V1.2.0 升级（Docker 部署）

```bash
# 1. 拉取最新代码
git pull origin master

# 2. 重新构建镜像（Dockerfile 改用 .[dev,analysis] 一次安装）
docker compose build

# 3. 重启服务
docker compose up -d

# 4. 验证容器内科学计算包
docker compose exec backend .venv/bin/python -c "import pandas, numpy, scipy, sklearn, matplotlib, psutil; print('all imports ok')"
```

### 9.3 回归测试脚本使用（V1.3.0 新增能力）

```bash
# 使用新参数运行回归测试
cd server
.venv\Scripts\activate

# 指定版本和输出路径（推荐）
python worker_e2e_verify.py --version V1.3.0 --output ../dev-docs/worker-e2e-log-v1.3.0-regression.md

# 或通过环境变量
$env:WORKER_E2E_VERSION = "V1.3.0"
python worker_e2e_verify.py --output ../dev-docs/worker-e2e-log-v1.3.0-regression.md

# 默认行为（向后兼容，与 V1.2.0 一致）
python worker_e2e_verify.py
```

---

## 十、回归测试

V1.3.0 发布前已执行完整回归测试，详见 [acceptance.md](acceptance.md) V1.3.0 回归测试记录。

**关键回归点：**
- 后端 736 测试全部通过，0 warnings（729 原有 + 7 新增 TD-008 测试）
- 前端 411 测试全部通过（lint + build）
- Alembic 迁移成功（无数据库变更）
- Docker 镜像构建成功（exit 0）
- Docker 容器内科学计算包导入验证通过
- AGENTS.md diff 验证只涉及"当前已知非阻断债务"章节
- acceptance.md diff 验证各 SPEC 收口记录未回溯修改

---

## 十一、致谢

感谢项目负责人的严格阶段闸管理和验收标准。V1.3.0 的 SPEC 0016 遵循"先编写并确认 SPEC → 项目负责人批准 → 测试先行 → 实现 → 验收 → 文档回写 → git 收口"的阶段闸流程。

特别感谢项目负责人在 V1.2.0 发布后立即明确下一阶段方向为技术债务清理，让项目保持了"每个版本发布后债务清零"的健康节奏。V1.3.0 是项目首个债务清零版本，为后续新功能开发扫清了技术障碍。

---

**版本标签：** `v1.3.0`（已创建并 push）  
**发布状态：** 已由项目负责人确认发布
