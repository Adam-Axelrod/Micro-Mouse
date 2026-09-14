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


# Maps and routes. belief.num and route.mmc are run artefacts copied in from the
# committed fixtures in mazes/ and routes/. Provenance: CONSTANTS.md.
DEFAULT_MAZE = _package_path("groundtruth.num")
SAVED_BELIEF_MAZE = _package_path("belief.num")
SAVED_ROUTE = _package_path("route.mmc")
MAZES_DIR = _package_path("mazes")
ROUTES_DIR = _package_path("routes")

# Follow-route mode (mode 6). A closed route driven N times: the offset after N
# laps is the accumulated open-loop error. Mode 5 is this, run long and logged.
FOLLOW_ROUTE_LAPS = 1                  # laps per run; > 1 to accumulate drift
INTER_LAP_SETTLE_S = 1.0               # brake held between laps (s)

# Motor command trace. Written on the Pico during a run, copied to the PC and
# replayed into the sim (see motor_log.py / replay_log.py).
MOTOR_LOG_PATH = _package_path("motor_log.csv")
MOTOR_LOG_POWER_EPSILON = 0.001  # commanded powers closer than this are "unchanged"

# Max speed test (mode 4). One dash at full duty over a marked distance, encoders
# sampled through it, so one run gives both the average speed and the ramp.
MAX_SPEED_LOG_PATH = _package_path("max_speed_test.csv")
MAX_SPEED_TEST_DISTANCE_MM = 5200.0    # 5 m marked run, plus 200 mm of overrun
MAX_SPEED_TEST_POWER = 1.0             # full duty: the point is the ceiling
MAX_SPEED_TEST_COUNTDOWN_BLINKS = 3    # slow LED blinks before the dash starts
MAX_SPEED_TEST_COUNTDOWN_MS = 700      # on-time of one countdown blink (ms)
MAX_SPEED_TEST_BRAKE_HOLD_S = 1.5      # hold the brake this long before reporting (s)
MAX_SPEED_TEST_MAX_DURATION_S = 20.0   # runaway guard on any single dash (s)

# Mode 4 encoder sampling. Polling during the dash turns one run into a velocity
# curve, so the ramp and the terminal speed come out together.
MAX_SPEED_SAMPLE_LOG_PATH = _package_path("max_speed_samples.csv")
MAX_SPEED_SAMPLE_INTERVAL_MS = 20       # encoder poll period during the dash (ms)
MAX_SPEED_SAMPLE_LIMIT = 1200           # pre-allocated sample slots (count)
MAX_SPEED_RAMP_SMOOTH_SAMPLES = 5       # samples averaged into one velocity point (count)
MAX_SPEED_RAMP_PLATEAU_FRACTION = 0.98  # of terminal speed = the ramp is over (fraction)
MAX_SPEED_TABLE_ROW_MS = 100            # one printed table row per this much time (ms)
MAX_SPEED_TABLE_MIN_ROWS = 20           # print every sample rather than fall below this (rows)

# Lap soak (mode 5). The route in SAVED_ROUTE, driven many times, one log row per
# lap. The robot starts at the CENTRE of the start cell. Background: D-023.
SOAK_LOG_PATH = _package_path("lap_soak.csv")
SOAK_LAPS = 30                         # laps per run
# Below cruise duty on purpose. Do not go far under it: the deadband is unmeasured
# and beneath it the wheels do not start at all.
SOAK_DRIVE_POWER = 0.40                # fraction of full duty on a straight
# Not slowed with the straights: a pivot scrubs and needs more duty to break away.
SOAK_TURN_POWER = 0.40                 # fraction of full duty in a pivot
SOAK_ABORT_POLL_S = 0.05               # button poll while settling between laps (s)
SOAK_SENSOR_SAMPLES = 8                # ADC reads averaged into one sensor value (count)
SOAK_EMITTER_SETTLE_S = 0.002          # emitter on/off settle before a read (s)
SOAK_TICK_DROPOUT_FRACTION = 0.5       # of the median lap; below this is a dropout (fraction)
SOAK_SLOWDOWN_WARN_PERCENT = -5.0      # first-to-last tick change that means battery sag (%)

# Compass & grid conventions (North, East, South, West)
DIRECTIONS = ("n", "e", "s", "w")
SIDE_DELTA = {"n": (0, 1), "e": (1, 0), "s": (0, -1), "w": (-1, 0)}
OPPOSITE = {"n": "s", "e": "w", "s": "n", "w": "e"}
WALL_INDEX = {side: i for i, side in enumerate(DIRECTIONS)}
DELTA_SIDE = {delta: side for side, delta in SIDE_DELTA.items()}
# World-frame heading of each compass side, matching SIDE_DELTA: north is +y.
HEADING_RADIANS = {"n": math.pi / 2.0, "e": 0.0, "s": -math.pi / 2.0, "w": math.pi}

START_POS = (0, 0)

# Physical maze dimensions (in mm)
MM_PER_CELL = 180
POST_SIDE_MM = 12
WALL_WIDTH_MM = POST_SIDE_MM
WALL_LENGTH_MM = 168

# Physical mouse dimensions (in mm). MEASURED, ruler, 2026-08-31.
WHEEL_DIAMETER_MM = 32
WHEEL_CIRCUMFERENCE_MM = math.pi * WHEEL_DIAMETER_MM
# mm, wheel centre to centre. MEASURED, ruler, 2026-08-31. Pivot timing divides by
# it. TRAP: a track error and a speed error cancel, so never change one alone.
# Provenance and the full caveat: CONSTANTS.md.
TRACK_WIDTH_MM = 75

