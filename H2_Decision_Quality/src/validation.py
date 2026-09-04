"""H2 Decision Quality — validation of the index.

The notebook is only an orchestrator: every check lives here so the
notebook reads as a report. Three families, matching the three things a
reviewer will ask about this index:

1. Statistical robustness — does `DQ_index` survive the arbitrary knobs?
   We refit the whole pipeline while moving, one at a time:
     - `XEPV_FAILURE_SCALE`   (the 1:1 turnover weight)
     - the minutes floor      (135 is H1's pool choice)
     - `MIN_ALTERNATIVES`     (need >=2 options for a rank)
   and report the Spearman rank correlation of the player ordering
   against the shipped index. A robust index keeps the *ordering* even
   when the level moves.

2. Construct validity — do the columns measure distinct things, and are
   the correlations we *claim* in the design the ones the data shows?
   Within-role Spearman matrix of the six headline metrics, plus the
   two head-line claims (DQ <-> Value ~0.71, accuracy <-> worst ~0.01)
   and the four-archetype population of the quadrant.

3. Face validity — does it agree with football knowledge, and where
   does the small-sample problem bite? Known decision-makers' standing,
   and the `n_decisions` -> `DQ_index` relationship that explains why a
   display-only sample floor is needed (the index/pool stay full 272).

Public API
----------
robustness_scale(alt, corpus, grid, roles, scales)   -> DataFrame
robustness_minutes(pe, roles, floors)                -> DataFrame
robustness_min_alts(alt, corpus, grid, roles, mins)  -> DataFrame
sample_size_effect(dq)                               -> dict
within_role_corr(dq, metrics)                        -> DataFrame
claimed_correlations(dq)                              -> DataFrame
quadrant_population(dq)                               -> DataFrame
face_validity(dq, names)                              -> DataFrame
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from . import decision_quality as dqm
from . import xepv as _xepv


# ---------------------------------------------------------------------------
# Helper: rank agreement of two player orderings on the shared players
# ---------------------------------------------------------------------------
def _rank_agreement(base: pd.DataFrame, other: pd.DataFrame,
                     col: str = "DQ_index") -> tuple[float, int]:
    """Spearman rho of `col` between two player tables, on shared players.

    Players are matched on (player, team). Returns (rho, n_shared).
    """
    key = ["player", "team"]
    m = base[key + [col]].merge(other[key + [col]], on=key,
                                suffixes=("_a", "_b"))
    if len(m) < 3:
        return float("nan"), len(m)
    rho, _ = spearmanr(m[f"{col}_a"], m[f"{col}_b"])
    return rho, len(m)


# ---------------------------------------------------------------------------
# 1. Statistical robustness
# ---------------------------------------------------------------------------
def robustness_scale(alt: pd.DataFrame, corpus_df: pd.DataFrame,
                      epv_grid: np.ndarray, roles: pd.DataFrame,
                      scales=(0.5, 0.75, 1.0, 1.25)) -> pd.DataFrame:
    """Refit the index at several `XEPV_FAILURE_SCALE` values.

    The shipped index uses scale = 1.0; every other scale's ordering is
    compared against it. High rho => the 1:1 turnover weight is a
    level choice, not a ranking choice (which is exactly the claim made
    to the supervisor).
    """
    rows = []
    base = None
    for s in scales:
        a = _xepv.compute_xepv(alt, epv_grid, failure_scale=s)
        pe = dqm.per_event_signals(a, corpus_df, epv_grid)
        dq = dqm.aggregate_players(pe, roles)
        if s == 1.0:
            base = dq
        rows.append((s, dq))
    out = []
    for s, dq in rows:
        rho, n = _rank_agreement(base, dq)
        out.append({"failure_scale": s, "rho_vs_shipped": round(rho, 4),
                    "n_players": n})
    return pd.DataFrame(out)


def robustness_minutes(pe: pd.DataFrame, roles: pd.DataFrame,
                        floors=(135, 200, 300)) -> pd.DataFrame:
    """Re-aggregate at stricter minutes floors.

    135 is H1's pool. Stricter floors drop low-exposure players; the
    survivors' ordering should barely move if the index is not an
    artefact of thin samples.
    """
    base = dqm.aggregate_players(pe, roles, min_minutes=135)
    out = []
    for f in floors:
        dq = dqm.aggregate_players(pe, roles, min_minutes=f)
        rho, n = _rank_agreement(base, dq)
        out.append({"minutes_floor": f, "n_players": len(dq),
                    "rho_vs_135_pool": round(rho, 4),
                    "n_shared_with_135": n})
    return pd.DataFrame(out)


def robustness_min_alts(alt: pd.DataFrame, corpus_df: pd.DataFrame,
                         epv_grid: np.ndarray, roles: pd.DataFrame,
                         mins=(2, 3, 4)) -> pd.DataFrame:
    """Tighten the "need >=k in-frame alternatives" event filter.

    `decision_quality.MIN_ALTERNATIVES` is monkey-set per run. Higher k
    keeps only events with a richer choice set; the player ordering
    should be stable if the index is not driven by trivial 2-option
    events.
    """
    original = dqm.MIN_ALTERNATIVES
    base = None
    rows = []
    try:
        for k in mins:
            dqm.MIN_ALTERNATIVES = k
            pe = dqm.per_event_signals(alt, corpus_df, epv_grid)
            dq = dqm.aggregate_players(pe, roles)
            if k == 2:
                base = dq
            rows.append((k, dq, len(pe)))
    finally:
        dqm.MIN_ALTERNATIVES = original
    out = []
    for k, dq, n_events in rows:
        rho, n = _rank_agreement(base, dq)
        out.append({"min_alternatives": k, "n_events": n_events,
                    "n_players": len(dq),
                    "rho_vs_k2": round(rho, 4)})
    return pd.DataFrame(out)


def sample_size_effect(dq: pd.DataFrame) -> dict:
    """How much does `DQ_index` ride on `n_decisions`?

    A large positive (or any strong) correlation would mean the index
    partly rewards involvement volume, not selection skill — the reason
    the page graph applies a *display-only* sample floor while the index
    and CSV stay the full pool.
    """
    rho_all, p_all = spearmanr(dq["n_decisions"], dq["DQ_index"])
    # within-role, pooled (z-style: correlate residuals from role medians)
    g = dq.groupby("macro_role")
    n_res = dq["n_decisions"] - g["n_decisions"].transform("median")
    d_res = dq["DQ_index"] - g["DQ_index"].transform("median")
    rho_wr, p_wr = spearmanr(n_res, d_res)
    low = dq[dq["n_decisions"] < 40]
    return {
        "rho_global": round(rho_all, 4), "p_global": round(p_all, 4),
        "rho_within_role": round(rho_wr, 4), "p_within_role": round(p_wr, 4),
        "n_below_40_decisions": int(len(low)),
        "share_below_40_pct": round(100 * len(low) / len(dq), 1),
        "mean_DQ_below_40": round(low["DQ_index"].mean(), 1),
        "mean_DQ_at_or_above_40":
            round(dq[dq["n_decisions"] >= 40]["DQ_index"].mean(), 1),
    }


# ---------------------------------------------------------------------------
# 2. Construct validity
# ---------------------------------------------------------------------------
# The six headline metrics, plain-language labels (mirrors viz.PCT_METRICS).
HEADLINE_METRICS = [
    ("DQ_index",          "Decision quality"),
    ("value_impact",      "Value added"),
    ("elite_per90",       "Elite reads /90"),
    ("poor_per90",        "Poor reads /90"),
    ("accuracy_pct",      "Picks best %"),
    ("worst_choice_pct",  "Picks worst %"),
]


def within_role_corr(dq: pd.DataFrame,
                     metrics=HEADLINE_METRICS) -> pd.DataFrame:
    """Within-role Spearman matrix of the headline metrics.

    Each metric is replaced by its within-`macro_role` rank before
    correlating, so the matrix is not inflated by role-level mean
    differences. This is the matrix that justifies which columns are
    redundant vs complementary on the website.
    """
    cols = [c for c, _ in metrics]
    g = dq.groupby("macro_role")
    R = pd.DataFrame(index=dq.index)
    for c in cols:
        R[c] = g[c].rank()
    M = R.corr(method="spearman")
    M.index = [lbl for _, lbl in metrics]
    M.columns = [lbl for _, lbl in metrics]
    return M.round(2)


def claimed_correlations(dq: pd.DataFrame) -> pd.DataFrame:
    """Check the two correlations the design explicitly states.

    Design claims, within-role: DQ <-> Value strong (redundant, scatter
    is diagnostic only) and Picks-best <-> Picks-worst weak (distinct
    axes, the quadrant's four boxes are all populated). This recomputes
    both so the notebook proves the numbers it asserts; `claimed_rho` is
    the value documented in viz.py / the design notes.
    """
    g = dq.groupby("macro_role")
    pairs = [
        ("DQ_index", "value_impact", "DQ_index <-> value_impact", 0.76,
         "strong -> redundant, scatter is diagnostic only"),
        ("accuracy_pct", "worst_choice_pct",
         "accuracy_pct <-> worst_choice_pct", 0.12,
         "weak -> distinct axes, quadrant boxes all populated"),
    ]
    rows = []
    for a, b, label, claimed, reading in pairs:
        ra = g[a].rank()
        rb = g[b].rank()
        rho, p = spearmanr(ra, rb)
        rows.append({"pair": label, "claimed_rho": claimed,
                     "measured_rho": round(rho, 3), "p_value": round(p, 4),
                     "n": len(dq), "reading": reading})
    return pd.DataFrame(rows)


def quadrant_population(dq: pd.DataFrame) -> pd.DataFrame:
    """Population of the four single-player-page archetypes, per role.

    Axes are within-role percentiles of accuracy_pct (X, picks best) and
    1 - worst_choice_pct rank (Y, avoids worst). Quadrants split at the
    role median (50th pct). For the archetypes to be meaningful, every
    role should put a non-trivial population in each of the four boxes
    (not all on a diagonal — which would mean one hidden axis).
    """
    g = dq.groupby("macro_role")
    x = g["accuracy_pct"].rank(pct=True) * 100
    y = (1 - g["worst_choice_pct"].rank(pct=True)) * 100
    arch = np.where((x >= 50) & (y >= 50), "ELITE",
            np.where((x < 50) & (y >= 50), "SAFE",
             np.where((x >= 50) & (y < 50), "BRILLIANT", "WEAK")))
    t = pd.crosstab(dq["macro_role"], arch)
    for c in ("ELITE", "SAFE", "BRILLIANT", "WEAK"):
        if c not in t.columns:
            t[c] = 0
    t = t[["ELITE", "SAFE", "BRILLIANT", "WEAK"]]
    t["total"] = t.sum(axis=1)
    return t


# ---------------------------------------------------------------------------
# 3. Face validity
# ---------------------------------------------------------------------------
def face_validity(dq: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    """Where do named players land in their role?

    `names` is a watch-list of widely-recognised passers/decision-makers.
    Substring match on `player` (accent/spacing tolerant is the caller's
    job — pass the dataframe's own spelling). Returns their standing so
    the reader can sanity-check the index against football knowledge,
    including `n_decisions` so small-sample placements are visible.
    """
    cols = ["player", "team", "macro_role", "minutes_played",
            "n_decisions", "DQ_index", "score", "value_impact",
            "accuracy_pct", "worst_choice_pct"]
    pat = "|".join(names)
    hit = dq[dq["player"].str.contains(pat, case=False, na=False)]
    return (hit[cols].sort_values("DQ_index", ascending=False)
                     .reset_index(drop=True))


def leaderboard_with_floor(dq: pd.DataFrame, min_n: int = 40,
                           top: int = 12) -> pd.DataFrame:
    """Top-N once tiny-sample players are removed (display-only floor).

    Shows the same leaderboard the page graph would produce: the index
    and CSV are untouched, but a reader-facing floor removes players
    with < `min_n` decisions whose percentile is dominated by variance.
    """
    cols = ["player", "team", "macro_role", "minutes_played",
            "n_decisions", "DQ_index", "score", "value_impact"]
    return (dq[dq["n_decisions"] >= min_n]
            .nlargest(top, "DQ_index")[cols].reset_index(drop=True))
