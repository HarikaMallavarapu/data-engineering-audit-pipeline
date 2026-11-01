import io
from decimal import Decimal

import pytest
from app.api.v1.engine import _merge_local_profile_suggestions
from app.engine.pipeline import validate_tabular_records
from app.engine.profiling.profiler import profile_records, suggest_regex
from app.engine.quality.rules import RULE_TYPE_REGISTRY, RuleDefinition, evaluate_rules
from app.engine.transformation.registry import TransformationDefinition, apply_transformations
from app.models import AIBudget, AICache, AIUsage, ValidationDefinition
from app.services.ai_service import infer_schema_with_tracking
from fastapi.testclient import TestClient
from openpyxl import Workbook
from pydantic import SecretStr, ValidationError


def test_profiler_reports_nulls_numeric_statistics_aliases_and_regex_evidence():
    columns = ["client_reference", "total_value", "invoice_number", "event_date"]
    records = [
        {
            "source_row_number": index + 2,
            "payload": {
                "client_reference": f"C-{index:04d}",
                "total_value": str(value),
                "invoice_number": f"INV-2026-{index:04d}" if index < 8 else "INVALID",
                "event_date": None if index == 0 else f"2026-11-{index + 1:02d}",
            },
        }
        for index, value in enumerate([1, 2, 3, 4, 5, 6, 7, 8, 900])
    ]
    profile = profile_records(columns, records, sample_size=100)
    assert profile["row_count"] == 9
    assert profile["profile_sample_size"] == 9
    assert profile["null_counts"]["event_date"] == 1
    assert profile["column_profiles"][1]["numeric"]["max"] == "900"
    assert profile["column_profiles"][2]["regex_suggestion"]["matching_count"] == 8
    assert profile["column_profiles"][2]["regex_suggestion"]["non_matching_count"] == 1
    assert any(item["suggested_semantic_field"] == "customer_id" for item in profile["mapping_candidates"])
    assert profile["schema_fingerprint"]


def test_regex_suggestion_refuses_too_few_values_and_reports_non_matches():
    assert suggest_regex(["A-001", "A-002"]) is None
    suggestion = suggest_regex(["A-001", "A-002", "invalid"])
    assert suggestion is not None
    assert suggestion["matching_count"] == 2
    assert suggestion["non_matching_examples"] == ["invalid"]
    assert suggestion["review_required"] is True


def test_llm_abstention_keeps_local_mappings_and_sample_regex_as_drafts():
    profile = profile_records(
        ["client_reference", "invoice_code"],
        [
            {"source_row_number": 2, "payload": {"client_reference": "C-001", "invoice_code": "INV-001"}},
            {"source_row_number": 3, "payload": {"client_reference": "C-002", "invoice_code": "INV-002"}},
            {"source_row_number": 4, "payload": {"client_reference": "C-003", "invoice_code": "INV-003"}},
        ],
    )
    analysis = {
        "mode": "llm",
        "mapping_suggestions": [],
        "rule_suggestions": [],
        "transformation_suggestions": [],
    }

    merged = _merge_local_profile_suggestions(analysis, profile)

    assert merged["mode"] == "llm"
    assert merged["mapping_suggestions"][0]["semantic_field"] == "customer_id"
    assert merged["mapping_suggestions"][0]["status"] == "suggested"
    assert merged["rule_suggestions"][0]["rule_type"] == "regex"
    assert merged["rule_suggestions"][0]["status"] == "draft"
    assert merged["rule_suggestions"][0]["enabled"] is False


