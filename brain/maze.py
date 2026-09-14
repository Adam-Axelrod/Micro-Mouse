import os
import config


class MazeStructure:
    def __init__(self, cells=None, cols=16, rows=16):
        self.cols = cols
        self.rows = rows
        self.cells = cells if cells else self.generate_empty_maze(cols, rows)
        # Centre cell. `(n - 1) // 2` is correct for BOTH parities: on an even
        # grid it picks the bottom-left of the four centre cells (16 -> 7, the
        # UKMARS convention), and on an odd grid it picks the single true centre
        # (3 -> 1). The old `n // 2 - 1` was even-only: it put a 5x5 goal
        # off-centre and, on a 3x3, put the goal ON THE START CELL, so the mouse
        # believed it had already arrived and every route came back empty.
        self.goal = ((self.cols - 1) // 2, (self.rows - 1) // 2)

    def __str__(self):
        return to_ascii(self)

    def generate_empty_maze(self, cols, rows):
        cells = {}
        for y in range(rows):
            for x in range(cols):
                n = 1 if y == rows - 1 else 0
                e = 1 if x == cols - 1 else 0
                s = 1 if y == 0 else 0
                w = 1 if x == 0 else 0
                cells[(x, y)] = (n, e, s, w)
        return cells

    def cell_update(self, cell, compass, value):
        side_index = config.WALL_INDEX[compass]
        walls = list(self.cells[cell])
        walls[side_index] = value
        self.cells[cell] = tuple(walls)

    def mark_wall(self, cell, compass, value=1):
        self.cell_update(cell, compass, value)
        dx, dy = config.SIDE_DELTA[compass]
        neighbour = (cell[0] + dx, cell[1] + dy)
        if neighbour in self.cells:
            self.cell_update(neighbour, config.OPPOSITE[compass], value)


def num_file_import(path_str):
    """Read a .num maze file into a cells dict. Returns (cells, cols, rows)."""
    cells = {}
    max_x = max_y = 0
    with open(path_str, "r") as file_handle:
        for line in file_handle:
            line = line.strip()
            if not line:
                continue
            x, y, n, e, s, w = (int(val) for val in line.split())
            cells[(x, y)] = (bool(n), bool(e), bool(s), bool(w))
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    return cells, max_x + 1, max_y + 1


def num_file_export(path_str, cells):
    """Write a cells dict to a .num maze file."""
    cols = max(x for x, y in cells) + 1
    rows = max(y for x, y in cells) + 1
    with open(path_str, "w") as file_handle:
        for x in range(cols):
            for y in range(rows):
                n, e, s, w = cells[(x, y)]
                file_handle.write(f"{x} {y} {int(n)} {int(e)} {int(s)} {int(w)}\n")


def to_ascii(maze, path=None, mouse_pos=None):
    """Render maze structure as ASCII text string."""
    path_cells = set(path) if path else set()

    def interior(x, y):
        if mouse_pos is not None and (x, y) == tuple(mouse_pos):
            return " @ "
        if (x, y) in path_cells:
            return " # "
        return "   "

    lines = []
    for y in range(maze.rows - 1, -1, -1):
        top_line = ""
        side_line = ""
        for x in range(maze.cols):
            n, e, s, w = maze.cells[(x, y)]
            top_line += "+" + ("---" if n else "   ")
            side_line += ("|" if w else " ") + interior(x, y)
            if x == maze.cols - 1:
                top_line += "+"
                side_line += "|" if e else " "
        lines.append(top_line)
        lines.append(side_line)

    bottom_floor = ""
    for x in range(maze.cols):
        _, _, s, _ = maze.cells[(x, 0)]
        bottom_floor += "+" + ("---" if s else "   ")
    bottom_floor += "+"
    lines.append(bottom_floor)
    return "\n".join(lines)


if __name__ == "__main__":
    test_maze = MazeStructure()
    print(test_maze)
