"""The scene and the clock behind hal.setup: what a mode asks for instead of the simulator.

`setup.wait` steps the physics and draws while it does. A frame only reads the
pose, so a run must give the same result with a window and without one.
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import config
import motion
from hal import setup
from sim import render_config
from sim import sim_machine

START = (1, 1, "n")
VERBS = [("F", 1), ("R", None), ("F", 1), ("L", None), ("H", None)]


class FakeRenderer:
    """Counts the frames it is asked for, and keeps what each one drew."""

    def __init__(self):
        self.frames = []

    def draw(self, belief, mouse=None, path=None, done=None, animate=False):
        self.frames.append((belief, path, done, animate))


def _drive(world):
    """Run VERBS from the start pose. Returns the final pose and the ticks it took."""
    state = sim_machine.get_mouse_state()
    ticks_before = (state.left_encoder_ticks, state.right_encoder_ticks)
    motion.execute(VERBS)
    return (world.pose(), state.left_encoder_ticks - ticks_before[0],
            state.right_encoder_ticks - ticks_before[1])


def test_wait_advances_the_simulated_clock_by_exactly_the_time():
    setup.scene(start_pose=START)
    before = setup.now_ms()
    setup.wait(0.07)
    assert setup.diff_ms(setup.now_ms(), before) == 70, "0.07 s is 70 ms, not 69"
    print("✓ test_wait_advances_the_simulated_clock_by_exactly_the_time passed")


def test_wait_keeps_the_remainder_of_a_short_move():
    """0.216 s is 21 steps and 6 ms. Rounding to whole steps turned it 91.6 degrees."""
    setup.scene(start_pose=START)
    before = sim_machine.simulation_engine.elapsed_seconds
    setup.wait(0.216)
    waited = sim_machine.simulation_engine.elapsed_seconds - before
    assert abs(waited - 0.216) < 1e-9, waited
    print("✓ test_wait_keeps_the_remainder_of_a_short_move passed")


def test_the_scene_places_the_mouse_and_reports_its_pose():
    world = setup.scene(grid=(3, 3), start_pose=(2, 1, "e"))
    x_mm, y_mm, heading = world.pose()
    assert abs(x_mm - 2.5 * config.MM_PER_CELL) < 1e-6, x_mm
    assert abs(y_mm - 1.5 * config.MM_PER_CELL) < 1e-6, y_mm
    assert abs(heading - config.HEADING_RADIANS["e"]) < 1e-6, heading
    print("✓ test_the_scene_places_the_mouse_and_reports_its_pose passed")


def test_a_frame_is_drawn_once_for_every_n_physics_steps():
    world = setup.scene(start_pose=START)
    fake = world._renderer = FakeRenderer()
    steps = 3 * render_config.RENDER_EVERY_N_STEPS
    setup.wait(steps * config.SIM_TIMESTEP_S)
    assert len(fake.frames) == 3, len(fake.frames)
    setup.wait(config.SIM_TIMESTEP_S)
    assert len(fake.frames) == 4, "the count carries over from one wait to the next"
    print("✓ test_a_frame_is_drawn_once_for_every_n_physics_steps passed")


def test_show_sets_what_every_later_frame_draws():
    world = setup.scene(start_pose=START)
    fake = world._renderer = FakeRenderer()
    belief, route, done = object(), [(0, 0), (0, 1)], [(0, 0)]

    world.show(belief=belief, route=route, done=done, animate=True)
    assert fake.frames == [(belief, route, done, True)]

    setup.wait(config.SIM_TIMESTEP_S)
    assert fake.frames[-1] == (belief, route, done, False), "a frame from a wait does not animate"

    world.show()
    assert fake.frames[-1] == (world.maze, None, None, False), "with no belief the true maze is drawn"
    print("✓ test_show_sets_what_every_later_frame_draws passed")


def test_a_run_gives_the_same_result_with_and_without_a_renderer():
    without = _drive(setup.scene(start_pose=START))

    world = setup.scene(start_pose=START)
    world._renderer = FakeRenderer()
    world.show(route=[(1, 1), (1, 2)])
    with_renderer = _drive(world)

    assert world._renderer.frames, "the renderer was never asked to draw"
    assert with_renderer == without, (with_renderer, without)
    print("✓ test_a_run_gives_the_same_result_with_and_without_a_renderer passed")


def test_a_new_scene_takes_over_the_frames():
    first = setup.scene(start_pose=START)
    first._renderer = FakeRenderer()
    second = setup.scene(start_pose=START)
    setup.wait(config.SIM_TIMESTEP_S)
    assert first._renderer.frames == [], "the old scene was still being drawn"
    assert second is not first
    print("✓ test_a_new_scene_takes_over_the_frames passed")


TESTS = (
    test_wait_advances_the_simulated_clock_by_exactly_the_time,
    test_wait_keeps_the_remainder_of_a_short_move,
    test_the_scene_places_the_mouse_and_reports_its_pose,
    test_a_frame_is_drawn_once_for_every_n_physics_steps,
    test_show_sets_what_every_later_frame_draws,
    test_a_run_gives_the_same_result_with_and_without_a_renderer,
    test_a_new_scene_takes_over_the_frames,
)


if __name__ == "__main__":
    if setup.sim is None:
        print("SKIPPED: no simulation engine (this is hardware)")
        sys.exit(0)
    for test in TESTS:
        test()
    print("ALL {} SCENE TESTS PASSED".format(len(TESTS)))
