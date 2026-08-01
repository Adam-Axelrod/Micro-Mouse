"""Hardware bench tests for the UKMARS Gemini chassis (Pico / MicroPython only).

This is the bring-up checklist from HANDOFF.md turned into runnable code. It
produces BENCH EVIDENCE: every check ends in a recorded PASS/FAIL/value that
`summary()` prints as one paste-back block. Sim-green proves nothing here.

    Copy to the Pico, then in the REPL:

        import bench_test
        bench_test.run_all()     # guided, in dependency order
        bench_test.summary()     # paste-back block of every result so far

    Or run one check at a time (same order run_all uses):

        bt0_boot()              passive  pins construct, LEDs walk, platform is HW
        bt1_buttons()           passive  SW1/SW2 read pressed
        bt2_motor_polarity()    POWERED  which pin drives which wheel, which way
        bt3_brake_vs_coast()    POWERED  what both-channels-65535 actually does
        bt4_encoders_passive()  passive  hand-roll each wheel, counts must move
        bt5_encoder_pairing()   POWERED  left motor moves the LEFT count, sign +
        bt6_sensors()           passive  lit-minus-unlit ADC at known distances
        bt7_counts_per_rev()    passive  push a measured distance, get ticks/rev
        bt8_track_width()       passive  pivot 360 by hand, derive track width

    Deep encoder fault-finding tools (dead channel, intermittent trace, J1 flex):
        channel_levels()        passive  raw A/B logic level (pins 8/9 & 6/7)
        monitor()               passive  continuous live tick count monitoring
        wiggle_watch()          passive  flex board near J1, catch intermittent cracks
        spin_check()            POWERED  brief pulse with runaway guard
        encoder_fault_menu()    interactive fault diagnostic menu

POWERED checks demand the wheels are OFF THE GROUND and ask you to confirm it
before any duty is written. Every powered pulse is hard-capped by
MAX_PULSE_MS and always ends in stop_motors().

Several checks cannot be judged by the software -- only you can see which way a
wheel turned. Those ask a question and record YOUR answer; that is deliberate,
the operator is the sensor. Answers are y / n / s (skip).

Needs the Pico's rp2/PIO for the encoder checks, so it does not run on the PC.
"""

import math
import time

import config
import main
import setup

# --------------------------------------------------------------------------------------
# Bench constants (invariant 5: no bare numbers in logic)
# --------------------------------------------------------------------------------------

# Powered pulses: gentle enough not to launch the robot off the stand, long
# enough to see the wheel turn and for the encoder to accumulate ticks.
BENCH_DUTY_POWER = 0.45      # signed fraction of full duty, as drive_motors takes
MAX_PULSE_MS = 1200          # hard cap on any single powered pulse (ms)
SETTLE_MS = 300              # let a wheel come to rest before reading counts (ms)

# A wheel this many ticks from baseline counts as "definitely moved" -- above
# quadrature jitter, well below one hand-roll revolution (~1400 ticks).
MOVED_TICKS = 20

# Encoder A/B pins (left = 8/9, right = 6/7)
LEFT_ENC_A, LEFT_ENC_B = 8, 9
RIGHT_ENC_A, RIGHT_ENC_B = 6, 7

# Emitter settle time before reading the lit ADC value (ms). The phototransistor
# needs the LED to actually be on; reading too early samples the unlit state.
EMITTER_SETTLE_MS = 5
SENSOR_SAMPLES = 8           # averaged per reading, to beat ADC noise

# Distances to sample the reflective sensors at, for calibrating SENSOR_* in
# config.py against the provisional 1/d^2 curve (mm).
SENSOR_CAL_DISTANCES_MM = (20, 40, 60, 90, 120, 180)

BUTTON_WAIT_S = 10           # how long to wait for a button press before giving up
BUTTON_POLL_MS = 20

LED_WALK_MS = 250            # dwell per LED in the indicator walk

# --------------------------------------------------------------------------------------
# Result recording
# --------------------------------------------------------------------------------------

RESULTS = []  # list of (check_id, outcome, detail)


def _record(check_id, outcome, detail=""):
    """Record one bench result and echo it. `outcome` is PASS / FAIL / VALUE / SKIP."""
    RESULTS.append((check_id, outcome, detail))
    print("  >> {} {} {}".format(check_id, outcome, detail))


def summary():
    """Print every result recorded this session as one paste-back block."""
    print("")
    print("==================== BENCH SUMMARY ====================")
    if not RESULTS:
        print("(nothing run yet)")
    for check_id, outcome, detail in RESULTS:
        print("{:<22} {:<6} {}".format(check_id, outcome, detail))
    print("=======================================================")
    print("Paste this into LOG.md / the session notes.")


def reset_results():
    """Clear recorded results (start a fresh bench session without a reboot)."""
    del RESULTS[:]
    print("Results cleared.")


