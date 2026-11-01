from app.models import AuditEvent, PipelineRun
from sqlalchemy import func, select


def test_identical_run_request_does_not_add_a_second_run_or_republish(
    client, transaction_csv_bytes
):
    source = client.post(
        "/api/v1/sources/upload", files={"file": ("tx.csv", transaction_csv_bytes, "text/csv")}
    ).json()
    first = client.post("/api/v1/runs", json={"source_file_id": source["source_file_id"]}).json()
    first_output = client.app.state.settings.output_dir / first["run_id"] / "transactions.csv"
    before_hash = __import__("hashlib").sha256(first_output.read_bytes()).hexdigest()
    second = client.post("/api/v1/runs", json={"source_file_id": source["source_file_id"]}).json()
    after_hash = __import__("hashlib").sha256(first_output.read_bytes()).hexdigest()
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PipelineRun)) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "run.created")
            )
            == 1
        )
    assert second["run_id"] == first["run_id"]
    assert before_hash == after_hash
