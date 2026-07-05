"""Pico 2 W on-board route runner (MicroPython).

Copy this file to the Pico's filesystem root AS `main.py` and it runs automatically on power-up
(MicroPython executes boot.py then main.py). It reads a route.mmc command file -- the egocentric
verbs produced on the PC by micromouse/commands.py -- and drives the mouse through it with
closed-loop encoder counting: `F n` = forward n cells, `L`/`R`/`U` = pivot in place, `H` = halt.

  Route grammar (one command per line, `#` lines and blanks ignored):
     F n   drive forward n cells        R    pivot 90 deg right
     L     pivot 90 deg left            U    180 deg turn        H  halt / end

!!! READ BEFORE POWERING THE MOTORS !!!
Everything in CONFIG below is hardware-specific and UNVERIFIED. In particular the pin numbers, the
motor-driver style, and the four *_SIGN flags depend entirely on how YOUR mouse is wired. Follow the
bring-up order in the comments by BRINGUP at the bottom before trusting a full route. The mouse waits
START_DELAY_S (blinking) on power-up so you can put it down / pull it off a table first.
"""

import machine
import time
import math
import micropython

from machine import Pin, PWM

micropython.alloc_emergency_exception_buf(100)   # so a fault inside an encoder IRQ prints a traceback

# ======================================================================================
# CONFIG  -- set your route here, and match the rest to your wiring before running.
# ======================================================================================

ROUTE_FILE = "route.mmc"          # <-- the command file to execute, sitting on the Pico's root

# --- Motor driver pins ----------------------------------------------------------------
# Assumes a DRV8833-style driver: TWO PWM inputs per motor (IN1/IN2). Forward drives IN1
# and holds IN2 low; reverse swaps them. If you have a TB6612 (PWM + 2 direction pins) the
# _apply() function needs changing, not this block.
LEFT_IN1  = 2
LEFT_IN2  = 3
RIGHT_IN1 = 4
RIGHT_IN2 = 5

# --- Encoder pins (quadrature A/B per wheel) ------------------------------------------
LEFT_ENC_A  = 6
LEFT_ENC_B  = 7
RIGHT_ENC_A = 8
RIGHT_ENC_B = 9

# --- Direction signs (flip these during bring-up, do NOT rewire) ----------------------
# +1 or -1. Get these right with the BRINGUP steps before running a route.
LEFT_FORWARD_SIGN  = +1   # make the LEFT wheel roll the mouse FORWARD on a positive duty
RIGHT_FORWARD_SIGN = +1   # same for the RIGHT wheel
LEFT_ENC_SIGN      = +1   # make the LEFT encoder COUNT UP when that wheel rolls forward
RIGHT_ENC_SIGN     = +1   # same for the RIGHT encoder

# --- Speeds / control (tune) ----------------------------------------------------------
PWM_FREQ_HZ   = 20000     # 20 kHz: above hearing, fine for DRV8833
CRUISE_DUTY   = 0.55      # straight-line cruise, fraction of full scale (0..1)
TURN_DUTY     = 0.40      # pivot speed; lower = more accurate stopping
MIN_DUTY      = 0.18      # floor so the motors don't stall when ramping down
RAMP_TICKS    = 300       # start easing off this many encoder ticks before a target
HEADING_KP    = 0.0008    # straight-drive correction gain (duty per tick of L-R imbalance)
LOOP_SLEEP_MS = 2         # control-loop period

START_DELAY_S = 3.0       # blink-and-wait on power-up before moving (safety)

# --- Geometry / encoder (mirror of micromouse/config.py) ------------------------------
MM_PER_CELL                 = 180
WHEEL_DIAMETER_MM           = 32
TRACK_WIDTH_MM              = 70      # wheel-centre to wheel-centre; sets the pivot arc length
ENCODER_COUNTS_PER_WHEEL_REV = 1400  # FULL-quadrature counts per wheel revolution

# ======================================================================================
# Derived constants -- do not edit; change the measured values above instead.
# ======================================================================================

