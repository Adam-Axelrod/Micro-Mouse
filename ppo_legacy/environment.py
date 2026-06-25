"""Training-facing environment: Gym-style ``reset()`` / ``step()``, fixed timestep.

This is the contract the (future) model layer plugs into. It needs only
``reset()``, ``step(action)``, ``action_space`` and ``observation_space``.

No pygame and NO clock here: ``step()`` always advances physics by
``config.FIXED_DT`` regardless of wall-clock time, so training runs as fast as
the CPU allows. Rendering is a separate, optional consumer (see ``render``).

The observation vector and reward are PROVISIONAL placeholders (clearly marked):
they return sensible values so the loop works end-to-end, but their exact form
is intended to be finalised together with the policy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


import numpy as np

from . import config
from .maze import Maze
from .maze_loader import load_maze
from .mouse import MouseState

Cell = tuple[int, int]
@dataclass
class Space:
    """Minimal description of a vector space (avoids a gym dependency for now)."""
    shape: tuple[int, ...]
    low: float
    high: float

def _wrap_angle(a: float) -> float:
    """Wrap an angle to (-pi, pi]."""
    return (a + math.pi) % (2 * math.pi) - math.pi


class MazeMouseEnv:
    def __init__(self, maze_file=None, start_cell: Cell = (0, 0), seed=None, path=None):
        if seed is not None:
            np.random.seed(seed)

        walls, width, height = load_maze(maze_file or config.DEFAULT_MAZE)
        self.maze = Maze(walls, width, height)
        self.start_cell = start_cell

        # --- PATH SOURCE (swap-in seam) --------------------------------------
        # Default: live flood fill. To hardcode, pass path=[(x, y), ...].
        if path is not None:
            self.maze.set_path(path)
        else:
            self.maze.compute_path(start_cell)
        # ---------------------------------------------------------------------

        start_world = self.maze.cell_to_world(start_cell)
        self.mouse = MouseState(start_world, heading=-math.pi / 2)   # face "up"

        self.steps = 0
        self._prev_progress = 0.0
        self._wp_idx = 0          # index of the waypoint currently being targeted
        self._wp_advanced = 0     # how many waypoints were reached in the last step

        # Spaces: 2 continuous actions; obs = rays + [sin dθ, cos dθ, dist, speed].
        self.action_space = Space((2,), -1.0, 1.0)
        self.observation_space = Space((config.NUM_RAYS + 4,), -1.0, 1.0)

        self._renderer = None

    # ----- core API ----------------------------------------------------------
    def reset(self) -> np.ndarray:
        self.mouse.reset(
            self.maze.cell_to_world(self.start_cell),
            heading=-math.pi / 2,
            jitter=config.START_JITTER,
        )
        self.steps = 0
        # Aim at the first waypoint after the start (index 0 is the start cell).
        self._wp_idx = min(1, len(self.maze.waypoints) - 1)
        self._wp_advanced = 0
        self._prev_progress = self._progress()
        return self._get_obs()

    def step(self, action):
        self.mouse.step(action, config.FIXED_DT, self.maze.segments)   # no clock
        self.steps += 1
        wp_before = self._wp_idx
        self._advance_waypoint()
        self._wp_advanced = self._wp_idx - wp_before
        reward, done = self._compute_reward()
        info = {"collided": self.mouse.collided, "steps": self.steps}
        return self._get_obs(), reward, done, info

    # ----- observation (PROVISIONAL: finalise with the policy) ---------------
    def _get_obs(self) -> np.ndarray:
        rays = self.mouse.sense(self.maze.segments)
        tx, ty = self._target_world()
        dx, dy = tx - self.mouse.x, ty - self.mouse.y
        dtheta = _wrap_angle(math.atan2(dy, dx) - self.mouse.heading)
        dist = min(1.0, math.hypot(dx, dy) / (5 * config.TILE_SIZE))
        speed_norm = self.mouse.speed / config.MAX_SPEED
        extra = np.array(
            [math.sin(dtheta), math.cos(dtheta), dist, speed_norm], dtype=np.float32
        )
        return np.concatenate([rays, extra])

    # ----- reward (PROVISIONAL: finalise with the policy) --------------------
    def _compute_reward(self):
        progress = self._progress()
        reward = (progress - self._prev_progress) * config.REWARD_PROGRESS  # path progress
        reward += config.REWARD_WAYPOINT * self._wp_advanced                # waypoint milestones
        reward += config.REWARD_HEADING * self._heading_alignment()         # move toward target
        reward -= config.REWARD_TIME                                        # time penalty
        if self.mouse.collided:
            reward -= config.REWARD_COLLISION                              # discourage walls
        self._prev_progress = progress

        done = False
        if self.maze.is_goal((self.mouse.x, self.mouse.y)):
            reward += config.REWARD_GOAL
            done = True
        elif self.steps >= config.MAX_EPISODE_STEPS:
            done = True
        return reward, done

    # ----- helpers -----------------------------------------------------------
    def _advance_waypoint(self) -> None:
        """Step the target index forward as the mouse reaches each waypoint."""
        wps = self.maze.waypoints
        while self._wp_idx < len(wps) - 1:
            tx, ty = self.maze.cell_to_world(wps[self._wp_idx])
            if math.hypot(self.mouse.x - tx, self.mouse.y - ty) <= config.WAYPOINT_RADIUS:
                self._wp_idx += 1
            else:
                break

    def _target_world(self) -> tuple[float, float]:
        """The NEXT waypoint to steer toward (not the final goal)."""
        wps = self.maze.waypoints
        if not wps:
            return self.mouse.x, self.mouse.y
        idx = min(self._wp_idx, len(wps) - 1)
        return self.maze.cell_to_world(wps[idx])

    def _heading_alignment(self) -> float:
        """Normalised speed projected onto the direction of the next waypoint.

        +1 when driving straight at the target at full speed, negative when
        moving away. Gives a dense per-step signal so the policy gets gradient
        everywhere, not only when it happens to reach the sparse goal.
        """
        tx, ty = self._target_world()
        dx, dy = tx - self.mouse.x, ty - self.mouse.y
        heading_err = _wrap_angle(math.atan2(dy, dx) - self.mouse.heading)
        return math.cos(heading_err) * (self.mouse.speed / config.MAX_SPEED)

    def _progress(self) -> float:
        """Fraction (0..1) of the path's arc-length the mouse has reached.

        Projects the mouse onto the nearest point of the polyline path and
        returns the arc-length up to that point, divided by the total length.
        """
        pts = [self.maze.cell_to_world(c) for c in self.maze.path]
        if len(pts) < 2:
            return 0.0
        px, py = self.mouse.x, self.mouse.y
        best_d2 = float("inf")
        best_len = 0.0
        cumulative = 0.0
        total = 0.0
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            seg_len = math.hypot(x2 - x1, y2 - y1)
            if seg_len > 1e-9:
                t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / (seg_len * seg_len)
                t = max(0.0, min(1.0, t))
            else:
                t = 0.0
            proj_x, proj_y = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
            d2 = (px - proj_x) ** 2 + (py - proj_y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_len = cumulative + t * seg_len
            cumulative += seg_len
            total += seg_len
        return best_len / total if total > 0 else 0.0

    # ----- rendering (the only path that imports pygame) ---------------------
    def render(self) -> None:
        if self._renderer is None:
            from .renderer import Renderer   # lazy import keeps pygame out of training
            self._renderer = Renderer(self.maze)
        self._renderer.draw(self.mouse, path=self.maze.path, rays=self._ray_endpoints())

    def _ray_endpoints(self):
        """World-space endpoints of each ray, for visualisation only."""
        readings = self.mouse.sense(self.maze.segments)
        ends = []
        for angle, r in zip(self.mouse.ray_angles(), readings):
            dist = float(r) * config.RAY_MAX_DIST
            ends.append((float(self.mouse.x + math.cos(angle) * dist),
                         float(self.mouse.y + math.sin(angle) * dist)))
        return ends

    def close(self) -> None:
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None
