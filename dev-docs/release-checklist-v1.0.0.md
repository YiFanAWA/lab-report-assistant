# V1.0.0 发布清单

> **版本号：** v1.0.0  
> **发布日期：** 2026-07-23  
> **发布状态：** 待项目负责人确认后打 tag  
> **当前 HEAD：** `a7d78a3`  
> **远程分支：** `origin/master`（已同步）

---

## 一、发布前状态纯净度检查

### 1.1 Git 工作区状态

| 检查项 | 命令 | 结果 | 状态 |
| --- | --- | --- | --- |
| 工作区干净 | `git status --short` | 无输出（无修改、无未跟踪文件） | ✅ 通过 |
| 与远程同步 | `git status -uno` | `Your branch is up to date with 'origin/master'` | ✅ 通过 |
| 无未推送提交 | `git log origin/master..HEAD` | 无输出 | ✅ 通过 |
| 无冲突标记 | `git grep -nE "^(<<<<<<<\|=======\|>>>>>>>)"` | 退出码 1（无匹配） | ✅ 通过 |

### 1.2 自动化测试验收

| 检查项 | 命令 | 结果 | 状态 |
| --- | --- | --- | --- |
| 后端单元测试 | `python -m pytest` | **569 passed, 0 warnings** in 56.54s | ✅ 通过 |
| 前端单元测试 | `npm run test` | **37 passed**（api 20 + 组件 17）in 3.66s | ✅ 通过 |
| 前端类型检查 | `npm run lint` | tsc --noEmit 通过 | ✅ 通过 |
| 前端生产构建 | `npm run build` | 113 模块，389.56 kB，gzip 106.12 kB | ✅ 通过 |

### 1.3 数据库迁移状态

| 检查项 | 结果 | 状态 |
| --- | --- | --- |
| Alembic 迁移版本 | 已迁移到 `0006`（outlines/deliverables/deliverable_versions 三表） | ✅ 通过 |
| 迁移文件 | `0001`-`0006` 共 6 个迁移，均已在远程仓库 | ✅ 通过 |

### 1.4 文档完整性

| 文档 | 状态 |
| --- | --- |
| [AGENTS.md](../AGENTS.md) | ✅ 项目宪法，无需修改 |
| [dev-docs/README.md](README.md) | ✅ 当前阶段已更新为 V1.0 验收完成 |
| [dev-docs/project-charter.md](project-charter.md) | ✅ 产品立项文档 |
| [dev-docs/architecture.md](architecture.md) | ✅ 架构主线和 owner 边界 |
| [dev-docs/tech-stack.md](tech-stack.md) | ✅ 技术栈和框架边界 |
| [dev-docs/dependency-review.md](dependency-review.md) | ✅ 前后端依赖已复核（含 Vitest + RTL） |
| [dev-docs/acceptance.md](acceptance.md) | ✅ 验收记录已回写至 2026-07-23 |
| [dev-docs/implementation-plan.md](implementation-plan.md) | ✅ 任务 0-9 已完成 |
| [dev-docs/changelog.md](changelog.md) | ✅ 各切片变更已记录 |
| [dev-docs/changelog-v1.0.0.md](changelog-v1.0.0.md) | ✅ 本文件（V1.0 详细变更日志） |
| SPEC 0001-0006 | ✅ 6 个 SPEC 均已完成并收口 |
| 决策记录 0001-0018 | ✅ 18 个决策记录完整 |

### 1.5 已知非阻断债务

| 编号 | 描述 | 状态 | 不阻断原因 |
| --- | --- | --- | --- |
| TD-001 | fastapi.testclient 使用 httpx 弃用提示 | ✅ 已清理（安装 httpx2） | warnings 归零 |
| TD-002 | pandas to_datetime 无法推断格式 UserWarning | ✅ 已清理（format="mixed"） | warnings 归零 |
| TD-003 | 未完成浏览器点击截图验收 | ✅ 已清理（browser_use agent 验证） | 截图已保存 |

**V1.0 发布前无未解决的阻断债务。**

---

## 二、发布物清单

### 2.1 后端（Python FastAPI）

| 模块 | 路径 | 功能 |
| --- | --- | --- |
| 项目工作区核心 | `server/app/modules/projects/` | 项目 CRUD、状态机、工作区管理 |
| 实验要求核心 | `server/app/modules/requirements/` | 要求来源、结构化任务单、L0-L3 分级 |
| 来源与证据核心 | `server/app/modules/sources/` + `evidence/` | 公开 URL 采集、证据卡片 |
| 数据集核心 | `server/app/modules/datasets/` | 数据集上传、解析、字段概览 |
| 分析核心 | `server/app/modules/analysis/` | 清洗方案、分析方案、图表方案候选 |
| 执行核心 | `server/app/modules/execution/` | CodeTask、ExecutionRun、ExecutionArtifact |
| 大纲核心 | `server/app/modules/outlines/` | 统一大纲、Word/PPT 交付物 |
| 后台任务核心 | `server/app/modules/jobs/` | 任务记录、状态、重试、领取 |
| LLM 网关 | `server/app/modules/llm/` | 统一 LLM 接入（V1 本地规则） |
| API 路由 | `server/app/api/routers/` | 12 个路由模块，~60+ 端点 |
| Worker 进程 | `server/worker/` | 独立后台任务执行进程 |
| 数据库迁移 | `server/alembic/versions/` | 6 个迁移（0001-0006） |

