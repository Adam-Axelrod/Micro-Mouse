# UKMARS Gemini Micromouse Codebase

Autonomous navigation, flood-fill maze exploration, and speed-run execution software for the **UKMARS Gemini** micromouse platform (Raspberry Pi Pico 2 W running MicroPython).

Designed so the **exact same code** runs on both PC simulation and Pico hardware.

---

## 1. Architecture & Design Principles

* **Zero Standard Library Dependencies**: Uses standard MicroPython modules (`os`, `time`, `math`, `machine`). No `pathlib` or desktop-only libraries are required on the Pico.
* **Unified Hardware Abstraction (`setup.py`)**: Defines physical pin mappings, PWM channels, ADC sensor inputs, and button handles.
  * **On Pico**: Loads MicroPython's native C `machine` module.
  * **On PC**: Loads desktop mock `machine.py`, which integrates differential-drive physics and sensor raycasting.
* **Discrete Belief vs. Continuous Geometry**:
  * `MazeStructure` (`maze.py`): Lightweight grid representation `(x, y): (N, E, S, W)` used as the internal belief map on both PC and Pico.
  * `MazeGeometry` (`geometry.py`): Continuous $mm$-space raycasting physics used **only on PC** for simulation.

---

## 2. Operation Modes (`main.py`)

When `main.py` runs, it selects the operation mode based on button input:

1. **Exploration Mode (Left Button / `btn1` - Pin 20)**:
   * Mouse explores the maze cell-by-cell using flood-fill (`search_algorithms.py`).
   * Updates its `belief_map` upon sensing walls.
   * Exports the discovered maze layout to `last_explored_belief.num` upon completion.
2. **Speed Run Mode (Right Button / `Switch` - Pin 14)**:
   * Loads the saved grid map (`last_explored_belief.num`) or `groundtruth.num`.
   * Calculates the optimal shortest path using flood fill.
   * Translates the path into egocentric verbs (`F n`, `L`, `R`, `U`, `H`) via `commands.py`.
   * Drives the mouse through the movement sequence.

---

## 3. Module Guide

| File | Purpose |
| :--- | :--- |
| **`main.py`** | Top-level entry point. Handles button state checks, mode selection, and command execution. |
| **`setup.py`** | Hardware pin definitions for motors, reflective sensors, and buttons. |
| **`machine.py`** | Desktop mock MicroPython `machine` module (`Pin`, `PWM`, `ADC`) for PC simulation. |
| **`config.py`** | Single source of truth for physical scale ($180\text{mm}$ cells, wheel diameter, track width), timing, and file paths. |
| **`maze.py`** | `MazeStructure` class and `.num` file reader (`num_file_import`) / writer (`num_file_export`). |
| **`geometry.py`** | 2D line segment calculations and `cast_ray()` engine for PC sensor simulation. |
| **`mouse.py`** | `MouseState` continuous pose integration (differential-drive kinematics) and phototransistor ADC light-intensity model. |
| **`explorer.py`** | Pure `Explorer` class that manages belief maps and steps between cells. |
| **`search_algorithms.py`** | Pure flood-fill distance transform and greedy descent pathfinding. |
| **`env_explorer.py`** | Exploration loop (`explore`) and grid loading/planning helper (`load_and_plan_route`). |
| **`commands.py`** | Translates absolute cell routes into egocentric relative commands (`F n`, `L`, `R`, `U`, `H`). |
| **`diagnostic_encoders.py`** | MicroPython PIO quadrature encoder counter class for hardware motor encoders. |
| **`groundtruth.num`** | Default ground-truth maze fixture used by PC simulation. |

---

## 4. How to Run

### Running in PC Simulation
Run `main.py` directly from the project directory:
```bash
python3 main.py
```
To run the automated physics and simulation test suite:
```bash
python3 tests/test_physics_sim.py
```

### Running on Pico W Hardware
1. Copy all files from `Micro-Mouse/micromouse/` to the Pico's root filesystem.
2. MicroPython automatically executes `main.py` on power-up.