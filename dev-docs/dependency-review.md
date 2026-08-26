- 官方 LibreOffice 26.2.5 Windows x86-64 MSI 已在临时 runtime 中完成真实验收；MSI SHA-256 为 `F15BA07BFCB0186986CF3171063506F5D207C11F8CC051BA0D135209E9E915F9`，安装包、二进制和解压 runtime 仍不写入 Git。
- 项目工作台和交付审阅 projection 不新增运行时依赖；它们只读取现有数据库事实，前端不得成为阶段、质量门禁或交付版本 owner。
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
| `scienceplots` | `2.1.0` | 已移除 | PyPI | ~~科研图表样式库（SPEC 0027 新增）~~ **SPEC 0028 已移除**：用 nature-figure rcParams 手动配置替换，不再需要外部样式库依赖 |
| `seaborn` | `0.13.0` | `0.13.0` | PyPI | 统计数据可视化（SPEC 0027 新增，analysis 可选依赖，用户代码通过沙箱调用） |
| `easypptx` | `0.5.0` | `0.5.0` | PyPI | python-pptx 封装层（SPEC 0027 新增，主 dependencies，仅借鉴百分比定位 + Grid 布局思路，不替换 PptRenderer 对象模型） |

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
| `python -m worker.main` | 启动后台 Worker |

这些命令当前只是规划，未创建对应文件或脚本。

## 8. 重新复核条件

出现以下情况时，必须重新复核本文件：

- 距离本次复核超过 7 天且尚未初始化依赖；
- 任一官方文档推荐方式发生变化；
- DeepSeek 模型名、价格、上下文长度或废弃计划变化；
- 样例数据文件发生修改；
- 项目从本地单用户改为在线多用户；
- 用户要求更换大模型供应商、前端框架或后端框架。

## 9. Docker 镜像依赖（SPEC 0013，2026-07-24 新增）

V1.2.0 Docker 化部署引入的基础设施镜像，不新增 Python/Node.js 业务依赖。

### 9.1 基础镜像

| 镜像 | 用途 | 选择理由 |
| --- | --- | --- |
| `python:3.13-slim` | 后端 + Worker 运行时 | 与开发环境 3.13.5 一致；slim（debian glibc）支持科学计算包预编译 wheel，alpine（musl libc）不支持 |
| `node:20-slim` | 前端构建阶段 | Node 20 LTS，支持 Vite 6 构建 |
| `nginx:alpine` | 前端静态托管 + API 反向代理 | 仅托管静态文件和反向代理，无需 Python/Node 运行时，alpine 体积小 |

### 9.2 科学计算包（已声明在 pyproject.toml optional-dependencies，TD-004 已于 SPEC 0016 清理）

AGENTS.md 要求"应用托管受控环境，用户不应手动安装 pandas/numpy/matplotlib"。这些包由用户代码通过 `python_executor` 运行时调用，应用代码不直接导入，因此声明在 `[project.optional-dependencies] analysis` 段（而非主 `dependencies`），让用户选择安装模式：

| 包 | 版本约束 | 用途 |
| --- | --- | --- |
| pandas | >=3.0.3 | 数据分析 |
| numpy | >=2.5.1 | 数值计算 |
| scipy | >=1.18.0 | 统计检验 |
| scikit-learn | >=1.9.0 | 机器学习 |
| matplotlib | >=3.11.0 | 图表生成 |
| psutil | >=7.2.2 | 执行沙箱内存监控 |
| scienceplots | ~~>=2.1.0~~ 已移除 | ~~科研图表样式库（SPEC 0027 新增）~~ **SPEC 0028 已移除**：用 nature-figure rcParams 手动配置替换 |
| seaborn | >=0.13.0 | 统计数据可视化（SPEC 0027 新增，用户代码通过沙箱调用） |

**SPEC 0027 新增主依赖（非 analysis 组）：**

