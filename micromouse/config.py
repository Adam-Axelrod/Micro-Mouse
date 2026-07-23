import math
import os

# Base directory for the micromouse package
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

# Default maze files (treats PACKAGE_DIR as root for MicroPython compatibility)
DEFAULT_MAZE = os.path.join(PACKAGE_DIR, "groundtruth.num")
SAVED_BELIEF_MAZE = os.path.join(PACKAGE_DIR, "belief.num")

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

# Render-only pixel scale
PX_PER_MM = 0.25
TILE_PX = MM_PER_CELL * PX_PER_MM