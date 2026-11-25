"""Test fixtures: a local HTTP server that serves synthetic websites.

The crawler's SSRF guard blocks private IPs by design, so for tests we
explicitly enable ``CRAWL_ALLOW_PRIVATE_TARGETS`` and point the crawler at
127.0.0.1. Production behaviour is covered by the security tests, which assert
that private targets are rejected when the flag is off.
"""
from __future__ import annotations

import asyncio
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

import pytest

from app.config import settings

GOOD_HOME = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Acme Analytics — Product analytics for B2B SaaS teams</title>
  <meta name="description" content="Acme Analytics is a product analytics platform for B2B SaaS teams that shows which onboarding steps turn trials into paying customers, without a data team.">
  <link rel="canonical" href="{base}/">
  <link rel="icon" href="/favicon.ico">
  <meta property="og:title" content="Acme Analytics">
  <meta property="og:description" content="Product analytics for B2B SaaS teams.">
  <meta property="og:image" content="{base}/og.png">
  <meta property="og:url" content="{base}/">
  <script type="application/ld+json">
  {"@context":"https://schema.org","@graph":[
    {"@type":"Organization","name":"Acme Analytics","url":"{base}/","logo":"{base}/logo.png",
      "description":"Product analytics for B2B SaaS teams.",
      "sameAs":["https://www.linkedin.com/company/acme-analytics"],
      "address":{"@type":"PostalAddress","streetAddress":"12 Market Street","addressLocality":"Pune"}},
    {"@type":"WebSite","name":"Acme Analytics","url":"{base}/"}
  ]}
  </script>
</head>
<body>
<header><nav><a href="/">Home</a> <a href="/pricing">Pricing</a> <a href="/about">About Acme</a> <a href="/faq">FAQ</a> <a href="/contact">Contact</a></nav></header>
<main>
  <h1>Product analytics for B2B SaaS teams</h1>
  <p>Acme Analytics is a product analytics platform that helps B2B SaaS teams find the onboarding steps that convert trials into paying customers. It works without a dedicated data team.</p>
  <h2>What is Acme Analytics?</h2>
  <p>Acme Analytics is a self-serve analytics tool that tracks activation, retention and expansion across your product, then explains which behaviours predict conversion in plain language for product managers.</p>
  <h2>How does it work?</h2>
  <p>You install a lightweight snippet, connect your billing system, and Acme models your funnel automatically within the first hour of data collection so you can see where accounts stall.</p>
  <ol><li>Install the snippet</li><li>Connect billing</li><li>Review your activation funnel</li></ol>
  <h2>Frequently asked questions</h2>
  <h3>How much does Acme Analytics cost?</h3>
  <p>Plans start at $99 per month for up to 50,000 monthly tracked users, with annual billing available and no setup fee for the standard onboarding path.</p>
  <h3>Do you support self-hosting?</h3>
  <p>Yes. Enterprise customers can self-host Acme inside their own VPC, and our team supports the deployment with documentation and a shared implementation call.</p>
  <h2>Evidence</h2>
  <p>Our methodology follows the <a href="https://www.nist.gov/itl/ai-risk-management-framework" rel="noopener">NIST AI Risk Management Framework</a> for measurement transparency.</p>
  <p>More detail on our <a href="/about">company and team</a> and <a href="/pricing">pricing</a>.</p>
  <img src="/dashboard.png" alt="Acme activation dashboard showing funnel conversion">
</main>
<footer>
  <p>Contact <a href="mailto:hello@acme.example">hello@acme.example</a> · 12 Market Street, Pune</p>
  <p><a href="https://example.org/reference">Reference source</a></p>
  <time datetime="2026-09-01">Updated 1 September 2026</time>
