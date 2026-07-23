"""Main Entry Point for UKMARS Gemini Micromouse.

Unified control loop running on both Raspberry Pi Pico 2 W and PC simulation.
Supports headless execution as well as optional Pygame desktop rendering (`python3 main.py --render`).
"""

import os
import sys
import time

# Ensure package directory is on sys.path for Pico and PC imports
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import commands
import config
import maze
import search_algorithms
import setup
from explorer import Explorer

# Optional Pygame desktop renderer (PC only; geometry is PC-only too, so it
# lives under the same guard rather than at top level, keeping main.py Pico-safe)
try:
    import geometry
    from renderer import Renderer
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False

# PC Hardware simulation engine (PC only)
try:
    import sim_machine
    HAS_SIM = True
except ImportError:
    HAS_SIM = False

CRUISE_DUTY_POWER = 0.55
TURN_DUTY_POWER = 0.40


def blink_led(times, on_duration_ms=100, off_duration_ms=100):
    for _ in range(times):
        setup.LED_PIN.value(1)
        time.sleep(on_duration_ms / 1000.0)
        setup.LED_PIN.value(0)
        time.sleep(off_duration_ms / 1000.0)


def drive_motors(left_power, right_power):
    """Active-low driver for dual PWM channels per motor: power in [-1.0, 1.0].
    
    65535 is OFF/HIGH, 0 is FULL LOW. Brake by setting both channels to 65535.
    """
    left_p = max(-1.0, min(1.0, left_power))
    right_p = max(-1.0, min(1.0, right_power))

    maxspeed = 65535
    if left_p >= 0:
        setup.leftFwd.duty_u16(maxspeed)
        setup.leftRev.duty_u16(int(maxspeed * (1.0 - left_p)))
    else:
        setup.leftRev.duty_u16(maxspeed)
        setup.leftFwd.duty_u16(int(maxspeed * (1.0 - abs(left_p))))

    if right_p >= 0:
        setup.rightFwd.duty_u16(maxspeed)
        setup.rightRev.duty_u16(int(maxspeed * (1.0 - right_p)))
    else:
        setup.rightRev.duty_u16(maxspeed)
        setup.rightFwd.duty_u16(int(maxspeed * (1.0 - abs(right_p))))


def stop_motors():
    maxspeed = 65535
    setup.leftFwd.duty_u16(maxspeed)
    setup.leftRev.duty_u16(maxspeed)
    setup.rightFwd.duty_u16(maxspeed)
    setup.rightRev.duty_u16(maxspeed)


def read_walls(real_maze, current_position):
    """Read true wall presence around current cell (simulation mode)."""
    walls = real_maze.cells[current_position]
    sensed_walls = []
    for wall_flag, compass_side in zip(walls, config.DIRECTIONS):
        if wall_flag:
            sensed_walls.append(compass_side)
    return sensed_walls


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


def load_and_plan_route(belief_file_path=None, start_heading=config.DIRECTIONS[0]):
    """Load saved grid belief map, flood fill shortest route, and return movement commands."""
    if belief_file_path is None:
        belief_file_path = config.SAVED_BELIEF_MAZE

    if not os.path.exists(belief_file_path):
        print(f"Warning: No saved belief at {belief_file_path}, using ground truth maze.")
        belief_file_path = config.DEFAULT_MAZE

    cells, cols, rows = maze.num_file_import(belief_file_path)
    discovered_maze = maze.MazeStructure(cells=cells, cols=cols, rows=rows)

    optimal_route = search_algorithms.flood_fill(discovered_maze, config.START_POS)
    movement_commands = commands.path_to_commands(optimal_route, start_heading=start_heading)

    return optimal_route, movement_commands


def run_exploration_mode(enable_render=False, save_belief_path=None):
    print("=== STARTING EXPLORATION MODE ===")
    blink_led(3, on_duration_ms=150, off_duration_ms=150)

    real_maze = maze.MazeStructure(*maze.num_file_import(config.DEFAULT_MAZE))
    
    if HAS_SIM:
        sim_machine.set_sim_maze(real_maze)

    belief = maze.MazeStructure(cols=real_maze.cols, rows=real_maze.rows)
    explorer_robot = Explorer(belief_map=belief)

    render_object = None
    if HAS_PYGAME and enable_render:
        try:
            render_object = Renderer(geometry.MazeGeometry(real_maze))
        except Exception as exc:
            print(f"Renderer init failed ({type(exc).__name__}: {exc}); continuing without rendering.")
            render_object = None

    previous_route = None

    while not explorer_robot.at_goal():
        sensed_walls = read_walls(real_maze, explorer_robot.pos)
        explorer_robot.observe(explorer_robot.pos, sensed_walls)
        route = search_algorithms.flood_fill(explorer_robot.belief_map, explorer_robot.pos)

        replanned = (previous_route is None or route != previous_route[1:])
        if render_object is not None:
            mouse_st = sim_machine.get_mouse_state() if HAS_SIM else None
            render_object.draw(
                belief=explorer_robot.belief_map,
                mouse=mouse_st,
                path=route,
                done=explorer_robot.path_done,
                animate=replanned
            )
        previous_route = route

        if len(route) < 2:
            break

        explorer_robot.path_to_execute = [route[1]]
        while explorer_robot.path_to_execute:
            explorer_robot.step()
            if HAS_SIM:
                sim_machine.step_sim_physics(delta_time_seconds=0.01)

    if save_belief_path is None:
        save_belief_path = config.SAVED_BELIEF_MAZE

    maze.num_file_export(save_belief_path, explorer_robot.belief_map.cells)
    print(f"Exploration finished! Grid belief map saved to: {save_belief_path}")

    return explorer_robot


def run_speed_run_mode():
    print("=== STARTING SPEED RUN MODE ===")
    blink_led(5, on_duration_ms=80, off_duration_ms=80)

    route, movement_commands = load_and_plan_route()
    print(f"Optimal cell path ({len(route)} cells): {route}")

    execute_movement_commands(movement_commands)


def main():
    stop_motors()

    enable_render = "--render" in sys.argv or "-r" in sys.argv

    print("Maze Mouse Ready. Press LEFT button for Exploration, RIGHT button for Speed Run.")
    if enable_render:
        print("[Rendering Enabled via CLI argument]")

    blink_led(2, on_duration_ms=200, off_duration_ms=200)

    left_button_pressed = (setup.leftButton.value() == 0)
    right_button_pressed = (setup.rightButton.value() == 0)

    if left_button_pressed:
        run_exploration_mode(enable_render=enable_render)
    elif right_button_pressed:
        run_speed_run_mode()
    else:
        print("No button pressed. Defaulting to Exploration mode.")
        run_exploration_mode(enable_render=enable_render)


if __name__ == "__main__":
    main()
