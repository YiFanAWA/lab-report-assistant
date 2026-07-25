# V1.2.0 发布清单

> **版本号：** v1.2.0  
> **发布日期：** 2026-07-25  
> **发布状态：** 待项目负责人确认发布，打 tag v1.2.0  
> **当前 HEAD：** `e203ac2`（已同步 origin/master）  
> **上一版本：** v1.1.0（`efac98b`）  
> **远程分支：** `origin/master`（V1.2.0 文档回写后将再次同步）

---

## 一、发布前状态纯净度检查

### 1.1 Git 工作区状态

| 检查项 | 命令 | 结果 | 状态 |
| --- | --- | --- | --- |
| 工作区干净 | `git status --short --untracked-files=all` | 仅 V1.2.0 发布文档相关文件（草稿 + 文档回写），无业务代码改动 | ✅ 通过 |
| 与远程同步 | `git rev-parse HEAD` vs `git rev-parse origin/master` | 两者均为 `e203ac2`，已同步 | ✅ 通过 |
| 无冲突标记 | `git grep -nE "^(<<<<<<<\|=======\|>>>>>>>)"` | 退出码 1（无匹配） | ✅ 通过 |

### 1.2 自动化测试验收

| 检查项 | 命令 | 结果 | 状态 |
| --- | --- | --- | --- |
| 后端单元测试 | `server/.venv/Scripts/python.exe -m pytest -q` | **729 passed in 79.72s, 0 warnings** | ✅ 通过 |
| 前端单元测试 | `npm.cmd test -- --run` | **411 passed**（19 个测试文件） | ✅ 通过 |
| 前端类型检查 | `npm.cmd run lint` | `tsc --noEmit` 通过，无类型错误 | ✅ 通过 |
| 前端生产构建 | `npm.cmd run build` | Vite 构建通过，114 模块转换，`dist/` 394.96 kB，gzip 107.49 kB | ✅ 通过 |

### 1.3 数据库迁移状态

| 检查项 | 结果 | 状态 |
| --- | --- | --- |
| Alembic 迁移版本 | 已迁移到 `0007`（V1.2.0 无新增迁移，SPEC 0014 缓存表通过 `CREATE TABLE IF NOT EXISTS` 自动建表，不走 Alembic） | ✅ 通过 |
| 迁移文件 | `0001`-`0007` 共 7 个迁移 | ✅ 通过 |
| 全新临时 SQLite 验证 | `DATABASE_URL=sqlite:///./.tmp/v1.2.0-verify.db alembic upgrade head` 迁移 7 个迁移（0001-0007）全部可从零执行 | ✅ 通过 |

### 1.4 文档完整性

| 文档 | 状态 |
| --- | --- |
| [AGENTS.md](../AGENTS.md) | ✅ 项目宪法，无需修改 |
| [dev-docs/README.md](README.md) | ✅ 已更新为 V1.2.0 已发布状态 + V1.2.0 发布文档索引 |
| [dev-docs/acceptance.md](acceptance.md) | ✅ SPEC 0013/0014/0015 已改为"已确认收口"，证据记录已回写至 2026-07-25 |
| [dev-docs/implementation-plan.md](implementation-plan.md) | ✅ V1.2.0 SPEC 0013-0015 任务已完成 |
| [dev-docs/changelog-v1.2.0.md](changelog-v1.2.0.md) | ✅ V1.2.0 详细变更日志（3 SPEC 新增功能 + 3 Bug 修复 + 升级指南） |
| [dev-docs/v1.2.0-regression-test-plan.md](v1.2.0-regression-test-plan.md) | ✅ 回归测试执行记录第九章 3 道门禁全部 ✅ |
| [dev-docs/release-checklist-v1.2.0.md](release-checklist-v1.2.0.md) | ✅ 本文件（V1.2.0 发布清单） |
| [dev-docs/tech-debt-inventory.md](tech-debt-inventory.md) | ✅ TD-007 已关闭，TD-004/005/006 仍为可记录债务 |
| SPEC 0013/0014/0015 | ✅ 3 个 SPEC 均已完成并收口 |
| 决策记录 0001-0021 | ✅ 21 个决策记录完整 |

### 1.5 已知非阻断债务

