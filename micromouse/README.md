# README

Program for simulating and driving a Gemini maze mouse. Exploration with a flood fill algorithm & racing with a PPO based ML model.

## Setup

**Simulation**

1.
2.

**Pico W port**

1. Copy over relevant files


## Files

### config.py


### maze.py

Classes for hosting the important features of the maze. Designed for easy and quick comparisons between ground truth and imagined representations of the maze.
Handles construction of mazes from .num files and mirror exports.

#### class MazeStructure

Holds all the information needed for logical step based solving. Initialises an empty maze with a perimeter wall. Wall properties changed via a `mark_wall` call.

- self.cells: {(x, y), (n, e, s, w)}

	Dictionary of coordinate tuples (keys) against tuples of boolean values for wall presence (values).

- self.cols: int

- self.rows: int

- self.goal: (x, y)

#### class MazeGeometry

Holds the mathematical information needed for collision calculations and rendering. Needed for simulations but not for driving the gemini platform.


#### Tests:

> python -m micromouse.maze


### explorer.py