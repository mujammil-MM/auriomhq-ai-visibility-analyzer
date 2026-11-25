"""Vercel serverless entry point.

Vercel's Python runtime imports this module and serves the exported ASGI app.
Three platform details shape what happens here:

* The filesystem is read-only apart from `/tmp`, so the SQLite database lives in
  `/tmp` and is scoped to a single function instance.
* The runtime freezes the process as soon as a response is sent, so audits run
  inline (see `settings.serverless`) instead of in a background task.
* A function file at `api/index.py` is invoked at `/api/index`; the real path
  arrives either as an `x-vercel-original-path`-style header or as the captured
  `path` query parameter produced by the rewrite in `vercel.json`. The middleware
  below restores it so FastAPI routes match normally.

For durable storage and long crawls, run the container image instead — see
docs/DEPLOY-VERCEL.md.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

# Must be set before app.config is imported: Settings reads the environment once.
os.environ.setdefault("SERVERLESS", "1")
os.environ.setdefault("DATABASE_PATH", "/tmp/auriomhq.db")
os.environ.setdefault("APP_ENV", "production")
os.environ.setdefault("STATIC_DIR", str(ROOT / "backend" / "static"))

from app.main import app  # noqa: E402  (import after env setup)

FUNCTION_PATH = "/api/index"
ORIGINAL_PATH_HEADERS = (b"x-vercel-original-path", b"x-forwarded-uri", b"x-original-uri")


class RestoreOriginalPath:
    """Make FastAPI see `/api/health` instead of `/api/index?path=health`."""

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("path", "").startswith(FUNCTION_PATH):
            headers = dict(scope.get("headers") or [])
            original = b""
            for name in ORIGINAL_PATH_HEADERS:
                if name in headers:
                    original = headers[name]
                    break

            if original:
                path = original.decode("latin-1").split("?", 1)[0] or "/"
                scope["path"] = path
                scope["raw_path"] = path.encode()
            else:
                params = dict(parse_qsl(scope.get("query_string", b"").decode("latin-1"),
                                        keep_blank_values=True))
                rest = params.pop("path", "")
                scope["path"] = f"/api/{rest}" if rest else "/api"
                scope["raw_path"] = scope["path"].encode()
                scope["query_string"] = urlencode(params).encode() if params else b""

        await self.asgi_app(scope, receive, send)


app = RestoreOriginalPath(app)

__all__ = ["app"]
