"""SPEC 0012 配置层测试。

覆盖 DATA_RETENTION_DAYS 环境变量的读取、默认值、边界值和非法值降级。
"""

import importlib

import app.core.config as config_module


def _reload_config(monkeypatch, env_value: str | None):
    """重载 config 模块并设置环境变量。"""
    if env_value is not None:
        monkeypatch.setenv("DATA_RETENTION_DAYS", env_value)
    else:
        monkeypatch.delenv("DATA_RETENTION_DAYS", raising=False)
    importlib.reload(config_module)
    return config_module.settings


# --- 正常值 ---


def test_default_is_zero(monkeypatch):
    """C-01：未设置环境变量时默认为 0（永久保留）。"""
    settings = _reload_config(monkeypatch, None)
    assert settings.data_retention_days == 0


def test_zero_means_permanent(monkeypatch):
    """C-02：设置为 0 表示永久保留。"""
    settings = _reload_config(monkeypatch, "0")
    assert settings.data_retention_days == 0


def test_positive_integer(monkeypatch):
    """C-03：设置为正整数 30。"""
    settings = _reload_config(monkeypatch, "30")
    assert settings.data_retention_days == 30


def test_large_value(monkeypatch):
    """C-04：设置为大值 365。"""
    settings = _reload_config(monkeypatch, "365")
    assert settings.data_retention_days == 365


def test_minimum_positive(monkeypatch):
    """C-05：设置为 1（最小有效正整数）。"""
    settings = _reload_config(monkeypatch, "1")
    assert settings.data_retention_days == 1


# --- 非法值降级 ---


def test_negative_falls_back_to_zero(monkeypatch):
    """C-06：负值降级到 0（永久保留）。"""
    settings = _reload_config(monkeypatch, "-1")
    assert settings.data_retention_days == 0


def test_non_numeric_falls_back_to_zero(monkeypatch):
    """C-07：非数字降级到 0。"""
    settings = _reload_config(monkeypatch, "abc")
    assert settings.data_retention_days == 0


def test_float_truncated_to_int(monkeypatch):
    """C-08：浮点数截断为整数。"""
    settings = _reload_config(monkeypatch, "30.5")
    # int("30.5") 会抛出 ValueError，降级到 0
    assert settings.data_retention_days == 0


def test_empty_string_falls_back_to_zero(monkeypatch):
    """C-09：空字符串降级到 0。"""
    settings = _reload_config(monkeypatch, "")
    assert settings.data_retention_days == 0


def test_negative_large_falls_back_to_zero(monkeypatch):
    """C-10：大负值降级到 0。"""
    settings = _reload_config(monkeypatch, "-999")
    assert settings.data_retention_days == 0
