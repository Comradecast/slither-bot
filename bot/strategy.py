from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from bot.config import DUMMY_COMMAND_BOOST, DUMMY_COMMAND_TURN_RADIANS
from bot.geometry import normalize_angle
from bot.perception import PerceptionSnapshot, snapshot_from_state


class StrategyMode(str, Enum):
    GROW = "GROW"
    SHADOW = "SHADOW"
    FLANK_CUT = "FLANK_CUT"
    HUNTER_KILLER = "HUNTER_KILLER"
    SCAVENGE = "SCAVENGE"
    PHASE1_DUMMY = "PHASE1_DUMMY"


@dataclass(frozen=True)
class StrategyDecision:
    angle: float
    boost: bool
    mode: StrategyMode
    reason: str


class Strategy:
    def __init__(self) -> None:
        self.mode = StrategyMode.PHASE1_DUMMY

    def decide_snapshot(self, snapshot: PerceptionSnapshot) -> StrategyDecision:
        current_angle = snapshot.self_agent.angle
        dummy_angle = normalize_angle(current_angle + DUMMY_COMMAND_TURN_RADIANS)

        return StrategyDecision(
            angle=dummy_angle,
            boost=DUMMY_COMMAND_BOOST,
            mode=self.mode,
            reason="phase1_dummy_turn_pipeline_test",
        )

    def decide_raw_state(self, state: dict) -> StrategyDecision:
        snapshot = snapshot_from_state(state)
        return self.decide_snapshot(snapshot)


def decide(state: dict) -> StrategyDecision:
    return Strategy().decide_raw_state(state)
