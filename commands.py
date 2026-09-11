import config

# Kept tiny and egocentric: F carries cell count; turns take no arguments
FORWARD = "F"   # F n: drive forward n cells
LEFT = "L"      # pivot 90 deg left in place
RIGHT = "R"     # pivot 90 deg right in place
UTURN = "U"     # 180 deg turn in place
HALT = "H"      # end of route

TURN_FOR_STEPS = {1: RIGHT, 2: UTURN, 3: LEFT}


def turn_between(current_heading, target_heading):
    """Determine the shortest pivot verb to change heading from current to target."""
    current_index = config.DIRECTIONS.index(current_heading)
    target_index = config.DIRECTIONS.index(target_heading)
    steps = (target_index - current_index) % len(config.DIRECTIONS)
    if steps == 0:
        raise ValueError(f"No turn needed from {current_heading} to {target_heading}")
    return TURN_FOR_STEPS[steps]


def path_to_commands(route, start_heading=config.DIRECTIONS[0]):
    """Convert a list of grid cells into egocentric movement commands (F n, L, R, U, H)."""
    movement_commands = []
    current_heading = start_heading
    forward_run_count = 0

    for current_cell, next_cell in zip(route, route[1:]):
        delta = (next_cell[0] - current_cell[0], next_cell[1] - current_cell[1])
        if delta not in config.DELTA_SIDE:
            raise ValueError(f"{next_cell} is not grid-adjacent to {current_cell}")
        needed_heading = config.DELTA_SIDE[delta]

        if needed_heading != current_heading:
            if forward_run_count > 0:
                movement_commands.append(f"{FORWARD} {forward_run_count}")
                forward_run_count = 0
            movement_commands.append(turn_between(current_heading, needed_heading))
            current_heading = needed_heading
        forward_run_count += 1

    if forward_run_count > 0:
        movement_commands.append(f"{FORWARD} {forward_run_count}")
    movement_commands.append(HALT)

    return movement_commands


QUARTER_TURNS = {RIGHT: 1, LEFT: -1, UTURN: 2}


def net_quarter_turns(movement_commands):
    """Signed quarter turns a verb list performs. Clockwise is positive.

    A route meant to be driven in laps should end on the heading it started on,
    i.e. a multiple of 4. `path_to_commands` cannot express that on its own: it
    derives turns from cell transitions, so the last verb is always a drive and
    the route ends facing wherever the final move pointed. A closing turn has to
    be appended deliberately -- see routes/lap3x3.mmc.
    """
    return sum(QUARTER_TURNS.get(verb.split()[0], 0) for verb in movement_commands if verb.strip())


def closes_the_loop(movement_commands):
    """True if the route returns to its starting heading."""
    return net_quarter_turns(movement_commands) % 4 == 0


# Clockwise quarter turns from each heading, so a verb list can be walked on the
# grid without a maze, a planner or a motor.
_RIGHT_OF = {"n": "e", "e": "s", "s": "w", "w": "n"}


def turn_heading(heading, quarter_turns):
    """The heading after `quarter_turns` clockwise quarters from `heading`."""
    for _ in range(quarter_turns % 4):
        heading = _RIGHT_OF[heading]
    return heading


def walk_route(movement_commands, start_pose):
    """Cells a verb list visits, as [(x, y, heading), ...] including the start.

    Pure grid arithmetic: it answers where a route GOES, which `net_quarter_turns`
    cannot. Laps need both. A route may end on its start heading and still finish
    two cells away, and driving that thirty times walks off the maze -- the saved
    perimeter route does exactly this.
    """
    x, y, heading = start_pose
    poses = [(x, y, heading)]
    for command_string in movement_commands:
        if not command_string or command_string.startswith("#"):
            continue
        parts = command_string.split()
        verb = parts[0]
        if verb == FORWARD:
            dx, dy = config.SIDE_DELTA[heading]
            for _ in range(int(parts[1])):
                x += dx
                y += dy
                poses.append((x, y, heading))
        elif verb in QUARTER_TURNS:
            heading = turn_heading(heading, QUARTER_TURNS[verb])
            poses.append((x, y, heading))
        elif verb == HALT:
            break
    return poses


def returns_to_start(movement_commands, start_pose):
    """True if the route ends in its start cell on its start heading."""
    return walk_route(movement_commands, start_pose)[-1] == tuple(start_pose)


def leaves_the_grid(movement_commands, start_pose, grid):
    """Cells the route visits that do not exist on a `grid` = (cols, rows)."""
    cols, rows = grid
    return [(x, y) for x, y, _heading in walk_route(movement_commands, start_pose)
            if not (0 <= x < cols and 0 <= y < rows)]


# Route file header. The verbs are egocentric, so the same verb list drives a
# different shape from a different start pose, and a grid that is not 16x16 has
# no centre convention to fall back on. The header carries the pose the route was
# drawn from so the operator knows where to place the robot and the sim can put
# the mouse in the same spot. Comment lines, so a reader that ignores them still
# gets the right verbs.
HEADER_MAZE = "# maze:"
HEADER_GRID = "# grid:"
HEADER_START = "# start:"
HEADER_GOAL = "# goal:"


