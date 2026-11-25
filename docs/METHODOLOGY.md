# Scoring methodology — AuriomHQ AI Visibility Analyzer

This document is generated from the live check catalogue (`backend/app/analyzers/*.py`)
and is served in-product at `GET /api/methodology` and `/methodology`.

## 1. Pillars and weights

| Pillar | Weight | What it measures |
| --- | --- | --- |
| SEO — Search Engine Optimisation | 40% | Technical and content signals that decide whether a page can be crawled, indexed and matched to a query. |
| AEO — Answer Engine Optimisation | 30% | How directly and clearly the content answers real questions, and whether that structure is machine readable. |
| GEO — Generative Engine Optimisation | 30% | Entity clarity, crawler access, attribution and credibility signals used by generative engines. |

## 2. The formula

```
pillar_score  = round(100 × Σ earned_points ÷ Σ weight_of_tested_checks)
overall_score = Σ(pillar_score × pillar_weight) ÷ Σ(pillar_weight of scored pillars)
```

| Result | Credit | Effect on the score |
| --- | --- | --- |
| Pass | 100% of the check weight | full points |
| Warning | 50–70% depending on the check | partial points |
| Fail | 0% | no points |
| Not tested | excluded from earned **and** available points | cannot be scored as a pass |

Checks that cannot be performed (for example: no images on the page, a single-page crawl, or an
inapplicable HowTo schema) are reported as **Not tested** and removed from the denominator.
An automated evaluator that raises an exception also yields **Not tested**, never a pass.

### Score bands

| Band | Score |
| --- | --- |
| Strong | 85–100 |
| Good | 70–84 |
| Needs work | 55–69 |
| Weak | 35–54 |
| Critical | 0–34 |

## 3. Check catalogue

Total:
**53 checks** across three pillars.

### SEO — 25 checks, 121 points available

| ID | Check | Category | Severity | Weight | Fix priority | Effort |
| --- | --- | --- | --- | --- | --- | --- |
| `seo.https` | HTTPS availability | Technical SEO | Critical | 8 | P1 | Moderate |
| `seo.http_status` | Homepage HTTP status | Technical SEO | Critical | 8 | P1 | Moderate |
| `seo.title` | Page titles | Technical SEO | High | 8 | P2 | Easy |
| `seo.meta_description` | Meta descriptions | Technical SEO | High | 7 | P2 | Easy |
| `seo.canonical` | Canonical URLs | Technical SEO | Medium | 5 | P2 | Easy |
| `seo.robots_meta` | Indexability (robots meta) | Technical SEO | Critical | 6 | P1 | Easy |
| `seo.robots_txt` | robots.txt | Technical SEO | High | 5 | P1 | Easy |
| `seo.sitemap` | XML sitemap | Technical SEO | Medium | 6 | P2 | Moderate |
| `seo.viewport` | Mobile viewport | Technical SEO | High | 6 | P1 | Easy |
| `seo.image_alt` | Image alt text | Content SEO | Medium | 6 | P1 | Moderate |
| `seo.lang` | HTML language declaration | Technical SEO | Low | 3 | P2 | Easy |
| `seo.headings` | Heading hierarchy | Content SEO | High | 5 | P2 | Easy |
| `seo.broken_links` | Broken internal links | Technical SEO | Critical | 8 | P1 | Moderate |
| `seo.duplicate_titles` | Duplicate page titles | Technical SEO | Medium | 4 | P2 | Easy |
| `seo.redirect_chains` | Redirect chains | Technical SEO | Low | 3 | P2 | Moderate |
| `seo.internal_linking` | Internal linking | Content SEO | Medium | 4 | P2 | Moderate |
| `seo.indexable_pages` | Site-wide indexability | Technical SEO | Medium | 4 | P1 | Easy |
| `seo.content_length` | Content depth | Content SEO | Medium | 6 | P2 | Hard |
| `seo.content_structure` | Content structure | Content SEO | Medium | 4 | P2 | Moderate |
| `seo.keyword_alignment` | Topic alignment | Content SEO | Low | 4 | P2 | Easy |
| `seo.anchor_text` | Descriptive anchor text | Content SEO | Low | 3 | P2 | Easy |
| `seo.external_links` | External references | Content SEO | Low | 3 | P3 | Moderate |
| `seo.open_graph` | Social preview metadata | Technical SEO | Low | 2 | P2 | Easy |
| `seo.favicon` | Favicon | Technical SEO | Informational | 1 | P2 | Easy |
| `seo.mixed_content` | Mixed content links | Technical SEO | Low | 2 | P2 | Easy |

