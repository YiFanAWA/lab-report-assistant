# 决策 0020：启动 SPEC 0014 LLM 调用缓存

## 状态

已接受。

## 日期

2026-07-24

## 决策人

项目负责人。

## 背景

SPEC 0007（真实 DeepSeek LLM 接入，V1.1.0）已明确"不做 LLM 调用缓存"作为推迟项。V1.2.0 承接该项，编写 SPEC 0014 草案。

V1.1.0 上线后，5 个 provider 全部接入 DeepSeek LLM。相同输入（相同 messages、model、temperature）会重复调用 API，增加成本和延迟。缓存层可避免重复调用，对 provider 和 API 路由透明。

## 决策

启动 **SPEC 0014 LLM 调用缓存** 切片实现。

### 技术选择

1. **独立 SQLite 文件存储**：缓存表使用 `data/llm_cache/llm_cache.db`，不走 Alembic 迁移。理由：缓存是性能优化非业务真相，独立存储保持 owner 边界清晰，与业务数据库 `infrastructure/database/` 隔离。
2. **DeepSeekClient 接入**：缓存接入点是 `DeepSeekClient.chat_completion()`，provider 和 gateway 工厂零改动。
3. **默认关闭**：`LLM_CACHE_ENABLED` 默认 `false`，需显式启用，保证现有行为零变化。
4. **SHA256 缓存 key**：基于 `model + messages + response_format + temperature` 的规范化 JSON 摘要，`sort_keys=True` 保证字段顺序不影响 key。

### 新增文件

- 基础设施：`server/app/infrastructure/llm/llm_cache.py`
- 测试：`server/tests/test_llm_cache.py`

### 修改文件

- `server/app/infrastructure/llm/deepseek_client.py`（注入 cache 参数）
- `server/app/core/config.py`（新增 3 个配置项）
- `.env.example`（新增 3 个环境变量）

### 新增依赖

无（使用 Python 标准库 `sqlite3`、`hashlib`、`json`）。

## 范围边界

本决策引入：

- LLMCache 存储层（建表、读写、TTL、惰性淘汰）
- DeepSeekClient 缓存接入（调用前查、调用后写）
- 3 个环境变量配置（含降级规则）
- ~15 个单元测试

本决策明确不做：

- 不做 Redis 或内存缓存
- 不做缓存统计 API
- 不做手动失效接口
- 不修改任何 provider 或 gateway 工厂
- 不修改现有 API 路由合同
- 不把缓存表加入业务数据库 Alembic 迁移

## 验收计划

- `python -m pytest`：704 + 新增 ~15 = ~719 passed, 0 warnings
- `alembic upgrade head`：迁移无变化（缓存表不走 Alembic）
- `npm run lint` + `npm run build`：通过
- 缓存命中跳过 HTTP、未命中调用 HTTP 并写入、过期重新调用、禁用不查不写、写入失败降级

## 约束

- `cache=None` 时行为与现有完全一致（零回归风险）
- 缓存写入失败不阻断主流程，降级到无缓存
- 缓存 key 含 model 字段，模型切换后 key 不同
- 不污染业务数据库，缓存表独立存储