# --------------------------------------------------------------------------------------
# Operator prompts
# --------------------------------------------------------------------------------------

def _ask(question):
    """Ask a yes/no/skip question. Returns True, False or None (skipped)."""
    while True:
        answer = input("  ? {} [y/n/s] ".format(question)).strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        if answer in ("s", "skip", ""):
            return None
        print("    (answer y, n, or s to skip)")


def _ask_number(question):
    """Ask for a number. Returns a float, or None if skipped."""
    while True:
        answer = input("  ? {} (blank to skip) ".format(question)).strip()
        if answer == "":
            return None
        try:
            return float(answer)
        except ValueError:
            print("    (that is not a number)")


def _pause(message):
    input("  - {} [Enter] ".format(message))


def _verdict(check_id, answer, pass_detail, fail_detail):
    """Turn an operator y/n/skip into a recorded result."""
    if answer is None:
        _record(check_id, "SKIP")
    elif answer:
        _record(check_id, "PASS", pass_detail)
    else:
        _record(check_id, "FAIL", fail_detail)
    return answer


# --------------------------------------------------------------------------------------
# Powered-test safety gate
# --------------------------------------------------------------------------------------

_wheels_clear_confirmed = False


def _require_wheels_off_ground():
    """Gate every powered check. Confirmed once per session (reboot to re-arm)."""
    global _wheels_clear_confirmed
    if _wheels_clear_confirmed:
        return True
    print("")
    print("  !! POWERED CHECK -- the wheels are about to turn.")
    print("  !! Put the robot on a stand so BOTH wheels spin free.")
    confirmed = _ask("Are both wheels off the ground and clear?")
    if confirmed is not True:
        print("  Aborted -- nothing was driven.")
        return False
    _wheels_clear_confirmed = True
    return True


def _pulse(left_power, right_power, duration_ms, label):
    """Drive for a capped duration through the real firmware path, then stop."""
    duration_ms = min(duration_ms, MAX_PULSE_MS)
    print("  -> {}: drive_motors({:+.2f}, {:+.2f}) for {} ms".format(
        label, left_power, right_power, duration_ms))
    try:
        main.drive_motors(left_power, right_power)
        time.sleep_ms(duration_ms)
    finally:
        main.stop_motors()
    time.sleep_ms(SETTLE_MS)


def _pulse_raw_channel(pwm_channel, name, duration_ms):
    """Drive ONE PWM channel low (active-low = ON) with the other three OFF.

    This bypasses drive_motors on purpose: it is the only way to learn which
    physical wheel and direction each pin actually owns, which is the question
    behind the setup.py / sim_machine pin-map desync.
    """
    duration_ms = min(duration_ms, MAX_PULSE_MS)
    all_channels = (setup.leftFwd, setup.leftRev, setup.rightFwd, setup.rightRev)
    off_duty = 65535
    print("  -> raw channel {}: duty low for {} ms".format(name, duration_ms))
    try:
        for channel in all_channels:
            channel.duty_u16(off_duty)
        pwm_channel.duty_u16(int(off_duty * (1.0 - BENCH_DUTY_POWER)))
        time.sleep_ms(duration_ms)
    finally:
        for channel in all_channels:
            channel.duty_u16(off_duty)
    time.sleep_ms(SETTLE_MS)


# --------------------------------------------------------------------------------------
# Encoders (lazy singleton -- the PIO state machines can only be claimed once)
# --------------------------------------------------------------------------------------

_encoders = None
_encoder_error = None


def _get_encoders():
    """Construct the PIO quadrature decoder once; None if it is unavailable."""
    global _encoders, _encoder_error
    if _encoders is None and _encoder_error is None:
        try:
            from diagnostic_encoders import Encoders
            _encoders = Encoders()
        except Exception as exc:  # ImportError on PC, PIO claim failure on Pico
            _encoder_error = str(exc)
            print("  !! encoders unavailable: {}".format(_encoder_error))
    return _encoders


def _counts():
    encoders = _get_encoders()
    if encoders is None:
        return None
    return encoders.get_counts()


def _mm(ticks):
    return ticks * config.MM_PER_TICK


# ======================================================================================
# BT-0  Boot and indicators -- passive
# ======================================================================================

