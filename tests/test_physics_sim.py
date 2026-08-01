import math
import os
import sys

# Add Micro-Mouse package directory to sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_DIR = os.path.dirname(TESTS_DIR)
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import config
from geometry import Segment, cast_ray
from maze import MazeStructure, num_file_import
from mouse import MouseState
from sim_machine import set_sim_maze, step_sim_physics, get_mouse_state


def test_kinematics_straight():
    mouse = MouseState(start_x_mm=90.0, start_y_mm=90.0, start_heading_radians=math.pi / 2.0)
    mouse.step(left_wheel_speed_mms=200.0, right_wheel_speed_mms=200.0, delta_time_seconds=0.5)

    assert abs(mouse.x_mm - 90.0) < 1e-3
    assert abs(mouse.y_mm - 190.0) < 1e-3
    assert abs(mouse.heading_radians - math.pi / 2.0) < 1e-3
    assert mouse.left_encoder_ticks > 0
    assert mouse.left_encoder_ticks == mouse.right_encoder_ticks
    print("✓ test_kinematics_straight passed")


def test_kinematics_pivot():
    mouse = MouseState(start_x_mm=90.0, start_y_mm=90.0, start_heading_radians=0.0)
    omega = (100.0 - (-100.0)) / config.TRACK_WIDTH_MM
    time_needed = (math.pi / 2.0) / omega

    mouse.step(left_wheel_speed_mms=100.0, right_wheel_speed_mms=-100.0, delta_time_seconds=time_needed)

    assert abs(mouse.x_mm - 90.0) < 1e-3
    assert abs(mouse.y_mm - 90.0) < 1e-3
    expected_heading = (2.0 * math.pi - math.pi / 2.0) % (2.0 * math.pi)
    assert abs(mouse.heading_radians - expected_heading) < 1e-3
    print("✓ test_kinematics_pivot passed")


def test_kinematics_arc():
    """Curved motion: the case neither straight-line nor pivot exercises.

    A straight run takes the |omega| < 1e-6 branch and a pivot has v = 0 (so the
    turn radius is 0), which means both of the other kinematics tests pass no
    matter what the arc formula does. Ground truth here is an independent
    fine-grained Euler integration of dx/dt = v.cos0, dy/dt = v.sin0, d0/dt = w.
    """
    left_speed, right_speed, duration = 100.0, 200.0, 0.5

    steps = 200000
    dt = duration / steps
    v = (left_speed + right_speed) / 2.0
    omega = (right_speed - left_speed) / config.TRACK_WIDTH_MM
    ex_x = ex_y = ex_heading = 0.0
    for _ in range(steps):
        ex_x += v * math.cos(ex_heading) * dt
        ex_y += v * math.sin(ex_heading) * dt
        ex_heading += omega * dt

    mouse = MouseState(start_x_mm=0.0, start_y_mm=0.0, start_heading_radians=0.0)
    mouse.step(left_speed, right_speed, duration)

    assert abs(mouse.x_mm - ex_x) < 1e-2, f"x: {mouse.x_mm} vs {ex_x}"
    assert abs(mouse.y_mm - ex_y) < 1e-2, f"y: {mouse.y_mm} vs {ex_y}"
    assert abs(mouse.heading_radians - ex_heading) < 1e-3

    # A left arc (right wheel faster) must end up left of and ahead of the start.
    assert mouse.y_mm > 0.0 and mouse.x_mm > 0.0
    print("✓ test_kinematics_arc passed")


def test_encoder_ticks_do_not_drift():
    """Ticks come from cumulative travel, so per-step rounding must not compound."""
    mouse = MouseState()
    speed_mms, dt, steps = 300.0, config.SIM_TIMESTEP_S, 100
    for _ in range(steps):
        mouse.step(speed_mms, speed_mms, dt)

    ideal_ticks = (speed_mms * dt * steps) / config.MM_PER_TICK
    error_mm = abs(mouse.left_encoder_ticks - ideal_ticks) * config.MM_PER_TICK
    assert error_mm < 0.1, f"odometry drifted {error_mm:.3f} mm over 300 mm"
    assert mouse.left_encoder_ticks == mouse.right_encoder_ticks
    print("✓ test_encoder_ticks_do_not_drift passed")


def test_setup_and_hardware_sim():
    cells, cols, rows = num_file_import(config.DEFAULT_MAZE)
    maze = MazeStructure(cells=cells, cols=cols, rows=rows)
    set_sim_maze(maze)

    import setup

    mstate = get_mouse_state()
    mstate.reset_pose(x_mm=90.0, y_mm=90.0, heading_radians=math.pi / 2.0)

    val_left = setup.Lsidesense.read_u16()
    assert val_left > 200, f"Expected left wall hit, got {val_left}"

    setup.LMOTOR_PWM.duty_u16(32768)
    setup.RMOTOR_PWM.duty_u16(32768)

    initial_y = mstate.y_mm
    step_sim_physics(delta_time_seconds=0.1)
    new_y = mstate.y_mm

    assert new_y > initial_y
    print("✓ test_setup_and_hardware_sim passed (clean setup.py integration!)")


if __name__ == "__main__":
    test_kinematics_straight()
    test_kinematics_pivot()
    test_kinematics_arc()
    test_encoder_ticks_do_not_drift()
    test_setup_and_hardware_sim()
    print("ALL PHYSICS SIM & SETUP TESTS PASSED!")
