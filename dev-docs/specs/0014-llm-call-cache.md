# SPEC 0014：LLM 调用缓存

> **状态：** 草案，待项目负责人确认  
> **日期：** 2026-07-24  
> **前置：** SPEC 0013 Docker 化部署已收口（commit `c210911`），V1.1.0 已发布（v1.1.0 标签），SPEC 0007 真实 DeepSeek LLM 接入已完成  
> **目标版本：** v1.2.0

---

## 一、目标与边界

### 1.1 目标

为 DeepSeek LLM 调用增加缓存层，避免相同输入重复调用 API，降低成本和延迟。缓存对 provider 和 API 路由透明，仅由基础设施层 `DeepSeekClient` 接入。

### 1.2 范围内

- 新增 `LLMCache` 存储层（独立 SQLite 文件，自动建表，不走 Alembic）
- `DeepSeekClient.chat_completion()` 注入缓存依赖，调用前查缓存，调用后写缓存
- 缓存 key 基于 `model + messages + response_format + temperature` 的 SHA256 摘要
- 新增 3 个环境变量：`LLM_CACHE_ENABLED`、`LLM_CACHE_TTL_SECONDS`、`LLM_CACHE_DB_PATH`
- 缓存命中时跳过 HTTP 调用，直接返回缓存内容（标记 `cache_hit=true`）
- 缓存写入失败不阻断主流程（降级到无缓存调用）
- 单元测试覆盖：命中、未命中、过期、禁用、写入失败降级、key 稳定性

### 1.3 范围外（不做清单）

| 不做项 | 原因 | 后续入口 |
| --- | --- | --- |
| 不做 Redis 或内存缓存 | V1 本地单用户，SQLite 足够；Redis 引入运维负担 | V2.0 多用户时评估 |
| 不做缓存统计 API | 运维监控非本轮目标，可通过日志查 | V2.0 |
| 不做手动失效接口 | TTL + 配置开关已满足；手动失效增加 API 面 | V2.0 |
| 不做跨模型缓存共享 | 不同模型输出不同，缓存 key 含 model 字段天然隔离 | 永久不做 |
| 不做缓存预热 | V1 场景不需要批量预填充 | V2.0 |
| 不修改任何 provider 或 gateway 工厂 | 缓存是基础设施关注点，不属于业务模块 | 永久不做 |
| 不修改现有 API 路由合同 | 缓存对前端透明 | 永久不做 |
| 不缓存 LocalRule 调用 | LocalRule 无网络成本，无需缓存 | 永久不做 |
| 不把缓存表加入业务数据库 Alembic 迁移 | 缓存是性能优化非业务真相，独立存储避免 owner 漂移 | 永久不做 |
| 不做缓存加密 | 缓存内容是 LLM 返回的 JSON，无敏感数据；API Key 不写入缓存 | 永久不做 |

### 1.4 与 SPEC 0007 的关系

SPEC 0007 已明确"不做 LLM 调用缓存"。本切片承接该项，将推迟项落地。SPEC 0007 建立的 `DeepSeekClient` 是本轮缓存的唯一接入点，不改动其错误码、重试、降级逻辑，只在外层包裹缓存查询。

---

## 二、架构设计

### 2.1 分层架构

```
API 路由 / Worker handler（不改动）
  ↓ 调用
Gateway 工厂函数（不改动）
  ↓ 返回
DeepSeekXxxProvider（不改动）
  ↓ 调用 self._client.chat_completion(...)
DeepSeekClient（扩展：调用前查缓存，调用后写缓存）
  ↓ 读 / 写
LLMCache（新增，基础设施层）
  ↓ SQLite
独立缓存文件 data/llm_cache/llm_cache.db
```

### 2.2 唯一 Owner 边界

