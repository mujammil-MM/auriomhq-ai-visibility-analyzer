"""Crawler tests using a local fixture website (scenarios 1, 3, 5, 6, 7, 10)."""
from __future__ import annotations

import asyncio

import pytest

from app.crawler import Crawler, parse_page
from app.config import settings


def crawl(url: str, max_pages: int = 5):
    return asyncio.run(Crawler(max_pages=max_pages).crawl(url))


def test_crawls_well_formed_site(good_site):
    result = crawl(good_site.base_url + "/", max_pages=5)
    assert result.pages, result.errors
    home = result.pages[0]
    assert home.status == 200
    assert "Acme Analytics" in home.title
    assert home.h1s and "Product analytics" in home.h1s[0]
    assert home.meta_description
    assert home.viewport
    assert home.lang == "en"
    assert len(result.pages) >= 4, [p.url for p in result.pages]
    assert result.robots.available is True
    assert result.robots.blocks_all is False
    assert result.sitemap.available is True
    assert len(result.sitemap.urls) >= 3
    assert result.https_available is False


def test_title_and_headings_come_from_actual_html(good_site):
    result = crawl(good_site.base_url + "/", max_pages=1)
    home = result.pages[0]
    assert home.title == "Acme Analytics — Product analytics for B2B SaaS teams"
    assert "What is Acme Analytics?" in home.h2s
    assert home.question_headings
    assert home.question_answer_pairs >= 2
    assert home.schema_types and "Organization" in home.schema_types
    assert home.faq_like_sections >= 1
    assert home.authoritative_citations


def test_detects_broken_internal_links(site, allow_private):
    base_routes = {
        "/": (200, {"Content-Type": "text/html"}, (
            "<html lang='en'><head><title>Broken link site</title></head><body><h1>Home</h1>"
            "<p>Some content here for the crawler to read and analyse properly.</p>"
            "<a href='/gone'>gone</a><a href='/server-error'>err</a><a href='/ok'>ok</a></body></html>"
        ).encode()),
        "/ok": (200, {"Content-Type": "text/html"}, "<html><head><title>OK</title></head><body><h1>OK</h1></body></html>".encode()),
        "/server-error": (500, {"Content-Type": "text/html"}, b"<html><body>boom</body></html>"),
    }
    site.set_routes(base_routes)
    result = crawl(site.base_url + "/", max_pages=4)
    broken_urls = {entry["url"] for entry in result.broken_links}
    assert any(u.endswith("/gone") for u in broken_urls), result.broken_links
    assert any(u.endswith("/server-error") for u in broken_urls), result.broken_links
    assert not any(u.endswith("/ok") for u in broken_urls)


def test_respects_robots_disallow(site, allow_private):
    site.set_routes({
        "/robots.txt": (200, {"Content-Type": "text/plain"}, b"User-agent: *\nDisallow: /private\n"),
        "/": (200, {"Content-Type": "text/html"}, (
            "<html><head><title>Robots site</title></head><body><h1>Home</h1>"
            "<a href='/private/page'>private</a><a href='/public'>public</a></body></html>"
        ).encode()),
        "/public": (200, {"Content-Type": "text/html"}, b"<html><head><title>Public</title></head><body><h1>Public</h1></body></html>"),
        "/private/page": (200, {"Content-Type": "text/html"}, b"<html><head><title>Private</title></head><body><h1>Private</h1></body></html>"),
    })
    result = crawl(site.base_url + "/", max_pages=5)
    crawled = {p.url for p in result.pages}
    assert not any("private" in url for url in crawled), crawled
    assert any(url.endswith("/public") for url in crawled)
    assert any("disallowed by robots.txt" in note for note in result.notes)


def test_site_blocking_everything_is_flagged(site, allow_private):
    site.set_routes({
        "/robots.txt": (200, {"Content-Type": "text/plain"}, b"User-agent: *\nDisallow: /\n"),
        "/": (200, {"Content-Type": "text/html"}, b"<html><head><title>Blocked</title></head><body><h1>Blocked</h1><a href='/a'>a</a></body></html>"),
    })
    result = crawl(site.base_url + "/", max_pages=3)
    assert result.robots.blocks_all is True
    assert len(result.pages) == 1  # homepage fetched before robots is evaluated


def test_redirect_chain_is_recorded(site, allow_private):
    site.set_routes({
        "/": (301, {"Location": "{base}/step1"}, b""),
        "/step1": (302, {"Location": "{base}/step2"}, b""),
        "/step2": (200, {"Content-Type": "text/html"}, b"<html><head><title>Final page</title></head><body><h1>Final</h1></body></html>"),
    })
    result = crawl(site.base_url + "/", max_pages=1)
    home = result.pages[0]
    assert home.status == 200
    assert len(home.redirect_chain) == 2, home.redirect_chain
    assert home.url.endswith("/step2")


def test_redirect_loop_is_detected(site, allow_private):
    site.set_routes({
        "/": (301, {"Location": "{base}/loop"}, b""),
        "/loop": (301, {"Location": "{base}/"}, b""),
    })
    result = crawl(site.base_url + "/", max_pages=1)
    assert not result.pages
    assert result.errors, "a redirect loop must produce a user-facing error"


def test_server_error_homepage_fails_with_message(site, allow_private):
    site.set_routes({"/": (500, {"Content-Type": "text/html"}, b"<html><body>error</body></html>")})
    result = crawl(site.base_url + "/", max_pages=1)
    assert not result.pages
    assert result.errors
    assert "500" in result.errors[0] or "HTTP" in result.errors[0]


def test_timeout_is_handled(site, allow_private, monkeypatch):
    monkeypatch.setattr(settings, "read_timeout", 0.6, raising=False)
    site.set_routes({"/": (200, {"Content-Type": "text/html"}, b"<html><body>slow</body></html>")},
                    delays={"/": 1.5})
    result = crawl(site.base_url + "/", max_pages=1)
    assert not result.pages
    assert result.errors and "timed out" in result.errors[0].lower()


def test_non_html_content_is_skipped(site, allow_private):
    site.set_routes({
        "/": (200, {"Content-Type": "application/pdf"}, b"%PDF-1.4 not html"),
    })
    result = crawl(site.base_url + "/", max_pages=1)
    assert not result.pages
    assert result.errors


def test_parse_page_extracts_schema_and_links():
    html_doc = """
    <html lang="en"><head>
      <title>Test page</title>
      <meta name="description" content="A description for the test page that is long enough to be useful.">
      <meta name="robots" content="index, follow">
      <script type="application/ld+json">{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[]}</script>
    </head><body>
      <h1>Test</h1><h3>Skipped level</h3>
      <a href="/internal">Internal</a><a href="https://external.example/x">External</a>
      <img src="/x.png">
    </body></html>
    """
    page = parse_page(html_doc, "https://site.example/page")
    assert page.title == "Test page"
    assert "FAQPage" in page.schema_types
    assert page.heading_skips
    assert page.images_missing_alt == 1
    assert len(page.links_internal) == 1
    assert len(page.links_external) == 1
    assert page.noindex is False


def test_noindex_detection():
    page = parse_page(
        '<html><head><title>x</title><meta name="robots" content="NOINDEX,FOLLOW"></head><body><h1>x</h1></body></html>',
        "https://site.example/",
    )
    assert page.noindex is True
