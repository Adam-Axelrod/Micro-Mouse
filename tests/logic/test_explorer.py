"""Pure: the Explorer. Belief map plus grid position, no sensors and no motors."""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_DIR = os.path.dirname(TESTS_DIR)
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import config
import maze
from explorer import Explorer


def test_starts_at_the_start_facing_north():
    ex = Explorer()
    assert ex.get_pos() == config.START_POS
    assert ex.get_direction() == config.DIRECTIONS[0] == "n"
    assert ex.get_destination() == ex.belief_map.goal
    assert ex.path_done == [config.START_POS]
    print("✓ test_starts_at_the_start_facing_north passed")


def test_observe_is_the_only_wall_channel_and_it_mirrors():
    ex = Explorer(belief_map=maze.MazeStructure(cols=4, rows=4))
    ex.observe((0, 0), ["e"])
    assert ex.belief_map.cells[(0, 0)][config.WALL_INDEX["e"]] == 1
    assert ex.belief_map.cells[(1, 0)][config.WALL_INDEX["w"]] == 1
    print("✓ test_observe_is_the_only_wall_channel_and_it_mirrors passed")


def test_observe_leaves_unreported_sides_open():
    """A blank belief is optimistic: every interior edge starts open, so an
    observation only has to record the walls it found."""
    ex = Explorer(belief_map=maze.MazeStructure(cols=4, rows=4))
    ex.observe((1, 1), ["n"])
    walls = ex.belief_map.cells[(1, 1)]
    assert walls[config.WALL_INDEX["n"]] == 1
    assert walls[config.WALL_INDEX["e"]] == 0
    assert walls[config.WALL_INDEX["s"]] == 0
    assert walls[config.WALL_INDEX["w"]] == 0
    print("✓ test_observe_leaves_unreported_sides_open passed")


def test_turn_clockwise_cycles_n_e_s_w():
    heading = "n"
    for expected in ("e", "s", "w", "n"):
        heading = Explorer.turn_clockwise(heading)
        assert heading == expected
    print("✓ test_turn_clockwise_cycles_n_e_s_w passed")


def test_step_turns_before_it_moves():
    """One step is one action: a pivot OR an advance, never both. The mouse body
    mirrors these steps, so a step that did two things would desynchronise it."""
    ex = Explorer(belief_map=maze.MazeStructure(cols=4, rows=4))
    ex.path_to_execute = [(1, 0)]            # east of the start, but we face north

    ex.step()
    assert ex.get_pos() == (0, 0), "must not move while pointing the wrong way"
    assert ex.get_direction() == "e"

    ex.step()
    assert ex.get_pos() == (1, 0)
    assert ex.path_to_execute == []
    assert ex.path_done == [(0, 0), (1, 0)]
    print("✓ test_step_turns_before_it_moves passed")


def test_step_turns_the_long_way_round_rather_than_anticlockwise():
    """turn_clockwise is the only pivot the Explorer has, so a westward target
    costs three steps. That is a known cost, not a bug -- pin it so a change
    to the turn logic is deliberate."""
    ex = Explorer(belief_map=maze.MazeStructure(cols=4, rows=4), pos=(1, 1))
    ex.path_to_execute = [(0, 1)]
    turns = 0
    while ex.get_pos() != (0, 1):
        ex.step()
        turns += 1
        assert turns < 10, "step never reached the target"
    assert turns == 4, f"three pivots plus one move, got {turns}"
    print("✓ test_step_turns_the_long_way_round_rather_than_anticlockwise passed")


def test_step_on_an_empty_plan_does_nothing():
    ex = Explorer()
    ex.step()
    assert ex.get_pos() == config.START_POS
    print("✓ test_step_on_an_empty_plan_does_nothing passed")


def test_step_rejects_a_non_adjacent_target():
    ex = Explorer(belief_map=maze.MazeStructure(cols=4, rows=4))
    ex.path_to_execute = [(2, 2)]
    raised = False
    try:
        ex.step()
    except ValueError:
        raised = True
    assert raised, "a diagonal or distant target must raise, not teleport"
    print("✓ test_step_rejects_a_non_adjacent_target passed")


def test_at_goal_and_at_destination_are_different_questions():
    """at_goal is reserved for the return-run trigger; at_destination answers
    'am I where I am currently heading'. A return run has them disagree."""
    belief = maze.MazeStructure(cols=4, rows=4)
    ex = Explorer(belief_map=belief, destination=(0, 0), pos=belief.goal)
    assert ex.at_goal()
    assert not ex.at_destination()

    ex.set_pos((0, 0))
    assert not ex.at_goal()
    assert ex.at_destination()
    print("✓ test_at_goal_and_at_destination_are_different_questions passed")


def test_optimal_from_known_strips_the_loops():
    belief = maze.MazeStructure(cols=4, rows=4)
    ex = Explorer(belief_map=belief, destination=(2, 0))
    # Walked out east, into a dead end north, back, then on: the loop must go.
    ex.path_done = [(0, 0), (1, 0), (1, 1), (1, 0), (2, 0)]
    ex.set_pos((2, 0))
    assert ex.optimal_from_known() == [(0, 0), (1, 0), (2, 0)]
    print("✓ test_optimal_from_known_strips_the_loops passed")


def test_optimal_from_known_is_empty_before_arrival():
    ex = Explorer()
    ex.path_done = [(0, 0), (0, 1)]
    assert ex.optimal_from_known() == [], "no route to report until it arrives"
    print("✓ test_optimal_from_known_is_empty_before_arrival passed")


TESTS = [
    test_starts_at_the_start_facing_north,
    test_observe_is_the_only_wall_channel_and_it_mirrors,
    test_observe_leaves_unreported_sides_open,
    test_turn_clockwise_cycles_n_e_s_w,
    test_step_turns_before_it_moves,
    test_step_turns_the_long_way_round_rather_than_anticlockwise,
    test_step_on_an_empty_plan_does_nothing,
    test_step_rejects_a_non_adjacent_target,
    test_at_goal_and_at_destination_are_different_questions,
    test_optimal_from_known_strips_the_loops,
    test_optimal_from_known_is_empty_before_arrival,
]

if __name__ == "__main__":
    for test in TESTS:
        test()
    print(f"ALL {len(TESTS)} EXPLORER TESTS PASSED")