def test_dominant_profile_type_drives_generic_validation_for_unknown_columns():
    columns = ["asset_tag", "quantity"]
    records = [
        {"source_row_number": row_number + 2, "payload": {"asset_tag": f"ASSET-{row_number:04d}", "quantity": str(row_number)}}
        for row_number in range(1, 10)
    ]
    records.append({"source_row_number": 11, "payload": {"asset_tag": "ASSET-0010", "quantity": "unknown"}})

    profile = profile_records(columns, records)
    result = validate_tabular_records(columns, records, profile=profile)

    assert profile["inferred_types"]["quantity"] == "integer"
    assert profile["column_profiles"][1]["inferred_type_confidence"] == 0.9
    assert len(result["accepted"]) == 9
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["reason_code"] == "type_mismatch"
    assert result["rejected"][0]["rejection_reasons"] == ["type_mismatch:quantity:expected_integer"]
    assert result["quality_summary"]["columns_checked"] >= 1
    assert result["quality_summary"]["type_mismatch_count"] == 1
    assert next(item for item in result["quality_summary"]["type_checks"] if item["field"] == "quantity")["mismatch_count"] == 1
    assert result["quality_summary"]["null_value_count"] == 0


def test_generic_row_uniqueness_emits_measured_result_with_row_only_examples():
    columns = ["event_id", "event_type"]
    records = [
        {"source_row_number": 2, "payload": {"event_id": "E-1", "event_type": "created"}},
        {"source_row_number": 3, "payload": {"event_id": "E-1", "event_type": "created"}},
        {"source_row_number": 4, "payload": {"event_id": "E-2", "event_type": "updated"}},
    ]

    result = validate_tabular_records(columns, records)

    uniqueness = next(
        item for item in result["validation_results"]
        if item["validation_id"] == "TABULAR:ROW_UNIQUENESS"
    )
    assert uniqueness["status"] == "FAIL"
    assert uniqueness["checked_rows"] == 3
    assert uniqueness["passed_rows"] == 2
    assert uniqueness["failed_rows"] == 1
    assert uniqueness["execution_time_ms"] > 0
    assert uniqueness["failure_examples"] == [{"source_row_number": 3}]
    assert "payload" not in uniqueness["failure_examples"][0]
    assert len(result["duplicates"]) == 1


def test_generic_parser_and_empty_row_checks_emit_persistable_results():
    columns = ["record_id", "status"]
    records = [
        {"source_row_number": 2, "payload": {"record_id": "R-1", "status": "ready"}, "parser_error": None},
        {"source_row_number": 3, "payload": {"record_id": "R-2", "status": "ready", "_parser_error": "malformed_row"}, "parser_error": "malformed_row"},
        {"source_row_number": 4, "payload": {"record_id": "", "status": None}, "parser_error": None},
    ]

    result = validate_tabular_records(columns, records)
    checks = {item["validation_id"]: item for item in result["validation_results"]}

    assert checks["TABULAR:ROW_FORMAT"]["status"] == "FAIL"
    assert checks["TABULAR:ROW_FORMAT"]["checked_rows"] == 3
    assert checks["TABULAR:ROW_FORMAT"]["failed_rows"] == 1
    assert checks["TABULAR:ROW_FORMAT"]["failure_examples"] == [{"source_row_number": 3}]
    assert checks["TABULAR:NONEMPTY_ROW"]["status"] == "FAIL"
    assert checks["TABULAR:NONEMPTY_ROW"]["checked_rows"] == 2
    assert checks["TABULAR:NONEMPTY_ROW"]["failed_rows"] == 1
    assert checks["TABULAR:NONEMPTY_ROW"]["failure_examples"] == [{"source_row_number": 4}]
    assert all("payload" not in example for check in checks.values() for example in check["failure_examples"])


