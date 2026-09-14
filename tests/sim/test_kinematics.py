"""Kinematics, encoder ticks, raycasting and the duty model.

Guards the sim's arithmetic only. The sim has no acceleration ramp, so nothing
here is evidence about the real robot.
"""

import math
import os
import sys

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import config
from brain.maze import MazeStructure
from sim.geometry import MazeGeometry, MazeSegments, cast_ray, merge_intervals
from sim.mouse import MouseState
from sim.sim_machine import simulation_engine


### Kinematics ---------------------------------------------------------------

def test_equal_wheel_speeds_drive_straight():
    mouse = MouseState(start_x_mm=90.0, start_y_mm=90.0, start_heading_radians=math.pi / 2.0)
    mouse.step(200.0, 200.0, 0.5)
    assert abs(mouse.x_mm - 90.0) < 1e-3
    assert abs(mouse.y_mm - 190.0) < 1e-3, mouse.y_mm
    assert abs(mouse.heading_radians - math.pi / 2.0) < 1e-3
    print("✓ test_equal_wheel_speeds_drive_straight passed")


def test_opposite_wheel_speeds_pivot_without_translating():
    mouse = MouseState(start_x_mm=90.0, start_y_mm=90.0, start_heading_radians=0.0)
    rate = 2 * 100.0 / config.TRACK_WIDTH_MM
    mouse.step(-100.0, 100.0, (math.pi / 2.0) / rate)
    assert abs(mouse.x_mm - 90.0) < 1e-3, mouse.x_mm
    assert abs(mouse.y_mm - 90.0) < 1e-3, mouse.y_mm
    assert abs(mouse.heading_radians - math.pi / 2.0) < 1e-3
    print("✓ test_opposite_wheel_speeds_pivot_without_translating passed")


def test_an_arc_curves_the_correct_way():
    """Swapping the two cosines mirrors every arc, and straight-line tests miss it."""
    mouse = MouseState(start_x_mm=0.0, start_y_mm=0.0, start_heading_radians=0.0)
    mouse.step(100.0, 200.0, 0.5)  # right faster: turns left
    assert mouse.x_mm > 0.0, mouse.x_mm
    assert mouse.y_mm > 0.0, mouse.y_mm
    assert 0.0 < mouse.heading_radians < math.pi

    mirror = MouseState(start_x_mm=0.0, start_y_mm=0.0, start_heading_radians=0.0)
    mirror.step(200.0, 100.0, 0.5)  # left faster: turns right
    assert mirror.y_mm < 0.0, mirror.y_mm
    assert abs(mirror.x_mm - mouse.x_mm) < 1e-6
    print("✓ test_an_arc_curves_the_correct_way passed")


def test_heading_stays_within_one_turn():
    mouse = MouseState(start_heading_radians=0.0)
    for _ in range(200):
        mouse.step(-100.0, 100.0, 0.05)
    assert 0.0 <= mouse.heading_radians < 2.0 * math.pi
    print("✓ test_heading_stays_within_one_turn passed")


### Encoders -----------------------------------------------------------------

def test_ticks_come_from_exact_travel_not_accumulated_ticks():
    """Integrating ticks would drift; travel is kept in mm and ticks derived."""
    mouse = MouseState()
    speed, dt, steps = 300.0, 0.001, 5000
    for _ in range(steps):
        mouse.step(speed, speed, dt)

    ideal_ticks = (speed * dt * steps) / config.MM_PER_TICK
    error_mm = abs(mouse.left_encoder_ticks - ideal_ticks) * config.MM_PER_TICK
    assert error_mm < 1.0, error_mm            # under a millimetre over 1.5 m
    assert mouse.left_encoder_ticks == mouse.right_encoder_ticks
    print("✓ test_ticks_come_from_exact_travel_not_accumulated_ticks passed")


def test_reverse_travel_counts_negative():
    mouse = MouseState()
    mouse.step(-200.0, -200.0, 1.0)
    assert mouse.left_encoder_ticks < 0 and mouse.right_encoder_ticks < 0
    print("✓ test_reverse_travel_counts_negative passed")


def test_a_pivot_splits_the_wheels_in_opposite_directions():
    mouse = MouseState()
    mouse.step(-150.0, 150.0, 1.0)
    assert mouse.left_encoder_ticks < 0 < mouse.right_encoder_ticks
    assert abs(mouse.left_encoder_ticks + mouse.right_encoder_ticks) <= 1
    print("✓ test_a_pivot_splits_the_wheels_in_opposite_directions passed")


### Geometry -----------------------------------------------------------------

def test_merge_intervals_joins_touching_spans():
    assert merge_intervals([]) == []
    assert merge_intervals([(0, 1), (1, 2)]) == [(0, 2)]
    assert merge_intervals([(0, 1), (3, 4)]) == [(0, 1), (3, 4)]
    assert merge_intervals([(0, 5), (1, 2)]) == [(0, 5)]
    assert merge_intervals([(3, 4), (0, 1)]) == [(0, 1), (3, 4)]  # unsorted input
    print("✓ test_merge_intervals_joins_touching_spans passed")


def test_cast_ray_finds_a_wall_dead_ahead():
    wall = MazeSegments(-100.0, 100.0, 100.0, 100.0)   # horizontal, 100 mm up
    assert abs(cast_ray((0.0, 0.0), math.pi / 2.0, [wall], 300.0) - 100.0) < 1e-6
    print("✓ test_cast_ray_finds_a_wall_dead_ahead passed")


