# 实验报告助手｜第一开发切片 SPEC：项目工作区与脚手架

> 状态：已完成命令、API 和前后端代理验收，并已由项目负责人确认  
> 创建日期：2026-06-16  
> 确认日期：2026-06-16  
> 依据：[project-charter.md](../project-charter.md)、[architecture.md](../architecture.md)、[tech-stack.md](../tech-stack.md)、[dependency-review.md](../dependency-review.md)、[implementation-plan.md](../implementation-plan.md)  
> 阶段约束：本文档定义第一开发切片规格；代码阶段已获项目负责人批准并已执行本切片。

## 1. 切片定位

第一开发切片只解决一个问题：**把项目从文档真源推进到可运行的最小工程骨架，并跑通“创建实验项目”的最小闭环。**

它不是 V1 全功能实现，也不是实验报告助手的完整业务流程。它的价值是先建立：

- 前端、后端、数据库、迁移、测试和运行命令的基本工程边界；
- 后端拥有业务状态的最小项目工作区核心；
- 前端只通过 API 展示和触发项目创建，不私造业务状态；
- 后续需求拆解、资料证据、数据分析、Python 执行、Word/PPT 生成可以接入的稳定起点。

## 2. 本轮目标

第一开发切片完成后，开发者应能在本地完成以下路径：

```text
启动后端 API
  -> 启动前端工作台
  -> 打开项目列表页
  -> 创建“胃病数据分析”实验项目
  -> 后端保存项目记录
  -> 前端展示项目和 DRAFT 状态
  -> 重新刷新页面后项目仍存在
```

本切片只要求项目工作区的最小闭环，不要求进入实验要求拆解。

## 3. 明确不做

本切片不得实现以下内容：

- 不接入 DeepSeek 真实调用。
- 不要求用户提供真实 API Key。
- 不上传或解析 `胃病数据集_教学实验版.xlsx`。
- 不做实验要求 Word 上传。
- 不做公开 URL 采集。
- 不生成证据卡片。
- 不生成 Python 分析代码。
- 不执行 Python 数据分析。
- 不生成 Word 或 PPT。
- 不做注册登录。
- 不做在线多用户账号体系。
- 不做自由拖拽工作流。
- 不做 Docker 或容器沙箱。
- 不把样例数据复制进仓库，除非后续 SPEC 明确要求。

## 4. 推荐实现范围

本切片覆盖 `implementation-plan.md` 中的：

- 任务 1：仓库与框架脚手架；
- 任务 2 的最小子集：项目相关核心合同；
- 任务 3 的最小子集：项目工作区创建、查询和持久化。

不覆盖任务 4 及之后的业务流程。

## 5. 目标目录结构

实际代码阶段开始后，第一切片建议创建以下目录和文件。这里是规格，不是当前轮创建结果。

```text
apps/
  web/
    index.html
    package.json
    vite.config.ts
    tsconfig.json
    src/
      main.tsx
      app/
      routes/
      features/
        projects/
      shared/

server/
  pyproject.toml
  alembic.ini
  alembic/
    env.py
    versions/
  app/
    __init__.py
    main.py
    api/
      routers/
        health.py
        projects.py
    core/
    modules/
      projects/
    infrastructure/
      database/
      storage/
  tests/

dev-docs/
  specs/
```

如实际脚手架生成的文件名与官方模板不同，应优先遵守官方模板，并在完成后回写本文档或新增决策记录。

## 6. 后端核心合同

第一切片只定义项目工作区所需的最小合同。

### 6.1 `Project`

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | 字符串 | 项目唯一标识，由后端生成 |
| `name` | 字符串 | 项目名称，第一样例为“胃病数据分析” |
| `topic` | 字符串 | 老师指定课题或用户输入课题 |
| `status` | 枚举 | 当前项目阶段，创建后为 `DRAFT` |
| `created_at` | 时间 | 创建时间 |
| `updated_at` | 时间 | 更新时间 |

约束：

- `name` 不能为空。
- `topic` 不能为空。
- `status` 由后端维护，前端不得自行推断。
- 删除项目不进入第一切片。

### 6.2 `ProjectStatus`

第一切片至少需要支持：

```text
DRAFT
```

代码结构应为后续完整状态枚举预留位置，但第一切片不得虚假推进到后续阶段。

后续状态仍以 `architecture.md` 中的完整状态机为准。

### 6.3 `ProjectWorkspace`

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `project_id` | 字符串 | 所属项目 |
| `root_path` | 字符串 | 项目工作区根目录 |
| `created_at` | 时间 | 工作区创建时间 |

约束：

- 工作区路径必须位于应用受控数据目录内。
- 不允许用户输入任意宿主机路径作为项目目录。
- 第一切片可以只创建目录和元数据，不创建业务产物文件。

## 7. 后端 API 合同

第一切片建议提供以下 API。

### 7.1 健康检查

```text
GET /health
```

成功响应：

```json
{
  "status": "ok",
  "service": "lab-report-assistant-api"
}
```

用途：

- 验证后端服务启动；
- 给前端和测试提供最小探针；
- 不暴露密钥、路径或内部调试信息。

### 7.2 创建项目

```text
POST /api/projects
```

请求体：

```json
{
  "name": "胃病数据分析",
  "topic": "胃病数据分析"
}
```

成功响应：

```json
{
  "id": "由后端生成",
  "name": "胃病数据分析",
  "topic": "胃病数据分析",
  "status": "DRAFT",
  "created_at": "ISO 时间",
  "updated_at": "ISO 时间"
}
```

错误规则：

- `name` 为空返回结构化错误。
- `topic` 为空返回结构化错误。
- 数据库或工作区创建失败时返回结构化错误，不返回裸异常。

