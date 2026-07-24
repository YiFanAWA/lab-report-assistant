# 决策 0021：启动 SPEC 0015 GitHub Actions CI 流水线

## 状态

已接受。

## 日期

2026-07-24

## 决策人

项目负责人。

## 背景

V1.1.0-planning.md 曾明确"CI/CD：本地 MVP 不需要，推迟 V2.0"。项目已推送至 GitHub 公开仓库 `YiFanAWA/lab-report-assistant`，无 CI 时无法在推送时自动验证回归。V1.1.0 已有 1115 个测试（704 后端 + 411 前端），CI 可自动运行，降低人工验收成本。

V1.2.0 将 CI 提前到当前版本，编写 SPEC 0015 草案。

## 决策

启动 **SPEC 0015 GitHub Actions CI 流水线** 切片实现。

### 技术选择

1. **仅 master 触发**：CI 只对 `master` 分支的 push 和 pull_request 触发，不做 feature 分支触发。
2. **两 Job 并行**：后端 Job（Python 3.13 + pytest）和前端 Job（Node 20 + lint + build）并行运行。
3. **不配置分支保护**：CI 失败不阻断推送，首版仅作通知。
4. **不使用缓存**：首版不配置 pip/npm cache，优先正确性。
5. **科学计算包额外安装**：CI 额外 `pip install` pandas/numpy/scipy 等，弥补 TD-004（不在本切片修复 TD-004）。

### 新增文件

- `.github/workflows/ci.yml`

### 修改文件

无（不触碰任何业务代码）。

### 新增依赖

无（使用 GitHub 官方 Actions：checkout@v4、setup-python@v5、setup-node@v4）。

## 范围边界

本决策引入：

- GitHub Actions 工作流（后端测试 + 数据库迁移 + 前端类型检查 + 前端构建）
- master 分支 push/PR 触发

本决策明确不做：

- 不做 CD（持续部署）
- 不做 Docker 镜像构建推送
- 不做多 OS 矩阵
- 不做 code coverage 上传
- 不做 lint 工具集成（ruff/flake8）
- 不做安全扫描
- 不做缓存优化
- 不配置分支保护规则（需项目负责人手动操作）
- 不修改任何业务代码

## 验收计划

- `.github/workflows/ci.yml` 语法正确
- push 到 master 触发 CI
- backend job 绿色（704 passed, 0 warnings）
- frontend job 绿色（tsc 通过 + Vite 构建通过）
- `git diff` 确认 server/ 和 apps/web/ 无改动

## 约束

- CI 是基础设施配置，不触碰业务代码
- 不使用任何 GitHub Secrets（DEEPSEEK_API_KEY 留空，测试全 mock）
- CI 失败不阻断推送（首版不强制门禁）
- 与 SPEC 0014 正交，可独立验收