def test_uncertain_or_empty_profiled_types_are_not_reported_as_passed():
    mixed_columns = ["value"]
    mixed_records = [
        {"source_row_number": 2, "payload": {"value": "alpha"}},
        {"source_row_number": 3, "payload": {"value": "not-an-integer"}},
    ]
    mixed_profile = profile_records(mixed_columns, mixed_records)
    mixed_result = validate_tabular_records(mixed_columns, mixed_records, profile=mixed_profile)
    mixed_check = next(
        item for item in mixed_result["validation_results"]
        if item["validation_id"] == "PROFILED_TYPE:value"
    )
    assert mixed_check["status"] == "NOT_APPLICABLE"
    assert mixed_check["applicability"]["status"] == "NOT_APPLICABLE"
    assert mixed_check["checked_rows"] == 0

    empty_records = [
        {"source_row_number": 2, "payload": {"quantity": None}},
        {"source_row_number": 3, "payload": {"quantity": ""}},
    ]
    empty_profile = {
        "inferred_types": {"quantity": "integer"},
        "column_profiles": [{"name": "quantity", "inferred_type_confidence": 0.9}],
    }
    empty_result = validate_tabular_records(["quantity"], empty_records, profile=empty_profile)
    empty_check = next(
        item for item in empty_result["validation_results"]
        if item["validation_id"] == "PROFILED_TYPE:quantity"
    )
    assert empty_check["status"] == "NOT_APPLICABLE"
    assert empty_check["checked_rows"] == 0


def test_general_pipeline_persists_inferred_type_rejections(client: TestClient):
    lines = ["asset_tag,quantity"]
    lines.extend(f"ASSET-{index:04d},{index}" for index in range(1, 10))
    lines.append("ASSET-0010,unknown")
    lines.append("ASSET-0011,")
    uploaded = client.post(
        "/api/v1/sources/upload",
        files={"file": ("warehouse.csv", ("\n".join(lines) + "\n").encode(), "text/csv")},
    )
    assert uploaded.status_code == 201, uploaded.text
    source = uploaded.json()
    assert source["profile"]["inferred_types"]["quantity"] == "integer"

    response = client.post(
        "/api/v1/runs",
        json={"source_file_id": source["source_file_id"], "pipeline_id": "general-tabular"},
    )

    assert response.status_code == 201, response.text
    run = response.json()
    assert run["counts"] == {"input": 11, "accepted": 10, "rejected": 1, "duplicates": 0, "published": 10}
    assert run["status"] == "PARTIAL"
    validation = next(stage for stage in run["stages"] if stage["stage_name"] == "validation")
    assert validation["details"]["quality_summary"]["type_mismatch_count"] == 1
    assert validation["details"]["quality_summary"]["null_value_count"] == 1
    rejected = client.get("/api/v1/quarantine", params={"run_id": run["run_id"]})
    assert rejected.status_code == 200
    assert rejected.json()["items"][0]["reason_code"] == "type_mismatch"
    assert rejected.json()["items"][0]["rejection_reasons"] == ["type_mismatch:quantity:expected_integer"]


def test_rule_registry_executes_only_approved_allowlisted_rules():
    rules = [
        RuleDefinition(
            rule_id="amount_floor",
            field="amount",
            rule_type="numeric_range",
            config={"minimum": 0},
            status="approved",
        ),
        RuleDefinition(
            rule_id="invoice_format",
            field="invoice",
            rule_type="regex",
            config={"pattern": r"^INV-\d{4}-\d{4}$"},
            status="draft",
        ),
    ]
    result = evaluate_rules(
        ["amount", "invoice"],
        [
            {"source_row_number": 2, "payload": {"amount": "10.00", "invoice": "bad"}},
            {"source_row_number": 3, "payload": {"amount": "-1.00", "invoice": "INV-2026-0003"}},
        ],
        rules,
    )
    assert len(result["accepted"]) == 1
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["rejection_reasons"] == ["rule_failed:amount_floor"]


def test_rule_type_registry_is_complete_and_rejects_duplicate_matchers():
    assert RULE_TYPE_REGISTRY.list() == [
        "conditional",
        "cross_field",
        "custom",
        "date_range",
        "domain",
        "email",
        "identifier",
        "numeric_range",
        "phone",
        "referential",
        "regex",
        "required",
        "type",
        "unique",
    ]
    with pytest.raises(ValueError, match="already registered"):
        RULE_TYPE_REGISTRY.register("required", lambda _rule, _payload, _seen: True)


