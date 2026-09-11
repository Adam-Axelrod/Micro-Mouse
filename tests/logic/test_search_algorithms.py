"""Pure: flood fill, greedy descent and the replan trigger. Cells only."""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_DIR = os.path.dirname(TESTS_DIR)
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import config
import maze
import search_algorithms as sa


def blank(cols=4, rows=4):
    return maze.MazeStructure(cols=cols, rows=rows)


def test_open_neighbours_respects_walls_and_the_border():
    grid = blank()
    assert sorted(sa.open_neighbours(grid, (0, 0))) == [(0, 1), (1, 0)], "corner has two exits"
    assert len(sa.open_neighbours(grid, (1, 1))) == 4

    grid.mark_wall((1, 1), "n")
    assert sorted(sa.open_neighbours(grid, (1, 1))) == [(0, 1), (1, 0), (2, 1)]
    assert (1, 1) not in sa.open_neighbours(grid, (1, 2)), "the mirrored side blocks too"
    print("✓ test_open_neighbours_respects_walls_and_the_border passed")


def test_open_neighbours_iterates_north_first():
    """Tie-break order is n, e, s, w. The blank-maze route depends on it."""
    assert sa.open_neighbours(blank(), (1, 1))[0] == (1, 2)
    print("✓ test_open_neighbours_iterates_north_first passed")


def test_flood_distances_are_manhattan_on_a_blank_grid():
    grid = blank()
    distances = sa.flood_distances(grid, (0, 0))
    assert len(distances) == 16, "every cell is reachable on a blank grid"
    for (x, y), distance in distances.items():
        assert distance == x + y, ((x, y), distance)
    print("✓ test_flood_distances_are_manhattan_on_a_blank_grid passed")


def test_flood_distances_omit_walled_off_cells():
    grid = blank()
    for side in config.DIRECTIONS:
        grid.mark_wall((1, 1), side)
    distances = sa.flood_distances(grid, (0, 0))
    assert (1, 1) not in distances, "a sealed cell has no distance"
    assert len(distances) == 15
    print("✓ test_flood_distances_omit_walled_off_cells passed")


def test_flood_fill_plans_a_shortest_route_to_the_goal():
    grid = blank()
    route = sa.flood_fill(grid, (0, 0))
    assert route[0] == (0, 0)
    assert route[-1] == grid.goal == (1, 1)
    assert len(route) == 3, f"two steps plus the start cell, got {route}"
    assert sa.route_is_open(grid, route)
    print("✓ test_flood_fill_plans_a_shortest_route_to_the_goal passed")


def test_flood_fill_takes_the_destination_argument_for_a_return_run():
    """The destination is mutable: the centre on the way out, the start on the
    way back. It is a parameter, not maze.goal."""
    grid = blank()
    route = sa.flood_fill(grid, grid.goal, destination=(0, 0))
    assert route[0] == grid.goal
    assert route[-1] == (0, 0)
    assert len(route) == 3
    print("✓ test_flood_fill_takes_the_destination_argument_for_a_return_run passed")


def test_flood_fill_returns_empty_when_the_destination_is_unreachable():
    grid = blank()
    for side in config.DIRECTIONS:
        grid.mark_wall(grid.goal, side)
    assert sa.flood_fill(grid, (0, 0)) == []
    print("✓ test_flood_fill_returns_empty_when_the_destination_is_unreachable passed")


def test_flood_fill_from_the_destination_is_a_single_cell():
    grid = blank()
    assert sa.flood_fill(grid, grid.goal) == [grid.goal]
    print("✓ test_flood_fill_from_the_destination_is_a_single_cell passed")


def test_flood_fill_walks_around_a_wall():
    """A wall on the direct line must lengthen the route, not break it."""
    grid = blank(cols=5, rows=5)
    grid.mark_wall((0, 0), "n")
    route = sa.flood_fill(grid, (0, 0), destination=(0, 2))
    assert route[0] == (0, 0) and route[-1] == (0, 2)
    assert len(route) == 5, f"detour of four steps, got {route}"
    assert sa.route_is_open(grid, route)
    print("✓ test_flood_fill_walks_around_a_wall passed")


def test_route_is_open_is_the_replan_trigger():
    grid = blank(cols=6, rows=6)
    route = sa.flood_fill(grid, (0, 0))
    assert sa.route_is_open(grid, route)

    # Drop a wall across the first step: the route must go stale.
    first, second = route[0], route[1]
    side = config.DELTA_SIDE[(second[0] - first[0], second[1] - first[1])]
    grid.mark_wall(first, side)
    assert not sa.route_is_open(grid, route)
    print("✓ test_route_is_open_is_the_replan_trigger passed")


def test_route_is_open_ignores_a_wall_off_the_route():
    grid = blank(cols=6, rows=6)
    route = sa.flood_fill(grid, (0, 0))
    grid.mark_wall((5, 5), "w")
    assert sa.route_is_open(grid, route), "an unrelated wall must not force a replan"
    print("✓ test_route_is_open_ignores_a_wall_off_the_route passed")


def test_route_is_open_rejects_a_broken_route():
    grid = blank()
    assert sa.route_is_open(grid, []), "nothing to walk is trivially open"
    assert sa.route_is_open(grid, [(0, 0)])
    assert not sa.route_is_open(grid, [(0, 0), (2, 2)]), "not grid-adjacent"
    assert not sa.route_is_open(grid, [(9, 9), (9, 8)]), "off the grid"
    print("✓ test_route_is_open_rejects_a_broken_route passed")


def test_flood_fill_solves_the_shipped_ground_truth_maze():
    cells, cols, rows = maze.num_file_import(config.DEFAULT_MAZE)
    grid = maze.MazeStructure(cells=cells, cols=cols, rows=rows)
    route = sa.flood_fill(grid, config.START_POS)
    assert route, "the shipped maze must be solvable from the start cell"
    assert route[0] == config.START_POS and route[-1] == grid.goal
    assert sa.route_is_open(grid, route)
    # Every step is one cell, and no cell repeats: a descent cannot double back.
    assert len(set(route)) == len(route)
    for cell, nxt in zip(route, route[1:]):
        assert abs(nxt[0] - cell[0]) + abs(nxt[1] - cell[1]) == 1
    print("✓ test_flood_fill_solves_the_shipped_ground_truth_maze passed")


TESTS = [
    test_open_neighbours_respects_walls_and_the_border,
    test_open_neighbours_iterates_north_first,
    test_flood_distances_are_manhattan_on_a_blank_grid,
    test_flood_distances_omit_walled_off_cells,
    test_flood_fill_plans_a_shortest_route_to_the_goal,
    test_flood_fill_takes_the_destination_argument_for_a_return_run,
    test_flood_fill_returns_empty_when_the_destination_is_unreachable,
    test_flood_fill_from_the_destination_is_a_single_cell,
    test_flood_fill_walks_around_a_wall,
    test_route_is_open_is_the_replan_trigger,
    test_route_is_open_ignores_a_wall_off_the_route,
    test_route_is_open_rejects_a_broken_route,
    test_flood_fill_solves_the_shipped_ground_truth_maze,
]

if __name__ == "__main__":
    for test in TESTS:
        test()
    print(f"ALL {len(TESTS)} SEARCH TESTS PASSED")
