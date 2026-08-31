"""Speed Run Mode for UKMARS Gemini Micromouse.

Loads explored belief map, flood-fills optimal route, and executes movement commands.
Pico and PC compatible.
"""

import math
import time
import commands
import config
import maze
import motor_log
import search_algorithms
import setup

# Optional PC-only Pygame renderer imports
try:
    import geometry
    from renderer import Renderer
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False

HAS_SIM = setup.sim is not None

CRUISE_DUTY_POWER = config.CRUISE_DUTY_POWER
TURN_DUTY_POWER = config.TURN_DUTY_POWER
RENDER_EVERY_N_STEPS = 4

MOTOR_TRACE = motor_log.MotorLog(
    config.MOTOR_LOG_PATH,
    clock_ms=setup.sim.sim_time_ms if setup.sim is not None else None,
)


def blink_led(times, on_duration_ms=80, off_duration_ms=80):
    for _ in range(times):
        setup.LED_PIN.value(1)
        time.sleep(on_duration_ms / 1000.0)
        setup.LED_PIN.value(0)
        time.sleep(off_duration_ms / 1000.0)


def drive_motors(left_power, right_power):
    """Active-low driver for dual PWM channels per motor: power in [-1.0, 1.0]."""
    left_p = max(-1.0, min(1.0, left_power))
    right_p = max(-1.0, min(1.0, right_power))

    MOTOR_TRACE.record(left_p, right_p)

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


def run_motion_for(duration_seconds, render_object=None, belief=None, route=None):
    """Let time pass while the motors drive."""
    if not HAS_SIM:
        time.sleep(duration_seconds)
        return

    dt = config.SIM_TIMESTEP_S
    # Whole steps plus the leftover. Rounding to whole steps instead put a
    # systematic error on every short move -- a 0.216 s pivot became 0.22 s and
    # turned 91.6 degrees -- which would show up as sim/hardware divergence that
    # the hardware had not actually caused.
    total_steps = int(duration_seconds / dt)
    remainder = duration_seconds - total_steps * dt
    for step_index in range(total_steps):
        setup.sim.step_sim_physics(dt)
        if render_object is not None and (
            step_index % RENDER_EVERY_N_STEPS == 0 or step_index == total_steps - 1
        ):
            render_object.draw(belief=belief, mouse=setup.sim.get_mouse_state(), path=route)

    if remainder > 0.0:
        setup.sim.step_sim_physics(remainder)


def pivot_in_place(quarter_turns, clockwise=True, render_object=None, belief=None, route=None):
    """Spin on the spot through `quarter_turns` x 90 degrees.

    The power is FIXED at TURN_DUTY_POWER and only the duration scales with the
    angle. Scaling both is what made a U-turn rotate 360 degrees: it drove at
    2 x TURN_DUTY_POWER, so it spun twice as fast for the time a 180 needed at
    the base rate. Corrected 2026-08-31.
    """
    pivot_rate_rads = 2.0 * TURN_DUTY_POWER * config.MAX_WHEEL_SPEED_MMS / config.TRACK_WIDTH_MM
    pivot_time_seconds = (math.pi / 2.0) * quarter_turns / pivot_rate_rads

    sign = 1.0 if clockwise else -1.0
    drive_motors(sign * TURN_DUTY_POWER, -sign * TURN_DUTY_POWER)
    run_motion_for(pivot_time_seconds, render_object, belief, route)
    stop_motors()


def execute_movement_commands(movement_commands, render_object=None, belief=None, route=None):
    """Execute egocentric movement verbs: F n, L, R, U, H."""
    print(f"Executing movement route: {movement_commands}")

    cruise_speed_mms = CRUISE_DUTY_POWER * config.MAX_WHEEL_SPEED_MMS

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
            # quarter turns, and which way round. A U-turn takes the same
            # direction as R; on the spot either way lands the same heading.
            if verb == "L":
                quarter_turns, clockwise = 1, False
            elif verb == "R":
                quarter_turns, clockwise = 1, True
            else:
                quarter_turns, clockwise = 2, True

            pivot_in_place(quarter_turns, clockwise, render_object, belief, route)

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


def run(enable_render=False):
    """Run speed run mode."""
    print("=== STARTING SPEED RUN MODE ===")
    blink_led(5, on_duration_ms=80, off_duration_ms=80)

    route, movement_commands, belief = load_and_plan_route()
    print(f"Optimal cell path ({len(route)} cells): {route}")

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


if __name__ == "__main__":
    run()
