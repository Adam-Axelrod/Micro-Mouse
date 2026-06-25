"""The ONLY pygame module: drawing and an optional human-view throttle.

It never gates the simulation. Its ``pygame.time.Clock`` limits the *display*
refresh rate so a person can watch at a sensible speed; the underlying sim has
no idea it exists.
"""
from __future__ import annotations

import math
import pygame

from . import config
from .maze import Maze
from .mouse import MouseState


class Renderer:
    def __init__(self, maze: Maze):
        pygame.init()
        self.maze = maze
        self.screen = pygame.display.set_mode(maze.pixel_size)
        pygame.display.set_caption("Micro-Mouse")
        self.clock = pygame.time.Clock()        # display throttle ONLY

    def draw(self, mouse: MouseState, path=None, rays=None) -> None:
        # Let the window be closed cleanly.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.close()
                raise SystemExit

        self.screen.fill(config.COLOUR_BG)

        # Path polyline.
        if path:
            world = [self.maze.cell_to_world(c) for c in path]
            if len(world) > 1:
                pygame.draw.lines(self.screen, config.COLOUR_PATH, False, world, 2)

        # Goal cells.
        for g in self.maze.goal:
            gx, gy = self.maze.cell_to_world(g)
            r = config.TILE_SIZE * 0.3
            pygame.draw.rect(self.screen, config.COLOUR_GOAL, (gx - r, gy - r, 2 * r, 2 * r))

        # Walls.
        for p1, p2 in self.maze.segments:
            pygame.draw.line(self.screen, config.COLOUR_WALL, p1, p2, 2)

        # Sensor rays.
        if rays:
            for end in rays:
                pygame.draw.line(self.screen, config.COLOUR_RAY, (mouse.x, mouse.y), end, 1)

        # The mouse, drawn as a rotated rectangle so heading is visible.
        self._draw_mouse(mouse)

        pygame.display.flip()
        self.clock.tick(config.RENDER_FPS)

    def _draw_mouse(self, mouse: MouseState) -> None:
        # Draw the mouse as its ACTUAL collision shape: a circle of MOUSE_RADIUS.
        # This guarantees "what you see is what collides" — the old rectangle's
        # corners reached further than the collider, which looked like clipping.
        cx, cy = int(mouse.x), int(mouse.y)
        radius = int(config.MOUSE_RADIUS)
        pygame.draw.circle(self.screen, config.COLOUR_MOUSE, (cx, cy), radius)
        # Heading indicator: a short spoke from the centre to the rim.
        hx = cx + math.cos(mouse.heading) * config.MOUSE_RADIUS
        hy = cy + math.sin(mouse.heading) * config.MOUSE_RADIUS
        pygame.draw.line(self.screen, config.COLOUR_BG, (cx, cy), (int(hx), int(hy)), 2)

    def close(self) -> None:
        pygame.quit()
