""" use python -m micromouse_new.maze for testing"""

# from pathlib import Path
import config

### Maze Skeleton -----------------------------------------------------------------------------------

"""MazeStructure will hold all the information needed for logical step based solving. Simulations will 
run separate MazeStructure objects for beliefs and for actual reality. Hardware will have a single
instance for its belief since solutions cannot be hardcoded.
"""

class MazeStructure:
    def __init__(self, cells=None, cols=16, rows=16):
        self.cols  = cols
        self.rows  = rows
        self.cells = cells if cells else self.generate_empty_maze(cols, rows)
        self.goal  = (self.cols // 2 - 1, self.rows // 2 - 1)

    def __str__(self):
        return to_ascii(self) # Prints an ascii maze

    def copy(self): #Allows MazeStructure objects to be copied without affecting the original object
        return MazeStructure(cells=dict(self.cells), cols=self.cols, rows=self.rows)

    def print_status(self): #Future method for when we want to return more info than just the ascii representation
        print(f"Goal: {self.goal}")

    def generate_empty_maze(self, cols, rows): #Set all inner cells to (0,0,0,0) but add a hard perimeter wall.
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
        side = config.WALL_INDEX[compass]
        walls = list(self.cells[cell])
        walls[side] = value
        self.cells[cell] = tuple(walls)

    """Record a wall on the `compass` side of `cell`, mirrored onto the neighbour so the shared wall 
    reads the same from both cells. Calls cell_update on said cell. Skips the mirror when the neighbour 
    is off-grid (a boundary wall has no cell to mirror onto)."""
    def mark_wall(self, cell, compass, value=1):
        self.cell_update(cell, compass, value) # Call on same cell
        dx, dy = config.SIDE_DELTA[compass] # Step to neighbour (1 step up, right, down or left)
        neighbour = (cell[0] + dx, cell[1] + dy)
        if neighbour in self.cells:
            self.cell_update(neighbour, config.OPPOSITE[compass], value) # Call on neighbour cell for symmetry

### Maze Geometry -----------------------------------------------------------------------------

"""
MazeGeometry will accept a MazeStructure object to generate a simulacrum of the maze where
relative distances matter. Odometry and wall sensor simulation will use this class.
0,0 at bottom left corner of bottom left post, pixel mm ratio not yet decided (can be adjustable??)
"""
class MazeGeometry:
    def __init__(self, structure):
        self.structure             = structure # Accepts a MazeStructure object
        self.posts                 = self.generate_post_polygons()
        self.h_walls, self.v_walls = self.generate_wall_polygons()
        self.boundaries            = self.generate_boundary_lines()

    def __str__(self):
        return to_ascii(self.structure)

    def generate_post_polygons(self):
        post_size  = config.POST_SIDE_MM     # 12 mm square peg
        cell_pitch = config.MM_PER_CELL      # The spacing between posts
        num_cols   = self.structure.cols
        num_rows   = self.structure.rows

        posts = {}
        for post_col in range(num_cols + 1):
            for post_row in range(num_rows + 1):
                left   = post_col * cell_pitch          # this post's bottom-left corner
                bottom = post_row * cell_pitch
                right  = left + post_size
                top    = bottom + post_size
                posts[(post_col, post_row)] = (
                    (left,  bottom),    # BL
                    (right, bottom),    # BR
                    (right, top),       # TR
                    (left,  top),       # TL
                )
        return posts # {(x,y), (BL,BR,TR,TL)} - lattice coord + sim corner coords

    def generate_wall_polygons(self):
        post_size  = config.POST_SIDE_MM
        cell_pitch = config.MM_PER_CELL
        num_cols   = self.structure.cols
        num_rows   = self.structure.rows
        cells      = self.structure.cells

        north = config.WALL_INDEX["n"]       # slot positions in a (n,e,s,w) tuple
        east  = config.WALL_INDEX["e"]
        south = config.WALL_INDEX["s"]
        west  = config.WALL_INDEX["w"]

        h_walls = {}
        v_walls = {}

        # span_col/row aligns with cell, line_col/row sits between cells
        # horizontal walls: sit on a row grid-line, span one cell across in x
        for span_col in range(num_cols):
            for line_row in range(num_rows + 1): # .get() returns None if cell non-existent - no index error
                cell_above = cells.get((span_col, line_row))       # line is this cell's south edge
                cell_below = cells.get((span_col, line_row - 1))   # line is this cell's north edge
                present = (cell_above and cell_above[south]) or (cell_below and cell_below[north])
                if present:
                    left   = span_col * cell_pitch + post_size     # start just past the left post
                    right  = (span_col + 1) * cell_pitch           # stop at the right post
                    bottom = line_row * cell_pitch
                    top    = bottom + post_size
                    h_walls[(span_col, line_row)] = (
                        (left, bottom), (right, bottom), (right, top), (left, top)
                    )

        # vertical walls: sit on a column grid-line, span one cell up in y
        for line_col in range(num_cols + 1):
            for span_row in range(num_rows):
                cell_right = cells.get((line_col, span_row))       # line is this cell's west edge
                cell_left  = cells.get((line_col - 1, span_row))   # line is this cell's east edge
                present = (cell_right and cell_right[west]) or (cell_left and cell_left[east])
                if present:
                    left   = line_col * cell_pitch
                    right  = left + post_size
                    bottom = span_row * cell_pitch + post_size     # start just above the bottom post
                    top    = (span_row + 1) * cell_pitch           # stop at the top post
                    v_walls[(line_col, span_row)] = (
                        (left, bottom), (right, bottom), (right, top), (left, top)
                    )
        return h_walls, v_walls # {(x,y), (BL,BR,TR,TL)} - placement + sim corner coords
    
    def generate_boundary_lines(self):
        pass # use self.h_walls, self.v_walls and self.posts

    def add_wall(self, cell, orientation):
        pass

### File Operations ---------------------------------------------------------------------------------

"""
.num schema (one line per cell, space-separated, no header):
    x y N E S W
x, y are 0-based cell coordinates. N E S W are wall flags (0 or 1) in fixed north/east/south/west order. 
Direction convention: n=+y, e=+x, s=-y, w=-x. So (0, 0) is the bottom-left cell. Reader and writer below 
are inverses of each other.
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


# """List all `.num` maze files in a directory, sorted by name."""
# def available_mazes(mazes_dir):
#     return sorted(Path(mazes_dir).glob("*.num"))

### General Functions -------------------------------------------------------------------------------

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

