from datetime import UTC, datetime

import pytest
from app.models import (
    DuplicateRecord,
    Pipeline,
    PipelineRun,
    PipelineVersion,
    RejectedRecord,
    RunAttempt,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


def test_rejected_row_cannot_point_to_a_different_source_than_its_run(
    client, transaction_csv_bytes
):
    source_a = client.post(
        "/api/v1/sources/upload", files={"file": ("a.csv", transaction_csv_bytes, "text/csv")}
    ).json()
    source_b = client.post(
        "/api/v1/sources/upload",
        files={"file": ("b.csv", transaction_csv_bytes + b"\n", "text/csv")},
    ).json()
    run = client.post("/api/v1/runs", json={"source_file_id": source_a["source_file_id"]}).json()
    with client.app.state.session_factory() as session:
        session.add(
            RejectedRecord(
                run_id=run["run_id"],
                attempt_id=run["stages"][0]["attempt_id"],
                source_file_id=source_b["source_file_id"],
                source_row_number=99,
                original_payload={"transaction_id": "MISMATCH"},
                reason_code="test",
                rejection_reasons=["test"],
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_disposition_rows_must_reference_an_attempt_from_their_run(client, transaction_csv_bytes):
    first_source = client.post(
        "/api/v1/sources/upload", files={"file": ("first.csv", transaction_csv_bytes, "text/csv")}
    ).json()
    second_source = client.post(
        "/api/v1/sources/upload",
        files={"file": ("second.csv", transaction_csv_bytes + b"\n", "text/csv")},
    ).json()
    first_run = client.post(
        "/api/v1/runs", json={"source_file_id": first_source["source_file_id"]}
    ).json()
    second_run = client.post(
        "/api/v1/runs", json={"source_file_id": second_source["source_file_id"]}
    ).json()

    with client.app.state.session_factory() as session:
        session.add(
            RejectedRecord(
                run_id=first_run["run_id"],
                attempt_id=second_run["stages"][0]["attempt_id"],
                source_file_id=first_source["source_file_id"],
                source_row_number=99,
                original_payload={"transaction_id": "MISMATCH"},
                reason_code="test",
                rejection_reasons=["test"],
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()
        session.add(
            DuplicateRecord(
                run_id=first_run["run_id"],
                attempt_id=second_run["stages"][0]["attempt_id"],
                source_row_number=99,
                duplicate_of_row_number=2,
                duplicate_key="test-key",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_run_cannot_reference_a_pipeline_version_from_another_pipeline(
    client, transaction_csv_bytes
):
    source = client.post(
        "/api/v1/sources/upload", files={"file": ("input.csv", transaction_csv_bytes, "text/csv")}
    ).json()
    with client.app.state.session_factory() as session:
        session.add(Pipeline(pipeline_id="other-pipeline", name="Other", version=1))
        session.commit()
        session.add(
            PipelineVersion(
                pipeline_version_id="other-pipeline:v1",
                pipeline_id="other-pipeline",
                version=1,
                configuration={},
            )
        )
        session.commit()
        session.add(
            PipelineRun(
                run_id="run_mismatched_version",
                idempotency_key="a" * 64,
                pipeline_id="other-pipeline",
                pipeline_version_id="financial-transactions:v1",
                source_file_id=source["source_file_id"],
                status="PENDING",
                counts={},
                profile={},
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_pipeline_version_must_be_positive(client):
    with client.app.state.session_factory() as session:
        session.add(
            PipelineVersion(
                pipeline_version_id="financial-transactions:v0",
                pipeline_id="financial-transactions",
                version=0,
                configuration={},
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_run_attempt_number_must_be_positive(client, transaction_csv_bytes):
    source = client.post(
        "/api/v1/sources/upload", files={"file": ("input.csv", transaction_csv_bytes, "text/csv")}
    ).json()
    run = client.post("/api/v1/runs", json={"source_file_id": source["source_file_id"]}).json()
    with client.app.state.session_factory() as session:
        session.add(
            RunAttempt(
                attempt_id=f"{run['run_id']}_attempt_0",
                run_id=run["run_id"],
                attempt_number=0,
                status="FAILED",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_sqlite_timestamps_round_trip_as_utc_aware_values(client, transaction_csv_bytes):
    source = client.post(
        "/api/v1/sources/upload", files={"file": ("input.csv", transaction_csv_bytes, "text/csv")}
    ).json()
    response = client.post("/api/v1/runs", json={"source_file_id": source["source_file_id"]})
    assert response.status_code == 201, response.text
    api_created_at = datetime.fromisoformat(response.json()["created_at"])
    assert api_created_at.tzinfo == UTC

    with client.app.state.session_factory() as session:
        run = session.scalar(
            select(PipelineRun).where(PipelineRun.run_id == response.json()["run_id"])
        )
        assert run is not None
        assert run.created_at.tzinfo is not None
        assert run.created_at.utcoffset().total_seconds() == 0
