"""Tests for H4 similarity functions (H4_Player_Similarity/src/similarity.py).

Tests the pure scoring / distance functions, money parser, and all pipeline/loading logic.
"""
import json
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from H4_Player_Similarity.src.similarity import (
    similarity_score,
    _parse_money,
    _distances,
    load_dna,
    load_display_names,
    load_market_values,
    neighbours,
    build_similarity_table,
    axis_redundancy,
    build,
)
from H4_Player_Similarity.src import config as cfg


# ── similarity_score ───────────────────────────────────────────────────────

class TestSimilarityScore:
    def test_identical_vectors(self):
        """Distance = 0 → score = 100."""
        assert similarity_score(np.array([0.0]), n_axes=11)[0] == pytest.approx(100.0)

    def test_max_distance(self):
        """Distance = sqrt(n_axes) * 100 → score = 0."""
        d_max = np.sqrt(11) * 100.0
        assert similarity_score(np.array([d_max]), n_axes=11)[0] == pytest.approx(0.0)

    def test_half_distance(self):
        """Distance = half of max → score = 50."""
        d_half = np.sqrt(11) * 100.0 / 2.0
        assert similarity_score(np.array([d_half]), n_axes=11)[0] == pytest.approx(50.0)

    def test_vectorised(self):
        dists = np.array([0.0, np.sqrt(11) * 50.0, np.sqrt(11) * 100.0])
        scores = similarity_score(dists, n_axes=11)
        assert scores.shape == (3,)
        assert scores[0] > scores[1] > scores[2]


# ── _parse_money ───────────────────────────────────────────────────────────

class TestParseMoney:
    def test_millions_dot_decimal(self):
        assert _parse_money("€80.00M") == pytest.approx(80_000_000.0)

    def test_millions_comma_decimal(self):
        assert _parse_money("€18,00M") == pytest.approx(18_000_000.0)

    def test_thousands(self):
        assert _parse_money("€300,00K") == pytest.approx(300_000.0)

    def test_no_suffix(self):
        """Plain numeric string with currency symbol."""
        assert _parse_money("€500") == pytest.approx(500.0)

    def test_non_string_returns_nan(self):
        assert np.isnan(_parse_money(None))
        assert np.isnan(_parse_money(42))

    def test_empty_string(self):
        assert np.isnan(_parse_money(""))

    def test_complex_format(self):
        """'€1.50M' → 1,500,000."""
        assert _parse_money("€1.50M") == pytest.approx(1_500_000.0)


# ── _distances (euclidean) ─────────────────────────────────────────────────

class TestDistances:
    def test_euclidean_zero(self):
        mat = np.array([[1.0, 2.0, 3.0]])
        vec = np.array([1.0, 2.0, 3.0])
        d = _distances(mat, vec, "euclidean")
        assert d[0] == pytest.approx(0.0)

    def test_euclidean_known(self):
        """Distance from (0,0,0) to (3,4,0) = 5."""
        mat = np.array([[3.0, 4.0, 0.0]])
        vec = np.array([0.0, 0.0, 0.0])
        d = _distances(mat, vec, "euclidean")
        assert d[0] == pytest.approx(5.0)

    def test_cosine_identical(self):
        """Cosine distance between identical vectors = 0."""
        mat = np.array([[1.0, 2.0, 3.0]])
        vec = np.array([1.0, 2.0, 3.0])
        d = _distances(mat, vec, "cosine")
        assert d[0] == pytest.approx(0.0, abs=1e-6)

    def test_unknown_metric_raises(self):
        with pytest.raises(ValueError, match="unknown metric"):
            _distances(np.array([[1, 2]]), np.array([1, 2]), "manhattan")


# ── Pipeline / Loading Tests ────────────────────────────────────────────────