def bt0_boot():
    """Confirm we are on real hardware, every pin object built, LEDs light."""
    print("")
    print("== BT-0  boot and indicators ==")

    if not setup.IS_HARDWARE:
        _record("BT-0.platform", "FAIL", "setup.IS_HARDWARE is False -- this is the PC sim")
        return
    _record("BT-0.platform", "PASS", "MicroPython machine module present")

    print("  Onboard LED: 3 blinks.")
    main.blink_led(3)

    indicators = (
        ("leftSensorLED", setup.leftSensorLED),
        ("centreSensorLED", setup.centreSensorLED),
        ("rightSensorLED", setup.rightSensorLED),
        ("leftMezzLED", setup.leftMezzLED),
        ("rightMezzLED", setup.rightMezzLED),
    )
    print("  Walking the 5 indicator LEDs, left to right...")
    for name, led in indicators:
        print("     {}".format(name))
        led.value(1)
        time.sleep_ms(LED_WALK_MS)
        led.value(0)

    _verdict("BT-0.leds",
             _ask("Did the onboard LED blink AND all 5 indicators light in turn?"),
             "onboard + 5 indicators OK",
             "an LED or its pin is wrong -- see setup.py pin map")


# ======================================================================================
# BT-1  Buttons -- passive
# ======================================================================================

def _wait_for_button(pin, name):
    """Wait for an active-low button press. True if seen within BUTTON_WAIT_S."""
    print("  Press the {} button ({}s)...".format(name, BUTTON_WAIT_S))
    deadline_ms = time.ticks_add(time.ticks_ms(), BUTTON_WAIT_S * 1000)
    while time.ticks_diff(deadline_ms, time.ticks_ms()) > 0:
        if pin.value() == 0:
            print("    {} pressed.".format(name))
            while pin.value() == 0:  # wait for release, so the next check is clean
                time.sleep_ms(BUTTON_POLL_MS)
            return True
        time.sleep_ms(BUTTON_POLL_MS)
    print("    ...no press seen.")
    return False


def bt1_buttons():
    """Both mode buttons must read pressed. main.py boots on these."""
    print("")
    print("== BT-1  buttons ==")

    left_ok = _wait_for_button(setup.leftButton, "LEFT / SW1 (exploration)")
    _record("BT-1.left", "PASS" if left_ok else "FAIL",
            "pin 15 reads low when pressed" if left_ok else "pin 15 never went low")

    right_ok = _wait_for_button(setup.rightButton, "RIGHT / SW2 (speed run)")
    _record("BT-1.right", "PASS" if right_ok else "FAIL",
            "pin 14 reads low when pressed" if right_ok else "pin 14 never went low")


# ======================================================================================
# BT-2  Motor polarity -- POWERED, wheels off the ground
# ======================================================================================

def bt2_motor_polarity():
    """Settle the pin map and the polarity trap: which pin turns which wheel, which way.

    setup.py says leftFwd=Pin(3)/leftRev=Pin(2); sim_machine.set_motor_duty maps
    pin 2 -> left_fwd. They cannot both be right. This check is the arbiter --
    it drives one raw channel at a time and asks what you saw.
    """
    print("")
    print("== BT-2  motor polarity and pin map ==")
    if not _require_wheels_off_ground():
        _record("BT-2", "SKIP", "operator did not confirm wheels clear")
        return

    channels = (
        ("pin3 (setup.leftFwd)", setup.leftFwd, "BT-2.pin3"),
        ("pin2 (setup.leftRev)", setup.leftRev, "BT-2.pin2"),
        ("pin4 (setup.rightFwd)", setup.rightFwd, "BT-2.pin4"),
        ("pin5 (setup.rightRev)", setup.rightRev, "BT-2.pin5"),
    )
    for name, channel, check_id in channels:
        _pause("about to drive {} alone".format(name))
        _pulse_raw_channel(channel, name, MAX_PULSE_MS)
        which = input("  ? Which wheel turned, and which way? "
                      "[LF/LR/RF/RR/none] ").strip().upper()
        _record(check_id, "VALUE", "{} -> {}".format(name, which or "no answer"))

    # Now the contract itself: the API the whole firmware drives on.
    _pause("now the real call: drive_motors(+{:.2f}, +{:.2f})".format(
        BENCH_DUTY_POWER, BENCH_DUTY_POWER))
    _pulse(BENCH_DUTY_POWER, BENCH_DUTY_POWER, MAX_PULSE_MS, "both forward")
    _verdict("BT-2.forward",
             _ask("Did BOTH wheels turn FORWARD?"),
             "drive_motors positive = forward on both",
             "polarity is wrong -- fix setup.py/sim_machine to match what BT-2.pinN showed")

    _pause("and the reverse: drive_motors(-{:.2f}, -{:.2f})".format(
        BENCH_DUTY_POWER, BENCH_DUTY_POWER))
    _pulse(-BENCH_DUTY_POWER, -BENCH_DUTY_POWER, MAX_PULSE_MS, "both reverse")
    _verdict("BT-2.reverse",
             _ask("Did BOTH wheels turn BACKWARD?"),
             "drive_motors negative = reverse on both",
             "reverse channel wrong or a bridge input is dead")

    _pause("and a pivot: drive_motors(+{:.2f}, -{:.2f}) should spin RIGHT".format(
        BENCH_DUTY_POWER, BENCH_DUTY_POWER))
    _pulse(BENCH_DUTY_POWER, -BENCH_DUTY_POWER, MAX_PULSE_MS, "pivot right")
    _verdict("BT-2.pivot",
             _ask("Left wheel forward, right wheel backward (a clockwise spin)?"),
             "left/right assignment confirmed",
             "left and right motors are swapped in setup.py")


