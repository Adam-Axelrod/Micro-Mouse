import pygame

from maze import Maze
from mouse import Action
from constants import *

class Environment:

    def __init__(self, walls_dict, max_y, render=True):
        self.maze = Maze(walls_dict, max_y)
        self.render = render
        self.mice = []

    def add_mouse(self, mouse):
        self.mice.append(mouse)
    
    def reset_mouse(self, mouse):
        mouse.reset()

    def draw(self, screen):
        screen.fill(BLACK) #drawing functions

        for wall in self.maze.walls:
            pygame.draw.rect(screen, WHITE, wall)

        for mouse in self.mice:
            rotated = pygame.transform.rotate(mouse.base_surface, -(mouse.angle+90))
            rotated_rect = rotated.get_rect(center=mouse.rect.center)
            screen.blit(rotated, rotated_rect)

        pygame.display.flip()

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
            self.game_tick(clock)
            if self.render:
                self.draw(screen)

        pygame.quit()

    def game_tick(self, clock):
        # delta time needed to calculate movement based on time rather than frame
        dt = clock.tick(60) / 1000.0

        for mouse in self.mice:

            
            signals = mouse.get_action()
            for action in signals:
                if action == Action.TURN_LEFT: mouse.angle -= mouse.turnspeed
                if action == Action.TURN_RIGHT: mouse.angle += mouse.turnspeed
                if action == Action.MOVE_FORWARD: mouse.speed += mouse.impulse
                if action == Action.MOVE_BACKWARD: mouse.speed -= 0.85 * mouse.impulse

            mouse.update(dt, self.maze.walls)

