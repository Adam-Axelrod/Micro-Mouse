"""Draw a route by hand, click by click, and write it as a .mmc file. PC-only.

Today the only way to get a route is to let flood fill plan one. That makes every
test of the motion layer a test of the planner as well. This tool separates them:
click the cells you want, save, and drive that file. Nothing about the planner is
involved, so a route that is driven wrongly is the drive layer's fault.

    python3 sim/route_editor.py                          # groundtruth.num -> route.mmc
    python3 sim/route_editor.py mazes/test_mazes/blank3x3.num  # a different maze
    python3 sim/route_editor.py --out routes/hairpin.mmc # save a committed fixture

Saving with no --out writes `route.mmc` at the package root: the working file the
robot carries, so `python3 main.py --follow` drives what you just drew. `routes/`
holds fixtures worth keeping.

Controls:
    left click   append the cell to the route; click the last cell again to undo
    s            save, and print the verb list
    c            clear the route
    q / escape   quit

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

import commands  # noqa: E402
import config  # noqa: E402
import maze  # noqa: E402
from sim import renderer  # noqa: E402


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


def save_route(route, out_path, maze_name):
    """Write the route as .mmc and return the verb list. Refuses an empty route."""
    if len(route) < 2:
        raise ValueError("a route needs at least two cells")
    movement_commands = commands.path_to_commands(route)
    directory = out_path.rsplit("/", 1)[0]
    if directory and directory != out_path and not maze.file_exists(directory):
        os.makedirs(directory)
    with open(out_path, "w") as file_handle:
        file_handle.write(commands.render_command_file(movement_commands, maze_name))
    return movement_commands


class RouteEditor:
    """A list of cells, a click handler, and a file write. Nothing else."""

    def __init__(self, maze_structure, maze_name, out_path):
        self.maze = maze_structure
        self.maze_name = maze_name
        self.out_path = out_path
        self.route = []
        self.reject_cell = None
        self.reject_until_s = 0.0

    def click(self, cell):
        if not self.route:
            self.route.append(cell)
            print("start {}".format(cell))
            return
        if cell == self.route[-1]:
            self.route.pop()
            print("undo -> route is now {} cell(s)".format(len(self.route)))
            return
        reason = step_is_legal(self.maze, self.route[-1], cell)
        if reason:
            self.reject(cell, reason)
            return
        self.route.append(cell)
        print("append {} -> {} cell(s)".format(cell, len(self.route)))

    def reject(self, cell, reason):
        self.reject_cell = cell
        self.reject_until_s = time.time() + config.ROUTE_EDITOR_REJECT_FLASH_S
        print("refused {}: {}".format(cell, reason))

    def key(self, name):
        if name in ("q", "escape"):
            raise SystemExit
        if name == "c":
            self.route = []
            print("cleared")
        elif name == "s":
            self.save()

    def save(self):
        try:
            movement_commands = save_route(self.route, self.out_path, self.maze_name)
        except ValueError as exc:
            self.reject(self.route[-1] if self.route else None, str(exc))
            return
        print("saved {} -> {}".format(self.out_path, movement_commands))
        # Laps are the drift test, and path_to_commands always ends on a drive,
        # so a loop never closes on its own. Say so at save time rather than let
        # lap 2 set off in the wrong direction.
        if self.route[0] == self.route[-1] and not commands.closes_the_loop(movement_commands):
            print("  NOTE: returns to its start CELL but not its start HEADING.")
            print("  Append a closing turn to drive it as laps (see routes/lap3x3.mmc).")

    def highlight(self):
        """Cells the renderer should paint over the route body: {cell: colour}."""
        marks = {}
        if self.route:
            marks[self.route[0]] = config.RENDER_TILE_START
            marks[self.route[-1]] = config.RENDER_TILE_END
        if self.reject_cell is not None:
            if time.time() < self.reject_until_s:
                marks[self.reject_cell] = config.RENDER_TILE_REJECT
            else:
                self.reject_cell = None
        return marks


def main(argv):
    maze_path = config.DEFAULT_MAZE
    out_path = config.SAVED_ROUTE
    positional = []
    index = 0
    while index < len(argv):
        if argv[index] == "--out":
            index += 1
            out_path = argv[index]
        else:
            positional.append(argv[index])
        index += 1
    if positional:
        maze_path = positional[0]

    maze_structure = maze.MazeStructure(*maze.num_file_import(maze_path))
    maze_name = maze_path.rsplit("/", 1)[-1]
    view = renderer.make_renderer(maze_structure)
    if view is None:
        raise SystemExit("route_editor.py needs a display.")

    editor = RouteEditor(maze_structure, maze_name, out_path)
    print("maze {} -> route {}".format(maze_path, out_path))
    print("click a cell to append, click the last cell to undo, "
          "s = save, c = clear, q = quit")
    while True:
        for kind, value in view.poll_input():
            if kind == "click":
                editor.click(value)
            else:
                editor.key(value)
        view.draw(maze_structure, path=editor.route, highlight=editor.highlight())


if __name__ == "__main__":
    main(sys.argv[1:])
