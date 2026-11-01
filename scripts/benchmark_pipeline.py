from __future__ import annotations

import argparse
import platform
import sys
import tempfile
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))
sys.path.insert(0, str(REPOSITORY_ROOT))

import pandas as pd  # noqa: E402
from app.engine.pipeline import (  # noqa: E402
    parse_csv_bytes,
    profile_records,
    read_master_ids,
    transform_records,
    validate_and_classify,
)

from scripts.generate_data import generate_transactions  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure DataTrace CSV engine throughput and peak traced memory."
    )
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=20261031)
    args = parser.parse_args()
    if args.rows < 100_000:
        parser.error("--rows must be at least 100000 to satisfy the repository benchmark target")

    with tempfile.TemporaryDirectory(prefix="datatrace-benchmark-") as directory:
        input_path = generate_transactions(
            Path(directory) / "transactions.csv", args.rows, args.seed
        )
        content = input_path.read_bytes()
        customers = read_master_ids(
            REPOSITORY_ROOT / "datasets/sample/customer_master.csv", "customer_id"
        )
        merchants = read_master_ids(
            REPOSITORY_ROOT / "datasets/sample/merchant_master.csv", "merchant_id"
        )
        tracemalloc.start()
        started = time.perf_counter()
        columns, records = parse_csv_bytes(content)
        profile = profile_records(columns, records)
        result = validate_and_classify(columns, records, customers, merchants)
        transformed = transform_records(result["accepted"], "src_benchmark", datetime.now(UTC))
        elapsed = time.perf_counter() - started
        _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    print(f"Python: {platform.python_version()} ({platform.platform()})")
    print(f"pandas: {pd.__version__}")
    print(f"Seed: {args.seed}; input rows: {profile['row_count']}")
    print(
        f"Elapsed: {elapsed:.3f} seconds; throughput: {profile['row_count'] / elapsed:,.0f} rows/second"
    )
    print(f"Peak traced Python memory: {peak_bytes / (1024 * 1024):.1f} MiB")
    print(
        f"Accepted: {len(transformed)}; rejected: {len(result['rejected'])}; duplicates: {len(result['duplicates'])}"
    )
    print(
        "Optimization used: hash-set identity lookup for expected O(1) duplicate checks per record."
    )


if __name__ == "__main__":
    main()
