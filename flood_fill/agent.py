import random

from collections import deque
import numpy as np
import pygame
import torch

from constants import *
from path_calcs import *
from maze_loader import load_maze
from mouse import Mouse, Action
from environment import Environment

from model import Linear_QNet, QTrainer
from helper import plot


class Agent(Mouse):
    def __init__(self, x, y, colour, max_y):
        super().__init__(x, y, colour)
        self.max_y = max_y
        self.score = 0
        self.n_games = 0
        self.epsilon = 0 # randomness
        self.gamma = 0.95 # discount rate
        self.memory = deque(maxlen=MAX_MEMORY) # popleft()
        self.model = Linear_QNet(14, 256, 6)
        self.trainer = QTrainer(self.model, lr=LR, gamma=self.gamma)

        self.waypoints = generate_turns(path)
        self.goal = self.waypoints[-1]

    # def generate_waypoints(self): for future maze solving
    #     self.waypoints = []

    def reset(self):
        super().reset() 
        self.score = 0
        self.waypoints = generate_turns(path)

    def get_state(self):
        """
        Returns the RL state for the AIMouse.        
        # flatten next 5 waypoints(turns)
        # repeat goal coords if less than 5 waypoints remain
        # adjust state to include maze, goal, position, speed, and angle
        """

        wp = list(self.waypoints[:5])  # last up to 5
        if len(wp) < 5 and len(self.waypoints) > 0:
            wp = wp + [self.waypoints[-1]] * (5 - len(wp))

        flat_wp = []
        for w in wp:
            flat_wp.extend([w[0], w[1]])

        state = [
            *flat_wp,
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

    def get_action(self, state):
        """model outputs a binary array 
        [forward, right, left, backward, forwardright, forwardleft]
        """
        movement_signals = []

        # self.epsilon = 80 - self.n_games
        self.epsilon = max(5, 80 * np.exp(-0.01 * self.n_games))
        final_move = [0,0,0,0,0,0]
        if random.randint(0, 200) < self.epsilon:
            move = random.randint(0, 5)
            final_move[move] = 1
        else:
            state0 = torch.tensor(state, dtype=torch.float)
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

        return movement_signals, final_move
    
    def update(self, dt, walls, signals):
        super().update(dt, walls, signals)
        if self.waypoints:
            waypoint_x, waypoint_y = self.waypoints[0] # Get the next waypoint's grid coordinates
            target_size = TILE_SIZE // 2 # Create a target rect for the waypoint to check for collision.
            target_x = waypoint_x * TILE_SIZE + (TILE_SIZE - target_size) // 2
            target_y = (self.max_y - waypoint_y) * TILE_SIZE + (TILE_SIZE - target_size) // 2
            waypoint_rect = pygame.Rect(target_x, target_y, target_size, target_size)
            if self.rect.colliderect(waypoint_rect):
                self.waypoints.pop(0) # Remove the waypoint hit

MAX_MEMORY = 50_000
BATCH_SIZE = 256
LR = 0.002

def train():
    maze_params = load_maze("/Users/victorciobanu/Documents/Programming/Micro-Mouse/mazes/example4.num")
    walls_dict, max_y = maze_params
    environment = Environment(walls_dict, max_y)
    environment.maze.build_rewards(path, max_y)
    environment.add_mouse(Agent(x=0.375, y=max_y+0.375, colour=RED, max_y=max_y))
    agent = environment.mice[0]

    plot_scores = []
    plot_mean_scores = []
    total_score = 0
    record = 0
    frame = 0

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Maze Environment")
    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()

        dt = clock.tick(60) / 1000.0
        frame += 1

        state_old = agent.get_state() # get old state

        movement_signals, action_array = agent.get_action(state_old) # get move

        agent.update(dt, environment.maze.walls, movement_signals)

        ## reward calcs
        done = False
        reward = -0.1
        if environment.maze.reward_gates and agent.rect.colliderect(environment.maze.reward_gates[0]):
            reward += 50
            environment.maze.reward_gates.pop(0)
        if agent.collided:
            reward -= 1
            done = True
        if (agent.pos_x, agent.pos_y) == agent.goal:
            reward += 5000
            done = True
        if frame > 50000 // len(environment.maze.reward_gates):
            print(frame)
            print(100000 // len(environment.maze.reward_gates))
            done = True
        agent.score += reward
        score = agent.score


        state_new = agent.get_state()

        agent.train_short_memory(state_old, action_array, reward, state_new, done) # train short memory

        agent.remember(state_old, action_array, reward, state_new, done) # remember

        if done: # train long memory, plot result
            frame = 0
            agent.reset()
            environment.maze.build_rewards(path, max_y) # Reset reward gates
            agent.n_games += 1
            agent.train_long_memory()

            if agent.score > record:
                record = score
                agent.model.save()

            print('Game', agent.n_games, 'Score', score, 'Record:', record)

            plot_scores.append(score)
            total_score += score
            mean_score = total_score / agent.n_games
            plot_mean_scores.append(mean_score)
            plot(plot_scores, plot_mean_scores)

        environment.draw(screen)


if __name__ == '__main__':
    train()
