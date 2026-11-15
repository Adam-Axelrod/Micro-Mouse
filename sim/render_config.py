"""Constants that only the PC window reads: the renderer and the route editor.

Nothing here goes on the board. config.py holds the constants that a deployed
file reads.
"""
import config

# PX_PER_MM is a FALLBACK: the Renderer picks its own scale per maze
# and stores it, so pixels stay inside the renderer (invariant 4).
PX_PER_MM = 0.25
TILE_PX = config.MM_PER_CELL * PX_PER_MM
RENDER_TARGET_WINDOW_PX = 720     # longest window edge the renderer aims for (px)
RENDER_MIN_TILE_PX = 24           # below this a cell is unclickable (px)
RENDER_MAX_TILE_PX = 160          # above this a 3x3 fills the screen for nothing (px)

# Window and animation. Only sim/renderer.py reads them.
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

# Route editor (sim/route_editor.py).
ROUTE_EDITOR_REJECT_FLASH_S = 0.6      # a refused click stays red this long (s)
ROUTE_EDITOR_DEFAULT_COLS = 3          # --size default: the physical test maze
ROUTE_EDITOR_DEFAULT_ROWS = 3
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
