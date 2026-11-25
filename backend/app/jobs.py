"""Audit job orchestration: crawl → analyse → summarise → persist.

Long-running audits run as asyncio tasks with an in-process progress registry
that the frontend polls. Progress is mirrored to SQLite so a completed audit is
never lost and can be reopened later.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from . import db
from .ai import enhance_with_ai, rule_based_summary
from .analyzers import analyse
from .config import settings
from .crawler import Crawler
from .report import build_report
from .security import UnsafeURLError, guard_fetch_url

logger = logging.getLogger("auriomhq.jobs")

MAX_EVENTS = 60
_registry: dict[str, dict[str, Any]] = {}
_semaphore = asyncio.Semaphore(settings.max_concurrent_audits)
_tasks: set[asyncio.Task] = set()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_progress(audit_id: str) -> dict[str, Any] | None:
    return _registry.get(audit_id)


def _record(audit_id: str, stage: str, message: str, percent: int, detail: str | None = None) -> None:
    state = _registry.setdefault(audit_id, {"events": [], "percent": 0, "stage": "queued",
                                           "message": "Audit queued", "startedAt": _now()})
    state.update({"stage": stage, "message": message, "percent": percent, "detail": detail})
    events = state["events"]
    if not events or events[-1]["message"] != message or events[-1]["stage"] != stage:
        events.append({"stage": stage, "message": message, "percent": percent, "at": _now(),
                       "detail": detail})
        if len(events) > MAX_EVENTS:
            del events[:-MAX_EVENTS]


async def start_audit(audit_id: str, url: str) -> None:
    """Kick off the background audit task."""
    task = asyncio.create_task(_run(audit_id, url))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def run_audit_inline(audit_id: str, url: str) -> None:
    """Run the whole audit inside the current request.

    Serverless platforms freeze the process as soon as the response is returned,
    so a background task would never finish there.
    """
    await _run(audit_id, url)


async def _run(audit_id: str, url: str) -> None:
    _record(audit_id, "queued", "Audit queued", 2)
    await db.update_progress(audit_id, "queued", "queued", "Audit queued", 2)
    started = time.monotonic()
    try:
        async with _semaphore:
            _record(audit_id, "validating", "Validating the URL and DNS records", 4)
            await db.update_progress(audit_id, "running", "validating", "Validating the URL and DNS records", 4)
            try:
                await guard_fetch_url(url)
            except UnsafeURLError as exc:
                await _fail(audit_id, str(exc), "unsafe_url")
                return

            crawler = Crawler()

            async def progress(stage: str, message: str, percent: int, detail: str | None = None) -> None:
                _record(audit_id, stage, message, percent, detail)
                await db.update_progress(audit_id, "running", stage, message, percent)

            await db.update_progress(audit_id, "running", "crawl", "Starting crawl", 5)
            try:
                crawl_result = await asyncio.wait_for(
                    crawler.crawl(url, progress=progress), timeout=settings.total_timeout + 30
                )
            except asyncio.TimeoutError:
                await _fail(audit_id, "The audit timed out before the website finished responding. "
                                      "The site may be slow or blocking automated requests.", "timeout")
                return

            if not crawl_result.pages:
                detail = crawl_result.errors[0] if crawl_result.errors else "The site returned no analysable HTML."
                await _fail(
                    audit_id,
                    f"We could not analyse {url}. {detail} "
                    "Check that the site is publicly reachable and returns HTML (not a login page or an error page).",
                    "unreachable",
                )
                return

            _record(audit_id, "analyse", "Scoring 60+ SEO, AEO and GEO checks", 90)
            await db.update_progress(audit_id, "running", "analyse", "Scoring 60+ SEO, AEO and GEO checks", 90)

            analysis = analyse(crawl_result)
            score_summary = analysis["_score_summary"]
            check_results = analysis["_check_results"]
            evidence = analysis["evidence"]

            _record(audit_id, "summary", "Writing the executive summary", 94)
            summary = rule_based_summary(crawl_result, check_results, score_summary)
            if settings.ai_ready:
                _record(audit_id, "summary", "Generating AI-assisted recommendations", 96)
                enhanced = await enhance_with_ai(crawl_result, check_results, score_summary, evidence)
                if enhanced:
                    # Keep rule-based findings that the model did not restate
                    summary = {**summary, **enhanced}

            report = build_report(crawl_result, summary, analysis)
            await db.save_result(audit_id, report, ai_enhanced=bool(summary.get("aiEnhanced")))
            _record(audit_id, "done", "Audit complete", 100)
            logger.info("audit %s completed in %.1fs", audit_id, time.monotonic() - started)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("audit %s failed", audit_id)
        await _fail(audit_id, f"The audit failed unexpectedly ({type(exc).__name__}). Please try again.", "internal_error")


async def _fail(audit_id: str, message: str, code: str) -> None:
    await db.mark_failed(audit_id, message)
    _record(audit_id, "failed", message, 100)
    _registry.setdefault(audit_id, {})["errorCode"] = code
    await db.log_event("audit_failed", audit_id, {"code": code, "message": message})


def serialize_status(row: dict[str, Any]) -> dict[str, Any]:
    """Build the polling payload from the DB row + live progress registry."""
    audit_id = row["id"]
    live = _registry.get(audit_id, {})
    report = None
    if row.get("result_json"):
        try:
            report = json.loads(row["result_json"])
        except json.JSONDecodeError:
            report = None
    share = None
    if row.get("share_token"):
        share = {
            "token": row["share_token"],
            "visibility": row.get("share_visibility", "private"),
            "sharedAt": row.get("shared_at"),
        }
    payload = {
        "id": audit_id,
        "status": row.get("status", "queued"),
        "progress": row.get("progress", 0),
        "stage": row.get("stage"),
        "message": row.get("stage_message"),
        "events": live.get("events", []),
        "error": row.get("error"),
        "createdAt": row.get("created_at"),
        "completedAt": row.get("completed_at"),
        "share": share,
        "report": report,
        "url": row.get("final_url") or row.get("requested_url"),
    }
    if live.get("errorCode"):
        payload["errorCode"] = live["errorCode"]
    return payload
