# Micro-Mouse — Project Overview

A reference for the `micromouse/` package: how we got here, how the pieces fit
together, and what every file / class / function does. Written as a learning aid.

---

## 1. The story so far

**Where we started.** The original code (still in `flood_fill/`) trained the mouse
with a **DQN** adapted from a Snake tutorial — a *value-based* method that picks
the single best of four discrete actions. On a continuous maze it barely moved a
few tiles. Two root problems: the state fed in absolute coordinates (so the agent
couldn't generalise — "a few pixels left" looked like a brand-new situation), and
a value-based/discrete method is the wrong tool for continuous control.

**The decision.** Rewrite around **PPO** (Proximal Policy Optimisation), a
*policy-gradient* method that outputs a probability distribution over *continuous*
actions. This naturally handles "many nearby steering angles are all fine", and is
the standard choice for control problems headed for real hardware.

**The rebuild (new `micromouse/` package).** We rebuilt the environment from
scratch with three rules:
1. **Decouple the simulation from the pygame clock** — physics advances by a fixed
   timestep, so training runs as fast as the CPU allows instead of being capped at
   60 FPS.
2. **pygame is the renderer only** — all physics, collision and sensing is pure
   maths, so headless training has no graphics overhead and the eventual 3D move
   is clean.
3. **Egocentric observations** — the mouse sees wall distances (raycasts) and the
   *direction to its next waypoint*, never absolute coordinates.

**Getting it to learn.** The first PPO run *didn't* learn (return flat at ≈ −7.6,
entropy rising). Diagnosis: the only strong reward was reaching the goal, which a
random policy never does, so every trajectory scored the same → zero advantage →
no gradient. Fixes:
- **Dense directional shaping** — reward for moving *toward* the next waypoint
  every step (gradient everywhere, not just at the goal).
- **Per-waypoint bonuses** — 36 milestones instead of one distant goal.
- **Lower initial exploration** — start the action spread small so early behaviour
  isn't wild spinning.

After those, it worked: mean return climbed −38 → ≈ +57, entropy fell (the policy
committed), and a greedy evaluation solves `example4` in ~933 steps.

**Current status.** Solves the **single maze it trains on** (`example4`).
Generalising to unseen mazes is the next milestone.

---

## 2. How it fits together (data flow)

### The simulation step (no learning involved)
```
action [turn_rate, accel]
        │
        ▼
MouseState.step ──► integrate heading/speed/position (fixed dt) ──► resolve wall collision
        │
        ▼
MazeMouseEnv.step ──► advance waypoint ──► compute reward ──► build observation
        │
        ▼
(obs, reward, done, info)
```
The environment is a standard `reset()` / `step(action)` interface. It owns a
`Maze` (static world) and a `MouseState` (moving agent). Nothing here imports
pygame; rendering is a separate optional call.

### The training loop (PPO)
```
for each update:
   collect a rollout:  policy.act(obs) → env.step(action) → store in RolloutBuffer   (×2048)
   buffer.compute_gae(...)   → returns + advantages
   ppo_update(...)           → a few epochs of clipped-surrogate gradient steps
   log + checkpoint
```
The policy proposes actions, the environment scores them, the buffer turns raw
rewards into learning targets, and the PPO update nudges the network toward
actions that did better than expected.

---

## 3. File-by-file reference

The package lives in `micromouse/`. Files are grouped by role.

### Simulation core (pure maths — no pygame, no torch)

**`config.py`** — every tunable constant in one place (paths, tile size, physics
rates, sim timestep, sensor setup, colours, reward weights, PPO hyperparameters).
The rule: no magic numbers anywhere else; import from here.

**`maze_loader.py`** — reads the `.num` maze tables.
- `load_maze(filename)` → `(walls, width, height)`. Parses lines of `x y N E S W`
  into a dict `{(x,y): (north, east, south, west) booleans}` plus the grid size.
- `available_mazes(dir)` → lists `.num` files in a folder.

**`flood_fill.py`** — plans the path the mouse should follow, from the maze itself.
This is also the **swap-in seam**: everything downstream only reads `Maze.path` /
`Maze.waypoints`, so a hardcoded path can replace the flood fill with no other
changes.
- `cell_neighbours(cell, walls)` → accessible neighbours (no wall between).
- `compute_distances(walls, goal_cells)` → BFS flood from the goal; every cell's
  step-distance to the nearest goal.
