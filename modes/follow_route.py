"""Mode 5. Drive a hand-authored .mmc route verbatim, `laps` times.

No planning happens here. The route comes from a file, so this exercises the
MOTION layer alone: if the robot ends up somewhere wrong, the planner is not a
suspect. That is what makes it the useful path-following test.

Driving a CLOSED route N times is the maze-relevant stress test. Every lap
should return the robot to its start pose, so the offset after N laps is the
accumulated open-loop error, and turn error accumulates instead of cancelling.

THE SOAK IS THIS MODE WITH DIFFERENT NUMBERS. `--soak` sets `SOAK_LAPS` laps at
`SOAK_DRIVE_POWER` and opens the lap log; that was mode 5 as a separate module,
which drove the same code down the same path and could only differ in its
defaults. Thirty laps of a 3x3 perimeter is about 22 m of driving, which turns a
per-move bias too small to see into an offset a tape measure reads off the floor.

It replaced an out-and-back corridor sprint, which reversed along its own arc and
so cancelled every symmetric error: a 7% distance error overshot going out and
undershot coming back, and landed on the start line regardless. A lap of a route
cannot cancel like that, because the turns accumulate too.

PLACEMENT: the robot goes at the CENTRE of the route's start cell, facing the
recorded heading, not back against a wall. Every `F n` divides a whole number of
cells by one speed, so a half-cell offset at the start is a half-cell error on
the first move and for the whole run after it.
"""

import math
import time

from brain import commands
from brain import maze
from hal import clock
import config
import files
from hal import drive
from record import lap_log
import motion
from hal import setup
import world

HAS_SIM = setup.sim is not None


def _load_route(route_path, laps, retrace=False):
    """Parse and vet a route file. Returns (verbs, header), or None to refuse.

    Parsing and validation happen BEFORE the motors are armed: a malformed or
    unloopable route must fail at the file, not halfway down a corridor.
    """
    if not files.file_exists(route_path):
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

    closes = commands.returns_to_start(movement_commands, start_pose)

    if retrace and not closes:
        movement_commands = commands.with_return_leg(movement_commands, start_pose)
        print("RETRACING: U-turn at the end, the path walked backwards, U-turn home.")
        print("  Lap is now {} verbs: {}".format(len(movement_commands), movement_commands))
        print("  A retrace cancels its own symmetric error -- an equal shortfall each")
        print("  way subtracts, and every right turn out is a left turn back. The two")
        print("  U-turns are what accumulates, so this measures pivots above all.")
        closes = commands.returns_to_start(movement_commands, start_pose)
    elif retrace:
        print("Route already returns to its start pose; no return leg added.")

    if laps > 1 and not closes:
        end_x, end_y, end_heading = commands.walk_route(movement_commands, start_pose)[-1]
        print("REFUSING: {} laps, but this route does not close.".format(laps))
        print("  It starts at ({}, {}) facing {} and ends at ({}, {}) facing {}.".format(
            start_pose[0], start_pose[1], start_pose[2], end_x, end_y, end_heading))
        print("  Lap 2 would set off from the wrong cell and drive into a wall.")
        print("  Three ways on: pass retrace=True (--retrace) to drive it out and")
        print("  back, extend the route to its start cell in the editor, or use")
        print("  {}/lap3x3_via_centre.mmc.".format(config.ROUTES_DIR))
        return None

    return movement_commands, header


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


def run(route_path=None, map_path=None, laps=None, enable_render=False,
        log_path=None, sample_light=False, power=None, turn_power=None,
        retrace=False, soak=False):
    """Drive the route `laps` times. See the module docstring for what it measures.

    `soak=True` (`--soak`) is the long recorded version: `SOAK_LAPS` laps at
    `SOAK_DRIVE_POWER`, every lap appended to `SOAK_LOG_PATH`, and the light
    sensors sampled. An explicit `laps` or `power` still wins over the preset, so
    a short soak is one flag away.

    `retrace` closes an open route by driving it out and back instead of refusing
    it. Read `commands.with_return_leg` before trusting what that measures.
    """
    if soak:
        if laps is None:
            laps = config.SOAK_LAPS
        if power is None:
            power = config.SOAK_DRIVE_POWER
        if turn_power is None:
            turn_power = config.SOAK_TURN_POWER
        if log_path is None:
            log_path = config.SOAK_LOG_PATH
        sample_light = True
    if route_path is None:
        route_path = config.SAVED_ROUTE
    if laps is None:
        laps = config.FOLLOW_ROUTE_LAPS

    if soak:
        print("=== LAP SOAK ({} laps) ===".format(laps))
        print("Drive power {:.2f} (a speed run cruises at {:.2f}); turns at {:.2f}."
              .format(power, drive.CRUISE_DUTY_POWER, turn_power))
        print("MARK THE START POSE: both wheel contact points and the heading.")
        print("Press either button between laps to abort.")
    else:
        print("=== STARTING FOLLOW ROUTE MODE ===")
    print("Place the robot at the CENTRE of the start cell, not against a wall.")
    vetted = _load_route(route_path, laps, retrace)
    if vetted is None:
        return None
    movement_commands, header = vetted

    drive.start_trace()
    drive.blink_led(5, 80)

    render_object, real_maze = world.sim_world(map_path, enable_render,
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

    per_lap_s = motion.lap_seconds(movement_commands, power, turn_power)
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
        motion.execute(movement_commands, render_object, real_maze, None,
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
