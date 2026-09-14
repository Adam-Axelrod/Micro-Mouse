"""The layer between the brain and the motors: verbs in, timed drives out.

`drive.py` owns the motor contract and knows nothing about a route. `brain/`
owns the route and knows nothing about time. This module is the join, and it is
where every open-loop error is made, because it is the ONE place a distance or
an angle becomes a duration.

Three sites used to compute a duration from a power: `drive.pivot_seconds`,
`speed_run` twice, and `max_speed_test.plan`. Closed-loop control deletes that
arithmetic, and it wants deleting in one place.

Open loop throughout. A verb becomes a fixed power held for a computed time, and
no encoder is read while it runs. Distance divides by ONE constant speed, so
nothing here models the acceleration ramp: see `MAX_WHEEL_SPEED_MMS` in
CONSTANTS.md before trusting a short move.

Pico-portable: `math`, `config`, `drive`, `brain.commands` only.
"""

import math

from brain import commands
import config
import drive


def cruise_speed_mms(power=None):
    """Ground speed assumed at `power`. The assumption every duration rests on.

    Speed is taken as LINEAR in duty and that has never been measured. A DC
    motor's deadband makes linearity false at low duty, so a gentle run misses
    its distance by MORE, not less.
    """
    if power is None:
        power = drive.CRUISE_DUTY_POWER
    return power * config.MAX_WHEEL_SPEED_MMS


def forward_seconds(distance_mm, power=None):
    """How long a straight `distance_mm` takes at `power`."""
    return distance_mm / cruise_speed_mms(power)


def pivot_seconds(quarter_turns, power=None):
    """How long a pivot of `quarter_turns` takes at `power`.

    The power is FIXED for a given turn and only the duration scales with the
    angle. Scaling both is what made a U-turn rotate 360 degrees: it drove at
    2 x TURN_DUTY_POWER, so it spun twice as fast for the time a 180 needed at
    the base rate. Corrected 2026-08-31.
    """
    if power is None:
        power = drive.TURN_DUTY_POWER
    pivot_rate_rads = 2.0 * power * config.MAX_WHEEL_SPEED_MMS / config.TRACK_WIDTH_MM
    return (math.pi / 2.0) * quarter_turns / pivot_rate_rads


def pivot(quarter_turns, clockwise=True, render_object=None, belief=None,
          route=None, power=None):
    """Spin on the spot through `quarter_turns` x 90 degrees at `power`.

    The duration is derived from whatever power is actually used, never from a
    different one. That is the same trap as scaling both, in another guise.
    """
    drive.pivot_for(pivot_seconds(quarter_turns, power), clockwise,
                    render_object, belief, route, power)


def _verb_and_argument(command_string):
    """("F 3") -> ("F", 3). None for a blank line or a comment."""
    if not command_string or command_string.startswith("#"):
        return None, None
    parts = command_string.split()
    return parts[0], (int(parts[1]) if len(parts) > 1 else None)


def execute(movement_commands, render_object=None, belief=None, route=None,
            drive_power=None, turn_power=None):
    """Execute egocentric movement verbs: F n, L, R, U, H.

    `drive_power` and `turn_power` let a mode go slower than a speed run.
    """
    print("Executing movement route: {}".format(movement_commands))

    for command_string in movement_commands:
        verb, argument = _verb_and_argument(command_string)
        if verb is None:
            continue

        if verb == commands.FORWARD:
            seconds = forward_seconds(argument * config.MM_PER_CELL, drive_power)
            power = drive.CRUISE_DUTY_POWER if drive_power is None else drive_power
            drive.drive_motors(power, power)
            drive.run_motion_for(seconds, render_object, belief, route)
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
            pivot(quarter_turns, clockwise, render_object, belief, route, turn_power)

        elif verb == commands.HALT:
            drive.stop_motors()
            print("Route completed successfully!")
            break

        drive.run_motion_for(config.INTER_COMMAND_SETTLE_S, render_object, belief, route)


def lap_seconds(movement_commands, drive_power=None, turn_power=None):
    """How long one lap of a route takes, by the same arithmetic that drives it.

    The operator needs this before the motors arm: thirty laps is a walk-away job
    or a stand-and-watch job depending on the number, and a mode that does not say
    which gets run with a flat battery.
    """
    total_seconds = 0.0
    for command_string in movement_commands:
        verb, argument = _verb_and_argument(command_string)
        if verb is None:
            continue
        if verb == commands.FORWARD:
            total_seconds += forward_seconds(argument * config.MM_PER_CELL, drive_power)
        elif verb in commands.QUARTER_TURNS:
            total_seconds += pivot_seconds(abs(commands.QUARTER_TURNS[verb]), turn_power)
        total_seconds += config.INTER_COMMAND_SETTLE_S
    return total_seconds
