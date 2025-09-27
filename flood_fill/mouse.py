import math
import pygame
from actions import Action

"""General Mouse Class"""
class Mouse:
    def __init__(self, x, y, walls, tile_size, colour):
        self.auto_mode = False # Default to manual control
        self.walls = walls # Drawn walls between cells
        self.tile_size = tile_size
        self.width = int(self.tile_size * 0.3) # Cell size
        self.height = int(self.tile_size * 0.5) # Cell size
        self.pos_x = x * self.tile_size # Grid coords
        self.pos_y = y * self.tile_size # Grid coords
        self.impulse = 0.3 # Momentum change from key press
        self.angle = -90 # Start facing up
        self.speed = 0 # Movement per frame
        self.collided = False # Collision with wall check
        self.score = 0

        self.colour = colour
        self.rect = pygame.Rect(self.pos_x, self.pos_y, self.width, self.height) # Draws mouse
        self.base_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.rect(self.base_surface, self.colour, (0, 0, self.width, self.height))

    def mouse_input(self):
        signals = []
        if not self.auto_mode:
            # Manual keyboard control
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                signals.append(Action.TURN_LEFT)
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                signals.append(Action.TURN_RIGHT)
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                signals.append(Action.MOVE_FORWARD)
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                signals.append(Action.MOVE_BACKWARD)

        else:
            # Autonomous mouse (AI or AutoMouse)
            signals = self.update()

        for action in signals:
            match action:
                case Action.TURN_LEFT:
                    self.angle -= 5
                case Action.TURN_RIGHT:
                    self.angle += 5
                case Action.MOVE_FORWARD:
                    self.speed += 1.5 * self.impulse
                case Action.MOVE_BACKWARD:
                    self.speed -= self.impulse

    def step(self, speed, angle):

        """Move mouse with collision detection"""

        self.angle = angle
        self.speed = speed
        self.collided = False
        dx, dy = self.angle_to_single_axis(speed, angle)



        if dx != 0: # x axis movement
            self.pos_x += dx
            self.rect.x = int(self.pos_x)

            for wall in self.walls:
                if self.rect.colliderect(wall):
                    self.collided = True
                    if dx > 0:
                        self.rect.right = wall.left
                        self.pos_x = self.rect.x
                    elif dx < 0:
                        self.rect.left = wall.right
                        self.pos_x = self.rect.x

        if dy != 0: # y axis movement
            self.pos_y += dy
            self.rect.y = int(self.pos_y)
            for wall in self.walls:
                if self.rect.colliderect(wall):
                    self.collided = True
                    if dy > 0:
                        self.rect.bottom = wall.top
                        self.pos_y = self.rect.y
                    elif dy < 0:
                        self.rect.top = wall.bottom
                        self.pos_y = self.rect.y



        if self.collided: 
            self.score = max(0, self.score - 1)
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
        if length > 0: #??
            dx = dx / length * abs(speed)
            dy = dy / length * abs(speed)

        return dx, dy

    def draw(self, surface):

        """Drawing function"""

        rotated = pygame.transform.rotate(self.base_surface, -(self.angle+90))
        rotated_rect = rotated.get_rect(center=self.rect.center)
        surface.blit(rotated, rotated_rect)

