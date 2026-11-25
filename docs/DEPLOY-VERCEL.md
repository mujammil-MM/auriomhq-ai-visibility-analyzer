# Deploying on Vercel

The wallet-sized version: **Vercel can host this app, but it is not the ideal host for it.**
Vercel functions have a read-only filesystem (only `/tmp` is writable), no shared state
between instances, and a hard request timeout. This project was designed around a
long-lived process with a real database, so the Vercel target runs in a reduced, documented
mode. Everything below is honest about what works and what does not.

Live deployment: https://auriomhq-ai-visibility-analyzer.vercel.app

---

## What is deployed

| Part | Where it runs |
|---|---|
| React SPA | Static output from `frontend/dist`, served by Vercel's CDN |
| FastAPI app | A single Python function at `api/index.py` (all `/api/*` routes) |
| PDF generation | Same function (ReportLab + bundled Inter/FontFragment TTFs) |
| Crawl + 53 checks | Same function, executed **inside the POST request** |

`vercel.json` wires this together:

```json
{
  "buildCommand": "npm --prefix frontend ci && npm --prefix frontend run build",
  "outputDirectory": "frontend/dist",
  "functions": { "api/index.py": { "maxDuration": 60, "memory": 1024,
                                   "includeFiles": "backend/app/**" } },
  "rewrites": [
    { "source": "/api/:path*", "destination": "/api/index" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

## Code changes that made it possible

Setting `SERVERLESS=1` (done inside `api/index.py`, so no dashboard secrets are needed)
changes three behaviours:

1. **Synchronous audits.** `POST /api/audits` runs the whole crawl and returns the finished
   report with `200` instead of queuing a background task. Vercel freezes the process as
   soon as a response is written, so a background task would silently die.
2. **`/tmp` database.** `DATABASE_PATH` defaults to `/tmp/auriomhq.db`. The schema is also
   created lazily on first connection, so a cold start never hits a missing table.
3. **Frontend hand-off.** The SPA renders the audit straight from the POST response
   (cached in `sessionStorage`), so the dashboard does not depend on the follow-up request
   reaching the same function instance.

Local and Docker runs are unchanged: without `SERVERLESS=1` the API stays asynchronous with
progress events.

## Limits you will hit on Vercel

| Limit | Effect |
|---|---|
| 60 s function timeout (Hobby) | A 10-page crawl of a slow site can be cut off. Set `CRAWL_MAX_PAGES=6` and `CRAWL_TOTAL_TIMEOUT=40` for safety. |
| `/tmp` is per-instance and ephemeral | An audit created on one instance is not visible to another. Reopening an old `/audit/<id>` after a cold start returns "Audit not found"; PDF and share links behave the same way. |
| No shared rate-limit state | `RATE_LIMIT_AUDITS_PER_WINDOW` applies per instance, so the effective limit is higher than configured. |
| Cold starts | The first request after idle pays ~1–2 s for Python + ReportLab import. |

**Everything the browser needs for a fresh audit works**: submit → crawl → scored dashboard →
PDF → share → lead form. What degrades is *persistence across instances and time*.

## Recommended production topology

If this is going in front of real customers, split it:

- **Vercel**: the static SPA (`frontend/dist`), with `/api/*` rewritten to the API host.
- **Railway / Render / Fly / any container host**: `backend/Dockerfile` — one always-on
  process, persistent disk for SQLite, real rate limiting, long crawls.
- Set `PUBLIC_BASE_URL` on the API to the public SPA origin so share links point at the right
  host, and `CORS_ORIGINS` to the Vercel domain if the SPA calls the API cross-origin.

That is the architecture in `docs/ARCHITECTURE.md`; the Vercel-only target exists because a
single-URL deployment is useful for demos and review.

## Two Vercel behaviours worth knowing

1. **Deployment protection.** Per-deployment URLs (`<deployment>-<hash>.vercel.app`) sit behind
   Vercel Authentication and return `302` to anonymous visitors. The project's production domain
   (`auriomhq-ai-visibility-analyzer.vercel.app`) is public. To share a preview build, disable
   *Settings → Deployment Protection*, or use the production domain.
2. **Git deploys are opt-in on API-created projects.** This project was created through the API, so
   `gitProviderOptions.createDeployments` is `disabled` and a `git push` does **not** start a build.
   Turn it on under *Settings → Git → Production deployments*, or deploy explicitly with
   `vercel --prod`. The commit that produced the current live deployment is named in the reply that
   shipped it.

## Deploying it yourself

```bash
npm i -g vercel
cd auriomhq-analyzer
vercel                  # first run links/creates the project
vercel --prod           # production deployment
```

Or connect the GitHub repo in the Vercel dashboard — no build settings are needed, because
`vercel.json` supplies them. Optional environment variables:

| Variable | Why |
|---|---|
| `CRAWL_MAX_PAGES` | Lower it to stay inside the 60 s function budget |
| `AI_ENABLED`, `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL` | Enable the optional AI summary layer |
| `LEAD_WEBHOOK_URL` | Forward leads somewhere durable (otherwise leads live in ephemeral `/tmp`) |
| `TRUST_PROXY=1` | Rate limiting by `X-Forwarded-For` behind Vercel's proxy |
| `PUBLIC_BASE_URL` | Absolute share links |

**Leads deserve a warning:** on Vercel they are written to `/tmp` and will vanish. Set
`LEAD_WEBHOOK_URL` (and `LEAD_WEBHOOK_TOKEN`) so submissions are delivered somewhere
permanent, or run the container image.
