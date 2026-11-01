import csv
from concurrent.futures import ThreadPoolExecutor

import app.services.execution_service as execution_service_module
from fastapi.testclient import TestClient
from pydantic import SecretStr


def upload_csv(client: TestClient, content: bytes) -> dict:
    response = client.post(
        "/api/v1/sources/upload",
        files={"file": ("transactions.csv", content, "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_run(client: TestClient, source_file_id: str) -> dict:
    response = client.post("/api/v1/runs", json={"source_file_id": source_file_id})
    assert response.status_code == 201, response.text
    return response.json()


def test_upload_run_rejections_and_reconciliation_are_persisted(client, transaction_csv_bytes):
    source = upload_csv(client, transaction_csv_bytes)
    assert source["checksum"]
    assert source["columns"] == [
        "transaction_id",
        "source_system",
        "customer_id",
        "merchant_id",
        "amount",
        "currency",
        "transaction_status",
        "event_time",
    ]
    run = create_run(client, source["source_file_id"])
    assert run["status"] == "PARTIAL"
    assert run["counts"] == {
        "input": 4,
        "accepted": 2,
        "rejected": 1,
        "duplicates": 1,
        "published": 2,
    }
    assert len(run["stages"]) >= 5

    detail = client.get(f"/api/v1/runs/{run['run_id']}").json()
    assert detail["run_id"] == run["run_id"]
    assert detail["status"] == "PARTIAL"
    rejected = client.get("/api/v1/quarantine", params={"run_id": run["run_id"]}).json()
    assert rejected["total"] == 1
    assert rejected["items"][0]["source_row_number"] == 4
    assert rejected["items"][0]["reason_code"] == "amount_not_positive"
    duplicates = client.get("/api/v1/duplicates", params={"run_id": run["run_id"]}).json()
    assert duplicates["total"] == 1
    assert duplicates["items"][0]["source_row_number"] == 3
    assert duplicates["items"][0]["duplicate_of_row_number"] == 2
    reconciliation = client.get(f"/api/v1/reconciliation/{run['run_id']}").json()
    assert reconciliation["balanced"] is True
    assert reconciliation["counts"] == run["counts"]
    assert reconciliation["accepted_amounts_by_currency"] == {"USD": "10.25", "INR": "3.50"}
    assert (
        reconciliation["published_amounts_by_currency"]
        == reconciliation["accepted_amounts_by_currency"]
    )
    audit = client.get("/api/v1/audit", params={"run_id": run["run_id"]}).json()
    assert {event["event_type"] for event in audit["items"]} >= {"run.created", "run.completed"}


def test_pre_publish_reconciliation_failure_is_saved_without_claiming_publication(client, monkeypatch):
    source = upload_csv(client, b"event_id,value\nE-1,one\n")
    monkeypatch.setattr(execution_service_module, "_count_output_rows", lambda _path: 2)

    response = client.post(
        "/api/v1/runs",
        json={"source_file_id": source["source_file_id"], "pipeline_id": "general-tabular"},
    )

    assert response.status_code == 201, response.text
    run = response.json()
    assert run["status"] == "FAILED"
    assert run["counts"]["published"] == 0
    reconciliation_stage = next(
        stage for stage in run["stages"] if stage["stage_name"] == "reconciliation"
    )
    assert reconciliation_stage["status"] == "FAILED"
    assert reconciliation_stage["details"]["phase"] == "pre_publish_preflight"

    results = client.get(f"/api/v1/validation/runs/{run['run_id']}")
    assert results.status_code == 200, results.text
    by_id = {item["validation_id"]: item for item in results.json()["items"]}
    assert by_id["RECONCILIATION:INPUT_DISPOSITIONS"]["status"] == "PASS"
    assert by_id["RECONCILIATION:PUBLISHED_COUNT"]["status"] == "FAIL"
    assert not (client.app.state.settings.output_dir / run["run_id"] / "records.csv").exists()


def test_general_tabular_pipeline_accepts_arbitrary_columns_and_publishes_with_lineage(client):
    content = (
        b"event_id,email_address,created_at,metric\n"
        b"E-1,one@example.test,2026-10-30T12:00:00Z,7.5\n"
        b"E-2,two@example.test,2026-10-30T12:01:00Z,8.0\n"
        b"E-2,two@example.test,2026-10-30T12:01:00Z,8.0\n"
        b",,,\n"
    )
    source = upload_csv(client, content)
    response = client.post(
        "/api/v1/runs",
        json={"source_file_id": source["source_file_id"], "pipeline_id": "general-tabular"},
    )
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["status"] == "PARTIAL"
    assert run["counts"] == {
        "input": 4,
        "accepted": 2,
        "rejected": 1,
        "duplicates": 1,
        "published": 2,
    }
    assert run["error"] is None
    assert "schema_analysis" not in run["profile"]
    validation = next(stage for stage in run["stages"] if stage["stage_name"] == "validation")
    assert validation["details"]["schema_compatibility"] == "DYNAMIC"

    output_path = client.app.state.settings.output_dir / run["run_id"] / "records.csv"
    with output_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2
    assert rows[0]["event_id"] == "E-1"
    assert rows[0]["_datatrace_source_file_id"] == source["source_file_id"]
    assert rows[0]["_datatrace_source_row_number"] == "2"
    assert rows[0]["_datatrace_record_id"]

    quarantine = client.get("/api/v1/quarantine", params={"run_id": run["run_id"]}).json()
    duplicates = client.get("/api/v1/duplicates", params={"run_id": run["run_id"]}).json()
    reconciliation = client.get(f"/api/v1/reconciliation/{run['run_id']}").json()
    assert quarantine["total"] == 1
    assert quarantine["items"][0]["reason_code"] == "empty_row"
    assert duplicates["total"] == 1
    assert reconciliation["balanced"] is True
    assert set(reconciliation["checks"]) == {
        "input_equals_dispositions",
        "accepted_equals_published",
    }


def test_json_source_upload_runs_through_general_tabular_pipeline(client):
    response = client.post(
        "/api/v1/sources/upload",
        files={
            "file": (
                "contacts.json",
                b'[{"contact":{"id":1,"email":"one@example.test"}},{"contact":{"id":2,"email":"two@example.test"}}]',
                "application/json",
            )
        },
    )
    assert response.status_code == 201, response.text
    source = response.json()
    assert source["columns"] == ["contact.id", "contact.email"]
    run = client.post(
        "/api/v1/runs",
        json={"source_file_id": source["source_file_id"], "pipeline_id": "general-tabular"},
    ).json()
    assert run["status"] == "SUCCESS"
    assert run["counts"] == {
        "input": 2,
        "accepted": 2,
        "rejected": 0,
        "duplicates": 0,
        "published": 2,
    }
    assert (client.app.state.settings.output_dir / run["run_id"] / "records.csv").exists()


def test_general_run_never_calls_model_and_idempotency_ignores_provider(client, monkeypatch):
    source = upload_csv(client, b"sku,quantity\nA-1,3\n")
    first = client.post(
        "/api/v1/runs",
        json={"source_file_id": source["source_file_id"], "pipeline_id": "general-tabular"},
    ).json()
    assert "schema_analysis" not in first["profile"]

    settings = client.app.state.settings
    settings.openrouter_api_key = SecretStr("test-key")
    settings.ai_provider = "auto"
    monkeypatch.setattr(
        "app.services.ai_service.provider.infer_schema_with_usage",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("ordinary pipeline run called the model")),
    )
    second = client.post(
        "/api/v1/runs",
        json={"source_file_id": source["source_file_id"], "pipeline_id": "general-tabular"},
    ).json()
    assert second["run_id"] == first["run_id"]
    assert "schema_analysis" not in second["profile"]

    repeated = client.post(
        "/api/v1/runs",
        json={"source_file_id": source["source_file_id"], "pipeline_id": "general-tabular"},
    ).json()
    assert repeated["run_id"] == second["run_id"]


def test_identical_content_reuses_source_run_and_artifact(client, transaction_csv_bytes):
    first_source = upload_csv(client, transaction_csv_bytes)
    first_run = create_run(client, first_source["source_file_id"])
    second_source = upload_csv(client, transaction_csv_bytes)
    second_run = create_run(client, second_source["source_file_id"])
    assert second_source["source_file_id"] == first_source["source_file_id"]
    assert second_run["run_id"] == first_run["run_id"]
    assert second_run["counts"] == first_run["counts"]


def test_concurrent_identical_run_requests_return_the_same_persisted_run(
    client, transaction_csv_bytes
):
    source = upload_csv(client, transaction_csv_bytes)
    payload = {"source_file_id": source["source_file_id"]}

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(lambda _: client.post("/api/v1/runs", json=payload), range(2))
        )

    assert [response.status_code for response in responses] == [201, 201]
    assert responses[0].json()["run_id"] == responses[1].json()["run_id"]


def test_upload_rejects_malformed_or_wrong_type_csv(client):
    malformed = client.post(
        "/api/v1/sources/upload",
        files={"file": ("bad.csv", b'"unterminated', "text/csv")},
    )
    assert malformed.status_code == 422
    wrong_type = client.post(
        "/api/v1/sources/upload",
        files={"file": ("data.txt", b"a,b\n1,2\n", "text/plain")},
    )
    assert wrong_type.status_code == 415
    invalid_json = client.post(
        "/api/v1/sources/upload",
        files={"file": ("bad.json", b"{invalid", "application/json")},
    )
    assert invalid_json.status_code == 422
    assert invalid_json.json()["error"]["code"] == "invalid_json"


def test_api_health_and_error_contract(client):
    health_response = client.get("/health", headers={"X-Request-ID": "request-test-123"})
    assert health_response.json() == {"status": "ok"}
    assert health_response.headers["X-Request-ID"] == "request-test-123"

    version_response = client.get("/api/v1/version")
    assert version_response.json() == {
        "name": client.app.title,
        "version": client.app.version,
    }

    response = client.get("/api/v1/runs/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "run_not_found"
    assert "traceback" not in response.text.lower()


def test_empty_header_only_input_publishes_an_empty_artifact(client):
    empty_csv = b"transaction_id,source_system,customer_id,merchant_id,amount,currency,transaction_status,event_time\n"
    source = upload_csv(client, empty_csv)
    run = create_run(client, source["source_file_id"])
    assert run["status"] == "SUCCESS"
    assert run["counts"] == {
        "input": 0,
        "accepted": 0,
        "rejected": 0,
        "duplicates": 0,
        "published": 0,
    }
    assert client.app.state.settings.output_dir.joinpath(run["run_id"], "transactions.csv").exists()


def test_missing_required_columns_block_publication_but_keep_row_evidence(client):
    source = upload_csv(client, b"transaction_id,amount\nTX-1,2.00\n")
    run = create_run(client, source["source_file_id"])
    assert run["status"] == "FAILED"
    assert run["profile"]["row_count"] == 1
    assert run["counts"] == {
        "input": 1,
        "accepted": 0,
        "rejected": 1,
        "duplicates": 0,
        "published": 0,
    }
    assert not client.app.state.settings.output_dir.joinpath(
        run["run_id"], "transactions.csv"
    ).exists()
    rejected = client.get("/api/v1/quarantine", params={"run_id": run["run_id"]}).json()
    assert rejected["items"][0]["reason_code"] == "missing_required_columns"
    reconciliation = client.get(f"/api/v1/reconciliation/{run['run_id']}")
    assert reconciliation.status_code == 200
    assert reconciliation.json()["counts"] == run["counts"]


def test_upload_size_limit_is_enforced(client):
    response = client.post(
        "/api/v1/sources/upload",
        files={"file": ("large.csv", b"id\n" + b"a" * 1100, "text/csv")},
    )
    assert response.status_code == 413


def test_runtime_failure_can_be_retried_without_losing_prior_attempt_evidence(
    client, transaction_csv_bytes
):
    source = upload_csv(client, transaction_csv_bytes)
    original_master_path = client.app.state.settings.customer_master_path
    client.app.state.settings.customer_master_path = original_master_path.with_name(
        "missing-customer-master.csv"
    )
    failed = create_run(client, source["source_file_id"])
    assert failed["status"] == "FAILED"
    first_attempt_stages = {
        stage["stage_name"]: stage["status"]
        for stage in failed["stages"]
        if stage["attempt_id"].endswith("_attempt_1")
    }
    assert first_attempt_stages == {
        "ingestion": "SUCCESS",
        "profiling": "SUCCESS",
        "validation": "FAILED",
    }
    client.app.state.settings.customer_master_path = original_master_path

    retried = client.post(f"/api/v1/runs/{failed['run_id']}/retry")
    assert retried.status_code == 200, retried.text
    assert retried.json()["run_id"] == failed["run_id"]
    assert retried.json()["status"] == "PARTIAL"
    stage_attempts = {stage["attempt_id"] for stage in retried.json()["stages"]}
    assert stage_attempts == {f"{failed['run_id']}_attempt_1", f"{failed['run_id']}_attempt_2"}
    audit = client.get("/api/v1/audit", params={"run_id": failed["run_id"]}).json()
    assert "run.retry_started" in {event["event_type"] for event in audit["items"]}


def test_retry_preserves_disposition_evidence_by_attempt(
    client, transaction_csv_bytes, monkeypatch
):
    from app.services import execution_service

    original_transform = execution_service.transform_records

    def fail_transform(*_args, **_kwargs):
        raise RuntimeError("test transform failure")

    monkeypatch.setattr(execution_service, "transform_records", fail_transform)
    source = upload_csv(client, transaction_csv_bytes)
    failed = create_run(client, source["source_file_id"])
    assert failed["status"] == "FAILED"
    assert {stage["stage_name"] for stage in failed["stages"]} >= {
        "ingestion",
        "profiling",
        "validation",
        "transformation",
    }
    assert (
        client.get("/api/v1/quarantine", params={"run_id": failed["run_id"]}).json()["total"] == 1
    )

    monkeypatch.setattr(execution_service, "transform_records", original_transform)
    retried = client.post(f"/api/v1/runs/{failed['run_id']}/retry")
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "PARTIAL"
    assert retried.json()["counts"]["rejected"] == 1
    attempt_ids = [f"{failed['run_id']}_attempt_{attempt}" for attempt in (1, 2)]

    for attempt_id in attempt_ids:
        rejected = client.get(
            "/api/v1/quarantine",
            params={"run_id": failed["run_id"], "attempt_id": attempt_id},
        ).json()
        duplicates = client.get(
            "/api/v1/duplicates",
            params={"run_id": failed["run_id"], "attempt_id": attempt_id},
        ).json()
        assert rejected["total"] == 1
        assert rejected["items"][0]["attempt_id"] == attempt_id
        assert duplicates["total"] == 1
        assert duplicates["items"][0]["attempt_id"] == attempt_id

    latest_rejected = client.get("/api/v1/quarantine", params={"run_id": failed["run_id"]}).json()
    latest_duplicates = client.get("/api/v1/duplicates", params={"run_id": failed["run_id"]}).json()
    assert latest_rejected["total"] == latest_duplicates["total"] == 1
    assert latest_rejected["items"][0]["attempt_id"] == attempt_ids[-1]
    assert latest_duplicates["items"][0]["attempt_id"] == attempt_ids[-1]


def test_finance_run_persists_actual_check_results_and_row_only_examples(client, transaction_csv_bytes):
    source = upload_csv(client, transaction_csv_bytes)
    run = create_run(client, source["source_file_id"])

    response = client.get(f"/api/v1/validation/runs/{run['run_id']}")
    assert response.status_code == 200, response.text
    payload = response.json()
    by_id = {item["validation_id"]: item for item in payload["items"]}
    assert payload["summary"]["executed"] >= 15
    assert by_id["FINANCE:POSITIVE_AMOUNT"]["status"] == "FAIL"
    assert by_id["FINANCE:POSITIVE_AMOUNT"]["checked_rows"] == 4
    assert by_id["FINANCE:POSITIVE_AMOUNT"]["failed_rows"] == 1
    assert by_id["FINANCE:POSITIVE_AMOUNT"]["failure_examples"] == [{"source_row_number": 4}]
    assert by_id["FINANCE:TRANSACTION_UNIQUENESS"]["failed_rows"] == 1
    assert by_id["FINANCE:TRANSACTION_UNIQUENESS"]["failure_examples"] == [{"source_row_number": 3}]
    assert by_id["FINANCE:EVENT_ORDER"]["status"] == "PASS"
    assert all(
        item["execution_time_ms"] > 0
        for item in payload["items"]
        if item["checked_rows"]
    )
    assert all("payload" not in example for item in payload["items"] for example in item["failure_examples"])


