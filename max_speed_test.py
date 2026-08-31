"""Max speed test (mode 4) for the UKMARS Gemini micromouse.

`MAX_WHEEL_SPEED_MMS` has never been measured. Every open-loop `F n` duration
divides by it, so every distance the robot drives inherits its error. This mode
measures it: one straight dash at full duty over a marked distance, then a hard
brake.

The operator is the instrument. Mark a 5 m line on the floor, put a stopwatch on
the run, and read the speed off the wall:

    real speed (mm/s) = marked distance (mm) / stopwatch seconds

The commanded duration comes from the provisional constant, so the robot stops
where the constant SAYS 5.2 m is. The gap between that point and the real 5.2 m
mark measures the same error a second time. Two independent readings of one
number, from one run.

Beware the circular case: on the PC the sim both plans and simulates with
MAX_WHEEL_SPEED_MMS, so a sim run always lands exactly on target. That proves
the arithmetic and nothing about the chassis. Only the floor run is evidence.

    On the Pico, from the REPL:

        import max_speed_test
        max_speed_test.run()                      # 5.2 m at full duty
        max_speed_test.run(distance_mm=3000)      # shorter dash
        max_speed_test.run(power=0.55)            # at cruise duty instead

Every run appends a row to `max_speed_test.csv` on the Pico's filesystem.
"""

import math
import time

import config
import maze
import setup
import speed_run

HAS_SIM = setup.sim is not None

# Where "now" comes from. The Pico really sleeps through the dash, so the wall
# clock times it. The PC steps physics instead and its wall clock barely moves,
# so in the sim the sim's own clock is the only one that means anything.
if HAS_SIM:
    _now_ms = setup.sim.sim_time_ms
elif hasattr(time, "ticks_ms"):
    _now_ms = time.ticks_ms
else:
    def _now_ms():
        return int(time.monotonic() * 1000.0)

if hasattr(time, "ticks_diff") and not HAS_SIM:
    _diff_ms = time.ticks_diff
else:
    def _diff_ms(new_ms, old_ms):
        return new_ms - old_ms


LOG_FORMAT_VERSION = 2
LOG_HEADER = "# micromouse max speed test v{}\n".format(LOG_FORMAT_VERSION)
LOG_COLUMNS = ("power,assumed_speed_mms,target_distance_mm,commanded_s,measured_s,"
               "left_ticks,right_ticks\n")

# Ticks over the last dash, so calibrate() can be called from the REPL after the
# tape has been read. None until a run has happened. Lost on reset, which is why
# the numbers also go to the log file.
LAST_RUN = None

# How far the tick-derived diameter may sit from the ruler before it means
# something. Covers tyre compression and tape-reading slop; anything past it is
# the decoder miscounting.
ENCODER_TOLERANCE = 0.02


def _blink(times, on_ms, off_ms=None):
    off_ms = on_ms if off_ms is None else off_ms
    for _ in range(times):
        setup.LED_PIN.value(1)
        time.sleep(on_ms / 1000.0)
        setup.LED_PIN.value(0)
        time.sleep(off_ms / 1000.0)


def _append_log_row(row_text):
    """Append one result row, writing the header first if the file is new."""
    is_new = not maze.file_exists(config.MAX_SPEED_LOG_PATH)
    try:
        with open(config.MAX_SPEED_LOG_PATH, "a") as file_handle:
            if is_new:
                file_handle.write(LOG_HEADER)
                file_handle.write(LOG_COLUMNS)
            file_handle.write(row_text)
    except OSError as exc:
        # A full or read-only filesystem must not cost us the run we just did.
        print("Could not write {}: {}".format(config.MAX_SPEED_LOG_PATH, exc))


