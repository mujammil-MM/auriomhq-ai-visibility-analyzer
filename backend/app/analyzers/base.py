"""Shared primitives for the analysis engines.

Every check is declared once with its metadata (id, category, severity, weight,
educational copy) and an evaluator function that returns an :class:`Outcome`.
The evaluator only ever sees evidence collected by the crawler — nothing is
invented.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any, Callable, Iterable, Sequence

from ..crawler import CrawlResult, PageSnapshot

PASS = "pass"
WARNING = "warning"
FAIL = "fail"
NOT_TESTED = "not_tested"

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}
STATUS_LABEL = {PASS: "Pass", WARNING: "Warning", FAIL: "Fail", NOT_TESTED: "Not tested"}
DEFAULT_WARNING_CREDIT = 0.5


@dataclass
class Outcome:
    status: str
    evidence: str
    credit: float | None = None      # explicit partial credit for warnings
    detail: str = ""
    pages: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CheckSpec:
    id: str
    pillar: str            # seo | aeo | geo
    category: str
    title: str
    description: str       # what the check verifies
    why: str               # why it matters (plain language)
    fix: str               # how to fix it
    example: str           # example corrected implementation
    severity: str
    weight: int
    priority: int          # 1 = fix immediately, 2 = discoverability, 3 = AI readiness
    evaluate: Callable[[CrawlResult], Outcome]


@dataclass
class CheckResult:
    id: str
    pillar: str
    category: str
    title: str
    description: str
    status: str
    status_label: str
    severity: str
    weight: int
    credit: float
    earned: float
    evidence: str
    why: str
    fix: str
    example: str
    priority: int
    pages: list[str] = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pillar": self.pillar,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "statusLabel": self.status_label,
            "severity": self.severity,
            "weight": self.weight,
            "credit": round(self.credit, 3),
            "earned": round(self.earned, 2),
            "evidence": self.evidence,
            "why": self.why,
            "fix": self.fix,
            "example": self.example,
            "priority": self.priority,
            "pages": self.pages[:8],
            "detail": self.detail,
        }


def run_checks(specs: Sequence[CheckSpec], crawl: CrawlResult) -> list[CheckResult]:
    results: list[CheckResult] = []
    for spec in specs:
        try:
            outcome = spec.evaluate(crawl)
        except Exception as exc:  # a failing evaluator must never award points
            outcome = Outcome(
                NOT_TESTED,
                f"Check could not be completed: {type(exc).__name__}. No score awarded.",
            )
        status = outcome.status
        if status == PASS:
            credit = 1.0
        elif status == WARNING:
            credit = DEFAULT_WARNING_CREDIT if outcome.credit is None else outcome.credit
        elif status == FAIL:
            credit = 0.0
        else:
            credit = 0.0
        credit = max(0.0, min(1.0, credit))
        earned = 0.0 if status == NOT_TESTED else round(spec.weight * credit, 2)
        results.append(
            CheckResult(
                id=spec.id,
                pillar=spec.pillar,
                category=spec.category,
                title=spec.title,
                description=spec.description,
                status=status,
                status_label=STATUS_LABEL[status],
                severity=spec.severity,
                weight=spec.weight,
                credit=credit,
                earned=earned,
                evidence=outcome.evidence,
                why=spec.why,
                fix=spec.fix,
                example=spec.example,
                priority=spec.priority,
                pages=outcome.pages,
                detail=outcome.detail,
            )
        )
    return results


# ---------------------------------------------------------------------------
# helpers used by evaluators
# ---------------------------------------------------------------------------
def analysable_pages(crawl: CrawlResult) -> list[PageSnapshot]:
    return [p for p in crawl.pages if p.ok and p.word_count > 0]


def home(crawl: CrawlResult) -> PageSnapshot | None:
    return crawl.home


def quote(text: str, limit: int = 180) -> str:
    text = " ".join((text or "").split())
    if not text:
        return "(empty)"
    return f"“{text[:limit]}{'…' if len(text) > limit else ''}”"


def pct(value: float) -> str:
    return f"{round(value * 100)}%"


def status_word(status: int | None) -> str:
    return f"HTTP {status}" if status else "no response"


def average(values: Iterable[float], default: float = 0.0) -> float:
    values = list(values)
    return round(mean(values), 2) if values else default


def host_of(url: str) -> str:
    from urllib.parse import urlsplit

    return (urlsplit(url).hostname or "").lower()
