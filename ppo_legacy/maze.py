"""The static world: wall geometry, the flood-fill path, and coordinate conversions.

All maze<->screen coordinate conversion (and the single y-flip) is centralised
here so the rest of the code never has to think about it.
"""
from __future__ import annotations

import math

from . import config, flood_fill
from .geometry import Segment, build_wall_segments
from .maze_loader import Walls

Cell = tuple[int, int]


class Maze:
    def __init__(self, walls: Walls, width: int, height: int, tile: float = config.TILE_SIZE):
        self.walls = walls
        self.width = width
        self.height = height
        self.tile = tile
        self.segments: list[Segment] = build_wall_segments(walls, tile, height)

        # Goal = the central cells that actually exist in this maze.
        self.goal: list[Cell] = [c for c in flood_fill.default_goal(width, height) if c in walls]
        self.path: list[Cell] = []
        self.waypoints: list[Cell] = []

    # ----- path planning (the swap-in seam) ----------------------------------
    def compute_path(self, start: Cell) -> list[Cell]:
        """Plan and cache the flood-fill path from `start` to the goal.

        SWAP-IN POINT: to use a hardcoded path, call ``set_path`` instead and
        skip this method. Downstream code only reads ``self.path`` /
        ``self.waypoints``.
        """
        path = flood_fill.get_path(self.walls, start, self.goal)
        self.set_path(path)
        return path

    def set_path(self, path: list[Cell]) -> None:
        """Install a path (from flood fill or hardcoded) and derive its turns."""
        self.path = list(path)
        self.waypoints = flood_fill.generate_turns(self.path)

    # ----- coordinate conversions (all y-flips live here) --------------------
    def cell_to_world(self, cell: Cell) -> tuple[float, float]:
        """Centre of a maze cell in screen pixels."""
        x, y = cell
        px = (x + 0.5) * self.tile
        py = (self.height - 1 - y + 0.5) * self.tile   # flip y once
        return px, py

    def world_to_cell(self, pos: tuple[float, float]) -> Cell:
        """Maze cell containing a screen-pixel position."""
        px, py = pos
        x = int(px // self.tile)
        y = self.height - 1 - int(py // self.tile)
        return x, y

    def is_goal(self, pos: tuple[float, float], tol: float | None = None) -> bool:
        """True if `pos` is within `tol` px of any goal-cell centre.

        Uses a distance threshold (not float equality) so the goal actually fires.
        """
        tol = self.tile * 0.4 if tol is None else tol
        for g in self.goal:
            gx, gy = self.cell_to_world(g)
            if math.hypot(pos[0] - gx, pos[1] - gy) <= tol:
                return True
        return False

    @property
    def pixel_size(self) -> tuple[int, int]:
        return int(self.width * self.tile), int(self.height * self.tile)
