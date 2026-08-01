"""Main Entry Point for UKMARS Gemini Micromouse.

Unified control loop running on both Raspberry Pi Pico 2 W and PC simulation.
Supports headless execution as well as optional Pygame desktop rendering (`python3 main.py --render`).
With no arguments (and no button pressed) the mode is Speed Run -- the same way
the Pico interprets an argument-less boot; pass `--step` for the step-by-step
exploration solve instead.
"""

import math
import os
import sys
import time

# Ensure package directory is on sys.path so PC imports work from any cwd.
# MicroPython has no os.path (AttributeError); the Pico runs from root, where
# sys.path already resolves the package modules.
try:
    PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
    if PACKAGE_DIR not in sys.path:
        sys.path.insert(0, PACKAGE_DIR)
except AttributeError:
    pass

import commands
import config
import maze
import motor_log
import search_algorithms
import setup
from explorer import Explorer

# Optional Pygame desktop renderer (PC only; geometry is PC-only too, so it
# lives under the same guard rather than at top level, keeping main.py Pico-safe)
try:
    import geometry
    from renderer import Renderer
    HAS_PYGAME = True
    RENDER_IMPORT_ERROR = None
except ImportError as exc:
    HAS_PYGAME = False
    RENDER_IMPORT_ERROR = str(exc)

# The platform probe and the sim import both live in setup.py (the hardware
# boundary, per the architectural tree): setup.sim is the simulation engine on
# PC and None on the Pico. main.py imports identically on both platforms.
HAS_SIM = setup.sim is not None

CRUISE_DUTY_POWER = config.CRUISE_DUTY_POWER
TURN_DUTY_POWER = config.TURN_DUTY_POWER

# Draw at most one frame per this many physics steps, so the renderer samples the
# sim instead of pacing it (invariant 3: the renderer never gates physics).
RENDER_EVERY_N_STEPS = 4

# Motor trace. Inactive until main() starts it, so importing main writes nothing
# and drive_motors stays usable from tests and the REPL.
#
# Timestamps come from whichever clock actually advances during a drive: on the
# Pico run_motion_for sleeps, so the wall clock is right; on PC it steps physics
# instead, so wall time barely moves and the sim's own clock is the only honest
# source. Getting this wrong stamps an entire run on one millisecond.
MOTOR_TRACE = motor_log.MotorLog(
    config.MOTOR_LOG_PATH,
    clock_ms=setup.sim.sim_time_ms if setup.sim is not None else None,
)


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

    # Trace the clamped boundary values -- what was actually commanded, not what
    # the caller asked for. No-op unless the trace was started.
    MOTOR_TRACE.record(left_p, right_p)

    # Active-low: to drive a channel, PWM it LOW (duty toward 0); hold the other
    # channel OFF (65535). Positive power drives the Fwd channel. Polarity is
    # provisional until HW-1 bench-confirms the pin-pair wiring on the real board.
    maxspeed = 65535
    if left_p >= 0:
        setup.leftRev.duty_u16(maxspeed)
        setup.leftFwd.duty_u16(int(maxspeed * (1.0 - left_p)))
    else:
        setup.leftFwd.duty_u16(maxspeed)
        setup.leftRev.duty_u16(int(maxspeed * (1.0 - abs(left_p))))

    if right_p >= 0:
        setup.rightRev.duty_u16(maxspeed)
        setup.rightFwd.duty_u16(int(maxspeed * (1.0 - right_p)))
    else:
        setup.rightFwd.duty_u16(maxspeed)
        setup.rightRev.duty_u16(int(maxspeed * (1.0 - abs(right_p))))


def stop_motors():
    MOTOR_TRACE.record(0.0, 0.0)
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


