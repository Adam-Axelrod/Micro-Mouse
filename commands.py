import os
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


def render_command_file(movement_commands, maze_name=None):
    """Render movement commands as line-oriented text string."""
    lines = ["# micromouse route v1"]
    if maze_name:
        lines.append(f"# maze: {maze_name}")
    lines.extend(movement_commands)
    return "\n".join(lines) + "\n"


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
