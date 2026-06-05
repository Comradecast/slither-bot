import math

from bot.config import BASE_RADIUS, TURN_RATE
from bot.geometry import (
    circle_collision,
    clamp_turn,
    distance,
    encode_angle_8,
    heading_between,
    intercept_time_linear,
    normalize_angle,
    predict_position,
    radius,
    ray_circle_intersection,
    shortest_angle_delta,
)


def test_radius_formula() -> None:
    assert radius(0) == BASE_RADIUS
    assert radius(100) == BASE_RADIUS + 5


def test_normalize_angle() -> None:
    assert normalize_angle(0) == 0
    assert normalize_angle(2 * math.pi) == 0
    assert math.isclose(normalize_angle(-math.pi), math.pi)


def test_shortest_angle_delta_wraparound() -> None:
    current = math.radians(350)
    target = math.radians(10)
    assert math.isclose(shortest_angle_delta(current, target), math.radians(20))


def test_clamp_turn_limits_turn_rate() -> None:
    current = 0.0
    target = math.pi
    result = clamp_turn(current, target, TURN_RATE)
    assert math.isclose(result, TURN_RATE)


def test_distance() -> None:
    assert distance((0, 0), (3, 4)) == 5


def test_heading_between() -> None:
    assert math.isclose(heading_between((0, 0), (0, 1)), math.pi / 2)


def test_circle_collision() -> None:
    assert circle_collision((0, 0), 5, (9, 0), 5)
    assert not circle_collision((0, 0), 5, (11, 0), 5)


def test_ray_circle_intersection_hit() -> None:
    hit = ray_circle_intersection(
        origin=(0, 0),
        angle=0,
        circle_center=(10, 0),
        circle_radius=2,
    )

    assert hit is not None
    assert math.isclose(hit.distance, 8)
    assert math.isclose(hit.point[0], 8)
    assert math.isclose(hit.point[1], 0)


def test_ray_circle_intersection_miss() -> None:
    hit = ray_circle_intersection(
        origin=(0, 0),
        angle=0,
        circle_center=(10, 10),
        circle_radius=2,
    )

    assert hit is None


def test_predict_position() -> None:
    point = predict_position((0, 0), 0, 5, 2)
    assert math.isclose(point[0], 10)
    assert math.isclose(point[1], 0)


def test_intercept_time_linear_stationary_target() -> None:
    t = intercept_time_linear(
        pursuer_position=(0, 0),
        pursuer_speed=5,
        target_position=(10, 0),
        target_velocity=(0, 0),
    )

    assert t is not None
    assert math.isclose(t, 2)


def test_encode_angle_8() -> None:
    assert encode_angle_8(0) == 0
    assert encode_angle_8(math.pi / 2) == 64
    assert encode_angle_8(math.pi) == 128