# ======================================================================================
# BT-3  Brake vs coast -- POWERED, wheels off the ground
# ======================================================================================

def bt3_brake_vs_coast():
    """What does both-channels-65535 actually DO?

    setup.py calls it an "active-low brake"; main.py:63 calls the same state
    "OFF". One comment is wrong, and open-loop timing depends on which. The
    wheel either stops dead (brake) or freewheels down (coast) -- you can see it.
    """
    print("")
    print("== BT-3  brake vs coast ==")
    if not _require_wheels_off_ground():
        _record("BT-3", "SKIP", "operator did not confirm wheels clear")
        return

    _pause("spinning up, then cutting to both-channels-65535 -- watch the wheels")
    print("  -> spinning up")
    main.drive_motors(BENCH_DUTY_POWER, BENCH_DUTY_POWER)
    time.sleep_ms(MAX_PULSE_MS)
    print("  -> cut (stop_motors)")
    main.stop_motors()

    braked = _ask("Did the wheels stop DEAD? (n = they freewheeled to a stop)")
    if braked is None:
        _record("BT-3.stop_state", "SKIP")
    else:
        _record("BT-3.stop_state", "VALUE",
                "both-channels-65535 = BRAKE (stops dead)" if braked
                else "both-channels-65535 = COAST (freewheels) -- setup.py comment is wrong")

    coast_ms = _ask_number("If it coasted, roughly how many ms to stop?")
    if coast_ms is not None:
        _record("BT-3.coast_ms", "VALUE", "{:.0f} ms freewheel".format(coast_ms))


# ======================================================================================
# BT-4  Encoders, passive hand-roll
# ======================================================================================

def _hand_roll_one(label, index, check_id):
    """Roll one wheel by hand; that wheel's count must move, the other must not."""
    before = _counts()
    if before is None:
        _record(check_id, "FAIL", "encoder decoder unavailable: {}".format(_encoder_error))
        return False
    _pause("roll the {} wheel forward by hand, about one full turn".format(label))
    after = _counts()
    delta_left = after[0] - before[0]
    delta_right = after[1] - before[1]
    mine = (delta_left, delta_right)[index]
    other = (delta_left, delta_right)[1 - index]

    print("     dL={:+} ticks ({:+.0f} mm)   dR={:+} ticks ({:+.0f} mm)".format(
        delta_left, _mm(delta_left), delta_right, _mm(delta_right)))

    if abs(mine) <= MOVED_TICKS:
        _record(check_id, "FAIL",
                "{} count did not move ({:+} ticks) -- dead channel, "
                "use channel_levels() or wiggle_watch()".format(label, mine))
        return False
    elif abs(other) > MOVED_TICKS:
        _record(check_id, "FAIL",
                "{} roll moved BOTH counts (dL={:+}, dR={:+}) -- channels crossed".format(
                    label, delta_left, delta_right))
        return False
    elif mine < 0:
        _record(check_id, "VALUE",
                "{} alive but rolls NEGATIVE forward ({:+} ticks) -- "
                "invert the sign in diagnostic_encoders.get_counts".format(label, mine))
        return True
    else:
        _record(check_id, "PASS", "{} alive, forward = positive ({:+} ticks)".format(label, mine))
        return True


def bt4_encoders_passive():
    """Both encoders must respond to a hand-roll. The known trap is the dead left."""
    print("")
    print("== BT-4  encoders, hand-roll ==")
    print("  Known live trap: the LEFT encoder is dead via a broken J1 signal line")
    print("  (pins 8/9). If BT-4.left fails, channel_levels() isolates which")
    print("  of the two channels is open, and wiggle_watch() checks for hairline cracks.")
    if _get_encoders() is None:
        _record("BT-4", "FAIL", "encoder decoder unavailable: {}".format(_encoder_error))
        return
    left_ok = _hand_roll_one("LEFT", 0, "BT-4.left")
    right_ok = _hand_roll_one("RIGHT", 1, "BT-4.right")

    if not left_ok or not right_ok:
        print("")
        print("  [!] Encoder issue detected during BT-4.")
        choice = _ask("Open deep encoder fault diagnostics menu now?")
        if choice is True:
            encoder_fault_menu()


# ======================================================================================
# Deep Encoder Fault Diagnostics (folded from encoder_fault_test.py)
# ======================================================================================

