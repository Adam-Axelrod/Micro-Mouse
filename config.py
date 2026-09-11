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


# Maps and routes. Two working files sit at the package root and are what the
# robot actually reads; both are run artefacts, and both are copied in from a
# committed fixture directory.
#
#   committed fixture        working file      read by
#   mazes/*.num              belief.num        mode 2, which plans over it
#   routes/*.mmc             route.mmc         mode 6, which follows it verbatim
#
DEFAULT_MAZE = _package_path("groundtruth.num")
SAVED_BELIEF_MAZE = _package_path("belief.num")
SAVED_ROUTE = _package_path("route.mmc")
MAZES_DIR = _package_path("mazes")
ROUTES_DIR = _package_path("routes")

# Follow-route mode (mode 6). Driving a CLOSED route N times is the maze-relevant
# stress test: every lap should return the robot to where it started, so the
# offset after N laps is the accumulated open-loop error. Unlike mode 5's
# corridor sprint, the turns accumulate too.
FOLLOW_ROUTE_LAPS = 1                  # laps per run; > 1 to accumulate drift
INTER_LAP_SETTLE_S = 1.0               # brake held between laps (s)

# Motor command trace. Written on the Pico during a run, copied to the PC and
# replayed into the sim (see motor_log.py / replay_log.py).
MOTOR_LOG_PATH = _package_path("motor_log.csv")
MOTOR_LOG_POWER_EPSILON = 0.001  # commanded powers closer than this are "unchanged"

# Straight-line max speed test (mode 4). Drives one open-loop dash at full duty
# over a marked distance, so a stopwatch can put a measured number behind
# MAX_WHEEL_SPEED_MMS below -- which has never been measured.
MAX_SPEED_LOG_PATH = _package_path("max_speed_test.csv")
MAX_SPEED_TEST_DISTANCE_MM = 5200.0    # 5 m marked run, plus 200 mm of overrun
MAX_SPEED_TEST_POWER = 1.0             # full duty: the point is the ceiling
MAX_SPEED_TEST_COUNTDOWN_BLINKS = 3    # slow LED blinks before the dash starts
MAX_SPEED_TEST_COUNTDOWN_MS = 700      # on-time of one countdown blink (ms)
MAX_SPEED_TEST_BRAKE_HOLD_S = 1.5      # hold the brake this long before reporting (s)
MAX_SPEED_TEST_MAX_DURATION_S = 20.0   # runaway guard on any single dash (s)

# --- Mode 4 encoder sampling: the acceleration ramp ---------------------------
# MAX_WHEEL_SPEED_MMS below is an AVERAGE FROM REST, because one dash used to
# yield one number. Polling the encoders DURING the dash turns the same run into
# a velocity curve, so the ramp duration and the terminal speed come out of a
# single run instead of a series of dashes at different distances.
MAX_SPEED_SAMPLE_LOG_PATH = _package_path("max_speed_samples.csv")
MAX_SPEED_SAMPLE_INTERVAL_MS = 20       # encoder poll period during the dash (ms)
MAX_SPEED_SAMPLE_LIMIT = 1200           # pre-allocated sample slots (count)
MAX_SPEED_RAMP_SMOOTH_SAMPLES = 5       # samples averaged into one velocity point (count)
MAX_SPEED_RAMP_PLATEAU_FRACTION = 0.98  # of terminal speed = the ramp is over (fraction)
MAX_SPEED_TABLE_ROW_MS = 100            # one printed table row per this much time (ms)
MAX_SPEED_TABLE_MIN_ROWS = 20           # print every sample rather than fall below this (rows)
# --- end mode 4 encoder sampling ----------------------------------------------

# Stress test (mode 5). Drives the sprint out and back N times to amplify small
# per-move errors, then reports where the encoders think it ended up. Run at a
# lower power than mode 4: the direction reversal is the harshest thing the
# gearbox sees, and a gentler leg keeps the jolt out of the measurement.
STRESS_LOG_PATH = _package_path("stress_test.csv")
STRESS_TEST_LAPS = 20                  # one lap = out and back
STRESS_TEST_DISTANCE_MM = 5000.0       # one leg
STRESS_TEST_POWER = 0.45               # fraction of full duty
STRESS_TEST_SETTLE_S = 1.0             # brake held between legs, before reversing (s)
STRESS_TEST_ABORT_POLL_S = 0.05        # button poll while settling between legs (s)

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
# Ruler-confirmed 2026-08-31. The EFFECTIVE rolling diameter under the robot's
# weight is a little smaller (tyre compression), never larger, but on a hard
# small wheel that gap is tenths of a mm, not millimetres.
WHEEL_DIAMETER_MM = 32
WHEEL_CIRCUMFERENCE_MM = math.pi * WHEEL_DIAMETER_MM
# Ruler, wheel centre to wheel centre, 2026-08-31. This replaces an unmeasured
# 70 and BT-8's encoder-derived ~66; BT-8 says itself that the ruler is the check
# on the derivation, not the reverse. Pivot timing divides by this, so a wrong
# value shows up as every turn being off by the same percentage.
# Caveat: the kinematic track is between the tyre CONTACT patches, and a pivot
# scrubs, so the effective value can sit a few percent off the geometric one. A
# powered 360 x N pivot against a heading line is what would settle that.
TRACK_WIDTH_MM = 75

