import math
import pygame
import maze_loader

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
    def __init__(self, x, y):

        """x, y position in maze coordinates (not pixels) + size based on TILE_SIZE"""

        self.width = int(TILE_SIZE * 0.3)
        self.height = int(TILE_SIZE * 0.5)
        self.pos_x = x * TILE_SIZE
        self.pos_y = y * TILE_SIZE
        self.rect = pygame.Rect(self.pos_x, self.pos_y, self.width, self.height)
        self.base_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.impulse = 0.3        
        self.angle = -90
        self.speed = 0
        pygame.draw.rect(self.base_surface, GREEN, (0, 0, self.width, self.height))

    def move(self, speed, angle, walls):

        """Move mouse with collision detection"""

        self.angle = angle
        self.speed = speed
        dx, dy = self.angle_to_single_axis(speed, angle)
        collided = False

        if dx != 0: # x axis movement
            self.pos_x += dx
            self.rect.x = int(self.pos_x)
            for wall in walls:
                if self.rect.colliderect(wall):
                    collided = True
                    if dx > 0:
                        self.rect.right = wall.left
                        self.pos_x = self.rect.x
                    elif dx < 0:
                        self.rect.left = wall.right
                        self.pos_x = self.rect.x

        if dy != 0: # y axis movement
            self.pos_y += dy
            self.rect.y = int(self.pos_y)
            for wall in walls:
                if self.rect.colliderect(wall):
                    collided = True
                    if dy > 0:
                        self.rect.bottom = wall.top
                        self.pos_y = self.rect.y
                    elif dy < 0:
                        self.rect.top = wall.bottom
                        self.pos_y = self.rect.y

        if collided: 
            # Assign negative reward in RL context
            self.speed *= 0.75  # Lose most speed on collision

    def angle_to_single_axis(self, speed, angle):

        """Convert speed and angle to dx, dy components with consistent magnitude
        Need to understand the hypotenuse normalization better / why it smooths it out"""

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
        """Draw the mouse on the given surface with rotation"""
        rotated = pygame.transform.rotate(self.base_surface, -(self.angle+90))
        rotated_rect = rotated.get_rect(center=self.rect.center)
        surface.blit(rotated, rotated_rect)


def main(mouse=None):
    maze = maze_loader.load()
    if not maze:
        print("No maze file selected. Exiting.")
        return
    else:
        walls_dict, max_y = maze

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Maze Environment")
    clock = pygame.time.Clock()    
    walls = build_walls(walls_dict, max_y)

    if not mouse:
        mouse = Mouse(0.375, max_y+0.375)  # Mouse starts near bottom-left corner

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        player_control = True  # Set to False for autonomous control
        if player_control:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                mouse.angle -= 5
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                mouse.angle += 5
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                mouse.speed += 1.5*mouse.impulse
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                mouse.speed -= mouse.impulse
            mouse.angle %= 360
        
        if not player_control:
            # automated_mouse.mouse.step_through_path(position)
            pass


        # Assign postive reward for higher speed in RL context

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