- `extract_path(distances, walls, start)` → greedy descent down that distance
  field from the start to the goal.
- `generate_turns(path)` → simplifies a full path to just its corner cells
  (the "waypoints").
- `default_goal(width, height)` → the standard central 2×2 goal block.
- `get_path(walls, start, goal_cells)` → convenience: flood then descend. The
  default path source the environment uses.

**`geometry.py`** — the pure-maths world: walls as line segments, raycasting and
circle collision. Keeping this pygame-free is what makes headless training fast.
All coordinates are screen pixels (y down); the maze's y-up convention is flipped
exactly once here.
- `build_wall_segments(walls, tile, height)` → wall flags → de-duplicated line
  segments `((x1,y1),(x2,y2))`.
- `closest_point_on_segment(p, seg)` → nearest point on a segment to `p`.
- `_segment_normal(seg)` → unit perpendicular (fallback push direction).
- `resolve_circle_collision(center, radius, segments)` → **the collision
  resolver**: for each wall, if the mouse-circle overlaps, slide it straight back
  out along the line from wall to centre. Returns `(corrected_center, collided)`.
- `ray_segment_intersection(origin, angle, seg)` → distance to a wall hit, or None.
- `cast_ray(origin, angle, segments, max_dist)` → nearest hit distance, normalised
  to [0,1] (1.0 = nothing in range).

**`maze.py`** — the static world.
- `class Maze`
  - `__init__(walls, width, height, tile)` → stores the grid, builds wall
    `segments`, runs the flood fill, sets the `goal`.
  - `compute_path(start)` → plan + cache the flood-fill path and waypoints.
  - `set_path(path)` → install any path (flood-fill or hardcoded) and derive its
    turns. (The swap-in entry point.)
  - `cell_to_world(cell)` / `world_to_cell(pos)` → all coordinate conversion and
    the single y-flip live here.
  - `is_goal(pos, tol)` → distance-threshold goal check (fixes the old float-equality
    bug that never fired).
  - `pixel_size` → window size in pixels.

**`mouse.py`** — the moving agent (physics + sensors, no pygame).
- `class MouseState`
  - `__init__/reset(pos, heading, jitter)` → place the mouse; optional spawn jitter.
  - `step(action, dt, segments)` → one physics tick: apply `turn_rate` and `accel`
    (both per-second so framerate-independent), apply friction, integrate position,
    resolve wall collision, bleed speed on contact.
  - `ray_angles()` → the absolute angles of the sensor fan.
  - `sense(segments)` → NUM_RAYS normalised wall distances for the current pose.
  - `pose` → `(x, y, heading)`.

### Environment interface

**`environment.py`** — the training-facing contract (Gym-style). No pygame, no
clock; `step()` always advances by `config.FIXED_DT`.
- `class Space` → tiny `(shape, low, high)` descriptor (avoids a gym dependency).
- `_wrap_angle(a)` → wrap to (−π, π].
- `class MazeMouseEnv`
  - `__init__(maze_file, start_cell, seed, path)` → load maze, build `Maze`, place
    the `MouseState`; chooses the **path source** (flood fill by default, or a
    passed-in hardcoded `path`).
  - `reset()` → reset mouse + counters, aim at the first waypoint, return the obs.
  - `step(action)` → advance physics, advance the waypoint target, compute reward,
    return `(obs, reward, done, info)`.
  - `_get_obs()` → the observation vector (see §4). *Provisional — tied to the policy.*
  - `_compute_reward()` → the reward (see §4). *Provisional.*
  - `_advance_waypoint()` → move the target index forward as each waypoint is reached.
  - `_target_world()` → world position of the **next** waypoint to steer toward.
  - `_heading_alignment()` → normalised speed projected onto the direction to the
    target (the dense shaping term).
  - `_progress()` → fraction (0..1) of the path's arc-length reached, via projection
    onto the path polyline.
  - `render()` / `_ray_endpoints()` / `close()` → the only code path that imports
    pygame (lazily), for visualisation.

### Rendering & harness

**`renderer.py`** — the **only** pygame file. Draws walls, the path, the goal, the
mouse (as its collision circle + heading spoke), and the sensor rays. Its
`pygame.time.Clock` throttles the *display* only — it never gates the simulation.
- `class Renderer`: `__init__(maze)`, `draw(mouse, path, rays)`, `_draw_mouse(mouse)`,
  `close()`.

