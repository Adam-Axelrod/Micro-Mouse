"""Continuous 2D geometry and raycasting engine for the micromouse simulation.

Operates strictly in world coordinates (millimeters) anchored to config.MM_PER_CELL.
Computes wall line segments from a MazeStructure and calculates exact raycast hit
distances for the reflective sensor simulation.
"""

import math
import config

class MazeGeometry:
    def __init__(self, structure):
        self.structure = structure #MazeStructure object
        self.posts = self.generate_post_polygons()
        self.h_walls, self.v_walls = self.generate_wall_polygons()
        
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
                    bottom = line_row * cell_pitch
                    h_walls[(span_col, line_row)] = (
                        (left, bottom), (span_col + 1) * cell_pitch, bottom + post_size
                    )

        for line_col in range(self.structure.cols + 1):
            for span_row in range(self.structure.rows):
                cell_right = cells.get((line_col, span_row))
                cell_left = cells.get((line_col - 1, span_row))
                present = (cell_right and cell_right[config.WALL_INDEX["w"]]) or (cell_left and cell_left[config.WALL_INDEX["e"]])
                if present:
                    left = line_col * cell_pitch
                    bottom = span_row * cell_pitch + post_size
                    v_walls[(line_col, span_row)] = (
                        left, bottom, left + post_size, (span_row + 1) * cell_pitch
                    )
        return h_walls, v_walls



class Segment:
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


def build_wall_segments(maze):
    """Convert a MazeStructure into a deduplicated list of 2D line segments in mm space."""
    cell_size_mm = config.MM_PER_CELL
    raw_segments = set()

    for (column, row), walls in maze.cells.items():
        cell_min_x = column * cell_size_mm
        cell_max_x = (column + 1) * cell_size_mm
        cell_min_y = row * cell_size_mm
        cell_max_y = (row + 1) * cell_size_mm

        # walls: (north, east, south, west)
        north_wall, east_wall, south_wall, west_wall = walls
        if north_wall:
            segment = Segment(cell_min_x, cell_max_y, cell_max_x, cell_max_y)
            raw_segments.add(segment.tuple_repr())
        if east_wall:
            segment = Segment(cell_max_x, cell_min_y, cell_max_x, cell_max_y)
            raw_segments.add(segment.tuple_repr())
        if south_wall:
            segment = Segment(cell_min_x, cell_min_y, cell_max_x, cell_min_y)
            raw_segments.add(segment.tuple_repr())
        if west_wall:
            segment = Segment(cell_min_x, cell_min_y, cell_min_x, cell_max_y)
            raw_segments.add(segment.tuple_repr())

    segment_list = []
    for point1, point2 in sorted(raw_segments):
        segment_list.append(Segment(point1[0], point1[1], point2[0], point2[1]))
    return segment_list


def cast_ray(ray_origin, ray_angle_radians, wall_segments, max_range_mm=300.0):
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