def run_motion_for(duration_seconds, render_object=None, belief=None, route=None):
    """Let time pass while the motors do their thing.

    On hardware (or without the sim) this is a plain sleep. On PC, sim time only
    advances via step_sim_physics, so slice the duration into dt steps and,
    when rendering, echo the sim's continuous pose each step. The renderer is a
    pure observer here: it samples MouseState, it never influences the physics.
    """
    if not HAS_SIM:
        time.sleep(duration_seconds)
        return

    dt = config.SIM_TIMESTEP_S
    total_steps = max(1, round(duration_seconds / dt))
    for step_index in range(total_steps):
        setup.sim.step_sim_physics(dt)
        # Sample the sim for display every Nth step (and always on the last one),
        # rather than once per step: physics rate must not follow the frame rate.
        if render_object is not None and (
            step_index % RENDER_EVERY_N_STEPS == 0 or step_index == total_steps - 1
        ):
            render_object.draw(belief=belief, mouse=setup.sim.get_mouse_state(), path=route)


def execute_movement_commands(movement_commands, render_object=None, belief=None, route=None):
    """Execute egocentric movement verbs: F n, L, R, U, H.

    Open-loop timed drive: durations are derived from the config motor model
    (duty x MAX_WHEEL_SPEED_MMS), not measured. Good enough to follow a route in
    sim; the real robot needs encoder/PD closed-loop control (SIM-8, LOC) to hold
    these numbers on carpet.
    """
    print(f"Executing movement route: {movement_commands}")

    cruise_speed_mms = CRUISE_DUTY_POWER * config.MAX_WHEEL_SPEED_MMS
    # Pivot: wheels counter-rotate, so omega = 2 * wheel_speed / track_width
    pivot_rate_rads = 2.0 * TURN_DUTY_POWER * config.MAX_WHEEL_SPEED_MMS / config.TRACK_WIDTH_MM

    for command_string in movement_commands:
        if not command_string or command_string.startswith("#"):
            continue

        parts = command_string.split()
        verb = parts[0]
        arg = int(parts[1]) if len(parts) > 1 else None

        if verb == "F":
            cells_to_drive = arg
            target_distance_mm = cells_to_drive * config.MM_PER_CELL
            drive_time_seconds = target_distance_mm / cruise_speed_mms

            drive_motors(CRUISE_DUTY_POWER, CRUISE_DUTY_POWER)
            run_motion_for(drive_time_seconds, render_object, belief, route)
            stop_motors()

        elif verb in ("L", "R", "U"):
            if verb == "L":
                turn_direction = -1.0
            elif verb == "R":
                turn_direction = 1.0
            else:
                turn_direction = 2.0

            pivot_time_seconds = (math.pi / 2.0) * abs(turn_direction) / pivot_rate_rads
            drive_motors(turn_direction * TURN_DUTY_POWER, -turn_direction * TURN_DUTY_POWER)
            run_motion_for(pivot_time_seconds, render_object, belief, route)
            stop_motors()

        elif verb == "H":
            stop_motors()
            print("Route completed successfully!")
            break

        run_motion_for(0.1, render_object, belief, route)


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


def run_exploration_mode(enable_render=False, save_belief_path=None):
    print("=== STARTING EXPLORATION MODE ===")
    blink_led(3, on_duration_ms=150, off_duration_ms=150)

    real_maze = maze.MazeStructure(*maze.num_file_import(config.DEFAULT_MAZE))
    
    if HAS_SIM:
        setup.sim.set_sim_maze(real_maze)

    belief = maze.MazeStructure(cols=real_maze.cols, rows=real_maze.rows)
    explorer_robot = Explorer(belief_map=belief)

    render_object = None
    if HAS_PYGAME and enable_render:
        try:
            render_object = Renderer(geometry.MazeGeometry(real_maze))
        except Exception as exc:
            print(f"Renderer init failed ({type(exc).__name__}: {exc}); continuing without rendering.")
            render_object = None

    # The planned route is held across ticks and only re-planned when an
    # observation actually invalidates it (a wall now crosses one of its steps).
    # Flooding every tick recomputed an identical answer from an unchanged belief.
    route = []

    while not explorer_robot.at_goal():
        sensed_walls = read_walls(real_maze, explorer_robot.pos)
        explorer_robot.observe(explorer_robot.pos, sensed_walls)

        # Drop the part of the route already walked, then test what remains.
        if explorer_robot.pos in route:
            route = route[route.index(explorer_robot.pos):]
        else:
            route = []

        replanned = len(route) < 2 or not search_algorithms.route_is_open(
            explorer_robot.belief_map, route
        )
        if replanned:
            route = search_algorithms.flood_fill(
                explorer_robot.belief_map, explorer_robot.pos
            )

        if render_object is not None:
            mouse_st = setup.sim.get_mouse_state() if HAS_SIM else None
            render_object.draw(
                belief=explorer_robot.belief_map,
                mouse=mouse_st,
                path=route,
                done=explorer_robot.path_done,
                animate=replanned
            )

        if len(route) < 2:
            break

        explorer_robot.path_to_execute = [route[1]]
        while explorer_robot.path_to_execute:
            explorer_robot.step()
            if HAS_SIM:
                setup.sim.step_sim_physics(delta_time_seconds=0.01)

    if save_belief_path is None:
        save_belief_path = config.SAVED_BELIEF_MAZE

    maze.num_file_export(save_belief_path, explorer_robot.belief_map.cells)
    print(f"Exploration finished! Grid belief map saved to: {save_belief_path}")

    return explorer_robot


