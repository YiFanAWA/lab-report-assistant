# SPEC 0012 测试计划｜数据保留周期配置

> 状态：测试计划已基于 SPEC 0012 决策最终化
> 所属 SPEC：[SPEC 0012 数据保留周期配置](0012-data-retention.md)

## 1. 测试范围

覆盖 SPEC 0012 的三个核心能力及其边界场景：

| 能力 | 说明 | 默认值 |
| --- | --- | --- |
| `DATA_RETENTION_DAYS` 环境变量 | int，0 表示永久保留，>0 表示保留 N 天（浮点数截断） | 0（永久） |
| 手动清理脚本 | `server/scripts/cleanup_expired_data.py`，手动执行 | `--dry-run`（只报告） |
| 级联清理 | 以项目为单位，基于 `Project.updated_at` 判断过期，删除 18 张表关联记录 + 文件系统目录 | — |
| RUNNING job 保护 | 清理前检查项目是否有 PENDING/RUNNING 状态 Job，有则跳过 | 已确认实现 |

### 决策依据（SPEC 0012 已确认）

- 过期判断字段：`Project.updated_at`（有 onupdate 自动刷新，活跃项目重置计时器）
- 浮点数处理：截断为整数（与现有 `int(raw)` 模式一致）
- RUNNING job 保护：实现
- 清理脚本位置：`server/scripts/`
- 文件锁定处理：跳过 + warning

### 不在本测试计划范围（SPEC 0012 明确不做）

- ❌ 自动定时清理（无 cron/scheduler）
- ❌ 项目级保留策略（全局统一）
- ❌ 软删除/回收站（直接物理删除）
- ❌ Web UI 触发清理（只命令行）
- ❌ 清理历史记录表

## 2. 配置层测试（后端单元测试）

文件：`server/tests/test_data_retention_config.py`

### 2.1 环境变量读取

| 测试 ID | 场景 | 输入 | 期望结果 |
| --- | --- | --- | --- |
| C-01 | 未设置环境变量 | 不设置 `DATA_RETENTION_DAYS` | `settings.data_retention_days == 0`（默认永久） |
| C-02 | 设置为 0 | `DATA_RETENTION_DAYS=0` | `settings.data_retention_days == 0`（永久保留） |
| C-03 | 设置为正整数 | `DATA_RETENTION_DAYS=30` | `settings.data_retention_days == 30` |
| C-04 | 设置为大值 | `DATA_RETENTION_DAYS=365` | `settings.data_retention_days == 365` |
| C-05 | 设置为 1（最小有效正整数） | `DATA_RETENTION_DAYS=1` | `settings.data_retention_days == 1` |

### 2.2 非法值处理

| 测试 ID | 场景 | 输入 | 期望结果 |
| --- | --- | --- | --- |
| C-06 | 设置为负值 | `DATA_RETENTION_DAYS=-1` | 返回 0（降级到默认永久） |
| C-07 | 设置为非数字 | `DATA_RETENTION_DAYS=abc` | 返回 0（降级到默认永久） |
| C-08 | 设置为浮点数 | `DATA_RETENTION_DAYS=30.5` | 返回 30（截断为整数，与现有 int(raw) 模式一致） |
| C-09 | 设置为空字符串 | `DATA_RETENTION_DAYS=` | 返回 0（默认永久） |

## 3. 清理逻辑测试（后端单元测试）

文件：`server/tests/test_cleanup_expired_data.py`

### 3.1 过期判断（基于 `Project.updated_at`）

| 测试 ID | 场景 | 数据准备 | 期望结果 |
| --- | --- | --- | --- |
| L-01 | 0 天保留期，不清理任何项目 | `DATA_RETENTION_DAYS=0`，3 个项目（updated_at 1天/10天/30天前） | 清理列表为空，不删除任何记录 |
| L-02 | 30 天保留期，清理超期项目 | `DATA_RETENTION_DAYS=30`，项目 A（updated_at 35天前）、项目 B（updated_at 20天前） | 仅项目 A 进入清理列表 |
| L-03 | 刚好 30 天（边界） | `DATA_RETENTION_DAYS=30`，项目 updated_at 刚好 30 天前 | 不清理（保留满 30 天，第 31 天才过期） |
| L-04 | 1 天保留期 | `DATA_RETENTION_DAYS=1`，项目 A（updated_at 2天前）、项目 B（今天） | 仅项目 A 进入清理列表 |
| L-05 | 活跃项目重置计时器 | `DATA_RETENTION_DAYS=30`，项目 A created_at 35天前但 updated_at 10天前（中途有更新） | 项目 A 不进入清理列表（updated_at 未过期） |