def test_cast_ray_returns_the_cap_when_nothing_is_hit():
    wall = MazeSegments(-100.0, 100.0, 100.0, 100.0)
    assert cast_ray((0.0, 0.0), -math.pi / 2.0, [wall], 300.0) == 300.0  # facing away
    assert cast_ray((0.0, 0.0), 0.0, [], 300.0) == 300.0                 # no walls
    print("✓ test_cast_ray_returns_the_cap_when_nothing_is_hit passed")


def test_cast_ray_takes_the_nearest_of_several_walls():
    near = MazeSegments(-100.0, 50.0, 100.0, 50.0)
    far = MazeSegments(-100.0, 150.0, 100.0, 150.0)
    assert abs(cast_ray((0.0, 0.0), math.pi / 2.0, [far, near], 300.0) - 50.0) < 1e-6
    print("✓ test_cast_ray_takes_the_nearest_of_several_walls passed")


def test_cast_ray_ignores_a_parallel_wall():
    parallel = MazeSegments(0.0, 0.0, 100.0, 0.0)
    assert cast_ray((0.0, 0.0), 0.0, [parallel], 300.0) == 300.0
    print("✓ test_cast_ray_ignores_a_parallel_wall passed")


def test_geometry_scales_with_the_grid():
    sizes = {n: len(MazeGeometry(MazeStructure(cols=n, rows=n)).posts) for n in (3, 6, 16)}
    assert sizes == {3: 16, 6: 49, 16: 289}, sizes   # (n + 1) squared
    assert len(MazeGeometry(MazeStructure(cols=3, rows=3)).segments) > 0
    print("✓ test_geometry_scales_with_the_grid passed")


### Sensors ------------------------------------------------------------------

def test_a_closer_wall_reads_brighter():
    mouse = MouseState()
    walls = [MazeSegments(-500.0, 300.0, 500.0, 300.0)]
    mouse.reset_pose(0.0, 0.0, math.pi / 2.0)
    far = mouse.read_sensor_adc("front", walls)
    mouse.reset_pose(0.0, 250.0, math.pi / 2.0)
    near = mouse.read_sensor_adc("front", walls)
    assert near > far, (near, far)
    assert config.SENSOR_ADC_FLOOR <= far <= config.SENSOR_ADC_CEILING
    print("✓ test_a_closer_wall_reads_brighter passed")


def test_nothing_in_range_reads_the_floor():
    mouse = MouseState()
    mouse.reset_pose(0.0, 0.0, math.pi / 2.0)
    assert mouse.read_sensor_adc("front", []) == config.SENSOR_ADC_FLOOR
    print("✓ test_nothing_in_range_reads_the_floor passed")


### Duty model ---------------------------------------------------------------

def test_duty_maps_back_to_signed_wheel_speed():
    """Active low: 65535 is OFF.

    Full duty means the SIM's own top speed, not the planner's constant. The two
    are deliberately different; see `SIM_TRUE_WHEEL_SPEED_MMS` in CONSTANTS.md.
    """
    engine = simulation_engine
    full = engine.max_wheel_speed_mms
    assert full != config.MAX_WHEEL_SPEED_MMS, (
        "the sim is taking the planner's constant, so it can only confirm it")

    engine.set_motor_duty(3, 0)      # left forward
    engine.set_motor_duty(2, 65535)
    engine.set_motor_duty(4, 0)      # right forward
    engine.set_motor_duty(5, 65535)
    left, right = engine.compute_wheel_speeds()
    assert abs(left - full) < 1e-6 and abs(right - full) < 1e-6

    for pin in (2, 3, 4, 5):
        engine.set_motor_duty(pin, 65535)
    assert engine.compute_wheel_speeds() == (0.0, 0.0)

    engine.set_motor_duty(2, 0)      # left reverse
    left, _ = engine.compute_wheel_speeds()
    assert abs(left + full) < 1e-6, left

    for pin in (2, 3, 4, 5):
        engine.set_motor_duty(pin, 65535)
    print("✓ test_duty_maps_back_to_signed_wheel_speed passed")


TESTS = (
    test_equal_wheel_speeds_drive_straight,
    test_opposite_wheel_speeds_pivot_without_translating,
    test_an_arc_curves_the_correct_way,
    test_heading_stays_within_one_turn,
    test_ticks_come_from_exact_travel_not_accumulated_ticks,
    test_reverse_travel_counts_negative,
    test_a_pivot_splits_the_wheels_in_opposite_directions,
    test_merge_intervals_joins_touching_spans,
    test_cast_ray_finds_a_wall_dead_ahead,
    test_cast_ray_returns_the_cap_when_nothing_is_hit,
    test_cast_ray_takes_the_nearest_of_several_walls,
    test_cast_ray_ignores_a_parallel_wall,
    test_geometry_scales_with_the_grid,
    test_a_closer_wall_reads_brighter,
    test_nothing_in_range_reads_the_floor,
    test_duty_maps_back_to_signed_wheel_speed,
)


if __name__ == "__main__":
    for test in TESTS:
        test()
    print("ALL {} KINEMATICS TESTS PASSED".format(len(TESTS)))