| 层 | Owner 文件 | 职责 | 本轮改动 |
| --- | --- | --- | --- |
| 基础设施 | `server/app/infrastructure/llm/llm_cache.py`（新建） | 缓存存储、建表、读写、TTL、淘汰 | 新建 |
| 基础设施 | `server/app/infrastructure/llm/deepseek_client.py` | HTTP 调用、超时、重试、错误映射 | 注入 cache 依赖 |
| LLM 模块 | `server/app/modules/llm/gateway.py` | 工厂选择 provider | 传递 cache 配置给 client |
| 配置 | `server/app/core/config.py` | 环境变量读取 | 新增 3 个配置项 |
| API 路由 | `server/app/api/routers/` | 协议映射 | 不改动 |
| provider | `server/app/modules/llm/deepseek_*.py` | Prompt 构造、结构化校验、降级 | 不改动 |
| 业务数据库 | `server/app/infrastructure/database/` | 业务真相表 | 不改动（缓存表不进入业务库） |

### 2.3 关键决策：缓存表不进入业务数据库 Alembic 迁移

**决策：** 缓存表使用独立 SQLite 文件 `data/llm_cache/llm_cache.db`，由 `LLMCache` 在首次访问时自动 `CREATE TABLE IF NOT EXISTS`，不走 Alembic 迁移。

**理由：**
- 按 AGENTS.md "数据库基础设施：拥有引擎、会话和迁移接线" —— Alembic 迁移归业务数据库 owner。缓存表是性能优化，不是业务真相，混入业务迁移会模糊 owner 边界。
- 缓存表丢失可重建（重新调用 LLM 即可），与业务表的不可丢失性质不同。
- 独立文件便于清理（删除文件即清空缓存，不影响业务数据）。
- Docker 化时缓存 volume 可独立挂载或 ephemeral（SPEC 0013 已建好的 `project-data` volume 可承载）。

**风险：** 独立 SQLite 文件需要单独的连接管理。`LLMCache` 自带 `sqlite3` 连接，不复用业务 SessionLocal，避免连接池混淆。

### 2.4 缓存命中/未命中流程

```
DeepSeekClient.chat_completion(messages, response_format, temperature)
  ↓
检查 LLM_CACHE_ENABLED
  ├─ false → 直接 HTTP 调用（现有逻辑不变）
  └─ true ↓
计算 cache_key = SHA256(model + messages + response_format + temperature)
  ↓
LLMCache.get(cache_key)
  ├─ 命中且未过期 → 返回缓存内容，日志记录 cache_hit
  └─ 未命中或已过期 ↓
HTTP 调用 DeepSeek API（现有逻辑不变）
  ├─ 成功 → LLMCache.set(cache_key, content) 写入缓存（失败不阻断），返回 content
  └─ 失败 → 抛 DeepSeekError（现有降级逻辑不变，不写入缓存）
```

---

## 三、LLMCache 存储层设计

### 3.1 基础设施层

**文件：** `server/app/infrastructure/llm/llm_cache.py`

```python
class LLMCache:
    """LLM 调用缓存存储层。

    职责：缓存 key 计算、SQLite 读写、TTL 过期判断、自动建表。
    不负责 HTTP 调用和错误映射（由 DeepSeekClient 负责）。

    使用独立 SQLite 文件，不走 Alembic 迁移，不复用业务 SessionLocal。
    缓存表丢失可重建，不影响业务数据。
    """

    def __init__(self, db_path: str, ttl_seconds: int = 86400): ...

    def get(self, cache_key: str) -> str | None:
        """查询缓存。返回 content 或 None（未命中/已过期/禁用/异常）。"""

    def set(self, cache_key: str, content: str) -> None:
        """写入缓存。失败不抛异常，仅记录 warning 日志。"""

    @staticmethod
    def compute_key(model: str, messages: list[dict],
                    response_format: dict | None,
                    temperature: float) -> str:
        """计算缓存 key = SHA256(规范化 JSON)。"""
```

### 3.2 缓存表结构

```sql
CREATE TABLE IF NOT EXISTS llm_call_cache (
    cache_key TEXT PRIMARY KEY,           -- SHA256 摘要（64 位十六进制）
    content TEXT NOT NULL,                -- LLM 返回的 content 字符串
    model TEXT NOT NULL,                  -- 模型名（便于排查）
    created_at REAL NOT NULL,             -- 写入时间戳（time.time()）
    expires_at REAL NOT NULL              -- 过期时间戳（created_at + ttl）
);
CREATE INDEX IF NOT EXISTS idx_llm_cache_expires_at ON llm_call_cache(expires_at);
```

