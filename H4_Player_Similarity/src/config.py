"""
config.py — H4 Player Similarity
Paths, the DNA feature definition, and the shared loaders for the H4 pipeline.

Path layout assumed on disk:
    Contextual-Football-Scouting/                 <- REPO_ROOT
        H1_Space_Control_and_Value/data/...       <- H1 indices CSV
        H2_Decision_Quality/data/...              <- H2 decision-quality CSV
        H3_Off_Ball_Movement/data/...             <- H3 URS CSV
        H4_Player_Similarity/
            src/config.py                         <- this file

H4 is the lightest pipeline of the four: it consumes the *committed output
CSVs* of H1, H2 and H3 (one row per player, already within-role percentiles)
and never re-runs any heavy computation. There are therefore no StatsBomb
pulls and no model loaders here — only file paths and the DNA definition.
"""
from __future__ import annotations
from pathlib import Path

# ── Repo layout ────────────────────────────────────────────────────────────────
H4_DIR    = Path(__file__).resolve().parents[1]          # H4_Player_Similarity/
REPO_ROOT = H4_DIR.parent                                # Contextual-Football-Scouting/

H1_INDICES = REPO_ROOT / "H1_Space_Control_and_Value" / "data" / "player_space_control_indices.csv"
H2_DQ      = REPO_ROOT / "H2_Decision_Quality"         / "data" / "player_decision_quality.csv"
H3_URS     = REPO_ROOT / "H3_Off_Ball_Movement"        / "data" / "player_urs_aggregated.csv"

# Transfermarkt market values (optional, for the value-arbitrage use case).
# The mapping ties StatsBomb (player, team) to the Transfermarkt player_id;
# player_data_clean already carries the pre- and post-Euro market values.
TM_MAPPING    = REPO_ROOT / "webapp" / "data" / "space_control_value" / "sc_player_mapping.json"
TM_PLAYER_DATA = REPO_ROOT / "webapp" / "data" / "data_clean" / "player_data_clean.csv"

# ── Output ────────────────────────────────────────────────────────────────────
DATA_DIR       = H4_DIR / "data"
DNA_PATH       = DATA_DIR / "player_dna.csv"           # one row per player, the 11 DNA axes
SIMILARITY_PATH = DATA_DIR / "player_similarity.csv"   # long table: source, neighbour, score

# ── The DNA: 11 style axes, all within-role percentiles (0–100) ───────────────
#
# Inclusion criterion: keep the *component axes* each study exposes on its radar,
# and exclude the headline aggregates (H2's DQ_index, H3's urs_per90 / its
# percentile) because they are functions — a rank, or the product Potential ×
# Latency — of axes already in the vector, hence redundant by construction.
# Dangerousness is kept: it is a distinct H1 index, not a function of the other
# axes, so it is not redundant with them.
#
# All three studies share H1's 272-player pool joined on (player, team), so the
# DNA has no missing players. Any stray NaN on an axis is filled with the
# within-role median before distances are computed.

H1_AXES = [
    "idx__PROGRESSION",
    "idx__DANGEROUSNESS",
    "idx__RECEPTION",
    "idx__GRAVITY",
]
H2_AXES = [
    "pct__accuracy",        # Picks the best
    "pct__worst_choice",    # Avoids the worst (already mirrored upstream)
    "pct__elite_per90",     # Elite reads / 90
    "pct__poor_per90",      # Avoids poor / 90 (already mirrored upstream)
]
H3_AXES = [
    "potential_pct_within_role",   # Off-Ball Potential
    "xepv_mean_pct_within_role",   # xEPV mean
    "latency_pct_within_role",     # Latency
]
DNA_AXES = H1_AXES + H2_AXES + H3_AXES   # 11 axes

# Human-readable labels for the radar / outputs, in DNA_AXES order.
DNA_LABELS = [
    "Progression", "Dangerousness", "Reception", "Gravity",
    "Picks best", "Avoids worst", "Elite reads/90", "Avoids poor/90",
    "Off-Ball Potential", "xEPV mean", "Latency",
]

# Default neighbour count for compact *notebook* views (face validity, charts).
# The shipped similarity CSV stores ALL within-role pairs (build(top_k=None)),
# so the website can rank and page through every same-role candidate.
TOP_K = 10

# Identity / join keys and the role column.
KEY        = ["player", "team"]
ROLE_COL   = "macro_role"
