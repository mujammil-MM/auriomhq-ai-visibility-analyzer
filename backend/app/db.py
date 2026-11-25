"""SQLite persistence (prototype-friendly; swap for Postgres/Supabase in prod).

Stores only audit metadata, findings and lead submissions — no visitor
personal data beyond what a lead explicitly submits. Client IPs are stored as
salted hashes for rate limiting only.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS audits (
    id                TEXT PRIMARY KEY,
    requested_url     TEXT NOT NULL,
    final_url         TEXT,
    status            TEXT NOT NULL DEFAULT 'queued',
    stage             TEXT,
    stage_message     TEXT,
    progress          INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL,
    completed_at      TEXT,
    duration_ms       INTEGER,
    overall_score     INTEGER,
    seo_score         INTEGER,
    aeo_score         INTEGER,
    geo_score         INTEGER,
    pages_analysed    INTEGER,
    counts_json       TEXT,
    error             TEXT,
    result_json       TEXT,
    summary_json      TEXT,
    ai_enhanced       INTEGER NOT NULL DEFAULT 0,
    share_token       TEXT UNIQUE,
    share_visibility  TEXT NOT NULL DEFAULT 'private',
    shared_at         TEXT,
    client_hash       TEXT
);
CREATE INDEX IF NOT EXISTS idx_audits_created ON audits(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audits_share ON audits(share_token);

CREATE TABLE IF NOT EXISTS leads (
    id            TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    name          TEXT NOT NULL,
    business      TEXT,
    email         TEXT NOT NULL,
    website       TEXT,
    interest      TEXT,
    message       TEXT,
    audit_id      TEXT,
    source        TEXT,
    client_hash   TEXT,
    delivery      TEXT
);
CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at DESC);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    audit_id    TEXT,
    name        TEXT NOT NULL,
    payload     TEXT
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_initialised: set[str] = set()


def _connect() -> sqlite3.Connection:
    path = settings.database_path
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # Serverless cold starts and freshly mounted volumes may not have run the
    # startup hook, so make sure the schema exists before the first statement.
    if path not in _initialised:
        conn.executescript(SCHEMA)
        conn.commit()
        _initialised.add(path)
    return conn


def _init() -> None:
    with _connect() as conn:
        conn.executescript(SCHEMA)


async def init_db() -> None:
    await asyncio.to_thread(_init)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


# ---------------------------------------------------------------------------
# audits
# ---------------------------------------------------------------------------
def _create_audit(audit_id: str, url: str, client_hash: str) -> dict[str, Any]:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO audits (id, requested_url, status, stage, stage_message, progress, created_at, client_hash) "
            "VALUES (?, ?, 'queued', 'queued', 'Audit queued', 0, ?, ?)",
            (audit_id, url, now_iso(), client_hash),
        )
    return {"id": audit_id, "url": url, "status": "queued"}


async def create_audit(url: str, client_hash: str = "") -> dict[str, Any]:
    return await asyncio.to_thread(_create_audit, uuid.uuid4().hex[:16], url, client_hash)


def _update_progress(audit_id: str, status: str, stage: str, message: str, progress: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE audits SET status=?, stage=?, stage_message=?, progress=? WHERE id=?",
            (status, stage, message, max(0, min(100, progress)), audit_id),
        )


async def update_progress(audit_id: str, status: str, stage: str, message: str, progress: int) -> None:
    await asyncio.to_thread(_update_progress, audit_id, status, stage, message, progress)


def _mark_failed(audit_id: str, error: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE audits SET status='failed', error=?, progress=100, completed_at=? WHERE id=?",
            (error, now_iso(), audit_id),
        )


async def mark_failed(audit_id: str, error: str) -> None:
    await asyncio.to_thread(_mark_failed, audit_id, error)


def _save_result(audit_id: str, report: dict[str, Any], ai_enhanced: bool) -> None:
    scores = report.get("scores", {})
    pillars = scores.get("pillars", {})
    counts = scores.get("counts", {})
    with _connect() as conn:
        conn.execute(
            """UPDATE audits SET status='completed', stage='done', stage_message='Audit complete',
                   progress=100, completed_at=?, duration_ms=?, overall_score=?, seo_score=?, aeo_score=?,
                   geo_score=?, pages_analysed=?, counts_json=?, result_json=?, summary_json=?, ai_enhanced=?,
                   final_url=?
               WHERE id=?""",
            (
                now_iso(),
                report.get("site", {}).get("durationMs"),
                scores.get("overall"),
                pillars.get("seo", {}).get("score"),
                pillars.get("aeo", {}).get("score"),
                pillars.get("geo", {}).get("score"),
                report.get("site", {}).get("pagesAnalysed"),
                json.dumps(counts),
                json.dumps(report),
                json.dumps(report.get("summary", {})),
                1 if ai_enhanced else 0,
                report.get("site", {}).get("url"),
                audit_id,
            ),
        )


async def save_result(audit_id: str, report: dict[str, Any], ai_enhanced: bool = False) -> None:
    await asyncio.to_thread(_save_result, audit_id, report, ai_enhanced)


def _get_audit(audit_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM audits WHERE id=?", (audit_id,)).fetchone()
    return _row_to_dict(row)


async def get_audit(audit_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_audit, audit_id)


def _get_by_share(token: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM audits WHERE share_token=?", (token,)).fetchone()
    return _row_to_dict(row)


async def get_by_share_token(token: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_by_share, token)


def _share_audit(audit_id: str, visibility: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT share_token FROM audits WHERE id=?", (audit_id,)).fetchone()
        if row is None:
            return None
        token = row["share_token"] or secrets.token_urlsafe(12)
        conn.execute(
            "UPDATE audits SET share_token=?, share_visibility=?, shared_at=? WHERE id=?",
            (token, visibility, now_iso(), audit_id),
        )
    return {"share_token": token, "visibility": visibility}


async def share_audit(audit_id: str, visibility: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_share_audit, audit_id, visibility)


def _unshare_audit(audit_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE audits SET share_visibility='private' WHERE id=?", (audit_id,)
        )
    return cur.rowcount > 0


async def unshare_audit(audit_id: str) -> bool:
    return await asyncio.to_thread(_unshare_audit, audit_id)


# ---------------------------------------------------------------------------
# leads
# ---------------------------------------------------------------------------
def _create_lead(data: dict[str, Any]) -> str:
    lead_id = uuid.uuid4().hex[:16]
    with _connect() as conn:
        conn.execute(
            """INSERT INTO leads (id, created_at, name, business, email, website, interest, message,
                                  audit_id, source, client_hash, delivery)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                lead_id, now_iso(), data["name"], data.get("business", ""), data["email"],
                data.get("website", ""), data.get("interest", ""), data.get("message", ""),
                data.get("audit_id", ""), data.get("source", "analyzer"), data.get("client_hash", ""),
                data.get("delivery", "stored"),
            ),
        )
    return lead_id


