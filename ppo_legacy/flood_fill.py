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


def extract_path(
    distances: dict[Cell, int],
    walls: Walls,
    start: Cell,
    heading: tuple[int, int] | None = None,
) -> list[Cell]:
    """Greedy descent from `start` down the distance field to a goal (distance 0).

    When several accessible neighbours are equally close to the goal, prefer the
    one that continues in the current ``heading`` (dx, dy), which minimises turns.
    Ported from the legacy ``adam_flood_fill`` straight-preferring tie-break.
    Pass ``heading=None`` for the original direction-agnostic behaviour.
    """
    if start not in distances:
        raise ValueError(f"Start cell {start} is unreachable from the goal.")
    path = [start]
    current = start
    guard = 0
    limit = len(distances) + 1
    while distances[current] != 0:
        neighbours = cell_neighbours(current, walls)
        # Accessible neighbours closest to the goal (the descent candidates).
        best = min(distances.get(c, 1 << 30) for c in neighbours)
        candidates = [c for c in neighbours if distances.get(c, 1 << 30) == best]
        # Prefer to keep going straight to cut turns; else take the first candidate.
        nxt = None
        if heading is not None:
            straight = (current[0] + heading[0], current[1] + heading[1])
            if straight in candidates:
                nxt = straight
        if nxt is None:
            nxt = candidates[0]
        heading = (nxt[0] - current[0], nxt[1] - current[1])
        current = nxt
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


def get_path(
    walls: Walls,
    start: Cell,
    goal_cells: list[Cell],
    heading: tuple[int, int] | None = None,
) -> list[Cell]:
    """Convenience: flood from the goal, then descend from `start`. The default
    path source used by the environment. Pass ``heading`` (dx, dy) to prefer
    continuing straight on ties (fewer turns)."""
    distances = compute_distances(walls, goal_cells)
    return extract_path(distances, walls, start, heading)


# ---------------------------------------------------------------------------
# Partial-knowledge exploration
# ---------------------------------------------------------------------------
# Everything above plans over a *known* maze. The pieces below let a mouse
# DISCOVER an unknown one: a belief map that grows as walls are sensed, and an
# Explorer that floods that belief and decides each step. They are fully
# backend-agnostic (only cells, compass sides and headings -- never sensors or
# motors), so the mms simulator, the micromouse env and the real robot can all
# share this single implementation, each supplying its own sensing and movement.

# Compass model, matching the wall-flag order above: N=+y, E=+x, S=-y, W=-x.
DIRECTIONS: tuple[str, ...] = ("n", "e", "s", "w")
DELTA: dict[str, Cell] = {"n": (0, 1), "e": (1, 0), "s": (0, -1), "w": (-1, 0)}
_SIDE_INDEX = {"n": 0, "e": 1, "s": 2, "w": 3}
_DELTA_TO_SIDE = {v: k for k, v in DELTA.items()}
_RELATIVE = {"front": 0, "right": 1, "back": 2, "left": 3}   # clockwise from heading


def opposite(side: str) -> str:
    """The compass side facing the other way ('n'<->'s', 'e'<->'w')."""
    dx, dy = DELTA[side]
    return _DELTA_TO_SIDE[(-dx, -dy)]


def absolute_side(heading: str, relative: str) -> str:
    """Map a heading-relative sensor ('front'/'right'/'back'/'left') to an
    absolute compass side, given the current `heading`. Useful to any robot
    whose wall sensors are relative to where it is facing."""
    return DIRECTIONS[(DIRECTIONS.index(heading) + _RELATIVE[relative]) % 4]


def step_side(cell_from: Cell, cell_to: Cell) -> str:
    """The compass side you exit `cell_from` through to reach an adjacent cell."""
    return _DELTA_TO_SIDE[(cell_to[0] - cell_from[0], cell_to[1] - cell_from[1])]


def new_belief(width: int, height: int) -> Walls:
    """A belief map as a walls dict: only the outer boundary is known, every
    interior edge assumed open until sensed. Values are mutable lists so walls
    can be added in place as they are discovered."""
    belief: Walls = {}
    for x in range(width):
        for y in range(height):
            belief[(x, y)] = [y == height - 1, x == width - 1, y == 0, x == 0]
    return belief


def mark_wall(belief: Walls, cell: Cell, side: str) -> None:
    """Record a wall on `side` of `cell`, mirrored onto the neighbour."""
    belief[cell][_SIDE_INDEX[side]] = True
    dx, dy = DELTA[side]
    neighbour = (cell[0] + dx, cell[1] + dy)
    if neighbour in belief:
        belief[neighbour][_SIDE_INDEX[opposite(side)]] = True


class Explorer:
    """A partial-knowledge flood-fill explorer shared by every backend.

    It owns the belief map and all the flood-fill decisions. A backend only has
    to (1) hand it the walls it senses at each cell via :meth:`observe`, (2) ask
    :meth:`next_cell` where to go, and (3) carry out the move. A typical loop::

        ex = Explorer(width, height)
        pos, heading = (0, 0), (0, 1)
        while not ex.at_goal(pos):
            ex.observe(pos, sensed_wall_sides)   # absolute sides, e.g. ["n", "e"]
            ex.flood()
            nxt = ex.next_cell(pos, heading)
            heading = (nxt[0] - pos[0], nxt[1] - pos[1])
            backend_drive_to(nxt)                # backend turns + moves
            pos = nxt
        route = ex.verified_route((0, 0))        # speed-run over confirmed cells
    """

    def __init__(self, width: int, height: int, goal: list[Cell] | None = None):
        self.width = width
        self.height = height
        self.belief: Walls = new_belief(width, height)
        self.known: set[Cell] = set()
        self.distances: dict[Cell, int] = {}
        if goal is None:
            goal = [g for g in default_goal(width, height) if g in self.belief]
        self.goal = goal

    def observe(self, cell: Cell, wall_sides: list[str]) -> None:
        """Fold sensed walls (absolute compass sides) into the belief and mark
        `cell` fully known: after sensing here all four of its edges are
        verified (a side not in `wall_sides` is confirmed open)."""
        for side in wall_sides:
            mark_wall(self.belief, cell, side)
        self.known.add(cell)

    def flood(self) -> dict[Cell, int]:
        """Recompute and cache distance-to-goal over the current belief."""
        self.distances = compute_distances(self.belief, self.goal)
        return self.distances

    def at_goal(self, cell: Cell) -> bool:
        return cell in self.goal

    def next_cell(self, cell: Cell, heading: Cell | None = None) -> Cell | None:
        """The next cell to step to from `cell`, or None if already at the goal.
        Reuses :func:`extract_path` so ties keep the mouse going straight. Call
        :meth:`flood` first (the loop above does); re-floods defensively if not."""
        if cell in self.goal:
            return None
        if cell not in self.distances:
            self.flood()
        path = extract_path(self.distances, self.belief, cell, heading)
        return path[1] if len(path) > 1 else None

    def verified_route(self, start: Cell, heading: Cell | None = None) -> list[Cell]:
        """Shortest route from `start` to the goal through cells actually sensed.
        Unknown cells are absent from the map, so every unverified edge is sealed
        and the route only uses confirmed-open corridors."""
        known_walls = {c: self.belief[c] for c in self.known}
        known_goal = [g for g in self.goal if g in known_walls]
        return get_path(known_walls, start, known_goal, heading)
