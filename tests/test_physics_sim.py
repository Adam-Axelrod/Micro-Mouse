import math
import os
import sys

# Add Micro-Mouse package directory to sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_DIR = os.path.dirname(TESTS_DIR)
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import config
from geometry import Segment, build_wall_segments, cast_ray
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
    test_setup_and_hardware_sim()
    print("ALL PHYSICS SIM & SETUP TESTS PASSED!")
