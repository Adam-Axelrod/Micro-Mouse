import pygame

from constants import TILE_SIZE

class Maze:

    def __init__(self, walls_dict, max_y):
        self.max_y = max_y
        self.walls = self.build_walls(walls_dict, self.max_y)

    def build_walls(self, walls_dict, max_y):

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
    