def plan(distance_mm=None, power=None):
    """Return (distance_mm, power, assumed_speed_mms, commanded_seconds).

    The duration is what the provisional constant claims the distance takes. It
    is capped by MAX_SPEED_TEST_MAX_DURATION_S so a bad argument cannot leave the
    motors running across the room.
    """
    if distance_mm is None:
        distance_mm = config.MAX_SPEED_TEST_DISTANCE_MM
    if power is None:
        power = config.MAX_SPEED_TEST_POWER

    power = max(0.0, min(1.0, power))
    if power <= 0.0:
        raise ValueError("power must be above 0 to move")

    assumed_speed_mms = power * config.MAX_WHEEL_SPEED_MMS
    commanded_seconds = distance_mm / assumed_speed_mms
    capped_seconds = min(commanded_seconds, config.MAX_SPEED_TEST_MAX_DURATION_S)
    if capped_seconds < commanded_seconds:
        print("Duration capped at {:.1f} s by MAX_SPEED_TEST_MAX_DURATION_S.".format(capped_seconds))

    return distance_mm, power, assumed_speed_mms, capped_seconds


def run(distance_mm=None, power=None, enable_render=False):
    """Drive one straight dash at full duty, brake hard, and report the timing."""
    distance_mm, power, assumed_speed_mms, commanded_seconds = plan(distance_mm, power)

    print("=== MAX SPEED TEST ===")
    print("Clear a straight lane of at least {:.2f} m.".format((distance_mm + 500.0) / 1000.0))
    print("Target distance : {:.0f} mm".format(distance_mm))
    print("Motor power     : {:.2f} of full duty".format(power))
    print("Assumed speed   : {:.0f} mm/s  (config.MAX_WHEEL_SPEED_MMS = {:.0f})".format(
        assumed_speed_mms, config.MAX_WHEEL_SPEED_MMS))
    print("Commanded drive : {:.2f} s".format(commanded_seconds))
    print("LED solid ON = moving. Start the stopwatch on the light.")

    # Arming signature: four fast blinks, the mode number, so the operator can
    # confirm mode 4 is what SW2 actually launched.
    _blink(4, 80)
    time.sleep(0.5)
    _blink(config.MAX_SPEED_TEST_COUNTDOWN_BLINKS,
            config.MAX_SPEED_TEST_COUNTDOWN_MS,
            config.MAX_SPEED_TEST_COUNTDOWN_MS)

    # Zero the encoders at the start line. None means no decoder, which is the
    # normal case on this board today; the dash still runs and still times.
    ticks_before = setup.read_encoders(reset=True)
    if ticks_before is None:
        print("No encoder decoder ({}). Timing only, no tick capture.".format(
            setup.encoder_error))

    setup.LED_PIN.value(1)
    start_ms = _now_ms()

    speed_run.drive_motors(power, power)
    speed_run.run_motion_for(commanded_seconds)
    speed_run.stop_motors()

    measured_seconds = _diff_ms(_now_ms(), start_ms) / 1000.0
    setup.LED_PIN.value(0)

    # Both channels at 65535 is a brake, not a coast (bench-confirmed, BT-3).
    # Hold it long enough that the robot has really stopped before we report.
    time.sleep(config.MAX_SPEED_TEST_BRAKE_HOLD_S)

    # Read after the brake has settled, so the ticks cover the coast-down too and
    # match the distance the tape will show.
    ticks_after = setup.read_encoders()
    left_ticks, right_ticks = ticks_after if ticks_after is not None else (0, 0)

    _blink(2, 400, 400)

    global LAST_RUN
    LAST_RUN = {
        "power": power,
        "target_distance_mm": distance_mm,
        "commanded_s": commanded_seconds,
        "measured_s": measured_seconds,
        "left_ticks": left_ticks,
        "right_ticks": right_ticks,
        "has_ticks": ticks_after is not None,
    }

    print("Drive finished. Commanded {:.2f} s, motors ran {:.2f} s.".format(
        commanded_seconds, measured_seconds))
    if ticks_after is not None:
        print("Encoder ticks: left {:+}, right {:+}.".format(left_ticks, right_ticks))

    print("")
    print("Now read the floor, then call calibrate() with what you measured:")
    print("    import max_speed_test")
    print("    max_speed_test.calibrate(travelled_mm=<nose to nose>, stopwatch_s=<t>)")
    print("  travelled_mm = start line to where the nose actually stopped")
    print("  stopwatch_s  = your time over the 5.00 m mark (marked_mm, default 5000)")

    _append_log_row("{:.2f},{:.1f},{:.0f},{:.3f},{:.3f},{},{}\n".format(
        power, assumed_speed_mms, distance_mm, commanded_seconds, measured_seconds,
        left_ticks, right_ticks))

    if HAS_SIM:
        state = setup.sim.get_mouse_state()
        print("Sim travelled {:.0f} mm (circular: the sim uses the same constant).".format(
            state.y_mm - config.MM_PER_CELL / 2.0))

    return commanded_seconds, measured_seconds