def channel_levels(period_ms=100):
    """Show the raw A/B logic level of all four encoder channels.

    Roll ONE wheel slowly by hand and watch its two channels: a healthy channel
    alternates 0/1/0/1 as the slots pass; a dead channel stays pinned at one
    value. The pinned pin is the open signal line -- that is the trace to buzz
    for continuity (compare against the same channel on the good wheel).

    Reads the pins directly (no PIO), so run this on its own -- Ctrl-C to stop.
    """
    try:
        from machine import Pin
    except ImportError:
        print("  !! channel_levels requires MicroPython machine module (Pico hardware only)")
        return

    left_a = Pin(LEFT_ENC_A, Pin.IN, Pin.PULL_UP)
    left_b = Pin(LEFT_ENC_B, Pin.IN, Pin.PULL_UP)
    right_a = Pin(RIGHT_ENC_A, Pin.IN, Pin.PULL_UP)
    right_b = Pin(RIGHT_ENC_B, Pin.IN, Pin.PULL_UP)
    print("Raw channel levels -- roll ONE wheel slowly by hand. Ctrl-C to stop.")
    print("(a healthy channel toggles 0/1; a dead one stays fixed)")
    print("          left            right")
    print("        A(8) B(9)       A(6) B(7)")
    try:
        while True:
            print("        {}    {}          {}    {}".format(
                left_a.value(), left_b.value(), right_a.value(), right_b.value()))
            time.sleep_ms(period_ms)
    except KeyboardInterrupt:
        print("done")


def monitor(period_ms=200):
    """Roll each wheel forward by hand and watch its count climb.

    A wheel whose count stays put while you roll it has NO encoder feedback --
    that is the dead J1 channel. The healthy wheel's count will track your hand.
    Ctrl-C to stop and print a verdict.
    """
    enc = _get_encoders()
    if enc is None:
        print("  !! encoders unavailable: {}".format(_encoder_error))
        return
    left_base, right_base = enc.get_counts()
    left_seen = right_seen = False
    print("Passive roll test -- turn each wheel by hand. Ctrl-C to stop.")
    print("(count should climb for whichever wheel you are rolling)")
    try:
        while True:
            left, right = enc.get_counts()
            dl, dr = left - left_base, right - right_base
            if abs(dl) > MOVED_TICKS:
                left_seen = True
            if abs(dr) > MOVED_TICKS:
                right_seen = True
            print("L={:>8} ({:>+7} tk / {:>+7.0f} mm)   R={:>8} ({:>+7} tk / {:>+7.0f} mm)   [{} {}]".format(
                left, dl, _mm(dl), right, dr, _mm(dr),
                "L-ok" if left_seen else "L-??",
                "R-ok" if right_seen else "R-??"))
            time.sleep_ms(period_ms)
    except KeyboardInterrupt:
        print("\n--- verdict ---")
        print("  left  encoder:", "responding" if left_seen else "DEAD -- no counts while rolled")
        print("  right encoder:", "responding" if right_seen else "DEAD -- no counts while rolled")


def wiggle_watch(threshold=MOVED_TICKS, poll_ms=5):
    """Flex/tap the board near J1 with the wheels held STILL.

    Prints only when a count actually changes, with a timestamp -- so a
    momentary tick appearing as you press near the J1 pad or its mounting slot
    means the trace is reconnecting under flex, i.e. a hairline crack rather
    than a clean break. Silence while you flex = the break is fully open (or
    you're flexing the wrong spot). Ctrl-C to stop.
    """
    enc = _get_encoders()
    if enc is None:
        print("  !! encoders unavailable: {}".format(_encoder_error))
        return
    left_prev, right_prev = enc.get_counts()
    print("Wiggle test -- keep wheels still, flex the board near J1. Ctrl-C to stop.")
    try:
        while True:
            left, right = enc.get_counts()
            if abs(left - left_prev) >= threshold or abs(right - right_prev) >= threshold:
                print("t={:>9}ms  L {:>8} ({:>+5})  R {:>8} ({:>+5})  <-- movement with wheels still".format(
                    time.ticks_ms(), left, left - left_prev, right, right - right_prev))
                left_prev, right_prev = left, right
            time.sleep_ms(poll_ms)
    except KeyboardInterrupt:
        print("done")


