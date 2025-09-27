import pygame
import sys

import maze_loader
from mouse import Mouse # player
from auto_mouse import AutoMouse # auto
from ai_mouse import AIMouse # deep learning

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
RED = (255, 0, 0)

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

class Maze:
    def __init__(self, walls, max_y, mice):
        self.walls = walls
        self.max_y = max_y
        self.mice = mice

    def game_loop(self):
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
            for mouse in self.mice:
                mouse.mouse_input()
                mouse.angle %= 360
                mouse.speed *= 0.9  # Simulate friction
                if abs(mouse.speed) < 0.05:
                    mouse.speed = 0   
                mouse.step(mouse.speed, mouse.angle)

            screen.fill(BLACK) #drawing functions

            for wall in self.walls:
                pygame.draw.rect(screen, WHITE, wall)

            for mouse in self.mice:
                mouse.draw(screen)

            pygame.display.flip()
            clock.tick(60)

        pygame.quit()
        

    def build_walls(walls_dict, max_y):

        """Convert maze dict to list of pygame.Rect wall objects for collision detection
        pygame.Rect starts at top-left then specifies width and height of the line"""

        walls = []

        for (x, y), wall_info in walls_dict.items():
            render_y = max_y - y        
            if int(wall_info[0]): #n
                walls.append(pygame.Rect(x * TILE_SIZE, render_y * TILE_SIZE, TILE_SIZE, 2))
            if int(wall_info[1]): #e
                walls.append(pygame.Rect((x + 1) * TILE_SIZE, render_y * TILE_SIZE, 2, TILE_SIZE))
            if int(wall_info[2]): #s
                walls.append(pygame.Rect(x * TILE_SIZE, (render_y + 1) * TILE_SIZE, TILE_SIZE, 2))
            if int(wall_info[3]): #w
                walls.append(pygame.Rect(x * TILE_SIZE, render_y * TILE_SIZE, 2, TILE_SIZE))
        
        return walls

    def build_rewards(path, max_y):
        """Create reward gate Rects along the given path, similar to waypoint logic (will disappear when hit)"""
        reward_gates = []
        for (x, y) in path:
            render_y = max_y - y
            reward_size = TILE_SIZE // 1.5
            reward_x = x * TILE_SIZE + (TILE_SIZE - reward_size) // 2
            reward_y = render_y * TILE_SIZE + (TILE_SIZE - reward_size) // 2
            reward_gates.append(pygame.Rect(reward_x, reward_y, reward_size, reward_size))
        return reward_gates
    

def mice_factory(max_y, walls, reward_gates):

    mice = []

    # Pink player mouse
    mouse = Mouse(
        x=0.375,
        y=max_y+0.375,
        walls=walls,
        tile_size=TILE_SIZE,
        colour=PINK
        ) 
    
    # Green auto mouse
    automouse = AutoMouse(
        x=0.375,
        y=max_y+0.375,
        walls=walls,
        tile_size=TILE_SIZE,
        colour=GREEN,
        max_y=max_y,
        path=path
    )

    # Red deep learning mouse
    aimouse = AIMouse(
        x=0.375,
        y=max_y+0.375,
        walls=walls,
        tile_size=TILE_SIZE,
        colour=GREEN,
        max_y=max_y,
        path=reward_gates
    )

    mice.append(mouse)
    mice.append(automouse)
    # mice.append(aimouse)

    return mice


def main():

    maze_params = maze_loader.load()
    if maze_params is None:
        print("No maze file selected.")  # optional for logging
        sys.exit(0)

    walls_dict, max_y = maze_params
    walls = Maze.build_walls(walls_dict, max_y)
    reward_gates = Maze.build_rewards(path, max_y)
    mice = mice_factory(max_y, walls, reward_gates)
    maze = Maze(walls, max_y, mice)
    maze.game_loop()

if __name__ == "__main__":
    main()

