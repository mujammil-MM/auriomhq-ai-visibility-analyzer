"""SSRF and input-validation tests — the restrictions must not be bypassable."""
from __future__ import annotations

import asyncio

import pytest

from app.config import settings
from app.security import (
    RateLimiter,
    UnsafeURLError,
    ip_is_public,
    normalise_input,
    resolve_safe_ips,
    validate_url,
)

PUBLIC_SCENARIOS = [
    "example.com",
    "https://example.com",
    "http://example.com/path?q=1",
]

BLOCKED_SCENARIOS = [
    ("http://localhost", "internal"),
    ("http://localhost:8000/admin", "internal"),
    ("http://127.0.0.1", "private"),
    ("http://127.0.0.1:8080", "private"),
    ("http://10.0.0.5", "private"),
    ("http://192.168.1.1", "private"),
    ("http://172.16.0.1", "private"),
    ("http://169.254.169.254/latest/meta-data/", "private"),
    ("http://[::1]/", "private"),
    ("http://[fd00::1]/", "private"),
    ("http://0.0.0.0/", "private"),
    ("ftp://example.com", "protocol"),
    ("file:///etc/passwd", "protocol"),
    ("javascript:alert(1)", "protocol"),
    ("http://user:pass@example.com", "credentials"),
    ("http://example.com:22", "port"),
    ("not a url", "invalid"),
    ("", "empty"),
    ("http://metadata.google.internal/", "internal"),
]


def test_public_urls_are_accepted():
    for candidate in PUBLIC_SCENARIOS:
        target = validate_url(candidate)
        assert target.scheme in {"http", "https"}
        assert target.host in {"example.com"}


@pytest.mark.parametrize("url,expected", BLOCKED_SCENARIOS)
def test_blocked_urls_raise(url, expected):
    with pytest.raises(UnsafeURLError):
        validate_url(url)


def test_scheme_is_added_for_bare_domains():
    assert normalise_input("example.com").startswith("https://")
    assert normalise_input("  example.com  ") == "https://example.com"


def test_control_characters_rejected():
    with pytest.raises(UnsafeURLError):
        validate_url("https://example.com/\x00admin")


def test_ip_is_public_helper():
    assert ip_is_public("93.184.216.34")
    assert not ip_is_public("127.0.0.1")
    assert not ip_is_public("10.1.2.3")
    assert not ip_is_public("169.254.169.254")
    assert not ip_is_public("::1")
    assert not ip_is_public("fc00::1")
    assert not ip_is_public("not-an-ip")


def test_dns_resolution_rejects_private_records(monkeypatch):
    """A hostname that resolves to a private IP must be refused (DNS rebinding guard)."""

    class FakeLoop:
        async def getaddrinfo(self, *args, **kwargs):
            return [(2, 1, 6, "", ("10.0.0.9", 443))]

    async def run() -> None:
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "getaddrinfo", FakeLoop().getaddrinfo)
        with pytest.raises(UnsafeURLError):
            await resolve_safe_ips("internal.example.com", 443)

    asyncio.run(run())


def test_rate_limiter_counts_and_resets():
    limiter = RateLimiter(limit=2, window_seconds=60)
    assert limiter.check("a")[0] is True
    assert limiter.check("a")[0] is True
    allowed, retry_after = limiter.check("a")
    assert allowed is False and retry_after > 0
    assert limiter.check("b")[0] is True
    assert limiter.remaining("a") == 0


def test_private_targets_can_be_enabled_only_explicitly(monkeypatch):
    """Guard exists only because the crawler resolves before connecting."""
    with pytest.raises(UnsafeURLError):
        validate_url("http://127.0.0.1:8080")
    monkeypatch.setattr(settings, "allow_private_targets", True, raising=False)
    target = validate_url("http://127.0.0.1:8080")
    assert target.host == "127.0.0.1"
    monkeypatch.setattr(settings, "allow_private_targets", False, raising=False)
