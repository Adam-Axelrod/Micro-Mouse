"""Pure: MazeStructure and the .num file format. Grid cells and compass sides only."""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_DIR = os.path.dirname(TESTS_DIR)
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import tempfile

import config
from maze import MazeStructure, num_file_import, num_file_export, file_exists, to_ascii


def test_blank_maze_is_walled_only_on_the_border():
    maze = MazeStructure(cols=4, rows=4)
    assert len(maze.cells) == 16

    n, e, s, w = maze.cells[(0, 0)]
    assert (s, w) == (1, 1), "the bottom-left cell must have its south and west border"
    assert (n, e) == (0, 0), "and no interior wall"

    n, e, s, w = maze.cells[(3, 3)]
    assert (n, e) == (1, 1)
    assert (s, w) == (0, 0)

    n, e, s, w = maze.cells[(1, 1)]
    assert (n, e, s, w) == (0, 0, 0, 0), "an interior cell starts open on every side"
    print("✓ test_blank_maze_is_walled_only_on_the_border passed")


def test_goal_is_the_centre_cell():
    assert MazeStructure(cols=16, rows=16).goal == (7, 7)
    assert MazeStructure(cols=4, rows=4).goal == (1, 1)
    print("✓ test_goal_is_the_centre_cell passed")


def test_goal_is_centred_on_odd_grids_too():
    """Regression: `cols // 2 - 1` put a 3x3 goal on the start cell."""
    assert MazeStructure(cols=3, rows=3).goal == (1, 1)
    assert MazeStructure(cols=5, rows=5).goal == (2, 2)
    assert MazeStructure(cols=3, rows=3).goal != config.START_POS

    assert MazeStructure(cols=3, rows=6).goal == (1, 2)
    print("✓ test_goal_is_centred_on_odd_grids_too passed")


def test_mark_wall_mirrors_onto_the_neighbour():
    """A wall is an EDGE, shared by two cells. If only one side records it the
    belief disagrees with itself depending on which cell you ask."""
    maze = MazeStructure(cols=4, rows=4)
    maze.mark_wall((1, 1), "e")

    assert maze.cells[(1, 1)][config.WALL_INDEX["e"]] == 1
    assert maze.cells[(2, 1)][config.WALL_INDEX["w"]] == 1, "not mirrored onto the neighbour"

    # Clearing must mirror too, or a correction leaves half a wall behind.
    maze.mark_wall((1, 1), "e", 0)
    assert maze.cells[(1, 1)][config.WALL_INDEX["e"]] == 0
    assert maze.cells[(2, 1)][config.WALL_INDEX["w"]] == 0
    print("✓ test_mark_wall_mirrors_onto_the_neighbour passed")


def test_mark_wall_on_the_border_has_no_neighbour():
    """Marking outward from an edge cell must not raise or invent a cell."""
    maze = MazeStructure(cols=4, rows=4)
    maze.mark_wall((0, 0), "w")
    assert maze.cells[(0, 0)][config.WALL_INDEX["w"]] == 1
    assert (-1, 0) not in maze.cells
    print("✓ test_mark_wall_on_the_border_has_no_neighbour passed")


def test_cell_update_touches_one_side_only():
    maze = MazeStructure(cols=4, rows=4)
    before = maze.cells[(1, 1)]
    maze.cell_update((1, 1), "n", 1)
    after = maze.cells[(1, 1)]
    assert after[config.WALL_INDEX["n"]] == 1
    for side in ("e", "s", "w"):
        assert after[config.WALL_INDEX[side]] == before[config.WALL_INDEX[side]]
    assert maze.cells[(1, 2)][config.WALL_INDEX["s"]] == 0, "cell_update must NOT mirror"
    print("✓ test_cell_update_touches_one_side_only passed")


def test_num_file_round_trip():
    maze = MazeStructure(cols=4, rows=4)
    maze.mark_wall((1, 1), "e")
    maze.mark_wall((2, 3), "s")

    handle, path = tempfile.mkstemp(suffix=".num")
    os.close(handle)
    try:
        num_file_export(path, maze.cells)
        cells, cols, rows = num_file_import(path)
        assert (cols, rows) == (4, 4)
        assert len(cells) == 16
        for cell, walls in maze.cells.items():
            assert tuple(int(v) for v in cells[cell]) == tuple(int(v) for v in walls), cell
    finally:
        os.remove(path)
    print("✓ test_num_file_round_trip passed")


def test_file_exists_is_os_path_free():
    """MicroPython's os has no `path` submodule, so this check uses os.stat."""
    handle, path = tempfile.mkstemp()
    os.close(handle)
    try:
        assert file_exists(path)
    finally:
        os.remove(path)
    assert not file_exists(path)
    assert not file_exists("/no/such/directory/at/all.num")
    print("✓ test_file_exists_is_os_path_free passed")


def test_shipped_maze_files_parse():
    """Committed fixtures (groundtruth.num and every .num under mazes/) must
    parse and describe full rectangles with a south border at (0,0). A malformed
    maze is a silent wrong-maze run, not a crash."""
    paths = [config.DEFAULT_MAZE]
    if os.path.isdir(config.MAZES_DIR):
        for entry in os.listdir(config.MAZES_DIR):
            if entry.endswith(".num"):
                paths.append(os.path.join(config.MAZES_DIR, entry))
    # Also include fixtures from subdirectories (e.g. mazes/example_mazes/)
    for root, dirs, files in os.walk(config.MAZES_DIR):
        for f in files:
            if f.endswith(".num"):
                p = os.path.join(root, f)
                if p not in paths:
                    paths.append(p)
    for path in paths:
        assert file_exists(path), path
        cells, cols, rows = num_file_import(path)
        assert cols > 0 and rows > 0
        assert len(cells) == cols * rows, f"{path} is not a full rectangle"
        maze = MazeStructure(cells=cells, cols=cols, rows=rows)
        assert maze.cells[(0, 0)][config.WALL_INDEX["s"]], f"{path} has no south border"
    print("✓ test_shipped_maze_files_parse passed")


def test_to_ascii_draws_every_row_and_the_mouse():
    maze = MazeStructure(cols=3, rows=3)
    art = to_ascii(maze, path=[(1, 1)], mouse_pos=(0, 0))
    lines = art.split("\n")
    assert len(lines) == 2 * maze.rows + 1, "one top line per row plus the floor"
    assert "@" in art, "the mouse must be drawn"
    assert "#" in art, "the planned path must be drawn"
    print("✓ test_to_ascii_draws_every_row_and_the_mouse passed")


TESTS = [
    test_blank_maze_is_walled_only_on_the_border,
    test_goal_is_the_centre_cell,
    test_goal_is_centred_on_odd_grids_too,
    test_mark_wall_mirrors_onto_the_neighbour,
    test_mark_wall_on_the_border_has_no_neighbour,
    test_cell_update_touches_one_side_only,
    test_num_file_round_trip,
    test_file_exists_is_os_path_free,
    test_shipped_maze_files_parse,
    test_to_ascii_draws_every_row_and_the_mouse,
]

if __name__ == "__main__":
    for test in TESTS:
        test()
    print(f"ALL {len(TESTS)} MAZE TESTS PASSED")
