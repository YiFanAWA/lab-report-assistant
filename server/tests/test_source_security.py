"""公开 URL 的协议、DNS、重定向和上界安全测试。"""

import socket

from app.infrastructure.sources.http_fetcher import FetchResult, fetch_url, TransportResponse
from app.infrastructure.sources.url_policy import validate_public_url


class FakeTransport:
    def __init__(self, responses):
        self._responses = iter(responses)

    def request(self, url: str, timeout_seconds: int, max_bytes: int):
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return response


def public_dns(*args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def test_blocks_hostname_resolving_to_private_network(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ],
    )
    _, error = validate_public_url("https://internal.example/path")
    assert error == "SOURCE_URL_BLOCKED_PRIVATE_NETWORK"


def test_rejects_credentials_before_fetch():
    _, error = validate_public_url("https://user:pass@example.com")
    assert error == "SOURCE_URL_UNSUPPORTED_SCHEME"


def test_fetch_revalidates_redirect_target():
    transport = FakeTransport(
        [TransportResponse(status_code=302, headers={"Location": "http://127.0.0.1/admin"}, body=b"", content_type="")]
    )
    result = fetch_url(
        "https://example.com/start", transport=transport, resolver=public_dns
    )
    assert isinstance(result, FetchResult)
    assert result.status == "BLOCKED"
    assert result.error_code == "SOURCE_URL_BLOCKED_PRIVATE_NETWORK"


def test_fetch_stops_after_three_redirects():
    transport = FakeTransport(
        [
            TransportResponse(302, {"Location": "https://example.com/one"}, b"", ""),
            TransportResponse(302, {"Location": "https://example.com/two"}, b"", ""),
            TransportResponse(302, {"Location": "https://example.com/three"}, b"", ""),
            TransportResponse(302, {"Location": "https://example.com/four"}, b"", ""),
        ]
    )
    result = fetch_url(
        "https://example.com/start", transport=transport, resolver=public_dns
    )
    assert isinstance(result, FetchResult)
    assert result.status == "FAILED"
    assert result.error_code == "SOURCE_URL_TOO_MANY_REDIRECTS"


def test_fetch_rejects_content_over_limit():
    transport = FakeTransport([TransportResponse(200, {}, b"12345", "")])
    result = fetch_url(
        "https://example.com/start",
        transport=transport,
        resolver=public_dns,
        max_bytes=4,
    )
    assert isinstance(result, FetchResult)
    assert result.status == "FAILED"
    assert result.error_code == "SOURCE_CONTENT_TOO_LARGE"


def test_fetch_returns_structured_timeout():
    result = fetch_url(
        "https://example.com/start",
        transport=FakeTransport([TimeoutError("timed out")]),
        resolver=public_dns,
    )
    assert isinstance(result, FetchResult)
    assert result.status == "FAILED"
    assert result.error_code == "SOURCE_URL_FETCH_FAILED"


def test_fetch_marks_unauthorized_response_as_access_blocked():
    result = fetch_url(
        "https://example.com/restricted",
        transport=FakeTransport([TransportResponse(403, {}, b"login required", "")]),
        resolver=public_dns,
    )
    assert result.status == "BLOCKED"
    assert result.error_code == "SOURCE_URL_ACCESS_BLOCKED"