WHEEL_CIRCUMFERENCE_MM = math.pi * WHEEL_DIAMETER_MM
MM_PER_TICK            = WHEEL_CIRCUMFERENCE_MM / ENCODER_COUNTS_PER_WHEEL_REV
TICKS_PER_CELL         = MM_PER_CELL / MM_PER_TICK
# A 90 deg pivot sweeps each wheel through a quarter of a circle of radius TRACK_WIDTH/2.
QUARTER_TURN_TICKS     = (TRACK_WIDTH_MM / 2) * (math.pi / 2) / MM_PER_TICK

# ======================================================================================
# Encoder -- software quadrature decoder (both edges of both channels = full 4x)
# ======================================================================================

# Classic transition table: index (prev_state << 2 | new_state), value is the count delta.
# state = (A << 1) | B. Illegal transitions (a missed edge) contribute 0.
_QTAB = (0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0)


class Encoder:
    def __init__(self, pin_a, pin_b, sign=1):
        self._a = Pin(pin_a, Pin.IN, Pin.PULL_UP)
        self._b = Pin(pin_b, Pin.IN, Pin.PULL_UP)
        self._sign = sign
        self.count = 0
        self._state = (self._a.value() << 1) | self._b.value()
        trig = Pin.IRQ_RISING | Pin.IRQ_FALLING
        self._a.irq(self._cb, trig)
        self._b.irq(self._cb, trig)

    def _cb(self, _pin):
        s = (self._a.value() << 1) | self._b.value()
        self.count += self._sign * _QTAB[(self._state << 2) | s]
        self._state = s

    def reset(self):
        self.count = 0


# ======================================================================================
# Motors -- differential drive over a dual-PWM (DRV8833-style) driver
# ======================================================================================

class Motor:
    """One wheel. `duty` in [-1, 1]; positive = FORWARD once fwd_sign is set correctly."""
    def __init__(self, pin_in1, pin_in2, fwd_sign=1):
        self._in1 = PWM(Pin(pin_in1)); self._in1.freq(PWM_FREQ_HZ)
        self._in2 = PWM(Pin(pin_in2)); self._in2.freq(PWM_FREQ_HZ)
        self._fwd = fwd_sign

    def drive(self, duty):
        duty *= self._fwd
        if duty > 1: duty = 1
        elif duty < -1: duty = -1
        u16 = int(abs(duty) * 65535)
        if duty >= 0:                       # forward: PWM on IN1, IN2 low
            self._in1.duty_u16(u16); self._in2.duty_u16(0)
        else:                               # reverse: swap
            self._in1.duty_u16(0); self._in2.duty_u16(u16)

    def stop(self):
        self._in1.duty_u16(0); self._in2.duty_u16(0)


# ======================================================================================
# Hardware handles (created at import; motors held stopped)
# ======================================================================================

led    = Pin("LED", Pin.OUT)
left   = Motor(LEFT_IN1,  LEFT_IN2,  LEFT_FORWARD_SIGN)
right  = Motor(RIGHT_IN1, RIGHT_IN2, RIGHT_FORWARD_SIGN)
enc_l  = Encoder(LEFT_ENC_A,  LEFT_ENC_B,  LEFT_ENC_SIGN)
enc_r  = Encoder(RIGHT_ENC_A, RIGHT_ENC_B, RIGHT_ENC_SIGN)


def stop_all():
    left.stop(); right.stop()


def _ramped_duty(remaining, cruise):
    """Ease the cruise duty down to MIN_DUTY over the last RAMP_TICKS to curb overshoot."""
    if remaining >= RAMP_TICKS:
        return cruise
    frac = remaining / RAMP_TICKS
    return MIN_DUTY + (cruise - MIN_DUTY) * frac


# ======================================================================================
# Motion primitives -- one per route verb
# ======================================================================================