def test_rule_registry_rejects_unsafe_or_unregistered_regex():
    with pytest.raises(ValidationError):
        RuleDefinition(
            rule_id="unsafe",
            field="value",
            rule_type="regex",
            config={"pattern": r"(a+)+$"},
        )
    with pytest.raises(ValidationError):
        RuleDefinition(
            rule_id="code",
            field="value",
            rule_type="custom",
            config={"operator": "python_eval", "value": "__import__('os')"},
        )


def test_approved_rule_with_missing_dependency_requires_configuration_instead_of_passing_or_crashing():
    rule = RuleDefinition(
        rule_id="amount_within_limit",
        field="amount",
        rule_type="cross_field",
        config={"other_field": "limit", "operator": "less_than_or_equal"},
        status="approved",
    )
    records = [{"source_row_number": 2, "payload": {"amount": "10"}}]

    result = evaluate_rules(["amount"], records, [rule])

    assert len(result["accepted"]) == 1
    assert result["accepted"][0]["payload"] == records[0]["payload"]
    assert result["rejected"] == []
    assert result["requires_configuration_count"] == 1
    assert result["executed_rule_ids"] == []
    check = result["validation_results"][0]
    assert check["validation_id"] == "RULE:amount_within_limit"
    assert check["status"] == "REQUIRES_CONFIGURATION"
    assert check["applicability"]["status"] == "REQUIRES_CONFIGURATION"
    assert check["applicability"]["required_configuration"] == ["column:limit"]
    assert check["checked_rows"] == 0


def test_transformations_are_ordered_and_keep_original_source_payload():
    records = [{"source_row_number": 2, "payload": {"customer": "  Alice   Smith  "}}]
    result = apply_transformations(
        ["customer"],
        records,
        [
            TransformationDefinition(
                transform_id="strip",
                operator="normalize_whitespace",
                field="customer",
                status="approved",
                order=1,
            ),
            TransformationDefinition(
                transform_id="case",
                operator="standardize_case",
                field="customer",
                config={"case": "lower"},
                status="approved",
                order=2,
            ),
        ],
    )
    assert result["records"][0]["payload"]["customer"] == "alice smith"
    assert result["records"][0]["original_payload"]["customer"] == "  Alice   Smith  "
    assert len(result["metrics"]) == 2


