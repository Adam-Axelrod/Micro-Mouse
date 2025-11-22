import random

from collections import deque
import numpy as np
import pygame
import torch
import psutil, os


from constants import *
from path_calcs import *
from maze_loader import load_maze
from mouse import Mouse, Action
from environment import Environment

from model import Linear_QNet, QTrainer
from helper import plot


def log_memory(): # trying to debug freezes down the line
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / (1024 ** 2)  # MB
    print(f"[MEM] Resident memory: {mem:.2f} MB")

MAX_MEMORY = 50_000
BATCH_SIZE = 256  # Smaller batch for more frequent updates
LR = 0.0005  # Lower learning rate for stability

class Agent(Mouse):
    def __init__(self, x, y, colour, max_y):
        super().__init__(x, y, colour)
        self.max_y = max_y
        self.score = 0
        self.n_games = 0
        self.epsilon = 0 # randomness
        self.gamma = 0.95 # discount rate - higher for better long-term planning
        self.memory = deque(maxlen=MAX_MEMORY) # popleft()
        self.model = Linear_QNet(16, 512, 4) # 18 inputs: 8 rays + 6 waypoints + 2 agent state
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
        dy = np.sin(angle_rad)  # Pygame y increases downward, so no negative needed

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

        # Convert waypoints to relative positions from agent
        agent_grid_x = self.pos_x / TILE_SIZE
        agent_grid_y = self.max_y - (self.pos_y / TILE_SIZE)

        flat_wp = []
        for w in wp:
            # Relative position: waypoint - agent position
            relative_x = w[0] - agent_grid_x
            relative_y = w[1] - agent_grid_y
            flat_wp.extend([relative_x, relative_y])

        state = [
            *ray_distances,      # 8 values: distances to walls in 8 directions
            *[x / self.max_y for x in flat_wp], # 6 values: next 3 waypoints (normalized)
            # agent_grid_x,        # 1 value: x position
            # agent_grid_y,        # 1 value: y position
            (self.angle % 360) / 180 - 1,  # 1 value: normalized angle
            self.speed / 100.0   # 1 value: speed (normalized, assuming max ~100)
            ]

        return np.array(state, dtype=float)
    
    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done)) # popleft if MAX_MEMORY is reached

    def train_long_memory(self):
        # Only train if we have enough diverse experiences
        if len(self.memory) < BATCH_SIZE:
            return

        # Prioritized + recency-weighted sampling
        memories = list(self.memory)
        rewards = [abs(m[2]) for m in memories]  # reward magnitude
        indices = np.arange(len(memories))

        # Combine priority (reward²) and recency bias (later entries weighted higher)
        priorities = np.array([(r + 1.0) ** 2 for r in rewards])
        recency = np.linspace(0.5, 1.0, len(memories))  # 0.5x weight for oldest, full for newest
        combined = priorities * recency
        probabilities = combined / combined.sum()

        # Sample with replacement using combined probabilities
        sampled_idx = np.random.choice(indices, size=BATCH_SIZE, p=probabilities, replace=True)
        mini_sample = [memories[i] for i in sampled_idx]

        states, actions, rewards, next_states, dones = zip(*mini_sample)
        self.trainer.train_step(states, actions, rewards, next_states, dones)

    def train_short_memory(self, state, action, reward, next_state, done):
        self.trainer.train_step(state, action, reward, next_state, done)

    def get_action(self, state):
        """model outputs a binary array 
        [forward, backward, left, right]
        """
        movement_signals = []

        # VERY aggressive epsilon - maintain 50% exploration indefinitely
        # Decays slowly from 100% to 50% over 500 games
        self.epsilon = max(15, 100 - (self.n_games * 0.125))
        final_move = [0,0,0,0]
        
        if random.randint(0, 100) < self.epsilon:
            # AGGRESSIVE exploration - heavily favor turning to discover alternate paths
            action_type = random.choices(['move', 'turn'], weights=[0.8, 0.2])[0]
            if action_type == 'move':
                # Strongly prefer forward over backward
                move_choice = random.choices([0, 1], weights=[0.95, 0.05])[0]
                final_move[move_choice] = 1
            else:
                # Equal chance of left or right turn
                turn_choice = random.randint(2, 3)
                final_move[turn_choice] = 1
        else:
            state0 = torch.tensor(state, dtype=torch.float)
            prediction = self.model(state0)

            # Add noise to Q-values for continued exploration during exploitation
            # This prevents getting stuck in deterministic policies
            noise = torch.randn_like(prediction) * 0.15  # noise
            noisy_prediction = prediction + noise

            # Choose the best action from noisy predictions
            best_action = torch.argmax(noisy_prediction).item()
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
    frame_budget = 200  # Generous time to explore maze

    gates_hit = 0  # Track cumulative gates hit in current episode
    dist_influence = 0
    frame_decay = 0
    speed_influence = 0

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

        if environment.maze.reward_gates: # reward shaping (dist to gate)
            # Get the center of the next reward gate
            first_gate = environment.maze.reward_gates[0]
            target_x = first_gate.centerx
            target_y = first_gate.centery

            # Calculate distance from agent center to gate center
            agent_center_x = agent.pos_x + agent.rect.width / 2
            agent_center_y = agent.pos_y + agent.rect.height / 2

            distance_to_gate = np.hypot(agent_center_x - target_x, agent_center_y - target_y)
            distance_in_tiles = distance_to_gate / TILE_SIZE

            # Exponential distance penalty - only applies if > 2.5 tiles away
            if distance_in_tiles > 2:
                # Exponential penalty: -k * (e^((d-2.5)/scale) - 1)
                # Gets much worse as agent strays further from optimal path
                distance_penalty = -0.25 * (np.exp((distance_in_tiles - 2) / 5.0) - 1)
                dist_influence += distance_penalty # debug
                reward += distance_penalty


        if environment.maze.reward_gates: # reward for being on the right path
            first_gate = environment.maze.reward_gates[0]
            if agent.rect.colliderect(first_gate):
                gates_hit += 1
                reward += 20 # Base gate reward (increased to make gates more valuable)
                reward += gates_hit * 1.0  # Bonus for progression
                frame_budget += 30
                environment.maze.reward_gates.pop(0)

        if Action.MOVE_FORWARD in movement_signals and agent.speed > 0.02: #reward for moving
            reward += 0.02
            speed_influence += 0.02 #debug

        # if agent.collided: # wall collision penalty
        #     reward -= 1 # commented out since model doesnt reach goal anyway
        #     done = True
        #     pass

        if (agent.pos_x, agent.pos_y) == agent.goal: # big reward for winning
            reward += 50
            done = True

        reward -= 0.001 # time penalty
        frame_decay += 0.001 # debug

        if frame > frame_budget: # time cutoff (per-gate budget)
            reward -= 0.5  # Small penalty for timeout
            done = True

        # # Clamp rewards to reasonable range for stable learning
        # reward = float(np.clip(reward, -5, 25))

        agent.score += reward
        score = agent.score

        state_new = agent.get_state(environment.maze.walls)

        # Only train every 4 steps to reduce instability
        if frame % 4 == 0:
            agent.train_short_memory(state_old, action_array, reward, state_new, done)

        agent.remember(state_old, action_array, reward, state_new, done) # remember

        if done: # train long memory, plot result
            log_memory()
            # debug
            print(f"Game {agent.n_games}, epsilon: {agent.epsilon:.2f}")
            print(frame)
            print(f"Dist influence: {dist_influence}")
            print(f"Frame decay: {frame_decay}")
            print(f"Speed influence: {speed_influence}")

            frame_decay = 0 # reset debug vars
            speed_influence = 0
            dist_influence=0

            frame = 0
            frame_budget = 200  # Reset to initial generous budget
            gates_hit = 0
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
