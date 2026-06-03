"""Parse `.num` maze tables into wall data.

`.num` format: one line per cell, `x y N E S W`, where N/E/S/W are 0/1 wall flags.
No GUI lives in the import path so headless training never pulls in tkinter.
"""
from __future__ import annotations

from pathlib import Path

# A cell's walls as (north, east, south, west) booleans.
Walls = dict[tuple[int, int], tuple[bool, bool, bool, bool]]


def load_maze(filename: str | Path) -> tuple[Walls, int, int]:
    """Read a `.num` file into a walls dict plus grid size.

    Returns ``(walls, width, height)`` where width/height are cell counts.
    """
    walls: Walls = {}
    max_x = max_y = 0
    with open(filename, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            x, y, n, e, s, w = (int(v) for v in line.split())
            walls[(x, y)] = (bool(n), bool(e), bool(s), bool(w))
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    return walls, max_x + 1, max_y + 1


def available_mazes(mazes_dir: str | Path) -> list[Path]:
    """List all `.num` maze files in a directory, sorted by name."""
    return sorted(Path(mazes_dir).glob("*.num"))
