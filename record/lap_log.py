"""The instrument for mode 5: one CSV row per lap of a route.

Mode 5 drives the same closed route thirty times. The value is not in the last
pose, it is in the SEQUENCE: ticks per lap show the battery sagging, a tick count
far off the median is an encoder dropout, and the heading residual grows lap by
lap if the turns are mistimed. None of that survives in a printed summary, so
every lap is appended to `config.SOAK_LOG_PATH` and kept.

The light sensor columns are here for the wall-distance work that has not been
done yet. `read_light_sensors()` is the lit-minus-unlit primitive from invariant
1; mode 5 samples it while braked at the end of each lap, so the same pose is
read thirty times and any optical drift is visible against the encoders. The
columns are blank when no reading is available, which is what the Pico reports
until the emitters are wired and checked.

On the PC the two halves are always EQUAL: `sim_machine.ADC` answers from the
1/d^2 wall model and ignores the emitter pin entirely, so lit minus unlit is zero
in the sim by construction. The absolute column still carries the modelled wall
distance. A zero difference on hardware means something; in the sim it means
nothing.

Pico-portable: `time`, `config`, `files`, `hal.setup` only.
"""

import time

import config
import files
from hal import setup

LOG_FORMAT_VERSION = 1
LOG_HEADER = "# micromouse lap soak v{}\n".format(LOG_FORMAT_VERSION)

TICK_COLUMNS = ("lap", "elapsed_s", "left_ticks", "right_ticks",
                "d_left", "d_right", "turn_residual_deg")

# Each channel reads lit minus unlit, so both halves are logged: a rising unlit
# reading is ambient light changing, and that would otherwise look like a wall.
SENSOR_CHANNELS = (
    ("left", "leftSensor", "sidesEmitter"),
    ("front", "frontSensor", "frontEmitter"),
    ("right", "rightSensor", "sidesEmitter"),
)
SENSOR_COLUMNS = tuple("{}_{}".format(name, half)
                       for name, _adc, _emitter in SENSOR_CHANNELS
                       for half in ("lit", "unlit"))

LOG_COLUMNS = ",".join(TICK_COLUMNS + SENSOR_COLUMNS) + "\n"


def _read_adc_average(adc, samples):
    total = 0
    for _ in range(samples):
        total += adc.read_u16()
    return total // samples


def read_light_sensors():
    """((lit, unlit), ...) per SENSOR_CHANNELS, or None if a read fails.

    Emitter off, read, emitter on, settle, read, subtract: the robot's sensing
    primitive. Both halves come back because the difference alone hides whether
    a change was the wall or the room.
    """
    samples = config.SOAK_SENSOR_SAMPLES
    settle_s = config.SOAK_EMITTER_SETTLE_S
    readings = []
    try:
        for _name, adc_name, emitter_name in SENSOR_CHANNELS:
            adc = getattr(setup, adc_name)
            emitter = getattr(setup, emitter_name)
            emitter.value(0)
            time.sleep(settle_s)
            unlit = _read_adc_average(adc, samples)
            emitter.value(1)
            time.sleep(settle_s)
            lit = _read_adc_average(adc, samples)
            emitter.value(0)
            readings.append((lit, unlit))
    except Exception:
        return None
    return tuple(readings)


class LapLog:
    """Append-only CSV of one row per lap. Never raises at the call site.

    A soak run is twenty minutes of driving; losing it to a full filesystem at
    lap 29 would be the worst possible failure, so every write is guarded and a
    dead log degrades to printed output instead of an exception.
    """

    def __init__(self, path=None):
        self.path = path or config.SOAK_LOG_PATH
        self._file = None
        self.rows_written = 0
        self.error = None

    def open(self, note=""):
        is_new = not files.file_exists(self.path)
        try:
            self._file = open(self.path, "a")
            if is_new:
                self._file.write(LOG_HEADER)
                self._file.write(LOG_COLUMNS)
            if note:
                self._file.write("# run: {}\n".format(note))
            self._file.flush()
        except OSError as exc:
            self.error = str(exc) or exc.__class__.__name__
            self._file = None
        return self._file is not None

    def record(self, lap, elapsed_s, ticks, deltas, turn_residual_deg, light=None):
        """One lap. `ticks` and `deltas` may be None when no decoder answered."""
        if self._file is None:
            return False
        fields = [
            str(lap),
            "{:.3f}".format(elapsed_s),
            str(ticks[0]) if ticks else "",
            str(ticks[1]) if ticks else "",
            str(deltas[0]) if deltas else "",
            str(deltas[1]) if deltas else "",
            "{:.2f}".format(turn_residual_deg) if turn_residual_deg is not None else "",
        ]
        for index in range(len(SENSOR_CHANNELS)):
            lit, unlit = light[index] if light else ("", "")
            fields.append(str(lit))
            fields.append(str(unlit))
        try:
            self._file.write(",".join(fields) + "\n")
            self._file.flush()
        except OSError as exc:
            self.error = str(exc) or exc.__class__.__name__
            return False
        self.rows_written += 1
        return True

    def close(self):
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None
