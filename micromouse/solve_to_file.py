"""Top-level entry point: take a maze, solve it, and write the Pico command file. This is the whole
PC-side pipeline in one call -- import the .num, flood_fill an optimal route over it, then hand the
absolute cell path to commands.write_command_file, which turns it into egocentric verbs (see
commands.py for the movement seam). No pygame / renderer is touched, so this runs headless.

The route here is the OMNISCIENT solve (flood_fill over the real maze), i.e. the shortest path, which
is what you want to run on hardware -- not the exploration wander. The mouse's real start heading is a
flag because it rotates every turn in the output; default 'n' matches the sim (config.DIRECTIONS[0]).

    python3 -m micromouse.solve_to_file                       # DEFAULT_MAZE -> route.mmc
    python3 -m micromouse.solve_to_file blank.num             # a named example maze
    python3 -m micromouse.solve_to_file blank.num -o run1.mmc # choose the output file
    python3 -m micromouse.solve_to_file --heading e           # real mouse starts facing east
"""

import argparse
import sys

from . import config
from . import maze
from . import commands
from . import search_algorithms


"""Resolve `name` to a maze file path. A bare name (e.g. 'blank.num') is looked up in the example maze
dir; anything with a path separator is used as-is. Returns a Path that exists or raises."""

def resolve_maze(name):
    from pathlib import Path
    candidate = Path(name)
    if candidate.parent == Path("."):                 # bare filename -> look in the example dir
        candidate = config.EXAMPLE_MAZES_DIR / name
    if not candidate.exists():
        raise FileNotFoundError(f"no maze file at {candidate}")
    return candidate


"""Solve `maze_path` and write the command file to `out_path`. Returns the (route, commands) pair so a
caller can inspect or assert on them. Raises if the maze can't be solved from the start cell."""

def solve_to_file(maze_path, out_path, start_heading=config.DIRECTIONS[0]):
    real = maze.MazeStructure(*maze.num_file_import(maze_path))
    route = search_algorithms.flood_fill(real, config.START_POS)
    if len(route) < 2:
        raise ValueError(f"{maze_path.name} is unsolvable from {config.START_POS} (route {len(route)} cells)")
    cmds = commands.write_command_file(
        route, out_path, start_heading=start_heading, maze_name=maze_path.name, solver="flood_fill"
    )
    return route, cmds


def main():
    parser = argparse.ArgumentParser(description="Solve a maze and write a Pico command file.")
    parser.add_argument("maze", nargs="?", default=str(config.DEFAULT_MAZE),
                        help="maze name (looked up in example_mazes) or path (default: DEFAULT_MAZE)")
    parser.add_argument("-o", "--out", default="route.mmc", help="output command file (default: route.mmc)")
    parser.add_argument("--heading", default=config.DIRECTIONS[0], choices=config.DIRECTIONS,
                        help="compass side the real mouse starts facing (default: n)")
    args = parser.parse_args()

    try:                                              # a missing/unsolvable maze is a user error, not a crash
        maze_path = resolve_maze(args.maze)
        route, cmds = solve_to_file(maze_path, args.out, start_heading=args.heading)
    except (FileNotFoundError, ValueError) as err:
        sys.exit(f"error: {err}")
    print(f"{maze_path.name}: {len(route)} cells -> {len(cmds)} commands, wrote {args.out}")


if __name__ == "__main__":
    main()
