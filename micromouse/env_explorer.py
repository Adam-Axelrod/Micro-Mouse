"""Env adapter for the Explorer (EXP-3/EXP-4).

This is the ONLY layer that holds the real maze. It senses walls from ground
truth, feeds them to the Explorer as plain compass sides, asks the Explorer to
plan over its belief, and drives one cell. The Explorer itself never sees the
real maze, so the same brain runs unchanged on noisy sensors or real hardware
later (EXP-7). Run with: python -m micromouse.env_explorer
"""

### Imports -----------------------------------------------------------------------------------------

from . import config
from . import maze
from .explorer import Explorer, flood_fill

### Sensing -----------------------------------------------------------------------------------------

"""Idealised wall read (EXP-3): look up the current cell's four edges in the real maze and return
the absolute sides that have a wall. This is the ground-truth seam; everything downstream only sees
the returned list. EXP-7 swaps this for a noisy 3-sensor read (left/right/front from `heading`,
rear inferred from entry) without the Explorer changing at all."""

def read_walls(real_maze, pos):
    walls = real_maze.cells[pos]
    return [side for flag, side in zip(walls, config.DIRECTIONS) if flag]

### Exploration loop --------------------------------------------------------------------------------

"""Drive the Explorer to the goal using only sensed walls.

The loop: sense the current cell -> observe (fold walls into belief) -> re-plan over the belief ->
commit to ONE cell -> drive onto it. Because a 16x16 flood is cheap we re-plan every cell instead of
detecting surprises, so a wall is always already in the belief before we try to cross its edge.

`belief` lets the same loop serve both modes the project cares about:
  - None  -> a blank belief: the real explorer, discovering the maze as it goes ("external").
  - a copy of the real maze -> belief already correct, so no surprise ever fires and the loop
    degenerates to plan-once-and-walk ("internal" / omniscient). See explore_omniscient.

Returns the Explorer so callers can read pos, path_done and the belief."""

def explore(real_maze, belief=None, algo=flood_fill):
    if belief is None:
        belief = maze.MazeStructure(rows=real_maze.rows, cols=real_maze.cols)  # blank, same size
    ex = Explorer(belief_map=belief)
    ex.path_done = [ex.pos]                                # record the start cell

    while not ex.at_goal():
        ex.observe(ex.pos, read_walls(real_maze, ex.pos))  # sense -> belief
        route = algo(ex.belief_map, ex.pos)                # plan over belief
        if len(route) < 2:
            break                                          # boxed in / dead-end (EXP-5 will handle)
        ex.path_to_execute = [route[1]]                    # commit to one cell only
        while ex.path_to_execute:                          # pivot, then drive onto it
            ex.step()

    return ex


"""Omniscient solve: seed the belief with a copy of the real maze, then run the same loop. The
tuple wall-values are immutable, so a shallow dict copy is a safe independent belief."""

def explore_omniscient(real_maze, algo=flood_fill):
    belief = maze.MazeStructure(cells=dict(real_maze.cells),
                                rows=real_maze.rows, cols=real_maze.cols)
    return explore(real_maze, belief=belief, algo=algo)

### Tests -------------------------------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Empty maze: the mouse should walk north then east to the centre using only sensed walls.
    empty = maze.MazeStructure()
    ex = explore(empty)
    print(ex)
    print("blank-belief path:", ex.path_done)
    assert ex.at_goal(), "did not reach the goal on the empty maze"

    # 2. A real maze: blank-belief exploration must still reach the goal, and the cells it walked
    #    must match the omniscient shortest path's length on a maze with a unique route. We assert
    #    the weaker, always-true property: both reach the goal, and exploration crosses no real wall.
    real = maze.MazeStructure(*maze.num_file_import(config.DEFAULT_MAZE))
    explored = explore(real)
    omniscient = explore_omniscient(real)
    assert explored.at_goal(), "blank-belief exploration failed to reach the goal"
    assert omniscient.at_goal(), "omniscient solve failed to reach the goal"

    # No step in the explored path crossed a real wall (belief-vs-reality check).
    for a, b in zip(explored.path_done, explored.path_done[1:]):
        side = config.DELTA_SIDE[(b[0] - a[0], b[1] - a[1])]
        assert real.cells[a][config.WALL_INDEX[side]] == 0, f"walked through wall {side} at {a}"

    print(explored)
    print(
        f"real-maze path reached goal in {len(explored.path_done)} steps", 
        f"({len(explored.optimal_from_known())} without doubling on itself)"
        )
