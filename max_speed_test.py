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

The dash also POLLS THE ENCODERS while it drives, every
`config.MAX_SPEED_SAMPLE_INTERVAL_MS`, and appends the samples to
`max_speed_samples.csv`. One run then gives the whole velocity curve instead of
one average, which is what finally separates the acceleration ramp from the
terminal speed. `report_ramp()` prints that curve; `run()` calls it for you.
"""

import gc
import math
import time

import clock
import config
import drive
from brain import maze
import setup

HAS_SIM = setup.sim is not None

# Whichever clock this target runs on. `clock` owns the choice.
_now_ms = clock.now_ms
_diff_ms = clock.diff_ms


LOG_FORMAT_VERSION = 2
LOG_HEADER = "# micromouse max speed test v{}\n".format(LOG_FORMAT_VERSION)
LOG_COLUMNS = ("power,assumed_speed_mms,target_distance_mm,commanded_s,measured_s,"
               "left_ticks,right_ticks\n")

# The samples go to their OWN file. The summary row above is one line per run and
# other things already read it; a dash now also writes a few hundred sample rows,
# and mixing the two would change a format that is not mine to change.
SAMPLE_LOG_HEADER = "# micromouse max speed samples v1\n"
SAMPLE_LOG_COLUMNS = "elapsed_ms,left_ticks,right_ticks\n"

# Ticks over the last dash, so calibrate() can be called from the REPL after the
# tape has been read. None until a run has happened. Lost on reset, which is why
# the numbers also go to the log file.
LAST_RUN = None

# The samples from the last dash: (count, times_ms, left_ticks, right_ticks).
# report_ramp() reads this when it is called with no arguments.
LAST_SAMPLES = None

# How far the tick-derived diameter may sit from the ruler before it means
# something. Covers tyre compression and tape-reading slop; anything past it is
# the decoder miscounting.
ENCODER_TOLERANCE = 0.02


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


def _drive_sampled(power, commanded_seconds, has_encoders):
    """Drive straight for `commanded_seconds`, polling the encoders as it goes.

    Returns (measured_seconds, count, times_ms, left_ticks, right_ticks).

    THE DASH IS THE MEASUREMENT, so the sampling must not stretch it. Three rules
    keep it honest:

      * Every buffer is allocated BEFORE the motors start, and the heap is
        collected first. Allocating inside a timing loop invites a garbage
        collection pause that lands in the numbers.
      * Each interval sleeps to an ABSOLUTE deadline measured from the start of
        the dash, so the cost of a poll comes out of the next sleep instead of
        adding to the total. A slow poll moves one sample, never the dash.
      * With no decoder there is nothing to poll, so the dash runs as one
        uninterrupted sleep exactly as it did before.

    On the PC `drive.run_motion_for` steps sim physics instead of sleeping, and
    `_now_ms` is already the sim clock, so the same loop times both targets.
    """
    interval_ms = config.MAX_SPEED_SAMPLE_INTERVAL_MS
    capacity = config.MAX_SPEED_SAMPLE_LIMIT
    total_ms = int(commanded_seconds * 1000.0)

    # Pre-allocated, fixed length, written by index. Never appended to.
    times_ms = [0] * capacity
    left_ticks = [0] * capacity
    right_ticks = [0] * capacity
    read_encoders = setup.read_encoders
    count = 0
    gc.collect()

    start_ms = _now_ms()
    drive.drive_motors(power, power)

    if not has_encoders:
        drive.run_motion_for(commanded_seconds)
    else:
        elapsed_ms = 0
        while elapsed_ms < total_ms:
            deadline_ms = elapsed_ms + interval_ms
            if deadline_ms > total_ms:
                deadline_ms = total_ms

            if HAS_SIM:
                drive.run_motion_for((deadline_ms - elapsed_ms) / 1000.0)
            else:
                remaining_ms = deadline_ms - _diff_ms(_now_ms(), start_ms)
                if remaining_ms > 0:
                    time.sleep(remaining_ms / 1000.0)
            elapsed_ms = deadline_ms

            if count < capacity:
                ticks = read_encoders()
                if ticks is not None:
                    times_ms[count] = _diff_ms(_now_ms(), start_ms)
                    left_ticks[count] = ticks[0]
                    right_ticks[count] = ticks[1]
                    count += 1

    drive.stop_motors()
    measured_seconds = _diff_ms(_now_ms(), start_ms) / 1000.0
    return measured_seconds, count, times_ms, left_ticks, right_ticks


def _write_samples(count, times_ms, left_ticks, right_ticks, power, distance_mm):
    """Append this dash's samples to their own CSV, under a run marker line.

    Written AFTER the brake, never during the dash: a file write mid-run would
    put flash latency straight into the measurement.
    """
    if count <= 0:
        return
    is_new = not maze.file_exists(config.MAX_SPEED_SAMPLE_LOG_PATH)
    try:
        with open(config.MAX_SPEED_SAMPLE_LOG_PATH, "a") as file_handle:
            if is_new:
                file_handle.write(SAMPLE_LOG_HEADER)
                file_handle.write(SAMPLE_LOG_COLUMNS)
            file_handle.write("# run power={:.2f} target_mm={:.0f} interval_ms={} samples={}\n".format(
                power, distance_mm, config.MAX_SPEED_SAMPLE_INTERVAL_MS, count))
            for index in range(count):
                file_handle.write("{},{},{}\n".format(
                    times_ms[index], left_ticks[index], right_ticks[index]))
    except OSError as exc:
        print("Could not write {}: {}".format(config.MAX_SPEED_SAMPLE_LOG_PATH, exc))


def report_ramp(samples=None, stride_ms=None):
    """Turn one dash's samples into a velocity-versus-time table.

    This is the number the project has never had. `MAX_WHEEL_SPEED_MMS` is an
    average from rest over several metres, so it is lower than the speed the
    robot actually settles at, and how much lower depends on the distance. The
    samples separate the two: the ramp, and the terminal speed after it.

    Speed per interval comes from the tick deltas, mean of the two wheels:

        mm/s = (|dL| + |dR|) / 2 x MM_PER_TICK / dt

    A single interval is noisy, so the table reports a trailing mean over
    MAX_SPEED_RAMP_SMOOTH_SAMPLES. Terminal speed is the highest smoothed value;
    the ramp ends at the first sample reaching MAX_SPEED_RAMP_PLATEAU_FRACTION of
    it, and the terminal figure printed is the mean over that plateau.
    """
    if samples is None:
        samples = LAST_SAMPLES
    if samples is None:
        print("No samples in this session. Run a dash first.")
        return None

    count, times_ms, left_ticks, right_ticks = samples
    if count < 2:
        print("Fewer than two samples; no velocity curve. "
              "The encoders read nothing during the dash.")
        return None

    mm_per_tick = config.MM_PER_TICK
    window = config.MAX_SPEED_RAMP_SMOOTH_SAMPLES

    # Per-interval speed. Index i covers sample i-1 to sample i.
    speeds_mms = [0.0] * count
    for index in range(1, count):
        dt_s = (times_ms[index] - times_ms[index - 1]) / 1000.0
        if dt_s <= 0.0:
            continue
        left_delta = abs(left_ticks[index] - left_ticks[index - 1])
        right_delta = abs(right_ticks[index] - right_ticks[index - 1])
        speeds_mms[index] = (left_delta + right_delta) / 2.0 * mm_per_tick / dt_s

    # Trailing mean. No lookahead, so the ramp is never smoothed backwards in
    # time into looking shorter than it was.
    smoothed_mms = [0.0] * count
    for index in range(1, count):
        first = index - window + 1
        if first < 1:
            first = 1
        total = 0.0
        for back in range(first, index + 1):
            total += speeds_mms[back]
        smoothed_mms[index] = total / (index - first + 1)

    terminal_peak = 0.0
    for index in range(1, count):
        if smoothed_mms[index] > terminal_peak:
            terminal_peak = smoothed_mms[index]

    plateau_speed = config.MAX_SPEED_RAMP_PLATEAU_FRACTION * terminal_peak
    ramp_end_index = None
    for index in range(1, count):
        if smoothed_mms[index] >= plateau_speed:
            ramp_end_index = index
            break

    if stride_ms is None:
        stride_ms = config.MAX_SPEED_TABLE_ROW_MS
    stride = int(stride_ms / config.MAX_SPEED_SAMPLE_INTERVAL_MS)
    # A short dash has few samples to begin with. Thinning it on the same time
    # grid as a 5 m run would print one row and hide the ramp, which is the one
    # part of a short run worth seeing.
    sparse_stride = count // config.MAX_SPEED_TABLE_MIN_ROWS
    if stride > sparse_stride:
        stride = sparse_stride
    if stride < 1:
        stride = 1

    print("")
    print("=== VELOCITY CURVE ===")
    print("{} samples every {} ms. Speed is the mean of both wheels over the".format(
        count, config.MAX_SPEED_SAMPLE_INTERVAL_MS))
    print("interval; the smoothed column is a trailing mean of {} samples.".format(window))
    print("")
    print("   time_s    dist_mm    mm/s   smoothed")
    for index in range(1, count, stride):
        travelled_mm = (abs(left_ticks[index]) + abs(right_ticks[index])) / 2.0 * mm_per_tick
        print("  {:7.2f}  {:9.0f}  {:6.0f}  {:9.0f}".format(
            times_ms[index] / 1000.0, travelled_mm,
            speeds_mms[index], smoothed_mms[index]))

    total_mm = (abs(left_ticks[count - 1]) + abs(right_ticks[count - 1])) / 2.0 * mm_per_tick
    total_s = times_ms[count - 1] / 1000.0
    average_mms = total_mm / total_s if total_s > 0.0 else 0.0

    print("")
    if ramp_end_index is None:
        print("Speed never settled: it was still rising at the end of the dash.")
        print("Run a longer lane before trusting any terminal figure.")
        terminal_mms = terminal_peak
        ramp_ms = None
    else:
        plateau_total = 0.0
        plateau_count = 0
        for index in range(ramp_end_index, count):
            plateau_total += smoothed_mms[index]
            plateau_count += 1
        terminal_mms = plateau_total / plateau_count
        ramp_ms = times_ms[ramp_end_index]
        ramp_mm = (abs(left_ticks[ramp_end_index]) + abs(right_ticks[ramp_end_index])) / 2.0 * mm_per_tick
        print("Ramp duration : {:.0f} ms, over {:.0f} mm, to {:.0f}% of terminal".format(
            ramp_ms, ramp_mm, config.MAX_SPEED_RAMP_PLATEAU_FRACTION * 100.0))
        print("TERMINAL SPEED: {:.0f} mm/s   (mean of {} samples after the ramp)".format(
            terminal_mms, plateau_count))
    print("Dash average  : {:.0f} mm/s over {:.0f} mm in {:.2f} s".format(
        average_mms, total_mm, total_s))
    print("config.MAX_WHEEL_SPEED_MMS = {:.0f}".format(config.MAX_WHEEL_SPEED_MMS))
    print("")
    print("The average is BELOW the terminal speed by however much of the dash")
    print("was ramp. That gap is why a 180 mm cell falls short: it is almost all")
    print("ramp. Use the terminal speed for long moves, the ramp for short ones.")

    return {
        "samples": count,
        "terminal_mms": terminal_mms,
        "ramp_ms": ramp_ms,
        "average_mms": average_mms,
        "travelled_mm": total_mm,
    }


def run(distance_mm=None, power=None, enable_render=False):
    """Drive one straight dash at full duty, brake hard, and report the timing."""
    distance_mm, power, assumed_speed_mms, commanded_seconds = plan(distance_mm, power)
    drive.start_trace()

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
    drive.blink_led(4, 80)
    time.sleep(0.5)
    drive.blink_led(config.MAX_SPEED_TEST_COUNTDOWN_BLINKS,
                    config.MAX_SPEED_TEST_COUNTDOWN_MS,
                    config.MAX_SPEED_TEST_COUNTDOWN_MS)

    # Zero the encoders at the start line. None means no decoder, which is the
    # normal case on this board today; the dash still runs and still times.
    ticks_before = setup.read_encoders(reset=True)
    has_encoders = ticks_before is not None
    if not has_encoders:
        print("No encoder decoder ({}). Timing only, no tick capture.".format(
            setup.encoder_error))
    else:
        print("Sampling the encoders every {} ms through the dash.".format(
            config.MAX_SPEED_SAMPLE_INTERVAL_MS))

    setup.LED_PIN.value(1)
    (measured_seconds, sample_count, sample_times_ms,
     sample_left, sample_right) = _drive_sampled(power, commanded_seconds, has_encoders)
    setup.LED_PIN.value(0)

    # Both channels at 65535 is a brake, not a coast (bench-confirmed, BT-3).
    # Hold it long enough that the robot has really stopped before we report.
    time.sleep(config.MAX_SPEED_TEST_BRAKE_HOLD_S)

    # Read after the brake has settled, so the ticks cover the coast-down too and
    # match the distance the tape will show.
    ticks_after = setup.read_encoders()
    left_ticks, right_ticks = ticks_after if ticks_after is not None else (0, 0)

    drive.blink_led(2, 400, 400)

    global LAST_RUN, LAST_SAMPLES
    LAST_SAMPLES = (sample_count, sample_times_ms, sample_left, sample_right)
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

    _write_samples(sample_count, sample_times_ms, sample_left, sample_right,
                   power, distance_mm)
    if sample_count > 1:
        print("{} samples written to {}.".format(
            sample_count, config.MAX_SPEED_SAMPLE_LOG_PATH))
        report_ramp()

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
