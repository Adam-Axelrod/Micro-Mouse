"""Pure-math world geometry: walls as line segments, raycasting and circle collision.

There is deliberately NO pygame in this module. Keeping the geometry pure is what
lets the simulation run headless and fast, and makes the eventual 3D swap clean.

All coordinates are screen pixels (y increases downward). The maze's y-up
convention is flipped exactly once, in :func:`build_wall_segments` (and mirrored
in :meth:`Maze.cell_to_world`).
"""
from __future__ import annotations

import math

from .maze_loader import Walls

Point = tuple[float, float]
Segment = tuple[Point, Point]   # an axis-aligned wall, ((x1, y1), (x2, y2))


def build_wall_segments(walls: Walls, tile: float, height: int) -> list[Segment]:
    """Convert each cell's wall flags into de-duplicated screen-space segments."""
    segments: set[Segment] = set()
    for (x, y), (n, e, s, w) in walls.items():
        # Screen row 0 is the top; maze y grows upward, so flip it here (once).
        top = (height - 1 - y) * tile
        left = x * tile
        right = left + tile
        bottom = top + tile
        if n:  # north (maze-up) -> top edge on screen
            segments.add(((left, top), (right, top)))
        if s:  # south -> bottom edge
            segments.add(((left, bottom), (right, bottom)))
        if e:  # east -> right edge
            segments.add(((right, top), (right, bottom)))
        if w:  # west -> left edge
            segments.add(((left, top), (left, bottom)))
    # Adjacent cells share edges; the set above already removes the duplicates.
    return list(segments)


def closest_point_on_segment(p: Point, seg: Segment) -> Point:
    """Nearest point to `p` lying on the line segment `seg`."""
    (x1, y1), (x2, y2) = seg
    px, py = p
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:          # degenerate segment (a point)
        return (x1, y1)
    # Project p onto the segment, clamped to the [start, end] range.
    t = ((px - x1) * dx + (py - y1) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return (x1 + t * dx, y1 + t * dy)


def _segment_normal(seg: Segment) -> Point:
    """A unit vector perpendicular to the segment (used as a fallback push)."""
    (x1, y1), (x2, y2) = seg
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0
    return (-dy / length, dx / length)


def resolve_circle_collision(
    center: Point, radius: float, segments: list[Segment]
) -> tuple[Point, bool]:
    """Push a circle out of every wall segment it overlaps.

    The mouse is modelled as a circle of `radius` centred at `center`. For each
    wall we find the closest point on that wall to the circle's centre. If the
    centre is nearer than `radius`, the circle overlaps the wall, so we slide it
    straight back out along the line joining the wall to the centre.

    Returns ``(corrected_center, collided)``.
    """
    cx, cy = center
    collided = False

    for seg in segments:
        nearest_x, nearest_y = closest_point_on_segment((cx, cy), seg)
        offset_x = cx - nearest_x
        offset_y = cy - nearest_y
        distance = math.hypot(offset_x, offset_y)

        if distance < radius:                       # overlapping this wall
            collided = True
            if distance > 1e-9:
                # Unit vector pointing from the wall to the circle's centre.
                push_x = offset_x / distance
                push_y = offset_y / distance
            else:
                # Centre sits exactly on the wall: push along its perpendicular.
                push_x, push_y = _segment_normal(seg)
            overlap = radius - distance
            cx += push_x * overlap
            cy += push_y * overlap

    return (cx, cy), collided


def ray_segment_intersection(origin: Point, angle: float, seg: Segment) -> float | None:
    """Distance from `origin` along `angle` to where it first hits `seg`.

    Returns the distance (>= 0), or None if the ray misses the segment.
    Solves ``origin + t * ray_dir == p1 + u * seg_dir`` for ``t >= 0`` and
    ``0 <= u <= 1``.
    """
    ox, oy = origin
    rdx, rdy = math.cos(angle), math.sin(angle)
    (x1, y1), (x2, y2) = seg
    sdx, sdy = x2 - x1, y2 - y1

    denom = rdx * sdy - rdy * sdx
    if abs(denom) < 1e-12:
        return None                                  # ray and segment are parallel

    t = ((x1 - ox) * sdy - (y1 - oy) * sdx) / denom  # distance along the ray
    u = ((x1 - ox) * rdy - (y1 - oy) * rdx) / denom  # position along the segment
    if t >= 0.0 and 0.0 <= u <= 1.0:
        return t
    return None


def cast_ray(origin: Point, angle: float, segments: list[Segment], max_dist: float) -> float:
    """Nearest wall-hit distance along `angle`, normalised to [0, 1] by `max_dist`.

    Returns 1.0 when nothing is hit within range.
    """
    nearest = max_dist
    for seg in segments:
        hit = ray_segment_intersection(origin, angle, seg)
        if hit is not None and hit < nearest:
            nearest = hit
    return nearest / max_dist
