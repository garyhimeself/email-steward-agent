"""Credential-free local network diagnostics for Alibaba Enterprise Mail."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import ipaddress
import socket
import ssl
from typing import Any
from urllib.request import urlopen


DEFAULT_IMAP_HOST = "imap.qiye.aliyun.com"
DEFAULT_IMAP_PORT = 993
NETWORK_TIMEOUT_SECONDS = 10.0
PUBLIC_IP_SERVICE_URL = "https://api.ipify.org"


@dataclass(frozen=True)
class LocalNetworkPreflight:
    """Non-secret observations from the computer running this command."""

    hostname: str
    imap_host: str
    imap_port: int
    dns_addresses: tuple[str, ...]
    tls_connected: bool
    public_ip: str


def run_local_network_preflight(
    *,
    hostname_fn: Callable[[], str] = socket.gethostname,
    resolver: Callable[[str, int], list[tuple[Any, ...]]] = socket.getaddrinfo,
    tls_probe: Callable[[str, int], bool] | None = None,
    public_ip_fetcher: Callable[[], str] | None = None,
    imap_host: str = DEFAULT_IMAP_HOST,
    imap_port: int = DEFAULT_IMAP_PORT,
) -> LocalNetworkPreflight:
    """Collect local network evidence without mailbox credentials or IMAP commands."""
    try:
        records = resolver(imap_host, imap_port)
    except OSError:
        records = []
    addresses = tuple(dict.fromkeys(str(record[4][0]) for record in records if len(record) > 4))
    connected = (tls_probe or probe_tls)(imap_host, imap_port)
    try:
        public_ip = _validated_public_ip((public_ip_fetcher or fetch_public_ip)())
    except (OSError, TimeoutError, ValueError):
        public_ip = "unknown"
    return LocalNetworkPreflight(
        hostname=_safe_hostname(hostname_fn()),
        imap_host=imap_host,
        imap_port=imap_port,
        dns_addresses=addresses,
        tls_connected=bool(connected),
        public_ip=public_ip,
    )


def probe_tls(
    host: str,
    port: int,
    *,
    socket_factory: Callable[..., Any] = socket.create_connection,
    context_factory: Callable[[], ssl.SSLContext] = ssl.create_default_context,
) -> bool:
    """Verify only TLS reachability; this deliberately never creates an IMAP client."""
    try:
        context = context_factory()
        with socket_factory((host, port), timeout=NETWORK_TIMEOUT_SECONDS) as raw_socket:
            with context.wrap_socket(raw_socket, server_hostname=host):
                return True
    except (OSError, TimeoutError, ssl.SSLError):
        return False


def fetch_public_ip() -> str:
    """Read a public IP from a HTTPS-only service; callers may treat failure as unknown."""
    with urlopen(PUBLIC_IP_SERVICE_URL, timeout=NETWORK_TIMEOUT_SECONDS) as response:  # nosec B310: fixed HTTPS URL
        return response.read(128).decode("ascii", errors="strict").strip()


def format_preflight_messages(result: LocalNetworkPreflight) -> tuple[str, ...]:
    """Create bilingual operator output without storing any diagnostic values."""
    resolved = ", ".join(result.dns_addresses) if result.dns_addresses else "unknown"
    tls_status = "passed" if result.tls_connected else "failed"
    tls_status_zh = "通过" if result.tls_connected else "失败"
    return (
        "Local network preflight (no mailbox login was attempted):",
        f"Computer: {result.hostname}",
        f"IMAP: {result.imap_host}:{result.imap_port}",
        f"DNS addresses: {resolved}",
        f"TLS connection: {tls_status}",
        f"Current public IP: {result.public_ip}",
        "This is a current observation, not a promise of a fixed IP. Compare it with the Alibaba mail login log before entering a third-party client password.",
        "本地网络预检（未尝试邮箱登录）：",
        f"电脑名称：{result.hostname}",
        f"IMAP：{result.imap_host}:{result.imap_port}",
        f"DNS 地址：{resolved}",
        f"TLS 连接：{tls_status_zh}",
        f"当前公网 IP：{result.public_ip}",
        "这是当前观测结果，不承诺公网 IP 固定。请在输入第三方客户端安全密码前，与阿里邮箱登录日志中的 IP 核对。",
    )


def _validated_public_ip(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("public IP response must be text")
    return str(ipaddress.ip_address(value.strip()))


def _safe_hostname(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return "unknown"
    return value.strip()