| 包 | 版本约束 | 用途 |
| --- | --- | --- |
| easypptx | >=0.5.0 | python-pptx 封装层（仅借鉴百分比定位 + Grid 布局思路到 `ppt_renderer.py` 辅助方法，不替换 `PptRenderer` 对象模型；不加入沙箱白名单） |

安装方式：

- LocalRule 模式（最小依赖）：`pip install -e ".[dev]"`
- 完整模式（含科学计算包，支持真实执行用户 Python 代码）：`pip install -e ".[dev,analysis]"`
- Docker 镜像自动安装完整依赖：Dockerfile 使用 `pip install -e ".[dev,analysis]"`

### 9.3 已知限制

- ~~科学计算包未声明在 `pyproject.toml` dependencies 中~~（**TD-004 已于 SPEC 0016 关闭**：已声明在 `[project.optional-dependencies] analysis` 段，Dockerfile 改用 `pip install -e ".[dev,analysis]"` 一次安装）。

### 9.4 文档解析依赖修复（2026-07-24，SPEC 0013 实现过程中发现）

Docker 化实现过程中发现 `pyproject.toml` 遗漏了 3 个文档解析直接依赖，导致 Worker 容器启动时 `ModuleNotFoundError: No module named 'bs4'`。已补充到 `pyproject.toml` 的 dependencies 中：

| 包 | 版本约束 | 用途 | 引用位置 |
| --- | --- | --- | --- |
| beautifulsoup4 | >=4.12.0 | HTML 文档解析 | `app/infrastructure/parsers/html_parser.py:9` |
| lxml | >=5.0.0 | BeautifulSoup 的 lxml 解析器后端 | `app/infrastructure/parsers/html_parser.py:26`（`BeautifulSoup(content, "lxml")`） |
| pypdf | >=4.0.0 | PDF 文档文本提取 | `app/infrastructure/parsers/pdf_parser.py:9` |

**根因：** 这些包在 SPEC 0003（公开资料与证据工作流）实现时手动 `pip install` 但未写入 `pyproject.toml`，本地开发环境能跑但 Docker 镜像构建时 `pip install -e ".[dev]"` 不会安装它们。

**验证：** 本地 venv 重新 `pip install -e ".[dev]"` 后 `pytest -q` 结果 704 passed，0 warnings，无回归。Docker 镜像重新 build 后 Worker 容器正常启动。

## 10. SPEC 0032 外部来源审查

本切片不新增运行时 Python/NPM 依赖，不把外部仓库整包复制到项目中。

| 来源 | 用途 | 许可/风险 | 决策 |
| --- | --- | --- | --- |
| `hugohe3/ppt-master` | 路由式 PPT 工作流、原生可编辑输出、模板复用和逐页质量门禁参考 | MIT；复制代码时需保留版权与许可证 | 只吸收工作流与验收思想，当前切片不复制完整 Skill 源码 |
| `xhh678876/openclaw-sjtu` | 交大 PPT 生成入口、模板目录和本地文件提取能力参考 | 仓库许可证以当前 `LICENSE` 为准；模板/字体再分发权需逐项确认 | 不接入校园账号和校园业务；模板授权未确认时只登记来源，不复制资源 |
| 当前项目 `pptxforge` | 现有 PPT 主渲染路径 | MIT，已在 SPEC 0030 审查 | 保留，不替换 |

网络下载、校园凭证、外部图片和模型服务均不作为 SPEC 0032 的运行时依赖。

## 11. SPEC 0033 论文级自适应版式审查

- 不新增运行时依赖；规划器使用 Python 标准库，PPT/Word 继续复用已批准的 `pptxforge`、`python-docx` 和现有渲染工具。
- 版式规划语义归属 `server/app/modules/outlines/layout_planner.py`，不下沉到前端、LLM prompt 或临时预览脚本。
- 规划器只读取大纲文本和真实执行产物，不生成统计指标、不下载素材、不改变数据结论。
- Word/PPT/PDF 视觉渲染属于验收工具链，不作为新的业务运行时依赖；本机缺少 LibreOffice/Word 时只记录视觉验收缺口，不伪装成通过。