def run_speed_run_mode(enable_render=False):
    print("=== STARTING SPEED RUN MODE ===")
    blink_led(5, on_duration_ms=80, off_duration_ms=80)

    route, movement_commands, belief = load_and_plan_route()
    print(f"Optimal cell path ({len(route)} cells): {route}")

    # Ground truth is a sim/render-only referee: sim physics/sensors act against
    # it and the renderer draws its geometry (walls shaded by the explored belief).
    # On hardware the real maze is the physical one, so it is never read from a
    # file -- groundtruth.num is not deployed to the Pico. Load it only when
    # something will actually consume it.
    render_object = None
    want_render = HAS_PYGAME and enable_render
    if HAS_SIM or want_render:
        real_maze = maze.MazeStructure(*maze.num_file_import(config.DEFAULT_MAZE))
        if HAS_SIM:
            setup.sim.set_sim_maze(real_maze)
        if want_render:
            try:
                render_object = Renderer(geometry.MazeGeometry(real_maze))
            except Exception as exc:
                print(f"Renderer init failed ({type(exc).__name__}: {exc}); continuing without rendering.")

    execute_movement_commands(movement_commands, render_object, belief, route)


def main():
    enable_render = "--render" in sys.argv or "-r" in sys.argv
    step_mode_requested = "--step" in sys.argv

    # Trace motor commands whenever there is no sim to watch -- i.e. always on the
    # Pico, which is the run that is otherwise invisible. On PC it is opt-in
    # (`--log`), since the sim can already be observed live.
    want_trace = (not HAS_SIM) or "--log" in sys.argv
    if want_trace:
        MOTOR_TRACE.start()
        print(f"[Motor trace -> {config.MOTOR_LOG_PATH}]")

    stop_motors()

    print("Maze Mouse Ready. Press LEFT button for Exploration, RIGHT button for Speed Run.")
    if enable_render:
        print("[Rendering Enabled via CLI argument]")
        if not HAS_PYGAME:
            print(f"  ...but the renderer failed to import ({RENDER_IMPORT_ERROR}); running headless.")

    blink_led(2, on_duration_ms=200, off_duration_ms=200)

    left_button_pressed = (setup.leftButton.value() == 0)
    right_button_pressed = (setup.rightButton.value() == 0)

    try:
        if step_mode_requested or left_button_pressed:  # --step is the PC's left button
            run_exploration_mode(enable_render=enable_render)
        elif right_button_pressed:
            run_speed_run_mode(enable_render=enable_render)
        else:
            print("No button pressed. Defaulting to Speed Run mode.")
            run_speed_run_mode(enable_render=enable_render)
    finally:
        # Close the trace even if the run dies mid-route: a crashed run is
        # exactly the one worth replaying.
        if want_trace:
            MOTOR_TRACE.close()
            print(f"[Motor trace: {MOTOR_TRACE.records_written} records]")


if __name__ == "__main__":
    main()