### 3.2 级联删除完整性

| 测试 ID | 场景 | 数据准备 | 期望结果 |
| --- | --- | --- | --- |
| L-05 | 完整项目级联删除 | 项目 A 含全部 18 张表关联记录 + 文件系统目录 | 删除后：18 张表中 project_id 关联记录全部删除，文件系统 `{project_id}/` 目录删除 |
| L-06 | 部分数据项目删除 | 项目 A 只有 projects + requirement_sources 记录（无后续流程数据） | 删除成功，不因缺失关联表记录报错 |
| L-07 | 多项目同时清理 | 3 个过期项目，每个含完整数据 | 3 个项目全部清理，互不影响 |

### 3.3 数据库删除顺序（外键安全）

| 测试 ID | 场景 | 数据准备 | 期望结果 |
| --- | --- | --- | --- |
| L-08 | 按依赖顺序删除 | 项目含全部表数据 | 删除顺序：叶子表（evidence_cards 等）→ 根表（projects），无外键冲突错误 |
| L-09 | 存在孤儿记录 | 手动删除父记录后留下孤儿子记录 | 清理时能删除孤儿记录，不因外键缺失报错 |

### 3.4 文件系统清理

| 测试 ID | 场景 | 数据准备 | 期望结果 |
| --- | --- | --- | --- |
| L-10 | 删除项目工作区目录 | 项目 A 的 `{project_id}/` 目录含 sources/、executions/、word_template/ 等子目录和文件 | 整个 `{project_id}/` 目录被删除 |
| L-11 | 文件系统目录不存在 | 数据库有项目记录但文件系统目录已被手动删除 | 清理数据库记录成功，不因目录缺失报错（warning 日志） |
| L-12 | 部分文件被占用 | 文件系统目录中部分文件被系统占用（Windows 锁定） | 删除能删除的文件，记录无法删除的文件 warning，继续清理数据库记录 |

## 4. 清理脚本测试（命令行接口）

文件：`server/tests/test_cleanup_script.py`

### 4.1 dry-run 模式（默认）

| 测试 ID | 场景 | 命令 | 期望结果 |
| --- | --- | --- | --- |
| S-01 | 默认 dry-run 不删除 | `python -m scripts.cleanup_expired_data`（无参数） | 输出过期项目清单和预估清理数量，不实际删除任何记录和文件 |
| S-02 | 显式 dry-run | `python -m scripts.cleanup_expired_data --dry-run` | 同 S-01 |
| S-03 | dry-run 输出报告格式 | 3 个过期项目 | 报告包含：项目 ID、项目名称、创建时间、过期天数、预估清理数据量 |
| S-04 | dry-run 无过期项目 | `DATA_RETENTION_DAYS=0` 或无过期项目 | 输出"无过期项目"，退出码 0 |

### 4.2 execute 模式

| 测试 ID | 场景 | 命令 | 期望结果 |
| --- | --- | --- | --- |
| S-05 | execute 实际删除 | `python -m scripts.cleanup_expired_data --execute` | 实际删除过期项目的数据库记录和文件系统目录，输出清理结果 |
| S-06 | execute 后再次 dry-run | 先 execute，再 dry-run | 第二次 dry-run 显示"无过期项目"（已清理） |
| S-07 | execute 无过期项目 | `DATA_RETENTION_DAYS=0` + `--execute` | 输出"无过期项目"，退出码 0，不报错 |

### 4.3 参数解析

| 测试 ID | 场景 | 命令 | 期望结果 |
| --- | --- | --- | --- |
| S-08 | 未知参数 | `python -m scripts.cleanup_expired_data --unknown` | 输出参数错误，退出码非 0 |
| S-09 | 同时指定 dry-run 和 execute | `--dry-run --execute` | 以 dry-run 为准（安全优先），输出提示"dry-run 和 execute 同时指定，采用 dry-run" |
| S-10 | help 输出 | `python -m scripts.cleanup_expired_data --help` | 输出用法说明，包含参数列表和示例 |

