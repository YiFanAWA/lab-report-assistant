"""LLMCache 单元测试（SPEC 0014）。

测试覆盖：
- 缓存 key 生成逻辑（稳定性、不同输入产生不同 key、SHA256 格式）
- 读写命中/未命中
- TTL 过期判断
- 写入失败降级（不抛异常）
- 自动建表与目录创建
- 独立 SQLite 文件不污染业务库
"""

import os
import time

import pytest

from app.infrastructure.llm.llm_cache import LLMCache


# ========== 缓存 key 生成逻辑测试 ==========


class TestComputeKey:
    """验证缓存 key 生成逻辑是否正确。"""

    def test_相同输入产生相同key(self):
        """稳定性：相同输入应产生相同的 key。"""
        messages = [{"role": "user", "content": "分析胃病数据"}]
        key1 = LLMCache.compute_key(
            "deepseek-v4-pro", messages, {"type": "json_object"}, 0.3
        )
        key2 = LLMCache.compute_key(
            "deepseek-v4-pro", messages, {"type": "json_object"}, 0.3
        )
        assert key1 == key2

    def test_messages字段顺序不影响key(self):
        """sort_keys 保证 messages 内部字段顺序不影响 key。

        场景：messages 中的 dict 字段顺序不同，但语义相同，
        应命中同一缓存。
        """
        messages_a = [
            {"role": "system", "content": "你是助手"},
            {"role": "user", "content": "生成大纲"},
        ]
        messages_b = [
            {"content": "你是助手", "role": "system"},
            {"content": "生成大纲", "role": "user"},
        ]
        key_a = LLMCache.compute_key(
            "deepseek-v4-pro", messages_a, None, 0.3
        )
        key_b = LLMCache.compute_key(
            "deepseek-v4-pro", messages_b, None, 0.3
        )
        assert key_a == key_b

    def test_不同model产生不同key(self):
        """不同模型名应产生不同 key（天然隔离不同模型缓存）。"""
        messages = [{"role": "user", "content": "hi"}]
        key_pro = LLMCache.compute_key(
            "deepseek-v4-pro", messages, None, 0.3
        )
        key_flash = LLMCache.compute_key(
            "deepseek-v4-flash", messages, None, 0.3
        )
        assert key_pro != key_flash

    def test_不同temperature产生不同key(self):
        """不同采样温度应产生不同 key（不同温度输出不同，不复用缓存）。"""
        messages = [{"role": "user", "content": "hi"}]
        key_03 = LLMCache.compute_key("deepseek-v4-pro", messages, None, 0.3)
        key_07 = LLMCache.compute_key("deepseek-v4-pro", messages, None, 0.7)
        assert key_03 != key_07

    def test_不同response_format产生不同key(self):
        """不同 response_format 应产生不同 key。"""
        messages = [{"role": "user", "content": "hi"}]
        key_json = LLMCache.compute_key(
            "deepseek-v4-pro", messages, {"type": "json_object"}, 0.3
        )
        key_none = LLMCache.compute_key("deepseek-v4-pro", messages, None, 0.3)
        assert key_json != key_none

    def test_不同messages内容产生不同key(self):
        """不同 messages 内容应产生不同 key。"""
        key_a = LLMCache.compute_key(
            "deepseek-v4-pro", [{"role": "user", "content": "分析数据A"}], None, 0.3
        )
        key_b = LLMCache.compute_key(
            "deepseek-v4-pro", [{"role": "user", "content": "分析数据B"}], None, 0.3
        )
        assert key_a != key_b

    def test_key是64位十六进制SHA256(self):
        """key 应为 64 位十六进制字符串（SHA256 摘要标准格式）。"""
        key = LLMCache.compute_key(
            "deepseek-v4-pro", [{"role": "user", "content": "test"}], None, 0.3
        )
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_中文content不影响key稳定性(self):
        """ensure_ascii=False 保留中文，相同中文内容产生相同 key。"""
        messages = [{"role": "user", "content": "胃病数据分析实验报告"}]
        key1 = LLMCache.compute_key("deepseek-v4-pro", messages, None, 0.3)
        key2 = LLMCache.compute_key("deepseek-v4-pro", messages, None, 0.3)
        assert key1 == key2


# ========== 读写与命中测试 ==========