def calibrate(travelled_mm=None, stopwatch_s=None, marked_mm=5000.0,
              left_ticks=None, right_ticks=None):
    """Turn the tape and the stopwatch into constants for config.py.

    Two independent results out of one dash:

      MAX_WHEEL_SPEED_MMS, from the stopwatch over the marked distance. This is
      GROUND speed and it owes nothing to any constant already in config.py,
      which is what makes it the reference the others are checked against.

      An encoder integrity check, from the ticks over the distance the robot
      really covered. Both constants it leans on are known: counts per wheel
      revolution is a designed integer (edges per shaft revolution times gear
      ratio) and WHEEL_DIAMETER_MM is ruler-confirmed at 32 mm. So the implied
      diameter should land within a percent or two of 32. Read a miss as a
      verdict on the encoder, not as a new measurement of the wheel.

      The implied diameter is travelled x counts_per_rev / ticks, so it moves
      OPPOSITE to the tick count:

        above 32  = too few ticks. Dropped edges, which is this board's known
                    fault, or drag, or an overstated distance.
        below 32  = too many ticks. A wheel spun without carrying the robot,
                    or the tyre is compressing (worth only tenths of a mm).

    Ticks default to the last run in this session. Pass them by hand to work
    from a row of max_speed_test.csv instead.
    """
    if left_ticks is None or right_ticks is None:
        if LAST_RUN is None:
            raise ValueError("no run in this session; pass left_ticks and right_ticks")
        if left_ticks is None:
            left_ticks = LAST_RUN["left_ticks"]
        if right_ticks is None:
            right_ticks = LAST_RUN["right_ticks"]

    power = LAST_RUN["power"] if LAST_RUN is not None else config.MAX_SPEED_TEST_POWER
    notes = []

    print("=== CALIBRATION ===")

    if stopwatch_s is not None and stopwatch_s > 0:
        ground_speed_mms = marked_mm / stopwatch_s
        full_duty_mms = ground_speed_mms / power
        print("Ground speed over {:.0f} mm in {:.2f} s: {:.0f} mm/s at power {:.2f}".format(
            marked_mm, stopwatch_s, ground_speed_mms, power))
        print("  MAX_WHEEL_SPEED_MMS = {:.0f}   (config.py currently says {:.0f})".format(
            full_duty_mms, config.MAX_WHEEL_SPEED_MMS))
        notes.append("speed_mms={:.1f}".format(full_duty_mms))
    else:
        print("No stopwatch time given; skipping the speed.")

    if travelled_mm is not None and travelled_mm > 0:
        moved = [t for t in (left_ticks, right_ticks) if abs(t) > 0]
        if not moved:
            print("Both tick counts are zero; the encoders read nothing. No diameter.")
        else:
            if len(moved) == 1:
                print("Only one encoder moved. Deriving from that wheel alone,")
                print("which folds any yaw over the run straight into the answer.")
            mean_ticks = sum(abs(t) for t in moved) / float(len(moved))
            wheel_revs = mean_ticks / config.ENCODER_COUNTS_PER_WHEEL_REV
            circumference_mm = travelled_mm / wheel_revs
            diameter_mm = circumference_mm / math.pi
            error_fraction = diameter_mm / config.WHEEL_DIAMETER_MM - 1.0
            print("Ticks {:.0f} over {:.0f} mm = {:.2f} wheel revolutions".format(
                mean_ticks, travelled_mm, wheel_revs))
            print("  implied rolling circumference = {:.2f} mm".format(circumference_mm))
            print("  implied diameter = {:.2f} mm, against a ruler-confirmed {:.1f}"
                  " ({:+.1f}%)".format(
                      diameter_mm, config.WHEEL_DIAMETER_MM, error_fraction * 100.0))
            if error_fraction > ENCODER_TOLERANCE:
                print("  [!] TICKS ARE MISSING: {:.1f}% short of what {:.0f} mm needs."
                      .format(error_fraction / (1.0 + error_fraction) * 100.0,
                              travelled_mm))
                print("      A 32 mm wheel cannot roll as {:.1f}. The count per rev is"
                      .format(diameter_mm))
                print("      fixed by the gearbox, so the shortfall is the decoder")
                print("      dropping edges. Do not trust odometry until this is 0.")
                print("      This is the same signature BT-7 and BT-8 both showed.")
                print("      See bench_test.wiggle_watch() and channel_levels().")
            elif error_fraction < -ENCODER_TOLERANCE:
                print("  [!] Too many ticks for the distance. A wheel turned without")
                print("      carrying the robot: suspect slip, or a wheel off the floor.")
            else:
                print("  Encoders agree with the ruler. Ticks are trustworthy.")
            notes.append("diameter_mm={:.2f}".format(diameter_mm))
    else:
        print("No travelled distance given; skipping the diameter.")

    if notes:
        _append_log_row("# calibration: {}\n".format(" ".join(notes)))
    return notes


