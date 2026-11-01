def test_rejected_payload_is_persisted_and_not_in_published_output(client, transaction_csv_bytes):
    upload = client.post(
        "/api/v1/sources/upload",
        files={"file": ("transactions.csv", transaction_csv_bytes, "text/csv")},
    ).json()
    run = client.post("/api/v1/runs", json={"source_file_id": upload["source_file_id"]}).json()
    rejection = client.get("/api/v1/quarantine", params={"run_id": run["run_id"]}).json()["items"][
        0
    ]
    assert rejection["original_payload"]["transaction_id"] == "TX-002"
    assert rejection["source_row_number"] == 4
    assert rejection["rejection_reasons"] == ["amount_not_positive"]

    output = client.app.state.settings.output_dir / run["run_id"] / "transactions.csv"
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "TX-002" not in content
    assert "TX-001" in content and "TX-003" in content