def test_excel_upload_is_profiled_and_runs_with_generic_schema(client: TestClient):
    client.app.state.settings.max_upload_bytes = 10_000
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["sku", "quantity", "received_at"])
    sheet.append(["P-001", 4, "2026-10-31"])
    sheet.append(["P-002", 9, "2026-11-01"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    uploaded = client.post(
        "/api/v1/sources/upload",
        files={"file": ("inventory.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert uploaded.status_code == 201, uploaded.text
    source = uploaded.json()
    assert source["columns"] == ["sku", "quantity", "received_at"]
    assert source["profile"]["row_count"] == 2
    assert source["profile"]["inferred_types"]["quantity"] == "integer"
    run = client.post(
        "/api/v1/runs",
        json={"source_file_id": source["source_file_id"], "pipeline_id": "general-tabular"},
    )
    assert run.status_code == 201, run.text
    assert run.json()["counts"]["published"] == 2


def test_schema_mapping_rule_transform_plan_and_run_are_versioned_and_reusable(client: TestClient):
    uploaded = client.post(
        "/api/v1/sources/upload",
        files={
            "file": (
                "invoices.csv",
                b"client_reference,txn_dt,total_value,currency_code,invoice_number\n"
                b"C-001,2026-10-30,24.50,usd,INV-2026-0001\n"
                b"C-002,2026-10-31,-1.00,eur,INV-2026-0002\n",
                "text/csv",
            )
        },
    )
    assert uploaded.status_code == 201, uploaded.text
    source = uploaded.json()
    source_id = source["source_file_id"]
    fingerprint = source["schema_fingerprint"]

    profile = client.get(f"/api/v1/engine/sources/{source_id}/profile").json()["profile"]
    assert profile["row_count"] == 2
    assert profile["column_profiles"][2]["numeric"]["min"] == "-1.00"

    suggestions = client.post(f"/api/v1/engine/sources/{source_id}/suggestions")
    assert suggestions.status_code == 200, suggestions.text
    assert suggestions.json()["analysis"]["mode"] == "local"
    suggested_mappings = suggestions.json()["analysis"]["mapping_suggestions"]
    assert {item["source_column"] for item in suggested_mappings} >= {
        "client_reference", "txn_dt", "total_value", "currency_code"
    }
    schema_profile_id = suggestions.json()["schema_profile_id"]
    approval = client.post(
        f"/api/v1/engine/schema-profiles/{schema_profile_id}/approve",
        json={
            "mappings": [
                {"source_column": "client_reference", "semantic_field": "customer_id", "action": "approve"},
                {"source_column": "txn_dt", "semantic_field": "transaction_date", "action": "approve"},
                {"source_column": "total_value", "semantic_field": "amount", "action": "approve"},
                {"source_column": "currency_code", "semantic_field": "currency", "action": "approve"},
            ]
        },
    )
    assert approval.status_code == 200, approval.text
    assert approval.json()["status"] == "approved"

    rule = client.post(
        "/api/v1/engine/rules",
        json={
            "schema_fingerprint": fingerprint,
            "status": "approved",
            "definition": {"field": "amount", "rule_type": "numeric_range", "config": {"minimum": 0.01}},
        },
    )
    assert rule.status_code == 200, rule.text
    assert rule.json()["status"] == "approved"
    transformation = client.post(
        "/api/v1/engine/transformations",
        json={
            "schema_fingerprint": fingerprint,
            "status": "approved",
            "definition": {
                "field": "currency",
                "operator": "standardize_case",
                "config": {"case": "upper"},
            },
        },
    )
    assert transformation.status_code == 200, transformation.text

    plan = client.post(
        "/api/v1/engine/plans",
        json={"source_file_id": source_id, "dry_run": True},
    )
    assert plan.status_code == 200, plan.text
    assert plan.json()["dry_run"]["counts"] == {
        "input": 2,
        "accepted": 1,
        "rejected": 1,
        "duplicates": 0,
        "published": 0,
    }

    run = client.post(
        "/api/v1/runs",
        json={"source_file_id": source_id, "pipeline_id": "general-tabular"},
    )
    assert run.status_code == 201, run.text
    result = run.json()
    assert result["status"] == "PARTIAL"
    assert result["counts"]["accepted"] == 1
    assert result["counts"]["rejected"] == 1
    assert result["profile"]["processing_plan_id"]
    validation_run = client.get(f"/api/v1/validation/runs/{result['run_id']}")
    assert validation_run.status_code == 200, validation_run.text
    validation_data = validation_run.json()
    history = client.get(
        "/api/v1/validation/history",
        params={
            "validation_id": f"RULE:{rule.json()['rule_id']}",
            "pipeline_id": "general-tabular",
            "source_file_id": source_id,
            "status": "FAIL",
        },
    )
    assert history.status_code == 200, history.text
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["run_id"] == result["run_id"]
    assert history.json()["items"][0]["original_filename"] == "invoices.csv"
    assert history.json()["items"][0]["attempt_number"] == 1
    quality_score = client.get(f"/api/v1/quality/runs/{result['run_id']}/score")
    assert quality_score.status_code == 200, quality_score.text
    assert quality_score.json()["score_status"] == "AVAILABLE"
    assert quality_score.json()["score_scope"] == "Persisted applicable runtime checks for the selected attempt."
    assert quality_score.json()["catalog_total"] == 0
    assert quality_score.json()["catalog_coverage_percent"] is None
    assert "severity_weighted_failure_rate" in quality_score.json()["methodology"]["formula"]
    baseline_response = client.post(
        "/api/v1/quality/baselines",
        json={"run_id": result["run_id"], "dataset_identity": "invoices:monthly"},
    )
    assert baseline_response.status_code == 201, baseline_response.text
    baseline = baseline_response.json()
    assert baseline["baseline_version"] == 1
    assert baseline["dataset_identity"] == "invoices:monthly"
    next_baseline = client.post(
        "/api/v1/quality/baselines",
        json={"run_id": result["run_id"], "dataset_identity": "invoices:monthly"},
    )
    assert next_baseline.status_code == 201, next_baseline.text
    assert next_baseline.json()["baseline_version"] == 2
    baseline_list = client.get(
        "/api/v1/quality/baselines",
        params={"dataset_identity": "invoices:monthly", "pipeline_id": "general-tabular"},
    )
    assert baseline_list.status_code == 200, baseline_list.text
    assert baseline_list.json()["total"] == 2
    baseline_comparison = client.get(
        f"/api/v1/quality/baselines/{baseline['baseline_id']}/compare",
        params={"run_id": result["run_id"]},
    )
    assert baseline_comparison.status_code == 200, baseline_comparison.text
    comparison_data = baseline_comparison.json()
    assert comparison_data["confirmed_invalid_records"] is False
    assert comparison_data["schema_drift"]["changed"] is False
    numeric_assessment = next(
        item for item in comparison_data["numeric_distribution_drift"]
        if item["column"] == "total_value"
    )
    assert numeric_assessment["status"] == "INSUFFICIENT_SAMPLE"
    assert "INV-2026-0001" not in baseline_comparison.text
    analytics = client.get(
        "/api/v1/validation/analytics",
        params={"days": 30, "pipeline_id": "general-tabular"},
    )
    assert analytics.status_code == 200, analytics.text
    assert analytics.json()["total_results"] >= validation_data["total"]
    assert analytics.json()["requires_configuration"] == 0
    assert analytics.json()["most_failing_checks"][0]["validation_id"] == f"RULE:{rule.json()['rule_id']}"
    assert any(point["run_id"] == result["run_id"] for point in analytics.json()["quality_trend"])
    assert validation_data["summary"]["executed"] >= 2
    uniqueness = next(
        item for item in validation_data["items"]
        if item["validation_id"] == "TABULAR:ROW_UNIQUENESS"
    )
    assert uniqueness["status"] == "PASS"
    assert uniqueness["checked_rows"] == 2
    reconciliation = {
        item["validation_id"]: item
        for item in validation_data["items"]
        if item["validation_id"].startswith("RECONCILIATION:")
    }
    assert reconciliation["RECONCILIATION:INPUT_DISPOSITIONS"]["status"] == "PASS"
    assert reconciliation["RECONCILIATION:PUBLISHED_COUNT"]["status"] == "PASS"
    rule_result = next(
        item for item in validation_data["items"]
        if item["validation_id"] == f"RULE:{rule.json()['rule_id']}"
    )
    assert rule_result["status"] == "FAIL"
    assert rule_result["checked_rows"] == 2
    assert rule_result["failed_rows"] == 1
    assert rule_result["configuration_snapshot"]["config"]["minimum"] == 0.01
    assert rule_result["failure_examples"] == [{"source_row_number": 3}]
    assert validation_run.json()["summary"]["checked_rows"] >= 2
    output = client.app.state.settings.output_dir / result["run_id"] / "records.csv"
    assert output.exists()
    assert "customer_id" in output.read_text(encoding="utf-8-sig").splitlines()[0]
    assert client.get(f"/api/v1/engine/rules?schema_fingerprint={fingerprint}").json()["total"] == 1
    assert client.get(f"/api/v1/engine/transformations?schema_fingerprint={fingerprint}").json()["total"] == 1


def test_validation_catalog_reports_missing_reference_documents_without_fabricating_entries(client: TestClient):
    response = client.get("/api/v1/validation/catalog")
    assert response.status_code == 200, response.text
    catalog = response.json()
    assert catalog["source_status"] == "SOURCE_MISSING"
    assert catalog["total"] == 0
    assert catalog["items"] == []
    assert "No catalog names" in catalog["message"]

    exported = client.get("/api/v1/validation/catalog/export/download", params={"format": "json"})
    assert exported.status_code == 200
    assert exported.headers["x-datatrace-catalog-status"] == "SOURCE_MISSING"
    assert exported.json()["total"] == 0
    assert exported.json()["items"] == []
    csv_export = client.get("/api/v1/validation/catalog/export/download", params={"format": "csv"})
    assert csv_export.status_code == 200
    assert "VAL-001" not in csv_export.text


def test_validation_catalog_filters_and_paginates_imported_definitions(client: TestClient):
    definitions = [
        ValidationDefinition(
            validation_id="VAL-001", catalog_number=1, name="Invoice amount check", description="Checks invoice amounts.",
            category="Finance", severity="ERROR", applicability_requirements=["amount column"], required_columns=["amount"],
            required_metadata=[], configuration_requirements=[], implementation_status="FULLY_IMPLEMENTED",
            implementation_version="1.0", test_status="TESTED", limitations=[], enabled=True,
            supported_file_types=["csv", "json"], applicability_support="TRANSACTION", definition_source="test fixture",
        ),
        ValidationDefinition(
            validation_id="VAL-002", catalog_number=2, name="Workbook reference check", description="Checks workbook references.",
            category="Reference", severity="WARNING", applicability_requirements=[], required_columns=[],
            required_metadata=[], configuration_requirements=[], implementation_status="CATALOG_ONLY",
            implementation_version="1.0", test_status="NOT_TESTED", limitations=[], enabled=False,
            supported_file_types=["xlsx"], applicability_support="FILE", definition_source="test fixture",
        ),
        ValidationDefinition(
            validation_id="VAL-003", catalog_number=3, name="Payment amount profile", description="Profiles payment amounts.",
            category="Finance", severity="INFO", applicability_requirements=[], required_columns=["amount"],
            required_metadata=[], configuration_requirements=[], implementation_status="FULLY_IMPLEMENTED",
            implementation_version="1.0", test_status="TESTED", limitations=[], enabled=True,
            supported_file_types=["CSV"], applicability_support="TRANSACTION", definition_source="test fixture",
        ),
    ]
    with client.app.state.session_factory() as session:
        session.add_all(definitions)
        session.commit()

    filtered = client.get(
        "/api/v1/validation/catalog",
        params={
            "validation_id": "val-001", "name": "invoice", "category": "finance", "severity": "error",
            "implementation_status": "FULLY_IMPLEMENTED", "enabled": "true", "applicability": "transaction",
            "supported_file_type": ".CSV",
        },
    )
    assert filtered.status_code == 200, filtered.text
    result = filtered.json()
    assert result["total"] == 1
    assert [item["validation_id"] for item in result["items"]] == ["VAL-001"]
    assert result["counts"]["FULLY_IMPLEMENTED"] == 2
    assert result["counts"]["enabled"] == 2
    assert result["filter_options"] == {
        "categories": ["Finance", "Reference"],
        "severities": ["ERROR", "INFO", "WARNING"],
        "applicabilities": ["FILE", "TRANSACTION"],
        "supported_file_types": ["csv", "json", "xlsx"],
    }

    second_page = client.get("/api/v1/validation/catalog", params={"supported_file_type": "csv", "page": 2, "page_size": 1})
    assert second_page.status_code == 200, second_page.text
    assert second_page.json()["total"] == 2
    assert [item["validation_id"] for item in second_page.json()["items"]] == ["VAL-003"]

    exported = client.get("/api/v1/validation/catalog/export/download", params={"format": "json"})
    assert exported.status_code == 200, exported.text
    assert exported.json()["source_status"] == "PARTIAL"
    assert exported.json()["total"] == 3
    assert [item["validation_id"] for item in exported.json()["items"]] == ["VAL-001", "VAL-002", "VAL-003"]


def test_ai_budget_cache_exhaustion_and_manual_reset_are_recorded(client: TestClient, monkeypatch):
    app = client.app
    settings = app.state.settings.model_copy(
        update={"ai_provider": "openrouter", "openrouter_api_key": SecretStr("unit-test-key")}
    )
    profile = {
        "columns": ["sku"],
        "row_count": 2,
        "inferred_types": {"sku": "string"},
        "null_counts": {"sku": 0},
        "distinct_counts": {"sku": 2},
        "value_shapes": {"sku": {"string": 2}},
    }
    calls = []

    def fake_inference(_profile, _settings):
        calls.append(1)
        return (
            {
                "mode": "llm",
                "provider": "openrouter",
                "model": "test/model",
                "dataset_kind": "inventory",
                "summary": "Inventory rows.",
                "columns": [],
                "candidate_key_columns": [],
                "quality_notes": [],
                "mapping_suggestions": [],
                "rule_suggestions": [],
                "transformation_suggestions": [],
                "input_sent": "profile metadata",
            },
            {
                "status": "success",
                "provider": "openrouter",
                "model": "test/model",
                "prompt_tokens": 100,
                "completion_tokens": 80,
                "reported_cost_usd": None,
                "latency_ms": 25,
            },
        )

    monkeypatch.setattr("app.services.ai_service.provider.infer_schema_with_usage", fake_inference)
    with app.state.session_factory() as session:
        first = infer_schema_with_tracking(session, profile, settings)
        cached = infer_schema_with_tracking(session, profile, settings)
        assert first["usage"]["status"] == "success"
        assert cached["usage"]["status"] == "cache_hit"
        assert cached["usage"]["estimated_cost_usd"] == "0.000000000"
        assert len(calls) == 1
        budget = session.get(AIBudget, 1)
        assert budget.used_usd > 0
        assert budget.reserved_usd == 0
        assert session.query(AICache).count() == 1
        assert session.query(AIUsage).count() == 2

        budget.used_usd = budget.limit_usd
        session.commit()
        monkeypatch.undo()
        exhausted = infer_schema_with_tracking(session, {**profile, "row_count": 3}, settings)
        assert exhausted["usage"]["status"] == "budget_exhausted"
        assert exhausted["mode"] == "local"
        assert len(calls) == 1

    reset = client.post("/api/v1/ai/budget/reset", json={"confirmation": "RESET_AI_BUDGET"})
    assert reset.status_code == 200, reset.text
    assert reset.json()["used_usd"] == "0.000000000"
    assert reset.json()["reset_count"] == 1
    usage = client.get("/api/v1/ai/usage").json()
    assert {item["status"] for item in usage["items"]} >= {"success", "cache_hit", "budget_exhausted"}
    assert "api_key" not in client.get("/api/v1/ai/status").text


def test_billed_invalid_provider_response_still_debits_local_budget(client: TestClient, monkeypatch):
    app = client.app
    settings = app.state.settings.model_copy(
        update={"ai_provider": "openrouter", "openrouter_api_key": SecretStr("unit-test-key")}
    )

    def invalid_but_billed(_profile, _settings):
        return (
            {"mode": "local", "provider": "openrouter", "model": "test/model"},
            {
                "status": "invalid_provider_response",
                "provider": "openrouter",
                "model": "test/model",
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "reported_cost_usd": "0.000050000",
                "latency_ms": 12,
            },
        )

    monkeypatch.setattr("app.services.ai_service.provider.infer_schema_with_usage", invalid_but_billed)
    with app.state.session_factory() as session:
        result = infer_schema_with_tracking(
            session,
            {"columns": ["opaque_field"], "row_count": 2, "inferred_types": {"opaque_field": "string"}},
            settings,
        )
        budget = session.get(AIBudget, 1)
        assert result["usage"]["status"] == "invalid_provider_response"
        assert budget.used_usd == Decimal("0.000050000")
        assert budget.reserved_usd == 0
