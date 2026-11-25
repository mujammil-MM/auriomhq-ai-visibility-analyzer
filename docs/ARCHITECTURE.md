# Architecture — AuriomHQ AI Visibility Analyzer

## 1. System overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Browser (React 18 + TypeScript + Tailwind)                               │
│   Landing → Progress → Dashboard (Overview│SEO│AEO│GEO│Recs│Pages)      │
│   Shared report  ·  Methodology  ·  Lead form  ·  PDF download           │
└───────────────▲──────────────────────────────────────────────────────────┘
                │ JSON over HTTPS (same origin, no secrets in the bundle)
┌───────────────┴──────────────────────────────────────────────────────────┐
│ FastAPI application (Python 3.12)                                        │
│                                                                          │
│  routers/audits.py    POST /api/audits · GET /api/audits/{id}            │
│                       GET /pdf · POST /share · DELETE /share             │
│  routers/reports.py   GET /api/reports/{token} · /pdf                    │
│  routers/leads.py     POST /api/leads                                    │
│  main.py              /api/config · /api/methodology · /api/health       │
│                       static SPA hosting + security headers              │
│                                                                          │
│  jobs.py        background audit orchestration + live progress registry  │
│  security.py    URL validation, SSRF/DNS-rebinding guard, rate limiting  │
│  crawler.py     safe fetch, robots.txt, sitemap, link discovery          │
│  analyzers/     seo.py · aeo.py · geo.py · scoring.py · recommendations  │
│  ai.py          optional LLM layer (provider replaceable, evidence-only) │
│  report.py      canonical audit payload (dashboard + share + PDF source) │
│  pdf.py         ReportLab renderer                                        │
│  db.py          SQLite persistence (audits, leads, events)               │
└───────────────▲──────────────────────────────────────────────────────────┘
                │ guarded outbound HTTPS (pinned IP, Host header, SNI)
        ┌───────┴────────┐
        │ Target website │  (public HTML only, no JS execution)
        └────────────────┘
```

## 2. Module responsibilities

| Module | Responsibility |
| --- | --- |
| `security.py` | Rejects non-http(s) schemes, credentials, exotic ports, control characters and internal hostnames. Resolves DNS once, requires **every** resolved IP to be public, then connects to that IP with the original `Host` header and TLS SNI — closing the DNS-rebinding (TOCTOU) window. Redirects are re-validated at each hop. Token-bucket rate limiting per hashed client IP. |
| `crawler.py` | BFS crawl with a configurable page cap (default 10, hard cap 25). Reads `robots.txt` (per-agent rules + crawl-delay + sitemap declarations), `sitemap.xml` (index + children), `llms.txt`. Detects redirect chains/loops, timeouts, non-HTML responses, size-capped streaming reads, broken internal links and inaccessible pages. Parses titles, metadata, headings, images, links, JSON-LD/microdata, text statistics, question/answer patterns and entity signals. Never executes JavaScript. |
| `analyzers/base.py` | `CheckSpec` (metadata + evaluator) and `CheckResult` (status, severity, weight, credit, earned points, evidence, why, fix, example). A failing evaluator yields **Not tested**, never a pass. |
| `analyzers/seo.py` | 25 technical and content SEO checks. |
| `analyzers/aeo.py` | 13 answer-readiness checks (FAQ, question headings, answer paragraphs, definitions, lists/steps, Article/FAQ/HowTo schema, author, dates, readability, HTML availability). |
| `analyzers/geo.py` | 15 generative-readiness checks (organisation identity, brand consistency, schema presence/depth, entity clarity, author entity, originality, citations, HTML content, AI crawler directives, llms.txt, structure, contact details, freshness, semantic HTML). |
| `analyzers/scoring.py` | Weighted scoring with partial credit, exclusion of untested checks, per-pillar and per-category breakdowns, weighted overall score, human-readable explanation. |
| `analyzers/recommendations.py` | Converts failures/warnings into a three-tier roadmap with impact, difficulty, benefit and guidance; drafts title/meta/heading/FAQ/schema suggestions strictly from crawled text. |
| `ai.py` | Optional, provider-agnostic LLM pass over the crawl evidence pack. Degrades silently to the deterministic engine. |
| `report.py` | Single canonical payload consumed by the dashboard, the share endpoint and the PDF renderer. |
| `pdf.py` | ReportLab document: branded cover, score dashboard, executive summary, site snapshot, critical findings, category performance, full check tables, roadmap, drafts, methodology, limitations, CTA. |
| `db.py` | SQLite (WAL) storage for audits, leads and events. Only metadata, findings and explicitly submitted lead data are stored; client IPs are stored as salted hashes. |

## 3. Audit lifecycle

1. `POST /api/audits` validates the URL (fast, no DNS) and applies the per-IP rate limit; returns `202` with an audit id.
2. `jobs.start_audit` runs a background task under a concurrency semaphore.
3. Progress events (`stage`, `message`, `percent`, `detail`) are pushed to an in-process registry and mirrored into SQLite.
4. The frontend polls `GET /api/audits/{id}` every ~1.1 s and renders the live timeline.
5. On completion: crawl → 53 checks → scores → recommendations → rule-based summary → optional AI enhancement → persisted payload.
6. Dashboard, share link and PDF all read the same stored payload.

## 4. Security posture

- SSRF: scheme/host/port allow-list, private/loopback/link-local/metadata IP blocking (IPv4 + IPv6), DNS resolved before connecting, connection pinned to the validated IP, every redirect hop re-validated, `trust_env=False` so proxy env vars cannot reroute traffic.
- Resource limits: connect/read/total timeouts, 3 MB response cap, max 5 redirects, page cap, per-host politeness delay, link-check cap, global concurrency cap.
- No JavaScript execution, no authenticated areas, no form submissions, no cookies persisted.
- Secrets exist only in server environment variables. The frontend bundle contains no keys.
- Security headers on every response; API responses marked `Cache-Control: no-store`.
- Share links are unguessable tokens, revocable, and return `404` when private.

## 5. Extensibility

- **New check**: add a `CheckSpec` with an evaluator and weight to `seo.py` / `aeo.py` / `geo.py`. It appears automatically in the API, methodology page, dashboard, PDF and scoring.
- **New crawler capability** (e.g. hreflang, Core Web Vitals via a rendering worker): extend `parse_page` and add fields to `PageSnapshot`; existing checks are unaffected.
- **Alternative storage**: `db.py` is the only persistence module; swap the four async functions for Postgres/Supabase.
- **Alternative AI provider**: any OpenAI-compatible chat endpoint via `AI_BASE_URL` / `AI_MODEL`.
- **Queue-based crawling**: replace the in-process task in `jobs.py` with a worker queue; the progress contract stays identical.
