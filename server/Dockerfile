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
RUN python -m venv .venv && \
    .venv/bin/pip install --no-cache-dir --upgrade pip && \
    .venv/bin/pip install --no-cache-dir -e ".[dev]" && \
    # 额外安装科学计算包（AGENTS.md 要求应用托管受控环境，用户不应手动安装分析依赖）
    # 版本与开发环境一致，确保容器内外行为一致
    .venv/bin/pip install --no-cache-dir \
        pandas==3.0.3 \
        numpy==2.5.1 \
        scipy==1.18.0 \
        scikit-learn==1.9.0 \
        matplotlib==3.11.0 \
        psutil==7.2.2

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
