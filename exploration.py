"""Exploration Mode for UKMARS Gemini Micromouse.

Autonomous cell-by-cell maze exploration using flood-fill and belief mapping.
Pico and PC compatible.
"""

import config
import drive
from brain import maze
from brain import search_algorithms
import setup
from brain.explorer import Explorer

try:
    from sim.renderer import make_renderer
except ImportError:
    def make_renderer(real_maze):
        return None

HAS_SIM = setup.sim is not None


def read_walls(real_maze, current_position):
    """Read true wall presence around current cell.

    SIMULATION ONLY, and a deliberate shortcut: this reads the ground-truth maze
    file, not a sensor. The simulated reflective sensors (sim/mouse.py,
    sim/geometry.py) are built but nothing converts an ADC reading into a sensed
    side yet, so mode 1 cannot run on the board -- there is no answer key there.
    Replacing this function is the whole of "autonomous exploration on hardware".
    """
    walls = real_maze.cells[current_position]
    sensed_walls = []
    for wall_flag, compass_side in zip(walls, config.DIRECTIONS):
        if wall_flag:
            sensed_walls.append(compass_side)
    return sensed_walls


def run(enable_render=False, save_belief_path=None):
    """Run cell-by-cell exploration mode."""
    print("=== STARTING EXPLORATION MODE ===")
    drive.blink_led(3, 150)

    real_maze = maze.MazeStructure(*maze.num_file_import(config.DEFAULT_MAZE))

    if HAS_SIM:
        setup.sim.set_sim_maze(real_maze)

    belief = maze.MazeStructure(cols=real_maze.cols, rows=real_maze.rows)
    explorer_robot = Explorer(belief_map=belief)

    render_object = make_renderer(real_maze) if enable_render else None

    route = []

    while not explorer_robot.at_goal():
        sensed_walls = read_walls(real_maze, explorer_robot.pos)
        explorer_robot.observe(explorer_robot.pos, sensed_walls)

        if explorer_robot.pos in route:
            route = route[route.index(explorer_robot.pos):]
        else:
            route = []

        replanned = len(route) < 2 or not search_algorithms.route_is_open(
            explorer_robot.belief_map, route
        )
        if replanned:
            route = search_algorithms.flood_fill(
                explorer_robot.belief_map, explorer_robot.pos
            )

        if render_object is not None:
            mouse_st = setup.sim.get_mouse_state() if HAS_SIM else None
            render_object.draw(
                belief=explorer_robot.belief_map,
                mouse=mouse_st,
                path=route,
                done=explorer_robot.path_done,
                animate=replanned
            )

        if len(route) < 2:
            break

        explorer_robot.path_to_execute = [route[1]]
        while explorer_robot.path_to_execute:
            explorer_robot.step()
            if HAS_SIM:
                setup.sim.step_sim_physics(config.SIM_TIMESTEP_S)

    if save_belief_path is None:
        save_belief_path = config.SAVED_BELIEF_MAZE

    maze.num_file_export(save_belief_path, explorer_robot.belief_map.cells)
    print(f"Exploration finished! Grid belief map saved to: {save_belief_path}")

    return explorer_robot


if __name__ == "__main__":
    run()
