from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from pathlib import Path
from typing import Any, BinaryIO

from bot import config
from bot.strategy import Strategy


class NativeMessagingError(RuntimeError):
    pass


class JsonlLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: dict[str, Any]) -> None:
        event = {
            "wall_time": time.time(),
            **event,
        }

        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, separators=(",", ":"), sort_keys=True))
            handle.write("\n")


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr, flush=True)


def read_exact(stream: BinaryIO, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length

    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            break

        chunks.append(chunk)
        remaining -= len(chunk)

    return b"".join(chunks)


def read_native_message(stream: BinaryIO) -> dict[str, Any] | None:
    raw_length = read_exact(stream, 4)
    if not raw_length:
        return None

    if len(raw_length) != 4:
        raise NativeMessagingError("incomplete native message length header")

    message_length = struct.unpack("<I", raw_length)[0]
    if message_length > config.MAX_NATIVE_MESSAGE_BYTES:
        raise NativeMessagingError(f"native message too large: {message_length} bytes")

    raw_payload = read_exact(stream, message_length)
    if len(raw_payload) != message_length:
        raise NativeMessagingError("incomplete native message payload")

    try:
        payload_text = raw_payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise NativeMessagingError("native message was not UTF-8") from exc

    try:
        message = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise NativeMessagingError(f"native message was not valid JSON: {exc}") from exc

    if not isinstance(message, dict):
        raise NativeMessagingError("native message payload must be a JSON object")

    return message


def write_native_message(stream: BinaryIO, message: dict[str, Any]) -> None:
    payload = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    stream.write(struct.pack("<I", len(payload)))
    stream.write(payload)
    stream.flush()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default

    return result if result == result else default


def _format_metric(metrics: dict[str, Any], key: str, digits: int = 2) -> str:
    value = metrics.get(key)
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return "-"


def validate_state(state: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any]]:
    errors: list[str] = []
    metrics: dict[str, Any] = {}

    if not isinstance(state, dict):
        return False, ["state payload is not an object"], metrics

    self_packet = state.get("self")
    if not isinstance(self_packet, dict):
        return False, ["state missing self object"], metrics

    x = _number(self_packet.get("x"), float("nan"))
    y = _number(self_packet.get("y"), float("nan"))
    angle = _number(self_packet.get("ang"), float("nan"))
    speed = _number(self_packet.get("sp"), float("nan"))
    mass = _number(self_packet.get("fam"), float("nan"))

    # Current slither.com runtime can report coordinates outside the older
    # 0..21000 assumption. Treat world bounds as telemetry, not a Phase 1
    # command blocker.
    if not (config.WORLD_MIN <= x <= config.WORLD_MAX):
        metrics["self_x_world_warning"] = f"out_of_expected_range:{x}"

    if not (config.WORLD_MIN <= y <= config.WORLD_MAX):
        metrics["self_y_world_warning"] = f"out_of_expected_range:{y}"

    if not (0.0 <= angle < config.TWO_PI):
        errors.append(f"self.ang not normalized radians: {angle}")

    if not (0.0 <= speed <= config.MAX_REASONABLE_SPEED):
        errors.append(f"self.sp unreasonable: {speed}")

    # Some current builds expose self.fam as 0 at spawn/runtime. Keep this as
    # telemetry for now; Phase 1 only needs command round trip.
    if not (0.0 <= mass <= config.MAX_REASONABLE_MASS):
        errors.append(f"self.fam unreasonable: {mass}")

    snakes = state.get("snakes", [])
    food = state.get("food", [])

    if not isinstance(snakes, list):
        errors.append("snakes is not a list")
        snakes = []

    if not isinstance(food, list):
        errors.append("food is not a list")
        food = []

    if len(snakes) > config.MAX_REASONABLE_SNAKES:
        errors.append(f"too many snakes in packet: {len(snakes)}")

    if len(food) > config.MAX_REASONABLE_FOOD:
        errors.append(f"too many food items in packet: {len(food)}")

    metrics.update(
        {
            "self_x": x,
            "self_y": y,
            "self_angle": angle,
            "self_speed": speed,
            "self_mass": mass,
            "snake_count": len(snakes),
            "food_count": len(food),
            "state_ts": state.get("ts"),
            "seq": state.get("seq"),
        }
    )

    return len(errors) == 0, errors, metrics