def forward(cells):
    """Drive forward `cells` cells, keeping straight by balancing the two encoders."""
    target = int(cells * TICKS_PER_CELL)
    enc_l.reset(); enc_r.reset()
    while True:
        cl = abs(enc_l.count); cr = abs(enc_r.count)
        travelled = (cl + cr) // 2
        remaining = target - travelled
        if remaining <= 0:
            break
        base = _ramped_duty(remaining, CRUISE_DUTY)
        correction = HEADING_KP * (cl - cr)     # left ahead -> slow left, speed right
        left.drive(base - correction)
        right.drive(base + correction)
        time.sleep_ms(LOOP_SLEEP_MS)
    stop_all()


def pivot(quarters, clockwise):
    """Spin in place. `quarters` = 1 for a 90 deg turn, 2 for 180. Clockwise spins the mouse
    to its right (left wheel forward, right wheel back)."""
    target = int(quarters * QUARTER_TURN_TICKS)
    enc_l.reset(); enc_r.reset()
    sign = 1 if clockwise else -1
    while True:
        travelled = (abs(enc_l.count) + abs(enc_r.count)) // 2
        remaining = target - travelled
        if remaining <= 0:
            break
        duty = _ramped_duty(remaining, TURN_DUTY)
        left.drive(sign * duty)
        right.drive(-sign * duty)
        time.sleep_ms(LOOP_SLEEP_MS)
    stop_all()


# ======================================================================================
# Route parsing + execution
# ======================================================================================

def run_command(verb, arg):
    if verb == "F":
        forward(int(arg))
    elif verb == "R":
        pivot(1, clockwise=True)
    elif verb == "L":
        pivot(1, clockwise=False)
    elif verb == "U":
        pivot(2, clockwise=True)
    elif verb == "H":
        return False                        # end of route
    else:
        raise ValueError("unknown command: %s" % verb)
    return True


def run_route(path):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            verb, *rest = line.split()
            if not run_command(verb, rest[0] if rest else None):
                break
    stop_all()


# ======================================================================================
# LED status helpers
# ======================================================================================

def blink(times, on_ms=120, off_ms=120):
    for _ in range(times):
        led.on();  time.sleep_ms(on_ms)
        led.off(); time.sleep_ms(off_ms)


def wait_before_start():
    """Slow blink for START_DELAY_S so you can set the mouse down before it moves."""
    t_end = time.ticks_add(time.ticks_ms(), int(START_DELAY_S * 1000))
    while time.ticks_diff(t_end, time.ticks_ms()) > 0:
        led.on();  time.sleep_ms(250)
        led.off(); time.sleep_ms(250)


# ======================================================================================
# Entry point
# ======================================================================================

def main():
    stop_all()                              # never move during init
    wait_before_start()
    try:
        run_route(ROUTE_FILE)
        led.on()                            # solid LED = route finished cleanly
    except OSError:
        stop_all(); blink(10, 60, 60)       # fast blink = route file missing / read error
    except Exception:
        stop_all(); blink(3, 400, 200)      # slow triple = bad command / other fault
        raise                               # still print the traceback to the REPL


# ---- BRINGUP: verify these IN ORDER on blocks, wheels off the ground, before a real route ----
# 1. Motor direction: temporarily call `left.drive(0.3)` then `right.drive(0.3)` from the REPL.
#    Any wheel spinning backward -> flip that motor's *_FORWARD_SIGN (do not rewire).
# 2. Encoder direction: roll each wheel forward BY HAND and print enc_l.count / enc_r.count.
#    A count that goes negative -> flip that encoder's *_ENC_SIGN.
# 3. Distance: run `forward(1)` and measure travel; if it's off, MM_PER_TICK is wrong -> confirm
#    ENCODER_COUNTS_PER_WHEEL_REV against a measured push (config.py's SIM-4 / HW-1 note).
# 4. Turns: run `pivot(1, True)` and check it's ~90 deg; tune TRACK_WIDTH_MM if the angle is off.
# Only after all four should you drop a full route.mmc in and power-cycle.

if __name__ == "__main__":
    main()
