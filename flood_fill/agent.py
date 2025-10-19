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
        self.model = Linear_QNet(18, 512, 4) # 18 inputs: 8 rays + 6 waypoints + 4 agent state
        self.trainer = QTrainer(self.model, lr=LR, gamma=self.gamma)

        self.waypoints = generate_turns(path)
        self.goal = self.waypoints[-1]

    # def generate_waypoints(self): for future maze solving
    #     self.waypoints = []

    def reset(self):
        super().reset() 
        self.score = 0
        self.waypoints = generate_turns(path)
        self.collided = False

        jitter = TILE_SIZE * 0.1 # e.g., 5% of a tile size
        self.pos_x += random.uniform(-jitter, jitter)
        self.pos_y += random.uniform(-jitter, jitter)
        self.rect.x = int(self.pos_x)
        self.rect.y = int(self.pos_y)

    def cast_ray(self, walls, angle_degrees, max_distance=10.0):
        """
        Cast a ray from the agent's position in a given direction.
        Returns normalized distance to nearest wall (0-1, where 1 = max_distance).

        Args:
            walls: List of pygame.Rect wall objects
            angle_degrees: Absolute angle in degrees to cast ray
            max_distance: Maximum ray distance in tile units
        """
        # Convert angle to radians and get direction vector
        angle_rad = np.radians(angle_degrees)
        dx = np.cos(angle_rad)
        dy = -np.sin(angle_rad)  # Negative because pygame y increases downward

        # Ray origin (agent center)
        ray_x = self.pos_x + self.rect.width / 2
        ray_y = self.pos_y + self.rect.height / 2

        # Step along ray in small increments
        max_distance_pixels = max_distance * TILE_SIZE
        step_size = 2  # pixels per step
        num_steps = int(max_distance_pixels / step_size)

        for step in range(1, num_steps + 1):
            test_x = ray_x + dx * step * step_size
            test_y = ray_y + dy * step * step_size

            # Create a small point rect for collision detection
            point_rect = pygame.Rect(test_x - 1, test_y - 1, 2, 2)

            # Check collision with any wall
            for wall in walls:
                if point_rect.colliderect(wall):
                    distance = step * step_size
                    return distance / max_distance_pixels  # Normalize to 0-1

        # No wall found within max_distance
        return 1.0

    def get_state(self, walls):
        """
        Returns the RL state for the AIMouse.
        Includes:
        - 8 ray cast distances (relative to agent's orientation)
        - 3 waypoint coordinates (reduced from 5 to keep state manageable)
        - Agent position, angle, and speed
        """

        # Ray casting in 8 directions relative to agent's heading
        # 0° = forward, 90° = right, 180° = backward, 270° = left
        ray_angles = [0, 45, 90, 135, 180, 225, 270, 315]  # Relative angles
        ray_distances = []

        for relative_angle in ray_angles:
            absolute_angle = (self.angle + relative_angle) % 360
            distance = self.cast_ray(walls, absolute_angle, max_distance=5.0)
            ray_distances.append(distance)

        # Waypoint information (use 3 waypoints for balance)
        wp = list(self.waypoints[:3])
        if len(wp) < 3 and len(self.waypoints) > 0:
            wp = wp + [self.waypoints[-1]] * (3 - len(wp))

        flat_wp = []
        for w in wp:
            flat_wp.extend([w[0], w[1]])

        # Agent state
        agent_grid_x = self.pos_x / TILE_SIZE
        agent_grid_y = self.max_y - (self.pos_y / TILE_SIZE)

        state = [
            *ray_distances,      # 8 values: distances to walls in 8 directions
            *flat_wp,            # 6 values: next 3 waypoints
            agent_grid_x,        # 1 value: x position
            agent_grid_y,        # 1 value: y position
            (self.angle % 360) / 180 - 1,  # 1 value: normalized angle
            self.speed           # 1 value: speed
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
        [forward, backward, left, right]
        """
        movement_signals = []

        # Slower epsilon decay to maintain exploration longer
        self.epsilon = max(5, 200 * np.exp(-0.015 * self.n_games))
        final_move = [0,0,0,0]
        
        if random.randint(0, 200) < self.epsilon:
            # Random exploration - choose either movement OR turning, not both
            action_type = random.choice(['move', 'turn'])
            if action_type == 'move':
                move_choice = random.randint(0, 1)
                final_move[move_choice] = 1
            else:
                turn_choice = random.randint(2, 3)
                final_move[turn_choice] = 1
        else:
            state0 = torch.tensor(state, dtype=torch.float)
            prediction = self.model(state0)
            
            # Choose the single best action instead of forcing multiple actions
            best_action = torch.argmax(prediction).item()
            final_move[best_action] = 1

        if final_move[0]: movement_signals.append(Action.MOVE_FORWARD)
        if final_move[1]: movement_signals.append(Action.MOVE_BACKWARD)
        if final_move[2]: movement_signals.append(Action.TURN_LEFT)
        if final_move[3]: movement_signals.append(Action.TURN_RIGHT)

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

MAX_MEMORY = 100_000
BATCH_SIZE = 256  # Smaller batch size for more frequent updates
LR = 0.001  # Lower learning rate for stability

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
    frame_budget = 250

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

        state_old = agent.get_state(environment.maze.walls) # get old state

        movement_signals, action_array = agent.get_action(state_old) # get move

        agent.update(dt, environment.maze.walls, movement_signals)

        ## reward calcs
        done = False
        reward = 0

        # Reward shaping: reward agent for getting closer to the next waypoint
        if agent.waypoints:
            waypoint_x, waypoint_y = agent.waypoints[0]
            # Convert waypoint to pixel coordinates
            target_x = waypoint_x * TILE_SIZE + TILE_SIZE / 2
            target_y = (max_y - waypoint_y) * TILE_SIZE + TILE_SIZE / 2

            # State indices: [8 rays, 6 waypoints, x, y, angle, speed] = indices 14, 15 for x, y
            dist_old = np.hypot(state_old[14]*TILE_SIZE - target_x, (max_y - state_old[15])*TILE_SIZE - target_y)
            dist_new = np.hypot(agent.pos_x - target_x, agent.pos_y - target_y)
            reward += (dist_old - dist_new) * 0.005 # Much smaller coefficient

        if environment.maze.reward_gates: # reward for being on the right path
            first_gate = environment.maze.reward_gates[0]
            if agent.rect.colliderect(first_gate):
                reward += 50 # Larger reward for hitting a gate
                frame_budget += 250
                environment.maze.reward_gates.pop(0)

        if agent.collided: # wall collision penalty
            reward -= 1
            done = True

        if (agent.pos_x, agent.pos_y) == agent.goal: # big reward for winning
            reward += 2000
            done = True

        # Encourage forward movement, discourage excessive turning
        if agent.speed < 0.01:  # Only penalize if truly stationary
            reward -= 0.5
        
        # Add small reward for forward movement to discourage spinning
        if Action.MOVE_FORWARD in movement_signals:
            reward += 0.025

        if frame > frame_budget: # time cutoff (per-gate budget)
            done = True

        # clamp non-terminal rewards to reduce variance
        if not done or ((agent.pos_x, agent.pos_y) != agent.goal):
            reward = float(np.clip(reward, -50, 50))


        agent.score += reward
        score = agent.score

        state_new = agent.get_state(environment.maze.walls)

        agent.train_short_memory(state_old, action_array, reward, state_new, done) # train short memory

        agent.remember(state_old, action_array, reward, state_new, done) # remember

        if done: # train long memory, plot result

            # debug
            print(frame)

            frame = 0
            frame_budget = 250
            agent.reset()
            environment.maze.build_rewards(path, max_y) # Reset reward gates
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

        environment.draw(screen)


if __name__ == '__main__':
    train()
