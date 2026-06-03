# Environment Rebuild — Design Doc

Scope: a clean, self-contained pygame **environment** in `maze_env/` (sibling of `flood_fill/`). Loads the same `.num` maze tables. Simulation is fully decoupled from the pygame clock so training can run headless at max speed. **No model/training code yet** — but the env exposes the exact interface training will plug into.

This is a design for review. Nothing is written as code yet. Push back on anything before we build.

---

## Two decisions baked in (flag if you disagree)

**1. pygame is the *renderer only*; the simulation core is pure Python/NumPy.**
You said "new pygame environment," and pygame will absolutely be there — but only for drawing and manual control. The physics, collision and sensors use plain math (no `pygame.Rect`, no display). Why:
- Headless training never touches pygame, so there's no display/init dependency and no per-step `pygame` overhead — the main point of decoupling.
- It parallelises cleanly later (many sims, one process) and makes the eventual 3D swap painless (replace geometry, keep the interface).
- Collision/raycasting become *exact* (analytic segment math) instead of the pixel-stepping approximation in the old code.

If you'd rather keep `pygame.Rect` collision for familiarity, we can — it just couples the core to pygame and is slower headless.

**2. The path comes from a live flood fill**, computed from the loaded `.num` walls, not a hardcoded list. We adapt the working flood fill already in `flood_fill/Main.py` (`calculate_distances` / `calculate_path`). This means any maze file just works.

**Deferred to the model stage:** the exact contents of the observation vector and the reward function. The env will return valid `obs`/`reward` from day one (a sensible provisional version), clearly marked `TODO: finalise with policy`, so we can iterate without restructuring.

---

## How the clock decoupling works (the core idea)

- One constant, `FIXED_DT` (e.g. `1/60` s), is the simulation timestep. Every `step()` advances physics by exactly `FIXED_DT` regardless of how long it took in real time.
- Training calls `env.step(action)` in a tight loop — as fast as the CPU allows. No `tick()`, no `sleep`, no real-time gating anywhere in the sim.
- The **only** place a `pygame.Clock` exists is the renderer, where it throttles the *display* refresh so a human can watch at normal speed. It never affects the simulation. You can render at 60 FPS while the underlying sim has already run thousands of steps, or skip rendering entirely.

Result: physics is reproducible (same actions → same outcome, independent of machine speed) and training speed is bounded by compute, not by a 60 FPS wall.

---

## File layout

```
maze_env/
  __init__.py        # package exports
  config.py          # all constants/hyperparameters, no magic numbers
  maze_loader.py     # parse .num tables -> walls dict + dimensions
  flood_fill.py      # distances from goal + path extraction
  geometry.py        # pure-math walls, raycasting, collision (no pygame)
  maze.py            # Maze: geometry + flood-fill path + coordinate conversions
  mouse.py           # MouseState: physics, integration, sensors (no pygame)
  environment.py     # MazeMouseEnv: reset()/step() Gym-style API, fixed dt
  renderer.py        # pygame drawing + manual control (only pygame file)
  run_manual.py      # entry point: drive manually OR headless benchmark
```

---

## Per-file / class / function spec

### `config.py`
Single source of truth for constants; everything else imports from here.
- **Geometry:** `TILE_SIZE`, `MAZES_DIR` (resolved relative to repo via `pathlib`, so no absolute paths ever).
- **Physics:** `MAX_SPEED`, `ACCEL` (impulse per unit input), `FRICTION` (per-second decay), `MAX_TURN_RATE` (rad/s), `MOUSE_RADIUS`, `MOUSE_DRAW_W/H`.
- **Simulation:** `FIXED_DT`, `MAX_EPISODE_STEPS`, `START_JITTER`.
- **Sensors:** `NUM_RAYS`, `RAY_FOV` (total spread), `RAY_MAX_DIST`.
- **Render:** colours, optional target FPS for the human view only.

### `maze_loader.py`
Parsing the `.num` tables, no GUI in the core.
- `load_maze(filename) -> (walls, width, height)` — read the `x y N E S W` lines into `walls: dict[(x,y) -> (n,e,s,w) bools]`; track grid `width`/`height`. (Keeps the existing format; replaces the `"NESW"` string with a bool tuple for clean indexing.)
- `available_mazes() -> list[Path]` — list `.num` files in `MAZES_DIR`.
- `pick_maze_dialog()` — optional tkinter file picker, kept out of the import path so headless runs never import tkinter.

### `flood_fill.py`
Computes the path the mouse should follow, from the maze itself.
- `cell_neighbours(cell, walls) -> list[cell]` — accessible 4-neighbours (respecting wall bits).
- `compute_distances(walls, goal_cells) -> dict[cell -> int]` — BFS flood from the goal outward; each cell gets its step-distance to goal. (Adapted from `Main.py.calculate_distances`.)
- `extract_path(distances, start_cell) -> list[cell]` — greedy descent from start along strictly decreasing distance to the goal.
- `default_goal(width, height) -> list[cell]` — the centre cells (the standard micromouse 2×2 goal), overridable.

### `geometry.py`
Pure math, the part that makes it pygame-free and exact.
- `build_wall_segments(walls, tile_size, height) -> list[Segment]` — convert each cell's wall bits into world-space line segments `((x1,y1),(x2,y2))`, de-duplicating shared edges. Y-flip handled here once (`.num` is y-up, screen is y-down).
- `point_segment_distance(p, seg) -> float` — nearest distance, used for circle collision.
- `ray_segment_intersection(origin, direction, seg) -> float | None` — distance to hit, or None.
- `cast_ray(origin, angle, segments, max_dist) -> float` — min intersection over all segments, normalised 0–1. (Exact replacement for the old pixel-march `cast_ray`.)
- `resolve_circle_collision(center, radius, segments) -> (new_center, collided)` — push the mouse out of any wall it overlaps; report whether contact happened.

