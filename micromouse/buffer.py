"""Rollout storage and Generalised Advantage Estimation (GAE).

Deliberately pure NumPy (no torch) so the advantage maths is easy to read and to
test on its own. Only the network and the optimisation step use torch.

One rollout = a fixed number of consecutive environment transitions. After it is
full we turn the raw rewards/values into "returns" (what the critic should have
predicted) and "advantages" (how much better an action was than expected), which
are what PPO actually optimises against.
"""
from __future__ import annotations

import numpy as np


class RolloutBuffer:
    def __init__(self, size: int, obs_dim: int, act_dim: int):
        self.size = size
        self.obs = np.zeros((size, obs_dim), dtype=np.float32)
        self.actions = np.zeros((size, act_dim), dtype=np.float32)
        self.logprobs = np.zeros(size, dtype=np.float32)   # log prob of each action when taken
        self.rewards = np.zeros(size, dtype=np.float32)
        self.values = np.zeros(size, dtype=np.float32)     # critic's estimate at each obs
        self.dones = np.zeros(size, dtype=np.float32)      # 1.0 if the episode ended here
        self.ptr = 0

    def reset(self) -> None:
        self.ptr = 0

    def is_full(self) -> bool:
        return self.ptr >= self.size

    def add(self, obs, action, logprob, reward, value, done) -> None:
        i = self.ptr
        self.obs[i] = obs
        self.actions[i] = action
        self.logprobs[i] = logprob
        self.rewards[i] = reward
        self.values[i] = value
        self.dones[i] = float(done)
        self.ptr += 1

    def compute_gae(self, last_value: float, gamma: float, lam: float):
        """Return ``(returns, advantages)`` for the stored rollout.

        ``last_value`` bootstraps the tail: it is the critic's value of the state
        that comes immediately after the final stored step. Walking backwards, the
        per-step TD error is ``delta = r + gamma * V(next) - V(now)`` and GAE
        accumulates these with a decay of ``gamma * lam``. A ``done`` flag zeroes
        both the bootstrap and the accumulation so episodes don't bleed together.
        """
        advantages = np.zeros(self.size, dtype=np.float32)
        last_gae = 0.0
        for t in reversed(range(self.size)):
            next_value = last_value if t == self.size - 1 else self.values[t + 1]
            next_nonterminal = 1.0 - self.dones[t]
            delta = self.rewards[t] + gamma * next_value * next_nonterminal - self.values[t]
            last_gae = delta + gamma * lam * next_nonterminal * last_gae
            advantages[t] = last_gae
        returns = advantages + self.values
        return returns, advantages