### 3.3 缓存 key 计算

```python
import hashlib
import json

payload = {
    "model": model,
    "messages": messages,            # list[dict]，OpenAI 格式
    "response_format": response_format,  # dict | None
    "temperature": temperature,      # float
}
canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
cache_key = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

**key 稳定性保证：**
- `sort_keys=True` 确保 messages 字段顺序不影响 key
- `ensure_ascii=False` 保留中文，避免编码差异
- `default=str` 兜底非 JSON 类型（理论不应出现，因为 messages 都是 str/dict）
- temperature 作为 float 直接序列化，Python `json.dumps` 对 0.3 输出 "0.3" 稳定

### 3.4 TTL 与淘汰策略

- **TTL 判断：** `get` 时比较 `expires_at` 与当前 `time.time()`，过期视为未命中。
- **惰性淘汰：** 过期记录不主动删除，`get` 时跳过。后台无定时清理任务（V1 不引入后台任务复杂度）。
- **手动清理入口：** 删除 `data/llm_cache/llm_cache.db` 文件即清空全部缓存，重启自动重建。
- **TTL 默认值：** `LLM_CACHE_TTL_SECONDS=86400`（1 天，86400/3600/24=1）。理由：实验报告工作流通常数天内完成，1 天覆盖典型单次工作周期；过长易脏（LLM 模型升级后旧缓存不再适用）。如需更长周期，可配置 `LLM_CACHE_TTL_SECONDS=604800`（7 天）。

### 3.5 并发安全

- SQLite 写入使用 `WAL` 模式（`PRAGMA journal_mode=WAL`），支持并发读 + 单写。
- `set` 操作使用 `INSERT OR REPLACE`，避免并发写入冲突。
- API 进程和 Worker 进程共享同一缓存文件，SQLite WAL 支持多进程并发访问。
- 不引入文件锁，依赖 SQLite 自身的数据库级锁（写入耗时极短，仅一行 content 文本）。

---

## 四、DeepSeekClient 缓存接入

### 4.1 改动范围

`server/app/infrastructure/llm/deepseek_client.py` 的 `DeepSeekClient` 新增可选 `cache` 参数：

```python
class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        timeout_seconds: int = 30,
        max_retries: int = 2,
        cache: "LLMCache | None" = None,  # 新增，默认 None（不缓存）
    ):
        ...
        self._cache = cache
```

### 4.2 chat_completion 改动

```python
def chat_completion(self, messages, response_format=None, temperature=0.3) -> str:
    # 缓存查询
    if self._cache is not None:
        cache_key = LLMCache.compute_key(
            self._model, messages, response_format, temperature
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info(f"LLM 缓存命中, key={cache_key[:12]}...")
            return cached

    # 原有 HTTP 调用逻辑（不变）
    content = self._do_http_call(messages, response_format, temperature)

    # 缓存写入（失败不阻断）
    if self._cache is not None:
        try:
            self._cache.set(cache_key, content)
        except Exception as e:
            logger.warning(f"LLM 缓存写入失败，降级到无缓存: {e}")

    return content
```

**改动原则：**
- `cache=None` 时行为与现有完全一致（零回归风险）
- 缓存查询/写入异常不阻断主流程，降级到无缓存
- 现有重试、错误码、降级逻辑全部不变

### 4.3 create_client_from_settings 扩展

```python
def create_client_from_settings() -> DeepSeekClient:
    from app.core.config import settings

    cache = None
    if settings.llm_cache_enabled:
        cache = LLMCache(
            db_path=settings.llm_cache_db_path,
            ttl_seconds=settings.llm_cache_ttl_seconds,
        )

    return DeepSeekClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.deepseek_timeout_seconds,
        max_retries=settings.deepseek_max_retries,
        cache=cache,  # 新增
    )
