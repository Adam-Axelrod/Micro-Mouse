"""Entry point for sanity-checking the environment (no manual control yet).

    python -m micromouse.run                 # headless benchmark (default)
    python -m micromouse.run --benchmark 50000
    python -m micromouse.run --render        # watch a random policy in pygame

Both modes drive with a simple random policy so we can confirm physics,
collision, sensors, the flood-fill path, and the clock-decoupling all work
before any learning code exists.
"""
from __future__ import annotations

import argparse
import time

import numpy as np

from . import config
from .environment import MazeMouseEnv


def random_action() -> np.ndarray:
    """Random steer in [-1, 1], throttle in [0, 1]."""
    return np.array([np.random.uniform(-1, 1), np.random.uniform(0, 1)], dtype=np.float32)


def benchmark(steps: int) -> None:
    env = MazeMouseEnv()
    obs = env.reset()
    print(f"maze: {env.maze.width}x{env.maze.height} cells, "
          f"{len(env.maze.segments)} wall segments")
    print(f"flood-fill path: {len(env.maze.path)} cells, "
          f"{len(env.maze.waypoints)} turn waypoints")
    print(f"obs dim: {obs.shape[0]}, action dim: {env.action_space.shape[0]}")

    start = time.perf_counter()
    episodes = 0
    for _ in range(steps):
        _, _, done, _ = env.step(random_action())
        if done:
            env.reset()
            episodes += 1
    elapsed = time.perf_counter() - start

    rate = steps / elapsed if elapsed > 0 else float("inf")
    print(f"\n{steps:,} steps in {elapsed:.2f}s  ->  {rate:,.0f} steps/s")
    print(f"episodes completed: {episodes}")
    print(f"(real-time at {1/config.FIXED_DT:.0f} FPS would be "
          f"{steps * config.FIXED_DT:.0f}s -> "
          f"~{rate * config.FIXED_DT:.0f}x faster than real time)")


def render_run(steps: int) -> None:
    env = MazeMouseEnv()
    env.reset()
    for _ in range(steps):
        _, _, done, _ = env.step(random_action())
        env.render()
        if done:
            env.reset()
    env.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Micro-Mouse environment harness")
    parser.add_argument("--benchmark", type=int, nargs="?", const=100_000, default=None,
                        help="run N headless steps and report steps/sec")
    parser.add_argument("--render", action="store_true", help="watch a random policy")
    parser.add_argument("--steps", type=int, default=3000, help="steps for --render")
    args = parser.parse_args()

    if args.render:
        render_run(args.steps)
    else:
        benchmark(args.benchmark or 100_000)


if __name__ == "__main__":
    main()
