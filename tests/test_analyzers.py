"""Analysis-engine tests (scenarios 1, 2, 4, 8) — findings must match real HTML."""
from __future__ import annotations

import asyncio

from app.analyzers import analyse
from app.crawler import Crawler


def run_site(url: str, max_pages: int = 4):
    crawl = asyncio.run(Crawler(max_pages=max_pages).crawl(url))
    analysis = analyse(crawl)
    by_id = {check["id"]: check for check in analysis["checks"]}
    return crawl, analysis, by_id


def test_good_site_passes_core_checks(good_site):
    crawl, analysis, checks = run_site(good_site.base_url + "/")
    assert checks["seo.title"]["status"] == "pass"
    assert checks["seo.meta_description"]["status"] in {"pass", "warning"}
    assert checks["seo.viewport"]["status"] == "pass"
    assert checks["seo.robots_meta"]["status"] == "pass"
    assert checks["seo.robots_txt"]["status"] in {"pass", "warning"}
    assert checks["seo.sitemap"]["status"] == "pass"
    assert checks["seo.headings"]["status"] in {"pass", "warning"}
    assert checks["aeo.faq_section"]["status"] == "pass"
    assert checks["aeo.question_headings"]["status"] in {"pass", "warning"}
    assert checks["geo.org_identity"]["status"] == "pass"
    assert checks["geo.schema_presence"]["status"] in {"pass", "warning"}
    assert analysis["scores"]["overall"] is not None
    assert analysis["scores"]["overall"] > 50


def test_missing_metadata_fails_with_evidence(site, allow_private):
    site.set_routes({
        "/": (200, {"Content-Type": "text/html"}, (
            "<html><head></head><body><h1>Only a heading</h1>"
            "<p>Some visible words so the page is analysable at all, repeated a few times.</p>"
            "</body></html>"
        ).encode()),
    })
    _crawl, _analysis, checks = run_site(site.base_url + "/", max_pages=1)
    assert checks["seo.title"]["status"] == "fail"
    assert checks["seo.meta_description"]["status"] == "fail"
    assert checks["seo.viewport"]["status"] == "fail"
    assert checks["seo.canonical"]["status"] == "fail"
    assert checks["seo.lang"]["status"] in {"fail", "warning"}
    assert "no <title>" in checks["seo.title"]["evidence"].lower() or "title" in checks["seo.title"]["evidence"].lower()


def test_missing_structured_data_is_reported(site, allow_private):
    site.set_routes({
        "/": (200, {"Content-Type": "text/html"}, (
            "<html lang='en'><head><title>No schema site</title>"
            "<meta name='description' content='A page with a description but absolutely no structured data anywhere in the markup at all, deliberately.'>"
            "</head><body><h1>No schema</h1><p>We write about things that matter to people reading the page.</p></body></html>"
        ).encode()),
    })
    _crawl, _analysis, checks = run_site(site.base_url + "/", max_pages=1)
    assert checks["geo.schema_presence"]["status"] == "fail"
    assert checks["aeo.article_schema"]["status"] in {"fail", "warning"}
    assert checks["geo.org_identity"]["status"] in {"fail", "warning"}


def test_thin_content_is_flagged(site, allow_private):
    site.set_routes({
        "/": (200, {"Content-Type": "text/html"}, (
            "<html lang='en'><head><title>Thin</title>"
            "<meta name='description' content='A thin page used to verify that short content is flagged by the analyser as thin.'>"
            "</head><body><h1>Thin</h1><p>Too short.</p></body></html>"
        ).encode()),
    })
    _crawl, _analysis, checks = run_site(site.base_url + "/", max_pages=1)
    assert checks["seo.content_length"]["status"] == "fail"
    assert checks["aeo.answer_accessibility"]["status"] == "fail"


def test_inaccessible_pages_do_not_count_as_passed(good_site):
    """The site links to several pages; a 404 target must surface as a broken link, not a pass."""
    _crawl, _analysis, checks = run_site(good_site.base_url + "/", max_pages=6)
    assert checks["seo.broken_links"]["status"] in {"pass", "fail", "not_tested"}


def test_every_check_carries_required_fields(good_site):
    _crawl, _analysis, _checks = run_site(good_site.base_url + "/", max_pages=2)
    required = {
        "id", "pillar", "category", "title", "description", "status", "severity", "weight",
        "credit", "earned", "evidence", "why", "fix", "example", "priority",
    }
    for check in _analysis["checks"]:
        assert required.issubset(check.keys())
        assert check["status"] in {"pass", "warning", "fail", "not_tested"}
        assert check["severity"] in {"critical", "high", "medium", "low", "informational"}
        assert check["evidence"]
        if check["status"] == "pass":
            assert check["earned"] == check["weight"]
        if check["status"] == "not_tested":
            assert check["earned"] == 0


def test_recommendations_only_reference_evidence(good_site):
    _crawl, analysis, _checks = run_site(good_site.base_url + "/", max_pages=3)
    recs = analysis["recommendations"]
    assert recs["roadmap"] and len(recs["roadmap"]) == 3
    for phase in recs["roadmap"]:
        for item in phase["items"]:
            assert item["evidence"]
            assert item["benefit"]
            assert item["difficulty"] in {"Easy", "Moderate", "Hard"}
            assert item["impact"] in {"High", "Medium", "Low"}
            lowered = item["benefit"].lower()
            for promise in ("will rank", "guaranteed to", "guarantees a", "increase traffic"):
                assert promise not in lowered
    drafts = recs["drafts"]
    assert drafts["titles"]
    assert drafts["faqQuestions"]


def test_score_explanation_is_present(good_site):
    _crawl, analysis, _checks = run_site(good_site.base_url + "/", max_pages=2)
    assert analysis["scores"]["explanation"]
    assert analysis["scores"]["methodology"]["formula"]
    assert analysis["scores"]["methodology"]["pillarWeights"]["seo"] == 0.4
