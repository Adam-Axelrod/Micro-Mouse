# UKMARS Gemini Micromouse Codebase

Autonomous navigation, flood-fill maze exploration, and speed-run execution software for the **UKMARS Gemini** micromouse platform (Raspberry Pi Pico 2 W running MicroPython).

Designed so the **exact same code** runs on both PC simulation and Pico hardware.

---

## 1. Architecture & Design Principles

### Tree view

```
                                  +---------------------------------------+
                                  |                main.py                |
                                  |  (Unified Control Loop PC & Pico)     |
                                  +---------------------------------------+
                                      |                |               |
          +---------------------------+                |               +---------------------------+
          | (Pure Decision Brain)                      | (Hardware)                                | (PC Visuals)
          v                                            v                                           v
+-------------------+                        +--------------------+                      +--------------------+
|    explorer.py    |                        |      setup.py      |                      |    renderer.py     |
| (Belief & Cells)  |                        | (Pins/Motors/ADCs) |                      | (Optional Pygame)  |
+-------------------+                        +--------------------+                      +--------------------+
          |                                            |
          v                                    +-------+-------+
+-------------------+                          |               |
| search_algorithms |                          v (Pico)        v (PC Sim)
|   (Flood Fill)    |                     [MicroPython]  [sim_machine.py]
+-------------------+                     [C `machine`]  [ (MouseState & ]
                                                         [  Ground Truth) ]
```
### Summary

* **Zero Standard Library Dependencies for Firmware**: Core logic on Pico uses standard MicroPython modules (`os`, `time`, `math`, `machine`). Desktop-only libraries like `pygame` are restricted to PC simulation wrappers.
* **Unified Hardware Abstraction (`setup.py`)**: Defines physical pin mappings, PWM channels, ADC sensor inputs, and button handles.
  * **On Pico**: Loads MicroPython's native C `machine` module.
  * **On PC**: Loads desktop mock `sim_machine.py`, which integrates differential-drive physics and sensor raycasting.
* **Discrete Belief vs. Continuous Geometry**:
  * `MazeStructure` (`maze.py`): Lightweight grid representation `(x, y): (N, E, S, W)` used as the internal belief map on both PC and Pico.
  * `MazeGeometry` (`geometry.py`): Continuous $mm$-space raycasting physics used **only on PC** for simulation.
* **Single Unified Main Loop (`main.py`)**:
  * `main.py` carries the `Explorer` decision brain (`explorer.py`), manages exploration and speed-run modes, drives hardware or PC simulation, and handles optional desktop rendering (`python3 main.py --render`).

---

## 2. Operation Modes (`main.py`)

When `main.py` runs, **SW1 (Pin 15)** cycles through available modes with onboard LED blinks ($N$ blinks = Mode $N$), and **SW2 (Pin 14)** executes the selected mode:

1. **Mode 1: Exploration Mode (`--step` / `--explorer`)**:
   * Mouse explores the maze cell-by-cell using flood-fill (`search_algorithms.py`).
   * Updates its `belief_map` upon sensing walls.
   * Exports the discovered maze layout to `belief.num` upon completion.
2. **Mode 2: Speed Run Mode (`--speed`)**:
   * Loads the saved grid map (`belief.num`) or `groundtruth.num`.
   * Calculates the optimal shortest path using flood fill.
   * Translates the path into egocentric verbs (`F n`, `L`, `R`, `U`, `H`) via `commands.py`.
   * Drives the mouse through the movement sequence.
3. **Mode 3: Bench Test Mode (`--bench`)**:
   * Runs bringing-up hardware checks end-to-end (`bench_test.py`).

---

## 3. Module Guide

| File | Purpose |
| :--- | :--- |
| **`main.py`** | Top-level entry point. Handles button state checks, mode selection, exploration loop, and command execution. |
| **`setup.py`** | Hardware pin definitions for motors, reflective sensors, and buttons. |
| **`sim_machine.py`** | Desktop mock MicroPython `machine` module (`Pin`, `PWM`, `ADC`) for PC simulation. |
| **`config.py`** | Single source of truth for physical scale ($180\text{mm}$ cells, wheel diameter, track width), timing, and file paths. |
| **`maze.py`** | `MazeStructure` class and `.num` file reader (`num_file_import`) / writer (`num_file_export`). |
| **`geometry.py`** | 2D line segment calculations and `cast_ray()` engine for PC sensor simulation. |
| **`mouse.py`** | `MouseState` continuous pose integration (differential-drive kinematics) and phototransistor ADC light-intensity model. |
| **`explorer.py`** | Pure `Explorer` class that manages belief maps and steps between cells. |
| **`search_algorithms.py`** | Pure flood-fill distance transform and greedy descent pathfinding. |
| **`renderer.py`** | Optional Pygame rendering engine for visualizing maze state, discovery, and path planning. |
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
1. Copy all files from `Micro-Mouse/` to the Pico's root filesystem. The MicroPico Device Controller lets you upload the 
whole project directly with a right click.
2. MicroPython automatically executes `main.py` on power-up.