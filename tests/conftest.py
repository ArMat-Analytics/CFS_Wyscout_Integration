"""Shared fixtures for the test suite.

Provides lightweight synthetic data so tests can exercise the pure
analytics functions without needing the full StatsBomb dataset or a
database connection.
"""
import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def small_epv_grid():
    """A tiny 4×6 EPV grid (rows=Y, cols=X) with linearly increasing values.

    Values go from 0.0 (top-left, defensive) to ~1.0 (bottom-right, attacking).
    This makes EPV lookups predictable for testing.
    """
    rows, cols = 4, 6
    grid = np.linspace(0.0, 1.0, rows * cols).reshape(rows, cols)
    return grid


@pytest.fixture
def sample_opponents():
    """Five opponent positions on a 105×68 pitch (in meters)."""
    return np.array([
        [50.0, 34.0],   # center
        [52.0, 34.0],   # 2m right of center
        [55.0, 34.0],   # 5m right of center
        [80.0, 20.0],   # far right
        [20.0, 60.0],   # far left-back
    ])


@pytest.fixture
def triangle_points():
    """Three points forming a right triangle with known area.

    Vertices: (0,0), (10,0), (0,10) → area = 50 m².
    """
    return np.array([
        [0.0, 0.0],
        [10.0, 0.0],
        [0.0, 10.0],
    ])


@pytest.fixture
def sample_player_df():
    """Minimal DataFrame mimicking H1's player_space_control_aggregated.csv.

    Four players across two macro_roles with synthetic per-90 stats.
    Used for testing the percentile/index pipeline.
    """
    return pd.DataFrame({
        "player": ["Alice", "Bob", "Carol", "Dave"],
        "team": ["TeamA", "TeamA", "TeamB", "TeamB"],
        "primary_role": ["CB", "CB", "FW", "FW"],
        "macro_role": ["CB", "CB", "FW", "FW"],
        "minutes_played": [270, 300, 200, 250],
        "epv_added_per90": [0.5, 0.8, 1.2, 0.3],
        "lb_geom_per90": [2.0, 3.0, 4.0, 1.0],
        "lb_quality_per90": [1.5, 2.5, 3.0, 1.0],
        "lb_epv_per90": [0.3, 0.6, 0.9, 0.2],
        "successful_hull_penetrations_per90": [1.0, 2.0, 3.0, 0.5],
        "defenders_bypassed_mean": [1.5, 2.0, 2.5, 1.0],
        "epv_penetration_per90": [0.1, 0.2, 0.4, 0.05],
        "epv_inside_circ_per90": [0.1, 0.15, 0.3, 0.1],
        "epv_exit_per90": [0.05, 0.1, 0.2, 0.05],
        "epv_outside_circ_per90": [0.05, 0.1, 0.1, 0.05],
        "between_lines_pct": [40.0, 55.0, 70.0, 30.0],
        "successful_hull_exits_per90": [1.0, 1.5, 2.0, 0.5],
        "pressure_resistance_pct": [60.0, 70.0, 80.0, 50.0],
        "gravity_proximity_pct": [30.0, 45.0, 60.0, 25.0],
        "gravity_hull_pct": [20.0, 35.0, 50.0, 15.0],
        "gravity_directional_m": [2.0, -3.0, 5.0, -1.0],
    })
