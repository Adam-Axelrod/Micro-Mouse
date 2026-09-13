"""One clock for every timed run, on either target.

The Pico really sleeps through a drive, so its wall clock times it. The PC steps
physics instead and its wall clock barely moves, so in the sim only the sim's own
clock means anything. Every mode that times something needs the same three lines,
and `max_speed_test` and `motor_log` each used to carry a private copy.

Pico-portable: `time`, `setup` only.
"""

import time

import setup

HAS_SIM = setup.sim is not None

if HAS_SIM:
    now_ms = setup.sim.sim_time_ms
elif hasattr(time, "ticks_ms"):
    now_ms = time.ticks_ms
else:
    def now_ms():
        return int(time.monotonic() * 1000.0)

if hasattr(time, "ticks_diff") and not HAS_SIM:
    diff_ms = time.ticks_diff
else:
    def diff_ms(new_ms, old_ms):
        return new_ms - old_ms


def elapsed_s(since_ms):
    return diff_ms(now_ms(), since_ms) / 1000.0
