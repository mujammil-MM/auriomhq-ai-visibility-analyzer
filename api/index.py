"""Vercel serverless entry point.

Vercel's Python runtime imports this module and serves the exported ASGI app.
Two platform constraints shape what happens here:

* The filesystem is read-only apart from `/tmp`, so the SQLite database lives in
  `/tmp` and is scoped to a single function instance.
* The runtime freezes the process as soon as a response is sent, so audits are
  executed inline (see `settings.serverless`) instead of in a background task.

For durable storage and long crawls, run the container image instead — see
docs/ARCHITECTURE.md and the deployment section of README.md.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

# Must be set before app.config is imported: Settings reads the environment once.
os.environ.setdefault("SERVERLESS", "1")
os.environ.setdefault("DATABASE_PATH", "/tmp/auriomhq.db")
os.environ.setdefault("APP_ENV", "production")
os.environ.setdefault("STATIC_DIR", str(ROOT / "backend" / "static"))

from app.main import app  # noqa: E402  (import after env setup)

__all__ = ["app"]
