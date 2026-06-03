# Maze Mouse — Rewrite Plan (PPO, decoupled env)

Status: draft for discussion. Nothing here is final; push back on anything.

---

## 1. Decisions (and the reasoning)

### Can PPO and the evolutionary (Code Bullet) approach be combined?
Not in the way it sounds, and you don't want to. They're two different paradigms:

- **Neuroevolution (Code Bullet):** no gradients. Spawn a population, score each network by fitness, keep/mutate the best. Simple, robust, but sample-inefficient and scales badly as the network grows.
- **PPO:** gradient-based. One policy network, updated by backprop from collected experience.

The "swarm of agents learning at once" look from the Code Bullet video does **not** require evolution. You get the same visual with **vectorised PPO**: run N copies of the environment in parallel, all controlled by the *same* policy, pool their experience into one PPO update. Many agents on screen, one brain improving. That scratches the same itch and is the correct engineering choice.

Real hybrids exist (Population-Based Training, CEM-RL, ES) but they're advanced and not worth it here.

### Paradigm: **PPO** (recommended)
You asked me to help decide, then said focus on PPO — agreed, and here's why it's the right call for *your* goals specifically:
- Your end target is a real continuous-control robot (UKMARS Gemini). PPO with a continuous action head is the standard for sim-to-real; neuroevolution is not.
- It directly fixes your core problem (see §2): a stochastic policy generalises smoothly over nearby states/actions, so "a couple pixels left" no longer needs a totally different action.
- It's the more valuable thing to learn.

Neuroevolution would be a faster "it works!" moment, but it's a detour from where you're headed.

### Build style: **minimal PPO from scratch**, in PyTorch
This is a learning project and the algorithm is the part worth understanding. A clean PPO is ~150–200 lines. The *environment* is the bigger engineering job either way. Fallback if it stalls: drop in Stable-Baselines3 (`PPO("MlpPolicy", env)`) behind the same env interface — which is exactly why we make the env a standard interface (§3).

---

## 2. What's wrong with the current approach (root causes)

The algorithm is the wrong tool, but the bigger problem is **state/reward design and several outright bugs**. Top issues found in the code:

