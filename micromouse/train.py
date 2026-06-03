"""Continuous PPO training loop for the Micro-Mouse environment (single env).

Readable first: one environment, a NumPy rollout buffer, a small actor-critic and
a straightforward PPO update. Vectorising across many envs for speed is a later
step (kept out on purpose for now).

    python -m micromouse.train            # full run
    python -m micromouse.train --smoke    # tiny run to confirm the loop works
"""
from __future__ import annotations

import argparse

import numpy as np
import torch

from . import config
from .buffer import RolloutBuffer
from .environment import MazeMouseEnv
from .policy import ActorCritic
from .ppo import ppo_update


def train(total_timesteps: int, rollout_steps: int, smoke: bool = False) -> ActorCritic:
    env = MazeMouseEnv()
    obs_dim = env.observation_space.shape[0]
    act_dim = env.action_space.shape[0]

    policy = ActorCritic(obs_dim, act_dim, config.HIDDEN_SIZE)
    optimizer = torch.optim.Adam(policy.parameters(), lr=config.PPO_LR)
    buffer = RolloutBuffer(rollout_steps, obs_dim, act_dim)

    obs = env.reset()
    ep_return = 0.0
    completed_returns: list[float] = []

    updates = max(1, total_timesteps // rollout_steps)
    for update in range(1, updates + 1):
        buffer.reset()

        # --- 1. collect a rollout -------------------------------------------
        while not buffer.is_full():
            obs_t = torch.as_tensor(obs, dtype=torch.float32)
            action, logprob, value = policy.act(obs_t)

            next_obs, reward, done, _ = env.step(action.numpy())
            buffer.add(obs, action.numpy(), float(logprob), reward, float(value), done)

            obs = next_obs
            ep_return += reward
            if done:
                completed_returns.append(ep_return)
                ep_return = 0.0
                obs = env.reset()

        # --- 2. bootstrap value of the state after the last stored step ------
        with torch.no_grad():
            obs_t = torch.as_tensor(obs, dtype=torch.float32)
            last_value = float(policy.critic(obs_t).squeeze(-1))

        # --- 3. compute returns/advantages, then update ---------------------
        returns, advantages = buffer.compute_gae(
            last_value, config.PPO_GAMMA, config.PPO_GAE_LAMBDA
        )
        stats = ppo_update(policy, optimizer, buffer, returns, advantages, config)

        mean_ret = float(np.mean(completed_returns[-20:])) if completed_returns else float("nan")
        print(f"update {update}/{updates}  steps {update * rollout_steps:,}  "
              f"mean_return {mean_ret:7.2f}  "
              f"pi_loss {stats['policy_loss']:+.3f}  "
              f"v_loss {stats['value_loss']:.3f}  "
              f"entropy {stats['entropy']:+.3f}")

        if not smoke and update % 10 == 0:
            _save(policy)

    if not smoke:
        _save(policy)
    env.close()
    return policy


def _save(policy: ActorCritic) -> None:
    config.CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(policy.state_dict(), config.CHECKPOINT_DIR / "ppo_policy.pth")


def main() -> None:
    parser = argparse.ArgumentParser(description="PPO training for Micro-Mouse")
    parser.add_argument("--smoke", action="store_true",
                        help="tiny run (no checkpoints) to verify the loop end-to-end")
    args = parser.parse_args()

    if args.smoke:
        train(total_timesteps=1536, rollout_steps=512, smoke=True)
    else:
        train(config.TOTAL_TIMESTEPS, config.PPO_ROLLOUT_STEPS)


if __name__ == "__main__":
    main()
