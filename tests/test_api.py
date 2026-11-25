"""End-to-end API tests: audit lifecycle, PDF, sharing, leads, validation."""
from __future__ import annotations

import json
import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import settings
from app.security import audit_rate_limiter, lead_rate_limiter

# Use an isolated database per test session
_tmpdir = tempfile.mkdtemp()
settings.database_path = os.path.join(_tmpdir, "test.db")  # type: ignore[misc]


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_rate_limits():
    audit_rate_limiter._events.clear()
    lead_rate_limiter._events.clear()
    yield


def wait_for_audit(client: TestClient, audit_id: str, timeout: float = 90) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        response = client.get(f"/api/audits/{audit_id}")
        assert response.status_code == 200
        last = response.json()
        if last["status"] in {"completed", "failed"}:
            return last
        time.sleep(0.4)
    raise AssertionError(f"audit did not finish: {last.get('status')} {last.get('progress')}")


def test_config_and_health(client):
    config = client.get("/api/config").json()
    assert config["brand"] == "AuriomHQ"
    assert config["features"]["pdf"] is True
    assert config["pillarWeights"] == {"seo": 0.4, "aeo": 0.3, "geo": 0.3}
    health = client.get("/api/health").json()
    assert health["status"] == "ok"


def test_methodology_lists_every_check(client):
    data = client.get("/api/methodology").json()
    assert len(data["checks"]) >= 50
    assert {check["pillar"] for check in data["checks"]} == {"seo", "aeo", "geo"}
    assert data["limitations"]


def test_invalid_urls_are_rejected(client):
    for payload in ("http://localhost:8000", "ftp://example.com", "not a url", "http://169.254.169.254/"):
        response = client.post("/api/audits", json={"url": payload})
        assert response.status_code == 400, payload
        assert response.json()["detail"]


def test_full_audit_lifecycle(client, good_site, monkeypatch):
    monkeypatch.setattr(settings, "allow_private_targets", True, raising=False)
    created = client.post("/api/audits", json={"url": good_site.base_url + "/"})
    assert created.status_code == 202
    audit_id = created.json()["id"]

    status = wait_for_audit(client, audit_id)
    assert status["status"] == "completed", status.get("error")
    report = status["report"]
    assert report["scores"]["overall"] is not None
    assert report["crawl"]["pagesAnalysed"] >= 2
    assert len(report["checks"]) >= 50
    assert report["summary"]["executiveSummary"]
    assert report["limitations"]

    # every displayed check has evidence
    for check in report["checks"]:
        assert check["evidence"]

    # PDF
    pdf = client.get(f"/api/audits/{audit_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert len(pdf.content) > 8000

    # sharing
    share = client.post(f"/api/audits/{audit_id}/share", json={"visibility": "public"})
    assert share.status_code == 200
    token = share.json()["token"]
    public = client.get(f"/api/reports/{token}")
    assert public.status_code == 200
    assert public.json()["scores"]["overall"] == report["scores"]["overall"]
    assert client.get(f"/api/reports/{token}/pdf").status_code == 200

    # making it private revokes the link
    assert client.request("DELETE", f"/api/audits/{audit_id}/share").status_code == 200
    assert client.get(f"/api/reports/{token}").status_code == 404


def test_unknown_audit_returns_404(client):
    assert client.get("/api/audits/does-not-exist").status_code == 404
    assert client.get("/api/reports/nope").status_code == 404


def test_unreachable_site_produces_actionable_error(client, monkeypatch):
    monkeypatch.setattr(settings, "allow_private_targets", True, raising=False)
    monkeypatch.setattr(settings, "connect_timeout", 1.0, raising=False)
    # Port 9 (discard) is closed on the fixture host -> connection refused
    created = client.post("/api/audits", json={"url": "http://127.0.0.1:9/"})
    if created.status_code == 400:  # port blocked by policy — also acceptable
        return
    audit_id = created.json()["id"]
    status = wait_for_audit(client, audit_id, timeout=40)
    assert status["status"] == "failed"
    assert status["error"]


def test_lead_validation_and_storage(client):
    bad = client.post("/api/leads", json={"name": "", "email": "nope"})
    assert bad.status_code == 422

    good = client.post("/api/leads", json={
        "name": "Priya Sharma",
        "business": "Sharma Interiors",
        "email": "priya@example.com",
        "website": "https://example.com",
        "interest": "GEO / AI visibility",
        "message": "We want to be more visible in AI answers.",
        "audit_id": "",
        "source": "test",
        "company_website_confirm": "",
    })
    assert good.status_code == 200
    body = good.json()
    assert body["ok"] is True and body["id"]
    assert "stored" in body["delivered"]

    honeypot = client.post("/api/leads", json={
        "name": "Bot", "email": "bot@example.com", "company_website_confirm": "http://spam",
    })
    assert honeypot.status_code == 400


def test_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(settings, "allow_private_targets", True, raising=False)
    audit_rate_limiter._events.clear()
    audit_rate_limiter.limit = 2
    try:
        codes = [client.post("/api/audits", json={"url": "http://127.0.0.1:9/"}).status_code for _ in range(3)]
    finally:
        audit_rate_limiter.limit = settings.rate_limit_audits
    assert codes[-1] == 429


def test_report_payload_contains_no_secrets(client, good_site, monkeypatch):
    monkeypatch.setattr(settings, "allow_private_targets", True, raising=False)
    created = client.post("/api/audits", json={"url": good_site.base_url + "/"}).json()
    status = wait_for_audit(client, created["id"])
    serialized = json.dumps(status)
    assert "api_key" not in serialized.lower()
    assert settings.ai_api_key == "" or settings.ai_api_key not in serialized
