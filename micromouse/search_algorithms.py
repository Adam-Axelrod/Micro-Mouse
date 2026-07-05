from collections import deque

import config
import maze
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
    distances = {destination: 0} # Distance dict
    frontier = deque([destination])
    while frontier:
        cell = frontier.popleft()
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

### Hug Left ----------------------------------------------------------------------------------------

def hug_left(maze, position, destination=None):
    pass

### Tests -------------------------------------------------------------------------------------------

if __name__ == "__main__":
    # flood_fill plans a shortest route over the (optimistic) belief.
    ex = explorer.Explorer()
    route = flood_fill(ex.belief_map, ex.pos)
    print("planned route on blank belief:", route)
    assert route[0] == ex.pos and route[-1] == ex.belief_map.goal # starts at start and ends at goal