"""Tests for H1 geometry helpers (H1_Space_Control_and_Value/src/geometry.py).

All functions tested here are pure: they take numpy arrays and return
scalars or arrays, with no I/O or database dependencies.
"""
import numpy as np
import pytest

from H1_Space_Control_and_Value.src.geometry import (
    to_meters,
    hull_area,
    is_inside_hull,
    count_opponents_within,
    mean_dist_k_nearest,
    count_bypassed,
    get_zone,
)
from H1_Space_Control_and_Value.src import config


# ── to_meters ──────────────────────────────────────────────────────────────

class TestToMeters:
    def test_origin(self):
        result = to_meters([0.0, 0.0])
        np.testing.assert_allclose(result, [0.0, 0.0])

    def test_full_pitch(self):
        """StatsBomb (120, 80) should map to UEFA (105, 68)."""
        result = to_meters([120.0, 80.0])
        np.testing.assert_allclose(result, [105.0, 68.0])

    def test_center_spot(self):
        result = to_meters([60.0, 40.0])
        np.testing.assert_allclose(result, [52.5, 34.0])

    def test_none_returns_none(self):
        assert to_meters(None) is None

    def test_nan_returns_none(self):
        assert to_meters(float("nan")) is None


# ── hull_area ──────────────────────────────────────────────────────────────

class TestHullArea:
    def test_right_triangle(self, triangle_points):
        """Right triangle (0,0)-(10,0)-(0,10) → area = 50 m²."""
        area = hull_area(triangle_points)
        assert pytest.approx(area, abs=1e-6) == 50.0

    def test_square(self):
        pts = np.array([[0, 0], [10, 0], [10, 10], [0, 10]])
        assert pytest.approx(hull_area(pts), abs=1e-6) == 100.0

    def test_fewer_than_3_points(self):
        assert np.isnan(hull_area(np.array([[0, 0], [1, 1]])))

    def test_collinear_points(self):
        """Collinear points have zero-area hull — scipy raises QhullError."""
        result = hull_area(np.array([[0, 0], [5, 0], [10, 0]]))
        assert np.isnan(result)


# ── is_inside_hull ─────────────────────────────────────────────────────────

class TestIsInsideHull:
    def test_point_inside(self, triangle_points):
        assert is_inside_hull(triangle_points, np.array([2.0, 2.0]))

    def test_point_outside(self, triangle_points):
        assert not is_inside_hull(triangle_points, np.array([20.0, 20.0]))

    def test_none_point(self, triangle_points):
        assert not is_inside_hull(triangle_points, None)

    def test_too_few_hull_points(self):
        assert not is_inside_hull(np.array([[0, 0], [1, 1]]), np.array([0.5, 0.5]))


# ── count_opponents_within ─────────────────────────────────────────────────

class TestCountOpponentsWithin:
    def test_known_distances(self, sample_opponents):
        """Center point (50, 34): opponents at 0m, 2m, 5m, ~32m, ~39m."""
        center = np.array([50.0, 34.0])
        # default radius = 2.5 m → should catch the first two (at 0m and 2m)
        assert count_opponents_within(center, sample_opponents, radius=2.5) == 2

    def test_large_radius(self, sample_opponents):
        center = np.array([50.0, 34.0])
        assert count_opponents_within(center, sample_opponents, radius=100.0) == 5

    def test_empty_opponents(self):
        assert count_opponents_within(np.array([50, 34]), np.array([]).reshape(0, 2)) == 0

    def test_none_point(self, sample_opponents):
        assert count_opponents_within(None, sample_opponents) == 0


# ── mean_dist_k_nearest ───────────────────────────────────────────────────

class TestMeanDistKNearest:
    def test_exact_distances(self):
        point = np.array([0.0, 0.0])
        opps = np.array([[3.0, 0.0], [4.0, 0.0], [10.0, 0.0]])
        # k=2 → mean of (3, 4) = 3.5
        assert pytest.approx(mean_dist_k_nearest(point, opps, k=2)) == 3.5

    def test_k_larger_than_n(self):
        point = np.array([0.0, 0.0])
        opps = np.array([[3.0, 0.0]])
        # k=4 but only 1 opponent → use all → mean = 3.0
        assert pytest.approx(mean_dist_k_nearest(point, opps, k=4)) == 3.0

    def test_empty_opponents(self):
        assert np.isnan(mean_dist_k_nearest(np.array([0, 0]), np.array([]).reshape(0, 2)))

    def test_none_point(self):
        assert np.isnan(mean_dist_k_nearest(None, np.array([[1, 1]])))


# ── count_bypassed ─────────────────────────────────────────────────────────

class TestCountBypassed:
    def test_opponent_in_corridor(self):
        """Pass from (0,0) to (10,0), opponent at (5, 2) with corridor=5 → inside."""
        opps = np.array([[5.0, 2.0]])
        assert count_bypassed(0, 0, 10, 0, opps, corridor_m=5.0) == 1

    def test_opponent_outside_corridor(self):
        """Opponent at (5, 8) with corridor=5 → outside."""
        opps = np.array([[5.0, 8.0]])
        assert count_bypassed(0, 0, 10, 0, opps, corridor_m=5.0) == 0

    def test_opponent_behind_start(self):
        """Opponent at (-2, 0) is behind the pass start → not bypassed."""
        opps = np.array([[-2.0, 0.0]])
        assert count_bypassed(0, 0, 10, 0, opps, corridor_m=5.0) == 0

    def test_opponent_beyond_end(self):
        """Opponent at (15, 0) is beyond the pass end → not bypassed."""
        opps = np.array([[15.0, 0.0]])
        assert count_bypassed(0, 0, 10, 0, opps, corridor_m=5.0) == 0

    def test_zero_length_pass(self):
        assert count_bypassed(5, 5, 5, 5, np.array([[5, 5]]), corridor_m=5.0) == 0

    def test_nan_start(self):
        assert count_bypassed(float("nan"), 0, 10, 0, np.array([[5, 0]])) == 0

    def test_multiple_opponents(self):
        """Two inside corridor, one outside."""
        opps = np.array([[3, 1], [7, -1], [5, 20]])
        assert count_bypassed(0, 0, 10, 0, opps, corridor_m=5.0) == 2


# ── get_zone ───────────────────────────────────────────────────────────────

class TestGetZone:
    def test_origin(self):
        assert get_zone(np.array([0.0, 0.0])) == (0, 0)

    def test_center(self):
        zx, zy = get_zone(np.array([52.5, 34.0]))
        assert 0 <= zx < config.ZONE_X_BINS
        assert 0 <= zy < config.ZONE_Y_BINS

    def test_far_corner(self):
        """Point at (105, 68) should clip to (ZONE_X_BINS-1, ZONE_Y_BINS-1)."""
        zx, zy = get_zone(np.array([105.0, 68.0]))
        assert zx == config.ZONE_X_BINS - 1
        assert zy == config.ZONE_Y_BINS - 1

    def test_none_returns_none(self):
        assert get_zone(None) is None
