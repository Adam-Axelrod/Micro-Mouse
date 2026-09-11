"""Contract: drive.py, the motor boundary.

Signed power in [-1.0, 1.0] goes in, PWM duties come out. Active-low drive, so a
channel at 65535 is OFF and both channels at 65535 is a BRAKE (BT-3).
"""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_DIR = os.path.dirname(TESTS_DIR)
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import config
import drive
import setup

OFF = 65535


def duties():
    """The four channel duties as the hardware holds them right now."""
    return (setup.leftFwd.duty_u16(), setup.leftRev.duty_u16(),
            setup.rightFwd.duty_u16(), setup.rightRev.duty_u16())


def test_the_boundary_symbols_exist_and_are_callable():
    """Every mode reaches for these names. bench_test and replay_log called
    `main.drive_motors` for weeks after it moved, because nothing asserted the
    name it used resolved."""
    for name in ("drive_motors", "stop_motors", "run_motion_for", "pivot_in_place",
                 "blink_led", "start_trace", "stop_trace"):
        assert callable(getattr(drive, name)), f"drive.{name} is missing or not callable"
    assert drive.MAX_DUTY == OFF
    assert drive.CRUISE_DUTY_POWER == config.CRUISE_DUTY_POWER
    assert drive.TURN_DUTY_POWER == config.TURN_DUTY_POWER
    assert isinstance(drive.RENDER_EVERY_N_STEPS, int) and drive.RENDER_EVERY_N_STEPS > 0
    print("✓ test_the_boundary_symbols_exist_and_are_callable passed")


def test_forward_power_drives_the_forward_channel_and_parks_reverse():
    drive.drive_motors(0.55, 0.55)
    left_fwd, left_rev, right_fwd, right_rev = duties()

    assert left_rev == OFF and right_rev == OFF, "reverse must be OFF while driving forward"
    assert left_fwd == int(OFF * (1.0 - 0.55))
    assert right_fwd == int(OFF * (1.0 - 0.55))
    assert 0 < left_fwd < OFF, "active low: more power is a LOWER duty"
    print("✓ test_forward_power_drives_the_forward_channel_and_parks_reverse passed")


def test_negative_power_drives_the_reverse_channel():
    drive.drive_motors(-0.5, -1.0)
    left_fwd, left_rev, right_fwd, right_rev = duties()

    assert left_fwd == OFF and right_fwd == OFF
    assert left_rev == int(OFF * 0.5)
    assert right_rev == 0, "full reverse is duty 0 on the reverse channel"
    print("✓ test_negative_power_drives_the_reverse_channel passed")


def test_the_two_wheels_are_driven_independently():
    """A pivot commands opposite signs. If one side leaked into the other the
    mouse would drive straight instead of turning."""
    drive.drive_motors(0.4, -0.4)
    left_fwd, left_rev, right_fwd, right_rev = duties()
    assert left_fwd == int(OFF * 0.6) and left_rev == OFF
    assert right_rev == int(OFF * 0.6) and right_fwd == OFF
    print("✓ test_the_two_wheels_are_driven_independently passed")


def test_zero_power_parks_both_channels_off():
    drive.drive_motors(0.0, 0.0)
    assert duties() == (OFF, OFF, OFF, OFF)
    print("✓ test_zero_power_parks_both_channels_off passed")


def test_power_is_clamped_to_the_contract_range():
    """The contract value is [-1.0, 1.0]. Out-of-range must saturate, never wrap
    a duty negative or past 16 bits."""
    drive.drive_motors(7.5, -7.5)
    left_fwd, left_rev, right_fwd, right_rev = duties()
    assert (left_fwd, left_rev) == (0, OFF)
    assert (right_fwd, right_rev) == (OFF, 0)

    for duty in duties():
        assert 0 <= duty <= OFF
    print("✓ test_power_is_clamped_to_the_contract_range passed")


def test_stop_motors_brakes_rather_than_coasting():
    drive.drive_motors(0.8, 0.8)
    drive.stop_motors()
    assert duties() == (OFF, OFF, OFF, OFF), "both channels of both motors at full duty"
    print("✓ test_stop_motors_brakes_rather_than_coasting passed")


def test_every_pwm_channel_runs_at_the_declared_frequency():
    for channel in (setup.leftFwd, setup.leftRev, setup.rightFwd, setup.rightRev):
        assert channel.freq() == 2000
    print("✓ test_every_pwm_channel_runs_at_the_declared_frequency passed")


def test_the_encoder_boundary_answers_a_pair_or_none():
    """`setup.read_encoders()` is the hook the dead-encoder watchdog will use:
    a pair of ticks, or None with the reason in setup.encoder_error."""
    reading = setup.read_encoders(reset=True)
    if reading is None:
        assert setup.encoder_error, "a failed read must say why"
    else:
        left, right = reading
        assert isinstance(left, int) and isinstance(right, int)
    print("✓ test_the_encoder_boundary_answers_a_pair_or_none passed")


def test_blink_led_returns_the_led_to_off():
    """A mode signature that ends with the LED lit looks like a hung run."""
    setup.LED_PIN.value(0)
    drive.blink_led(2, on_duration_ms=1, off_duration_ms=1)
    assert setup.LED_PIN.value() == 0
    print("✓ test_blink_led_returns_the_led_to_off passed")


def test_a_pivot_scales_its_duration_with_the_angle_and_not_its_power():
    """The U-turn bug: scaling power AND duration together spun a 180 through 360."""
    quarter = drive.pivot_seconds(1)
    assert abs(drive.pivot_seconds(2) - 2.0 * quarter) < 1e-9
    assert abs(drive.pivot_seconds(1, config.TURN_DUTY_POWER) - quarter) < 1e-9
    print("✓ test_a_pivot_scales_its_duration_with_the_angle_and_not_its_power passed")


def test_a_gentler_pivot_is_timed_longer():
    """A mode may turn slowly, but only if the clock knows it."""
    assert drive.pivot_seconds(1, 0.20) > drive.pivot_seconds(1, 0.40)
    print("✓ test_a_gentler_pivot_is_timed_longer passed")


TESTS = [
    test_the_boundary_symbols_exist_and_are_callable,
    test_a_pivot_scales_its_duration_with_the_angle_and_not_its_power,
    test_a_gentler_pivot_is_timed_longer,
    test_forward_power_drives_the_forward_channel_and_parks_reverse,
    test_negative_power_drives_the_reverse_channel,
    test_the_two_wheels_are_driven_independently,
    test_zero_power_parks_both_channels_off,
    test_power_is_clamped_to_the_contract_range,
    test_stop_motors_brakes_rather_than_coasting,
    test_every_pwm_channel_runs_at_the_declared_frequency,
    test_the_encoder_boundary_answers_a_pair_or_none,
    test_blink_led_returns_the_led_to_off,
]

if __name__ == "__main__":
    for test in TESTS:
        test()
    drive.stop_motors()
    print(f"ALL {len(TESTS)} DRIVE BOUNDARY TESTS PASSED")