### 2.2 前端（React + TypeScript + Vite）

| 模块 | 路径 | 功能 |
| --- | --- | --- |
| 项目列表 | `features/projects/` | 项目列表、详情、状态展示 |
| 实验要求 | `features/requirements/` | 要求输入、任务单、L0-L3 展示 |
| 公开资料 | `features/sources/` | URL 登记、来源列表 |
| 证据卡片 | `features/evidence/` | 证据卡片候选、确认 |
| 数据集 | `features/datasets/` | 数据集上传、字段概览 |
| 分析方案 | `features/analysis/` | 分析方案候选、确认 |
| 执行核心 | `features/execution/` | 代码任务、执行记录、产物下载 |
| 大纲 | `features/outlines/` | 大纲生成、编辑、确认 |
| 交付物 | `features/outlines/` | Word/PPT 生成、版本、下载 |
| 后台任务 | `features/jobs/` | 任务状态轮询 |
| 路由 | `routes/` | 8 个工作区视图 |
| 测试 | `__tests__/` | 37 个单元测试 |

### 2.3 测试覆盖

| 测试套件 | 数量 | 命令 |
| --- | --- | --- |
| 后端 pytest | 569 | `python -m pytest` |
| 前端 Vitest | 37 | `npm run test` |
| **总计** | **606** | — |

### 2.4 提交历史（11 个提交）

| # | Commit | 日期 | 说明 |
| --- | --- | --- | --- |
| 1 | `14450a6` | 2026-06-17 | 完成 SPEC 0002 实验要求输入与结构化任务单 |
| 2 | `ba683db` | 2026-07-06 | 完成 SPEC 0003 公开资料与证据工作流 |
| 3 | `fba27b5` | 2026-07-10 | 完成 SPEC 0004 数据集工作区 |
| 4 | `86503b6` | 2026-07-16 | 完成 SPEC 0005 受控 Python 执行文档编写 |
| 5 | `f30d500` | 2026-07-17 | 完成 SPEC 0005 受控 Python 执行 |
| 6 | `8e098ab` | 2026-07-21 | 完成 SPEC 0006 大纲与交付物 |
| 7 | `869fd9c` | 2026-07-21 | 更新 SPEC 0006 验收记录版本控制收口证据 |
| 8 | `bef1695` | 2026-07-22 | 补上 V1.0 端到端验收并生成技术债务清理计划 |
| 9 | `989b31f` | 2026-07-22 | 完成 V1.0 验收阶段：技术债务清理 + Worker 验证 + 前端 UI 补充 |
| 10 | `b70547f` | 2026-07-23 | 完成 SPEC 0005 前端接线：代码任务与执行记录工作区 |
| 11 | `174a92c` | 2026-07-23 | 完成 SPEC 0005 前端测试：Vitest + RTL 单元测试 |
| 12 | `a7d78a3` | 2026-07-23 | 补充 SPEC 0005 前端测试框架引入的文档回写 |

---

## 三、版本标签操作

### 3.1 标签信息

- **标签名：** `v1.0.0`
- **指向提交：** `a7d78a3`（当前 HEAD）
- **标签类型：** 附注标签（annotated tag）
- **标签信息：** 中文，包含版本概述

### 3.2 打标签命令

```bash
git tag -a v1.0.0 -m "V1.0.0 发布：实验报告助手本地单用户 Web MVP"
git push origin v1.0.0
```

### 3.3 发布后检查

- [ ] `git tag -l v1.0.0` 确认本地标签存在
- [ ] `git ls-remote --tags origin` 确认远程标签存在
- [ ] GitHub Releases 页面确认标签可见

---

## 四、V1.0 产品边界确认

| 边界 | 状态 |
| --- | --- |
| 本地单用户 Web MVP | ✅ 符合 |
| 不做注册登录 | ✅ 符合 |
| 首个演示课题：胃病数据分析 | ✅ 符合 |
| 聚焦数据分析与可视化类实验 | ✅ 符合 |
| 公开资料只面向公开 URL | ✅ 符合 |
| 不绕过登录/验证码/付费墙 | ✅ 符合 |
| 不自动登录知网等受限平台 | ✅ 符合 |
| V1 不支持 L3 完整复现 | ✅ 符合 |
| 医学内容只作教学数据分析 | ✅ 符合 |
| Word/PPT 来自同一份已确认大纲 | ✅ 符合 |

---

## 五、发布确认

**发布前状态：纯净**

- 工作区干净，无未提交修改
- 与远程仓库完全同步
- 无 Git 冲突标记
- 606 个测试全部通过（569 后端 + 37 前端）
- 0 warnings
- 无未解决的非阻断债务
- 所有文档已回写

**等待项目负责人确认后执行标签创建和推送。**
