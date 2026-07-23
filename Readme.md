# UKMARS Gemini Micromouse Rebuild

Autonomous navigation, flood-fill maze exploration, and speed-run execution software for the **UKMARS Gemini** micromouse platform (Raspberry Pi Pico 2 W running MicroPython).

Designed so the **exact same code** runs on both PC simulation and Pico hardware.

---

## Architecture Overview

```
                        +------------------------------------+
                        |              main.py               |
                        | (Shared Exploration & Run Control) |
                        +------------------------------------+
                                          |
                        +------------------------------------+
                        |              setup.py              |
                        |  (Standard Pin & Hardware Mapping) |
                        +------------------------------------+
                                          |
               +--------------------------+--------------------------+
               | (On Pico W)                                         | (On PC Simulation)
+-----------------------------+                       +-----------------------------+
| Native C `machine` Module   |                       | PC Mock `machine.py` Module |
| (MicroPython Firmware)      |                       | (PC Simulation Backend)     |
+-----------------------------+                       +-----------------------------+
               |                                                     |
[ Physical Motors & Sensors ]                         +-------------------------------+
                                                      | mouse.py (Differential Drive) |
                                                      | geometry.py (MazeGeometry)    |
                                                      +-------------------------------+
```

---

## Directory Structure

* **`Micro-Mouse/`**: The core package containing all portable source code and maze files.
  * `main.py`: Unified entry point with Left Button (Exploration) and Right Button (Speed Run) modes.
  * `setup.py`: Pin, PWM, and ADC hardware definitions.
  * `machine.py`: Mock MicroPython hardware module for PC simulation.
  * `config.py`: Hardware constants, dimensions ($180\text{mm}$ cells, wheel diameter, track width), and paths.
  * `maze.py`: `MazeStructure` grid representation and `.num` file parser/writer.
  * `geometry.py`: 2D line segment calculations and `cast_ray()` raycasting engine for PC.
  * `mouse.py`: Differential-drive kinematics (`MouseState`) and phototransistor ADC light-intensity model.
  * `explorer.py` & `search_algorithms.py`: Pure flood-fill algorithm and belief observer.
  * `env_explorer.py`: Exploration loop (`explore`) and grid persistence (`load_and_plan_route`).
  * `commands.py`: Egocentric verb translator (`F n`, `L`, `R`, `U`, `H`).
  * `diagnostic_encoders.py`: PIO quadrature counter for hardware motor encoders.
  * `groundtruth.num`: Default maze fixture for simulation.
* **`tests/`**: Headless automated test suite (`test_physics_sim.py`).
* **`agent-context/`**: Master documentation and epic specifications.

---

## Quick Start

### Running in PC Simulation
```bash
python3 main.py
```

### Running Automated Test Suite
```bash
python3 tests/test_physics_sim.py
```

### Deployment to Pico W
Copy all files inside `Micro-Mouse/` to the root filesystem of the Pico 2 W.