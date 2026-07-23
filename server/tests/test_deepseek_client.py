"""DeepSeekClient 单元测试。

mock httpx.Client 测试：
- 成功响应（提取 content）
- 超时（重试 + 最终失败）
- 连接错误（重试 + 最终失败）
- 401 鉴权失败（不重试）
- 429 限流（不重试）
- 5xx 服务端错误（重试 + 最终失败）
- JSON 解析失败
- 响应格式异常（choices 为空 / content 为空 / 字段缺失）
"""

import json
from unittest.mock import patch, MagicMock

import httpx
import pytest

from app.infrastructure.llm.deepseek_client import DeepSeekClient, DeepSeekError


def _make_response(status_code: int, body: dict | str | None = None) -> httpx.Response:
    """构造 httpx.Response mock。"""
    if body is None:
        content = b""
    elif isinstance(body, str):
        content = body.encode("utf-8")
    else:
        content = json.dumps(body).encode("utf-8")
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers={"content-type": "application/json"},
    )


def _make_chat_response(content: str = "test response") -> httpx.Response:
    """构造标准 chat/completions 200 响应。"""
    return _make_response(200, {
        "choices": [
            {"message": {"role": "assistant", "content": content}}
        ]
    })


class TestDeepSeekClientSuccess:
    """成功响应场景。"""

    def test_成功提取_content(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=0)
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = _make_chat_response("hello world")
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client.chat_completion(
                messages=[{"role": "user", "content": "hi"}]
            )

            assert result == "hello world"
            mock_http.post.assert_called_once()

    def test_带response_format调用(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=0)
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = _make_chat_response('{"key": "value"}')
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client.chat_completion(
                messages=[{"role": "user", "content": "hi"}],
                response_format={"type": "json_object"},
                temperature=0.7,
            )

            _, kwargs = mock_http.post.call_args
            assert kwargs["json"]["response_format"] == {"type": "json_object"}
            assert kwargs["json"]["temperature"] == 0.7


class TestDeepSeekClientErrors:
    """错误场景。"""

    def test_超时触发重试并最终失败(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=2, timeout_seconds=5)
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.post.side_effect = httpx.TimeoutException("timeout")
            mock_client_cls.return_value.__enter__.return_value = mock_http

            with pytest.raises(DeepSeekError) as exc_info:
                client.chat_completion(messages=[{"role": "user", "content": "hi"}])

            assert exc_info.value.code == "DEEPSEEK_TIMEOUT"
            # 重试 3 次（初始 + 2 次重试）
            assert mock_http.post.call_count == 3

    def test_连接错误触发重试(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=1, timeout_seconds=5)
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.post.side_effect = httpx.ConnectError("connection refused")
            mock_client_cls.return_value.__enter__.return_value = mock_http

            with pytest.raises(DeepSeekError) as exc_info:
                client.chat_completion(messages=[{"role": "user", "content": "hi"}])

            assert exc_info.value.code == "DEEPSEEK_CONNECTION_ERROR"
            assert mock_http.post.call_count == 2  # 初始 + 1 次重试

    def test_401鉴权失败不重试(self):
        client = DeepSeekClient(api_key="sk-invalid", max_retries=3)
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = _make_response(401, {"error": "invalid key"})
            mock_client_cls.return_value.__enter__.return_value = mock_http

            with pytest.raises(DeepSeekError) as exc_info:
                client.chat_completion(messages=[{"role": "user", "content": "hi"}])

            assert exc_info.value.code == "DEEPSEEK_AUTH_ERROR"
            # 401 不重试
            mock_http.post.assert_called_once()

    def test_429限流不重试(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=3)
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = _make_response(429, {"error": "rate limited"})
            mock_client_cls.return_value.__enter__.return_value = mock_http

            with pytest.raises(DeepSeekError) as exc_info:
                client.chat_completion(messages=[{"role": "user", "content": "hi"}])

            assert exc_info.value.code == "DEEPSEEK_RATE_LIMITED"
            mock_http.post.assert_called_once()

    def test_5xx服务端错误触发重试(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=2)
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = _make_response(500, {"error": "server error"})
            mock_client_cls.return_value.__enter__.return_value = mock_http

            with pytest.raises(DeepSeekError) as exc_info:
                client.chat_completion(messages=[{"role": "user", "content": "hi"}])

            assert exc_info.value.code == "DEEPSEEK_SERVER_ERROR"
            assert mock_http.post.call_count == 3  # 初始 + 2 次重试

    def test_400客户端错误不重试(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=3)
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = _make_response(400, {"error": "bad request"})
            mock_client_cls.return_value.__enter__.return_value = mock_http

            with pytest.raises(DeepSeekError) as exc_info:
                client.chat_completion(messages=[{"role": "user", "content": "hi"}])

            assert exc_info.value.code == "DEEPSEEK_CLIENT_ERROR"
            mock_http.post.assert_called_once()


class TestDeepSeekClientResponseParsing:
    """响应解析场景。"""

    def test_JSON解析失败(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=0)
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            # 返回非 JSON 内容
            mock_http.post.return_value = _make_response(200, "not json {{{")
            mock_client_cls.return_value.__enter__.return_value = mock_http

            with pytest.raises(DeepSeekError) as exc_info:
                client.chat_completion(messages=[{"role": "user", "content": "hi"}])

            assert exc_info.value.code == "DEEPSEEK_JSON_PARSE_ERROR"

    def test_choices为空(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=0)
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = _make_response(200, {"choices": []})
            mock_client_cls.return_value.__enter__.return_value = mock_http

            with pytest.raises(DeepSeekError) as exc_info:
                client.chat_completion(messages=[{"role": "user", "content": "hi"}])

            assert exc_info.value.code == "DEEPSEEK_EMPTY_CHOICES"

    def test_content为空(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=0)
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = _make_response(200, {
                "choices": [{"message": {"content": ""}}]
            })
            mock_client_cls.return_value.__enter__.return_value = mock_http

            with pytest.raises(DeepSeekError) as exc_info:
                client.chat_completion(messages=[{"role": "user", "content": "hi"}])

            assert exc_info.value.code == "DEEPSEEK_EMPTY_CONTENT"

    def test_响应格式异常_字段缺失(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=0)
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            # 缺少 message 字段
            mock_http.post.return_value = _make_response(200, {
                "choices": [{"no_message": True}]
            })
            mock_client_cls.return_value.__enter__.return_value = mock_http

            with pytest.raises(DeepSeekError) as exc_info:
                client.chat_completion(messages=[{"role": "user", "content": "hi"}])

            assert exc_info.value.code == "DEEPSEEK_RESPONSE_FORMAT_ERROR"


class TestDeepSeekClientInit:
    """初始化校验。"""

    def test_缺少APIKey抛出错误(self):
        with pytest.raises(DeepSeekError) as exc_info:
            DeepSeekClient(api_key="")

        assert exc_info.value.code == "DEEPSEEK_API_KEY_MISSING"

    def test_base_url去除尾部斜杠(self):
        client = DeepSeekClient(
            api_key="sk-test",
            base_url="https://api.deepseek.com/"
        )
        assert client._base_url == "https://api.deepseek.com"
