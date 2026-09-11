"""Speed Run Mode (mode 2) for UKMARS Gemini Micromouse.

Loads the explored belief map, flood-fills the optimal route, and executes the
resulting movement commands. Pico and PC compatible.

This module owns the ROUTE: loading a belief, planning over it, and turning
egocentric verbs into timed drives. It does not own the motors -- `drive.py`
does. Anything that only needs to move a wheel should import `drive`, not this.
"""

import math
import time

import clock
import commands
import config
import drive
import lap_log
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


def execute_movement_commands(movement_commands, render_object=None, belief=None,
                              route=None, drive_power=None, turn_power=None):
    """Execute egocentric movement verbs: F n, L, R, U, H.

    Open loop. Each verb becomes a fixed power held for a computed number of
    seconds, and no encoder is read while it runs. Distance divides by one
    constant speed, so nothing here models the acceleration ramp -- see the
    MAX_WHEEL_SPEED_MMS comment in config.py before trusting a short move.

    `drive_power` and `turn_power` let a mode go slower than a speed run. Duration
    is derived from the power actually used. Be careful what a slow run proves:
    the speed a duty produces is assumed LINEAR in the duty and that has never
    been measured, so a gentle lap misses its distance by more, not less.
    """
    if drive_power is None:
        drive_power = drive.CRUISE_DUTY_POWER
    print(f"Executing movement route: {movement_commands}")

    cruise_speed_mms = drive_power * config.MAX_WHEEL_SPEED_MMS

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

            drive.drive_motors(drive_power, drive_power)
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

            drive.pivot_in_place(quarter_turns, clockwise, render_object, belief,
                                 route, turn_power)

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


def _load_route(route_path, laps):
    """Parse and vet a route file. Returns (verbs, header), or None to refuse.

    Parsing and validation happen BEFORE the motors are armed: a malformed or
    unloopable route must fail at the file, not halfway down a corridor.
    """
    if not maze.file_exists(route_path):
        print("No route at {}. Draw one with sim/route_editor.py, or copy a".format(route_path))
        print("fixture from {} into place.".format(config.ROUTES_DIR))
        return None

    movement_commands = commands.read_command_file(route_path)
    header = commands.read_route_header(route_path)
    print("Route: {} ({} verbs) x {} lap(s)".format(route_path, len(movement_commands), laps))
    print("Verbs: {}".format(movement_commands))
    _report_route_pose(header)

    start_pose = header.get("start")
    if start_pose is None:
        if laps > 1:
            print("No start pose in the header, so the laps cannot be checked.")
            print("  Redraw the route to record one before trusting a lap count.")
        return movement_commands, header

    if "grid" in header:
        outside = commands.leaves_the_grid(movement_commands, start_pose, header["grid"])
        if outside:
            print("REFUSING: this route leaves its own {}x{} grid at {}.".format(
                header["grid"][0], header["grid"][1], outside[0]))
            return None

    if laps > 1 and not commands.returns_to_start(movement_commands, start_pose):
        end_x, end_y, end_heading = commands.walk_route(movement_commands, start_pose)[-1]
        print("REFUSING: {} laps, but this route does not close.".format(laps))
        print("  It starts at ({}, {}) facing {} and ends at ({}, {}) facing {}.".format(
            start_pose[0], start_pose[1], start_pose[2], end_x, end_y, end_heading))
        print("  Lap 2 would set off from the wrong cell and drive into a wall.")
        print("  Extend the route back to its start cell, or use {}/lap3x3.mmc."
              .format(config.ROUTES_DIR))
        return None

    return movement_commands, header


def lap_seconds(movement_commands, drive_power=None, turn_power=None):
    """How long one lap of a route takes, by the same arithmetic that drives it.

    The operator needs this before the motors arm: thirty laps is a walk-away job
    or a stand-and-watch job depending on the number, and a mode that does not say
    which gets run with a flat battery.
    """
    if drive_power is None:
        drive_power = drive.CRUISE_DUTY_POWER
    cruise_speed_mms = drive_power * config.MAX_WHEEL_SPEED_MMS
    total_seconds = 0.0
    for command_string in movement_commands:
        if not command_string or command_string.startswith("#"):
            continue
        parts = command_string.split()
        verb = parts[0]
        if verb == commands.FORWARD:
            total_seconds += int(parts[1]) * config.MM_PER_CELL / cruise_speed_mms
        elif verb in commands.QUARTER_TURNS:
            total_seconds += drive.pivot_seconds(
                abs(commands.QUARTER_TURNS[verb]), turn_power)
        total_seconds += config.INTER_COMMAND_SETTLE_S
    return total_seconds


