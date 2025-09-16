import os
import math
import pygame

"""Maze format: [X Y N E S W] <-- each cell is separated with a newline"""


"""Constants"""
SCREEN_WIDTH = 700
SCREEN_HEIGHT = 700
TILE_SIZE = 40  # Adjust based on your maze size and screen resolution
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)

def load_maze(filename):

    """Load maze from .num file and makes a dict in form {(x,y): "NESW"}
    max_y needed for rendering as pygame's y=0 is top of screen
    Removes newline and splits by space, converting to int"""

    walls = {}
    max_y = -1  # Initialize max_y
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


"""Controllable mouse"""
class Mouse:
    def __init__(self, x, y, instructions=None):
        """x, y position in maze coordinates (not pixels) + size based on TILE_SIZE"""
        self.width = int(TILE_SIZE * 0.4)
        self.height = int(TILE_SIZE * 0.5)
        self.rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, self.width, self.height)
        self.impulse = 0.3
        self.instructions = instructions # for autonomous mice
        self.base_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.angle = -90
        self.speed = 0
        pygame.draw.rect(self.base_surface, GREEN, (0, 0, self.width, self.height))

    def move(self, speed, angle, walls):
        """Move the mouse and handle collisions"""
        self.angle = angle
        self.speed = speed
        dx, dy = self.angle_to_single_axis(speed, angle)
        if dx != 0:
            self.move_single_axis(dx, 0, walls)
        if dy != 0:
            self.move_single_axis(0, dy, walls)

    def move_single_axis(self, dx, dy, walls):
        self.rect.x += dx
        self.rect.y += dy
        for wall in walls:
            if self.rect.colliderect(wall):
                if dx > 0:
                    self.rect.right = wall.left
                if dx < 0:
                    self.rect.left = wall.right
                if dy > 0:
                    self.rect.bottom = wall.top
                if dy < 0:
                    self.rect.top = wall.bottom
    
    def angle_to_single_axis(self, speed, angle):
        """Convert speed and angle to dx, dy components with consistent magnitude"""
        rad = math.radians(angle)
        dx = speed * math.cos(rad)
        dy = speed * math.sin(rad)

        # Normalize to ensure consistent speed in all directions
        # Not sure why it works but the movement is way better this way
        length = math.hypot(dx, dy)
        if length > 0:
            dx = dx / length * abs(speed)
            dy = dy / length * abs(speed)


        return dx, dy

    def draw(self, surface):
        # Rotate the base surface
        rotated = pygame.transform.rotate(self.base_surface, -(self.angle+90))
        # Get the new rect and center it on the current position
        rotated_rect = rotated.get_rect(center=self.rect.center)
        surface.blit(rotated, rotated_rect)


"""Main game loop (adjust to incorporate external mice and default
to a keyboard-controlled mouse)

Also needs to become wheel impulse-based rather than frame-based for movement"""
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Maze Environment")
    clock = pygame.time.Clock()

    repo_root = os.getcwd() # Gets the current working directory
    maze_path = os.path.join(repo_root, "mazes", "blank.num")
    walls_dict, max_y = load_maze(maze_path)
    walls = build_walls(walls_dict, max_y)
    mouse = Mouse(0.3, max_y+0.3, None)  # Mouse starts near bottom-left corner, no instructions = keyboard control

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        if not mouse.instructions:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                mouse.angle -= 4
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                mouse.angle += 4
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                mouse.speed += mouse.impulse
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                mouse.speed -= mouse.impulse
            mouse.angle %= 360
            
        mouse.speed *= 0.9  # Simulate friction
        if abs(mouse.speed) < 0.05:
            mouse.speed = 0

        mouse.move(mouse.speed, mouse.angle, walls)

        screen.fill(BLACK)
        for wall in walls:
            pygame.draw.rect(screen, WHITE, wall)
        mouse.draw(screen)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()
