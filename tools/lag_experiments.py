from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def load_ack_latencies(path: Path) -> list[float]:
    latencies: list[float] = []

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at line {line_number}: {exc}") from exc

            if not isinstance(record, dict):
                continue

            if record.get("event") != "command_ack":
                continue

            ack = record.get("ack")
            if not isinstance(ack, dict):
                continue

            latency = ack.get("command_latency_ms")
            if isinstance(latency, (int, float)):
                latencies.append(float(latency))

    return latencies


def percentile(values: list[float], p: float) -> float:
    if not values:
        raise ValueError("cannot compute percentile of empty list")

    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * p
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower

    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def summarize(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "error": "no command_ack latency values found",
        }

    return {
        "count": len(values),
        "min_ms": min(values),
        "max_ms": max(values),
        "mean_ms": statistics.mean(values),
        "median_ms": statistics.median(values),
        "p90_ms": percentile(values, 0.90),
        "p95_ms": percentile(values, 0.95),
        "p99_ms": percentile(values, 0.99),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize Slither command latency")
    parser.add_argument(
        "log",
        type=Path,
        nargs="?",
        default=Path("logs/native_bridge.jsonl"),
        help="Path to native bridge JSONL log",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    values = load_ack_latencies(args.log)
    summary = summarize(values)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if values else 1


if __name__ == "__main__":
    raise SystemExit(main())
