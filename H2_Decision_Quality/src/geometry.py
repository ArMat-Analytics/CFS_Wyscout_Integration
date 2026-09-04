"""Geometric helpers used by the H2 feature engineering layer.

Mirrors the two H1 primitives used by the xPass features (`count_bypassed`
and `count_opponents_within`). Inlined here so H2 has no import dependency
on H1's `src/`. All inputs are in pitch metres (105 × 68).
"""
import numpy as np
import pandas as pd

from . import config


def count_opponents_within(point, opponents,
                            radius: float = config.PRESSURE_RADIUS) -> int:
    """Number of opponents within ``radius`` meters from the point."""
    if len(opponents) == 0 or point is None:
        return 0
    dists = np.linalg.norm(opponents - point, axis=1)
    return int((dists <= radius).sum())


def count_bypassed(sx, sy, ex, ey, opps,
                   corridor_m: float = config.CORRIDOR_M) -> int:
    """Number of opponents inside the ``corridor_m`` band along the pass line.

    Uses scalar projection along the pass direction (must lie strictly
    between start and end) and perpendicular distance to the line. Returns
    0 if the pass has zero length or the inputs are missing.
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
