"""Draw a route by hand, click by click, and write it as a .mmc file. PC-only.

Today the only other way to get a route is to let flood fill plan one. That makes
every test of the motion layer a test of the planner as well. This tool separates
them: click the cells you want, save, and drive that file. Nothing about the
planner is involved, so a route that is driven wrongly is the drive layer's fault.

    python3 sim/route_editor.py                      # 3x3 blank grid -> route.mmc
    python3 sim/route_editor.py --size 16x16         # any grid, no maze file needed
    python3 sim/route_editor.py mazes/test_mazes/blank3x3.num   # walls from a file
    python3 sim/route_editor.py --out routes/hairpin.mmc        # save a fixture

Saving with no --out writes `route.mmc` at the package root: the working file the
robot carries, so `python3 main.py --follow` drives what you just drew. `routes/`
holds fixtures worth keeping.

Controls, also shown in the window's status bar:
    left click   append the cell to the route
    u / backspace  undo the last cell (or click the last cell again)
    r            rotate the start heading (n -> e -> s -> w)
    s            save, and print the verb list
    c            clear the route
    q / escape   quit

The first cell clicked is the START and the last is the END; both are written
into the file's header along with the start heading, because .mmc verbs are
egocentric. The same verb list drives a different shape from a different start
pose, and on a grid that is not 16x16 there is no centre convention to fall back
on, so the pose has to travel with the route.

The route must stay walkable: a click is refused unless the cell is orthogonally
adjacent to the current end and the maze says no wall stands between them. A
refusal flashes the cell red; it is never silently dropped.

This file holds NO pygame and NO pixels. It asks the renderer for input already
translated into cells, and hands it cells to colour in. Serialising is
`commands.path_to_commands` + `commands.render_command_file`, which already
define the .mmc format -- there is no second writer here.
"""

import os
import sys
import time

# Runnable directly (`python3 sim/route_editor.py`), which puts sim/ on sys.path
# instead of the package root. Everything below imports from the root, so it has
# to be added before anything else is imported.
PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

from brain import commands  # noqa: E402
import config  # noqa: E402
import files  # noqa: E402
from brain import maze  # noqa: E402
from sim import renderer  # noqa: E402


def parse_grid_size(text):
    """'16x16' or '3' -> (cols, rows). Raises ValueError on anything else."""
    cols, _, rows = text.lower().partition("x")
    cols = int(cols)
    rows = int(rows) if rows else cols
    if cols < 1 or rows < 1:
        raise ValueError("a grid needs at least one cell per side")
    return cols, rows


def step_is_legal(maze_structure, from_cell, to_cell):
    """True if `to_cell` is one open orthogonal step from `from_cell`.

    Returns the reason string instead when it is not, so the caller can say why.
    """
    delta = (to_cell[0] - from_cell[0], to_cell[1] - from_cell[1])
    side = config.DELTA_SIDE.get(delta)
    if side is None:
        return "not orthogonally adjacent to {}".format(from_cell)
    if maze_structure.cells[from_cell][config.WALL_INDEX[side]]:
        return "a wall stands on the {} side of {}".format(side, from_cell)
    return None


def save_route(route, out_path, maze_name, start_heading=None, grid=None):
    """Write the route as .mmc and return the verb list. Refuses an empty route."""
    if len(route) < 2:
        raise ValueError("a route needs at least two cells")
    if start_heading is None:
        start_heading = config.ROUTE_EDITOR_START_HEADING
    movement_commands = commands.path_to_commands(route, start_heading)
    directory = out_path.rsplit("/", 1)[0]
    if directory and directory != out_path and not files.file_exists(directory):
        os.makedirs(directory)
    with open(out_path, "w") as file_handle:
        file_handle.write(commands.render_command_file(
            movement_commands, maze_name, grid,
            start=(route[0][0], route[0][1], start_heading),
            goal=route[-1]))
    return movement_commands