```

---

## 五、配置项

### 5.1 新增环境变量

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_CACHE_ENABLED` | `false` | 是否启用缓存（默认关闭，需显式开启） |
| `LLM_CACHE_TTL_SECONDS` | `86400` | 缓存有效期（秒），默认 1 天 |
| `LLM_CACHE_DB_PATH` | `data/llm_cache/llm_cache.db`（相对 server/） | 缓存 SQLite 文件路径 |

### 5.2 配置降级规则

| 输入 | 降级结果 | 日志 |
| --- | --- | --- |
| `LLM_CACHE_ENABLED=true` | 启用 | 无 |
| `LLM_CACHE_ENABLED=false` / `""` / 未设置 | 禁用（默认） | 无 |
| `LLM_CACHE_ENABLED=非 true/false 值` | 禁用 | warning：非法值降级 |
| `LLM_CACHE_TTL_SECONDS=非数字` | 86400 | warning：降级到默认 |
| `LLM_CACHE_TTL_SECONDS<=0` | 禁用缓存（视为关闭） | warning：非正值禁用 |
| `LLM_CACHE_TTL_SECONDS=浮点数` | 截断为整数 | 无 |
| `LLM_CACHE_DB_PATH` 为空 | 默认 `data/llm_cache/llm_cache.db` | 无 |
| 缓存文件目录不存在 | 自动创建目录 | 无 |

### 5.3 .env.example 更新

```ini
# === LLM 调用缓存（SPEC 0014）===
# 是否启用 LLM 调用缓存（默认关闭，启用后相同输入复用 LLM 返回）
LLM_CACHE_ENABLED=false
# 缓存有效期（秒），默认 1 天
LLM_CACHE_TTL_SECONDS=86400
# 缓存 SQLite 文件路径（相对 server/ 目录）
LLM_CACHE_DB_PATH=data/llm_cache/llm_cache.db
```

### 5.4 Docker 环境注入（SPEC 0013 已建立）

按 SPEC 0013，`.env` 文件注入容器环境变量。新增的 3 个变量通过同一机制注入，无需改动 `docker-compose.yml` 结构。缓存文件路径默认指向 `data/llm_cache/`，已被 `project-data` volume 覆盖（`/app/data/projects` 挂载点），但缓存文件在 `/app/data/llm_cache/`，需确认 volume 挂载。

**Docker 配置调整：** `docker-compose.yml` 的 `backend` 和 `worker` 服务新增 volume 挂载 `/app/data/llm_cache`（共享缓存，因为 API 和 Worker 都调用 LLM）。

---

## 六、API 合同

### 6.1 不修改现有 API

V1.2.0 **不修改任何现有 API 路由合同**。缓存对前端透明：
- `DeepSeekClient` 内部自动查缓存
- `candidate_source` 字段值不变（仍是 `DEEPSEEK` 或 `LOCAL_RULE_FALLBACK`）
- 响应结构不变
- 缓存命中时 `source_label` 仍为 `DEEPSEEK`（因为确实是 DeepSeek 生成的，只是复用了上次结果）

### 6.2 不新增运维 API

本轮**不新增** `GET /api/llm/cache/status` 等运维端点。理由：
- 缓存状态可通过日志查
- 新增 API 增加测试面和合同维护成本
- 运维端点推迟到 V2.0（与 LLM 成本统计、调用统计一起规划）

---

## 七、测试策略

### 7.1 单元测试

**文件：** `server/tests/test_llm_cache.py`

| 测试用例 | 覆盖点 |
| --- | --- |
| `test_compute_key_stability` | 相同输入产生相同 key；messages 字段顺序不影响 key |
| `test_compute_key_different_model` | 不同 model 产生不同 key |
| `test_compute_key_different_temperature` | 不同 temperature 产生不同 key |
| `test_get_miss` | 空 cache 返回 None |
| `test_set_then_get` | 写入后读取命中 |
| `test_get_expired` | 过期记录返回 None |
| `test_get_disabled` | enabled=False 时 get 返回 None |
| `test_set_failure_no_raise` | 写入异常不抛错，仅 warning |
| `test_auto_create_table` | 首次访问自动建表 |
| `test_auto_create_dir` | 目录不存在自动创建 |

