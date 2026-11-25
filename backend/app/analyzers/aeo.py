"""AEO (Answer Engine Optimisation) analysis engine.

The question this engine answers: *if an engine wanted to extract a direct
answer from this page, is the answer there, clearly written and machine
readable?*

Nothing here claims that structured data guarantees rich results or AI
citations — it only measures readiness.
"""
from __future__ import annotations

from ..crawler import CrawlResult
from .base import (
    FAIL, NOT_TESTED, PASS, WARNING, CheckSpec, Outcome, analysable_pages, average, home,
    pct, quote,
)

PILLAR = "aeo"


def _pages(crawl: CrawlResult):
    return analysable_pages(crawl)


def _primary(crawl: CrawlResult):
    pages = _pages(crawl)
    return home(crawl) or (pages[0] if pages else None)


def _site_schema_types(crawl: CrawlResult) -> set[str]:
    types: set[str] = set()
    for page in crawl.pages:
        types.update(page.schema_types)
    return types


def check_faq_section(crawl: CrawlResult) -> Outcome:
    p = _primary(crawl)
    if not p:
        return Outcome(NOT_TESTED, "No HTML content was available.")
    if p.faq_like_sections >= 1:
        sample = (p.question_headings[:3] or p.h2s[:3])
        return Outcome(
            PASS,
            f"FAQ / question-answer content detected ({p.faq_like_sections} section signal(s)). Example headings: {quote(' | '.join(sample), 160)}",
        )
    return Outcome(
        FAIL,
        f"No FAQ or question-and-answer block was detected in the {p.word_count}-word homepage HTML.",
    )


def check_question_headings(crawl: CrawlResult) -> Outcome:
    p = _primary(crawl)
    if not p:
        return Outcome(NOT_TESTED, "No HTML content was available.")
    q = p.question_headings
    if len(q) >= 3:
        return Outcome(PASS, f"{len(q)} question-style headings found, e.g. {quote(' | '.join(q[:3]), 170)}")
    if q:
        return Outcome(WARNING, f"Only {len(q)} question-style heading(s) found: {quote(' | '.join(q), 150)}", 0.6)
    return Outcome(FAIL, "No question-style headings (e.g. “How does it work?”) were found on the primary page.")


def check_answer_paragraphs(crawl: CrawlResult) -> Outcome:
    p = _primary(crawl)
    if not p:
        return Outcome(NOT_TESTED, "No HTML content was available.")
    if p.question_answer_pairs >= 3:
        sample = quote(p.answer_examples[0], 150) if p.answer_examples else ""
        return Outcome(PASS, f"{p.question_answer_pairs} headings are followed by a direct answer paragraph. Example: {sample}")
    if p.question_answer_pairs >= 1:
        sample = quote(p.answer_examples[0], 150) if p.answer_examples else ""
        return Outcome(
            WARNING,
            f"Only {p.question_answer_pairs} heading(s) are immediately followed by a short answer paragraph. Example: {sample}",
            0.55,
        )
    if p.question_headings:
        return Outcome(
            FAIL,
            f"{len(p.question_headings)} question heading(s) exist but none is followed by a concise answer paragraph (40–90 words).",
        )
    return Outcome(FAIL, "No question heading + answer paragraph pattern was found.")


def check_definitions(crawl: CrawlResult) -> Outcome:
    p = _primary(crawl)
    if not p:
        return Outcome(NOT_TESTED, "No HTML content was available.")
    if p.has_definition_list or p.definition_sentences >= 2:
        return Outcome(
            PASS,
            f"{p.definition_sentences} concise definition-style sentence(s) detected"
            + (" plus a <dl> definition list" if p.has_definition_list else "")
            + ".",
        )
    if p.definition_sentences == 1:
        return Outcome(WARNING, "Only one definition-style sentence was detected; add short, quotable definitions of key terms.", 0.5)
    return Outcome(FAIL, "No clear, self-contained definitions of the site's key terms were detected.")


def check_lists_and_steps(crawl: CrawlResult) -> Outcome:
    p = _primary(crawl)
    if not p:
        return Outcome(NOT_TESTED, "No HTML content was available.")
    if p.step_like_sections and p.list_items >= 5:
        return Outcome(PASS, f"Step-by-step content is present ({p.step_like_sections} process section(s), {p.list_items} list items).")
    if p.list_items >= 5 or p.step_like_sections:
        return Outcome(
            WARNING,
            f"Some structured lists exist ({p.list_items} list items, {p.step_like_sections} process section(s)) but no clear numbered workflow.",
            0.6,
        )
    return Outcome(FAIL, f"Almost no structured lists or steps were found ({p.list_items} list items, {p.step_like_sections} process sections).")


