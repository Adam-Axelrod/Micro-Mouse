"""Actor-critic network for continuous PPO (PyTorch).

The **actor** maps an observation to the *mean* of a Gaussian over the two
continuous actions ``[turn_rate, accel]``; a single learnable ``log_std`` gives
the spread. Sampling from that Gaussian is what lets nearby steering angles share
similar probability — the whole reason we moved off discrete Q-values.

The **critic** maps an observation to a single scalar value estimate.
"""
from __future__ import annotations

import torch
import torch.nn as nn
from torch.distributions import Normal

from . import config


def _mlp(in_dim: int, out_dim: int, hidden: int) -> nn.Sequential:
    """A small two-hidden-layer MLP with Tanh activations."""
    return nn.Sequential(
        nn.Linear(in_dim, hidden), nn.Tanh(),
        nn.Linear(hidden, hidden), nn.Tanh(),
        nn.Linear(hidden, out_dim),
    )


class ActorCritic(nn.Module):
    def __init__(self, obs_dim: int, act_dim: int, hidden: int = 64):
        super().__init__()
        self.actor_mean = _mlp(obs_dim, act_dim, hidden)
        self.critic = _mlp(obs_dim, 1, hidden)
        # State-independent log standard deviation (a common, stable choice).
        # Starting below 0 keeps early exploration calmer than std=1 (wild spinning).
        self.log_std = nn.Parameter(torch.full((act_dim,), float(config.INIT_LOG_STD)))

    def _distribution(self, obs: torch.Tensor) -> Normal:
        mean = self.actor_mean(obs)
        std = torch.exp(self.log_std)
        return Normal(mean, std)

    @torch.no_grad()
    def act(self, obs: torch.Tensor):
        """Sample an action while collecting a rollout.

        Returns ``(action, logprob, value)`` for a single observation. The action
        is unbounded here; the environment clips it to [-1, 1].
        """
        dist = self._distribution(obs)
        action = dist.sample()
        logprob = dist.log_prob(action).sum(-1)   # sum over action dims -> joint log prob
        value = self.critic(obs).squeeze(-1)
        return action, logprob, value

    @torch.no_grad()
    def mean_action(self, obs: torch.Tensor) -> torch.Tensor:
        """Greedy (deterministic) action for evaluation: the distribution mean."""
        return self.actor_mean(obs)

    def evaluate(self, obs: torch.Tensor, action: torch.Tensor):
        """Re-score stored transitions during the update.

        Returns ``(logprob, entropy, value)`` for a batch of obs/actions, with
        gradients enabled so PPO can backpropagate.
        """
        dist = self._distribution(obs)
        logprob = dist.log_prob(action).sum(-1)
        entropy = dist.entropy().sum(-1)
        value = self.critic(obs).squeeze(-1)
        return logprob, entropy, value
