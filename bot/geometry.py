from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

from bot.config import BASE_RADIUS, TWO_PI


Point = tuple[float, float]


@dataclass(frozen=True)
class RayCircleHit:
    distance: float
    point: Point


def radius(mass: float) -> float:
    return BASE_RADIUS + mass * 0.05


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def normalize_angle(angle: float) -> float:
    result = angle % TWO_PI
    if result < 0:
        result += TWO_PI
    return result


def angle_to_vector(angle: float) -> Point:
    return (math.cos(angle), math.sin(angle))


def vector_to_angle(dx: float, dy: float) -> float:
    return normalize_angle(math.atan2(dy, dx))


def shortest_angle_delta(current: float, target: float) -> float:
    delta = (normalize_angle(target) - normalize_angle(current) + math.pi) % TWO_PI - math.pi

    if math.isclose(delta, -math.pi):
        return math.pi

    return delta


def clamp_turn(current: float, target: float, max_turn: float) -> float:
    delta = shortest_angle_delta(current, target)
    limited = clamp(delta, -abs(max_turn), abs(max_turn))
    return normalize_angle(current + limited)


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def distance_sq(a: Point, b: Point) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return dx * dx + dy * dy


def project_point(origin: Point, angle: float, distance_value: float) -> Point:
    vx, vy = angle_to_vector(angle)
    return (origin[0] + vx * distance_value, origin[1] + vy * distance_value)


def heading_between(origin: Point, target: Point) -> float:
    return vector_to_angle(target[0] - origin[0], target[1] - origin[1])


def dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def subtract(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])


def add(a: Point, b: Point) -> Point:
    return (a[0] + b[0], a[1] + b[1])


def scale(a: Point, scalar: float) -> Point:
    return (a[0] * scalar, a[1] * scalar)


def circle_collision(center_a: Point, radius_a: float, center_b: Point, radius_b: float) -> bool:
    combined = radius_a + radius_b
    return distance_sq(center_a, center_b) <= combined * combined


def point_in_world(point: Point, world_min: float = 0.0, world_max: float = 21000.0) -> bool:
    return world_min <= point[0] <= world_max and world_min <= point[1] <= world_max


def ray_circle_intersection(
    origin: Point,
    angle: float,
    circle_center: Point,
    circle_radius: float,
    max_distance: float | None = None,
) -> RayCircleHit | None:
    direction = angle_to_vector(angle)
    oc = subtract(origin, circle_center)

    a = dot(direction, direction)
    b = 2.0 * dot(oc, direction)
    c = dot(oc, oc) - circle_radius * circle_radius

    discriminant = b * b - 4.0 * a * c
    if discriminant < 0:
        return None

    sqrt_disc = math.sqrt(discriminant)
    t1 = (-b - sqrt_disc) / (2.0 * a)
    t2 = (-b + sqrt_disc) / (2.0 * a)

    candidates = [t for t in (t1, t2) if t >= 0]
    if not candidates:
        return None

    t = min(candidates)
    if max_distance is not None and t > max_distance:
        return None

    hit_point = project_point(origin, angle, t)
    return RayCircleHit(distance=t, point=hit_point)


def nearest_point_on_segment(point: Point, segment_a: Point, segment_b: Point) -> Point:
    ab = subtract(segment_b, segment_a)
    ab_len_sq = dot(ab, ab)

    if ab_len_sq == 0:
        return segment_a

    t = dot(subtract(point, segment_a), ab) / ab_len_sq
    t = clamp(t, 0.0, 1.0)
    return add(segment_a, scale(ab, t))


def distance_to_polyline(point: Point, polyline: Sequence[Point]) -> float:
    if not polyline:
        return math.inf

    if len(polyline) == 1:
        return distance(point, polyline[0])

    best = math.inf
    for a, b in zip(polyline, polyline[1:]):
        nearest = nearest_point_on_segment(point, a, b)
        best = min(best, distance(point, nearest))

    return best


def predict_position(position: Point, angle: float, speed: float, ticks: float) -> Point:
    return project_point(position, angle, speed * ticks)


def intercept_time_linear(
    pursuer_position: Point,
    pursuer_speed: float,
    target_position: Point,
    target_velocity: Point,
) -> float | None:
    rel = subtract(target_position, pursuer_position)

    a = dot(target_velocity, target_velocity) - pursuer_speed * pursuer_speed
    b = 2.0 * dot(rel, target_velocity)
    c = dot(rel, rel)

    if abs(a) < 1e-9:
        if abs(b) < 1e-9:
            return 0.0 if c == 0 else None
        t = -c / b
        return t if t >= 0 else None

    discriminant = b * b - 4.0 * a * c
    if discriminant < 0:
        return None

    sqrt_disc = math.sqrt(discriminant)
    candidates = [
        (-b - sqrt_disc) / (2.0 * a),
        (-b + sqrt_disc) / (2.0 * a),
    ]
    candidates = [t for t in candidates if t >= 0]
    if not candidates:
        return None

    return min(candidates)


def encode_angle_8(angle: float) -> int:
    return math.floor((normalize_angle(angle) / TWO_PI) * 256) & 255


def average_point(points: Iterable[Point]) -> Point | None:
    points_list = list(points)
    if not points_list:
        return None

    sx = sum(p[0] for p in points_list)
    sy = sum(p[1] for p in points_list)
    count = len(points_list)
    return (sx / count, sy / count)
