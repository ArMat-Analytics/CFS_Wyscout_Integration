"""Tests for H1 config (H1_Space_Control_and_Value/src/config.py).

Validates the role mapping logic and the consistency of the role
taxonomy — the part of config.py that is pure logic rather than
file-path declarations.
"""
from H1_Space_Control_and_Value.src.config import (
    map_role,
    ROLE_MAP,
    ROLE_REMAP,
    MACRO_ROLES,
    X_SCALE,
    Y_SCALE,
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
)


# ── map_role ───────────────────────────────────────────────────────────────

class TestMapRole:
    def test_goalkeeper(self):
        assert map_role("Goalkeeper") == "GK"

    def test_right_back(self):
        assert map_role("Right Back") == "FB"

    def test_left_wing(self):
        assert map_role("Left Wing") == "W"

    def test_center_forward(self):
        assert map_role("Center Forward") == "FW"

    def test_center_midfield(self):
        assert map_role("Center Midfield") == "CM"

    def test_unknown_position(self):
        assert map_role("Invented Position") == "OTHER"

    def test_none_as_string(self):
        """map_role converts to str first, so None → 'None' → 'OTHER'."""
        assert map_role(None) == "OTHER"


# ── Scale constants ────────────────────────────────────────────────────────

class TestScaleConstants:
    def test_x_scale(self):
        """X_SCALE = 105 / 120 = 0.875."""
        assert X_SCALE == PITCH_LENGTH_M / 120.0

    def test_y_scale(self):
        """Y_SCALE = 68 / 80 = 0.85."""
        assert Y_SCALE == PITCH_WIDTH_M / 80.0


# ── Role taxonomy consistency ──────────────────────────────────────────────

class TestRoleTaxonomy:
    def test_all_role_map_values_are_known(self):
        """Every raw role in ROLE_MAP maps to a value that, after ROLE_REMAP,
        is either in MACRO_ROLES or is 'GK'."""
        for pos, raw_role in ROLE_MAP.items():
            final = ROLE_REMAP.get(raw_role, raw_role)
            assert final in MACRO_ROLES or final == "GK", (
                f"Position {pos!r} maps to {raw_role!r} → {final!r}, "
                f"which is not in MACRO_ROLES or 'GK'"
            )

    def test_remap_targets_are_in_macro_roles(self):
        """Every value in ROLE_REMAP should be one of the MACRO_ROLES."""
        for src, dst in ROLE_REMAP.items():
            assert dst in MACRO_ROLES, (
                f"ROLE_REMAP[{src!r}] = {dst!r}, not in MACRO_ROLES"
            )
