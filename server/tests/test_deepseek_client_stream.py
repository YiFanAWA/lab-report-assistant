"""DeepSeekClient.stream_chat_completion 流式调用单元测试。

mock httpx.Client 测试：
- 流式成功（多 chunk yield）
- 缓存命中（一次性 yield 完整字符串）
- 缓存写入（完成后 cache.set 被调用）
- 首 chunk 前失败（401 / 429 / 5xx / 超时 / 连接错误）
- 中途失败（已 yield 一个 chunk 后抛异常）
- [DONE] 标记处理
- chunk 解析失败跳过

测试原则：
- 不调用真实 DeepSeek API
- mock httpx.Client 的 stream() 方法
"""

import json
from unittest.mock import patch, MagicMock

import httpx
import pytest

from app.infrastructure.llm.deepseek_client import DeepSeekClient, DeepSeekError
from app.infrastructure.llm.llm_cache import LLMCache


def _make_stream_response(
    status_code: int = 200,
    lines: list[str] | None = None,
    iter_lines_generator=None,
) -> MagicMock:
    """构造 mock httpx 流式响应。

    参数：
    - status_code: HTTP 状态码
    - lines: iter_lines() 返回的行列表（普通场景）
    - iter_lines_generator: 生成器对象，作为 iter_lines() 的返回值（用于中途失败场景）

    注意：使用 return_value 而非 side_effect，因为 side_effect 设为生成器时
    MagicMock 会迭代返回每个值，而非返回生成器本身。
    """
    resp = MagicMock()
    resp.status_code = status_code
    if iter_lines_generator is not None:
        resp.iter_lines.return_value = iter_lines_generator
    else:
        resp.iter_lines.return_value = lines or []
    return resp


def _patch_httpx_client_stream(resp: MagicMock):
    """patch httpx.Client，使 stream() 返回给定的 mock 响应。

    注意：MagicMock 的 __exit__ 默认返回 truthy 值会抑制异常，
    必须显式设为 False 以保证异常正确传播。
    """
    mock_client = MagicMock()
    mock_client.stream.return_value.__enter__.return_value = resp
    mock_client.stream.return_value.__exit__.return_value = False  # 不抑制异常
    mock_client_cls = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client_cls.return_value.__exit__.return_value = False  # 不抑制异常
    return mock_client_cls


def _make_sse_lines(chunks: list[str]) -> list[str]:
    """将 content chunk 列表转为 DeepSeek SSE 行格式。"""
    lines = []
    for c in chunks:
        data = json.dumps({"choices": [{"delta": {"content": c}}]})
        lines.append(f"data: {data}")
    lines.append("data: [DONE]")
    return lines


class TestStreamChatCompletionSuccess:
    """流式成功场景。"""

    def test_多chunk按序yield(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=0)
        chunks = ["实验", "目的", "：分析"]
        resp = _make_stream_response(200, _make_sse_lines(chunks))
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            result = list(client.stream_chat_completion(
                messages=[{"role": "user", "content": "hi"}]
            ))

        assert result == chunks

    def test_空delta跳过(self):
        """LLM 返回 delta.content 为空字符串的 chunk，应跳过不 yield。"""
        client = DeepSeekClient(api_key="sk-test", max_retries=0)
        lines = [
            f"data: {json.dumps({'choices': [{'delta': {'content': ''}}]})}",
            f"data: {json.dumps({'choices': [{'delta': {'content': '有效'}}]})}",
            "data: [DONE]",
        ]
        resp = _make_stream_response(200, lines)
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            result = list(client.stream_chat_completion(
                messages=[{"role": "user", "content": "hi"}]
            ))

        assert result == ["有效"]

    def test_DONE标记后停止(self):
        """遇到 data: [DONE] 应停止读取后续行。"""
        client = DeepSeekClient(api_key="sk-test", max_retries=0)
        lines = [
            f"data: {json.dumps({'choices': [{'delta': {'content': '前'}}]})}",
            "data: [DONE]",
            f"data: {json.dumps({'choices': [{'delta': {'content': '后'}}]})}",
        ]
        resp = _make_stream_response(200, lines)
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            result = list(client.stream_chat_completion(
                messages=[{"role": "user", "content": "hi"}]
            ))

        assert result == ["前"]

    def test_非data行跳过(self):
        """SSE 注释行或空行应跳过。"""
        client = DeepSeekClient(api_key="sk-test", max_retries=0)
        lines = [
            ": comment line",
            "",
            f"data: {json.dumps({'choices': [{'delta': {'content': '有效'}}]})}",
            "data: [DONE]",
        ]
        resp = _make_stream_response(200, lines)
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            result = list(client.stream_chat_completion(
                messages=[{"role": "user", "content": "hi"}]
            ))

        assert result == ["有效"]

    def test_chunkJSON解析失败跳过(self):
        """单个 chunk JSON 解析失败应跳过，不中断流。"""
        client = DeepSeekClient(api_key="sk-test", max_retries=0)
        lines = [
            "data: {invalid json",
            f"data: {json.dumps({'choices': [{'delta': {'content': '有效'}}]})}",
            "data: [DONE]",
        ]
        resp = _make_stream_response(200, lines)
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            result = list(client.stream_chat_completion(
                messages=[{"role": "user", "content": "hi"}]
            ))

        # 无效 chunk 跳过，有效 chunk 仍 yield
        assert result == ["有效"]

    def test_带response_format调用(self):
        """验证 stream=True 和 response_format 透传到 payload。"""
        client = DeepSeekClient(api_key="sk-test", max_retries=0)
        resp = _make_stream_response(200, _make_sse_lines(["x"]))
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            list(client.stream_chat_completion(
                messages=[{"role": "user", "content": "hi"}],
                response_format={"type": "json_object"},
                temperature=0.7,
            ))

        # 验证 stream() 调用参数
        mock_client = mock_cls.return_value.__enter__.return_value
        _, kwargs = mock_client.stream.call_args
        assert kwargs["json"]["stream"] is True
        assert kwargs["json"]["response_format"] == {"type": "json_object"}
        assert kwargs["json"]["temperature"] == 0.7


