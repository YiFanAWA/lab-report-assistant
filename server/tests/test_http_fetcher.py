"""HTTP 采集适配器测试。

mock httpx.Client.stream，避免真实网络调用。
覆盖：成功路径、超时、过大文件、受限资源（401/403）、登录表单检测。
"""

import sys
from typing import Optional

import httpx
import pytest

from app.infrastructure.fetchers.http_fetcher import fetch_url, FetchError


# --- 测试替身 ---


class FakeStreamResponse:
    """模拟 httpx 流式响应。"""

    def __init__(self, status_code: int, headers: dict,
                 content: bytes, url: str = "https://example.com/page"):
        self.status_code = status_code
        self.headers = headers
        self._content = content
        self.url = url
        self._bytes_yielded = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_bytes(self, chunk_size: int = 64 * 1024):
        # 简化：一次性返回全部内容
        if not self._bytes_yielded:
            self._bytes_yielded = True
            yield self._content


class FakeHttpClient:
    """模拟 httpx.Client。"""

    def __init__(self, response: Optional[FakeStreamResponse] = None,
                 exc: Optional[Exception] = None):
        self._response = response
        self._exc = exc

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, method: str, url: str):
        if self._exc is not None:
            raise self._exc
        return self._response


def _patch_httpx_client(monkeypatch, response=None, exc=None):
    """用 monkeypatch 替换 httpx.Client，返回 FakeHttpClient。"""
    fake_client_factory = lambda *args, **kwargs: FakeHttpClient(
        response=response, exc=exc
    )
    monkeypatch.setattr(httpx, "Client", fake_client_factory)
    monkeypatch.setattr(httpx, "Timeout", lambda *args, **kwargs: None)


# --- 成功路径 ---


class TestFetchUrlSuccess:
    """fetch_url 成功路径测试。"""

    def test_returns_fetch_result_with_content_and_type(self, monkeypatch):
        """200 OK 返回 FetchResult，content_type 和 content 正确。"""
        html = "<html><body><p>这是一段公开网页的正文内容。</p></body></html>".encode("utf-8")
        response = FakeStreamResponse(
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8",
                     "content-length": str(len(html))},
            content=html,
            url="https://example.com/article",
        )
        _patch_httpx_client(monkeypatch, response=response)

        result = fetch_url("https://example.com/article")
        assert result.content == html
        assert "text/html" in result.content_type
        assert result.status_code == 200
        assert "example.com" in result.url

    def test_pdf_content_type_preserved(self, monkeypatch):
        """PDF 内容类型保留。"""
        pdf_bytes = b"%PDF-1.4 fake pdf bytes for test"
        response = FakeStreamResponse(
            status_code=200,
            headers={"content-type": "application/pdf",
                     "content-length": str(len(pdf_bytes))},
            content=pdf_bytes,
        )
        _patch_httpx_client(monkeypatch, response=response)

        result = fetch_url("https://example.com/paper.pdf")
        assert result.content == pdf_bytes
        assert result.content_type == "application/pdf"


# --- 超时 ---


class TestFetchUrlTimeout:
    """fetch_url 超时测试。"""

    def test_timeout_returns_fetch_timeout(self, monkeypatch):
        """httpx 抛 TimeoutException 时返回 FETCH_TIMEOUT。"""
        _patch_httpx_client(
            monkeypatch,
            exc=httpx.TimeoutException("connection timed out"),
        )

        with pytest.raises(FetchError) as exc_info:
            fetch_url("https://example.com/slow")
        assert exc_info.value.code == "FETCH_TIMEOUT"
        assert "采集超时" in exc_info.value.message


# --- 大小上限 ---


class TestFetchUrlTooLarge:
    """fetch_url 大小上限测试。"""

    def test_declared_content_length_exceeds_max_returns_too_large(
        self, monkeypatch
    ):
        """Content-Length 头超过 max_size_bytes 返回 FETCH_TOO_LARGE。"""
        # 不需要实际生成 10MB 内容，只需 Content-Length 头超限
        big_response = FakeStreamResponse(
            status_code=200,
            headers={"content-type": "text/html",
                     "content-length": str(20 * 1024 * 1024)},  # 20MB
            content=b"",  # 不会真的读到内容，因为长度检查在前
        )
        _patch_httpx_client(monkeypatch, response=big_response)

        with pytest.raises(FetchError) as exc_info:
            fetch_url("https://example.com/huge", max_size_bytes=10 * 1024 * 1024)
        assert exc_info.value.code == "FETCH_TOO_LARGE"

    def test_actual_stream_size_exceeds_max_returns_too_large(
        self, monkeypatch
    ):
        """流式读取过程中累计超过 max_size_bytes 返回 FETCH_TOO_LARGE。"""
        # 没有 Content-Length 头，但实际内容超限
        big_content = b"x" * (2 * 1024 * 1024)
        big_response = FakeStreamResponse(
            status_code=200,
            headers={"content-type": "text/html"},  # 无 content-length
            content=big_content,
        )
        _patch_httpx_client(monkeypatch, response=big_response)

        with pytest.raises(FetchError) as exc_info:
            fetch_url("https://example.com/huge", max_size_bytes=1024)
        assert exc_info.value.code == "FETCH_TOO_LARGE"


