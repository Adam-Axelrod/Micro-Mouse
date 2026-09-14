"""Mode 2. Plan the shortest route over the explored belief map, and drive it.

This is the goal of the project, and the only mode that PLANS. It loads the
belief map mode 1 saved, floods it for the shortest path, turns that path into
egocentric verbs, and hands the verbs to `motion.execute`.

It owns the ROUTE and nothing else. It does not own the motors (`drive.py`) and
it does not own the timing (`motion.py`). Anything that only needs to move a
wheel imports `drive`; anything that needs the executor imports `motion`.
"""

from brain import commands
from brain import maze
from brain import search_algorithms
import config
import files
from hal import drive
import motion
import world


def load_and_plan_route(belief_file_path=None, start_heading=config.DIRECTIONS[0]):
    """Load saved grid belief map, flood fill shortest route, and return movement commands."""
    if belief_file_path is None:
        belief_file_path = config.SAVED_BELIEF_MAZE

    if not files.file_exists(belief_file_path):
        print("Warning: No saved belief at {}, using ground truth maze.".format(
            belief_file_path))
        belief_file_path = config.DEFAULT_MAZE

    cells, cols, rows = maze.num_file_import(belief_file_path)
    discovered_maze = maze.MazeStructure(cells=cells, cols=cols, rows=rows)

    optimal_route = search_algorithms.flood_fill(discovered_maze, config.START_POS)
    movement_commands = commands.path_to_commands(optimal_route, start_heading=start_heading)

    return optimal_route, movement_commands, discovered_maze


def run(enable_render=False):
    """Run speed run mode."""
    print("=== STARTING SPEED RUN MODE ===")
    drive.start_trace()
    drive.blink_led(2, 80)

    route, movement_commands, belief = load_and_plan_route()
    print("Optimal cell path ({} cells): {}".format(len(route), route))

    render_object, _real_maze = world.sim_world(enable_render=enable_render)

    motion.execute(movement_commands, render_object, belief, route)


if __name__ == "__main__":
    run()
