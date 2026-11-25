"""Public, share-token based report access."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Response

from .. import db
from ..pdf import render_report
from ..report import public_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


async def _load_public(token: str) -> tuple[dict, dict]:
    row = await db.get_by_share_token(token)
    if row is None:
        raise HTTPException(status_code=404, detail="This report link is not valid.")
    if row.get("share_visibility") != "public":
        raise HTTPException(status_code=404, detail="This report link is not valid.")
    if not row.get("result_json"):
        raise HTTPException(status_code=404, detail="This report is not ready yet.")
    return json.loads(row["result_json"]), row


@router.get("/{token}")
async def get_shared_report(token: str) -> dict:
    report, row = await _load_public(token)
    payload = public_report(report, row)
    payload["shared"] = True
    return payload


@router.get("/{token}/pdf")
async def shared_report_pdf(token: str) -> Response:
    report, _row = await _load_public(token)
    pdf_bytes = render_report(report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="auriomhq-ai-visibility-report.pdf"'},
    )
