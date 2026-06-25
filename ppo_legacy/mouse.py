"""The dynamic agent: physics state, fixed-dt integration and ray sensors.

Pure math, no pygame. The action is continuous-native: ``[turn_rate, accel]``,
each in ``[-1, 1]``. A discrete policy can drive this same interface later via a
small lookup table, with no change here.
"""
from __future__ import annotations

import math

import numpy as np

from . import config
from .geometry import Segment, cast_ray, resolve_circle_collision

Point = tuple[float, float]


class MouseState:
    def __init__(self, start_pos: Point, heading: float = 0.0):
        self.start_pos = start_pos
        self.start_heading = heading
        self.reset(start_pos, heading)

    def reset(self, pos: Point, heading: float = 0.0, jitter: float = 0.0) -> None:
        x, y = pos
        if jitter:
            x += float(np.random.uniform(-jitter, jitter))
            y += float(np.random.uniform(-jitter, jitter))
        self.x = x
        self.y = y
        self.heading = heading      # radians; 0 = +x (screen right)
        self.speed = 0.0            # px / s
        self.collided = False

    def step(self, action, dt: float, segments: list[Segment]) -> None:
        """Advance one fixed timestep. ``action = (turn_rate, accel)`` in [-1, 1]."""
        turn_rate = float(np.clip(action[0], -1.0, 1.0))
        accel = float(np.clip(action[1], -1.0, 1.0))

        # --- rotation (rate * dt, so framerate-independent) ---
        self.heading += turn_rate * config.MAX_TURN_RATE * dt

        # --- speed: throttle then friction, both per-second ---
        self.speed += accel * config.ACCEL * dt
        self.speed *= config.FRICTION ** dt
        low = -config.MAX_SPEED if config.ALLOW_REVERSE else 0.0
        self.speed = float(np.clip(self.speed, low, config.MAX_SPEED))

        # --- integrate position ---
        self.x += self.speed * math.cos(self.heading) * dt
        self.y += self.speed * math.sin(self.heading) * dt

        # --- collide with walls (pure-math circle vs segments) ---
        (self.x, self.y), self.collided = resolve_circle_collision(
            (self.x, self.y), config.MOUSE_RADIUS, segments
        )
        if self.collided:
            self.speed *= 0.5       # bleed speed on contact

    def ray_angles(self) -> list[float]:
        """Absolute angles of each sensor ray, fanned across RAY_FOV around heading."""
        if config.NUM_RAYS == 1:
            return [self.heading]
        start = self.heading - config.RAY_FOV / 2
        step = config.RAY_FOV / (config.NUM_RAYS - 1)
        return [start + i * step for i in range(config.NUM_RAYS)]

    def sense(self, segments: list[Segment]) -> np.ndarray:
        """NUM_RAYS normalised wall distances (0..1) for the current pose."""
        readings = np.empty(config.NUM_RAYS, dtype=np.float32)
        for i, angle in enumerate(self.ray_angles()):
            readings[i] = cast_ray((self.x, self.y), angle, segments, config.RAY_MAX_DIST)
        return readings

    @property
    def pose(self) -> tuple[float, float, float]:
        return self.x, self.y, self.heading