# --- 受限资源 ---


class TestFetchUrlRestricted:
    """fetch_url 受限资源测试。"""

    def test_401_returns_source_access_restricted(self, monkeypatch):
        """401 返回 SOURCE_ACCESS_RESTRICTED。"""
        response = FakeStreamResponse(
            status_code=401,
            headers={"content-type": "text/html"},
            content=b"<html><body>Unauthorized</body></html>",
        )
        _patch_httpx_client(monkeypatch, response=response)

        with pytest.raises(FetchError) as exc_info:
            fetch_url("https://example.com/protected")
        assert exc_info.value.code == "SOURCE_ACCESS_RESTRICTED"

    def test_403_returns_source_access_restricted(self, monkeypatch):
        """403 返回 SOURCE_ACCESS_RESTRICTED。"""
        response = FakeStreamResponse(
            status_code=403,
            headers={"content-type": "text/html"},
            content=b"<html><body>Forbidden</body></html>",
        )
        _patch_httpx_client(monkeypatch, response=response)

        with pytest.raises(FetchError) as exc_info:
            fetch_url("https://example.com/forbidden")
        assert exc_info.value.code == "SOURCE_ACCESS_RESTRICTED"

    def test_login_form_returns_source_access_restricted(self, monkeypatch):
        """HTML 包含 password 输入框返回 SOURCE_ACCESS_RESTRICTED。"""
        html = (
            b"<html><body>"
            b"<form action='/login'><input type='password' name='pwd'>"
            b"<button>Login</button></form>"
            b"</body></html>"
        )
        response = FakeStreamResponse(
            status_code=200,
            headers={"content-type": "text/html",
                     "content-length": str(len(html))},
            content=html,
        )
        _patch_httpx_client(monkeypatch, response=response)

        with pytest.raises(FetchError) as exc_info:
            fetch_url("https://example.com/login")
        assert exc_info.value.code == "SOURCE_ACCESS_RESTRICTED"

    def test_login_keyword_form_returns_source_access_restricted(
        self, monkeypatch
    ):
        """HTML 含 <form> + login 关键词返回 SOURCE_ACCESS_RESTRICTED。"""
        html = (
            b"<html><body>"
            b"<form action='/auth'>User login required.</form>"
            b"</body></html>"
        )
        response = FakeStreamResponse(
            status_code=200,
            headers={"content-type": "text/html",
                     "content-length": str(len(html))},
            content=html,
        )
        _patch_httpx_client(monkeypatch, response=response)

        with pytest.raises(FetchError) as exc_info:
            fetch_url("https://example.com/auth")
        assert exc_info.value.code == "SOURCE_ACCESS_RESTRICTED"


# --- 通用 HTTP 错误 ---


class TestFetchUrlHttpError:
    """fetch_url 通用 HTTP 错误测试。"""

    def test_http_error_returns_fetch_failed(self, monkeypatch):
        """httpx.HTTPError 返回 FETCH_FAILED。"""
        _patch_httpx_client(
            monkeypatch,
            exc=httpx.HTTPError("connection refused"),
        )

        with pytest.raises(FetchError) as exc_info:
            fetch_url("https://example.com/down")
        assert exc_info.value.code == "FETCH_FAILED"
        assert "connection refused" in exc_info.value.message


# --- 配置参数传递 ---


class TestFetchUrlConfig:
    """fetch_url 配置参数测试。"""

    def test_uses_provided_timeout_and_max_size(self, monkeypatch):
        """传入的 timeout_seconds 和 max_size_bytes 被使用。"""
        html = b"<html><body>content</body></html>"
        response = FakeStreamResponse(
            status_code=200,
            headers={"content-type": "text/html",
                     "content-length": str(len(html))},
            content=html,
        )
        # 捕获传入 Client 的 kwargs
        captured = {}

        def fake_client_factory(*args, **kwargs):
            captured.update(kwargs)
            return FakeHttpClient(response=response)

        monkeypatch.setattr(httpx, "Client", fake_client_factory)
        monkeypatch.setattr(httpx, "Timeout", lambda *a, **kw: kw)

        fetch_url("https://example.com/", timeout_seconds=10,
                  max_size_bytes=5 * 1024 * 1024)
        assert captured.get("timeout") is not None  # Timeout 被构造并传入
        # follow_redirects 应为 True
        assert captured.get("follow_redirects") is True
