from types import SimpleNamespace

from app.services.quality_service import calculate_quality_score


def _result(validation_id: str, status: str, severity: str, applicability: str, checked: int, failed: int):
    return SimpleNamespace(
        validation_id=validation_id,
        status=status,
        severity=severity,
        applicability=applicability,
        checked_rows=checked,
        failed_rows=failed,
    )


def test_score_requires_minimum_checks_and_coverage_and_excludes_not_applicable():
    rows = [
        _result("A", "PASS", "ERROR", "APPLICABLE", 10, 0),
        _result("B", "FAIL", "CRITICAL", "APPLICABLE", 10, 1),
        _result("C", "PASS", "WARNING", "APPLICABLE", 0, 0),
        _result("D", "BLOCKED", "CRITICAL", "APPLICABLE", 0, 0),
        _result("E", "NOT_APPLICABLE", "INFO", "NOT_APPLICABLE", 0, 0),
    ]

    insufficient = calculate_quality_score(rows, catalog_total=0)
    assert insufficient["score"] is None
    assert insufficient["score_status"] == "INSUFFICIENT_DATA"
    assert insufficient["coverage_percent"] == 75
    assert insufficient["applicable_checks"] == 4
    assert insufficient["executed_checks"] == 3
    assert insufficient["not_applicable_checks"] == 1
    assert insufficient["blocked_checks"] == 1
    assert insufficient["catalog_coverage_percent"] is None

    rows.append(_result("F", "PASS", "INFO", "APPLICABLE", 2, 0))
    available = calculate_quality_score(rows, catalog_total=0)
    assert available["score_status"] == "AVAILABLE"
    assert available["coverage_percent"] == 80
    assert available["score"] == 96
