"""公开 URL 的协议、认证信息和 DNS/SSRF 安全策略。"""

import socket
from ipaddress import ip_address
from urllib.parse import urlparse


_LOCAL_HOSTNAMES = {"localhost", "localhost.localdomain"}


def _address_strings(records) -> list[str]:
    addresses: list[str] = []
    for record in records:
        if isinstance(record, str):
            addresses.append(record)
            continue
        if isinstance(record, tuple) and len(record) >= 5:
            sockaddr = record[4]
            if isinstance(sockaddr, tuple) and sockaddr:
                addresses.append(str(sockaddr[0]))
    return addresses


def validate_public_url(raw_url: str, resolver=None) -> tuple[str, str | None]:
    """返回规范化 URL 和结构化错误码；全部解析地址都必须是公网地址。"""
    raw = raw_url.strip()
    try:
        parsed = urlparse(raw)
    except (TypeError, ValueError):
        return "", "SOURCE_URL_UNSUPPORTED_SCHEME"

    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return "", "SOURCE_URL_UNSUPPORTED_SCHEME"

    host = (parsed.hostname or "").strip().lower()
    if not host:
        return "", "SOURCE_URL_UNSUPPORTED_SCHEME"
    if host in _LOCAL_HOSTNAMES:
        return "", "SOURCE_URL_BLOCKED_PRIVATE_NETWORK"

    try:
        literal = ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        return "", "SOURCE_URL_BLOCKED_PRIVATE_NETWORK"

    resolver = resolver or socket.getaddrinfo
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        try:
            records = resolver(host, port, type=socket.SOCK_STREAM)
        except TypeError:
            records = resolver(host)
        addresses = _address_strings(records)
    except (OSError, ValueError):
        return "", "SOURCE_URL_FETCH_FAILED"

    if not addresses:
        return "", "SOURCE_URL_FETCH_FAILED"
    for address in addresses:
        try:
            if not ip_address(address).is_global:
                return "", "SOURCE_URL_BLOCKED_PRIVATE_NETWORK"
        except ValueError:
            return "", "SOURCE_URL_FETCH_FAILED"

    return parsed.geturl(), None
