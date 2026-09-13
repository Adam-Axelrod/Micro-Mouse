"""Pure: cell routes to egocentric verbs (F n, L, R, U, H)."""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_DIR = os.path.dirname(TESTS_DIR)
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import tempfile

from brain import commands
import config
from brain import maze
from brain import search_algorithms as sa


def test_turn_between_picks_the_shortest_pivot():
    assert commands.turn_between("n", "e") == commands.RIGHT
    assert commands.turn_between("n", "w") == commands.LEFT
    assert commands.turn_between("n", "s") == commands.UTURN
    assert commands.turn_between("w", "n") == commands.RIGHT
    assert commands.turn_between("e", "n") == commands.LEFT
    print("✓ test_turn_between_picks_the_shortest_pivot passed")


def test_turn_between_rejects_a_turn_that_is_not_needed():
    raised = False
    try:
        commands.turn_between("n", "n")
    except ValueError:
        raised = True
    assert raised, "asking for a zero turn is a caller bug, not a no-op"
    print("✓ test_turn_between_rejects_a_turn_that_is_not_needed passed")


def test_path_to_commands_runs_straight_cells_together():
    route = [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2)]
    assert commands.path_to_commands(route) == ["F 2", "R", "F 2", "H"]
    print("✓ test_path_to_commands_runs_straight_cells_together passed")


def test_path_to_commands_starts_with_a_turn_when_it_must():
    """Facing north, an eastward first step has to pivot before it drives."""
    assert commands.path_to_commands([(0, 0), (1, 0)]) == ["R", "F 1", "H"]
    print("✓ test_path_to_commands_starts_with_a_turn_when_it_must passed")


def test_path_to_commands_honours_the_start_heading():
    route = [(0, 0), (1, 0), (2, 0)]
    assert commands.path_to_commands(route, start_heading="e") == ["F 2", "H"]
    assert commands.path_to_commands(route, start_heading="w") == ["U", "F 2", "H"]
    print("✓ test_path_to_commands_honours_the_start_heading passed")


def test_path_to_commands_emits_a_uturn_for_a_reversal():
    route = [(0, 0), (0, 1), (0, 0)]
    assert commands.path_to_commands(route) == ["F 1", "U", "F 1", "H"]
    print("✓ test_path_to_commands_emits_a_uturn_for_a_reversal passed")


def test_an_empty_or_single_cell_route_is_just_halt():
    assert commands.path_to_commands([]) == ["H"]
    assert commands.path_to_commands([(0, 0)]) == ["H"]
    print("✓ test_an_empty_or_single_cell_route_is_just_halt passed")


def test_path_to_commands_rejects_a_non_adjacent_step():
    raised = False
    try:
        commands.path_to_commands([(0, 0), (2, 2)])
    except ValueError:
        raised = True
    assert raised
    print("✓ test_path_to_commands_rejects_a_non_adjacent_step passed")


def test_commands_end_with_halt_and_use_only_known_verbs():
    """Whatever the route, the verb set is closed. speed_run switches on it and
    silently ignores anything it does not recognise."""
    cells, cols, rows = maze.num_file_import(config.DEFAULT_MAZE)
    grid = maze.MazeStructure(cells=cells, cols=cols, rows=rows)
    route = sa.flood_fill(grid, config.START_POS)
    verbs = commands.path_to_commands(route)

    assert verbs[-1] == commands.HALT
    assert commands.HALT not in verbs[:-1]
    forward_cells = 0
    for verb in verbs[:-1]:
        parts = verb.split()
        assert parts[0] in (commands.FORWARD, commands.LEFT, commands.RIGHT, commands.UTURN), verb
        if parts[0] == commands.FORWARD:
            assert len(parts) == 2 and int(parts[1]) > 0, verb
            forward_cells += int(parts[1])
        else:
            assert len(parts) == 1, "a turn verb takes no argument"
    assert forward_cells == len(route) - 1, "every step of the route must be driven"
    print("✓ test_commands_end_with_halt_and_use_only_known_verbs passed")


def test_render_command_file_has_a_version_header():
    text = commands.render_command_file(["F 2", "H"], maze_name="groundtruth")
    lines = text.split("\n")
    assert lines[0] == "# micromouse route v1"
    assert lines[1] == "# maze: groundtruth"
    assert lines[2:4] == ["F 2", "H"]
    assert text.endswith("\n")

    assert commands.render_command_file(["H"]).split("\n")[1] == "H", "maze name is optional"
    print("✓ test_render_command_file_has_a_version_header passed")


