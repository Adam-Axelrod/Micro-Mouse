""" use python -m micromouse_new.maze for testing"""

from pathlib import Path

from . import config

### Maze Skeleton -----------------------------------------------------------------------------------

"""MazeStructure will hold all the information needed for logical step based solving. Any 
mms interaction can ignore MazeVirtualisation and interact with this class only. Simulations will 
run separate MazeStructure objects for beliefs and for actual reality. Hardware will have a single
instance for its belief since solutions cannot be hardcoded.

    cells   : Dict of coordinate tuple keys and wall tuple values (x, y), (n, e, s, w)

"""

class MazeStructure:
    def __init__(self, cells=None, rows=16, cols=16):
        self.rows = rows
        self.cols = cols
        self.cells = cells if cells else self.generate_empty_maze(rows, cols)
        self.goal = (self.cols // 2 - 1, self.rows // 2 - 1)

    """Bare ASCII representation. Overlays (path, mouse) are a rendering concern,
    so they live in the free function to_ascii, not here."""
    def __str__(self):
        return to_ascii(self)

    """Future method for when we want to return more info than just the ascii representation"""
    def print_status(self):
        pass

    """Set all inner cells to (0,0,0,0) but add a hard perimeter wall."""
    def generate_empty_maze(self, rows, cols):
        cells = {}
        for y in range(rows):
            for x in range(cols):
                n = 1 if y == rows - 1 else 0 # Outer boundary checks
                e = 1 if x == cols - 1 else 0
                s = 1 if y == 0 else 0
                w = 1 if x == 0 else 0
                cells[(x, y)] = (n, e, s, w)
        return cells

    """Set one wall of `cell` to `value`. Updates one cell only. A wall is shared between two cells, so a
    caller wanting the belief consistent must also set the mirrored side on the neighbour (e.g. setting 
    'n' here means setting 's' on the cell above)."""

    def cell_update(self, cell, compass, value):
        walls = list(self.cells[cell])
        walls[config.WALL_INDEX[compass]] = value
        self.cells[cell] = tuple(walls)

    """Record a wall on the `compass` side of `cell`, mirrored onto the neighbour so the shared wall 
    reads the same from both cells. Calls cell_update on said cell. Skips the mirror when the neighbour 
    is off-grid (a boundary wall has no cell to mirror onto)."""
    
    def mark_wall(self, cell, compass, value=1):
        self.cell_update(cell, compass, value) # Call on same cell
        dx, dy = config.SIDE_DELTA[compass]
        neighbour = (cell[0] + dx, cell[1] + dy)
        if neighbour in self.cells:
            self.cell_update(neighbour, config.OPPOSITE[compass], value) # Call on neighbour cell for symmetry

### Maze Virtualisation -----------------------------------------------------------------------------

# """
# MazeVirtualisation will accept a MazeStructure object to generate a simulacrum of the maze where
# relative distances matter. Odometry and wall sensor simulation will use this class.

# 0,0 at bottom left corner of bottom left post, pixel mm ratio not yet decided (can be adjustable??)
# """
# class MazeVirtualisation:
#     def __init__(self, structure):
#         self.structure = structure # Accepts a MazeStructure object
#         self.walls = self.generate_wall_polygons(structure.cells)

#     def generate_wall_polygons(self, cells):
#         pass
#     """
#     tba 
#     def update beliefs
#     def return structure
#     """


### File Operations ---------------------------------------------------------------------------------

"""
.num schema (one line per cell, space-separated, no header):
    x y N E S W
x, y are 0-based cell coordinates. N E S W are wall flags (0 or 1) in fixed
north/east/south/west order. Direction convention: n=+y, e=+x, s=-y, w=-x.
So (0, 0) is the bottom-left cell. Reader and writer below are inverses of each
other; a hand-verified fixture pins the convention to ground truth.
"""

"""Read a .num file into a cells dict. Returns (cells, cols, rows)."""
def num_file_import(path):
    cells = {}
    max_x = max_y = 0
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            x, y, n, e, s, w = (int(v) for v in line.split())
            cells[(x, y)] = (bool(n), bool(e), bool(s), bool(w))
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    return cells, max_x + 1, max_y + 1


"""Write a cells dict to a .num file. Mirrors num_file_import exactly."""
def num_file_export(path, cells):
    cols = max(x for x, y in cells) + 1
    rows = max(y for x, y in cells) + 1
    with open(path, "w") as f:
        for x in range(cols):           # column-major to match the example files
            for y in range(rows):
                n, e, s, w = cells[(x, y)]
                f.write(f"{x} {y} {int(n)} {int(e)} {int(s)} {int(w)}\n")


"""List all `.num` maze files in a directory, sorted by name."""
def available_mazes(mazes_dir):
    return sorted(Path(mazes_dir).glob("*.num"))

### Terminal Operations -----------------------------------------------------------------------------

"""Render a maze as ASCII, optionally overlaying a path and/or the mouse.
    maze  : any object with .rows, .cols and .cells[(x, y)] -> (n, e, s, w)
    path  : iterable of (x, y) cells to mark with the path glyph
    mouse : a single (x, y) cell to mark with the mouse glyph (takes precedence)"""

def to_ascii(maze, path=None, mouse_pos=None):
    path_cells = set(path) if path else set()

    def interior(x, y):                 # the 3-char cell body
        if mouse_pos is not None and (x, y) == tuple(mouse_pos):
            return " @ "
        if (x, y) in path_cells:
            return " # "
        return "   "

    lines = []
    for y in range(maze.rows - 1, -1, -1): # Highest row index prints first, so y increases up the page (n=+y).
        top_line = ""
        side_line = ""
        for x in range(maze.cols):
            n, e, s, w = maze.cells[(x, y)]   # walls for this cell: (N, E, S, W)

            top_line += "+"                   # corner post + north wall
            top_line += "---" if n else "   "

            side_line += "|" if w else " "    # west wall + cell interior
            side_line += interior(x, y)

            if x == maze.cols - 1:            # seal the east boundary
                top_line += "+"
                side_line += "|" if e else " "

        lines.append(top_line)
        lines.append(side_line)

    bottom_floor = "" # Seal the very bottom floor from row 0's south walls.
    for x in range(maze.cols):
        _, _, s, _ = maze.cells[(x, 0)]
        bottom_floor += "+"
        bottom_floor += "---" if s else "   "
    bottom_floor += "+"
    lines.append(bottom_floor)
    return "\n".join(lines)

### Tests -------------------------------------------------------------------------------------------

if __name__ == "__main__": # Blank maze loads, export and imports remain mirror images
    maze = MazeStructure()
    print(maze)
    maze2 = MazeStructure(*num_file_import(config.DEFAULT_MAZE))
    print(maze2)
    num_file_export(f"{config.GENERATED_MAZES_DIR}/test_example4.num", maze2.cells)
    # print(maze2.cells)

