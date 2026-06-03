"""The PPO update: turn one rollout into a gradient step on the policy.

Given the stored transitions plus their computed returns/advantages, we do a few
epochs of minibatch SGD on the clipped surrogate objective:

    ratio   = exp(new_logprob - old_logprob)        # how much the policy changed
    loss_pi = -min(ratio * A, clip(ratio, 1-e, 1+e) * A)

The clip stops any single update from moving the policy too far. We add a value
loss (so the critic tracks the returns) and subtract an entropy bonus (so the
policy keeps some exploration).
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn


def ppo_update(policy, optimizer, buffer, returns, advantages, cfg) -> dict:
    # Move the stored rollout into tensors once.
    obs = torch.as_tensor(buffer.obs)
    actions = torch.as_tensor(buffer.actions)
    old_logprobs = torch.as_tensor(buffer.logprobs)
    returns_t = torch.as_tensor(returns)
    adv_t = torch.as_tensor(advantages)

    # Normalising advantages keeps the gradient scale stable across updates.
    adv_t = (adv_t - adv_t.mean()) / (adv_t.std() + 1e-8)

    n = buffer.size
    indices = np.arange(n)
    policy_loss = value_loss = entropy = torch.tensor(0.0)

    for _ in range(cfg.PPO_EPOCHS):
        np.random.shuffle(indices)
        for start in range(0, n, cfg.PPO_MINIBATCH):
            mb = indices[start:start + cfg.PPO_MINIBATCH]

            new_logprob, entropy, value = policy.evaluate(obs[mb], actions[mb])
            ratio = torch.exp(new_logprob - old_logprobs[mb])

            # Clipped surrogate (policy) loss.
            surr1 = ratio * adv_t[mb]
            surr2 = torch.clamp(ratio, 1 - cfg.PPO_CLIP, 1 + cfg.PPO_CLIP) * adv_t[mb]
            policy_loss = -torch.min(surr1, surr2).mean()

            # Critic regression toward the returns.
            value_loss = ((value - returns_t[mb]) ** 2).mean()

            entropy = entropy.mean()
            loss = (policy_loss
                    + cfg.PPO_VALUE_COEF * value_loss
                    - cfg.PPO_ENTROPY_COEF * entropy)

            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(policy.parameters(), cfg.PPO_MAX_GRAD_NORM)
            optimizer.step()

    return {
        "policy_loss": policy_loss.detach().item(),
        "value_loss": value_loss.detach().item(),
        "entropy": entropy.detach().item(),
    }