**`run.py`** — sanity-check harness (random policy, no learning).
- `random_action()`, `benchmark(steps)` (headless steps/sec — proves clock
  decoupling), `render_run(steps)` (watch it), `main()`.
- Usage: `python -m micromouse.run --benchmark 50000` or `--render`.

### Learning (PyTorch)

**`policy.py`** — the actor-critic network.
- `_mlp(in, out, hidden)` → a two-hidden-layer Tanh MLP.
- `class ActorCritic`
  - `actor_mean` → maps obs to the **mean** of a Gaussian over `[turn_rate, accel]`.
  - `critic` → maps obs to a scalar value estimate.
  - `log_std` → a learnable, state-independent action spread (starts at
    `config.INIT_LOG_STD`).
  - `act(obs)` → sample an action for rollout: `(action, logprob, value)`.
  - `mean_action(obs)` → greedy action (the mean) for evaluation.
  - `evaluate(obs, action)` → re-score stored transitions with gradients on:
    `(logprob, entropy, value)`.

**`buffer.py`** — rollout storage + GAE, deliberately pure NumPy so the advantage
maths is readable/testable without torch.
- `class RolloutBuffer`: `add(...)`, `is_full()`, `reset()`, and
  `compute_gae(last_value, gamma, lam)` → turns stored rewards/values into
  `(returns, advantages)`; a `done` flag stops credit bleeding across episodes.

**`ppo.py`** — the gradient step.
- `ppo_update(policy, optimizer, buffer, returns, advantages, cfg)` → a few epochs
  of minibatch SGD on the **clipped surrogate** objective (policy loss + value loss
  − entropy bonus), with advantage normalisation and gradient clipping. Returns
  loss/entropy stats for logging.

**`train.py`** — the training loop.
- `train(total_timesteps, rollout_steps, smoke)` → collect rollout → GAE → update →
  log → checkpoint, repeated. Single environment for now (vectorising is a later
  perf step).
- `_save(policy)` → write `model/ppo_policy.pth`.
- Usage: `python -m micromouse.train` (full) or `--smoke` (tiny check).

**`eval.py`** — watch / measure a trained policy.
- `load_policy(env)`, `run_episode(env, policy, render)`, `main()`.
- Acts **greedily** (the distribution mean) and reports whether the goal is reached.
- Usage: `python -m micromouse.eval` (render) · `--episodes 10 --no-render` (stats)
  · `--maze example2.num` (test generalisation on another maze).

---

## 4. The observation and reward (current, provisional)

**Observation** (length `NUM_RAYS + 4` = 11): the 7 normalised raycast distances,
plus `[sin Δθ, cos Δθ, distance, speed]` where `Δθ` is the heading error to the
**next waypoint**. Everything is egocentric and normalised — no absolute position.

**Reward** per step:
- `+ REWARD_PROGRESS × (Δ fraction of path covered)` — main forward driver.
- `+ REWARD_WAYPOINT × (waypoints reached this step)` — milestone bonus.
- `+ REWARD_HEADING × (speed · cos(heading error))` — dense "move toward target".
- `− REWARD_TIME` each step — encourages finishing.
- `− REWARD_COLLISION` while touching a wall.
- `+ REWARD_GOAL` and episode ends when the goal is reached (or on time-out).

These are marked *provisional* in the code because they're expected to evolve
alongside the policy.

---

## 5. Running it

```
python -m micromouse.run --render          # watch a random policy (no learning)
python -m micromouse.train                 # train PPO (writes model/ppo_policy.pth)
python -m micromouse.train --smoke         # quick end-to-end sanity run
python -m micromouse.eval                  # watch the trained policy
python -m micromouse.eval --maze example2.num --no-render   # test another maze
```

---

## 6. Status & next steps

- **Works:** solves `example4` (its training maze) with a clean greedy run.
- **Open:** generalisation to unseen mazes — likely needs training across several
  mazes (randomised per episode), and possibly a curriculum.
- **Possible refinements:** stronger time incentive for faster solves, annealing
  exploration, training-curve logging, and (only if speed becomes a problem)
  spatial culling of wall segments to raise steps/sec.

Related design docs: `GENERAL_PLAN.md` (overall DQN→PPO plan) and
`micromouse/ENV_PLAN.md` (the original environment design).
