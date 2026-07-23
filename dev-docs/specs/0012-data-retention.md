# SPEC 0012｜数据保留周期配置

> 状态：SPEC 已编写，待项目负责人确认后进入实现
> 版本：v1.0
> 日期：2026-07-23
> 关联：[v1.1.0-planning.md](../v1.1.0-planning.md) 增强目标 6、[0012-test-plan.md](0012-test-plan.md)

---

## 1. 背景与目标

### 1.1 问题

当前项目数据无限增长：SQLite 数据库（18 张业务表）+ `PROJECT_DATA_ROOT` 文件系统目录（项目工作区）会随使用持续累积，无任何清理机制。长期使用后数据膨胀，影响存储和性能，且过期数据无保留价值。

### 1.2 目标

提供可选的手动清理能力，让用户按保留周期清理过期项目数据：

- 新增 `DATA_RETENTION_DAYS` 环境变量配置保留周期
- 新增手动清理脚本，支持 dry-run 预览和 execute 实际删除
- 以项目为单位级联清理，确保数据库记录和文件系统目录完整删除
- 保护运行中任务，避免清理有活跃 Job 的项目

### 1.3 价值

- 用户可控制数据增长，按需清理过期项目
- 默认永久保留（`DATA_RETENTION_DAYS=0`），不影响现有行为
- 手动执行，不引入自动清理的复杂性

---

## 2. 范围

### 2.1 做什么

| 能力 | 说明 |
| --- | --- |
| `DATA_RETENTION_DAYS` 环境变量 | int 类型，0=永久保留（默认），>0=保留 N 天，超过 N 天的项目进入清理列表 |
| 过期判断 | 基于 `Project.updated_at` 字段（项目最近更新时间），活跃项目自动重置计时器 |
| 手动清理脚本 | `server/scripts/cleanup_expired_data.py`，支持 `--dry-run`（默认）和 `--execute` |
| 级联清理 | 以项目为单位，删除 18 张表关联记录 + 文件系统 `{project_id}/` 目录 |
| RUNNING job 保护 | 清理前检查项目是否有 `PENDING`/`RUNNING` 状态的 Job，有则跳过 |
| 安全机制 | 默认 dry-run；0 天保留期不清理；清理失败继续其他项目 |

### 2.2 不做什么

| 不做项 | 原因 | 推迟到 |
| --- | --- | --- |
| 自动定时清理 | V1.1.0 保持手动，避免引入 scheduler 依赖 | V2.0 |
| 项目级保留策略 | 全局统一，避免复杂度 | V2.0 |
| 软删除/回收站 | 物理删除，简单直接 | 不做 |
| Web UI 触发清理 | 只命令行 | V2.0 |
| 清理历史记录表 | 不记录清理操作本身 | 不做 |
| LLM 调用日志清理 | L3 表独立，不在本轮范围 | V2.0 |
| 数据库 VACUUM 优化 | SQLite 清理后空间回收 | 可选手动执行 |
| 前端变更 | 本切片无前端改动 | — |

---

## 3. 技术设计

### 3.1 配置层

**文件：[server/app/core/config.py](../../server/app/core/config.py)**

新增 `data_retention_days` property，遵循现有 Settings 类模式：

```python
@property
def data_retention_days(self) -> int:
    """数据保留天数，0=永久保留，>0=保留 N 天。

    非法值（负值、非数字）降级到 0（永久保留）。
    """
    raw = os.getenv("DATA_RETENTION_DAYS", "0")
    try:
        value = int(raw)
        if value < 0:
            return 0
        return value
    except (TypeError, ValueError):
        return 0
```

**设计要点：**
- 浮点数处理：`int(raw)` 截断为整数（与现有 `execution_timeout_seconds` 等配置模式一致），如 `30.5` → `30`
- 负值降级到 0（永久保留），记录 warning 由调用方处理
- 空字符串降级到 0

### 3.2 过期判断逻辑

**判断字段：`Project.updated_at`**

