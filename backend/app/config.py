"""Application configuration.

All secrets are read from environment variables (never hard-coded, never
shipped to the browser). See .env.example for the full list.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


@dataclass
class Settings:
    # --- runtime ---------------------------------------------------------
    env: str = os.getenv("APP_ENV", "development")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = _env_int("PORT", 8000)
    # Serverless hosts (Vercel, Lambda) only allow writes to /tmp and cannot keep
    # background tasks alive after the response, so audits run inline instead.
    serverless: bool = _env_bool("SERVERLESS", False)
    database_path: str = os.getenv(
        "DATABASE_PATH",
        "/tmp/auriomhq.db" if _env_bool("SERVERLESS", False) else str(BASE_DIR / "data" / "auriomhq.db"),
    )
    static_dir: str = os.getenv("STATIC_DIR", str(BASE_DIR / "backend" / "static"))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()
        )
    )
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "")

    # --- crawler ---------------------------------------------------------
    user_agent: str = os.getenv(
        "CRAWLER_USER_AGENT",
        "AuriomHQ-AI-Visibility-Analyzer/1.0 (+https://auriomhq.work; audit bot)",
    )
    max_pages: int = _env_int("CRAWL_MAX_PAGES", 10)
    max_pages_hard_limit: int = _env_int("CRAWL_MAX_PAGES_HARD_LIMIT", 25)
    connect_timeout: float = _env_float("CRAWL_CONNECT_TIMEOUT", 8.0)
    read_timeout: float = _env_float("CRAWL_READ_TIMEOUT", 15.0)
    total_timeout: float = _env_float("CRAWL_TOTAL_TIMEOUT", 120.0)
    max_response_bytes: int = _env_int("CRAWL_MAX_RESPONSE_BYTES", 3_000_000)
    max_redirects: int = _env_int("CRAWL_MAX_REDIRECTS", 5)
    link_check_limit: int = _env_int("CRAWL_LINK_CHECK_LIMIT", 25)
    per_host_delay: float = _env_float("CRAWL_PER_HOST_DELAY", 0.35)
    allow_private_targets: bool = _env_bool("CRAWL_ALLOW_PRIVATE_TARGETS", False)

    # --- rate limiting ---------------------------------------------------
    rate_limit_window_seconds: int = _env_int("RATE_LIMIT_WINDOW_SECONDS", 600)
    rate_limit_audits: int = _env_int("RATE_LIMIT_AUDITS_PER_WINDOW", 10)
    max_concurrent_audits: int = _env_int("MAX_CONCURRENT_AUDITS", 3)

    # --- AI (optional) ---------------------------------------------------
    ai_enabled: bool = _env_bool("AI_ENABLED", False)
    ai_provider: str = os.getenv("AI_PROVIDER", "openai")
    ai_base_url: str = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
    ai_model: str = os.getenv("AI_MODEL", "gpt-4o-mini")
    ai_api_key: str = os.getenv("AI_API_KEY", "")
    ai_timeout: float = _env_float("AI_TIMEOUT_SECONDS", 45.0)

    # --- brand / lead gen ------------------------------------------------
    brand_name: str = os.getenv("BRAND_NAME", "AuriomHQ")
    product_name: str = os.getenv("PRODUCT_NAME", "AI Visibility Analyzer")
    brand_url: str = os.getenv("BRAND_URL", "https://auriomhq.work")
    contact_url: str = os.getenv("CONTACT_URL", "https://auriomhq.work/contact")
    contact_email: str = os.getenv("CONTACT_EMAIL", "")
    lead_webhook_url: str = os.getenv("LEAD_WEBHOOK_URL", "")
    lead_webhook_token: str = os.getenv("LEAD_WEBHOOK_TOKEN", "")

    @property
    def ai_ready(self) -> bool:
        return bool(self.ai_enabled and self.ai_api_key and self.ai_base_url and self.ai_model)


settings = Settings()
