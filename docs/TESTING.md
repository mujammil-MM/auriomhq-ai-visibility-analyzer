# Testing report — AuriomHQ AI Visibility Analyzer

Run with:

```bash
cd backend && python -m pytest ../tests -v
```

**Result: 63 passed, 0 failed (≈41 s)** on Python 3.13 / pytest 9.

Test architecture: a threaded local HTTP server serves synthetic websites (good site, broken-link
site, robots-blocked site, redirect chains, slow/erroring hosts). Because the SSRF guard blocks
private IPs by design, the tests explicitly enable `CRAWL_ALLOW_PRIVATE_TARGETS` for those fixtures
only; production behaviour (rejection) is asserted separately in `tests/test_security.py`.

## Scenario matrix (required cases)

| # | Required scenario | Test | Asserted behaviour | Result |
| --- | --- | --- | --- | --- |
| 1 | Valid website with good metadata | `test_crawls_well_formed_site`, `test_good_site_passes_core_checks` | Title/description/viewport/canonical/robots/sitemap parsed from real HTML; core checks pass; overall score computed | ✅ |
| 2 | Website with missing metadata | `test_missing_metadata_fails_with_evidence` | `seo.title`, `seo.meta_description`, `seo.viewport`, `seo.canonical` fail with evidence; never silently passed | ✅ |
| 3 | Website with broken internal links | `test_detects_broken_internal_links` | 404 and 500 internal targets surface in `broken_links`; working links excluded | ✅ |
| 4 | Website with missing structured data | `test_missing_structured_data_is_reported` | `geo.schema_presence` fails; `aeo.article_schema` and `geo.org_identity` fail/warn | ✅ |
| 5 | Website with inaccessible pages | `test_inaccessible_pages_do_not_count_as_passed`, `test_server_error_homepage_fails_with_message` | Inaccessible pages recorded; 5xx homepage aborts the audit with an actionable error | ✅ |
| 6 | Website blocking crawlers | `test_respects_robots_disallow`, `test_site_blocking_everything_is_flagged` | Disallowed paths never fetched; full block sets `robots.blocks_all` and `seo.robots_txt` fails | ✅ |
| 7 | Website with redirect chains | `test_redirect_chain_is_recorded`, `test_redirect_loop_is_detected` | Multi-hop chain recorded and scored; loops detected and reported | ✅ |
| 8 | Website with incomplete content | `test_thin_content_is_flagged` | `seo.content_length` and `aeo.answer_accessibility` fail | ✅ |
| 9 | Invalid URL | `test_invalid_urls_are_rejected`, `test_blocked_urls_raise` (20 cases) | `400` with a specific reason for localhost, private ranges, metadata IPs, IPv6, credentials, ports, protocols, control characters | ✅ |
| 10 | Timeout / server failure | `test_timeout_is_handled`, `test_unreachable_site_produces_actionable_error` | Read timeout and connection refusal produce a user-facing error; audit marked `failed` | ✅ |

## Additional verification required by the brief

| Requirement | Test(s) | Result |
| --- | --- | --- |
| Scores are calculated correctly | `test_scoring.py` (8 tests): earned/available, warning credit, weight blending, renormalisation, category totals | ✅ |
| Findings match actual HTML evidence | `test_title_and_headings_come_from_actual_html`, `test_every_check_carries_required_fields` — asserts exact title string, H2 text, schema type, alt-text count and that every check has non-empty evidence | ✅ |
| Unavailable checks are not falsely passed | `test_not_tested_is_excluded_from_both_sides`, `test_all_untested_pillar_is_unscored`, `test_evaluator_exception_is_not_a_pass` | ✅ |
| PDF reports contain correct results | `test_full_audit_lifecycle` — renders the PDF from the stored payload, asserts valid `%PDF` header and size; visual review of all 8 pages during development | ✅ |
| Shareable reports work | `test_full_audit_lifecycle` — share → public payload matches scores → public PDF → revoke → `404` | ✅ |
| Mobile interface is usable | Manual review at 390×844 (mobile nav, dashboard stack, tabs, tables, forms); no horizontal overflow | ✅ |
| Security restrictions cannot be bypassed | `test_security.py` (26 tests) incl. DNS rebinding mock, private IPv4/IPv6, metadata endpoint, scheme/port/credential rules | ✅ |
| No secrets leak to the client | `test_report_payload_contains_no_secrets` | ✅ |
| Lead submission is honest | `test_lead_validation_and_storage` — invalid email → 422; valid → 200 only after persistence; honeypot → 400 | ✅ |

## Manual verification performed

- Audited live sites: `auriomhq.work` (10 pages, overall 77), `example.com` (1 page, overall 26) — findings matched the actual HTML (e.g. missing `FAQPage` schema, 31% images without alt text, JS-heavy text/HTML ratio).
- Reviewed the generated PDF page by page (cover/dashboard, executive summary, site snapshot, critical findings, category performance, full check tables, roadmap, drafts, methodology/limitations/CTA).
- Reviewed desktop (1440 px) and mobile (390 px) renders of landing, progress, dashboard, all six tabs, share dialog, failure state, shared report and methodology pages.
- Verified the AI layer end-to-end against a local OpenAI-compatible stub: `aiEnhanced: true`, findings limited to supplied evidence; with no key the rule-based engine is used and the audit still completes.

## Known test gaps

- No browser-automation regression suite is committed (visual review only); adding Playwright is recommended before production.
- No load test: concurrency is bounded by `MAX_CONCURRENT_AUDITS` and per-IP rate limits, but throughput was not benchmarked.
- The AI layer is tested against a stub provider, not a live vendor endpoint.
