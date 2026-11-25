"""GEO (Generative Engine Optimisation) analysis engine.

Measures how ready a site is for generative search: can a machine identify who
you are, what you do, whether it is allowed to read you, and whether your
content is quotable and attributable.

Important framing: GEO readiness here is an *estimate built from measurable
on-site signals*. It is never a claim about how ChatGPT, Gemini or Perplexity
rank or cite the site — that would require observed answer data this prototype
does not have.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from ..crawler import AI_CRAWLERS, CrawlResult
from .base import (
    FAIL, NOT_TESTED, PASS, WARNING, CheckSpec, Outcome, analysable_pages, home, pct, quote,
)

PILLAR = "geo"


def _pages(crawl: CrawlResult):
    return analysable_pages(crawl)


def _primary(crawl: CrawlResult):
    pages = _pages(crawl)
    return home(crawl) or (pages[0] if pages else None)


def _all_types(crawl: CrawlResult) -> set[str]:
    types: set[str] = set()
    for page in crawl.pages:
        types.update(page.schema_types)
    return types


def _org_nodes(crawl: CrawlResult) -> list[dict]:
    out = []
    for page in crawl.pages:
        for node in page.schema_nodes:
            node_type = node.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if any(isinstance(t, str) and t.split("/")[-1] in {
                "Organization", "LocalBusiness", "Corporation", "ProfessionalService",
                "OnlineBusiness", "Store", "NGO",
            } for t in types):
                out.append(node)
    return out


def infer_brand(crawl: CrawlResult) -> str:
    orgs = _org_nodes(crawl)
    for node in orgs:
        name = node.get("name") or node.get("legalName")
        if isinstance(name, str) and name.strip():
            return name.strip()
    host = (urlsplit(crawl.final_url).hostname or "").removeprefix("www.")
    root = host.split(".")[0] if host else ""
    p = _primary(crawl)
    if p and p.title:
        for sep in ("|", "—", "–", "-", "·", ":"):
            parts = [s.strip() for s in p.title.split(sep)]
            if len(parts) >= 2 and parts[-1] and len(parts[-1].split()) <= 3:
                return parts[-1]
    return root.capitalize() if root else host


def check_org_identity(crawl: CrawlResult) -> Outcome:
    p = _primary(crawl)
    if not p:
        return Outcome(NOT_TESTED, "No HTML content was available.")
    orgs = _org_nodes(crawl)
    has_about = any("/about" in l.url for l in p.links_internal)
    if orgs:
        node = orgs[0]
        fields = [k for k in ("name", "url", "logo", "description", "sameAs", "address", "contactPoint") if node.get(k)]
        return Outcome(
            PASS,
            f"Organisation entity is described in structured data with fields: {', '.join(fields) or 'name only'}.",
        )
    if has_about:
        return Outcome(WARNING, "An About page is linked but no Organization/LocalBusiness structured data describes the entity.", 0.45)
    return Outcome(FAIL, "No organisation entity (Organization schema, About page or company description) could be identified.")


def check_brand_consistency(crawl: CrawlResult) -> Outcome:
    pages = [p for p in _pages(crawl) if p.title]
    if len(pages) < 2:
        return Outcome(NOT_TESTED, "Fewer than two titled pages were crawled, so brand consistency was not measured.")
    brand = infer_brand(crawl)
    if not brand:
        return Outcome(NOT_TESTED, "A brand name could not be inferred from the crawled evidence.")
    key = brand.lower()
    mentions = [p for p in pages if key in p.title.lower()]
    ratio = len(mentions) / len(pages)
    if ratio >= 0.8:
        return Outcome(PASS, f"“{brand}” appears in {len(mentions)} of {len(pages)} page titles — brand naming is consistent.")
    if ratio >= 0.5:
        return Outcome(WARNING, f"“{brand}” appears in only {len(mentions)} of {len(pages)} page titles.", 0.6,
                       pages=[p.url for p in pages if key not in p.title.lower()])
    return Outcome(FAIL, f"“{brand}” appears in only {len(mentions)} of {len(pages)} page titles; entity naming is inconsistent.")


def check_schema_presence(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    if not pages:
        return Outcome(NOT_TESTED, "No HTML pages were available.")
    with_schema = [p for p in pages if p.schema_types or p.has_microdata]
    invalid = [e for p in pages for e in p.schema_errors]
    if not with_schema and invalid:
        return Outcome(FAIL, f"JSON-LD blocks were found but none parsed correctly: {invalid[0]}")
    if not with_schema:
        return Outcome(FAIL, f"None of the {len(pages)} analysed pages contains Schema.org structured data (JSON-LD or microdata).")
    types = sorted(_all_types(crawl))[:8]
    if invalid:
        return Outcome(
            WARNING,
            f"Structured data found on {len(with_schema)} of {len(pages)} pages ({', '.join(types)}), but {len(invalid)} block(s) are invalid: {invalid[0]}",
            0.6,
        )
    if len(with_schema) < len(pages):
        return Outcome(
            WARNING,
            f"Structured data exists on {len(with_schema)} of {len(pages)} pages ({', '.join(types)}).",
            0.7,
        )
    return Outcome(PASS, f"Schema.org markup on every analysed page: {', '.join(types)}.")


def check_schema_quality(crawl: CrawlResult) -> Outcome:
    nodes = [n for p in crawl.pages for n in p.schema_nodes]
    if not nodes:
        return Outcome(NOT_TESTED, "No structured data nodes were found to evaluate.")
    rich = []
    for node in nodes:
        if any(k in node for k in ("sameAs", "logo", "address", "contactPoint", "description", "author", "publisher")):
            rich.append(node)
    types = sorted({t for n in rich for t in ([n["@type"]] if isinstance(n.get("@type"), str) else n.get("@type") or [])})
    if len(rich) >= max(1, len(nodes) // 2):
        return Outcome(PASS, f"{len(rich)} of {len(nodes)} schema nodes include identity details ({', '.join(types[:5])}).")
    if rich:
        return Outcome(WARNING, f"Only {len(rich)} of {len(nodes)} schema nodes include identity details such as sameAs, logo or address.", 0.5)
    return Outcome(
        FAIL,
        f"{len(nodes)} schema node(s) exist but none includes sameAs, logo, address, contactPoint or description — the entity stays ambiguous.",
    )


def check_entity_clarity(crawl: CrawlResult) -> Outcome:
    p = _primary(crawl)
    if not p:
        return Outcome(NOT_TESTED, "No HTML content was available.")
    intro = " ".join(p.paragraphs[:3])[:1200]
    who_re = re.compile(
        r"\b(we are|we're|is a|is an|helps|specialis|specializ|provides|build|agency|studio|platform|consultancy|company)\b",
        re.IGNORECASE,
    )
    has_who = bool(who_re.search(intro))
    has_location_or_market = bool(re.search(r"\b(for|serving|based in|across|worldwide|global)\b", intro, re.IGNORECASE))
    has_about_link = any(re.search(r"/(about|company|team|who-we-are)", l.url) for l in p.links_internal)
    score = sum([has_who, has_location_or_market, has_about_link])
    if score == 3:
        return Outcome(PASS, "A clear entity statement was found in the opening copy and an About page is linked.")
    if score == 2:
        return Outcome(WARNING, f"Entity description is partial ({score}/3 clarity signals): {quote(intro, 160)}", 0.6)
    return Outcome(FAIL, f"The opening content does not clearly say who the organisation is or what it does: {quote(intro, 160)}")


def check_author_entity(crawl: CrawlResult) -> Outcome:
    person = [n for p in crawl.pages for n in p.schema_nodes
              if isinstance(n.get("@type"), str) and n["@type"].split("/")[-1] == "Person"]
    with_sameas = [n for n in person if n.get("sameAs") or n.get("url")]
    if person and with_sameas:
        name = with_sameas[0].get("name", "an author")
        return Outcome(PASS, f"Person schema present with linked identity ({name}: {len(with_sameas[0].get('sameAs') or []) or 1} reference(s)).")
    if person:
        return Outcome(WARNING, "Person schema exists but does not link the author to any external profile (sameAs).", 0.5)
    bylines = [p for p in crawl.pages if p.author_meta]
    if bylines:
        return Outcome(WARNING, "Author bylines exist as text/meta tags but there is no Person schema tying the author to a verified identity.", 0.4)
    return Outcome(FAIL, "No author entity (Person schema or byline) was found to attribute the content.")


def check_original_content(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    if not pages:
        return Outcome(NOT_TESTED, "No HTML pages were available.")
    h = home(crawl) or pages[0]
    others = [p for p in pages if p.url != h.url]
    if not others:
        if h.word_count >= 400:
            return Outcome(WARNING, "Only one page was analysed, so duplicate/boilerplate content could not be compared across the site.", 0.7)
        return Outcome(FAIL, f"Only one short page ({h.word_count} words) was analysed; there is little substantive content.", 0.0)
    shared = 0
    total_sentences = 0
    home_sentences = {s.strip().lower()[:120] for s in re.split(r"[.!?]\s+", " ".join(h.paragraphs)) if len(s) > 40}
    for page in others:
        sentences = [s.strip().lower()[:120] for s in re.split(r"[.!?]\s+", " ".join(page.paragraphs)) if len(s) > 40]
        total_sentences += len(sentences)
        shared += sum(1 for s in sentences if s in home_sentences)
    ratio = shared / total_sentences if total_sentences else 0
    avg_words = round(sum(p.word_count for p in pages) / len(pages))
    if ratio <= 0.2 and avg_words >= 300:
        return Outcome(PASS, f"Low boilerplate overlap ({pct(ratio)} of sentences repeat across pages) with an average of {avg_words} words per page.")
    if ratio <= 0.4:
        return Outcome(
            WARNING,
            f"{pct(ratio)} of sentences on secondary pages also appear on the homepage (avg {avg_words} words/page) — content is partly templated.",
            0.6,
        )
    return Outcome(
        FAIL,
        f"{pct(ratio)} of sentences on secondary pages are duplicated from the homepage, leaving little original content for engines to cite.",
    )


def check_evidence_sources(crawl: CrawlResult) -> Outcome:
    p = _primary(crawl)
    if not p:
        return Outcome(NOT_TESTED, "No HTML content was available.")
    cited = p.authoritative_citations
    ext = len(p.links_external)
    if cited:
        return Outcome(PASS, f"The homepage cites authoritative external sources: {', '.join(cited[:4])}.")
    if ext >= 3:
        return Outcome(WARNING, f"The homepage links to {ext} external sites but none are recognisable authoritative sources.", 0.5)
    return Outcome(FAIL, "No outbound citations or source links were found, so claims cannot be verified by an engine.")


def check_html_content(crawl: CrawlResult) -> Outcome:
    p = _primary(crawl)
    if not p:
        return Outcome(NOT_TESTED, "No HTML content was available.")
    ratio = p.text_html_ratio
    js_shell = p.word_count < 120 and p.html_bytes > 15000
    if js_shell:
        return Outcome(
            FAIL,
            f"Only {p.word_count} words of text inside {p.html_bytes // 1024} KB of HTML — the page looks like a JavaScript shell that renders content client-side.",
        )
    if ratio >= 0.1:
        return Outcome(PASS, f"Content is server-rendered in HTML ({p.word_count} words, text/HTML ratio {pct(ratio)}).")
    if ratio >= 0.05:
        return Outcome(WARNING, f"Text/HTML ratio is low ({pct(ratio)}, {p.word_count} words). Check that key content is not hidden in scripts.", 0.6)
    return Outcome(FAIL, f"Very little text is served in HTML (text/HTML ratio {pct(ratio)}); most content appears to require JavaScript.")


def check_ai_crawler_access(crawl: CrawlResult) -> Outcome:
    robots = crawl.robots
    if not robots.available:
        return Outcome(
            WARNING,
            "No robots.txt was found. Nothing is blocked, but there are also no explicit rules for AI crawlers.",
            0.55,
        )
    blocked = [bot for bot, info in robots.ai_access.items() if not info["allowed"]]
    allowed = [bot for bot, info in robots.ai_access.items() if info["allowed"]]
    explicit = [bot for bot, info in robots.ai_access.items() if info["explicitly_listed"]]
    if blocked and len(blocked) < len(robots.ai_access):
        return Outcome(
            WARNING,
            f"robots.txt allows {len(allowed)} of {len(robots.ai_access)} known AI crawlers but blocks: {', '.join(blocked[:5])}.",
            0.55,
        )
    if blocked:
        return Outcome(FAIL, f"robots.txt blocks all known AI crawlers we tested: {', '.join(blocked[:6])}.")
    note = f" ({len(explicit)} explicitly named)" if explicit else " (via wildcard rules)"
    return Outcome(PASS, f"robots.txt does not block any of the {len(robots.ai_access)} known AI crawlers we checked{note}.")


def check_llms_txt(crawl: CrawlResult) -> Outcome:
    info = crawl.llms_txt or {}
    if info.get("available"):
        return Outcome(PASS, f"An llms.txt file is published at {info.get('url')}.")
    if info.get("status") and info.get("status") < 400:
        return Outcome(WARNING, f"A file exists at {info.get('url')} but it does not look like a valid llms.txt document.", 0.4)
    return Outcome(
        WARNING,
        f"No llms.txt was found (HTTP {info.get('status') or 'no response'} at {info.get('url')}). This is an emerging convention, not yet used by every engine.",
        0.25,
    )


def check_descriptive_structure(crawl: CrawlResult) -> Outcome:
    pages = _pages(crawl)
    if not pages:
        return Outcome(NOT_TESTED, "No HTML pages were available.")
    h = home(crawl) or pages[0]
    signals = sum([
        bool(h.title),
        bool(h.meta_description),
        len(h.h1s) == 1,
        len(h.h2s) >= 2,
        sum(1 for p in pages if p.title) >= max(1, len(pages) // 2),
    ])
    if signals >= 4:
        return Outcome(PASS, f"Descriptive page structure present ({signals}/5 signals, {len(h.h2s)} H2 sections).")
    if signals == 3:
        return Outcome(WARNING, f"Page structure is partial ({signals}/5 descriptive signals).", 0.55)
    return Outcome(FAIL, f"Page structure is weak ({signals}/5 descriptive signals) — engines get little context from headings.")


def check_contact_details(crawl: CrawlResult) -> Outcome:
    p = _primary(crawl)
    if not p:
        return Outcome(NOT_TESTED, "No HTML content was available.")
    emails = list({e for page in crawl.pages for e in page.email_addresses})
    phones = [n for page in crawl.pages for n in page.phone_numbers]
    address = any(page.has_address_signal for page in crawl.pages)
    contact_link = any("contact" in l.url.lower() for l in p.links_internal)
    found = []
    if emails:
        found.append(f"email ({emails[0]})")
    if address:
        found.append("postal address signals")
    if contact_link:
        found.append("contact page")
    if len(found) >= 2:
        return Outcome(PASS, f"Business contact details are published: {', '.join(found)}.")
    if found:
        return Outcome(WARNING, f"Only partial contact information found: {', '.join(found)}.", 0.55)
    return Outcome(FAIL, "No contact email, address or contact page was found on the crawled pages.")


def check_freshness(crawl: CrawlResult) -> Outcome:
    dated = [p for p in crawl.pages if p.published_date or p.modified_date]
    if not dated:
        return Outcome(FAIL, "No publication or update dates were found across the crawled pages.")
    sample = dated[0]
    value = sample.modified_date or sample.published_date
    if len(dated) >= max(1, len(crawl.pages) // 2):
        return Outcome(PASS, f"{len(dated)} of {len(crawl.pages)} pages expose dates (e.g. {quote(value, 40)} on {sample.url}).")
    return Outcome(WARNING, f"Only {len(dated)} of {len(crawl.pages)} pages expose dates (e.g. {quote(value, 40)}).", 0.5)


def check_semantic_html(crawl: CrawlResult) -> Outcome:
    p = _primary(crawl)
    if not p:
        return Outcome(NOT_TESTED, "No HTML content was available.")
    tags = set(p.semantic_tags)
    important = {"main", "article", "header", "nav", "footer", "section"}
    found = sorted(tags & important)
    if len(found) >= 4:
        return Outcome(PASS, f"Semantic landmarks present: {', '.join(found)}.")
    if found:
        return Outcome(WARNING, f"Only some semantic landmarks were found: {', '.join(found)}.", 0.6)
    return Outcome(FAIL, "No semantic HTML landmarks (<main>, <article>, <nav>, <footer>) were found; the page is a div soup.")


GEO_CHECKS: list[CheckSpec] = [
    CheckSpec(
        id="geo.org_identity", pillar=PILLAR, category="Entity", title="Organisation identity",
        description="The site clearly describes the organisation as an entity (schema, About page, company description).",
        why="Generative engines resolve pages to entities. A machine-readable organisation identity is how you get described correctly instead of being guessed at.",
        fix="Add Organization (or LocalBusiness) JSON-LD with name, url, logo, description and sameAs profiles, and keep an About page linked from the footer.",
        example='{"@context":"https://schema.org","@type":"Organization","name":"AuriomHQ","url":"https://auriomhq.work","logo":"https://auriomhq.work/logo.png","sameAs":["https://www.linkedin.com/company/…"]}',
        severity="critical", weight=10, priority=3, evaluate=check_org_identity,
    ),
    CheckSpec(
        id="geo.brand_consistency", pillar=PILLAR, category="Entity", title="Consistent brand information",
        description="The inferred brand name appears consistently in page titles across the crawled site.",
        why="Inconsistent naming splits your entity across the web and confuses summarisation (“Auriom”, “AuriomHQ”, “Auriom HQ” behave like three companies).",
        fix="Standardise the brand string everywhere: titles, schema, meta descriptions, footer and social profiles.",
        example="<title>AI Visibility Analyzer | AuriomHQ</title>  (same brand string on every page)",
        severity="high", weight=8, priority=3, evaluate=check_brand_consistency,
    ),
    CheckSpec(
        id="geo.schema_presence", pillar=PILLAR, category="Structured data", title="Schema.org structured data",
        description="Pages contain valid Schema.org JSON-LD or microdata.",
        why="Structured data is the least ambiguous way to tell an engine what a page is, who published it and what it is about.",
        fix="Add JSON-LD to key templates (Organization, WebSite, WebPage, Article, BreadcrumbList, FAQPage) and validate it.",
        example='<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebPage","name":"…"}</script>',
        severity="high", weight=10, priority=2, evaluate=check_schema_presence,
    ),
    CheckSpec(
        id="geo.schema_quality", pillar=PILLAR, category="Structured data", title="Structured data depth",
        description="Schema nodes include identity properties such as sameAs, logo, address or description.",
        why="A bare @type tells an engine very little. Identity properties are what connect your page to the wider knowledge graph.",
        fix="Enrich each node: add sameAs links to official profiles, logo, description, address and contactPoint.",
        example='"sameAs": ["https://www.linkedin.com/company/auriomhq","https://x.com/auriomhq"]',
        severity="medium", weight=7, priority=2, evaluate=check_schema_quality,
    ),
    CheckSpec(
        id="geo.entity_clarity", pillar=PILLAR, category="Entity", title="Entity clarity",
        description="The opening copy states who the organisation is, what it does and who it serves.",
        why="The first 100 words are the most heavily weighted context an engine has. Ambiguous intros produce ambiguous summaries.",
        fix="Open with one plain sentence: “[Brand] is a [category] that helps [audience] [outcome].”",
        example="<p>AuriomHQ is an AI growth partner that helps ambitious businesses grow with AI websites, automation and search visibility.</p>",
        severity="high", weight=8, priority=3, evaluate=check_entity_clarity,
    ),
    CheckSpec(
        id="geo.author_entity", pillar=PILLAR, category="Credibility", title="Author attribution",
        description="Named authors are connected to external identities via Person schema and sameAs.",
        why="Engines weight content by who is accountable for it. A linked author identity is verifiable; an anonymous page is not.",
        fix="Add Person schema with name, jobTitle, url and sameAs (LinkedIn, X, Google Scholar) and link the byline to an author page.",
        example='{"@context":"https://schema.org","@type":"Person","name":"Jane Doe","jobTitle":"Head of SEO","sameAs":["https://www.linkedin.com/in/janedoe"]}',
        severity="high", weight=7, priority=3, evaluate=check_author_entity,
    ),
    CheckSpec(
        id="geo.original_content", pillar=PILLAR, category="Content signals", title="Original, substantive content",
        description="Pages contain substantial original text rather than reused boilerplate.",
        why="Generative engines synthesise from unique, specific material. Templated pages give them nothing new to say, so they are rarely cited.",
        fix="Publish page-specific detail: examples, numbers, process, edge cases and original explanations.",
        example="A service page that explains scope, timeline, deliverables and results — not the same 80-word blurb used site-wide.",
        severity="medium", weight=8, priority=3, evaluate=check_original_content,
    ),
    CheckSpec(
        id="geo.evidence_sources", pillar=PILLAR, category="Content signals", title="Evidence and source attribution",
        description="Claims are supported by outbound links to authoritative sources.",
        why="Citations make content verifiable, and verifiable content is safer for an engine to repeat.",
        fix="Link key claims to primary sources (standards, official docs, studies) and name the source in the text.",
        example='<p>Per the <a href="https://www.nist.gov/itl/ai-risk-management-framework">NIST AI RMF</a>, …</p>',
        severity="medium", weight=7, priority=3, evaluate=check_evidence_sources,
    ),
    CheckSpec(
        id="geo.html_content", pillar=PILLAR, category="Accessibility", title="Information available in HTML",
        description="Core content is server-rendered rather than requiring JavaScript.",
        why="Many AI crawlers do not execute JavaScript. If your content only exists after hydration, it is invisible to them.",
        fix="Server-render or pre-render key content so the HTML contains the text, then hydrate for interactivity.",
        example="<div id=\"root\">…server-rendered HTML with headings and copy…</div>",
        severity="high", weight=8, priority=1, evaluate=check_html_content,
    ),
    CheckSpec(
        id="geo.ai_crawler_access", pillar=PILLAR, category="Access", title="AI crawler directives",
        description="robots.txt does not block known AI crawlers (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, CCBot …).",
        why="If a crawler is disallowed, the content cannot be read at all. This is the single most binary GEO signal there is.",
        fix="Review robots.txt rules for each AI agent you want to allow, and remove disallow rules that block them unintentionally.",
        example="User-agent: GPTBot\nAllow: /\n\nUser-agent: PerplexityBot\nAllow: /",
        severity="critical", weight=9, priority=1, evaluate=check_ai_crawler_access,
    ),
    CheckSpec(
        id="geo.llms_txt", pillar=PILLAR, category="Access", title="llms.txt",
        description="An llms.txt file is published to guide large language models.",
        why="llms.txt is an emerging, community-proposed convention for pointing models at your key content. Adoption is uneven, so treat it as a low-cost bonus.",
        fix="Publish /llms.txt with a short site summary and curated links to your most important pages.",
        example="# AuriomHQ\n> AI growth partner for ambitious businesses\n\n## Core pages\n- [Services](https://auriomhq.work/services)",
        severity="low", weight=5, priority=3, evaluate=check_llms_txt,
    ),
    CheckSpec(
        id="geo.descriptive_structure", pillar=PILLAR, category="Accessibility", title="Descriptive page structure",
        description="Pages use titles, descriptions and headings consistently.",
        why="Structure is how engines decide which passage answers which question. Weak structure means weak passage selection.",
        fix="Give every page a distinct title, description and a heading outline that mirrors your content.",
        example="<h1>AI Visibility Analyzer</h1><h2>What it checks</h2><h2>How scoring works</h2>",
        severity="medium", weight=6, priority=2, evaluate=check_descriptive_structure,
    ),
    CheckSpec(
        id="geo.contact_details", pillar=PILLAR, category="Entity", title="Business contact details",
        description="Contact information (email, address, contact page) is published.",
        why="Contact details are a legitimacy signal for both buyers and engines, and they support local and brand-entity resolution.",
        fix="Publish a contact page with a real email, business address and phone where relevant; mirror it in Organization schema.",
        example='<a href="mailto:hello@example.com">hello@example.com</a> · 12 Example Street, Pune',
        severity="medium", weight=5, priority=3, evaluate=check_contact_details,
    ),
    CheckSpec(
        id="geo.freshness", pillar=PILLAR, category="Content signals", title="Content freshness signals",
        description="Publication and update dates are exposed across the site.",
        why="Engines and buyers use dates to judge whether a page is current. Undated content is treated as stale by default.",
        fix="Show a visible update date and expose dateModified in JSON-LD on every substantive page.",
        example='<time datetime="2026-10-01">Updated 1 October 2026</time>',
        severity="medium", weight=6, priority=3, evaluate=check_freshness,
    ),
    CheckSpec(
        id="geo.semantic_html", pillar=PILLAR, category="Accessibility", title="Semantic HTML landmarks",
        description="Pages use semantic landmarks (main, article, nav, footer).",
        why="Landmarks tell parsers which part of the DOM is the actual content, so boilerplate is less likely to be mistaken for the answer.",
        fix="Wrap primary content in <main>/<article> and keep navigation and footers outside it.",
        example="<main><article><h1>…</h1><p>…</p></article></main>",
        severity="low", weight=4, priority=2, evaluate=check_semantic_html,
    ),
]