- [projects/models.py:30-34](../../server/app/modules/projects/models.py) 中 `updated_at` 有 `onupdate=lambda: datetime.now(timezone.utc)`，任何字段更新自动刷新
- 活跃项目（状态变更、字段更新）会自动重置保留计时器，无需额外维护
- 过期条件：`Project.updated_at < now - timedelta(days=DATA_RETENTION_DAYS)`

**为什么用 `updated_at` 而非 `created_at`：**
- `updated_at` 更合理：活跃项目（有任何更新）不应过期，只有长期未活动的项目才清理
- 自动刷新：`onupdate` 机制确保状态推进时自动重置计时器
- 与现有行为一致：`list_projects` 已按 `updated_at` 降序排列（[projects/service.py:47-52](../../server/app/modules/projects/service.py)）

### 3.3 RUNNING job 保护

**文件：[server/app/modules/jobs/service.py](../../server/app/modules/jobs/service.py)**

新增 `has_active_jobs` 查询方法（jobs 模块作为唯一 owner）：

```python
def has_active_jobs(db: Session, project_id: str) -> bool:
    """检查项目是否有活跃任务（PENDING 或 RUNNING）。

    用于清理脚本保护：有活跃任务的项目跳过清理。
    """
    count = (
        db.query(BackgroundJob)
        .filter(
            BackgroundJob.project_id == project_id,
            BackgroundJob.status.in_([
                JobStatus.PENDING.value,
                JobStatus.RUNNING.value,
            ]),
        )
        .count()
    )
    return count > 0
```

**清理脚本调用：**
- 每个过期项目清理前调用 `has_active_jobs`
- 返回 True 时跳过该项目，记录 warning"项目 X 有活跃任务，跳过清理"
- 返回 False 时继续清理

### 3.4 清理脚本

**文件：`server/scripts/cleanup_expired_data.py`（新建）**
**文件：`server/scripts/__init__.py`（新建，包初始化）**

**命令行接口：**

```bash
# 默认 dry-run，只输出清理报告，不删除
python -m scripts.cleanup_expired_data

# 显式 dry-run
python -m scripts.cleanup_expired_data --dry-run

# 实际执行清理
python -m scripts.cleanup_expired_data --execute

# 查看帮助
python -m scripts.cleanup_expired_data --help
```

**执行流程：**

```
1. 读取 DATA_RETENTION_DAYS 配置
2. 若为 0，输出"保留期为永久，无过期项目"，退出
3. 查询所有 updated_at < now - retention_days 的项目
4. 对每个过期项目：
   a. 检查 has_active_jobs，有则跳过 + warning
   b. dry-run 模式：只收集报告信息
   c. execute 模式：
      - 删除文件系统 {PROJECT_DATA_ROOT}/{project_id}/ 目录
      - 按依赖顺序删除数据库关联记录（叶子→根）
      - 记录清理结果
5. 输出清理报告（项目数、成功/失败/跳过数）
6. 退出（有失败时退出码非 0）
```

**参数解析：**
- `--dry-run` / `--execute` 互斥，同时指定时 dry-run 优先（安全优先）
- `--help` 输出用法说明

### 3.5 级联删除顺序

**文件系统**（先删文件，后删数据库）：
- 删除 `PROJECT_DATA_ROOT/{project_id}/` 整个目录（含 sources/、executions/、word_template/ 等子目录）
- 目录不存在时记录 warning，继续清理数据库记录

**数据库**（按外键依赖，叶子→根）：

| 顺序 | 表名 | 模块 | 说明 |
| --- | --- | --- | --- |
| 1 | `execution_artifacts` | execution | 叶子，依赖 execution_runs |
| 2 | `execution_runs` | execution | 依赖 code_tasks |
| 3 | `code_tasks` | execution | 依赖 projects |
| 4 | `deliverable_versions` | outlines | 叶子，依赖 deliverables |
| 5 | `deliverables` | outlines | 依赖 outlines |
| 6 | `outlines` | outlines | 依赖 projects |
| 7 | `word_templates` | outlines | 依赖 projects |
| 8 | `analysis_plans` | analysis | 依赖 projects |
| 9 | `dataset_versions` | datasets | 依赖 datasets |
| 10 | `datasets` | datasets | 依赖 projects |
| 11 | `evidence_cards` | sources | 依赖 sources |
| 12 | `parsed_documents` | sources | 依赖 sources |
| 13 | `sources` | sources | 依赖 projects |
| 14 | `change_records` | requirements | 依赖 projects |
| 15 | `requirement_plans` | requirements | 依赖 projects |
| 16 | `requirement_sources` | requirements | 依赖 projects |
| 17 | `background_jobs` | jobs | 依赖 projects |
| 18 | `projects` | projects | 根表，最后删除 |

