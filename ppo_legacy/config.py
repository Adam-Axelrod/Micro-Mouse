"""Central configuration.

Every tunable constant lives here so there are no magic numbers scattered through
the code. Import from this module rather than hard-coding values.
"""
from __future__ import annotations

import math
from pathlib import Path

# --- Paths (resolved relative to the repo, so no absolute paths ever) --------
PACKAGE_DIR = Path(__file__).resolve().parent          # .../Micro-Mouse/micromouse
REPO_DIR = PACKAGE_DIR.parent                          # .../Micro-Mouse
MAZES_DIR = REPO_DIR / "mazes" / "example_mazes"
DEFAULT_MAZE = MAZES_DIR / "example4.num"

# --- Maze geometry -----------------------------------------------------------
TILE_SIZE = 40.0          # pixels per maze cell

# --- Mouse body --------------------------------------------------------------
MOUSE_RADIUS = TILE_SIZE * 0.18    # collision circle radius (px)
MOUSE_DRAW_W = TILE_SIZE * 0.30    # render size only (px)
MOUSE_DRAW_H = TILE_SIZE * 0.50

# --- Physics (every rate is per-second, so behaviour is framerate-independent)
MAX_SPEED = 120.0                      # px / s
ACCEL = 300.0                          # px / s^2 at full throttle (action = 1)
FRICTION = 0.5                         # speed multiplier per second with no input
MAX_TURN_RATE = math.radians(220.0)    # rad / s at full steer (action = 1)
ALLOW_REVERSE = False                  # if False, speed is clamped to [0, MAX_SPEED]

# --- Simulation stepping -----------------------------------------------------
FIXED_DT = 1.0 / 60.0      # seconds advanced per step(); DECOUPLED from real time
MAX_EPISODE_STEPS = 2000   # episode time-out (steps)
START_JITTER = 0.0         # random spawn offset in px (0 = deterministic)

# --- Sensors (raycasts) ------------------------------------------------------
NUM_RAYS = 7
RAY_FOV = math.radians(180.0)   # total fan width, centred on the heading
RAY_MAX_DIST = 5 * TILE_SIZE    # px

# --- Colours / rendering (renderer only) -------------------------------------
COLOUR_BG = (12, 12, 16)
COLOUR_WALL = (230, 230, 230)
COLOUR_PATH = (60, 90, 160)
COLOUR_GOAL = (255, 165, 0)
COLOUR_MOUSE = (235, 60, 60)
COLOUR_RAY = (70, 160, 70)
RENDER_FPS = 60   # human-view throttle ONLY; never gates the simulation

# --- Reward shaping ----------------------------------------------------------
REWARD_PROGRESS = 10.0      # scales the fraction-of-path progress gained per step
REWARD_HEADING = 0.01       # dense bonus for moving TOWARD the next waypoint
REWARD_WAYPOINT = 1.0       # one-off bonus each time a waypoint is reached
REWARD_TIME = 0.005         # flat per-step penalty (encourages finishing sooner)
REWARD_COLLISION = 0.05     # per-step penalty while touching a wall
REWARD_GOAL = 10.0          # one-off bonus for reaching the goal
WAYPOINT_RADIUS = TILE_SIZE * 0.5   # how close counts as "reached" a waypoint

# --- PPO hyperparameters -----------------------------------------------------
HIDDEN_SIZE = 64            # width of the actor and critic MLPs
INIT_LOG_STD = -0.5         # initial action spread (std=exp(-0.5)≈0.61); lower = calmer start
PPO_LR = 3e-4               # Adam learning rate
PPO_GAMMA = 0.99            # reward discount
PPO_GAE_LAMBDA = 0.95       # GAE smoothing factor
PPO_CLIP = 0.2             # policy-ratio clip range
PPO_ENTROPY_COEF = 0.01     # entropy bonus (keeps exploration alive)
PPO_VALUE_COEF = 0.5        # weight of the value-function loss
PPO_MAX_GRAD_NORM = 0.5     # gradient clipping
PPO_ROLLOUT_STEPS = 2048    # environment steps collected per update
PPO_EPOCHS = 10             # optimisation passes over each rollout
PPO_MINIBATCH = 256
TOTAL_TIMESTEPS = 1_000_000
CHECKPOINT_DIR = REPO_DIR / "model"
