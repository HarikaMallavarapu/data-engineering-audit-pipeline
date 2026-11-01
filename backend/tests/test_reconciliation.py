from decimal import Decimal

from app.engine.reconciliation import reconcile_counts


def test_reconciliation_checks_dispositions_publication_and_currency_totals():
    counts = {"input": 4, "accepted": 2, "rejected": 1, "duplicates": 1, "published": 2}
    result = reconcile_counts(counts, {"USD": Decimal("10.00")}, {"USD": Decimal("10.00")})
    assert result["balanced"] is True
    assert result["checks"] == {
        "input_equals_dispositions": True,
        "accepted_equals_published": True,
        "accepted_amount_equals_published_amount": True,
    }
    assert {item["validation_id"] for item in result["validation_results"]} == {
        "RECONCILIATION:INPUT_DISPOSITIONS",
        "RECONCILIATION:PUBLISHED_COUNT",
        "RECONCILIATION:AMOUNT_TOTALS",
    }
    assert all(item["status"] == "PASS" for item in result["validation_results"])
    assert all(item["execution_time_ms"] > 0 for item in result["validation_results"])


def test_reconciliation_detects_count_or_amount_mismatch():
    result = reconcile_counts(
        {"input": 3, "accepted": 2, "rejected": 1, "duplicates": 0, "published": 1},
        {"USD": Decimal("10.00")},
        {"USD": Decimal("9.00")},
    )
    assert result["balanced"] is False
    assert result["checks"]["input_equals_dispositions"] is True
    assert result["checks"]["accepted_equals_published"] is False
    assert result["checks"]["accepted_amount_equals_published_amount"] is False
    by_id = {item["validation_id"]: item for item in result["validation_results"]}
    assert by_id["RECONCILIATION:PUBLISHED_COUNT"]["status"] == "FAIL"
    assert by_id["RECONCILIATION:AMOUNT_TOTALS"]["status"] == "FAIL"
