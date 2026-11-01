from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest
from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def app(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        storage_dir=tmp_path / "storage",
        output_dir=tmp_path / "output",
        quarantine_dir=tmp_path / "quarantine",
        customer_master_path=Path(__file__).parents[2]
        / "datasets"
        / "sample"
        / "customer_master.csv",
        merchant_master_path=Path(__file__).parents[2]
        / "datasets"
        / "sample"
        / "merchant_master.csv",
        ai_provider="none",
        openrouter_api_key=None,
        gemini_api_key=None,
        max_upload_bytes=1024,
        log_level="WARNING",
    )
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def transaction_csv_bytes() -> bytes:
    rows = [
        [
            "transaction_id",
            "source_system",
            "customer_id",
            "merchant_id",
            "amount",
            "currency",
            "transaction_status",
            "event_time",
        ],
        ["TX-001", "stripe", "C1001", "M1001", "10.25", "USD", "settled", "2026-10-30T12:00:00Z"],
        ["TX-001", "stripe", "C1001", "M1001", "10.25", "USD", "settled", "2026-10-30T12:00:00Z"],
        ["TX-002", "stripe", "C1001", "M1001", "-2", "USD", "settled", "2026-10-30T12:01:00Z"],
        [
            "TX-003",
            "razorpay",
            "C1002",
            "M1002",
            "3.50",
            "INR",
            "authorized",
            "2026-10-30T12:02:00Z",
        ],
    ]
    stream = io.StringIO(newline="")
    csv.writer(stream).writerows(rows)
    return stream.getvalue().encode("utf-8")
