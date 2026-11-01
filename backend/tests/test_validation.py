import csv
import io

from app.engine.pipeline import parse_csv_bytes, validate_and_classify

HEADER = "transaction_id,source_system,customer_id,merchant_id,amount,currency,transaction_status,event_time\n"


def parse_rows(rows: list[list[str]]):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(HEADER.strip().split(","))
    writer.writerows(rows)
    columns, records = parse_csv_bytes(stream.getvalue().encode())
    return validate_and_classify(columns, records, {"C1001"}, {"M1001"})


def valid_row(
    transaction_id="T1",
    amount="1.00",
    currency="USD",
    customer="C1001",
    merchant="M1001",
    event_time="2026-10-31T10:00:00Z",
):
    return [transaction_id, "stripe", customer, merchant, amount, currency, "settled", event_time]


def test_rejects_invalid_domains_and_references_with_rule_codes():
    result = parse_rows(
        [
            valid_row("NEG", amount="-1"),
            valid_row("CUR", currency="JPY"),
            valid_row("REF", customer="C9999"),
            valid_row("TIME", event_time="2026-10-31 10:00:00"),
        ]
    )
    assert [record["reason_code"] for record in result["rejected"]] == [
        "amount_not_positive",
        "unsupported_currency",
        "unknown_customer",
        "invalid_event_time",
    ]
    assert not result["accepted"]


def test_amount_must_be_numeric_finite_and_positive():
    result = parse_rows(
        [
            valid_row("TEXT", amount="not-money"),
            valid_row("INFINITE", amount="Infinity"),
            valid_row("ZERO", amount="0"),
        ]
    )
    assert [record["reason_code"] for record in result["rejected"]] == [
        "amount_not_numeric",
        "amount_not_finite",
        "amount_not_positive",
    ]


def test_invalid_duplicate_is_rejected_before_duplicate_classification():
    result = parse_rows([valid_row("SAME"), valid_row("SAME", amount="0")])
    assert len(result["accepted"]) == 1
    assert result["accepted"][0]["source_row_number"] == 2
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["reason_code"] == "amount_not_positive"
    assert result["duplicates"] == []
    assert not (
        {record["source_row_number"] for record in result["rejected"]}
        & {record["source_row_number"] for record in result["duplicates"]}
    )


def test_row_disposition_sets_are_disjoint_and_cover_each_source_record_once():
    result = parse_rows([valid_row("SAME"), valid_row("SAME"), valid_row("BAD", amount="0")])
    disposition_rows = [
        {record["source_row_number"] for record in result["accepted"]},
        {record["source_row_number"] for record in result["rejected"]},
        {record["source_row_number"] for record in result["duplicates"]},
    ]
    assert not (disposition_rows[0] & disposition_rows[1])
    assert not (disposition_rows[0] & disposition_rows[2])
    assert not (disposition_rows[1] & disposition_rows[2])
    assert set.union(*disposition_rows) == {2, 3, 4}


def test_valid_duplicate_identity_is_source_system_and_transaction_id_casefolded():
    result = parse_rows(
        [
            valid_row("Txn-1"),
            ["txn-1", "STRIPE", "C1001", "M1001", "1.00", "USD", "settled", "2026-10-31T10:00:00Z"],
        ]
    )
    assert len(result["accepted"]) == 1
    assert len(result["duplicates"]) == 1
    assert result["duplicates"][0]["duplicate_of_row_number"] == 2


def test_additive_schema_change_is_recorded_and_out_of_order_is_detected():
    columns, records = parse_csv_bytes(
        (
            HEADER.replace("event_time", "event_time,provider_note")
            + "T1,stripe,C1001,M1001,1.00,USD,settled,2026-10-31T12:00:00Z,first\n"
            + "T2,stripe,C1001,M1001,1.00,USD,settled,2026-10-31T11:00:00Z,second\n"
        ).encode()
    )
    result = validate_and_classify(columns, records, {"C1001"}, {"M1001"})
    assert result["compatibility"] == "ADDITIVE"
    assert result["added_columns"] == ["provider_note"]
    assert result["out_of_order_count"] == 1
    assert result["accepted"][1]["is_out_of_order"] is True


def test_missing_required_columns_are_classified_as_blocking_schema_drift():
    columns, records = parse_csv_bytes(b"transaction_id,amount\nT1,1.00\n")
    result = validate_and_classify(columns, records, set(), set())
    assert result["missing_columns"]
    assert result["compatibility"] == "BLOCKING"
    assert result["rejected"][0]["reason_code"] == "missing_required_columns"
