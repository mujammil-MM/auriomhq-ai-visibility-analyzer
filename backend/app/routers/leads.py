"""Lead generation endpoint.

Delivery order: (1) persist to the database — the success criterion, (2) POST to
an optional webhook (Slack/Zapier/CRM) when LEAD_WEBHOOK_URL is configured.
A success response is only returned after the lead has actually been stored.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request

from .. import db
from ..config import settings
from ..models import LeadRequest, LeadResponse
from ..security import lead_rate_limiter
from .audits import client_hash, client_ip

logger = logging.getLogger("auriomhq.leads")
router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.post("", response_model=LeadResponse)
async def create_lead(payload: LeadRequest, request: Request) -> LeadResponse:
    if payload.company_website_confirm.strip():
        # honeypot triggered — silently accept-looking failure for bots
        raise HTTPException(status_code=400, detail="Submission rejected.")

    chash = client_hash(request)
    allowed, retry = lead_rate_limiter.check(chash)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many submissions. Try again in {retry} seconds.")

    delivery: list[str] = []
    webhook_error: str | None = None
    if settings.lead_webhook_url:
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as http:
                headers = {"Content-Type": "application/json"}
                if settings.lead_webhook_token:
                    headers["Authorization"] = f"Bearer {settings.lead_webhook_token}"
                response = await http.post(
                    settings.lead_webhook_url,
                    headers=headers,
                    json={
                        "name": payload.name,
                        "business": payload.business,
                        "email": payload.email,
                        "website": payload.website,
                        "interest": payload.interest,
                        "message": payload.message,
                        "auditId": payload.audit_id,
                        "source": payload.source,
                    },
                )
                if response.status_code < 400:
                    delivery.append("webhook")
                else:
                    webhook_error = f"webhook HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            webhook_error = type(exc).__name__

    lead_id = await db.create_lead({
        "name": payload.name,
        "business": payload.business,
        "email": payload.email,
        "website": payload.website,
        "interest": payload.interest,
        "message": payload.message,
        "audit_id": payload.audit_id,
        "source": payload.source,
        "client_hash": chash,
        "delivery": ",".join(delivery) or "stored",
    })
    await db.log_event("lead_created", payload.audit_id, {
        "leadId": lead_id, "delivery": delivery, "webhookError": webhook_error,
        "interest": payload.interest[:80],
    })
    if webhook_error:
        logger.warning("lead %s stored but webhook delivery failed: %s", lead_id, webhook_error)

    return LeadResponse(
        ok=True,
        id=lead_id,
        message="Thanks — your request has been received. AuriomHQ will reply within one business day.",
        delivered=delivery + ["stored"],
    )
