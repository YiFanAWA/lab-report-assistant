"""HTTP 采集适配器。

负责公开 URL 的下载，内置超时、大小上限和登录限制检测。
不绕过登录、验证码、付费墙或访问控制。
"""

from dataclasses import dataclass


@dataclass
class FetchResult:
    """采集结果。"""

    content: bytes
    content_type: str
    status_code: int
    url: str


class FetchError(Exception):
    """采集失败的结构化错误。

    code 用于映射到 BackgroundJob.error_code 与 Source.error_code。
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _looks_like_login_page(content: bytes, content_type: str) -> bool:
    """检测 HTML 是否包含登录表单特征。"""
    if "text/html" not in content_type.lower():
        return False
    try:
        text = content.decode("utf-8", errors="ignore").lower()
    except Exception:
        return False
    if '<input type="password"' in text or "<input type='password'" in text:
        return True
    # 检测含 login 关键词的 form
    if "<form" in text and "login" in text:
        return True
    return False


def fetch_url(
    url: str,
    timeout_seconds: int = 30,
    max_size_bytes: int = 10 * 1024 * 1024,
) -> FetchResult:
    """采集公开 URL 内容。

    - 超时返回 FETCH_TIMEOUT。
    - 401/403 返回 SOURCE_ACCESS_RESTRICTED。
    - 内容过大返回 FETCH_TOO_LARGE。
    - 检测到登录表单特征返回 SOURCE_ACCESS_RESTRICTED。
    """
    import httpx

    try:
        with httpx.Client(timeout=httpx.Timeout(timeout_seconds), follow_redirects=True) as client:
            # 先以流式请求获取响应头，避免一次性下载超大文件。
            with client.stream("GET", url) as response:
                status_code = response.status_code
                if status_code in (401, 403):
                    raise FetchError("SOURCE_ACCESS_RESTRICTED", "来源需要登录或付费")

                # 检查 Content-Length 头
                content_length_header = response.headers.get("content-length")
                if content_length_header:
                    try:
                        declared_size = int(content_length_header)
                    except ValueError:
                        declared_size = None
                    if declared_size is not None and declared_size > max_size_bytes:
                        raise FetchError("FETCH_TOO_LARGE", "采集内容过大")

                content_type = response.headers.get("content-type", "")

                # 读取响应内容，逐块累加并检查大小
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    total += len(chunk)
                    if total > max_size_bytes:
                        raise FetchError("FETCH_TOO_LARGE", "采集内容过大")
                    chunks.append(chunk)
                content = b"".join(chunks)

            # 检测登录表单特征
            if _looks_like_login_page(content, content_type):
                raise FetchError("SOURCE_ACCESS_RESTRICTED", "来源需要登录")

            # 取最终 URL（含重定向后的地址）
            final_url = str(response.url)

            return FetchResult(
                content=content,
                content_type=content_type,
                status_code=status_code,
                url=final_url,
            )
    except httpx.TimeoutException as exc:
        raise FetchError("FETCH_TIMEOUT", "采集超时") from exc
    except FetchError:
        raise
    except httpx.HTTPError as exc:
        raise FetchError("FETCH_FAILED", f"采集失败：{exc}") from exc
