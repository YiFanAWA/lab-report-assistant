# V1.1.0 发布清单

> **版本号：** v1.1.0  
> **发布日期：** 2026-07-23  
> **发布状态：** 项目负责人已确认发布，打 tag v1.1.0  
> **当前 HEAD：** `efac98b`  
> **上一版本：** v1.0.0（`a7d78a3`）  
> **远程分支：** `origin/master`（待 push 后同步）

---

## 一、发布前状态纯净度检查

### 1.1 Git 工作区状态

| 检查项 | 命令 | 结果 | 状态 |
| --- | --- | --- | --- |
| 工作区干净 | `git status --short --untracked-files=all` | 仅 V1.1.0 发布文档相关文件（草稿 + 文档回写），无业务代码改动 | ✅ 通过 |
| 与远程同步 | `git status -uno` | 发布前 commit `efac98b` 已同步 origin/master | ✅ 通过 |
| 无冲突标记 | `git grep -nE "^(<<<<<<<\|=======\|>>>>>>>)"` | 退出码 1（无匹配） | ✅ 通过 |

### 1.2 自动化测试验收

| 检查项 | 命令 | 结果 | 状态 |
| --- | --- | --- | --- |
| 后端单元测试 | `server/.venv/Scripts/python.exe -m pytest -q` | **704 passed in 59.46s, 0 warnings** | ✅ 通过 |
| 前端单元测试 | `npm.cmd test -- --run` | **411 passed**（19 个测试文件） | ✅ 通过 |
| 前端类型检查 | `npm.cmd run lint` | `tsc --noEmit` 通过，无类型错误 | ✅ 通过 |
| 前端生产构建 | `npm.cmd run build` | Vite 构建通过，114 模块转换，`dist/` 394.96 kB，gzip 107.49 kB | ✅ 通过 |

### 1.3 数据库迁移状态

| 检查项 | 结果 | 状态 |
| --- | --- | --- |
| Alembic 迁移版本 | 已迁移到 `0007`（V1.1.0 SPEC 0010 新增 `word_templates` 表） | ✅ 通过 |
| 迁移文件 | `0001`-`0007` 共 7 个迁移 | ✅ 通过 |
| SPEC 0011/0012 schema 变更 | 无（SPEC 0011 配置不持久化，SPEC 0012 仅新增配置和脚本） | ✅ 通过 |

### 1.4 文档完整性

| 文档 | 状态 |
| --- | --- |
| [AGENTS.md](../AGENTS.md) | ✅ 项目宪法，无需修改 |
| [dev-docs/README.md](README.md) | ✅ 已更新为 V1.1.0 已发布状态 + V1.1 发布文档索引 |
| [dev-docs/acceptance.md](acceptance.md) | ✅ SPEC 0010/0011/0012 已改为"已确认收口"，证据记录已回写至 2026-07-23 |
| [dev-docs/implementation-plan.md](implementation-plan.md) | ✅ V1.1.0 SPEC 0007-0012 任务已完成 |
| [dev-docs/v1.1.0-planning.md](v1.1.0-planning.md) | ✅ 6 个 SPEC 均标记已完成 |
| [dev-docs/changelog-v1.1.0.md](changelog-v1.1.0.md) | ✅ V1.1.0 详细变更日志（6 SPEC 新增功能 + 5 Bug 修复 + 升级指南） |
| [dev-docs/v1.1.0-regression-test-plan.md](v1.1.0-regression-test-plan.md) | ✅ 回归测试执行记录第九章 6 项全部 ✅ |
| [dev-docs/release-checklist-v1.1.0.md](release-checklist-v1.1.0.md) | ✅ 本文件（V1.1.0 发布清单） |
| SPEC 0007/0008/0009/0010/0011/0012 | ✅ 6 个 SPEC 均已完成并收口 |
| 决策记录 0001-0019 | ✅ 19 个决策记录完整 |

### 1.5 已知非阻断债务

| 编号 | 描述 | 状态 | 不阻断原因 |
| --- | --- | --- | --- |
| L-1 | 当前会话未暴露 in-app Browser 工具 | ✅ 已记录 | 以 Vitest 组件测试（411）+ API 测试套件作为替代证据 |
| L-2 | 真实 DeepSeek 调用需要有效 API Key | ✅ 已记录 | 无 Key 时走 LocalRule 降级，36 个 mock 测试覆盖 |
| L-3 | SPEC 0012 清理脚本 `--execute` 会删除真实数据 | ✅ 已记录 | dry-run 验证为主，execute 用测试内存数据库验证 |

**V1.1.0 发布前无未解决的阻断债务。**

