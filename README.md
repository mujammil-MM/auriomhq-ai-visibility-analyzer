# AuriomHQ — AI Visibility Analyzer

**Make your website visible everywhere people search.**

A production-minded web application that crawls a real website and scores its readiness for
**SEO** (search), **AEO** (answer engines) and **GEO** (generative / AI search), then explains every
finding with evidence from the site's own HTML, generates a prioritised roadmap, exports a branded
PDF and creates shareable reports — with an AuriomHQ lead-capture path at the point of highest intent.

- **Brand:** AuriomHQ · **Product:** AI Visibility Analyzer
- **Primary CTA:** Analyse My Website
- **Live deployment:** https://auriomhq-ai-visibility-analyzer.vercel.app
- **Live surface:** `/` (analyzer), `/methodology`, `/audit/{id}` (results), `/r/{token}` (shared report)

> This repository is a standalone application. It does not modify or replace the existing
> `auriomhq.work` site — it can be served on its own subdomain (`analyzer.auriomhq.work`) or mounted
> behind a reverse proxy at a subpath. See [Deployment](#10-deployment).

---

## 1. Quick start

### Local (recommended)

```bash
cd auriomhq-analyzer
./run.sh                 # creates .env, installs deps, builds frontend, starts the server
# → http://localhost:8000
```

`run.sh` is idempotent: it only installs/builds what is missing. If the runtime was reset
(e.g. a fresh sandbox/container), re-running it restores Python packages — workspace files,
the built frontend and the SQLite database persist, installed packages do not.

### Manual

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install && npm run build && cd ..   # builds into backend/static

cp .env.example .env                                   # optional: configure secrets
cd backend && ../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend development (hot reload)

```bash
cd backend && python -m uvicorn app.main:app --port 8000     # terminal 1 (API)
cd frontend && npm run dev                                   # terminal 2 (Vite on :5173, proxies /api)
```

### Docker

```bash
cp .env.example .env
docker compose up --build      # → http://localhost:8000
```

---

## 2. What a run actually does

1. **Validate** — scheme/host/port checks, DNS resolution, SSRF guard (see [Security](#9-security-model)).
2. **Crawl** — homepage + up to 10 discovered internal pages (configurable), respecting `robots.txt`,
   reading `sitemap.xml` and `llms.txt`, following and validating every redirect hop.
3. **Parse** — titles, meta descriptions, canonicals, robots directives, headings, images and alt text,
   internal/external links and anchor text, JSON-LD/microdata, text statistics, question/answer
   patterns, entity and contact signals.
4. **Score** — 53 weighted checks (25 SEO, 13 AEO, 15 GEO) → three pillar scores + one overall score.
5. **Recommend** — three-tier roadmap, drafted titles/descriptions/headings/FAQ questions/JSON-LD,
   all derived from the crawled evidence.
6. **Deliver** — dashboard, PDF report, shareable link, lead form.

No step uses sample, seeded or random data. Every number in the UI, PDF and share link comes from the
stored audit payload produced by that crawl.

---

## 3. Architecture

```
frontend/                      React 18 + TypeScript + Tailwind (Vite build → backend/static)
  src/pages/                   Landing · AuditPage · SharedReportPage · MethodologyPage
  src/components/              Dashboard, CheckList, Charts, Recommendations, PagesTable,
                               ProgressTimeline, ShareDialog, LeadForm, ScoreRing, Primitives
  src/lib/                     api client, types, formatting helpers

backend/app/
  main.py                      FastAPI app, static SPA hosting, config/methodology endpoints
  config.py                    environment-driven settings (no secrets in code)
  security.py                  URL validation, SSRF + DNS-rebinding guard, rate limiters
  crawler.py                   safe fetch, robots/sitemap/llms.txt, discovery, parsing
  analyzers/
    base.py                    CheckSpec / CheckResult / outcome contract
    seo.py  aeo.py  geo.py     25 + 13 + 15 checks with evidence, why, fix, example
    scoring.py                 weighted model, partial credit, categories, explanation
    recommendations.py         roadmap, quick wins, content drafts
  ai.py                        optional provider-replaceable LLM layer
  report.py                    canonical audit payload (dashboard + share + PDF)
  pdf.py                       ReportLab report (8–10 pages, branded)
  db.py                        SQLite persistence (audits, leads, events)
  routers/                     audits · reports (share tokens) · leads

tests/                         63 tests: security, scoring, crawler, analyzers, API end-to-end
docs/ARCHITECTURE.md           module responsibilities & extension points
docs/METHODOLOGY.md            full check catalogue, weights and formula (generated from code)
```

Full details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 4. Completed features

### Core audit engine
- [x] URL submission with strict validation (bare domains normalised to `https://`).
- [x] Real crawling: homepage + internal discovery, up to a configurable page cap (default 10, hard cap 25).
- [x] `robots.txt` parsing with per-agent rules, crawl-delay and sitemap declarations; disallowed URLs are skipped and reported.
- [x] `sitemap.xml` (including sitemap indexes and child sitemaps) and `llms.txt` detection.
- [x] Broken internal link verification, inaccessible page detection, redirect chain & loop detection.
- [x] Timeouts, non-HTML responses, DNS failures and unreachable hosts produce specific, actionable errors.
- [x] No JavaScript execution — analysis is performed on the HTML the server returns (stated in the report).

### Analysis & scoring
- [x] 25 SEO checks (technical + content), 13 AEO checks, 15 GEO checks — each with id, category, description, result, severity, weight, evidence, why, fix and example.
- [x] `Pass` / `Warning` / `Fail` / `Not tested` states; untested checks are excluded from both numerator and denominator.
- [x] Weighted scoring with documented partial credit for warnings; three pillar scores plus a weighted overall score (SEO 40%, AEO 30%, GEO 30%).
- [x] Category breakdown, severity distribution and per-pillar explanation surfaced in the UI and PDF.
- [x] Public methodology page and `GET /api/methodology` generated from the live check catalogue.

### Recommendations
- [x] Priority 1 (fix immediately) / Priority 2 (discoverability) / Priority 3 (AI readiness) roadmap.
- [x] Impact (High/Medium/Low), difficulty (Easy/Moderate/Hard), expected benefit, implementation guidance and example per item.
- [x] Draft titles, meta descriptions, heading outline, FAQ questions and JSON-LD blocks generated from crawled text.
- [x] Optional AI layer (OpenAI-compatible, server-side only) that rewrites summary wording from the evidence pack; the product is fully functional without it.

### Product surface
- [x] Premium responsive dashboard: score cards, rings, bars, category table, severity distribution, quick wins.
- [x] Six tabs: Overview, SEO, AEO, GEO, Recommendations, Crawled pages — with issue drill-down (what / why / evidence / fix / example).
- [x] Real progress interface with staged timeline and live log, driven by server-sent progress events.
- [x] PDF report: cover, score dashboard, executive summary, site snapshot, critical findings, category performance, full check tables, roadmap, drafts, methodology, limitations, AuriomHQ CTA.
- [x] Shareable read-only report links with public/private toggle and revocation.
- [x] Contextual CTA + working lead form (name, business, work email, website, interest, message) persisted server-side, with optional webhook delivery.
- [x] Per-browser audit history for anonymous users (localStorage) — no account required.

### Engineering
- [x] 63 automated tests covering the 10 required scenarios, scoring maths, evidence accuracy and security restrictions.
- [x] Docker + docker-compose, `.env.example`, idempotent `run.sh`.
- [x] No secrets in the frontend bundle; all configuration server-side.

---

## 5. Deliberately not implemented (and why)

| Item | Status | Notes / alternative |
| --- | --- | --- |
| User accounts, login, cross-device audit history | **Not implemented** | The spec makes this conditional ("if authentication is implemented"). Anonymous users get shareable reports plus per-browser history. Adding Supabase Auth would mean: `user_id` column on `audits`, a history endpoint and an `/account` route — the storage layer is already isolated in `db.py`. |
| Audit comparison / trend charts | **Not implemented** | Depends on stored history per user. Share tokens + stable schema make this straightforward to add later. |
| Keyword rankings, search volume, backlink data, Google index status | **Out of scope by design** | Requires paid third-party APIs. Never estimated or faked — documented in-product. |
| Core Web Vitals / real-user performance | **Out of scope by design** | Requires a rendering browser and field data (CrUX). Would be a separate worker; halved page throughput, so excluded from this prototype. |
| JavaScript rendering | **Out of scope by design** | The crawler reads server HTML only; JS-only shells are explicitly flagged as a GEO failure (`geo.html_content`). |
| Email delivery of reports / lead notifications | **Not implemented** | Lead delivery is: (1) SQLite persistence — the success condition, (2) optional `LEAD_WEBHOOK_URL` POST to Slack/Zapier/CRM. No SMTP credentials were available in this environment, so email is documented as a webhook integration instead. |
| Distributed crawl queue / multi-instance rate limiting | **Not implemented** | In-process task registry and token buckets. For horizontal scaling, replace with Redis (rate limit) and a worker queue; the API contracts do not change. |
| Payment / plan gating | **Not implemented** | Out of scope for the prototype. |

---

## 6. Scoring model (summary)

```
pillar_score  = round(100 × Σ earned_points ÷ Σ weight_of_tested_checks)
overall_score = Σ(pillar_score × pillar_weight) ÷ Σ(pillar_weight of scored pillars)
```

| Result | Credit |
| --- | --- |
| Pass | 100% of the check weight |
| Warning | 50–70% depending on the check |
| Fail | 0% |
| Not tested | excluded from **both** earned and available points — never a pass |

Full catalogue (53 checks with weights, severities and fix priorities) → [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md)
or the in-product page at `/methodology`.

---

## 7. Environment variables

All optional except where noted. Copy `.env.example` → `.env`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | Enables uvicorn reload when set to `development` |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Bind address |
| `DATABASE_PATH` | `./data/auriomhq.db` | SQLite file (mount a volume in production) |
| `STATIC_DIR` | `./backend/static` | Built frontend location |
| `PUBLIC_BASE_URL` | *(empty)* | Absolute base for share links (set behind a proxy) |
| `TRUST_PROXY` | `0` | `1` trusts `X-Forwarded-For/Proto/Host` (only behind a trusted proxy) |
| `CORS_ORIGINS` | *(empty)* | Only needed if the API and UI are on different origins |
| `IP_HASH_SALT` | `change-me…` | Salt for hashed client IPs used in rate limiting — **set in production** |
| `CRAWLER_USER_AGENT` | `AuriomHQ-AI-Visibility-Analyzer/1.0 …` | Identifies the audit bot |
| `CRAWL_MAX_PAGES` | `10` | Pages per audit (hard cap `CRAWL_MAX_PAGES_HARD_LIMIT`, default 25) |
| `CRAWL_CONNECT_TIMEOUT` / `CRAWL_READ_TIMEOUT` | `8` / `15` s | Network timeouts |
| `CRAWL_TOTAL_TIMEOUT` | `120` s | Total crawl budget |
| `CRAWL_MAX_RESPONSE_BYTES` | `3000000` | Response size cap (streamed, truncated) |
| `CRAWL_MAX_REDIRECTS` | `5` | Redirect cap (each hop re-validated) |
| `CRAWL_LINK_CHECK_LIMIT` | `25` | Broken-link probes per audit |
| `CRAWL_PER_HOST_DELAY` | `0.35` s | Politeness delay between requests |
| `CRAWL_ALLOW_PRIVATE_TARGETS` | `0` | **Development only.** Never enable in production |
| `RATE_LIMIT_WINDOW_SECONDS` / `RATE_LIMIT_AUDITS_PER_WINDOW` | `600` / `10` | Per-IP audit limit |
| `MAX_CONCURRENT_AUDITS` | `3` | Global concurrency cap |
| `AI_ENABLED` | `0` | Turns on the optional LLM layer |
| `AI_PROVIDER` / `AI_BASE_URL` / `AI_MODEL` | `openai` / `https://api.openai.com/v1` / `gpt-4o-mini` | Any OpenAI-compatible endpoint |
| `AI_API_KEY` | *(empty)* | Server-side only; never exposed to the browser |
| `AI_TIMEOUT_SECONDS` | `45` | Provider timeout |
| `BRAND_NAME` / `PRODUCT_NAME` | `AuriomHQ` / `AI Visibility Analyzer` | Used in UI, PDF and metadata |
| `BRAND_URL` / `CONTACT_URL` | `https://auriomhq.work` / `…/contact` | CTA targets in UI and PDF |
| `CONTACT_EMAIL` | *(empty)* | Optional; printed in the PDF when set |
| `LEAD_WEBHOOK_URL` / `LEAD_WEBHOOK_TOKEN` | *(empty)* | Optional lead delivery webhook |

---

## 8. API reference

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/config` | Brand, feature flags, limits, aggregate stats, pillar weights |
| `GET` | `/api/methodology` | Pillar weights, formula, bands and the full check catalogue |
| `GET` | `/api/health` | Health probe |
| `POST` | `/api/audits` | Start an audit `{ "url": "example.com" }` → `202 {id}` (400 on unsafe URL, 429 on rate limit) |
| `GET` | `/api/audits/{id}` | Status, progress events, and the full report payload when complete |
| `GET` | `/api/audits/{id}/pdf` | Branded PDF report |
| `POST` | `/api/audits/{id}/share` | `{ "visibility": "public" \| "private" }` → share token + absolute URL |
| `DELETE` | `/api/audits/{id}/share` | Revoke sharing |
| `GET` | `/api/reports/{token}` | Public report (404 when private or unknown) |
| `GET` | `/api/reports/{token}/pdf` | Public PDF |
| `POST` | `/api/leads` | Lead submission (validated, honeypot-protected, rate limited) |

Interactive docs: `/docs` (Swagger UI) while the server is running.

---

## 9. Security model

- **SSRF / DNS rebinding** — only `http`/`https`, only ports 80/443, no credentials in URLs, no control characters. DNS is resolved before connecting; **every** resolved IP must be public (IPv4 and IPv6, including `169.254.169.254`, `::1`, `fc00::/7`). The crawler then connects to the validated IP while sending the original `Host` header and TLS SNI, so a second DNS answer cannot redirect the request inward. Every redirect hop is validated again. Proxy environment variables are ignored (`trust_env=False`).
- **Resource limits** — connect/read/total timeouts, 3 MB streamed response cap, 5-hop redirect cap, page cap, per-host delay, bounded concurrency.
- **No dangerous execution** — no JavaScript, no authenticated areas, no cookies retained, no form submissions.
- **Rate limiting** — per-IP token buckets for audits and leads (hashed IPs, salted).
- **Secrets** — server-side environment only; the React bundle contains no keys and the report payload is scanned by a test for accidental key leakage.
- **Sharing privacy** — tokens are unguessable, revocable, and return `404` when private; reports contain no personal data.
- **Headers** — `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`; API responses are `no-store`.

---

## 10. Deployment

### Docker (any VPS / cloud)

```bash
cp .env.example .env        # set IP_HASH_SALT, PUBLIC_BASE_URL, optional AI + webhook
docker compose up -d --build
```

The image builds the frontend in a Node stage, then serves API + static assets from a single Python
container on port 8000. The SQLite database lives on the `analyzer-data` volume.

### Render / Railway / Fly.io

- Build command: `cd frontend && npm ci && npm run build && cd .. && pip install -r requirements.txt`
- Start command: `cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Attach a persistent disk for `DATABASE_PATH` (e.g. `/var/data/auriomhq.db`).
- Set `PUBLIC_BASE_URL` to the public origin so share links are absolute.
- Set `TRUST_PROXY=1` behind the platform proxy.

### Vercel

A Vercel target is included (`vercel.json` + `api/index.py`): the SPA is served from the CDN and
all API routes hit one Python function. Set `SERVERLESS=1` there (the entry point does it for you)
so audits run inside the request instead of a background task, and expect a **reduced** mode —
`/tmp` storage per instance, a 60 s function budget, per-instance rate limiting. Full details,
limits and the recommended split (static site on Vercel + container for the API):
**[docs/DEPLOY-VERCEL.md](docs/DEPLOY-VERCEL.md)**.

### Reverse proxy (nginx example)

```nginx
server {
  server_name analyzer.auriomhq.work;
  client_max_body_size 1m;

  location / {
    proxy_pass         http://127.0.0.1:8000;
    proxy_set_header   Host $host;
    proxy_set_header   X-Forwarded-For $remote_addr;
    proxy_set_header   X-Forwarded-Proto $scheme;
    proxy_read_timeout 180s;   # audits can take up to ~2 minutes
  }
}
```

Notes:
- Audits are asynchronous, so a long `proxy_read_timeout` matters more than a long request timeout.
- Serve over HTTPS; the crawler works over HTTPS independently of the host scheme.
- Multi-instance deployments need Redis-backed rate limiting and a shared job queue (see *Not implemented*).

---

## 11. Testing

```bash
cd backend && python -m pytest ../tests -v
```

Current result on this machine: **63 passed** (≈41 s). Details and the scenario matrix are in
[`docs/TESTING.md`](docs/TESTING.md).

Coverage highlights:
- Security: 20+ blocked-URL cases, DNS-rebinding refusal, IPv6/metadata addresses, rate limiter, port/scheme/credential rules.
- Scoring: partial credit, untested exclusion, weight renormalisation, category totals, evaluator-exception safety.
- Crawler: robots enforcement, full-site block, broken links, redirect chains and loops, timeouts, non-HTML, 500 homepage, parsing accuracy.
- API: full lifecycle, PDF bytes, share + revoke, lead validation & honeypot, rate limiting, no secret leakage.

---

## 12. Known limitations

1. **HTML only** — no JavaScript execution. Sites that render content client-side will score low on GEO/AEO; the report says so explicitly (`geo.html_content`).
2. **Page cap** — default 10 pages. Site-wide findings (duplicate titles, noindex patterns) are representative, not exhaustive.
3. **Single-threaded politeness** — the crawler is deliberately gentle (0.35 s per-host delay), so large sites take longer per page.
4. **No ranking/backlink/AI-citation data** — by design; the product never estimates these.
5. **SQLite + in-process jobs** — perfect for a prototype and single-instance deployments; not for multi-instance scale.
6. **AI layer is advisory** — when enabled, the model receives only the crawler's evidence pack and is instructed not to invent findings; the deterministic rule-based engine remains the source of truth for scores and recommendations.
7. **Sites behind aggressive bot protection** (Cloudflare challenges, WAF blocks) may return non-HTML or 403; the audit fails with a clear message rather than guessing.
8. **Score interpretation** — scores describe on-page readiness for machine reading. They do not predict rankings, traffic or AI citations.

---

## 13. Design notes

The interface follows the AuriomHQ design language observed on `auriomhq.work`: warm off-white
(`#FAF9F5`), near-black ink (`#14130F`), Inter for text with Fragment Mono for labels, hairline
`#E5E2D9` borders, 0.875–1.125 rem radii and restrained motion. Status colour is reserved for
meaning (pass `#15803D`, warning `#B45309`, fail `#B91C1C`) plus a single warm accent (`#C2410C`).

Avoided deliberately: decorative gradients, glassmorphism, glow effects, generic AI illustrations,
oversized hero graphics and — most importantly — placeholder metrics presented as results.

---

## 14. License / ownership

Prototype built for AuriomHQ. Brand assets, copy and product naming belong to AuriomHQ; the
application is self-contained and does not modify the main website.
