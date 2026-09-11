# UKMARS Gemini Micromouse Codebase

Autonomous navigation, flood-fill maze exploration, and speed-run execution software for the **UKMARS Gemini** micromouse platform (Raspberry Pi Pico 2 W running MicroPython).

Designed so the **exact same code** runs on both PC simulation and Pico hardware.

---

## 1. Architecture & Design Principles

### Tree view

Four layers. Each knows the layer below it and nothing above.

```
 1  PURE BRAIN -- cells and compass sides only; no pins, no mm, no pixels
    +-------------+ +--------------------+ +-------------+ +--------------+
    |   maze.py   | | search_algorithms  | | explorer.py | | commands.py  |
    | belief grid | |     flood fill     | |  belief +   | |  cells ->    |
    | + .num I/O  | |  + route_is_open   | |  position   | | F n/L/R/U/H  |
    +-------------+ +--------------------+ +-------------+ +--------------+

 2  MODES -- turn a plan into timed motor powers
    +-----------+ +-------------+ +--------------+ +--------------+ +------------+
    |  main.py  | | exploration | |  speed_run   | |  bench_test  | | max_speed_ |
    | SW1/SW2 + | |   mode 1    | |    mode 2    | |    mode 3    | |    test    |
    | dispatch  | |             | | route + exec | | lazy import  | | modes 4, 5 |
    +-----------+ +-------------+ +--------------+ +--------------+ +------------+
                         |              |                |               |
                         +--------------+----------------+---------------+
                                        v
 3  MOTOR BOUNDARY      +--------------------------------------------+
                        |                  drive.py                  |
                        |   drive_motors(left, right), [-1.0, 1.0]   |
                        |   stop_motors, run_motion_for, pivot,      |
                        |   blink_led, the motor trace               |
                        +--------------------------------------------+
                                        |
 4  PLATFORM BOUNDARY   +--------------------------------------------+
                        |                  setup.py                  |
                        |  the ONLY "try: from machine import ..."   |
                        |  every pin, PWM, ADC, read_encoders()      |
                        +--------------------------------------------+
                              |                       |
                    (Pico)    v                       v    (PC)
            +------------------------+   +--------------------------+
            | MicroPython "machine"  |   |       sim/ package       |
            | real PWM / ADC         |   | sim_machine -> mouse ->  |
            | diagnostic_encoders    |   | geometry; renderer;      |
            | (PIO quadrature)       |   | replay_log.  NEVER       |
            |                        |   | deployed to the board.   |
            +------------------------+   +--------------------------+
```

**The `sim/` rule.** Anything in `sim/` is PC-only and is never copied to the
Pico. Nothing imports it unconditionally: `setup.py` reaches for
`sim.sim_machine` only when the real `machine` module is absent, and the mode
modules guard `sim.renderer` behind a `try/except ImportError`. A board without
the directory runs headless, which is what it does today.

### Summary

* **Zero Standard Library Dependencies for Firmware**: Core logic on Pico uses standard MicroPython modules (`os`, `time`, `math`, `machine`). Desktop-only libraries like `pygame` are restricted to PC simulation wrappers.
* **Unified Hardware Abstraction (`setup.py`)**: Defines physical pin mappings, PWM channels, ADC sensor inputs, and button handles.
  * **On Pico**: Loads MicroPython's native C `machine` module.
  * **On PC**: Loads desktop mock `sim_machine.py`, which integrates differential-drive physics and sensor raycasting.
* **Discrete Belief vs. Continuous Geometry**:
  * `MazeStructure` (`maze.py`): Lightweight grid representation `(x, y): (N, E, S, W)` used as the internal belief map on both PC and Pico.
  * `MazeGeometry` (`geometry.py`): Continuous $mm$-space raycasting physics used **only on PC** for simulation.
* **`main.py` is a dispatcher and nothing else**: it registers the five modes, reads SW1/SW2 or a CLI flag, opens the motor trace around the run, and hands off. The behaviour lives in the mode modules.
* **One motor boundary (`drive.py`)**: every mode moves a wheel through `drive_motors(left, right)` with signed power in `[-1.0, 1.0]`. No mode imports another mode to get a driver.

---

## 2. Operation Modes (`main.py`)

When `main.py` runs, **SW1 (Pin 15)** cycles through available modes with onboard LED blinks ($N$ blinks = Mode $N$), and **SW2 (Pin 14)** executes the selected mode:

1. **Mode 1: Exploration Mode (`--step` / `--explorer`)** -- *simulation only*:
   * Mouse explores the maze cell-by-cell using flood-fill (`search_algorithms.py`).
   * Updates its `belief_map`, then exports the discovered layout to `belief.num`.
   * **It does not use a sensor.** `read_walls()` reads `groundtruth.num` directly. The simulated reflective sensors exist (`sim/mouse.py`, `sim/geometry.py`) but nothing yet converts an ADC reading into a sensed side, so this mode has no hardware path. It also never calls `drive_motors`, so the simulated body does not move -- only the logical `Explorer` advances.
2. **Mode 2: Speed Run Mode (`--speed`)**:
   * Loads the saved grid map (`belief.num`) or `groundtruth.num`.
   * Calculates the optimal shortest path using flood fill.
   * Translates the path into egocentric verbs (`F n`, `L`, `R`, `U`, `H`) via `commands.py`.
   * Drives the mouse through the movement sequence.
