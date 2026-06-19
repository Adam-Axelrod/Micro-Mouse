"""mms entry point: a flood-fill explorer driven by the shared micromouse planner.

Runs inside the mackorone/mms simulator (https://github.com/mackorone/mms).
Configure an algorithm with:

    Directory:    this `flood_fill/` folder
    Run command:  python run_mms.py      (or `python3 run_mms.py`)

Communication with the simulator is over stdin/stdout via `API.py`; logging goes
to stderr (`log()` below). See `mms_README.md` and
https://github.com/mackorone/mms#mouse-api

This file is only the mms BACKEND: it reads the four wall sensors, turns and
drives the mouse, and draws on the maze. All of the actual flood-fill logic
(the belief map, the flood, the per-step decision, the verified speed-run route)
lives in `micromouse/flood_fill.py` as the shared `Explorer`, which the
micromouse env and, later, the robot use too. We load that module from its two
pure source files (`flood_fill.py` plus the stdlib-only `maze_loader.py`) so the
mms runtime never has to import the full sim package (numpy / pygame).
"""
import importlib.util
import os
import sys
import types

import API

SHOW_DISTANCES = True   # set False to stop drawing flood values (faster)


def log(message):
    """Log to stderr; stdout is reserved for the mms protocol."""
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


def _load_planner():
    """Load `micromouse/flood_fill.py` without triggering the package __init__
    (which would pull in numpy/pygame). Register a lightweight stub `micromouse`
    package so the module's `from .maze_loader import Walls` resolves, then exec
    the two pure files from disk."""
    here = os.path.dirname(os.path.abspath(__file__))
    mm_dir = os.path.join(os.path.dirname(here), "micromouse")

    stub = types.ModuleType("micromouse")
    stub.__path__ = [mm_dir]
    sys.modules.setdefault("micromouse", stub)

    def load(modname, filename):
        spec = importlib.util.spec_from_file_location(modname, os.path.join(mm_dir, filename))
        module = importlib.util.module_from_spec(spec)
        sys.modules[modname] = module
        spec.loader.exec_module(module)
        return module

    load("micromouse.maze_loader", "maze_loader.py")
    return load("micromouse.flood_fill", "flood_fill.py")


ff = _load_planner()


def read_walls(heading):
    """The absolute compass sides currently showing a wall, read from the four
    heading-relative mms sensors."""
    sides = []
    if API.wallFront():
        sides.append(ff.absolute_side(heading, "front"))
    if API.wallRight():
        sides.append(ff.absolute_side(heading, "right"))
    if API.wallBack():
        sides.append(ff.absolute_side(heading, "back"))
    if API.wallLeft():
        sides.append(ff.absolute_side(heading, "left"))
    return sides


def turn_to(heading, target):
    """Issue the minimal turns to face `target`; return the new heading."""
    diff = (ff.DIRECTIONS.index(target) - ff.DIRECTIONS.index(heading)) % 4
    if diff == 1:
        API.turnRight()
    elif diff == 2:
        API.turnRight()
        API.turnRight()
    elif diff == 3:
        API.turnLeft()
    return target


def draw_distances(distances):
    if SHOW_DISTANCES:
        for (x, y), d in distances.items():
            API.setText(x, y, str(d))


def main():
    log("run_mms.py: flood-fill explorer (shared micromouse planner)")
    width, height = API.mazeWidth(), API.mazeHeight()
    explorer = ff.Explorer(width, height)
    for gx, gy in explorer.goal:
        API.setColor(gx, gy, "G")

    pos = (0, 0)
    heading = "n"                      # mms starts the mouse at (0,0) facing north

    for _ in range(width * height * 4):
        walls = read_walls(heading)
        for side in walls:             # mirror the discovery onto the mms display
            API.setWall(pos[0], pos[1], side)
        explorer.observe(pos, walls)
        draw_distances(explorer.flood())
        if explorer.at_goal(pos):
            log(f"reached goal at {pos}")
            break
        nxt = explorer.next_cell(pos, ff.DELTA[heading])
        if nxt is None:
            break
        target = ff.step_side(pos, nxt)
        heading = turn_to(heading, target)
        try:
            API.moveForward()
        except API.MouseCrashedError:
            # Edge we believed open turned out walled; record it and replan.
            log(f"crash moving {target} from {pos}; marking wall")
            ff.mark_wall(explorer.belief, pos, target)
            API.setWall(pos[0], pos[1], target)
            continue
        API.setColor(pos[0], pos[1], "b")
        pos = nxt
    else:
        log("step budget exhausted without reaching the goal")

    # Draw the speed-run route through cells we actually verified (see
    # Explorer.verified_route): unknown cells are sealed off, so it stays on real
    # corridors rather than the optimistic belief.
    try:
        route = explorer.verified_route((0, 0))
        for cx, cy in ff.generate_turns(route):
            API.setColor(cx, cy, "y")
        log(f"verified route length: {len(route)} cells")
    except (ValueError, RuntimeError) as exc:
        log(f"no fully-known route yet: {exc}")


if __name__ == "__main__":
    main()
