"""The route editor's rules: what a click may do, and what it writes.

A route that steps through a wall would make mode 6 look broken when the editor
was at fault, so the legality gate is the part worth guarding.
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import commands
import config
import maze

try:
    import pygame  # noqa: F401
    from sim.route_editor import (RouteEditor, load_maze, parse_args,
                                  parse_grid_size, save_route, step_is_legal)
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False

OUT_PATH = "_route_editor_selftest.mmc"


def _blank3x3():
    return maze.MazeStructure(cols=3, rows=3)


def _editor():
    return RouteEditor(_blank3x3(), "blank3x3.num", OUT_PATH)


def test_an_open_step_is_legal():
    assert step_is_legal(_blank3x3(), (0, 0), (0, 1)) is None
    assert step_is_legal(_blank3x3(), (1, 1), (2, 1)) is None
    print("✓ test_an_open_step_is_legal passed")


def test_a_diagonal_is_refused():
    reason = step_is_legal(_blank3x3(), (0, 0), (1, 1))
    assert reason and "adjacent" in reason, reason
    print("✓ test_a_diagonal_is_refused passed")


def test_a_step_through_a_wall_is_refused():
    reason = step_is_legal(_blank3x3(), (0, 0), (-1, 0))   # perimeter wall
    assert reason and "wall" in reason, reason
    print("✓ test_a_step_through_a_wall_is_refused passed")


def test_an_interior_wall_is_refused():
    grid = _blank3x3()
    grid.mark_wall((1, 1), "n")
    reason = step_is_legal(grid, (1, 1), (1, 2))
    assert reason and "wall" in reason, reason
    assert step_is_legal(grid, (1, 2), (1, 1)) is not None
    print("✓ test_an_interior_wall_is_refused passed")


def test_clicks_build_a_route_and_refusals_leave_it_untouched():
    editor = _editor()
    for cell in ((0, 0), (0, 1), (0, 2)):
        editor.click(cell)
    assert editor.route == [(0, 0), (0, 1), (0, 2)]

    editor.click((2, 2))                       # not adjacent
    assert editor.route == [(0, 0), (0, 1), (0, 2)], editor.route
    assert editor.reject_cell == (2, 2)
    print("✓ test_clicks_build_a_route_and_refusals_leave_it_untouched passed")


def test_clicking_the_last_cell_undoes_it():
    editor = _editor()
    for cell in ((0, 0), (0, 1), (0, 2)):
        editor.click(cell)
    editor.click((0, 2))
    assert editor.route == [(0, 0), (0, 1)], editor.route
    editor.click((0, 1))
    editor.click((0, 0))
    assert editor.route == [], editor.route
    print("✓ test_clicking_the_last_cell_undoes_it passed")


def test_clear_empties_the_route():
    editor = _editor()
    editor.click((0, 0))
    editor.click((0, 1))
    editor.key("c")
    assert editor.route == []
    print("✓ test_clear_empties_the_route passed")


def test_quit_raises_system_exit():
    for key in ("q", "escape"):
        try:
            _editor().key(key)
        except SystemExit:
            continue
        raise AssertionError("{} did not quit".format(key))
    print("✓ test_quit_raises_system_exit passed")


def test_a_route_shorter_than_two_cells_is_not_saved():
    for route in ([], [(0, 0)]):
        try:
            save_route(route, OUT_PATH, "blank3x3.num")
        except ValueError:
            continue
        raise AssertionError("saved a route of {} cell(s)".format(len(route)))
    print("✓ test_a_route_shorter_than_two_cells_is_not_saved passed")


def test_any_grid_size_can_be_drawn_on_without_a_maze_file():
    """The physical test maze is 3x3 and has no .num file behind it."""
    for size, cols, rows in (((3, 3), 3, 3), ((16, 16), 16, 16), ((4, 9), 4, 9), (None, 3, 3)):
        grid, name = load_maze(size=size)
        assert (grid.cols, grid.rows) == (cols, rows), (size, grid.cols, grid.rows)
        assert name == "blank{}x{}".format(cols, rows), name
        assert len(grid.cells) == cols * rows
    print("✓ test_any_grid_size_can_be_drawn_on_without_a_maze_file passed")


def test_grid_sizes_parse_in_both_spellings():
    assert parse_grid_size("16x16") == (16, 16)
    assert parse_grid_size("3X7") == (3, 7)
    assert parse_grid_size("6") == (6, 6)          # square shorthand
    for bad in ("0", "3x0", "", "wide"):
        try:
            parse_grid_size(bad)
        except ValueError:
            continue
        raise AssertionError("parse_grid_size accepted " + repr(bad))
    print("✓ test_grid_sizes_parse_in_both_spellings passed")


def test_the_size_flag_needs_no_maze_file():
    assert parse_args(["--size", "16x16"])[:2] == (None, (16, 16))
    assert parse_args(["--size=4x2"])[:2] == (None, (4, 2))
    assert parse_args(["--out=x.mmc"])[2] == "x.mmc"
    maze_path, size, _ = parse_args(["mazes/test_mazes/blank3x3.num"])
    assert maze_path == "mazes/test_mazes/blank3x3.num" and size is None
    print("✓ test_the_size_flag_needs_no_maze_file passed")


def test_a_maze_file_still_supplies_the_walls():
    grid, name = load_maze("mazes/test_mazes/blank3x3.num")
    assert (grid.cols, grid.rows) == (3, 3)
    assert name == "blank3x3.num"
    print("✓ test_a_maze_file_still_supplies_the_walls passed")


def test_rotating_the_start_heading_changes_the_verbs_not_the_cells():
    """The verbs are egocentric, so the placed heading redraws the whole shape."""
    editor = _editor()
    for cell in ((0, 0), (0, 1), (0, 2)):
        editor.click(cell)
    cells_before = list(editor.route)

    assert editor.start_heading == "n"
    assert commands.path_to_commands(editor.route, "n") == ["F 2", "H"]
    editor.key("r")
    assert editor.start_heading == "e"
    assert editor.route == cells_before, "rotating moved a cell"
    assert commands.path_to_commands(editor.route, "e") == ["L", "F 2", "H"]

    for expected in ("s", "w", "n"):
        editor.key("r")
        assert editor.start_heading == expected
    print("✓ test_rotating_the_start_heading_changes_the_verbs_not_the_cells passed")


def test_the_start_and_end_are_the_first_and_last_cells():
    editor = _editor()
    assert editor.start is None and editor.end is None
    for cell in ((0, 0), (0, 1), (1, 1)):
        editor.click(cell)
    assert editor.start == (0, 0) and editor.end == (1, 1)
    assert editor.highlight()[(0, 0)] == config.RENDER_TILE_START
    assert editor.highlight()[(1, 1)] == config.RENDER_TILE_END
    assert editor.heading_marks() == {(0, 0): "n"}
    print("✓ test_the_start_and_end_are_the_first_and_last_cells passed")


def test_the_saved_header_carries_the_pose_and_the_grid():
    """A .mmc drives a different shape from a different pose, so it travels."""
    editor = RouteEditor(*load_maze(size=(4, 9)), OUT_PATH)
    for cell in ((1, 0), (1, 1), (2, 1)):
        editor.click(cell)
    editor.key("r")           # face east
    editor.key("s")
    try:
        header = commands.read_route_header(OUT_PATH)
        assert header["grid"] == (4, 9), header
        assert header["start"] == (1, 0, "e"), header
        assert header["goal"] == (2, 1), header
        assert commands.read_command_file(OUT_PATH) == ["L", "F 1", "R", "F 1", "H"]
    finally:
        os.remove(OUT_PATH)
    print("✓ test_the_saved_header_carries_the_pose_and_the_grid passed")


def test_the_saved_file_round_trips_through_the_reader():
    route = [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2)]
    written = save_route(route, OUT_PATH, "blank3x3.num", "n", (3, 3))
    try:
        assert commands.read_command_file(OUT_PATH) == written, written
        assert written == commands.path_to_commands(route)
        assert open(OUT_PATH).read().startswith("# micromouse route v1")
    finally:
        os.remove(OUT_PATH)
    print("✓ test_the_saved_file_round_trips_through_the_reader passed")


def test_a_drawn_perimeter_lap_does_not_close_in_heading():
    """path_to_commands ends on a drive, so a loop never closes itself."""
    lap = [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2), (2, 1), (2, 0), (1, 0), (0, 0)]
    verbs = commands.path_to_commands(lap)
    assert lap[0] == lap[-1]
    assert not commands.closes_the_loop(verbs), verbs
    assert commands.closes_the_loop(verbs[:-1] + ["R", commands.HALT])
    print("✓ test_a_drawn_perimeter_lap_does_not_close_in_heading passed")


def test_the_real_loop_survives_real_clicks_at_every_grid_size():
    """Post pygame events and run the editor's own poll-click-draw cycle.

    Every other test calls `click` directly, so nothing here would notice a
    broken draw call or a wrong pixel inverse. The renderer was silently broken
    for weeks that way: `make_renderer` swallows the exception and continues.
    """
    from sim import renderer, route_editor

    for size in ("3x3", "16x16", "4x9"):
        grid, name = route_editor.load_maze(size=route_editor.parse_grid_size(size))
        view = renderer.make_renderer(grid)
        assert view is not None, "no renderer at " + size
        editor = RouteEditor(grid, name, OUT_PATH)

        for cell in ((0, 0), (0, 1), (1, 1)):
            centre_mm = ((cell[0] + 0.5) * config.MM_PER_CELL,
                         (cell[1] + 0.5) * config.MM_PER_CELL)
            pygame.event.post(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1,
                pos=[int(value) for value in view._px(*centre_mm)]))
        for key in (pygame.K_r, pygame.K_s):
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))

        try:
            for _ in range(3):
                for kind, value in view.poll_input():
                    (editor.click if kind == "click" else editor.key)(value)
                view.draw(grid, path=editor.route, highlight=editor.highlight(),
                          heading_marks=editor.heading_marks())
            assert editor.route == [(0, 0), (0, 1), (1, 1)], (size, editor.route)
            assert editor.start_heading == "e"
            assert commands.read_route_header(OUT_PATH)["grid"] == (grid.cols, grid.rows)
        finally:
            view.close()
            if os.path.exists(OUT_PATH):
                os.remove(OUT_PATH)
    print("✓ test_the_real_loop_survives_real_clicks_at_every_grid_size passed")


def test_the_committed_lap_fixture_is_walkable_and_closed():
    verbs = commands.read_command_file(config.ROUTES_DIR + "/lap3x3.mmc")
    assert commands.closes_the_loop(verbs), verbs
    assert verbs[-1] == commands.HALT
    header = commands.read_route_header(config.ROUTES_DIR + "/lap3x3.mmc")
    assert header["grid"] == (3, 3), header
    assert header["start"][:2] == header["goal"], "a lap must end where it began"
    print("✓ test_the_committed_lap_fixture_is_walkable_and_closed passed")


TESTS = (
    test_an_open_step_is_legal,
    test_any_grid_size_can_be_drawn_on_without_a_maze_file,
    test_grid_sizes_parse_in_both_spellings,
    test_the_size_flag_needs_no_maze_file,
    test_a_maze_file_still_supplies_the_walls,
    test_rotating_the_start_heading_changes_the_verbs_not_the_cells,
    test_the_start_and_end_are_the_first_and_last_cells,
    test_the_saved_header_carries_the_pose_and_the_grid,
    test_a_diagonal_is_refused,
    test_a_step_through_a_wall_is_refused,
    test_an_interior_wall_is_refused,
    test_clicks_build_a_route_and_refusals_leave_it_untouched,
    test_clicking_the_last_cell_undoes_it,
    test_clear_empties_the_route,
    test_quit_raises_system_exit,
    test_a_route_shorter_than_two_cells_is_not_saved,
    test_the_saved_file_round_trips_through_the_reader,
    test_a_drawn_perimeter_lap_does_not_close_in_heading,
    test_the_real_loop_survives_real_clicks_at_every_grid_size,
    test_the_committed_lap_fixture_is_walkable_and_closed,
)


if __name__ == "__main__":
    if not HAS_PYGAME:
        print("SKIPPED: pygame is not installed (the editor imports the renderer)")
        sys.exit(0)
    for test in TESTS:
        test()
    print("ALL {} ROUTE EDITOR TESTS PASSED".format(len(TESTS)))
