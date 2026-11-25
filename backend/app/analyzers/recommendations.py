"""Recommendation engine.

Two layers:

1. **Rule-based (always available).** Every failed or warning check becomes an
   actionable recommendation with priority, expected benefit, difficulty and
   guidance. Concrete drafts (titles, meta descriptions, heading outlines, FAQ
   questions, schema additions) are generated *from text found on the site* and
   are labelled as drafts.
2. **Optional AI layer** (``ai.py``) which rewrites the wording more naturally
   while being restricted to the same evidence pack.

No recommendation promises a ranking improvement, and nothing is invented that
the crawler did not observe.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from ..crawler import CrawlResult
from .base import NOT_TESTED, SEVERITY_ORDER, CheckResult
from .geo import infer_brand

PRIORITY_TITLES = {
    1: "Priority 1 — Fix immediately",
    2: "Priority 2 — Improve discoverability",
    3: "Priority 3 — Improve AI visibility readiness",
}
PRIORITY_DESCRIPTIONS = {
    1: "Critical technical and accessibility problems that can prevent your site from being crawled, indexed or understood at all.",
    2: "Metadata, structure, schema and internal linking work that improves how your pages are found and summarised.",
    3: "Entity clarity, answer-focused content and credibility signals that generative engines rely on when choosing what to cite.",
}

# Implementation effort per check (Easy / Moderate / Hard)
DIFFICULTY = {
    "seo.https": "Moderate", "seo.http_status": "Moderate", "seo.title": "Easy",
    "seo.meta_description": "Easy", "seo.canonical": "Easy", "seo.robots_meta": "Easy",
    "seo.robots_txt": "Easy", "seo.sitemap": "Moderate", "seo.viewport": "Easy",
    "seo.image_alt": "Moderate", "seo.lang": "Easy", "seo.headings": "Easy",
    "seo.broken_links": "Moderate", "seo.duplicate_titles": "Easy",
    "seo.redirect_chains": "Moderate", "seo.internal_linking": "Moderate",
    "seo.indexable_pages": "Easy", "seo.content_length": "Hard",
    "seo.content_structure": "Moderate", "seo.keyword_alignment": "Easy",
    "seo.anchor_text": "Easy", "seo.external_links": "Moderate", "seo.open_graph": "Easy",
    "seo.favicon": "Easy", "seo.mixed_content": "Easy",
    "aeo.faq_section": "Moderate", "aeo.question_headings": "Moderate",
    "aeo.answer_paragraphs": "Moderate", "aeo.definitions": "Moderate",
    "aeo.lists_steps": "Easy", "aeo.structured_content": "Moderate",
    "aeo.article_schema": "Moderate", "aeo.faq_schema": "Easy", "aeo.howto_schema": "Easy",
    "aeo.author_info": "Easy", "aeo.dates": "Easy", "aeo.readability": "Hard",
    "aeo.answer_accessibility": "Moderate",
    "geo.org_identity": "Moderate", "geo.brand_consistency": "Easy",
    "geo.schema_presence": "Moderate", "geo.schema_quality": "Moderate",
    "geo.entity_clarity": "Moderate", "geo.author_entity": "Moderate",
    "geo.original_content": "Hard", "geo.evidence_sources": "Moderate",
    "geo.html_content": "Hard", "geo.ai_crawler_access": "Easy", "geo.llms_txt": "Easy",
    "geo.descriptive_structure": "Moderate", "geo.contact_details": "Easy",
    "geo.freshness": "Easy", "geo.semantic_html": "Easy",
}

BENEFIT = {
    "seo.https": "Removes browser security warnings and consolidates every URL onto its secure version.",
    "seo.http_status": "Makes the homepage reliably retrievable by search and AI crawlers.",
    "seo.title": "Improves click-through from results pages and gives engines an unambiguous page subject.",
    "seo.meta_description": "Produces a controlled summary that answer engines can quote instead of guessing.",
    "seo.canonical": "Consolidates duplicate URL variants so ranking signals stop competing with each other.",
    "seo.robots_meta": "Prevents pages being silently excluded from search results.",
    "seo.robots_txt": "Gives crawlers clear guidance and a sitemap reference instead of leaving them to guess.",
    "seo.sitemap": "Accelerates discovery of new and updated pages, especially deep or weakly linked ones.",
    "seo.viewport": "Makes the mobile rendering — the version most crawlers evaluate — usable and legible.",
    "seo.image_alt": "Makes imagery understandable to screen readers and gives engines a text signal for every image.",
    "seo.lang": "Enables correct indexing, screen-reader pronunciation and language matching for AI answers.",
    "seo.headings": "Gives crawlers and LLMs a clean outline so they select the right passage.",
    "seo.broken_links": "Stops crawlers and visitors hitting dead ends and recovers lost internal link equity.",
    "seo.duplicate_titles": "Lets crawlers and buyers tell your pages apart in results.",
    "seo.redirect_chains": "Reduces crawl waste and keeps link signals flowing to the final URL.",
    "seo.internal_linking": "Helps crawlers discover your most important pages faster and spreads authority.",
    "seo.indexable_pages": "Restores whole sections of the site to search results.",
    "seo.content_length": "Creates enough substance to answer real questions and be quotable.",
    "seo.content_structure": "Turns walls of text into scannable, extractable sections.",
    "seo.keyword_alignment": "Aligns headings with what the page actually discusses so it matches the right queries.",
    "seo.anchor_text": "Describes destination pages properly for crawlers and assistive technology.",
    "seo.external_links": "Signals credibility by connecting claims to verifiable sources.",
    "seo.open_graph": "Makes shared links look intentional in Slack, LinkedIn, WhatsApp and email.",
    "seo.favicon": "Adds a small but visible brand-consistency cue in tabs, bookmarks and result surfaces.",
    "seo.mixed_content": "Keeps every internal link on the canonical HTTPS version of the site.",
    "aeo.faq_section": "Creates directly extractable question/answer pairs for high-intent queries.",
    "aeo.question_headings": "Matches the phrasing people use in prompts and long-tail searches.",
    "aeo.answer_paragraphs": "Puts a quotable answer immediately under each question instead of burying it.",
    "aeo.definitions": "Gives engines the safest pattern to quote — a one-sentence definition.",
    "aeo.lists_steps": "Makes processes answerable from numbered steps rather than prose.",
    "aeo.structured_content": "Produces well-formed passages that retrieval systems can chunk accurately.",
    "aeo.article_schema": "States headline, author and date explicitly instead of leaving them to inference.",
    "aeo.faq_schema": "Declares question/answer pairs machine-readably (no guaranteed rich results).",
    "aeo.howto_schema": "Labels each instruction step as a discrete unit for step-by-step answers.",
    "aeo.author_info": "Adds the accountability signal engines weigh when choosing what to cite.",
    "aeo.dates": "Tells engines whether the content is current rather than undated and stale by default.",
    "aeo.readability": "Makes sentences short enough to be extracted verbatim.",
    "aeo.answer_accessibility": "Ensures the answer text is in the HTML and summarised up front.",
    "geo.org_identity": "Gives engines an unambiguous organisation entity to describe and cite.",
    "geo.brand_consistency": "Stops one company appearing as several different entities across the site.",
    "geo.schema_presence": "States page meaning explicitly rather than leaving it to inference.",
    "geo.schema_quality": "Connects your pages to the wider knowledge graph through sameAs and identity fields.",
    "geo.entity_clarity": "Produces cleaner summaries of who you are, what you do and who you serve.",
    "geo.author_entity": "Makes authorship verifiable by linking named people to real profiles.",
    "geo.original_content": "Gives generative engines something unique worth quoting.",
    "geo.evidence_sources": "Lets an engine verify claims before repeating them.",
    "geo.html_content": "Makes content readable by crawlers that do not execute JavaScript.",
    "geo.ai_crawler_access": "Removes the single biggest blocker to being read by AI search engines.",
    "geo.llms_txt": "Provides a curated map of your key content for models that look for it.",
    "geo.descriptive_structure": "Improves which passage an engine chooses for a given question.",
    "geo.contact_details": "Adds a legitimacy signal that supports brand-entity resolution.",
    "geo.freshness": "Signals that the content is maintained rather than abandoned.",
    "geo.semantic_html": "Separates real content from boilerplate so answers are easier to isolate.",
}


def _difficulty(check_id: str) -> str:
    return DIFFICULTY.get(check_id, "Moderate")


def _impact(result: CheckResult) -> str:
    if result.severity in {"critical", "high"}:
        return "High"
    if result.severity == "medium":
        return "Medium"
    return "Low"


def _clip(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0]
    return clipped.rstrip(" ,.;:—-") + "…"


def _title_case(text: str) -> str:
    return " ".join(w[:1].upper() + w[1:] if w.islower() else w for w in text.split())


def build_recommendations(crawl: CrawlResult, results: list[CheckResult]) -> dict[str, Any]:
    brand = infer_brand(crawl)
    primary = crawl.home or (crawl.pages[0] if crawl.pages else None)

    improving = [r for r in results if r.status in {"fail", "warning"}]
    improving.sort(key=lambda r: (
        SEVERITY_ORDER.get(r.severity, 9),
        0 if r.status == "fail" else 1,
        -r.weight,
    ))

    roadmap: dict[int, list[dict[str, Any]]] = {1: [], 2: [], 3: []}
    for result in improving:
        priority = result.priority if result.priority in (1, 2, 3) else 2
        # Escalate genuinely critical failures to priority 1 regardless of default bucket
        if result.status == "fail" and result.severity == "critical":
            priority = 1
        roadmap[priority].append({
            "id": f"rec.{result.id}",
            "checkId": result.id,
            "title": result.title,
            "pillar": result.pillar,
            "status": result.status,
            "severity": result.severity,
            "impact": _impact(result),
            "difficulty": _difficulty(result.id),
            "benefit": BENEFIT.get(result.id) or _default_benefit(result),
            "guidance": result.fix,
            "example": result.example,
            "evidence": result.evidence,
            "scoreImpact": round(result.weight * (1 - result.credit), 1),
            "pages": result.pages[:5],
        })

    drafts = build_drafts(crawl, results, brand)
    untested = [r.title for r in results if r.status == NOT_TESTED]

    roadmap_payload = [
        {
            "priority": p,
            "title": PRIORITY_TITLES[p],
            "description": PRIORITY_DESCRIPTIONS[p],
            "items": roadmap[p],
            "itemCount": len(roadmap[p]),
            "potentialPoints": round(sum(item["scoreImpact"] for item in roadmap[p]), 1),
        }
        for p in (1, 2, 3)
    ]

    high_impact_quick_wins = [
        item for item in (roadmap[1] + roadmap[2] + roadmap[3])
        if item["difficulty"] == "Easy" and item["impact"] in {"High", "Medium"}
    ][:5]

    return {
        "roadmap": roadmap_payload,
        "quickWins": high_impact_quick_wins,
        "drafts": drafts,
        "untested": untested,
        "generatedFrom": {"pages": len(crawl.pages), "brand": brand, "url": crawl.final_url},
    }


def _default_benefit(result: CheckResult) -> str:
    return f"Closes the {result.severity}-severity “{result.title.lower()}” gap measured in this audit."


def build_drafts(crawl: CrawlResult, results: list[CheckResult], brand: str) -> dict[str, Any]:
    primary = crawl.home or (crawl.pages[0] if crawl.pages else None)
    if primary is None:
        return {"titles": [], "metaDescriptions": [], "headingOutline": [], "faqQuestions": [],
                "schemaSuggestions": [], "note": "No page content was available to draft from."}

    page_label = _page_label(primary)
    h1 = primary.h1s[0] if primary.h1s else (primary.h2s[0] if primary.h2s else page_label)
    audience_terms = _top_terms(primary, limit=6)

    titles: list[str] = []
    if brand and brand.lower() not in h1.lower():
        titles.append(_clip(f"{h1} | {brand}", 62))
    titles.append(_clip(f"{h1} — {_benefit_phrase(primary)}", 62))
    if audience_terms:
        titles.append(_clip(f"{_title_case(audience_terms[0])} for {_title_case(audience_terms[1]) if len(audience_terms) > 1 else 'your business'} | {brand}", 62))
    titles = [t for t in dict.fromkeys(titles) if 15 <= len(t) <= 65][:3]

    meta = ""
    if primary.paragraphs:
        meta = _clip(primary.paragraphs[0], 155)
    if len(meta) < 60 and len(primary.paragraphs) > 1:
        meta = _clip(" ".join(primary.paragraphs[:2]), 155)
    meta_alt = _clip(
        f"{_clip(h1, 70)}. {brand} explains what is included, how it works and what to expect.", 155
    )
    metas = [m for m in dict.fromkeys([meta, meta_alt]) if m and len(m) >= 60][:2]

    outline = []
    if primary.h1s:
        outline.append({"level": 1, "text": primary.h1s[0], "source": "existing H1"})
    for h2 in primary.h2s[:6]:
        outline.append({"level": 2, "text": h2, "source": "existing H2"})
    existing = " ".join(h["text"].lower() for h in outline)
    suggestions = []
    if "pricing" not in existing and "cost" not in existing:
        suggestions.append("How much does it cost?")
    if "process" not in existing and "how it works" not in existing:
        suggestions.append("How does it work?")
    if "faq" not in existing:
        suggestions.append("Frequently asked questions")
    if "who" not in existing and "about" not in existing:
        suggestions.append(f"Who is {brand}?")
    if primary.h3s:
        outline.append({"level": 2, "text": "Suggested new section: Questions we hear most", "source": "suggested"})
    for text in suggestions:
        outline.append({"level": 2, "text": text, "source": "suggested"})

    faq_questions: list[str] = []
    for q in primary.question_headings[:5]:
        faq_questions.append(q if q.endswith("?") else f"{q}?")
    for term in audience_terms[:4]:
        faq_questions.append(f"What is {term}?")
    if brand:
        faq_questions.append(f"Who is {brand} and what does it do?")
    faq_questions = list(dict.fromkeys(faq_questions))[:8]

    types = {t for p in crawl.pages for t in p.schema_types}
    schema_suggestions = []
    if not ({"Organization", "LocalBusiness"} & types):
        schema_suggestions.append({
            "type": "Organization",
            "reason": "No organisation entity was found in structured data.",
            "draft": {
                "@context": "https://schema.org",
                "@type": "Organization",
                "name": brand or "[Your brand]",
                "url": crawl.final_url,
                "description": _clip(meta or h1, 200),
                "sameAs": ["https://www.linkedin.com/company/[your-profile]"],
            },
        })
    if "WebSite" not in types:
        schema_suggestions.append({
            "type": "WebSite",
            "reason": "No WebSite entity was found; this helps engines associate pages with your site name.",
            "draft": {
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": brand or "[Your brand]",
                "url": crawl.final_url,
            },
        })
    if {"FAQPage"} - types and (primary.faq_like_sections or primary.question_headings):
        schema_suggestions.append({
            "type": "FAQPage",
            "reason": "Question-style content exists without FAQPage markup.",
            "draft": {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": faq_questions[0] if faq_questions else "[Question]",
                        "acceptedAnswer": {"@type": "Answer", "text": "[Answer taken from your existing content]"},
                    }
                ],
            },
        })
    if not ({"Article", "BlogPosting"} & types) and any(re.search(r"/(blog|news|insights|article)", p.url) for p in crawl.pages):
        schema_suggestions.append({
            "type": "Article",
            "reason": "Editorial pages were crawled without Article markup.",
            "draft": {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": "[Page title]",
                "author": {"@type": "Person", "name": "[Author name]"},
                "datePublished": "[YYYY-MM-DD]",
            },
        })
    if "BreadcrumbList" not in types:
        schema_suggestions.append({
            "type": "BreadcrumbList",
            "reason": "Breadcrumb markup was not detected; it clarifies site hierarchy.",
            "draft": {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [{"@type": "ListItem", "position": 1, "name": "Home", "item": crawl.final_url}],
            },
        })

    return {
        "titles": titles,
        "currentTitle": primary.title,
        "metaDescriptions": metas,
        "currentMetaDescription": primary.meta_description,
        "headingOutline": outline[:10],
        "faqQuestions": faq_questions,
        "schemaSuggestions": schema_suggestions,
        "note": (
            "Drafts are generated strictly from text found on your site. Review them before publishing — "
            "they are starting points, not final copy."
        ),
    }


def _page_label(page) -> str:
    from urllib.parse import urlsplit

    path = urlsplit(page.url).path.strip("/")
    if not path:
        return "Home"
    return _title_case(path.split("/")[-1].replace("-", " ").replace("_", " "))


def _benefit_phrase(page) -> str:
    words = _top_terms(page, limit=3)
    if words:
        return _title_case(" ".join(words[:2]))
    return "Overview"


def _top_terms(page, limit: int = 6) -> list[str]:
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "your", "you", "our", "are", "was",
        "have", "has", "will", "can", "all", "not", "but", "they", "their", "its", "how", "what",
        "who", "when", "where", "why", "more", "most", "into", "than", "then", "out", "get",
        "about", "also", "which", "there", "these", "those", "them", "been", "were", "being",
        "would", "could", "should", "does", "each", "other", "such", "only", "just", "over",
        "very", "much", "many", "some", "any", "one", "two", "use", "used", "using", "make",
        "like", "need", "want", "help", "helps", "here", "well", "back", "even", "every",
    }
    words = re.findall(r"[A-Za-z][a-z]{3,}", page.text or "")
    counts = Counter(w.lower() for w in words if w.lower() not in stop)
    return [w for w, _ in counts.most_common(limit)]


def build_evidence_pack(crawl: CrawlResult, results: list[CheckResult], scores: Any) -> dict[str, Any]:
    """Compact, factual payload handed to the optional AI layer."""
    primary = crawl.home or (crawl.pages[0] if crawl.pages else None)
    return {
        "url": crawl.final_url,
        "pagesAnalysed": len(crawl.pages),
        "scores": {
            "overall": scores.overall,
            **{k: v.score for k, v in scores.pillars.items()},
        },
        "page": {
            "title": primary.title if primary else "",
            "metaDescription": primary.meta_description if primary else "",
            "h1": primary.h1s[:2] if primary else [],
            "h2": primary.h2s[:8] if primary else [],
            "wordCount": primary.word_count if primary else 0,
            "schemaTypes": sorted({t for p in crawl.pages for t in p.schema_types})[:12],
            "questionHeadings": primary.question_headings[:5] if primary else [],
            "intro": _clip(primary.paragraphs[0], 320) if primary and primary.paragraphs else "",
        },
        "failingChecks": [
            {"id": r.id, "pillar": r.pillar, "title": r.title, "status": r.status,
             "severity": r.severity, "evidence": r.evidence}
            for r in results if r.status in {"fail", "warning"}
        ][:25],
        "robotsAiAccess": crawl.robots.ai_access,
        "llmsTxt": bool((crawl.llms_txt or {}).get("available")),
    }