# Chassis body frame (in mm)
BODY_LENGTH_MM = 100
BODY_WIDTH_MM = 80
WHEEL_AXIS_TO_BACK_MM = 36
WHEEL_AXIS_TO_FRONT_MM = BODY_LENGTH_MM - WHEEL_AXIS_TO_BACK_MM

# Encoder calibration. This is a DESIGNED INTEGER, not a measurement: the
# encoder's edges per motor shaft revolution times the gearbox ratio (28 edges
# from a 7-pole ring at full quadrature, times 50:1). Hold it fixed. The wheel
# and track are ruler-confirmed too, so if ticks and tape disagree the error is
# in the TICKS: the decoder is dropping edges. BT-7 (~1306) and BT-8 (~66) were
# both that fault, not measurements of the chassis.
ENCODER_COUNTS_PER_WHEEL_REV = 1400
MM_PER_TICK = WHEEL_CIRCUMFERENCE_MM / ENCODER_COUNTS_PER_WHEEL_REV

# Wheel ground speed at 100% duty. MEASURED 2026-08-31, mode 4: 5904 mm of wheel
# travel in 8.667 s. Taken from the encoders, not the stopwatch, because the tape
# confirmed them to 1.6% on that run and they carry no human reaction time.
#
# Read it as an AVERAGE FROM REST over ~5.9 m, not as a terminal speed. The same
# run timed 5000 mm in 7.77 s by hand, i.e. 644 mm/s: a shorter run averaging
# lower is the acceleration ramp showing itself. Terminal speed is above 681 and
# nothing has measured it.
#
# Nothing anywhere models that ramp -- not commands.py, not the sim, which jumps
# to full speed in one timestep. So this constant is only honest for moves of a
# few metres. A 180 mm cell commands 0.264 s of drive, which is mostly ramp, and
# will fall short. Short-move timing needs its own calibration.
MAX_WHEEL_SPEED_MMS = 681.0

# Open-loop drive powers, signed fraction of full duty in [-1.0, 1.0].
# Provisional: derived from the motor model, not measured on the chassis.
CRUISE_DUTY_POWER = 0.55
TURN_DUTY_POWER = 0.40

# Brake held between two movement verbs, so a pivot does not start while the
# chassis is still rocking from the drive before it (s).
INTER_COMMAND_SETTLE_S = 0.1

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

# Render-only, PC-only. Every one of these was a literal inside renderer.py,
# against invariant 5. They are here so the invariant holds without an exception,
# not because the Pico will ever read them -- `sim/renderer.py` is the only
# consumer and it never goes on the board.
RENDER_MARGIN_PX = 10            # blank border around the maze (px)
RENDER_FPS = 60                  # display throttle, never gates physics (fps)
RENDER_PATH_STEP_DELAY_S = 0.05  # per-cell delay when animating a planned route (s)
RENDER_DONE_STEP_DELAY_S = 0.025 # per-cell delay when animating the walked path (s)
RENDER_MOUSE_OUTLINE_PX = 2      # chassis outline and nose line width (px)

RENDER_BACKGROUND = (0, 0, 0)
RENDER_WALL_KNOWN = (255, 255, 255)    # a wall the belief map has recorded
RENDER_WALL_UNKNOWN = (80, 80, 80)     # a wall in the truth the belief has not seen
RENDER_TILE_DONE = (0, 180, 160)       # cells already walked
RENDER_TILE_PATH = (0, 90, 80)         # cells on the current plan
RENDER_MOUSE_BODY = (220, 60, 60)      # chassis outline
RENDER_MOUSE_NOSE = (255, 200, 0)      # heading line

# Route editor (sim/route_editor.py). PC-only, never read on the Pico.
ROUTE_EDITOR_REJECT_FLASH_S = 0.6      # a refused click stays red this long (s)
RENDER_TILE_START = (240, 240, 120)    # the route's first cell
RENDER_TILE_END = (0, 220, 200)        # the route's current last cell
RENDER_TILE_REJECT = (220, 40, 40)     # a click the editor refused