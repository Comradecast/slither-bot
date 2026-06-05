from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bot.config import AI_VISION_RADIUS
from bot.geometry import Point, distance, radius


@dataclass(frozen=True)
class PerceivedObstacle:
    kind: str
    x: float
    y: float
    radius: float
    source_id: int | None = None

    @property
    def center(self) -> Point:
        return (self.x, self.y)


@dataclass(frozen=True)
class PerceivedAgent:
    id: int | None
    x: float
    y: float
    angle: float
    speed: float
    mass: float
    points: tuple[Point, ...] = field(default_factory=tuple)
    is_self: bool = False

    @property
    def head(self) -> Point:
        return (self.x, self.y)

    @property
    def body_radius(self) -> float:
        return radius(self.mass)

    def as_obstacles(self) -> tuple[PerceivedObstacle, ...]:
        obstacles: list[PerceivedObstacle] = [
            PerceivedObstacle(
                kind="snake_head",
                x=self.x,
                y=self.y,
                radius=self.body_radius,
                source_id=self.id,
            )
        ]

        for point in self.points:
            obstacles.append(
                PerceivedObstacle(
                    kind="snake_body",
                    x=point[0],
                    y=point[1],
                    radius=self.body_radius,
                    source_id=self.id,
                )
            )

        return tuple(obstacles)


@dataclass(frozen=True)
class PerceivedFood:
    x: float
    y: float
    size: float

    @property
    def center(self) -> Point:
        return (self.x, self.y)


@dataclass(frozen=True)
class PerceptionSnapshot:
    self_agent: PerceivedAgent
    snakes: tuple[PerceivedAgent, ...]
    food: tuple[PerceivedFood, ...]
    ts: float
    seq: int | None = None

    def nearby_snakes(self, radius_value: float = AI_VISION_RADIUS) -> tuple[PerceivedAgent, ...]:
        return tuple(
            snake
            for snake in self.snakes
            if distance(self.self_agent.head, snake.head) <= radius_value
        )

    def nearby_food(self, radius_value: float = AI_VISION_RADIUS) -> tuple[PerceivedFood, ...]:
        return tuple(
            item
            for item in self.food
            if distance(self.self_agent.head, item.center) <= radius_value
        )


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default

    return result if result == result else default


def _point_tuple(raw_points: Any) -> tuple[Point, ...]:
    if not isinstance(raw_points, list):
        return tuple()

    points: list[Point] = []

    for item in raw_points:
        if isinstance(item, list) and len(item) >= 2:
            points.append((_number(item[0]), _number(item[1])))
        elif isinstance(item, tuple) and len(item) >= 2:
            points.append((_number(item[0]), _number(item[1])))

    return tuple(points)


def agent_from_self_packet(packet: dict[str, Any]) -> PerceivedAgent:
    return PerceivedAgent(
        id=None,
        x=_number(packet.get("x")),
        y=_number(packet.get("y")),
        angle=_number(packet.get("ang")),
        speed=_number(packet.get("sp")),
        mass=_number(packet.get("fam"), 1.0),
        points=_point_tuple(packet.get("pts")),
        is_self=True,
    )


def agent_from_snake_packet(packet: dict[str, Any]) -> PerceivedAgent:
    return PerceivedAgent(
        id=int(_number(packet.get("id"), -1)),
        x=_number(packet.get("xx")),
        y=_number(packet.get("yy")),
        angle=_number(packet.get("ang")),
        speed=_number(packet.get("sp")),
        mass=_number(packet.get("sc"), 1.0),
        points=_point_tuple(packet.get("pts")),
        is_self=False,
    )


def food_from_packet(packet: dict[str, Any]) -> PerceivedFood:
    return PerceivedFood(
        x=_number(packet.get("x")),
        y=_number(packet.get("y")),
        size=_number(packet.get("sz"), 1.0),
    )


def snapshot_from_state(state: dict[str, Any]) -> PerceptionSnapshot:
    if not isinstance(state, dict):
        raise TypeError("state must be a dict")

    self_packet = state.get("self")
    if not isinstance(self_packet, dict):
        raise ValueError("state missing self packet")

    raw_snakes = state.get("snakes", [])
    raw_food = state.get("food", [])

    if not isinstance(raw_snakes, list):
        raw_snakes = []

    if not isinstance(raw_food, list):
        raw_food = []

    return PerceptionSnapshot(
        self_agent=agent_from_self_packet(self_packet),
        snakes=tuple(
            agent_from_snake_packet(item)
            for item in raw_snakes
            if isinstance(item, dict)
        ),
        food=tuple(
            food_from_packet(item)
            for item in raw_food
            if isinstance(item, dict)
        ),
        ts=_number(state.get("ts")),
        seq=int(state["seq"]) if "seq" in state and state["seq"] is not None else None,
    )
