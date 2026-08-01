### Imports -----------------------------------------------------------------------------------------

import config
import explorer

### Flood Fill --------------------------------------------------------------------------------------

"""Cells reachable from `cell` in one step: the side has no wall (0) and the neighbour exists on the grid.
Iterates n, e, s, w so ties later resolve in that order (north first), which is what makes the blank maze
go up then right."""

def open_neighbours(maze, cell):

    x, y = cell
    walls = maze.cells[cell]
    neighbours = []

    for wall_index, side in enumerate(config.DIRECTIONS):
        if walls[wall_index]: # 1 = wall on this side, can't pass
            continue
        dx, dy =  config.SIDE_DELTA[side]
        candidate = (x + dx, y + dy)
        if candidate in maze.cells: # stay inside the maze
            neighbours.append(candidate)

    return neighbours


"""The flood itself: breadth-first from the destination outward, labelling every cell with its
step-distance to the destination through open edges. The destination is 0 and distance grows by 1 each
ring out. Cells walled off from the destination are absent. The destination is whatever the caller is
heading for right now (the maze centre on the way out, the start on a return run), NOT a fixed maze
property, so it is passed in rather than read from maze.goal."""

def flood_distances(maze, destination):
    # A plain list with a head index is the queue: append to grow the frontier,
    # advance `head` to pop. This is O(1) amortised and avoids collections.deque,
    # whose MicroPython signature requires a maxlen the CPython call omitted.
    distances = {destination: 0} # Distance dict
    frontier = [destination]
    head = 0
    while head < len(frontier):
        cell = frontier[head]
        head += 1
        for nxt in open_neighbours(maze, cell):
            if nxt not in distances:          # first time we reach it = shortest
                distances[nxt] = distances[cell] + 1
                frontier.append(nxt)
    return distances

"""Plan a route from `position` to `destination` over the given belief map.

`destination` is where we are heading right now; it defaults to maze.goal (the centre) for the outward
explore, and the caller passes the start cell for the return run. It is not necessarily the maze's
fixed goal, which is why it is a parameter.

1. Flood distance-to-destination across the maze (flood_distances).
2. From `position`, keep stepping to the open neighbour with the lowest distance until we stand on
the destination: always walking downhill on the distance field is guaranteed to be a shortest path.

Returns the list of cells [position, ..., destination]; empty if it is unreachable from `position`."""

def flood_fill(maze, position, destination=None):
    if destination is None:
        destination = maze.goal
    distances = flood_distances(maze, destination)
    if position not in distances: # the destination can't be reached from here
        return []

    path = [position]
    while path[-1] != destination:
        cell = path[-1]
        best_cell = None # Find the neighbour that is strictly closer to the goal than we are.
        best_distance = distances[cell]
        for neighbour in open_neighbours(maze, cell):
            if distances.get(neighbour, float("inf")) < best_distance:
                best_distance = distances[neighbour]
                best_cell = neighbour
        if best_cell is None: # nothing nearer the destination: dead end, stop
            break
        path.append(best_cell)

    return path

### Route validity ----------------------------------------------------------------------------------

def route_is_open(maze, route):
    """True if every step of `route` is still passable in this belief map.

    A route is a list of grid-adjacent cells. It stays valid until an observation
    marks a wall across one of its steps, so this is the test for "do I need to
    re-plan?". Flood-filling every tick is wasted work: the belief only changes
    where a sensor reported something, and a wall that isn't on the current route
    cannot make the current route worse.

    A route of fewer than two cells is trivially open (there is nothing to walk).
    """
    for cell, nxt in zip(route, route[1:]):
        if cell not in maze.cells:
            return False
        delta = (nxt[0] - cell[0], nxt[1] - cell[1])
        side = config.DELTA_SIDE.get(delta)
        if side is None:                       # not grid-adjacent: not a walkable route
            return False
        if maze.cells[cell][config.WALL_INDEX[side]]:
            return False                       # a wall now blocks this step
    return True


### Hug Left ----------------------------------------------------------------------------------------

def hug_left(maze, position, destination=None):
    """Intentionally unimplemented stub (no call sites yet) -- not a bug.

    Planned: left-hand wall-follower as a simple non-flood baseline/fallback --
    from `position`, keep the left hand on the wall until `destination` is
    reached. Signature mirrors flood_fill so it can slot in as an alternative
    planner when implemented.
    """
    pass

### Tests -------------------------------------------------------------------------------------------

if __name__ == "__main__":
    # flood_fill plans a shortest route over the (optimistic) belief.
    ex = explorer.Explorer()
    route = flood_fill(ex.belief_map, ex.pos)
    print("planned route on blank belief:", route)
    assert route[0] == ex.pos and route[-1] == ex.belief_map.goal # starts at start and ends at goal

    # route_is_open: a fresh plan is walkable, and a wall dropped across its first
    # step invalidates it -- that is exactly the replan trigger.
    assert route_is_open(ex.belief_map, route)
    ex.observe(route[0], [config.DELTA_SIDE[(route[1][0] - route[0][0],
                                             route[1][1] - route[0][1])]])
    assert not route_is_open(ex.belief_map, route)
    # A wall somewhere else on the map leaves an unrelated route alone.
    ex2 = explorer.Explorer()
    route2 = flood_fill(ex2.belief_map, ex2.pos)
    ex2.observe((15, 15), ["w"])
    assert route_is_open(ex2.belief_map, route2)
    print("route_is_open replan trigger OK")