3. **Mode 3: Bench Test Mode (`--bench`)**:
   * Runs bringing-up hardware checks end-to-end (`bench_test.py`).
4. **Mode 4: Max Speed Test (`--maxspeed`)**:
   * Drives one straight dash at full duty over a marked distance (5.2 m by default), then brakes hard.
   * The LED goes solid for the whole drive, so a stopwatch can time a marked 5 m. See `CHEATSHEET.md` §5.1.
   * Captures the encoder ticks either side of the dash. `calibrate(travelled_mm, stopwatch_s)` yields `MAX_WHEEL_SPEED_MMS` from the stopwatch, and checks the decoder against the ruler-confirmed wheel: an implied diameter above 32 mm means edges are being dropped.
5. **Mode 5: Stress Test (`--stress`)**:
   * N laps of the sprint (default 20 × 5 m, ~11 min), reversing between legs, then reports accumulated drift.
   * Reversing cancels symmetric error, so it measures asymmetry, encoder dropout and battery sag. `turn_around=True` pivots 180° instead, letting distance and turn error accumulate.
   * Either button aborts between legs.

---

## 3. Module Guide

| File | Purpose |
| :--- | :--- |
| **`main.py`** | Dispatcher. Registers `MODES`, reads SW1/SW2 or a CLI flag, opens and closes the motor trace around the run. Keeps a `stop_motors` alias for the REPL e-stop. |
| **`drive.py`** | The motor boundary. `drive_motors` / `stop_motors` / `run_motion_for` / `pivot_in_place` / `blink_led`, and the motor trace. Everything that moves a wheel goes through here. |
| **`setup.py`** | Hardware pin definitions for motors, reflective sensors, buttons and encoders, plus `read_encoders()`. The single platform boundary. |
| **`config.py`** | Single source of truth for physical scale (180 mm cells, wheel diameter, track width), timing, render colours, and file paths. |
| **`maze.py`** | `MazeStructure` class and `.num` file reader (`num_file_import`) / writer (`num_file_export`). |
| **`explorer.py`** | Pure `Explorer` class that manages belief maps and steps between cells. |
| **`search_algorithms.py`** | Pure flood-fill distance transform and greedy descent pathfinding, plus `route_is_open` (the replan trigger). |
| **`commands.py`** | Translates absolute cell routes into egocentric relative commands (`F n`, `L`, `R`, `U`, `H`) and writes the `.mmc` route file. |
| **`exploration.py`** | Mode 1. Cell-by-cell exploration loop. Simulation only -- see section 2. |
| **`speed_run.py`** | Mode 2. Loads a belief, plans over it, and executes the verbs as timed open-loop drives. Owns the route, not the motors. |
| **`bench_test.py`** | Mode 3. The BT-0..BT-8 hardware bring-up checks. Imported lazily by `main.py`; not in the minimal deployment set. |
| **`max_speed_test.py`** | Modes 4 and 5. One straight dash over a marked distance plus `calibrate()`, and the N-lap stress run. |
| **`motor_log.py`** | Change-only CSV trace of commanded motor powers (format v1). Written on every hardware run, and on `--log` from the PC. |
| **`diagnostic_encoders.py`** | PIO quadrature encoder counter. Takes its pins from `setup.py` and is reached through `setup.read_encoders()`, never imported directly. |
| **`groundtruth.num`** | Default ground-truth maze fixture used by PC simulation. |
| **`belief.num`** | The map a speed run drives. Written by mode 1, and the hand-authored input for a known-map run on hardware. |

### PC-only (`sim/`) -- never deployed to the Pico

| File | Purpose |
| :--- | :--- |
| **`sim/sim_machine.py`** | Mock MicroPython `machine` module (`Pin`, `PWM`, `ADC`). Writing a PWM duty steps the physics instead of driving a pin. |
| **`sim/mouse.py`** | `MouseState` continuous pose integration (exact-arc differential drive), encoder tick accumulation, and the phototransistor ADC model. |
| **`sim/geometry.py`** | `MazeGeometry` mm-space wall segments and post polygons, and the `cast_ray()` engine. |
| **`sim/renderer.py`** | Optional Pygame renderer, plus `make_renderer()` so no mode has to import another mode in order to draw. |
| **`sim/replay_log.py`** | Re-drives the sim from a Pico `motor_log.csv`. The gap between the replayed pose and where the robot really stopped is the measurement. |

---

## 4. How to Run

### Running in PC Simulation
Run `main.py` directly from the project directory:
```bash
python3 main.py
```
There is no test suite at present: `tests/` was cleared on 2026-09-11 to be rebuilt with divisions by purpose and responsibility. `maze.py`, `explorer.py`, `search_algorithms.py`, `commands.py` and `motor_log.py` still carry runnable inline self-tests (`python3 maze.py`).

To replay a hardware trace into the sim:
```bash
python3 sim/replay_log.py --render
```

### Running on Pico W Hardware
1. Copy the deployment set to the Pico's root filesystem -- **not** the whole directory. `sim/` must never go on the board, and `bench_test.py` is optional. `CHEATSHEET.md` section 2 has the exact `mpremote` line.
2. MicroPython automatically executes `main.py` on power-up.