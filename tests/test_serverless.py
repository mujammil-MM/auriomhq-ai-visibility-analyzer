"""Serverless (Vercel) execution mode.

On Vercel the runtime freezes the process once a response is returned, so an
audit cannot continue as a background task. In serverless mode the POST must
return the finished audit. These tests lock in that contract without changing
how the local/docker server behaves.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.security import audit_rate_limiter


@pytest.fixture()
def serverless_client(monkeypatch):
    """A client where settings.serverless is on, as configured on Vercel."""
    monkeypatch.setattr(settings, "serverless", True, raising=False)
    monkeypatch.setattr(settings, "allow_private_targets", True, raising=False)
    audit_rate_limiter._events.clear()
    from app.main import app

    with TestClient(app) as client:
        yield client
    audit_rate_limiter._events.clear()


def test_post_returns_finished_audit(serverless_client: TestClient, good_site):
    response = serverless_client.post("/api/audits", json={"url": good_site.base_url})
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["report"] is not None
    assert payload["report"]["scores"]["overall"] > 0
    assert len(payload["report"]["checks"]) == 53
    assert payload["id"]


def test_result_is_readable_again_on_the_same_instance(serverless_client: TestClient, good_site):
    created = serverless_client.post("/api/audits", json={"url": good_site.base_url}).json()

    again = serverless_client.get(f"/api/audits/{created['id']}")
    assert again.status_code == 200
    assert again.json()["report"]["scores"] == created["report"]["scores"]

    pdf = serverless_client.get(f"/api/audits/{created['id']}/pdf")
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"


def test_failed_audit_still_reports_a_reason(serverless_client: TestClient, site):
    """A dead target must come back as a failed audit with actionable copy."""
    site.set_routes({"/": (404, {"Content-Type": "text/html"}, b"<html><body>gone</body></html>")})
    response = serverless_client.post("/api/audits", json={"url": site.base_url})

    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["report"] is None
    assert "could not analyse" in payload["error"].lower()


def test_local_mode_still_returns_a_job_handle(monkeypatch, good_site):
    """Guards the default path: without SERVERLESS the API stays asynchronous."""
    monkeypatch.setattr(settings, "serverless", False, raising=False)
    monkeypatch.setattr(settings, "allow_private_targets", True, raising=False)
    audit_rate_limiter._events.clear()
    from app.main import app

    with TestClient(app) as client:
        response = client.post("/api/audits", json={"url": good_site.base_url})
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "queued"
        assert body["pollUrl"].endswith(body["id"])
    audit_rate_limiter._events.clear()
