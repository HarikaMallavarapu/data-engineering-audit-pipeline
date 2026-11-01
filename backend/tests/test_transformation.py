from datetime import UTC, datetime

from app.engine.pipeline import parse_csv_bytes, transform_records, validate_and_classify


def test_transform_normalizes_fields_and_preserves_source_provenance():
    columns, records = parse_csv_bytes(
        b"transaction_id,source_system,customer_id,merchant_id,amount,currency,transaction_status,event_time\n"
        b" Tx-1 , STRIPE , C1001 , M1001 , 10.2 , usd , SETTLED , 2026-10-31T10:00:00+05:30\n"
    )
    result = validate_and_classify(columns, records, {"C1001"}, {"M1001"})
    transformed = transform_records(
        result["accepted"], "src_test", datetime(2026, 10, 31, tzinfo=UTC)
    )[0]
    assert transformed["source_system"] == "stripe"
    assert transformed["transaction_id"] == "Tx-1"
    assert transformed["amount"] == "10.20"
    assert transformed["currency"] == "USD"
    assert transformed["event_time"] == "2026-10-31T04:30:00Z"
    assert transformed["source_file_id"] == "src_test"
    assert transformed["source_row_number"] == 2