</footer>
</body>
</html>
"""

POOR_HOME = """<html><head><title>Home</title></head><body>
<h1>Welcome</h1>
<p>We do things.</p>
<a href="/missing-page">link</a>
<img src="/a.png"><img src="/b.png">
</body></html>
"""

REDIRECT_A = """<html><head><title>Redirect A</title></head><body><p>redirecting</p></body></html>"""


class Handler(BaseHTTPRequestHandler):
    routes: dict[str, tuple[int, dict[str, str], bytes]] = {}
    delay_routes: dict[str, float] = {}

    def log_message(self, *args):  # silence test server logging
        return

    def do_HEAD(self):  # noqa: N802
        self.do_GET(head_only=True)

    def do_GET(self, head_only: bool = False):  # noqa: N802
        path = self.path.split("?")[0]
        if path in self.delay_routes:
            time.sleep(self.delay_routes[path])
        status, headers, body = self.routes.get(
            path, (404, {"Content-Type": "text/html; charset=utf-8"}, b"<html><body>Not found</body></html>")
        )
        resolved = body.replace(b"{base}", self.server.base_url.encode())
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value.replace("{base}", self.server.base_url))
        self.send_header("Content-Length", str(len(resolved)))
        self.end_headers()
        if not head_only:
            self.wfile.write(resolved)


class FixtureSite:
    def __init__(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return self.server.base_url

    def set_routes(self, routes: dict[str, tuple[int, dict[str, str], bytes]], delays: dict[str, float] | None = None) -> None:
        Handler.routes = routes
        Handler.delay_routes = delays or {}

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def html(body: str, status: int = 200, extra: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    headers = {"Content-Type": "text/html; charset=utf-8"}
    headers.update(extra or {})
    return status, headers, body.encode()


@pytest.fixture(scope="session")
def site() -> FixtureSite:
    server = FixtureSite()
    server.start()
    yield server
    server.stop()


@pytest.fixture()
def allow_private(monkeypatch):
    monkeypatch.setattr(settings, "allow_private_targets", True, raising=False)


@pytest.fixture()
def good_site(site, allow_private):
    base = site.base_url
    robots = "User-agent: *\nAllow: /\nDisallow: /dashboard\n\nSitemap: {base}/sitemap.xml\n"
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>{base}/</loc></url><url><loc>{base}/pricing</loc></url>"
        "<url><loc>{base}/about</loc></url></urlset>"
    )
    pages = {
        "/": html(GOOD_HOME),
        "/pricing": html(
            "<html lang='en'><head><title>Pricing — Acme Analytics</title>"
            "<meta name='description' content='Transparent product analytics pricing for B2B SaaS teams, from $99 per month with no setup fee and annual billing options.'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'><link rel='canonical' href='{base}/pricing'></head>"
            "<body><h1>Pricing</h1><p>Plans start at $99 per month for up to 50,000 monthly tracked users. Annual billing saves two months.</p>"
            "<h2>Which plan fits a Series A team?</h2><p>Teams under 50,000 monthly tracked users usually start on the Growth plan, then move to Scale once they track multiple products or need SSO.</p>"
            "<ul><li>Growth</li><li>Scale</li><li>Enterprise</li></ul></body></html>"
        ),
        "/about": html(
            "<html lang='en'><head><title>About Acme Analytics</title>"
            "<meta name='description' content='Acme Analytics is built by a small team of product analysts and engineers who previously ran data teams at B2B SaaS companies.'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'></head>"
            "<body><h1>About Acme</h1><p>Acme Analytics is a product analytics company founded in 2021 by former data leads at B2B SaaS businesses.</p></body></html>"
        ),
        "/faq": html(
            "<html lang='en'><head><title>FAQ — Acme Analytics</title>"
            "<meta name='description' content='Answers to common questions about Acme Analytics pricing, implementation time and data residency options.'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'></head>"
            "<body><h1>Frequently asked questions</h1>"
            "<h2>How long does setup take?</h2><p>Most teams see their first funnel within an hour of installing the snippet and connecting a billing source.</p></body></html>"
        ),
        "/contact": html(
            "<html lang='en'><head><title>Contact Acme Analytics</title>"
            "<meta name='description' content='Contact the Acme Analytics team about pricing, implementation or data residency questions.'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'></head>"
            "<body><h1>Contact</h1><p>Email hello@acme.example or call +91 20 1234 5678.</p></body></html>"
        ),
        "/robots.txt": (200, {"Content-Type": "text/plain"}, robots.encode()),
        "/sitemap.xml": (200, {"Content-Type": "application/xml"}, sitemap.encode()),
    }
    site.set_routes(pages)
    return site


@pytest.fixture()
def ctx():
    """Run an async crawl+analyse inside a sync test."""

    def run(coro):
        return asyncio.run(coro)

    return run
