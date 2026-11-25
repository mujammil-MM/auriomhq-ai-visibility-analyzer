"""Analysis pipeline: crawl result → checks → scores → recommendations."""
from __future__ import annotations

from typing import Any

from ..crawler import CrawlResult
from .aeo import AEO_CHECKS
from .base import CheckResult, run_checks
from .geo import GEO_CHECKS
from .recommendations import build_evidence_pack, build_recommendations
from .scoring import PILLAR_LABELS, PILLAR_WEIGHTS, ScoreSummary, band, summarise
from .seo import SEO_CHECKS

ALL_CHECKS = {"seo": SEO_CHECKS, "aeo": AEO_CHECKS, "geo": GEO_CHECKS}

__all__ = [
    "ALL_CHECKS", "PILLAR_LABELS", "PILLAR_WEIGHTS", "analyse", "band", "summarise",
]


def analyse(crawl: CrawlResult) -> dict[str, Any]:
    results: list[CheckResult] = []
    for pillar, specs in ALL_CHECKS.items():
        results.extend(run_checks(specs, crawl))

    scores: ScoreSummary = summarise(results)
    recommendations = build_recommendations(crawl, results)
    evidence = build_evidence_pack(crawl, results, scores)

    return {
        "checks": [r.to_dict() for r in results],
        "scores": scores.to_dict(),
        "band": band(scores.overall),
        "recommendations": recommendations,
        "evidence": evidence,
        "_score_summary": scores,
        "_check_results": results,
    }
