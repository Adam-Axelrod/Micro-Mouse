### Imports ----------------------------------------------------------------------------------------- 

from collections import deque
from pathlib import Path

from . import config
from . import maze

### Variables --------------------------------------------------------------------------------------- 

# Compass convention is defined once in config (the lowest layer). Bound to short
# local names here so the methods below read cleanly. A side's position in
# DIRECTIONS is also its slot in a cell's (n, e, s, w) wall tuple, which is what
# couples movement and wall-checking.
DIRECTIONS = config.DIRECTIONS        # ("n", "e", "s", "w"): mouse orientation / wall-tuple order
SIDE_DELTA = config.SIDE_DELTA        # side -> (dx, dy) step to the neighbour
DELTA_SIDE = config.DELTA_SIDE        # inverse: (dx, dy) step -> side

### Explorer Class ----------------------------------------------------------------------------------

class Explorer:
    def __init__(self, belief_map=None):
        self.belief_map = belief_map if belief_map else maze.MazeStructure()
        self.path_done = []
        self.path_to_execute = []
        self.pos = (0,0) # This is where the mouse should be - this class handles logic so all the sim has to do is bring the mouse here
        self.direction = DIRECTIONS[0] #turn by incrementing through this tuple

    def __str__(self): # Same as MazeStructure but with Path and Mouse representation
        return maze.to_ascii(self.belief_map, self.path_done, self.pos)

    def at_goal(self):
        return self.pos == self.belief_map.goal

    def get_goal(self):
        return self.belief_map.goal

    def get_pos(self):
        return self.pos

    def get_direction(self):
        return self.direction

    def move_to_target(self, target): # teleport in step based solution, implement signal 
        self.pos = target 
        # append target coords to be reached which step will signal     
        return

    """One physical action toward the next cell in path_to_execute: either pivot one notch 
    clockwise to face it, or, if already facing it, drive onto it. A real mouse can only rotate 
    or go forward, so a single 'step' is one of those, not a teleport to the target."""

    def step(self):
        if not self.path_to_execute:
            return

        target = self.path_to_execute[0]
        delta = (target[0] - self.pos[0], target[1] - self.pos[1]) # check if adjacent to next cell
        if delta not in DELTA_SIDE:
            raise ValueError(f"{target} is not adjacent to {self.pos}")

        needed = DELTA_SIDE[delta] # check if pointing at next cell
        if self.direction != needed:
            self.direction = turn_clockwise(self.direction) # if not rotate clockwise
            return

        self.pos = target
        self.path_done.append(target)
        self.path_to_execute.pop(0)


    """Fold sensed walls into the belief. `sensed_sides` is a list of absolute compass sides
    (subset of n/e/s/w) a sensor reported as walled at `cell`. This is the ONLY channel by which
    the outside world tells the Explorer about walls: the adapter senses (idealised from the real
    maze now, noisy 3-sensor later) and hands over a plain list, so the Explorer never knows where it
    came from. mark_wall mirrors the shared edge onto the neighbour to keep the belief consistent.
    Sides not reported are left untouched: a blank belief starts every interior edge open, so an
    idealised read only needs to record the walls it found."""
    def observe(self, cell, sensed_sides):
        for side in sensed_sides:
            self.belief_map.mark_wall(cell, side)

    def optimal_path(self):
        if self.at_goal():
            # return compressed self.path without overlaps
            pass
        
### Generic Movement Functions ----------------------------------------------------------------------

"""One clockwise pivot: n -> e -> s -> w -> n. Incrementing the index into DIRECTIONS IS a clockwise 
turn, which is why the mouse can only ever turn one way for now (a real mouse would also turn left; 
that is a later optimisation)."""

def turn_clockwise(direction):
    return DIRECTIONS[(DIRECTIONS.index(direction) + 1) % len(DIRECTIONS)]

### Flood Fill --------------------------------------------------------------------------------------

"""Cells reachable from `cell` in one step: the side has no wall (0) and the neighbour exists on the grid.
Iterates n, e, s, w so ties later resolve in that order (north first), which is what makes the blank maze 
go up then right."""

def open_neighbours(maze, cell):

    x, y = cell
    walls = maze.cells[cell]
    neighbours = []

    for wall_index, side in enumerate(DIRECTIONS):
        if walls[wall_index]: # 1 = wall on this side, can't pass
            continue
        dx, dy = SIDE_DELTA[side]
        candidate = (x + dx, y + dy)
        if candidate in maze.cells: # stay inside the maze
            neighbours.append(candidate)

    return neighbours


"""The flood itself: breadth-first from the goal outward, labelling every cell with its step-distance to
the goal through open edges. The goal is 0 and distance grows by 1 each ring out. Cells walled off from 
the goal are absent."""

def flood_distances(maze, goal):
    distances = {goal: 0} # Distance dict
    frontier = deque([goal]) 
    while frontier:
        cell = frontier.popleft()
        for nxt in open_neighbours(maze, cell):
            if nxt not in distances:          # first time we reach it = shortest
                distances[nxt] = distances[cell] + 1
                frontier.append(nxt)
    return distances

"""Plan a route from `position` to maze.goal over the given belief map.

1. Flood distance-to-goal across the maze (flood_distances).
2. From `position`, keep stepping to the open neighbour with the lowest distance until we stand on 
the goal: always walking downhill on the distance field is guaranteed to be a shortest path.

Returns the list of cells [position, ..., goal]; empty if the goal is unreachable from `position`."""

def flood_fill(maze, position):
    distances = flood_distances(maze, maze.goal)
    if position not in distances: # the goal can't be reached from here
        return []

    path = [position]
    while path[-1] != maze.goal:
        cell = path[-1]
        best_cell = None # Find the neighbour that is strictly closer to the goal than we are.
        best_distance = distances[cell]
        for neighbour in open_neighbours(maze, cell):
            if distances.get(neighbour, float("inf")) < best_distance:
                best_distance = distances[neighbour]
                best_cell = neighbour
        if best_cell is None: # nothing nearer the goal: dead end, stop
            break
        path.append(best_cell)

    return path

### Hug Left ----------------------------------------------------------------------------------------

def hug_left(maze, position):
    pass

### Tests -------------------------------------------------------------------------------------------

if __name__ == "__main__":
    # Pure-planner tests only: no adapter, no ground truth. 
    # observe folds a sensed wall into the belief, mirrored onto the neighbour.
    ex = Explorer()
    ex.observe((0, 0), ["e"])                       # sense an east wall at the start cell
    assert ex.belief_map.cells[(0, 0)][1] == 1      # east wall recorded here
    assert ex.belief_map.cells[(1, 0)][3] == 1      # and mirrored as the neighbour's west wall

    # flood_fill plans a shortest route over the (optimistic) belief.
    route = flood_fill(ex.belief_map, ex.pos)
    print("planned route on blank belief:", route)
    assert route[0] == ex.pos and route[-1] == ex.belief_map.goal # starts at start and ends at goal


