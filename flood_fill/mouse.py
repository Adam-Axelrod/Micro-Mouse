from enum import Enum, auto
import math
import pygame
from constants import *

class Action(Enum):
    TURN_LEFT = auto()
    TURN_RIGHT = auto()
    MOVE_FORWARD = auto()
    MOVE_BACKWARD = auto()

"""General Mouse Class"""
class Mouse:

    impulse = 20 # Momentum change from key press
    turnspeed = 5
    
    def __init__(self, x, y, colour):
        self.width = int(TILE_SIZE * 0.3) # Cell size
        self.height = int(TILE_SIZE * 0.5) # Cell size
        self.pos_x = x * TILE_SIZE # Grid coords
        self.pos_y = y * TILE_SIZE # Grid coords

        self.angle = -90 # Start facing up
        self.speed = 0 # Movement per frame
        self.collided = False # Collision with wall check
        self.frame = 0
        self.score = 0

        self.colour = colour
        self.rect = pygame.Rect(self.pos_x, self.pos_y, self.width, self.height) # Draws mouse
        self.base_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.rect(self.base_surface, self.colour, (0, 0, self.width, self.height))

    def reset(self):
        self.pos_x = self.rect.x 
        self.pos_y = self.rect.y
        self.angle = -90 # Start facing up
        self.speed = 0 # Movement per frame
        self.collided = False # Collision with wall check

    def get_action(self):
        signals = []
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

        return signals

    def update(self, dt, walls):
        """Advance physics and resolve collisions using the provided walls list."""
        self.angle %= 360 #normalise
        self.speed *= 0.96 ** (dt * 100) #friction
        if abs(self.speed) < 0.05:
            self.speed = 0

        self.collided = False

        rad = math.radians(self.angle) # compute movement components
        dx = self.speed * math.cos(rad)
        dy = self.speed * math.sin(rad)

        length = math.hypot(dx, dy) # preserve magnitude consistency (idk why but its needed)
        if length > 0:
            dx = dx / length * abs(self.speed)
            dy = dy / length * abs(self.speed)

        dx *= dt
        dy *= dt

        if dx != 0: #x axis movement / collision
            self.pos_x += dx
            self.rect.x = int(self.pos_x)

            for wall in walls:
                if self.rect.colliderect(wall):
                    self.collided = True
                    if dx > 0:
                        self.rect.right = wall.left
                    else:
                        self.rect.left = wall.right
                    self.pos_x = self.rect.x
                    break

        if dy != 0: #x axis movement / collision
            self.pos_y += dy
            self.rect.y = int(self.pos_y)

            for wall in walls:
                if self.rect.colliderect(wall):
                    self.collided = True
                    if dy > 0:
                        self.rect.bottom = wall.top
                    else:
                        self.rect.top = wall.bottom
                    self.pos_y = self.rect.y
                    break

        if self.collided:
            self.speed *= 0.75  # Lose most speed on collision
