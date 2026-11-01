import json
import logging

from app.core.logging_config import CorrelationFilter, JsonFormatter, bind_request_id


def test_json_formatter_includes_request_and_run_correlation():
    record = logging.LogRecord(
        "datatrace.test", logging.INFO, "test.py", 10, "run complete", (), None
    )
    record.run_id = "run-test"
    with bind_request_id("request-test"):
        CorrelationFilter().filter(record)
        payload = json.loads(JsonFormatter().format(record))
    assert payload["request_id"] == "request-test"
    assert payload["run_id"] == "run-test"
