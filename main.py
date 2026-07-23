import math
import os
import sys
import time

# Ensure package directory is on sys.path for Pico and PC imports
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import config
import setup
from env_explorer import explore, load_and_plan_route
from maze import MazeStructure, num_file_import

CRUISE_DUTY_POWER = 0.55
TURN_DUTY_POWER = 0.40


def blink_led(times, on_duration_ms=100, off_duration_ms=100):
    for _ in range(times):
        setup.LED_PIN.value(1)
        time.sleep(on_duration_ms / 1000.0)
        setup.LED_PIN.value(0)
        time.sleep(off_duration_ms / 1000.0)


def drive_motors(left_power, right_power):
    """Active-low driver: power in [-1.0, 1.0], duty_u16 65535 is OFF, 0 is FULL."""
    left_duty = int(65535 * (1.0 - max(0.0, min(1.0, left_power))))
    right_duty = int(65535 * (1.0 - max(0.0, min(1.0, right_power))))
    setup.LMOTOR_PWM.duty_u16(left_duty)
    setup.RMOTOR_PWM.duty_u16(right_duty)


def stop_motors():
    setup.LMOTOR_PWM.duty_u16(65535)
    setup.RMOTOR_PWM.duty_u16(65535)


def execute_movement_commands(movement_commands):
    """Execute egocentric movement verbs: F n, L, R, U, H."""
    print(f"Executing movement route: {movement_commands}")

    for command_string in movement_commands:
        if not command_string or command_string.startswith("#"):
            continue

        parts = command_string.split()
        verb = parts[0]
        arg = int(parts[1]) if len(parts) > 1 else None

        if verb == "F":
            cells_to_drive = arg
            target_distance_mm = cells_to_drive * config.MM_PER_CELL
            drive_time_seconds = target_distance_mm / 300.0

            drive_motors(CRUISE_DUTY_POWER, CRUISE_DUTY_POWER)
            time.sleep(drive_time_seconds)
            stop_motors()

        elif verb in ("L", "R", "U"):
            if verb == "L":
                turn_direction = -1.0
            elif verb == "R":
                turn_direction = 1.0
            else:
                turn_direction = 2.0

            pivot_time_seconds = 0.4 * abs(turn_direction)
            drive_motors(turn_direction * TURN_DUTY_POWER, -turn_direction * TURN_DUTY_POWER)
            time.sleep(pivot_time_seconds)
            stop_motors()

        elif verb == "H":
            stop_motors()
            print("Route completed successfully!")
            break

        time.sleep(0.1)


def run_exploration_mode():
    print("=== STARTING EXPLORATION MODE ===")
    blink_led(3, on_duration_ms=150, off_duration_ms=150)

    real_maze = MazeStructure(*num_file_import(config.DEFAULT_MAZE))
    explore(real_maze)
    print("Exploration finished and grid map saved.")


def run_speed_run_mode():
    print("=== STARTING SPEED RUN MODE ===")
    blink_led(5, on_duration_ms=80, off_duration_ms=80)

    route, movement_commands = load_and_plan_route()
    print(f"Optimal cell path ({len(route)} cells): {route}")

    execute_movement_commands(movement_commands)


def main():
    stop_motors()
    print("Maze Mouse Ready. Press LEFT button for Exploration, RIGHT button for Speed Run.")

    blink_led(2, on_duration_ms=200, off_duration_ms=200)

    left_button_pressed = (setup.btn1.value() == 0)
    right_button_pressed = (setup.Switch.value() == 0)

    if left_button_pressed:
        run_exploration_mode()
    elif right_button_pressed:
        run_speed_run_mode()
    else:
        print("No button pressed. Defaulting to Speed Run mode.")
        run_speed_run_mode()


if __name__ == "__main__":
    main()