def check_structured_content(crawl: CrawlResult) -> Outcome:
    p = _primary(crawl)
    if not p:
        return Outcome(NOT_TESTED, "No HTML content was available.")
    signals = sum([
        len(p.h2s) >= 2,
        p.paragraphs and len(p.paragraphs) >= 4,
        p.list_items >= 3,
        p.has_table or p.has_definition_list,
        p.faq_like_sections >= 1,
    ])
    if signals >= 4:
        return Outcome(PASS, f"Content is well structured ({len(p.h2s)} H2 sections, {len(p.paragraphs)} paragraphs, {p.list_items} list items).")
    if signals == 3:
        return Outcome(WARNING, f"Content structure is partial ({signals}/5 structure signals present).", 0.6)
    return Outcome(FAIL, f"Content structure is weak ({signals}/5 structure signals present) — answers are hard to isolate.")


def check_article_schema(crawl: CrawlResult) -> Outcome:
    types = _site_schema_types(crawl)
    found = sorted(types & {"Article", "BlogPosting", "NewsArticle", "TechArticle", "ScholarlyArticle", "Report"})
    if found:
        return Outcome(PASS, f"Article-type structured data found: {', '.join(found)}.")
    others = sorted(t for t in types if t in {"WebSite", "WebPage", "Organization", "LocalBusiness"})
    if others:
        return Outcome(WARNING, f"No Article/BlogPosting schema. Only {', '.join(others)} schema was found.", 0.4)
    return Outcome(FAIL, "No Article or BlogPosting structured data was found on the crawled pages.")


def check_faq_schema(crawl: CrawlResult) -> Outcome:
    types = _site_schema_types(crawl)
    if {"FAQPage", "QAPage"} & types:
        return Outcome(PASS, f"FAQ structured data is present ({', '.join(sorted({'FAQPage', 'QAPage'} & types))}).")
    faq_content = any(p.faq_like_sections for p in crawl.pages)
    if faq_content:
        return Outcome(
            WARNING,
            "FAQ-style content exists but is not marked up with FAQPage schema, so engines must infer the pairs.",
            0.35,
        )
    return Outcome(FAIL, "No FAQPage or QAPage structured data was found.")


def check_howto_schema(crawl: CrawlResult) -> Outcome:
    types = _site_schema_types(crawl)
    has_process = any(p.step_like_sections >= 1 or p.has_ordered_list for p in crawl.pages)
    if "HowTo" in types:
        return Outcome(PASS, "HowTo structured data is present on the site.")
    if not has_process:
        return Outcome(
            NOT_TESTED,
            "The site does not publish step-by-step instructional content, so HowTo schema is not applicable. No score awarded.",
        )
    return Outcome(WARNING, "Step-by-step content exists but no HowTo structured data accompanies it.", 0.3)


def check_author_info(crawl: CrawlResult) -> Outcome:
    p = _primary(crawl)
    if not p:
        return Outcome(NOT_TESTED, "No HTML content was available.")
    if p.author_meta or p.author_schema:
        source = "Person schema" if p.author_schema else "meta/rel author"
        return Outcome(PASS, f"Author attribution found via {source}: {quote(p.author_schema or p.author_meta, 90)}")
    site_author = next((pg.author_meta or pg.author_schema for pg in crawl.pages if pg.author_meta or pg.author_schema), "")
    if site_author:
        return Outcome(WARNING, f"Author attribution exists on some pages but not the primary page: {quote(site_author, 80)}", 0.5)
    return Outcome(FAIL, "No author attribution (byline, meta author or Person schema) was found.")


def check_dates(crawl: CrawlResult) -> Outcome:
    p = _primary(crawl)
    if not p:
        return Outcome(NOT_TESTED, "No HTML content was available.")
    any_page = next((pg for pg in crawl.pages if pg.published_date or pg.modified_date), None)
    if not any_page:
        return Outcome(FAIL, "No publication or modification dates were found in the HTML.")
    if p.published_date or p.modified_date:
        bits = []
        if p.published_date:
            bits.append(f"published {p.published_date[:10]}")
        if p.modified_date:
            bits.append(f"modified {p.modified_date[:10]}")
        return Outcome(PASS, f"Dates are exposed on the primary page ({', '.join(bits)}).")
    return Outcome(WARNING, f"Dates exist on other pages but not the primary page (e.g. {any_page.url}).", 0.5)


