"""Motor command trace -- what the mouse actually drove, for replay on the PC.

The Pico has no renderer and no simulation, so a hardware run is invisible. This
records every commanded motor power to a file on the Pico's own filesystem; copy
it to the PC afterwards and `replay_log.py` re-drives the simulation from it, so
a real run can be watched in the sim that could not observe it live.

Pico-portable: standard builtins only (`time`), no os.path, no f-string-free
constraints beyond what the rest of the deployment set already assumes.

Format (v1), one header block then one record per line:

    # micromouse motor log v1
    # t_ms,left_power,right_power
    0,0.000,0.000
    412,0.550,0.550
    1173,0.000,0.000

`t_ms` is milliseconds since the log was started. `left_power`/`right_power` are
the signed powers in [-1.0, 1.0] handed to drive_motors -- the robot-boundary
contract value, not duty counts, so the trace stays meaningful if the PWM
encoding or the pin map changes.

Records are written only when a commanded power CHANGES. The open-loop driver
holds a power for the whole of each verb, so a full speed run is a few dozen
lines. Replay therefore holds each power until the next timestamp.
"""

import time

import config

LOG_FORMAT_VERSION = 1

# MicroPython counts milliseconds with ticks_ms(); CPython has no such call, so
# fall back to monotonic(). Resolved once at import rather than per record.
try:
    _ticks_ms = time.ticks_ms
    _ticks_diff = time.ticks_diff
except AttributeError:  # CPython
    def _ticks_ms():
        return int(time.monotonic() * 1000.0)

    def _ticks_diff(new, old):
        return new - old


class MotorLog:
    """Append-only trace of commanded motor powers. Not started = does nothing."""

    def __init__(self, path_str, power_epsilon=None, clock_ms=None):
        self.path_str = path_str
        # Where "now" comes from. Defaults to the wall clock, which is correct on
        # the Pico because the drive routines really do sleep. On PC they step
        # physics instead, so sim time and wall time diverge completely and the
        # caller must pass the sim's clock -- otherwise every record in a run
        # lands on the same millisecond.
        self.clock_ms = clock_ms if clock_ms is not None else _ticks_ms
        # Powers closer together than this count as unchanged. Guards against a
        # float round-trip emitting a record that says nothing.
        self.power_epsilon = (
            config.MOTOR_LOG_POWER_EPSILON if power_epsilon is None else power_epsilon
        )
        self._file = None
        self._start_ticks = None
        self._last_powers = None
        self.records_written = 0

    def start(self):
        self._file = open(self.path_str, "w")
        self._file.write(f"# micromouse motor log v{LOG_FORMAT_VERSION}\n")
        self._file.write("# t_ms,left_power,right_power\n")
        self._start_ticks = self.clock_ms()
        self._last_powers = None
        self.records_written = 0
        return self

    def record(self, left_power, right_power):
        """Note a commanded power pair. Writes only if it differs from the last."""
        if self._file is None:
            return

        if self._last_powers is not None:
            last_left, last_right = self._last_powers
            if (abs(left_power - last_left) < self.power_epsilon
                    and abs(right_power - last_right) < self.power_epsilon):
                return

        elapsed_ms = _ticks_diff(self.clock_ms(), self._start_ticks)
        self._file.write(f"{elapsed_ms},{left_power:.3f},{right_power:.3f}\n")
        self._last_powers = (left_power, right_power)
        self.records_written += 1

    def close(self):
        if self._file is None:
            return
        self._file.close()
        self._file = None


def read_log(path_str):
    """Parse a motor log into [(t_ms, left_power, right_power), ...].

    PC-side helper for replay. Comment lines (leading '#') and blanks are skipped.
    """
    records = []
    with open(path_str, "r") as file_handle:
        for line in file_handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            t_ms, left_power, right_power = line.split(",")
            records.append((int(t_ms), float(left_power), float(right_power)))
    return records


### Tests -------------------------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    test_path = "_motor_log_selftest.csv"
    log = MotorLog(test_path).start()

    log.record(0.0, 0.0)
    log.record(0.55, 0.55)
    log.record(0.55, 0.55)   # unchanged: must not add a record
    log.record(0.40, -0.40)
    log.close()

    assert log.records_written == 3, log.records_written

    parsed = read_log(test_path)
    assert len(parsed) == 3
    assert parsed[0][1:] == (0.0, 0.0)
    assert parsed[1][1:] == (0.55, 0.55)
    assert parsed[2][1:] == (0.40, -0.40)
    assert all(parsed[i][0] <= parsed[i + 1][0] for i in range(len(parsed) - 1))

    # A log that was never started swallows records instead of raising.
    quiet = MotorLog(test_path)
    quiet.record(1.0, 1.0)
    assert quiet.records_written == 0

    # An injected clock is what stamps the records: with a sim clock that only
    # advances when physics is stepped, timestamps must follow it and not the
    # wall clock (which barely moves during a PC run).
    fake_time = {"ms": 0}
    timed = MotorLog(test_path, clock_ms=lambda: fake_time["ms"]).start()
    timed.record(0.55, 0.55)
    fake_time["ms"] = 900
    timed.record(0.0, 0.0)
    fake_time["ms"] = 1500
    timed.record(0.40, -0.40)
    timed.close()
    stamps = [record[0] for record in read_log(test_path)]
    assert stamps == [0, 900, 1500], stamps

    os.remove(test_path)
    print("motor_log self-tests passed")