async def create_lead(data: dict[str, Any]) -> str:
    return await asyncio.to_thread(_create_lead, data)


def _recent_audit_count(client_hash: str, minutes: int = 60) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM audits WHERE client_hash=? AND created_at > datetime('now', ?)",
            (client_hash, f"-{minutes} minutes"),
        ).fetchone()
    return int(row["c"])


async def recent_audit_count(client_hash: str, minutes: int = 60) -> int:
    return await asyncio.to_thread(_recent_audit_count, client_hash, minutes)


def _stats() -> dict[str, Any]:
    with _connect() as conn:
        audits = conn.execute("SELECT COUNT(*) AS c FROM audits WHERE status='completed'").fetchone()["c"]
        leads = conn.execute("SELECT COUNT(*) AS c FROM leads").fetchone()["c"]
        latest = conn.execute("SELECT MAX(completed_at) AS t FROM audits").fetchone()["t"]
    return {"completedAudits": audits, "leads": leads, "lastAuditAt": latest}


async def stats() -> dict[str, Any]:
    return await asyncio.to_thread(_stats)


def _log_event(name: str, audit_id: str = "", payload: dict[str, Any] | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO events (created_at, audit_id, name, payload) VALUES (?,?,?,?)",
            (now_iso(), audit_id, name, json.dumps(payload or {})),
        )


async def log_event(name: str, audit_id: str = "", payload: dict[str, Any] | None = None) -> None:
    await asyncio.to_thread(_log_event, name, audit_id, payload)
