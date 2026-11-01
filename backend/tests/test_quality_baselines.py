from decimal import Decimal
import csv
import io
import json

from app.services.baseline_service import (
    _histogram,
    compare_observations,
    statistical_configuration,
)


def _create_tabular_run(client, filename: str, content: bytes) -> dict:
    uploaded = client.post(
        "/api/v1/sources/upload",
        files={"file": (filename, content, "text/csv")},
    )
    assert uploaded.status_code == 201, uploaded.text
    run = client.post(
        "/api/v1/runs",
        json={"source_file_id": uploaded.json()["source_file_id"], "pipeline_id": "general-tabular"},
    )
    assert run.status_code == 201, run.text
    return run.json()


def test_numeric_drift_uses_shared_bins_and_marks_shift_as_a_signal():
    baseline_values = [Decimal(index) for index in range(100)]
    target_values = [Decimal(index + 1000) for index in range(100)]
    baseline_distribution = _histogram(baseline_values, 10)
    target_distribution = _histogram(
        target_values,
        10,
        baseline_distribution["edges"],
    )
    assert target_distribution["edges"] == baseline_distribution["edges"]

    baseline_profile = {
        "columns": ["amount"],
        "row_count": 100,
        "null_counts": {"amount": 0},
        "inferred_types": {"amount": "integer"},
        "duplicate_row_count": 0,
        "column_profiles": {
            "amount": {
                "numeric": {"sample_size": 100, "outlier_count_iqr": 0},
                "value_shapes": {"INTEGER": 100},
            }
        },
    }
    target_profile = {
        **baseline_profile,
        "column_profiles": {
            "amount": {
                "numeric": {"sample_size": 100, "outlier_count_iqr": 0},
                "value_shapes": {"INTEGER": 100},
            }
        },
    }
    comparison = compare_observations(
        baseline_profile,
        {"amount": baseline_distribution},
        {},
        target_profile,
        {"amount": target_distribution},
        {},
        [],
        [],
        configuration=statistical_configuration(),
    )

    assessment = comparison["numeric_distribution_drift"][0]
    assert assessment["status"] == "ASSESSED"
    assert assessment["psi"] > 0.25
    assert assessment["binned_ks_distance"] == 1
    assert comparison["anomaly_signals"][0]["type"] == "NUMERIC_DISTRIBUTION_SHIFT"
    assert comparison["confirmed_invalid_records"] is False


def test_numeric_drift_is_not_reported_below_minimum_sample():
    baseline_distribution = _histogram([Decimal(index) for index in range(99)], 10)
    target_distribution = _histogram(
        [Decimal(index) for index in range(99)],
        10,
        baseline_distribution["edges"],
    )
    profile = {
        "columns": ["amount"],
        "row_count": 99,
        "null_counts": {"amount": 0},
        "inferred_types": {"amount": "integer"},
        "duplicate_row_count": 0,
        "column_profiles": {"amount": {"numeric": {}, "value_shapes": {}}},
    }
    comparison = compare_observations(
        profile,
        {"amount": baseline_distribution},
        {},
        profile,
        {"amount": target_distribution},
        {},
        [],
        [],
        configuration=statistical_configuration(),
    )
    assessment = comparison["numeric_distribution_drift"][0]
    assert assessment["status"] == "INSUFFICIENT_SAMPLE"
    assert assessment["psi"] is None
    assert assessment["binned_ks_distance"] is None


def test_direct_run_comparison_uses_persisted_results_and_does_not_create_baseline(client):
    reference = _create_tabular_run(
        client,
        "reference.csv",
        b"record_id,amount\nA,1\nB,2\n",
    )
    comparison = _create_tabular_run(
        client,
        "comparison.csv",
        b"record_id,amount\nA,1\nA,1\nC,5\n",
    )

    before = client.get("/api/v1/quality/baselines").json()["total"]
    response = client.get(
        "/api/v1/quality/runs/compare",
        params={
            "reference_run_id": reference["run_id"],
            "comparison_run_id": comparison["run_id"],
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["reference_run_id"] == reference["run_id"]
    assert result["comparison_run_id"] == comparison["run_id"]
    assert result["reference_filename"] == "reference.csv"
    assert result["comparison_filename"] == "comparison.csv"
    assert result["row_count_change"] == {"baseline": 2, "current": 3, "delta": 1, "delta_percent": 50.0}
    assert result["duplicate_rate_change"]["baseline_rate"] == 0
    assert result["duplicate_rate_change"]["current_rate"] == 1 / 3
    uniqueness = next(
        item for item in result["validation_failure_changes"]
        if item["validation_id"] == "TABULAR:ROW_UNIQUENESS"
    )
    assert uniqueness["baseline_status"] == "PASS"
    assert uniqueness["current_status"] == "FAIL"
    assert result["confirmed_invalid_records"] is False
    assert client.get("/api/v1/quality/baselines").json()["total"] == before == 0

    json_export = client.get(
        f"/api/v1/validation/runs/{comparison['run_id']}/export",
        params={"format": "json"},
    )
    assert json_export.status_code == 200
    exported = json.loads(json_export.text)
    assert exported["run_id"] == comparison["run_id"]
    assert exported["attempt_id"]
    assert exported["total"] == len(exported["items"]) > 0
    assert any(item["validation_id"] == "TABULAR:ROW_UNIQUENESS" for item in exported["items"])

    csv_export = client.get(
        f"/api/v1/validation/runs/{comparison['run_id']}/export",
        params={"format": "csv", "status": "FAIL", "execution_stage": "pre_transformation"},
    )
    assert csv_export.status_code == 200
    rows = list(csv.reader(io.StringIO(csv_export.text)))
    assert len(rows) > 1
    assert "TABULAR:ROW_UNIQUENESS" in csv_export.text


def test_run_comparison_does_not_turn_non_executed_states_into_failure_rates():
    from app.services.baseline_service import _compare_validation_failures

    comparison = _compare_validation_failures(
        [{"validation_id": "RULE:amount", "status": "PASS", "checked_rows": 10, "failed_rows": 0}],
        [
            type("Execution", (), {
                "validation_id": "RULE:amount",
                "status": "REQUIRES_CONFIGURATION",
                "checked_rows": 0,
                "failed_rows": 0,
            })()
        ],
    )
    assert comparison[0]["baseline_failure_rate"] == 0
    assert comparison[0]["current_failure_rate"] is None
    assert comparison[0]["assessment"] == "COMPARED"