def check_readability(crawl: CrawlResult) -> Outcome:
    pages = [p for p in _pages(crawl) if p.avg_sentence_words > 0]
    if not pages:
        return Outcome(NOT_TESTED, "There was not enough prose to measure sentence length.")
    avg = average(p.avg_sentence_words for p in pages)
    longest = max(pages, key=lambda p: p.avg_sentence_words)
    if avg <= 22:
        return Outcome(PASS, f"Average sentence length is {avg} words — comfortably readable.")
    if avg <= 28:
        return Outcome(WARNING, f"Average sentence length is {avg} words; shorten for answer extraction.", 0.6)
    return Outcome(
        FAIL,
        f"Average sentence length is {avg} words (highest: {longest.avg_sentence_words} on {longest.url}). Long sentences are harder for engines to quote cleanly.",
    )


def check_answer_accessibility(crawl: CrawlResult) -> Outcome:
    p = _primary(crawl)
    if not p:
        return Outcome(NOT_TESTED, "No HTML content was available.")
    if p.word_count < 150:
        return Outcome(FAIL, f"Only {p.word_count} words are available in the HTML — there is very little to answer with.")
    signals = sum([p.has_summary_block, p.text_html_ratio >= 0.08, len(p.paragraphs) >= 4])
    if signals == 3:
        return Outcome(
            PASS,
            f"Answers are directly available in the HTML ({p.word_count} words, text/HTML ratio {pct(p.text_html_ratio)}, summary block present).",
        )
    if signals == 2:
        return Outcome(WARNING, "Content is present in HTML but there is no concise summary/TL;DR block to anchor an answer.", 0.6)
    return Outcome(
        WARNING,
        f"Mostly markup rather than readable text (text/HTML ratio {pct(p.text_html_ratio)} across {p.word_count} words).",
        0.4,
    )


