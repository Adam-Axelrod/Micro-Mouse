"""Watch / evaluate a trained PPO policy.

    python -m micromouse.eval                      # render the greedy policy
    python -m micromouse.eval --episodes 10 --no-render   # quick stats, no window

Loads ``model/ppo_policy.pth`` and acts greedily (the distribution mean, no
sampling), reporting whether the mouse reaches the goal and how long it takes.
"""
from __future__ import annotations

import argparse

import torch

from . import config
from .environment import MazeMouseEnv
from .policy import ActorCritic


def load_policy(env: MazeMouseEnv) -> ActorCritic:
    policy = ActorCritic(
        env.observation_space.shape[0], env.action_space.shape[0], config.HIDDEN_SIZE
    )
    path = config.CHECKPOINT_DIR / "ppo_policy.pth"
    policy.load_state_dict(torch.load(path, map_location="cpu"))
    policy.eval()
    return policy


def run_episode(env: MazeMouseEnv, policy: ActorCritic, render: bool = True):
    obs = env.reset()
    total = 0.0
    reached = False
    for _ in range(config.MAX_EPISODE_STEPS):
        obs_t = torch.as_tensor(obs, dtype=torch.float32)
        action = policy.mean_action(obs_t).numpy()   # greedy: no exploration noise
        obs, reward, done, _ = env.step(action)
        total += reward
        if render:
            env.render()
        if done:
            reached = env.maze.is_goal((env.mouse.x, env.mouse.y))
            break
    return total, reached, env.steps


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trained Micro-Mouse policy")
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--no-render", action="store_true", help="run headless, just print stats")
    parser.add_argument("--maze", type=str, default=None,
                        help="maze file to test on (name under mazes/example_mazes/ or a full path); "
                             "defaults to the training maze. Use this to check generalisation.")
    args = parser.parse_args()

    maze_file = None
    if args.maze:
        candidate = config.MAZES_DIR / args.maze
        maze_file = candidate if candidate.exists() else args.maze

    env = MazeMouseEnv(maze_file=maze_file)
    policy = load_policy(env)

    solved = 0
    for i in range(args.episodes):
        total, reached, steps = run_episode(env, policy, render=not args.no_render)
        solved += int(reached)
        print(f"episode {i + 1}: return {total:7.2f}  steps {steps}  reached_goal {reached}")
    if args.episodes > 1:
        print(f"solved {solved}/{args.episodes}")
    env.close()


if __name__ == "__main__":
    main()
