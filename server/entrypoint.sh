#!/bin/sh
# 后端容器入口脚本：先执行数据库迁移，再启动 uvicorn
set -e

echo "[Entrypoint] 等待数据库 volume 就绪..."
sleep 1

echo "[Entrypoint] 执行数据库迁移..."
.venv/bin/python -m alembic upgrade head

echo "[Entrypoint] 启动后端服务..."
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
