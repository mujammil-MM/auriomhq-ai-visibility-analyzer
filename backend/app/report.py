"""Assembles the persisted audit payload (the single source of truth for the
dashboard, the shareable report and the PDF)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .analyzers import analyse
from .analyzers.base import CheckResult
from .crawler import CrawlResult, PageSnapshot

SCHEMA_VERSION = 1


def _page_payload(page: PageSnapshot) -> dict[str, Any]:
    return {
        "url": page.url,
        "finalUrl": page.final_url,
        "status": page.status,
        "ok": page.ok,
        "error": page.error,
        "title": page.title,
        "metaDescription": page.meta_description,
        "canonical": page.canonical,
        "robotsMeta": page.robots_meta[:6],
        "xRobotsTag": page.x_robots_tag,
        "lang": page.lang,
        "viewport": page.viewport,
        "headings": page.headings[:20],
        "h1": page.h1s[:3],
        "h2": page.h2s[:12],
        "imagesTotal": page.images_total,
        "imagesMissingAlt": page.images_missing_alt,
        "internalLinks": len(page.links_internal),
        "externalLinks": len(page.links_external),
        "schemaTypes": page.schema_types[:15],
        "schemaErrors": page.schema_errors[:3],
        "wordCount": page.word_count,
        "textHtmlRatio": page.text_html_ratio,
        "questionHeadings": page.question_headings[:8],
        "listItems": page.list_items,
        "author": page.author_meta or page.author_schema,
        "published": page.published_date,
        "modified": page.modified_date,
        "redirectChain": page.redirect_chain,
        "excerpt": (page.text or "")[:600],
    }


def _crawl_payload(crawl: CrawlResult) -> dict[str, Any]:
    robots = crawl.robots
    return {
        "startUrl": crawl.start_url,
        "finalUrl": crawl.final_url,
        "host": crawl.host,
        "durationMs": crawl.duration_ms,
        "pagesAnalysed": len(crawl.pages),
        "pages": [_page_payload(p) for p in crawl.pages],
        "robots": {
            "available": robots.available,
            "url": robots.url,
            "status": robots.status,
            "error": robots.error,
            "crawlDelay": robots.crawl_delay,
            "blockedPaths": robots.blocked_paths,
            "blocksAll": robots.blocks_all,
            "aiAccess": robots.ai_access,
        },
        "sitemap": {
            "available": crawl.sitemap.available,
            "url": crawl.sitemap.url,
            "urlCount": len(crawl.sitemap.urls),
            "sitemapCount": crawl.sitemap.sitemap_count,
            "error": crawl.sitemap.error,
            "sample": crawl.sitemap.urls[:10],
        },
        "llmsTxt": crawl.llms_txt,
        "brokenLinks": crawl.broken_links[:15],
        "inaccessiblePages": crawl.inaccessible_pages[:10],
        "discoveredInternalLinks": crawl.discovered_internal_links,
        "httpsAvailable": crawl.https_available,
        "httpToHttpsRedirect": crawl.http_to_https_redirect,
        "homepageStatus": crawl.homepage_status,
        "notes": crawl.notes[:10],
        "errors": crawl.errors[:5],
    }


def build_report(
    crawl: CrawlResult,
    summary: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    analysis = analysis or analyse(crawl)
    checks: list[dict[str, Any]] = analysis["checks"]
    scores = analysis["scores"]

    by_pillar: dict[str, list[dict[str, Any]]] = {"seo": [], "aeo": [], "geo": []}
    for check in checks:
        by_pillar[check["pillar"]].append(check)

    critical = [c for c in checks if c["status"] == "fail" and c["severity"] in {"critical", "high"}]

    report = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "site": {
            "url": crawl.final_url,
            "requestedUrl": crawl.start_url,
            "host": crawl.host,
            "httpsAvailable": crawl.https_available,
            "homepageStatus": crawl.homepage_status,
            "pagesAnalysed": len(crawl.pages),
            "durationMs": crawl.duration_ms,
        },
        "crawl": _crawl_payload(crawl),
        "scores": scores,
        "band": analysis["band"],
        "checks": checks,
        "checksByPillar": by_pillar,
        "criticalFindings": critical[:8],
        "recommendations": analysis["recommendations"],
        "summary": summary or {},
        "evidence": analysis["evidence"],
        "limitations": LIMITATIONS,
    }
    return report


LIMITATIONS = [
    "The audit analyses the HTML returned by your server for up to the configured number of pages (default 10). "
    "JavaScript-rendered content is not executed, so client-side-only content is invisible to this audit.",
    "Scores measure on-page readiness. They are not search rankings, traffic estimates, backlink data or observed AI citations.",
    "Keyword rankings, search volume, backlink profiles and Google index status require external data providers and are "
    "deliberately not estimated here.",
    "GEO readiness is an estimate built from measurable signals (entity data, crawler access, structure, attribution). "
    "It does not indicate whether ChatGPT, Gemini, Perplexity or any other engine currently recommends or cites the site.",
    "Structured data recommendations improve machine understanding; they do not guarantee rich results or AI citations.",
    "Checks that could not be performed are reported as “Not tested” and excluded from the score — they are never treated as passes.",
    "Third-party scripts, Core Web Vitals and real-user performance metrics are out of scope for this prototype.",
]


def public_report(report: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    """Payload shared for a public report link — no internal identifiers."""
    return {
        "id": meta.get("id"),
        "createdAt": meta.get("created_at"),
        "completedAt": meta.get("completed_at"),
        "shareToken": meta.get("share_token"),
        "visibility": meta.get("share_visibility"),
        "site": report.get("site"),
        "scores": report.get("scores"),
        "band": report.get("band"),
        "checks": report.get("checks"),
        "checksByPillar": report.get("checksByPillar"),
        "criticalFindings": report.get("criticalFindings"),
        "recommendations": report.get("recommendations"),
        "summary": report.get("summary"),
        "crawl": {
            "robots": report.get("crawl", {}).get("robots"),
            "sitemap": report.get("crawl", {}).get("sitemap"),
            "llmsTxt": report.get("crawl", {}).get("llmsTxt"),
            "pages": report.get("crawl", {}).get("pages"),
            "brokenLinks": report.get("crawl", {}).get("brokenLinks"),
            "inaccessiblePages": report.get("crawl", {}).get("inaccessiblePages"),
            "pagesAnalysed": report.get("crawl", {}).get("pagesAnalysed"),
            "durationMs": report.get("crawl", {}).get("durationMs"),
            "notes": report.get("crawl", {}).get("notes"),
        },
        "limitations": report.get("limitations"),
        "generatedAt": report.get("generatedAt"),
    }