**文件：** `server/tests/test_deepseek_client.py`（扩展现有）

| 测试用例 | 覆盖点 |
| --- | --- |
| `test_cache_hit_skips_http` | 缓存命中时不发起 HTTP（mock httpx 不被调用） |
| `test_cache_miss_calls_http` | 未命中时调用 HTTP 并写入缓存 |
| `test_cache_disabled_no_query` | cache=None 时不查缓存 |
| `test_cache_write_failure_degrades` | 缓存写入异常不阻断，仍返回 content |
| `test_cache_expired_calls_http` | 过期后重新调用 HTTP |

### 7.2 测试原则

- 不调用真实 DeepSeek API（mock `httpx.Client`）
- 缓存测试使用临时 SQLite 文件（`tmp_path` fixture），不污染业务库
- 测试覆盖降级路径（缓存异常不阻断主流程）
- 0 warnings

### 7.3 验收命令

```text
server/.venv/Scripts/python.exe -m pytest
server/.venv/Scripts/python.exe -m alembic upgrade head
npm.cmd run lint
npm.cmd run build
```

预期：
- pytest: 704 + 新增 ~15 测试 = ~719 passed, 0 warnings
- alembic: 迁移无变化（缓存表不走 Alembic）
- lint: TypeScript 通过
- build: Vite 构建通过

---

## 八、依赖

### 8.1 不新增依赖

- `sqlite3`：Python 标准库，无需安装
- `hashlib`：Python 标准库
- `json`：Python 标准库
- `httpx`：SPEC 0007 已引入

### 8.2 不引入的依赖

| 依赖 | 不引入原因 |
| --- | --- |
| `redis` | V1 本地单用户不需要 |
| `diskcache` | 标准库 sqlite3 已足够 |
| `cachetools` | 不需要内存 LRU |
| `sqlalchemy`（用于缓存）| 缓存表简单，原生 sqlite3 更轻量，避免与业务 SessionLocal 混淆 |

---

## 九、验收标准

| AC # | 验收项 | 通过标准 |
| --- | --- | --- |
| AC-1 | LLMCache 存储层 | 新建 `llm_cache.py`，自动建表、读写、TTL、淘汰逻辑全部实现 |
| AC-2 | 缓存 key 稳定性 | 相同输入产生相同 key，messages 字段顺序不影响 key |
| AC-3 | DeepSeekClient 接入 | `cache=None` 时行为零变化；`cache` 注入后调用前查缓存、调用后写缓存 |
| AC-4 | 缓存命中跳过 HTTP | mock httpx 不被调用，直接返回缓存内容 |
| AC-5 | 缓存未命中调用 HTTP | 调用 HTTP 并写入缓存，下次命中 |
| AC-6 | 过期缓存 | TTL 过期后重新调用 HTTP |
| AC-7 | 禁用缓存 | `LLM_CACHE_ENABLED=false` 时不查不写缓存 |
| AC-8 | 写入失败降级 | 缓存写入异常不阻断，仍返回 content，记录 warning |
| AC-9 | 配置降级 | 非法 TTL/ENABLED 值降级到默认，记录 warning |
| AC-10 | 现有 API 合同不变 | 5 个 provider 的响应结构、source_label 不变 |
| AC-11 | 现有测试无回归 | 原有 704 个测试全部通过 |
| AC-12 | 新增测试通过 | 新增 ~15 个测试全部通过，0 warnings |
| AC-13 | Docker 环境变量注入 | `.env.example` 新增 3 个变量；`docker-compose.yml` 新增 cache volume 挂载 |
| AC-14 | 文档回写 | acceptance.md、dependency-review.md、README.md 更新 |

---

## 十、实施顺序

按 AGENTS.md 阶段闸：

1. **SPEC 0014 文档确认**（本文件，待项目负责人批准）
2. **LLMCache 存储层**（`server/app/infrastructure/llm/llm_cache.py`）
3. **DeepSeekClient 扩展**（注入 cache 参数，调用前查/调用后写）
4. **create_client_from_settings 扩展**（根据配置创建 cache）
5. **config.py 配置项**（新增 3 个环境变量 + 降级规则）
6. **单元测试**（test_llm_cache.py + 扩展 test_deepseek_client.py）
7. **Docker 配置**（`.env.example` + `docker-compose.yml` volume）
8. **验收命令**（pytest + alembic + lint + build）
9. **文档回写**（acceptance.md、dependency-review.md、README.md、decisions/0020）
10. **git 提交推送**

