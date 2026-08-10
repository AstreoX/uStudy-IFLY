"""SSRF protection — URL safety validation.

Extracted to its own module to avoid circular imports between
chat.tools.web_tools ↔ crawler.deep_crawler.
"""

import ipaddress
import socket
from urllib.parse import urlparse


BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "[::1]",
}

BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),       # Private
    ipaddress.ip_network("172.16.0.0/12"),    # Private
    ipaddress.ip_network("192.168.0.0/16"),   # Private
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local / Cloud metadata
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
]


def is_safe_url(url: str) -> tuple[bool, str]:
    """
    Validate URL is safe to fetch (SSRF prevention).

    Returns:
        Tuple of (is_safe, error_message)
    """
    try:
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return False, "URL 必须使用 http 或 https 协议"

        hostname = parsed.hostname
        if not hostname:
            return False, "URL 格式无效：缺少主机名"

        if hostname.lower() in BLOCKED_HOSTS:
            return False, "不允许访问内部主机"

        try:
            resolved_ip = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(resolved_ip)
            for blocked_range in BLOCKED_IP_RANGES:
                if ip in blocked_range:
                    return False, "不允许访问内部 IP 地址段"
        except socket.gaierror:
            return False, "无法解析主机名"
        except ValueError:
            pass

        return True, ""

    except Exception as e:
        return False, f"URL 格式无效: {str(e)}"
