from __future__ import annotations

import argparse
import csv
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CSV_COLUMNS = [
    "transaction_id",
    "source_system",
    "customer_id",
    "merchant_id",
    "amount",
    "currency",
    "transaction_status",
    "event_time",
    "settlement_id",
]


def generate_transactions(
    path: Path,
    rows: int,
    seed: int = 20261031,
    duplicate_every: int = 0,
    invalid_every: int = 0,
) -> Path:
    if rows < 0:
        raise ValueError("rows must be zero or greater")
    randomizer = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    prior_rows: list[dict[str, str]] = []
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for index in range(rows):
            transaction = {
                "transaction_id": f"TX-{index:09d}",
                "source_system": "stripe" if randomizer.randrange(2) == 0 else "razorpay",
                "customer_id": f"C{1001 + randomizer.randrange(3)}",
                "merchant_id": f"M{1001 + randomizer.randrange(3)}",
                "amount": _format_cents(randomizer.randrange(100, 2_000_000)),
                "currency": randomizer.choice(["USD", "EUR", "INR"]),
                "transaction_status": randomizer.choice(["authorized", "settled", "refunded"]),
                "event_time": (base_time + timedelta(seconds=index))
                .isoformat()
                .replace("+00:00", "Z"),
                "settlement_id": f"SET-{index // 1000:06d}",
            }
            if duplicate_every and index > 0 and index % duplicate_every == 0:
                previous = prior_rows[index - 1]
                transaction["transaction_id"] = previous["transaction_id"]
                transaction["source_system"] = previous["source_system"]
            if invalid_every and (index + 1) % invalid_every == 0:
                transaction["amount"] = "-1.00"
            writer.writerow(transaction)
            prior_rows.append(transaction.copy())
    return path


def _format_cents(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate reproducible synthetic DataTrace transaction CSVs."
    )
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261031)
    parser.add_argument(
        "--output", type=Path, default=REPOSITORY_ROOT / "datasets/generated/transactions.csv"
    )
    parser.add_argument("--duplicate-every", type=int, default=0)
    parser.add_argument("--invalid-every", type=int, default=0)
    args = parser.parse_args()
    destination = args.output if args.output.is_absolute() else REPOSITORY_ROOT / args.output
    generate_transactions(
        destination, args.rows, args.seed, args.duplicate_every, args.invalid_every
    )
    print(f"Generated {args.rows} synthetic rows at {destination}")


if __name__ == "__main__":
    main()
