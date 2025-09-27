import math
import random

from collections import deque
import numpy as np
import torch


from mouse import Mouse
from actions import Action


MAX_MEMORY = 100_000
BATCH_SIZE = 1000
LR = 0.001


class Agent:
    def __init__(self):
        self.n_games = 0
        self.epsilon = 0 # Randomness
        self.gamma = 0 # Discount rate
        self.memory = deque(max_len=MAX_MEMORY)
        # otdo model, trainer

    def get_state(self):
        pass

    def remember(self):
        pass
    
    def train_long_mem(self):
        pass

    def train_short_mem(self):
        pass

    def get_action():
        pass


def train():
    pass

if __name__ == "main":
    train()

