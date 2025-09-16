import os
import tkinter as tk
from tkinter import filedialog

def choose_maze_file():

    """Open a file dialog to select a .num maze file from the mazes directory."""

    root = tk.Tk()
    root.withdraw()  # Hide the main window
    mazes_dir = os.path.join(os.getcwd(), "mazes")
    file_path = filedialog.askopenfilename(
        initialdir=mazes_dir,
        title="Select maze file",
        filetypes=(("Maze files", "*.num"), ("All files", "*.*"))
    )
    root.destroy() # Close the Tkinter instance
    # print (f"Selected maze file: {file_path}")

    if not file_path:
        return None

    return file_path

def load_maze(filename):

    """Load maze from .num file and makes a dict in form {(x,y): "NESW"}
    max_y needed for rendering as pygame's y=0 is top of screen
    Removes newline and splits by space, converting to int"""

    walls = {}
    max_y = -1

    with open(filename, 'r') as f:
        for line in f:
            parts = [int(value) for value in line.strip().split()]
            x, y, n, e, s, w = parts
            nesw = f"{n}{e}{s}{w}"
            walls[(x, y)] = nesw
            if y > max_y:
                max_y = y
    
    # print (walls) # debug
    return walls, max_y

def load():
    maze_path = choose_maze_file()
    if maze_path:
        return load_maze(maze_path)
    else:
        print("No maze file selected.")
        return None