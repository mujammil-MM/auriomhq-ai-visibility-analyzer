"""SEO analysis engine — measurable, on-page and technical signals only.

Deliberately excluded (and stated in the UI/report): keyword rankings, search
volume, backlink data, and Google index status. Those require external data
sources that this prototype does not have access to.
"""
from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlsplit

from ..crawler import CrawlResult
from .base import (
    FAIL, NOT_TESTED, PASS, WARNING, CheckSpec, Outcome, analysable_pages, average,
    home, pct, quote,
)

PILLAR = "seo"


def _pages(crawl: CrawlResult):
    return analysable_pages(crawl)


def check_https(crawl: CrawlResult) -> Outcome:
    if crawl.https_available is None:
        return Outcome(NOT_TESTED, "HTTPS availability could not be verified.")
    final = crawl.final_url
    if not crawl.https_available:
        return Outcome(FAIL, f"The homepage is served over plain HTTP ({final}).")
    if crawl.http_to_https_redirect is False:
        return Outcome(
            WARNING,
            f"HTTPS works ({final}) but the http:// version does not redirect to https://.",
            0.6,
        )
    return Outcome(PASS, f"HTTPS is available and http:// redirects to https:// ({final}).")


def check_home_status(crawl: CrawlResult) -> Outcome:
    status = crawl.homepage_status
    if status is None:
        return Outcome(FAIL, "The homepage did not return an HTTP response.")
    if 200 <= status < 300:
        return Outcome(PASS, f"The homepage returned HTTP {status}.")
    if 300 <= status < 400:
        return Outcome(WARNING, f"The homepage returned a redirect (HTTP {status}) that was followed.", 0.7)
    return Outcome(FAIL, f"The homepage returned HTTP {status}.")