## 12. SPEC 0034 正式论文与高级答辩 PPT 审查

- 不新增运行时依赖；正式论文结构规划使用 Python 标准库，Word/PDF/PPT 继续复用现有 `python-docx`、`pptxforge`、`python-pptx` 和渲染工具链。
- 新增 `server/app/modules/outlines/document_planner.py` 属于交付物结构规划，不拥有数据、证据或实验结论；只读取已确认大纲和真实执行产物。
- DOCX 仍是可编辑源，PDF 只允许从最终 DOCX 导出；当前机器缺少 LibreOffice/Word，因此本轮只完成 DOCX 结构验收和 PPT 视觉验收，未将 PDF 视觉转换标记为通过。
- 未复制外部仓库、校园模板、字体或图片资源，不新增在线服务、模型调用或运行时包。

## 13. SPEC 0035 大样本公开论文解读案例审查

- 不新增运行时依赖；案例生成脚本复用现有 pandas、matplotlib、python-docx、pptxforge 和 python-pptx 能力。
- 论文 PDF、全文 XML、原始 CSV 和来源清单属于 `server/dev-docs/e2e-screenshots/spec0035_paper_review/` 下的可复核演示资料，不进入应用运行时依赖和用户任意路径读取范围。
- 数据集页面标注 CC BY 4.0，论文为开放获取；交付物保留论文 DOI、数据集 DOI、原始页面、全文 XML 地址和本地文件路径。
- 本切片只做原论文结论解读与本地描述性复核，不新增医学诊断、治疗建议或论文原始回归模型自动复现能力。

## 14. SPEC 0036 论文解读深度整改审查

- 不新增运行时依赖；回归、置信区间和图表复用已有 `scikit-learn`、`scipy`、`pandas`、`matplotlib` 与交付物渲染链。
- `statsmodels` 未安装，因此未新增该依赖；简化 Logistic 使用现有 `scikit-learn`，标准误由信息矩阵计算并在来源清单中标注为教学性复核。
- 新增结果图表和 CSV 仍属于 `spec0035_paper_review` 可复核演示资料，不改变应用运行时依赖，不进入任意路径读取。
- 统计结果不等同原论文模型复现，不扩展医学诊疗边界，不新增在线服务、模型调用或外部仓库代码。

## 15. SPEC 0037 语义图表选择与 PPT 组件优化审查

- 不新增运行时依赖；图表规划器只使用 Python 标准库，真实绘图继续复用现有 `pandas`、`matplotlib` 和 `scikit-learn`。
- PPT 继续复用项目已经批准的 `pptxforge` 依赖及其 `StatRow`、`Callout`、`TwoColumn`、`IconRow`、`Grid` 和 `Stack` 组件。
- 不复制 `ppt-master`、上海交大模板、字体或图片资源；外部仓库只作为此前已登记的工作流/风格参考。
- 图表 artifact 增加的是追溯元数据，不改变 API、数据库 schema、沙箱白名单或 LLM 模型合同。

## 16. SPEC 0038 正式学术论文规范化审查

- 不新增运行时依赖；正式论文结构、引用映射和章节编号使用现有 Python 标准库、`python-docx` 与已有渲染链。
- `formal_academic` 是 `WordRenderer` 的文档 profile，不改变 API、数据库 schema、LLM Gateway、Worker 或 PPT 组件合同。
- 论文引用只消费案例脚本提供的已确认论文/数据集来源目录；不在 renderer 内生成虚构来源。
- PDF 由最终 DOCX 通过当前机器的 Word 发布流程导出；PDF 仅作为交付物和视觉验收产物，不作为新的运行时依赖。
- 本轮复用现有图表、`pptxforge` 组件和数据文件，不复制 `ppt-master`、上海交大模板、字体或图片资源。

## 17. SPEC 0039 论文级多语义图形系统审查

