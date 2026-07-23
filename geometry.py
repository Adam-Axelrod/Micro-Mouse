"""Continuous 2D geometry and raycasting engine for the micromouse simulation.

PC-only: the Pico never needs this module (see agent-context architectural tree).
It has real sensors returning true environment data directly; there is no
continuous mm-space maze to derive or raycast against. `maze.py` (MazeStructure)
is the only maze representation shared with the Pico.

Operates strictly in world coordinates (millimeters) anchored to config.MM_PER_CELL.
Builds wall/post polygons and the joined collision/raycast boundary from a
MazeStructure, and calculates exact raycast hit distances for the reflective
sensor simulation.
"""

import math
import config


def merge_intervals(intervals):
    """Merge overlapping or touching (lo, hi) 1D intervals into maximal spans.

    Pure interval-merge helper used to collapse a grid-line's wall intervals
    and post stubs into the joined boundary segments.
    """
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = [ordered[0]]
    for lo, hi in ordered[1:]:
        last_lo, last_hi = merged[-1]
        if lo <= last_hi:
            merged[-1] = (last_lo, max(last_hi, hi))
        else:
            merged.append((lo, hi))
    return merged


class MazeGeometry:  # render + collision class, PC-only
    """Continuous mm-space geometry derived from a MazeStructure, built once at load.

    Two layers:
      1. Source polygons (posts, h_walls, v_walls) -- per-cell objects with
         identity, used only for rendering.
      2. Derived boundary segments (vertical_boundaries, horizontal_boundaries,
         flattened into segments) -- the joined/merged centreline set shared by
         collision and raycasting (MazeSegments objects). Static, not
         recomputed per tick.

    Centreline model: boundary segments sit on the grid-line itself
    (x or y = k * MM_PER_CELL), not offset to the thick-wall faces. The ~6mm
    simplification is deliberate -- it's under the sensor noise floor, and
    collision is a terminal flag (no push-out), so exact faces aren't needed.
    See agent-context/00_PROJECT_STORY.md section 12 for the full decision log.
    """

    def __init__(self, structure):
        self.structure = structure  # MazeStructure object
        self.posts = self.generate_post_polygons()
        self.h_walls, self.v_walls = self.generate_wall_polygons()
        self.vertical_boundaries, self.horizontal_boundaries = self.generate_boundary_segments()
        self.segments = self.build_wall_segments()

    def generate_post_polygons(self):
        post_size = config.POST_SIDE_MM
        cell_pitch = config.MM_PER_CELL
        posts = {}
        for post_col in range(self.structure.cols + 1):
            for post_row in range(self.structure.rows + 1):
                left = post_col * cell_pitch
                bottom = post_row * cell_pitch
                posts[(post_col, post_row)] = (
                    (left, bottom),
                    (left + post_size, bottom),
                    (left + post_size, bottom + post_size),
                    (left, bottom + post_size),
                )
        return posts

    def generate_wall_polygons(self):
        """Per-cell wall face polygons (BL, BR, TR, TL), offset inward from the
        lattice by post_size so they sit flush against the post squares.
        Source layer -- rendering only, not the collision boundary."""
        post_size = config.POST_SIDE_MM
        cell_pitch = config.MM_PER_CELL
        cells = self.structure.cells
        h_walls, v_walls = {}, {}

        for span_col in range(self.structure.cols):
            for line_row in range(self.structure.rows + 1):
                cell_above = cells.get((span_col, line_row))
                cell_below = cells.get((span_col, line_row - 1))
                present = (cell_above and cell_above[config.WALL_INDEX["s"]]) or (cell_below and cell_below[config.WALL_INDEX["n"]])
                if present:
                    left = span_col * cell_pitch + post_size
                    right = (span_col + 1) * cell_pitch
                    bottom = line_row * cell_pitch
                    top = bottom + post_size
                    h_walls[(span_col, line_row)] = (
                        (left, bottom), (right, bottom), (right, top), (left, top)
                    )

        for line_col in range(self.structure.cols + 1):
            for span_row in range(self.structure.rows):
                cell_right = cells.get((line_col, span_row))
                cell_left = cells.get((line_col - 1, span_row))
                present = (cell_right and cell_right[config.WALL_INDEX["w"]]) or (cell_left and cell_left[config.WALL_INDEX["e"]])
                if present:
                    left = line_col * cell_pitch
                    right = left + post_size
                    bottom = span_row * cell_pitch + post_size
                    top = (span_row + 1) * cell_pitch
                    v_walls[(line_col, span_row)] = (
                        (left, bottom), (right, bottom), (right, top), (left, top)
                    )

        return h_walls, v_walls

    def generate_boundary_segments(self):
        """Derived boundary set (layer 2): treat each grid-line as a 1D number
        line, drop the wall intervals and post stubs onto it, then merge into
        maximal segments.

        Vertical boundaries live on column grid-lines (x = line_col * cell_pitch);
        horizontal boundaries live on row grid-lines (y = line_row * cell_pitch).
        Each present wall contributes a full-cell interval; every lattice point
        on the line contributes a small +/-post_size/2 stub (posts are always
        present per UK MARS rules). A run of connected walls collapses to one
        long segment; a post with no wall on this plane survives as an isolated
        stub -- it's still held in the maze by a wall on the perpendicular plane.
        """
        cell_pitch = config.MM_PER_CELL
        post_size = config.POST_SIDE_MM
        half_post = post_size / 2.0
        cells = self.structure.cells

        vertical_boundaries = []
        for line_col in range(self.structure.cols + 1):
            x = line_col * cell_pitch
            intervals = []
            for span_row in range(self.structure.rows):
                cell_right = cells.get((line_col, span_row))
                cell_left = cells.get((line_col - 1, span_row))
                present = (cell_right and cell_right[config.WALL_INDEX["w"]]) or (cell_left and cell_left[config.WALL_INDEX["e"]])
                if present:
                    intervals.append((span_row * cell_pitch, (span_row + 1) * cell_pitch))
            for post_row in range(self.structure.rows + 1):
                centre = post_row * cell_pitch
                intervals.append((centre - half_post, centre + half_post))
            for lo, hi in merge_intervals(intervals):
                vertical_boundaries.append(MazeSegments(x, lo, x, hi))

        horizontal_boundaries = []
        for line_row in range(self.structure.rows + 1):
            y = line_row * cell_pitch
            intervals = []
            for span_col in range(self.structure.cols):
                cell_above = cells.get((span_col, line_row))
                cell_below = cells.get((span_col, line_row - 1))
                present = (cell_above and cell_above[config.WALL_INDEX["s"]]) or (cell_below and cell_below[config.WALL_INDEX["n"]])
                if present:
                    intervals.append((span_col * cell_pitch, (span_col + 1) * cell_pitch))
            for post_col in range(self.structure.cols + 1):
                centre = post_col * cell_pitch
                intervals.append((centre - half_post, centre + half_post))
            for lo, hi in merge_intervals(intervals):
                horizontal_boundaries.append(MazeSegments(lo, y, hi, y))

        return vertical_boundaries, horizontal_boundaries

    def build_wall_segments(self):
        """Flatten the two merged boundary families into one list, in mm world
        coordinates, for raycasting (cast_ray) and collision. Static -- built
        once in __init__, not recomputed per tick."""
        return self.vertical_boundaries + self.horizontal_boundaries