def _lap_record(lap, started_ms, ticks_before, commanded_deg_per_lap, sample_light):
    """Everything measurable about one finished lap, while the brake is held."""
    ticks = setup.read_encoders()
    deltas = None
    residual_deg = None
    if ticks is not None:
        if ticks_before is not None:
            deltas = (ticks[0] - ticks_before[0], ticks[1] - ticks_before[1])
            turned_mm = (deltas[1] - deltas[0]) * config.MM_PER_TICK
            measured_deg = math.degrees(turned_mm / config.TRACK_WIDTH_MM)
            residual_deg = measured_deg - commanded_deg_per_lap
    return {
        "lap": lap,
        "elapsed_s": clock.elapsed_s(started_ms),
        "ticks": ticks,
        "deltas": deltas,
        "residual_deg": residual_deg,
        "light": lap_log.read_light_sensors() if sample_light else None,
    }


def _abort_requested(seconds):
    """Hold the brake for `seconds`, returning True if a button is pressed.

    The only way to stop a thirty lap run without pulling the battery, so it
    polls rather than sleeping. Either button aborts: mid-run you will not care
    which one you hit.
    """
    waited = 0.0
    step = config.SOAK_ABORT_POLL_S
    while waited < seconds:
        if setup.sw1.value() == 0 or setup.sw2.value() == 0:
            return True
        time.sleep(step)
        waited += step
    return False


