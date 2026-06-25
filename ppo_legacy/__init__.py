"""Micro-Mouse simulation package.

Pure-math, clock-decoupled environment for training a 2D maze-following mouse.
pygame is used only for optional rendering (see ``renderer``).
"""
from __future__ import annotations

from .environment import MazeMouseEnv
from .maze import Maze
from .maze_loader import load_maze
from .mouse import MouseState

__all__ = ["MazeMouseEnv", "Maze", "MouseState", "load_maze"]
