import os
import config
import maze
import commands
import search_algorithms
from explorer import Explorer

try:
    from renderer import Renderer
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False


def read_walls(real_maze, current_position):
    """Read true wall presence around current cell."""
    walls = real_maze.cells[current_position]
    sensed_walls = []
    for wall_flag, compass_side in zip(walls, config.DIRECTIONS):
        if wall_flag:
            sensed_walls.append(compass_side)
    return sensed_walls


def explore(real_maze, belief=None, algo=search_algorithms.flood_fill, save_belief_path=None, enable_render=True):
    """Drive Explorer using sensed walls and save discovered grid belief to .num file."""
    if belief is None:
        belief = maze.MazeStructure(cols=real_maze.cols, rows=real_maze.rows)

    explorer_robot = Explorer(belief_map=belief)

    render_object = None
    if HAS_PYGAME and enable_render:
        try:
            render_object = Renderer(maze.MazeGeometry(real_maze))
        except Exception:
            render_object = None

    previous_route = None

    while not explorer_robot.at_goal():
        sensed_walls = read_walls(real_maze, explorer_robot.pos)
        explorer_robot.observe(explorer_robot.pos, sensed_walls)
        route = algo(explorer_robot.belief_map, explorer_robot.pos)

        replanned = (previous_route is None or route != previous_route[1:])
        if render_object is not None:
            render_object.draw(belief=explorer_robot.belief_map, mouse=None, path=route, done=explorer_robot.path_done, animate=replanned)
        previous_route = route

        if len(route) < 2:
            break

        explorer_robot.path_to_execute = [route[1]]
        while explorer_robot.path_to_execute:
            explorer_robot.step()

    # Save discovered grid belief map to disk
    if save_belief_path is None:
        save_belief_path = config.SAVED_BELIEF_MAZE

    maze.num_file_export(save_belief_path, explorer_robot.belief_map.cells)
    print(f"Exploration complete! Grid belief map saved to: {save_belief_path}")

    return explorer_robot


def load_and_plan_route(belief_file_path=None, start_heading=config.DIRECTIONS[0]):
    """Load saved grid belief map, flood fill shortest route, and return movement commands."""
    if belief_file_path is None:
        belief_file_path = config.SAVED_BELIEF_MAZE

    if not os.path.exists(belief_file_path):
        print(f"Warning: No saved belief at {belief_file_path}, using ground truth maze.")
        belief_file_path = config.DEFAULT_MAZE

    cells, cols, rows = maze.num_file_import(belief_file_path)
    discovered_maze = maze.MazeStructure(cells=cells, cols=cols, rows=rows)

    optimal_route = search_algorithms.flood_fill(discovered_maze, config.START_POS)
    movement_commands = commands.path_to_commands(optimal_route, start_heading=start_heading)

    return optimal_route, movement_commands


def explore_omniscient(real_maze, algo=search_algorithms.flood_fill):
    belief = real_maze.copy()
    return explore(real_maze, belief=belief, algo=algo)


def step_test(test_maze_path):
    real_maze = maze.MazeStructure(*maze.num_file_import(test_maze_path))
    explored_robot = explore(real_maze)
    print("Exploration finished. Goal reached:", explored_robot.at_goal())

    route, cmds = load_and_plan_route()
    print("Speed run optimal route length:", len(route))
    print("Speed run commands:", cmds)


if __name__ == "__main__":
    step_test(config.DEFAULT_MAZE)