## 5. 安全机制测试

文件：`server/tests/test_cleanup_safety.py`

### 5.1 默认安全

| 测试 ID | 场景 | 数据准备 | 期望结果 |
| --- | --- | --- | --- |
| F-01 | 默认 dry-run 保护 | 3 个过期项目，不传 `--execute` | 不删除任何数据，只输出报告 |
| F-02 | 0 天保留期保护 | `DATA_RETENTION_DAYS=0`，10 个项目 | 清理列表为空，即使 `--execute` 也不删除任何项目 |

### 5.2 RUNNING job 保护（已确认实现）

| 测试 ID | 场景 | 数据准备 | 期望结果 |
| --- | --- | --- | --- |
| F-03 | 项目有 RUNNING 状态 job | 过期项目 A 含 1 个 `status=RUNNING` 的 background_job | 项目 A 被跳过，输出 warning"项目 A 有活跃任务，跳过清理" |
| F-04 | 项目有 PENDING 状态 job | 过期项目 A 含 1 个 `status=PENDING` 的 background_job | 项目 A 被跳过（PENDING 也属于活跃任务） |
| F-05 | 项目的 job 全部终态 | 过期项目 A 的 job 全部 SUCCEEDED/FAILED/CANCELLED | 项目 A 正常清理 |
| F-06 | has_active_jobs 查询方法 | `jobs/service.py` 新增方法 | `has_active_jobs(db, project_id)` 正确返回 True/False |

### 5.3 清理失败处理

| 测试 ID | 场景 | 数据准备 | 期望结果 |
| --- | --- | --- | --- |
| F-07 | 单个项目清理失败 | 3 个过期项目，项目 B 的文件系统目录权限不足 | 项目 A、C 清理成功，项目 B 记录错误，继续清理其他项目，退出码非 0 |
| F-08 | 数据库删除失败 | 模拟数据库异常 | 记录错误，输出失败项目清单，退出码非 0 |

## 6. 集成测试（真实 SQLite + 文件系统）

文件：`server/tests/test_cleanup_integration.py`

| 测试 ID | 场景 | 数据准备 | 期望结果 |
| --- | --- | --- | --- |
| I-01 | 端到端清理流程 | 创建完整项目（含来源/数据集/执行/大纲/交付物），mock updated_at 为 35 天前，`DATA_RETENTION_DAYS=30`，`--execute` | 项目完全清理：18 张表关联记录删除、文件系统目录删除、数据库无残留 |
| I-02 | 端到端 dry-run | 同 I-01 但 `--dry-run` | 输出清理报告，项目和数据全部保留 |
| I-03 | 混合场景 | 5 个项目：2 个过期（updated_at 35天前）、2 个未过期（updated_at 10天前）、1 个永久（0天保留期） | 仅 2 个过期项目进入清理列表 |
| I-04 | 清理后数据库完整性 | I-01 清理后 | 其他项目数据无影响，数据库可正常查询，无外键断裂 |
| I-05 | 清理后文件系统完整性 | I-01 清理后 | `PROJECT_DATA_ROOT` 下仅保留未过期项目的目录 |
| I-06 | 活跃项目重置计时器 | 项目 created_at 35天前但 updated_at 5天前（中途有状态更新），`DATA_RETENTION_DAYS=30` | 项目不进入清理列表（updated_at 未过期） |
| I-07 | RUNNING job 保护端到端 | 过期项目含 RUNNING job，`--execute` | 项目跳过清理，数据完整保留 |

## 7. 文档验收

| 验收 ID | 场景 | 检查文件 | 期望结果 |
| --- | --- | --- | --- |
| D-01 | `.env.example` 更新 | `server/.env.example` | 新增 `DATA_RETENTION_DAYS=0` 并注释说明"0=永久保留，>0=保留N天" |
| D-02 | `config.py` 更新 | `server/app/core/config.py` | Settings 类新增 `data_retention_days` property，含非法值降级逻辑 |
| D-03 | 根目录 README.md 更新 | `README.md` | 新增"数据保留与清理"章节，说明清理策略和命令 |
| D-04 | 部署文档更新 | `dev-docs/` 相关文档 | 记录 DATA_RETENTION_DAYS 环境变量和清理脚本使用方法 |

## 8. 验收命令

