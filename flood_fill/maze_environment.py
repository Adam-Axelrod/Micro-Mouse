import pygame
import sys

import maze_loader
from mouse import Mouse # player
from auto_mouse import AutoMouse # auto

"""
Maze format: [X Y N E S W] <-- each cell is separated with a newline
Set directory to Micro-Mouse and then use 
"python3 flood_fill/maze_environment.py" to run from terminal
"""

"""Constants"""
SCREEN_WIDTH = 700
SCREEN_HEIGHT = 700
TILE_SIZE = 40  # Adjust based on your maze size and screen resolution
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
PINK = (255, 0, 255)


def build_walls(walls, max_y):

    """Convert maze dict to list of pygame.Rect wall objects for collision detection
    pygame.Rect starts at top-left then specifies width and height of the line"""

    wall_objects = []

    for (x, y), wall_info in walls.items():
        render_y = max_y - y        
        if int(wall_info[0]): #n
            wall_objects.append(pygame.Rect(x * TILE_SIZE, render_y * TILE_SIZE, TILE_SIZE, 2))
        if int(wall_info[1]): #e
            wall_objects.append(pygame.Rect((x + 1) * TILE_SIZE, render_y * TILE_SIZE, 2, TILE_SIZE))
        if int(wall_info[2]): #s
            wall_objects.append(pygame.Rect(x * TILE_SIZE, (render_y + 1) * TILE_SIZE, TILE_SIZE, 2))
        if int(wall_info[3]): #w
            wall_objects.append(pygame.Rect(x * TILE_SIZE, render_y * TILE_SIZE, 2, TILE_SIZE))
    
    return wall_objects


def coords_to_instructions(path=None):
    """Convert path coordinates to simple waypoint instructions. ignore this lol"""
    if path is None:
        path = [(0, 1), (1, 1), (2, 1), (2, 2), (3, 2),
                   (3, 3), (4, 3), (4, 4), (3, 4), (3, 5),
                   (2, 5), (2, 6), (1, 6), (1, 7), (1, 8),
                   (1, 9), (1, 10), (1, 11), (1, 12), (1, 13),
                   (1, 14), (0, 14), (0, 15), (1, 15), (2, 15),
                   (3, 15), (4, 15), (5, 15), (6, 15), (7, 15),
                   (7, 14), (8, 14), (8, 13), (9, 13), (9, 14),
                   (10, 14), (10, 13), (11, 13), (11, 12), (11, 11),
                   (11, 10), (11, 9), (11, 8), (10, 8), (10, 7),
                   (9, 7), (9, 6), (8, 6), (8, 5), (7, 5), (6, 5),
                   (6, 6), (7, 6), (7, 7)]
    return path[1:]  # Skip starting position


def main(mice):

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Maze Environment")
    clock = pygame.time.Clock()    

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Assign postive reward for higher speed in RL context 
        for mouse in mice:
            mouse.mouse_input()
            mouse.angle %= 360
            mouse.speed *= 0.9  # Simulate friction
            if abs(mouse.speed) < 0.05:
                mouse.speed = 0   
            mouse.move(mouse.speed, mouse.angle)

        screen.fill(BLACK)

        for wall in mice[0].walls:
            pygame.draw.rect(screen, WHITE, wall)

        for mouse in mice:
            mouse.draw(screen)
            
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":

    maze = maze_loader.load()
    if not maze:
        print("No maze file selected. Exiting.")
        sys.exit()
    else:
        walls_dict, max_y = maze
    walls = build_walls(walls_dict, max_y)
    instructions = coords_to_instructions()

    mice = []

    # Player controlled
    mouse = Mouse(
        x=0.375,
        y=max_y,
        walls=walls,
        colour=PINK
        ) 

    # Green auto mouse
    automouse = AutoMouse(
        x=0.375,
        y=max_y+0.375,
        walls=walls,
        colour=GREEN,
        max_y=max_y,
        waypoints=instructions
    )

    mice = [mouse, automouse]
    main(mice)


    # goal_pos = maze.width // 2 - 1, maze.height // 2 - 1
    # maze.set_goal_pos(goal_pos)


    # example path for maze 4
    # [(0, 1), (1, 1), (2, 1), (2, 2), (3, 2), (3, 3), (4, 3), (4, 4), (3, 4), (3, 5), (2, 5), (2, 6), (1, 6), (1, 7), (1, 8), (1, 9), (1, 10), (1, 11), (1, 12), (1, 13), (1, 14), (0, 14), (0, 15), (1, 15), (2, 15), (3, 15), (4, 15), (5, 15), (6, 15), (7, 15), (7, 14), (8, 14), (8, 13), (9, 13), (9, 14), (10, 14), (10, 13), (11, 13), (11, 12), (11, 11), (11, 10), (11, 9), (11, 8), (10, 8), (10, 7), (9, 7), (9, 6), (8, 6), (8, 5), (7, 5), (6, 5), (6, 6), (7, 6), (7, 7)]