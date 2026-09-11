"""Mode 6 must start the simulated mouse where the route says it starts.

The sim always begins at cell (0, 0) facing north. A route drawn from any other
pose would replay from the wrong square, and the divergence would look like a
drive bug rather than a placement bug.
"""

import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import commands
import config
import setup
import speed_run

TOLERANCE_MM = 1e-6


def _pose():
    state = setup.sim.get_mouse_state()
    return state.x_mm, state.y_mm, state.heading_radians


def test_the_sim_mouse_lands_in_the_centre_of_the_start_cell():
    for cell, heading in (((0, 0), "n"), ((2, 1), "e"), ((1, 2), "s"), ((3, 3), "w")):
        speed_run._place_sim_mouse((cell[0], cell[1], heading))
        x_mm, y_mm, heading_radians = _pose()
        assert abs(x_mm - (cell[0] + 0.5) * config.MM_PER_CELL) < TOLERANCE_MM, cell
        assert abs(y_mm - (cell[1] + 0.5) * config.MM_PER_CELL) < TOLERANCE_MM, cell
        expected = config.HEADING_RADIANS[heading] % (2.0 * math.pi)
        assert abs(heading_radians % (2.0 * math.pi) - expected) < TOLERANCE_MM, heading
    print("✓ test_the_sim_mouse_lands_in_the_centre_of_the_start_cell passed")


def test_every_compass_heading_points_the_way_side_delta_says():
    """HEADING_RADIANS and SIDE_DELTA must agree, or a route drives sideways."""
    for side, (dx, dy) in config.SIDE_DELTA.items():
        angle = config.HEADING_RADIANS[side]
        assert abs(math.cos(angle) - dx) < 1e-9, side
        assert abs(math.sin(angle) - dy) < 1e-9, side
    print("✓ test_every_compass_heading_points_the_way_side_delta_says passed")


def test_a_route_grid_builds_the_world_without_a_maze_file():
    """A hand-drawn 3x3 has no .num behind it; the 16x16 default is the wrong world."""
    _render, world = speed_run._sim_world(grid=(3, 3), start_pose=(1, 1, "e"))
    assert (world.cols, world.rows) == (3, 3), (world.cols, world.rows)
    x_mm, _y_mm, _heading = _pose()
    assert abs(x_mm - 1.5 * config.MM_PER_CELL) < TOLERANCE_MM, x_mm
    print("✓ test_a_route_grid_builds_the_world_without_a_maze_file passed")


def test_a_map_file_still_wins_over_the_route_grid():
    _render, world = speed_run._sim_world("mazes/blank6x6.num", grid=(3, 3))
    assert (world.cols, world.rows) == (6, 6), (world.cols, world.rows)
    print("✓ test_a_map_file_still_wins_over_the_route_grid passed")


def test_the_committed_lap_fixture_starts_and_ends_in_the_same_cell():
    header = commands.read_route_header(config.ROUTES_DIR + "/lap3x3.mmc")
    speed_run._place_sim_mouse(header["start"])
    before = _pose()
    speed_run._place_sim_mouse((header["goal"][0], header["goal"][1], header["start"][2]))
    assert _pose() == before, "the fixture's goal is not its start"
    print("✓ test_the_committed_lap_fixture_starts_and_ends_in_the_same_cell passed")


TESTS = (
    test_the_sim_mouse_lands_in_the_centre_of_the_start_cell,
    test_every_compass_heading_points_the_way_side_delta_says,
    test_a_route_grid_builds_the_world_without_a_maze_file,
    test_a_map_file_still_wins_over_the_route_grid,
    test_the_committed_lap_fixture_starts_and_ends_in_the_same_cell,
)


if __name__ == "__main__":
    if setup.sim is None:
        print("SKIPPED: no simulation engine (this is hardware)")
        sys.exit(0)
    for test in TESTS:
        test()
    print("ALL {} ROUTE POSE TESTS PASSED".format(len(TESTS)))