---

## 十一、风险与回退

### 11.1 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| 缓存返回脏数据（模型升级后旧输出不适用） | 中 | 候选质量下降 | TTL 默认 1 天；可手动删缓存文件重建 |
| 缓存文件损坏 | 低 | 缓存丢失 | SQLite WAL 模式；损坏时删除文件自动重建 |
| 缓存写入失败导致主流程中断 | 极低 | LLM 调用失败 | `set` 异常不抛错，降级到无缓存 |
| 并发写入冲突 | 低 | 个别写入失败 | SQLite WAL + INSERT OR REPLACE |
| 跨进程访问锁竞争 | 低 | 性能下降 | WAL 模式支持并发读；写入极短 |

### 11.2 回退方案

如缓存引入问题，可通过以下方式回退，**无需改代码**：

1. 设置 `LLM_CACHE_ENABLED=false`，立即禁用缓存（`cache=None`，行为回到 SPEC 0007 状态）
2. 删除 `data/llm_cache/llm_cache.db` 文件，清空全部缓存
3. 如需彻底移除，删除 `llm_cache.py` 和 `DeepSeekClient` 的 cache 参数（`cache=None` 默认值保证现有调用不受影响）

### 11.3 最大回归风险

**最大风险：** 缓存返回过期内容导致用户看到旧候选。

**阻断证据：**
- TTL 机制确保过期缓存不被返回（`test_get_expired`）
- 缓存 key 含 model 字段，模型切换后 key 不同（`test_compute_key_different_model`）
- temperature 进入 key，不同采样温度不复用缓存
- `LLM_CACHE_ENABLED` 默认 `false`，不主动启用需显式配置

---

## 十二、确认事项（待项目负责人确认）

> 本章节的技术决策需项目负责人确认后方可进入实现。

### 12.1 缓存存储：独立 SQLite 文件（不走 Alembic）

**决策：** 缓存表使用独立 SQLite 文件 `data/llm_cache/llm_cache.db`，不走 Alembic 迁移。

**理由：** 见 §2.3。缓存是性能优化非业务真相，独立存储保持 owner 边界清晰。

### 12.2 缓存默认关闭

**决策：** `LLM_CACHE_ENABLED` 默认 `false`，需显式启用。

**理由：** 缓存可能返回旧内容，默认关闭保证现有行为零变化；用户明确需要时再开启。

### 12.3 TTL 默认 1 天

**决策：** `LLM_CACHE_TTL_SECONDS` 默认 `86400`（1 天）。

**理由：** 平衡缓存命中率和数据新鲜度。如需更长，用户可配置。

### 12.4 不新增运维 API

**决策：** 本轮不新增 `GET /api/llm/cache/status` 等运维端点。

**理由：** 减少合同面，运维端点推迟到 V2.0 与 LLM 成本统计一起规划。

---

## 十三、与 V1.2.0 整体规划的关系

本切片是 V1.2.0 的第二个 SPEC（SPEC 0013 Docker 化已收口）。按 AGENTS.md "多 SPEC 版本规划时需保证各 SPEC 关注点正交、风险隔离、独立验收"：

| SPEC | 关注点 | owner 层 | 风险隔离 |
| --- | --- | --- | --- |
| SPEC 0013 | Docker 化部署 | 基础设施（Dockerfile/compose） | 不触碰业务代码 |
| SPEC 0014 | LLM 调用缓存 | 基础设施（llm_cache.py） + LLM 模块（deepseek_client） | 不触碰业务数据库，不修改 API 合同 |

两切片正交，可独立验收。SPEC 0014 依赖 SPEC 0013 的 Docker 环境变量注入机制（`.env`），但不依赖 Docker 化本身（本地开发也可用缓存）。
