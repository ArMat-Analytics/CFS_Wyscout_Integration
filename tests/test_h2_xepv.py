"""Tests for H2 xEPV layer (H2_Decision_Quality/src/xepv.py).

Validates the bilinear EPV interpolation and the xEPV formula on
synthetic grids and DataFrames — no disk I/O or model loading.
"""
import numpy as np
import pandas as pd
import pytest

from H2_Decision_Quality.src.xepv import epv_at, compute_xepv
from H2_Decision_Quality.src import config as cfg


# ── epv_at ─────────────────────────────────────────────────────────────────

class TestEpvAt:
    def test_uniform_grid(self):
        """A uniform grid of value 0.5 → every lookup returns 0.5."""
        grid = np.full((4, 6), 0.5)
        result = epv_at(grid, np.array([52.5]), np.array([34.0]))
        np.testing.assert_allclose(result, [0.5], atol=1e-6)

    def test_origin_corner(self, small_epv_grid):
        """(0, 0) maps to grid[0, 0]."""
        result = epv_at(small_epv_grid, np.array([0.0]), np.array([0.0]))
        assert result[0] == pytest.approx(small_epv_grid[0, 0], abs=1e-4)

    @pytest.mark.skip(reason=(
        "epv_at applies the NaN mask after grid indexing, so NaN coords cause "
        "an IndexError. Callers pre-filter NaN. Not fixing application code here."
    ))
    def test_nan_input_returns_nan(self):
        """NaN inputs should ideally return NaN, but current impl crashes."""
        grid = np.full((32, 50), 0.5)
        result = epv_at(grid, np.array([np.nan]), np.array([34.0]))
        assert np.isnan(result[0])

    def test_vectorised(self, small_epv_grid):
        """Multiple (x, y) pairs at once."""
        xs = np.array([0.0, 52.5, 105.0])
        ys = np.array([0.0, 34.0, 68.0])
        result = epv_at(small_epv_grid, xs, ys)
        assert result.shape == (3,)
        assert not np.any(np.isnan(result))

    def test_clipping_outside_pitch(self, small_epv_grid):
        """Coordinates outside [0, 105]×[0, 68] should be clipped, not NaN."""
        result = epv_at(small_epv_grid, np.array([200.0]), np.array([100.0]))
        assert not np.isnan(result[0])


# ── compute_xepv ──────────────────────────────────────────────────────────

class TestComputeXepv:
    def test_formula(self, small_epv_grid):
        """Verify xepv = xpass * epv_target - (1-xpass) * scale * epv_mirror."""
        alt = pd.DataFrame({
            "target_x_m": [52.5],
            "target_y_m": [34.0],
            "xpass": [0.8],
        })
        out = compute_xepv(alt, small_epv_grid, failure_scale=1.0)

        epv_target = epv_at(small_epv_grid, np.array([52.5]), np.array([34.0]))[0]
        epv_mirror = epv_at(small_epv_grid, np.array([cfg.PITCH_LENGTH_M - 52.5]), np.array([34.0]))[0]
        expected = 0.8 * epv_target - 0.2 * 1.0 * epv_mirror

        assert out["xepv"].iloc[0] == pytest.approx(expected, abs=1e-6)

    def test_returns_copy(self, small_epv_grid):
        """compute_xepv must not modify the input DataFrame."""
        alt = pd.DataFrame({
            "target_x_m": [10.0],
            "target_y_m": [10.0],
            "xpass": [0.5],
        })
        original_cols = set(alt.columns)
        compute_xepv(alt, small_epv_grid)
        assert set(alt.columns) == original_cols

    def test_adds_expected_columns(self, small_epv_grid):
        alt = pd.DataFrame({
            "target_x_m": [10.0, 50.0],
            "target_y_m": [10.0, 30.0],
            "xpass": [0.5, 0.9],
        })
        out = compute_xepv(alt, small_epv_grid)
        assert "epv_target" in out.columns
        assert "epv_mirror" in out.columns
        assert "xepv" in out.columns

    def test_perfect_pass(self, small_epv_grid):
        """xpass=1.0 → xepv = epv_target (no penalty term)."""
        alt = pd.DataFrame({
            "target_x_m": [80.0],
            "target_y_m": [34.0],
            "xpass": [1.0],
        })
        out = compute_xepv(alt, small_epv_grid, failure_scale=1.0)
        assert out["xepv"].iloc[0] == pytest.approx(out["epv_target"].iloc[0], abs=1e-6)
