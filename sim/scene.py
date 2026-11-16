"""The simulated world: maze, mouse, renderer, and the clock that moves them. PC only.

`hal.setup.scene(...)` returns a `Scene` here, and `hal.setup.wait`, `now_ms` and
`diff_ms` are the three functions below. A mode asks setup for them and never
learns that a simulator stands behind them.

On the robot time passes by itself. In the simulation it passes only when
`wait` steps the physics, and that is also the moment to draw: a frame every
`RENDER_EVERY_N_STEPS` steps, through the scene that `Scene(...)` made last. A
frame only reads the pose, so a run gives the same result with and without it.

Never deployed to the board. `pygame` is reached only through `sim.renderer`. A
machine without it runs headless: the renderer import fails and no window opens.
"""

import config
from brain import maze
from sim import render_config
from sim import sim_machine

try:
    from sim.renderer import make_renderer
except ImportError:  # no pygame: every run is headless
    make_renderer = None

# The scene that `wait` draws through. The last `Scene(...)` made owns it.
_active = None

now_ms = sim_machine.sim_time_ms


def diff_ms(new_ms, old_ms):
    """Milliseconds from `old_ms` to `new_ms`. Simulated time never wraps."""
    return new_ms - old_ms


def wait(seconds):
    """Let `seconds` of simulated time pass: step the physics, drawing as it goes."""
    dt = config.SIM_TIMESTEP_S
    # Whole steps plus the leftover. Rounding to whole steps instead put a
    # systematic error on every short move -- a 0.216 s pivot became 0.22 s and
    # turned 91.6 degrees -- which would show up as sim/hardware divergence that
    # the hardware had not actually caused.
    total_steps = int(seconds / dt)
    remainder = seconds - total_steps * dt
    for _ in range(total_steps):
        sim_machine.step_sim_physics(dt)
        if _active is not None:
            _active._stepped()

    if remainder > 0.0:
        sim_machine.step_sim_physics(remainder)


def place_sim_mouse(start_pose):
    """Put the simulated mouse in the middle of `start_pose`'s cell, facing it.

    The sim always begins at (0, 0) facing north. A route drawn from anywhere
    else would replay from the wrong square, which looks like a drive bug.
    """
    x, y, heading = start_pose
    sim_machine.get_mouse_state().reset_pose(
        (x + 0.5) * config.MM_PER_CELL,
        (y + 0.5) * config.MM_PER_CELL,
        config.HEADING_RADIANS[heading])


class Scene:
    """What a run happens in: the maze loaded into the sim, and an optional window.

    With no map file but a `grid`, the world is a blank grid of that size. A
    hand-drawn 3x3 route has no maze file behind it, and drawing it on the 16x16
    default would put the mouse in the wrong world entirely. `start_pose`
    places the mouse in the middle of that cell, facing its heading.
    """

    def __init__(self, map_path=None, grid=None, start_pose=None, render=False):
        global _active
        if map_path:
            real_maze = maze.MazeStructure(*maze.num_file_import(map_path))
        elif grid:
            real_maze = maze.MazeStructure(cols=grid[0], rows=grid[1])
        else:
            real_maze = maze.MazeStructure(*maze.num_file_import(config.DEFAULT_MAZE))
        self.maze = real_maze
        sim_machine.set_sim_maze(real_maze)
        if start_pose is not None:
            place_sim_mouse(start_pose)
        self._renderer = make_renderer(real_maze) if render and make_renderer else None
        self._belief = real_maze
        self._route = None
        self._done = None
        self._steps = 0
        _active = self

    def show(self, belief=None, route=None, done=None, animate=False):
        """Set what the next frames draw, and draw one now.

        `belief` is the map whose walls count as known: the true maze when None.
        `route` is the planned cells, `done` the cells already walked. `animate`
        paints them one cell at a time.
        """
        self._belief = belief if belief is not None else self.maze
        self._route = route
        self._done = done
        self._draw(animate)

    def pose(self):
        """(x_mm, y_mm, heading_radians) of the simulated mouse."""
        state = sim_machine.get_mouse_state()
        return state.x_mm, state.y_mm, state.heading_radians

    def _stepped(self):
        """One physics step passed: draw every RENDER_EVERY_N_STEPS-th one."""
        if self._steps % render_config.RENDER_EVERY_N_STEPS == 0:
            self._draw(False)
        self._steps += 1

    def _draw(self, animate):
        if self._renderer is None:
            return
        self._renderer.draw(belief=self._belief, mouse=sim_machine.get_mouse_state(),
                            path=self._route, done=self._done, animate=animate)
