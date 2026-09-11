"""Speed Run Mode (mode 2) for UKMARS Gemini Micromouse.

Loads the explored belief map, flood-fills the optimal route, and executes the
resulting movement commands. Pico and PC compatible.

This module owns the ROUTE: loading a belief, planning over it, and turning
egocentric verbs into timed drives. It does not own the motors -- `drive.py`
does. Anything that only needs to move a wheel should import `drive`, not this.
"""

import commands
import config
import drive
import maze
import search_algorithms
import setup

# Rendering is PC-only and optional. The `sim` package is never deployed to the
# board, so on the Pico this import fails and every mode runs headless.
try:
    from sim.renderer import make_renderer
except ImportError:
    def make_renderer(real_maze):
        return None

HAS_SIM = setup.sim is not None


def execute_movement_commands(movement_commands, render_object=None, belief=None, route=None):
    """Execute egocentric movement verbs: F n, L, R, U, H.

    Open loop. Each verb becomes a fixed power held for a computed number of
    seconds, and no encoder is read while it runs. Distance divides by one
    constant speed, so nothing here models the acceleration ramp -- see the
    MAX_WHEEL_SPEED_MMS comment in config.py before trusting a short move.
    """
    print(f"Executing movement route: {movement_commands}")

    cruise_speed_mms = drive.CRUISE_DUTY_POWER * config.MAX_WHEEL_SPEED_MMS

    for command_string in movement_commands:
        if not command_string or command_string.startswith("#"):
            continue

        parts = command_string.split()
        verb = parts[0]
        arg = int(parts[1]) if len(parts) > 1 else None

        if verb == commands.FORWARD:
            cells_to_drive = arg
            target_distance_mm = cells_to_drive * config.MM_PER_CELL
            drive_time_seconds = target_distance_mm / cruise_speed_mms

            drive.drive_motors(drive.CRUISE_DUTY_POWER, drive.CRUISE_DUTY_POWER)
            drive.run_motion_for(drive_time_seconds, render_object, belief, route)
            drive.stop_motors()

        elif verb in (commands.LEFT, commands.RIGHT, commands.UTURN):
            # quarter turns, and which way round. A U-turn takes the same
            # direction as R; on the spot either way lands the same heading.
            if verb == commands.LEFT:
                quarter_turns, clockwise = 1, False
            elif verb == commands.RIGHT:
                quarter_turns, clockwise = 1, True
            else:
                quarter_turns, clockwise = 2, True

            drive.pivot_in_place(quarter_turns, clockwise, render_object, belief, route)

        elif verb == commands.HALT:
            drive.stop_motors()
            print("Route completed successfully!")
            break

        drive.run_motion_for(config.INTER_COMMAND_SETTLE_S, render_object, belief, route)


def load_and_plan_route(belief_file_path=None, start_heading=config.DIRECTIONS[0]):
    """Load saved grid belief map, flood fill shortest route, and return movement commands."""
    if belief_file_path is None:
        belief_file_path = config.SAVED_BELIEF_MAZE

    if not maze.file_exists(belief_file_path):
        print(f"Warning: No saved belief at {belief_file_path}, using ground truth maze.")
        belief_file_path = config.DEFAULT_MAZE

    cells, cols, rows = maze.num_file_import(belief_file_path)
    discovered_maze = maze.MazeStructure(cells=cells, cols=cols, rows=rows)

    optimal_route = search_algorithms.flood_fill(discovered_maze, config.START_POS)
    movement_commands = commands.path_to_commands(optimal_route, start_heading=start_heading)

    return optimal_route, movement_commands, discovered_maze


def run(enable_render=False):
    """Run speed run mode."""
    print("=== STARTING SPEED RUN MODE ===")
    drive.start_trace()
    drive.blink_led(5, 80)

    route, movement_commands, belief = load_and_plan_route()
    print(f"Optimal cell path ({len(route)} cells): {route}")

    render_object = None
    if HAS_SIM or enable_render:
        real_maze = maze.MazeStructure(*maze.num_file_import(config.DEFAULT_MAZE))
        if HAS_SIM:
            setup.sim.set_sim_maze(real_maze)
        if enable_render:
            render_object = make_renderer(real_maze)

    execute_movement_commands(movement_commands, render_object, belief, route)


if __name__ == "__main__":
    run()
