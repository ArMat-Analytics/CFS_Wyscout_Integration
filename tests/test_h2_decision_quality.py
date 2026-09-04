"""Tests for H2 decision quality functions (H2_Decision_Quality/src/decision_quality.py).
"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from H2_Decision_Quality.src.decision_quality import (
    per_event_signals,
    aggregate_players,
    build,
)


class TestH2DecisionQuality:
    def test_per_event_signals(self):
        # Create a mock alternatives DataFrame
        # event_id has 3 options (1 chosen, 2 alternatives)
        # chosen option xepv = 0.5
        # alternative 1 xepv = 0.4 (beaten)
        # alternative 2 xepv = 0.6 (not beaten)
        alt = pd.DataFrame({
            "event_id": ["ev1", "ev1", "ev1"],
            "is_chosen": [True, False, False],
            "xepv": [0.5, 0.4, 0.6],
        })

        # Mock corpus dataframe with player and team
        corpus_df = pd.DataFrame({
            "event_id": ["ev1"],
            "player": ["Alice"],
            "team": ["TeamA"],
        })

        pe = per_event_signals(alt, corpus_df, epv_grid=np.zeros((4, 6)))

        assert len(pe) == 1
        assert pe.index[0] == "ev1"
        assert pe.loc["ev1", "player"] == "Alice"
        assert pe.loc["ev1", "chosen_xepv"] == 0.5
        assert pe.loc["ev1", "n_alt"] == 2
        # score = share of alternatives <= chosen xepv.
        # Alternatives are 0.4 and 0.6. 0.4 <= 0.5 (True), 0.6 <= 0.5 (False).
        # Beaten mean = 0.5
        assert pe.loc["ev1", "score"] == 0.5
        assert pe.loc["ev1", "beat_all"] == 0
        assert pe.loc["ev1", "worst_pick"] == 0

    def test_aggregate_players(self):
        # Create a mock pe DataFrame with 4 events for 2 players
        # Alice (CB): 2 decisions, scores: 0.8, 0.9
        # Bob (CB): 2 decisions, scores: 0.4, 0.6
        pe = pd.DataFrame({
            "player": ["Alice", "Alice", "Bob", "Bob"],
            "team": ["TeamA", "TeamA", "TeamB", "TeamB"],
            "score": [0.8, 0.9, 0.4, 0.6],
            "delta_xepv": [0.1, 0.2, -0.05, 0.0],
            "beat_all": [1, 1, 0, 0],
            "worst_pick": [0, 0, 0, 1],
            "miss_cost": [np.nan, np.nan, 0.1, np.nan],
        }, index=["ev1", "ev2", "ev3", "ev4"])

        roles = pd.DataFrame({
            "player": ["Alice", "Bob"],
            "team": ["TeamA", "TeamB"],
            "primary_role": ["CB", "CB"],
            "macro_role": ["CB", "CB"],
            "minutes_played": [180, 180],
        })

        dq = aggregate_players(pe, roles, min_minutes=90)

        assert len(dq) == 2
        # Alice should have a higher score than Bob
        alice_row = dq[dq["player"] == "Alice"].iloc[0]
        bob_row = dq[dq["player"] == "Bob"].iloc[0]

        assert alice_row["score"] == pytest.approx(0.85)
        assert bob_row["score"] == pytest.approx(0.50)
        assert alice_row["DQ_index"] == 100.0  # highest score in role
        assert bob_row["DQ_index"] == 50.0

    @patch("pandas.read_csv")
    @patch("pandas.read_parquet")
    def test_build(self, mock_read_parquet, mock_read_csv):
        # Mock the build file inputs
        alt = pd.DataFrame({
            "event_id": ["ev1", "ev1", "ev1"],
            "is_chosen": [True, False, False],
            "xepv": [0.5, 0.4, 0.3],
        })
        corpus_df = pd.DataFrame({
            "event_id": ["ev1"],
            "player": ["Alice"],
            "team": ["TeamA"],
        })
        roles = pd.DataFrame({
            "player": ["Alice"],
            "team": ["TeamA"],
            "primary_role": ["CB"],
            "macro_role": ["CB"],
            "minutes_played": [180],
        })

        # Set up mock returns
        mock_read_parquet.return_value = alt
        # mock_read_csv is called twice in build: one for DQ_CORPUS_PATH, one for H1_PLAYER_AGG
        mock_read_csv.side_effect = [corpus_df, roles]

        dq = build(epv_grid=np.zeros((4, 6)), write=False)
        assert len(dq) == 1
        assert dq.loc[0, "player"] == "Alice"
        assert dq.loc[0, "DQ_index"] == 100.0
