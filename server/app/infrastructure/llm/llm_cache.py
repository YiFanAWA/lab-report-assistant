"""LLM 调用缓存存储层。

职责：缓存 key 计算、SQLite 读写、TTL 过期判断、自动建表。
不负责 HTTP 调用和错误映射（由 DeepSeekClient 负责）。

设计决策（SPEC 0014）：
- 使用独立 SQLite 文件，不走 Alembic 迁移。
- 缓存表丢失可重建（重新调用 LLM 即可），与业务表的不可丢失性质不同。
- 不复用业务 SessionLocal，避免连接池混淆。
- SQLite WAL 模式支持 API 进程和 Worker 进程并发访问。
- set 操作失败不抛异常（降级到无缓存，不阻断主流程）。
"""

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path


logger = logging.getLogger(__name__)


class LLMCache:
    """LLM 调用缓存存储层。

    使用独立 SQLite 文件存储 LLM 调用结果，避免相同输入重复调用 API。
    缓存对 provider 和 API 路由透明，仅由 DeepSeekClient 接入。

    线程安全：每次操作创建独立连接（短连接模式），依赖 SQLite 自身的数据库级锁。
    WAL 模式支持多进程并发读 + 单写。
    """

    def __init__(self, db_path: str, ttl_seconds: int = 86400):
        """初始化缓存。

        参数：
        - db_path: 缓存 SQLite 文件路径（相对路径基于 server/ 目录）
        - ttl_seconds: 缓存有效期（秒），默认 86400（1 天）

        首次访问时自动创建目录和表。
        """
        self._db_path = str(db_path)
        self._ttl_seconds = int(ttl_seconds)
        self._ensure_dir()
        self._ensure_table()

    def get(self, cache_key: str) -> str | None:
        """查询缓存。

        返回 content 或 None（未命中/已过期/异常）。
        过期记录视为未命中（惰性淘汰，不主动删除）。
        查询异常不抛错，返回 None 降级到无缓存。
        """
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT content, expires_at FROM llm_call_cache WHERE cache_key = ?",
                    (cache_key,),
                ).fetchone()
            if row is None:
                return None
            content, expires_at = row
            if time.time() > expires_at:
                # 已过期，视为未命中
                return None
            return content
        except Exception as e:
            logger.warning(f"LLM 缓存查询失败，降级到无缓存: {e}")
            return None

    def set(self, cache_key: str, content: str, model: str = "") -> None:
        """写入缓存。

        使用 INSERT OR REPLACE 避免并发写入冲突。
        写入失败不抛异常，仅记录 warning（不阻断主流程）。
        """
        now = time.time()
        expires_at = now + self._ttl_seconds
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO llm_call_cache
                        (cache_key, content, model, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (cache_key, content, model, now, expires_at),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"LLM 缓存写入失败，降级到无缓存: {e}")

    @staticmethod
    def compute_key(
        model: str,
        messages: list[dict],
        response_format: dict | None,
        temperature: float,
    ) -> str:
        """计算缓存 key。

        key = SHA256(规范化 JSON)。

        规范化保证：
        - sort_keys=True：messages 字段顺序不影响 key
        - ensure_ascii=False：保留中文，避免编码差异
        - default=str：兜底非 JSON 类型

        不同 model / temperature / response_format 产生不同 key，
        天然隔离不同配置的缓存。
        """
        payload = {
            "model": model,
            "messages": messages,
            "response_format": response_format,
            "temperature": temperature,
        }
        canonical = json.dumps(
            payload, sort_keys=True, ensure_ascii=False, default=str
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _connect(self) -> sqlite3.Connection:
        """创建 SQLite 连接。

        每次操作创建新连接（短连接模式），避免跨线程/跨进程连接复用问题。
        开启 WAL 模式支持并发读。
        """
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_dir(self) -> None:
        """确保缓存文件所在目录存在。"""
        db_path = Path(self._db_path)
        parent = db_path.parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)

    def _ensure_table(self) -> None:
        """自动建表（IF NOT EXISTS）。

        缓存表结构：
        - cache_key: SHA256 摘要（主键）
        - content: LLM 返回的 content 字符串
        - model: 模型名（便于排查）
        - created_at: 写入时间戳
        - expires_at: 过期时间戳
        """
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_call_cache (
                    cache_key TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    model TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_llm_cache_expires_at "
                "ON llm_call_cache(expires_at)"
            )
            conn.commit()