class TestStreamChatCompletionCache:
    """流式缓存场景。"""

    def test_cache为None时不查缓存(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=0, cache=None)
        resp = _make_stream_response(200, _make_sse_lines(["hello"]))
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            result = list(client.stream_chat_completion(
                messages=[{"role": "user", "content": "hi"}]
            ))

        assert result == ["hello"]

    def test_缓存命中一次性yield(self, tmp_path):
        """缓存命中时不发起 HTTP，一次性 yield 完整字符串。"""
        cache = LLMCache(str(tmp_path / "cache.db"))
        messages = [{"role": "user", "content": "hi"}]
        cache_key = LLMCache.compute_key("deepseek-chat", messages, None, 0.3)
        cache.set(cache_key, "完整缓存内容", model="deepseek-chat")

        client = DeepSeekClient(
            api_key="sk-test", max_retries=0, cache=cache, model="deepseek-chat"
        )
        resp = _make_stream_response(200, _make_sse_lines(["不应被调用"]))
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            result = list(client.stream_chat_completion(
                messages=messages, temperature=0.3
            ))

        # 缓存命中时一次性 yield
        assert result == ["完整缓存内容"]
        # HTTP 不应被调用
        mock_client = mock_cls.return_value.__enter__.return_value
        mock_client.stream.assert_not_called()

    def test_缓存未命中调用HTTP并写入(self, tmp_path):
        """未命中时调用 HTTP，成功后写入缓存。"""
        cache = LLMCache(str(tmp_path / "cache.db"))
        client = DeepSeekClient(
            api_key="sk-test", max_retries=0, cache=cache, model="deepseek-chat"
        )
        messages = [{"role": "user", "content": "hi"}]
        resp = _make_stream_response(200, _make_sse_lines(["fresh", "response"]))
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            result = list(client.stream_chat_completion(
                messages=messages, temperature=0.3
            ))

        assert result == ["fresh", "response"]

        # 验证缓存已写入（拼接后的完整字符串）
        cache_key = LLMCache.compute_key("deepseek-chat", messages, None, 0.3)
        assert cache.get(cache_key) == "freshresponse"

    def test_缓存写入失败不阻断(self, tmp_path, monkeypatch):
        """缓存 set 抛异常时不应阻断主流程。"""
        cache = LLMCache(str(tmp_path / "cache.db"))

        def _raise_set(*args, **kwargs):
            raise RuntimeError("模拟写入失败")

        monkeypatch.setattr(cache, "set", _raise_set)

        client = DeepSeekClient(api_key="sk-test", max_retries=0, cache=cache)
        resp = _make_stream_response(200, _make_sse_lines(["content"]))
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            result = list(client.stream_chat_completion(
                messages=[{"role": "user", "content": "hi"}]
            ))

        # 仍正常返回 chunk
        assert result == ["content"]


