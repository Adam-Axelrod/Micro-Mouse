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


def render_command_file(movement_commands, maze_name=None):
    """Render movement commands as line-oriented text string."""
    lines = ["# micromouse route v1"]
    if maze_name:
        lines.append(f"# maze: {maze_name}")
    lines.extend(movement_commands)
    return "\n".join(lines) + "\n"


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


def write_command_file(route, out_path_str, start_heading=config.DIRECTIONS[0], maze_name=None):
    """Convert route to commands and write to text file."""
    movement_commands = path_to_commands(route, start_heading)
    with open(out_path_str, "w") as file_handle:
        file_handle.write(render_command_file(movement_commands, maze_name))
    return movement_commands


if __name__ == "__main__":
    test_route = [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2)]
    cmds = path_to_commands(test_route)
    print("Test commands:", cmds)
    assert cmds == ["F 2", "R", "F 2", "H"]

    # Render and parse must round-trip: what the route editor writes is exactly
    # what the follow-route mode reads back.
    rendered = render_command_file(cmds, maze_name="selftest.num")
    assert parse_command_file(rendered) == cmds, parse_command_file(rendered)

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
