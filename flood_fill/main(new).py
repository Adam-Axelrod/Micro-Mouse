import sys

import maze_loader
from mouse import Mouse
from environment import Environment
from constants import *

"""
Maze format: [X Y N E S W] <-- each cell is separated with a newline
Set directory to Micro-Mouse and then use 
"python3 flood_fill/maze_environment.py" to run from terminal
"""

def main():
    maze_params = maze_loader.load_maze()
    if maze_params is None:
        print("No maze file selected.")  # optional for logging
        sys.exit(0)

    walls_dict, max_y = maze_params
    environment = Environment(walls_dict, max_y)
    environment.add_mouse(Mouse(x=0.375, y=max_y+0.375, colour=PINK))
    environment.game_loop()

if __name__ == "__main__":
    main()