class MazeSegments:
    def __init__(self, start_x, start_y, end_x, end_y):
        self.x1 = start_x
        self.y1 = start_y
        self.x2 = end_x
        self.y2 = end_y

    def tuple_repr(self):
        point1 = (round(self.x1, 3), round(self.y1, 3))
        point2 = (round(self.x2, 3), round(self.y2, 3))
        if point1 <= point2:
            return (point1, point2)
        else:
            return (point2, point1)


Segment = MazeSegments


### this provides the information to the simulated pin to fabricate a light intensity
### the neural net will in effect be doing this in its hidden layers should we provide the sensors as input
def cast_ray(ray_origin, ray_angle_radians, wall_segments, max_range_mm=300.0): # not a fan of the name ray cast, this is just calculating trig distances
    """Cast a 2D ray from ray_origin=(x, y) at ray_angle_radians.

    Returns the distance (in mm) to the nearest segment intersection, capped at max_range_mm.
    """
    origin_x, origin_y = ray_origin
    ray_dir_x = math.cos(ray_angle_radians)
    ray_dir_y = math.sin(ray_angle_radians)

    minimum_distance_mm = max_range_mm

    for segment in wall_segments:
        seg_x1, seg_y1 = segment.x1, segment.y1
        seg_x2, seg_y2 = segment.x2, segment.y2
        seg_delta_x = seg_x2 - seg_x1
        seg_delta_y = seg_y2 - seg_y1

        denominator = ray_dir_x * seg_delta_y - ray_dir_y * seg_delta_x
        if abs(denominator) < 1e-9:
            continue  # Parallel or collinear

        distance_along_ray = ((seg_x1 - origin_x) * seg_delta_y - (seg_y1 - origin_y) * seg_delta_x) / denominator
        distance_along_segment = ((seg_x1 - origin_x) * ray_dir_y - (seg_y1 - origin_y) * ray_dir_x) / denominator

        if distance_along_ray >= 0.0 and 0.0 <= distance_along_segment <= 1.0:
            if distance_along_ray < minimum_distance_mm:
                minimum_distance_mm = distance_along_ray

    return minimum_distance_mm