def unwrap_state_message(message: dict[str, Any]) -> dict[str, Any] | None:
    if message.get("kind") == "state" and isinstance(message.get("payload"), dict):
        return message["payload"]

    if "self" in message:
        return message

    return None


def unwrap_ack_message(message: dict[str, Any]) -> dict[str, Any] | None:
    if message.get("kind") == "ack" and isinstance(message.get("payload"), dict):
        return message["payload"]

    if message.get("kind") == "command_ack" and isinstance(message.get("payload"), dict):
        return message["payload"]

    return None


def build_command(state: dict[str, Any], strategy: Strategy, seq: int) -> dict[str, Any]:
    decision = strategy.decide_raw_state(state)

    return {
        "kind": "command",
        "command": {
            "angle": decision.angle,
            "boost": decision.boost,
            "seq": seq,
            "state_ts": state.get("ts"),
            "mode": decision.mode.value,
            "reason": decision.reason,
            "py_sent_wall_time": time.time(),
        },
    }


def run_bridge(log_path: Path) -> int:
    logger = JsonlLogger(log_path)
    strategy = Strategy()

    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer

    frame_count = 0
    valid_count = 0
    invalid_count = 0
    command_seq = 0

    eprint("[slither-bot/native] starting")
    eprint(f"[slither-bot/native] log: {log_path}")

    logger.write(
        {
            "event": "bridge_start",
            "python": sys.version,
            "log_path": str(log_path),
        }
    )

    while True:
        try:
            message = read_native_message(stdin)
        except NativeMessagingError as exc:
            logger.write(
                {
                    "event": "native_message_error",
                    "error": str(exc),
                }
            )
            eprint(f"[slither-bot/native] protocol error: {exc}")
            return 2

        if message is None:
            logger.write(
                {
                    "event": "bridge_eof",
                    "frames": frame_count,
                    "valid": valid_count,
                    "invalid": invalid_count,
                }
            )
            eprint("[slither-bot/native] EOF")
            return 0

        ack = unwrap_ack_message(message)
        if ack is not None:
            logger.write(
                {
                    "event": "command_ack",
                    "ack": ack,
                }
            )

            latency = ack.get("command_latency_ms")
            if isinstance(latency, (int, float)):
                eprint(f"[slither-bot/native] command ack latency_ms={latency:.2f}")
            continue

        if message.get("kind") == "inject_status":
            logger.write(
                {
                    "event": "inject_status",
                    "status": message.get("payload"),
                }
            )
            continue

        state = unwrap_state_message(message)
        if state is None:
            logger.write(
                {
                    "event": "ignored_message",
                    "message": message,
                }
            )
            continue

        frame_count += 1
        valid, errors, metrics = validate_state(state)

        if valid:
            valid_count += 1
        else:
            invalid_count += 1

        if frame_count % config.STATE_LOG_SAMPLE_EVERY_N_FRAMES == 0 or not valid:
            eprint(
                "[slither-bot/native] "
                f"frame={frame_count} valid={valid} "
                f"pos=({_format_metric(metrics, 'self_x', 1)},{_format_metric(metrics, 'self_y', 1)}) "
                f"ang={_format_metric(metrics, 'self_angle', 3)} "
                f"sp={_format_metric(metrics, 'self_speed', 2)} "
                f"mass={_format_metric(metrics, 'self_mass', 1)} "
                f"snakes={metrics.get('snake_count', '-')} "
                f"food={metrics.get('food_count', '-')}"
            )

        logger.write(
            {
                "event": "state",
                "frame": frame_count,
                "valid": valid,
                "errors": errors,
                "metrics": metrics,
            }
        )

        if not valid:
            continue

        command_seq += 1
        command = build_command(state, strategy, command_seq)

        logger.write(
            {
                "event": "command_sent",
                "seq": command_seq,
                "command": command["command"],
            }
        )

        write_native_message(stdout, command)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Slither Bot native messaging bridge")
    parser.add_argument(
        "--log-path",
        type=Path,
        default=config.NATIVE_LOG_PATH,
        help="Path to JSONL bridge log. Default: logs/native_bridge.jsonl",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return run_bridge(args.log_path)


if __name__ == "__main__":
    raise SystemExit(main())