# Chassis body frame (in mm)
BODY_LENGTH_MM = 100
BODY_WIDTH_MM = 80
WHEEL_AXIS_TO_BACK_MM = 36
WHEEL_AXIS_TO_FRONT_MM = BODY_LENGTH_MM - WHEEL_AXIS_TO_BACK_MM

# DESIGNED, not measured: 28 edges per motor shaft rev at full quadrature, times
# a 50:1 gearbox. Hold it fixed. If ticks and tape disagree, the ticks are wrong.
ENCODER_COUNTS_PER_WHEEL_REV = 1400
MM_PER_TICK = WHEEL_CIRCUMFERENCE_MM / ENCODER_COUNTS_PER_WHEEL_REV

# mm/s at 100% duty. MEASURED 2026-08-31, mode 4.
# TRAP: an AVERAGE FROM REST over ~5.9 m, not a terminal speed, and nothing models
# the ramp. Short moves fall short. A 180 mm cell is 0.264 s, mostly ramp.
# Provenance: CONSTANTS.md.
MAX_WHEEL_SPEED_MMS = 681.0

# What the SIMULATED robot actually does, as opposed to what the planner above
# believes. MEASURED on the same 2026-08-31 dash, over the marked 5.0 m rather
# than the full 5.9 m, so it carries less of the acceleration ramp.
# The two numbers must stay APART. The sim used to take its speed from the
# planner's constant, so every planned move landed exactly on target and the sim
# could only ever confirm the planner. With its own truth it undershoots by the
# real 5.4%, and open-loop drift is measurable without the robot on the floor.
# Provenance: CONSTANTS.md.
SIM_TRUE_WHEEL_SPEED_MMS = 644.0

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

# Render-only. PX_PER_MM is a FALLBACK: the Renderer picks its own scale per maze
# and stores it, so pixels stay inside the renderer (invariant 4).
PX_PER_MM = 0.25
TILE_PX = MM_PER_CELL * PX_PER_MM
RENDER_TARGET_WINDOW_PX = 720     # longest window edge the renderer aims for (px)
RENDER_MIN_TILE_PX = 24           # below this a cell is unclickable (px)
RENDER_MAX_TILE_PX = 160          # above this a 3x3 fills the screen for nothing (px)

# Render-only, PC-only. Here so invariant 5 holds without an exception; only
# sim/renderer.py reads them and it never goes on the board.
RENDER_MARGIN_PX = 10            # blank border around the maze (px)
RENDER_FPS = 60                  # display throttle, never gates physics (fps)
RENDER_PATH_STEP_DELAY_S = 0.05  # per-cell delay when animating a planned route (s)
RENDER_DONE_STEP_DELAY_S = 0.025 # per-cell delay when animating the walked path (s)
RENDER_MOUSE_OUTLINE_PX = 2      # chassis outline and nose line width (px)

RENDER_BACKGROUND = (0, 0, 0)
RENDER_WALL_KNOWN = (255, 255, 255)    # a wall the belief map has recorded
RENDER_WALL_UNKNOWN = (80, 80, 80)     # a wall in the truth the belief has not seen
RENDER_TILE_DONE = (0, 180, 160)       # cells already walked
RENDER_TILE_PATH = (0, 62, 56)         # cells on the current plan
RENDER_MOUSE_BODY = (220, 60, 60)      # chassis outline
RENDER_MOUSE_NOSE = (255, 200, 0)      # heading line

# Route editor (sim/route_editor.py). PC-only, never read on the Pico.
ROUTE_EDITOR_REJECT_FLASH_S = 0.6      # a refused click stays red this long (s)
ROUTE_EDITOR_DEFAULT_COLS = 3          # --size default: the physical test maze
ROUTE_EDITOR_DEFAULT_ROWS = 3
ROUTE_EDITOR_START_HEADING = "n"       # heading the robot is placed in, before rotation
RENDER_TILE_START = (240, 240, 120)    # the route's first cell
RENDER_TILE_END = (0, 220, 200)        # the route's current last cell
RENDER_TILE_REJECT = (220, 40, 40)     # a click the editor refused
RENDER_HEADING_ARROW = (255, 120, 0)   # the start heading drawn on the start cell
RENDER_HEADING_ARROW_PX = 3            # arrow line width (px)

# The drawn route. A flat fill hides the ORDER, which is the only thing a route
# is, so the polyline and its arrows carry order and direction instead.
RENDER_ROUTE_LINE = (255, 255, 255)    # polyline through the cell centres
RENDER_ROUTE_LINE_PX = 5               # polyline width (px)
RENDER_ROUTE_ARROW_FRACTION = 0.16     # arrowhead size, of a cell (fraction)
RENDER_ROUTE_LABEL = (255, 255, 255)   # step number text
RENDER_ROUTE_LABEL_MIN_TILE_PX = 56    # below this a step number does not fit (px)
RENDER_ROUTE_LABEL_FONT_FRACTION = 0.2 # step number height, of a cell (fraction)
RENDER_END_RING = (255, 90, 160)       # ring drawn inside the route's last cell
RENDER_END_RING_PX = 5                 # ring line width (px)
RENDER_END_RING_INSET = 0.22           # ring inset from the cell edge (fraction)

# Editor status bar. Only the route editor asks for one.
RENDER_HUD_PX = 54                     # height of the status strip (px)
RENDER_HUD_BACKGROUND = (22, 22, 26)
RENDER_HUD_TEXT = (215, 215, 220)
RENDER_HUD_FONT_PX = 15
RENDER_HUD_LINE_PX = 19                # baseline spacing between HUD lines (px)