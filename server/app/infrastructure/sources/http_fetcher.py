"""公开 URL 单次获取器；每次重定向都重新执行同一 URL 安全策略。"""

from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.core.config import settings
from app.infrastructure.sources.url_policy import validate_public_url


@dataclass(frozen=True)
class FetchResult:
    content: bytes
    content_type: str
    final_url: str
    status: str
    error_code: str | None
    error_message: str | None


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes
    content_type: str


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UrllibTransport:
    def request(
        self, url: str, timeout_seconds: int, max_bytes: int
    ) -> TransportResponse:
        request = Request(url, headers={"User-Agent": "lab-report-assistant/0.1.0"})
        opener = build_opener(_NoRedirectHandler())
        try:
            response = opener.open(request, timeout=timeout_seconds)
        except HTTPError as exc:
            response = exc

        try:
            body = response.read(max_bytes + 1)
            headers = {key: value for key, value in response.headers.items()}
            return TransportResponse(
                status_code=int(getattr(response, "status", response.code)),
                headers=headers,
                body=body,
                content_type=response.headers.get_content_type(),
            )
        finally:
            response.close()


def _header(headers: dict[str, str], name: str) -> str | None:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return None


def _failure(
    url: str,
    code: str,
    message: str | None = None,
    *,
    blocked: bool = False,
) -> FetchResult:
    return FetchResult(
        content=b"",
        content_type="",
        final_url=url,
        status="BLOCKED" if blocked else "FAILED",
        error_code=code,
        error_message=message,
    )


def fetch_url(
    url: str,
    transport=None,
    resolver=None,
    max_redirects: int = 3,
    timeout_seconds: int | None = None,
    max_bytes: int | None = None,
) -> FetchResult:
    timeout_seconds = timeout_seconds or settings.source_fetch_timeout_seconds
    max_bytes = max_bytes or settings.source_fetch_max_bytes
    transport = transport or UrllibTransport()

    current_url = url
    redirect_count = 0
    while True:
        normalized_url, error = validate_public_url(current_url, resolver=resolver)
        if error:
            return _failure(
                current_url,
                error,
                blocked=error != "SOURCE_URL_FETCH_FAILED",
            )

        try:
            response = transport.request(normalized_url, timeout_seconds, max_bytes)
        except Exception as exc:
            return _failure(
                normalized_url,
                "SOURCE_URL_FETCH_FAILED",
                str(exc)[:200],
            )

        if response.status_code in {301, 302, 303, 307, 308}:
            location = _header(response.headers, "Location")
            if not location:
                return _failure(
                    normalized_url,
                    "SOURCE_URL_FETCH_FAILED",
                    "重定向缺少 Location",
                )
            if redirect_count >= max_redirects:
                return _failure(
                    normalized_url,
                    "SOURCE_URL_TOO_MANY_REDIRECTS",
                    "重定向次数超过上限",
                )
            current_url = urljoin(normalized_url, location)
            redirect_count += 1
            continue

        if response.status_code in {401, 403}:
            return _failure(
                normalized_url,
                "SOURCE_URL_ACCESS_BLOCKED",
                f"HTTP {response.status_code}",
                blocked=True,
            )
        if response.status_code < 200 or response.status_code >= 300:
            return _failure(
                normalized_url,
                "SOURCE_URL_FETCH_FAILED",
                f"HTTP {response.status_code}",
            )
        if len(response.body) > max_bytes:
            return _failure(
                normalized_url,
                "SOURCE_CONTENT_TOO_LARGE",
                "内容超过大小上限",
            )

        content_type = response.content_type or (
            (_header(response.headers, "Content-Type") or "").split(";", 1)[0]
        )
        return FetchResult(
            content=response.body,
            content_type=content_type,
            final_url=normalized_url,
            status="FETCHED",
            error_code=None,
            error_message=None,
        )