def follow(route_path=None, map_path=None, laps=None, enable_render=False,
           log_path=None, sample_light=False, power=None, turn_power=None):
    """Mode 6. Drive a hand-authored .mmc route verbatim, `laps` times.

    No planning happens here. The route comes from a file, so this exercises the
    MOTION layer alone: if the robot ends up somewhere wrong, the planner is not
    a suspect. That is what makes it the useful path-following test.

    Driving a CLOSED route N times is the maze-relevant stress test. Every lap
    should return the robot to its start pose, so the offset after N laps is the
    accumulated open-loop error, and turn error accumulates instead of cancelling.

    With `log_path` every lap is appended to that CSV, and `power` drives the
    whole route slower than a speed run. That is mode 5: see `soak()` below, which
    is this function with the soak defaults.
    """
    if route_path is None:
        route_path = config.SAVED_ROUTE
    if laps is None:
        laps = config.FOLLOW_ROUTE_LAPS

    print("=== STARTING FOLLOW ROUTE MODE ===")
    vetted = _load_route(route_path, laps)
    if vetted is None:
        return None
    movement_commands, header = vetted

    drive.start_trace()
    drive.blink_led(6, 80)

    render_object, real_maze = _sim_world(map_path, enable_render,
                                         grid=header.get("grid"),
                                         start_pose=header.get("start"))

    ticks_before = setup.read_encoders(reset=True)
    if ticks_before is None:
        print("No encoder decoder ({}). Driving blind, no drift figure.".format(
            setup.encoder_error))

    log = None
    if log_path is not None:
        log = lap_log.LapLog(log_path)
        if log.open(note="route={} laps={} start={} placed=cell-centre".format(
                route_path, laps, header.get("start"))):
            print("Logging one row per lap to {}.".format(log.path))
        else:
            print("Could not open {}: {}. Driving without a log.".format(
                log.path, log.error))

    per_lap_s = lap_seconds(movement_commands, power, turn_power)
    total_s = laps * (per_lap_s + config.INTER_LAP_SETTLE_S)
    print("One lap takes {:.1f} s; {} lap(s) is about {:.0f} min {:.0f} s.".format(
        per_lap_s, laps, total_s // 60, total_s % 60))

    commanded_deg_per_lap = -90.0 * commands.net_quarter_turns(movement_commands)
    records = []
    aborted = False

    for lap in range(1, laps + 1):
        if laps > 1:
            print("--- lap {} of {}".format(lap, laps))
        started_ms = clock.now_ms()
        execute_movement_commands(movement_commands, render_object, real_maze, None,
                                  power, turn_power)
        drive.stop_motors()

        record = _lap_record(lap, started_ms, ticks_before, commanded_deg_per_lap,
                             sample_light)
        records.append(record)
        ticks_before = record["ticks"]
        _print_lap(record)
        if log is not None:
            log.record(record["lap"], record["elapsed_s"], record["ticks"],
                       record["deltas"], record["residual_deg"], record["light"])

        if lap < laps:
            if _abort_requested(config.INTER_LAP_SETTLE_S):
                print("ABORTED by button after lap {}.".format(lap))
                aborted = True
                break

    drive.stop_motors()
    if log is not None:
        log.close()
        print("Wrote {} lap row(s) to {}.".format(log.rows_written, log.path))

    _report_drift(len(records), movement_commands, header.get("start"))
    if len(records) > 1:
        _report_laps(records, aborted, laps)
    return movement_commands


def soak(laps=None, route_path=None, map_path=None, enable_render=False, power=None):
    """Mode 5. Drive the saved route `laps` times over, logging every lap.

    The same motion as mode 6, run long and recorded. Thirty laps of a 3x3
    perimeter is about 22 m of driving, which turns a per-move bias too small to
    see into an offset a tape measure reads off the floor.

    It replaced an out-and-back corridor sprint, which reversed along its own arc
    and so cancelled every symmetric error: a 7% distance error overshot going
    out and undershot coming back, and landed on the start line regardless. A lap
    of a route cannot cancel like that, because the turns accumulate too.

    SPEED: it runs at `config.SOAK_DRIVE_POWER`, below the speed-run cruise duty,
    because the first question is whether the robot holds a line at all. Raise it
    with `power=` once it does.

    PLACEMENT: the robot goes at the CENTRE of the route's start cell, facing the
    recorded heading, not back against a wall. Every `F n` divides a whole number
    of cells by one speed, so a half-cell offset at the start is a half-cell
    error on the first move and for the whole run after it.
    """
    if laps is None:
        laps = config.SOAK_LAPS
    if power is None:
        power = config.SOAK_DRIVE_POWER
    turn_power = config.SOAK_TURN_POWER
    print("=== LAP SOAK ({} laps) ===".format(laps))
    print("Drive power {:.2f} (a speed run cruises at {:.2f}); turns at {:.2f}."
          .format(power, drive.CRUISE_DUTY_POWER, turn_power))
    print("Place the robot at the CENTRE of the start cell, not against a wall.")
    print("MARK THE START POSE: both wheel contact points and the heading.")
    print("Press either button between laps to abort.")
    return follow(route_path=route_path, map_path=map_path, laps=laps,
                  enable_render=enable_render, log_path=config.SOAK_LOG_PATH,
                  sample_light=True, power=power, turn_power=turn_power)


def _print_lap(record):
    parts = ["  lap {:2d}  {:5.1f} s".format(record["lap"], record["elapsed_s"])]
    if record["deltas"] is not None:
        parts.append("dL={:+7d} dR={:+7d}".format(*record["deltas"]))
    if record["residual_deg"] is not None:
        parts.append("heading residual {:+5.1f} deg".format(record["residual_deg"]))
    if record["light"] is not None:
        parts.append("light " + " ".join(
            "{}={:+d}".format(name, lit - unlit)
            for (name, _adc, _emitter), (lit, unlit)
            in zip(lap_log.SENSOR_CHANNELS, record["light"])))
    print("  ".join(parts))


def _report_laps(records, aborted, laps):
    """What only a long run can say: does every lap measure the same?"""
    print("")
    print("=== LAP SOAK REPORT ===")
    print("Laps completed: {} of {}{}".format(
        len(records), laps, " (ABORTED)" if aborted else ""))

    residuals = [r["residual_deg"] for r in records if r["residual_deg"] is not None]
    if residuals:
        print("Heading residual per lap: first {:+.1f} deg, last {:+.1f} deg, total {:+.1f} deg"
              .format(residuals[0], residuals[-1], sum(residuals)))
        print("  A residual of the same sign every lap is a mistimed turn, not noise.")

    lap_ticks = [(abs(r["deltas"][0]) + abs(r["deltas"][1])) / 2.0
                 for r in records if r["deltas"] is not None]
    if len(lap_ticks) < 2:
        print("No per-lap encoder data. Measure the floor offset by hand.")
        return

    ordered = sorted(lap_ticks)
    median = ordered[len(ordered) // 2]
    print("Ticks per lap: median {:.0f} ({:.2f} m of wheel travel)".format(
        median, median * config.MM_PER_TICK / 1000.0))

    dropouts = [index + 1 for index, total in enumerate(lap_ticks)
                if total < median * config.SOAK_TICK_DROPOUT_FRACTION]
    if dropouts:
        print("  [!] ENCODER DROPOUT on lap(s) {}: far fewer ticks than the median.".format(
            dropouts))
        print("      This board has a history of intermittent channels, and a soak")
        print("      run is exactly how that fault shows itself.")

    if len(lap_ticks) >= 6:
        first = sum(lap_ticks[:3]) / 3.0
        last = sum(lap_ticks[-3:]) / 3.0
        change = (last / first - 1.0) * 100.0 if first else 0.0
        print("Ticks per lap: first three {:.0f}, last three {:.0f} ({:+.1f}%)".format(
            first, last, change))
        if change < config.SOAK_SLOWDOWN_WARN_PERCENT:
            print("  [!] The robot slowed over the run. Battery sag or a hot motor.")
            print("      Every lap was the same DURATION, so fewer ticks means less")
            print("      distance, and a speed run on a tired battery undershoots.")

    print("")
    print("Now measure the floor: offset from the start mark and the final heading.")
    print("That is the real answer; the encoders only say what the robot BELIEVES.")


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


def _report_drift(laps, movement_commands, start_pose=None):
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
        start_cell = start_pose[:2] if start_pose else config.START_POS
        start_x = (start_cell[0] + 0.5) * config.MM_PER_CELL
        start_y = (start_cell[1] + 0.5) * config.MM_PER_CELL
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
