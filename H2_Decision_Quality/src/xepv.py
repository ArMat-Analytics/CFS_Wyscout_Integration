"""xEPV layer for H2.

For each candidate (sender, target) pair in `alternatives.parquet`,
attaches the expected Expected-Possession-Value (EPV) of the pass.

Formulation (symmetric mirror penalty):

    epv_target := EPV(target_x, target_y)              — value if pass arrives
    epv_mirror := EPV(105 - target_x, target_y)        — opponent's EPV from
                                                          the same world point
                                                          flipped along the
                                                          long axis
    xepv       := xpass · epv_target
                  - (1 - xpass) · XEPV_FAILURE_SCALE · epv_mirror

The second term penalises turnovers using the symmetric counterfactual:
if the pass is intercepted, the opponent attacks from the mirrored
location. XEPV_FAILURE_SCALE defaults to 1.0 (full mirror penalty);
lower values soften the penalty if it turns out to discourage ambitious
passes too aggressively (e.g. 0.5).

The EPV grid is the 32 x 50 lookup from H1 (rows=Y/width,
cols=X/length, attacking direction = increasing X), already in meters
on the UEFA 105 x 68 pitch.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as cfg


# =============================================================================
# Grid I/O
# =============================================================================
def load_epv_grid(path: Path | None = None) -> np.ndarray:
    """Load the EPV grid (rows=Y/width, cols=X/length)."""
    p = Path(path) if path is not None else cfg.EPV_GRID_PATH
    return pd.read_csv(p, header=None).values.astype(float)


# =============================================================================
# Vectorised bilinear interpolation
# =============================================================================
def epv_at(grid: np.ndarray, x_m, y_m) -> np.ndarray:
    """Bilinear EPV lookup at (x, y) in meters. NaN-safe, vectorised.

    Mirrors H1's `epv_pipeline._epv_at` formula but accepts arrays.
    Coordinates outside the pitch are clipped to the edge.
    """
    x = np.asarray(x_m, dtype=float)
    y = np.asarray(y_m, dtype=float)
    rows, cols = grid.shape
    col_c = np.clip(x / cfg.PITCH_LENGTH_M * cols, 0, cols - 1.0001)
    row_c = np.clip(y / cfg.PITCH_WIDTH_M  * rows, 0, rows - 1.0001)
    col_lo = col_c.astype(int)
    row_lo = row_c.astype(int)
    fx = col_c - col_lo
    fy = row_c - row_lo
    v_tl = grid[row_lo,     col_lo]
    v_tr = grid[row_lo,     col_lo + 1]
    v_bl = grid[row_lo + 1, col_lo]
    v_br = grid[row_lo + 1, col_lo + 1]
    out = (v_tl * (1 - fx) * (1 - fy) + v_tr * fx * (1 - fy) +
           v_bl * (1 - fx) * fy       + v_br * fx * fy)
    nan_mask = np.isnan(x) | np.isnan(y)
    return np.where(nan_mask, np.nan, out)


# =============================================================================
# xEPV computation
# =============================================================================
def compute_xepv(alt: pd.DataFrame, grid: np.ndarray,
                 failure_scale: float | None = None) -> pd.DataFrame:
    """Attach `epv_target`, `epv_mirror`, `xepv` columns to `alt`.

    `failure_scale` defaults to `cfg.XEPV_FAILURE_SCALE` (1.0 = full
    mirror penalty). Returns a copy.
    """
    scale = cfg.XEPV_FAILURE_SCALE if failure_scale is None else failure_scale
    out = alt.copy()
    out['epv_target'] = epv_at(grid, out['target_x_m'].values,
                                     out['target_y_m'].values)
    out['epv_mirror'] = epv_at(grid,
                               cfg.PITCH_LENGTH_M - out['target_x_m'].values,
                               out['target_y_m'].values)
    out['xepv'] = (out['xpass']        * out['epv_target']
                   - (1 - out['xpass']) * scale * out['epv_mirror'])
    return out
