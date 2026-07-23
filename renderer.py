import pygame
import time

import config
import maze

### Renderer Class-----------------------------------------------------------------------------------

class Renderer:
    #receives MazeGeometry object with a nested true MazeStructure and a belief MazeStructure
    def __init__(self, maze):
        pygame.init()
        self.maze = maze
        self.maze_height_mm = self.maze.structure.rows * config.MM_PER_CELL
        self.scale = int(config.PX_PER_MM*config.MM_PER_CELL)
        self.screen = pygame.display.set_mode((maze.structure.cols*self.scale+20, maze.structure.rows*self.scale+20))
        self.offset = 10
        self.clock = pygame.time.Clock()        # display throttle
        pygame.display.set_caption("Micro-Mouse")

    def draw(self, belief, mouse=None, path=None, done=None, animate=False):
        for event in pygame.event.get(): # Let the window be closed cleanly.
            if event.type == pygame.QUIT:
                self.close()
                raise SystemExit

        self.screen.fill((0,0,0)) # Will repalce with config nums later

        for post in self.maze.posts.values(): #unconditionally draw in all posts
            rect = self._rect_from_corners(post)
            pygame.draw.rect(self.screen, (255,255,255), rect)

        for wall, corners in self.maze.h_walls.items():
            rect = self._rect_from_corners(corners)
            known = self.belief_state("H", wall, belief)
            pygame.draw.rect(self.screen, (255,255,255) if known else (80,80,80), rect)

        for wall, corners in self.maze.v_walls.items():
            rect = self._rect_from_corners(corners)
            known = self.belief_state("V", wall, belief)
            pygame.draw.rect(self.screen, (255,255,255) if known else (80,80,80), rect)


        if done:
            post_size = config.POST_SIDE_MM
            cell_pitch = config.MM_PER_CELL
            for step in done:
                x, y = step
                # Cell interior corners in mm (excluding the post corners)
                bl = (x * cell_pitch + post_size, y * cell_pitch + post_size)
                br = ((x + 1) * cell_pitch, y * cell_pitch + post_size)
                tr = ((x + 1) * cell_pitch, (y + 1) * cell_pitch)
                tl = (x * cell_pitch + post_size, (y + 1) * cell_pitch)
                rect = self._rect_from_corners((bl, br, tr, tl))
                pygame.draw.rect(self.screen, (0, 180, 160), rect) # Vibrant teal for done tiles
            if animate:
                time.sleep(0.025) # nice animation
                pygame.display.flip()

        if path:
            post_size = config.POST_SIDE_MM
            cell_pitch = config.MM_PER_CELL
            for step in path:
                x, y = step
                # Cell interior corners in mm (excluding the post corners)
                bl = (x * cell_pitch + post_size, y * cell_pitch + post_size)
                br = ((x + 1) * cell_pitch, y * cell_pitch + post_size)
                tr = ((x + 1) * cell_pitch, (y + 1) * cell_pitch)
                tl = (x * cell_pitch + post_size, (y + 1) * cell_pitch)
                rect = self._rect_from_corners((bl, br, tr, tl))
                pygame.draw.rect(self.screen, (0, 90, 80), rect) # Faded teal for path tiles
                if animate:
                    time.sleep(0.05) # nice animation
                    pygame.display.flip()
        
        pygame.display.flip()
        self.clock.tick(60) # also replace with config num

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

### Test --------------------------------------------------------------------------------------------

if __name__ == "__main__":
    maze_struct = maze.MazeStructure(*maze.num_file_import(config.DEFAULT_MAZE)) # gen maze struct from file
    maze_actual = maze.MazeGeometry(maze_struct) # init obstacle features
    render = Renderer(maze_actual) # provide ground truth for renderer
    empty = maze.MazeStructure() # empty belief to compare it to
    while True: # continuously feed in empty belief - should always have an aligned perimeter wall with faded interior walls
        render.draw(empty, None)