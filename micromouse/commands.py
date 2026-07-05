"""Turns an absolute cell path (what the planner produces) into an egocentric command file the
Pi Pico can execute. This is the hardware seam for MOVEMENT, the mirror of env_explorer's sensing
seam: everything above here thinks in compass sides and (col,row) cells; everything below (the
Pico's motor loop) only ever sees relative verbs -- forward, turn left/right, u-turn -- and never
needs to know where north is. All maze-awareness stays on the PC side.

The route is emitted as line-oriented text, one `verb <int>` per line, distances in CELLS (the Pico
converts cells -> ticks with config.MM_PER_CELL / MM_PER_TICK, so the hardware constants live in one
place). Straights are compressed into a single `F n` so the motor loop can run one
accelerate/cruise/decelerate profile per run instead of stopping at every cell.
"""

from pathlib import Path

from . import config

### Command vocabulary ------------------------------------------------------------------------------
# Kept deliberately tiny and egocentric. F carries a cell count; the pivots and halt take no argument.
FORWARD = "F"   # F n : drive forward n cells
LEFT    = "L"   # pivot 90 deg left, in place
RIGHT   = "R"   # pivot 90 deg right, in place
UTURN   = "U"   # 180 deg turn, in place
HALT    = "H"   # end of route

# Clockwise pivots needed to get from the current heading to the target heading, indexed by
# (target_index - current_index) % 4 over config.DIRECTIONS (n,e,s,w is clockwise). We always pick the
# SHORTEST pivot, so a left turn is one `L`, never three `R` -- the planner's clockwise-only limitation
# (explorer.turn_clockwise) is a sim detail and must not leak into what the real mouse does.
TURN_FOR_STEPS = {1: RIGHT, 2: UTURN, 3: LEFT}

### Path -> commands --------------------------------------------------------------------------------

"""The 90 deg pivot that rotates `current` heading onto `target`, both compass sides in DIRECTIONS.
Assumes the two differ (a caller only turns when it must); a 0-step 'no turn' is not a command."""

def turn_between(current, target):
    steps = (config.DIRECTIONS.index(target) - config.DIRECTIONS.index(current)) % len(config.DIRECTIONS)
    if steps == 0:
        raise ValueError(f"no turn needed from {current} to {target}")
    return TURN_FOR_STEPS[steps]


"""Fold an absolute cell route into a list of relative command strings.

`route` is [cell, cell, ...] of grid-adjacent cells, exactly what search_algorithms.flood_fill or
Explorer.optimal_from_known returns. `start_heading` is the compass side the real mouse physically
faces in its start cell (the sim starts at DIRECTIONS[0] = 'n').

Walk consecutive cells: the step's compass side is the heading we need. If it differs from where we
face, flush any forward run we were building, emit the shortest pivot, and turn. Every step then adds
one cell to the current forward run. A trailing `H` marks the end so the Pico knows the route is done
rather than having simply run out of bytes. A route shorter than two cells is just `['H']`."""

def path_to_commands(route, start_heading=config.DIRECTIONS[0]):
    commands = []
    heading = start_heading
    run = 0  # forward cells accumulated in the current straight

    for a, b in zip(route, route[1:]):
        delta = (b[0] - a[0], b[1] - a[1])
        if delta not in config.DELTA_SIDE:
            raise ValueError(f"{b} is not grid-adjacent to {a} (delta {delta})")
        needed = config.DELTA_SIDE[delta]

        if needed != heading:
            if run:                                   # close the straight before pivoting
                commands.append(f"{FORWARD} {run}")
                run = 0
            commands.append(turn_between(heading, needed))
            heading = needed
        run += 1

    if run:
        commands.append(f"{FORWARD} {run}")
    commands.append(HALT)
    return commands

### Command file emit -------------------------------------------------------------------------------

"""Render commands as the on-disk file: a couple of `#` header lines (version + provenance, so a route
and the firmware that reads it can't silently drift) followed by one command per line, newline-ended.
Header lines are comments the Pico parser skips."""

def render_command_file(commands, maze_name=None, solver=None):
    lines = ["# micromouse route v1"]
    if maze_name or solver:
        lines.append(f"# maze: {maze_name}   solver: {solver}")
    lines.extend(commands)
    return "\n".join(lines) + "\n"


"""Write a cell route straight to `out_path` as a command file and return the commands emitted.
This is the one call a solve script makes: path_to_commands + render + write, in order."""

def write_command_file(route, out_path, start_heading=config.DIRECTIONS[0], maze_name=None, solver=None):
    commands = path_to_commands(route, start_heading)
    Path(out_path).write_text(render_command_file(commands, maze_name, solver))
    return commands

### Tests -------------------------------------------------------------------------------------------

if __name__ == "__main__":
    # Shortest-pivot table: from north, e is one right, w is one left, s is a u-turn.
    assert turn_between("n", "e") == RIGHT
    assert turn_between("n", "w") == LEFT
    assert turn_between("n", "s") == UTURN

    # Up two, right two, down one -- starting faced north.
    route = [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2), (2, 1)]
    cmds = path_to_commands(route)
    print("commands:", cmds)
    assert cmds == ["F 2", "R", "F 2", "R", "F 1", "H"], cmds

    # Straights compress and a trailing halt is always emitted; a stationary route is just a halt.
    assert path_to_commands([(0, 0)]) == ["H"]

    print(render_command_file(cmds, maze_name="example4.num", solver="flood_fill"), end="")