class TestCacheReadWrite:
    """缓存读写命中场景。"""

    def test_空缓存get返回None(self, tmp_path):
        """未写入的 key 应返回 None。"""
        cache = LLMCache(str(tmp_path / "test_cache.db"))
        result = cache.get("non_existent_key")
        assert result is None

    def test_写入后读取命中(self, tmp_path):
        """set 后 get 应返回缓存内容。"""
        cache = LLMCache(str(tmp_path / "test_cache.db"))
        cache.set("key_001", "LLM 返回内容", model="deepseek-v4-pro")
        result = cache.get("key_001")
        assert result == "LLM 返回内容"

    def test_相同key覆盖旧内容(self, tmp_path):
        """INSERT OR REPLACE：相同 key 再次写入应覆盖旧内容。"""
        cache = LLMCache(str(tmp_path / "test_cache.db"))
        cache.set("key_001", "旧内容", model="deepseek-v4-pro")
        cache.set("key_001", "新内容", model="deepseek-v4-pro")
        assert cache.get("key_001") == "新内容"

    def test_多个key互不干扰(self, tmp_path):
        """不同 key 的缓存互不干扰。"""
        cache = LLMCache(str(tmp_path / "test_cache.db"))
        cache.set("key_a", "内容A", model="m1")
        cache.set("key_b", "内容B", model="m2")
        assert cache.get("key_a") == "内容A"
        assert cache.get("key_b") == "内容B"


# ========== TTL 过期测试 ==========


class TestCacheTTL:
    """TTL 过期判断。"""

    def test_过期记录返回None(self, tmp_path):
        """超过 TTL 的记录应视为未命中。"""
        db_path = str(tmp_path / "test_cache.db")
        # TTL=0：写入后立即过期
        cache = LLMCache(db_path, ttl_seconds=0)
        cache.set("key_expired", "内容", model="m1")
        # TTL=0 时 expires_at = now + 0，下次 get 时 now > expires_at
        assert cache.get("key_expired") is None

    def test_未过期记录正常返回(self, tmp_path):
        """TTL 内的记录应正常返回。"""
        cache = LLMCache(str(tmp_path / "test_cache.db"), ttl_seconds=3600)
        cache.set("key_fresh", "内容", model="m1")
        assert cache.get("key_fresh") == "内容"


# ========== 异常与降级测试 ==========


class TestCacheDegradation:
    """异常降级场景（不阻断主流程）。"""

    def test_查询异常返回None不抛错(self, tmp_path, monkeypatch):
        """get 异常应返回 None，不抛错。"""
        cache = LLMCache(str(tmp_path / "test_cache.db"))

        # 模拟连接失败
        def _raise(*args, **kwargs):
            raise RuntimeError("模拟数据库不可用")

        monkeypatch.setattr(cache, "_connect", _raise)
        # get 不应抛异常
        result = cache.get("any_key")
        assert result is None

    def test_写入异常不抛错(self, tmp_path, monkeypatch):
        """set 异常应不抛错，仅记录 warning。"""
        cache = LLMCache(str(tmp_path / "test_cache.db"))

        def _raise(*args, **kwargs):
            raise RuntimeError("模拟写入失败")

        monkeypatch.setattr(cache, "_connect", _raise)
        # set 不应抛异常
        cache.set("key_001", "内容", model="m1")


# ========== 自动建表与目录创建测试 ==========


class TestCacheInit:
    """初始化与建表。"""

    def test_首次访问自动建表(self, tmp_path):
        """首次访问应自动创建缓存表。"""
        db_path = str(tmp_path / "test_cache.db")
        # 文件不存在时初始化应成功
        cache = LLMCache(db_path)
        # 写入后能读取，说明表已创建
        cache.set("key_001", "内容", model="m1")
        assert cache.get("key_001") == "内容"

    def test_目录不存在自动创建(self, tmp_path):
        """缓存文件目录不存在时应自动创建。"""
        nested_path = str(tmp_path / "nested" / "deeper" / "cache.db")
        cache = LLMCache(nested_path)
        cache.set("key_001", "内容", model="m1")
        assert cache.get("key_001") == "内容"
        assert os.path.exists(nested_path)

    def test_重复初始化不报错(self, tmp_path):
        """对已存在的缓存文件重复初始化应幂等。"""
        db_path = str(tmp_path / "test_cache.db")
        cache1 = LLMCache(db_path)
        cache1.set("key_001", "内容", model="m1")
        # 再次初始化（表已存在）
        cache2 = LLMCache(db_path)
        assert cache2.get("key_001") == "内容"


# ========== 独立存储验证 ==========


class TestCacheIsolation:
    """验证缓存表独立于业务数据库。"""

    def test_缓存表不依赖alembic迁移(self, tmp_path):
        """缓存表通过 CREATE TABLE IF NOT EXISTS 自动建表，
        不依赖 Alembic 迁移（SPEC 0014 §2.3 决策）。"""
        db_path = str(tmp_path / "test_cache.db")
        cache = LLMCache(db_path)
        cache.set("key_001", "内容", model="m1")
        # 直接查询表是否存在
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        table_names = [t[0] for t in tables]
        assert "llm_call_cache" in table_names
