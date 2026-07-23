# 前端镜像：多阶段构建（node 构建产物 + nginx 静态托管）

# ===== 阶段 1：构建前端产物（builder）=====
FROM node:20-slim AS builder
WORKDIR /app

# 先复制依赖描述，利用 Docker 层缓存
COPY package.json package-lock.json* ./
RUN npm ci

# 复制源码并构建
COPY . .
RUN npm run build

# ===== 阶段 2：nginx 静态托管（runtime）=====
FROM nginx:alpine AS runtime

# 复制构建产物到 nginx 静态目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# nginx 默认 CMD 即可，无需覆盖