class TestStreamChatCompletionErrors:
    """首 chunk 前失败场景（HTTP 错误、网络错误）。"""

    def test_401鉴权失败抛DeepSeekError(self):
        client = DeepSeekClient(api_key="sk-invalid", max_retries=0)
        resp = _make_stream_response(401)
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            with pytest.raises(DeepSeekError) as exc_info:
                list(client.stream_chat_completion(
                    messages=[{"role": "user", "content": "hi"}]
                ))

        assert exc_info.value.code == "DEEPSEEK_AUTH_ERROR"

    def test_429限流抛DeepSeekError(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=0)
        resp = _make_stream_response(429)
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            with pytest.raises(DeepSeekError) as exc_info:
                list(client.stream_chat_completion(
                    messages=[{"role": "user", "content": "hi"}]
                ))

        assert exc_info.value.code == "DEEPSEEK_RATE_LIMITED"

    def test_5xx服务端错误抛DeepSeekError(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=0)
        resp = _make_stream_response(500)
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            with pytest.raises(DeepSeekError) as exc_info:
                list(client.stream_chat_completion(
                    messages=[{"role": "user", "content": "hi"}]
                ))

        assert exc_info.value.code == "DEEPSEEK_SERVER_ERROR"

    def test_400客户端错误抛DeepSeekError(self):
        client = DeepSeekClient(api_key="sk-test", max_retries=0)
        resp = _make_stream_response(400)
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            with pytest.raises(DeepSeekError) as exc_info:
                list(client.stream_chat_completion(
                    messages=[{"role": "user", "content": "hi"}]
                ))

        assert exc_info.value.code == "DEEPSEEK_CLIENT_ERROR"

    def test_超时抛DeepSeekError(self):
        """httpx.TimeoutException 应映射为 DEEPSEEK_TIMEOUT。"""
        client = DeepSeekClient(api_key="sk-test", max_retries=0)

        # 构造 stream() 抛 TimeoutException 的 mock
        mock_client = MagicMock()
        mock_client.stream.side_effect = httpx.TimeoutException("timeout")
        mock_cls = MagicMock()
        mock_cls.return_value.__enter__.return_value = mock_client

        with patch("httpx.Client", mock_cls):
            with pytest.raises(DeepSeekError) as exc_info:
                list(client.stream_chat_completion(
                    messages=[{"role": "user", "content": "hi"}]
                ))

        assert exc_info.value.code == "DEEPSEEK_TIMEOUT"

    def test_连接错误抛DeepSeekError(self):
        """httpx.ConnectError 应映射为 DEEPSEEK_CONNECTION_ERROR。"""
        client = DeepSeekClient(api_key="sk-test", max_retries=0)

        mock_client = MagicMock()
        mock_client.stream.side_effect = httpx.ConnectError("refused")
        mock_cls = MagicMock()
        mock_cls.return_value.__enter__.return_value = mock_client

        with patch("httpx.Client", mock_cls):
            with pytest.raises(DeepSeekError) as exc_info:
                list(client.stream_chat_completion(
                    messages=[{"role": "user", "content": "hi"}]
                ))

        assert exc_info.value.code == "DEEPSEEK_CONNECTION_ERROR"


class TestStreamChatCompletionMidStreamFailure:
    """中途失败场景（已 yield chunk 后异常）。"""

    def test_中途失败已yield的chunk保留(self):
        """第一个 chunk yield 成功后，iter_lines 抛异常，应已 yield 一个 chunk。"""
        client = DeepSeekClient(api_key="sk-test", max_retries=0)

        def _lines_then_fail():
            yield f"data: {json.dumps({'choices': [{'delta': {'content': '第一个'}}]})}"
            raise httpx.ReadError("连接中断")

        # 使用 iter_lines_generator 传入生成器（非 side_effect，避免 MagicMock 迭代）
        resp = _make_stream_response(200, iter_lines_generator=_lines_then_fail())
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            gen = client.stream_chat_completion(
                messages=[{"role": "user", "content": "hi"}]
            )
            # 第一个 chunk 应成功 yield
            first = next(gen)
            assert first == "第一个"
            # 之后应抛 DeepSeekError（httpx.ReadError 是 HTTPError 子类）
            with pytest.raises(DeepSeekError):
                next(gen)

    def test_中途失败不写入缓存(self, tmp_path):
        """流式中途失败时不应写入缓存。"""
        cache = LLMCache(str(tmp_path / "cache.db"))
        client = DeepSeekClient(
            api_key="sk-test", max_retries=0, cache=cache, model="deepseek-chat"
        )

        def _lines_then_fail():
            yield f"data: {json.dumps({'choices': [{'delta': {'content': '部分'}}]})}"
            raise httpx.ReadError("中断")

        resp = _make_stream_response(200, iter_lines_generator=_lines_then_fail())
        mock_cls = _patch_httpx_client_stream(resp)

        with patch("httpx.Client", mock_cls):
            gen = client.stream_chat_completion(
                messages=[{"role": "user", "content": "hi"}]
            )
            chunks = []
            with pytest.raises(DeepSeekError):
                for c in gen:
                    chunks.append(c)

        # 已 yield 的 chunk 保留
        assert chunks == ["部分"]
        # 缓存不应被写入
        cache_key = LLMCache.compute_key(
            "deepseek-chat", [{"role": "user", "content": "hi"}], None, 0.3
        )
        assert cache.get(cache_key) is None