AEO_CHECKS: list[CheckSpec] = [
    CheckSpec(
        id="aeo.faq_section", pillar=PILLAR, category="Answer content", title="FAQ content",
        description="The page includes a FAQ or question-and-answer section.",
        why="FAQ blocks are the most direct source of extractable answers and map onto the long-tail questions buyers actually ask.",
        fix="Add a short FAQ (5–8 real customer questions) near the point of decision, each with a 40–80 word answer.",
        example="<h2>Frequently asked questions</h2>\n<h3>How long does an AI visibility audit take?</h3>\n<p>Most audits finish in under a minute…</p>",
        severity="high", weight=10, priority=3, evaluate=check_faq_section,
    ),
    CheckSpec(
        id="aeo.question_headings", pillar=PILLAR, category="Answer content", title="Question-style headings",
        description="Headings are phrased as the questions users ask.",
        why="Question headings match how people phrase queries to ChatGPT, Perplexity and Google, and they mark the passage an engine can lift.",
        fix="Rewrite informational headings as questions (“What is GEO?”) and answer them in the next paragraph.",
        example="<h2>What is generative engine optimisation?</h2>",
        severity="high", weight=10, priority=3, evaluate=check_question_headings,
    ),
    CheckSpec(
        id="aeo.answer_paragraphs", pillar=PILLAR, category="Answer content", title="Direct answer paragraphs",
        description="Question headings are immediately followed by a concise answer.",
        why="Answer engines extract the first self-contained paragraph under a heading. If the answer is buried three paragraphs later, it is often skipped.",
        fix="Put a 40–90 word answer directly under each question heading, then expand with detail.",
        example="<h3>What does an AI visibility audit measure?</h3>\n<p>It measures three things: technical SEO health, answer readiness (AEO) and generative-search readiness (GEO)…</p>",
        severity="high", weight=8, priority=3, evaluate=check_answer_paragraphs,
    ),
    CheckSpec(
        id="aeo.definitions", pillar=PILLAR, category="Clarity", title="Concise definitions",
        description="Key terms are defined in short, quotable sentences.",
        why="Definitions are the highest-confidence pattern for LLM retrieval: the model can quote “X is Y” without inventing context.",
        fix="Add one-sentence definitions for your core terms, ideally in a glossary or inline at first use.",
        example="<p><strong>GEO</strong> is the practice of structuring a website so generative engines can understand and cite it.</p>",
        severity="medium", weight=7, priority=3, evaluate=check_definitions,
    ),
    CheckSpec(
        id="aeo.lists_steps", pillar=PILLAR, category="Structure", title="Lists and step-by-step content",
        description="Processes are expressed as ordered steps or lists.",
        why="“How do I…?” queries are answered from lists and numbered steps far more reliably than from prose.",
        fix="Convert processes into ordered lists with one action per item, starting each with a verb.",
        example="<ol><li>Enter your URL</li><li>Run the audit</li><li>Export the PDF report</li></ol>",
        severity="medium", weight=7, priority=3, evaluate=check_lists_and_steps,
    ),
    CheckSpec(
        id="aeo.structured_content", pillar=PILLAR, category="Structure", title="Answer-friendly structure",
        description="Headings, paragraphs and lists combine to make answers extractable.",
        why="Retrieval systems chunk pages by heading. Clear sections with self-contained paragraphs produce better chunks and better citations.",
        fix="Keep sections short and self-contained: one idea per H2, 2–4 sentences per paragraph.",
        example="<h2>Pricing</h2><p>Audits start at …</p><ul><li>One-off audit</li><li>Ongoing programme</li></ul>",
        severity="medium", weight=8, priority=2, evaluate=check_structured_content,
    ),
    CheckSpec(
        id="aeo.article_schema", pillar=PILLAR, category="Structured data", title="Article schema",
        description="Article/BlogPosting structured data is present.",
        why="Article schema gives machines explicit headline, author and date fields instead of forcing them to infer from layout.",
        fix="Add Article or BlogPosting JSON-LD to every editorial page, including headline, author, datePublished and image.",
        example='{"@context":"https://schema.org","@type":"Article","headline":"…","author":{"@type":"Person","name":"…"},"datePublished":"2026-01-12"}',
        severity="high", weight=9, priority=2, evaluate=check_article_schema,
    ),
    CheckSpec(
        id="aeo.faq_schema", pillar=PILLAR, category="Structured data", title="FAQPage schema",
        description="FAQ content is marked up with FAQPage structured data.",
        why="FAQPage markup states question/answer pairs explicitly. Note: this improves machine understanding — it does not guarantee rich results or citations.",
        fix="Mirror each visible FAQ question and answer in FAQPage JSON-LD, keeping the text identical to the page.",
        example='{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":"…","acceptedAnswer":{"@type":"Answer","text":"…"}}]}',
        severity="high", weight=8, priority=2, evaluate=check_faq_schema,
    ),
    CheckSpec(
        id="aeo.howto_schema", pillar=PILLAR, category="Structured data", title="HowTo schema",
        description="Instructional content is marked up with HowTo structured data (where applicable).",
        why="HowTo markup labels each step as a discrete unit, which is exactly the structure step-by-step answers need.",
        fix="Where the page genuinely teaches a process, add HowTo JSON-LD with named steps; skip it for marketing pages.",
        example='{"@context":"https://schema.org","@type":"HowTo","name":"Run an AI visibility audit","step":[{"@type":"HowToStep","text":"Enter your URL"}]}',
        severity="low", weight=5, priority=2, evaluate=check_howto_schema,
    ),
    CheckSpec(
        id="aeo.author_info", pillar=PILLAR, category="Credibility", title="Author information",
        description="Content is attributed to a named author or organisation.",
        why="Attribution is a core part of E-E-A-T: engines prefer content they can trace to a responsible, identifiable source.",
        fix="Add a visible byline linked to an author page, plus Person schema with jobTitle and sameAs profiles.",
        example='<p>Written by <a href="/authors/jane-doe">Jane Doe</a>, Head of SEO</p>',
        severity="high", weight=7, priority=3, evaluate=check_author_info,
    ),
    CheckSpec(
        id="aeo.dates", pillar=PILLAR, category="Credibility", title="Publication and update dates",
        description="Pages expose publication and last-modified dates.",
        why="Freshness is used to rank and to decide whether an answer is current; missing dates leave engines guessing.",
        fix="Show a visible “Updated 12 March 2026” line and expose datePublished/dateModified in schema.",
        example='<time datetime="2026-03-12">Updated 12 March 2026</time>',
        severity="medium", weight=6, priority=3, evaluate=check_dates,
    ),
    CheckSpec(
        id="aeo.readability", pillar=PILLAR, category="Clarity", title="Sentence clarity",
        description="Sentences are short enough to quote cleanly.",
        why="Answer engines quote sentences, not paragraphs. Long, clause-heavy sentences are usually paraphrased or dropped.",
        fix="Target an average of 15–20 words per sentence and split compound sentences.",
        example="“Long sentence with several clauses that qualifies everything” ⇒ three short sentences.",
        severity="medium", weight=7, priority=3, evaluate=check_readability,
    ),
    CheckSpec(
        id="aeo.answer_accessibility", pillar=PILLAR, category="Clarity", title="Answers available in HTML",
        description="Answer content is present as readable HTML text with a summary.",
        why="If an answer only appears after JavaScript renders or behind an interaction, many crawlers never see it.",
        fix="Server-render the core answer text and add a short summary/TL;DR at the top of long pages.",
        example="<h2>In short</h2><p>Your site scores 62/100 for AI visibility because…</p>",
        severity="medium", weight=6, priority=2, evaluate=check_answer_accessibility,
    ),
]
