# 实验报告助手｜依赖版本与官方目录规范复核

> 状态：已复核  
> 复核日期：2026-06-16  
> 依据：[tech-stack.md](tech-stack.md)、[implementation-plan.md](implementation-plan.md)  
> 阶段约束：本文档记录代码阶段前的版本与目录规范复核；实际安装和验收证据见 [acceptance.md](acceptance.md) 与 [commands.md](commands.md)。

## 1. 复核来源

本次复核使用以下来源：

- `npm.cmd view <package> version` 只读查询 npm 注册表。
- `python -m pip index versions <package>` 只读查询 PyPI 索引。
- Vite 官方文档：[Getting Started](https://vite.dev/guide/)。
- React Router 官方文档：[Installation](https://reactrouter.com/start/framework/installation)。
- TanStack Query 官方文档：[Installation](https://tanstack.com/query/latest/docs/framework/react/installation)。
- FastAPI 官方文档：[Bigger Applications - Multiple Files](https://fastapi.tiangolo.com/tutorial/bigger-applications/)。
- SQLAlchemy 官方文档：[ORM Quick Start](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)。
- Alembic 官方文档：[Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)。
- DeepSeek 官方文档：[Your First API Call](https://api-docs.deepseek.com/) 与 [Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing)。

本节为代码阶段前的只读复核记录。后续实际安装、脚手架创建和验收结果以 [acceptance.md](acceptance.md) 为准。

## 2. 样例数据复核

V1 首个标准演示课题：**胃病数据分析**。

样例数据文件：

```text
C:\Users\爹\Downloads\胃病数据集_教学实验版.xlsx
```

文件属性：

- 文件大小：66554 字节。
- 最近修改时间：2026-06-16 19:31:06。
- 当前只作为代码阶段样例数据来源记录，尚未复制到项目仓库。

工作簿结构：

| 工作表 | 行数 | 最大列数 | 说明 |
| --- | ---: | ---: | --- |
| 说明 | 10 | 2 | 数据集说明 |
| 数据概览 | 11 | 2 | 指标与数值概览 |
| 胃病数据 | 601 | 22 | 主数据表 |
| 数据字典 | 23 | 4 | 字段解释 |

主数据表字段：

```text
patient_id
age
sex
bmi
smoking_status
alcohol_frequency
spicy_food_days_per_week
nsaid_use
family_history_gastric_disease
stress_score
sleep_hours
h_pylori_positive
upper_abdominal_pain_score
bloating_score
nausea_score
acid_reflux_score
symptom_duration_months
endoscopy_inflammation_grade
diagnosis
gastric_disease
severity
treatment_response
```

代码阶段若需要把样例数据纳入仓库，应复制到后续样例数据目录，并记录来源、哈希、字段版本和导入时间。当前不执行复制。

## 3. 大模型供应商复核

V1 暂定大模型供应商：**DeepSeek**。

官方文档显示 DeepSeek API 兼容 OpenAI/Anthropic 格式，OpenAI 格式的 `base_url` 为：

```text
https://api.deepseek.com
```

V1 默认模型：

```text
deepseek-v4-pro
```

V1 快速或低成本候选模型：

```text
deepseek-v4-flash
```

不得把模型名写死在业务模块中。必须通过 `LLMGateway` 和配置读取，至少支持后续替换供应商或模型。

注意：

- `deepseek-chat` 与 `deepseek-reasoner` 已被官方标注将在 2026-07-24 15:59 UTC 废弃。
- 代码阶段不得默认使用上述两个旧模型名。
- 真实密钥不得写入仓库，只能通过环境变量或本地未提交配置读取。

## 4. 前端依赖复核

| 依赖 | 复核版本 | 来源 | 用途 |
| --- | --- | --- | --- |
| `react` | `19.2.7` | npm 注册表 | 前端 UI |
| `react-dom` | `19.2.7` | npm 注册表 | 浏览器渲染 |
| `vite` | `8.0.16` | npm 注册表 / Vite 官方文档 | 前端开发与构建 |
| `@vitejs/plugin-react` | `6.0.2` | npm 注册表 | React 插件 |
| `typescript` | `6.0.3` | npm 注册表 | 类型系统 |
| `react-router` | `7.17.0` | npm 注册表 | 前端路由 |
| `@tanstack/react-query` | `5.101.0` | npm 注册表 | 接口状态与轮询 |
| `vitest` | `4.1.10` | npm 注册表 | 前端单元测试框架（Vite 原生） |
| `@testing-library/react` | `^16.0.0` | npm 注册表 | React 组件 DOM 测试 |
| `@testing-library/jest-dom` | `^6.0.0` | npm 注册表 | jest-dom matchers（toBeInTheDocument 等） |
| `@testing-library/user-event` | `^14.0.0` | npm 注册表 | 用户交互模拟 |
| `jsdom` | `^25.0.0` | npm 注册表 | 浏览器环境模拟 |

前端目录规范：

```text
apps/web/
  index.html
  package.json
  vite.config.ts
  tsconfig.json
  src/
    main.tsx
    app/
    routes/
    features/
    shared/
```

约束：

- 使用 Vite 的 `react-ts` 模板方向。
- `index.html` 保持在 Vite 项目根目录，不移动到 `public`。
- 前端只消费后端状态和命令，不拥有业务状态机。
- TanStack Query 负责接口请求、缓存、刷新和任务状态轮询。
- React Router 只负责页面路由，不承担业务流程判断。

## 5. 后端依赖复核

| 依赖 | 复核版本 | 来源 | 用途 |
| --- | --- | --- | --- |
| `fastapi` | `0.137.1` | PyPI | API 框架 |
| `pydantic` | `2.13.4` | PyPI | 数据校验与 schema |
| `sqlalchemy` | `2.0.51` | PyPI | ORM 与数据库访问 |
| `alembic` | `1.18.4` | PyPI | 数据库迁移 |
| `uvicorn` | `0.49.0` | PyPI | 本地 ASGI 服务 |
| `httpx` | `0.28.1` | PyPI | HTTP 客户端 |
| `openai` | `2.41.1` | PyPI | DeepSeek OpenAI 兼容接口客户端 |
| `python-docx` | `1.2.0` | PyPI | SPEC 0002 简单 Word 要求文件正文提取 |
| `python-multipart` | `0.0.32` | PyPI | SPEC 0002 FastAPI `multipart/form-data` 文件上传 |

后端目录规范：

```text
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
    core/
    modules/
      projects/
      requirements/
      sources/
      evidence/
      datasets/
      analysis/
      execution/
      outlines/
      deliverables/
    infrastructure/
      database/
      storage/
      llm/
      fetchers/
      parsers/
      sandbox/
      renderers/
  worker/
  tests/
```

约束：

- 采用 FastAPI 官方多文件应用思路，`app/main.py` 作为入口，API 路由放在 `app/api/routers/`。
- 核心业务语义放在 `app/modules/` 与 `app/core/`，API 层只做协议映射。
- 数据库模型、会话和迁移放在 `app/infrastructure/database/` 与 `alembic/`。
- Alembic 使用 `pyproject` 或等价官方模板方向，迁移文件不得手写绕过迁移系统。
- Worker 独立于 HTTP 请求进程，但复用同一套核心模块和数据库合同。

SPEC 0002 当前实际启用的新增后端依赖为 `python-docx` 与 `python-multipart`。`python-docx` 安装时引入传递依赖 `lxml 6.1.1`。真实 DeepSeek 调用和 `openai` 客户端仍未接入本切片，后续接入前需重新复核配置、错误处理和无密钥降级行为。

SPEC 0003 实际启用的新增后端依赖：

| 依赖 | 复核版本 | 实际安装版本 | 来源 | 用途 |
| --- | --- | --- | --- | --- |
| `httpx` | `0.28.1` | `0.28.1` | PyPI | HTTP 采集适配器 |
| `pypdf` | `6.13.2` | `6.14.2` | PyPI | PDF 文档解析 |
| `beautifulsoup4` | `4.15.0` | `4.15.0` | PyPI | HTML 文档解析 |
| `lxml` | `6.1.1` | `6.1.1` | PyPI（SPEC 0002 已作为传递依赖安装） | beautifulsoup4 解析器 |

`playwright` 未在 SPEC 0003 安装，符合本切片边界。真实 DeepSeek 调用继续推迟到后续切片。

SPEC 0004 实际启用的新增后端依赖：

| 依赖 | 复核版本 | 实际安装版本 | 来源 | 用途 |
| --- | --- | --- | --- | --- |
| `pandas` | `3.0.3` | `3.0.3` | PyPI | 表格数据处理与字段类型推断 |
| `numpy` | `2.4.6` | `2.5.1` | PyPI | 数值计算（pandas 3.0.3 传递依赖升级，无破坏性变更） |
| `openpyxl` | `3.1.5` | `3.1.5` | PyPI | Excel 读取 |

`scipy`、`scikit-learn`、`matplotlib`、`playwright` 未在 SPEC 0004 安装，符合本切片边界（推迟到 SPEC 0005 Python 执行切片）。真实 DeepSeek 调用继续推迟到后续切片。

### SPEC 0005 计划启用的新增后端依赖

本切片已安装以下运行时依赖，实际安装版本记录如下：

| 依赖 | 复核版本 | 实际安装版本 | 来源 | 用途 |
| --- | --- | --- | --- | --- |
| `scipy` | `1.17.1` | `1.18.0` | PyPI | 统计检验（执行环境 import 白名单） |
| `scikit-learn` | `1.9.0` | `1.9.0` | PyPI | 基础建模（执行环境 import 白名单） |
| `matplotlib` | `3.11.0` | `3.11.0` | PyPI | 图表生成（agg backend，执行环境 import 白名单） |
| `psutil` | — | `7.2.2` | PyPI | 进程树内存软监控（SPEC 0005 新增，0.5s 轮询） |

约束：

- 上述依赖作为受控执行环境的 import 白名单成员，由应用托管，普通用户不手动安装。
- `playwright` 不在 SPEC 0005 安装，继续推迟到后续需要动态网页渲染的切片。
- 真实 DeepSeek 调用继续推迟到后续切片，本切片继续使用本地规则提供者 `LocalRuleCodeTaskProvider`。
- 执行环境严格限制 import 白名单为 `pandas`、`numpy`、`matplotlib`、`scipy.stats`、`sklearn`、`openpyxl`，禁止 `os`、`subprocess`、`socket`、`ssl`、`http.client`、`urllib`、`requests` 等，并通过 AST 校验拦截 `__import__()` 和 `importlib.import_module()` 动态导入。
- 内存监控使用 psutil 进程树总 RSS（解决 Windows venv launcher 导致的子进程内存遗漏问题），0.5s 轮询，超限 kill 整个进程树并标记 EXECUTION_MEMORY_LIMIT。

### SPEC 0006 计划启用的新增后端依赖

本切片计划安装以下运行时依赖，实际安装版本以 SPEC 0006 验收时记录为准：

| 依赖 | 复核版本 | 计划安装版本 | 来源 | 用途 |
| --- | --- | --- | --- | --- |
| `python-pptx` | `1.0.2` | `1.0.2` | PyPI | PPT 生成（从已确认大纲渲染 `.pptx` 文件） |

约束：

- `python-docx` `1.2.0` 已在 SPEC 0002 阶段安装，本切片复用，不重复安装。
- `python-pptx` `1.0.2` 在 SPEC 0006 阶段安装，传递依赖 `XlsxWriter 3.2.9`、`lxml 6.1.1`、`Pillow 12.3.0`、`typing-extensions 4.16.0` 复用现有环境。
- Word/PPT 生成依赖只能消费结构化大纲模型，不直接消费模型临时对话。
- 真实 DeepSeek 调用继续推迟到后续切片，本切片继续使用本地规则提供者 `LocalRuleOutlineProvider`。
- Word 渲染使用 python-docx 原生 API 构建，不引入外部模板引擎。
- PPT 渲染使用 python-pptx 母版驱动，不引入外部 PPT 模板引擎。
- 交付物文件大小上限 50MB，超限返回错误。

## 6. 数据分析与交付物依赖复核

| 依赖 | 复核版本 | 实际安装版本 | 来源 | 用途 |
| --- | --- | --- | --- | --- |
| `pandas` | `3.0.3` | `3.0.3` | PyPI | 表格数据处理 |
| `numpy` | `2.4.6` | `2.5.1` | PyPI | 数值计算（pandas 3.0.3 传递依赖升级） |
| `scipy` | `1.17.1` | `1.18.0` | PyPI | 统计检验（SPEC 0005 安装时升级到 1.18.0） |
| `scikit-learn` | `1.9.0` | `1.9.0` | PyPI | 基础建模 |
| `matplotlib` | `3.11.0` | `3.11.0` | PyPI | 图表生成 |
| `psutil` | — | `7.2.2` | PyPI | 进程树内存监控（SPEC 0005 新增，用于受控执行环境软监控） |
| `openpyxl` | `3.1.5` | `3.1.5` | PyPI | Excel 读取 |
| `python-docx` | `1.2.0` | `1.2.0` | PyPI | Word 生成 |
| `python-pptx` | `1.0.2` | `1.0.2` | PyPI | PPT 生成（SPEC 0006 安装） |
| `XlsxWriter` | — | `3.2.9` | PyPI | python-pptx 传递依赖（SPEC 0006 安装） |
| `httpx2` | — | `2.7.0` | PyPI | httpx 后继版本（V1.0 TD-001 清理安装，消除 fastapi.testclient 弃用警告；传递依赖 `httpcore2 2.7.0`、`truststore 0.10.4`） |
| `httpx` | `0.28.1` | `0.28.1` | PyPI | DeepSeek API HTTP 客户端（SPEC 0007 从 dev 依赖提升为生产依赖） |
| `pypdf` | `6.13.2` | `6.14.2` | PyPI | PDF 文本读取 |
| `beautifulsoup4` | `4.15.0` | `4.15.0` | PyPI | HTML 解析 |
| `playwright` | `1.60.0` | 未安装 | PyPI | 动态网页后备渲染（推迟到后续切片） |

约束：

- 上述依赖只是 V1 候选白名单，代码阶段应按最小闭环逐步加入。
- Playwright 只作为动态网页后备，不作为所有 URL 的默认采集方式。
- Python 数据分析环境由应用托管，普通用户不手动安装这些依赖。
- Word/PPT 生成依赖只能消费结构化交付物模型，不直接消费模型临时对话。

## 7. 代码阶段命令规范草案

代码阶段开始后，建议命令命名如下，具体命令以实际脚手架生成后为准：

| 命令 | 作用 |
| --- | --- |
| `npm run dev --workspace apps/web` | 启动前端开发服务 |
| `npm run build --workspace apps/web` | 构建前端 |
| `npm run test --workspace apps/web` | 前端测试 |
| `python -m uvicorn app.main:app --reload` | 启动后端 API |
| `python -m pytest` | 后端测试 |
| `alembic upgrade head` | 应用数据库迁移 |
| `python -m worker` | 启动后台 Worker |

这些命令当前只是规划，未创建对应文件或脚本。

## 8. 重新复核条件

出现以下情况时，必须重新复核本文件：

- 距离本次复核超过 7 天且尚未初始化依赖；
- 任一官方文档推荐方式发生变化；
- DeepSeek 模型名、价格、上下文长度或废弃计划变化；
- 样例数据文件发生修改；
- 项目从本地单用户改为在线多用户；
- 用户要求更换大模型供应商、前端框架或后端框架。
