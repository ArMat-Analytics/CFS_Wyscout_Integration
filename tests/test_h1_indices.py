"""Tests for H1 composite-index functions (H1_Space_Control_and_Value/src/indices.py).
"""
import numpy as np
import pandas as pd
from unittest.mock import patch

from H1_Space_Control_and_Value.src.indices import (
    load_player_table,
    build_pct_table,
    percentile_matrix,
    RADAR_SPECS,
    DANGEROUSNESS_HEADLINE_VAR,
)


class TestH1Indices:
    @patch("pandas.read_csv")
    def test_load_player_table(self, mock_read_csv):
        # Mock dataframe representing player_space_control_aggregated.csv
        mock_df = pd.DataFrame({
            "player": ["Alice", "Bob"],
            "team": ["TeamA", "TeamB"],
            "minutes_played": [100, 200],
            "gravity_directional_m": [2.5, -1.5],
        })
        mock_read_csv.return_value = mock_df

        # Case 1: no minutes filter
        df = load_player_table(min_minutes=0)
        assert len(df) == 2
        assert "gravity_abs_m" in df.columns
        np.testing.assert_allclose(df["gravity_abs_m"], [2.5, 1.5])

        # Case 2: minutes filter
        df_filtered = load_player_table(min_minutes=150)
        assert len(df_filtered) == 1
        assert df_filtered.loc[0, "player"] == "Bob"

    def test_build_pct_table(self, sample_player_df):
        # We need to add gravity_abs_m since it's used in RADAR_SPECS but computed in load_player_table
        df = sample_player_df.copy()
        df["gravity_abs_m"] = df["gravity_directional_m"].abs()

        df_out, pct = build_pct_table(df)

        # check that original df is returned or similar
        assert df_out is df

        # check shape and columns of pct table
        assert pct.shape[0] == df.shape[0]
        # check that pct contains role columns
        for col in ["player", "team", "primary_role", "macro_role", "minutes_played"]:
            assert col in pct.columns

        # check percentile and index columns are present
        assert f"{DANGEROUSNESS_HEADLINE_VAR}__p" in pct.columns
        assert "PROGRESSION_idx" in pct.columns
        assert "DANGEROUSNESS_idx" in pct.columns
        assert "RECEPTION_idx" in pct.columns
        assert "GRAVITY_idx" in pct.columns

        # check mock percentile calculation for DANGEROUSNESS_idx (percentile of epv_added_per90)
        # Alice (0.5), Bob (0.8) are CBs. Bob > Alice, so Bob should have higher percentile
        cb_pcts = pct[pct["macro_role"] == "CB"].set_index("player")
        assert cb_pcts.loc["Bob", f"{DANGEROUSNESS_HEADLINE_VAR}__p"] > cb_pcts.loc["Alice", f"{DANGEROUSNESS_HEADLINE_VAR}__p"]

    def test_percentile_matrix(self, sample_player_df):
        df = sample_player_df.copy()
        df["gravity_abs_m"] = df["gravity_directional_m"].abs()
        _, pct = build_pct_table(df)

        mat = percentile_matrix(pct)
        all_vars = list({v for spec in RADAR_SPECS.values() for _, v, _ in spec})

        assert isinstance(mat, np.ndarray)
        assert mat.shape == (len(pct), len(all_vars))