| 编号 | 描述 | 状态 | 不阻断原因 |
| --- | --- | --- | --- |
| TD-004 | 科学计算包未声明在 pyproject.toml dependencies | ✅ 可记录债务 | CI 通过额外安装弥补；V1.3.0 计划修复 |
| TD-005 | AGENTS.md "当前已知非阻断债务"表述过时 | ✅ 可记录债务 | 文档准确性问题，不影响代码 |
| TD-006 | acceptance.md 各 SPEC "可视化点击验收"历史记录与 V1.0 整体验收状态不一致 | ✅ 可记录债务 | 历史快照，保留追溯 |
| TD-007 | openpyxl 未声明在 pyproject.toml dependencies | ✅ **V1.2.0 已关闭** | SPEC 0015 CI 修复 |
| TD-008 | worker_e2e_verify.py 硬编码日志标题为"V1.0" | ✅ V1.2.0 新登记 | 已手动修正日志标题，脚本本身缺陷作为可记录债务 |

**V1.2.0 发布前无未解决的阻断债务。**

---

## 二、V1.2.0 SPEC 摘要

| SPEC | 标题 | commit | 后端测试增量 | 累计后端测试 |
| --- | --- | --- | --- | --- |
| SPEC 0013 | Docker 化部署 | `c210911` | 0（基础设施，AC 通过 Docker 实际构建验证） | 704 |
| SPEC 0014 | LLM 调用缓存 | `31ec6cd` | +25 | 729 |
| SPEC 0015 | GitHub Actions CI 流水线 | `e203ac2` | 0（基础设施，AC 通过 CI 实际运行验证） | 729 |

详细变更内容见 [changelog-v1.2.0.md](changelog-v1.2.0.md)。

---

## 三、发布物清单

### 3.1 后端新增/扩展模块

| 模块 | 路径 | 新增能力 |
| --- | --- | --- |
| LLM 缓存基础设施 | `server/app/infrastructure/llm/llm_cache.py` | LLMCache 存储层（独立 SQLite、自动建表、TTL、降级） |
| DeepSeekClient 缓存接入 | `server/app/infrastructure/llm/deepseek_client.py` | cache 参数注入（默认 None 零回归） |
| LLM 网关缓存配置 | `server/app/modules/llm/gateway.py` | 根据 LLM_CACHE_ENABLED 创建 cache |
| 配置层 | `server/app/core/config.py` | 新增 3 个环境变量（ENABLED/TTL/DB_PATH） |

### 3.2 前端新增/扩展模块

**V1.2.0 无前端代码改动。** SPEC 0013/0014/0015 均为基础设施切片，不触碰 `apps/web/` 业务代码。

### 3.3 Docker 化基础设施

| 文件 | 路径 | 新增能力 |
| --- | --- | --- |
| 后端 Dockerfile | `server/Dockerfile` | 多阶段构建（builder + runtime），含科学计算栈 |
| 前端 Dockerfile | `apps/web/Dockerfile` | 多阶段构建（node build + nginx runtime） |
| Compose 编排 | `docker-compose.yml` | 三服务（backend + worker + frontend）+ 命名卷 |
| 启动入口 | `server/entrypoint.sh` | 自动迁移 + uvicorn 启动 |
| Nginx 配置 | `apps/web/nginx.conf` | 静态托管 + `/api` 反向代理 |
| Docker 忽略 | `server/.dockerignore`、`apps/web/.dockerignore` | 排除 .venv/node_modules/tests/dist |
| 环境变量模板 | `server/.env.example` | Docker 化路径（4 斜杠 DATABASE_URL） |

### 3.4 CI 流水线基础设施

| 文件 | 路径 | 新增能力 |
| --- | --- | --- |
| CI 工作流 | `.github/workflows/ci.yml` | push/PR to master 触发，backend + frontend 两 Job 并行 |

### 3.5 测试覆盖

| 测试套件 | V1.1.0 | V1.2.0 | 新增 |
| --- | --- | --- | --- |
| 后端 pytest | 704 | 729 | +25 |
| 前端 Vitest | 411 | 411 | 0 |
| **总计** | **1115** | **1140** | **+25** |

### 3.6 依赖变更

