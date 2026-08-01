"""Encoder fault-finder for the Gemini chassis (MicroPython / Pico only).

Purpose-built to chase the J1 dead-encoder symptom: a wheel spins continuously
because its control loop gets ZERO encoder feedback and saturates. This tool
proves *which* encoder is dead, whether it's intermittent (a hairline trace
crack that comes back under flex), and confirms the motor<->encoder pairing --
the software version of the physical J1/J2 cable swap.

It reuses the codebase's real encoder decoder (diagnostic_encoders.Encoders,
PIO quadrature, left = pins 8/9, right = pins 6/7) and setup.py's motor
channels, so it exercises exactly what the live firmware uses.

    Run it (auto on boot, or `import encoder_fault_test` in the REPL) and it
    starts the SAFE passive monitor. The powered check is opt-in only.

    monitor()        passive: roll each wheel BY HAND, watch its count move.
    channel_levels() passive: raw A/B pin levels, to see WHICH of a wheel's two
                     channels is dead (the live one toggles, the broken one is
                     pinned) -- isolates a single open signal line.
    wiggle_watch()   passive: hold wheels still, flex the board near J1, catch
                     intermittent ticks from a cracking trace.
    spin_check()     POWERED, wheels off the ground: nudges each wheel and checks
                     its own encoder responded. Has a hard runaway guard.

This file needs the Pico's rp2/PIO, so it does not run on the PC.
"""

import time

from machine import Pin

import config
import setup
from diagnostic_encoders import Encoders


# A wheel this many ticks from its baseline counts as "definitely moved" -- above
# quadrature jitter, below a real hand-roll (~1400 ticks/rev).
MOVED_TICKS = 20

# Encoder A/B pins, mirroring diagnostic_encoders.Encoders (left = 8/9, right = 6/7).
LEFT_ENC_A, LEFT_ENC_B = 8, 9
RIGHT_ENC_A, RIGHT_ENC_B = 6, 7


def _mm(ticks):
    """Ticks -> mm, using the same calibration constant the firmware drives on."""
    return ticks * config.MM_PER_TICK


# ======================================================================================
# Passive tests -- no motor power, safe on the bench
# ======================================================================================

def monitor(period_ms=200):
    """Roll each wheel forward by hand and watch its count climb.

    A wheel whose count stays put while you roll it has NO encoder feedback --
    that is the dead J1 channel. The healthy wheel's count will track your hand.
    Ctrl-C to stop and print a verdict.
    """
    enc = Encoders()
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


def channel_levels(period_ms=100):
    """Show the raw A/B logic level of all four encoder channels.

    Roll ONE wheel slowly by hand and watch its two channels: a healthy channel
    alternates 0/1/0/1 as the slots pass; a dead channel stays pinned at one
    value. The pinned pin is the open signal line -- that is the trace to buzz
    for continuity (compare against the same channel on the good wheel).

    Reads the pins directly (no PIO), so run this on its own -- Ctrl-C to stop.
    """
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


def wiggle_watch(threshold=MOVED_TICKS, poll_ms=5):
    """Flex/tap the board near J1 with the wheels held STILL.

    Prints only when a count actually changes, with a timestamp -- so a
    momentary tick appearing as you press near the J1 pad or its mounting slot
    means the trace is reconnecting under flex, i.e. a hairline crack rather
    than a clean break. Silence while you flex = the break is fully open (or
    you're flexing the wrong spot). Ctrl-C to stop.
    """
    enc = Encoders()
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


# ======================================================================================
# Powered pairing check -- OPT-IN, wheels must be off the ground
# ======================================================================================

def _drive(fwd_channel, rev_channel, power):
    """Active-low nudge (matches setup.py/main.drive_motors): hold the reverse
    leg off (65535) and PWM the forward leg down. `power` in [0, 1]."""
    full = 65535
    rev_channel.duty_u16(full)
    fwd_channel.duty_u16(int(full * (1.0 - power)))


def _stop():
    for channel in (setup.leftFwd, setup.leftRev, setup.rightFwd, setup.rightRev):
        channel.duty_u16(65535)


def spin_check(power=0.35, timeout_ms=400, settle_ms=500):
    """POWERED test -- PUT THE MOUSE ON BLOCKS, WHEELS OFF THE GROUND.

    Briefly drives each wheel forward and confirms that wheel's OWN encoder
    registered motion. This is the J1/J2 swap test in software: if the left
    motor drives but the left encoder shows no ticks, the fault is on the left
    encoder path, not the motor.

    Runaway guard: each wheel is driven for at most `timeout_ms` and then
    stopped no matter what, so a dead encoder can never spin unbounded here
    (unlike the real route loop, which keeps pushing until ticks arrive).
    Ctrl-C aborts and stops the motors.
    """
    enc = Encoders()
    print("!!! POWERED test. Wheels OFF THE GROUND. Starting in 2s -- Ctrl-C to abort.")
    time.sleep(2)
    try:
        wheels = (
            ("left", setup.leftFwd, setup.leftRev, 0),
            ("right", setup.rightFwd, setup.rightRev, 1),
        )
        for name, fwd, rev, index in wheels:
            base = enc.get_counts()[index]
            _drive(fwd, rev, power)
            deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
            moved = 0
            while time.ticks_diff(deadline, time.ticks_ms()) > 0:
                moved = abs(enc.get_counts()[index] - base)
                if moved > MOVED_TICKS:
                    break
                time.sleep_ms(5)
            _stop()
            if moved > MOVED_TICKS:
                print("  {:>5} motor -> encoder OK ({} ticks / {:.0f} mm)".format(name, moved, _mm(moved)))
            else:
                print("  {:>5} motor -> NO ENCODER FEEDBACK ({} ticks) -- suspect this channel's trace".format(name, moved))
            time.sleep_ms(settle_ms)
    finally:
        _stop()  # never leave a wheel powered, even on Ctrl-C or error


# ======================================================================================
# Entry point -- default to the SAFE passive monitor
# ======================================================================================

if __name__ == "__main__":
    print("encoder_fault_test: passive monitor (safe). Call channel_levels() to")
    print("find which channel is dead, or spin_check() (on blocks) for the")
    print("powered pairing check -- both from the REPL.")
    monitor()
