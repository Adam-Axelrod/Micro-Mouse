"""Replay a Pico motor trace through the PC simulation. PC-only.

The Pico can drive but cannot draw; the PC can draw but was not there. This
closes that gap: take the `motor_log.csv` a hardware run wrote, feed the recorded
powers back through the same drive_motors path, and step the sim between records
so the run can be watched (or measured) after the fact.

    python3 sim/replay_log.py                    # headless, prints the reconstructed pose
    python3 replay_log.py --render           # watch it
    python3 sim/replay_log.py path/to/other.csv  # a specific trace

What this does and does not tell you: the sim is re-driven by the SAME commands
the hardware got, so a divergence between the replayed pose and where the robot
physically ended up is a measurement of how wrong the sim's motor/kinematic model
is. That difference is the point of the tool -- it is not a bug in the replay.
Records hold their power until the next timestamp (the trace is change-only), so
a replay is only as faithful as the open-loop timing that produced it.
"""

import os
import sys

# Runnable directly (`python3 sim/replay_log.py`), which puts sim/ on sys.path
# instead of the package root. Everything below imports from the root, so it has
# to be added before anything else is imported.
PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import config  # noqa: E402
from brain import maze  # noqa: E402
from record import motor_log  # noqa: E402
from hal import setup  # noqa: E402

if setup.sim is None:
    raise SystemExit("replay_log.py is PC-only: there is no simulation to replay into.")

from hal import drive  # noqa: E402  -- the motor boundary, after the sim check


def replay(records, render_object=None, belief=None):
    """Drive the sim from a parsed trace. Returns the final MouseState."""
    mouse_state = setup.sim.get_mouse_state()
    dt = config.SIM_TIMESTEP_S

    for index, (t_ms, left_power, right_power) in enumerate(records):
        drive.drive_motors(left_power, right_power)

        # Hold this power until the next record's timestamp. The last record is
        # the end of the trace, so it carries no duration.
        if index + 1 >= len(records):
            break
        hold_seconds = (records[index + 1][0] - t_ms) / 1000.0
        if hold_seconds <= 0.0:
            continue

        for step_index in range(max(1, round(hold_seconds / dt))):
            setup.sim.step_sim_physics(dt)
            if render_object is not None and step_index % drive.RENDER_EVERY_N_STEPS == 0:
                render_object.draw(belief=belief, mouse=mouse_state)

    drive.stop_motors()
    return mouse_state


def main_cli():
    paths = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    log_path = paths[0] if paths else config.MOTOR_LOG_PATH
    enable_render = "--render" in sys.argv or "-r" in sys.argv

    if not files.file_exists(log_path):
        raise SystemExit(
            f"No motor trace at {log_path}.\n"
            "Run the mouse with --log (PC) or on the Pico (always traced), then copy the file here."
        )

    records = motor_log.read_log(log_path)
    print(f"Replaying {len(records)} records from {log_path}")
    if not records:
        raise SystemExit("Trace is empty -- nothing to replay.")

    real_maze = maze.MazeStructure(*maze.num_file_import(config.DEFAULT_MAZE))
    setup.sim.set_sim_maze(real_maze)

    render_object = None
    if enable_render:
        from sim.renderer import make_renderer
        render_object = make_renderer(real_maze)

    start = setup.sim.get_mouse_state()
    print(f"start pose: x={start.x_mm:.1f} y={start.y_mm:.1f} heading={start.heading_radians:.3f}")

    final = replay(records, render_object, belief=real_maze)

    print(f"final pose: x={final.x_mm:.1f} y={final.y_mm:.1f} heading={final.heading_radians:.3f}")
    print(f"cell:       {(int(final.x_mm // config.MM_PER_CELL), int(final.y_mm // config.MM_PER_CELL))}")
    print(f"encoders:   left={final.left_encoder_ticks} right={final.right_encoder_ticks}")
    print(f"trace span: {(records[-1][0] - records[0][0]) / 1000.0:.2f} s")


if __name__ == "__main__":
    main_cli()