**清理方式：** 按 `project_id` 过滤删除（`DELETE FROM {table} WHERE project_id = ?`）

### 3.6 文件系统锁定处理

Windows 下文件可能被占用（如用户正在查看交付物）：
- 使用 `shutil.rmtree(path, ignore_errors=True)` 删除目录
- 删除后检查目录是否仍存在，存在则记录 warning"文件系统目录删除不完整"
- 继续清理数据库记录（避免数据不一致：数据库已删但文件残留）
- 不阻塞清理流程

---

## 4. 数据模型影响

**SPEC 0012 无 schema 变更。**

- 不新增表、不新增字段、不新增迁移
- 配置不持久化（`DATA_RETENTION_DAYS` 只读环境变量）
- 清理操作直接 DELETE，不新增软删除字段

**受影响的现有表：** 18 张表（清理时按 project_id 删除关联记录）

---

## 5. 测试要求

详见 [0012-test-plan.md](0012-test-plan.md)。核心覆盖：

| 测试类别 | 文件 | 测试数 | 说明 |
| --- | --- | --- | --- |
| 配置层 | `test_data_retention_config.py` | ~9 | 环境变量读取、非法值降级、边界值 |
| 清理逻辑 | `test_cleanup_expired_data.py` | ~9 | 过期判断、级联删除、文件系统清理 |
| 脚本接口 | `test_cleanup_script.py` | ~10 | dry-run/execute 模式、参数解析、help |
| 安全机制 | `test_cleanup_safety.py` | ~6 | 默认安全、RUNNING job 保护、失败处理 |
| 集成测试 | `test_cleanup_integration.py` | ~5 | 端到端清理、混合场景、完整性验证 |

---

## 6. 验收标准

### 6.1 功能验收

| 验收 ID | 场景 | 期望结果 |
| --- | --- | --- |
| AC-01 | `DATA_RETENTION_DAYS=0`，执行 `--execute` | 不清理任何项目 |
| AC-02 | `DATA_RETENTION_DAYS=30`，项目 updated_at 35天前，执行 `--execute` | 项目完全清理（18 张表 + 文件目录） |
| AC-03 | `DATA_RETENTION_DAYS=30`，项目 updated_at 20天前 | 不进入清理列表 |
| AC-04 | 默认无参数执行 | dry-run 模式，只输出报告不删除 |
| AC-05 | 过期项目有 RUNNING job | 跳过该项目 + warning |
| AC-06 | 过期项目 job 全部终态 | 正常清理 |
| AC-07 | `DATA_RETENTION_DAYS=abc` | 降级到 0，不清理 |
| AC-08 | 项目活跃更新后 updated_at 刷新 | 重置保留计时器，不过期 |

### 6.2 回归验收

| 验收 ID | 命令 | 期望结果 |
| --- | --- | --- |
| AC-09 | `server\.venv\Scripts\python.exe -m pytest server\tests -q` | 全量通过，0 warnings，无回归 |
| AC-10 | `server\.venv\Scripts\python.exe -m alembic upgrade head` | 无错误（无 schema 变更） |
| AC-11 | `npm.cmd run lint`（apps/web） | 通过（无前端变更） |
| AC-12 | `npm.cmd run build`（apps/web） | 通过（无前端变更） |

### 6.3 文档验收

