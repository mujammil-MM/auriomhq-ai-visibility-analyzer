"""SSRF protection, URL validation and rate limiting.

Every outbound request made by the crawler passes through
:func:`validate_url` and :func:`resolve_safe_ips` so that:

* only ``http``/``https`` URLs are accepted,
* credentials / exotic ports / control characters are rejected,
* DNS is resolved **before** connecting and every resolved IP must be public,
* the crawler then connects to the validated IP while sending the original
  ``Host`` header (and TLS SNI), which closes the DNS-rebinding window
  between "validation time" and "connect time" (TOCTOU).
"""
from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import time
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from .config import settings

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443}

# Hostnames that commonly resolve to internal services in container / cloud envs
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata",
    "metadata.google.internal",
    "instance-data",
    "kubernetes",
    "kubernetes.default",
    "kubernetes.default.svc",
}

HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))*\.?$")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")

# Networks that must never be contacted by the crawler.
_BLOCKED_V4 = [
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.0.2.0/24",
        "192.88.99.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "198.51.100.0/24",
        "203.0.113.0/24",
        "224.0.0.0/4",
        "240.0.0.0/4",
    )
]
_BLOCKED_V6 = [
    ipaddress.ip_network(n)
    for n in (
        "::/128",
        "::1/128",
        "64:ff9b::/96",
        "100::/64",
        "2001::/32",
        "2001:db8::/32",
        "fc00::/7",
        "fe80::/10",
        "ff00::/8",
    )
]


class UnsafeURLError(ValueError):
    """Raised when a URL fails validation or points at a non-public target."""


@dataclass(frozen=True)
class SafeTarget:
    url: str          # normalised URL (original hostname)
    scheme: str
    host: str         # hostname (lower-case, no trailing dot)
    port: int
    path_query: str
    ips: tuple[str, ...]  # validated public IPs

    @property
    def ip(self) -> str:
        return self.ips[0]

    def connect_url(self, ip: str | None = None) -> str:
        """URL with the host replaced by a validated IP (Host header is set separately)."""
        ip = ip or self.ip
        host_part = f"[{ip}]" if ":" in ip else ip
        default_port = 443 if self.scheme == "https" else 80
        netloc = host_part if self.port == default_port else f"{host_part}:{self.port}"
        return urlunsplit((self.scheme, netloc, self.path_query, "", ""))

    @property
    def host_header(self) -> str:
        default_port = 443 if self.scheme == "https" else 80
        return self.host if self.port == default_port else f"{self.host}:{self.port}"


def ip_is_public(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip.strip("[]"))
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast:
        return False
    if addr.is_reserved or addr.is_unspecified:
        return False
    nets = _BLOCKED_V4 if addr.version == 4 else _BLOCKED_V6
    return not any(addr in net for net in nets)


def normalise_input(raw: str) -> str:
    """Turn user input such as ``example.com`` into ``https://example.com/``."""
    if raw is None:
        raise UnsafeURLError("Please provide a website URL.")
    value = raw.strip()
    if not value:
        raise UnsafeURLError("Please provide a website URL.")
    if CONTROL_CHARS_RE.search(value):
        raise UnsafeURLError("URL contains control characters.")
    if len(value) > 2048:
        raise UnsafeURLError("URL is too long (maximum 2048 characters).")
    if "://" not in value:
        value = "https://" + value.lstrip("/")
    return value


def validate_url(raw: str) -> SafeTarget:
    """Validate scheme/host/port of a URL *without* network access."""
    value = normalise_input(raw)
    parts = urlsplit(value)
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Unsupported protocol '{scheme}'. Only http and https are allowed.")
    if parts.username or parts.password or "@" in parts.netloc:
        raise UnsafeURLError("URLs containing credentials are not allowed.")
    host = (parts.hostname or "").lower().strip(".")
    if not host:
        raise UnsafeURLError("URL is missing a hostname.")
    if host in BLOCKED_HOSTNAMES or host.endswith(".localhost") or host.endswith(".internal"):
        raise UnsafeURLError("That hostname points to an internal network and cannot be analysed.")

    # Bare IP literals
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not settings.allow_private_targets and not ip_is_public(str(literal)):
            raise UnsafeURLError("Private, loopback and link-local IP addresses cannot be analysed.")
        if not settings.allow_private_targets:
            raise UnsafeURLError(
                "Please use a public domain name rather than an IP address so we can verify the site."
            )
    else:
        if not HOSTNAME_RE.match(host):
            raise UnsafeURLError("That does not look like a valid domain name.")
        if "." not in host:
            raise UnsafeURLError("Please enter a full domain name such as example.com.")

    try:
        port = parts.port
    except ValueError as exc:  # malformed port
        raise UnsafeURLError("URL contains an invalid port.") from exc
    if port is None:
        port = 443 if scheme == "https" else 80
    if port not in ALLOWED_PORTS and not settings.allow_private_targets:
        raise UnsafeURLError(f"Port {port} is not allowed. Only 80 (http) and 443 (https) are supported.")

    path = parts.path or "/"
    path_query = path + (f"?{parts.query}" if parts.query else "")
    return SafeTarget(url=urlunsplit((scheme, parts.netloc, path, parts.query, "")), scheme=scheme, host=host, port=port, path_query=path_query, ips=())


async def resolve_safe_ips(host: str, port: int) -> tuple[str, ...]:
    """Resolve a hostname and require *every* returned address to be public."""
    if settings.allow_private_targets:
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            raise UnsafeURLError(f"Could not resolve '{host}'. Check the domain name and try again.") from exc
        return tuple(dict.fromkeys(info[4][0] for info in infos))

    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(host, port, type=socket.SOCK_STREAM), timeout=6.0
        )
    except (socket.gaierror, asyncio.TimeoutError) as exc:
        raise UnsafeURLError(
            f"Could not resolve '{host}'. The domain may not exist or DNS may be unavailable."
        ) from exc
    ips = tuple(dict.fromkeys(str(info[4][0]) for info in infos))
    if not ips:
        raise UnsafeURLError(f"'{host}' did not resolve to any IP address.")
    for ip in ips:
        if not ip_is_public(ip):
            raise UnsafeURLError(
                "That domain resolves to a private or internal address, so it cannot be analysed."
            )
    return ips


async def guard_fetch_url(raw: str) -> SafeTarget:
    """Full guard: format validation + DNS resolution + IP allow-listing."""
    target = validate_url(raw)
    ips = await resolve_safe_ips(target.host, target.port)
    return SafeTarget(**{**target.__dict__, "ips": ips})


# --------------------------------------------------------------------------
# Rate limiting (in-process token bucket; swap for Redis in multi-instance setups)
# --------------------------------------------------------------------------
class RateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._events: dict[str, list[float]] = {}

    def check(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        bucket = [t for t in self._events.get(key, []) if now - t < self.window]
        if len(bucket) >= self.limit:
            retry_after = int(self.window - (now - bucket[0])) + 1
            self._events[key] = bucket
            return False, retry_after
        bucket.append(now)
        self._events[key] = bucket
        if len(self._events) > 5000:  # crude memory guard
            self._events = {k: v for k, v in self._events.items() if v and now - v[-1] < self.window}
        return True, 0

    def remaining(self, key: str) -> int:
        now = time.monotonic()
        bucket = [t for t in self._events.get(key, []) if now - t < self.window]
        return max(0, self.limit - len(bucket))


audit_rate_limiter = RateLimiter(settings.rate_limit_audits, settings.rate_limit_window_seconds)
lead_rate_limiter = RateLimiter(5, 900)