class TestH4Pipeline:
    @patch("H4_Player_Similarity.src.similarity.load_display_names")
    @patch("pandas.read_csv")
    def test_load_dna(self, mock_read_csv, mock_load_display_names):
        # Create mock dataframes for H1, H2, and H3
        players = ["Alice", "Bob"]
        teams = ["TeamA", "TeamB"]
        roles = ["CB", "CB"]

        h1_df = pd.DataFrame({
            "player": players,
            "team": teams,
            "macro_role": roles,
            "idx__PROGRESSION": [1.0, 2.0],
            "idx__DANGEROUSNESS": [2.0, 3.0],
            "idx__RECEPTION": [3.0, 4.0],
            "idx__GRAVITY": [4.0, 5.0],
        })

        h2_df = pd.DataFrame({
            "player": players,
            "team": teams,
            "pct__accuracy": [50.0, 60.0],
            "pct__worst_choice": [60.0, 70.0],
            "pct__elite_per90": [70.0, 80.0],
            "pct__poor_per90": [80.0, 90.0],
        })

        h3_df = pd.DataFrame({
            "player": players,
            "team": teams,
            "potential_pct_within_role": [10.0, 20.0],
            "xepv_mean_pct_within_role": [20.0, 30.0],
            "latency_pct_within_role": [30.0, 40.0],
        })

        # Mock side effects for pd.read_csv
        mock_read_csv.side_effect = [h1_df, h2_df, h3_df]
        mock_load_display_names.return_value = None

        dna = load_dna()

        assert len(dna) == 2
        assert "idx__PROGRESSION" in dna.columns
        # Bob > Alice on idx__PROGRESSION, so Bob's percentile should be higher
        assert dna.loc[1, "idx__PROGRESSION"] > dna.loc[0, "idx__PROGRESSION"]

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    @patch("pandas.read_csv")
    def test_load_display_names(self, mock_read_csv, mock_read_text, mock_exists):
        # exists should return True for both files
        mock_exists.return_value = True

        # json mappings: db_player_id mapping to sc_player / sc_team
        mock_read_text.return_value = json.dumps([
            {"db_player_id": 123, "sc_player": "Alice", "sc_team": "TeamA"}
        ])

        # player details CSV: player_id mapping to player_name
        mock_read_csv.return_value = pd.DataFrame({
            "player_id": [123],
            "player_name": ["Alicia"],
        })

        names = load_display_names()
        assert names is not None
        assert len(names) == 1
        assert names.loc[0, "player"] == "Alice"
        assert names.loc[0, "display"] == "Alicia"

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    @patch("pandas.read_csv")
    def test_load_market_values(self, mock_read_csv, mock_read_text, mock_exists):
        mock_exists.return_value = True

        mock_read_text.return_value = json.dumps([
            {"db_player_id": 123, "sc_player": "Alice", "sc_team": "TeamA"}
        ])

        mock_read_csv.return_value = pd.DataFrame({
            "player_id": [123],
            "market_value_before_euros": ["€80.00M"],
            "market_value_after_euros": ["€90.00M"],
        })

        mv = load_market_values()
        assert mv is not None
        assert len(mv) == 1
        assert mv.loc[0, "player"] == "Alice"
        assert mv.loc[0, "mv_pre"] == pytest.approx(80_000_000.0)
        assert mv.loc[0, "mv_post"] == pytest.approx(90_000_000.0)

    def test_neighbours(self):
        # Create a mock DNA DataFrame
        dna = pd.DataFrame({
            "player": ["Alice", "Bob", "Carol"],
            "display": ["Alice", "Bob", "Carol"],
            "team": ["TeamA", "TeamB", "TeamC"],
            "macro_role": ["CB", "CB", "CB"],
        })
        for c in cfg.DNA_AXES:
            # Alice: 50 for all axes
            # Bob: 51 for all axes (close to Alice)
            # Carol: 99 for all axes (far from Alice)
            dna[c] = [50.0, 51.0, 99.0]

        # Find neighbours for Alice
        nb = neighbours(dna, player="Alice")
        assert len(nb) == 2  # excludes Alice
        assert nb.loc[0, "player"] == "Bob"  # Bob is closer than Carol
        assert nb.loc[0, "similarity"] > nb.loc[1, "similarity"]

        # Test with top_k = 1
        nb_top = neighbours(dna, player="Alice", top_k=1)
        assert len(nb_top) == 1
        assert nb_top.loc[0, "player"] == "Bob"

        # Test case-insensitive substring match
        nb_sub = neighbours(dna, player="alice")
        assert len(nb_sub) == 2

    def test_build_similarity_table(self):
        dna = pd.DataFrame({
            "player": ["Alice", "Bob"],
            "display": ["Alice", "Bob"],
            "team": ["TeamA", "TeamB"],
            "macro_role": ["CB", "CB"],
        })
        for c in cfg.DNA_AXES:
            dna[c] = [50.0, 60.0]

        sim = build_similarity_table(dna, top_k=1)
        assert len(sim) == 2
        assert "source_player" in sim.columns
        assert "neighbour_player" in sim.columns
        assert "similarity" in sim.columns

    def test_axis_redundancy(self):
        dna = pd.DataFrame({
            "player": ["Alice", "Bob", "Carol"],
            "team": ["TeamA", "TeamB", "TeamC"],
            "macro_role": ["CB", "CB", "CB"],
        })
        for c in cfg.DNA_AXES:
            dna[c] = [50.0, 60.0, 70.0]

        red = axis_redundancy(dna)
        assert red.shape == (len(cfg.DNA_AXES), len(cfg.DNA_AXES))

    @patch("H4_Player_Similarity.src.similarity.build_similarity_table")
    @patch("H4_Player_Similarity.src.similarity.load_dna")
    @patch("pandas.DataFrame.to_csv")
    @patch("pathlib.Path.mkdir")
    def test_build(self, mock_mkdir, mock_to_csv, mock_load_dna, mock_build_sim):
        mock_load_dna.return_value = pd.DataFrame({"player": ["Alice"]})
        mock_build_sim.return_value = pd.DataFrame({"source_player": ["Alice"]})

        dna, sim = build(write=True)
        assert mock_load_dna.called
        assert mock_build_sim.called
        assert mock_to_csv.called
