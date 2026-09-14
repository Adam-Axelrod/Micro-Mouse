import math
import time

import pygame

import config
from brain import maze
from sim import geometry

def _load_font(size_px):
    """A pygame font, or None where fonts are unavailable (some headless runners).

    Text is never load-bearing here: every caller draws the same picture without
    it, so a missing font costs labels and nothing else.
    """
    try:
        pygame.font.init()
        return pygame.font.Font(None, size_px)
    except Exception as exc:
        print("Fonts unavailable ({}: {}); drawing without labels.".format(
            type(exc).__name__, exc))
        return None


def tile_px_for(cols, rows):
    """Cell size in pixels so a `cols` x `rows` maze fills the target window.

    A fixed scale cannot serve both grids the project uses: the physical test
    maze is 3x3 and the competition maze is 16x16. Clamped at both ends, because
    a cell too small cannot be clicked and a cell too large wins nothing.
    """
    longest_side = max(cols, rows)
    fitted = config.RENDER_TARGET_WINDOW_PX // longest_side
    return int(max(config.RENDER_MIN_TILE_PX, min(config.RENDER_MAX_TILE_PX, fitted)))


def make_renderer(real_maze, hud_px=0):
    """A Renderer for `real_maze`, or None if the display will not start.

    Every mode wants the same three lines: build the mm-space geometry, open a
    window, and carry on headless if that fails (no display, no pygame, a remote
    shell). Put here rather than in a mode module so no mode has to import
    another mode to draw.

    `hud_px` reserves a status strip under the maze. Only the route editor uses
    it; every other mode gets the window it always had.
    """
    try:
        return Renderer(geometry.MazeGeometry(real_maze), hud_px)
    except Exception as exc:
        print("Renderer init failed ({}: {}); continuing without rendering.".format(
            type(exc).__name__, exc))
        return None


### Renderer Class

