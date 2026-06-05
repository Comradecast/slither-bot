from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


FIELDNAMES = [
    "seq",
    "ts",
    "self_x",
    "self_y",
    "self_ang",
    "self_sp",
    "self_fam",
    "snake_count",
    "food_count",
]


def unwrap_state(record: dict[str, Any]) -> dict[str, Any] | None:
    if "self" in record:
        return record

    if record.get("event") == "state":
        metrics = record.get("metrics")
        if isinstance(metrics, dict):
            return {
                "seq": metrics.get("seq"),
                "ts": metrics.get("state_ts"),
                "self": {
                    "x": metrics.get("self_x"),
                    "y": metrics.get("self_y"),
                    "ang": metrics.get("self_angle"),
                    "sp": metrics.get("self_speed"),
                    "fam": metrics.get("self_mass"),
                },
                "snakes": [None] * int(metrics.get("snake_count", 0)),
                "food": [None] * int(metrics.get("food_count", 0)),
            }

    if record.get("kind") == "state" and isinstance(record.get("payload"), dict):
        return record["payload"]

    return None


def row_from_state(state: dict[str, Any]) -> dict[str, Any]:
    self_packet = state.get("self", {})
    snakes = state.get("snakes", [])
    food = state.get("food", [])

    if not isinstance(self_packet, dict):
        self_packet = {}

    if not isinstance(snakes, list):
        snakes = []

    if not isinstance(food, list):
        food = []

    return {
        "seq": state.get("seq"),
        "ts": state.get("ts"),
        "self_x": self_packet.get("x"),
        "self_y": self_packet.get("y"),
        "self_ang": self_packet.get("ang"),
        "self_sp": self_packet.get("sp"),
        "self_fam": self_packet.get("fam"),
        "snake_count": len(snakes),
        "food_count": len(food),
    }


def convert_jsonl_to_csv(input_path: Path, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0

    with input_path.open("r", encoding="utf-8") as source, output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as destination:
        writer = csv.DictWriter(destination, fieldnames=FIELDNAMES)
        writer.writeheader()

        for line_number, line in enumerate(source, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at line {line_number}: {exc}") from exc

            if not isinstance(record, dict):
                continue

            state = unwrap_state(record)
            if state is None:
                continue

            writer.writerow(row_from_state(state))
            count += 1

    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert Slither state JSONL to CSV")
    parser.add_argument("input", type=Path, help="Input JSONL path")
    parser.add_argument("output", type=Path, help="Output CSV path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    count = convert_jsonl_to_csv(args.input, args.output)
    print(f"wrote {count} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
