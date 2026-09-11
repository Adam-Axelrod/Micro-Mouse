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
    from sim.route_editor import RouteEditor, save_route, step_is_legal
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


def test_the_saved_file_round_trips_through_the_reader():
    route = [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2)]
    written = save_route(route, OUT_PATH, "blank3x3.num")
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


def test_the_committed_lap_fixture_is_walkable_and_closed():
    verbs = commands.read_command_file(config.ROUTES_DIR + "/lap3x3.mmc")
    assert commands.closes_the_loop(verbs), verbs
    assert verbs[-1] == commands.HALT
    print("✓ test_the_committed_lap_fixture_is_walkable_and_closed passed")


TESTS = (
    test_an_open_step_is_legal,
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
    test_the_committed_lap_fixture_is_walkable_and_closed,
)


if __name__ == "__main__":
    if not HAS_PYGAME:
        print("SKIPPED: pygame is not installed (the editor imports the renderer)")
        sys.exit(0)
    for test in TESTS:
        test()
    print("ALL {} ROUTE EDITOR TESTS PASSED".format(len(TESTS)))