def test_write_command_file_round_trips():
    handle, path = tempfile.mkstemp(suffix=".mmc")
    os.close(handle)
    try:
        route = [(0, 0), (0, 1), (1, 1)]
        written = commands.write_command_file(route, path, maze_name="unit")
        with open(path) as file_handle:
            body = [line for line in file_handle.read().split("\n")
                    if line and not line.startswith("#")]
        assert body == written == ["F 1", "R", "F 1", "H"]
    finally:
        os.remove(path)
    print("✓ test_write_command_file_round_trips passed")


def test_the_header_carries_the_pose_a_route_was_drawn_from():
    """Egocentric verbs are only correct from one pose, so the file records it."""
    verbs = ["F 2", "R", "F 1", commands.HALT]
    text = commands.render_command_file(verbs, maze_name="blank3x3.num", grid=(3, 3),
                                        start=(0, 0, "n"), goal=(2, 2))
    header = commands.parse_route_header(text)
    assert header == {"maze": "blank3x3.num", "grid": (3, 3),
                      "start": (0, 0, "n"), "goal": (2, 2)}, header
    assert commands.parse_command_file(text) == verbs, "the header changed the verbs"
    print("✓ test_the_header_carries_the_pose_a_route_was_drawn_from passed")


def test_a_route_written_before_the_header_existed_still_parses():
    """Header fields are absent, never guessed: (0, 0) facing north is a guess."""
    legacy = "# micromouse route v1\n# maze: old.num\nF 2\nH\n"
    assert commands.parse_command_file(legacy) == ["F 2", commands.HALT]
    assert commands.parse_route_header(legacy) == {"maze": "old.num"}
    print("✓ test_a_route_written_before_the_header_existed_still_parses passed")


def test_a_header_naming_a_direction_that_is_not_a_compass_side_is_refused():
    for bad in ("# start: 0 0 up\n", "# start: 0 0 N\n"):
        try:
            commands.parse_route_header(bad)
        except ValueError:
            continue
        raise AssertionError("parse_route_header accepted " + repr(bad))
    print("✓ test_a_header_naming_a_direction_that_is_not_a_compass_side_is_refused passed")


def test_omitted_header_fields_are_left_out_of_the_file():
    text = commands.render_command_file(["F 1", commands.HALT])
    assert commands.parse_route_header(text) == {}
    assert text.startswith("# micromouse route v1")
    print("✓ test_omitted_header_fields_are_left_out_of_the_file passed")


def test_write_command_file_records_the_start_and_the_goal():
    path = "_commands_header_selftest.mmc"
    try:
        route = [(2, 1), (2, 2), (3, 2)]
        commands.write_command_file(route, path, start_heading="e",
                                    maze_name="unit", grid=(6, 6))
        header = commands.read_route_header(path)
        assert header["start"] == (2, 1, "e"), header
        assert header["goal"] == (3, 2), header
        assert header["grid"] == (6, 6), header
    finally:
        os.remove(path)
    print("✓ test_write_command_file_records_the_start_and_the_goal passed")


def test_walk_route_reports_every_cell_in_order():
    verbs = ["F 2", "R", "F 1", "H"]
    poses = commands.walk_route(verbs, (0, 0, "n"))
    assert poses[0] == (0, 0, "n"), poses
    assert [p[:2] for p in poses] == [(0, 0), (0, 1), (0, 2), (0, 2), (1, 2)], poses
    assert poses[-1] == (1, 2, "e"), poses[-1]
    print("✓ test_walk_route_reports_every_cell_in_order passed")


def test_walk_route_stops_at_halt():
    poses = commands.walk_route(["F 1", "H", "F 9"], (0, 0, "n"))
    assert poses[-1] == (0, 1, "n"), poses
    print("✓ test_walk_route_stops_at_halt passed")


def test_a_route_can_close_in_heading_and_not_in_position():
    """The saved perimeter route did exactly this, and 30 laps of it drives off."""
    verbs = ["F 2", "R", "F 2", "R", "F 2", "R", "F 1", "R", "F 1", "H"]
    assert commands.closes_the_loop(verbs), "four right turns is a closed heading"
    assert not commands.returns_to_start(verbs, (0, 0, "n")), "but it ends at (1, 1)"
    print("✓ test_a_route_can_close_in_heading_and_not_in_position passed")