### 7.3 项目列表

```text
GET /api/projects
```

成功响应：

```json
{
  "items": [
    {
      "id": "项目标识",
      "name": "胃病数据分析",
      "topic": "胃病数据分析",
      "status": "DRAFT",
      "created_at": "ISO 时间",
      "updated_at": "ISO 时间"
    }
  ]
}
```

### 7.4 项目详情

```text
GET /api/projects/{project_id}
```

成功响应与创建项目响应保持一致。

找不到项目时返回结构化 `404` 错误。

## 8. 前端工作台范围

第一切片前端只需要两个视图：

### 8.1 项目列表视图

展示：

- 项目名称；
- 课题；
- 状态；
- 创建时间或更新时间；
- 创建项目入口。

行为：

- 页面加载时调用 `GET /api/projects`。
- 创建成功后刷新列表或更新缓存。
- 接口失败时展示可读错误，不伪装为空列表。

### 8.2 创建项目表单

字段：

- 项目名称；
- 课题。

默认建议：

- 可预填“胃病数据分析”，但必须允许用户修改。

提交行为：

- 调用 `POST /api/projects`。
- 成功后回到列表或进入项目详情。
- 失败时展示后端返回的结构化错误。

## 9. 数据库与迁移

第一切片使用 SQLite。

最低要求：

- 通过 SQLAlchemy 定义项目表。
- 通过 Alembic 创建第一条迁移。
- 运行迁移后能创建项目表。
- 项目记录刷新页面后仍存在。

表建议：

```text
projects
  id
  name
  topic
  status
  workspace_root
  created_at
  updated_at
```

约束：

- 不在业务代码中直接拼接 SQLite 私有 SQL。
- 数据库路径由配置提供。
- 迁移文件不得手写绕过 Alembic 流程。

## 10. 本地配置

第一切片应创建 `.env.example`，但不得写入真实密钥。

建议配置项：

```text
APP_ENV=local
DATABASE_URL=sqlite:///./data/app.db
PROJECT_DATA_ROOT=./data/projects
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-v4-pro
DEEPSEEK_API_KEY=
```

约束：

- `DEEPSEEK_API_KEY` 留空。
- 第一切片不实际调用 DeepSeek。
- 配置读取失败时应给出结构化错误或清晰启动错误。

## 11. 测试与验收

第一切片完成后必须提供当前实际运行过的命令和结果。

最低验收命令建议：

```text
npm run build --workspace apps/web
python -m pytest
alembic upgrade head
python -m uvicorn app.main:app --reload
```

本切片验收项：

- 后端健康检查返回 `status=ok`。
- 数据库迁移可以创建项目表。
- `POST /api/projects` 可以创建“胃病数据分析”项目。
- `GET /api/projects` 可以列出已创建项目。
- `GET /api/projects/{project_id}` 可以读取项目详情。
- 前端项目列表页能展示后端返回的项目。
- 刷新前端页面后项目仍能从后端加载。
- 空项目名称或空课题会得到结构化错误。
- 前端构建通过。
- 后端测试通过。

如果任一命令无法运行，必须说明原因、影响范围和替代证据。

## 12. 错误处理

第一切片应建立统一错误形状。

建议结构：

```json
{
  "error": {
    "code": "PROJECT_NAME_REQUIRED",
    "message": "项目名称不能为空",
    "field": "name"
  }
}
```

约束：

- 不向前端返回裸异常堆栈。
- 不把数据库错误原文直接暴露给用户。
- 前端不得用固定字符串猜测错误原因，应展示后端结构化错误。

## 13. 安全与边界

第一切片虽然是本地单用户，也必须遵守以下边界：

- 不做注册登录。
- 不写入真实 DeepSeek API Key。
- 不允许用户指定任意项目工作区根路径。
- 不在前端保存业务真相。
- 不执行用户上传代码。
- 不读取 `胃病数据集_教学实验版.xlsx`。
- 不访问公开 URL。

## 14. 文档回写要求

第一切片代码真正完成后，必须回写：

- `dev-docs/README.md`：补充实际运行命令索引。
- `dev-docs/acceptance.md`：记录实际验收命令和结果。
- `dev-docs/implementation-plan.md`：勾选任务 1 以及任务 2、任务 3 中已完成的最小子项。
- 本 SPEC：若实现范围与本文档不同，必须更新差异和原因。

当前实现备注：

- 后端实际目录采用 `server/`，仍符合技术栈决策中“Python + FastAPI 后端”的主线。
- 第一切片已完成后端测试、数据库迁移、API 合同、前端类型检查、前端构建和 Vite `/api` 代理联通验收。
- 当前会话未暴露内置浏览器执行工具，本机也未发现 Edge/Chrome 可执行文件，因此未做真实可视化点击验收；该限制已写入 `acceptance.md`。
- 第一切片暂无独立 format 命令，当前门禁以 TypeScript 检查、Vite 构建、pytest、Alembic 迁移和前后端联通验证为准。

## 15. 停止条件

第一切片完成的停止条件：

- 工程骨架存在并能启动。
- 项目创建、列表和详情三个最小 API 可用。
- 前端能完成创建和展示项目。
- SQLite 持久化可用。
- 基础测试和构建命令有当前证据。
- 没有引入本 SPEC 明确排除的功能。
- 文档回写完成。

完成第一切片后必须暂停，由项目负责人确认后再进入下一切片。

## 16. 后续切片入口

第一切片之后，下一切片建议进入：

```text
实验要求输入与结构化任务单 SPEC
```

该下一切片才开始处理：

- Word 要求上传；
- 粘贴实验要求；
- LLM Gateway 的结构化输出候选；
- 用户确认任务单；
- L0-L3 复刻分级。