def check_title(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    if not pages:
        return Outcome(NOT_TESTED, "No HTML pages were available for analysis.")
    h = home(crawl) or pages[0]
    missing = [p.url for p in pages if not p.title]
    if missing:
        return Outcome(
            FAIL,
            f"{len(missing)} of {len(pages)} analysed pages have no <title> element (e.g. {missing[0]}).",
            pages=missing,
        )
    length = len(h.title)
    if 15 <= length <= 65:
        return Outcome(PASS, f"Homepage title is {length} characters: {quote(h.title)}")
    issue = "too short" if length < 15 else "likely to be truncated in results"
    return Outcome(WARNING, f"Homepage title is {length} characters ({issue}): {quote(h.title)}", 0.6)


def check_meta_description(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    if not pages:
        return Outcome(NOT_TESTED, "No HTML pages were available for analysis.")
    h = home(crawl) or pages[0]
    missing = [p.url for p in pages if not p.meta_description]
    if not h.meta_description:
        return Outcome(FAIL, "The homepage has no meta description.", pages=["homepage"])
    if missing and len(missing) > len(pages) / 2:
        return Outcome(
            WARNING,
            f"Meta description present on the homepage ({len(h.meta_description)} characters) but missing on {len(missing)} of {len(pages)} pages.",
            0.6,
            pages=missing,
        )
    length = len(h.meta_description)
    if 70 <= length <= 165:
        return Outcome(PASS, f"Meta description is {length} characters: {quote(h.meta_description)}")
    return Outcome(
        WARNING,
        f"Meta description is {length} characters (recommended 70–165): {quote(h.meta_description)}",
        0.65,
    )


def check_canonical(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    if not pages:
        return Outcome(NOT_TESTED, "No HTML pages were available for analysis.")
    with_canonical = [p for p in pages if p.canonical]
    if not with_canonical:
        return Outcome(FAIL, f"None of the {len(pages)} analysed pages declare a canonical URL.")
    if len(with_canonical) < len(pages):
        return Outcome(
            WARNING,
            f"{len(with_canonical)} of {len(pages)} pages declare a canonical URL; missing on {len(pages) - len(with_canonical)}.",
            0.7,
        )
    h = home(crawl) or pages[0]
    if h.canonical and not h.canonical.startswith(("http://", "https://", "/")):
        return Outcome(WARNING, f"Canonical URL looks malformed: {quote(h.canonical)}", 0.5)
    return Outcome(PASS, f"All analysed pages declare a canonical URL (homepage: {quote(h.canonical, 120)}).")


def check_robots_meta(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    if not pages:
        return Outcome(NOT_TESTED, "No HTML pages were available for analysis.")
    blocked = [p.url for p in pages if p.noindex]
    if blocked:
        note = " The homepage itself is blocked." if (home(crawl) and home(crawl).noindex) else ""
        return Outcome(
            FAIL,
            f"{len(blocked)} of {len(pages)} analysed pages are marked noindex.{note}",
            pages=blocked,
        )
    return Outcome(PASS, "No noindex directives were found on the analysed pages.")


def check_robots_txt(crawl: CrawlResult) -> Outcome:
    robots = crawl.robots
    if robots.available and robots.blocks_all:
        return Outcome(FAIL, f"robots.txt ({robots.url}) disallows crawling of the whole site.")
    if robots.available:
        blocked = len(robots.blocked_paths)
        if blocked:
            return Outcome(
                PASS,
                f"robots.txt is available and allows crawling; {blocked} path rule(s) are disallowed: {', '.join(robots.blocked_paths[:4])}.",
            )
        return Outcome(PASS, f"robots.txt is available with no disallow rules ({robots.url}).")
    return Outcome(
        WARNING,
        f"No robots.txt was found (HTTP {robots.status} at {robots.url}). Crawling is allowed by default, but the file gives no sitemap or crawl guidance.",
        0.5,
    )


def check_sitemap(crawl: CrawlResult) -> Outcome:
    sitemap = crawl.sitemap
    if not sitemap.available:
        return Outcome(FAIL, sitemap.error or "No XML sitemap could be found or parsed.")
    count = len(sitemap.urls)
    if count == 0:
        return Outcome(WARNING, f"A sitemap exists at {sitemap.url} but contains no page URLs we could parse.", 0.4)
    sample = ", ".join(urlsplit(u).path or "/" for u in sitemap.urls[:3])
    if count == 1:
        return Outcome(WARNING, f"The sitemap lists only 1 URL ({sitemap.url}).", 0.6)
    return Outcome(PASS, f"The sitemap at {sitemap.url} lists {count} URLs (e.g. {sample}).")


def check_viewport(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    if not pages:
        return Outcome(NOT_TESTED, "No HTML pages were available for analysis.")
    missing = [p.url for p in pages if not p.viewport]
    h = home(crawl) or pages[0]
    if missing:
        return Outcome(FAIL, f"{len(missing)} of {len(pages)} analysed pages have no mobile viewport meta tag.", pages=missing)
    if "width=device-width" not in h.viewport:
        return Outcome(WARNING, f"Viewport tag found but it does not use width=device-width: {quote(h.viewport)}", 0.5)
    return Outcome(PASS, f"Mobile viewport is configured: {quote(h.viewport, 100)}")


def check_image_alt(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    total = sum(p.images_total for p in pages)
    missing = sum(p.images_missing_alt for p in pages)
    if total == 0:
        return Outcome(NOT_TESTED, "No <img> elements were found in the analysed HTML.")
    ratio = missing / total
    h = home(crawl) or pages[0]
    if ratio == 0:
        return Outcome(PASS, f"All {total} images have alt attributes.")
    if ratio <= 0.2:
        return Outcome(WARNING, f"{missing} of {total} images are missing alt text ({pct(ratio)}).", 0.65,
                       pages=[h.url] if h.images_missing_alt else [])
    samples = "; ".join(h.missing_alt_samples[:3]) or "no sample available"
    return Outcome(
        FAIL,
        f"{missing} of {total} images ({pct(ratio)}) are missing alt text. Examples from the homepage: {samples}.",
    )


def check_lang(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    if not pages:
        return Outcome(NOT_TESTED, "No HTML pages were available for analysis.")
    missing = [p.url for p in pages if not p.lang]
    if missing:
        return Outcome(WARNING, f"{len(missing)} of {len(pages)} pages have no html lang attribute.", 0.5, pages=missing)
    h = home(crawl) or pages[0]
    return Outcome(PASS, f"Language is declared on every page (homepage: lang={quote(h.lang, 20)}).")


def check_heading_structure(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    if not pages:
        return Outcome(NOT_TESTED, "No HTML pages were available for analysis.")
    h = home(crawl) or pages[0]
    no_h1 = [p.url for p in pages if not p.h1s]
    multi_h1 = [p.url for p in pages if len(p.h1s) > 1]
    skips = [p.url for p in pages if p.heading_skips]
    if no_h1:
        return Outcome(FAIL, f"{len(no_h1)} of {len(pages)} pages have no H1 heading.", pages=no_h1)
    if len(h.h1s) > 1:
        return Outcome(
            WARNING,
            f"The homepage has {len(h.h1s)} H1 headings: {quote(' | '.join(h.h1s[:3]))}",
            0.55,
            pages=[h.url],
        )
    if skips:
        return Outcome(
            WARNING,
            f"Heading levels skip on {len(skips)} page(s), e.g. {h.heading_skips[0] if h.heading_skips else 'H2 → H4'}.",
            0.65,
            pages=skips,
        )
    return Outcome(PASS, f"One H1 per page with a consistent hierarchy (homepage H1: {quote(h.h1s[0])}).")


def check_broken_links(crawl: CrawlResult) -> Outcome:
    broken = [b for b in crawl.broken_links if b.get("status") and b["status"] >= 400]
    unreachable = [b for b in crawl.broken_links if not b.get("status")]
    if broken or unreachable:
        sample = ", ".join(f"{b['url']} (HTTP {b.get('status') or 'no response'})" for b in (broken + unreachable)[:4])
        severity_status = FAIL
        return Outcome(severity_status, f"{len(broken) + len(unreachable)} internal link(s) failed: {sample}.",
                       pages=[b["url"] for b in broken + unreachable])
    if not crawl.broken_links and crawl.discovered_internal_links == 0:
        return Outcome(NOT_TESTED, "No internal links were available to verify.")
    return Outcome(PASS, f"No broken internal links were detected across {len(crawl.pages)} crawled pages and checked links.")


def check_duplicate_titles(crawl: CrawlResult) -> Outcome:
    pages = [p for p in _pages(crawl) if p.title]
    if len(pages) < 2:
        return Outcome(NOT_TESTED, "Not enough pages with titles were crawled to compare duplicates.")
    counts = Counter(p.title.strip().lower() for p in pages)
    dupes = {t: c for t, c in counts.items() if c > 1}
    if dupes:
        sample = next(iter(dupes))
        affected = [p.url for p in pages if p.title.strip().lower() == sample]
        return Outcome(
            WARNING,
            f"{len(dupes)} duplicated title(s) across {len(pages)} pages, e.g. {quote(sample)} used {dupes[sample]} times.",
            0.4,
            pages=affected,
        )
    return Outcome(PASS, f"All {len(pages)} analysed pages have unique titles.")


def check_redirect_chains(crawl: CrawlResult) -> Outcome:
    chained = [p for p in crawl.pages if len(p.redirect_chain) > 1]
    redirected = [p for p in crawl.pages if p.redirect_chain]
    if chained:
        p = chained[0]
        return Outcome(
            WARNING,
            f"{len(chained)} page(s) required more than one redirect hop, e.g. {' → '.join(p.redirect_chain + [p.final_url or p.url])}",
            0.4,
            pages=[p.url for p in chained],
        )
    if redirected:
        return Outcome(PASS, f"{len(redirected)} page(s) redirect once (e.g. {redirected[0].redirect_chain[0]} → {redirected[0].final_url}).")
    return Outcome(PASS, "No redirect chains were detected in the crawled pages.")


def check_internal_linking(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    h = home(crawl) or (pages[0] if pages else None)
    if not h:
        return Outcome(NOT_TESTED, "No pages were available for analysis.")
    internal = {urlsplit(link.url).path for link in h.links_internal}
    if len(internal) >= 8:
        return Outcome(PASS, f"The homepage links to {len(internal)} distinct internal URLs.")
    if len(internal) >= 3:
        return Outcome(WARNING, f"The homepage links to only {len(internal)} distinct internal URLs.", 0.6)
    return Outcome(FAIL, f"The homepage links to only {len(internal)} distinct internal URL(s), which limits discoverability.")


def check_noindex_pages(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    if len(pages) < 2:
        return Outcome(NOT_TESTED, "Only one page was analysed, so a site-wide indexability comparison was not possible.")
    noindex = [p for p in pages if p.noindex]
    if noindex:
        return Outcome(
            FAIL,
            f"{len(noindex)} of {len(pages)} crawled pages are excluded from search indexes via noindex/X-Robots-Tag.",
            pages=[p.url for p in noindex],
        )
    return Outcome(PASS, f"All {len(pages)} crawled pages are indexable (no noindex directives).")


def check_content_length(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    h = home(crawl) or (pages[0] if pages else None)
    if not h:
        return Outcome(NOT_TESTED, "No HTML text content was available.")
    words = h.word_count
    avg = average(p.word_count for p in pages)
    if words >= 500:
        return Outcome(PASS, f"The homepage has {words} words of visible text (site average {avg}).")
    if words >= 250:
        return Outcome(WARNING, f"The homepage has only {words} words of visible text (site average {avg}).", 0.6)
    return Outcome(FAIL, f"The homepage has only {words} words of visible text — thin content is hard to rank or quote.")


def check_content_structure(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    h = home(crawl) or (pages[0] if pages else None)
    if not h:
        return Outcome(NOT_TESTED, "No HTML text content was available.")
    h2 = len(h.h2s)
    paragraphs = len(h.paragraphs)
    items = h.list_items
    if h2 >= 3 and paragraphs >= 4:
        return Outcome(PASS, f"Content is structured with {h2} H2 sections, {paragraphs} paragraphs and {items} list items.")
    if h2 >= 1 or paragraphs >= 2:
        return Outcome(WARNING, f"Limited structure: {h2} H2 sections, {paragraphs} paragraphs, {items} list items.", 0.55)
    return Outcome(FAIL, f"Content lacks structure: {h2} H2 sections, {paragraphs} substantive paragraphs, {items} list items.")


def check_keyword_presence(crawl: CrawlResult) -> Outcome:
    """Checks whether the page's own primary topic appears in title/headings."""
    pages = _pages(crawl)
    h = home(crawl) or (pages[0] if pages else None)
    if not h:
        return Outcome(NOT_TESTED, "No page content was available.")
    if not h.title and not h.h2s:
        return Outcome(NOT_TESTED, "The page has no title or headings to compare against its content.")
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "your", "you", "our", "are", "was",
        "have", "has", "will", "can", "all", "not", "but", "they", "their", "its", "how", "what",
        "who", "when", "where", "why", "more", "most", "into", "than", "then", "out", "get",
    }
    words = re.findall(r"[a-z]{4,}", h.text.lower())
    if len(words) < 200:
        return Outcome(NOT_TESTED, "Not enough body text on the homepage to infer a primary topic.")
    common = [w for w, _ in Counter(w for w in words if w not in stop).most_common(12)]
    heading_text = " ".join([h.title] + [x["text"] for x in h.headings]).lower()
    in_headings = [w for w in common[:6] if w in heading_text]
    if len(in_headings) >= 3:
        return Outcome(PASS, f"Top content terms appear in headings/title: {', '.join(in_headings[:5])}.")
    if in_headings:
        return Outcome(
            WARNING,
            f"Only {len(in_headings)} of the page's top 6 content terms appear in the title/headings ({', '.join(in_headings)} vs. {', '.join(common[:6])}).",
            0.5,
        )
    return Outcome(FAIL, f"None of the page's most frequent content terms ({', '.join(common[:6])}) appear in the title or headings.")


def check_anchor_text(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    h = home(crawl) or (pages[0] if pages else None)
    if not h:
        return Outcome(NOT_TESTED, "No links were available.")
    total = len(h.links_internal) + len(h.links_external)
    if total == 0:
        return Outcome(NOT_TESTED, "The homepage contains no outgoing links.")
    ratio = h.generic_anchors / total
    if h.generic_anchors == 0:
        return Outcome(PASS, f"All {total} links on the homepage use descriptive anchor text.")
    if ratio <= 0.15:
        return Outcome(WARNING, f"{h.generic_anchors} of {total} links use generic anchor text such as “click here”.", 0.7)
    return Outcome(FAIL, f"{h.generic_anchors} of {total} links ({pct(ratio)}) use generic anchor text.")


def check_external_links(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    h = home(crawl) or (pages[0] if pages else None)
    if not h:
        return Outcome(NOT_TESTED, "No links were available.")
    ext = len(h.links_external)
    if ext >= 3:
        return Outcome(PASS, f"The homepage links out to {ext} external URLs.")
    if ext >= 1:
        return Outcome(WARNING, f"The homepage links out to only {ext} external URL(s).", 0.7)
    return Outcome(WARNING, "The homepage contains no external links, which weakens credibility signals.", 0.4)


def check_open_graph(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    h = home(crawl) or (pages[0] if pages else None)
    if not h:
        return Outcome(NOT_TESTED, "No HTML pages were available.")
    required = ["og:title", "og:description", "og:image", "og:url"]
    missing = [k for k in required if k not in h.og_tags]
    if not missing:
        return Outcome(PASS, "Open Graph tags are complete (title, description, image, url).")
    if len(missing) <= 2:
        return Outcome(WARNING, f"Open Graph tags present but missing: {', '.join(missing)}.", 0.6)
    return Outcome(FAIL, f"Social preview metadata is incomplete — missing {', '.join(missing)}.")


def check_favicon(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    h = home(crawl) or (pages[0] if pages else None)
    if not h:
        return Outcome(NOT_TESTED, "No HTML pages were available.")
    if h.favicon:
        return Outcome(PASS, "A favicon is declared in the homepage HTML.")
    return Outcome(WARNING, "No favicon <link> was found; browsers and some search surfaces fall back to a generic icon.", 0.6)


def check_mixed_content(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    https_pages = [p for p in pages if (p.final_url or p.url).startswith("https://")]
    if not https_pages:
        return Outcome(NOT_TESTED, "The site is not served over HTTPS, so mixed-content scanning does not apply.")
    offenders: list[str] = []
    for p in https_pages:
        for ref in p.links_internal:
            if ref.url.startswith("http://") and host_of(urlsplit(ref.url).hostname or ""):
                offenders.append(ref.url)
    if offenders:
        return Outcome(WARNING, f"{len(offenders)} insecure http:// internal link(s) on an HTTPS page (mixed content risk).", 0.5,
                       pages=offenders[:5])
    return Outcome(PASS, "No insecure internal links were found on HTTPS pages.")


def host_of(host: str) -> bool:
    return bool(host)


SEO_CHECKS: list[CheckSpec] = [
    CheckSpec(
        id="seo.https", pillar=PILLAR, category="Technical SEO", title="HTTPS availability",
        description="The site is served over HTTPS and http:// redirects to https://.",
        why="HTTPS is a baseline trust and ranking signal. Browsers warn visitors about insecure pages, and mixed HTTP/HTTPS setups create duplicate URLs.",
        fix="Serve the site over HTTPS with a valid certificate and add a 301 redirect from every http:// URL to its https:// equivalent.",
        example='<VirtualHost *:80>\n  ServerName example.com\n  Redirect permanent / https://example.com/\n</VirtualHost>',
        severity="critical", weight=8, priority=1, evaluate=check_https,
    ),
    CheckSpec(
        id="seo.http_status", pillar=PILLAR, category="Technical SEO", title="Homepage HTTP status",
        description="The homepage returns a successful (2xx) HTTP status code.",
        why="Search engines and AI crawlers must receive a 200 response to read and index the page. A 4xx/5xx status means the page cannot be reliably discovered.",
        fix="Fix the server configuration or upstream proxy so the homepage returns HTTP 200.",
        example="curl -I https://example.com  →  HTTP/2 200",
        severity="critical", weight=8, priority=1, evaluate=check_home_status,
    ),
    CheckSpec(
        id="seo.title", pillar=PILLAR, category="Technical SEO", title="Page titles",
        description="Every analysed page has a <title> element of a sensible length (15–65 characters).",
        why="The title is the strongest on-page relevance signal and the headline shown in search results and AI answer citations.",
        fix="Give each page a unique, descriptive title: primary topic first, brand second, under ~65 characters.",
        example='<title>AI Visibility Audit for B2B SaaS | AuriomHQ</title>',
        severity="high", weight=8, priority=2, evaluate=check_title,
    ),
    CheckSpec(
        id="seo.meta_description", pillar=PILLAR, category="Technical SEO", title="Meta descriptions",
        description="Pages include a meta description between 70 and 165 characters.",
        why="Descriptions are used as search snippets and are frequently quoted by answer engines when summarising a page.",
        fix="Write a unique, benefit-led description of ~150 characters for every important page.",
        example='<meta name="description" content="Run a free SEO, AEO and GEO audit of your website in under a minute and get prioritised fixes.">',
        severity="high", weight=7, priority=2, evaluate=check_meta_description,
    ),
    CheckSpec(
        id="seo.canonical", pillar=PILLAR, category="Technical SEO", title="Canonical URLs",
        description="Pages declare a canonical URL.",
        why="Canonicals consolidate duplicate versions of a page (tracking parameters, www/non-www, trailing slashes) so signals are not split.",
        fix="Add a self-referencing absolute canonical to every indexable page; point variants at the preferred URL.",
        example='<link rel="canonical" href="https://example.com/services/ai-automation">',
        severity="medium", weight=5, priority=2, evaluate=check_canonical,
    ),
    CheckSpec(
        id="seo.robots_meta", pillar=PILLAR, category="Technical SEO", title="Indexability (robots meta)",
        description="Pages are not accidentally blocked with noindex or none directives.",
        why="A stray noindex tag removes a page from search results entirely — a common, high-impact launch mistake.",
        fix="Remove noindex from pages you want indexed, or scope it to staging environments only.",
        example='<meta name="robots" content="index, follow, max-image-preview:large">',
        severity="critical", weight=6, priority=1, evaluate=check_robots_meta,
    ),
    CheckSpec(
        id="seo.robots_txt", pillar=PILLAR, category="Technical SEO", title="robots.txt",
        description="robots.txt exists, is readable and does not block the site.",
        why="robots.txt is the first thing a crawler reads. A missing file gives no guidance; an over-broad rule can hide entire sections.",
        fix="Publish a robots.txt that allows important paths, blocks admin/search URLs and references your sitemap.",
        example="User-agent: *\nDisallow: /admin/\nAllow: /\n\nSitemap: https://example.com/sitemap.xml",
        severity="high", weight=5, priority=1, evaluate=check_robots_txt,
    ),
    CheckSpec(
        id="seo.sitemap", pillar=PILLAR, category="Technical SEO", title="XML sitemap",
        description="A valid XML sitemap is available and lists the site's pages.",
        why="Sitemaps accelerate discovery of new and updated pages and give crawlers an authoritative list of canonical URLs.",
        fix="Generate an XML sitemap of indexable URLs, keep it current, and reference it from robots.txt.",
        example='<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  <url><loc>https://example.com/services</loc></url>\n</urlset>',
        severity="medium", weight=6, priority=2, evaluate=check_sitemap,
    ),
    CheckSpec(
        id="seo.viewport", pillar=PILLAR, category="Technical SEO", title="Mobile viewport",
        description="Every page declares a responsive viewport meta tag.",
        why="Mobile-first indexing means the mobile rendering of a page is what gets evaluated. Without a viewport the page renders zoomed-out and unusable.",
        fix="Add the standard responsive viewport tag to the <head> of every page.",
        example='<meta name="viewport" content="width=device-width, initial-scale=1">',
        severity="high", weight=6, priority=1, evaluate=check_viewport,
    ),
    CheckSpec(
        id="seo.image_alt", pillar=PILLAR, category="Content SEO", title="Image alt text",
        description="Images carry descriptive alt attributes.",
        why="Alt text makes images understandable to screen readers, and it is the only text signal available for imagery in search and AI systems.",
        fix="Describe the image's purpose in alt text; use empty alt=\"\" only for purely decorative images.",
        example='<img src="/audit-dashboard.png" alt="AI visibility dashboard showing SEO, AEO and GEO scores">',
        severity="medium", weight=6, priority=1, evaluate=check_image_alt,
    ),
    CheckSpec(
        id="seo.lang", pillar=PILLAR, category="Technical SEO", title="HTML language declaration",
        description="The <html> element declares a lang attribute.",
        why="Language declarations drive correct indexing, hreflang handling, screen-reader pronunciation and AI language matching.",
        fix="Set the primary language on the html element and use hreflang for translated versions.",
        example='<html lang="en-GB">',
        severity="low", weight=3, priority=2, evaluate=check_lang,
    ),
    CheckSpec(
        id="seo.headings", pillar=PILLAR, category="Content SEO", title="Heading hierarchy",
        description="Each page has exactly one H1 and a logical heading order.",
        why="Headings are the outline both crawlers and LLMs use to understand page structure and to select the most relevant passage for an answer.",
        fix="Use one H1 per page for the main topic, then H2/H3 for sections without skipping levels.",
        example="<h1>AI visibility for B2B SaaS</h1>\n  <h2>What we audit</h2>\n    <h3>Technical SEO</h3>",
        severity="high", weight=5, priority=2, evaluate=check_heading_structure,
    ),
    CheckSpec(
        id="seo.broken_links", pillar=PILLAR, category="Technical SEO", title="Broken internal links",
        description="Internal links resolve to working pages.",
        why="Broken links waste crawl budget, fragment link equity and frustrate visitors; AI agents following links may abandon the site.",
        fix="Fix or redirect broken internal links to the closest relevant page (301), and update the referring content.",
        example="GET /services/old-page → 404  ⇒  add 301 redirect to /services/ai-automation",
        severity="critical", weight=8, priority=1, evaluate=check_broken_links,
    ),
    CheckSpec(
        id="seo.duplicate_titles", pillar=PILLAR, category="Technical SEO", title="Duplicate page titles",
        description="No two crawled pages share the same title.",
        why="Duplicate titles make it hard for crawlers to tell pages apart and usually mean templated, low-relevance metadata.",
        fix="Rewrite titles so each page describes its specific content and intent.",
        example='<title>AI Automation for Real Estate Agencies | AuriomHQ</title>',
        severity="medium", weight=4, priority=2, evaluate=check_duplicate_titles,
    ),
    CheckSpec(
        id="seo.redirect_chains", pillar=PILLAR, category="Technical SEO", title="Redirect chains",
        description="Crawled pages reach their destination in at most one redirect hop.",
        why="Each extra hop slows crawling and dilutes signals; long chains often indicate stale internal links.",
        fix="Point internal links directly at the final URL and collapse chains into a single 301.",
        example="http://example.com → https://example.com → https://www.example.com  ⇒  single 301 to https://www.example.com",
        severity="low", weight=3, priority=2, evaluate=check_redirect_chains,
    ),
    CheckSpec(
        id="seo.internal_linking", pillar=PILLAR, category="Content SEO", title="Internal linking",
        description="The homepage links to a healthy number of distinct internal pages.",
        why="Internal links spread authority and help crawlers (and AI agents) discover the pages that matter.",
        fix="Add contextual links from high-traffic pages to key service, product and answer pages using descriptive anchors.",
        example='<a href="/services/aeo-geo">AEO and GEO services</a>',
        severity="medium", weight=4, priority=2, evaluate=check_internal_linking,
    ),
    CheckSpec(
        id="seo.indexable_pages", pillar=PILLAR, category="Technical SEO", title="Site-wide indexability",
        description="Crawled pages are all indexable (no noindex at scale).",
        why="Systematic noindex directives usually come from a template or staging configuration and silently remove whole sections from search.",
        fix="Audit robots meta tags and X-Robots-Tag headers per template; keep only the intended exclusions.",
        example='<meta name="robots" content="noindex">  ⇒  remove from public templates, keep on /thank-you/ pages only',
        severity="medium", weight=4, priority=1, evaluate=check_noindex_pages,
    ),
    CheckSpec(
        id="seo.content_length", pillar=PILLAR, category="Content SEO", title="Content depth",
        description="Pages contain a meaningful amount of visible text.",
        why="Thin pages rarely satisfy a query and give answer engines nothing quotable. Depth is not about word count alone, but very short pages are a reliable warning sign.",
        fix="Expand the page with the specifics a buyer needs: what you do, who it is for, how it works, proof and answers to common questions.",
        example="Homepage with 700–1,200 words: value proposition, services, process, proof, FAQ.",
        severity="medium", weight=6, priority=2, evaluate=check_content_length,
    ),
    CheckSpec(
        id="seo.content_structure", pillar=PILLAR, category="Content SEO", title="Content structure",
        description="Content is broken into sections, paragraphs and lists.",
        why="Structured content is easier to scan and much easier for retrieval systems to split into answerable passages.",
        fix="Use H2 sections with short paragraphs (2–4 sentences) and bullet lists for scannable facts.",
        example="<h2>How the audit works</h2><ul><li>Crawl the site</li><li>Score 60+ signals</li><li>Prioritise fixes</li></ul>",
        severity="medium", weight=4, priority=2, evaluate=check_content_structure,
    ),
    CheckSpec(
        id="seo.keyword_alignment", pillar=PILLAR, category="Content SEO", title="Topic alignment",
        description="The page's most frequent content terms also appear in its title and headings.",
        why="When the headings ignore what the body actually discusses, both search engines and LLMs struggle to match the page to a query.",
        fix="Rewrite the title and headings around the topics the page genuinely covers, using the language your customers use.",
        example='Body discusses “AI visibility, AEO, GEO”  ⇒  <h1>AI visibility: SEO, AEO and GEO</h1>',
        severity="low", weight=4, priority=2, evaluate=check_keyword_presence,
    ),
    CheckSpec(
        id="seo.anchor_text", pillar=PILLAR, category="Content SEO", title="Descriptive anchor text",
        description="Links use descriptive text rather than “click here” or “read more”.",
        why="Anchor text tells crawlers and AI models what the destination page is about; generic anchors waste that signal and hurt accessibility.",
        fix="Rewrite anchors to describe the destination, not the click action.",
        example='<a href="/pricing">See AI visibility pricing</a>  (not “Click here”)',
        severity="low", weight=3, priority=2, evaluate=check_anchor_text,
    ),
    CheckSpec(
        id="seo.external_links", pillar=PILLAR, category="Content SEO", title="External references",
        description="The homepage links out to relevant external sources.",
        why="Outbound links to credible sources are a well-established trust signal and they demonstrate the content is grounded in something verifiable.",
        fix="Cite primary sources (official documentation, studies, standards) next to the claims they support.",
        example='<a href="https://www.nist.gov/..." rel="noopener">NIST AI Risk Management Framework</a>',
        severity="low", weight=3, priority=3, evaluate=check_external_links,
    ),
    CheckSpec(
        id="seo.open_graph", pillar=PILLAR, category="Technical SEO", title="Social preview metadata",
        description="Open Graph tags are present for link previews.",
        why="When your URL is shared in Slack, LinkedIn, WhatsApp or an email, the preview is generated from these tags — missing tags look unfinished.",
        fix="Add og:title, og:description, og:image (1200×630) and og:url to every important page.",
        example='<meta property="og:image" content="https://example.com/og/audit.png">',
        severity="low", weight=2, priority=2, evaluate=check_open_graph,
    ),
    CheckSpec(
        id="seo.favicon", pillar=PILLAR, category="Technical SEO", title="Favicon",
        description="A favicon is declared in the HTML.",
        why="Favicons appear in browser tabs, bookmarks and some AI answer surfaces — a small, visible brand-consistency signal.",
        fix="Add a modern favicon set and reference it in the head.",
        example='<link rel="icon" href="/favicon.ico" sizes="any">',
        severity="informational", weight=1, priority=2, evaluate=check_favicon,
    ),
    CheckSpec(
        id="seo.mixed_content", pillar=PILLAR, category="Technical SEO", title="Mixed content links",
        description="HTTPS pages do not link to insecure http:// versions of the same site.",
        why="HTTP links on an HTTPS page fragment the canonical version of your site and may trigger browser warnings for embedded resources.",
        fix="Update internal links to https:// (or use root-relative URLs).",
        example='<a href="https://example.com/contact">Contact</a>',
        severity="low", weight=2, priority=2, evaluate=check_mixed_content,
    ),
]
