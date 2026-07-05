
from . import config
from . import maze

### Explorer Class ----------------------------------------------------------------------------------

"""Works as the internal decision maker, something akin to following map instructions while building up memory. 
Doesn't know its pixel/mm position but knows what step it is meant to be undertaking right now."""

"""pos - mouse is here or should be here, next_pos next waypoint"""

class Explorer:
    def __init__(self, belief_map=None, destination=None, pos=None, render=True):
        self.belief_map = belief_map if belief_map else maze.MazeStructure()
        self.destination = destination if destination else self.belief_map.goal
        self.pos = pos if pos else (0,0)
        self.next_pos = self.pos
        self.path_done = [self.pos]
        self.path_to_execute = []
        self.direction = config.DIRECTIONS[0] #turn by incrementing through this tuple

    def __str__(self): # Same as MazeStructure but with Path and Mouse representation
        return maze.to_ascii(self.belief_map, self.optimal_from_known(), self.pos)

    def at_goal(self):
        return self.pos == self.belief_map.goal

    def at_destination(self):
        return self.pos == self.destination
    
    def get_destination(self):
        return self.destination

    def set_pos(self, pos):
        self.pos = pos

    def get_pos(self):
        return self.pos

    def get_direction(self):
        return self.direction

    def move_to_target(self): # this is more for updating internal logic, mouse body uses this function to update where it should be
        self.pos = self.next_pos # does not actually control mouse location
        self.path_done.append(self.pos)
        self.path_to_execute.pop(0)
        return

    def step(self):
        if not self.path_to_execute:
            return

        target = self.path_to_execute[0]
        delta = (target[0] - self.pos[0], target[1] - self.pos[1]) # check if adjacent to next cell
        if delta not in config.DELTA_SIDE:
            raise ValueError(f"{target} is not adjacent to {self.pos}")

        needed = config.DELTA_SIDE[delta] # check if pointing at next cell
        if self.direction != needed:
            self.direction = turn_clockwise(self.direction) # if not rotate clockwise
            return

        self.next_pos = target
        self.move_to_target()

    """Fold sensed walls into the belief. `sensed_sides` is a list of absolute compass sides
    (subset of n/e/s/w) a sensor reported as walled at `cell`. This is the ONLY channel by which
    the outside world tells the Explorer about walls. mark_wall mirrors the shared edge onto the
    neighbour to keep the belief consistent. Sides not reported are left untouched: a blank belief 
    starts every interior edge open, so an idealised read only needs to record the walls it found."""

    def observe(self, cell, sensed_sides): 
        for side in sensed_sides:
            self.belief_map.mark_wall(cell, side)

    """Prints path done but removes any loops that cause it to visit the same cell twice."""

    def optimal_from_known(self):
        if not self.at_destination():
            return []
        route = []
        seen = {}                                 # cell -> its index in route
        for cell in self.path_done:
            if cell in seen:                      # been here: drop the loop back to the first visit
                for c in route[seen[cell] + 1:]:
                    del seen[c]
                del route[seen[cell] + 1:]
            else:
                seen[cell] = len(route)
                route.append(cell)
        return route

        
### Generic Movement Functions ----------------------------------------------------------------------

"""One clockwise pivot: n -> e -> s -> w -> n. Incrementing the index into DIRECTIONS IS a clockwise 
turn, which is why the mouse can only ever turn one way for now (a real mouse would also turn left; 
that is a later optimisation)."""

def turn_clockwise(direction):
    return config.DIRECTIONS[(config.DIRECTIONS.index(direction) + 1) % len(config.DIRECTIONS)]

### Tests -------------------------------------------------------------------------------------------

if __name__ == "__main__":
    # Pure-planner tests only: no adapter, no ground truth. 
    # observe folds a sensed wall into the belief, mirrored onto the neighbour.
    ex = Explorer()
    ex.observe((0, 0), ["e"])                       # sense an east wall at the start cell
    assert ex.belief_map.cells[(0, 0)][1] == 1      # east wall recorded here
    assert ex.belief_map.cells[(1, 0)][3] == 1      # and mirrored as the neighbour's west wall
    print(ex)