1. **Value-based + discrete actions on a continuous problem.** `Linear_QNet(16,512,4)` picks one of `[forward, back, left, right]` by argmax. No smooth generalisation — your exact diagnosis.
2. **The goal is essentially never reached.** `if (agent.pos_x, agent.pos_y) == agent.goal` compares float pixel coords to a grid-tuple. This is almost always False, so the `+50` win reward basically never fires. The agent has had no real "success" signal.
3. **Two desynced path systems.** `self.waypoints` (only *turns*, used in the observation) vs `maze.reward_gates` (every *tile*, used for reward). The agent is shown distance to the next turns but rewarded for hitting per-tile gates — observation and reward disagree.
4. **No target network, and the TD target isn't detached.** `Q_new = reward + gamma * max(self.model(next_state))` is computed from the same live network *with gradients on*, so you backprop through the bootstrap target. Classic source of DQN instability.
5. **Permanent heavy exploration.** `epsilon = max(15, 100 - n_games*0.125)` floors at 15% random forever, *plus* Gaussian noise added to Q-values during exploitation. The policy can never settle.
6. **Dropout in the value net, never set to eval.** `nn.Dropout(0.2)` makes Q-values stochastic at decision time — noise on top of noise.
7. **Collision penalty commented out, episodes don't end on collision.** The agent can grind along walls for free.
8. **Training is locked to the pygame clock.** `dt = clock.tick(60)/1000` caps the sim at 60 FPS / real time. This is the speed problem you want gone.
9. **Single hardcoded path / single maze.** `path` is a fixed list in `path_calcs.py`; training always loads `example4.num`. It can only ever overfit one route (flood fill isn't computed live in the training loop).

Net effect: a noisy value estimator, a contradictory reward signal, a goal it can't reach, and real-time-capped training. "A few tiles after many generations" is consistent with all of that.

---

## 3. Target architecture

Clean separation so the learning code never imports pygame, and any algorithm can plug in:

```
maze_mouse/
  env/
    maze.py          # maze load + live flood fill + path/waypoints
    mouse.py         # physics: position, heading, speed, collision (no pygame draw)
    sim.py           # Gym-style env: reset() / step(action) -> (obs, reward, done, info)
    vec.py           # run N sims in parallel (the "swarm")
  render/
    renderer.py      # ALL pygame draw calls; optional, toggled by a flag
  model/
    network.py       # actor-critic MLP
    ppo.py           # PPO update (GAE, clipping, entropy)
  train.py           # training loop, logging, checkpoints
  infer.py           # load checkpoint, run + render one agent
  config.py          # every hyperparameter, no magic numbers
```

Key rule: **`env/` has zero pygame dependency.** Pygame lives only in `render/`. This is what makes headless training fast and the later 3D swap clean.

### The env interface (the important boundary)
```python
class MazeMouseEnv:
    def reset(self) -> obs: ...
    def step(self, action) -> (obs, reward, done, info): ...
```
Fixed timestep, e.g. `DT = 1/60`, passed to physics directly. **No `clock.tick()` anywhere in the env.** Training calls `step()` in a tight loop as fast as the CPU allows; rendering is a separate, optional consumer. This alone is your biggest speedup.

---

## 4. State representation (egocentric — the real fix)

Everything relative to the agent, so the same situation looks the same anywhere in the maze. Reuse your existing `cast_ray` (it's fine), but drop absolute coordinates entirely.

Proposed observation vector:
- **N raycasts** (e.g. 7), distances normalised 0–1, cast *relative to heading* (you already do this).
- **Heading error** to the next waypoint: `sin(Δ)`, `cos(Δ)` (two values — avoids the wraparound discontinuity that a single normalised angle has).
- **Distance** to the next waypoint (normalised).
- Optionally heading error + distance to the *second* waypoint (lookahead for cornering).
- **Current speed** (normalised).

That's ~13 inputs, all position-invariant. Note the fix vs current code: feed *heading error*, not relative x/y in mixed coordinate frames.

---

## 5. Action space

**The env is continuous-native. Action type is a property of the policy head, not the env.** Build `step()` to accept continuous control only:

```python
action = [turn_rate, acceleration]   # floats, each clipped to a fixed range
```

This matches the physics (angle/speed are already floats) and is the PPO target. A discrete policy, if used for early debugging, maps onto the *same* continuous interface via a thin adapter — no env change:

```python
DISCRETE = {0:[0.0, 1.0], 1:[-0.5, 1.0], 2:[0.5, 1.0], 3:[-1.0, 0.5], 4:[1.0, 0.5]}
# straight, soft-left, soft-right, hard-left, hard-right
```

- **(A) Continuous (target):** Gaussian over `[turn_rate, acceleration]`. Actor outputs mean ± std per dim, so nearby steering values get similar probability — Adam's point exactly. Watch for std collapse/explosion and clipping skew.
- **(B) Discrete adapter (optional, debugging):** categorical over the table above. Cheap way to verify env + reward are correct before tuning the continuous policy.

Recommendation: build the continuous env once. Optionally start learning with the **(B)** adapter to isolate env bugs from PPO-tuning bugs, then swap the head to **(A)** — only `network.py`/policy changes, env untouched.

---

## 6. Reward design

Replace the contradictory gate/waypoint mix with a single **progress-along-path** signal:

- **Progress reward:** project the agent's position onto the flood-fill path and reward the *increase* in arc-length covered each step. Dense, smooth, and impossible to game by circling. This is the main driver.
- **Time penalty:** small constant per step (e.g. `-0.01`) to discourage dawdling.
- **Collision:** real penalty and **terminate the episode** (uncomment + commit to it). Without termination there's no pressure to avoid walls.
- **Goal bonus:** large `+1`-scale reward on reaching the final waypoint — and fix the goal check to use a distance threshold, not float equality.
- Keep total per-step rewards roughly in `[-1, 1]`; PPO is much happier with normalised, consistent scales than the current `+20` gate vs `-0.001` time mix.

---

## 7. PPO essentials (what we'll implement)

Actor-critic MLP (shared trunk or two small nets):
- **Actor** → action distribution (Gaussian or categorical).
- **Critic** → scalar state value `V(s)`.

Loop:
1. Collect a rollout of T steps across the N parallel envs (store obs, action, logprob, reward, value, done).
2. Compute returns + advantages with **GAE** (`gamma`, `lambda`).
3. For K epochs over minibatches, optimise the **clipped surrogate**:
   `L = min(r·A, clip(r, 1−ε, 1+ε)·A)` where `r = exp(logπ_new − logπ_old)`,
   plus a value-function loss and an **entropy bonus** (keeps exploration without the epsilon hacks).
4. Repeat.

Hyperparameters to expose in `config.py`: `gamma`, `gae_lambda`, `clip_eps`, `entropy_coef`, `value_coef`, `lr`, `rollout_len`, `epochs`, `minibatch_size`, `num_envs`. Seed everything for reproducibility.

This replaces the entire DQN stack: no replay buffer, no target network, no epsilon schedule, no Q-values.

---

## 8. What to keep vs rewrite from the current code

**Keep / adapt:**
- `cast_ray` ray-casting logic (sound).
- Maze loading (`maze_loader`, `maze.py` wall building) and the flood-fill path generation.
- Core physics in `mouse.py` (turn/impulse/friction/collision) — but remove the redundant `length` re-normalisation block and decouple from the pygame clock.

**Rewrite / drop:**
- `model.py` (DQN) → actor-critic.
- `agent.py` training loop, replay buffer, epsilon, prioritised sampling → PPO.
- Reward logic → progress-based (§6).
- `environment.py` draw/loop → split into `sim.py` (logic) + `render/renderer.py` (pygame).
- Hardcoded absolute maze path in `train()`.

---

## 9. Roadmap (with a check at each step)

1. **Env standalone, headless, fixed-dt.** Verify: a hardcoded "drive forward" policy moves the mouse and `step()` returns sane obs/reward with no pygame running.
2. **Renderer split out.** Verify: same env runs identically with rendering on/off; manual keyboard control still works for sanity.
3. **Random-agent baseline.** Verify: rewards and episode termination behave; log mean episode length.
4. **Single-env PPO, discrete actions, one simple maze.** Verify: mean episode reward trends up; agent reaches the goal sometimes.
5. **Vectorised PPO (the swarm).** Verify: training wall-clock time drops sharply; convergence on the full `example4` path.
6. **Continuous action head.** Verify: smoother trajectories, comparable or better convergence.
7. **Curriculum / multiple mazes.** Short→long, then live flood-fill on unseen mazes to test generalisation.
8. **3D later:** replace `env/` only; model + training reused unchanged.

---

## 10. Open question for you
The env is continuous-native either way (§5). Remaining choice is only on the learning side: start PPO with the **discrete adapter** to isolate env bugs first (my recommendation), or go **straight to a continuous Gaussian head**? Everything else above I'd proceed with unless you want changes.