| 依赖 | 版本 | 用途 | 引入版本 |
| --- | --- | --- | --- |
| `openpyxl` | `>=3.1.0` | Excel 数据集解析 | V1.2.0（TD-007 修复） |
| `beautifulsoup4` | `>=4.12.0` | HTML 解析 | V1.2.0（SPEC 0013 修复） |
| `lxml` | `>=5.0.0` | BeautifulSoup 解析器 | V1.2.0（SPEC 0013 修复） |
| `pypdf` | `>=4.0.0` | PDF 文档解析 | V1.2.0（SPEC 0013 修复） |

---

## 四、版本标签操作

### 4.1 标签信息

- **标签名：** `v1.2.0`
- **指向提交：** 发布文档回写后的 HEAD（commit 待生成后填入）
- **标签类型：** 附注标签（annotated tag）
- **标签信息：** 中文，包含版本概述

### 4.2 打标签命令

```bash
git tag -a v1.2.0 -m "完成 V1.2.0 版本发布：3 个基础设施 SPEC 全部收口"
git push origin master --tags
```

### 4.3 发布后检查

- [ ] `git tag -l v1.2.0` 确认本地标签存在
- [ ] `git ls-remote --tags origin` 确认远程标签存在
- [ ] GitHub Releases 页面确认标签可见
- [ ] GitHub Actions 在 tag push 后不会触发（CI 仅对 master 分支 push 触发）

---

## 五、V1.2.0 产品边界确认

| 边界 | 状态 |
| --- | --- |
| 本地单用户 Web MVP | ✅ 符合（未扩张边界） |
| 不做注册登录 | ✅ 符合 |
| 不做 L3 完整复现 | ✅ 符合 |
| 医学内容只作教学数据分析 | ✅ 符合 |
| Word/PPT 来自同一份已确认大纲 | ✅ 符合 |
| 不绕过登录/验证码/付费墙 | ✅ 符合 |
| 唯一 owner 层架构 | ✅ 符合（API/UI/Worker/prompt 只做接线） |
| LLM 通过统一 Gateway 接入 | ✅ 符合（不写死模型名，不直接调用 SDK） |
| V1 Python 执行为应用托管受控环境 | ✅ 符合（Docker 镜像内置科学计算栈，无需用户手动安装） |

---

## 六、发布确认

**发布前状态：纯净**

- 工作树仅含 V1.2.0 发布文档相关改动，无业务代码改动
- 后端 729 测试 + 前端 411 测试 = 1140 个测试全部通过
- 前端 lint 和 build 均通过
- 0 warnings
- 数据库迁移到 0007 无错误（全新临时 SQLite 可从零执行）
- 无未解决的阻断债务
- 所有文档已回写（README.md、acceptance.md、changelog-v1.2.0.md、regression-test-plan.md、release-checklist-v1.2.0.md、tech-debt-inventory.md）
- CI Run #2（`64f2eb4`）和 Run #3（`e203ac2`）均 completed + conclusion=success
- worker_e2e_verify 端到端验证 E2E_RESULT=PASS
- 关键回归点 63 个测试通过（STALE/沙箱/路径穿越/URL 安全等）

**待项目负责人确认 SPEC 0013/0014/0015 收口并发布 V1.2.0。**

---

## 七、V1.2.0 收口后下一步

按项目负责人 2026-07-25 确认，下一阶段方向为：

**修复可记录债务 TD-004/005/006**

| TD # | 描述 | 计划处理入口 |
| --- | --- | --- |
| TD-004 | 科学计算包未声明在 pyproject.toml dependencies | 在 `pyproject.toml` 新增 `[project.optional-dependencies] analysis` 段，声明 pandas/numpy/scipy/scikit-learn/matplotlib/psutil；CI 改为 `pip install -e ".[dev,analysis]"`；Dockerfile 简化为 `pip install -e ".[dev,analysis]"` |
| TD-005 | AGENTS.md "当前已知非阻断债务"表述过时 | 修订 AGENTS.md "测试与验收"章节，引用 e2e-acceptance-report-v1.0.md 作为浏览器验收证据 |
| TD-006 | acceptance.md 各 SPEC "可视化点击验收"历史记录与 V1.0 整体验收状态不一致 | 在 acceptance.md 顶部"当前限制"说明中明确：V1.0 整体验收已补做浏览器验收 |

按 AGENTS.md 阶段闸：先编写并确认下一切片 SPEC（暂定 SPEC 0016：TD-004/005/006 修复），项目负责人批准后再进入实现。