---

## 二、V1.1.0 SPEC 摘要

| SPEC | 标题 | commit | 后端测试增量 | 累计后端测试 |
| --- | --- | --- | --- | --- |
| SPEC 0007 | 真实 DeepSeek LLM 接入 | `36e39f9` | +36 | 605 |
| SPEC 0008 | 部署文档与运维指南 | `4da4a1b` | —（文档） | 605 |
| SPEC 0009 | 前端测试覆盖补全 | `c8bbdf9` ~ `e70bb51` | —（前端 +374） | 605 |
| SPEC 0010 | Word 模板支持 | `fa35b79` | +18 | 623 |
| SPEC 0011 | PPT 配置选项 | `8b34b69` | +23 | 646 |
| SPEC 0012 | 数据保留周期配置 | `efac98b` | +58 | 704 |

详细变更内容见 [changelog-v1.1.0.md](changelog-v1.1.0.md)。

---

## 三、发布物清单

### 3.1 后端新增/扩展模块

| 模块 | 路径 | 新增能力 |
| --- | --- | --- |
| LLM 网关基础设施 | `server/app/infrastructure/llm/` | DeepSeek 客户端（httpx2，超时/重试/温度） |
| LLM Provider | `server/app/modules/llm/` | 5 个 Provider 全部 LLM 优先 + LocalRule 降级 |
| Word 模板 | `server/app/modules/outlines/`（含 `WordTemplate` ORM + 迁移 0007） | 项目级模板上传、Jinja2 占位符、章节循环、降级链 |
| Word 渲染器 | `server/app/infrastructure/renderers/word_renderer.py` | `render_with_template` 方法 |
| PPT 配置 | `server/app/modules/outlines/` + `ppt_renderer.py` | 页数控制、6 预设主题色、图表开关、配置不持久化 |
| 数据保留 | `server/app/core/config.py` + `server/app/modules/jobs/service.py` | `DATA_RETENTION_DAYS` 配置 + `has_active_jobs` 保护 |
| 清理脚本 | `server/scripts/cleanup_expired_data.py` | 双模式（dry-run/execute）+ 18 表级联删除 + 文件系统清理 |

### 3.2 前端新增/扩展模块

| 模块 | 路径 | 新增能力 |
| --- | --- | --- |
| Word 模板 UI | `apps/web/src/features/outlines/` + `OutlineWorkspaceView.tsx` | 模板上传/下载/删除 UI + 占位符说明 |
| PPT 配置 UI | `apps/web/src/features/outlines/` + `OutlineWorkspaceView.tsx` | 页数输入/色板选择/图表开关表单 |
| 前端测试 | `apps/web/src/{features,routes}/__tests__/` | 8 API 模块 + 11 Workspace 组件，共 411 个测试 |

### 3.3 测试覆盖

| 测试套件 | V1.0.0 | V1.1.0 | 新增 |
| --- | --- | --- | --- |
| 后端 pytest | 569 | 704 | +135 |
| 前端 Vitest | 37 | 411 | +374 |
| **总计** | **606** | **1115** | **+509** |

### 3.4 依赖变更

**V1.1.0 无新增运行时依赖。** 全部复用 V1.0 已有依赖（httpx2、python-docx、python-pptx）。

---

## 四、版本标签操作

### 4.1 标签信息

- **标签名：** `v1.1.0`
- **指向提交：** 发布文档回写后的 HEAD（commit 待生成后填入）
- **标签类型：** 附注标签（annotated tag）
- **标签信息：** 中文，包含版本概述

### 4.2 打标签命令

```bash
git tag -a v1.1.0 -m "完成 V1.1.0 版本发布：6 个 SPEC 全部收口"
git push origin master --tags
```

### 4.3 发布后检查

- [ ] `git tag -l v1.1.0` 确认本地标签存在
- [ ] `git ls-remote --tags origin` 确认远程标签存在
- [ ] GitHub Releases 页面确认标签可见

---

## 五、V1.1.0 产品边界确认

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

---

## 六、发布确认

**发布前状态：纯净**

- 工作树仅含 V1.1.0 发布文档相关改动，无业务代码改动
- 后端 704 测试 + 前端 411 测试 = 1115 个测试全部通过
- 前端 lint 和 build 均通过
- 0 warnings
- 数据库迁移到 0007 无错误
- 无未解决的阻断债务
- 所有文档已回写（README.md、acceptance.md、changelog-v1.1.0.md、regression-test-plan.md、release-checklist-v1.1.0.md）

**项目负责人已确认 SPEC 0010/0011/0012 收口并发布 V1.1.0。**