if __name__ == "__main__":
    run()


# ======================================================================================
# Mode 5 -- stress test: N laps of the sprint, out and back
# ======================================================================================

STRESS_LOG_COLUMNS = ("leg,direction,commanded_s,left_ticks,right_ticks,"
                      "cum_left,cum_right,veer_deg\n")
STRESS_LOG_HEADER = "# micromouse stress test v1\n"

# A leg whose tick count falls this far below the running median is treated as an
# encoder dropout rather than a slow leg. Generous: battery sag over 20 laps is
# real and should not be reported as a fault.
DROPOUT_FRACTION = 0.5


def _stress_leg(distance_mm, power, direction, render_object=None, turn_around=False):
    """Drive one leg and return (commanded_s, left_delta, right_delta).

    `direction` is +1 out, -1 back. With turn_around the robot always drives
    FORWARDS and pivots 180 degrees at the end of each leg instead, so
    `direction` only decides whether to pivot afterwards.

    Ticks are read either side of the leg (pivot included), so the deltas are
    signed the way the wheels actually turned.
    """
    _, _, _, commanded_seconds = plan(distance_mm, power)

    before = setup.read_encoders()
    signed_power = power if turn_around else direction * power

    speed_run.drive_motors(signed_power, signed_power)
    speed_run.run_motion_for(commanded_seconds, render_object)
    speed_run.stop_motors()

    if turn_around:
        time.sleep(config.STRESS_TEST_SETTLE_S)
        speed_run.pivot_in_place(2, clockwise=True, render_object=render_object)

    after = setup.read_encoders()
    if before is None or after is None:
        return commanded_seconds, 0, 0
    return commanded_seconds, after[0] - before[0], after[1] - before[1]


def _abort_requested(seconds):
    """Hold the brake for `seconds`, returning True if a button is pressed.

    The only way to stop a twenty minute run without pulling the battery, so it
    polls rather than sleeping. Either button aborts: at the far end of a lane
    you will not care which one you hit.
    """
    waited = 0.0
    step = config.STRESS_TEST_ABORT_POLL_S
    while waited < seconds:
        if setup.sw1.value() == 0 or setup.sw2.value() == 0:
            return True
        time.sleep(step)
        waited += step
    return False


