"""Renderer construct-and-draw smoke tests, and the pixel-to-cell inverse.

`make_renderer` swallows construction errors and continues headless, so a broken
Renderer shows up only as a window that never opens. These make it loud.
"""

import math
import os
import sys

# Chosen before pygame initialises a display.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import config
from maze import MazeStructure

try:
    import pygame  # noqa: F401
    from sim.geometry import MazeGeometry
    from sim.renderer import Renderer, make_renderer, tile_px_for
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False


def _view(cols=16, rows=16):
    return Renderer(MazeGeometry(MazeStructure(cols=cols, rows=rows)))


def test_a_renderer_constructs_at_every_grid_size():
    for cols, rows in ((3, 3), (6, 6), (16, 16), (3, 6), (32, 32), (1, 1)):
        view = _view(cols, rows)
        tile = tile_px_for(cols, rows)
        expected = (cols * tile + 2 * config.RENDER_MARGIN_PX,
                    rows * tile + 2 * config.RENDER_MARGIN_PX)
        assert view.screen.get_size() == expected, (cols, rows, view.screen.get_size())
    print("✓ test_a_renderer_constructs_at_every_grid_size passed")


def test_the_tile_scale_stays_clickable_and_bounded():
    """A fixed scale served 16x16 alone: a 3x3 was a 135 px window."""
    for cols, rows in ((1, 1), (3, 3), (6, 6), (16, 16), (32, 32), (3, 16)):
        tile = tile_px_for(cols, rows)
        assert config.RENDER_MIN_TILE_PX <= tile <= config.RENDER_MAX_TILE_PX, (cols, rows, tile)
        longest_px = tile * max(cols, rows)
        assert longest_px <= config.RENDER_TARGET_WINDOW_PX or tile == config.RENDER_MIN_TILE_PX
    assert tile_px_for(3, 3) > tile_px_for(16, 16), "a small grid must draw bigger cells"
    print("✓ test_the_tile_scale_stays_clickable_and_bounded passed")


def test_a_click_lands_in_the_right_cell_at_every_grid_size():
    """cell_at_px is the editor's whole input path, and the scale now varies."""
    for cols, rows in ((3, 3), (6, 6), (16, 16), (3, 16)):
        view = _view(cols, rows)
        for cell in ((0, 0), (cols - 1, rows - 1), (cols // 2, rows // 2)):
            centre_mm = ((cell[0] + 0.5) * config.MM_PER_CELL,
                         (cell[1] + 0.5) * config.MM_PER_CELL)
            assert view.cell_at_px(view._px(*centre_mm)) == cell, (cols, rows, cell)
    print("✓ test_a_click_lands_in_the_right_cell_at_every_grid_size passed")


def test_draw_paints_a_heading_arrow():
    view = _view(3, 3)
    for side in config.DIRECTIONS:
        view.draw(None, heading_marks={(1, 1): side})
    print("✓ test_draw_paints_a_heading_arrow passed")


def test_make_renderer_returns_a_renderer_not_none():
    assert make_renderer(MazeStructure(cols=3, rows=3)) is not None
    print("✓ test_make_renderer_returns_a_renderer_not_none passed")


def test_draw_survives_every_optional_argument():
    view = _view(6, 6)
    belief = MazeStructure(cols=6, rows=6)
    path = [(0, 0), (0, 1), (1, 1)]

    view.draw(belief)
    view.draw(belief, path=path)
    view.draw(belief, path=path, done=[(0, 0)])
    view.draw(belief, path=path, highlight={(1, 1): config.RENDER_TILE_END})
    print("✓ test_draw_survives_every_optional_argument passed")


def test_draw_accepts_a_caller_with_no_belief_map():
    """A route file carries no walls, so mode 6 and the editor have no belief."""
    view = _view(3, 3)
    view.draw(None)
    view.draw(None, path=[(0, 0), (0, 1)])
    assert view.belief_state("H", (0, 1), None) is False
    print("✓ test_draw_accepts_a_caller_with_no_belief_map passed")


def test_draw_places_the_mouse_without_raising():
    from sim.mouse import MouseState
    view = _view(3, 3)
    state = MouseState()
    state.reset_pose(90.0, 90.0, math.pi / 2.0)
    view.draw(MazeStructure(cols=3, rows=3), mouse=state)
    print("✓ test_draw_places_the_mouse_without_raising passed")


def test_cell_at_px_inverts_px():
    view = _view(6, 6)
    for cell in ((0, 0), (2, 3), (5, 5)):
        centre_mm = ((cell[0] + 0.5) * config.MM_PER_CELL,
                     (cell[1] + 0.5) * config.MM_PER_CELL)
        assert view.cell_at_px(view._px(*centre_mm)) == cell, cell
    print("✓ test_cell_at_px_inverts_px passed")


def test_cell_at_px_rejects_clicks_outside_the_grid():
    view = _view(3, 3)
    assert view.cell_at_px((0, 0)) is None            # inside the top margin
    assert view.cell_at_px((10_000, 10_000)) is None  # far off the board
    print("✓ test_cell_at_px_rejects_clicks_outside_the_grid passed")


TESTS = (
    test_a_renderer_constructs_at_every_grid_size,
    test_the_tile_scale_stays_clickable_and_bounded,
    test_a_click_lands_in_the_right_cell_at_every_grid_size,
    test_draw_paints_a_heading_arrow,
    test_make_renderer_returns_a_renderer_not_none,
    test_draw_survives_every_optional_argument,
    test_draw_accepts_a_caller_with_no_belief_map,
    test_draw_places_the_mouse_without_raising,
    test_cell_at_px_inverts_px,
    test_cell_at_px_rejects_clicks_outside_the_grid,
)


if __name__ == "__main__":
    if not HAS_PYGAME:
        print("SKIPPED: pygame is not installed (renderer tests need it)")
        sys.exit(0)
    for test in TESTS:
        test()
    print("ALL {} RENDERER SMOKE TESTS PASSED".format(len(TESTS)))
