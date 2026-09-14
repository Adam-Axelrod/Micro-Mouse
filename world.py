"""The one place a run's world and renderer are set up.

Both are optional. On the Pico there is no sim and no renderer, so every
function here returns None and the mode runs headless. Kept out of `motion.py`
because that module owns TIMING, and out of the modes because two of them need
the same world.

Pico-portable: `config`, `setup`, `brain` only. The renderer import is guarded.
"""

import config
from brain import maze
import setup

# Rendering is PC-only and optional. The `sim` package is never deployed to the
# board, so on the Pico this import fails and every mode runs headless.
try:
    from sim.renderer import make_renderer
except ImportError:
    def make_renderer(real_maze):
        return None

HAS_SIM = setup.sim is not None


def sim_world(map_path=None, enable_render=False, grid=None, start_pose=None):
    """Load the maze the sim and the renderer should use.

    Returns (render_object, real_maze); either may be None. The maze comes back
    as well as the renderer because a caller with no belief map of its own still
    has to give the renderer something to draw.

    With no map file but a `grid`, the world is a blank grid of that size. A
    hand-drawn 3x3 route has no maze file behind it, and drawing it on the 16x16
    default would put the mouse in the wrong world entirely.
    """
    if not (HAS_SIM or enable_render):
        return None, None
    if map_path:
        real_maze = maze.MazeStructure(*maze.num_file_import(map_path))
    elif grid:
        real_maze = maze.MazeStructure(cols=grid[0], rows=grid[1])
    else:
        real_maze = maze.MazeStructure(*maze.num_file_import(config.DEFAULT_MAZE))
    if HAS_SIM:
        setup.sim.set_sim_maze(real_maze)
        if start_pose is not None:
            place_sim_mouse(start_pose)
    return (make_renderer(real_maze) if enable_render else None), real_maze


def place_sim_mouse(start_pose):
    """Put the simulated mouse in the middle of `start_pose`'s cell, facing it.

    The sim always begins at (0, 0) facing north. A route drawn from anywhere
    else would replay from the wrong square, which looks like a drive bug.
    """
    x, y, heading = start_pose
    setup.sim.get_mouse_state().reset_pose(
        (x + 0.5) * config.MM_PER_CELL,
        (y + 0.5) * config.MM_PER_CELL,
        config.HEADING_RADIANS[heading])