def stress(laps=None, distance_mm=None, power=None, turn_around=False,
           enable_render=False):
    """Drive `laps` out-and-back legs of the sprint, then report the drift.

    Every leg is open loop, so nothing corrects anything: forty legs turn a small
    per-move bias into something you can see with a tape measure. That is the
    point. Three separate things come out of one run:

      Where the robot ends up. Out and back should return it to the start line,
      pointing the same way. It will not. The offset is the accumulated bias.

      What the encoders think. Net ticks should be ~0 after equal legs; a
      systematic residual is the drive being asymmetric forward versus reverse.

      Whether the encoders survive. Twenty minutes of vibration is a far harder
      test of this board's intermittent channels than any bench check.

    WHAT REVERSING CANNOT SEE. Backing up along the same wheel-speed ratio
    retraces the arc exactly, so any error that is the same in both directions
    cancels: a 7% distance-calibration error overshoots by the same amount going
    out and coming back and lands you on the start line regardless. This mode
    measures ASYMMETRY and RANDOMNESS, not calibration.

    Pass turn_around=True to pivot 180 degrees instead of reversing. Then every
    leg is a forward drive plus a turn, which is what a speed run is made of,
    and distance and turn errors both accumulate instead of cancelling. It is
    the harsher test and the more maze-relevant one.
    """
    if laps is None:
        laps = config.STRESS_TEST_LAPS
    if distance_mm is None:
        distance_mm = config.STRESS_TEST_DISTANCE_MM
    if power is None:
        power = config.STRESS_TEST_POWER

    _, _, assumed_speed_mms, leg_seconds = plan(distance_mm, power)
    total_seconds = laps * 2 * (leg_seconds + config.STRESS_TEST_SETTLE_S)

    print("=== STRESS TEST ===")
    print("{} laps, {:.0f} mm per leg, power {:.2f}, {}".format(
        laps, distance_mm, power,
        "180 pivot between legs" if turn_around else "reversing between legs"))
    if not turn_around:
        print("Reversing cancels symmetric error: this measures asymmetry, not")
        print("calibration. turn_around=True is the maze-relevant version.")
    print("Leg takes {:.1f} s, whole run about {:.0f} min {:.0f} s.".format(
        leg_seconds, total_seconds // 60, total_seconds % 60))
    print("Total commanded travel: {:.1f} m.".format(laps * 2 * distance_mm / 1000.0))
    print("MARK THE START POSE: both wheel contact points and the heading.")
    print("Press either button between legs to abort.")

    has_ticks = setup.read_encoders(reset=True) is not None
    if not has_ticks:
        print("No encoder decoder ({}). Physical drift only.".format(setup.encoder_error))

    is_new = not maze.file_exists(config.STRESS_LOG_PATH)
    log = None
    try:
        log = open(config.STRESS_LOG_PATH, "a")
        if is_new:
            log.write(STRESS_LOG_HEADER)
            log.write(STRESS_LOG_COLUMNS)
    except OSError as exc:
        print("Could not open {}: {}".format(config.STRESS_LOG_PATH, exc))

    _blink(5, 80)
    time.sleep(0.5)
    _blink(config.MAX_SPEED_TEST_COUNTDOWN_BLINKS,
           config.MAX_SPEED_TEST_COUNTDOWN_MS,
           config.MAX_SPEED_TEST_COUNTDOWN_MS)

    cum_left = 0
    cum_right = 0
    cum_veer_rad = 0.0
    leg_totals = []
    legs_done = 0
    aborted = False

    mm_per_tick = config.MM_PER_TICK

    for leg_index in range(laps * 2):
        direction = 1 if leg_index % 2 == 0 else -1

        setup.LED_PIN.value(1)
        commanded, left_delta, right_delta = _stress_leg(
            distance_mm, power, direction, turn_around=turn_around)
        setup.LED_PIN.value(0)

        cum_left += left_delta
        cum_right += right_delta
        legs_done += 1

        # Heading change of a differential drive is (right - left) / track, and
        # it holds for a reversing leg too because both deltas flip sign.
        leg_veer_rad = (right_delta - left_delta) * mm_per_tick / config.TRACK_WIDTH_MM
        cum_veer_rad += leg_veer_rad
        leg_totals.append((abs(left_delta) + abs(right_delta)) / 2.0)

        if log is not None:
            log.write("{},{},{:.3f},{},{},{},{},{:.2f}\n".format(
                legs_done, "out" if direction > 0 else "back", commanded,
                left_delta, right_delta, cum_left, cum_right,
                math.degrees(leg_veer_rad)))

        print("  leg {:2d} {:4s}  dL={:+7d} dR={:+7d}  veer {:+5.1f} deg  net L{:+d} R{:+d}".format(
            legs_done, "out" if direction > 0 else "back",
            left_delta, right_delta, math.degrees(leg_veer_rad), cum_left, cum_right))

        if _abort_requested(config.STRESS_TEST_SETTLE_S):
            print("ABORTED by button after leg {}.".format(legs_done))
            aborted = True
            break

    speed_run.stop_motors()
    if log is not None:
        log.close()
    _blink(3, 400, 400)

    _stress_report(legs_done, laps, aborted, distance_mm, has_ticks,
                   cum_left, cum_right, cum_veer_rad, leg_totals, mm_per_tick)

    return {
        "legs": legs_done,
        "aborted": aborted,
        "cum_left": cum_left,
        "cum_right": cum_right,
        "veer_deg": math.degrees(cum_veer_rad),
    }


def _stress_report(legs_done, laps, aborted, distance_mm, has_ticks,
                   cum_left, cum_right, cum_veer_rad, leg_totals, mm_per_tick):
    print("")
    print("=== STRESS TEST REPORT ===")
    print("Legs completed: {} of {}{}".format(
        legs_done, laps * 2, " (ABORTED)" if aborted else ""))
    print("Commanded travel: {:.1f} m".format(legs_done * distance_mm / 1000.0))

    if not has_ticks:
        print("No encoder data. Measure the physical drift by hand.")
        return

    travelled_mm = sum(leg_totals) * mm_per_tick
    print("Encoder travel:   {:.1f} m".format(travelled_mm / 1000.0))

    # After an even number of equal legs the net should cancel to nothing.
    net_mm = (cum_left + cum_right) / 2.0 * mm_per_tick
    print("")
    print("NET displacement per the encoders: {:+.0f} mm".format(net_mm))
    if legs_done % 2 == 1:
        print("  (odd number of legs, so a leg's worth of offset is expected)")
    elif abs(net_mm) > distance_mm * 0.02:
        print("  [!] Forward and reverse are NOT symmetric. One direction is")
        print("      travelling further per leg than the other.")

    print("NET heading per the encoders:      {:+.1f} deg".format(math.degrees(cum_veer_rad)))
    print("  Compare against the heading mark you left on the floor. A big")
    print("  encoder number with the robot straight means the ticks are lying;")
    print("  agreement means both are telling you the drive is asymmetric.")

    if len(leg_totals) >= 6:
        first = sum(leg_totals[:3]) / 3.0
        last = sum(leg_totals[-3:]) / 3.0
        change = (last / first - 1.0) * 100.0 if first else 0.0
        print("")
        print("Ticks per leg: first three {:.0f}, last three {:.0f} ({:+.1f}%)".format(
            first, last, change))
        if change < -5.0:
            print("  [!] The robot slowed over the run. Battery sag or a hot motor.")
            print("      Every leg was the same DURATION, so fewer ticks means less")
            print("      distance, and a speed run late in a battery will undershoot.")

    ordered = sorted(leg_totals)
    median = ordered[len(ordered) // 2]
    dropouts = [i + 1 for i, total in enumerate(leg_totals)
                if total < median * DROPOUT_FRACTION]
    if dropouts:
        print("")
        print("  [!] ENCODER DROPOUT on leg(s) {}: far fewer ticks than the median.".format(
            dropouts))
        print("      This board has a history of intermittent channels. A soak run")
        print("      is exactly how that fault shows itself.")
    else:
        print("")
        print("Every leg counted consistently. No dropout over {:.1f} m.".format(
            legs_done * distance_mm / 1000.0))

    print("")
    print("Now measure the floor: lateral offset from the line, distance short of")
    print("or past the start mark, and the final heading. That is the real answer;")
    print("the encoders only tell you what the robot BELIEVES it did.")
