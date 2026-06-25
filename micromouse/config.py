import math
from pathlib import Path

# --- Paths (resolved relative to the repo, so no absolute paths ever) --------
PACKAGE_DIR = Path(__file__).resolve().parent          # .../Micro-Mouse/micromouse_new
REPO_DIR = PACKAGE_DIR.parent                          # .../Micro-Mouse
EXAMPLE_MAZES_DIR = REPO_DIR / "mazes" / "example_mazes"
GENERATED_MAZES_DIR = REPO_DIR / "mazes" / "generated_mazes"
DEFAULT_MAZE = EXAMPLE_MAZES_DIR / "example4.num"

### Compass / grid convention (single source of truth) ----------------------
# Every module that talks about sides, steps or wall slots imports these so the
# n/e/s/w ordering is defined exactly once. Lives here in config (the lowest
# layer) so maze.py and explorer.py can share it without depending on each other.

DIRECTIONS = ("n", "e", "s", "w")                  # side order; also the (n,e,s,w) wall-tuple order
SIDE_DELTA = {"n": (0, 1), "e": (1, 0), "s": (0, -1), "w": (-1, 0)}  # (dx, dy) step per side
OPPOSITE = {"n": "s", "e": "w", "s": "n", "w": "e"}                  # mirror side across a shared wall
WALL_INDEX = {side: i for i, side in enumerate(DIRECTIONS)}          # side -> slot in a wall tuple
DELTA_SIDE = {delta: side for side, delta in SIDE_DELTA.items()}     # inverse of SIDE_DELTA

START_POS = (0, 0)                                 # bottom-left cell; the mouse always starts here

### Maze attributes (all lengths in millimetres) ----------------------------

MM_PER_CELL = 180          # Centre-to-centre distance between cells.
POST_SIDE_MM = 12          # Posts that hold up the walls, same width as the walls.
WALL_WIDTH_MM = POST_SIDE_MM  # Makes the maze a maze, same width as the posts.
WALL_LENGTH_MM = 168       # Long side of a wall.

### Mouse attributes (all lengths in millimetres) ---------------------------

WHEEL_DIAMETER_MM = 32                                  # Pololu 32x7 wheel.
WHEEL_CIRCUMFERENCE_MM = math.pi * WHEEL_DIAMETER_MM    # ~100.53 mm; derived, never hard-coded.
TRACK_WIDTH_MM = 70  # PROVISIONAL: wheel separation. MEASURE on chassis (story 9.2).
# MAX_SPEED = No #m/s or turns tbd

### Encoder (provisional; confirm by SIM-4 / HW-1) --------------------------
# Encoder rule: keep ONE measured count here, derive everything else from it.
# Every distance is ticks * MM_PER_TICK, so this cannot drift out of sync.
ENCODER_COUNTS_PER_WHEEL_REV = 500  # PROVISIONAL: full-quadrature counts per wheel rev.
                                    # CONFIRM: push robot a measured distance, read ticks (HW-1).
MM_PER_TICK = WHEEL_CIRCUMFERENCE_MM / ENCODER_COUNTS_PER_WHEEL_REV  # ~0.20 mm/tick; derived.

### Render-only pixel scale (no logic code reads pixels) ---------------------

PX_PER_MM = 0.5                          # Render scale only.
TILE_PX = MM_PER_CELL * PX_PER_MM        # Pixel size of one cell when drawing.



""" will integrate properly soon enough
### Gemini platform (drive and sensing)

| Quantity | Value | Class | Notes |
|---|---|---|---|
| Wheel diameter | 32 mm (Pololu 32x7) | FIXED | Circumference = pi x 32 = 100.53 mm. |
| Cell in wheel revs | 180 / 100.53 = 1.79 rev | FIXED | Do not assume exactly 1 rev per cell. |
| Top speed | ~1.0 m/s no-load | FIXED-ish | N20 ~600 rpm at 12 V x 100.5 mm. Cap lower for safety. |
| Track width (wheel separation) | MEASURE | MEASURE | Needed for differential-drive kinematics. Measure on the chassis; put a named provisional in config. |
| Motor | N20 micro metal gearmotor | FIXED | Brushed DC, gearbox. |
| Encoder | magnetic Hall quadrature | FIXED | On the motor shaft. Counts per wheel rev = CPR_at_shaft x gear_ratio (full quadrature). |
| Encoder resolution | ~0.2 mm/tick, ~900 ticks/cell | MEASURE | Order of magnitude only. Confirm exact CPR and gear ratio (SIM-4, HW-1). |

**Encoder rule (design this so it cannot be wrong):** put one constant
`ENCODER_COUNTS_PER_WHEEL_REV` in config, then derive
`MM_PER_TICK = WHEEL_CIRCUMFERENCE_MM / ENCODER_COUNTS_PER_WHEEL_REV`. Every
distance is `ticks * MM_PER_TICK`. The exact count is confirmed by pushing the
real robot a measured distance and reading ticks (SIM-4 done-when, HW-1).

**Pixels:** `PX_PER_MM` is a render-only scale in config. `TILE_PX = 180 *
PX_PER_MM`. No logic reads pixels.
"""