| 验收 ID | 命令 | 期望结果 |
| --- | --- | --- |
| V-01 | `server\.venv\Scripts\python.exe -m pytest server\tests\test_data_retention_config.py -v` | 全部通过 |
| V-02 | `server\.venv\Scripts\python.exe -m pytest server\tests\test_cleanup_expired_data.py -v` | 全部通过 |
| V-03 | `server\.venv\Scripts\python.exe -m pytest server\tests\test_cleanup_script.py -v` | 全部通过 |
| V-04 | `server\.venv\Scripts\python.exe -m pytest server\tests\test_cleanup_safety.py -v` | 全部通过 |
| V-05 | `server\.venv\Scripts\python.exe -m pytest server\tests\test_cleanup_integration.py -v` | 全部通过 |
| V-06 | `server\.venv\Scripts\python.exe -m pytest server\tests -q` | 全量通过，无回归，0 warnings |
| V-07 | `server\.venv\Scripts\python.exe -m alembic upgrade head` | 无错误（SPEC 0012 无 schema 变更） |
| V-08 | `npm.cmd run lint`（apps/web） | 通过（SPEC 0012 无前端变更） |
| V-09 | `npm.cmd run build`（apps/web） | 通过（SPEC 0012 无前端变更） |
| V-10 | 手动执行 `python -m scripts.cleanup_expired_data --dry-run` | 输出清理报告，不删除数据 |

## 9. 测试数据准备

### 9.1 时间 mock 策略

由于保留周期基于 `Project.updated_at` 判断，测试需要 mock 项目 updated_at：

```python
from datetime import datetime, timedelta, timezone

def _create_project_with_updated_at(db, project_id: str, updated_days_ago: int,
                                      created_days_ago: int | None = None):
    """创建一个项目并设置 updated_at（用于过期判断测试）。

    created_days_ago 可选，默认等于 updated_days_ago。
    """
    now = datetime.now(timezone.utc)
    created_at = now - timedelta(days=created_days_ago or updated_days_ago)
    updated_at = now - timedelta(days=updated_days_ago)
    project = Project(
        id=project_id,
        name=f"测试项目_{project_id}",
        topic=f"测试课题_{project_id}",
        status=ProjectStatus.COMPLETED.value,
        created_at=created_at,
        updated_at=updated_at,
    )
    db.add(project)
    db.commit()
```

### 9.2 完整项目数据构造

为集成测试构造含全部 18 张表数据的项目：

```python
def _create_full_project(db, project_id: str, updated_days_ago: int):
    """创建含完整链路数据的项目（要求→来源→证据→数据集→分析→执行→大纲→交付物）。"""
    _create_project_with_updated_at(db, project_id, updated_days_ago)
    _seed_requirement(db, project_id)
    _seed_source_and_evidence(db, project_id)
    _seed_dataset_and_analysis(db, project_id)
    _seed_execution(db, project_id)
    _seed_outline_and_deliverable(db, project_id)
    # 对应文件系统目录也需创建
    _create_project_workspace_files(project_id)
```

### 9.3 RUNNING job 构造

为 RUNNING job 保护测试构造活跃任务：

```python
def _create_active_job(db, project_id: str, status: str = "RUNNING"):
    """创建一个活跃状态的 Job（PENDING 或 RUNNING）。"""
    job = BackgroundJob(
        id=_uid(),
        project_id=project_id,
        job_type="FETCH_URL",
        status=status,
        input_json="{}",
        retry_count=0,
        max_retries=2,
    )
    db.add(job)
    db.commit()
```

## 10. 待确认项状态

所有待确认项已在 SPEC 0012 中确认决策：

| 待确认项 | 决策 | 依据 |
| --- | --- | --- |
| 过期判断字段 | `updated_at` | 活跃项目自动重置计时器（onupdate 机制）；与 list_projects 排序一致 |
| 浮点数处理 | 截断为整数 | 与现有 int(raw) 配置模式一致 |
| RUNNING job 保护 | 实现 | 避免清理正在执行任务的项目导致数据不一致 |
| 清理脚本位置 | `server/scripts/` | 独立于 app 模块，脚本性质明确 |
| 文件锁定处理 | 跳过 + warning | 不阻塞清理流程，记录残留供人工处理 |

> 测试计划已基于 SPEC 0012 决策最终化，可直接用于实现后的验证。