### AEO — 13 checks, 98 points available

| ID | Check | Category | Severity | Weight | Fix priority | Effort |
| --- | --- | --- | --- | --- | --- | --- |
| `aeo.faq_section` | FAQ content | Answer content | High | 10 | P3 | Moderate |
| `aeo.question_headings` | Question-style headings | Answer content | High | 10 | P3 | Moderate |
| `aeo.answer_paragraphs` | Direct answer paragraphs | Answer content | High | 8 | P3 | Moderate |
| `aeo.definitions` | Concise definitions | Clarity | Medium | 7 | P3 | Moderate |
| `aeo.lists_steps` | Lists and step-by-step content | Structure | Medium | 7 | P3 | Easy |
| `aeo.structured_content` | Answer-friendly structure | Structure | Medium | 8 | P2 | Moderate |
| `aeo.article_schema` | Article schema | Structured data | High | 9 | P2 | Moderate |
| `aeo.faq_schema` | FAQPage schema | Structured data | High | 8 | P2 | Easy |
| `aeo.howto_schema` | HowTo schema | Structured data | Low | 5 | P2 | Easy |
| `aeo.author_info` | Author information | Credibility | High | 7 | P3 | Easy |
| `aeo.dates` | Publication and update dates | Credibility | Medium | 6 | P3 | Easy |
| `aeo.readability` | Sentence clarity | Clarity | Medium | 7 | P3 | Hard |
| `aeo.answer_accessibility` | Answers available in HTML | Clarity | Medium | 6 | P2 | Moderate |

### GEO — 15 checks, 108 points available

| ID | Check | Category | Severity | Weight | Fix priority | Effort |
| --- | --- | --- | --- | --- | --- | --- |
| `geo.org_identity` | Organisation identity | Entity | Critical | 10 | P3 | Moderate |
| `geo.brand_consistency` | Consistent brand information | Entity | High | 8 | P3 | Easy |
| `geo.schema_presence` | Schema.org structured data | Structured data | High | 10 | P2 | Moderate |
| `geo.schema_quality` | Structured data depth | Structured data | Medium | 7 | P2 | Moderate |
| `geo.entity_clarity` | Entity clarity | Entity | High | 8 | P3 | Moderate |
| `geo.author_entity` | Author attribution | Credibility | High | 7 | P3 | Moderate |
| `geo.original_content` | Original, substantive content | Content signals | Medium | 8 | P3 | Hard |
| `geo.evidence_sources` | Evidence and source attribution | Content signals | Medium | 7 | P3 | Moderate |
| `geo.html_content` | Information available in HTML | Accessibility | High | 8 | P1 | Hard |
| `geo.ai_crawler_access` | AI crawler directives | Access | Critical | 9 | P1 | Easy |
| `geo.llms_txt` | llms.txt | Access | Low | 5 | P3 | Easy |
| `geo.descriptive_structure` | Descriptive page structure | Accessibility | Medium | 6 | P2 | Moderate |
| `geo.contact_details` | Business contact details | Entity | Medium | 5 | P3 | Easy |
| `geo.freshness` | Content freshness signals | Content signals | Medium | 6 | P3 | Easy |
| `geo.semantic_html` | Semantic HTML landmarks | Accessibility | Low | 4 | P2 | Easy |

## 4. What the score does **not** measure

- Search rankings, impressions, clicks or traffic.
- Backlink profiles, domain authority or competitor visibility.
- Google index status (only on-page indexability signals are measured).
- Observed AI citations or recommendations in ChatGPT, Gemini, Perplexity or any other engine.
- Core Web Vitals or real-user performance (no rendering browser is used).

Those require external data providers and are deliberately excluded rather than estimated.

## 5. Reproducibility

Scoring is deterministic. Given the same HTML and configuration, the same crawl produces the
same score. Every point can be traced to a row in the report: the evidence string next to each
check is quoted from the crawled page.