def render_command_file(movement_commands, maze_name=None, grid=None,
                        start=None, goal=None):
    """Render movement commands as line-oriented text string.

    `grid` is (cols, rows), `start` is (x, y, heading), `goal` is (x, y).
    """
    lines = ["# micromouse route v1"]
    if maze_name:
        lines.append(f"{HEADER_MAZE} {maze_name}")
    if grid:
        lines.append(f"{HEADER_GRID} {grid[0]}x{grid[1]}")
    if start:
        lines.append(f"{HEADER_START} {start[0]} {start[1]} {start[2]}")
    if goal:
        lines.append(f"{HEADER_GOAL} {goal[0]} {goal[1]}")
    lines.extend(movement_commands)
    return "\n".join(lines) + "\n"


def parse_route_header(text):
    """Read the header comments of a .mmc into a dict. Missing keys are absent.

    A file written before the header existed yields {}, which every caller must
    treat as "unknown pose", not as (0, 0) facing north.
    """
    header = {}
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line.startswith("#"):
            continue
        if line.startswith(HEADER_MAZE):
            header["maze"] = line[len(HEADER_MAZE):].strip()
        elif line.startswith(HEADER_GRID):
            cols, _, rows = line[len(HEADER_GRID):].strip().partition("x")
            header["grid"] = (int(cols), int(rows))
        elif line.startswith(HEADER_START):
            x, y, heading = line[len(HEADER_START):].split()
            if heading not in config.DIRECTIONS:
                raise ValueError(f"'{heading}' is not a compass heading")
            header["start"] = (int(x), int(y), heading)
        elif line.startswith(HEADER_GOAL):
            x, y = line[len(HEADER_GOAL):].split()
            header["goal"] = (int(x), int(y))
    return header


def read_route_header(path_str):
    """Header dict of a .mmc file on disk."""
    with open(path_str, "r") as file_handle:
        return parse_route_header(file_handle.read())


VERBS_WITHOUT_ARG = (LEFT, RIGHT, UTURN, HALT)


def parse_command_file(text):
    """Parse .mmc text into a list of movement verbs.

    The inverse of render_command_file. Comment lines (leading '#') and blanks
    are dropped. Every verb is VALIDATED here rather than at the motors: a
    malformed route must fail before the wheels turn, not halfway down a
    corridor. Returns the same shape path_to_commands produces.
    """
    movement_commands = []
    for line_number, raw_line in enumerate(text.split("\n"), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        verb = parts[0]

        if verb == FORWARD:
            if len(parts) != 2:
                raise ValueError("line {}: '{}' needs a cell count".format(line_number, line))
            try:
                cells = int(parts[1])
            except ValueError:
                raise ValueError("line {}: '{}' is not a cell count".format(line_number, parts[1]))
            if cells < 1:
                raise ValueError("line {}: F {} does not move".format(line_number, cells))
            movement_commands.append("{} {}".format(FORWARD, cells))
        elif verb in VERBS_WITHOUT_ARG:
            if len(parts) != 1:
                raise ValueError("line {}: '{}' takes no argument".format(line_number, verb))
            movement_commands.append(verb)
        else:
            raise ValueError("line {}: unknown verb '{}'".format(line_number, verb))

    if not movement_commands:
        raise ValueError("route is empty")
    return movement_commands


def read_command_file(path_str):
    """Read a .mmc route file into a list of movement verbs."""
    with open(path_str, "r") as file_handle:
        return parse_command_file(file_handle.read())


def write_command_file(route, out_path_str, start_heading=config.DIRECTIONS[0],
                       maze_name=None, grid=None):
    """Convert route to commands and write to text file."""
    movement_commands = path_to_commands(route, start_heading)
    with open(out_path_str, "w") as file_handle:
        file_handle.write(render_command_file(
            movement_commands, maze_name, grid,
            start=(route[0][0], route[0][1], start_heading),
            goal=route[-1]))
    return movement_commands


if __name__ == "__main__":
    test_route = [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2)]
    cmds = path_to_commands(test_route)
    print("Test commands:", cmds)
    assert cmds == ["F 2", "R", "F 2", "H"]

    # Render and parse must round-trip: what the route editor writes is exactly
    # what the follow-route mode reads back.
    rendered = render_command_file(cmds, maze_name="selftest.num", grid=(3, 3),
                                   start=(0, 0, "n"), goal=(2, 2))
    assert parse_command_file(rendered) == cmds, parse_command_file(rendered)
    header = parse_route_header(rendered)
    assert header == {"maze": "selftest.num", "grid": (3, 3),
                      "start": (0, 0, "n"), "goal": (2, 2)}, header
    assert parse_route_header(render_command_file(cmds)) == {}

    for bad, why in (("F", "F with no count"), ("F 0", "a move of zero cells"),
                     ("F x", "a non-numeric count"), ("R 2", "a turn with an argument"),
                     ("Z", "an unknown verb"), ("# only a comment", "an empty route")):
        try:
            parse_command_file(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("parse_command_file accepted " + why)
    print("commands self-tests passed")
