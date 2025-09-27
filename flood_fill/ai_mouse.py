import math
import random

from collections import deque
import numpy as np
import torch


from mouse import Mouse
from actions import Action

class AIMouse(Mouse):
    def __init__(self, x, y, walls, tile_size, colour, max_y, path=None):
        super().__init__(x, y, walls, tile_size, colour)
        self.x = x
        self.y = y
        self.tile_size = tile_size
        self.auto_mode = True
        self.max_y = max_y
        self.path = path
        self.reset()

    def reset(self):
        self.frame = 0
        self.pos_x = self.x * self.tile_size # Grid coords
        self.pos_y = self.y * self.tile_size # Grid coords
        self.active_path = self.path

    def update(self):
        self.frame += 1
        movement_signals = []

        # Reward gate check
        if self.active_path and self.rect.colliderect(self.active_path[0]):
            self.score += 10
            self.active_path.pop(0)

        if not self.active_path:
            self.score += 100
            self.reset()

        # Example: pretend model outputs a binary array [forward, right, left, backward]
        model_input = np.array([1, 1, 0, 0])  # forward + right at same time

        if model_input[0] == 1:
            movement_signals.append(Action.MOVE_FORWARD)
        if model_input[1] == 1:
            movement_signals.append(Action.TURN_RIGHT)
        if model_input[2] == 1:
            movement_signals.append(Action.TURN_LEFT)
        if model_input[3] == 1:
            movement_signals.append(Action.MOVE_BACKWARD)

        return movement_signals





     