def spin_check(power=BENCH_DUTY_POWER, timeout_ms=400, settle_ms=500):
    """POWERED test -- PUT THE MOUSE ON BLOCKS, WHEELS OFF THE GROUND.

    Briefly drives each wheel forward and confirms that wheel's OWN encoder
    registered motion. Software version of J1/J2 cable swap check with runaway guard.
    Ctrl-C aborts and stops the motors.
    """
    enc = _get_encoders()
    if enc is None:
        print("  !! encoders unavailable: {}".format(_encoder_error))
        return
    if not _require_wheels_off_ground():
        print("  Aborted -- wheels not clear.")
        return
    print("!!! POWERED spin check. Wheels OFF THE GROUND. Starting in 2s -- Ctrl-C to abort.")
    time.sleep(2)
    try:
        wheels = (
            ("left", setup.leftFwd, setup.leftRev, 0),
            ("right", setup.rightFwd, setup.rightRev, 1),
        )
        for name, fwd, rev, index in wheels:
            base = enc.get_counts()[index]
            _pulse_raw_channel(fwd, name + "Fwd", timeout_ms)
            moved = abs(enc.get_counts()[index] - base)
            if moved > MOVED_TICKS:
                print("  {:>5} motor -> encoder OK ({} ticks / {:.0f} mm)".format(name, moved, _mm(moved)))
            else:
                print("  {:>5} motor -> NO ENCODER FEEDBACK ({} ticks) -- suspect this channel's trace".format(name, moved))
            time.sleep_ms(settle_ms)
    finally:
        main.stop_motors()


def encoder_fault_menu():
    """Interactive deep diagnostic menu for encoder troubleshooting."""
    print("")
    print("--- ENCODER FAULT DIAGNOSTICS ---")
    print("  1) Raw channel levels (channel_levels) - pin 8/9 & 6/7 0/1 levels")
    print("  2) Continuous monitor (monitor)       - live tick counts per wheel")
    print("  3) Wiggle watch       (wiggle_watch)   - flex board near J1, catch cracks")
    print("  4) Powered spin check (spin_check)     - brief pulse with runaway guard")
    print("  5) Return to bench tests")
    while True:
        opt = input("  Select diagnostic tool [1-5]: ").strip()
        if opt == "1":
            channel_levels()
        elif opt == "2":
            monitor()
        elif opt == "3":
            wiggle_watch()
        elif opt == "4":
            spin_check()
        elif opt in ("5", "q", "exit", ""):
            break


# Aliases for explicit naming clarity
encoder_channel_levels = channel_levels
encoder_monitor = monitor
encoder_wiggle_watch = wiggle_watch
encoder_spin_check = spin_check


# ======================================================================================
# BT-5  Motor <-> encoder pairing -- POWERED, wheels off the ground
# ======================================================================================

def _powered_one_wheel(label, left_power, right_power, index, check_id):
    before = _counts()
    if before is None:
        _record(check_id, "FAIL", "encoder decoder unavailable")
        return
    _pulse(left_power, right_power, MAX_PULSE_MS, "{} wheel only".format(label))
    after = _counts()
    delta_left = after[0] - before[0]
    delta_right = after[1] - before[1]
    driven = (delta_left, delta_right)[index]
    idle = (delta_left, delta_right)[1 - index]
    print("     dL={:+} ticks   dR={:+} ticks".format(delta_left, delta_right))

    if abs(driven) <= MOVED_TICKS:
        _record(check_id, "FAIL",
                "drove {} but its count stayed put ({:+}) -- dead encoder or "
                "dead motor; BT-2 says which".format(label, driven))
    elif abs(idle) > MOVED_TICKS:
        _record(check_id, "FAIL",
                "drove {} but the OTHER count moved too (dL={:+}, dR={:+}) -- "
                "motor and encoder are cross-wired".format(label, delta_left, delta_right))
    elif driven < 0:
        _record(check_id, "VALUE",
                "{} paired correctly but forward drive counts NEGATIVE "
                "({:+})".format(label, driven))
    else:
        _record(check_id, "PASS",
                "{} motor moves the {} count, forward = positive ({:+})".format(
                    label, label, driven))


def bt5_encoder_pairing():
    """Drive one wheel at a time and confirm its OWN encoder is the one that moved.

    This is the software version of swapping the J1/J2 cables: it catches a
    motor wired to the other side's encoder, which closed-loop control would
    turn into a runaway.
    """
    print("")
    print("== BT-5  motor <-> encoder pairing ==")
    if _get_encoders() is None:
        _record("BT-5", "FAIL", "encoder decoder unavailable: {}".format(_encoder_error))
        return
    if not _require_wheels_off_ground():
        _record("BT-5", "SKIP", "operator did not confirm wheels clear")
        return
    _powered_one_wheel("LEFT", BENCH_DUTY_POWER, 0.0, 0, "BT-5.left")
    _powered_one_wheel("RIGHT", 0.0, BENCH_DUTY_POWER, 1, "BT-5.right")


# ======================================================================================
# BT-6  Reflective sensors -- passive
# ======================================================================================

def _read_adc_avg(adc):
    total = 0
    for _ in range(SENSOR_SAMPLES):
        total += adc.read_u16()
    return total // SENSOR_SAMPLES


