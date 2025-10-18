import math
import random

from collections import deque
import numpy as np
import torch

from constants import *
from path_calcs import *
from maze_loader import load_maze
from maze import Maze
from mouse import Mouse, Action
from environment import Environment

from model import Linear_QNet, QTrainer
# from helper import plot


class Agent(Mouse):
    def __init__(self, x, y, colour):
        super().__init__(x, y, colour)
        self.x = x
        self.y = y
        self.score = 0
        self.frame = 0

        self.n_games = 0
        self.epsilon = 0 # randomness
        self.gamma = 0.9 # discount rate
        self.memory = deque(maxlen=MAX_MEMORY) # popleft()
        self.model = Linear_QNet(11, 256, 3)
        self.trainer = QTrainer(self.model, lr=LR, gamma=self.gamma)

        self.waypoints = generate_turns(path)


    def generate_waypoints(self):
        self.waypoints = []

    def reset(self):
        super().reset() 
        self.score = 0
        self.frame = 0
        self.waypoints = generate_turns(path)

    def get_state(self):
        """
        Returns the RL state for the AIMouse.        
        # flatten next 5 waypoints(turns)
        # repeat goal coords if less than 5 waypoints remain
        # adjust state to include maze, goal, position, speed, and angle
        """

        if len(self.waypoints) < 5:
            self.waypoints += [self.waypoints[-1]]

        state = [
            self.waypoints[-5:],
            self.pos_x,
            self.pos_y,
            self.angle,
            self.speed
            ]

        return np.array(state, dtype=float)
    
    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done)) # popleft if MAX_MEMORY is reached

    def train_long_memory(self):
        if len(self.memory) > BATCH_SIZE:
            mini_sample = random.sample(self.memory, BATCH_SIZE) # list of tuples
        else:
            mini_sample = self.memory

        states, actions, rewards, next_states, dones = zip(*mini_sample)
        self.trainer.train_step(states, actions, rewards, next_states, dones)

    def train_short_memory(self, state, action, reward, next_state, done):
        self.trainer.train_step(state, action, reward, next_state, done)

    def get_action(self):
        """model outputs a binary array 
        [forward, right, left, backward, forwardright, forwardleft]
        """
        movement_signals = []

        self.epsilon = 80 - self.n_games
        final_move = [0,0,0,0,0,0]
        if random.randint(0, 200) < self.epsilon:
            move = random.randint(0, 5)
            final_move[move] = 1
        else:
            state0 = torch.tensor(self.state, dtype=torch.float)
            prediction = self.model(state0)
            move = torch.argmax(prediction).item()
            final_move[move] = 1        

        model_input = np.array(final_move)

        if model_input[0] == 1:
            movement_signals.append(Action.MOVE_FORWARD)
        if model_input[1] == 1:
            movement_signals.append(Action.TURN_RIGHT)
        if model_input[2] == 1:
            movement_signals.append(Action.TURN_LEFT)
        if model_input[3] == 1:
            movement_signals.append(Action.MOVE_BACKWARD)
        if model_input[4] == 1:
            movement_signals.append(Action.MOVE_FORWARD)
            movement_signals.append(Action.TURN_RIGHT)
        if model_input[5] == 1:
            movement_signals.append(Action.MOVE_FORWARD)
            movement_signals.append(Action.TURN_LEFT)

        return movement_signals



MAX_MEMORY = 100_000
BATCH_SIZE = 1000
LR = 0.001

def train():
    maze_params = load_maze("/Users/victorciobanu/Documents/Programming/Micro-Mouse/mazes/example4.num")
    walls_dict, max_y = maze_params
    environment = Environment(walls_dict, max_y)
    environment.maze.build_rewards(path, max_y)
    environment.add_mouse(Agent(x=0.375, y=max_y+0.375, colour=PINK))

    plot_scores = []
    plot_mean_scores = []
    total_score = 0
    record = 0


    while True:
        ## implement ticking

        # get old state
        state_old = agent.get_state()

        # get move
        final_move = agent.update(state_old)

        # perform move and get new state
        reward, done, score = agent.play_step(final_move)
        state_new = agent.get_state()

        # train short memory
        agent.train_short_memory(state_old, final_move, reward, state_new, done)

        # remember
        agent.remember(state_old, final_move, reward, state_new, done)

        if done:
            # train long memory, plot result
            agent.reset()
            agent.n_games += 1
            agent.train_long_memory()

            if score > record:
                record = score
                agent.model.save()

            print('Game', agent.n_games, 'Score', score, 'Record:', record)

            plot_scores.append(score)
            total_score += score
            mean_score = total_score / agent.n_games
            plot_mean_scores.append(mean_score)
            plot(plot_scores, plot_mean_scores)


if __name__ == '__main__':
    train()