| 验收 ID | 文件 | 期望 |
| --- | --- | --- |
| AC-13 | `server/.env.example` | 新增 `DATA_RETENTION_DAYS=0` |
| AC-14 | `server/app/core/config.py` | Settings 类新增 `data_retention_days` property |
| AC-15 | 根目录 `README.md` | 新增"数据保留与清理"章节 |
| AC-16 | `dev-docs/acceptance.md` | 记录 SPEC 0012 验收证据 |
| AC-17 | `dev-docs/README.md` | 更新 SPEC 0012 状态 |
| AC-18 | `dev-docs/v1.1.0-planning.md` | 更新 SPEC 0012 为已完成 |

---

## 7. 实现步骤

按 AGENTS.md 阶段闸推进：

| 步骤 | 内容 | 涉及文件 |
| --- | --- | --- |
| 1 | 配置层 | `config.py`、`.env.example` |
| 2 | RUNNING job 查询方法 | `jobs/service.py` |
| 3 | 清理脚本主体 | `scripts/__init__.py`、`scripts/cleanup_expired_data.py` |
| 4 | 级联删除逻辑 | `scripts/cleanup_expired_data.py` |
| 5 | 文件系统清理 | `scripts/cleanup_expired_data.py` |
| 6 | RUNNING job 保护接线 | `scripts/cleanup_expired_data.py` |
| 7 | 文档回写 | `README.md`、`dev-docs/*` |
| 8 | 测试 | `tests/test_*.py`（5 个文件） |
| 9 | 验收 + git 收口 | 全量测试 + lint + build + commit + push |

---

## 8. 决策记录

| 决策项 | 选择 | 理由 |
| --- | --- | --- |
| 过期判断字段 | `updated_at` | 活跃项目自动重置计时器（onupdate 机制）；与 list_projects 排序一致 |
| 浮点数处理 | 截断为整数 | 与现有 `int(raw)` 配置模式一致（如 execution_timeout_seconds） |
| RUNNING job 保护 | 实现 | 避免清理正在执行任务的项目导致数据不一致 |
| 清理脚本位置 | `server/scripts/` | 独立于 app 模块，脚本性质明确 |
| 文件锁定处理 | 跳过 + warning | 不阻塞清理流程，记录残留供人工处理 |
| 默认保留期 | 0（永久） | 不影响现有行为，用户需显式配置才启用清理 |
| 清理模式默认 | dry-run | 安全优先，必须显式 `--execute` 才删除 |

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 误删活跃项目数据 | 数据丢失 | 默认 dry-run + RUNNING job 保护 + updated_at 活跃判断 |
| 文件系统删除不完整 | 数据库已删但文件残留 | `ignore_errors=True` + warning 记录残留 |
| 外键约束冲突 | 删除失败 | 按依赖顺序删除（叶子→根） |
| SQLite 锁定 | 并发清理失败 | 清理脚本是单进程，无并发问题 |
| 大量数据清理耗时长 | 阻塞用户 | 手动执行，用户可控制时机 |

---

## 10. 依赖

**无新增依赖。**

- 使用标准库：`argparse`（参数解析）、`shutil`（文件删除）、`os`/`pathlib`（路径）
- 使用现有 SQLAlchemy Session 查询和删除
- 无 cron/scheduler/apscheduler 等定时任务依赖

---

## 11. 后续展望（不在本切片范围）

- V2.0：自动定时清理（apscheduler 或 cron）
- V2.0：项目级保留策略（不同项目不同保留期）
- V2.0：Web UI 触发清理
- V2.0：软删除/回收站机制
- V2.0：清理历史记录表（记录清理操作）

---

## 12. 确认要求

本 SPEC 编写完成，待项目负责人确认以下内容后进入实现：

1. ✅ 过期判断字段使用 `updated_at`
2. ✅ 浮点数截断为整数
3. ✅ 实现 RUNNING job 保护
4. ✅ 清理脚本位于 `server/scripts/`
5. ✅ 文件锁定跳过 + warning
6. ✅ 默认 `DATA_RETENTION_DAYS=0`（永久保留）
7. ✅ 默认 dry-run 模式
8. ✅ 无 schema 变更、无新增依赖、无前端变更

**项目负责人确认后，按实现步骤 1-9 推进。**
