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

Durations are NOT computed here. `motion.py` turns a distance or an angle into
a number of seconds; this module holds a power for however long it is told to.

Pico-portable: `time`, `config`, `setup` only.
"""

import time

import config
from hal import setup

HAS_SIM = setup.sim is not None

CRUISE_DUTY_POWER = config.CRUISE_DUTY_POWER
TURN_DUTY_POWER = config.TURN_DUTY_POWER

# Draw one frame in this many physics steps. Render-only; it never gates physics.
RENDER_EVERY_N_STEPS = 4

# Full 16-bit duty. Active-low drive, so this value is a channel OFF.
MAX_DUTY = 65535

# None, or a function of (left_power, right_power). drive_motors and stop_motors
# call it with the clamped powers. `record.motor_log` sets it to trace a run.
power_listener = None


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

    if power_listener is not None:
        power_listener(left_p, right_p)

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
    if power_listener is not None:
        power_listener(0.0, 0.0)
    setup.leftFwd.duty_u16(MAX_DUTY)
    setup.leftRev.duty_u16(MAX_DUTY)
    setup.rightFwd.duty_u16(MAX_DUTY)
    setup.rightRev.duty_u16(MAX_DUTY)


def run_motion_for(duration_seconds, render_object=None, belief=None, route=None):
    """Let time pass while the motors drive.

    On the Pico this sleeps. On the PC it steps the sim instead, so wall-clock
    time and sim time diverge completely.
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


def pivot_for(seconds, clockwise=True, render_object=None, belief=None,
              route=None, power=None):
    """Spin on the spot for `seconds` at `power`. Actuation only.

    The DURATION is computed by `motion.py`, which is the one place a distance
    or an angle becomes a time. This function does not know what angle it is
    turning through, and that is deliberate: the arithmetic closed-loop control
    deletes lives in one module, not in the driver.
    """
    if power is None:
        power = TURN_DUTY_POWER
    sign = 1.0 if clockwise else -1.0
    drive_motors(sign * power, -sign * power)
    run_motion_for(seconds, render_object, belief, route)
    stop_motors()
