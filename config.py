import math
import os

# Base directory for the micromouse package. MicroPython's os has no `path`
# submodule; on the Pico the package runs from the filesystem root, so bare
# filenames resolve correctly there.
try:
    PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
except AttributeError:  # MicroPython
    PACKAGE_DIR = ""


def _package_path(filename):
    return PACKAGE_DIR + "/" + filename if PACKAGE_DIR else filename


# Default maze files
DEFAULT_MAZE = _package_path("groundtruth.num")
SAVED_BELIEF_MAZE = _package_path("belief.num")

# Motor command trace. Written on the Pico during a run, copied to the PC and
# replayed into the sim (see motor_log.py / replay_log.py).
MOTOR_LOG_PATH = _package_path("motor_log.csv")
MOTOR_LOG_POWER_EPSILON = 0.001  # commanded powers closer than this are "unchanged"

# Compass & grid conventions (North, East, South, West)
DIRECTIONS = ("n", "e", "s", "w")
SIDE_DELTA = {"n": (0, 1), "e": (1, 0), "s": (0, -1), "w": (-1, 0)}
OPPOSITE = {"n": "s", "e": "w", "s": "n", "w": "e"}
WALL_INDEX = {side: i for i, side in enumerate(DIRECTIONS)}
DELTA_SIDE = {delta: side for side, delta in SIDE_DELTA.items()}

START_POS = (0, 0)

# Physical maze dimensions (in mm)
MM_PER_CELL = 180
POST_SIDE_MM = 12
WALL_WIDTH_MM = POST_SIDE_MM
WALL_LENGTH_MM = 168

# Physical mouse dimensions (in mm)
WHEEL_DIAMETER_MM = 32
WHEEL_CIRCUMFERENCE_MM = math.pi * WHEEL_DIAMETER_MM
TRACK_WIDTH_MM = 70

# Chassis body frame (in mm)
BODY_LENGTH_MM = 100
BODY_WIDTH_MM = 80
WHEEL_AXIS_TO_BACK_MM = 36
WHEEL_AXIS_TO_FRONT_MM = BODY_LENGTH_MM - WHEEL_AXIS_TO_BACK_MM

# Encoder calibration
ENCODER_COUNTS_PER_WHEEL_REV = 1400
MM_PER_TICK = WHEEL_CIRCUMFERENCE_MM / ENCODER_COUNTS_PER_WHEEL_REV

# Motor limits (SIM-3): wheel ground speed at 100% duty. Provisional until measured;
# N20 no-load ceiling is ~1000 mm/s (~600 rpm x wheel circumference), capped lower.
MAX_WHEEL_SPEED_MMS = 600.0

# Open-loop drive powers, signed fraction of full duty in [-1.0, 1.0].
# Provisional: derived from the motor model, not measured on the chassis.
CRUISE_DUTY_POWER = 0.55
TURN_DUTY_POWER = 0.40

# Fixed simulation timestep (s). The sim is deterministic in this step, not in
# wall-clock time; the renderer samples it but never sets it.
SIM_TIMESTEP_S = 0.01

# Reflective sensor mounts, in the body frame: +forward (mm), +right (mm), and
# the sensor's angle relative to the mouse heading (radians, + = left/CCW).
SENSOR_MOUNTS = {
    "left":  {"forward_mm": 45.0, "lateral_mm": -25.0, "angle_rad":  math.pi / 4.0},
    "right": {"forward_mm": 45.0, "lateral_mm":  25.0, "angle_rad": -math.pi / 4.0},
    "front": {"forward_mm": 50.0, "lateral_mm":   0.0, "angle_rad":  0.0},
}

# Phototransistor model: intensity = SCALE / (distance + OFFSET)^2, clamped to a
# 16-bit ADC range. Provisional -- these are the numbers HW calibration replaces.
SENSOR_RANGE_MM = 250.0          # ray cap; beyond this the sensor reads the floor
SENSOR_BACKGROUND_MM = 240.0     # distance at/after which nothing is seen
SENSOR_ADC_FLOOR = 200           # unlit background reading (16-bit counts)
SENSOR_ADC_CEILING = 65535       # 16-bit ADC saturation
SENSOR_INTENSITY_SCALE = 4.5e7   # counts * mm^2
SENSOR_DISTANCE_OFFSET_MM = 15.0 # emitter-to-target standoff in the 1/d^2 law

# Render-only pixel scale
PX_PER_MM = 0.25
TILE_PX = MM_PER_CELL * PX_PER_MM