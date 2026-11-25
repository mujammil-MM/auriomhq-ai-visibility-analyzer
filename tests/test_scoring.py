"""Scoring-model tests: weights, partial credit, not-tested handling, blending."""
from __future__ import annotations

from app.analyzers.base import CheckResult, run_checks
from app.analyzers.base import CheckSpec, Outcome
from app.analyzers.scoring import PILLAR_WEIGHTS, summarise


def make_result(check_id: str, pillar: str, weight: int, status: str, credit: float | None = None) -> CheckResult:
    if status == "pass":
        effective = 1.0
    elif status == "warning":
        effective = 0.5 if credit is None else credit
    else:
        effective = 0.0
    return CheckResult(
        id=check_id, pillar=pillar, category="Test", title=check_id, description="", status=status,
        status_label=status, severity="high", weight=weight, credit=effective,
        earned=0.0 if status == "not_tested" else round(weight * effective, 2),
        evidence="", why="", fix="", example="", priority=1,
    )


def test_pillar_score_is_earned_over_available():
    results = [
        make_result("a", "seo", 10, "pass"),
        make_result("b", "seo", 10, "fail"),
    ]
    summary = summarise(results)
    assert summary.pillars["seo"].score == 50
    assert summary.pillars["seo"].earned == 10


def test_warning_gets_partial_credit():
    results = [make_result("a", "seo", 10, "warning", credit=0.6)]
    summary = summarise(results)
    assert summary.pillars["seo"].score == 60


def test_not_tested_is_excluded_from_both_sides():
    results = [
        make_result("a", "seo", 10, "pass"),
        make_result("b", "seo", 10, "not_tested"),
    ]
    summary = summarise(results)
    # 10/10 available (only tested) — the untested check neither helps nor hurts
    assert summary.pillars["seo"].score == 100
    assert summary.pillars["seo"].not_tested == 1
    assert summary.counts["not_tested"] == 1


def test_all_untested_pillar_is_unscored():
    results = [make_result("a", "aeo", 10, "not_tested")]
    summary = summarise(results)
    assert summary.pillars["aeo"].score is None
    assert "not scored" in " ".join(summary.explanation).lower()


def test_overall_uses_documented_pillar_weights():
    results = [
        make_result("a", "seo", 10, "pass"),   # 100
        make_result("b", "aeo", 10, "pass"),   # 100
        make_result("c", "geo", 10, "fail"),   # 0
    ]
    summary = summarise(results)
    assert summary.pillars["seo"].score == 100
    assert summary.pillars["geo"].score == 0
    expected = round(100 * PILLAR_WEIGHTS["seo"] + 100 * PILLAR_WEIGHTS["aeo"] + 0 * PILLAR_WEIGHTS["geo"])
    assert summary.overall == expected
    assert PILLAR_WEIGHTS["seo"] == 0.4 and PILLAR_WEIGHTS["aeo"] == 0.3 and PILLAR_WEIGHTS["geo"] == 0.3


def test_missing_pillar_weight_is_renormalised():
    results = [
        make_result("a", "seo", 10, "pass"),
        make_result("c", "geo", 10, "fail"),
    ]
    summary = summarise(results)
    expected = round((100 * 0.4 + 0 * 0.3) / 0.7)
    assert summary.overall == expected


def test_evaluator_exception_is_not_a_pass():
    def boom(crawl):
        raise ValueError("kaboom")

    spec = CheckSpec(
        id="x", pillar="seo", category="Test", title="Exploding", description="", why="", fix="",
        example="", severity="high", weight=10, priority=1, evaluate=boom,
    )
    results = run_checks([spec], crawl=None)  # type: ignore[arg-type]
    assert results[0].status == "not_tested"
    assert results[0].earned == 0.0


def test_category_breakdown_sums_match():
    results = [
        make_result("a", "seo", 10, "pass"),
        make_result("b", "seo", 10, "warning", credit=0.5),
        make_result("c", "geo", 10, "fail"),
    ]
    summary = summarise(results)
    seo = next(c for c in summary.categories if c["pillar"] == "seo")
    assert seo["available"] == 20
    assert seo["earned"] == 15
    assert seo["score"] == 75
