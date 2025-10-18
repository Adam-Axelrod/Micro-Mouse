import os
import tkinter as tk
from tkinter import filedialog

def get_file():
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

    if not file_path:
        return None

    return file_path

def load_maze(filename=None):
    if filename == None:  
        filename = get_file()
        if not filename:
            print("No maze file selected.")
            return None

    """Load maze from .num file and makes a dict in form {(x,y): "NESW"}
    max_y needed for rendering as pygame's y=0 is top of screen
    Removes newline and splits by space, converting to int"""

    walls_dict = {}
    max_y = -1

    with open(filename, 'r') as f:
        for line in f:
            parts = [int(value) for value in line.strip().split()]
            x, y, n, e, s, w = parts
            nesw = f"{n}{e}{s}{w}"
            walls_dict[(x, y)] = nesw
            if y > max_y:
                max_y = y
    
    # print (walls_dict) # debug
    return walls_dict, max_y