def _lit_minus_unlit(adc, emitter):
    """The robot's actual sensing primitive: reading with the LED on, minus off."""
    emitter.value(0)
    time.sleep_ms(EMITTER_SETTLE_MS)
    unlit = _read_adc_avg(adc)
    emitter.value(1)
    time.sleep_ms(EMITTER_SETTLE_MS)
    lit = _read_adc_avg(adc)
    emitter.value(0)
    return lit, unlit, lit - unlit


SENSORS = (
    ("left", "leftSensor(ADC28)", lambda: setup.leftSensor, lambda: setup.sidesEmitter),
    ("front", "frontSensor(ADC27)", lambda: setup.frontSensor, lambda: setup.frontEmitter),
    ("right", "rightSensor(ADC26)", lambda: setup.rightSensor, lambda: setup.sidesEmitter),
)


def bt6_sensors():
    """Prove lit-minus-unlit responds to a wall, then sample the distance curve.

    The numbers this prints are what replaces the provisional SENSOR_* constants
    in config.py -- the sim's 1/d^2 curve has never been checked against glass.
    """
    print("")
    print("== BT-6  reflective sensors ==")

    # Part 1: does the emitter do anything at all?
    print("  Baseline, nothing in front of the robot:")
    for key, name, get_adc, get_emitter in SENSORS:
        lit, unlit, delta = _lit_minus_unlit(get_adc(), get_emitter())
        print("     {:<20} lit={:>6}  unlit={:>6}  delta={:>+7}".format(name, lit, unlit, delta))

    _pause("now hold a wall (or your hand) close in front of ALL THREE sensors")
    responded = []
    for key, name, get_adc, get_emitter in SENSORS:
        lit, unlit, delta = _lit_minus_unlit(get_adc(), get_emitter())
        print("     {:<20} lit={:>6}  unlit={:>6}  delta={:>+7}".format(name, lit, unlit, delta))
        responded.append((key, delta))

    _verdict("BT-6.response",
             _ask("Did all three deltas rise clearly with the wall close?"),
             "lit-minus-unlit responds on all 3: " +
             ", ".join("{}={:+}".format(k, d) for k, d in responded),
             "a sensor or its emitter is dead -- deltas: " +
             ", ".join("{}={:+}".format(k, d) for k, d in responded))

    # Part 2: the calibration curve.
    print("")
    print("  Distance sweep -- place a wall at each distance from the sensor face.")
    do_sweep = _ask("Run the distance sweep now? (needs a ruler)")
    if do_sweep is not True:
        _record("BT-6.curve", "SKIP", "distance sweep not run")
        return

    print("   dist_mm |    left |   front |   right   (lit-minus-unlit counts)")
    rows = []
    for distance_mm in SENSOR_CAL_DISTANCES_MM:
        _pause("set the wall at {} mm".format(distance_mm))
        deltas = []
        for key, name, get_adc, get_emitter in SENSORS:
            _, _, delta = _lit_minus_unlit(get_adc(), get_emitter())
            deltas.append(delta)
        print("   {:>7} | {:>7} | {:>7} | {:>7}".format(distance_mm, *deltas))
        rows.append((distance_mm, deltas))

    _record("BT-6.curve", "VALUE",
            "; ".join("{}mm:L{},F{},R{}".format(d, *v) for d, v in rows))
    print("")
    print("  Fit these against config.SENSOR_INTENSITY_SCALE /")
    print("  SENSOR_DISTANCE_OFFSET_MM / SENSOR_ADC_FLOOR before trusting the sim's")
    print("  sensor model. Current provisional values:")
    print("     SCALE={:g}  OFFSET={:g} mm  FLOOR={}  RANGE={:g} mm".format(
        config.SENSOR_INTENSITY_SCALE, config.SENSOR_DISTANCE_OFFSET_MM,
        config.SENSOR_ADC_FLOOR, config.SENSOR_RANGE_MM))


# ======================================================================================
# BT-7  Encoder counts per wheel revolution -- passive
# ======================================================================================

