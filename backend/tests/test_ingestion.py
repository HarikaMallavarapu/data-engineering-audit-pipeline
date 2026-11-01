import pytest
from app.engine.pipeline import (
    parse_csv_bytes,
    parse_json_bytes,
    profile_records,
    validate_tabular_records,
)


def test_parser_retains_physical_source_line_numbers_for_multiline_records():
    columns, records = parse_csv_bytes(b'id,note\n1,first\n2,"two\nlines"\n3,last\n')
    assert columns == ["id", "note"]
    assert [record["source_row_number"] for record in records] == [2, 3, 5]


def test_parser_marks_wrong_column_count_instead_of_dropping_row():
    columns, records = parse_csv_bytes(b"id,amount\n1,2,extra\n2\n")
    assert columns == ["id", "amount"]
    assert len(records) == 2
    assert records[0]["payload"]["_parser_error"] == "malformed_row"
    assert records[1]["payload"]["_parser_error"] == "malformed_row"


def test_parser_rejects_malformed_csv_and_duplicate_headers():
    with pytest.raises(ValueError):
        parse_csv_bytes(b'"unterminated')
    with pytest.raises(ValueError):
        parse_csv_bytes(b"id,id\n1,2\n")


def test_profile_reports_row_count_nulls_and_inferred_types():
    columns, records = parse_csv_bytes(b"customer_id,amount\nC1,2.25\n,4.00\n")
    profile = profile_records(columns, records)
    assert profile["row_count"] == 2
    assert profile["null_counts"] == {"customer_id": 1, "amount": 0}
    assert profile["inferred_types"] == {"customer_id": "string", "amount": "decimal"}


def test_json_parser_flattens_nested_objects_and_keeps_array_values():
    columns, records = parse_json_bytes(
        b'[{"user":{"id":7,"email":"person@example.test"},"tags":["a","b"]}]'
    )
    assert columns == ["user.id", "user.email", "tags"]
    assert records[0]["source_row_number"] == 1
    assert records[0]["payload"] == {
        "user.id": 7,
        "user.email": "person@example.test",
        "tags": '["a", "b"]',
    }


def test_json_lines_parser_preserves_physical_line_numbers_and_bad_line_evidence():
    columns, records = parse_json_bytes(b'{"id":1}\nnot-json\n{"id":2}\n', line_delimited=True)
    assert columns == ["id"]
    assert [row["source_row_number"] for row in records] == [1, 2, 3]
    assert records[1]["parser_error"] == "malformed_json_line"


def test_generic_classifier_does_not_require_domain_specific_columns():
    columns, records = parse_csv_bytes(b"event_id,label\nE-1,Alpha\nE-1,Alpha\nE-2,Beta\n")
    result = validate_tabular_records(columns, records)
    assert result["compatibility"] == "DYNAMIC"
    assert result["missing_columns"] == []
    assert len(result["accepted"]) == 2
    assert len(result["duplicates"]) == 1
    assert result["duplicates"][0]["duplicate_of_row_number"] == 2
