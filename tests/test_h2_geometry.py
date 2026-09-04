"""Tests for H2 geometry helpers (H2_Decision_Quality/src/geometry.py).

All functions tested here are pure.
"""
import numpy as np

from H2_Decision_Quality.src.geometry import (
    count_opponents_within,
    count_bypassed,
)


class TestH2Geometry:
    def test_count_opponents_within(self, sample_opponents):
        center = np.array([50.0, 34.0])
        # default radius is 2.5m (or similar configured radius)
        assert count_opponents_within(center, sample_opponents, radius=2.5) == 2
        assert count_opponents_within(center, sample_opponents, radius=100.0) == 5
        assert count_opponents_within(center, np.array([]).reshape(0, 2)) == 0
        assert count_opponents_within(None, sample_opponents) == 0

    def test_count_bypassed(self):
        # Pass from (0,0) to (10,0), opponent at (5, 2) inside corridor=5
        opps = np.array([[5.0, 2.0]])
        assert count_bypassed(0, 0, 10, 0, opps, corridor_m=5.0) == 1

        # Opponent at (5, 8) outside corridor=5
        opps = np.array([[5.0, 8.0]])
        assert count_bypassed(0, 0, 10, 0, opps, corridor_m=5.0) == 0

        # Opponent behind start or beyond end
        assert count_bypassed(0, 0, 10, 0, np.array([[-2.0, 0.0]]), corridor_m=5.0) == 0
        assert count_bypassed(0, 0, 10, 0, np.array([[15.0, 0.0]]), corridor_m=5.0) == 0

        # Zero length pass
        assert count_bypassed(5, 5, 5, 5, np.array([[5, 5]]), corridor_m=5.0) == 0

        # Nan start
        assert count_bypassed(float("nan"), 0, 10, 0, np.array([[5, 0]])) == 0

        # Multiple opponents
        opps = np.array([[3, 1], [7, -1], [5, 20]])
        assert count_bypassed(0, 0, 10, 0, opps, corridor_m=5.0) == 2
