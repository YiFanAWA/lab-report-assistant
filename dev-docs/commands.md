# 实验报告助手｜命令索引

本文档记录代码阶段实际可用的命令。

## 前置条件

- **Node.js** >= 22，npm >= 10
- **Python** >= 3.10，建议使用项目内虚拟环境（`server/.venv/`）
- **数据库**：SQLite，由 Alembic 迁移管理
- SPEC 0001 和 SPEC 0002 不访问真实 DeepSeek，`DEEPSEEK_API_KEY` 留空即可

## 首次安装

```bash
# 前端
cd apps/web
npm install

# 后端 — Windows PowerShell
cd server
python -m venv .venv
.venv\Scripts\activate
python -m pip install setuptools wheel
python -m pip install -e ".[dev]"
```

## 前端

全部命令在 `apps/web/` 目录下执行。

| 命令 | 作用 |
| --- | --- |
| `npm install` | 安装前端依赖 |
| `npm run dev` | 启动 Vite 开发服务 (localhost:5173) |
| `npm run build` | TypeScript 检查 + Vite 生产构建 |
| `npm run lint` | TypeScript 类型检查 |

## 后端

全部命令在 `server/` 目录下执行。

| 命令 | 作用 |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest` | 运行全部后端测试 |
| `.venv\Scripts\python.exe -m alembic upgrade head` | 应用数据库迁移 |
| `.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001` | 启动 API 服务 |

## 环境变量

SQLite 数据库路径默认使用 `server/data/db/app.db`。本地开发时可直接使用默认值，无需额外配置。

```bash
# Windows PowerShell
$env:DATABASE_URL = "sqlite:///./data/db/app.db"
```

`APP_ENV`、`LLM_PROVIDER`、`LLM_MODEL`、`DEEPSEEK_API_KEY` 采用默认值即可。SPEC 0002 默认使用本地规则草案提供者，不访问真实 DeepSeek。

## 验收命令

完整验收轮：

```bash
# 后端
cd server
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest

# 前端
cd apps/web
npm run build
```

## 版本收口命令

每完成一版或一个已确认开发切片后执行。提交前必须先确认验收证据和文档回写已经完成。

当前远程仓库：

```bash
origin  https://github.com/YiFanAWA/lab-report-assistant.git
```

```bash
git status --short --untracked-files=all
git diff -- <本版相关文件路径>
git add <本版相关文件路径>
git status --short
git commit -m "完成 SPEC XXXX 中文切片名称"
git push
```

版本收口禁止使用 `git add .`。如果远程仓库尚未配置，先完成本地 commit，并在 `dev-docs/acceptance.md` 或交接记录中说明未上传原因。
