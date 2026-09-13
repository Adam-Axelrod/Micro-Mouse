"""The motor boundary: the one way anything in this project moves a wheel.

Every mode drives through `drive_motors(left, right)` with signed power in
[-1.0, 1.0]. That pair is the robot-boundary contract value (AGENTS.md invariant
1), not a duty count, so it stays meaningful if the PWM encoding or the pin map
changes underneath it.

This module used to live inside `speed_run.py`. It was moved out because four
other modules -- `max_speed_test`, `bench_test`, `exploration` and the PC-only
`sim.replay_log` -- need a driver, not a speed run, and importing a *mode* to get
a *driver* is what left `bench_test` and `replay_log` calling
`main.drive_motors` after the functions had moved.

Pico-portable: `math`, `time`, `config`, `setup`, `motor_log` only.
"""

import math
import time

import config
import motor_log
import setup

HAS_SIM = setup.sim is not None

CRUISE_DUTY_POWER = config.CRUISE_DUTY_POWER
TURN_DUTY_POWER = config.TURN_DUTY_POWER

# Draw one frame in this many physics steps. Render-only; it never gates physics.
RENDER_EVERY_N_STEPS = 4

# Full 16-bit duty. Active-low drive, so this value is a channel OFF.
MAX_DUTY = 65535

MOTOR_TRACE = motor_log.MotorLog(
    config.MOTOR_LOG_PATH,
    clock_ms=setup.sim.sim_time_ms if setup.sim is not None else None,
)


def start_trace(force=False):
    """Begin recording commanded motor powers to config.MOTOR_LOG_PATH.

    Idempotent, so a mode may call it without knowing whether `main` already did.
    On the Pico there is no renderer and no sim, so a run is otherwise invisible
    and the trace is ON BY DEFAULT; on the PC it costs a file for nothing unless
    the caller asks for it with `--log`.
    """
    if MOTOR_TRACE.is_recording():
        return MOTOR_TRACE
    if force or not HAS_SIM:
        MOTOR_TRACE.start()
        # Record the resting state so the first real power change has a baseline
        # to be a change FROM. Without it the trace starts mid-motion.
        MOTOR_TRACE.record(0.0, 0.0)
    return MOTOR_TRACE


def stop_trace():
    """Close the trace file. Safe to call when nothing was ever started."""
    MOTOR_TRACE.close()


def blink_led(times, on_duration_ms=100, off_duration_ms=None):
    """Flash the onboard LED. The mode's signature lives at the call site.

    This replaces four near-identical copies that differed only in their default
    durations (main, exploration, speed_run, max_speed_test).
    """
    if off_duration_ms is None:
        off_duration_ms = on_duration_ms
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

    if left_p >= 0:
        setup.leftRev.duty_u16(MAX_DUTY)
        setup.leftFwd.duty_u16(int(MAX_DUTY * (1.0 - left_p)))
    else:
        setup.leftFwd.duty_u16(MAX_DUTY)
        setup.leftRev.duty_u16(int(MAX_DUTY * (1.0 - abs(left_p))))

    if right_p >= 0:
        setup.rightRev.duty_u16(MAX_DUTY)
        setup.rightFwd.duty_u16(int(MAX_DUTY * (1.0 - right_p)))
    else:
        setup.rightFwd.duty_u16(MAX_DUTY)
        setup.rightRev.duty_u16(int(MAX_DUTY * (1.0 - abs(right_p))))


def stop_motors():
    """Both channels of both motors at full duty: a BRAKE, not a coast (BT-3)."""
    MOTOR_TRACE.record(0.0, 0.0)
    setup.leftFwd.duty_u16(MAX_DUTY)
    setup.leftRev.duty_u16(MAX_DUTY)
    setup.rightFwd.duty_u16(MAX_DUTY)
    setup.rightRev.duty_u16(MAX_DUTY)


def run_motion_for(duration_seconds, render_object=None, belief=None, route=None):
    """Let time pass while the motors drive.

    On the Pico this sleeps. On the PC it steps the sim instead, so wall-clock
    time and sim time diverge completely -- which is why MOTOR_TRACE is given the
    sim's clock above.
    """
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


def pivot_seconds(quarter_turns, power=None):
    """How long a pivot of `quarter_turns` takes at `power`. The one place it is timed."""
    if power is None:
        power = TURN_DUTY_POWER
    pivot_rate_rads = 2.0 * power * config.MAX_WHEEL_SPEED_MMS / config.TRACK_WIDTH_MM
    return (math.pi / 2.0) * quarter_turns / pivot_rate_rads


def pivot_in_place(quarter_turns, clockwise=True, render_object=None, belief=None,
                   route=None, power=None):
    """Spin on the spot through `quarter_turns` x 90 degrees.

    The power is FIXED for a given turn and only the duration scales with the
    angle. Scaling both is what made a U-turn rotate 360 degrees: it drove at
    2 x TURN_DUTY_POWER, so it spun twice as fast for the time a 180 needed at
    the base rate. Corrected 2026-08-31.

    `power` lets a mode turn more gently than TURN_DUTY_POWER. The duration is
    derived from whatever power is used, never from a different one, which is the
    same trap in another guise.
    """
    if power is None:
        power = TURN_DUTY_POWER
    pivot_time_seconds = pivot_seconds(quarter_turns, power)

    sign = 1.0 if clockwise else -1.0
    drive_motors(sign * power, -sign * power)
    run_motion_for(pivot_time_seconds, render_object, belief, route)
    stop_motors()
