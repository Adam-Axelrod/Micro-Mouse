"""Headless tests for the max speed test mode (mode 4).

Done when: the dash lasts distance / (power x MAX_WHEEL_SPEED_MMS) seconds, the
runaway guard caps it, the sim really travels the target distance, and every run
appends one row to the log.
"""

import os
import sys

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import math

import config
import max_speed_test
import setup


def test_plan_duration_follows_the_speed_constant():
    distance_mm, power, assumed, seconds = max_speed_test.plan(distance_mm=5200.0, power=1.0)
    assert distance_mm == 5200.0
    assert power == 1.0
    assert abs(assumed - config.MAX_WHEEL_SPEED_MMS) < 1e-9
    assert abs(seconds - 5200.0 / config.MAX_WHEEL_SPEED_MMS) < 1e-9

    # Half the duty is twice the time.
    _, _, _, half_duty_seconds = max_speed_test.plan(distance_mm=5200.0, power=0.5)
    assert abs(half_duty_seconds - 2.0 * seconds) < 1e-9
    print("✓ test_plan_duration_follows_the_speed_constant passed")


def test_runaway_guard_caps_the_duration():
    _, _, _, seconds = max_speed_test.plan(distance_mm=1.0e6, power=1.0)
    assert seconds == config.MAX_SPEED_TEST_MAX_DURATION_S
    print("✓ test_runaway_guard_caps_the_duration passed")


def test_zero_power_is_rejected():
    try:
        max_speed_test.plan(distance_mm=5200.0, power=0.0)
    except ValueError:
        print("✓ test_zero_power_is_rejected passed")
        return
    raise AssertionError("power 0.0 must not be planned as a dash")


def test_run_drives_the_target_distance_and_logs_it():
    assert setup.sim is not None, "this test needs the PC sim"

    log_path = config.MAX_SPEED_LOG_PATH
    saved_log = None
    if os.path.exists(log_path):
        with open(log_path) as file_handle:
            saved_log = file_handle.read()
        os.remove(log_path)

    # Blinks and the brake hold are real sleeps; shorten them so the suite is quick.
    saved_constants = (
        config.MAX_SPEED_TEST_COUNTDOWN_BLINKS,
        config.MAX_SPEED_TEST_COUNTDOWN_MS,
        config.MAX_SPEED_TEST_BRAKE_HOLD_S,
    )
    config.MAX_SPEED_TEST_COUNTDOWN_BLINKS = 1
    config.MAX_SPEED_TEST_COUNTDOWN_MS = 1
    config.MAX_SPEED_TEST_BRAKE_HOLD_S = 0.0

    try:
        state = setup.sim.get_mouse_state()
        start_y_mm = state.y_mm

        commanded, measured = max_speed_test.run(distance_mm=1000.0, power=1.0)

        # Ticks were captured around the dash: 1000 mm of travel at the nominal
        # 32 mm wheel is 1000 / (pi * 32) revolutions.
        expected_ticks = (1000.0 / (math.pi * config.WHEEL_DIAMETER_MM)) * \
            config.ENCODER_COUNTS_PER_WHEEL_REV
        assert max_speed_test.LAST_RUN["has_ticks"] is True
        for side in ("left_ticks", "right_ticks"):
            assert abs(max_speed_test.LAST_RUN[side] - expected_ticks) < 100, \
                max_speed_test.LAST_RUN

        assert abs(commanded - 1000.0 / config.MAX_WHEEL_SPEED_MMS) < 1e-9
        # Sim time is stepped, not slept, so the two must agree to a timestep.
        assert abs(measured - commanded) <= config.SIM_TIMESTEP_S

        travelled_mm = state.y_mm - start_y_mm
        assert abs(travelled_mm - 1000.0) < 5.0, travelled_mm

        # The brake, not a coast: both channels sit at full duty afterwards.
        assert setup.leftFwd.duty_u16() == 65535
        assert setup.leftRev.duty_u16() == 65535

        with open(log_path) as file_handle:
            lines = [line for line in file_handle if line.strip() and not line.startswith("#")]
        assert lines[0].strip() == max_speed_test.LOG_COLUMNS.strip()
        assert len(lines) == 2, lines

        # A second run appends rather than rewriting the header.
        max_speed_test.run(distance_mm=100.0, power=1.0)
        with open(log_path) as file_handle:
            lines = [line for line in file_handle if line.strip() and not line.startswith("#")]
        assert len(lines) == 3, lines
    finally:
        (config.MAX_SPEED_TEST_COUNTDOWN_BLINKS,
         config.MAX_SPEED_TEST_COUNTDOWN_MS,
         config.MAX_SPEED_TEST_BRAKE_HOLD_S) = saved_constants
        if os.path.exists(log_path):
            os.remove(log_path)
        if saved_log is not None:
            with open(log_path, "w") as file_handle:
                file_handle.write(saved_log)

    print("✓ test_run_drives_the_target_distance_and_logs_it passed")


def test_encoders_come_through_the_boundary():
    """setup.py owns the encoder pins, and reading them never raises."""
    assert (setup.LEFT_ENCODER_A, setup.LEFT_ENCODER_B) == (8, 9)
    assert (setup.RIGHT_ENCODER_A, setup.RIGHT_ENCODER_B) == (6, 7)
    # The PIO decoder reads an adjacent pair.
    assert setup.LEFT_ENCODER_B == setup.LEFT_ENCODER_A + 1
    assert setup.RIGHT_ENCODER_B == setup.RIGHT_ENCODER_A + 1

    # No encoder pin may collide with a motor PWM pin.
    encoder_pins = {setup.LEFT_ENCODER_A, setup.LEFT_ENCODER_B,
                    setup.RIGHT_ENCODER_A, setup.RIGHT_ENCODER_B}
    assert encoder_pins.isdisjoint({2, 3, 4, 5})

    # reset=True returns the count accumulated so far and zeroes it AFTER, so
    # the next read starts from zero. Same contract as the Pico's decoder.
    assert setup.read_encoders(reset=True) is not None, setup.encoder_error
    assert setup.read_encoders() == (0, 0)

    # Forward motion counts positive on both wheels, as on hardware.
    state = setup.sim.get_mouse_state()
    state.step(100.0, 100.0, 1.0)
    left_ticks, right_ticks = setup.read_encoders()
    assert left_ticks > 0 and right_ticks > 0, (left_ticks, right_ticks)
    print("✓ test_encoders_come_through_the_boundary passed")


