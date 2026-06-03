"""Flood-fill path planning over maze cells.

This module is the single, well-labelled source of the path the mouse follows.

SWAP-IN POINT
-------------
Everything downstream only reads ``Maze.path`` / ``Maze.waypoints``. To use a
hardcoded path instead of the flood fill, simply call ``Maze.set_path(my_path)``
(or pass ``path=[...]`` to ``MazeMouseEnv``) and this module is bypassed entirely.
``get_path()`` below is the only function the environment calls by default.
"""
from __future__ import annotations

from collections import deque

from .maze_loader import Walls

Cell = tuple[int, int]

# Wall-flag order in the walls dict is (north, east, south, west).
# Each entry is (dx, dy, wall_index) for the corresponding neighbour.
_DIRECTIONS = (
    (0, 1, 0),    # north
    (1, 0, 1),    # east
    (0, -1, 2),   # south
    (-1, 0, 3),   # west
)


def cell_neighbours(cell: Cell, walls: Walls) -> list[Cell]:
    """Cells reachable from `cell` in one step (i.e. no wall in between)."""
    cell_walls = walls.get(cell)
    if cell_walls is None:
        return []
    x, y = cell
    neighbours = []
    for dx, dy, wall_index in _DIRECTIONS:
        if not cell_walls[wall_index]:               # open on this side
            candidate = (x + dx, y + dy)
            if candidate in walls:
                neighbours.append(candidate)
    return neighbours


def compute_distances(walls: Walls, goal_cells: list[Cell]) -> dict[Cell, int]:
    """BFS flood from the goal outward; maps each cell -> steps to nearest goal."""
    distances: dict[Cell, int] = {g: 0 for g in goal_cells if g in walls}
    queue: deque[Cell] = deque(distances)
    while queue:
        current = queue.popleft()
        for neighbour in cell_neighbours(current, walls):
            if neighbour not in distances:
                distances[neighbour] = distances[current] + 1
                queue.append(neighbour)
    return distances


def extract_path(distances: dict[Cell, int], walls: Walls, start: Cell) -> list[Cell]:
    """Greedy descent from `start` down the distance field to a goal (distance 0)."""
    if start not in distances:
        raise ValueError(f"Start cell {start} is unreachable from the goal.")
    path = [start]
    current = start
    guard = 0
    limit = len(distances) + 1
    while distances[current] != 0:
        neighbours = cell_neighbours(current, walls)
        # Step to the accessible neighbour closest to the goal.
        current = min(neighbours, key=lambda c: distances.get(c, 1 << 30))
        path.append(current)
        guard += 1
        if guard > limit:                            # safety against bad mazes
            raise RuntimeError("Path extraction failed to reach the goal.")
    return path


def generate_turns(path: list[Cell]) -> list[Cell]:
    """Simplify a cell path to just its turning points (start, corners, goal)."""
    if len(path) < 3:
        return list(path)
    simplified = [path[0]]
    prev_dx = path[1][0] - path[0][0]
    prev_dy = path[1][1] - path[0][1]
    for i in range(2, len(path)):
        dx = path[i][0] - path[i - 1][0]
        dy = path[i][1] - path[i - 1][1]
        if (dx, dy) != (prev_dx, prev_dy):           # direction changed -> a turn
            simplified.append(path[i - 1])
        prev_dx, prev_dy = dx, dy
    simplified.append(path[-1])
    return simplified


def default_goal(width: int, height: int) -> list[Cell]:
    """Standard micromouse goal: the central 2x2 block."""
    cx, cy = width // 2, height // 2
    return [(cx, cy), (cx - 1, cy), (cx, cy - 1), (cx - 1, cy - 1)]


def get_path(walls: Walls, start: Cell, goal_cells: list[Cell]) -> list[Cell]:
    """Convenience: flood from the goal, then descend from `start`. The default
    path source used by the environment."""
    distances = compute_distances(walls, goal_cells)
    return extract_path(distances, walls, start)