class Renderer:
    # receives MazeGeometry object with a nested true MazeStructure and a belief MazeStructure
    def __init__(self, maze, hud_px=0):
        pygame.init()
        self.hud_px = hud_px
        self.font = _load_font(config.RENDER_HUD_FONT_PX)
        self.maze = maze
        self.maze_height_mm = self.maze.structure.rows * config.MM_PER_CELL
        self.scale = tile_px_for(maze.structure.cols, maze.structure.rows)
        self.px_per_mm = self.scale / float(config.MM_PER_CELL)
        # The margin is assigned BEFORE set_mode uses it. It was the other way
        # round briefly, which made every Renderer raise AttributeError; the
        # exception went unseen because make_renderer catches it and carries on
        # headless, and no automated run passed --render.
        self.offset = config.RENDER_MARGIN_PX
        self.screen = pygame.display.set_mode((maze.structure.cols * self.scale + 2 * self.offset,
             maze.structure.rows * self.scale + 2 * self.offset + self.hud_px))
        self.clock = pygame.time.Clock()        # display throttle
        pygame.display.set_caption("Micro-Mouse")

    def draw(self, belief, mouse=None, path=None, done=None, animate=False,
             highlight=None, heading_marks=None, route=None, status=None):
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

        if highlight and not route:  # {cell: colour}, painted over path/done
            for cell, colour in highlight.items():
                self._fill_cell(cell, colour)

        if route:  # an ORDERED cell list: the line and its arrows carry the order
            for step in route:
                self._fill_cell(step, config.RENDER_TILE_PATH)

        if highlight:  # repainted after the route fill so start/end still win
            for cell, colour in highlight.items():
                self._fill_cell(cell, colour)

        if route:
            self._draw_route_line(route)
            self._draw_step_labels(route)
            self._draw_end_ring(route[-1])

        if heading_marks:  # {cell: compass side}, an arrow through the cell centre
            for cell, side in heading_marks.items():
                self._draw_heading_arrow(cell, side)

        if mouse is not None:
            self._draw_mouse(mouse)

        if self.hud_px:
            self._draw_hud(status or ())

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

    def _cell_centre_mm(self, cell):
        return ((cell[0] + 0.5) * config.MM_PER_CELL,
                (cell[1] + 0.5) * config.MM_PER_CELL)

    def _draw_route_line(self, route):
        """Join the route's cell centres in order, with an arrow on each step.

        A flat fill over every visited cell says WHICH cells, never in what order
        or which way, and a route is nothing but an order. Doubling back draws
        two arrows head to head, which is the picture the operator needs.
        """
        centres_px = [self._px(*self._cell_centre_mm(cell)) for cell in route]
        if len(centres_px) > 1:
            pygame.draw.lines(self.screen, config.RENDER_ROUTE_LINE, False, centres_px,
                              config.RENDER_ROUTE_LINE_PX)
        for start_cell, end_cell in zip(route, route[1:]):
            self._draw_step_arrow(start_cell, end_cell)

    def _draw_step_arrow(self, from_cell, to_cell):
        """An arrowhead at the midpoint of one step, pointing the way it travels."""
        from_mm = self._cell_centre_mm(from_cell)
        to_mm = self._cell_centre_mm(to_cell)
        midpoint_mm = ((from_mm[0] + to_mm[0]) / 2.0, (from_mm[1] + to_mm[1]) / 2.0)
        span_mm = math.hypot(to_mm[0] - from_mm[0], to_mm[1] - from_mm[1])
        if span_mm == 0:
            return
        dx = (to_mm[0] - from_mm[0]) / span_mm
        dy = (to_mm[1] - from_mm[1]) / span_mm
        reach_mm = config.MM_PER_CELL * config.RENDER_ROUTE_ARROW_FRACTION
        tip_mm = (midpoint_mm[0] + dx * reach_mm, midpoint_mm[1] + dy * reach_mm)
        pygame.draw.polygon(self.screen, config.RENDER_ROUTE_LINE, [
            self._px(*tip_mm),
            self._px(tip_mm[0] - dx * reach_mm - dy * reach_mm * 0.7,
                     tip_mm[1] - dy * reach_mm + dx * reach_mm * 0.7),
            self._px(tip_mm[0] - dx * reach_mm + dy * reach_mm * 0.7,
                     tip_mm[1] - dy * reach_mm - dx * reach_mm * 0.7),
        ])

    def _draw_step_labels(self, route):
        """Number each cell by the step it is visited on. A revisit lists both.

        Skipped when the cells are too small to hold a number, which is the
        16x16 case: the arrows still carry the order there.
        """
        if self.font is None or self.scale < config.RENDER_ROUTE_LABEL_MIN_TILE_PX:
            return
        visits = {}
        for step_number, cell in enumerate(route, start=1):
            visits.setdefault(cell, []).append(str(step_number))
        label_font = _load_font(int(self.scale * config.RENDER_ROUTE_LABEL_FONT_FRACTION))
        if label_font is None:
            return
        for cell, step_numbers in visits.items():
            text = label_font.render(",".join(step_numbers), True, config.RENDER_ROUTE_LABEL)
            corner_mm = (cell[0] * config.MM_PER_CELL + config.POST_SIDE_MM * 1.5,
                         (cell[1] + 1) * config.MM_PER_CELL - config.POST_SIDE_MM * 1.5)
            self.screen.blit(text, self._px(*corner_mm))

    def _draw_end_ring(self, cell):
        """Ring the route's last cell. A fill colour alone reads as one more cell."""
        inset_mm = config.MM_PER_CELL * config.RENDER_END_RING_INSET
        corner_px = self._px(cell[0] * config.MM_PER_CELL + inset_mm,
                             (cell[1] + 1) * config.MM_PER_CELL - inset_mm)
        side_px = (config.MM_PER_CELL - 2 * inset_mm) * self.px_per_mm
        pygame.draw.rect(self.screen, config.RENDER_END_RING,
                         (corner_px[0], corner_px[1], side_px, side_px),
                         config.RENDER_END_RING_PX)

    def _draw_hud(self, lines):
        """The status strip under the maze: what is drawn, and which key does what."""
        strip = (0, self.screen.get_height() - self.hud_px,
                 self.screen.get_width(), self.hud_px)
        pygame.draw.rect(self.screen, config.RENDER_HUD_BACKGROUND, strip)
        if self.font is None:
            return
        y = strip[1] + (self.hud_px - len(lines) * config.RENDER_HUD_LINE_PX) / 2.0
        for line in lines:
            self.screen.blit(self.font.render(line, True, config.RENDER_HUD_TEXT),
                             (self.offset, y))
            y += config.RENDER_HUD_LINE_PX

    def _draw_heading_arrow(self, cell, side):
        """Point an arrow out of a cell along a compass side.

        The route editor needs to show which way the robot is placed: a .mmc is
        a list of egocentric verbs, so the same file drives a different shape
        depending on the start heading, and that is invisible from the cells.
        """
        dx, dy = config.SIDE_DELTA[side]
        centre_mm = ((cell[0] + 0.5) * config.MM_PER_CELL,
                     (cell[1] + 0.5) * config.MM_PER_CELL)
        reach_mm = config.MM_PER_CELL * 0.35
        tip_mm = (centre_mm[0] + dx * reach_mm, centre_mm[1] + dy * reach_mm)
        barb_mm = reach_mm * 0.4
        head = [
            self._px(*tip_mm),
            self._px(tip_mm[0] - dx * barb_mm - dy * barb_mm,
                     tip_mm[1] - dy * barb_mm + dx * barb_mm),
            self._px(tip_mm[0] - dx * barb_mm + dy * barb_mm,
                     tip_mm[1] - dy * barb_mm - dx * barb_mm),
        ]
        pygame.draw.line(self.screen, config.RENDER_HEADING_ARROW,
                         self._px(centre_mm[0] - dx * reach_mm, centre_mm[1] - dy * reach_mm),
                         self._px(*tip_mm), config.RENDER_HEADING_ARROW_PX)
        pygame.draw.polygon(self.screen, config.RENDER_HEADING_ARROW, head)

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
        x_mm = (x_px - self.offset) / self.px_per_mm
        y_mm = self.maze_height_mm - (y_px - self.offset) / self.px_per_mm
        x = int(x_mm // config.MM_PER_CELL)
        y = int(y_mm // config.MM_PER_CELL)
        if 0 <= x < self.maze.structure.cols and 0 <= y < self.maze.structure.rows:
            return (x, y)
        return None

    """World mm -> screen px, flipping the y-axis (maze 0,0 bottom-left; pygame 0,0 top-left)."""
    def _px(self, x_mm, y_mm):
        return (x_mm * self.px_per_mm + self.offset,
                (self.maze_height_mm - y_mm) * self.px_per_mm + self.offset)

    """Turn a (BL, BR, TR, TL) mm-corner polygon into a pygame (x, y, w, h) rect, deriving width/height
    straight from the corners instead of a hardcoded config constant, and flipping the y-axis (maze 0,0 is 
    bottom-left; pygame 0,0 is top-left)."""
    def _rect_from_corners(self, corners):
        bl, br, tr, tl = corners
        width_mm  = br[0] - bl[0]
        height_mm = tl[1] - bl[1]
        x = bl[0] * self.px_per_mm + self.offset
        y = (self.maze_height_mm - bl[1] - height_mm) * self.px_per_mm + self.offset
        w = width_mm * self.px_per_mm
        h = height_mm * self.px_per_mm
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