class RouteEditor:
    """A list of cells, a start heading, a click handler, and a file write."""

    def __init__(self, maze_structure, maze_name, out_path):
        self.maze = maze_structure
        self.maze_name = maze_name
        self.out_path = out_path
        self.route = []
        self.start_heading = config.ROUTE_EDITOR_START_HEADING
        self.reject_cell = None
        self.reject_until_s = 0.0

    @property
    def grid(self):
        return (self.maze.cols, self.maze.rows)

    @property
    def start(self):
        return self.route[0] if self.route else None

    @property
    def end(self):
        return self.route[-1] if self.route else None

    def click(self, cell):
        if not self.route:
            self.route.append(cell)
            print("start {} facing {}".format(cell, self.start_heading))
            return
        if cell == self.route[-1]:
            self.undo()
            return
        reason = step_is_legal(self.maze, self.route[-1], cell)
        if reason:
            self.reject(cell, reason)
            return
        self.route.append(cell)
        print("append {} -> {} cell(s), end {}".format(cell, len(self.route), cell))

    def reject(self, cell, reason):
        self.reject_cell = cell
        self.reject_until_s = time.time() + config.ROUTE_EDITOR_REJECT_FLASH_S
        print("refused {}: {}".format(cell, reason))

    def rotate_start_heading(self):
        """Turn the placed robot a quarter turn clockwise, without moving it.

        The verbs are egocentric, so this changes the whole shape the route
        drives on the floor while leaving every clicked cell where it is.
        """
        index = config.DIRECTIONS.index(self.start_heading)
        self.start_heading = config.DIRECTIONS[(index + 1) % len(config.DIRECTIONS)]
        print("start heading -> {}".format(self.start_heading))

    def undo(self):
        """Drop the last cell. A misclick has to be cheap to take back.

        Clicking the last cell again does the same thing, but nothing on screen
        said so, so a misclick looked permanent.
        """
        if not self.route:
            print("nothing to undo")
            return
        dropped = self.route.pop()
        print("undo {} -> {} cell(s)".format(dropped, len(self.route)))

    def key(self, name):
        if name in ("q", "escape"):
            raise SystemExit
        if name == "c":
            self.route = []
            print("cleared")
        elif name in ("u", "backspace"):
            self.undo()
        elif name == "r":
            self.rotate_start_heading()
        elif name == "s":
            self.save()

    def status_lines(self):
        """The two lines the window's status bar shows: state, then the keys."""
        if self.route:
            state = "start {} facing {}   end {}   {} cell(s)".format(
                self.start, self.start_heading, self.end, len(self.route))
        else:
            state = "click a cell to place the start ({}x{} grid, facing {})".format(
                self.grid[0], self.grid[1], self.start_heading)
        return (state,
                "click add   u undo   r rotate start   s save   c clear   q quit")

    def save(self):
        try:
            movement_commands = save_route(self.route, self.out_path, self.maze_name,
                                           self.start_heading, self.grid)
        except ValueError as exc:
            self.reject(self.end, str(exc))
            return
        print("saved {}".format(self.out_path))
        print("  {}x{} grid, start {} facing {}, end {}".format(
            self.grid[0], self.grid[1], self.start, self.start_heading, self.end))
        print("  {}".format(movement_commands))
        # Laps are the drift test, and path_to_commands always ends on a drive,
        # so a loop never closes on its own. Say so at save time rather than let
        # lap 2 set off in the wrong direction.
        if self.start == self.end and not commands.closes_the_loop(movement_commands):
            print("  NOTE: returns to its start CELL but not its start HEADING.")
            print("  Append a closing turn to drive it as laps (see routes/lap3x3.mmc).")

    def highlight(self):
        """Cells the renderer should paint over the route body: {cell: colour}."""
        marks = {}
        if self.route:
            marks[self.end] = config.RENDER_TILE_END
            marks[self.start] = config.RENDER_TILE_START   # start wins a 1-cell route
        if self.reject_cell is not None:
            if time.time() < self.reject_until_s:
                marks[self.reject_cell] = config.RENDER_TILE_REJECT
            else:
                self.reject_cell = None
        return marks

    def heading_marks(self):
        """The start heading arrow: {cell: compass side}."""
        return {self.start: self.start_heading} if self.route else {}


def load_maze(maze_path=None, size=None):
    """The grid to draw on, from a .num file or from a bare (cols, rows) size.

    Returns (maze_structure, name). A hand-drawn route usually wants an empty
    grid of the right shape and no maze file at all, which is why --size exists.
    """
    if maze_path:
        return maze.MazeStructure(*maze.num_file_import(maze_path)), maze_path.rsplit("/", 1)[-1]
    cols, rows = size or (config.ROUTE_EDITOR_DEFAULT_COLS, config.ROUTE_EDITOR_DEFAULT_ROWS)
    return maze.MazeStructure(cols=cols, rows=rows), "blank{}x{}".format(cols, rows)


def parse_args(argv):
    """-> (maze_path or None, size or None, out_path)."""
    maze_path = None
    size = None
    out_path = config.SAVED_ROUTE
    positional = []
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == "--out":
            index += 1
            out_path = argv[index]
        elif argument == "--size":
            index += 1
            size = parse_grid_size(argv[index])
        elif argument.startswith("--size="):
            size = parse_grid_size(argument.split("=", 1)[1])
        elif argument.startswith("--out="):
            out_path = argument.split("=", 1)[1]
        else:
            positional.append(argument)
        index += 1
    if positional:
        maze_path = positional[0]
    return maze_path, size, out_path


def main(argv):
    maze_path, size, out_path = parse_args(argv)
    maze_structure, maze_name = load_maze(maze_path, size)

    view = renderer.make_renderer(maze_structure, config.RENDER_HUD_PX)
    if view is None:
        raise SystemExit("route_editor.py needs a display.")

    editor = RouteEditor(maze_structure, maze_name, out_path)
    print("{}x{} grid ({}) -> route {}".format(
        maze_structure.cols, maze_structure.rows, maze_name, out_path))
    print("click a cell to append, u to undo, "
          "r = rotate start heading, s = save, c = clear, q = quit")
    while True:
        for kind, value in view.poll_input():
            if kind == "click":
                editor.click(value)
            else:
                editor.key(value)
        view.draw(maze_structure, route=editor.route, highlight=editor.highlight(),
                  heading_marks=editor.heading_marks(), status=editor.status_lines())


if __name__ == "__main__":
    main(sys.argv[1:])
