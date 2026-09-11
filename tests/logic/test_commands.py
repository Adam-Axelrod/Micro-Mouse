"""Pure: cell routes to egocentric verbs (F n, L, R, U, H)."""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_DIR = os.path.dirname(TESTS_DIR)
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import tempfile

import commands
import config
import maze
import search_algorithms as sa


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


TESTS = [
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
]

if __name__ == "__main__":
    for test in TESTS:
        test()
    print(f"ALL {len(TESTS)} COMMAND TESTS PASSED")