def test_the_committed_lap_fixtures_close_and_stay_on_their_grid():
    for name in ("lap3x3.mmc", "lap3x3_via_centre.mmc"):
        path = config.ROUTES_DIR + "/" + name
        verbs = commands.read_command_file(path)
        header = commands.read_route_header(path)
        start = header["start"]
        assert commands.returns_to_start(verbs, start), name
        assert not commands.leaves_the_grid(verbs, start, header["grid"]), name
    print("✓ test_the_committed_lap_fixtures_close_and_stay_on_their_grid passed")


def test_leaves_the_grid_names_the_first_cell_that_does_not_exist():
    outside = commands.leaves_the_grid(["F 4", "H"], (0, 0, "n"), (3, 3))
    assert outside == [(0, 3), (0, 4)], outside
    print("✓ test_leaves_the_grid_names_the_first_cell_that_does_not_exist passed")


def test_turn_heading_wraps_the_compass():
    assert commands.turn_heading("n", 4) == "n"
    assert commands.turn_heading("n", 1) == "e"
    assert commands.turn_heading("n", -1) == "w"
    print("✓ test_turn_heading_wraps_the_compass passed")


def test_a_return_leg_closes_any_walkable_route():
    """A U-turn, the path backwards, a U-turn home: the cell and the heading close."""
    open_route = ["F 2", "R", "F 2", "R", "F 2", "R", "F 1", "R", "F 1", "H"]
    start = (0, 0, "n")
    lap = commands.with_return_leg(open_route, start)
    assert commands.returns_to_start(lap, start), lap
    assert commands.net_quarter_turns(lap) % 4 == 0, lap
    assert not commands.leaves_the_grid(lap, start, (3, 3)), lap
    print("✓ test_a_return_leg_closes_any_walkable_route passed")


def test_a_return_leg_walks_the_same_cells_in_reverse():
    out = ["F 2", "R", "F 1", "H"]
    start = (0, 0, "n")
    there = commands.cell_path(out, start)
    lap = commands.cell_path(commands.with_return_leg(out, start), start)
    assert lap == there + list(reversed(there))[1:], lap
    print("✓ test_a_return_leg_walks_the_same_cells_in_reverse passed")


def test_a_return_leg_ends_with_a_halt_and_only_known_verbs():
    lap = commands.with_return_leg(["F 1", "R", "F 1", "H"], (0, 0, "n"))
    assert lap[-1] == commands.HALT, lap
    assert lap.count(commands.HALT) == 1, lap
    for verb in lap:
        assert verb.split()[0] in (commands.FORWARD,) + commands.VERBS_WITHOUT_ARG, verb
    print("✓ test_a_return_leg_ends_with_a_halt_and_only_known_verbs passed")


def test_cell_path_drops_the_cell_a_turn_repeats():
    path = commands.cell_path(["F 1", "R", "F 1", "H"], (0, 0, "n"))
    assert path == [(0, 0), (0, 1), (1, 1)], path
    print("✓ test_cell_path_drops_the_cell_a_turn_repeats passed")


TESTS = [
    test_a_return_leg_closes_any_walkable_route,
    test_a_return_leg_walks_the_same_cells_in_reverse,
    test_a_return_leg_ends_with_a_halt_and_only_known_verbs,
    test_cell_path_drops_the_cell_a_turn_repeats,
    test_walk_route_reports_every_cell_in_order,
    test_walk_route_stops_at_halt,
    test_a_route_can_close_in_heading_and_not_in_position,
    test_the_committed_lap_fixtures_close_and_stay_on_their_grid,
    test_leaves_the_grid_names_the_first_cell_that_does_not_exist,
    test_turn_heading_wraps_the_compass,
    test_turn_between_picks_the_shortest_pivot,
    test_turn_between_rejects_a_turn_that_is_not_needed,
    test_path_to_commands_runs_straight_cells_together,
    test_path_to_commands_starts_with_a_turn_when_it_must,
    test_path_to_commands_honours_the_start_heading,
    test_path_to_commands_emits_a_uturn_for_a_reversal,
    test_an_empty_or_single_cell_route_is_just_halt,
    test_path_to_commands_rejects_a_non_adjacent_step,
    test_commands_end_with_halt_and_use_only_known_verbs,
    test_render_command_file_has_a_version_header,
    test_write_command_file_round_trips,
    test_the_header_carries_the_pose_a_route_was_drawn_from,
    test_a_route_written_before_the_header_existed_still_parses,
    test_a_header_naming_a_direction_that_is_not_a_compass_side_is_refused,
    test_omitted_header_fields_are_left_out_of_the_file,
    test_write_command_file_records_the_start_and_the_goal,
]

if __name__ == "__main__":
    for test in TESTS:
        test()
    print(f"ALL {len(TESTS)} COMMAND TESTS PASSED")
