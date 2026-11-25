"""Scoring model.

Documented, deterministic and evidence-based:

* Every check carries a fixed weight (points) that reflects how much the signal
  matters for that pillar.
* A **Pass** earns the full weight, a **Warning** earns partial credit
  (check-specific, usually 50–70%), a **Fail** earns 0.
* **Not tested** checks are removed from both the earned and the available
  points — so an unmeasured signal can never be awarded full marks, and it can
  never unfairly drag the score down either.
* Pillar score = round(100 × earned / available), where `available` only counts
  tested checks.

Overall AI Visibility Score = weighted blend of the three pillars
(SEO 40%, AEO 30%, GEO 30%) computed over the pillars that were actually
measured; if a pillar has no tested checks the remaining weights are
re-normalised.

The weighting rationale is published in /docs/METHODOLOGY.md and served at
GET /api/methodology so the UI can explain the number.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .base import NOT_TESTED, SEVERITY_ORDER, CheckResult, Outcome

PILLAR_WEIGHTS = {"seo": 0.40, "aeo": 0.30, "geo": 0.30}
PILLAR_LABELS = {"seo": "SEO", "aeo": "AEO", "geo": "GEO"}


@dataclass
class PillarScore:
    pillar: str
    label: str
    score: int | None
    earned: float
    available: float
    checks_total: int
    tested: int
    passed: int
    warnings: int
    failed: int
    not_tested: int
    weight: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "pillar": self.pillar,
            "label": self.label,
            "score": self.score,
            "earned": round(self.earned, 1),
            "available": round(self.available, 1),
            "checksTotal": self.checks_total,
            "tested": self.tested,
            "passed": self.passed,
            "warnings": self.warnings,
            "failed": self.failed,
            "notTested": self.not_tested,
            "weight": self.weight,
        }


@dataclass
class ScoreSummary:
    overall: int | None
    pillars: dict[str, PillarScore]
    counts: dict[str, int]
    severity_counts: dict[str, int]
    categories: list[dict[str, Any]] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "pillars": {k: v.to_dict() for k, v in self.pillars.items()},
            "counts": self.counts,
            "severityCounts": self.severity_counts,
            "categories": self.categories,
            "explanation": self.explanation,
            "methodology": {
                "pillarWeights": PILLAR_WEIGHTS,
                "warningCredit": "Warning = partial credit (50–70% depending on the check)",
                "notTested": "Excluded from both earned and available points",
                "formula": "pillar = round(100 × earned / available); overall = Σ(pillar × weight) / Σ(weight)",
            },
        }


def _score_pillar(pillar: str, results: list[CheckResult]) -> PillarScore:
    tested = [r for r in results if r.status != NOT_TESTED]
    earned = sum(r.earned for r in tested)
    available = float(sum(r.weight for r in tested))
    score = round(100 * earned / available) if available else None
    return PillarScore(
        pillar=pillar,
        label=PILLAR_LABELS.get(pillar, pillar.upper()),
        score=score,
        earned=earned,
        available=available,
        checks_total=len(results),
        tested=len(tested),
        passed=sum(1 for r in tested if r.status == "pass"),
        warnings=sum(1 for r in tested if r.status == "warning"),
        failed=sum(1 for r in tested if r.status == "fail"),
        not_tested=len(results) - len(tested),
        weight=PILLAR_WEIGHTS.get(pillar, 0),
    )


def summarise(all_results: Iterable[CheckResult]) -> ScoreSummary:
    results = list(all_results)
    pillars: dict[str, PillarScore] = {}
    for pillar in ("seo", "aeo", "geo"):
        pillar_results = [r for r in results if r.pillar == pillar]
        pillars[pillar] = _score_pillar(pillar, pillar_results)

    weighted_sum = 0.0
    weight_total = 0.0
    for pillar, ps in pillars.items():
        if ps.score is None:
            continue
        weighted_sum += ps.score * ps.weight
        weight_total += ps.weight
    overall = round(weighted_sum / weight_total) if weight_total else None

    counts = {
        "pass": sum(1 for r in results if r.status == "pass"),
        "warning": sum(1 for r in results if r.status == "warning"),
        "fail": sum(1 for r in results if r.status == "fail"),
        "not_tested": sum(1 for r in results if r.status == NOT_TESTED),
        "total": len(results),
    }
    severity_counts = {k: 0 for k in SEVERITY_ORDER}
    for r in results:
        if r.status in {"fail", "warning"}:
            severity_counts[r.severity] = severity_counts.get(r.severity, 0) + 1

    # category breakdown per pillar
    categories: list[dict[str, Any]] = []
    seen = {}
    for r in results:
        key = (r.pillar, r.category)
        if key not in seen:
            seen[key] = {"pillar": r.pillar, "category": r.category, "earned": 0.0, "available": 0.0,
                         "passed": 0, "warning": 0, "failed": 0, "notTested": 0}
            categories.append(seen[key])
        bucket = seen[key]
        if r.status == NOT_TESTED:
            bucket["notTested"] += 1
            continue
        bucket["available"] += r.weight
        bucket["earned"] += r.earned
        if r.status == "pass":
            bucket["passed"] += 1
        elif r.status == "warning":
            bucket["warning"] += 1
        else:
            bucket["failed"] += 1
    for bucket in categories:
        bucket["score"] = round(100 * bucket["earned"] / bucket["available"]) if bucket["available"] else None
        bucket["earned"] = round(bucket["earned"], 1)
        bucket["available"] = round(bucket["available"], 1)

    explanation = _explain(overall, pillars, counts)
    return ScoreSummary(overall=overall, pillars=pillars, counts=counts,
                        severity_counts=severity_counts, categories=categories,
                        explanation=explanation)


def _explain(overall: int | None, pillars: dict[str, PillarScore], counts: dict[str, int]) -> list[str]:
    lines: list[str] = []
    if overall is None:
        lines.append("No overall score could be calculated because no checks were testable.")
        for pillar in ("seo", "aeo", "geo"):
            ps = pillars[pillar]
            lines.append(f"{ps.label}: not scored — no checks in this pillar could be completed.")
        return lines
    lines.append(
        f"Overall AI Visibility Score: {overall}/100 — a weighted blend of SEO (40%), AEO (30%) and GEO (30%)."
    )
    for pillar in ("seo", "aeo", "geo"):
        ps = pillars[pillar]
        if ps.score is None:
            lines.append(f"{ps.label}: not scored — no checks in this pillar could be completed.")
            continue
        lines.append(
            f"{ps.label}: {ps.score}/100 from {ps.earned:.1f} of {ps.available:.0f} available points "
            f"across {ps.tested} tested checks ({ps.passed} pass, {ps.warnings} warning, {ps.failed} fail)."
        )
    if counts["not_tested"]:
        lines.append(
            f"{counts['not_tested']} check(s) could not be tested and were excluded from the score — "
            "they are neither passed nor failed."
        )
    lines.append(
        "Warnings earn partial credit (50–70% of the check weight). Failures earn none. "
        "Scores describe on-page readiness only; they are not rankings, traffic or citation data."
    )
    return lines


def band(score: int | None) -> dict[str, str]:
    """Human label + tone for a score, used by the UI and the PDF."""
    if score is None:
        return {"label": "Not scored", "tone": "neutral"}
    if score >= 85:
        return {"label": "Strong", "tone": "positive"}
    if score >= 70:
        return {"label": "Good", "tone": "positive"}
    if score >= 55:
        return {"label": "Needs work", "tone": "warning"}
    if score >= 35:
        return {"label": "Weak", "tone": "warning"}
    return {"label": "Critical", "tone": "negative"}
