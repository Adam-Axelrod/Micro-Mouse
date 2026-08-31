"""Headless tests for the stress test (mode 5).

Done when: legs alternate out and back, the tick accounting cancels over an even
number of legs, an asymmetric drive shows up as net displacement and net heading,
a button aborts mid-run, and a dropped leg is called out.
"""

import math
import os
import sys

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import config
import max_speed_test
import setup


def _quiet():
    """Blinks and settles are real sleeps; a suite must not wait on them."""
    saved = (config.MAX_SPEED_TEST_COUNTDOWN_BLINKS,
             config.MAX_SPEED_TEST_COUNTDOWN_MS,
             config.STRESS_TEST_SETTLE_S)
    config.MAX_SPEED_TEST_COUNTDOWN_BLINKS = 1
    config.MAX_SPEED_TEST_COUNTDOWN_MS = 1
    config.STRESS_TEST_SETTLE_S = 0.0
    return saved


def _restore(saved):
    (config.MAX_SPEED_TEST_COUNTDOWN_BLINKS,
     config.MAX_SPEED_TEST_COUNTDOWN_MS,
     config.STRESS_TEST_SETTLE_S) = saved


def _clean_log():
    if os.path.exists(config.STRESS_LOG_PATH):
        os.remove(config.STRESS_LOG_PATH)


def test_out_and_back_cancels():
    """A symmetric drive must return to zero net ticks and zero net heading."""
    saved = _quiet()
    _clean_log()
    try:
        result = max_speed_test.stress(laps=3, distance_mm=1000.0, power=0.45)
        assert result["legs"] == 6, result
        assert result["aborted"] is False
        assert result["cum_left"] == 0, result
        assert result["cum_right"] == 0, result
        assert abs(result["veer_deg"]) < 1e-6, result

        with open(config.STRESS_LOG_PATH) as file_handle:
            rows = [line.strip().split(",") for line in file_handle
                    if line.strip() and not line.startswith("#")][1:]
        assert len(rows) == 6, rows
        assert [row[1] for row in rows] == ["out", "back"] * 3
        # Out legs count positive, back legs negative.
        assert int(rows[0][3]) > 0 and int(rows[1][3]) < 0
    finally:
        _restore(saved)
        _clean_log()
    print("✓ test_out_and_back_cancels passed")


def test_direction_asymmetry_shows_up():
    """An error that differs between out and back must NOT average away."""
    saved = _quiet()
    _clean_log()
    real_leg = max_speed_test._stress_leg

    # Out legs run 2% long, back legs are exact. Invisible in one leg.
    def biased_leg(distance_mm, power, direction, render_object=None, turn_around=False):
        travel = int(10000 * (1.02 if direction > 0 else 1.0)) * direction
        return 3.0, travel, travel

    max_speed_test._stress_leg = biased_leg
    try:
        result = max_speed_test.stress(laps=10, distance_mm=1000.0, power=0.45)
        assert result["legs"] == 20, result
        # Ten out legs of +10200 against ten back legs of -10000.
        assert result["cum_left"] == 10 * 200, result
        assert result["cum_right"] == 10 * 200, result
    finally:
        max_speed_test._stress_leg = real_leg
        _restore(saved)
        _clean_log()
    print("✓ test_direction_asymmetry_shows_up passed")


def test_reversing_cancels_a_constant_wheel_bias():
    """The blind spot, pinned so nobody trusts this mode to find calibration.

    Backing up along the same wheel-speed ratio retraces the arc, so a bias that
    is identical in both directions leaves no trace. That is physics, not a bug,
    and it is exactly why turn_around exists.
    """
    saved = _quiet()
    _clean_log()
    real_leg = max_speed_test._stress_leg

    # The right wheel leads by 50 ticks in whichever direction the robot moves.
    def biased_leg(distance_mm, power, direction, render_object=None, turn_around=False):
        travel = 10000 * direction
        return 3.0, travel, travel + 50 * direction

    max_speed_test._stress_leg = biased_leg
    try:
        result = max_speed_test.stress(laps=10, distance_mm=1000.0, power=0.45)
        assert abs(result["veer_deg"]) < 1e-6, (
            "a constant bias must cancel over out-and-back", result)

        # The same bias with a pivot instead of a reversal does NOT cancel:
        # every leg is forward, so every leg's veer adds.
        def forward_only_leg(distance_mm, power, direction,
                             render_object=None, turn_around=False):
            return 3.0, 10000, 10050

        max_speed_test._stress_leg = forward_only_leg
        _clean_log()
        turned = max_speed_test.stress(laps=10, distance_mm=1000.0, power=0.45,
                                       turn_around=True)
        expected = math.degrees(20 * 50 * config.MM_PER_TICK / config.TRACK_WIDTH_MM)
        assert abs(turned["veer_deg"] - expected) < 0.01, turned
        assert turned["veer_deg"] > 1.0, "a real bias must not round to nothing"
    finally:
        max_speed_test._stress_leg = real_leg
        _restore(saved)
        _clean_log()
    print("✓ test_reversing_cancels_a_constant_wheel_bias passed")


def test_button_aborts_the_run():
    """A twenty minute run must be stoppable without pulling the battery."""
    saved = _quiet()
    _clean_log()
    config.STRESS_TEST_SETTLE_S = 0.2
    real_value = setup.sw1.value
    state = {"legs": 0}

    def pressed_after_two(*args):
        if args:
            return real_value(*args)
        state["legs"] += 1
        return 0 if state["legs"] > 2 else 1

    setup.sw1.value = pressed_after_two
    try:
        result = max_speed_test.stress(laps=10, distance_mm=500.0, power=0.45)
        assert result["aborted"] is True, result
        assert result["legs"] < 20, result
    finally:
        setup.sw1.value = real_value
        _restore(saved)
        _clean_log()
    print("✓ test_button_aborts_the_run passed")


def test_dropout_is_reported():
    """A leg that counts almost nothing is the intermittent-channel fault."""
    saved = _quiet()
    _clean_log()
    real_leg = max_speed_test._stress_leg
    state = {"n": 0}

    def dropping_leg(distance_mm, power, direction, render_object=None,
                     turn_around=False):
        state["n"] += 1
        travel = (200 if state["n"] == 4 else 10000) * direction
        return 3.0, travel, travel

    max_speed_test._stress_leg = dropping_leg
    try:
        import io
        captured, real_stdout = io.StringIO(), sys.stdout
        sys.stdout = captured
        try:
            max_speed_test.stress(laps=4, distance_mm=1000.0, power=0.45)
        finally:
            sys.stdout = real_stdout
        output = captured.getvalue()
        assert "ENCODER DROPOUT" in output, output[-500:]
        assert "[4]" in output, output[-500:]
    finally:
        max_speed_test._stress_leg = real_leg
        _restore(saved)
        _clean_log()
    print("✓ test_dropout_is_reported passed")


def test_mode_five_is_registered():
    import main
    assert len(main.MODES) == 5
    assert main.MODES[4][0] == "Stress Test"
    assert main.MODES[4][1] is max_speed_test.stress
    print("✓ test_mode_five_is_registered passed")


if __name__ == "__main__":
    test_out_and_back_cancels()
    test_direction_asymmetry_shows_up()
    test_reversing_cancels_a_constant_wheel_bias()
    test_button_aborts_the_run()
    test_dropout_is_reported()
    test_mode_five_is_registered()
    print("ALL STRESS TEST TESTS PASSED!")
