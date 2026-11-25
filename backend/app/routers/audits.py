"""Audit lifecycle endpoints."""
from __future__ import annotations

import hashlib
import json
import os
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from .. import db, jobs
from ..config import settings
from ..models import AuditCreatedResponse, AuditRequest, ShareRequest
from ..pdf import render_report
from ..report import public_report
from ..security import UnsafeURLError, audit_rate_limiter, validate_url

router = APIRouter(prefix="/api/audits", tags=["audits"])

IP_SALT = os.getenv("IP_HASH_SALT", "auriomhq-analyzer-proto")


def client_ip(request: Request) -> str:
    if os.getenv("TRUST_PROXY", "0") in {"1", "true", "yes"}:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def client_hash(request: Request) -> str:
    return hashlib.sha256(f"{IP_SALT}:{client_ip(request)}".encode()).hexdigest()[:24]


def base_url(request: Request) -> str:
    if settings.public_base_url:
        return settings.public_base_url.rstrip("/")
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}"


@router.post("", response_model=AuditCreatedResponse, status_code=202)
async def create_audit(payload: AuditRequest, request: Request) -> AuditCreatedResponse:
    try:
        target = validate_url(payload.url)
    except UnsafeURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    chash = client_hash(request)
    allowed, retry_after = audit_rate_limiter.check(chash)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many audits from this connection. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    url = target.url
    record = await db.create_audit(url, chash)
    await db.log_event("audit_started", record["id"], {"url": url, "maxPages": payload.max_pages})
    await jobs.start_audit(record["id"], url)
    return AuditCreatedResponse(
        id=record["id"], status="queued", url=url,
        pollUrl=f"/api/audits/{record['id']}",
    )


@router.get("/{audit_id}")
async def get_audit(audit_id: str) -> JSONResponse:
    row = await db.get_audit(audit_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Audit not found.")
    return JSONResponse(jobs.serialize_status(row))


@router.get("/{audit_id}/pdf")
async def audit_pdf(audit_id: str, request: Request) -> Response:
    row = await db.get_audit(audit_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Audit not found.")
    if not row.get("result_json"):
        raise HTTPException(status_code=409, detail="This audit is not finished yet.")
    report = json.loads(row["result_json"])
    pdf_bytes = render_report(report)
    host = (urlsplit(report.get("site", {}).get("url", "site")).hostname or "site").replace(".", "-")
    filename = f"auriomhq-ai-visibility-{host}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, max-age=300",
        },
    )


@router.post("/{audit_id}/share")
async def share_audit(audit_id: str, payload: ShareRequest, request: Request) -> dict:
    row = await db.get_audit(audit_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Audit not found.")
    if not row.get("result_json"):
        raise HTTPException(status_code=409, detail="Only completed audits can be shared.")
    result = await db.share_audit(audit_id, payload.visibility)
    if result is None:
        raise HTTPException(status_code=404, detail="Audit not found.")
    await db.log_event("audit_shared", audit_id, {"visibility": payload.visibility})
    token = result["share_token"]
    return {
        "token": token,
        "visibility": result["visibility"],
        "url": f"{base_url(request)}/r/{token}",
        "path": f"/r/{token}",
    }


@router.delete("/{audit_id}/share")
async def unshare_audit(audit_id: str) -> dict:
    row = await db.get_audit(audit_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Audit not found.")
    await db.unshare_audit(audit_id)
    return {"visibility": "private"}


@router.get("/{audit_id}/public")
async def audit_public_preview(audit_id: str) -> dict:
    """Full report for the owner's own dashboard (not a shared link)."""
    row = await db.get_audit(audit_id)
    if row is None or not row.get("result_json"):
        raise HTTPException(status_code=404, detail="Report not available.")
    return public_report(json.loads(row["result_json"]), row)
