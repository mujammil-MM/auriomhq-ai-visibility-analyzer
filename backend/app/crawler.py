"""Crawling engine.

Responsibilities
----------------
* Fetch HTML safely (SSRF-guarded, redirect-validated, size- and time-limited).
* Respect robots.txt (including per-agent crawl delays) and read sitemap.xml.
* Discover internal links, cap the crawl, detect broken internal links.
* Parse page-level SEO / AEO / GEO signals into :class:`PageSnapshot` objects.

The module never executes JavaScript: analysis is performed on the HTML the
server returns, exactly like a classic crawler.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import re
import time
import zlib
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup, Tag

from .config import settings
from .security import SafeTarget, UnsafeURLError, guard_fetch_url, validate_url

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
AI_CRAWLERS = {
    "GPTBot": "OpenAI / ChatGPT",
    "OAI-SearchBot": "OpenAI search",
    "ChatGPT-User": "ChatGPT browsing",
    "ClaudeBot": "Anthropic / Claude",
    "anthropic-ai": "Anthropic (legacy)",
    "PerplexityBot": "Perplexity",
    "Google-Extended": "Google Gemini training",
    "CCBot": "Common Crawl",
    "Bingbot": "Bing / Copilot",
    "Applebot-Extended": "Apple Intelligence",
    "Bytespider": "ByteDance",
    "Amazonbot": "Amazon",
    "Meta-ExternalAgent": "Meta AI",
}

SKIP_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg", ".ico", ".bmp", ".tiff",
    ".pdf", ".zip", ".rar", ".7z", ".gz", ".tar", ".mp4", ".mp3", ".wav", ".avi", ".mov",
    ".webm", ".css", ".js", ".json", ".xml", ".txt", ".woff", ".woff2", ".ttf", ".eot",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".exe", ".dmg", ".apk",
)

ARTICLE_SCHEMA_TYPES = {
    "Article", "BlogPosting", "NewsArticle", "TechArticle", "ScholarlyArticle",
    "Report", "HowTo", "FAQPage", "QAPage", "Recipe", "Course", "Product",
}
ORG_SCHEMA_TYPES = {
    "Organization", "LocalBusiness", "Corporation", "ProfessionalService", "Store",
    "Restaurant", "MedicalBusiness", "EducationalOrganization", "NGO", "OnlineBusiness",
}
PERSON_SCHEMA_TYPES = {"Person"}
WEBSITE_SCHEMA_TYPES = {"WebSite", "WebPage", "BreadcrumbList"}

QUESTION_LEAD_RE = re.compile(
    r"^\s*(what|why|how|who|when|where|which|can|could|does|do|is|are|will|should|"
    r"was|were|may|might|has|have|did|am)\b",
    re.IGNORECASE,
)
DEFINITION_RE = re.compile(
    r"\b(is|are|refers to|means|describes|is defined as|is a|is an|stands for)\b", re.IGNORECASE
)
DATE_META_KEYS = (
    "article:published_time", "article:modified_time", "og:updated_time",
    "datePublished", "dateModified", "last-modified", "pubdate", "publish-date",
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int | None
    ok: bool
    content_type: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    text: str = ""
    error: str | None = None
    redirect_chain: list[str] = field(default_factory=list)
    truncated: bool = False
    elapsed_ms: int = 0


@dataclass
class LinkRef:
    url: str
    anchor: str = ""
    rel: str = ""
    nofollow: bool = False


@dataclass
class PageSnapshot:
    url: str
    final_url: str
    status: int | None = None
    ok: bool = False
    error: str | None = None
    redirect_chain: list[str] = field(default_factory=list)
    http_headers: dict[str, str] = field(default_factory=dict)
    x_robots_tag: str = ""

    title: str = ""
    meta_description: str = ""
    canonical: str = ""
    robots_meta: list[str] = field(default_factory=list)
    viewport: str = ""
    lang: str = ""
    charset: str = ""
    favicon: bool = False
    og_tags: dict[str, str] = field(default_factory=dict)
    twitter_tags: dict[str, str] = field(default_factory=dict)

    headings: list[dict[str, Any]] = field(default_factory=list)
    h1s: list[str] = field(default_factory=list)
    h2s: list[str] = field(default_factory=list)
    h3s: list[str] = field(default_factory=list)
    heading_skips: list[str] = field(default_factory=list)

    images_total: int = 0
    images_missing_alt: int = 0
    missing_alt_samples: list[str] = field(default_factory=list)
    has_picture_or_srcset: bool = False

    links_internal: list[LinkRef] = field(default_factory=list)
    links_external: list[LinkRef] = field(default_factory=list)
    authoritative_citations: list[str] = field(default_factory=list)
    generic_anchors: int = 0

    jsonld_blocks: list[str] = field(default_factory=list)
    schema_types: list[str] = field(default_factory=list)
    schema_nodes: list[dict[str, Any]] = field(default_factory=list)
    schema_errors: list[str] = field(default_factory=list)
    has_microdata: bool = False

    text: str = ""
    word_count: int = 0
    html_bytes: int = 0
    text_html_ratio: float = 0.0
    paragraphs: list[str] = field(default_factory=list)
    avg_sentence_words: float = 0.0
    list_items: int = 0
    has_ordered_list: bool = False
    has_table: bool = False
    has_definition_list: bool = False

    question_headings: list[str] = field(default_factory=list)
    question_answer_pairs: int = 0
    answer_examples: list[str] = field(default_factory=list)
    faq_like_sections: int = 0
    has_summary_block: bool = False
    step_like_sections: int = 0
    definition_sentences: int = 0

    author_meta: str = ""
    author_schema: str = ""
    published_date: str = ""
    modified_date: str = ""
    semantic_tags: list[str] = field(default_factory=list)
    email_addresses: list[str] = field(default_factory=list)
    phone_numbers: list[str] = field(default_factory=list)
    has_address_signal: bool = False

    @property
    def noindex(self) -> bool:
        tokens = {t.strip().lower() for t in self.robots_meta}
        tokens.update(t.strip().lower() for t in self.x_robots_tag.split(","))
        return "noindex" in tokens or "none" in tokens

    @property
    def schema_type_set(self) -> set[str]:
        return set(self.schema_types)


@dataclass
class RobotsInfo:
    available: bool = False
    url: str = ""
    status: int | None = None
    raw: str = ""
    error: str | None = None
    groups: dict[str, list[tuple[bool, str]]] = field(default_factory=dict)
    sitemaps: list[str] = field(default_factory=list)
    crawl_delay: float = 0.0
    blocks_all: bool = False
    blocked_paths: list[str] = field(default_factory=list)
    ai_access: dict[str, dict[str, Any]] = field(default_factory=dict)

    def allows(self, user_agent: str, path: str) -> bool:
        return _robots_allows(self.groups, user_agent, path)


@dataclass
class SitemapInfo:
    available: bool = False
    url: str = ""
    urls: list[str] = field(default_factory=list)
    sitemap_count: int = 0
    error: str | None = None
    status: int | None = None


@dataclass
class CrawlResult:
    start_url: str
    final_url: str
    pages: list[PageSnapshot] = field(default_factory=list)
    robots: RobotsInfo = field(default_factory=RobotsInfo)
    sitemap: SitemapInfo = field(default_factory=SitemapInfo)
    broken_links: list[dict[str, Any]] = field(default_factory=list)
    inaccessible_pages: list[dict[str, Any]] = field(default_factory=list)
    discovered_internal_links: int = 0
    llms_txt: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: int = 0
    https_available: bool | None = None
    http_to_https_redirect: bool | None = None
    homepage_status: int | None = None

    @property
    def home(self) -> PageSnapshot | None:
        return next((p for p in self.pages if p.url == self.start_url), self.pages[0] if self.pages else None)

    @property
    def host(self) -> str:
        return (urlsplit(self.final_url).hostname or "").lower()


# ---------------------------------------------------------------------------
# robots.txt handling
# ---------------------------------------------------------------------------
def parse_robots(text: str) -> tuple[dict[str, list[tuple[bool, str]]], list[str], float]:
    groups: dict[str, list[tuple[bool, str]]] = {}
    sitemaps: list[str] = []
    crawl_delay = 0.0
    agents: list[str] = []
    in_agent_block = False
    pending_rules: list[tuple[bool, str]] = []

    def flush() -> None:
        nonlocal agents, pending_rules, crawl_delay
        for agent in agents:
            groups.setdefault(agent, []).extend(pending_rules)
        agents, pending_rules = [], []

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            if not in_agent_block:
                flush()
                in_agent_block = True
            agents.append(value.lower())
        elif key in {"allow", "disallow"}:
            in_agent_block = False
            if value:
                pending_rules.append((key == "allow", value))
        elif key == "sitemap":
            if value:
                sitemaps.append(value)
        elif key == "crawl-delay":
            try:
                crawl_delay = max(crawl_delay, float(value))
            except ValueError:
                pass
    flush()
    return groups, sitemaps, crawl_delay


def _robots_allows(groups: dict[str, list[tuple[bool, str]]], user_agent: str, path: str) -> bool:
    ua = user_agent.lower()
    rules: list[tuple[bool, str]] = []
    matched_specific = False
    for agent, agent_rules in groups.items():
        if agent == "*":
            continue
        if agent and agent in ua:
            rules.extend(agent_rules)
            matched_specific = True
    if not matched_specific:
        rules.extend(groups.get("*", []))
    if not rules:
        return True
    best_len = -1
    allowed = True
    for allow, rule_path in rules:
        if not rule_path:
            continue
        pattern = re.escape(rule_path).replace(r"\*", ".*")
        if re.match(pattern, path):
            specificity = len(rule_path)
            if specificity > best_len or (specificity == best_len and allow):
                best_len = specificity
                allowed = allow
    return allowed


# ---------------------------------------------------------------------------
# HTTP fetcher
# ---------------------------------------------------------------------------
class Fetcher:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._host_lock = asyncio.Lock()
        self._host_last_request: dict[str, float] = {}

    async def __aenter__(self) -> "Fetcher":
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=settings.connect_timeout,
                read=settings.read_timeout,
                write=settings.read_timeout,
                pool=settings.read_timeout,
            ),
            follow_redirects=False,
            trust_env=False,
            http2=False,
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "close",
            },
        )
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _polite_wait(self, host: str, crawl_delay: float) -> None:
        delay = max(settings.per_host_delay, crawl_delay)
        if delay <= 0:
            return
        async with self._host_lock:
            last = self._host_last_request.get(host, 0.0)
            wait = delay - (time.monotonic() - last)
            if wait > 0:
                await asyncio.sleep(min(wait, 5.0))
            self._host_last_request[host] = time.monotonic()

    async def fetch(
        self,
        url: str,
        *,
        max_redirects: int | None = None,
        crawl_delay: float = 0.0,
        allow_html_only: bool = True,
    ) -> FetchResult:
        started = time.monotonic()
        chain: list[str] = []
        current = url
        max_redirects = settings.max_redirects if max_redirects is None else max_redirects
        assert self._client is not None

        for hop in range(max_redirects + 1):
            try:
                target: SafeTarget = await guard_fetch_url(current)
            except UnsafeURLError as exc:
                return FetchResult(url=url, final_url=current, status=None, ok=False,
                                   error=str(exc), redirect_chain=chain,
                                   elapsed_ms=int((time.monotonic() - started) * 1000))
            await self._polite_wait(target.host, crawl_delay)

            result = await self._single_request(target, allow_html_only=allow_html_only)
            if not result.ok and result.error and "redirect" not in (result.error or "").lower():
                result.url = url
                result.redirect_chain = chain
                result.elapsed_ms = int((time.monotonic() - started) * 1000)
                return result

            if result.status in {301, 302, 303, 307, 308}:
                location = result.headers.get("location", "")
                if not location:
                    result.ok = False
                    result.error = "Redirect response without a Location header."
                    return result
                nxt = urljoin(current, location)
                chain.append(current)
                if len(chain) > max_redirects:
                    return FetchResult(url=url, final_url=current, status=result.status, ok=False,
                                       error=f"Too many redirects (>{max_redirects}).",
                                       redirect_chain=chain,
                                       elapsed_ms=int((time.monotonic() - started) * 1000))
                if nxt in chain:
                    return FetchResult(url=url, final_url=current, status=result.status, ok=False,
                                       error="Redirect loop detected.", redirect_chain=chain,
                                       elapsed_ms=int((time.monotonic() - started) * 1000))
                current = nxt
                continue

            result.url = url
            result.redirect_chain = chain
            result.elapsed_ms = int((time.monotonic() - started) * 1000)
            return result

        return FetchResult(url=url, final_url=current, status=None, ok=False,
                           error="Redirect limit exceeded.", redirect_chain=chain,
                           elapsed_ms=int((time.monotonic() - started) * 1000))

    async def _single_request(self, target: SafeTarget, *, allow_html_only: bool) -> FetchResult:
        assert self._client is not None
        last_error: str | None = None
        for ip in target.ips[:3]:
            try:
                async with self._client.stream(
                    "GET",
                    target.connect_url(ip),
                    headers={"Host": target.host_header},
                    extensions={"sni_hostname": target.host},
                ) as response:
                    headers = {k.lower(): v for k, v in response.headers.items()}
                    status = response.status_code
                    content_type = headers.get("content-type", "")
                    if status in {301, 302, 303, 307, 308}:
                        return FetchResult(url=target.url, final_url=target.url, status=status,
                                           ok=True, content_type=content_type, headers=headers)
                    if allow_html_only and content_type and not any(
                        t in content_type.lower() for t in ("text/html", "application/xhtml", "text/plain")
                    ):
                        return FetchResult(url=target.url, final_url=target.url, status=status,
                                           ok=False, content_type=content_type, headers=headers,
                                           error=f"Skipped: non-HTML content type ({content_type.split(';')[0]}).")
                    buffer = bytearray()
                    truncated = False
                    async for chunk in response.aiter_bytes():
                        buffer.extend(chunk)
                        if len(buffer) > settings.max_response_bytes:
                            truncated = True
                            break
                    raw = bytes(buffer)
                    encoding = headers.get("content-encoding", "").lower()
                    if encoding == "gzip" or raw[:2] == b"\x1f\x8b":
                        try:
                            raw = gzip.decompress(raw)
                        except OSError:
                            pass
                    elif encoding == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except zlib.error:
                            pass
                    charset = _charset_from(content_type, raw)
                    try:
                        text = raw.decode(charset, errors="replace")
                    except (LookupError, UnicodeDecodeError):
                        text = raw.decode("utf-8", errors="replace")
                    return FetchResult(
                        url=target.url, final_url=target.url, status=status,
                        ok=200 <= status < 300, content_type=content_type, headers=headers,
                        body=raw[: settings.max_response_bytes], text=text, truncated=truncated,
                        error=None if 200 <= status < 300 else f"HTTP {status} response.",
                    )
            except httpx.TimeoutException:
                last_error = "The request timed out before the server responded."
            except httpx.HTTPError as exc:
                last_error = f"Connection failed ({type(exc).__name__})."
        return FetchResult(url=target.url, final_url=target.url, status=None, ok=False,
                           error=last_error or "Could not connect to the server.")


def _charset_from(content_type: str, raw: bytes) -> str:
    match = re.search(r"charset=([\w\-]+)", content_type or "", re.IGNORECASE)
    if match:
        return match.group(1)
    head = raw[:2048].decode("ascii", errors="ignore")
    match = re.search(r'charset=["\']?([\w\-]+)', head, re.IGNORECASE)
    return match.group(1) if match else "utf-8"


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------
def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_page(html: str, url: str) -> PageSnapshot:
    soup = BeautifulSoup(html, "lxml")
    page = PageSnapshot(url=url, final_url=url, ok=True, html_bytes=len(html.encode("utf-8", "ignore")))

    title_tag = soup.find("title")
    page.title = _clean(title_tag.get_text() if title_tag else "")

    for meta in soup.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or meta.get("itemprop") or "").lower().strip()
        content = meta.get("content") or ""
        if name == "description" and not page.meta_description:
            page.meta_description = _clean(content)
        elif name in {"viewport", "viewport-fit"}:
            page.viewport = page.viewport or _clean(content)
        elif name in {"robots", "googlebot", "bingbot"}:
            page.robots_meta.extend(t.strip().lower() for t in content.split(",") if t.strip())
        elif name.startswith("og:"):
            page.og_tags[name] = _clean(content)
        elif name.startswith("twitter:"):
            page.twitter_tags[name] = _clean(content)
        elif name == "author":
            page.author_meta = page.author_meta or _clean(content)
        elif name in DATE_META_KEYS:
            if not page.published_date:
                page.published_date = _clean(content)
        elif name in {"article:modified_time", "og:updated_time"}:
            page.modified_date = _clean(content)
        elif name == "charset":
            page.charset = _clean(content)

    html_tag = soup.find("html")
    if html_tag is not None:
        page.lang = _clean(html_tag.get("lang") or html_tag.get("xml:lang") or "")

    link_tags = soup.find_all("link")
    for link in link_tags:
        rel = " ".join(link.get("rel") or []).lower()
        if "canonical" in rel and not page.canonical:
            page.canonical = _clean(link.get("href"))
        if "icon" in rel or "shortcut icon" in rel:
            page.favicon = True
        if "author" in rel and not page.author_meta:
            page.author_meta = _clean(link.get("href"))

    # headings
    for level in range(1, 7):
        for tag in soup.find_all(f"h{level}"):
            text = _clean(tag.get_text())
            if not text:
                continue
            page.headings.append({"level": level, "text": text[:240]})
            if level == 1:
                page.h1s.append(text[:240])
            elif level == 2:
                page.h2s.append(text[:240])
            elif level == 3:
                page.h3s.append(text[:240])
    prev_level = 0
    for heading in page.headings:
        if prev_level and heading["level"] - prev_level > 1:
            page.heading_skips.append(f"H{prev_level} → H{heading['level']} before “{heading['text'][:60]}”")
        prev_level = heading["level"]

    # images
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src and not img.get("srcset"):
            continue
        page.images_total += 1
        alt = img.get("alt")
        if alt is None or not alt.strip():
            page.images_missing_alt += 1
            if len(page.missing_alt_samples) < 5:
                page.missing_alt_samples.append(_clean(src)[:140] or "(inline image)")
        if img.get("srcset") or img.parent and getattr(img.parent, "name", "") == "picture":
            page.has_picture_or_srcset = True
    if soup.find("picture") is not None:
        page.has_picture_or_srcset = True

    # links
    generic_anchor_words = {"click here", "here", "read more", "more", "learn more", "link", "this", "website"}
    for a in soup.find_all("a", href=True):
        href = _clean(a.get("href"))
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        absolute = urljoin(url, href)
        scheme = urlsplit(absolute).scheme.lower()
        if scheme not in {"http", "https"}:
            continue
        anchor = _clean(a.get_text())[:160]
        rel = _clean(" ".join(a.get("rel") or []))
        ref = LinkRef(url=absolute, anchor=anchor, rel=rel, nofollow="nofollow" in rel.lower())
        if anchor.lower().strip(" .!?→>") in generic_anchor_words:
            page.generic_anchors += 1
        if _same_site(absolute, url):
            page.links_internal.append(ref)
        else:
            page.links_external.append(ref)

    authoritative_tlds = (".gov", ".edu", ".gov.uk", ".ac.uk", ".who.int", ".europa.eu", ".org")
    auth_domains = (
        "wikipedia.org", "who.int", "cdc.gov", "nih.gov", "europa.eu", "un.org",
        "nature.com", "sciencedirect.com", "ieee.org", "acm.org", "statista.com",
        "gartner.com", "mckinsey.com", "harvard.edu", "mit.edu", "stanford.edu", "oecd.org",
    )
    for ref in page.links_external:
        host = (urlsplit(ref.url).hostname or "").lower()
        if host.endswith(authoritative_tlds) or any(host == d or host.endswith("." + d) for d in auth_domains):
            if host not in page.authoritative_citations:
                page.authoritative_citations.append(host)

    # structured data
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        if len(raw) > 20000:
            raw = raw[:20000]
        page.jsonld_blocks.append(raw)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            page.schema_errors.append(f"Invalid JSON-LD: {exc.msg} (line {exc.lineno})")
            continue
        for node in _iter_schema_nodes(data):
            page.schema_nodes.append(node)
            for type_name in _node_types(node):
                if type_name not in page.schema_types:
                    page.schema_types.append(type_name)
            if _node_types(node) & PERSON_SCHEMA_TYPES:
                author = node.get("name") or ""
                if author and not page.author_schema:
                    page.author_schema = _clean(author)[:120]
            for key in ("datePublished", "dateModified", "dateCreated"):
                value = node.get(key)
                if isinstance(value, str) and value:
                    if key == "datePublished" and not page.published_date:
                        page.published_date = value[:40]
                    if key == "dateModified":
                        page.modified_date = page.modified_date or value[:40]
    page.has_microdata = soup.find(attrs={"itemscope": True}) is not None

    # visible text
    body = soup.find("body") or soup
    for tag in body.find_all(["script", "style", "noscript", "template", "svg", "iframe"]):
        tag.decompose()
    page.paragraphs = [_clean(p.get_text()) for p in body.find_all("p") if _clean(p.get_text())]
    page.paragraphs = [p for p in page.paragraphs if len(p) > 30]
    text = _clean(body.get_text(" "))
    page.text = text[:40_000]
    page.word_count = len(re.findall(r"[A-Za-z0-9’'\-]+", page.text))
    if page.html_bytes:
        page.text_html_ratio = round(min(1.0, len(text) / page.html_bytes), 3)

    sentences = [s for s in re.split(r"[.!?]+\s+", " ".join(page.paragraphs[:120])) if len(s) > 15]
    if sentences:
        page.avg_sentence_words = round(
            sum(len(re.findall(r"\w+", s)) for s in sentences) / len(sentences), 1
        )
    page.definition_sentences = sum(
        1 for p in page.paragraphs[:80] if DEFINITION_RE.search(p[:160]) and len(p.split()) < 80
    )

    # lists / tables
    page.list_items = len(body.find_all("li"))
    page.has_ordered_list = body.find("ol") is not None
    page.has_table = body.find("table") is not None
    page.has_definition_list = body.find("dl") is not None

    # question-style headings & FAQ heuristics
    page.question_headings = [
        h["text"] for h in page.headings
        if h["text"].endswith("?") or QUESTION_LEAD_RE.match(h["text"])
    ][:25]
    faq_heading_re = re.compile(r"\b(faq|frequently asked|questions|q\s*&\s*a|help centre|help center)\b", re.IGNORECASE)
    for tag in body.find_all(["section", "div", "h1", "h2", "h3", "article"]):
        label = _clean(tag.get("aria-label") or tag.get("id") or " ".join(tag.get("class") or []))
        if "faq" in label.lower() or (tag.name in {"h2", "h3"} and faq_heading_re.search(tag.get_text())):
            page.faq_like_sections += 1
    page.faq_like_sections = min(page.faq_like_sections, 6)
    if body.find(["details", "summary"]) is not None:
        page.faq_like_sections = max(page.faq_like_sections, 1)

    step_re = re.compile(r"\b(step\s*\d|how to|how it works|process|getting started|instructions)\b", re.IGNORECASE)
    page.step_like_sections = sum(
        1 for tag in body.find_all(["h2", "h3", "section"]) if step_re.search(tag.get_text()[:160])
    )
    page.step_like_sections = min(page.step_like_sections, 6)

    summary_re = re.compile(r"\b(tl;?dr|in short|summary|key takeaways|quick answer|the short answer)\b", re.IGNORECASE)
    page.has_summary_block = any(
        summary_re.search(_clean(tag.get_text()[:200])) for tag in body.find_all(["h2", "h3", "p", "div", "aside", "blockquote"])[:400]
    )

    # entity / contact signals
    page.semantic_tags = sorted({t.name for t in body.find_all(["article", "main", "header", "nav", "footer", "aside", "section"])})
    page.email_addresses = list(dict.fromkeys(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)))[:3]
    phone_candidates = re.findall(r"(?:\+\d{1,3}[\s-]?)?(?:\(\d{2,4}\)[\s-]?)?\d{3,5}[\s-]\d{3,4}(?:[\s-]\d{2,4})?", text)
    page.phone_numbers = [c for c in dict.fromkeys(phone_candidates) if sum(ch.isdigit() for ch in c) >= 8][:3]
    page.has_address_signal = soup.find(attrs={"itemtype": re.compile("PostalAddress")}) is not None or bool(
        re.search(r"\b(street|suite|floor|road|avenue|pin\s*code|zip|postal code)\b", text[:6000], re.IGNORECASE)
    )
    # question heading -> immediate answer paragraph
    for heading in body.find_all(["h2", "h3", "h4"]):
        label = _clean(heading.get_text())
        if not (label.endswith("?") or QUESTION_LEAD_RE.match(label)):
            continue
        sibling = heading.find_next_sibling()
        hops = 0
        while sibling is not None and hops < 3:
            if getattr(sibling, "name", None) in {"p", "div", "span"}:
                answer = _clean(sibling.get_text())
                words = len(answer.split())
                if 25 <= words <= 120:
                    page.question_answer_pairs += 1
                    if len(page.answer_examples) < 3:
                        page.answer_examples.append(answer[:220])
                break
            if getattr(sibling, "name", None) in {"h1", "h2", "h3", "h4", "h5", "ul", "ol", "table"}:
                break
            sibling = sibling.find_next_sibling()
            hops += 1

    if not page.published_date:
        time_tag = body.find("time")
        if time_tag is not None:
            page.published_date = _clean(time_tag.get("datetime") or time_tag.get_text())[:40]
    return page


def _iter_schema_nodes(data: Any) -> Iterable[dict[str, Any]]:
    if isinstance(data, dict):
        yield data
        graph = data.get("@graph")
        if isinstance(graph, list):
            for node in graph:
                if isinstance(node, dict):
                    yield node
        for value in data.values():
            if isinstance(value, (dict, list)) and value is not data.get("@graph"):
                yield from _iter_schema_nodes(value)
    elif isinstance(data, list):
        for item in data:
            yield from _iter_schema_nodes(item)


def _node_types(node: dict[str, Any]) -> set[str]:
    raw = node.get("@type") or node.get("type") or ""
    if isinstance(raw, str):
        types = {raw}
    elif isinstance(raw, list):
        types = {t for t in raw if isinstance(t, str)}
    else:
        types = set()
    return {t.split("/")[-1].split(":")[-1] for t in types if isinstance(t, str) and t.strip()}


def _same_site(url_a: str, url_b: str) -> bool:
    host_a = (urlsplit(url_a).hostname or "").lower().lstrip("www.")
    host_b = (urlsplit(url_b).hostname or "").lower().lstrip("www.")
    if not host_a or not host_b:
        return False
    return host_a == host_b or host_a.endswith("." + host_b) or host_b.endswith("." + host_a)


def _normalise_link(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def is_crawlable_url(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"}:
        return False
    path = parts.path.lower()
    if path.endswith(SKIP_EXTENSIONS):
        return False
    if any(path.endswith(ext) for ext in (".jpg", ".png", ".gif", ".svg", ".webp", ".pdf")):
        return False
    return True


def score_candidate(url: str, anchor: str) -> int:
    """Heuristic ranking for crawl priority (higher = crawl sooner)."""
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    score = 0
    depth = len([s for s in path.split("/") if s])
    score += max(0, 10 - depth * 3)
    if path == "/":
        score += 20
    for keyword in ("about", "services", "service", "pricing", "contact", "faq", "product", "solutions", "company", "team", "blog"):
        if keyword in path.lower():
            score += 4
    if parts.query:
        score -= 6
    if len(anchor) > 3:
        score += 1
    return score


# ---------------------------------------------------------------------------
# Crawl orchestration
# ---------------------------------------------------------------------------
class Crawler:
    def __init__(self, max_pages: int | None = None) -> None:
        requested = max_pages or settings.max_pages
        self.max_pages = max(1, min(requested, settings.max_pages_hard_limit))

    async def crawl(self, start_url: str, progress: Any = None) -> CrawlResult:
        started = time.monotonic()
        result = CrawlResult(start_url=start_url, final_url=start_url)

        deadline = started + settings.total_timeout
        async with Fetcher() as fetcher:
            await _notify(progress, "connecting", "Checking the website is reachable", 5)
            home_fetch = await fetcher.fetch(start_url)
            if home_fetch.status is None or not (home_fetch.ok and home_fetch.text):
                reason = home_fetch.error or "The website did not return a usable HTML response."
                result.errors.append(reason)
                result.inaccessible_pages.append({
                    "url": start_url, "status": home_fetch.status, "error": reason,
                })
                result.final_url = home_fetch.final_url or start_url
                result.duration_ms = int((time.monotonic() - started) * 1000)
                return result

            final_url = home_fetch.final_url
            result.final_url = final_url
            result.homepage_status = home_fetch.status

            # robots.txt
            await _notify(progress, "robots", "Reading robots.txt and crawl rules", 12)
            robots = await self._load_robots(fetcher, final_url)
            result.robots = robots
            crawl_delay = robots.crawl_delay

            # HTTPS availability
            result.https_available = final_url.lower().startswith("https://")
            if result.https_available:
                http_url = "http://" + final_url[len("https://"):]
                http_probe = await fetcher.fetch(http_url, max_redirects=2, allow_html_only=True)
                result.http_to_https_redirect = bool(
                    http_probe.redirect_chain
                    and urljoin(http_url, http_probe.headers.get("location", "")).lower().startswith("https://")
                ) or http_probe.final_url.lower().startswith("https://")

            # homepage snapshot
            home_page = parse_page(home_fetch.text, final_url)
            home_page.status = home_fetch.status
            home_page.final_url = final_url
            home_page.redirect_chain = home_fetch.redirect_chain
            home_page.http_headers = home_fetch.headers
            home_page.x_robots_tag = home_fetch.headers.get("x-robots-tag", "")
            result.pages.append(home_page)

            # sitemap + llms.txt
            await _notify(progress, "sitemap", "Inspecting sitemap.xml and llms.txt", 20)
            result.sitemap = await self._load_sitemap(fetcher, final_url, robots)
            result.llms_txt = await self._load_llms_txt(fetcher, final_url)

            # discovery
            await _notify(progress, "discover", "Discovering internal pages", 26)
            queue: deque[tuple[int, str, str]] = deque()
            seen = {_normalise_link(final_url), _normalise_link(start_url)}
            if home_fetch.redirect_chain:
                for hop in home_fetch.redirect_chain:
                    seen.add(_normalise_link(hop))

            def enqueue(refs: Iterable[LinkRef]) -> None:
                for ref in refs:
                    norm = _normalise_link(ref.url)
                    if norm in seen or not is_crawlable_url(ref.url):
                        continue
                    if not _same_site(ref.url, final_url):
                        continue
                    seen.add(norm)
                    queue.append((score_candidate(ref.url, ref.anchor), ref.url, ref.anchor))

            enqueue(home_page.links_internal)
            sitemap_urls = [u for u in result.sitemap.urls if _same_site(u, final_url) and is_crawlable_url(u)]
            for sitemap_url in sitemap_urls[: self.max_pages * 3]:
                norm = _normalise_link(sitemap_url)
                if norm in seen:
                    continue
                seen.add(norm)
                queue.append((score_candidate(sitemap_url, ""), sitemap_url, ""))

            result.discovered_internal_links = len(queue) + len(home_page.links_internal)

            # crawl queue
            while queue and len(result.pages) < self.max_pages and time.monotonic() < deadline:
                ranked = sorted(queue, key=lambda item: item[0], reverse=True)
                queue = deque(ranked)
                _, next_url, _anchor = queue.popleft()
                if not robots.allows(settings.user_agent, urlsplit(next_url).path or "/"):
                    result.notes.append(f"Skipped {next_url} — disallowed by robots.txt.")
                    continue
                if robots.blocks_all:
                    result.notes.append("robots.txt disallows all crawling for this user agent; stopping.")
                    break
                index = len(result.pages)
                await _notify(
                    progress, "crawl", f"Analysing page {index + 1} of up to {self.max_pages}",
                    30 + int(45 * (index / self.max_pages)), detail=next_url,
                )
                fetch = await fetcher.fetch(next_url, crawl_delay=crawl_delay)
                if not fetch.ok or not fetch.text:
                    entry = {"url": next_url, "status": fetch.status, "error": fetch.error or "No content returned."}
                    if fetch.status is None:
                        result.inaccessible_pages.append(entry)
                    else:
                        result.broken_links.append({**entry, "found_on": final_url, "type": "crawl_failure"})
                    continue
                page = parse_page(fetch.text, next_url)
                page.status = fetch.status
                page.final_url = fetch.final_url
                page.redirect_chain = fetch.redirect_chain
                page.http_headers = fetch.headers
                page.x_robots_tag = fetch.headers.get("x-robots-tag", "")
                result.pages.append(page)
                enqueue(page.links_internal)

            # broken link verification (uncrawled internal links)
            await _notify(progress, "links", "Verifying internal links", 78)
            result.broken_links.extend(await self._check_links(fetcher, result, deadline, progress))

        result.duration_ms = int((time.monotonic() - started) * 1000)
        await _notify(progress, "analyse", "Running SEO, AEO and GEO analysis", 88)
        return result

    async def _load_robots(self, fetcher: Fetcher, base_url: str) -> RobotsInfo:
        parts = urlsplit(base_url)
        robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
        info = RobotsInfo(url=robots_url)
        fetch = await fetcher.fetch(robots_url, allow_html_only=False)
        info.status = fetch.status
        if not fetch.ok or not fetch.text:
            info.error = fetch.error or "robots.txt not available."
            # Absence of robots.txt means crawling is allowed by default
            info.blocks_all = False
            return info
        info.available = True
        info.raw = fetch.text[:20000]
        groups, sitemaps, delay = parse_robots(info.raw)
        info.groups = groups
        info.sitemaps = sitemaps
        info.crawl_delay = delay
        paths = [p for rules in groups.values() for allow, p in rules if not allow]
        info.blocked_paths = list(dict.fromkeys(paths))[:15]
        info.blocks_all = bool(
            not info.allows(settings.user_agent, "/")
            and not info.allows(settings.user_agent, "/index.html")
        )
        for bot, label in AI_CRAWLERS.items():
            rules = []
            matched = False
            for agent, agent_rules in groups.items():
                if agent != "*" and agent in bot.lower():
                    rules.extend(agent_rules)
                    matched = True
            if not matched:
                rules = groups.get("*", [])
            blocked = [
                {"path": path, "type": "disallow" if not allow else "allow"}
                for allow, path in rules if not allow and path
            ]
            allowed_root = info.allows(bot, "/")
            info.ai_access[bot] = {
                "label": label,
                "explicitly_listed": matched,
                "allowed": allowed_root,
                "blocked_paths": blocked[:6],
            }
        return info

    async def _load_sitemap(self, fetcher: Fetcher, base_url: str, robots: RobotsInfo) -> SitemapInfo:
        parts = urlsplit(base_url)
        candidates = list(robots.sitemaps)
        for default_path in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
            candidates.append(urlunsplit((parts.scheme, parts.netloc, default_path, "", "")))
        info = SitemapInfo()
        for candidate in dict.fromkeys(candidates):
            fetch = await fetcher.fetch(candidate, allow_html_only=False)
            if not fetch.ok or not fetch.text:
                info.error = info.error or (fetch.error or "Sitemep not available.")
                continue
            text = fetch.text
            if "<" not in text[:200].lower() and "<urlset" not in text.lower() and "<sitemapindex" not in text.lower():
                continue
            info.available = True
            info.url = candidate
            info.status = fetch.status
            urls, sitemaps = _parse_sitemap_xml(text, candidate)
            info.urls = urls
            info.sitemap_count = len(sitemaps)
            # follow child sitemaps (one level) if the index itself has no page URLs
            if not urls and sitemaps:
                for child in sitemaps[:3]:
                    child_fetch = await fetcher.fetch(child, allow_html_only=False)
                    if child_fetch.ok and child_fetch.text:
                        child_urls, _ = _parse_sitemap_xml(child_fetch.text, child)
                        info.urls.extend(child_urls)
                        if len(info.urls) >= 500:
                            break
            info.urls = list(dict.fromkeys(info.urls))[:500]
            return info
        return info

    async def _load_llms_txt(self, fetcher: Fetcher, base_url: str) -> dict[str, Any]:
        parts = urlsplit(base_url)
        url = urlunsplit((parts.scheme, parts.netloc, "/llms.txt", "", ""))
        fetch = await fetcher.fetch(url, allow_html_only=False)
        if fetch.ok and fetch.text and "html" not in (fetch.content_type or "").lower():
            snippet = _clean(fetch.text)[:600]
            looks_valid = "#" in fetch.text[:400] or ">" in fetch.text[:400]
            return {"available": looks_valid, "url": url, "status": fetch.status, "snippet": snippet}
        return {"available": False, "url": url, "status": fetch.status, "snippet": ""}

    async def _check_links(
        self, fetcher: Fetcher, result: CrawlResult, deadline: float, progress: Any
    ) -> list[dict[str, Any]]:
        crawled = {_normalise_link(p.url) for p in result.pages}
        already_broken = {entry["url"] for entry in result.broken_links}
        candidates: dict[str, dict[str, Any]] = {}
        for page in result.pages:
            for ref in page.links_internal:
                norm = _normalise_link(ref.url)
                if norm in crawled or ref.url in already_broken or not is_crawlable_url(ref.url):
                    continue
                candidates.setdefault(norm, {"url": ref.url, "found_on": page.url, "anchor": ref.anchor})
        # also verify sitemap URLs that were never crawled
        for sitemap_url in result.sitemap.urls:
            norm = _normalise_link(sitemap_url)
            if norm in crawled or not is_crawlable_url(sitemap_url) or not _same_site(sitemap_url, result.final_url):
                continue
            candidates.setdefault(norm, {"url": sitemap_url, "found_on": "sitemap.xml", "anchor": ""})

        selected = list(candidates.values())[: settings.link_check_limit]
        broken: list[dict[str, Any]] = []
        if not selected:
            return broken

        semaphore = asyncio.Semaphore(4)

        async def check(entry: dict[str, Any]) -> None:
            async with semaphore:
                if time.monotonic() > deadline:
                    return
                fetch = await fetcher.fetch(entry["url"], max_redirects=3)
                status = fetch.status
                is_broken = status is None or status >= 400
                if is_broken:
                    broken.append({
                        "url": entry["url"],
                        "status": status,
                        "error": fetch.error or f"HTTP {status}",
                        "found_on": entry["found_on"],
                        "anchor": entry["anchor"][:100],
                        "type": "broken_link" if status and status >= 400 else "unreachable",
                    })

        await asyncio.gather(*(check(entry) for entry in selected), return_exceptions=True)
        await _notify(progress, "links", "Verifying internal links", 84)
        return broken


def _parse_sitemap_xml(text: str, base: str) -> tuple[list[str], list[str]]:
    urls: list[str] = []
    sitemaps: list[str] = []
    try:
        from xml.etree import ElementTree as ET

        root = ET.fromstring(text.strip())
        tag = root.tag.split("}")[-1].lower()
        for child in root:
            child_tag = child.tag.split("}")[-1].lower()
            loc = None
            for sub in child:
                if sub.tag.split("}")[-1].lower() == "loc":
                    loc = (sub.text or "").strip()
                    break
            if not loc:
                continue
            if tag == "sitemapindex" or child_tag == "sitemap":
                sitemaps.append(urljoin(base, loc))
            elif child_tag == "url":
                urls.append(urljoin(base, loc))
    except Exception:
        urls.extend(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text, re.IGNORECASE)[:500])
    return list(dict.fromkeys(urls))[:500], list(dict.fromkeys(sitemaps))[:50]


async def _notify(progress: Any, stage: str, message: str, percent: int, detail: str | None = None) -> None:
    if progress is None:
        return
    maybe = progress(stage, message, percent, detail)
    if asyncio.iscoroutine(maybe):
        await maybe