def test_motor_polarity_is_untouched():
    """The encoder work must not have moved a motor pin or a direction.

    Driving pin 3 alone runs the LEFT wheel forward (bench-confirmed, BT-2).
    """
    import drive

    assert setup.leftFwd.pin.id == 3
    assert setup.leftRev.pin.id == 2
    assert setup.rightFwd.pin.id == 4
    assert setup.rightRev.pin.id == 5

    state = setup.sim.get_mouse_state()
    state.reset_pose(0.0, 0.0, math.pi / 2.0)  # facing north

    drive.drive_motors(0.5, 0.5)
    setup.sim.step_sim_physics(0.1)
    drive.stop_motors()
    assert state.y_mm > 0.0, "positive power must drive forward"

    state.reset_pose(0.0, 0.0, math.pi / 2.0)
    drive.drive_motors(-0.5, -0.5)
    setup.sim.step_sim_physics(0.1)
    drive.stop_motors()
    assert state.y_mm < 0.0, "negative power must drive backward"

    # Right wheel faster than left turns to the left (CCW, heading increases).
    state.reset_pose(0.0, 0.0, 0.0)
    drive.drive_motors(0.0, 0.5)
    setup.sim.step_sim_physics(0.1)
    drive.stop_motors()
    assert 0.0 < state.heading_radians < math.pi, state.heading_radians
    print("✓ test_motor_polarity_is_untouched passed")


def test_calibrate_derives_speed_and_checks_the_encoder():
    """A 1306-shaped tick count must point at the encoder, not the wheel.

    The implied diameter is travelled x counts_per_rev / ticks, so it moves
    OPPOSITE to the tick count. Missing edges therefore read as a wheel LARGER
    than the ruler says, which is physically impossible and is the tell.
    """
    log_path = config.MAX_SPEED_LOG_PATH
    saved_log = None
    if os.path.exists(log_path):
        with open(log_path) as file_handle:
            saved_log = file_handle.read()
        os.remove(log_path)

    saved_last_run = max_speed_test.LAST_RUN
    max_speed_test.LAST_RUN = {"power": 1.0, "left_ticks": 0, "right_ticks": 0}
    try:
        # 50 revolutions of a true 32 mm wheel over its own circumference.
        true_circumference = math.pi * config.WHEEL_DIAMETER_MM
        ticks = 50 * config.ENCODER_COUNTS_PER_WHEEL_REV
        max_speed_test.calibrate(travelled_mm=50 * true_circumference,
                                 stopwatch_s=10.0, marked_mm=5000.0,
                                 left_ticks=ticks, right_ticks=ticks)
        with open(log_path) as file_handle:
            note = [line for line in file_handle if line.startswith("# calibration")][0]
        assert "speed_mms=500.0" in note, note
        assert "diameter_mm=32.00" in note, note

        # Same distance, but 6.7% of the edges went missing, which is what BT-7
        # actually saw. That implies a 34.3 mm wheel: impossible on a 32 mm one,
        # so the shortfall can only be the decoder.
        os.remove(log_path)
        max_speed_test.calibrate(travelled_mm=50 * true_circumference,
                                 left_ticks=int(50 * 1306), right_ticks=int(50 * 1306))
        with open(log_path) as file_handle:
            note = [line for line in file_handle if line.startswith("# calibration")][0]
        assert "diameter_mm=34.30" in note, note

        # Too MANY ticks is the opposite fault, a wheel spinning free.
        os.remove(log_path)
        max_speed_test.calibrate(travelled_mm=50 * true_circumference,
                                 left_ticks=int(50 * 1500), right_ticks=int(50 * 1500))
        with open(log_path) as file_handle:
            note = [line for line in file_handle if line.startswith("# calibration")][0]
        assert "diameter_mm=29.87" in note, note

        # A dead encoder yields no diameter rather than a wrong one.
        os.remove(log_path)
        notes = max_speed_test.calibrate(travelled_mm=5000.0, left_ticks=0, right_ticks=0)
        assert notes == [], notes
    finally:
        max_speed_test.LAST_RUN = saved_last_run
        if os.path.exists(log_path):
            os.remove(log_path)
        if saved_log is not None:
            with open(log_path, "w") as file_handle:
                file_handle.write(saved_log)
    print("✓ test_calibrate_derives_speed_and_checks_the_encoder passed")


def test_mode_four_is_registered():
    import main
    assert main.MODES[3][0] == "Max Speed Test"
    assert main.MODES[3][1] is max_speed_test.run
    print("✓ test_mode_four_is_registered passed")


if __name__ == "__main__":
    test_plan_duration_follows_the_speed_constant()
    test_runaway_guard_caps_the_duration()
    test_zero_power_is_rejected()
    test_run_drives_the_target_distance_and_logs_it()
    test_encoders_come_through_the_boundary()
    test_motor_polarity_is_untouched()
    test_calibrate_derives_speed_and_checks_the_encoder()
    test_mode_four_is_registered()
    print("ALL MAX SPEED TEST TESTS PASSED!")