def bt7_counts_per_rev():
    """Push the robot a measured straight distance; derive ticks per wheel rev.

    config.ENCODER_COUNTS_PER_WHEEL_REV is provisional, and MM_PER_TICK (hence
    all odometry) is derived from it.
    """
    print("")
    print("== BT-7  encoder counts per wheel revolution ==")
    if _get_encoders() is None:
        _record("BT-7", "FAIL", "encoder decoder unavailable: {}".format(_encoder_error))
        return

    print("  Put the robot on the floor. Mark a start line and an end line.")
    distance_mm = _ask_number("How far will you push it, in mm? (a metre is ideal)")
    if distance_mm is None or distance_mm <= 0:
        _record("BT-7", "SKIP", "no distance given")
        return

    before = _counts()
    _pause("push it straight, exactly {:.0f} mm, then stop".format(distance_mm))
    after = _counts()
    delta_left = after[0] - before[0]
    delta_right = after[1] - before[1]
    print("     dL={:+} ticks   dR={:+} ticks".format(delta_left, delta_right))

    revolutions = distance_mm / config.WHEEL_CIRCUMFERENCE_MM
    measured = []
    for label, delta in (("left", delta_left), ("right", delta_right)):
        if abs(delta) <= MOVED_TICKS:
            print("     {} encoder did not move -- excluded".format(label))
            continue
        measured.append(abs(delta) / revolutions)

    if not measured:
        _record("BT-7", "FAIL", "neither encoder moved over {:.0f} mm".format(distance_mm))
        return

    counts_per_rev = sum(measured) / len(measured)
    _record("BT-7.counts_per_rev", "VALUE",
            "{:.0f} counts/rev over {:.0f} mm (config says {}) "
            "-> MM_PER_TICK {:.4f}".format(
                counts_per_rev, distance_mm, config.ENCODER_COUNTS_PER_WHEEL_REV,
                config.WHEEL_CIRCUMFERENCE_MM / counts_per_rev))
    print("  Set config.ENCODER_COUNTS_PER_WHEEL_REV = {:.0f} if this repeats.".format(
        counts_per_rev))


# ======================================================================================
# BT-8  Track width -- passive
# ======================================================================================

def bt8_track_width():
    """Pivot the robot 360 degrees on the spot by hand; derive the track width.

    In a pure pivot each wheel travels pi * TRACK_WIDTH per full turn, so the
    tick count gives the track width directly -- but only as accurately as BT-7
    set counts-per-rev, so run BT-7 first.
    """
    print("")
    print("== BT-8  track width ==")
    if _get_encoders() is None:
        _record("BT-8", "FAIL", "encoder decoder unavailable: {}".format(_encoder_error))
        return

    print("  Mark the floor under the robot's centre and a heading line.")
    print("  Also measure it with a ruler (wheel centre to wheel centre) -- the")
    print("  ruler is the check on this derivation, not the other way round.")
    ruler_mm = _ask_number("Ruler measurement of track width, mm?")
    if ruler_mm is not None:
        _record("BT-8.ruler", "VALUE",
                "{:.1f} mm measured (config says {})".format(ruler_mm, config.TRACK_WIDTH_MM))

    before = _counts()
    _pause("rotate the robot exactly 360 degrees on the spot, then stop")
    after = _counts()
    delta_left = after[0] - before[0]
    delta_right = after[1] - before[1]
    print("     dL={:+} ticks   dR={:+} ticks".format(delta_left, delta_right))

    usable = [abs(d) for d in (delta_left, delta_right) if abs(d) > MOVED_TICKS]
    if not usable:
        _record("BT-8.derived", "FAIL", "neither encoder moved during the pivot")
        return

    arc_mm = sum(_mm(t) for t in usable) / len(usable)
    derived_track_mm = arc_mm / math.pi
    _record("BT-8.derived", "VALUE",
            "{:.1f} mm from {} encoder(s) (config says {})".format(
                derived_track_mm, len(usable), config.TRACK_WIDTH_MM))
    if len(usable) < 2:
        print("  NOTE: only one encoder contributed, so this assumes a perfect")
        print("  pivot about the wheel centre. Trust the ruler more.")


# ======================================================================================
# Runner
# ======================================================================================

ORDERED_CHECKS = (
    ("BT-0  boot and indicators", bt0_boot),
    ("BT-1  buttons", bt1_buttons),
    ("BT-2  motor polarity", bt2_motor_polarity),
    ("BT-3  brake vs coast", bt3_brake_vs_coast),
    ("BT-4  encoders hand-roll", bt4_encoders_passive),
    ("BT-5  motor/encoder pairing", bt5_encoder_pairing),
    ("BT-6  reflective sensors", bt6_sensors),
    ("BT-7  counts per rev", bt7_counts_per_rev),
    ("BT-8  track width", bt8_track_width),
)


def run_all():
    """Walk every check in dependency order, then print the summary."""
    print("")
    print("############ GEMINI BENCH TESTS ############")
    print("Order matters: polarity before pairing, counts-per-rev before track width.")
    print("Answer y / n / s at each prompt; 's' skips a judgement.")
    for title, check in ORDERED_CHECKS:
        print("")
        choice = _ask("Run {}?".format(title))
        if choice is not True:
            _record(title.split()[0], "SKIP", "not run")
            continue
        try:
            check()
        except KeyboardInterrupt:
            main.stop_motors()
            print("  Interrupted -- motors stopped.")
            _record(title.split()[0], "SKIP", "interrupted")
        except Exception as exc:
            main.stop_motors()
            _record(title.split()[0], "FAIL", "raised: {}".format(exc))
    summary()


if __name__ == "__main__":
    run_all()
