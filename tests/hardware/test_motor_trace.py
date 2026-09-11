"""Contract: the motor trace. What drive.py records is the only evidence a
hardware run leaves behind, so the record must match what was commanded.
"""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_DIR = os.path.dirname(TESTS_DIR)
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import tempfile

import config
import drive
import motor_log
import setup

# Write the trace to a scratch file, never over the repository's motor_log.csv:
# that file is a real measurement of a real run.
TRACE_PATH = os.path.join(tempfile.gettempdir(), "micromouse_trace_contract.csv")
drive.MOTOR_TRACE.path_str = TRACE_PATH


def fresh_trace():
    """A closed trace, reopened onto the scratch file, with the baseline record."""
    drive.stop_trace()
    drive.start_trace(force=True)
    return drive.MOTOR_TRACE


def cleanup():
    drive.stop_trace()
    if os.path.exists(TRACE_PATH):
        os.remove(TRACE_PATH)


def test_the_trace_uses_the_sim_clock_not_the_wall_clock():
    """On the PC the drive routines step physics instead of sleeping, so wall
    time barely moves. A wall-clocked trace lands every record on one
    millisecond and replays as an instantaneous run."""
    if setup.sim is None:
        print("✓ test_the_trace_uses_the_sim_clock_not_the_wall_clock skipped (no sim)")
        return
    assert drive.MOTOR_TRACE.clock_ms is setup.sim.sim_time_ms
    print("✓ test_the_trace_uses_the_sim_clock_not_the_wall_clock passed")


def test_start_trace_writes_a_resting_baseline_and_is_idempotent():
    trace = fresh_trace()
    assert trace.is_recording()
    assert trace.records_written == 1, "the resting state is record one"

    drive.start_trace(force=True)
    assert drive.MOTOR_TRACE.records_written == 1, "a second start must not restart the file"
    cleanup()
    print("✓ test_start_trace_writes_a_resting_baseline_and_is_idempotent passed")


def test_only_changed_powers_are_recorded():
    trace = fresh_trace()
    drive.drive_motors(0.55, 0.55)
    drive.drive_motors(0.55, 0.55)                 # unchanged
    drive.drive_motors(0.5505, 0.5505)             # inside MOTOR_LOG_POWER_EPSILON
    drive.drive_motors(-0.4, 0.4)
    drive.stop_motors()
    assert trace.records_written == 4, trace.records_written
    drive.stop_trace()

    records = motor_log.read_log(TRACE_PATH)
    powers = [(left, right) for _, left, right in records]
    assert powers == [(0.0, 0.0), (0.55, 0.55), (-0.4, 0.4), (0.0, 0.0)], powers
    timestamps = [t for t, _, _ in records]
    assert all(a <= b for a, b in zip(timestamps, timestamps[1:])), timestamps
    cleanup()
    print("✓ test_only_changed_powers_are_recorded passed")


def test_the_trace_records_the_clamped_power_the_motors_actually_got():
    """The record has to be what the hardware was told, not what the caller
    asked for, or a replay diverges from the run it is meant to reproduce."""
    fresh_trace()
    drive.drive_motors(3.0, -3.0)
    drive.stop_trace()

    _, left, right = motor_log.read_log(TRACE_PATH)[-1]
    assert (left, right) == (1.0, -1.0)
    cleanup()
    print("✓ test_the_trace_records_the_clamped_power_the_motors_actually_got passed")


def test_the_file_carries_the_v1_header():
    fresh_trace()
    drive.stop_trace()
    with open(TRACE_PATH) as file_handle:
        header = [file_handle.readline().strip() for _ in range(2)]
    assert header[0] == f"# micromouse motor log v{motor_log.LOG_FORMAT_VERSION}"
    assert header[1] == "# t_ms,left_power,right_power"
    cleanup()
    print("✓ test_the_file_carries_the_v1_header passed")


def test_a_pivot_is_traced_as_a_turn_then_a_stop():
    """pivot_in_place is the one place a turn is timed. Its trace must show the
    opposite-sign pair held for a nonzero sim interval, then the brake."""
    fresh_trace()
    drive.pivot_in_place(1, clockwise=True)
    drive.stop_trace()

    records = motor_log.read_log(TRACE_PATH)
    powers = [(left, right) for _, left, right in records]
    assert powers[1] == (drive.TURN_DUTY_POWER, -drive.TURN_DUTY_POWER), powers
    assert powers[-1] == (0.0, 0.0), "a pivot must end stopped"

    if setup.sim is not None:
        held_ms = records[-1][0] - records[1][0]
        assert held_ms > 0, "the pivot must occupy sim time"
    cleanup()
    print("✓ test_a_pivot_is_traced_as_a_turn_then_a_stop passed")


def test_an_anticlockwise_pivot_reverses_the_pair():
    fresh_trace()
    drive.pivot_in_place(1, clockwise=False)
    drive.stop_trace()
    _, left, right = motor_log.read_log(TRACE_PATH)[1]
    assert (left, right) == (-drive.TURN_DUTY_POWER, drive.TURN_DUTY_POWER)
    cleanup()
    print("✓ test_an_anticlockwise_pivot_reverses_the_pair passed")


def test_driving_without_a_trace_is_silent_not_an_error():
    """Most PC runs never open the trace. drive_motors still records into the
    closed log object, and that must be a no-op."""
    drive.stop_trace()
    assert not drive.MOTOR_TRACE.is_recording()
    drive.drive_motors(0.3, 0.3)
    drive.stop_motors()
    assert not os.path.exists(TRACE_PATH)
    print("✓ test_driving_without_a_trace_is_silent_not_an_error passed")


def test_start_trace_without_force_stays_off_when_a_sim_is_present():
    """On the Pico the trace is on by default, because a run is otherwise
    invisible. On the PC it costs a file for nothing unless --log asks."""
    drive.stop_trace()
    drive.start_trace()
    if setup.sim is None:
        assert drive.MOTOR_TRACE.is_recording(), "hardware runs must always trace"
    else:
        assert not drive.MOTOR_TRACE.is_recording()
    cleanup()
    print("✓ test_start_trace_without_force_stays_off_when_a_sim_is_present passed")


def test_the_log_path_is_config_owned():
    assert config.MOTOR_LOG_PATH.endswith("motor_log.csv")
    assert config.MOTOR_LOG_POWER_EPSILON > 0.0
    print("✓ test_the_log_path_is_config_owned passed")


TESTS = [
    test_the_trace_uses_the_sim_clock_not_the_wall_clock,
    test_start_trace_writes_a_resting_baseline_and_is_idempotent,
    test_only_changed_powers_are_recorded,
    test_the_trace_records_the_clamped_power_the_motors_actually_got,
    test_the_file_carries_the_v1_header,
    test_a_pivot_is_traced_as_a_turn_then_a_stop,
    test_an_anticlockwise_pivot_reverses_the_pair,
    test_driving_without_a_trace_is_silent_not_an_error,
    test_start_trace_without_force_stays_off_when_a_sim_is_present,
    test_the_log_path_is_config_owned,
]

if __name__ == "__main__":
    try:
        for test in TESTS:
            test()
    finally:
        cleanup()
        drive.stop_motors()
    print(f"ALL {len(TESTS)} MOTOR TRACE TESTS PASSED")
