"""AuriomHQ AI Visibility Analyzer — FastAPI application."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .analyzers import ALL_CHECKS
from .analyzers.scoring import PILLAR_WEIGHTS
from .config import settings
from .routers import audits, leads, reports

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("auriomhq")

STATIC_DIR = Path(settings.static_dir)
CHECK_CATALOGUE = [
    {
        "id": spec.id,
        "pillar": spec.pillar,
        "category": spec.category,
        "title": spec.title,
        "description": spec.description,
        "why": spec.why,
        "severity": spec.severity,
        "weight": spec.weight,
        "priority": spec.priority,
    }
    for pillar_checks in ALL_CHECKS.values()
    for spec in pillar_checks
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    logger.info("database ready at %s", settings.database_path)
    logger.info("AI recommendations: %s", "enabled" if settings.ai_ready else "disabled (rule-based engine)")
    yield


app = FastAPI(
    title="AuriomHQ AI Visibility Analyzer API",
    version="1.0.0",
    description="SEO, AEO and GEO auditing for real websites.",
    lifespan=lifespan,
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


app.include_router(audits.router)
app.include_router(reports.router)
app.include_router(leads.router)


@app.get("/api/health", tags=["meta"])
async def health() -> dict:
    return {
        "status": "ok",
        "aiEnabled": settings.ai_ready,
        "maxPages": settings.max_pages,
        "environment": settings.env,
    }


@app.get("/api/config", tags=["meta"])
async def public_config() -> dict:
    stats = await db.stats()
    return {
        "brand": settings.brand_name,
        "product": settings.product_name,
        "tagline": "Make your website visible everywhere people search.",
        "brandUrl": settings.brand_url,
        "contactUrl": settings.contact_url,
        "contactEmail": settings.contact_email,
        "maxPages": settings.max_pages,
        "aiEnabled": settings.ai_ready,
        "rateLimit": {
            "auditsPerWindow": settings.rate_limit_audits,
            "windowSeconds": settings.rate_limit_window_seconds,
        },
        "features": {
            "pdf": True,
            "sharing": True,
            "accounts": False,
            "aiRecommendations": settings.ai_ready,
            "leadCapture": True,
        },
        "stats": stats,
        "pillarWeights": PILLAR_WEIGHTS,
    }


@app.get("/api/methodology", tags=["meta"])
async def methodology() -> dict:
    return {
        "pillars": {
            "seo": {"label": "Search Engine Optimisation", "weight": PILLAR_WEIGHTS["seo"],
                    "description": "Technical and content signals that determine whether a page can be crawled, "
                                   "indexed and matched to a query."},
            "aeo": {"label": "Answer Engine Optimisation", "weight": PILLAR_WEIGHTS["aeo"],
                    "description": "How directly and clearly the content answers real questions, and whether that "
                                   "structure is machine readable."},
            "geo": {"label": "Generative Engine Optimisation", "weight": PILLAR_WEIGHTS["geo"],
                    "description": "Entity clarity, crawler access, attribution and content credibility signals that "
                                   "generative engines rely on."},
        },
        "scoring": {
            "formula": "pillar = round(100 × Σ(earned) ÷ Σ(weight of tested checks))",
            "overall": "Σ(pillar score × pillar weight) ÷ Σ(pillar weight of scored pillars)",
            "credits": {
                "pass": "Earns 100% of the check weight.",
                "warning": "Earns 50–70% of the check weight (varies per check).",
                "fail": "Earns 0 points.",
                "not_tested": "Excluded from earned and available points — never counted as a pass.",
            },
            "bands": [
                {"min": 85, "label": "Strong"}, {"min": 70, "label": "Good"},
                {"min": 55, "label": "Needs work"}, {"min": 35, "label": "Weak"}, {"min": 0, "label": "Critical"},
            ],
        },
        "checks": CHECK_CATALOGUE,
        "limitations": [
            "Only HTML returned by the server is analysed (no JavaScript execution).",
            "No ranking, traffic, backlink or AI-citation data is measured or estimated.",
            "GEO readiness is an estimate from measurable on-site signals, not observed AI answers.",
            "Structured data does not guarantee rich results or citations.",
        ],
    }


@app.get("/api/stats", tags=["meta"])
async def public_stats() -> dict:
    return await db.stats()


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt() -> PlainTextResponse:
    return PlainTextResponse("User-agent: *\nAllow: /\nDisallow: /api/\n")


@app.get("/api/{path:path}", include_in_schema=False)
async def api_not_found(path: str) -> JSONResponse:
    return JSONResponse({"detail": "Endpoint not found."}, status_code=404)


# ---------------------------------------------------------------------------
# Static frontend (single-page app)
# ---------------------------------------------------------------------------
if STATIC_DIR.exists():
    if (STATIC_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file() and ".." not in full_path:
            return FileResponse(candidate)
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(index, headers={"Cache-Control": "no-cache"})
        return PlainTextResponse("Frontend build not found. Run `npm run build` in /frontend.", status_code=503)

else:  # pragma: no cover
    @app.get("/", include_in_schema=False)
    async def no_frontend() -> PlainTextResponse:
        return PlainTextResponse(
            "API is running. Build the frontend (`cd frontend && npm install && npm run build`) "
            "to serve the dashboard from this server.", status_code=200,
        )


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port,
                reload=os.getenv("APP_ENV", "development") == "development")
