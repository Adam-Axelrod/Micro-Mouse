"""Contract: the lap log. A soak run is twenty minutes of driving, and the CSV is
all that survives it, so a row must be complete and a write must never raise.
"""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_DIR = os.path.dirname(TESTS_DIR)
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import tempfile

from record import lap_log

LIGHT = ((1200, 200), (900, 210), (1100, 205))


def fresh_log():
    path = os.path.join(tempfile.mkdtemp(), "lap_soak.csv")
    log = lap_log.LapLog(path)
    assert log.open(note="test"), log.error
    return log


def rows(path):
    """Data rows only: the comments and the column line are not laps."""
    skip = ("#", lap_log.LOG_COLUMNS.split(",")[0])
    with open(path) as handle:
        return [line.rstrip("\n") for line in handle
                if line.strip() and not line.startswith(skip)]


def test_a_new_log_starts_with_a_version_and_a_column_line():
    log = fresh_log()
    log.close()
    with open(log.path) as handle:
        lines = handle.read().split("\n")
    assert lines[0] == lap_log.LOG_HEADER.strip(), lines[0]
    assert lines[1] == lap_log.LOG_COLUMNS.strip(), lines[1]
    assert lines[2].startswith("# run: test"), lines[2]
    print("✓ test_a_new_log_starts_with_a_version_and_a_column_line passed")


def test_every_row_has_one_field_per_column():
    log = fresh_log()
    log.record(1, 5.5, (100, 101), (100, 101), 0.25, LIGHT)
    log.record(2, 5.5, None, None, None, None)
    log.close()
    expected = len(lap_log.LOG_COLUMNS.strip().split(","))
    for row in rows(log.path):
        assert len(row.split(",")) == expected, row
    print("✓ test_every_row_has_one_field_per_column passed")


def test_a_lap_with_no_encoder_leaves_the_tick_fields_empty():
    log = fresh_log()
    log.record(1, 5.5, None, None, None, None)
    log.close()
    fields = rows(log.path)[0].split(",")
    assert fields[0] == "1", fields
    assert fields[2:] == [""] * (len(fields) - 2), fields
    print("✓ test_a_lap_with_no_encoder_leaves_the_tick_fields_empty passed")


def test_both_halves_of_every_light_reading_are_kept():
    """lit alone cannot tell a wall from the room lights changing."""
    log = fresh_log()
    log.record(1, 5.5, (0, 0), (0, 0), 0.0, LIGHT)
    log.close()
    fields = rows(log.path)[0].split(",")
    assert fields[-6:] == ["1200", "200", "900", "210", "1100", "205"], fields
    print("✓ test_both_halves_of_every_light_reading_are_kept passed")


def test_a_second_run_appends_without_a_second_header():
    log = fresh_log()
    log.record(1, 1.0, None, None, None, None)
    log.close()
    again = lap_log.LapLog(log.path)
    again.open(note="second")
    again.record(1, 1.0, None, None, None, None)
    again.close()
    with open(log.path) as handle:
        text = handle.read()
    assert text.count(lap_log.LOG_HEADER) == 1, text
    assert text.count("# run:") == 2, text
    print("✓ test_a_second_run_appends_without_a_second_header passed")


def test_a_log_that_will_not_open_degrades_instead_of_raising():
    log = lap_log.LapLog(os.path.join(tempfile.gettempdir(), "no_such_dir", "x.csv"))
    assert not log.open(), "opening a path with no directory should fail"
    assert log.error, "the reason must be kept for the operator"
    assert not log.record(1, 1.0, None, None, None, None), "a dead log records nothing"
    log.close()
    print("✓ test_a_log_that_will_not_open_degrades_instead_of_raising passed")


def test_the_sensor_primitive_reads_both_halves_or_answers_none():
    reading = lap_log.read_light_sensors()
    assert reading is None or len(reading) == len(lap_log.SENSOR_CHANNELS), reading
    if reading is not None:
        for lit, unlit in reading:
            assert isinstance(lit, int) and isinstance(unlit, int), reading
    print("✓ test_the_sensor_primitive_reads_both_halves_or_answers_none passed")


TESTS = (
    test_a_new_log_starts_with_a_version_and_a_column_line,
    test_every_row_has_one_field_per_column,
    test_a_lap_with_no_encoder_leaves_the_tick_fields_empty,
    test_both_halves_of_every_light_reading_are_kept,
    test_a_second_run_appends_without_a_second_header,
    test_a_log_that_will_not_open_degrades_instead_of_raising,
    test_the_sensor_primitive_reads_both_halves_or_answers_none,
)


if __name__ == "__main__":
    for test in TESTS:
        test()
    print("ALL {} LAP LOG TESTS PASSED".format(len(TESTS)))
