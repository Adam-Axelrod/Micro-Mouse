"""Speed Run Mode (mode 2) for UKMARS Gemini Micromouse.

Loads the explored belief map, flood-fills the optimal route, and executes the
resulting movement commands. Pico and PC compatible.

This module owns the ROUTE: loading a belief, planning over it, and turning
egocentric verbs into timed drives. It does not own the motors -- `drive.py`
does. Anything that only needs to move a wheel should import `drive`, not this.
"""

import math

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


def _sim_world(map_path=None, enable_render=False, grid=None, start_pose=None):
    """Load the maze the sim and the renderer should use.

    Returns (render_object, real_maze); either may be None. The maze comes back
    as well as the renderer because a caller with no belief map of its own still
    has to give the renderer something to draw.

    With no map file but a `grid`, the world is a blank grid of that size. A
    hand-drawn 3x3 route has no maze file behind it, and drawing it on the 16x16
    default would put the mouse in the wrong world entirely.
    """
    if not (HAS_SIM or enable_render):
        return None, None
    if map_path:
        real_maze = maze.MazeStructure(*maze.num_file_import(map_path))
    elif grid:
        real_maze = maze.MazeStructure(cols=grid[0], rows=grid[1])
    else:
        real_maze = maze.MazeStructure(*maze.num_file_import(config.DEFAULT_MAZE))
    if HAS_SIM:
        setup.sim.set_sim_maze(real_maze)
        if start_pose is not None:
            _place_sim_mouse(start_pose)
    return (make_renderer(real_maze) if enable_render else None), real_maze


def _place_sim_mouse(start_pose):
    """Put the simulated mouse in the middle of `start_pose`'s cell, facing it.

    The sim always begins at (0, 0) facing north. A route drawn from anywhere
    else would replay from the wrong square, which looks like a drive bug.
    """
    x, y, heading = start_pose
    setup.sim.get_mouse_state().reset_pose(
        (x + 0.5) * config.MM_PER_CELL,
        (y + 0.5) * config.MM_PER_CELL,
        config.HEADING_RADIANS[heading])


def follow(route_path=None, map_path=None, laps=None, enable_render=False):
    """Mode 6. Drive a hand-authored .mmc route verbatim, `laps` times.

    No planning happens here. The route comes from a file, so this exercises the
    MOTION layer alone: if the robot ends up somewhere wrong, the planner is not
    a suspect. That is what makes it the useful path-following test.

    Driving a CLOSED route N times is the maze-relevant stress test. Every lap
    should return the robot to its start pose, so the offset after N laps is the
    accumulated open-loop error -- and unlike mode 5's corridor sprint, the turn
    error accumulates too instead of cancelling.
    """
    if route_path is None:
        route_path = config.SAVED_ROUTE
    if laps is None:
        laps = config.FOLLOW_ROUTE_LAPS

    print("=== STARTING FOLLOW ROUTE MODE ===")
    if not maze.file_exists(route_path):
        print("No route at {}. Draw one with sim/route_editor.py, or copy a".format(route_path))
        print("fixture from {} into place.".format(config.ROUTES_DIR))
        return None

    # Parsed and validated BEFORE the motors are armed: a malformed route must
    # fail at the file, not halfway down a corridor.
    movement_commands = commands.read_command_file(route_path)
    header = commands.read_route_header(route_path)
    print("Route: {} ({} verbs) x {} lap(s)".format(route_path, len(movement_commands), laps))
    print("Verbs: {}".format(movement_commands))
    _report_route_pose(header)

    if laps > 1 and not commands.closes_the_loop(movement_commands):
        print("WARNING: this route ends {} quarter turn(s) off its start heading.".format(
            commands.net_quarter_turns(movement_commands) % 4))
        print("  Lap 2 will set off in the wrong direction. Append a closing turn")
        print("  to the route file before using it as a drift test.")

    drive.start_trace()
    drive.blink_led(6, 80)

    render_object, real_maze = _sim_world(map_path, enable_render,
                                          grid=header.get("grid"),
                                          start_pose=header.get("start"))

    ticks_before = setup.read_encoders(reset=True)
    if ticks_before is None:
        print("No encoder decoder ({}). Driving blind, no drift figure.".format(
            setup.encoder_error))

    for lap in range(laps):
        if laps > 1:
            print("--- lap {} of {}".format(lap + 1, laps))
        execute_movement_commands(movement_commands, render_object, real_maze, None)

        ticks = setup.read_encoders()
        if ticks is not None:
            print("    ticks so far: left {:+}, right {:+}  ({:.0f} mm / {:.0f} mm)".format(
                ticks[0], ticks[1], ticks[0] * config.MM_PER_TICK, ticks[1] * config.MM_PER_TICK))
        if lap + 1 < laps:
            drive.stop_motors()
            drive.run_motion_for(config.INTER_LAP_SETTLE_S, render_object)

    drive.stop_motors()
    _report_drift(laps, movement_commands)
    return movement_commands


