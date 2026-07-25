# 后端镜像：多阶段构建（builder 安装依赖 + runtime 精简运行时）
# 基础镜像用 slim（debian glibc），不用 alpine（musl libc 无科学计算包预编译 wheel）

# ===== 阶段 1：依赖安装（builder）=====
FROM python:3.13-slim AS builder
WORKDIR /app

# editable install 需要包源码，先复制依赖描述和源码目录
COPY pyproject.toml ./
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY worker/ worker/
COPY scripts/ scripts/

# 创建 venv 并安装依赖
# Linux 容器 venv 路径为 .venv/bin/（非 Windows 的 .venv/Scripts/）
# TD-004 已清理（SPEC 0016）：科学计算包声明在 pyproject.toml [project.optional-dependencies] analysis
# Docker 镜像需要完整分析依赖（容器内执行用户 Python 代码），使用 .[dev,analysis] 一次安装
RUN python -m venv .venv && \
    .venv/bin/pip install --no-cache-dir --upgrade pip && \
    .venv/bin/pip install --no-cache-dir -e ".[dev,analysis]"

# ===== 阶段 2：运行时（runtime）=====
FROM python:3.13-slim AS runtime
WORKDIR /app

# 从 builder 复制 venv（含全部依赖）
COPY --from=builder /app/.venv /app/.venv

# 复制源码（不复制 tests/data/.venv，由 .dockerignore 排除）
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY worker/ worker/
COPY scripts/ scripts/
COPY entrypoint.sh ./

# 处理 Windows 创建的 entrypoint.sh 可能的 CRLF 行尾
# 确保 shell 脚本在 Linux 容器中可执行
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

# 时区设置
ENV TZ=Asia/Shanghai

EXPOSE 8001

# 健康检查：用 venv 内 Python 调用 /health 端点
HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=15s \
  CMD .venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health').read()" || exit 1

# 入口：先迁移数据库，再启动 uvicorn
CMD ["./entrypoint.sh"]