### `maze.py`
- **class `Maze`** — owns the static world.
  - `__init__(self, walls, width, height, tile_size)` — store grid; build `self.segments` (collision + render geometry); run flood fill; store `self.distances`, `self.goal`.
  - `compute_path(self, start_cell) -> list[cell]` — flood-fill path for a given start; also caches simplified `waypoints` (turn points only, via a `generate_turns` helper carried over from the old `path_calcs`).
  - `cell_to_world(self, cell) -> (x, y)` and `world_to_cell(self, pos) -> cell` — all coordinate/y-flip conversion lives here (fixes the scattered, inconsistent conversions in the old code).
  - `is_goal(self, pos) -> bool` — distance-threshold check (fixes the old float-equality goal bug that never fired).
  - `pixel_size` property — `(width*tile, height*tile)` for the renderer.

### `mouse.py`
- **class `MouseState`** — the dynamic agent, physics only, no pygame.
  - fields: `x, y` (float pixels), `heading` (radians), `speed` (float), `collided` (bool).
  - `__init__(self, start_pos, heading)` / `reset(self, start_pos, heading, jitter=0)` — (re)initialise; optional spawn jitter for robustness.
  - `step(self, action, dt, segments)` — the physics integrator. `action = [turn_rate, accel]`, each in `[-1, 1]` (continuous-native, per our earlier discussion). Updates heading from `turn_rate`, speed from `accel` and `FRICTION`, integrates position by `dt`, then calls `resolve_circle_collision` and sets `collided`. Fully `dt`-scaled so behaviour is framerate-independent.
  - `sense(self, segments) -> np.ndarray` — cast `NUM_RAYS` rays across `RAY_FOV` relative to `heading`; return normalised distances.
  - `pose` property — `(x, y, heading)` for the renderer.

### `environment.py`
The training-facing interface — this is the contract the model will use.
- **class `ActionSpace` / `ObservationSpace`** — tiny dataclasses describing shapes/bounds (so the future policy knows dimensions without importing gym). Optionally swap for `gymnasium.spaces` later.
- **class `MazeMouseEnv`**
  - `__init__(self, maze_file=None, seed=None)` — load maze (default if `None`), build `Maze`, create `MouseState` at the start cell, set RNG. No pygame.
  - `reset(self) -> obs` — reset mouse (+jitter), reset step counter and progress, recompute path, return `_get_obs()`.
  - `step(self, action) -> (obs, reward, done, info)` — advance `MouseState` by `FIXED_DT`; update path progress; compute reward; set `done` on goal / collision / `MAX_EPISODE_STEPS`; return tuple. **No clock here.**
  - `_get_obs(self) -> np.ndarray` — *provisional*: rays + heading-error (sin/cos) to next waypoint(s) + normalised speed + progress. `TODO: finalise with policy.`
  - `_compute_reward(self) -> float` — *provisional*: Δ progress-along-path − time penalty − collision penalty (+ goal bonus). `TODO: finalise with policy.`
  - `_progress(self) -> float` — project mouse position onto the path's arc-length (monotonic progress measure).
  - `render(self)` — lazy-create a `Renderer` on first call and draw current state (the only path that imports pygame).
  - `close(self)` — tidy up renderer if any.

### `renderer.py`
The only pygame file. Drawing + human input; never gates the sim.
- **class `Renderer`**
  - `__init__(self, maze)` — `pygame.init()`, create display sized to `maze.pixel_size`, own a `pygame.time.Clock` used *only* for human-view throttling.
  - `draw(self, mouse_state, path=None, rays=None)` — clear; draw wall segments, goal, path/waypoints, the mouse (rotated), and optionally its rays.
  - `poll(self) -> dict` — handle events; return manual controls (keys → a continuous `action`) and a quit flag.
  - `tick(self, fps)` — throttle the *display* to `fps` for watchability. Not called during training.
  - `close(self)` — `pygame.quit()`.

### `run_manual.py`
Verification harness (lets us confirm the env feels right before any ML).
- `manual()` — open the renderer, drive the mouse with the keyboard mapped to a continuous `action`, draw rays/path live. Sanity-checks physics, collision, sensors, coordinate conversions.
- `benchmark(steps)` — run `env.step()` headless with a random/scripted policy as fast as possible; print steps/second. This is the concrete proof that the sim is clock-independent.
- `main()` — arg parse: `--manual` (default) or `--benchmark [N]`.

### `__init__.py`
Export `MazeMouseEnv`, `Maze`, `MouseState`, `load_maze` for clean imports.

---

## Build & verify order (once you approve this design)

1. `config.py` + `maze_loader.py` — load a `.num` file, print dims and a few cells.
2. `geometry.py` — build wall segments from a loaded maze; unit-check a couple of known raycasts.
3. `flood_fill.py` — compute distances + path on `example4`; print the path, eyeball it.
4. `maze.py` — wire geometry + flood fill + conversions together.
5. `mouse.py` — physics + sensors; drive it with scripted actions, assert collision keeps it inside walls.
6. `environment.py` — `reset()`/`step()` returning valid tuples (provisional obs/reward).
7. `renderer.py` + `run_manual.py` — **manual drive** to confirm it feels right, then **`--benchmark`** to confirm headless steps/sec ≫ 60.

Each step is checkable on its own before moving on.

---

## Open decisions for you
1. Folder name `maze_env/` OK, or you prefer something else?
2. Pure-math core with pygame-as-renderer (my recommendation) vs keeping `pygame.Rect` collision?
3. Live flood fill (recommended) vs reusing the old hardcoded path for now?