def _report_route_pose(header):
    """Say where the robot has to be placed before this route means anything.

    .mmc verbs are egocentric, so the route is only correct from the pose it was
    drawn from. A file written before the header existed says nothing, and the
    operator is told that rather than given a guess.
    """
    if "start" not in header:
        print("Route carries no start pose. Place the robot in cell {} facing {}"
              .format(config.START_POS, config.ROUTE_EDITOR_START_HEADING))
        print("  (the assumed default) or redraw the route to record one.")
        return
    x, y, heading = header["start"]
    print("Place the robot in cell ({}, {}) facing {}.".format(x, y, heading))
    if "goal" in header:
        print("  It should finish in cell {}.".format(header["goal"]))
    if "grid" in header:
        print("  Drawn on a {}x{} grid ({}).".format(
            header["grid"][0], header["grid"][1], header.get("maze", "unnamed")))


def _report_drift(laps, movement_commands):
    """Say where the run ended up, by whichever measure is available.

    The wheel differential is TOTAL TURNING, not error: a lap with four right
    turns differentially counts a full 360 whether or not it drove accurately.
    So the honest figure is the residual against what the route asked for.
    """
    ticks = setup.read_encoders()
    if ticks is not None:
        left_mm = ticks[0] * config.MM_PER_TICK
        right_mm = ticks[1] * config.MM_PER_TICK
        print("Encoders over {} lap(s): left {:+.0f} mm, right {:+.0f} mm.".format(
            laps, left_mm, right_mm))

        measured_deg = math.degrees((right_mm - left_mm) / config.TRACK_WIDTH_MM)
        commanded_deg = -90.0 * commands.net_quarter_turns(movement_commands) * laps
        print("  turning: commanded {:+.0f} deg, encoders say {:+.0f} deg".format(
            commanded_deg, measured_deg))
        print("  HEADING RESIDUAL: {:+.1f} deg over {} lap(s)".format(
            measured_deg - commanded_deg, laps))

    if HAS_SIM:
        state = setup.sim.get_mouse_state()
        start_x = start_y = config.MM_PER_CELL / 2.0
        print("Sim pose: x {:.0f} mm, y {:.0f} mm, heading {:.1f} deg".format(
            state.x_mm, state.y_mm, math.degrees(state.heading_radians)))
        print("  offset from start: {:.0f} mm".format(
            ((state.x_mm - start_x) ** 2 + (state.y_mm - start_y) ** 2) ** 0.5))
        print("  (the sim has no acceleration ramp, so its offset is optimistic)")


def run(enable_render=False):
    """Run speed run mode."""
    print("=== STARTING SPEED RUN MODE ===")
    drive.start_trace()
    drive.blink_led(5, 80)

    route, movement_commands, belief = load_and_plan_route()
    print(f"Optimal cell path ({len(route)} cells): {route}")

    render_object, _real_maze = _sim_world(enable_render=enable_render)

    execute_movement_commands(movement_commands, render_object, belief, route)


if __name__ == "__main__":
    run()
