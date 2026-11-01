"""Transparent scoring over persisted validation records only."""

from collections import Counter
from typing import Any

EXECUTED_STATUSES = {"PASS", "FAIL", "WARNING", "ERROR"}
SEVERITY_WEIGHTS = {"CRITICAL": 4, "ERROR": 3, "WARNING": 2, "INFO": 1}
MINIMUM_EXECUTED_CHECKS = 3
MINIMUM_COVERAGE_PERCENT = 80.0


def calculate_quality_score(
    rows: list[Any],
    *,
    catalog_total: int,
    eligible_catalog_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Score eligible persisted runtime checks; never treat absent or N/A checks as passes."""
    score_eligible = [
        row for row in rows
        if row.applicability not in {"NOT_APPLICABLE", "DISABLED", "UNSUPPORTED_INTEGRATION"}
    ]
    executed = [
        row for row in score_eligible
        if row.applicability == "APPLICABLE" and row.status in EXECUTED_STATUSES
    ]
    status_counts = Counter(row.status for row in rows)
    coverage_percent = (100 * len(executed) / len(score_eligible)) if score_eligible else None

    weighted_failure = 0.0
    total_weight = 0
    for row in executed:
        weight = SEVERITY_WEIGHTS.get(row.severity, 1)
        if row.status == "ERROR":
            failure_rate = 1.0
        elif row.checked_rows:
            failure_rate = min(1.0, max(0.0, row.failed_rows / row.checked_rows))
        else:
            failure_rate = 0.0 if row.status == "PASS" else 1.0
        weighted_failure += weight * failure_rate
        total_weight += weight

    reasons = []
    if not score_eligible:
        reasons.append("No validation results were eligible for scoring on this attempt.")
    if len(executed) < MINIMUM_EXECUTED_CHECKS:
        reasons.append(f"At least {MINIMUM_EXECUTED_CHECKS} executed checks are required; {len(executed)} were available.")
    if coverage_percent is not None and coverage_percent < MINIMUM_COVERAGE_PERCENT:
        reasons.append(
            f"Observed validation coverage is {coverage_percent:.1f}%; at least {MINIMUM_COVERAGE_PERCENT:.0f}% is required."
        )

    score = None
    if not reasons and total_weight:
        score = round(100 * (1 - weighted_failure / total_weight), 2)

    catalog_coverage = None
    if catalog_total == 200 and eligible_catalog_ids is not None:
        eligible_ids = eligible_catalog_ids
        assessed_ids = {row.validation_id for row in rows}
        catalog_coverage = round(100 * len(assessed_ids & eligible_ids) / len(eligible_ids), 2) if eligible_ids else None

    return {
        "score": score,
        "score_status": "AVAILABLE" if score is not None else "INSUFFICIENT_DATA",
        "coverage_percent": round(coverage_percent, 2) if coverage_percent is not None else None,
        "applicable_checks": len(score_eligible),
        "executed_checks": len(executed),
        "passed_checks": status_counts.get("PASS", 0),
        "failed_checks": status_counts.get("FAIL", 0) + status_counts.get("ERROR", 0),
        "warning_checks": status_counts.get("WARNING", 0),
        "skipped_checks": status_counts.get("SKIPPED", 0),
        "not_applicable_checks": status_counts.get("NOT_APPLICABLE", 0),
        "requires_configuration_checks": status_counts.get("REQUIRES_CONFIGURATION", 0),
        "blocked_checks": status_counts.get("BLOCKED", 0),
        "dataset_level_failures": sum(
            row.status in {"FAIL", "WARNING", "ERROR"} and row.checked_rows == 0 for row in executed
        ),
        "catalog_total": catalog_total,
        "catalog_eligible_checks": len(eligible_catalog_ids) if eligible_catalog_ids is not None else 0,
        "catalog_coverage_percent": catalog_coverage,
        "insufficiency_reasons": reasons,
        "score_scope": "Persisted applicable runtime checks for the selected attempt.",
        "methodology": {
            "formula": "100 × (1 − severity_weighted_failure_rate)",
            "severity_weights": SEVERITY_WEIGHTS,
            "row_level_failure_rate": "failed_rows / checked_rows; dataset-level non-PASS results with zero checked rows count as fully failed",
            "coverage_formula": "executed applicable checks / eligible assessed results × 100; not-applicable, disabled, and unsupported checks are excluded; skipped, blocked, and configuration-dependent checks remain uncovered",
            "minimum_executed_checks": MINIMUM_EXECUTED_CHECKS,
            "minimum_coverage_percent": MINIMUM_COVERAGE_PERCENT,
            "not_applicable_skipped_blocked_or_unconfigured": "excluded from score; applicable non-executed checks reduce coverage",
            "catalog_wide_coverage": "computed only when all 200 definitions are imported; numerator is exact-ID assessed enabled checks marked fully or partially implemented",
        },
    }