- 当前 SPEC 只登记设计合同和实施边界，不新增运行时依赖；规划器使用 Python 标准库，真实图形继续复用现有 `matplotlib`、`python-docx`、`python-pptx` 和已批准的 `pptxforge`。
- `figure_planner.py` 作为图形语义唯一 owner；`chart_planner.py` 只保留数据图子适配，不在 Word/PDF/PPT renderer 中复制语义判断。
- 计划复用 `pptxforge` 的 `Stack`、`TwoColumn`、`Grid`、`IconRow`、`Callout`，不复制 `ppt-master`、上海交大模板、字体或图片资源。
- 不改变 API、数据库 schema、LLM Gateway、Worker、沙箱白名单或产品边界；是否需要任何新依赖必须在进入实现前重新审查。

## 18. SPEC 0042 开放科研资产与 SVG 转换依赖审查

| 项目 | 版本/来源 | 用途 | 决策与证据 |
|---|---|---|---|
| `resvg_py` | `==0.3.3` | 将已通过许可证、哈希与安全校验的静态 SVG 转换为 Word/PPT 兼容 PNG | 锁定精确版本；仅接收注册表路径；Windows venv 转换通过；`python:3.13-slim` manylinux wheel 安装并输出有效 PNG 签名 |
| Bioicons CC0 资产 | 上游 commit `d29e766ea7580b8063c4f47b29e872db40a4d979` | 首批科研器材、仪器、算法和结果组件 | 只收录 `static/icons/cc-0/` 下逐项审计的 7 个 SVG；manifest 记录上游 URL、作者、许可和 SHA-256；不整仓 vendoring |
| CC0 1.0 | Creative Commons | 资产许可 | 本地 `LICENSES/CC0-1.0.md` 提供离线审计入口；完整法律文本以官方 URL 为准 |

安全边界：转换前拒绝脚本、事件、DTD、实体、动画、`foreignObject`、外部资源、外部 CSS URL、路径逃逸、哈希漂移、超 2 MiB、超 5,000 元素和超 64 层嵌套。运行时不联网，不接受任意文件路径，不收录 BioRender/Mind the Graph 受限或带水印素材。
### SPEC 0042 验收工具链补充

- 最终 PDF 样稿使用 Codex 文档/PDF运行时自带的 ReportLab、PyPDF 与 PDFium 生成/验收，不写入 `server/pyproject.toml`，不构成应用运行时依赖。
- PDF 嵌入本机已有的开放许可 Noto Sans SC 字体子集，并附两张原始科研 PNG 与对应 JSON；不复制或打包受限商业字体。
- Microsoft Word COM 在当前宿主连续出现无窗口自动化卡死，相关本轮/遗留 `/Automation -Embedding` 孤儿进程已按 PID 核验后清理；最终 PDF 改用独立 PDF 工具链，PowerPoint 原生导出仍成功。
- 跨平台像素级确定性仍受字体可用性影响；当前合同保证画布、语义、资产真源和同一环境内渲染稳定。若要求跨平台 PNG 哈希完全一致，后续切片需审计并随应用分发固定开放许可 CJK 字体。

## 19. SPEC 0047 PDF portable runtime 与投影审查

- PDF 正式交付物不新增正文排版 owner；PDF 仅由最终 DOCX 通过 DocxPdfExporter 派生。
- LibreOffice headless 作为 Windows portable bundle 的显式运行时输入，构建脚本不自动下载、不静默替换，并要求 runtime-metadata.json 记录版本、来源、source_sha256 和许可证文件。
- 运行时通过 PDF_CONVERTER_PATH 注入 service/worker；转换适配器设置临时 profile、超时、输出大小上限和 PDF 魔数校验。
- 官方 MSI 已完成临时解压 runtime、许可证路径和 SHA-256 验收；portable bundle 约 1.88 GB，完整包体仍只保留在临时/忽略目录，不作为仓库依赖文件提交。
- 项目工作台和交付审阅 projection 不新增运行时依赖；它们只读取现有数据库事实，前端不得成为阶段、质量门禁或交付版本 owner。
