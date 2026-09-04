"""Geometric helpers for hull metrics and line-breaker pipelines.

All functions operate in pitch meters (105 x 68). Use `to_meters` to convert
from the StatsBomb yard system before feeding any of the helpers.
"""
import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull, Delaunay

from . import config


def to_meters(point):
    """Convert a (x, y) point from StatsBomb yards to meters.

    Returns ``None`` if the input is None or NaN.
    """
    if point is None:
        return None
    try:
        if isinstance(point, float) and np.isnan(point):
            return None
    except Exception:
        pass
    return np.array([point[0] * config.X_SCALE, point[1] * config.Y_SCALE])


def is_inside_hull(hull_points, point) -> bool:
    """Robust point-in-hull test via Delaunay triangulation."""
    if len(hull_points) < 3 or point is None:
        return False
    try:
        return Delaunay(hull_points).find_simplex(point) >= 0
    except Exception:
        return False


def hull_area(points) -> float:
    """Convex hull area in m^2 (scipy's .volume is the 2D area for 2D input)."""
    if len(points) < 3:
        return np.nan
    try:
        return ConvexHull(points).volume
    except Exception:
        return np.nan


def count_opponents_within(point, opponents, radius: float = config.PRESSURE_RADIUS) -> int:
    """Number of opponents within ``radius`` meters from the point."""
    if len(opponents) == 0 or point is None:
        return 0
    dists = np.linalg.norm(opponents - point, axis=1)
    return int((dists <= radius).sum())


def mean_dist_k_nearest(point, opponents, k: int = config.K_NEAREST) -> float:
    """Mean distance from ``point`` to the k nearest opponents.

    Robust to outliers (a single faraway defender does not inflate the
    signal). If fewer than ``k`` opponents are available, uses all of them.
    """
    if len(opponents) == 0 or point is None:
        return np.nan
    dists = np.linalg.norm(opponents - point, axis=1)
    k_actual = min(k, len(dists))
    return float(np.sort(dists)[:k_actual].mean())


def get_zone(point_m,
             zone_x_bins: int = config.ZONE_X_BINS,
             zone_y_bins: int = config.ZONE_Y_BINS):
    """Map a position (in meters) to a (zone_x, zone_y) grid index."""
    if point_m is None:
        return None
    zx = int(np.clip(point_m[0] / config.PITCH_LENGTH_M * zone_x_bins, 0, zone_x_bins - 1))
    zy = int(np.clip(point_m[1] / config.PITCH_WIDTH_M  * zone_y_bins, 0, zone_y_bins - 1))
    return (zx, zy)


def count_bypassed(sx, sy, ex, ey, opps,
                   corridor_m: float = config.CORRIDOR_M) -> int:
    """Number of opponents inside the ``corridor_m`` band along the pass line.

    Uses scalar projection along the pass direction (must lie strictly
    between start and end) and perpendicular distance to the line. Returns 0
    if the pass has zero length or the inputs are missing.
    """
    if pd.isna(sx) or opps is None or len(opps) == 0:
        return 0
    vx, vy = ex - sx, ey - sy
    L = (vx * vx + vy * vy) ** 0.5
    if L < 1e-6:
        return 0
    n = 0
    for ox, oy in opps:
        ux, uy = ox - sx, oy - sy
        proj = (ux * vx + uy * vy) / L
        if 0 < proj < L:
            perp = abs(ux * vy - uy * vx) / L
            if perp <= corridor_m:
                n += 1
    return n
