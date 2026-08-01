"""Exploration Mode for UKMARS Gemini Micromouse.

Autonomous cell-by-cell maze exploration using flood-fill and belief mapping.
Pico and PC compatible.
"""

import time
import config
import maze
import search_algorithms
import setup
from explorer import Explorer

# Optional PC-only Pygame renderer imports
try:
    import geometry
    from renderer import Renderer
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False

HAS_SIM = setup.sim is not None


def blink_led(times, on_duration_ms=150, off_duration_ms=150):
    for _ in range(times):
        setup.LED_PIN.value(1)
        time.sleep(on_duration_ms / 1000.0)
        setup.LED_PIN.value(0)
        time.sleep(off_duration_ms / 1000.0)


def read_walls(real_maze, current_position):
    """Read true wall presence around current cell (simulation mode)."""
    walls = real_maze.cells[current_position]
    sensed_walls = []
    for wall_flag, compass_side in zip(walls, config.DIRECTIONS):
        if wall_flag:
            sensed_walls.append(compass_side)
    return sensed_walls


def run(enable_render=False, save_belief_path=None):
    """Run cell-by-cell exploration mode."""
    print("=== STARTING EXPLORATION MODE ===")
    blink_led(3, on_duration_ms=150, off_duration_ms=150)

    real_maze = maze.MazeStructure(*maze.num_file_import(config.DEFAULT_MAZE))
    
    if HAS_SIM:
        setup.sim.set_sim_maze(real_maze)

    belief = maze.MazeStructure(cols=real_maze.cols, rows=real_maze.rows)
    explorer_robot = Explorer(belief_map=belief)

    render_object = None
    if HAS_PYGAME and enable_render:
        try:
            render_object = Renderer(geometry.MazeGeometry(real_maze))
        except Exception as exc:
            print(f"Renderer init failed ({type(exc).__name__}: {exc}); continuing without rendering.")
            render_object = None

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
                setup.sim.step_sim_physics(delta_time_seconds=0.01)

    if save_belief_path is None:
        save_belief_path = config.SAVED_BELIEF_MAZE

    maze.num_file_export(save_belief_path, explorer_robot.belief_map.cells)
    print(f"Exploration finished! Grid belief map saved to: {save_belief_path}")

    return explorer_robot


if __name__ == "__main__":
    run()
