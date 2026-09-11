import math
import time

import pygame

import config
import maze
from sim import geometry

def make_renderer(real_maze):
    """A Renderer for `real_maze`, or None if the display will not start.

    Every mode wants the same three lines: build the mm-space geometry, open a
    window, and carry on headless if that fails (no display, no pygame, a remote
    shell). Put here rather than in a mode module so no mode has to import
    another mode to draw.
    """
    try:
        return Renderer(geometry.MazeGeometry(real_maze))
    except Exception as exc:
        print("Renderer init failed ({}: {}); continuing without rendering.".format(
            type(exc).__name__, exc))
        return None


### Renderer Class

class Renderer:
    # receives MazeGeometry object with a nested true MazeStructure and a belief MazeStructure
    def __init__(self, maze):
        pygame.init()
        self.maze = maze
        self.maze_height_mm = self.maze.structure.rows * config.MM_PER_CELL
        self.scale = int(config.TILE_PX)
        # The margin is assigned BEFORE set_mode uses it. It was the other way
        # round briefly, which made every Renderer raise AttributeError; the
        # exception went unseen because make_renderer catches it and carries on
        # headless, and no automated run passed --render.
        self.offset = config.RENDER_MARGIN_PX
        self.screen = pygame.display.set_mode((maze.structure.cols * self.scale + 2 * self.offset,
             maze.structure.rows * self.scale + 2 * self.offset))
        self.clock = pygame.time.Clock()        # display throttle
        pygame.display.set_caption("Micro-Mouse")

    def draw(self, belief, mouse=None, path=None, done=None, animate=False,
             highlight=None):
        for event in pygame.event.get(): # Let the window be closed cleanly.
            if event.type == pygame.QUIT:
                self.close()
                raise SystemExit

        self.screen.fill(config.RENDER_BACKGROUND)

        for post in self.maze.posts.values(): # Unconditionally draw in all posts
            rect = self._rect_from_corners(post)
            pygame.draw.rect(self.screen, config.RENDER_WALL_KNOWN, rect)

        for wall, corners in self.maze.h_walls.items():
            rect = self._rect_from_corners(corners)
            known = self.belief_state("H", wall, belief)
            pygame.draw.rect(
                self.screen,
                config.RENDER_WALL_KNOWN if known else config.RENDER_WALL_UNKNOWN,
                rect)

        for wall, corners in self.maze.v_walls.items():
            rect = self._rect_from_corners(corners)
            known = self.belief_state("V", wall, belief)
            pygame.draw.rect(
                self.screen,
                config.RENDER_WALL_KNOWN if known else config.RENDER_WALL_UNKNOWN,
                rect)


        if done:
            for step in done:
                self._fill_cell(step, config.RENDER_TILE_DONE)
            if animate:
                time.sleep(config.RENDER_DONE_STEP_DELAY_S)
                pygame.display.flip()

        if path:
            for step in path:
                self._fill_cell(step, config.RENDER_TILE_PATH)
                if animate:
                    time.sleep(config.RENDER_PATH_STEP_DELAY_S)
                    pygame.display.flip()

        if highlight:  # {cell: colour}, painted last so it wins over path/done
            for cell, colour in highlight.items():
                self._fill_cell(cell, colour)

        if mouse is not None:
            self._draw_mouse(mouse)

        pygame.display.flip()
        self.clock.tick(config.RENDER_FPS)

    """Echo the sim's continuous pose as a rotated chassis rectangle. Pure observer: samples
    MouseState (x_mm, y_mm, heading_radians) and the config chassis constants; body frame is
    +y forward / +x right around the wheel axle, matching MouseState's sensor frame. The
    yellow nose line points along heading."""
    def _draw_mouse(self, mouse):
        cos_h = math.cos(mouse.heading_radians)
        sin_h = math.sin(mouse.heading_radians)
        half_width = config.BODY_WIDTH_MM / 2.0
        corners_body = (  # (forward, lateral) offsets from the axle centre
            (config.WHEEL_AXIS_TO_FRONT_MM, -half_width),
            (config.WHEEL_AXIS_TO_FRONT_MM,  half_width),
            (-config.WHEEL_AXIS_TO_BACK_MM,  half_width),
            (-config.WHEEL_AXIS_TO_BACK_MM, -half_width),
        )
        points_px = [self._px(mouse.x_mm + fwd * cos_h - lat * sin_h,
                              mouse.y_mm + fwd * sin_h + lat * cos_h)
                     for fwd, lat in corners_body]
        pygame.draw.polygon(self.screen, config.RENDER_MOUSE_BODY, points_px,
                            config.RENDER_MOUSE_OUTLINE_PX)
        nose = self._px(mouse.x_mm + config.WHEEL_AXIS_TO_FRONT_MM * cos_h,
                        mouse.y_mm + config.WHEEL_AXIS_TO_FRONT_MM * sin_h)
        pygame.draw.line(self.screen, config.RENDER_MOUSE_NOSE,
                         self._px(mouse.x_mm, mouse.y_mm), nose,
                         config.RENDER_MOUSE_OUTLINE_PX)

    def _fill_cell(self, cell, colour):
        """Paint one cell's interior, stopping short of the post corners."""
        x, y = cell
        post_size = config.POST_SIDE_MM
        cell_pitch = config.MM_PER_CELL
        bl = (x * cell_pitch + post_size, y * cell_pitch + post_size)
        br = ((x + 1) * cell_pitch, y * cell_pitch + post_size)
        tr = ((x + 1) * cell_pitch, (y + 1) * cell_pitch)
        tl = (x * cell_pitch + post_size, (y + 1) * cell_pitch)
        pygame.draw.rect(self.screen, colour, self._rect_from_corners((bl, br, tr, tl)))

    def poll_input(self):
        """Drain the window's event queue and return it in GRID terms, not pixels.

        Records are ("click", (x, y)) for a left click inside a cell and
        ("key", name) for a key press, where `name` is pygame's own key name
        ("s", "c", "escape"). A QUIT closes the window and raises SystemExit, the
        same way `draw` does. This lives here because the renderer owns the only
        mm-to-pixel mapping in the codebase, so it owns the inverse too: a caller
        that needs mouse input must not have to know PX_PER_MM.
        """
        records = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.close()
                raise SystemExit
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                cell = self.cell_at_px(event.pos)
                if cell is not None:
                    records.append(("click", cell))
            elif event.type == pygame.KEYDOWN:
                records.append(("key", pygame.key.name(event.key)))
        return records

    def cell_at_px(self, position_px):
        """Inverse of `_px`: a screen pixel -> the cell under it, or None if outside."""
        x_px, y_px = position_px
        x_mm = (x_px - self.offset) / config.PX_PER_MM
        y_mm = self.maze_height_mm - (y_px - self.offset) / config.PX_PER_MM
        x = int(x_mm // config.MM_PER_CELL)
        y = int(y_mm // config.MM_PER_CELL)
        if 0 <= x < self.maze.structure.cols and 0 <= y < self.maze.structure.rows:
            return (x, y)
        return None

    """World mm -> screen px, flipping the y-axis (maze 0,0 bottom-left; pygame 0,0 top-left)."""
    def _px(self, x_mm, y_mm):
        return (x_mm * config.PX_PER_MM + self.offset,
                (self.maze_height_mm - y_mm) * config.PX_PER_MM + self.offset)

    """Turn a (BL, BR, TR, TL) mm-corner polygon into a pygame (x, y, w, h) rect, deriving width/height
    straight from the corners instead of a hardcoded config constant, and flipping the y-axis (maze 0,0 is 
    bottom-left; pygame 0,0 is top-left)."""
    def _rect_from_corners(self, corners):
        bl, br, tr, tl = corners
        width_mm  = br[0] - bl[0]
        height_mm = tl[1] - bl[1]
        x = bl[0] * config.PX_PER_MM + self.offset
        y = (self.maze_height_mm - bl[1] - height_mm) * config.PX_PER_MM + self.offset
        w = width_mm * config.PX_PER_MM
        h = height_mm * config.PX_PER_MM
        return (x, y, w, h)

    def belief_state(self, orientation, key, belief):
        """Has the belief map recorded this wall? No belief = nothing known yet.

        Mode 6 follows a route file, which carries no walls, and the route editor
        draws a bare maze, so a caller may legitimately have no belief. Both
        render every wall as unknown rather than raising.
        """
        if belief is None:
            return False
        if orientation == "H":
            span_col, line_row = key
            cell_above = belief.cells.get((span_col, line_row))
            cell_below = belief.cells.get((span_col, line_row - 1))
            return bool((cell_above and cell_above[config.WALL_INDEX["s"]]) or
                        (cell_below and cell_below[config.WALL_INDEX["n"]]))
        else:  # "V"
            line_col, span_row = key
            cell_right = belief.cells.get((line_col, span_row))
            cell_left  = belief.cells.get((line_col - 1, span_row))
            return bool((cell_right and cell_right[config.WALL_INDEX["w"]]) or
                        (cell_left and cell_left[config.WALL_INDEX["e"]]))

    def close(self):
        pygame.quit()

### Test

if __name__ == "__main__":
    maze_struct = maze.MazeStructure(*maze.num_file_import(config.DEFAULT_MAZE)) # gen maze struct from file
    maze_actual = geometry.MazeGeometry(maze_struct) # init obstacle features
    render = Renderer(maze_actual) # provide ground truth for renderer
    empty = maze.MazeStructure() # empty belief to compare it to
    while True: # continuously feed in empty belief - should always have an aligned perimeter wall with faded interior walls
        render.draw(empty, None)