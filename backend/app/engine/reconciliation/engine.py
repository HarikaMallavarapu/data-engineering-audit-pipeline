from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

from app.engine.validation.contracts import ApplicabilityAssessment, ValidationResult


def reconcile_counts(
    counts: dict[str, int],
    accepted_amounts: dict[str, Decimal],
    published_amounts: dict[str, Decimal],
    *,
    amounts_applicable: bool = True,
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    results: list[dict[str, Any]] = []

    started_ns = time.perf_counter_ns()
    rows_balance = counts["input"] == (
        counts["accepted"] + counts["rejected"] + counts["duplicates"]
    )
    elapsed_ns = time.perf_counter_ns() - started_ns
    checks["input_equals_dispositions"] = rows_balance
    results.append(
        _result(
            validation_id="RECONCILIATION:INPUT_DISPOSITIONS",
            name="Input rows equal final dispositions",
            passed=rows_balance,
            elapsed_ns=elapsed_ns,
            configuration={
                "formula": "input == accepted + rejected + duplicates",
                "input": counts["input"],
                "accepted": counts["accepted"],
                "rejected": counts["rejected"],
                "duplicates": counts["duplicates"],
            },
        ).model_dump(mode="json")
    )

    started_ns = time.perf_counter_ns()
    published_balance = counts["accepted"] == counts["published"]
    elapsed_ns = time.perf_counter_ns() - started_ns
    checks["accepted_equals_published"] = published_balance
    results.append(
        _result(
            validation_id="RECONCILIATION:PUBLISHED_COUNT",
            name="Accepted rows equal published rows",
            passed=published_balance,
            elapsed_ns=elapsed_ns,
            configuration={
                "formula": "accepted == published",
                "accepted": counts["accepted"],
                "published": counts["published"],
            },
        ).model_dump(mode="json")
    )

    amount_balance = True
    if amounts_applicable:
        started_ns = time.perf_counter_ns()
        amount_balance = accepted_amounts == published_amounts
        elapsed_ns = time.perf_counter_ns() - started_ns
        checks["accepted_amount_equals_published_amount"] = amount_balance
        results.append(
            _result(
                validation_id="RECONCILIATION:AMOUNT_TOTALS",
                name="Accepted and published amount totals match",
                passed=amount_balance,
                elapsed_ns=elapsed_ns,
                configuration={
                    "formula": "accepted_amounts_by_currency == published_amounts_by_currency",
                    "accepted_amounts_by_currency": {
                        currency: format(amount, ".2f")
                        for currency, amount in sorted(accepted_amounts.items())
                    },
                    "published_amounts_by_currency": {
                        currency: format(amount, ".2f")
                        for currency, amount in sorted(published_amounts.items())
                    },
                },
            ).model_dump(mode="json")
        )

    return {
        "balanced": rows_balance and published_balance and amount_balance,
        "checks": checks,
        "validation_results": results,
    }


def _result(
    *,
    validation_id: str,
    name: str,
    passed: bool,
    elapsed_ns: int,
    configuration: dict[str, Any],
) -> ValidationResult:
    return ValidationResult(
        validation_id=validation_id,
        name=name,
        category="Reconciliation",
        status="PASS" if passed else "FAIL",
        severity="ERROR",
        applicability=ApplicabilityAssessment(
            status="APPLICABLE",
            reason="The pipeline compared persisted run counts or financial totals.",
        ),
        execution_stage="RECONCILIATION",
        checked_rows=1,
        passed_rows=int(passed),
        failed_rows=int(not passed),
        failure_percentage=0 if passed else 100,
        message=(
            "The reconciliation comparison matched."
            if passed
            else "The reconciliation comparison did not match."
        ),
        recommendation=None if passed else "Inspect the run counts, published artifact, and aggregate totals.",
        execution_time_ms=max(1, (elapsed_ns + 999_999) // 1_000_000),
        rule_version="reconciliation-1",
        configuration_snapshot=configuration,
    )
